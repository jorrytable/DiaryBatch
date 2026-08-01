# Hatena日記アプリ 開発記録・設計方針

`Doc/doc.md`（当初の引継ぎ資料、一部古い）に対し、2026-07-19の引継ぎレビュー以降に確定した設計方針・実装済み機能・障害対応・運用メモをまとめたもの。以後の開発・引継ぎはこちらを正とする。

---

## 1. 基本設計方針（決定事項）

### 1.1 データ取得方式：AtomPub API方式
doc.mdは「トップページのHTMLスクレイピング」と書かれているが、実際は`blog.hatena.ne.jp/{HatenaId}/{BlogId}/atom/entry`のAtomPub API（APIキー認証）を使う方式が正。過去ページの一括取込もAtomの`<link rel="next">`を辿るページネーションで実装している。

### 1.2 パーサ仕様：実装（parser.py）が正
`src/backend/batch/parser.py`は行頭`- `（作品）/ `-- `（感想）のプレーンテキスト判定ロジック。テストはこの実装形式（はてな記法プレーンテキスト）に合わせて書く。

### 1.3 認証方式：API Gateway側でのサーバサイド認証
フロントのビルド時埋め込みパスワード等の「気休め」レベルは不採用。API Gateway側にLambda Authorizerを設定し、正しい資格情報がないとAPIレスポンス自体が返らない構成。TOKEN型Lambda Authorizerが、SSMパラメータ`/hatena-site/access-token`と`Authorization`ヘッダーの値を照合する。

### 1.4 冪等性：全削除＆再構築方式
再取込のたびに過去分データを全削除し、分類ロジックも含めて一からやり直す。バッチ処理は「①ReviewTable全件削除 → ②API取得・パース・分類 → ③全件put_item」の順。IDは毎回`uuid.uuid4()`の新規発行（upsertキー設計は無し）。

### 1.5 検索API設計
`scan()`全件取得＋メモリソートは不採用。`FeedIndex`というGSI（`data_type`固定値をHASH、`review_date`をRANGE）に対して`Query`し、DynamoDB側で日付降順ソート済みのデータを取得する設計。

### 1.6 ジャンル体系
ジャンルは「映像/音楽/ゲーム/テキスト/体験/ラジオ/その他」の7区分（当初6区分から後日「ラジオ」を追加）。判定ソースは主にURLドメイン。

### 1.7 バッチの定期実行
`template.yaml`の`BatchFunction`に`Events`として`Schedule`タイプ（EventBridge Rule、`cron(0 18 * * ? *)` = 毎日JST3:00）を設定済み。

### 1.8 リポジトリ構成
旧実装（`old/Hatena-Batch`）は削除済み。`Hatena-Diary-DataBase`（バックエンド）と`Hatena-Diary-Frontend`（フロントエンド）の2ディレクトリで構成。GitHubリポジトリは`jorrytable/DiaryBatch`（ブランチ`main`）。

---

## 2. 実装済み機能

### 2.1 ロードマップ①〜④（2026-07-25〜26完了）
- ① Vercelデプロイ + API Gateway Lambda Authorizerによる本格認証
- ② Atomフィードのページネーション対応（`MAX_PAGES=1000`、Lambda `Timeout=900`）。実測：全履歴130ページ・4764件、約83秒で完了
- ③ ジャンル自動判別（`GENRE_DOMAIN_MAP`→後に`classify.py`に分離）
- ④ 検索・フィルタUI（テキスト検索＋ジャンル絞り込み、クライアントサイド実装）

### 2.2 title改善・埋め込みコンテンツ対応（2026-07-26完了）
- `parser.py`: `:title=`指定なしの場合、`title`を`None`（要取得マーカー）にする方式
- 新規`enrich.py` + 新規DynamoDBテーブル`UrlMetadataCacheTable`（PK: `url`）でtitle/embed_html/OGP情報をURL単位にキャッシュ。`ReviewTable`の日次全削除の影響を受けず永続する
- oEmbed対応（YouTube/Spotify/SoundCloud）→OGPスクレイピング→プレーンリンクの3段階フォールバック
- 1回のバッチ実行あたり未キャッシュURLの新規取得は`ENRICH_BUDGET=200`件まで
- フロント`App.jsx`に`EmbedPreview`コンポーネントを追加

