"""Discovery endpoints: hashtags, sounds, playlists, collections, places,
effects and the two feeds (trending and explore).

Upstream (probed 2026-10-05):
  * hashtag  /api/challenge/detail (by name; 10205 = unknown) then
             /api/challenge/item_list by id, 30 a page, offset cursor
  * music    /api/music/detail (10203 = unknown), /api/music/item_list 30 a page
  * playlist /api/mix/detail (an unknown id answers 200 without `mixInfo`),
             /api/mix/item_list in playlist order
  * collection /api/collection/item_list 30 a page (the collection's own
             name / owner come from the owner's collection list)
  * place    /api/poi/detail, /api/poi/item_list 30 a page
  * effect   /api/sticker/detail (its video list is refused logged out)
  * trending /api/recommend/item_list — the logged-out For You feed of the
             exit's country, up to 30 fresh videos per call, no cursor:
             calling again returns a new batch
  * explore  /api/explore/item_list — the Explore page's category tabs,
             up to 30 per call, same "call again" paging

The item lists carry full videos (stats, author, music, every rendition).
"""
import threading
import time

from . import parsers as P
from . import shared
from .fetch import TikTokNotFound, api, country_order, eu_country

PAGE = 30
LOOKUP_TTL = 3600
_lookup_lock = threading.Lock()
_hashtag_ids = {}       # lower-case name -> (expires, challengeInfo)

# The Explore page's tabs (categoryType), read off the live feeds 2026-10-05.
EXPLORE_CATEGORIES = {
    "all": 120,
    "singing-dancing": 119,
    "comedy": 104,
    "sports": 112,
    "anime-comics": 100,
    "relationship": 107,
    "shows": 101,
    "lipsync": 110,
    "daily-life": 105,
    "beauty-care": 102,
    "games": 103,
    "society": 114,
    "outfit": 109,
    "cars": 115,
    "food": 111,
    "animals": 113,
    "family": 106,
    "drama": 108,
    "fitness-health": 117,
    "education": 116,
    "technology": 118,
}
EXPLORE_NAMES = {
    "all": "All", "singing-dancing": "Singing & Dancing", "comedy": "Comedy", "sports": "Sports",
    "anime-comics": "Anime & Comics", "relationship": "Relationship", "shows": "Shows", "lipsync": "Lipsync",
    "daily-life": "Daily Life", "beauty-care": "Beauty Care", "games": "Games", "society": "Society",
    "outfit": "Outfit", "cars": "Cars", "food": "Food", "animals": "Animals", "family": "Family",
    "drama": "Drama", "fitness-health": "Fitness & Health", "education": "Education", "technology": "Technology",
}


# ---- hashtags --------------------------------------------------------------------------

def _hashtag_info(name):
    key = name.lower()
    with _lookup_lock:
        hit = _hashtag_ids.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
    payload = api("/api/challenge/detail/", {"challengeName": name}, countries=country_order(None, eu_country()),
                  not_found=shared.HASHTAG_NOT_FOUND, label=f"hashtag #{name}")
    info = payload.get("challengeInfo")
    if not isinstance(info, dict) or not (info.get("challenge") or {}).get("id"):
        raise TikTokNotFound(f"hashtag #{name} not found")
    with _lookup_lock:
        if len(_hashtag_ids) > 5000:
            _hashtag_ids.clear()
        _hashtag_ids[key] = (time.time() + LOOKUP_TTL, info)
    return info


def get_hashtag(hashtag):
    """A hashtag's id, description, video count and total views."""
    return P.hashtag(_hashtag_info(hashtag))


def get_hashtag_posts(hashtag, cursor=None, country=None):
    """Videos under a hashtag, in the site's ranked order."""
    info = _hashtag_info(hashtag)
    payload = api("/api/challenge/item_list/", {"challengeID": info["challenge"]["id"], "count": PAGE, "cursor": cursor or 0},
                  countries=country_order(country, eu_country()), label=f"videos of #{hashtag}")
    return shared.video_page(payload, hashtag=P.hashtag_ref(info["challenge"]))


# ---- music -----------------------------------------------------------------------------

def _music_info(music, country=None):
    payload = api("/api/music/detail/", {"musicId": music}, countries=country_order(country, eu_country()),
                  not_found=shared.MUSIC_NOT_FOUND, label=f"sound {music}")
    info = payload.get("musicInfo")
    if not isinstance(info, dict) or not (info.get("music") or {}).get("id"):
        raise TikTokNotFound(f"sound {music} not found")
    return info


def get_music(music):
    """A sound: title, artist, duration, audio file, usage count, the
    account that posted it and its Apple Music / Spotify ids."""
    info = _music_info(music)
    return P.music(info.get("music"), info.get("stats") or {}, info.get("author") or {})


