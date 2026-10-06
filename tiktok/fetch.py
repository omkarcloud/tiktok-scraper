"""TikTok transport: plain curl_cffi with browser-impersonated TLS through
sticky residential exits. No browser, no login.

Validated 2026-10-05 through US / GB / DE residential exits. TikTok is not
reachable from direct Indian egress at all (TCP timeout), and the pod's own
US datacenter egress is untested — config.TIKTOK_USE_PROXY keeps everything
on residential exits.

Upstream surfaces:

  * WEB API   GET https://www.tiktok.com/api/<group>/<action>/
    The web app's own JSON. Every call carries the app's fixed query params
    (aid=1988, app_name=tiktok_web, device_id, region ...). Most endpoints
    are SIGNED: the page's webmssdk appends X-Dynosaur, msToken, X-Bogus=1
    and X-Gnarly, reproduced in pure python by signer.py. An unsigned (or
    badly signed) call to a signed endpoint is NOT an error: HTTP 200, a
    0-byte body and the header `tt_orcas_res: 1`. The same silent empty body
    is how TikTok refuses anything else it dislikes, so it is the one block
    signal here (TikTokBlocked):
      - the FIRST signed call of a session is often empty and the retry on
        the same session answers -> a fresh session gets one free retry;
      - endpoints differ by exit REGION: /api/user/detail and
        /api/search/user answer on EU exits and are always empty on US ones;
        /api/search/item is the reverse. Callers pass `countries`, the exit
        order to try;
      - /api/post/item_list goes empty after ~17-27 calls per exit IP (a
        new ttwid on the same IP does not help, a new exit works at once)
        -> `budget=` retires a session for that endpoint after
        config.TIKTOK_POSTS_CALLS_PER_EXIT calls.
    A few endpoints need no signature (creator/item_list, repost/item_list,
    user/list, user/playlist, mix/item_list, explore/item_list,
    search/general/preview) and are sent bare.
    Search answers `status_code 2483 "Please login"` to a session with no
    cookies: `boot=True` first loads one profile page, which sets ttwid /
    tt_csrf_token / tt_chain_token and yields the page's own device id.
    msToken is taken from the session's cookie jar when TikTok has issued
    one and sent empty otherwise — a made-up token is refused.

  * PAGES     GET https://www.tiktok.com/@<user>
    Server-rendered rehydration JSON (`__UNIVERSAL_DATA_FOR_REHYDRATION__`),
    used to boot a session and as the profile fallback.

  * WEBCAST   GET https://webcast.tiktok.com/webcast/room/info/ — live rooms,
    unsigned.

  * ADS LIBRARY  https://library.tiktok.com/api/v1/* — no cookies, but a
    per-exit handshake: GET /location, then GET /support-regions whose
    `config_str` rides every later call as the X-CCL-STR header. Skip either
    step and the answer is HTTP 421 with the plain text "system busy".

  * CREATIVE CENTER  https://ads.tiktok.com/creative_radar_api/v1/top_ads/*
    — headers anonymous-user-id (any uuid) + timestamp + user-sign (an md5
    fold, creative_center()). The other creative_radar lists answer
    "deprecated" since 2026 and are not used.

FALLBACK if the signer stops working (every signed call empty on every
exit): the patchright pattern — warm a headed Chrome on www.tiktok.com and
run these same GETs through the page's own fetch, which webmssdk signs.
Not built: dead code while the port works.

Failure taxonomy (scraper_errors, mapped to HTTP by route_glue):
  TikTokUpstreamError  transport failure / 5xx / unexpected status code — retryable
  TikTokBlocked        silent empty body, 403 / 429, login wall          — retryable on a new exit
  TikTokBadRequest     upstream rejected the params                       — never retried
  TikTokNotFound       unknown user / video / hashtag / sound ...         — never retried
"""
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError

from . import signer

