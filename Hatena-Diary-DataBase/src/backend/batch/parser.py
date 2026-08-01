import uuid
import re

from batch.classify import classify_genre_and_tags, classify_from_content

# 埋め込み専用ブラケット（[url:embed]）。自前でoEmbed/OGPを取得するため中身は使わず、
# タイトル/サブタイトル抽出の邪魔にならないよう事前に取り除く
_EMBED_BRACKET_RE = re.compile(r'\[https?://[^\s\]]+?:embed\]')

# リンクとタイトルを抽出するパターン。[URL] / [URL:title] / [URL:title=カスタムタイトル] のいずれにも対応する。
# URL部分は非貪欲マッチにして、":title"以降をURLに巻き込まないようにする。
_URL_TITLE_RE = re.compile(r'\[(https?://[^\s\]]+?)(?::title(?:=([^\]]*))?)?\]')

# 感想本文中に残るはてな記法（[url] / [url:title] / [url:title=カスタムタイトル] / [url:embed]）を検出するパターン
_IMPRESSION_TOKEN_RE = re.compile(r'\[(https?://[^\s\]]+?)(?::(title(?:=([^\]]*))?|embed))?\]')


def tokenize_impression(text: str):
    # 感想本文中のはてな記法（インラインリンク・埋め込みマーカー）をテキスト/リンク/埋め込みの
    # セグメント列に分解する。記法が1つも無ければNoneを返す（呼び出し側は生テキスト表示にフォールバックする）。
    matches = list(_IMPRESSION_TOKEN_RE.finditer(text))
    if not matches:
        return None

    segments = []
    pos = 0
    for m in matches:
        if m.start() > pos:
            segments.append({'type': 'text', 'text': text[pos:m.start()]})

        url = m.group(1)
        modifier = m.group(2)
        if modifier == 'embed':
            segments.append({'type': 'embed', 'url': url, 'title': None})
        else:
            # :title= があればそれを使い、無ければNone（後段のenrichで解決するマーカー）
            title = m.group(3) if modifier else None
            segments.append({'type': 'link', 'url': url, 'title': title})

        pos = m.end()

    if pos < len(text):
        segments.append({'type': 'text', 'text': text[pos:]})

    return segments


def flatten_impression_segments(segments) -> str:
    # 検索対象の平文impressionを再構成する。テキストはそのまま、リンクはtitle（未確定ならurl）、
    # 埋め込みは意味のある平文が無いため何も出力しない。
    parts = []
    for seg in segments:
        if seg['type'] == 'text':
            parts.append(seg['text'])
        elif seg['type'] == 'link':
            parts.append(seg.get('title') or seg['url'])
    return ''.join(parts)


def _extract_subtitle(text: str) -> str:
    # 動画・番組系のリンクは「[url:title=タイトル] 第N話「サブタイトル」」のように、
    # リンクの後ろに話数・「」区切りのサブタイトルが続く記法があるため、その部分を抜き出す。
    if text.startswith('』'):
        text = text[1:]
    text = text.strip()
    # 複数リンクを" / "等で並記する記法の区切り文字だけが残った場合は中身なしとして扱う
    text = text.strip('/').strip()
    # 話数列挙全体が括弧で囲まれている場合、括弧自体は表示上不要なので取り除く
    if (text.startswith('(') and text.endswith(')')) or \
       (text.startswith('（') and text.endswith('）')):
        text = text[1:-1].strip()
    if not text:
        return ""
    # 複数話をまとめて書く場合の区切り「・」は改行に変換する。
    # ただし「」で囲まれたサブタイトル文言内の「・」はそのまま残す
    # （「」部分を丸ごと温存し、その外側だけを置換対象にする）
    parts = re.split(r'(「[^」]*」)', text)
    return ''.join(
        part if part.startswith('「') else part.replace('・', '\n')
        for part in parts
    )


