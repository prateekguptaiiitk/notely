import hashlib

from django.core.cache import cache

FAILURE_LIMIT = 5
WINDOW_SECONDS = 15 * 60


def cache_key(ip_address, username):
    digest = hashlib.sha256(
        f"{ip_address}|{username.casefold()}".encode("utf-8")
    ).hexdigest()
    return f"notely:login:{digest}"


def is_blocked(ip_address, username):
    return int(cache.get(cache_key(ip_address, username), 0)) >= FAILURE_LIMIT


def record_failure(ip_address, username):
    key = cache_key(ip_address, username)
    if cache.add(key, 1, timeout=WINDOW_SECONDS):
        return
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=WINDOW_SECONDS)


def clear_failures(ip_address, username):
    cache.delete(cache_key(ip_address, username))