### 2.3 ジャンル「ラジオ」新設＋YouTubeタグ・音楽ジャンル上書き（2026-07-26完了）
- `radiko.jp`→ラジオ。`open.spotify.com`はURLパス（`/episode/`, `/show/`）で判定し、podcastのみラジオ、trackは音楽のまま
- YouTube動画は oEmbedの`author_name`（チャンネル名）を`tags`に格納
- 音楽判定は**YouTube Data API v3の`categoryId`（音楽=10）**を使用。該当する場合は`genre`を「映像」→「音楽」に上書き（tagsには追加しない）
- SSMパラメータ`/hatena-batch/youtube-api-key`（未設定でも動作継続、音楽判定のみスキップ）

### 2.4 「その他」ジャンル精度向上（2026-07-26完了）
- `GENRE_DOMAIN_MAP`/`classify_genre`を`batch/classify.py`に分離（`DOMAIN_RULES`辞書、`classify_genre_and_tags()`、`classify_from_content()`）。共通`hostname()`は`common/urls.py`に切り出し
- テキスト8ドメイン、映像+タグ「テレビ」26ドメイン、映像+タグ「TVアニメ」1ドメインを追加
- `- 映画『』`/`- TVアニメ『』`で始まる行はURLが無くてもアイテムとして採用
- `tests/conftest.py`新設（Lambdaランタイムと同じ`batch.x`/`common.x`のbareインポートをローカルpytestでも解決）

### 2.5 UI改善5件（2026-07-26完了）
`App.jsx`に実装: ①見出し+検索/フィルタ枠のsticky化 ②検索ボックスの✕クリアボタン ③テキスト検索対象にtagsを追加 ④登録日（review_date）の期間絞り込み ⑤ページネーション（前へ/次へボタン）。
微修正（2026-08-01）: sticky header内の上部ページネーションは、結果が1ページのみでもボタンを不活性状態のまま常時表示するよう変更。

### 2.6 話数・サブタイトル反映（`subtitle`項目、2026-07-31〜08-01完了）
- テレビ番組等、`- {局名}『[{url}:title={番組名}]』{第N話}?{「サブタイトル」}*[{url}:embed]`のような記法から、番組名リンクの後ろ〜次の`:embed`ブラケットまでのテキストを新規`subtitle`項目として抽出
- 複数話をまとめて書く区切り「・」は改行に変換（「」で囲まれた文言内の「・」は保持）。丸括弧/全角括弧で囲まれた話数列挙は括弧を除去
- 当初「`テレビ`タグ限定」だった適用条件を「URLリンクがあれば常時」に一般化（Amazon Prime Video、TVアニメ専用ドメイン等でも同じ記法が使われるため）
- 副次発見（未対応）: Amazon Prime Videoの`:title=`値に`| Amazon Prime Video`のようなサービス名接尾辞が生で入る問題（→ 今後の課題参照）

### 2.7 1行複数コンテンツの取り込み対応（`links`配列、2026-08-01完了）
- `[url1:title] / [url2:title][url1:embed][url2:embed]`のように1行に複数リンクが並記される記法に対応
- 当初は各リンクを独立アイテムに分割する設計で実装したが、ユーザーからのリテイク指示（「1つのアイテムにまとめるのが正、ブログの見た目通りタイトルを並べた後に埋め込みを並べる」）を受けて、**1アイテム＋新規`links`配列**（`{url, title, subtitle}`の配列）に統合する方式に変更
- ジャンル/タグは先頭リンクの判定を採用。titleは各リンクのエンリッチ後に`" / "`結合して再構築
- フロントは各リンクのタイトルを縦に並べ、その下に全埋め込みを連続表示

