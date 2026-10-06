"""Video endpoints: details, media files, comments, comment replies, related
videos, transcript and resolve.

`video` is {"id": ..., "short_link": ...} from refs.resolve_video. A share
link (vm.tiktok.com/…, tiktok.com/t/…) carries no id: it is followed once
(memoised) and the id read off the page it lands on.

Upstream (all signed, probed 2026-10-05):
  * /api/item/detail      one itemStruct, videos and photo posts alike;
                          status 10204 = no such video
  * /api/comment/list     up to 50 a page, offset cursor, `total`; an
                          unknown video answers `comments: null` with no
                          total, which is told apart from "no comments yet"
                          by one detail call
  * /api/comment/list/reply  20 a page
  * /api/related/item_list   one page of 8-16
  * subtitles: itemStruct.video.subtitleInfos[] -> WebVTT files on the CDN
    (auto captions as "ASR", machine translations as "MT"), no cookies needed

`country` picks the exit the video is fetched through (the default exit
serves everything; a video that is unavailable in one region can still be
read through another).
"""
import re
import threading
import time

from . import parsers as P
from . import refs
from . import shared
from .fetch import TikTokBadRequest, TikTokNotFound, api, country_order, eu_country, get_text, resolve_redirect

COMMENTS_PAGE = 50
REPLIES_PAGE = 20
SHORT_TTL = 3600
_short_lock = threading.Lock()
_short_links = {}       # share link -> (expires, video id)

_CUE_TIME_RE = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})")
_TAG_RE = re.compile(r"<[^>]+>")


def video_id(video, country=None):
    """The numeric id of a resolved ref, following a share link if needed."""
    if video.get("id"):
        return video["id"]
    link = video["short_link"]
    with _short_lock:
        hit = _short_links.get(link)
        if hit and hit[0] > time.time():
            return hit[1]
    target = resolve_redirect(link, country=country)
    found = refs.video_id_from_link(target)
    if not found:
        raise TikTokNotFound("that share link does not lead to a video")
    with _short_lock:
        if len(_short_links) > 5000:
            _short_links.clear()
        _short_links[link] = (time.time() + SHORT_TTL, found)
    return found


def _item(video, country):
    vid = video_id(video, country)
    payload = api("/api/item/detail/", {"itemId": vid}, countries=country_order(country, eu_country()),
                  not_found=shared.VIDEO_NOT_FOUND, label=f"video {vid}")
    item = (payload.get("itemInfo") or {}).get("itemStruct")
    if not isinstance(item, dict) or not item.get("id"):
        raise TikTokNotFound(f"video {vid} not found")
    return item


def get_details(video, country=None):
    """Everything about one video or photo post."""
    return P.video(_item(video, country))


def get_media(video, country=None):
    """Only the files: every video rendition, photo, cover, subtitle and the sound."""
    return P.media(_item(video, country))


def resolve(video, country=None):
    """Any accepted reference -> the video's id, canonical link, type and author."""
    parsed = P.video(_item(video, country))
    return {"id": parsed["id"], "link": parsed["link"], "type": parsed["type"],
            "created_at": parsed["created_at"], "author": parsed["author"]}


def get_comments(video, cursor=None, country=None):
    """Top-level comments, ranked as the site shows them."""
    vid = video_id(video, country)
    payload = api("/api/comment/list/", {"aweme_id": vid, "count": COMMENTS_PAGE, "cursor": cursor or 0},
                  country=country, label=f"comments of video {vid}")
    if payload.get("comments") is None and payload.get("total") is None and not cursor:
        _item({"id": vid}, country)          # raises TikTokNotFound for an unknown video
    comments = P.comments(payload.get("comments"))
    next_cursor = shared.next_cursor(payload)
    return {
        "video_id": vid,
        "total_count": P.to_int(payload.get("total")),
        "comment_count": len(comments),
        "comments": comments,
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None,
    }


