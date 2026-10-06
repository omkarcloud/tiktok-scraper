"""Offline tests for the TikTok refs, schemas and parsers — no network.

Every fixture in tiktok/fixtures/ is a real upstream payload captured on
2026-10-05 through tiktok/fetch.py (lists trimmed to a few rows, tracking
blocks and third-party tokens blanked). The assertions pin the field
mapping decoded from live data, so a silent upstream rename shows up here
rather than as nulls in a customer's response.

    python -m pytest tiktok/test_parsers.py -q
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from tiktok import ads, discovery, parsers as P, refs, schemas, search, shared, videos  # noqa: E402
from tiktok import fetch, signer  # noqa: E402
from schema_fields import load_query  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SEC_UID = "MS4wLjABAAAAv7iSuuXDJGDvJkmH_vz1qkDZYo1apxgzaxdBSeIuPiM"
VIDEO_ID = "7692114317151423775"


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


# ---- refs --------------------------------------------------------------------------------

@pytest.mark.parametrize("value", [
    "nasa", "@nasa", "@NASA", " Nasa ", "https://www.tiktok.com/@nasa", "tiktok.com/@nasa?lang=en",
    "https://www.tiktok.com/@nasa/video/7692114317151423775", "https://m.tiktok.com/@nasa/",
])
def test_user_ref_username_forms(value):
    assert refs.resolve_user(value) == {"username": "nasa", "sec_uid": None}


def test_user_ref_sec_uid_and_digit_username():
    assert refs.resolve_user(SEC_UID) == {"username": None, "sec_uid": SEC_UID}
    assert refs.resolve_user("107955") == {"username": "107955", "sec_uid": None}
    assert refs.resolve_user("tiktok.community") == {"username": "tiktok.community", "sec_uid": None}


@pytest.mark.parametrize("value", ["", "not a user!", "https://instagram.com/nasa", "https://www.tiktok.com/tag/nasa",
                                   "a" * 25, "ends.with.dot."])
def test_user_ref_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_user(value)


@pytest.mark.parametrize("value", [
    VIDEO_ID,
    f"https://www.tiktok.com/@tiktok/video/{VIDEO_ID}",
    f"https://www.tiktok.com/@tiktok/video/{VIDEO_ID}?is_from_webapp=1&sender_device=pc",
    f"https://www.tiktok.com/@espn/photo/{VIDEO_ID}",
    f"https://m.tiktok.com/v/{VIDEO_ID}.html",
    f"www.tiktok.com/@tiktok/video/{VIDEO_ID}/",
])
def test_video_ref_id_forms(value):
    assert refs.resolve_video(value) == {"id": VIDEO_ID, "short_link": None}


def test_video_ref_share_links():
    assert refs.resolve_video("https://vm.tiktok.com/ZMekDdGJ7/") == {"id": None, "short_link": "https://vm.tiktok.com/ZMekDdGJ7/"}
    assert refs.resolve_video("vt.tiktok.com/ZSabc123") == {"id": None, "short_link": "https://vt.tiktok.com/ZSabc123/"}
    assert refs.resolve_video("https://www.tiktok.com/t/ZTjabc123/") == {"id": None, "short_link": "https://www.tiktok.com/t/ZTjabc123/"}
    assert refs.video_id_from_link(f"https://www.tiktok.com/@tiktok/video/{VIDEO_ID}?_r=1") == VIDEO_ID
    assert refs.video_id_from_link("https://www.tiktok.com/?_r=1") is None


@pytest.mark.parametrize("value", ["", "12345", "nasa", "https://www.tiktok.com/@nasa", "https://youtube.com/watch?v=1"])
def test_video_ref_rejects(value):
    with pytest.raises(ValueError):
        refs.resolve_video(value)


def test_hashtag_and_id_refs():
    assert refs.resolve_hashtag("#nasa") == "nasa"
    assert refs.resolve_hashtag("https://www.tiktok.com/tag/nasa?lang=en") == "nasa"
    with pytest.raises(ValueError):
        refs.resolve_hashtag("two words")
    assert refs.resolve_music("https://www.tiktok.com/music/snowfall-Slowed-Reverb-7077435666233051138") == "7077435666233051138"
    assert refs.resolve_music("7077435666233051138") == "7077435666233051138"
    assert refs.resolve_playlist("https://www.tiktok.com/@tiktok/playlist/Songs-Of-The-Summer-2026-7681171537575824159") == "7681171537575824159"
    assert refs.resolve_collection("https://www.tiktok.com/@tiktok/collection/Summer-of-Sports-7394627756635573022") == "7394627756635573022"
    assert refs.resolve_place("https://www.tiktok.com/place/Los-Angeles-California-Temple-20442395500433212") == "20442395500433212"
    assert refs.resolve_effect("https://www.tiktok.com/sticker/Makeup-Lush-3390122645") == "3390122645"
    for bad in ("", "snowfall", "https://www.tiktok.com/@tiktok"):
        with pytest.raises(ValueError):
            refs.resolve_music(bad)


def test_links():
    assert refs.video_link("tiktok", VIDEO_ID) == f"https://www.tiktok.com/@tiktok/video/{VIDEO_ID}"
    assert refs.video_link("espn", "1", is_photo=True) == "https://www.tiktok.com/@espn/photo/1"
    assert refs.music_link("snowfall (Slowed + Reverb)", "7") == "https://www.tiktok.com/music/snowfall-Slowed-Reverb-7"
    assert refs.music_link(None, "7") == "https://www.tiktok.com/music/original-sound-7"
    assert refs.hashtag_link("fypシ") == "https://www.tiktok.com/tag/fyp%E3%82%B7"


# ---- schemas -----------------------------------------------------------------------------

def test_schema_defaults_and_resolution():
    data, error = load_query(schemas.UserPostsSchema, {"user": "https://www.tiktok.com/@NASA", "country": "de"})
    assert error is None
    assert data == {"user": {"username": "nasa", "sec_uid": None}, "cursor": None, "country": "de", "sort": "latest"}
    data, error = load_query(schemas.TopAdsSchema, {"period": "7", "sort": "likes"})
    assert error is None and data["period"] == 7 and data["country"] == "US"
    data, error = load_query(schemas.ExploreSchema, {})
    assert error is None and data == {"category": "all", "country": None}


@pytest.mark.parametrize("schema,query", [
    (schemas.UserSchema, {}),
    (schemas.UserSchema, {"user": "nasa", "id": "1"}),                       # unknown params are rejected
    (schemas.UserPostsSchema, {"user": "nasa", "sort": "random"}),
    (schemas.UserPageSchema, {"user": "nasa", "cursor": "abc"}),
    (schemas.VideoSchema, {"video": "nasa"}),
    (schemas.VideoSchema, {"video": VIDEO_ID, "country": "ZZ"}),
    (schemas.CommentRepliesSchema, {"video": VIDEO_ID}),
    (schemas.CommentRepliesSchema, {"video": VIDEO_ID, "comment_id": "x"}),
    (schemas.SearchSchema, {"query": ""}),
    (schemas.SearchSchema, {"query": "x", "cursor": "20.short"}),
    (schemas.VideoSearchSchema, {"query": "x", "published": "year"}),
    (schemas.ExploreSchema, {"category": "cooking"}),
    (schemas.AdSchema, {"ad": "abc"}),
    (schemas.AdsSearchSchema, {"query": "x", "start_date": "2026/01/01"}),
    (schemas.TopAdsSchema, {"period": "14"}),
    (schemas.TopAdsSchema, {"objective": "sales"}),
])
def test_schema_rejects(schema, query):
    data, error = load_query(schema, query)
    assert data is None and error["error"].startswith("Invalid parameters")


def test_cursor_shapes_accepted():
    assert load_query(schemas.SearchSchema, {"query": "x", "cursor": "20.20261005135356D987AA8C89367BE6C0E1"})[1] is None
    cursor = "1.eyJsYXN0X3NvcnQiOlsxNi4yMTM1MTgsMTc4OTY4OTYwMDAwMF0sIm5leHRfY3Vyc29yIjoxMn0="
    assert load_query(schemas.AdsSearchSchema, {"query": "x", "cursor": cursor})[0]["cursor"] == cursor
    assert load_query(schemas.UserPageSchema, {"user": "nasa", "cursor": "1784326203949"})[1] is None


# ---- transport helpers -------------------------------------------------------------------

def test_signer_appends_the_four_params_in_order():
    query, params = signer.sign([("aid", "1988"), ("keyword", "a b")], fetch.USER_AGENT, ms_token="")
    assert query.startswith("aid=1988&keyword=a%20b&X-Dynosaur=")
    assert list(params) == ["X-Dynosaur", "msToken", "X-Bogus", "X-Gnarly"]
    assert "&msToken=&X-Bogus=1&X-Gnarly=" in query


def test_status_and_country_order(monkeypatch):
    assert fetch.status_of({"statusCode": 10221}) == 10221
    assert fetch.status_of({"status_code": 0, "statusCode": 0}) == 0
    assert fetch.status_of({"code": 40004}) == 40004
    assert fetch.status_of({"items": []}) == 0
    monkeypatch.setattr(fetch.config, "TIKTOK_DEFAULT_COUNTRY", "us")
    assert fetch.country_order(None, "de") == ("us", "de")
    assert fetch.country_order("DE", "de", "us") == ("de", "us")


def test_universal_data():
    html = '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">{"__DEFAULT_SCOPE__":{"webapp.app-context":{"wid":"7"}}}</script>'
    assert fetch.universal_data(html) == {"webapp.app-context": {"wid": "7"}}
    assert fetch.universal_data("<html></html>") is None
    assert fetch.universal_data('<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">not json</script>') is None


def test_creative_center_sign_is_a_16_hex_fold():
    sign = fetch._creative_center_sign("6f1c2c4e-0000-4000-8000-000000000000", 1791196906)
    assert len(sign) == 16 and all(ch in "0123456789abcdef" for ch in sign)
    assert sign == fetch._creative_center_sign("6f1c2c4e-0000-4000-8000-000000000000", 1791196906)


# ---- users -------------------------------------------------------------------------------

def test_profile():
    profile = P.profile(load("user_detail.json")["userInfo"])
    assert profile["id"] == "6614519312189947909"
    assert profile["username"] == "mrbeast" and profile["nickname"] == "MrBeast"
    assert profile["link"] == "https://www.tiktok.com/@mrbeast"
    assert profile["sec_uid"].startswith("MS4wLjABAAAA")
    assert profile["is_verified"] is True and profile["is_private"] is False
    assert profile["bio_link"] == "http://themostdangerousgames.com"
    assert profile["profile_picture"].startswith("https://")
    assert profile["is_live"] is False and profile["live_room_id"] is None
    assert profile["nickname_changed_at"] == "2022-04-29T19:56:02Z"
    stats = profile["stats"]
    assert stats["follower_count"] == 142928477           # the exact statsV2 value, not the rounded 142900000
    assert stats["following_count"] == 355 and stats["video_count"] == 477
    assert stats["like_count"] == 1510358266
    assert profile["tabs"]["has_playlists"] is True


def test_profile_missing_and_partial():
    assert P.profile(load("user_detail_missing.json").get("userInfo")) is None
    assert P.profile(None) is None
    assert P.profile({"user": {"uniqueId": "x"}})["stats"]["follower_count"] is None
    assert load("user_detail_missing.json")["statusCode"] in shared.USER_NOT_FOUND


def test_followers():
    users = P.users(load("followers.json")["userList"], P.user_with_stats)
    assert len(users) == 2
    first = users[0]
    assert first["username"] and first["link"] == f"https://www.tiktok.com/@{first['username']}"
    assert isinstance(first["stats"]["follower_count"], int)
    assert first["is_private"] in (True, False)


def test_search_user_dialect():
    users = P.users(load("search_user.json")["user_list"], P.search_user)
    nasa = users[0]
    assert nasa["username"] == "nasa" and nasa["id"] == "7664638705177150477"
    assert nasa["is_verified"] is True and nasa["verification_reason"] == "institution account"
    assert nasa["follower_count"] >= 1_000_000 and nasa["like_count"] > 0
    assert nasa["is_live"] is False and nasa["live_room_id"] is None
    assert nasa["profile_picture"].startswith("https://")


# ---- videos ------------------------------------------------------------------------------

def test_video_details():
    video = P.video(load("item_detail.json")["itemInfo"]["itemStruct"])
    assert video["id"] == VIDEO_ID
    assert video["link"] == f"https://www.tiktok.com/@tiktok/video/{VIDEO_ID}"
    assert video["type"] == "video" and video["images"] == []
    assert video["created_at"] == "2026-10-02T16:52:37Z"
    assert video["language"] == "en" and video["is_ad"] is False
    assert video["is_duet_enabled"] is True and video["is_share_enabled"] is True
    assert video["stats"]["play_count"] > 250_000 and video["stats"]["repost_count"] == 0
    assert set(video["stats"]) == {"play_count", "like_count", "comment_count", "share_count", "save_count", "repost_count"}
    assert video["author"]["username"] == "tiktok" and video["author"]["sec_uid"] == SEC_UID
    assert video["author_stats"]["video_count"] == 1509
    assert video["mentions"] == [{"id": "6805952240777085958", "sec_uid": video["mentions"][0]["sec_uid"],
                                  "username": "rachelszero", "link": "https://www.tiktok.com/@rachelszero"}]
    assert "dance" in video["suggested_searches"]
    assert video["music"]["id"] == "7692114426937346847" and video["music"]["is_original_sound"] is True
    assert video["music"]["link"] == "https://www.tiktok.com/music/original-sound-7692114426937346847"


def test_video_file_and_qualities():
    file = P.video(load("item_detail.json")["itemInfo"]["itemStruct"])["video"]
    assert file["duration_seconds"] == 65 and (file["width"], file["height"]) == (720, 1280)
    assert file["codec"] == "h264" and file["format"] == "mp4" and file["size_bytes"] == 15062406
    assert file["play_link"].startswith(P.COOKIELESS_PLAY_PREFIX)      # the cookieless form is listed first
    assert file["download_link"].startswith("https://") and file["cover"].startswith("https://")
    qualities = file["qualities"]
    assert len(qualities) == 4
    assert [q["quality"] for q in qualities][0] == "1080p"             # best first
    assert {q["codec"] for q in qualities} == {"h264", "h265_hvc1"}
    for quality in qualities:
        assert quality["play_links"][0] == quality["play_link"]
        assert quality["bitrate"] > 0 and quality["size_bytes"] > 0
    subtitle = file["subtitles"][0]
    assert subtitle["language"] == "eng-US" and subtitle["format"] == "webvtt"
    assert subtitle["is_auto_generated"] is True and subtitle["is_translation"] is False
    assert subtitle["link"].startswith("https://") and subtitle["expires_at"].endswith("Z")


def test_photo_post():
    item = load("item_detail_photo.json")["itemInfo"]["itemStruct"]
    video = P.video(item)
    assert video["type"] == "photo" and video["video"] is None
    assert video["link"] == "https://www.tiktok.com/@espn/photo/7692968080456092958"
    assert len(video["images"]) == 5
    assert video["images"][0]["width"] == 1600 and video["images"][0]["height"] == 2000
    assert video["images"][0]["link"] == video["images"][0]["links"][0]
    assert video["cover"].startswith("https://")
    assert [tag["name"] for tag in video["hashtags"]][:1] == ["nflfootball"]
    assert video["hashtags"][0]["id"] == "3397183"
    music = video["music"]
    assert music["title"] == "snowfall (Slowed + Reverb)" and music["is_original_sound"] is False
    assert {link["platform"] for link in music["streaming_links"]} == {"apple_music", "spotify"}
    media = P.media(item)
    assert set(media) == {"id", "link", "type", "description", "author", "cover", "video", "images", "music"}


def test_video_lists_and_rich_fields():
    page = shared.video_page(load("items_rich.json"), user=None)
    assert page["video_count"] == 4 and page["next_cursor"] == "30" and page["has_more"] is True
    with_place, with_anchor, with_effect, with_words = page["videos"]
    place = with_place["location"]
    assert place["id"] and place["name"] and place["link"].startswith("https://www.tiktok.com/place/")
    assert place["address"] and isinstance(place["category_path"], list)
    assert with_anchor["anchors"][0]["title"] and isinstance(with_anchor["anchors"][0]["type"], int)
    assert with_effect["effects"][0]["id"] and with_effect["effects"][0]["link"].startswith("https://www.tiktok.com/sticker/")
    assert with_effect["text_stickers"]
    assert with_words["suggested_searches"]
    posts = shared.video_page(load("posts.json"), user=None)
    assert posts["video_count"] == 2 and posts["videos"][1]["playlist_id"]
    assert posts["next_cursor"] == "1784326203949"


def test_video_is_robust_to_partial_rows():
    assert P.video(None) is None and P.video({}) is None and P.video({"desc": "no id"}) is None
    bare = P.video({"id": 1})
    assert bare["id"] == "1" and bare["author"] is None and bare["video"] is None and bare["music"] is None
    assert bare["stats"]["play_count"] is None and bare["hashtags"] == [] and bare["location"] is None
    assert P.videos([None, "x", {"id": "2", "author": "legacy-string", "video": [], "challenges": None}])[0]["id"] == "2"
    assert shared.video_page({"itemList": None, "hasMore": False})["videos"] == []


# ---- comments ----------------------------------------------------------------------------

def test_comments():
    payload = load("comments.json")
    comments = P.comments(payload["comments"], "tiktok")
    assert len(comments) == len(payload["comments"])
    first = comments[0]
    assert first["video_id"] == VIDEO_ID and first["id"]
    assert first["link"] == f"https://www.tiktok.com/@tiktok/video/{VIDEO_ID}?comment_id={first['id']}"
    assert first["created_at"].endswith("Z") and isinstance(first["like_count"], int)
    assert first["parent_comment_id"] is None and first["replied_to_comment_id"] is None
    assert first["user"]["username"] and first["user"]["is_verified"] is False
    assert any(comment["reply_count"] for comment in comments)
    assert shared.next_cursor(payload) == "50"
    with_image = [comment for comment in comments if comment["images"]]
    if with_image:
        assert with_image[0]["images"][0]["link"].startswith("https://")


def test_comment_replies_and_missing():
    reply = P.comments(load("comment_replies.json")["comments"])[0]
    assert reply["parent_comment_id"] and reply["parent_comment_id"] != "0"
    assert reply["text"]
    missing = load("comments_missing.json")
    assert missing.get("comments") is None and missing.get("total") is None
    assert P.comments(missing.get("comments")) == []


def test_webvtt():
    with open(os.path.join(FIXTURES, "subtitle.vtt"), encoding="utf-8") as handle:
        segments = videos.parse_webvtt(handle.read())
    assert segments[0] == {"start_seconds": 0.3, "end_seconds": 4.38,
                           "text": "girl you look like you must be a K pop fan wow how'd you know"}
    assert all(segment["end_seconds"] > segment["start_seconds"] for segment in segments)
    assert videos.parse_webvtt("WEBVTT\n\n01:00:01.000 --> 01:00:02.500\n<c>hi</c>\nthere\n")[0] == {
        "start_seconds": 3601.0, "end_seconds": 3602.5, "text": "hi there"}
    assert videos.parse_webvtt("") == []


def test_caption_language_matching():
    tracks = [{"language": "eng-US", "is_translation": False}, {"language": "spa-ES", "is_translation": True},
              {"language": "cmn-Hans-CN", "is_translation": True}]
    assert videos._pick_subtitle(tracks, None)["language"] == "eng-US"
    assert videos._pick_subtitle(tracks, "en")["language"] == "eng-US"
    assert videos._pick_subtitle(tracks, "es-ES")["language"] == "spa-ES"
    assert videos._pick_subtitle(tracks, "zh")["language"] == "cmn-Hans-CN"
    assert videos._pick_subtitle(tracks, "spa-es")["language"] == "spa-ES"
    assert videos._pick_subtitle(tracks, "fr") is None and videos._pick_subtitle(tracks, "es-MX") is None


# ---- search ------------------------------------------------------------------------------

def test_search_top_mixes_users_and_videos():
    found_videos, found_users = P.top_results(load("search_general.json")["data"])
    assert len(found_videos) == 2 and found_users[0]["username"] == "nasa"
    assert found_videos[0]["author"]["username"] and found_videos[0]["video"]["play_link"]


def test_search_cursor_round_trip():
    payload = load("search_item.json")
    payload["extra"] = {"logid": "20261005135356D987AA8C89367BE6C0E1"}
    cursor = search._next_cursor(payload, "")
    assert cursor == "20.20261005135356D987AA8C89367BE6C0E1"
    assert search._split_cursor(cursor) == (20, "20261005135356D987AA8C89367BE6C0E1")
    assert search._split_cursor(None) == (0, "") and search._split_cursor("40") == (40, "")
    assert search._next_cursor({"has_more": 0, "cursor": 20}, "x") is None
    assert len(P.videos(payload["item_list"])) == 2
    # the id later pages echo: log_pb.impr_id (video / top / live), rid (users), or the one already in hand
    assert search._next_cursor({"has_more": 1, "cursor": 12, "log_pb": {"impr_id": "IMPR"}}, "") == "12.IMPR"
    assert search._next_cursor(load("search_user.json"), "") == "10.20261005133316AC6B4AB57B9D191696F5"
    assert search._next_cursor({"has_more": 1, "cursor": 40}, "KEEP") == "40.KEEP"
    assert search._next_cursor({"has_more": 1, "cursor": 40}, "") == "40"


def test_idle_pool_evicts_least_recently_used(monkeypatch):
    class Client:
        def __init__(self, name):
            self.country, self.name, self.closed = "zz", name, False
            self.born, self.spent = fetch.time.time(), {}

        def close(self):
            self.closed = True

    monkeypatch.setattr(fetch.config, "TIKTOK_IDLE_SESSIONS_PER_COUNTRY", 2)
    monkeypatch.setattr(fetch, "_idle", {})
    a, b, c = Client("a"), Client("b"), Client("c")
    for client in (a, b):
        fetch._release(client)
    a.spent["posts"] = 5                                   # a has spent its posts budget
    b.spent["posts"] = 5
    fetch._release(c)                                      # pool full: the oldest (a) goes, c stays
    assert a.closed and not b.closed and not c.closed
    assert [cl.name for cl in fetch._idle["zz"]] == ["b", "c"]
    assert fetch._acquire("zz", ("posts", 5)) is c        # the only one with budget left
    assert fetch._acquire("zz") is b                       # exhausted sessions still serve other endpoints


def test_search_live_and_suggestions():
    room = P.search_live_room(load("search_live.json")["data"][0])
    assert room["room_id"] and room["title"] and room["link"].endswith("/live")
    assert isinstance(room["viewer_count"], int) and room["started_at"].endswith("Z")
    assert room["owner"]["username"] and room["streams"][0]["flv_link"].startswith("https://")
    assert P.search_live_room({"live_info": {"raw_data": "not json"}}) is None
    suggestions = P.suggestions(load("search_preview.json")["sug_list"])
    assert suggestions and all(isinstance(text, str) for text in suggestions)
    assert len(suggestions) == len(set(suggestions))


# ---- hashtags / music / playlists / places / effects --------------------------------------

def test_hashtag():
    hashtag = P.hashtag(load("challenge_detail.json")["challengeInfo"])
    assert hashtag["id"] == "3301" and hashtag["name"] == "nasa"
    assert hashtag["link"] == "https://www.tiktok.com/tag/nasa"
    assert hashtag["video_count"] > 1_000_000 and hashtag["view_count"] > 50_000_000_000
    assert hashtag["is_commercial"] is False and hashtag["announcement"] is None
    assert P.hashtag({}) is None


def test_music():
    info = load("music_detail.json")["musicInfo"]
    music = P.music(info["music"], info["stats"], info.get("author") or {})
    assert music["id"] == "7077435666233051138" and music["duration_seconds"] == 60
    assert music["album"] == "snowfall (Slowed + Reverb)" and music["video_count"] > 100_000
    assert music["play_link"].startswith("https://") and music["cover"].startswith("https://")
    assert {"platform": "spotify", "song_id": "4VkEkljlOC5cMbRMhREO5E",
            "link": "https://open.spotify.com/track/4VkEkljlOC5cMbRMhREO5E"} in music["streaming_links"]
    assert "author" in music and P.music({}) is None


def test_playlists_and_collections():
    playlist = P.playlist(load("playlists.json")["playList"][0])
    assert playlist["id"] == "7681171537575824159" and playlist["name"] == "Songs Of The Summer 2026"
    assert playlist["video_count"] == 3 and playlist["creator"]["username"] == "tiktok"
    assert playlist["link"] == "https://www.tiktok.com/@tiktok/playlist/Songs-Of-The-Summer-2026-7681171537575824159"
    assert P.playlist(load("mix_detail.json")["mixInfo"])["id"] == playlist["id"]
    assert P.playlist(None) is None
    collection = P.collection(load("collections.json")["collectionList"][0])
    assert collection == {
        "id": "7394627756635573022", "name": "Summer of Sports",
        "link": "https://www.tiktok.com/@tiktok/collection/Summer-of-Sports-7394627756635573022",
        "video_count": 139, "cover": collection["cover"],
        "owner": {"id": "107955", "username": "tiktok", "link": "https://www.tiktok.com/@tiktok"},
    }


def test_place_and_effect():
    place = P.place(load("poi_detail.json")["poiInfo"])
    assert place["id"] == "20442395500433212" and place["name"] == "Los Angeles California Temple"
    assert place["address"].startswith("10777 Santa Monica Blvd") and place["category"] == "Church"
    assert place["parent"] == {"id": "22535796484723736", "name": "East Los Angeles"}
    assert place["video_count"] > 1_000_000 and place["pictures"] and place["is_claimed"] is False
    effect = P.effect(load("sticker_detail.json")["stickerInfo"])
    assert effect["id"] == "3390122645" and effect["name"] == "Makeup Lush"
    assert effect["icon"].startswith("https://") and effect["author"]["username"]
    assert P.place({}) is None and P.effect({}) is None


def test_explore_categories():
    listing = discovery.get_explore_categories()
    assert listing["category_count"] == 21 and listing["categories"][0] == {"id": "all", "name": "All"}
    assert set(discovery.EXPLORE_CATEGORIES) == set(discovery.EXPLORE_NAMES)
    assert len(set(discovery.EXPLORE_CATEGORIES.values())) == 21


# ---- live --------------------------------------------------------------------------------

def test_live_room():
    data = load("live_user_room.json")["data"]
    room = P.live_room(data, load("webcast_room.json")["data"])
    assert room["is_live"] is True and room["status"] == "live"
    assert room["room_id"] == "7692023419818265357" and room["title"] == "BEST FEMALE FORTNITE PLAYER"
    assert room["started_at"] == "2026-10-02T11:02:53Z"
    assert room["viewer_count"] > 0 and room["total_viewer_count"] > room["viewer_count"]
    assert room["category"] == "Gaming" and room["game"] == "Fortnite"
    assert room["streams"][0]["flv_link"].startswith("https://")
    assert room["owner"]["username"] == "mrlustfn" and room["owner"]["follower_count"] > 1_000_000
    assert room["link"] == "https://www.tiktok.com/@mrlustfn/live"


def test_live_room_offline_hides_stale_audience():
    data = load("live_user_room.json")["data"]
    data["liveRoom"]["status"] = 4
    data["user"]["status"] = 4
    room = P.live_room(data)
    assert room["is_live"] is False and room["status"] == "offline"
    assert room["viewer_count"] is None and room["started_at"] is None and room["streams"] == []
    assert P.live_room({})["is_live"] is False


# ---- ads ---------------------------------------------------------------------------------

def test_library_ads():
    rows = [P.library_ad(row) for row in load("ads_library_search.json")["data"]]
    ad = rows[0]
    assert ad["id"] == "1878154340615249" and ad["advertiser_name"] == "sportschnapper.at"
    assert ad["first_shown_date"] == "2026-10-04" and ad["last_shown_date"] == "2026-10-04"
    assert ad["estimated_audience"] == "0-1K" and ad["is_removed"] is False
    assert ad["videos"][0]["video_link"].startswith("https://library.tiktok.com/")
    assert ad["link"] == "https://library.tiktok.com/ads/detail/?ad_id=1878154340615249"


def test_library_ad_details():
    ad = P.library_ad_details(load("ads_library_details.json")["data"])
    assert ad["objective"] == "Community interaction"
    assert ad["advertiser"] == {"id": "7672216207558410241", "name": "Sportschnapper", "paid_for_by": "Sportschnapper",
                                "registry_location": "Austria", "tiktok_account": None}
    targeting = ad["targeting"]
    assert targeting["countries"] == ["HU", "AT", "DE"] and targeting["audience_size"] == "29.3M-35.8M"
    assert targeting["ages"][0] == {"country": "HU", "values": ["13-17", "18-24", "25-34", "35-44", "45-54", "55+"]}
    assert targeting["genders"][0]["values"] == ["female", "male", "unknown"]
    assert targeting["uses_custom_audience"] is False and targeting["operating_systems"] == ["ALL"]
    reach = ad["reach"]
    assert reach["country_count"] == 3 and reach["countries"][0]["country"] == "HU"
    assert reach["countries"][0]["breakdowns"][0] == {"age": "13-17", "gender": "male", "impressions": "0-1K"}
    assert P.library_ad_details({}) is None


def test_ads_library_reference():
    assert {"code": "DE", "name": "Germany"} in load("ads_library_regions.json")["regions"]
    names = load("ads_library_suggestion.json")["data"]["adv_names"]
    assert {"name": "NIKE Retail B.V.", "ids": "6876453864464188162"} in names
    assert ads._epoch("2026-10-05") == 1791158400 and ads._epoch("2026-10-05", end=True) == 1791244799


def test_top_ads():
    ads_list = [P.top_ad(row) for row in load("top_ads.json")["data"]["materials"]]
    ad = ads_list[0]
    assert ad["id"] == "7686346996722745360" and ad["objective"] == "conversion"
    assert ad["like_count"] == 71 and ad["ctr"] == 0.81
    assert ad["video"]["duration_seconds"] == 18.8 and ad["video"]["play_links"][0]["quality"] == "1080p"
    assert "landing_page" not in ad
    detail = P.top_ad(load("top_ad_details.json")["data"])
    assert detail["landing_page"].startswith("https://www.emiriah.com")
    assert detail["countries"] == ["AE", "MX", "US", "IT"] and detail["objectives"] == ["conversion", "traffic"]
    assert detail["comment_count"] == 0 and detail["source"] == "Others"
    assert P.top_ad({}) is None