def get_music_posts(music, cursor=None, country=None):
    """Videos that use a sound."""
    payload = api("/api/music/item_list/", {"musicID": music, "count": PAGE, "cursor": cursor or 0},
                  countries=country_order(country, eu_country()), not_found=shared.BAD_ID,
                  label=f"sound {music}")
    if not payload.get("itemList") and not cursor:
        _music_info(music, country)          # raises TikTokNotFound for an unknown sound
    return shared.video_page(payload, music_id=music)


# ---- playlists / collections -----------------------------------------------------------

def get_playlist(playlist):
    """A playlist's name, cover, video count and creator."""
    payload = api("/api/mix/detail/", {"mixId": playlist}, not_found=shared.BAD_ID, label=f"playlist {playlist}")
    parsed = P.playlist(payload.get("mixInfo"))
    if parsed is None:
        raise TikTokNotFound(f"playlist {playlist} not found")
    return parsed


def get_playlist_posts(playlist, cursor=None, country=None):
    """A playlist's videos in the creator's order."""
    payload = api("/api/mix/item_list/", {"mixId": playlist, "count": PAGE, "cursor": cursor or 0},
                  country=country, signed=False, not_found=shared.BAD_ID, label=f"playlist {playlist}")
    if not payload.get("itemList") and not cursor:
        get_playlist(playlist)               # raises TikTokNotFound for an unknown playlist
    return shared.video_page(payload, playlist_id=playlist)


def get_collection_posts(collection, cursor=None, country=None):
    """The videos saved in a public collection."""
    payload = api("/api/collection/item_list/", {"collectionId": collection, "count": PAGE, "cursor": cursor or 0,
                                                 "sourceType": 113},
                  country=country, not_found=shared.BAD_ID, label=f"collection {collection}")
    if not payload.get("itemList") and not cursor:
        raise TikTokNotFound(f"collection {collection} not found (or it is private)")
    return shared.video_page(payload, collection_id=collection)


# ---- places / effects ------------------------------------------------------------------

def get_place(place):
    """A tagged location: name, address, category, photos and video count."""
    payload = api("/api/poi/detail/", {"poiId": place}, not_found=shared.PLACE_NOT_FOUND + shared.BAD_ID,
                  label=f"place {place}")
    parsed = P.place(payload.get("poiInfo"))
    if parsed is None:
        raise TikTokNotFound(f"place {place} not found")
    return parsed


def get_place_posts(place, cursor=None, country=None):
    """Videos tagged at a location."""
    payload = api("/api/poi/item_list/", {"poiId": place, "count": PAGE, "cursor": cursor or 0},
                  country=country, not_found=shared.PLACE_NOT_FOUND + shared.BAD_ID, label=f"place {place}")
    if not payload.get("itemList") and not cursor:
        get_place(place)                     # raises TikTokNotFound for an unknown place
    return shared.video_page(payload, place_id=place)


def get_effect(effect):
    """An effect (sticker): name, icon and the creator who made it."""
    payload = api("/api/sticker/detail/", {"stickerId": effect}, not_found=shared.EFFECT_NOT_FOUND + shared.BAD_ID,
                  label=f"effect {effect}")
    parsed = P.effect(payload.get("stickerInfo"))
    if parsed is None:
        raise TikTokNotFound(f"effect {effect} not found")
    return parsed


# ---- feeds -----------------------------------------------------------------------------

def get_trending(country=None):
    """The For You feed a logged-out visitor in `country` is shown right
    now. Every call returns a fresh batch."""
    code = (country or "").lower() or None
    payload = api("/api/recommend/item_list/", {"count": PAGE}, country=code, label="trending feed")
    videos = P.videos(payload.get("itemList"))
    return {"country": (code or country_order(None)[0]).upper(), "video_count": len(videos), "videos": videos}


def get_explore(category="all", country=None):
    """One tab of the Explore page. Every call returns a fresh batch."""
    code = (country or "").lower() or None
    payload = api("/api/explore/item_list/", {"categoryType": EXPLORE_CATEGORIES[category], "count": PAGE},
                  country=code, signed=False, label="explore feed")
    videos = P.videos(payload.get("itemList"))
    return {"category": category, "country": (code or country_order(None)[0]).upper(),
            "video_count": len(videos), "videos": videos}


def get_explore_categories():
    """The Explore tabs accepted by /tiktok/feed/explore."""
    return {"category_count": len(EXPLORE_CATEGORIES),
            "categories": [{"id": key, "name": EXPLORE_NAMES[key]} for key in EXPLORE_CATEGORIES]}
