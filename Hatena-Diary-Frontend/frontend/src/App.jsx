import { useState } from 'react'

const GENRES = ['映像', '音楽', 'ゲーム', 'テキスト', '体験', 'ラジオ', 'その他']

// oEmbed(embed_html)があればそれを埋め込み表示、無ければOGP情報で簡易プレビューカードを表示。
// どちらも無ければ何も表示しない。embed_htmlはYouTube/Spotify/SoundCloud等、
// 許可リスト化された信頼できるサービスのoEmbed応答のみが入る想定。
function EmbedPreview({ item }) {
  if (item.embed_html) {
    return (
      <div
        className="mb-3 [&_iframe]:w-full [&_iframe]:aspect-video"
        dangerouslySetInnerHTML={{ __html: item.embed_html }}
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
          <img src={item.og_image} alt="" className="w-28 h-28 object-cover flex-shrink-0" />
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

function App() {
  // 認証用の状態
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [passwordInput, setPasswordInput] = useState('')

  // データ用の状態
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(false)

  // 検索・フィルタ用の状態
  const [searchText, setSearchText] = useState('')
  const [selectedGenres, setSelectedGenres] = useState([])

  const toggleGenre = (genre) => {
    setSelectedGenres((prev) =>
      prev.includes(genre) ? prev.filter((g) => g !== genre) : [...prev, genre]
    )
  }

  const filteredReviews = reviews.filter((item) => {
    const matchesGenre = selectedGenres.length === 0 || selectedGenres.includes(item.genre)
    const matchesText =
      searchText === '' ||
      `${item.title}${item.impression}`.toLowerCase().includes(searchText.toLowerCase())
    return matchesGenre && matchesText
  })

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
        return res.json()
      })
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
    <div className="min-h-screen bg-gray-50 p-4 md:p-10">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-800 mb-8 border-b-2 border-blue-500 pb-2">
          今日見たもの ログ
        </h1>

        <div className="bg-white rounded-lg shadow-md p-4 mb-6 space-y-3">
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="タイトル・感想で検索"
            className="border border-gray-300 p-2 w-full rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
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
          <p className="text-sm text-gray-500">
            {filteredReviews.length}件 / 全{reviews.length}件
          </p>
        </div>

        {filteredReviews.length === 0 && (
          <p className="text-center text-gray-500 py-10">該当するレビューがありません</p>
        )}

        <div className="space-y-6">
          {filteredReviews.map((item) => (
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
              <h2 className="text-xl font-bold text-gray-900 mb-3">
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-blue-600 underline">
                  {item.title}
                </a>
              </h2>
              <EmbedPreview item={item} />
              <p className="text-gray-700 whitespace-pre-wrap leading-relaxed bg-gray-50 p-4 rounded border-l-4 border-gray-200">
                {item.impression}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default App