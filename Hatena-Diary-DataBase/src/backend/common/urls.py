from urllib.parse import urlparse


def hostname(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith('www.'):
        host = host[len('www.'):]
    return host


def match_domain(rules: dict, host: str):
    """rulesを完全一致で調べ、無ければ`.`+ドメインでの接尾辞一致（サブドメイン許容）で調べる。
    一致すればその値を、無ければNoneを返す。"""
    if host in rules:
        return rules[host]
    for domain, value in rules.items():
        if host.endswith('.' + domain):
            return value
    return None
