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
`template.yaml`の`BatchFunction`に`Events`として`Schedule`タイプ（EventBridge Rule、`cron(30 20 * * ? *)` = 毎日JST5:30）を設定済み。**2026-08-07、JST3:00→JST5:30に変更**（日記は予約投稿でJST5:00に発火するため、旧設定だと直前の予約投稿がまだ発火前でその日の取り込みが1日分遅れていたことが判明。詳細は「6. 未着手の今後の課題」の課題#14参照）。

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
- 出現件数の多い順に上位5件を候補としてドロップダウン表示
- `hasActiveFilters`/`clearAllFilters`にタグ状態も統合済み
- ※候補の表示タイミング・クリック時の挙動はその後の2.16でさらに調整されている

### 2.15 ディレクトリ名リネーム（2026-08-01完了）
バックエンドのディレクトリ名の誤字（`Hatena-DIary-DataBase`）を`Hatena-Diary-DataBase`に修正。Windowsの大文字小文字を区別しないファイルシステム対策として、一時名を経由する2段階`git mv`で実施。

### 2.16 検索ボタン新設：全フィルタ条件を明示的な検索実行に統一（2026-08-01完了）
比較的大規模なUI変更のため、着手前にPlanモードでmd方針を作成しレビューを受けてから実装。

- **背景**: ジャンルチェックボックス・登録日・統合検索を操作するたびに一覧（最大約4800件からの絞り込み＋最大50件のカード再描画）が即座に再計算されており、「入力のたびに画面がリフレッシュされる」という指摘が繰り返し出ていた（タグ検索のEnter駆動化だけでは解決しなかった）。
- **設計**: すべてのフィルタ条件を「下書き」（入力欄の表示専用、操作しても一覧に影響しない）と「適用済み」（実際の絞り込みに使う値、検索実行時のみ更新）に分離した。
  - 統合検索: `searchInput`(下書き)/`searchText`(適用済み)、タグ: `tagInput`(下書き)/`selectedTag`(適用済み)、ジャンル: `draftGenres`(下書き)/`selectedGenres`(適用済み)、登録日: `draftDateFrom`/`draftDateTo`(下書き)/`dateFrom`/`dateTo`(適用済み)
- 新規「検索」ボタン（フィルタ枠内、日付欄の下）を新設。クリック、または統合検索欄でのEnter押下で`executeSearch()`が下書きの内容をまとめて適用済みstateへ反映し、一覧の再計算・再描画はこの時だけ発生する。
- ジャンルのチェック・日付選択はその場では一覧に一切影響しない（下書きの見た目が変わるだけ）。
- タグ候補ドロップダウンの計算タイミングは、Enter駆動から**IME確定（`compositionend`）方式に差し戻した**（一覧への反映自体が検索ボタン実行時のみに切り離されたため、候補計算だけなら都度行っても体感の重さにつながらないと判断）。候補をクリックした場合は`tagInput`に値を入れるだけで、一覧への反映は検索ボタン実行時まで行われない。
- ✕クリアボタン・「条件をすべてクリア」は例外的に即座に反映される（検索ボタンを介さない、明示的な取り消し操作のため）。
- `hasActiveFilters`は適用済みstateを基準にするよう修正（以前は下書きの`searchInput`を見ていた不整合を解消）。

### 2.17 埋め込みコンテンツのフォーカス外れ時再読み込み対策（2026-08-01完了）
- **症状**: 検索コントロール（統合検索・タグ・ジャンル・登録日）からフォーカスを外すと、一覧内の埋め込みコンテンツ（iframe）が再読み込みされているように見える
- **原因の見立て**: `App.jsx`は検索・フィルタ用stateを1つの`App()`関数コンポーネントに集約しており、そのどれか1つでも変化すると一覧全体（埋め込みを含む）が丸ごと再計算される。カード部分がメモ化されておらず、無関係な状態変化のたびに一覧全体がReactの差分計算に巻き込まれていたことが本質と判断
- **対応**: カード1件分の描画を`ReviewCard({ item })`という独立コンポーネントに切り出し`React.memo`で包んだ。`item`は元の`reviews`配列の要素をそのまま参照しているため、レビュー内容自体が変わらない限り同じオブジェクト参照のままとなり、検索欄操作等の無関係なstate変化時は再描画・差分計算そのものがスキップされるようになった。`PaginationControls`も同様に`React.memo`化

