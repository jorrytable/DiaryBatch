from urllib.parse import urlparse


def hostname(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith('www.'):
        host = host[len('www.'):]
    return host
