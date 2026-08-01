from urllib.parse import urlparse

from common.urls import hostname as _hostname

# ドメイン(ホスト名)→(genre, tags)の対応表。網羅的ではなく随時追記していく前提の初期値
DOMAIN_RULES = {
    # 映像
    'youtube.com': ('映像', []),
    'youtu.be': ('映像', []),
    'nicovideo.jp': ('映像', []),
    'tver.jp': ('映像', []),
    'abema.tv': ('映像', []),
    'netflix.com': ('映像', []),
    'twitch.tv': ('映像', []),
    'watch.amazon.co.jp': ('映像', []),
    'animestore.docomo.ne.jp': ('映像', ['TVアニメ']),
    # 地上波・BSキー局・お笑い賞レース等（タグ「テレビ」）
    'nhk.or.jp': ('映像', ['テレビ']),
    'ntv.co.jp': ('映像', ['テレビ']),
    'tv-asahi.co.jp': ('映像', ['テレビ']),
    'tbs.co.jp': ('映像', ['テレビ']),
    'tv-tokyo.co.jp': ('映像', ['テレビ']),
    'fujitv.co.jp': ('映像', ['テレビ']),
    'ytv.co.jp': ('映像', ['テレビ']),
    'asahi.co.jp': ('映像', ['テレビ']),
    'mbs.jp': ('映像', ['テレビ']),
    'ktv.jp': ('映像', ['テレビ']),
    'tv-osaka.co.jp': ('映像', ['テレビ']),
    'ctv.co.jp': ('映像', ['テレビ']),
    'nagoyatv.co.jp': ('映像', ['テレビ']),
    'hicbc.com': ('映像', ['テレビ']),
    'tv-aichi.co.jp': ('映像', ['テレビ']),
    'tokai-tv.com': ('映像', ['テレビ']),
    'bs4.jp': ('映像', ['テレビ']),
    'bs-asahi.or.jp': ('映像', ['テレビ']),
    'bs.tbs.or.jp': ('映像', ['テレビ']),
    'bsfuji.tv': ('映像', ['テレビ']),
    'bs10.jp': ('映像', ['テレビ']),
    'bs11.jp': ('映像', ['テレビ']),
    'twellv.co.jp': ('映像', ['テレビ']),
    'm-1gp.com': ('映像', ['テレビ']),
    'king-of-conte.com': ('映像', ['テレビ']),
    'r-1gp.com': ('映像', ['テレビ']),
    # 音楽
    'music.youtube.com': ('音楽', []),
    'open.spotify.com': ('音楽', []),
    'music.apple.com': ('音楽', []),
    'soundcloud.com': ('音楽', []),
    # ゲーム
    'store.steampowered.com': ('ゲーム', []),
    'store.epicgames.com': ('ゲーム', []),
    'nintendo.com': ('ゲーム', []),
    'store.playstation.com': ('ゲーム', []),
    # テキスト
    'kakuyomu.jp': ('テキスト', []),
    'syosetu.com': ('テキスト', []),
    'note.com': ('テキスト', []),
    'qiita.com': ('テキスト', []),
    'zenn.dev': ('テキスト', []),
    'asahi.com': ('テキスト', []),
    'jstage.jst.go.jp': ('テキスト', []),
    'ddnavi.com': ('テキスト', []),
    'webgenron.com': ('テキスト', []),
    'president.jp': ('テキスト', []),
    'omocoro.jp': ('テキスト', []),
    'nikkei.com': ('テキスト', []),
    'co-coco.jp': ('テキスト', []),
    # 体験
    'tabelog.com': ('体験', []),
    'retty.me': ('体験', []),
    'jalan.net': ('体験', []),
    'ikyu.com': ('体験', []),
    # ラジオ
    'radiko.jp': ('ラジオ', []),
}


def classify_genre_and_tags(url: str) -> tuple:
    host = _hostname(url)

    # Spotifyはpodcast(episode/show)のみラジオ扱いにし、それ以外(track/album/playlist等)は音楽のまま
    if host == 'open.spotify.com':
        path = urlparse(url).path
        if path.startswith('/episode/') or path.startswith('/show/'):
            return 'ラジオ', []

    if host in DOMAIN_RULES:
        genre, tags = DOMAIN_RULES[host]
        return genre, list(tags)

    for domain, (genre, tags) in DOMAIN_RULES.items():
        if host.endswith('.' + domain):
            return genre, list(tags)

    return 'その他', []


# 日記本文の行の接頭辞→(genre, tag)。URLが無い作品名行から分類するためのルール
CONTENT_PREFIX_RULES = [
    ('- 映画『', '映像', '映画'),
    ('- TVアニメ『', '映像', 'TVアニメ'),
]


def classify_from_content(line: str):
    for prefix, genre, tag in CONTENT_PREFIX_RULES:
        if line.startswith(prefix):
            return genre, tag
    return None
