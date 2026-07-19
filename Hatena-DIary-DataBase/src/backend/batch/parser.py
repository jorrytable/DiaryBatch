import uuid
import re

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

                # リンクとタイトルを抽出 [URL:title] または [URL] の形式
                # 正規表現でURLとタイトル部分を抜き出す
                match = re.search(r'\[(https?://[^\s\]]+):title\]', line)
                if not match:
                    match = re.search(r'\[(https?://[^\s\]]+)\]', line)
                
                if match:
                    url = match.group(1)
                    # タイトル部分（:titleがあれば取得、なければURL）
                    title_match = re.search(r':title=([^\]]+)\]', line)
                    title = title_match.group(1) if title_match else url
                    
                    current_item = {
                        'id': str(uuid.uuid4()),
                        'data_type': 'review',
                        'review_date': date_str,
                        'title': title,
                        'url': url,
                        'genre': "Web",
                        'impression': ""
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