def parse_html_content(content_text: str,
                       date_str: any) -> list:
    results = []
    lines = content_text.splitlines()

    is_target_section = False
    current_items = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 1. 「*** 今日見たもの」という見出しを探す
        if '***' in line and '今日見たもの' in line:
            is_target_section = True
            continue

        # 2. 次の見出し（***）が来たら終了
        if is_target_section and line.startswith('***') and '今日見たもの' not in line:
            break

        if is_target_section:
            # 3. 作品名（行頭が「- 」で始まる行）
            if line.startswith('- '):
                # 直前のアイテムがあれば保存
                results.extend(current_items)
                current_items = []

                line_no_embed = _EMBED_BRACKET_RE.sub('', line)
                url_matches = list(_URL_TITLE_RE.finditer(line_no_embed))

                # URLが無くても「- 映画『』」「- TVアニメ『』」等の記法ならアイテムとして採用する
                content_rule = classify_from_content(line_no_embed)

                if len(url_matches) >= 2:
                    # "[url1:title] / [url2:title] / ..." のように1行に複数リンクが
                    # 並記されている場合は、ブログ本文の見た目どおり1アイテムにまとめる
                    # （タイトルを並べた後にすべての埋め込みを続けて表示する）。
                    # ジャンル・タグはリンク群を代表して先頭リンクの判定を採用する。
                    links = []
                    for i, m in enumerate(url_matches):
                        url = m.group(1)
                        title = m.group(2)

                        start = m.end()
                        end = url_matches[i + 1].start() if i + 1 < len(url_matches) else len(line_no_embed)
                        subtitle = _extract_subtitle(line_no_embed[start:end])

                        links.append({
                            'url': url,
                            'title': title,
                            'subtitle': subtitle
                        })

                    genre, tags = classify_genre_and_tags(links[0]['url'])

                    current_items.append({
                        'id': str(uuid.uuid4()),
                        'data_type': 'review',
                        'review_date': date_str,
                        'title': None,
                        'url': "",
                        'genre': genre,
                        'tags': tags,
                        'impression': "",
                        'subtitle': "",
                        'links': links
                    })
                elif url_matches or content_rule:
                    if url_matches:
                        url = url_matches[0].group(1)
                        # カスタムタイトル（:title=）があれば取得、なければNone＝後段でページタイトルを取得する必要ありのマーカー
                        title = url_matches[0].group(2)
                        genre, tags = classify_genre_and_tags(url)
                    else:
                        url = ""
                        title = None
                        genre, tags = 'その他', []

                    if content_rule:
                        genre = content_rule[0]
                        if content_rule[1] not in tags:
                            tags = tags + [content_rule[1]]
                        if title is None:
                            quote_match = re.search(r'『(.+?)』', line_no_embed)
                            title = quote_match.group(1) if quote_match else line_no_embed[len('- '):].strip()

                    # ジャンル・タグは問わない（テレビ局サイトに限らずAmazon Prime Video等でも同じ記法が使われるため）
                    subtitle = _extract_subtitle(line_no_embed[url_matches[0].end():]) if url_matches else ""

                    current_items.append({
                        'id': str(uuid.uuid4()),
                        'data_type': 'review',
                        'review_date': date_str,
                        'title': title,
                        'url': url,
                        'genre': genre,
                        'tags': tags,
                        'impression': "",
                        'subtitle': subtitle
                    })
                # どちらにも該当しない場合、current_itemsは空のまま（このアイテムは不採用）

            # 4. 感想（行頭が「-- 」で始まる行）
            elif line.startswith('-- ') and current_items:
                impression = line.lstrip('- ').strip()
                # 脚注記号 ((...)) などを除去（任意ですが、きれいに見せるため）
                impression = re.sub(r'\(\(.*?\)\)', '', impression)

                # 1つの「- 」行から複数アイテムに分割された場合、感想は全アイテムに反映する
                for item in current_items:
                    if item['impression']:
                        item['impression'] += "\n" + impression
                    else:
                        item['impression'] = impression

    # 最後のアイテムをリストに追加
    results.extend(current_items)

    # 感想本文にはてな記法（インラインリンク・埋め込みマーカー）が残っていれば
    # セグメント配列に分解する。無ければimpressionは生テキストのまま。
    for item in results:
        segments = tokenize_impression(item['impression'])
        if segments is not None:
            item['impression_segments'] = segments
            item['impression'] = flatten_impression_segments(segments)

    return results