### 2.18 ジャンル・タグバッジをクリックして絞り込み（2026-08-01完了）
- カード上のジャンル/タグバッジを`<span>`から`<button>`に変更し、クリックで即座に絞り込みを実行するようにした（検索ボタンを介さない、✕クリア等と同様の明示的な即時操作）
- ジャンルバッジをクリックすると、既存の複数選択に追加ではなく**そのジャンル1つだけに置き換わる**
- タグバッジをクリックすると、そのタグが即座にタグ検索欄・絞り込みの両方に反映される
- `filterByGenre`/`filterByTag`は`useCallback`で関数参照を固定し、`ReviewCard`の`React.memo`によるメモ化を壊さないようにしている

### 2.19 表示日付（review_date）が実際の日記日付と1日ずれる問題の調査・対応（2026-08-07完了）
- **症状**: 各コンテンツ左上の日付表示が、日記の実際の投稿日とずれて見える、との指摘。
- **調査**: `batch/app.py`はAtomフィードの`<published>`（Hatenaが技術的に投稿処理をした日時）から`review_date`を算出しているが、実際のAtomPubフィードを直接取得して確認したところ、日記は**予約投稿**（ユーザーの運用：当日深夜に書いた内容を翌朝JST5:00に予約投稿で発火）を使っており、`<published>`は常に日記の対象日（エントリの`<title>`欄、`YYYY-MM-DD`形式）の**1日後**になっていた（60件以上サンプリングし例外なし）。
- **一時的な二重ラベル事象の原因**: 上記に加えて、当時のバッチ実行スケジュール（毎日JST3:00）は予約投稿の発火時刻（JST5:00）より**2時間早く**、その日の未発火の予約投稿を取りこぼしたまま実行されていた。CloudWatch Logsで前回実行時刻（2026-08-07 03:03 JST）を確認し、対象の予約投稿（2026-08-07 05:00発火）がその2時間後に発火していたことを突き合わせて確認。取りこぼし中に本文が編集されたことで、DynamoDB上に新旧2つの投稿由来のコンテンツが同じ日付ラベルで混在する一時的な状態が発生していた。
- **方針決定**: `<title>`は日付以外の値も入力できてしまうため形式外データの混入を避ける目的で、日付ソースは`<published>`のまま維持する方針をユーザーが決定。代わりに**バッチの実行時刻を予約投稿の発火時刻（JST5:00）より後にずらす**ことで、取りこぼし自体を無くす対応とした。
- **対応**: `template.yaml`の`BatchFunction`の`Schedule`を`cron(0 18 * * ? *)`（JST3:00）→`cron(30 20 * * ? *)`（JST5:30）に変更。`sam build && sam deploy`で本番反映済み、EventBridgeルールのスケジュール反映も確認済み。

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
`/aws/lambda/...`のような先頭`/`の引数は、コマンド前に`MSYS_NO_PATHCONV=1`を付ける。**注意**：引数全体が`/`始まりの場合だけでなく、`--environment "Variables={SSM_PARAM_NAME=/hatena-site/access-token}"`のように**引数の中に埋め込まれた`/`始まりの値**でも同様に誤変換される（2026-08-07、合言葉変更作業中に`SSM_PARAM_NAME`の値が`/C`のような意味不明な文字列に壊れる事故が発生。`MSYS_NO_PATHCONV=1`を付けて再実行し復旧）。AWS CLIコマンドの引数に`/`始まりの文字列が一箇所でも含まれる場合は、常に`MSYS_NO_PATHCONV=1`を付ける習慣にする。

### 4.5 `aws lambda invoke`はCLI側の応答待ちタイムアウトで先に諦めることがある
Lambda自体は正常でも、botocore側のHTTP読み取りタイムアウト（デフォルト約60秒）で先にエラーになる。長時間実行が想定される場合は`--cli-read-timeout 910`等を指定し、CloudWatch Logsで実際の結果を確認する。

### 4.6 Vercelの「固有デプロイURL」と「安定ドメイン」の違い
Vercelは各デプロイに固有URL（`https://diary-batch-<ランダム文字列>-jorrytable.vercel.app`）を発行し、それとは別に安定ドメイン（`https://diary-batch.vercel.app`）がある。固有URLは不変なので、新しいpush後もその時点のビルドを配信し続ける。「デプロイしたのに反映されない」という報告時は、まずアクセスURLが安定ドメインかどうかを確認する。

### 4.7 DynamoDB Queryは1回の応答が1MBまで
`Query`/`Scan`は1回のAPI呼び出しにつき最大1MBまでしか返さない。`LastEvaluatedKey`をチェックしてループする実装が必須。

### 4.8 YouTube Musicの利用可否はHTTPスクレイピングで判定不可
`music.youtube.com`は非ブラウザ環境からのアクセスに対し実データではなく固定の代替ページを返す。動画の実際のカテゴリ判定にはYouTube Data API v3の`videos.list`（`snippet.categoryId`）を使う。

