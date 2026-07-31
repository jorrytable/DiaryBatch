import sys
print(sys.path)

from src.backend.batch.parser import parse_html_content, tokenize_impression, flatten_impression_segments

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


def test_tokenize_impression_no_notation_returns_none():
    assert tokenize_impression("普通の感想文だけ") is None


def test_tokenize_impression_link_and_embed_real_example():
    text = (
        "[https://youtu.be/9BB8zcWZ3VU:title=前の動画]を見返していたら本当にパフォーマンスが高すぎて"
        "腹捩れたので、頼むから幸せになってほしいなと願わずにはいられなかった 叶え！"
        "[https://youtu.be/9BB8zcWZ3VU:embed]"
    )
    segments = tokenize_impression(text)

    assert segments == [
        {'type': 'link', 'url': 'https://youtu.be/9BB8zcWZ3VU', 'title': '前の動画'},
        {
            'type': 'text',
            'text': (
                "を見返していたら本当にパフォーマンスが高すぎて腹捩れたので、"
                "頼むから幸せになってほしいなと願わずにはいられなかった 叶え！"
            ),
        },
        {'type': 'embed', 'url': 'https://youtu.be/9BB8zcWZ3VU', 'title': None},
    ]


def test_flatten_impression_segments_uses_title_and_skips_embed():
    segments = [
        {'type': 'link', 'url': 'https://x.com', 'title': 'リンク先'},
        {'type': 'text', 'text': 'を見た'},
        {'type': 'embed', 'url': 'https://x.com', 'title': None},
    ]
    assert flatten_impression_segments(segments) == "リンク先を見た"


def test_flatten_impression_segments_falls_back_to_url_when_title_unresolved():
    segments = [{'type': 'link', 'url': 'https://x.com', 'title': None}]
    assert flatten_impression_segments(segments) == "https://x.com"


