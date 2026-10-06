"""TikTok reference parsing: ONE param per input that auto-detects its forms
(tripadvisor QueryOrIdField convention — never a sibling `url`/`id` pair).

  user      nasa | @nasa | MS4wLjABAAAA… (a secUid) | https://www.tiktok.com/@nasa
            | a video link (its author)
    -> {"username": "nasa", "sec_uid": None} / {"username": None, "sec_uid": "MS4w…"}
    A bare numeric user id is NOT accepted: the web API cannot look a user
    up by it, and an all-digit string is a valid username.

  video     7692114317151423775 | https://www.tiktok.com/@tiktok/video/7692114317151423775
            | …/photo/<id> | https://m.tiktok.com/v/<id>.html
            | a share link: https://vm.tiktok.com/ZM…/ , https://vt.tiktok.com/ZS…/ ,
              https://www.tiktok.com/t/ZT…/
    -> {"id": "7692…", "short_link": None} / {"id": None, "short_link": "https://vm.tiktok.com/ZM…/"}
    (a share link is resolved by following its redirect, videos.py)

  hashtag   nasa | #nasa | https://www.tiktok.com/tag/nasa            -> "nasa"
  music     7077435666233051138 | https://www.tiktok.com/music/snowfall-7077435666233051138 -> id
  playlist  7681171537575824159 | https://www.tiktok.com/@tiktok/playlist/Songs-7681171537575824159 -> id
  collection 7394627756635573022 | https://www.tiktok.com/@tiktok/collection/Summer-7394627756635573022 -> id
  place     20442395500433212 | https://www.tiktok.com/place/Los-Angeles-Temple-20442395500433212 -> id
  effect    3390122645 | https://www.tiktok.com/sticker/Makeup-Lush-3390122645 -> id
"""
import re
from urllib.parse import quote, unquote, urlparse

SITE = "https://www.tiktok.com"

_HOST_RE = re.compile(r"(^|\.)tiktok\.com$")
_SHORT_HOSTS = {"vm.tiktok.com", "vt.tiktok.com"}
_BARE_LINK_RE = re.compile(r"^(?:[a-z0-9-]+\.)*tiktok\.com(?:[/?#]|$)", re.I)
_USERNAME_RE = re.compile(r"^[a-z0-9._]{1,24}$")
_SEC_UID_RE = re.compile(r"^MS4wLjABAAAA[A-Za-z0-9_-]{20,120}$")
_ID_RE = re.compile(r"^\d{5,25}$")
_VIDEO_ID_RE = re.compile(r"^\d{15,25}$")
_SHORT_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{5,20}$")
_TRAILING_ID_RE = re.compile(r"(?:^|-)(\d{5,25})$")


def _as_url(text):
    if text.startswith(("http://", "https://")):
        return text
    if text.startswith("//"):
        return "https:" + text
    return "https://" + text


def _looks_like_link(text):
    # a bare host must end at a path boundary: "tiktok.community" is a username
    low = text.lower()
    return low.startswith(("http://", "https://", "//")) or bool(_BARE_LINK_RE.match(text))


def _parse_link(text, kind):
    parsed = urlparse(_as_url(text))
    host = (parsed.hostname or "").lower()
    if not _HOST_RE.search(host):
        raise ValueError(f"{kind} link must be a tiktok.com link")
    return host, [unquote(p) for p in parsed.path.split("/") if p]


def _username(text, original):
    name = text.lstrip("@").lower()
    if not _USERNAME_RE.match(name) or name.endswith("."):
        raise ValueError(f"invalid TikTok username {original!r}")
    return name


