import { useEffect, useRef, useState } from 'react'

const GENRES = ['映像', '音楽', 'ゲーム', 'テキスト', '体験', 'ラジオ', 'その他']

// 検索APIはLambdaの応答サイズ上限(6MB)対策として、gzip圧縮したJSONをBase64文字列で返す。
// （API GatewayのBinaryMediaTypesはCORSプリフライトを壊すため使わず、ここで手動展開する）
async function decodeGzipBase64Json(base64Text) {
  const binary = Uint8Array.from(atob(base64Text), (c) => c.charCodeAt(0))
  const stream = new Blob([binary]).stream().pipeThrough(new DecompressionStream('gzip'))
  const text = await new Response(stream).text()
  return JSON.parse(text)
}

// このアイテム（またはlinks配列内の1件）にEmbedPreviewで表示できる内容があるかどうか
function hasEmbeddableContent(item) {
  return Boolean(item.embed_html || item.og_title || item.og_description || item.og_image)
}

// YouTubeのような「動画」埋め込みかどうか。Spotify/SoundCloud等の
// コンパクトなプレイヤー型埋め込みは16:9を強制すると高さが崩れるため区別する
function isVideoEmbed(item) {
  return Boolean(item.url && (item.url.includes('youtube.com') || item.url.includes('youtu.be')))
}

// oEmbedのiframeにネイティブ遅延読み込み属性を付与する（未指定の場合のみ）
function withLazyLoading(html) {
  if (!html) return html
  if (/<iframe\b[^>]*\bloading=/i.test(html)) return html
  return html.replace(/<iframe\b/i, '<iframe loading="lazy"')
}

// IntersectionObserverで画面に近づくまで子要素の実体をマウントしない。
// スマートフォンで1ページあたり多数のYouTube/Spotify埋め込みiframeが
// 一斉に読み込まれて重くなる問題への対策（一度表示されたら以後はマウントを維持する）。
function LazyMount({ placeholderClassName, children }) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (visible || !ref.current) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: '300px' }
    )
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [visible])

  if (visible) {
    return children
  }

  return <div ref={ref} className={placeholderClassName} />
}

// oEmbed(embed_html)があればそれを埋め込み表示、無ければOGP情報で簡易プレビューカードを表示。
// どちらも無ければ何も表示しない。embed_htmlはYouTube/Spotify/SoundCloud等、
// 許可リスト化された信頼できるサービスのoEmbed応答のみが入る想定。
function EmbedPreview({ item }) {
  if (item.embed_html) {
    const embedClassName = isVideoEmbed(item)
      ? "mb-3 [&_iframe]:w-full [&_iframe]:h-auto [&_iframe]:aspect-video"
      : "mb-3 [&_iframe]:w-full"
    return (
      <div
        className={embedClassName}
        dangerouslySetInnerHTML={{ __html: withLazyLoading(item.embed_html) }}
      />
    )
  }

  if (item.og_title || item.og_description || item.og_image) {
    return (
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mb-3 flex gap-3 border border-gray-200 rounded overflow-hidden hover:bg-gray-50 transition"
      >
        {item.og_image && (
          <img src={item.og_image} alt="" loading="lazy" className="w-28 h-28 object-cover flex-shrink-0" />
        )}
        <div className="p-2 overflow-hidden">
          {item.og_title && <p className="font-bold text-sm text-gray-800 truncate">{item.og_title}</p>}
          {item.og_description && (
            <p className="text-xs text-gray-500 line-clamp-2">{item.og_description}</p>
          )}
        </div>
      </a>
    )
  }

  return null
}

// 埋め込み内容の種類に応じたプレースホルダーの見た目（レイアウトシフトを抑えるための概算サイズ）
function embedPlaceholderClassName(item) {
  if (item.embed_html) {
    return isVideoEmbed(item)
      ? "mb-3 aspect-video bg-gray-100 rounded animate-pulse"
      : "mb-3 h-40 bg-gray-100 rounded animate-pulse"
  }
  return "mb-3 h-28 bg-gray-100 rounded animate-pulse"
}

function PaginationControls({ page, totalPages, onPrev, onNext }) {
  return (
    <div className="flex items-center justify-center gap-4 text-sm text-gray-600">
      <button
        type="button"
        onClick={onPrev}
        disabled={page <= 1}
        className="px-3 py-1 rounded border border-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-100"
      >
        ← 前へ
      </button>
      <span>ページ {page} / {totalPages}</span>
      <button
        type="button"
        onClick={onNext}
        disabled={page >= totalPages}
        className="px-3 py-1 rounded border border-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-100"
      >
        次へ →
      </button>
    </div>
  )
}

const PAGE_SIZE = 50

