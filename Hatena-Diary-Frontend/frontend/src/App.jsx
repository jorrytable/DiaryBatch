import { useState } from 'react'

function App() {
  // 認証用の状態
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [passwordInput, setPasswordInput] = useState('')

  // データ用の状態
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(false)

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
        <div className="space-y-6">
          {reviews.map((item) => (
            <div key={item.id} className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition">
              <div className="flex justify-between items-start mb-2">
                <span className="text-sm text-blue-600 font-mono">{item.review_date}</span>
                <span className="bg-gray-100 text-gray-600 text-xs px-2 py-1 rounded">{item.genre}</span>
              </div>
              <h2 className="text-xl font-bold text-gray-900 mb-3">
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-blue-600 underline">
                  {item.title}
                </a>
              </h2>
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