### 4.9 合言葉（SSMパラメータ）の変更方法
**2026-08-02更新**: 課題#12対応で`authorizer.py`がSSMパラメータをLambdaのウォームコンテナ内にモジュールスコープでキャッシュするようになったため（[[hatena_diary_app_decisions]]参照）、**値を更新するだけでは既存のウォームコンテナには即時反映されない**（コールドスタートまで古い値が使われ続ける）。値の更新に加えて、`AuthorizerFunction`を強制的に新しい実行環境に切り替える必要がある。
```
MSYS_NO_PATHCONV=1 aws ssm put-parameter --name "/hatena-site/access-token" --value "新しい値" --type SecureString --overwrite
MSYS_NO_PATHCONV=1 aws lambda update-function-configuration --function-name <AuthorizerFunctionの物理名> --environment "Variables={SSM_PARAM_NAME=/hatena-site/access-token}"
```
2つ目のコマンドの`--environment`の値は必ず現状のまま（変更しない）で実行すること。目的は値の変更ではなく、更新をトリガーに全ウォームコンテナを入れ替えさせること。実行後は`aws lambda invoke`で`authorizationToken`に新しい合言葉を渡し、`Effect: "Allow"`が返ることを確認する（2026-08-07、合言葉変更時に本手順で実施・確認済み。実際の合言葉の値は本ファイルには記載しない）。

### 4.10 API GatewayのBinaryMediaTypesはCORSプリフライトを壊すことがある
このAPIでは`BinaryMediaTypes`を設定すると原因不明のままCORSプリフライト（OPTIONSのMock統合）が壊れた（3.1参照）。同様の対応をする場合はAPI Gateway側のバイナリパススルーに頼らず、フロント側で手動base64デコード＋展開する方式を最初から採用すること。

---

## 5. デプロイ関連の実績値（変更されうるので都度確認）
- GitHubリポジトリ: `jorrytable/DiaryBatch`（ブランチ`main`）
- API Gatewayエンドポイント: `https://qg18xf1xq3.execute-api.ap-northeast-1.amazonaws.com/Prod/reviews`（スタック再作成で変わる）
- Vercel安定ドメイン: `https://diary-batch.vercel.app`相当（CORSの`AllowOrigin`は現状`'*'`のままで、実質的な保護はLambda Authorizerが担っている）

---

## 6. 未着手の今後の課題

### 6.1 未着手の課題一覧（2026-08-02時点、番号は本表内限定の通し番号）

出所A: 全ソース4観点レビュー（reuse/simplification/efficiency/altitude）で「安全な項目」以外として見送ったもの。
出所B: ユーザーからの追加起票（2026-08-02）。

2026-08-02、同根と判断した課題をユーザー指示によりそれぞれ1件に統合済み（旧#4・旧#5・旧#16→新#4、旧#12・旧#13→新#11。旧番号は本改訂前のコミット履歴上のみに残る）。

