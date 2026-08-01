from src.backend.batch.classify import classify_genre_and_tags, classify_from_content


def test_classify_genre_known_domain():
    assert classify_genre_and_tags("https://www.youtube.com/watch?v=x") == ("映像", [])


def test_classify_genre_subdomain():
    assert classify_genre_and_tags("https://m.youtube.com/watch?v=x") == ("映像", [])


def test_classify_genre_amazon_prime_video():
    assert classify_genre_and_tags("https://watch.amazon.co.jp/detail?gti=abc") == ("映像", [])


def test_classify_genre_unknown_domain():
    assert classify_genre_and_tags("https://example.com/page") == ("その他", [])


def test_classify_genre_radiko():
    assert classify_genre_and_tags("https://radiko.jp/#!/live/TBS") == ("ラジオ", [])


def test_classify_genre_spotify_episode_is_radio():
    assert classify_genre_and_tags("https://open.spotify.com/episode/abc123") == ("ラジオ", [])


def test_classify_genre_spotify_show_is_radio():
    assert classify_genre_and_tags("https://open.spotify.com/show/abc123") == ("ラジオ", [])


def test_classify_genre_spotify_track_is_music():
    assert classify_genre_and_tags("https://open.spotify.com/track/abc123") == ("音楽", [])


def test_classify_new_text_domain():
    assert classify_genre_and_tags("https://www.asahi.com/articles/xxx.html") == ("テキスト", [])


def test_classify_tv_domain_has_tv_tag():
    assert classify_genre_and_tags("https://www.nhk.or.jp/some/page") == ("映像", ["テレビ"])


def test_classify_anime_store_domain_has_tv_anime_tag():
    assert classify_genre_and_tags("https://animestore.docomo.ne.jp/some/page") == ("映像", ["TVアニメ"])


def test_classify_from_content_movie():
    assert classify_from_content("- 映画『花のあすか組』") == ("映像", "映画")


def test_classify_from_content_tv_anime():
    assert classify_from_content("- TVアニメ『葬送のフリーレン』") == ("映像", "TVアニメ")


def test_classify_from_content_no_match():
    assert classify_from_content("- 何か普通の作品名") is None
