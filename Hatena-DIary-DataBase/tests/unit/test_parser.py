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


def test_tv_program_with_episode_number_extracts_subtitle():
    content = "*** 今日見たもの\n- TBSテレビ『[https://www.tbs.co.jp/VIVANT_tbs/:title=VIVANT]』第11話[https://www.tbs.co.jp/VIVANT_tbs/:embed]"
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['title'] == "VIVANT"
    assert results[0]['url'] == "https://www.tbs.co.jp/VIVANT_tbs/"
    assert results[0]['genre'] == "映像"
    assert results[0]['tags'] == ["テレビ"]
    assert results[0]['subtitle'] == "第11話"


def test_tv_program_with_episode_number_and_quoted_subtitle():
    content = (
        "*** 今日見たもの\n"
        "- TBSテレビ『[https://www.tbs.co.jp/umininemuru_diamond_tbs/:title=海に眠るダイヤモンド]』"
        "第2話「スクエアダンス」[https://www.tbs.co.jp/umininemuru_diamond_tbs/:embed]"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['title'] == "海に眠るダイヤモンド"
    assert results[0]['subtitle'] == "第2話「スクエアダンス」"


def test_tv_program_with_multiple_quoted_segments_and_no_episode_number():
    content = (
        "*** 今日見たもの\n"
        "- TBSテレビ『[https://www.tbs.co.jp/suiyobinodowntown/:title=水曜日のダウンタウン]』"
        "「記憶喪失王決定戦」「大鶴肥満が酔い潰れたら一巻の終わり説」"
        "[https://www.tbs.co.jp/suiyobinodowntown/:embed]"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['title'] == "水曜日のダウンタウン"
    assert results[0]['subtitle'] == "「記憶喪失王決定戦」「大鶴肥満が酔い潰れたら一巻の終わり説」"


def test_tv_program_with_single_quoted_segment():
    content = (
        "*** 今日見たもの\n"
        "- TBSテレビ『[https://www.tbs.co.jp/johnson_tbs/:title=ジョンソン]』"
        "「芸人大運動会2023★総勢59人の人気芸人が大集合」"
        "[https://www.tbs.co.jp/johnson_tbs/:embed]"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['title'] == "ジョンソン"
    assert results[0]['subtitle'] == "「芸人大運動会2023★総勢59人の人気芸人が大集合」"


def test_tv_program_with_multiple_episodes_converts_nakaguro_to_newlines():
    content = (
        "*** 今日見たもの\n"
        "- TBSテレビ『[https://www.tbs.co.jp/umininemuru_diamond_tbs/:title=海に眠るダイヤモンド]』"
        "第2話「スクエアダンス」・第3話「孤島の花」・第4話「沈黙」・第5話「一島一家」・"
        "第6話「希望の種」・第7話「消えない火」・第8話「ダイヤモンド」"
        "[https://www.tbs.co.jp/umininemuru_diamond_tbs/:embed]"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['title'] == "海に眠るダイヤモンド"
    assert results[0]['subtitle'] == (
        "第2話「スクエアダンス」\n"
        "第3話「孤島の花」\n"
        "第4話「沈黙」\n"
        "第5話「一島一家」\n"
        "第6話「希望の種」\n"
        "第7話「消えない火」\n"
        "第8話「ダイヤモンド」"
    )


def test_non_tv_item_has_empty_subtitle():
    content = "*** 今日見たもの\n- [https://www.youtube.com/watch?v=x:title=何かの動画]\n-- 良かった"
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['subtitle'] == ""


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
