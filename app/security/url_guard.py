from ipaddress import ip_address
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    pass


def validate_url(url: str, allowed_hosts: set[str]) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("only http/https URLs are allowed")
    host = (parsed.hostname or "").lower()
    if not host or host not in {h.lower() for h in allowed_hosts}:
        raise UnsafeUrlError(f"host is not allowlisted: {host or '<empty>'}")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("credentials in URLs are forbidden")
    if host not in {"localhost"}:
        try:
            if not ip_address(host).is_loopback:
                raise UnsafeUrlError("only loopback addresses are enabled by default")
        except ValueError:
            pass
    return url

