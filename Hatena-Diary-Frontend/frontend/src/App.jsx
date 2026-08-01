import { memo, useEffect, useRef, useState } from 'react'

const GENRES = ['映像', '音楽', 'ゲーム', 'テキスト', '体験', 'ラジオ', 'その他']

// ジャンルごとのバッジ配色。未知のジャンルは「その他」と同じ配色にフォールバックする
const GENRE_BADGE_COLORS = {
  '映像': 'bg-blue-100 text-blue-700',
  '音楽': 'bg-pink-100 text-pink-700',
  'ゲーム': 'bg-green-100 text-green-700',
  'テキスト': 'bg-yellow-100 text-yellow-700',
  '体験': 'bg-orange-100 text-orange-700',
  'ラジオ': 'bg-cyan-100 text-cyan-700',
  'その他': 'bg-gray-100 text-gray-600',
}

function genreBadgeClassName(genre) {
  return GENRE_BADGE_COLORS[genre] || GENRE_BADGE_COLORS['その他']
}

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

const PaginationControls = memo(function PaginationControls({ page, totalPages, onPrev, onNext }) {
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
})

// レビュー1件分のカード。React.memoで包み、propsのitemが同じオブジェクト参照のままなら
// （検索欄の操作等、無関係なApp()の状態変化では）再描画・差分計算そのものをスキップする。
// これにより、フォーカスの移動や入力操作のたびに埋め込み（iframe）が不必要に
// Reactの差分計算に巻き込まれてちらつく／再読み込みされることを防ぐ。
const ReviewCard = memo(function ReviewCard({ item }) {
  return (
    <div className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition">
      <div className="flex justify-between items-start mb-2">
        <span className="text-sm text-blue-600 font-mono">{item.review_date}</span>
        <div className="flex flex-wrap gap-1 justify-end">
          <span className={`${genreBadgeClassName(item.genre)} text-xs px-2 py-1 rounded`}>{item.genre}</span>
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
            // type: 'text'。ブログ本文中の<b>等のHTMLタグをそのまま反映するため
            // エスケープせずHTMLとして描画する（自分のブログの自作コンテンツのみが
            // 対象で、embed_html同様の信頼範囲のため許容している）
            return <span key={i} dangerouslySetInnerHTML={{ __html: seg.text }} />
          })
        ) : (
          <span dangerouslySetInnerHTML={{ __html: item.impression }} />
        )}
      </div>
    </div>
  )
})

const PAGE_SIZE = 50

