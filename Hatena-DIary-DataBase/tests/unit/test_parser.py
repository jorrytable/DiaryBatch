import sys
print(sys.path)

from src.backend.batch.parser import parse_html_content

def test_kanryo():
    # 実験用のニセ日記データ
    test_html = "<h3>*** 今日見たもの</h3><ul><li><a href='http://x.com'>テスト動画</a><ul><li>面白かった</li></ul></li></ul>"
    kekka = parse_html_content(test_html, "2026-01-05")

    # ちゃんと1件抜き出せたか確認
    assert len(kekka) == 1
    assert kekka[0]['title'] == "テスト動画"
    print("\n★テスト成功！正しく抜き出せています★")


def test_movie_line_without_url_is_captured():
    content = "*** 今日見たもの\n- 映画『花のあすか組』\n-- 面白かった"
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['title'] == "花のあすか組"
    assert results[0]['url'] == ""
    assert results[0]['genre'] == "映像"
    assert results[0]['tags'] == ["映画"]
    assert results[0]['impression'] == "面白かった"


def test_tv_anime_line_without_url_is_captured():
    content = "*** 今日見たもの\n- TVアニメ『葬送のフリーレン』"
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['title'] == "葬送のフリーレン"
    assert results[0]['url'] == ""
    assert results[0]['genre'] == "映像"
    assert results[0]['tags'] == ["TVアニメ"]