| # | 出所 | 分野 | 課題 | 詳細・備考 |
|---|------|------|------|------------|
| 1 | A | 構造（バックエンド+フロント） | 単一URL/`links`配列の二重データ構造の統合 | `parser.py`/`batch/app.py`/`App.jsx`の3箇所で「1件 vs 複数リンク」の分岐が並行して存在し、重複コードの根本原因。`links`配列に統一すれば解消するが、データモデル変更のため既存テスト(`test_parser.py`)の書き直しを伴う。 |
| 2 | A | バックエンド（性能） | バッチジョブの差分同期化 | `batch/app.py`が毎回Atomフィード全履歴を再取得・再パースし、DynamoDBも毎回全件削除→全件書き込みしている。差分方式にすればLambda実行時間・書き込みコストを削減できるが、挙動変更を伴うアーキテクチャ変更のため別途相談。 |
| 3 | A | バックエンド（性能） | oEmbed取得の並列化 | `batch/enrich.py`の未キャッシュURL取得（最大200件）が逐次実行。`ThreadPoolExecutor`等で並列化すれば短縮できるが、外部サービスへのレート制限リスクを考慮した設計が必要。 |
| 4 | A+B | バックエンド主体（一部フロント） | 埋め込み/メタデータのドメイン別処理の汎用化（タグ抽出・embed種別判定を含む） | 統合元3件は根本原因が共通：`enrich.py`の`_fetch_oembed`がYouTube専用ロジックを`YOUTUBE_HOSTS`のその場凌ぎif分岐で持っており、ドメインごとの追加処理を汎用的にフック化する仕組みが無い。結果として①YouTube専用分岐がenrich.py内に居座り、②フロントエンド`App.jsx`の`isVideoEmbed`がembed種別(video/compact)判定をURLのsubstringで独自に再実装せざるを得ず`classify.py`/`enrich.py`のドメイン知識と3重管理になり、③Spotify(番組名/アーティスト名)・note(オーサー情報)・カスタムタイトルのタグ抽出を追加しようとすると同じ場当たり的パターンが増える。対応方針：ドメインごとの後処理フック（タグ抽出・genre上書き・フロント向けembed種別ヒント等）をテーブル駆動で定義できる仕組みに一般化し、そこにSpotify/note等の抽出ロジックとembed種別ヒントの算出をまとめて追加する。 |
| 5 | A | バックエンド（構造・見送り推奨） | Spotifyパス別分岐の一般化 | `classify.py`の`DOMAIN_RULES`（ジャンル分類）にSpotifyのepisode/show判定がその場凌ぎのif分岐で入っている。#4と似た「ドメイン別特殊分岐」パターンだが、対象が別ファイル・別ロジック（ジャンル分類 vs メタデータ/タグ抽出）のため統合はせず別課題とした。現状Spotifyの1ケースのみのため、テーブル駆動化は時期尚早と判断し見送り推奨。 |
| 6 | A | バックエンド（構造・見送り推奨） | `_extract_subtitle`の宣言的書き換え | `parser.py`。逐次的な文字列加工の積み重ねになっているが、コアなパース処理でリグレッションリスクがある。 |
| 7 | B | フロントエンド | タグバッジの表示色変更 | 現行の紫→グレーに変更。 |
| 8 | B | フロントエンド | 検索フィールドの各コントロールの位置整理 | 検索ボタンとリセット（条件をすべてクリア）ボタンの位置関係、統合検索ボックス内の「×」クリアボタンの扱い。 |
| 9 | B | フロントエンド | スマートフォン対応 | スマートフォン表示時に検索フィールド一式の高さを低くする。 |
| 10 | B | バックエンド | 分類ロジックの見直し | 「テキスト」「ラジオ」ジャンルへの対応ドメイン追加。`classify.py`の`DOMAIN_RULES`にエントリを増やす想定（#5とは異なり、既存の仕組みのままエントリを増やすだけで対応可能）。 |
| 11 | B | バックエンド | レビュー本文（自由記述部分）のパース範囲拡張（脚注内容・深い階層の箇条書き） | 統合元2件は根本原因が共通：`parser.py`の本文パースが「- 」（作品名）「-- 」（感想）の2階層＋脚注記号`((...))`の除去、という現状のモデルしかカバーしておらず、実際の日記本文にはそれ以上の階層や脚注中身が含まれることがある。①注（脚注）の中身自体を取り込むか、②「--- 」等さらに深い階層の記法をどう解釈するか、いずれも本文パースモデル自体の要ヒアリング・再設計を要する。 |
| ~~12~~ | B | バックエンド | ~~初回読み込み時間の短縮~~ → **2026-08-07クローズ（ユーザー確認：体感改善済み）** | 実測（`aws lambda invoke`で直接計測、現存エントリ数1309件）: `SearchFunction`のDuration約2.9秒→`MemorySize`を1769MB（Lambdaが1vCPUをフル割当する境界値）に引き上げて約0.9秒（約3.2倍高速化）。`json.dumps`/`gzip.compress`がCPU律速（GIL）だったことが原因。`AuthorizerFunction`は512MBのまま据え置き（既存のSSMキャッシュ化で warm時約1ms）。デプロイ後、ユーザーより「軽くなりました」と体感改善の報告あり、クローズ。**保留した二次対応**（必要になれば再起票）：①ペイロードサイズ削減（embed_html等を初回ロードから外す・ページング化。課題#1のlinks統合と関連）②Provisioned Concurrency導入（個人利用の低頻度アクセスでは費用対効果が悪く見送り推奨）③フロントの`decodeGzipBase64Json`のストリーミング化（体感寄与度が低いと判断）。 |
| 13 | B | フロントエンド | 各操作ボタン押下時にスクロール位置を最上部に戻す | 検索ボタン・条件をすべてクリアボタン・ページ送り（次へ/前へ）ボタンを押しても、一覧の途中にスクロールしたままになる。`App.jsx`の該当ハンドラ（`executeSearch`/`clearAllFilters`/`goToPrevPage`/`goToNextPage`）に`window.scrollTo`等の追加が必要と想定。 |

### 6.2 対応不要と判断してクローズした項目
- **titleに混入するサービス名接尾辞**: Amazon Prime Videoの`:title=`値が`カルテット | Amazon Prime Video`のようにサービス名接尾辞込みでそのまま入る件。ユーザーが「その記述をそのまま生かす」として対応不要と判断。表示title文字列のみへの影響（対象はAmazon Prime Videoの案件のみ）で、セキュリティ・データ整合性・他機能への影響はなく、深刻なリスクは無いと判断。