function App() {
  // 認証用の状態
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [passwordInput, setPasswordInput] = useState('')

  // データ用の状態
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(false)

  // 検索・フィルタ用の状態。
  // 「下書き」（入力欄の表示専用、操作しても一覧には即座に反映されない）と
  // 「適用済み」（実際に一覧の絞り込みに使われる、検索実行時にのみ更新される）を分離している。
  // 統合検索: searchInput(下書き) / searchText(適用済み)
  // ジャンル : draftGenres(下書き) / selectedGenres(適用済み)
  // 登録日  : draftDateFrom/draftDateTo(下書き) / dateFrom/dateTo(適用済み)
  const [searchInput, setSearchInput] = useState('')
  const [searchText, setSearchText] = useState('')
  const [selectedGenres, setSelectedGenres] = useState([])
  const [draftGenres, setDraftGenres] = useState([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [draftDateFrom, setDraftDateFrom] = useState('')
  const [draftDateTo, setDraftDateTo] = useState('')
  const [currentPage, setCurrentPage] = useState(1)

  // タグ専用検索欄の状態。tagInputは表示値（IME変換中含む）、tagQueryは候補計算に使う確定値、
  // selectedTagは実際に一覧を絞り込むタグ（適用済み。検索実行時にtagInputの値が反映される）。
  const [tagInput, setTagInput] = useState('')
  const [tagQuery, setTagQuery] = useState('')
  const [selectedTag, setSelectedTag] = useState('')
  const [tagDropdownOpen, setTagDropdownOpen] = useState(false)
  const isTagComposingRef = useRef(false)

  // ジャンルのチェックは見た目（draftGenres）だけを切り替える。実際の絞り込みへの反映は
  // 検索ボタン押下時（executeSearch）にまとめて行うため、ここではcurrentPageも変更しない。
  const toggleGenre = (genre) => {
    setDraftGenres((prev) =>
      prev.includes(genre) ? prev.filter((g) => g !== genre) : [...prev, genre]
    )
  }

  // タグ欄の入力候補は、一覧の絞り込みとは別の軽い処理（登録済みタグを数えるだけ）のため、
  // 従来通りIME確定時（および英数字等の通常入力時）に都度計算して表示する。
  const handleTagInputChange = (e) => {
    const value = e.target.value
    setTagInput(value)
    if (!isTagComposingRef.current) {
      setTagQuery(value)
      setTagDropdownOpen(value !== '')
    }
  }

  const handleTagCompositionEnd = (e) => {
    isTagComposingRef.current = false
    const value = e.target.value
    setTagQuery(value)
    setTagDropdownOpen(value !== '')
  }

  // 候補をクリックしても欄に入力されるだけで、一覧への反映（絞り込み実行）は行わない。
  // 実際に絞り込むには検索ボタンを押す（または統合検索欄でEnterを押す）必要がある。
  const selectTagCandidate = (tag) => {
    setTagInput(tag)
    setTagQuery(tag)
    setTagDropdownOpen(false)
  }

  // ✕ボタンでのクリアは「その場でフィルタを取り消す」明示的な操作のため、
  // 下書き・適用済み両方を即座にリセットし、検索ボタンを押さなくても反映する。
  const clearTagFilter = () => {
    setTagInput('')
    setTagQuery('')
    setSelectedTag('')
    setTagDropdownOpen(false)
    setCurrentPage(1)
  }

  // タグ入力中の文字列を含む既存タグを、出現件数の多い順に上位5件だけ候補として出す
  const tagCandidates = (() => {
    if (tagQuery === '') return []
    const query = tagQuery.toLowerCase()
    const counts = new Map()
    for (const item of reviews) {
      for (const tag of item.tags || []) {
        if (tag.toLowerCase().includes(query)) {
          counts.set(tag, (counts.get(tag) || 0) + 1)
        }
      }
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([tag]) => tag)
  })()

  // 「検索」ボタン（または統合検索欄でのEnter）を押した時にのみ、下書きの内容を
  // まとめて適用済みstateへ反映する。これにより、複数条件を組み立てている最中は
  // 一覧の絞り込み直し（重い処理）が一切走らない。
  const executeSearch = () => {
    setSearchText(searchInput)
    setSelectedTag(tagInput)
    setSelectedGenres(draftGenres)
    setDateFrom(draftDateFrom)
    setDateTo(draftDateTo)
    setCurrentPage(1)
  }

  const handleSearchInputKeyDown = (e) => {
    if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
      e.preventDefault()
      executeSearch()
    }
  }

  // クリア判定・全クリアは実行済み（適用済み）の検索条件を基準にする
  const hasActiveFilters = searchText !== '' || selectedGenres.length > 0 || dateFrom !== '' || dateTo !== '' || selectedTag !== ''

  const clearAllFilters = () => {
    setSearchInput('')
    setSearchText('')
    setSelectedGenres([])
    setDraftGenres([])
    setDateFrom('')
    setDateTo('')
    setDraftDateFrom('')
    setDraftDateTo('')
    setTagInput('')
    setTagQuery('')
    setSelectedTag('')
    setTagDropdownOpen(false)
    setCurrentPage(1)
  }

  const filteredReviews = reviews.filter((item) => {
    const matchesGenre = selectedGenres.length === 0 || selectedGenres.includes(item.genre)
    const searchTarget = `${item.title}${item.impression}`.toLowerCase()
    const matchesText = searchText === '' || searchTarget.includes(searchText.toLowerCase())
    const matchesTag = selectedTag === '' || (item.tags || []).includes(selectedTag)
    const matchesDateFrom = dateFrom === '' || item.review_date >= dateFrom
    const matchesDateTo = dateTo === '' || item.review_date <= dateTo
    return matchesGenre && matchesText && matchesTag && matchesDateFrom && matchesDateTo
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
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onKeyDown={handleSearchInputKeyDown}
                  placeholder="タイトル・感想で検索（Enterで実行）"
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

              <div className="relative w-48">
                <input
                  type="text"
                  value={tagInput}
                  onChange={handleTagInputChange}
                  onCompositionStart={() => {
                    isTagComposingRef.current = true
                  }}
                  onCompositionEnd={handleTagCompositionEnd}
                  onFocus={() => {
                    if (tagQuery !== '') setTagDropdownOpen(true)
                  }}
                  onBlur={() => {
                    setTimeout(() => setTagDropdownOpen(false), 150)
                  }}
                  placeholder="タグで検索"
                  className="border border-gray-300 p-2 pr-8 w-full rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {(tagInput !== '' || selectedTag !== '') && (
                  <button
                    type="button"
                    onClick={clearTagFilter}
                    aria-label="タグ検索をクリア"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    ✕
                  </button>
                )}
                {tagDropdownOpen && tagCandidates.length > 0 && (
                  <ul className="absolute z-20 mt-1 w-full bg-white border border-gray-200 rounded shadow-md text-sm overflow-hidden">
                    {tagCandidates.map((tag) => (
                      <li key={tag}>
                        <button
                          type="button"
                          onClick={() => selectTagCandidate(tag)}
                          className="w-full text-left px-3 py-1.5 hover:bg-gray-100"
                        >
                          {tag}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              {GENRES.map((genre) => (
                <label key={genre} className="flex items-center gap-1 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={draftGenres.includes(genre)}
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
                  value={draftDateFrom}
                  onChange={(e) => setDraftDateFrom(e.target.value)}
                  className="border border-gray-300 rounded p-1"
                />
              </label>
              〜
              <input
                type="date"
                value={draftDateTo}
                onChange={(e) => setDraftDateTo(e.target.value)}
                className="border border-gray-300 rounded p-1"
              />
            </div>

            <div>
              <button
                type="button"
                onClick={executeSearch}
                className="bg-blue-600 text-white text-sm font-bold px-4 py-2 rounded hover:bg-blue-700 transition"
              >
                検索
              </button>
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
              <PaginationControls
                page={currentPageSafe}
                totalPages={totalPages}
                onPrev={goToPrevPage}
                onNext={goToNextPage}
              />
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
            <ReviewCard key={item.id} item={item} />
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