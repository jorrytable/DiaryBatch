# はてなブログ「今日見たもの」抽出・閲覧Webアプリ プロジェクト引継ぎ資料

## 1. プロジェクト概要
はてなブログの独自記法（はてな記法）で書かれた「今日見たもの（レビューや感想）」を定期的にスクレイピングし、自分専用のオシャレなWeb画面で閲覧・検索できるようにするフルスタックアプリケーション。

## 2. システム構成
- **バックエンド:** AWS SAM (AWS Lambda, Amazon DynamoDB, Amazon API Gateway) / Python 3.11
- **フロントエンド:** React (Vite) / Tailwind CSS v4
- **デプロイ先(予定):** フロントエンドは Vercel、バックエンドは AWS

## 3. 現在の進捗状況
- バックエンドのスクレイピング、DB保存、API構築は完了しAWSへデプロイ済み。
- フロントエンドはローカル環境（Vite）での構築が完了。Tailwind v4 を用いたスタイリングと、環境変数を用いた簡易パスワード認証画面を実装済み。
- **現在地:** ロードマップの「① Vercelへのデプロイ・公開」の直前（ローカルで動く状態からGitHubへPushする段階）。

## 4. 今後のロードマップ
これ以降のサポートでは、以下の順番で作業を進める予定です。
1. **デプロイ・公開:** フロントエンドをGitHubにPushし、Vercelでホスティング。認証付きでWebから閲覧可能にする。（←現在ここ）
2. **ブログ取込関数の修正:** `batch.py` を修正し、トップページだけでなく過去ページも一括で取り込む仕様（ページネーション対応）にする。
3. **ジャンル自動判別ロジックの修正:** `parser.py` を修正し、現在は「Web」固定になっているジャンルを、URL（例: youtube.comなら動画）などに基づいて自動判別する。
4. **検索・フィルタ機能追加:** フロントエンド側（React）に、ジャンル絞り込みやテキスト検索のUIを追加する。

## 5. フロントエンドの現在のコード (frontend/)

### `vite.config.js`
Tailwind CSS v4の仕様に合わせてプラグインを設定しています。
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
})
```

### `src/index.css`
```css
@import "tailwindcss";
```

### `src/App.jsx`
簡易パスワード認証（合言葉）と、AWS API Gatewayからのデータ取得・表示処理を実装しています。
```jsx
import { useEffect, useState } from 'react'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [passwordInput, setPasswordInput] = useState('')
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(true)

  // 環境変数からパスワードを取得（開発中は 'secret'）
  const CORRECT_PASSWORD = import.meta.env.VITE_SITE_PASSWORD || 'secret'
  
  // AWS API Gatewayのエンドポイント
  const API_URL = "※ここにAWS API GatewayのURLが入ります"

  const handleLogin = (e) => {
    e.preventDefault()
    if (passwordInput === CORRECT_PASSWORD) {
      setIsAuthenticated(true)
    } else {
      alert("パスワードが違います")
    }
  }

  useEffect(() => {
    if (!isAuthenticated) return;

    fetch(API_URL)
      .then(res => res.json())
      .then(data => {
        setReviews(data)
        setLoading(false)
      })
      .catch(err => {
        console.error("APIエラー:", err)
        setLoading(false)
      })
  }, [isAuthenticated])

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
          <button type="submit" className="w-full bg-blue-600 text-white p-3 rounded font-bold hover:bg-blue-700 transition">
            開く
          </button>
        </form>
      </div>
    )
  }

  if (loading) return <div className="min-h-screen flex items-center justify-center bg-gray-50 text-gray-600 font-bold">データを読み込み中...</div>

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
```

## 6. バックエンドの現状 (AWS SAM)
バックエンド側のコードは既にAWS上にデプロイされていますが、今後の改修（ロードマップ2, 3）のために仕様を記録しておきます。

### DynamoDB テーブル設計 (`ReviewTable`)
- **パーティションキー (PK):** `id` (String) - UUIDを利用
- **属性:** 
  - `review_date` (String: YYYY-MM-DD)
  - `genre` (String)
  - `title` (String)
  - `url` (String)
  - `impression` (String)

### 各ファイルと機能
- **`template.yaml`**: DynamoDB(`ReviewTable`)、スクレイピング用Lambda(`BatchFunction`)、データ取得API用Lambda(`SearchFunction`)を定義。API Gateway経由で `/reviews` にGETリクエストを受け付ける（CORS許可済み）。
- **`parser.py`**: はてなブログのHTML/DOM構造や、はてな記法（`*`, `**`, `>|...|<` など）を解析し、日付、タイトル、URL、感想を抽出するロジック。
- **`batch.py`**: ブログのトップページを取得し、`parser.py` を呼び出して抽出したデータを DynamoDB に保存（put_item）する。（※現在はトップページのみ対象）
- **`search.py`**: DynamoDB に対して `scan` を実行し、保存されている全データをJSON形式でフロントエンドに返すAPI用ハンドラー。