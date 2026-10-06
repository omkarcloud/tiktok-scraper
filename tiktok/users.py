"""User endpoints: profile, resolve, videos, reposts, followers / following,
playlists and collections.

`user` is {"username": ..., "sec_uid": ...} from refs.resolve_user. Every
list endpoint needs the account's secUid, so a username is first looked up
(the profile call, memoised in-process for LOOKUP_TTL so a paging client
pays for it once).

Where each call is served (probed 2026-10-05, see fetch.py):
  * /api/user/detail  answers on EU exits only -> looked up there, with the
    profile PAGE on the default exit as the fallback (username refs only;
    the page cannot be addressed by secUid).
  * /api/post/item_list (signed, 35 a page, latest / popular / oldest) is
    throttled per exit IP, so each session serves a small budget of calls.
    When it still comes back empty, `latest` falls back to the unsigned
    /api/creator/item_list (15 a page, same cursor scale: createTime in ms).
  * reposts 30 a page (offset cursor), followers / following 30 a page
    (cursor = the upstream minCursor), playlists and collections 20 a page.

A private account answers its lists with no rows; the profile says
`is_private`.
"""
import threading
import time

import config

from . import parsers as P
from . import shared
from .fetch import TikTokBlocked, TikTokNotFound, TikTokUpstreamError, api, country_order, eu_country, get_page

LOOKUP_TTL = 600
_lookup_lock = threading.Lock()
_lookups = {}           # ("username"|"sec_uid", value) -> (expires, userInfo)

POSTS_PAGE = 35
CREATOR_PAGE = 15
LIST_PAGE = 30
SORTS = {"latest": 0, "popular": 1, "oldest": 2}
FOLLOW_SCENES = {"followers": 67, "following": 21}
LIST_HIDDEN = 10222      # the account hides this list (profile setting)


def _describe(user):
    return f"@{user['username']}" if user.get("username") else "that secUid"


def _remember(info):
    raw = info.get("user") or {}
    expires = time.time() + LOOKUP_TTL
    with _lookup_lock:
        if len(_lookups) > 5000:
            _lookups.clear()
        if raw.get("uniqueId"):
            _lookups[("username", str(raw["uniqueId"]).lower())] = (expires, info)
        if raw.get("secUid"):
            _lookups[("sec_uid", raw["secUid"])] = (expires, info)


def lookup(user):
    """The raw webapp userInfo ({user, stats, statsV2}) for a resolved ref;
    TikTokNotFound if the account does not exist."""
    key = ("username", user["username"]) if user.get("username") else ("sec_uid", user["sec_uid"])
    with _lookup_lock:
        hit = _lookups.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
    params = {"uniqueId": user.get("username") or "", "secUid": user.get("sec_uid") or ""}
    label = f"user {_describe(user)}"
    try:
        payload = api("/api/user/detail/", params, countries=(eu_country(),),
                      not_found=shared.USER_NOT_FOUND, label=label)
        info = payload.get("userInfo")
    except TikTokNotFound:
        raise
    except TikTokUpstreamError:
        if not user.get("username"):
            raise
        scope = get_page(f"/@{user['username']}")
        detail = scope.get("webapp.user-detail") or {}
        if detail.get("statusCode") in shared.USER_NOT_FOUND:
            raise TikTokNotFound(f"{label} not found")
        info = detail.get("userInfo")
    if not isinstance(info, dict) or not (info.get("user") or {}).get("secUid"):
        raise TikTokNotFound(f"{label} not found")
    _remember(info)
    return info


def _identity(user):
    """(secUid, compact user) — one lookup, skipped when the ref already is
    a secUid and no compact user is needed."""
    info = lookup(user)
    return info["user"]["secUid"], P.user_ref(info["user"])


def resolve(user):
    """Username <-> user id <-> secUid, with the basic account facts."""
    info = lookup(user)
    out = P.user_ref(info["user"])
    out["follower_count"] = P.user_stats(info.get("stats"), info.get("statsV2"))["follower_count"]
    return out


def get_profile(user):
    """The full profile: bio, bio link, counters, flags, live room id."""
    parsed = P.profile(lookup(user))
    if parsed is None:
        raise TikTokNotFound(f"user {_describe(user)} not found")
    return parsed


