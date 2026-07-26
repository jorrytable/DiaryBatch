import datetime
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from boto3.dynamodb.types import TypeDeserializer

from common.urls import hostname as _hostname

# oEmbed対応ドメイン→エンドポイントURL。網羅的ではなく、確認済みのものから随時追記していく前提の初期値
OEMBED_ENDPOINTS = {
    'youtube.com': 'https://www.youtube.com/oembed',
    'youtu.be': 'https://www.youtube.com/oembed',
    'open.spotify.com': 'https://open.spotify.com/oembed',
    'soundcloud.com': 'https://soundcloud.com/oembed',
}

YOUTUBE_HOSTS = {'youtube.com', 'youtu.be'}

REQUEST_TIMEOUT = 3

_deserializer = TypeDeserializer()


def _find_oembed_endpoint(url: str) -> str | None:
    hostname = _hostname(url)
    if hostname in OEMBED_ENDPOINTS:
        return OEMBED_ENDPOINTS[hostname]
    for domain, endpoint in OEMBED_ENDPOINTS.items():
        if hostname.endswith('.' + domain):
            return endpoint
    return None


def _extract_youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    hostname = parsed.netloc.lower()
    if 'youtu.be' in hostname:
        return parsed.path.lstrip('/') or None
    query = parse_qs(parsed.query)
    if 'v' in query:
        return query['v'][0]
    return None


YOUTUBE_MUSIC_CATEGORY_ID = '10'


def _is_music_category(video_id: str, youtube_api_key: str) -> bool:
    """YouTube Data API v3のcategoryId（音楽=10）で公式に音楽判定する。"""
    try:
        resp = requests.get(
            'https://www.googleapis.com/youtube/v3/videos',
            params={'part': 'snippet', 'id': video_id, 'key': youtube_api_key},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        items = resp.json().get('items', [])
        if not items:
            return False
        return items[0]['snippet'].get('categoryId') == YOUTUBE_MUSIC_CATEGORY_ID
    except Exception:
        return False


def _fetch_oembed(url: str, endpoint: str, hostname: str, youtube_api_key: str | None) -> dict:
    resp = requests.get(endpoint, params={'url': url, 'format': 'json'}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    result = {}
    if data.get('title'):
        result['title'] = data['title']
    if data.get('html'):
        result['embed_html'] = data['html']

    if hostname in YOUTUBE_HOSTS and data.get('author_name'):
        result['tags'] = [data['author_name']]
        video_id = _extract_youtube_video_id(url)
        if video_id and youtube_api_key and _is_music_category(video_id, youtube_api_key):
            # 音楽カテゴリの動画は、tagsではなくgenre自体を「映像」から「音楽」に上書きする
            result['is_music'] = True

    return result


def _fetch_page_metadata(url: str) -> dict:
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'lxml')

    result = {}
    if soup.title and soup.title.string:
        result['title'] = soup.title.string.strip()

    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        result['og_title'] = og_title['content']

    og_description = soup.find('meta', property='og:description')
    if og_description and og_description.get('content'):
        result['og_description'] = og_description['content']

    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        result['og_image'] = og_image['content']

    return result


def fetch_metadata(url: str, youtube_api_key: str | None = None) -> dict:
    """URL1件分のtitle/embed情報を外部サイトから取得する。失敗しても例外は投げない。"""
    try:
        endpoint = _find_oembed_endpoint(url)
        if endpoint:
            return _fetch_oembed(url, endpoint, _hostname(url), youtube_api_key)
        return _fetch_page_metadata(url)
    except Exception as e:
        print(f"メタデータ取得失敗: {url} ({e})")
        return {}


def batch_get_cached(dynamodb_client, table_name: str, urls: list) -> dict:
    """複数URL分のキャッシュ済みメタデータを一括取得する（GetItemを1件ずつ呼ぶより高速）。"""
    unique_urls = list(dict.fromkeys(urls))
    cached = {}

    for i in range(0, len(unique_urls), 100):
        chunk = unique_urls[i:i + 100]
        keys = [{'url': {'S': u}} for u in chunk]
        request_items = {table_name: {'Keys': keys}}

        while request_items:
            resp = dynamodb_client.batch_get_item(RequestItems=request_items)
            for raw_item in resp['Responses'].get(table_name, []):
                item = {k: _deserializer.deserialize(v) for k, v in raw_item.items()}
                cached[item['url']] = item
            request_items = resp.get('UnprocessedKeys') or {}

    return cached


def get_or_fetch(table, url: str, cached: dict, budget: dict, youtube_api_key: str | None = None) -> dict:
    """事前取得済みキャッシュ(cached)にあればそれを使い、無ければ予算が残っていれば取得してキャッシュする。"""
    if url in cached:
        return cached[url]

    if budget['remaining'] <= 0:
        return {}

    metadata = fetch_metadata(url, youtube_api_key)
    budget['remaining'] -= 1

    item = {'url': url, 'fetched_at': datetime.datetime.utcnow().isoformat(), **metadata}
    table.put_item(Item=item)
    cached[url] = item
    return item