### 2.8 スマートフォンでの負荷軽減策（2026-08-01完了）
- 原因: YouTube動画等の`embed_html`（`<iframe>`）に`loading`属性が無く、1ページ分の全埋め込みが画面外分も含め一斉に読み込まれていた
- `LazyMount`コンポーネント新設（`IntersectionObserver`、`rootMargin: '300px'`）: 画面に近づくまで埋め込みの実体をマウントせず、プレースホルダーのみ表示。一度マウントしたら維持
- oEmbedの`<iframe>`・OGPの`<img>`に`loading="lazy"`を注入（補助対策）
- `PAGE_SIZE`を100→50に引き下げ

### 2.9 YouTube埋め込みの高さ問題（2026-08-01完了）
- 原因: oEmbedが返す`<iframe height="113">`のHTML属性はCSS上「明示的なheight値」として扱われ、`aspect-ratio`（`aspect-video`）は高さが`auto`の場合のみ機能するため無効化されていた
- `[&_iframe]:h-auto`を追加して明示的に`height: auto`を指定
- 副作用として、Spotify等のコンパクトプレイヤー型埋め込みまで16:9に強制されてしまったため、`item.url`が`youtube.com`/`youtu.be`の場合のみ`h-auto`+`aspect-video`を適用するよう修正（Spotify/SoundCloudは`w-full`のみ、oEmbed指定の高さを維持）

### 2.10 IME変換確定前は検索フィルタを動かさない（2026-08-01完了）
- 検索stateを`searchInput`（表示値、常に更新）と`searchText`（フィルタ判定用の確定値）に分離
- `isComposingRef`（useRef）でIME変換中かどうかを判定し、変換中は`searchText`を更新しない。`onCompositionEnd`で最終値を反映
- デバウンス方式ではなく`compositionend`イベント方式を採用（変換確定タイミングに正確に追随するため）

### 2.11 感想本文中のはてな記法リンク化・埋め込み再現（`impression_segments`、2026-08-01完了）
- `[url:title=タイトル]`のようなインラインリンクや`[url:embed]`の埋め込みマーカーが感想本文中にそのまま残っていた問題への対応
- `parser.py`に`tokenize_impression(text)`を新設: 本文中の全ブラケットを検出し、`text`/`link`/`embed`のセグメント列に分解。記法が皆無ならNoneを返し平文表示にフォールバック
- `flatten_impression_segments(segments)`で検索用の平文impressionを再構成
- `app.py`でlink/embed各セグメントを既存のエンリッチ処理（oEmbed/OGP取得）にかけてtitle/embed_html/OGPを解決
- フロントは`impression_segments`があればセグメントをmapし、linkはインラインリンク、embedは既存の`EmbedPreview`/`LazyMount`をそのまま再利用して描画

### 2.12 感想中のHTMLタグの反映（2026-08-01完了）
- 感想本文中に`<b>`等のHTMLタグが直書きされているケースで、Reactの文字列エスケープにより生テキストのまま表示されていた問題
- 感想描画部分（`impression_segments`の`text`セグメント、および非該当時のプレーンフォールバック）を`dangerouslySetInnerHTML`に変更。自分のブログ本文（自作コンテンツ）が対象であり、既存の`embed_html`（oEmbed応答）と同じ信頼レベルとして許容
- バックエンド側は無変更（HTMLタグは`[url:...]`ブラケット記法の対象外のため、`text`セグメントにそのまま含まれる）

### 2.13 UI操作系の小改善（2026-08-01完了）
- 全検索条件クリアボタン: `hasActiveFilters`（検索テキスト・ジャンル・期間のいずれかが有効か）と`clearAllFilters()`を追加。何か一つでも条件が有効な時だけ、件数表示の隣に「条件をすべてクリア」ボタンを表示
- ジャンルバッジの配色: ジャンルごとに異なる色を割り当て（映像=青/音楽=ピンク/ゲーム=緑/テキスト=黄/体験=オレンジ/ラジオ=水色/その他=灰色）。タグは紫色統一のまま変更なし