function App() {
  // 認証用の状態
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [passwordInput, setPasswordInput] = useState('')

  // データ用の状態
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(false)

  // 検索・フィルタ用の状態
  // searchInputは検索ボックスの表示値（IME変換中の未確定文字列も含む）、
  // searchTextはフィルタ判定に使う確定値。IME変換中はsearchTextを更新しないことで、
  // 変換確定前の文字列で一覧が何度もちらつくのを防ぐ。
  const [searchInput, setSearchInput] = useState('')
  const [searchText, setSearchText] = useState('')
  const isComposingRef = useRef(false)
  const [selectedGenres, setSelectedGenres] = useState([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [currentPage, setCurrentPage] = useState(1)

  const toggleGenre = (genre) => {
    setSelectedGenres((prev) =>
      prev.includes(genre) ? prev.filter((g) => g !== genre) : [...prev, genre]
    )
    setCurrentPage(1)
  }

  const hasActiveFilters = searchInput !== '' || selectedGenres.length > 0 || dateFrom !== '' || dateTo !== ''

  const clearAllFilters = () => {
    setSearchInput('')
    setSearchText('')
    setSelectedGenres([])
    setDateFrom('')
    setDateTo('')
    setCurrentPage(1)
  }

  const filteredReviews = reviews.filter((item) => {
    const matchesGenre = selectedGenres.length === 0 || selectedGenres.includes(item.genre)
    const searchTarget = `${item.title}${item.impression}${(item.tags || []).join(' ')}`.toLowerCase()
    const matchesText = searchText === '' || searchTarget.includes(searchText.toLowerCase())
    const matchesDateFrom = dateFrom === '' || item.review_date >= dateFrom
    const matchesDateTo = dateTo === '' || item.review_date <= dateTo
    return matchesGenre && matchesText && matchesDateFrom && matchesDateTo
  })

  const totalPages = Math.max(1, Math.ceil(filteredReviews.length / PAGE_SIZE))
  const currentPageSafe = Math.min(currentPage, totalPages)
  const pagedReviews = filteredReviews.slice(
    (currentPageSafe - 1) * PAGE_SIZE,
    currentPageSafe * PAGE_SIZE
  )
  const goToPrevPage = () => setCurrentPage((p) => Math.max(1, p - 1))
  const goToNextPage = () => setCurrentPage((p) => Math.min(totalPages, p + 1))

  const API_URL = import.meta.env.VITE_API_URL

  // 入力された合言葉をAuthorizationヘッダーとしてAPIに送り、
  // サーバー側（Lambda Authorizer）で照合する。合言葉はstateにのみ保持し、
  // ブラウザには永続化しない。
  const handleLogin = (e) => {
    e.preventDefault()
    setLoading(true)

    fetch(API_URL, {
      headers: { Authorization: passwordInput }
    })
      .then(res => {
        if (!res.ok) throw new Error('unauthorized')
        return res.text()
      })
      .then(decodeGzipBase64Json)
      .then(data => {
        setReviews(data)
        setIsAuthenticated(true)
        setLoading(false)
      })
      .catch(() => {
        alert("パスワードが違います")
        setLoading(false)
      })
  }

  // ===== ログイン画面 =====
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <form onSubmit={handleLogin} className="bg-white p-8 rounded-lg shadow-md w-80">
          <h2 className="text-2xl font-bold mb-6 text-center text-gray-800">マイログ閲覧</h2>
          <input
            type="password"
            value={passwordInput}
            onChange={(e) => setPasswordInput(e.target.value)}
            className="border border-gray-300 p-3 w-full mb-4 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="合言葉を入力"
          />
          <button type="submit" disabled={loading} className="w-full bg-blue-600 text-white p-3 rounded font-bold hover:bg-blue-700 transition disabled:opacity-50">
            {loading ? "確認中..." : "開く"}
          </button>
        </form>
      </div>
    )
  }

  // ===== メイン画面 =====
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="sticky top-0 z-10 bg-gray-50 shadow-sm">
        <div className="max-w-4xl mx-auto p-4 md:px-10 md:pt-10 md:pb-4">
          <h1 className="text-3xl font-bold text-gray-800 mb-4 border-b-2 border-blue-500 pb-2">
            今日見たもの ログ
          </h1>

          <div className="bg-white rounded-lg shadow-md p-4 space-y-3">
            <div className="relative">
              <input
                type="text"
                value={searchInput}
                onChange={(e) => {
                  setSearchInput(e.target.value)
                  if (!isComposingRef.current) {
                    setSearchText(e.target.value)
                    setCurrentPage(1)
                  }
                }}
                onCompositionStart={() => {
                  isComposingRef.current = true
                }}
                onCompositionEnd={(e) => {
                  isComposingRef.current = false
                  setSearchText(e.target.value)
                  setCurrentPage(1)
                }}
                placeholder="タイトル・感想・タグで検索"
                className="border border-gray-300 p-2 pr-8 w-full rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {searchInput !== '' && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchInput('')
                    setSearchText('')
                    setCurrentPage(1)
                  }}
                  aria-label="検索内容をクリア"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="flex flex-wrap gap-3">
              {GENRES.map((genre) => (
                <label key={genre} className="flex items-center gap-1 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={selectedGenres.includes(genre)}
                    onChange={() => toggleGenre(genre)}
                  />
                  {genre}
                </label>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-2 text-sm text-gray-700">
              <label className="flex items-center gap-1">
                登録日
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => {
                    setDateFrom(e.target.value)
                    setCurrentPage(1)
                  }}
                  className="border border-gray-300 rounded p-1"
                />
              </label>
              〜
              <input
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value)
                  setCurrentPage(1)
                }}
                className="border border-gray-300 rounded p-1"
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <p className="text-sm text-gray-500">
                  {filteredReviews.length}件 / 全{reviews.length}件
                </p>
                {hasActiveFilters && (
                  <button
                    type="button"
                    onClick={clearAllFilters}
                    className="text-sm text-blue-600 hover:text-blue-800 underline"
                  >
                    条件をすべてクリア
                  </button>
                )}
              </div>
              {totalPages > 1 && (
                <PaginationControls
                  page={currentPageSafe}
                  totalPages={totalPages}
                  onPrev={goToPrevPage}
                  onNext={goToNextPage}
                />
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto p-4 md:px-10 md:pb-10">
        {filteredReviews.length === 0 && (
          <p className="text-center text-gray-500 py-10">該当するレビューがありません</p>
        )}

        <div className="space-y-6">
          {pagedReviews.map((item) => (
            <div key={item.id} className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition">
              <div className="flex justify-between items-start mb-2">
                <span className="text-sm text-blue-600 font-mono">{item.review_date}</span>
                <div className="flex flex-wrap gap-1 justify-end">
                  <span className="bg-gray-100 text-gray-600 text-xs px-2 py-1 rounded">{item.genre}</span>
                  {item.tags?.map((tag) => (
                    <span key={tag} className="bg-purple-100 text-purple-700 text-xs px-2 py-1 rounded">{tag}</span>
                  ))}
                </div>
              </div>
              {item.links ? (
                <div className="mb-3 space-y-1">
                  {item.links.map((link, i) => (
                    <div key={i}>
                      <h2 className="text-xl font-bold text-gray-900">
                        {link.url ? (
                          <a href={link.url} target="_blank" rel="noopener noreferrer" className="hover:text-blue-600 underline">
                            {link.title}
                          </a>
                        ) : (
                          link.title
                        )}
                      </h2>
                      {link.subtitle && (
                        <p className="text-sm text-gray-500 mt-1 whitespace-pre-wrap">{link.subtitle}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mb-3">
                  <h2 className="text-xl font-bold text-gray-900">
                    {item.url ? (
                      <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-blue-600 underline">
                        {item.title}
                      </a>
                    ) : (
                      item.title
                    )}
                  </h2>
                  {item.subtitle && (
                    <p className="text-sm text-gray-500 mt-1 whitespace-pre-wrap">{item.subtitle}</p>
                  )}
                </div>
              )}
              {item.links ? (
                item.links.map((link, i) => (
                  hasEmbeddableContent(link) ? (
                    <LazyMount key={i} placeholderClassName={embedPlaceholderClassName(link)}>
                      <EmbedPreview item={link} />
                    </LazyMount>
                  ) : null
                ))
              ) : (
                hasEmbeddableContent(item) && (
                  <LazyMount placeholderClassName={embedPlaceholderClassName(item)}>
                    <EmbedPreview item={item} />
                  </LazyMount>
                )
              )}
              <div className="text-gray-700 whitespace-pre-wrap leading-relaxed bg-gray-50 p-4 rounded border-l-4 border-gray-200">
                {item.impression_segments ? (
                  item.impression_segments.map((seg, i) => {
                    if (seg.type === 'link') {
                      return (
                        <a key={i} href={seg.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">
                          {seg.title}
                        </a>
                      )
                    }
                    if (seg.type === 'embed') {
                      return hasEmbeddableContent(seg) ? (
                        <LazyMount key={i} placeholderClassName={embedPlaceholderClassName(seg)}>
                          <EmbedPreview item={seg} />
                        </LazyMount>
                      ) : null
                    }
                    return seg.text
                  })
                ) : (
                  item.impression
                )}
              </div>
            </div>
          ))}
        </div>

        {totalPages > 1 && (
          <div className="mt-6">
            <PaginationControls
              page={currentPageSafe}
              totalPages={totalPages}
              onPrev={goToPrevPage}
              onNext={goToNextPage}
            />
          </div>
        )}
      </div>
    </div>
  )
}

export default App