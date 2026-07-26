import uuid
import re
from urllib.parse import urlparse

# ドメイン(ホスト名)→ジャンルの対応表。網羅的ではなく随時追記していく前提の初期値
GENRE_DOMAIN_MAP = {
    # 映像
    'youtube.com': '映像',
    'youtu.be': '映像',
    'nicovideo.jp': '映像',
    'tver.jp': '映像',
    'abema.tv': '映像',
    'netflix.com': '映像',
    'twitch.tv': '映像',
    # 音楽
    'music.youtube.com': '音楽',
    'open.spotify.com': '音楽',
    'music.apple.com': '音楽',
    'soundcloud.com': '音楽',
    # ゲーム
    'store.steampowered.com': 'ゲーム',
    'store.epicgames.com': 'ゲーム',
    'nintendo.com': 'ゲーム',
    'store.playstation.com': 'ゲーム',
    # テキスト
    'kakuyomu.jp': 'テキスト',
    'syosetu.com': 'テキスト',
    'note.com': 'テキスト',
    'qiita.com': 'テキスト',
    'zenn.dev': 'テキスト',
    # 体験
    'tabelog.com': '体験',
    'retty.me': '体験',
    'jalan.net': '体験',
    'ikyu.com': '体験',
}


def classify_genre(url: str) -> str:
    hostname = urlparse(url).netloc.lower()
    if hostname.startswith('www.'):
        hostname = hostname[len('www.'):]

    if hostname in GENRE_DOMAIN_MAP:
        return GENRE_DOMAIN_MAP[hostname]

    for domain, genre in GENRE_DOMAIN_MAP.items():
        if hostname.endswith('.' + domain):
            return genre

    return 'その他'


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
                    # タイトル部分（:titleがあれば取得、なければNone＝後段でページタイトルを取得する必要ありのマーカー）
                    title_match = re.search(r':title=([^\]]+)\]', line)
                    title = title_match.group(1) if title_match else None

                    current_item = {
                        'id': str(uuid.uuid4()),
                        'data_type': 'review',
                        'review_date': date_str,
                        'title': title,
                        'url': url,
                        'genre': classify_genre(url),
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