"""TikTok normalizers: the web API's objects -> one clean snake_case shape per
entity, whichever endpoint served them.

Output conventions (shared with the other scrapers here): `link` for
canonical tiktok.com URLs, `*_link` / `cover` / `profile_picture` for media
URLs, `*_count` for counters, `is_*` / `has_*` for booleans, ISO-8601 UTC
timestamps (the upstream's epoch seconds), numbers as numbers, null for
missing, [] for empty lists. Ids stay STRINGS: they are 19-20 digits and
overflow a JavaScript number.

Entity shapes:
  user (compact)  {id, sec_uid, username, nickname, link, profile_picture,
                   is_verified, is_private, biography}
  profile         compact user + created_at, bio_link, language, flags,
                   live room id, stats{...}, tabs{...}
  video           {id, link, type, description, language, created_at, flags,
                   playlist_id, stats{...}, author, author_stats, music,
                   video{...} | images[...], hashtags, mentions, location,
                   effects, text_stickers, anchors, suggested_searches}
                   `type` is "video" or "photo" (a photo carousel: `images`
                   is filled and `video` is null).
  comment         {id, video_id, link, text, language, created_at,
                   like_count, reply_count, flags, parent_comment_id,
                   user, images, mentions}

The web API serves the same entity in two dialects — camelCase from the
webapp services (itemStruct, userInfo) and snake_case from search and
comments (user_info, comments[].user) — and counters twice (`stats` rounded
to 3 digits: 96100000, `statsV2` exact strings: "96072949"). Every parser
reads both dialects and prefers the exact counters.

Media links (checked 2026-10-05 from fresh exits with no cookies):
`video.play_link` and every `qualities[].play_link` prefer TikTok's
`www.tiktok.com/aweme/v1/play/` form, which streams the mp4 with no cookie
and no Referer — but only to IPs in the region that hosts the video (a US
video answered 206 video/mp4 from US exits and an HTML page from German
ones, whichever exit minted the link). The CDN-host forms that follow it in
`play_links`, and `download_link`, answer 403 without the minting session's
`tt_chain_token` cookie. Cover / avatar / photo / subtitle / sound links
carry their own signature and open anywhere until their `x-expires`.

Deliberately dropped as noise:
  viewer state   digged, collected, relation, followStatus, user_digged,
                 user_buried, is_author_digged's sibling collect_stat,
                 forFriend, secret (= privateAccount), openFavorite on
                 compact users, isCollected — the logged-out viewer's own
                 state, always false
  tracking       extra.logid, log_pb, backendSourceEventTracking,
                 diversificationId, contentContext, enterMdpPV, sort_tags,
                 sort_extra_score, word_record, extra_info, logExtra,
                 penaltyContext / item_control / creatorAIComment /
                 itemCommentStatus (moderation and ranking internals)
  duplicates     stats when statsV2 is present, avatarMedium / avatarThumb
                 (avatarLarger kept), coverMedium / coverThumb,
                 video.PlayAddrStruct (= bitrateInfo[0].PlayAddr),
                 video.zoomCover (four resizes of cover), contents[] (desc
                 + textExtra again), heart (= heartCount), mixName (= name),
                 claInfo.captionInfos (= subtitleInfos), shareMeta (title /
                 description strings built from the same fields),
                 comment share_info (a share sentence + the video link)
  undocumented enums  commentSetting, duetSetting, stitchSetting,
                 downloadSetting, followingVisibility, duetDisplay,
                 stitchDisplay, CategoryType, maskType, itemMute,
                 trans_btn_style, fold_status, reply_style — per-viewer
                 permission codes TikTok never labels; the booleans that
                 matter (duetEnabled, stitchEnabled, shareEnabled) are kept
  player internals    VQScore, MVMAF, VideoExtra, FileCs, FileHash,
                 volumeInfo, encodedType, encodeUserTag, videoTags,
                 tt2dsp tokens (Apple Music developer JWTs)
  live internals      room_auth, link_mic, room_create_ab_param, the
                 `deprecated*` keys, pay grades, badge lists, push urls —
                 broadcaster / gifting plumbing with no public reading
"""
import json
import re
from datetime import datetime, timezone

from . import refs

_QUALITY_RE = re.compile(r"_(\d{3,4}p)(?:_|$)")
_GEAR_RE = re.compile(r"_(\d{3,4})_")
COOKIELESS_PLAY_PREFIX = "https://www.tiktok.com/aweme/v1/play/"
DSP_PLATFORMS = {1: ("apple_music", "https://music.apple.com/song/{}"),
                 3: ("spotify", "https://open.spotify.com/track/{}")}
LIVE_STATUS = {2: "live", 4: "offline"}


# ---- scalars ---------------------------------------------------------------------------
# The same scalar helpers the other scrapers here use, kept inside this
# package so it runs standalone (no sibling scraper packages needed).

def clean(value):
    """Whitespace-trimmed string, or None for empty / non-strings."""
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = str(value).strip()
    return text or None