### 2.14 タグ専用の独立した検索欄（2026-08-01完了）
- 統合検索（タイトル・感想）からtagを除外し、検索ボックス右側に専用のタグ検索欄を新設
- IME対応（本文検索と同じ`compositionstart`/`compositionend`方式）。確定後、出現件数の多い順に上位5件を候補としてドロップダウン表示し、候補をクリックした時だけ実際に一覧が絞り込まれる（入力中は絞り込まれない）
- `hasActiveFilters`/`clearAllFilters`にタグ状態も統合済み

### 2.14 ディレクトリ名リネーム（2026-08-01完了）
バックエンドのディレクトリ名の誤字（`Hatena-DIary-DataBase`）を`Hatena-Diary-DataBase`に修正。Windowsの大文字小文字を区別しないファイルシステム対策として、一時名を経由する2段階`git mv`で実施。

---

## 3. 障害対応履歴

### 3.1 SearchFunctionの6MB応答上限超過による502エラー（2026-08-01発生・同日修正）
- **症状**: 課題2.11のデプロイ直後、正しいパスワードでアクセスできなくなった
- **原因**: `subtitle`・`links`・`impression_segments`等の追加により、embed_html/OGP情報が同じURLに対して複数箇所で重複保持されるようになり、JSON応答がLambdaの同期呼び出し応答上限（6MB, 6,291,556 bytes）を超過。フロントの汎用エラーハンドラが失敗理由を問わず「パスワードが違います」と表示するため、認証エラーに見えた
- **調査手順**: `aws logs tail /aws/lambda/<SearchFunction名> --since 2h`でCloudWatch Logsの`RequestEntityTooLarge`エラーを直接確認するのが最速
- **1stの修正（後に置き換え）**: `search.py`でレスポンスをgzip圧縮しBase64化して`isBase64Encoded: true`で返し、API Gatewayの`BinaryMediaTypes`でバイナリパススルーさせる方式。GET単体では動作を確認したが、**CORSプリフライト（OPTIONSのMock統合）が500エラーになる副作用**が発覚（`BinaryMediaTypes`の存在自体がこのMock統合と相性が悪い。`"*/*"`でも特定MIMEタイプに絞っても解消せず）
- **最終修正**: `BinaryMediaTypes`を完全に削除。`search.py`は`isBase64Encoded`を使わず、gzip圧縮データをBase64化した**普通の文字列**として返す。フロント側で`atob()`→`DecompressionStream('gzip')`→`JSON.parse`という手動展開処理を追加
- **今後の懸念**: gzip圧縮は一時しのぎであり、記事数が増え続ければ圧縮後サイズもいずれ6MBに達しうる。恒久対策としては検索API側のサーバーサイドページネーション（全件返却をやめる）の検討が必要

### 3.2 感想内埋め込み（impression_segments）が予算切れで反映されない（2026-08-01発見・同日修正）
- **原因**: `app.py`の`ENRICH_BUDGET=200`（1回の実行あたりの新規URL取得上限）が、メインコンテンツ（url/links）のエンリッチを先に処理していたため、感想内埋め込みに回る前に使い切られていた（過去の大量履歴backlogが依然として多く残っているため）
- **修正**: エンリッチ処理順序を変更し、件数の少ないimpression_segmentsを先に処理してからメインコンテンツを処理するようにした。感想内embed解決数が1/63→50/64に改善

---

## 4. 運用メモ

### 4.1 Windows(日本語ロケール)でのSAM CLI文字コードエラー
`sam build`/`sam deploy`が`'utf-8' codec can't decode`等で失敗する場合、`$env:PYTHONUTF8 = "1"`をセットする。

### 4.2 DynamoDBの既存GSIはキースキーマをその場で変更できない
GSIのKeySchema変更は不可、同一デプロイでのGSI追加+削除も不可（1回のUpdateTableにつき1操作まで）。スキーマを変えたい場合は名前ごと変更する（本アプリでは`DateIndex`→`FeedIndex`）。ドリフトが疑わしい場合はスタックごと削除して作り直すのが確実。