def test_parse_html_content_impression_with_inline_link_and_embed():
    content = (
        "*** 今日見たもの\n"
        "- [https://youtu.be/9BB8zcWZ3VU:title=前の動画]\n"
        "-- [https://youtu.be/AAAA:title=別の動画]を見返していたら最高だった[https://youtu.be/AAAA:embed]"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    segments = results[0]['impression_segments']
    assert segments[0] == {'type': 'link', 'url': 'https://youtu.be/AAAA', 'title': '別の動画'}
    assert segments[-1] == {'type': 'embed', 'url': 'https://youtu.be/AAAA', 'title': None}
    assert results[0]['impression'] == "別の動画を見返していたら最高だった"


def test_parse_html_content_impression_without_notation_has_no_segments():
    content = "*** 今日見たもの\n- [http://x.com]\n-- 普通の感想"
    results = parse_html_content(content, "2026-01-05")

    assert 'impression_segments' not in results[0]
    assert results[0]['impression'] == "普通の感想"


def test_multi_link_spotify_line_becomes_single_item_with_links():
    content = (
        "*** 今日見たもの\n"
        "- [https://open.spotify.com/episode/7oAW6149hWPcAVihImVuAl:title] / "
        "[https://open.spotify.com/episode/1CramcCoktxTn8xcUDUij3:title]"
        "[https://open.spotify.com/episode/7oAW6149hWPcAVihImVuAl:embed]"
        "[https://open.spotify.com/episode/1CramcCoktxTn8xcUDUij3:embed]\n"
        "-- どちらも面白かった"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['genre'] == "ラジオ"
    assert results[0]['impression'] == "どちらも面白かった"
    assert len(results[0]['links']) == 2
    assert results[0]['links'][0]['url'] == "https://open.spotify.com/episode/7oAW6149hWPcAVihImVuAl"
    assert results[0]['links'][0]['subtitle'] == ""
    assert results[0]['links'][1]['url'] == "https://open.spotify.com/episode/1CramcCoktxTn8xcUDUij3"
    assert results[0]['links'][1]['subtitle'] == ""


def test_multi_link_youtube_line_becomes_single_item_with_three_links():
    content = (
        "*** 今日見たもの\n"
        "- [https://youtu.be/wAF0DOomCdk:title] / "
        "[https://youtu.be/6omZRLUmSVA:title] / "
        "[https://youtu.be/kk_-1-fsHlM:title]"
        "[https://youtu.be/wAF0DOomCdk:embed]"
        "[https://youtu.be/6omZRLUmSVA:embed]"
        "[https://youtu.be/kk_-1-fsHlM:embed]"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['genre'] == "映像"
    assert [l['url'] for l in results[0]['links']] == [
        "https://youtu.be/wAF0DOomCdk",
        "https://youtu.be/6omZRLUmSVA",
        "https://youtu.be/kk_-1-fsHlM",
    ]
    assert all(l['subtitle'] == "" for l in results[0]['links'])


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


def test_tv_program_keeps_nakaguro_inside_quoted_subtitle():
    # 「」内の「・」は改行にせず、そのまま残す
    content = (
        "*** 今日見たもの\n"
        "- TBSテレビ『[https://www.tbs.co.jp/example_tbs/:title=サンプル番組]』"
        "第1話「サスペンス・ホラー編」・第2話「コメディ編」"
        "[https://www.tbs.co.jp/example_tbs/:embed]"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['subtitle'] == "第1話「サスペンス・ホラー編」\n第2話「コメディ編」"


def test_parenthesized_two_episodes_strips_parens():
    content = (
        "*** 今日見たもの\n"
        "- [https://animestore.docomo.ne.jp/animestore/ci_pc?workId=99999:title] "
        "(第1話・第2話)"
        "[https://animestore.docomo.ne.jp/animestore/ci_pc?workId=99999:embed]"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['subtitle'] == "第1話\n第2話"


def test_non_tv_item_has_empty_subtitle():
    content = "*** 今日見たもの\n- [https://www.youtube.com/watch?v=x:title=何かの動画]\n-- 良かった"
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['subtitle'] == ""


def test_amazon_prime_video_subtitle_extracted_without_tv_tag():
    # テレビタグが付かないジャンル（映像、タグなし）でも、リンク直後の話数表記はsubtitleに抜き出す
    content = (
        "*** 今日見たもの\n"
        "- [https://watch.amazon.co.jp/detail?gti=amzn1.dv.gti.b2acd844-523a-5e5d-e9ff-578863f17b19"
        ":title=カルテット | Amazon Prime Video] 第1話・第2話"
        "[https://watch.amazon.co.jp/detail?gti=amzn1.dv.gti.b2acd844-523a-5e5d-e9ff-578863f17b19:embed]"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['genre'] == "映像"
    assert results[0]['tags'] == []
    assert results[0]['subtitle'] == "第1話\n第2話"


def test_tv_anime_content_rule_line_with_url_extracts_subtitle():
    content = (
        "*** 今日見たもの\n"
        "- TVアニメ『[https://yurucamp.jp/third/:title=ゆるキャン△ SEASON3]』"
        "第3話「出発! 吊り橋の国」[https://yurucamp.jp/third/:embed]"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['title'] == "ゆるキャン△ SEASON3"
    assert results[0]['genre'] == "映像"
    assert results[0]['tags'] == ["TVアニメ"]
    assert results[0]['subtitle'] == "第3話「出発! 吊り橋の国」"


def test_tv_anime_domain_bare_title_marker_with_parenthesized_episodes():
    content = (
        "*** 今日見たもの\n"
        "- [https://animestore.docomo.ne.jp/animestore/ci_pc?workId=25330:title] "
        "(第3話・第4話・第5話)"
        "[https://animestore.docomo.ne.jp/animestore/ci_pc?workId=25330:embed]"
    )
    results = parse_html_content(content, "2026-01-05")

    assert len(results) == 1
    assert results[0]['title'] is None
    assert results[0]['genre'] == "映像"
    assert results[0]['tags'] == ["TVアニメ"]
    assert results[0]['subtitle'] == "第3話\n第4話\n第5話"


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
