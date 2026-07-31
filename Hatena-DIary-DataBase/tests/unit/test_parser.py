import sys
print(sys.path)

from src.backend.batch.parser import parse_html_content

def test_kanryo():
    # 実際のはてな記法（プレーンテキスト）に合わせたニセ日記データ
    content = "*** 今日見たもの\n- [http://x.com]\n-- 面白かった"
    kekka = parse_html_content(content, "2026-01-05")

    # ちゃんと1件抜き出せたか確認
    assert len(kekka) == 1
    # title未指定行はNone（実タイトルは後段のenrich処理で取得するマーカー）
    assert kekka[0]['title'] is None
    assert kekka[0]['url'] == "http://x.com"
    assert kekka[0]['impression'] == "面白かった"
    print("\n★テスト成功！正しく抜き出せています★")


def test_url_with_custom_title_notation_extracts_bare_url():
    # [url:title=カスタムタイトル] 形式で、URLに ":title=..." が混入しないことを確認
    content = "*** 今日見たもの\n- [http://x.com:title=テスト動画]\n-- 面白かった"
    kekka = parse_html_content(content, "2026-01-05")

    assert len(kekka) == 1
    assert kekka[0]['url'] == "http://x.com"
    assert kekka[0]['title'] == "テスト動画"


def test_url_with_bare_title_marker_has_no_title():
    # [url:title]（カスタムタイトルなし）はURLのみ抽出し、titleはNone（後段fetchマーカー）のまま
    content = "*** 今日見たもの\n- [http://x.com:title]\n-- 面白かった"
    kekka = parse_html_content(content, "2026-01-05")

    assert len(kekka) == 1
    assert kekka[0]['url'] == "http://x.com"
    assert kekka[0]['title'] is None


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
