"""Configuration for the TikTok Scraper. Everything can be set with an
environment variable; the defaults work out of the box.

    PORT          port the API listens on (default 8000)
    TIKTOK_PROXY  proxy URL for every request, e.g. http://user:pass@host:port
                  (default: none — direct). TikTok answers plain requests from
                  an ordinary residential IP in a country where TikTok is
                  available, so you very likely don't need this. Set it if
                  TikTok is blocked where you run (India, for example), or if
                  a user's videos start coming back empty at high volume —
                  TikTok retires an IP for that endpoint after ~20 calls.
                  If your proxy provider targets countries through the URL,
                  put `{country}` where the 2-letter code goes, e.g.
                  http://user-cr.{country}:pass@host:port — the scraper then
                  asks each request from the country it needs (TikTok answers
                  user search only from Europe and video search only from
                  the US).

Everything else below is a plain constant with a working default — edit it
here if you need to.
"""
import os

PORT = int(os.environ.get("PORT", "8000"))

# Retry policy for transport errors and blocks (every request).
MAX_RETRIES = 3
RETRY_BACKOFF = 2          # seconds, multiplied by the attempt number

TIKTOK_PROXY = os.environ.get("TIKTOK_PROXY") or None
TIKTOK_USE_PROXY = TIKTOK_PROXY is not None

# `country` on a request is the TikTok edition asked for (the `region`
# param). With TIKTOK_PROXY set, every request goes through that one proxy
# whatever the country — these only name the defaults.
TIKTOK_DEFAULT_COUNTRY = "us"              # edition for calls that take no `country`
TIKTOK_EU_COUNTRY = "de"                   # edition tried for the endpoints TikTok only answers from Europe

TIKTOK_POSTS_CALLS_PER_EXIT = 12           # user-video calls one session serves before a fresh one is used
TIKTOK_SESSION_MAX_AGE = 1800              # seconds a pooled session is reused
TIKTOK_IDLE_SESSIONS_PER_COUNTRY = 6       # pooled sessions kept per country


def tiktok_proxy(country):
    """The proxy for one session in `country` (None = direct)."""
    if not TIKTOK_PROXY:
        return None
    return TIKTOK_PROXY.replace("{country}", (country or TIKTOK_DEFAULT_COUNTRY).lower())