def get_comment_replies(video, comment_id, cursor=None, country=None):
    """Replies under one comment, oldest first."""
    vid = video_id(video, country)
    payload = api("/api/comment/list/reply/", {"item_id": vid, "comment_id": comment_id, "count": REPLIES_PAGE,
                                               "cursor": cursor or 0},
                  country=country, label=f"replies to comment {comment_id}")
    replies = P.comments(payload.get("comments"))
    next_cursor = shared.next_cursor(payload)
    return {
        "video_id": vid,
        "comment_id": comment_id,
        "total_count": P.to_int(payload.get("total")),
        "reply_count": len(replies),
        "replies": replies,
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None,
    }


def get_related(video, country=None):
    """Videos TikTok recommends next to this one."""
    vid = video_id(video, country)
    payload = api("/api/related/item_list/", {"itemID": vid, "count": 16, "cursor": 0},
                  country=country, label=f"videos related to {vid}")
    videos = P.videos(payload.get("itemList"))
    return {"video_id": vid, "video_count": len(videos), "videos": videos}


# ---- transcript ------------------------------------------------------------------------

def _seconds(hours, minutes, seconds, millis):
    return round(int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000, 3)


def parse_webvtt(text):
    """WebVTT -> [{start_seconds, end_seconds, text}]."""
    segments, current = [], None
    for line in (text or "").replace("\r", "").split("\n"):
        match = _CUE_TIME_RE.search(line)
        if match:
            g = match.groups()
            current = {"start_seconds": _seconds(*g[:4]), "end_seconds": _seconds(*g[4:]), "text": ""}
            segments.append(current)
        elif not line.strip():
            current = None
        elif current is not None:
            piece = _TAG_RE.sub("", line).strip()
            if piece:
                current["text"] = f"{current['text']} {piece}".strip()
    return [segment for segment in segments if segment["text"]]


# TikTok labels caption tracks with ISO 639-3 + region ("eng-US", "spa-ES",
# "cmn-Hans-CN"); callers pass the usual two-letter code.
_ISO3 = {"en": "eng", "es": "spa", "pt": "por", "de": "deu", "fr": "fra", "it": "ita", "ja": "jpn", "ko": "kor",
         "id": "ind", "ru": "rus", "ar": "ara", "vi": "vie", "zh": "cmn", "tr": "tur", "th": "tha", "nl": "nld",
         "pl": "pol", "hi": "hin", "ms": "msa", "sv": "swe", "ro": "ron", "uk": "ukr", "he": "heb", "el": "ell",
         "cs": "ces", "hu": "hun", "fil": "fil", "tl": "fil", "bn": "ben", "ur": "urd", "fa": "fas"}


def _language_matches(track_language, wanted):
    track, wanted = (track_language or "").lower(), wanted.lower()
    if track == wanted:
        return True
    primary, wanted_primary = track.split("-")[0], wanted.split("-")[0]
    if primary not in (wanted_primary, _ISO3.get(wanted_primary)):
        return False
    region = wanted.split("-")[1] if "-" in wanted else None
    return region is None or track.endswith("-" + region)


def _pick_subtitle(tracks, language):
    if language:
        return next((track for track in tracks if _language_matches(track["language"], language)), None)
    originals = [track for track in tracks if not track["is_translation"]]
    return (originals or tracks)[0]


def get_transcript(video, language=None, country=None):
    """The video's captions as timed segments plus the joined text. Without
    `language` the original (auto-generated) track is returned."""
    item = _item(video, country)
    tracks = [t for t in P.subtitles((item.get("video") or {}).get("subtitleInfos")) if (t["format"] or "").lower() == "webvtt"]
    available = sorted({track["language"] for track in tracks if track["language"]})
    if not tracks:
        raise TikTokNotFound(f"video {item.get('id')} has no captions")
    track = _pick_subtitle(tracks, language)
    if track is None:
        raise TikTokBadRequest(f"no captions in {language!r}; available: {', '.join(available)}")
    segments = parse_webvtt(get_text(track["link"], country=country))
    return {
        "video_id": P.to_id(item.get("id")),
        "language": track["language"],
        "is_auto_generated": track["is_auto_generated"],
        "is_translation": track["is_translation"],
        "available_languages": available,
        "text": " ".join(segment["text"] for segment in segments),
        "segment_count": len(segments),
        "segments": segments,
    }