### 4.3 SAMのAPI Auth設定はCORSプリフライトも巻き込む
`Auth.DefaultAuthorizer`設定時は`AddDefaultAuthorizerToCorsPreflight: false`を必ず入れる（デフォルトtrueだとOPTIONSにもAuthorizerが適用され401になる）。

### 4.4 Git Bash（MSYS）はAWS CLIの先頭スラッシュ引数を誤変換する
`/aws/lambda/...`のような先頭`/`の引数は、コマンド前に`MSYS_NO_PATHCONV=1`を付ける。

### 4.5 `aws lambda invoke`はCLI側の応答待ちタイムアウトで先に諦めることがある
Lambda自体は正常でも、botocore側のHTTP読み取りタイムアウト（デフォルト約60秒）で先にエラーになる。長時間実行が想定される場合は`--cli-read-timeout 910`等を指定し、CloudWatch Logsで実際の結果を確認する。

### 4.6 Vercelの「固有デプロイURL」と「安定ドメイン」の違い
Vercelは各デプロイに固有URL（`https://diary-batch-<ランダム文字列>-jorrytable.vercel.app`）を発行し、それとは別に安定ドメイン（`https://diary-batch.vercel.app`）がある。固有URLは不変なので、新しいpush後もその時点のビルドを配信し続ける。「デプロイしたのに反映されない」という報告時は、まずアクセスURLが安定ドメインかどうかを確認する。

### 4.7 DynamoDB Queryは1回の応答が1MBまで
`Query`/`Scan`は1回のAPI呼び出しにつき最大1MBまでしか返さない。`LastEvaluatedKey`をチェックしてループする実装が必須。

### 4.8 YouTube Musicの利用可否はHTTPスクレイピングで判定不可
`music.youtube.com`は非ブラウザ環境からのアクセスに対し実データではなく固定の代替ページを返す。動画の実際のカテゴリ判定にはYouTube Data API v3の`videos.list`（`snippet.categoryId`）を使う。

### 4.9 合言葉（SSMパラメータ）の変更方法
`authorizer.py`はSSMパラメータ`/hatena-site/access-token`を毎回リクエスト時に取得するため、値を更新するだけでデプロイ不要・即時反映される。
```
MSYS_NO_PATHCONV=1 aws ssm put-parameter --name "/hatena-site/access-token" --value "新しい値" --type SecureString --overwrite
```

### 4.10 API GatewayのBinaryMediaTypesはCORSプリフライトを壊すことがある
このAPIでは`BinaryMediaTypes`を設定すると原因不明のままCORSプリフライト（OPTIONSのMock統合）が壊れた（3.1参照）。同様の対応をする場合はAPI Gateway側のバイナリパススルーに頼らず、フロント側で手動base64デコード＋展開する方式を最初から採用すること。

---

## 5. デプロイ関連の実績値（変更されうるので都度確認）
- GitHubリポジトリ: `jorrytable/DiaryBatch`（ブランチ`main`）
- API Gatewayエンドポイント: `https://qg18xf1xq3.execute-api.ap-northeast-1.amazonaws.com/Prod/reviews`（スタック再作成で変わる）
- Vercel安定ドメイン: `https://diary-batch.vercel.app`相当（CORSの`AllowOrigin`は現状`'*'`のままで、実質的な保護はLambda Authorizerが担っている）

---

## 6. 未着手の今後の課題

1. **ジャンル・タグバッジをクリックしてその属性で絞り込む機能**: 各コンテンツのジャンル/タグバッジをクリックすると、その属性に一致するものに絞り込まれる機能。「並べ替え」ではなく「絞り込み」の可能性が高いが、着手時に要確認。
2. **titleに混入するサービス名接尾辞の除去**: Amazon Prime Videoの`:title=`値が`カルテット | Amazon Prime Video`のようにサービス名接尾辞込みでそのまま入る問題。「| 任意の文字列」を一律除去する汎用ロジックか、サービスごとの個別指定にするか要ヒアリング（本体titleに元々`|`を含むケースを誤って切り落とすリスクに注意）。
