"""Helpers shared by the endpoint modules: the paged-list envelope and the
upstream status codes that mean "does not exist"."""
from . import parsers as P

# statusCode values of the webapp services (probed 2026-10-05)
USER_NOT_FOUND = (10202, 10221, 10223)
VIDEO_NOT_FOUND = (10204, 10215, 10216)
MUSIC_NOT_FOUND = (10203, 10218)
HASHTAG_NOT_FOUND = (10205,)
EFFECT_NOT_FOUND = (10208,)
PLACE_NOT_FOUND = (205001,)
BAD_ID = (100001,)            # "invalid params": an id of the right shape that names nothing

INVALID_CURSOR = "invalid cursor: pass the next_cursor value from the previous page unchanged"


def has_more(payload):
    return bool(payload.get("hasMore") or payload.get("has_more") or payload.get("hasMorePrevious"))


def next_cursor(payload, key="cursor"):
    """The upstream cursor as an opaque string, or None on the last page."""
    if not has_more(payload):
        return None
    value = payload.get(key)
    return str(value) if value not in (None, "") else None


def video_page(payload, key="itemList", **head):
    """{...head, video_count, videos, next_cursor, has_more} for one page of
    itemStructs."""
    videos = P.videos(payload.get(key))
    cursor = next_cursor(payload)
    return {**head, "video_count": len(videos), "videos": videos, "next_cursor": cursor, "has_more": cursor is not None}
