import uuid
import re

from batch.classify import classify_genre_and_tags, classify_from_content


def parse_html_content(content_text: str,
                       date_str: any) -> list:
    results = []
    lines = content_text.splitlines()

    is_target_section = False
    current_item = None

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
                if current_item:
                    results.append(current_item)

                # リンクとタイトルを抽出。[URL] / [URL:title] / [URL:title=カスタムタイトル] のいずれの形式にも対応する。
                # URL部分は非貪欲マッチにして、":title"以降をURLに巻き込まないようにする。
                url_match = re.search(r'\[(https?://[^\s\]]+?)(?::title(?:=([^\]]*))?)?\]', line)

                # URLが無くても「- 映画『』」「- TVアニメ『』」等の記法ならアイテムとして採用する
                content_rule = classify_from_content(line)

                if url_match or content_rule:
                    if url_match:
                        url = url_match.group(1)
                        # カスタムタイトル（:title=）があれば取得、なければNone＝後段でページタイトルを取得する必要ありのマーカー
                        title = url_match.group(2)
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
                            quote_match = re.search(r'『(.+?)』', line)
                            title = quote_match.group(1) if quote_match else line[len('- '):].strip()

                    # テレビタグの番組は「- 局名『[url:title=番組名]』第N話「サブタイトル」[url:embed]」のように
                    # 番組名リンクの後ろに話数・「」区切りのサブタイトルが続く記法があるため、
                    # 番組名の直後〜次の「[」（埋め込みリンク）までのテキストをsubtitleとして別項目に抜き出す
                    subtitle = ""
                    if url_match and title and 'テレビ' in tags:
                        remainder = line[url_match.end():]
                        if remainder.startswith('』'):
                            remainder = remainder[1:]
                        remainder = remainder.split('[', 1)[0].strip()
                        if remainder:
                            # 複数話をまとめて書く場合の区切り「・」は改行に変換する。
                            # ただし「」で囲まれたサブタイトル文言内の「・」はそのまま残す
                            # （「」部分を丸ごと温存し、その外側だけを置換対象にする）
                            parts = re.split(r'(「[^」]*」)', remainder)
                            subtitle = ''.join(
                                part if part.startswith('「') else part.replace('・', '\n')
                                for part in parts
                            )

                    current_item = {
                        'id': str(uuid.uuid4()),
                        'data_type': 'review',
                        'review_date': date_str,
                        'title': title,
                        'url': url,
                        'genre': genre,
                        'tags': tags,
                        'impression': "",
                        'subtitle': subtitle
                    }
                else:
                    current_item = None

            # 4. 感想（行頭が「-- 」で始まる行）
            elif line.startswith('-- ') and current_item:
                impression = line.lstrip('- ').strip()
                # 脚注記号 ((...)) などを除去（任意ですが、きれいに見せるため）
                impression = re.sub(r'\(\(.*?\)\)', '', impression)

                if current_item['impression']:
                    current_item['impression'] += "\n" + impression
                else:
                    current_item['impression'] = impression

    # 最後のアイテムをリストに追加
    if current_item:
        results.append(current_item)

    return results
