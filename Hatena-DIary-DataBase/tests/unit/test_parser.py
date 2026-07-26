import sys
print(sys.path)

from src.backend.batch.parser import parse_html_content, classify_genre

def test_kanryo():
    # 実験用のニセ日記データ
    test_html = "<h3>*** 今日見たもの</h3><ul><li><a href='http://x.com'>テスト動画</a><ul><li>面白かった</li></ul></li></ul>"
    kekka = parse_html_content(test_html, "2026-01-05")

    # ちゃんと1件抜き出せたか確認
    assert len(kekka) == 1
    assert kekka[0]['title'] == "テスト動画"
    print("\n★テスト成功！正しく抜き出せています★")


def test_classify_genre_known_domain():
    assert classify_genre("https://www.youtube.com/watch?v=x") == "映像"


def test_classify_genre_subdomain():
    assert classify_genre("https://m.youtube.com/watch?v=x") == "映像"


def test_classify_genre_unknown_domain():
    assert classify_genre("https://example.com/page") == "その他"


def test_classify_genre_radiko():
    assert classify_genre("https://radiko.jp/#!/live/TBS") == "ラジオ"


def test_classify_genre_spotify_episode_is_radio():
    assert classify_genre("https://open.spotify.com/episode/abc123") == "ラジオ"


def test_classify_genre_spotify_show_is_radio():
    assert classify_genre("https://open.spotify.com/show/abc123") == "ラジオ"


def test_classify_genre_spotify_track_is_music():
    assert classify_genre("https://open.spotify.com/track/abc123") == "音楽"