def resolve_user(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("user must not be empty")
    if _looks_like_link(text):
        _, parts = _parse_link(text, "user")
        if not parts or not parts[0].startswith("@") or len(parts[0]) < 2:
            raise ValueError(f"no @username in link {text!r}")
        text = parts[0]
    if _SEC_UID_RE.match(text):
        return {"username": None, "sec_uid": text}
    if " " in text:
        raise ValueError(f"user must be a TikTok username, a secUid or a tiktok.com profile link, got {text!r}")
    return {"username": _username(text, text), "sec_uid": None}


def resolve_video(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("video must not be empty")
    if _VIDEO_ID_RE.match(text):
        return {"id": text, "short_link": None}
    if not _looks_like_link(text):
        raise ValueError(f"video must be a TikTok video id or a tiktok.com video link, got {text!r}")
    host, parts = _parse_link(text, "video")
    if host in _SHORT_HOSTS:
        if not parts or not _SHORT_CODE_RE.match(parts[0]):
            raise ValueError(f"no share code in link {text!r}")
        return {"id": None, "short_link": f"https://{host}/{parts[0]}/"}
    for i, part in enumerate(parts):
        if part in ("video", "photo", "v") and i + 1 < len(parts):
            candidate = parts[i + 1].split(".")[0]
            if _VIDEO_ID_RE.match(candidate):
                return {"id": candidate, "short_link": None}
        if part == "t" and i + 1 < len(parts) and _SHORT_CODE_RE.match(parts[i + 1]):
            return {"id": None, "short_link": f"{SITE}/t/{parts[i + 1]}/"}
    raise ValueError(f"no video id in link {text!r}")


def video_id_from_link(url):
    """The video id in a full video link, or None (used on the target of a
    resolved share link)."""
    try:
        ref = resolve_video(url)
    except ValueError:
        return None
    return ref["id"]


def resolve_hashtag(value):
    text = str(value or "").strip()
    if _looks_like_link(text):
        _, parts = _parse_link(text, "hashtag")
        if len(parts) < 2 or parts[0] != "tag":
            raise ValueError(f"no hashtag in link {text!r}")
        text = parts[1]
    text = text.lstrip("#").strip()
    if not text:
        raise ValueError("hashtag must not be empty")
    if len(text) > 100 or any(ch.isspace() for ch in text):
        raise ValueError("hashtag must be one word of at most 100 characters")
    return text


def _id_ref(kind, markers, example):
    """A resolver for an entity addressed by a numeric id or by a link whose
    path segment after one of `markers` ends in that id."""
    def resolve(value):
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{kind} must not be empty")
        if _ID_RE.match(text):
            return text
        if _looks_like_link(text):
            _, parts = _parse_link(text, kind)
            for i, part in enumerate(parts):
                if part in markers and i + 1 < len(parts):
                    match = _TRAILING_ID_RE.search(parts[i + 1])
                    if match:
                        return match.group(1)
            raise ValueError(f"no {kind} id in link {text!r}")
        raise ValueError(f"{kind} must be a numeric {kind} id or a tiktok.com {kind} link like {example}, got {text!r}")
    return resolve


resolve_music = _id_ref("music", ("music",), f"{SITE}/music/original-sound-6689804660171082501")
resolve_playlist = _id_ref("playlist", ("playlist",), f"{SITE}/@tiktok/playlist/Songs-7681171537575824159")
resolve_collection = _id_ref("collection", ("collection",), f"{SITE}/@tiktok/collection/Summer-7394627756635573022")
resolve_place = _id_ref("place", ("place",), f"{SITE}/place/Los-Angeles-California-Temple-20442395500433212")
resolve_effect = _id_ref("effect", ("sticker", "effect"), f"{SITE}/sticker/Makeup-Lush-3390122645")


# ---- links -------------------------------------------------------------------------------

def _slug(name):
    text = re.sub(r"[^\w]+", "-", str(name or ""), flags=re.UNICODE).strip("-")
    return quote(text, safe="-") if text else None


def user_link(username):
    return f"{SITE}/@{username}" if username else None


def video_link(username, video_id, is_photo=False):
    if not video_id:
        return None
    kind = "photo" if is_photo else "video"
    # TikTok redirects /@/video/<id> to the author's canonical link
    return f"{SITE}/@{username or ''}/{kind}/{video_id}"


def hashtag_link(name):
    return f"{SITE}/tag/{quote(str(name), safe='')}" if name else None


def music_link(title, music_id):
    if not music_id:
        return None
    return f"{SITE}/music/{_slug(title) or 'original-sound'}-{music_id}"


def playlist_link(username, name, playlist_id):
    if not playlist_id or not username:
        return None
    return f"{SITE}/@{username}/playlist/{_slug(name) or 'playlist'}-{playlist_id}"


def collection_link(username, name, collection_id):
    if not collection_id or not username:
        return None
    return f"{SITE}/@{username}/collection/{_slug(name) or 'collection'}-{collection_id}"


def place_link(name, place_id):
    if not place_id:
        return None
    return f"{SITE}/place/{_slug(name) or 'place'}-{place_id}"


def effect_link(name, effect_id):
    if not effect_id:
        return None
    return f"{SITE}/sticker/{_slug(name) or 'effect'}-{effect_id}"


def live_link(username):
    return f"{SITE}/@{username}/live" if username else None