def get_posts(user, sort="latest", cursor=None, country=None):
    """The user's videos and photo posts: latest (default), popular or oldest."""
    sec_uid, compact = _identity(user)
    head = {"user": compact, "sort": sort}
    params = {"secUid": sec_uid, "count": POSTS_PAGE, "cursor": cursor or 0,
              "post_item_list_request_type": SORTS[sort], "coverFormat": 2, "needPinnedItemIds": "true"}
    try:
        payload = api("/api/post/item_list/", params, countries=country_order(country, eu_country()),
                      budget=("posts", config.TIKTOK_POSTS_CALLS_PER_EXIT), label=f"videos of {_describe(user)}")
    except TikTokBlocked:
        if sort != "latest":
            raise
        return _creator_posts(sec_uid, cursor, country, head)
    return shared.video_page(payload, **head)


def _creator_posts(sec_uid, cursor, country, head):
    """The unsigned fallback for `latest`. Its cursor is inclusive (the item
    created at the cursor comes back again), so rows at or after it are cut."""
    payload = api("/api/creator/item_list/", {"secUid": sec_uid, "count": CREATOR_PAGE, "cursor": cursor or 0, "type": 1},
                  country=country, signed=False)
    rows = [row for row in payload.get("itemList") or [] if isinstance(row, dict)]
    limit = P.to_int(cursor)
    if limit:
        rows = [row for row in rows if (P.to_int(row.get("createTime")) or 0) * 1000 < limit]
    videos = P.videos(rows)
    more = bool(payload.get("hasMorePrevious")) and bool(rows)
    last = (P.to_int(rows[-1].get("createTime")) or 0) * 1000 if rows else 0
    return {**head, "video_count": len(videos), "videos": videos,
            "next_cursor": str(last) if more and last else None, "has_more": more and bool(last)}


def get_reposts(user, cursor=None, country=None):
    """Videos the user reposted, newest repost first."""
    sec_uid, compact = _identity(user)
    payload = api("/api/repost/item_list/", {"secUid": sec_uid, "count": LIST_PAGE, "cursor": cursor or 0},
                  country=country, signed=False)
    return shared.video_page(payload, user=compact)


def _follow_list(user, kind, cursor):
    sec_uid, compact = _identity(user)
    payload = api("/api/user/list/", {"secUid": sec_uid, "scene": FOLLOW_SCENES[kind], "count": LIST_PAGE,
                                      "minCursor": cursor or 0, "maxCursor": 0},
                  countries=country_order(None, eu_country()), signed=False, ok=(0, LIST_HIDDEN),
                  label=f"{kind} of {_describe(user)}")
    if payload.get("statusCode") == LIST_HIDDEN:
        raise TikTokNotFound(f"{_describe(user)} keeps its {kind} list private")
    rows = P.users(payload.get("userList"), P.user_with_stats)
    next_cursor = shared.next_cursor(payload, "minCursor")
    return {
        "user": compact,
        "total_count": P.to_int(payload.get("total")),
        "user_count": len(rows),
        "users": rows,
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None,
    }


def get_followers(user, cursor=None):
    """Accounts following the user, most recent first, with each one's counters."""
    return _follow_list(user, "followers", cursor)


def get_following(user, cursor=None):
    """Accounts the user follows, most recent first, with each one's counters."""
    return _follow_list(user, "following", cursor)


def get_playlists(user, cursor=None):
    """The user's playlists (ordered series of their own videos)."""
    sec_uid, compact = _identity(user)
    payload = api("/api/user/playlist/", {"secUid": sec_uid, "count": 20, "cursor": cursor or 0}, signed=False)
    playlists = [p for p in (P.playlist(row) for row in payload.get("playList") or []) if p]
    next_cursor = shared.next_cursor(payload)
    return {"user": compact, "playlist_count": len(playlists), "playlists": playlists,
            "next_cursor": next_cursor, "has_more": next_cursor is not None}


def get_collections(user, cursor=None):
    """The user's public collections (folders of saved videos)."""
    sec_uid, compact = _identity(user)
    payload = api("/api/user/collection_list/", {"secUid": sec_uid, "count": 20, "cursor": cursor or 0})
    collections = [c for c in (P.collection(row) for row in payload.get("collectionList") or []) if c]
    next_cursor = shared.next_cursor(payload)
    return {"user": compact, "total_count": P.to_int(payload.get("total")), "collection_count": len(collections),
            "collections": collections, "next_cursor": next_cursor, "has_more": next_cursor is not None}
