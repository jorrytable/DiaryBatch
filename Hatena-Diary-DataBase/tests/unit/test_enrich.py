from src.backend.batch.enrich import _find_oembed_endpoint, OEMBED_ENDPOINTS


def test_find_oembed_endpoint_youtube():
    assert _find_oembed_endpoint("https://www.youtube.com/watch?v=x") == OEMBED_ENDPOINTS['youtube.com']


def test_find_oembed_endpoint_youtube_short_url():
    assert _find_oembed_endpoint("https://youtu.be/x") == OEMBED_ENDPOINTS['youtu.be']


def test_find_oembed_endpoint_unknown_domain():
    assert _find_oembed_endpoint("https://example.com/page") is None
