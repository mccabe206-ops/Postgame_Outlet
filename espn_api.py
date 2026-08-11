"""Robust ESPN JSON fetch.

ESPN's unofficial site API is free and needs no key, but which User-Agent it
accepts depends on the network in front of it:

- On some corporate/proxied networks, a browser-style UA ("Mozilla/5.0") is
  BLOCKED (403) while urllib's default UA ("Python-urllib/x.y") is allowed.
- On other networks / CI runners the reverse can be true.

So we try a sequence of request strategies and return the first that succeeds,
rather than hard-coding one UA. Stdlib only (urllib) — no external deps.
"""

import json
import urllib.error
import urllib.request

# Ordered strategies. Each is a dict of extra headers to send (empty = urllib
# default UA). We try them in order and keep the first that returns 200.
_STRATEGIES = (
    {},                                   # urllib default UA (works behind the proxy here)
    {"User-Agent": "Mozilla/5.0"},        # browser UA (works on unproxied networks / CI)
    {"User-Agent": "curl/8.0"},           # last-ditch alternative UA
)


def fetch_json(url, timeout=20):
    """GET `url` and parse JSON, trying multiple UA strategies.

    Returns the decoded object. Raises the last error if every strategy fails.
    """
    last_err = None
    for headers in _STRATEGIES:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            continue
    raise last_err if last_err else RuntimeError(f"Failed to fetch {url}")