def to_int(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip().replace(",", "")
    try:
        return int(text)
    except ValueError:
        return None


def to_float(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_bool(value):
    """True/False for real booleans (and 0/1), None when absent."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def to_id(value):
    """An upstream numeric id as a string (they exceed 2**53)."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def iso_utc(epoch):
    """Epoch seconds -> 2026-09-17T14:27:44Z."""
    seconds = to_int(epoch)
    if not seconds:
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        return None


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _pick(raw, *keys):
    """The first non-empty value among `keys` (the two API dialects)."""
    for key in keys:
        value = raw.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def link_list(value):
    """Every URL in a string | [urls] | {urlList / url_list / UrlList: [...]}."""
    if isinstance(value, str):
        return [value] if value.startswith("http") else []
    if isinstance(value, dict):
        value = value.get("urlList") or value.get("url_list") or value.get("UrlList")
    return [url for url in _list(value) if isinstance(url, str) and url.startswith("http")]


def first_link(value):
    urls = link_list(value)
    return urls[0] if urls else None


def iso_utc_ms(epoch_ms):
    value = to_int(epoch_ms)
    return iso_utc(value // 1000) if value else None


def iso_date_ms(epoch_ms):
    """Epoch milliseconds -> YYYY-MM-DD (UTC) for day-granular fields."""
    stamp = iso_utc_ms(epoch_ms)
    return stamp[:10] if stamp else None


# ---- users -----------------------------------------------------------------------------

def user_ref(raw):
    """The compact user from either dialect, or None without an id / name."""
    raw = _dict(raw)
    username = clean(_pick(raw, "uniqueId", "unique_id", "display_id"))
    user_id = to_id(_pick(raw, "id", "uid", "id_str"))
    if not username and not user_id:
        return None
    if "verified" in raw:
        is_verified = to_bool(raw.get("verified"))
    else:
        is_verified = bool(clean(raw.get("custom_verify")) or clean(raw.get("enterprise_verify_reason")))
    return {
        "id": user_id,
        "sec_uid": clean(_pick(raw, "secUid", "sec_uid")),
        "username": username,
        "nickname": clean(raw.get("nickname")),
        "link": refs.user_link(username),
        "profile_picture": first_link(_pick(raw, "avatarLarger", "avatar_larger", "avatar_large", "avatarMedium",
                                            "avatar_medium", "avatarThumb", "avatar_thumb")),
        "is_verified": is_verified,
        "is_private": to_bool(_pick(raw, "privateAccount", "secret")) if ("privateAccount" in raw or "secret" in raw) else None,
        "biography": clean(_pick(raw, "signature", "bio_description")),
    }


def user_stats(stats, exact=None):
    """Counters of a user; `exact` (statsV2) wins over the rounded `stats`."""
    stats, exact = _dict(stats), _dict(exact)

    def count(*keys):
        for source in (exact, stats):
            for key in keys:
                value = to_int(source.get(key))
                if value is not None:
                    return value
        return None

    return {
        "follower_count": count("followerCount", "follower_count"),
        "following_count": count("followingCount", "following_count"),
        "like_count": count("heartCount", "heart", "total_favorited"),
        "video_count": count("videoCount", "aweme_count"),
        "friend_count": count("friendCount"),
        "liked_video_count": count("diggCount"),
    }


def profile(user_info):
    """webapp userInfo ({user, stats, statsV2}) -> the full profile."""
    user_info = _dict(user_info)
    raw = _dict(user_info.get("user"))
    out = user_ref(raw)
    if out is None:
        return None
    commerce = _dict(raw.get("commerceUserInfo"))
    tabs = _dict(raw.get("profileTab"))
    room_id = to_id(raw.get("roomId")) if raw.get("roomId") not in ("", "0", 0) else None
    out.update({
        "bio_link": clean(_dict(raw.get("bioLink")).get("link")),
        "language": clean(raw.get("language")),
        "region": clean(raw.get("region")),
        "created_at": iso_utc(raw.get("createTime")),
        "username_changed_at": iso_utc(raw.get("uniqueIdModifyTime")),
        "nickname_changed_at": iso_utc(raw.get("nickNameModifyTime")),
        "is_organization": to_bool(raw.get("isOrganization")),
        "is_seller": to_bool(raw.get("ttSeller")),
        "is_business_account": to_bool(commerce.get("commerceUser")),
        "business_category": clean(commerce.get("category")),
        "is_virtual_ad_account": to_bool(raw.get("isADVirtual")),
        "is_under_ftc_restriction": to_bool(raw.get("ftc")),
        "is_embed_banned": to_bool(raw.get("isEmbedBanned")),
        "are_liked_videos_public": to_bool(raw.get("openFavorite")),
        "is_live": room_id is not None,
        "live_room_id": room_id,
        "stats": user_stats(user_info.get("stats"), user_info.get("statsV2")),
        "tabs": {
            "has_playlists": to_bool(tabs.get("showPlayListTab")),
            "has_music": to_bool(tabs.get("showMusicTab")),
            "has_questions": to_bool(tabs.get("showQuestionTab")),
        },
    })
    return out


def user_with_stats(row):
    """A {user, stats, statsV2} row (followers / following lists)."""
    row = _dict(row)
    out = user_ref(row.get("user"))
    if out is None:
        return None
    out["is_seller"] = to_bool(_dict(row.get("user")).get("ttSeller"))
    out["stats"] = user_stats(row.get("stats"), row.get("statsV2"))
    return out


def search_user(row):
    """One user search hit (snake_case `user_info`)."""
    raw = _dict(_dict(row).get("user_info"))
    out = user_ref(raw)
    if out is None:
        return None
    room_id = to_id(raw.get("room_id_str") or raw.get("room_id"))
    out["verification_reason"] = clean(raw.get("enterprise_verify_reason")) or clean(raw.get("custom_verify"))
    out["follower_count"] = to_int(raw.get("follower_count"))
    out["like_count"] = to_int(raw.get("total_favorited"))
    out["is_live"] = bool(room_id and room_id != "0")
    out["live_room_id"] = room_id if room_id and room_id != "0" else None
    return out


def users(rows, parser=user_ref):
    return [user for user in (parser(row) for row in _list(rows)) if user]


# ---- music -----------------------------------------------------------------------------

def _streaming_links(raw):
    out = []
    for info in _list(_dict(raw.get("tt2dsp")).get("tt_to_dsp_song_infos")):
        info = _dict(info)
        song_id = clean(info.get("song_id"))
        platform = DSP_PLATFORMS.get(info.get("platform"))
        if song_id and platform:
            out.append({"platform": platform[0], "song_id": song_id, "link": platform[1].format(song_id)})
    return out


def music(raw, stats=None, author=None):
    raw = _dict(raw)
    music_id = to_id(raw.get("id"))
    if not music_id:
        return None
    title = clean(raw.get("title"))
    out = {
        "id": music_id,
        "title": title,
        "link": refs.music_link(title, music_id),
        "author_name": clean(raw.get("authorName")),
        "album": clean(raw.get("album")),
        "duration_seconds": to_int(raw.get("duration")),
        "play_link": first_link(raw.get("playUrl")),
        "cover": first_link(_pick(raw, "coverLarge", "coverMedium", "coverThumb")),
        "is_original_sound": to_bool(raw.get("original")),
        "is_copyrighted": to_bool(raw.get("isCopyrighted")),
        "is_commercial_use_allowed": to_bool(raw.get("is_commerce_music")),
        "is_unlimited_music": to_bool(raw.get("is_unlimited_music")),
        "is_private": to_bool(raw.get("private")),
        "streaming_links": _streaming_links(raw),
    }
    if stats is not None:
        out["video_count"] = to_int(_dict(stats).get("videoCount"))
    if author is not None:
        out["author"] = user_ref(author)
    return out


# ---- hashtags --------------------------------------------------------------------------

def hashtag_ref(raw):
    raw = _dict(raw)
    name = clean(_pick(raw, "title", "hashtagName", "cha_name"))
    if not name:
        return None
    return {"id": to_id(_pick(raw, "id", "hashtagId", "cid")), "name": name, "link": refs.hashtag_link(name)}


def hashtag(challenge_info):
    """webapp challengeInfo ({challenge, stats, statsV2}) -> the hashtag."""
    info = _dict(challenge_info)
    raw = _dict(info.get("challenge"))
    out = hashtag_ref(raw)
    if out is None:
        return None
    exact, stats = _dict(info.get("statsV2")), _dict(info.get("stats") or raw.get("stats"))
    announcement = _dict(info.get("challengeAnnouncement"))
    out.update({
        "description": clean(raw.get("desc")),
        "is_commercial": to_bool(raw.get("isCommerce")),
        "video_count": to_int(exact.get("videoCount")) if exact.get("videoCount") is not None else to_int(stats.get("videoCount")),
        "view_count": to_int(exact.get("viewCount")) if exact.get("viewCount") is not None else to_int(stats.get("viewCount")),
        "cover": first_link(_pick(raw, "coverLarger", "coverMedium", "coverThumb")),
        "profile_picture": first_link(_pick(raw, "profileLarger", "profileMedium", "profileThumb")),
        "announcement": {"title": clean(announcement.get("title")), "body": clean(announcement.get("body"))}
        if clean(announcement.get("title")) or clean(announcement.get("body")) else None,
    })
    return out


# ---- places ----------------------------------------------------------------------------

def location(raw):
    """A video's tagged place (`poi`), or None."""
    raw = _dict(raw)
    place_id = to_id(raw.get("id"))
    name = clean(raw.get("name"))
    if not place_id and not name:
        return None
    return {
        "id": place_id,
        "name": name,
        "link": refs.place_link(name, place_id),
        "address": clean(raw.get("address")),
        "city": clean(raw.get("city")),
        "province": clean(raw.get("province")),
        "country": clean(raw.get("country")),
        "category": clean(raw.get("category")),
        "category_path": [name for name in (clean(raw.get(key)) for key in
                                            ("ttTypeNameSuper", "ttTypeNameMedium", "ttTypeNameTiny")) if name],
        "parent": {"id": to_id(raw.get("fatherPoiId")), "name": clean(raw.get("fatherPoiName"))}
        if clean(raw.get("fatherPoiId")) or clean(raw.get("fatherPoiName")) else None,
    }


def place(poi_info):
    """webapp poiInfo ({poi, stats}) -> the place page."""
    info = _dict(poi_info)
    raw = _dict(info.get("poi"))
    out = location(raw)
    if out is None:
        return None
    stats = _dict(info.get("stats"))
    out.update({
        "is_claimed": to_bool(raw.get("isClaimed")),
        "has_phone": to_bool(_dict(raw.get("phoneInfo")).get("exist")),
        "video_count": to_int(stats.get("videoCount")),
        "pictures": [url for url in (first_link(pic) for pic in _list(_dict(raw.get("pictureAlbum")).get("pictures"))) if url],
    })
    return out


# ---- videos ----------------------------------------------------------------------------

def _stats(item):
    exact, stats = _dict(item.get("statsV2")), _dict(item.get("stats"))

    def count(key):
        value = to_int(exact.get(key))
        return value if value is not None else to_int(stats.get(key))

    return {
        "play_count": count("playCount"),
        "like_count": count("diggCount"),
        "comment_count": count("commentCount"),
        "share_count": count("shareCount"),
        "save_count": count("collectCount"),
        "repost_count": count("repostCount"),
    }


def _ordered_links(value):
    """A rendition's URLs with the cookieless www.tiktok.com form first."""
    urls = link_list(value)
    return sorted(urls, key=lambda url: not url.startswith(COOKIELESS_PLAY_PREFIX))


def _quality_label(row):
    match = _QUALITY_RE.search(str(_dict(row.get("PlayAddr")).get("UrlKey") or ""))
    if match:
        return match.group(1)
    match = _GEAR_RE.search(str(row.get("GearName") or ""))
    return match.group(1) + "p" if match else None


def _qualities(rows):
    out = []
    for row in _list(rows):
        row = _dict(row)
        address = _dict(row.get("PlayAddr"))
        urls = _ordered_links(address)
        if not urls:
            continue
        out.append({
            "quality": _quality_label(row),
            "codec": clean(row.get("CodecType")),
            "format": clean(row.get("Format")),
            "bitrate": to_int(row.get("Bitrate")),
            "fps": to_int(row.get("BitrateFPS")),
            "width": to_int(address.get("Width")),
            "height": to_int(address.get("Height")),
            "size_bytes": to_int(address.get("DataSize")),
            "play_link": urls[0],
            "play_links": urls,
        })
    out.sort(key=lambda q: (-(min(q["width"] or 0, q["height"] or 0)), -(q["bitrate"] or 0)))
    return out


def subtitles(rows):
    out = []
    for row in _list(rows):
        row = _dict(row)
        url = first_link(row.get("Url"))
        if not url:
            continue
        source = clean(row.get("Source"))
        out.append({
            "language": clean(row.get("LanguageCodeName")),
            "source": source.lower() if source else None,
            "is_auto_generated": source == "ASR" if source else None,
            "is_translation": source == "MT" if source else None,
            "format": clean(row.get("Format")),
            "size_bytes": to_int(row.get("Size")),
            "link": url,
            "expires_at": iso_utc(row.get("UrlExpire")),
        })
    return out


def video_file(raw):
    """itemStruct.video -> the playable video block (None for photo posts,
    whose `video` holds only a cover)."""
    raw = _dict(raw)
    qualities = _qualities(raw.get("bitrateInfo"))
    play_links = _ordered_links(_dict(raw.get("PlayAddrStruct"))) or link_list(raw.get("playAddr"))
    if not qualities and not play_links:
        return None
    return {
        "duration_seconds": to_int(raw.get("duration")),
        "width": to_int(raw.get("width")),
        "height": to_int(raw.get("height")),
        "quality": clean(_pick(raw, "definition", "ratio")),
        "format": clean(raw.get("format")),
        "codec": clean(raw.get("codecType")),
        "bitrate": to_int(raw.get("bitrate")),
        "size_bytes": to_int(raw.get("size")),
        "cover": first_link(raw.get("cover")),
        "origin_cover": first_link(raw.get("originCover")),
        "animated_cover": first_link(raw.get("dynamicCover")),
        "play_link": play_links[0] if play_links else (qualities[0]["play_link"] if qualities else None),
        "download_link": first_link(raw.get("downloadAddr")),
        "qualities": qualities,
        "subtitles": subtitles(raw.get("subtitleInfos")),
    }


def images(image_post):
    out = []
    for image in _list(_dict(image_post).get("images")):
        image = _dict(image)
        urls = link_list(image.get("imageURL"))
        if urls:
            out.append({"width": to_int(image.get("imageWidth")), "height": to_int(image.get("imageHeight")),
                        "link": urls[0], "links": urls})
    return out


def _text_entities(item):
    """(hashtags, mentions) from challenges + the caption's textExtra."""
    hashtags, seen = [], set()
    for raw in _list(item.get("challenges")) + [t for t in _list(item.get("textExtra")) if _dict(t).get("hashtagName")]:
        tag = hashtag_ref(raw)
        if tag and tag["name"].lower() not in seen:
            seen.add(tag["name"].lower())
            hashtags.append(tag)
    mentions, seen_users = [], set()
    for raw in _list(item.get("textExtra")):
        raw = _dict(raw)
        username = clean(raw.get("userUniqueId"))
        if username and username not in seen_users:
            seen_users.add(username)
            mentions.append({"id": to_id(raw.get("userId")), "sec_uid": clean(raw.get("secUid")),
                             "username": username, "link": refs.user_link(username)})
    return hashtags, mentions


def _effects(rows):
    out = []
    for raw in _list(rows):
        raw = _dict(raw)
        effect_id, name = to_id(raw.get("ID")), clean(raw.get("name"))
        if effect_id or name:
            out.append({"id": effect_id, "name": name, "link": refs.effect_link(name, effect_id)})
    return out


def _text_stickers(rows):
    """Text overlays the creator placed on the video."""
    out = []
    for raw in _list(rows):
        for text in _list(_dict(raw).get("stickerText")):
            text = clean(text)
            if text:
                out.append(text)
    return out


def _anchors(rows):
    """Link stickers under the caption (CapCut template, shop, playlist …)."""
    out = []
    for raw in _list(rows):
        raw = _dict(raw)
        title = clean(raw.get("keyword"))
        if not title and not clean(raw.get("description")):
            continue
        out.append({"id": to_id(raw.get("id")), "type": to_int(raw.get("type")), "title": title,
                    "description": clean(raw.get("description")), "link": clean(raw.get("schema")),
                    "icon": first_link(raw.get("icon"))})
    return out


def _suggested_searches(item):
    words = [clean(word) for word in _list(item.get("suggestedWords"))]
    for group in _list(_dict(item.get("videoSuggestWordsList")).get("video_suggest_words_struct")):
        words += [clean(_dict(word).get("word")) for word in _list(_dict(group).get("words"))]
    out = []
    for word in words:
        if word and word not in out:
            out.append(word)
    return out


def video(item):
    """One webapp itemStruct -> the video shape, or None without an id."""
    item = _dict(item)
    video_id = to_id(item.get("id"))
    if not video_id:
        return None
    author = user_ref(item.get("author"))
    photo_post = _dict(item.get("imagePost"))
    is_photo = bool(photo_post)
    raw_video = _dict(item.get("video"))
    hashtags, mentions = _text_entities(item)
    author_stats = item.get("authorStats") or item.get("authorStatsV2")
    aigc = item.get("aigcLabelType")
    return {
        "id": video_id,
        "link": refs.video_link(author["username"] if author else None, video_id, is_photo),
        "type": "photo" if is_photo else "video",
        "description": clean(item.get("desc")),
        "title": clean(photo_post.get("title")) if is_photo else None,
        "language": clean(item.get("textLanguage")),
        "created_at": iso_utc(item.get("createTime")),
        "location_created": clean(item.get("locationCreated")),
        "is_ad": to_bool(item.get("isAd")),
        "is_pinned": bool(item.get("isPinnedItem")),
        "is_private": to_bool(item.get("privateItem")),
        "is_ai_generated": bool(aigc) if aigc is not None else None,
        "is_original": to_bool(item.get("originalItem")),
        "is_official": to_bool(item.get("officalItem")),
        "is_duet_enabled": to_bool(item.get("duetEnabled")),
        "is_stitch_enabled": to_bool(item.get("stitchEnabled")),
        "is_share_enabled": to_bool(item.get("shareEnabled")),
        "playlist_id": to_id(item.get("playlistId")),
        "stats": _stats(item),
        "author": author,
        "author_stats": user_stats(item.get("authorStats"), item.get("authorStatsV2")) if author_stats else None,
        "music": music(item.get("music")),
        "video": None if is_photo else video_file(raw_video),
        "images": images(photo_post),
        "cover": first_link(_pick(raw_video, "cover", "originCover")) or first_link(_dict(photo_post.get("cover")).get("imageURL")),
        "hashtags": hashtags,
        "mentions": mentions,
        "location": location(item.get("poi")),
        "effects": _effects(item.get("effectStickers")),
        "text_stickers": _text_stickers(item.get("stickersOnItem")),
        "anchors": _anchors(item.get("anchors")),
        "suggested_searches": _suggested_searches(item),
    }


def videos(rows):
    return [parsed for parsed in (video(row) for row in _list(rows)) if parsed]


def media(item):
    """Just the downloadable files of one itemStruct (/videos/media)."""
    parsed = video(item)
    if parsed is None:
        return None
    return {
        "id": parsed["id"],
        "link": parsed["link"],
        "type": parsed["type"],
        "description": parsed["description"],
        "author": parsed["author"],
        "cover": parsed["cover"],
        "video": parsed["video"],
        "images": parsed["images"],
        "music": parsed["music"],
    }


# ---- comments --------------------------------------------------------------------------

def _comment_images(rows):
    out = []
    for raw in _list(rows):
        raw = _dict(raw)
        origin = _dict(raw.get("origin_url") or raw.get("crop_url"))
        url = first_link(origin)
        if url:
            out.append({"width": to_int(origin.get("width")), "height": to_int(origin.get("height")), "link": url})
    return out


def comment(raw, username=None):
    raw = _dict(raw)
    comment_id = to_id(raw.get("cid"))
    if not comment_id:
        return None
    video_id = to_id(raw.get("aweme_id"))
    parent = to_id(raw.get("reply_id"))
    reply_to = to_id(raw.get("reply_to_reply_id"))
    mentions = []
    for extra in _list(raw.get("text_extra")):
        extra = _dict(extra)
        user_id = to_id(extra.get("user_id"))
        if user_id:
            mentions.append({"id": user_id, "sec_uid": clean(extra.get("sec_uid"))})
    link = refs.video_link(username, video_id)
    return {
        "id": comment_id,
        "video_id": video_id,
        "link": f"{link}?comment_id={comment_id}" if link else None,
        "text": clean(raw.get("text")),
        "language": clean(raw.get("comment_language")),
        "created_at": iso_utc(raw.get("create_time")),
        "like_count": to_int(raw.get("digg_count")),
        "reply_count": to_int(raw.get("reply_comment_total")),
        "is_liked_by_author": to_bool(raw.get("is_author_digged")),
        "is_pinned_by_author": bool(raw.get("author_pin")) or bool(to_int(raw.get("stick_position"))),
        "has_purchase_intent": to_bool(raw.get("is_high_purchase_intent")),
        "parent_comment_id": parent if parent and parent != "0" else None,
        "replied_to_comment_id": reply_to if reply_to and reply_to != "0" else None,
        "user": user_ref(raw.get("user")),
        "images": _comment_images(raw.get("image_list")),
        "mentions": mentions,
    }


def comments(rows, username=None):
    return [parsed for parsed in (comment(row, username) for row in _list(rows)) if parsed]


# ---- playlists / collections -----------------------------------------------------------

def playlist(raw):
    raw = _dict(raw)
    playlist_id = to_id(_pick(raw, "id", "mixId"))
    if not playlist_id:
        return None
    creator = user_ref(raw.get("creator"))
    name = clean(_pick(raw, "name", "mixName"))
    return {
        "id": playlist_id,
        "name": name,
        "link": refs.playlist_link(creator["username"] if creator else None, name, playlist_id),
        "video_count": to_int(raw.get("videoCount")),
        "cover": first_link(raw.get("cover")),
        "creator": creator,
    }


def collection(raw):
    raw = _dict(raw)
    collection_id = to_id(raw.get("collectionId"))
    if not collection_id:
        return None
    name, username = clean(raw.get("name")), clean(raw.get("userName"))
    return {
        "id": collection_id,
        "name": name,
        "link": refs.collection_link(username, name, collection_id),
        "video_count": to_int(raw.get("total")),
        "cover": first_link(raw.get("cover")),
        "owner": {"id": to_id(raw.get("userId")), "username": username, "link": refs.user_link(username)},
    }


# ---- effects ---------------------------------------------------------------------------

def effect(sticker_info):
    info = _dict(sticker_info)
    raw = _dict(info.get("sticker"))
    effect_id, name = to_id(_pick(raw, "id", "ID")), clean(raw.get("name"))
    if not effect_id and not name:
        return None
    return {
        "id": effect_id,
        "name": name,
        "link": refs.effect_link(name, effect_id),
        "description": clean(raw.get("desc")),
        "icon": first_link(_pick(raw, "coverUrls", "coverLarger", "coverMedium", "coverThumb")),
        "author": user_ref(info.get("author")),
    }


# ---- search ----------------------------------------------------------------------------

def suggestions(rows):
    out = []
    for row in _list(rows):
        text = clean(_dict(row).get("content"))
        if text and text not in out:
            out.append(text)
    return out


def top_results(rows):
    """The mixed "Top" search list -> (videos, users), each in page order."""
    found_videos, found_users = [], []
    for row in _list(rows):
        row = _dict(row)
        if row.get("type") == 1:
            parsed = video(row.get("item"))
            if parsed:
                found_videos.append(parsed)
        elif row.get("type") == 4:
            found_users += users(row.get("user_list"), search_user)
    return found_videos, found_users


# ---- live ------------------------------------------------------------------------------

def _stream_links(stream_data):
    """streamData.pull_data.stream_data (a JSON string) -> {quality: {flv, hls}}."""
    raw = _dict(_dict(_dict(stream_data).get("pull_data")).get("stream_data"))
    if not raw:
        text = _dict(_dict(stream_data).get("pull_data")).get("stream_data")
        try:
            raw = _dict(json.loads(text)) if isinstance(text, str) and text else {}
        except ValueError:
            raw = {}
    out = []
    for quality, entry in _dict(raw.get("data")).items():
        main = _dict(_dict(entry).get("main"))
        flv, hls = first_link(main.get("flv")), first_link(main.get("hls"))
        if flv or hls:
            out.append({"quality": quality, "flv_link": flv, "hls_link": hls})
    return out


def live_room(data, room_info=None):
    """api-live/user/room `data` ({user, stats, liveRoom}) merged with the
    webcast room info (`room_info`, optional) -> one live room."""
    data, room_info = _dict(data), _dict(room_info)
    raw_user = _dict(data.get("user"))
    room = _dict(data.get("liveRoom"))
    owner = user_ref(raw_user)
    status_code = to_int(_pick(room, "status") or raw_user.get("status"))
    is_live = status_code == 2
    room_stats, stats = _dict(room.get("liveRoomStats")), _dict(room_info.get("stats"))
    room_id = to_id(raw_user.get("roomId")) or to_id(room_info.get("id_str"))
    hashtag_info = _dict(room_info.get("hashtag"))
    games = [clean(_dict(game).get("show_name")) for game in _list(room_info.get("game_tag"))]
    if owner is not None:
        owner["follower_count"] = to_int(_dict(data.get("stats")).get("followerCount"))
        owner["following_count"] = to_int(_dict(data.get("stats")).get("followingCount"))
    return {
        "room_id": room_id if room_id and room_id != "0" else None,
        "link": refs.live_link(owner["username"] if owner else None),
        "status": LIVE_STATUS.get(status_code, "offline"),
        "is_live": is_live,
        "title": clean(room.get("title")) or clean(room_info.get("title")),
        "started_at": iso_utc(room.get("startTime") or room_info.get("create_time")) if is_live else None,
        # offline, the room keeps the counters of the last broadcast: not a current audience
        "viewer_count": (to_int(room_stats.get("userCount")) if room_stats else to_int(room_info.get("user_count"))) if is_live else None,
        "total_viewer_count": to_int(room_stats.get("enterCount")) if room_stats else to_int(stats.get("total_user")),
        "like_count": to_int(room_info.get("like_count")) if is_live else None,
        "category": clean(hashtag_info.get("title")),
        "game": next((game for game in games if game), None),
        "is_subscribers_only": bool(to_int(room.get("liveSubOnly"))),
        "is_paid_event": bool(to_int(_dict(room.get("paidEvent")).get("paid_type"))),
        "is_age_restricted": to_bool(_dict(room_info.get("age_restricted")).get("restricted")),
        "has_shopping": to_bool(room_info.get("has_commerce_goods")),
        "cover": first_link(_pick(room, "coverUrl", "squareCoverImg")) or first_link(room_info.get("cover")),
        "streams": _stream_links(room.get("streamData")) if is_live else [],
        "owner": owner,
    }


def search_live_room(row):
    """One live search hit: live_info.raw_data is the webcast room as a JSON string."""
    info = _dict(_dict(row).get("live_info"))
    try:
        raw = _dict(json.loads(info.get("raw_data") or "{}"))
    except ValueError:
        return None
    room_id = to_id(raw.get("id_str") or raw.get("id"))
    if not room_id:
        return None
    owner = user_ref(raw.get("owner"))
    if owner is not None:
        owner["follower_count"] = to_int(_dict(_dict(raw.get("owner")).get("follow_info")).get("follower_count"))
    stream = _dict(raw.get("stream_url"))
    names = _dict(stream.get("resolution_name"))
    return {
        "room_id": room_id,
        "link": refs.live_link(owner["username"] if owner else None),
        "title": clean(raw.get("title")),
        "started_at": iso_utc(raw.get("start_time") or raw.get("create_time")),
        "viewer_count": to_int(raw.get("user_count")),
        "like_count": to_int(raw.get("like_count")),
        "category": clean(_dict(raw.get("hashtag")).get("title")),
        "game": next((clean(_dict(game).get("show_name")) for game in _list(raw.get("game_tag"))
                      if clean(_dict(game).get("show_name"))), None),
        "is_game": bool(to_int(raw.get("is_game"))),
        "has_shopping": to_bool(_dict(info.get("room_info")).get("has_commerce_goods")),
        "is_battle": to_bool(_dict(info.get("room_info")).get("is_battle")),
        "cover": first_link(raw.get("cover")),
        "streams": [{"quality": clean(names.get(key)) or key, "flv_link": url, "hls_link": None}
                    for key, url in _dict(stream.get("flv_pull_url")).items() if isinstance(url, str)],
        "hls_link": clean(stream.get("hls_pull_url")),
        "owner": owner,
    }


# ---- ads library -----------------------------------------------------------------------

AD_STATUS = {"1": "active", "2": "inactive"}


def _ad_videos(rows):
    out = []
    for raw in _list(rows):
        raw = _dict(raw)
        url = clean(raw.get("video_url"))
        if url or clean(raw.get("cover_img")):
            out.append({"video_link": url, "cover": clean(raw.get("cover_img"))})
    return out


def library_ad(raw):
    """One Commercial Content Library ad (search row or details.ad)."""
    raw = _dict(raw)
    ad_id = to_id(raw.get("id"))
    if not ad_id:
        return None
    return {
        "id": ad_id,
        "link": f"https://library.tiktok.com/ads/detail/?ad_id={ad_id}",
        "advertiser_name": clean(raw.get("name")),
        "caption": clean(raw.get("title")),
        "objective": clean(raw.get("advertising_objective")),
        "first_shown_date": iso_date_ms(raw.get("first_shown_date")),
        "last_shown_date": iso_date_ms(raw.get("last_shown_date")),
        "estimated_audience": clean(raw.get("estimated_audience")),
        "is_removed": raw.get("rejection_info") not in (None, {}, ""),
        "removal_reason": clean(_dict(raw.get("rejection_info")).get("reason")),
        "videos": _ad_videos(raw.get("videos")),
        "images": [url for url in _list(raw.get("image_urls")) if isinstance(url, str) and url],
    }


def library_ad_details(data):
    data = _dict(data)
    out = library_ad(data.get("ad"))
    if out is None:
        return None
    advertiser = _dict(data.get("advertiser"))
    tt_user = _dict(advertiser.get("tt_user"))
    out["advertiser"] = {
        "id": clean(advertiser.get("adv_biz_ids")),
        "name": clean(advertiser.get("name")),
        "paid_for_by": clean(advertiser.get("sponsor")),
        "registry_location": clean(advertiser.get("registry_location")),
        "tiktok_account": user_ref(tt_user) if tt_user else None,
    }
    targeting = _dict(data.get("targeting"))
    regions = _dict(targeting.get("location"))

    def enabled(rows):
        """[{region, <option>: bool, ...}] -> {region: [options switched on]}."""
        return [{"country": clean(_dict(row).get("region")),
                 "values": [key for key, value in _dict(row).items() if key != "region" and value is True]}
                for row in _list(rows)]

    def yes_no(value):
        text = (clean(value) or "").lower()
        return True if text == "yes" else False if text == "no" else None

    def strings(value):
        return [text for text in (clean(v) for v in _list(value)) if text]

    out["targeting"] = {
        "audience_size": clean(targeting.get("target_audience_size")),
        "countries": strings(targeting.get("countries")),
        "provinces": strings(targeting.get("provinces")),
        "cities": strings(targeting.get("cities")),
        "languages": strings(targeting.get("languages")),
        "operating_systems": strings(targeting.get("operating_systems")),
        "device_models": strings(targeting.get("device_models")),
        "ages": enabled(targeting.get("age")),
        "genders": enabled(targeting.get("gender")),
        "interest": clean(targeting.get("interest")),
        "video_interactions": clean(targeting.get("video_interactions")),
        "creator_interactions": clean(targeting.get("creator_interactions")),
        "uses_custom_audience": yes_no(targeting.get("audience")),
        "excludes_audience": yes_no(targeting.get("audience_exclude")),
        "targets_high_spending_power": yes_no(targeting.get("high_spending_power")),
    }
    out["reach"] = {
        "country_count": to_int(regions.get("total_region")),
        "total_impressions": clean(regions.get("total_impressions")),
        "countries": [{
            "country": clean(_dict(region).get("region")),
            "impressions": clean(_dict(region).get("impressions")),
            "breakdowns": [{"age": clean(_dict(b).get("age")), "gender": (clean(_dict(b).get("gender")) or "").lower() or None,
                            "impressions": clean(_dict(b).get("impressions"))}
                           for b in _list(_dict(region).get("breakdowns"))],
        } for region in _list(regions.get("data"))],
    }
    return out


# ---- creative center top ads -----------------------------------------------------------

def _label(key, prefix):
    """campaign_objective_conversion -> conversion (the site's i18n key tail)."""
    text = clean(key)
    if not text:
        return None
    return text[len(prefix):] if text.startswith(prefix) else text


def top_ad(raw):
    raw = _dict(raw)
    ad_id = to_id(raw.get("id"))
    if not ad_id:
        return None
    info = _dict(raw.get("video_info"))
    renditions = _dict(info.get("video_url"))
    out = {
        "id": ad_id,
        "link": f"https://ads.tiktok.com/business/creativecenter/topads/{ad_id}/pc/en",
        "caption": clean(raw.get("ad_title")),
        "brand_name": clean(raw.get("brand_name")),
        "objective": _label(raw.get("objective_key"), "campaign_objective_"),
        "industry_key": clean(raw.get("industry_key")),
        "ctr": to_float(raw.get("ctr")),
        "cost": to_int(raw.get("cost")),
        "like_count": to_int(raw.get("like")),
        "video": {
            "id": clean(info.get("vid")),
            "duration_seconds": to_float(info.get("duration")),
            "width": to_int(info.get("width")),
            "height": to_int(info.get("height")),
            "cover": clean(info.get("cover")),
            "play_links": [{"quality": quality, "link": url} for quality, url in sorted(
                renditions.items(), key=lambda kv: -(to_int(str(kv[0]).rstrip("p")) or 0)) if isinstance(url, str)],
        } if info else None,
    }
    if "comment" in raw or "landing_page" in raw:      # the detail payload
        out.update({
            "comment_count": to_int(raw.get("comment")),
            "share_count": to_int(raw.get("share")),
            "countries": [code for code in _list(raw.get("country_code")) if isinstance(code, str)],
            "landing_page": clean(raw.get("landing_page")),
            "objectives": [_label(_dict(o).get("label"), "campaign_objective_") for o in _list(raw.get("objectives"))],
            "keywords": [word for word in (clean(k) for k in _list(raw.get("keyword_list"))) if word],
            "source": clean(raw.get("source")),
        })
    return out