WWW = "https://www.tiktok.com"
WEBCAST = "https://webcast.tiktok.com"
ADS_LIBRARY = "https://library.tiktok.com"
CREATIVE_CENTER = "https://ads.tiktok.com"
IMPERSONATE = "chrome"

# The signer seals the User-Agent into X-Gnarly, so the header, the
# browser_version param and the signer input must be this same string.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

API_TIMEOUT = 30
PAGE_TIMEOUT = 45
FANOUT_WORKERS = 4
SESSIONS_PER_COUNTRY = 2       # fresh exits tried per country before moving on
BOOT_PATH = "/@tiktok"         # any profile page sets the session cookies

LOGIN_WALL_STATUS = 2483       # "Please login your account first" (search without cookies)

PAGE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "upgrade-insecure-requests": "1",
}

_UNIVERSAL_RE = re.compile(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', re.S)


class TikTokUpstreamError(UpstreamError):
    """Transport failure, 5xx or an unexpected upstream status — retryable."""


class TikTokBlocked(TikTokUpstreamError, Blocked):
    """Silent empty body, 403 / 429 or a login wall — retryable on a new exit."""


class TikTokBadRequest(BadRequest):
    """Upstream rejected the params — never retried."""


class TikTokNotFound(NotFound):
    """The user / video / hashtag / sound ... does not exist — never retried."""


def default_country():
    return config.TIKTOK_DEFAULT_COUNTRY


def eu_country():
    return config.TIKTOK_EU_COUNTRY


def country_order(country, *fallbacks):
    """`country` (or the default) first, then the fallbacks, de-duplicated."""
    order = []
    for code in (country or default_country(),) + fallbacks:
        code = (code or "").lower()
        if code and code not in order:
            order.append(code)
    return tuple(order)


# ---- sessions --------------------------------------------------------------------
# A client = one curl session on one sticky exit, with its own device id and
# cookie jar. Clients are pooled per exit country and checked out by one
# request thread at a time (a curl handle must not be shared across threads).

class _Client:
    __slots__ = ("session", "country", "device_id", "born", "booted", "answered", "spent", "ccl")

    def __init__(self, country):
        from curl_cffi import requests as curl_requests
        self.session = curl_requests.Session(impersonate=IMPERSONATE)
        proxy = config.tiktok_proxy(country)
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
        self.session.headers.update({"user-agent": USER_AGENT, "accept-language": "en-US,en;q=0.9"})
        self.country = country
        self.device_id = str(random.randint(7250000000000000000, 7351147085025500000))
        self.born = time.time()
        self.booted = False
        self.answered = False      # has a signed call ever answered on this session
        self.spent = {}            # budget key -> calls served
        self.ccl = None            # ads library (config_str, regions, expires)

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass


_pool_lock = threading.Lock()
_idle = {}                         # country -> [clients], most recently used last


def _acquire(country, budget=None):
    """An idle client for `country` that still has `budget` left, else a new
    one on a fresh exit."""
    now = time.time()
    with _pool_lock:
        clients = _idle.setdefault(country, [])
        for i in range(len(clients) - 1, -1, -1):
            client = clients[i]
            if now - client.born > config.TIKTOK_SESSION_MAX_AGE:
                clients.pop(i)
                client.close()
                continue
            if budget and client.spent.get(budget[0], 0) >= budget[1]:
                continue
            return clients.pop(i)
    return _Client(country)


def _release(client):
    """Return a client to its country's idle pool, most recently used last.
    A full pool evicts its least recently used client, so sessions that have
    spent their budget for an endpoint drift out instead of pinning the pool
    and forcing every later call of that endpoint onto a fresh exit."""
    evicted = None
    with _pool_lock:
        clients = _idle.setdefault(client.country, [])
        if len(clients) >= config.TIKTOK_IDLE_SESSIONS_PER_COUNTRY:
            evicted = clients.pop(0)
        clients.append(client)
    if evicted is not None:
        evicted.close()


def dump_debug(name, text):
    """Write a raw response to $TIKTOK_DEBUG_DIR/<name>.txt."""
    dbg = os.environ.get("TIKTOK_DEBUG_DIR", "")
    if dbg and text:
        try:
            os.makedirs(dbg, exist_ok=True)
            with open(os.path.join(dbg, name + ".txt"), "w") as f:
                f.write(text)
        except OSError:
            pass


def universal_data(html):
    """The page's `__DEFAULT_SCOPE__` rehydration dict, or None."""
    match = _UNIVERSAL_RE.search(html or "")
    if not match:
        return None
    try:
        scope = json.loads(match.group(1)).get("__DEFAULT_SCOPE__")
    except (ValueError, AttributeError):
        return None
    return scope if isinstance(scope, dict) else None


def _load_page(client, path):
    """GET one www page on `client` -> its rehydration scope. Also adopts
    the page's own device id, so a page load doubles as the session boot."""
    try:
        resp = client.session.get(WWW + path, headers=PAGE_HEADERS, timeout=PAGE_TIMEOUT, allow_redirects=True)
    except Exception as e:
        raise TikTokUpstreamError(f"request failed: {type(e).__name__}: {e}")
    status = resp.status_code
    if status in (401, 403, 429):
        raise TikTokBlocked(f"HTTP {status} on {path}")
    if status != 200:
        raise TikTokUpstreamError(f"HTTP {status} on {path}")
    scope = universal_data(resp.text)
    if scope is None:
        # ~1 page in 25 arrives without its rehydration script; a new exit fixes it
        dump_debug("page_no_data", resp.text)
        raise TikTokBlocked(f"{path} came back without page data")
    wid = (scope.get("webapp.app-context") or {}).get("wid")
    if wid:
        client.device_id = str(wid)
    client.booted = True
    return scope


def _base_params(client, region):
    """The web app's fixed query params, in the app's own order."""
    return {
        "WebIdLastTime": str(int(client.born)),
        "aid": "1988",
        "app_language": "en",
        "app_name": "tiktok_web",
        "browser_language": "en-US",
        "browser_name": "Mozilla",
        "browser_online": "true",
        "browser_platform": "MacIntel",
        "browser_version": USER_AGENT[8:],
        "channel": "tiktok_web",
        "cookie_enabled": "true",
        "data_collection_enabled": "false",
        "device_id": client.device_id,
        "device_platform": "web_pc",
        "focus_state": "true",
        "from_page": "user",
        "history_len": "3",
        "is_fullscreen": "false",
        "is_page_visible": "true",
        "language": "en",
        "os": "mac",
        "priority_region": "",
        "referer": "",
        "region": region,
        "screen_height": "1080",
        "screen_width": "1920",
        "tz_name": "America/New_York",
        "user_is_login": "false",
        "webcast_language": "en",
    }


def status_of(payload):
    """The upstream status code of a JSON answer (0 = ok). The web API
    spells it statusCode, status_code or code depending on the service."""
    for key in ("statusCode", "status_code", "code"):
        value = payload.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return 0


def _status_message(payload):
    return payload.get("statusMsg") or payload.get("status_msg") or payload.get("msg") or ""


def _api_once(client, path, params, *, signed, base, host, referer):
    query = _base_params(client, client.country.upper()) if base else {}
    query.update({key: str(value) for key, value in params.items() if value is not None})
    ms_token = client.session.cookies.get("msToken") or ""
    if signed:
        query_string, _ = signer.sign(list(query.items()), USER_AGENT, ms_token=ms_token)
    else:
        if ms_token and base:
            query["msToken"] = ms_token
        query_string = urlencode(query)
    try:
        resp = client.session.get(f"{host}{path}?{query_string}",
                                  headers={"accept": "*/*", "referer": referer or WWW + "/"}, timeout=API_TIMEOUT)
    except Exception as e:
        raise TikTokUpstreamError(f"request failed: {type(e).__name__}: {e}")
    status = resp.status_code
    text = resp.text or ""
    if status in (401, 403, 429):
        raise TikTokBlocked(f"HTTP {status} on {path}")
    if status >= 500:
        raise TikTokUpstreamError(f"HTTP {status} on {path}")
    if status == 400:
        raise TikTokBadRequest(f"tiktok rejected {path}")
    if not text.strip():
        raise TikTokBlocked(f"{path} answered with an empty body")
    try:
        payload = json.loads(text)
    except ValueError:
        dump_debug("nonjson" + path.replace("/", "_"), text)
        raise TikTokBlocked(f"{path} returned a non-JSON body")
    if not isinstance(payload, dict):
        raise TikTokUpstreamError(f"{path} returned unexpected JSON")
    if status_of(payload) == LOGIN_WALL_STATUS:
        raise TikTokBlocked(f"{path} asked for a login")
    return payload


def api(path, params, *, country=None, countries=None, signed=True, boot=False, base=True, host=WWW,
        budget=None, referer=None, not_found=(), bad_request=(), ok=(0,), label=None):
    """One web API call -> the parsed JSON dict.

    countries    exit countries to try in order (default: `country` or the
                 configured default). Each gets SESSIONS_PER_COUNTRY exits.
    signed       seal the query with signer.py (False for the bare endpoints)
    boot         load one page on the session first (search needs cookies)
    base         send the web app's fixed params (False for other services)
    budget       (key, max calls) — a session serves at most that many calls
                 under `key`, then a fresh exit is used
    not_found    upstream status codes that mean the entity does not exist
    bad_request  upstream status codes that mean the params were refused
    ok           status codes returned to the caller as-is; any other code is
                 an upstream error naming the code
    """
    order = countries or country_order(country)
    what = label or path
    last = None
    for code in order:
        for _ in range(SESSIONS_PER_COUNTRY):
            client = _acquire(code, budget)
            # a session often drops its FIRST signed call; unsigned calls never need the retry
            tries = 2 if signed and not client.answered else 1
            payload = None
            try:
                if boot and not client.booted:
                    _load_page(client, BOOT_PATH)
                for attempt in range(tries):
                    try:
                        payload = _api_once(client, path, params, signed=signed, base=base, host=host, referer=referer)
                        break
                    except TikTokBlocked as e:
                        last = e
                        if attempt + 1 == tries:
                            raise
            except TikTokBadRequest:
                _release(client)
                raise
            except TikTokUpstreamError as e:
                last = e
                client.close()
                continue
            if signed:
                client.answered = True
            if budget:
                client.spent[budget[0]] = client.spent.get(budget[0], 0) + 1
            _release(client)
            status = status_of(payload)
            if status in not_found:
                raise TikTokNotFound(f"{what} not found")
            if status in bad_request:
                raise TikTokBadRequest(_status_message(payload) or f"status {status}")
            if status not in ok:
                raise TikTokUpstreamError(f"{what}: upstream status {status} {_status_message(payload)}".strip())
            return payload
    raise last or TikTokUpstreamError(f"{what} failed")


def get_page(path, *, country=None, countries=None):
    """GET one www.tiktok.com page -> its rehydration scope dict."""
    last = None
    for code in countries or country_order(country):
        for _ in range(SESSIONS_PER_COUNTRY):
            client = _acquire(code)
            try:
                scope = _load_page(client, path)
            except TikTokUpstreamError as e:
                last = e
                client.close()
                continue
            _release(client)
            return scope
    raise last or TikTokUpstreamError(f"{path} failed")


def resolve_redirect(url, *, country=None):
    """Where a short link (vm.tiktok.com/…, tiktok.com/t/…) points — the
    final URL after redirects. TikTokNotFound when it leads nowhere."""
    last = None
    for _ in range(SESSIONS_PER_COUNTRY + 1):
        client = _acquire((country or default_country()).lower())
        try:
            resp = client.session.get(url, headers=PAGE_HEADERS, timeout=PAGE_TIMEOUT, allow_redirects=True)
        except Exception as e:
            last = TikTokUpstreamError(f"request failed: {type(e).__name__}: {e}")
            client.close()
            continue
        _release(client)
        if resp.status_code == 404:
            raise TikTokNotFound("link not found")
        return str(resp.url or url)
    raise last


def get_text(url, *, country=None):
    """GET a signed CDN file (a WebVTT subtitle) -> its text."""
    last = None
    for _ in range(SESSIONS_PER_COUNTRY + 1):
        client = _acquire((country or default_country()).lower())
        try:
            resp = client.session.get(url, headers={"accept": "*/*", "referer": WWW + "/"}, timeout=API_TIMEOUT)
        except Exception as e:
            last = TikTokUpstreamError(f"request failed: {type(e).__name__}: {e}")
            client.close()
            continue
        _release(client)
        if resp.status_code == 200 and resp.text:
            return resp.text
        last = TikTokUpstreamError(f"HTTP {resp.status_code} on a media file")
    raise last


# ---- ads library ---------------------------------------------------------------------

CCL_TTL = 1800


def _ads_library_once(client, method, path, *, params=None, body=None, config_str=None):
    headers = {"accept": "application/json, text/plain, */*", "origin": ADS_LIBRARY, "referer": ADS_LIBRARY + "/ads"}
    if config_str:
        headers["X-CCL-STR"] = config_str
    try:
        if method == "GET":
            resp = client.session.get(ADS_LIBRARY + path, params=params, headers=headers, timeout=API_TIMEOUT)
        else:
            resp = client.session.post(ADS_LIBRARY + path, params=params, json=body, headers=headers, timeout=API_TIMEOUT)
    except Exception as e:
        raise TikTokUpstreamError(f"request failed: {type(e).__name__}: {e}")
    status = resp.status_code
    if status in (401, 403, 429):
        raise TikTokBlocked(f"HTTP {status} on {path}")
    if status >= 500:
        raise TikTokUpstreamError(f"HTTP {status} on {path}")
    try:
        payload = resp.json()
    except Exception:
        text = (resp.text or "").strip()
        if status in (421, 425) and len(text) < 200:
            return status, {"err_msg": text}       # "system busy" / "params error" arrive as plain text
        dump_debug("ads_library_nonjson", text)
        raise TikTokBlocked(f"{path} returned a non-JSON body (HTTP {status})")
    if not isinstance(payload, dict):
        raise TikTokUpstreamError(f"{path} returned unexpected JSON")
    return status, payload


def _ads_library_regions(client):
    """(config_str, regions) from /support-regions. The handshake is bound
    to the exit that made it, so it lives on the client."""
    cached = client.ccl
    if cached and cached[2] > time.time():
        return cached[0], cached[1]
    # /location first: without it every later call from this exit is answered
    # 421 "system busy", config string or not (the service keys on the IP)
    _ads_library_once(client, "GET", "/api/v1/location")
    _, payload = _ads_library_once(client, "GET", "/api/v1/support-regions", params={"lang": "en"})
    value = payload.get("config_str")
    if not value:
        raise TikTokUpstreamError("ads library gave no config string")
    client.ccl = (value, payload.get("regions") or [], time.time() + CCL_TTL)
    return value, client.ccl[1]


def ads_library(method, path, *, params=None, body=None, not_found=None):
    """One Commercial Content Library call -> JSON dict. HTTP 421 is the
    service's catch-all refusal: "system busy" for a stale / foreign
    X-CCL-STR (retried on a fresh session) and "params error" for a
    rejected body; HTTP 425 is its answer to params it cannot serve
    (`not_found` names the entity when that means a missing ad)."""
    last = None
    for _ in range(config.MAX_RETRIES):
        client = _acquire(default_country())
        try:
            config_str, _ = _ads_library_regions(client)
            status, payload = _ads_library_once(client, method, path, params=params, body=body, config_str=config_str)
        except TikTokUpstreamError as e:
            last = e
            client.close()
            continue
        if status == 425:
            # the service's answer to params it cannot serve: an unknown ad
            # id, a region it does not cover, a page without its search id
            _release(client)
            if not_found:
                raise TikTokNotFound(f"{not_found} not found")
            raise TikTokBadRequest("the ads library refused these parameters")
        if status == 421 or payload.get("code") not in (0, None):
            message = str(payload.get("err_msg") or payload.get("msg") or payload.get("message") or "")
            if "param" in message.lower():
                _release(client)
                raise TikTokBadRequest(message)
            last = TikTokUpstreamError(f"ads library: {message or payload.get('code') or status}")
            client.close()
            continue
        _release(client)
        return payload
    raise last


def ads_library_regions():
    """The countries the Commercial Content Library covers: [{code, name}]."""
    last = None
    for _ in range(config.MAX_RETRIES):
        client = _acquire(default_country())
        try:
            _, regions = _ads_library_regions(client)
        except TikTokUpstreamError as e:
            last = e
            client.close()
            continue
        _release(client)
        return regions
    raise last


# ---- creative center ----------------------------------------------------------------

_CC_SALT = "A7B&9z#1G6$2K@8M!3"


def _creative_center_sign(user_id, timestamp):
    digest = hashlib.md5(f"{_CC_SALT}-{user_id}-{timestamp}".encode()).hexdigest()
    return "".join(format(int(a, 16) ^ int(b, 16), "x") for a, b in zip(digest[:16], digest[16:]))


def creative_center(path, params, *, not_found=()):
    """One Creative Center radar call -> its `data` object."""
    last = None
    for _ in range(config.MAX_RETRIES):
        client = _acquire(default_country())
        user_id = str(uuid.uuid4())
        timestamp = int(time.time())
        headers = {
            "accept": "application/json, text/plain, */*",
            "lang": "en",
            "referer": CREATIVE_CENTER + "/business/creativecenter/inspiration/topads/pc/en",
            "anonymous-user-id": user_id,
            "timestamp": str(timestamp),
            "user-sign": _creative_center_sign(user_id, timestamp),
        }
        try:
            resp = client.session.get(CREATIVE_CENTER + path, params=params, headers=headers, timeout=API_TIMEOUT)
            payload = resp.json()
        except Exception as e:
            last = TikTokUpstreamError(f"request failed: {type(e).__name__}: {e}")
            client.close()
            continue
        _release(client)
        if not isinstance(payload, dict):
            last = TikTokUpstreamError(f"{path} returned unexpected JSON")
            continue
        code = payload.get("code")
        if code in not_found:
            raise TikTokNotFound("ad not found")
        if code != 0:
            last = TikTokUpstreamError(f"creative center: {code} {payload.get('msg')}")
            continue
        data = payload.get("data")
        return data if isinstance(data, dict) else {}
    raise last


# ---- fan-out -------------------------------------------------------------------------

def run_parallel(fns):
    """Run zero-arg callables in parallel; results align with `fns`.
    Exceptions propagate from the first failing call."""
    if not fns:
        return []
    if len(fns) == 1:
        return [fns[0]()]
    with ThreadPoolExecutor(max_workers=min(FANOUT_WORKERS, len(fns))) as ex:
        futures = [ex.submit(fn) for fn in fns]
        return [f.result() for f in futures]


if __name__ == "__main__":
    # Smoke test: python -m tiktok.fetch [username]
    who = sys.argv[1] if len(sys.argv) > 1 else "nasa"
    data = api("/api/user/detail/", {"uniqueId": who, "secUid": ""}, countries=(eu_country(),))
    info = data.get("userInfo") or {}
    print("user:", (info.get("user") or {}).get("uniqueId"), (info.get("statsV2") or {}).get("followerCount"))
