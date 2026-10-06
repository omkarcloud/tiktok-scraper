"""The 41 TikTok endpoints. Every path is served with and without the
`/tiktok` prefix, so code generated against the hosted API on RapidAPI
(paths like /videos/details) runs unchanged against this server.

Params are validated by the same marshmallow schemas the hosted API uses
(tiktok/schemas.py): `user`, `video`, `hashtag`, `music`, `playlist`,
`collection`, `place` and `effect` each accept a bare value or a pasted
tiktok.com link."""
import json

from bottle import request, response, route

from schema_fields import load_query
from scraper_errors import BadRequest, Blocked, NotFound, UpstreamError
from tiktok import ads, discovery, live, schemas, search, users, videos


def json_response(data, status=200):
    response.status = status
    response.content_type = "application/json"
    return json.dumps(data, ensure_ascii=False)


def query_dict():
    """The query as unicode strings (bottle 0.12's .get() hands back latin-1
    decoded bytes, so a UTF-8 "Amélie" would arrive as "AmÃ©lie")."""
    return {key: request.query.getunicode(key) for key in request.query.keys()}


def call(label, schema, fn):
    """Validate, run, map errors: bad params -> 400, missing entity -> 404,
    transport/blocks -> 500."""
    data, error = load_query(schema, query_dict())
    if error:
        return json_response(error, 400)
    try:
        return json_response(fn(**data))
    except ValueError as e:                # bad value
        return json_response({"error": str(e)}, 400)
    except BadRequest as e:                # upstream rejected the request (e.g. a bad cursor)
        return json_response({"error": f"tiktok rejected the request: {e}"}, 400)
    except NotFound as e:
        return json_response({"error": str(e) or "not found"}, 404)
    except Blocked as e:                   # silent empty body, 403 / 429
        return json_response({"error": f"tiktok blocked the request, retry later: {e}"}, 502)
    except UpstreamError as e:             # retries exhausted
        return json_response({"error": f"tiktok {label} failed: {e}"}, 502)
    except Exception as e:                 # parser surprises
        return json_response({"error": f"tiktok {label} failed: {type(e).__name__}: {e}"}, 500)


def mount(path, schema, fn):
    """Serve an endpoint function at /path and /tiktok/path."""
    label = path.strip("/")

    def handler():
        return call(label, schema, fn)

    handler.__name__ = "tiktok_" + label.replace("/", "_").replace("-", "_")
    route(path, method="GET")(handler)
    route("/tiktok" + path, method="GET")(handler)


ENDPOINTS = [
    # videos
    ("/videos/details", schemas.VideoSchema, videos.get_details),
    ("/videos/media", schemas.VideoSchema, videos.get_media),
    ("/videos/comments", schemas.VideoPageSchema, videos.get_comments),
    ("/videos/comment-replies", schemas.CommentRepliesSchema, videos.get_comment_replies),
    ("/videos/transcript", schemas.TranscriptSchema, videos.get_transcript),
    ("/videos/related", schemas.VideoSchema, videos.get_related),
    ("/videos/resolve", schemas.VideoSchema, videos.resolve),
    # users
    ("/users/profile", schemas.UserSchema, users.get_profile),
    ("/users/videos", schemas.UserPostsSchema, users.get_posts),
    ("/users/reposts", schemas.UserVideosSchema, users.get_reposts),
    ("/users/followers", schemas.UserPageSchema, users.get_followers),
    ("/users/following", schemas.UserPageSchema, users.get_following),
    ("/users/playlists", schemas.UserPageSchema, users.get_playlists),
    ("/users/collections", schemas.UserPageSchema, users.get_collections),
    ("/users/resolve", schemas.UserSchema, users.resolve),
    # search
    ("/search/suggestions", schemas.SuggestionsSchema, search.get_suggestions),
    ("/search/videos", schemas.VideoSearchSchema, search.search_videos),
    ("/search/users", schemas.UserSearchSchema, search.search_users),
    ("/search/top", schemas.SearchSchema, search.search_top),
    ("/search/live", schemas.SearchSchema, search.search_live),
    # hashtags, sounds, playlists, collections, places, effects
    ("/hashtags/details", schemas.HashtagSchema, discovery.get_hashtag),
    ("/hashtags/videos", schemas.HashtagPostsSchema, discovery.get_hashtag_posts),
    ("/music/details", schemas.MusicSchema, discovery.get_music),
    ("/music/videos", schemas.MusicPostsSchema, discovery.get_music_posts),
    ("/playlists/details", schemas.PlaylistSchema, discovery.get_playlist),
    ("/playlists/videos", schemas.PlaylistPostsSchema, discovery.get_playlist_posts),
    ("/collections/videos", schemas.CollectionPostsSchema, discovery.get_collection_posts),
    ("/places/details", schemas.PlaceSchema, discovery.get_place),
    ("/places/videos", schemas.PlacePostsSchema, discovery.get_place_posts),
    ("/effects/details", schemas.EffectSchema, discovery.get_effect),
    # feeds
    ("/feed/trending", schemas.TrendingSchema, discovery.get_trending),
    ("/feed/explore", schemas.ExploreSchema, discovery.get_explore),
    ("/feed/explore/categories", schemas.EmptySchema, discovery.get_explore_categories),
    # live
    ("/live/details", schemas.UserSchema, live.get_room),
    # ads: Commercial Content Library + Creative Center top ads
    ("/ads/search", schemas.AdsSearchSchema, ads.search_library),
    ("/ads/details", schemas.AdSchema, ads.get_library_ad),
    ("/ads/advertisers", schemas.AdvertiserSearchSchema, ads.search_advertisers),
    ("/ads/countries", schemas.EmptySchema, ads.get_library_countries),
    ("/ads/top", schemas.TopAdsSchema, ads.get_top_ads),
    ("/ads/top/details", schemas.AdSchema, ads.get_top_ad),
    ("/ads/top/filters", schemas.EmptySchema, ads.get_top_ad_filters),
]

for _path, _schema, _fn in ENDPOINTS:
    mount(_path, _schema, _fn)


@route("/", method="GET")
@route("/health", method="GET")
def health():
    return json_response({"status": "ok", "endpoints": [p for p, _, _ in ENDPOINTS]})
