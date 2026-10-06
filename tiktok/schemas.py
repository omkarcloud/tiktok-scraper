"""Marshmallow request schemas for every /tiktok/* route.

Generic fields live in the shared top-level schema_fields.py; this module
adds the TikTok resolvers and the per-route schemas. Every schema's load()
output is the kwargs dict its endpoint function takes.

ONE param per input (tripadvisor QueryOrIdField convention, never a sibling
`url`/`id` pair), auto-detected by refs.py:
  user        a username, @username, secUid or tiktok.com profile link
  video       a video id or any tiktok.com video / photo / share link
  hashtag     a hashtag (with or without #) or a tiktok.com/tag/ link
  music, playlist, collection, place, effect
              the numeric id or the entity's tiktok.com link
"""
from marshmallow import validate

from schema_fields import (BaseSchema, ChoiceField, CountryCodeField, DateField, LanguageCodeField, QueryField,
                           RefField, StrippedString)
from tiktok import ads, discovery, refs, search, users


class UserRefField(RefField):
    resolver = staticmethod(refs.resolve_user)


class VideoRefField(RefField):
    resolver = staticmethod(refs.resolve_video)


class HashtagRefField(RefField):
    resolver = staticmethod(refs.resolve_hashtag)


class MusicRefField(RefField):
    resolver = staticmethod(refs.resolve_music)


class PlaylistRefField(RefField):
    resolver = staticmethod(refs.resolve_playlist)


class CollectionRefField(RefField):
    resolver = staticmethod(refs.resolve_collection)


class PlaceRefField(RefField):
    resolver = staticmethod(refs.resolve_place)


class EffectRefField(RefField):
    resolver = staticmethod(refs.resolve_effect)


class CursorField(StrippedString):
    """Opaque next_cursor from the previous page (absent = first page).
    `pattern` is the shape the endpoint's cursors have, so a mangled value
    is a 400 here instead of a silent first page upstream."""

    def __init__(self, pattern=r"\d{1,20}", **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", None)
        kwargs.setdefault("validate", validate.Regexp(
            rf"^(?:{pattern})$", error="Must be the next_cursor value of the previous page, unchanged."))
        super().__init__(**kwargs)


class ExitCountryField(CountryCodeField):
    """Country whose TikTok is asked (the request leaves from a residential
    exit there). Lower-cased for the transport; absent = the default exit."""

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        return value.lower() if value else None


SEARCH_CURSOR = r"\d{1,5}(?:\.[0-9A-Za-z]{8,64})?"
ADS_CURSOR = r"\d{1,4}\.[A-Za-z0-9+/=_-]{1,600}"
USER_DESC = "username, @username, secUid or tiktok.com profile link"
VIDEO_DESC = "video id, or a tiktok.com video / photo link, or a share link (vm.tiktok.com/…, tiktok.com/t/…)"


class EmptySchema(BaseSchema):
    pass


# ---- users -----------------------------------------------------------------------------

class UserSchema(BaseSchema):
    user = UserRefField(metadata={"description": USER_DESC})


class UserPageSchema(UserSchema):
    cursor = CursorField()


class UserVideosSchema(UserPageSchema):
    country = ExitCountryField()


class UserPostsSchema(UserVideosSchema):
    sort = ChoiceField(list(users.SORTS), load_default="latest")


# ---- videos ----------------------------------------------------------------------------

class VideoSchema(BaseSchema):
    video = VideoRefField(metadata={"description": VIDEO_DESC})
    country = ExitCountryField()


class VideoPageSchema(VideoSchema):
    cursor = CursorField()


class CommentRepliesSchema(VideoPageSchema):
    comment_id = StrippedString(required=True, validate=validate.Regexp(
        r"^\d{10,25}$", error="Must be a comment id from /tiktok/videos/comments."))


class TranscriptSchema(VideoSchema):
    language = LanguageCodeField(metadata={"description": "caption language, e.g. en or es-ES (default: the original)"})


# ---- search ----------------------------------------------------------------------------

class SearchSchema(BaseSchema):
    query = QueryField(max_length=200)
    country = ExitCountryField()
    cursor = CursorField(pattern=SEARCH_CURSOR)


class VideoSearchSchema(SearchSchema):
    sort = ChoiceField(list(search.SORTS), load_default="relevance")
    published = ChoiceField(list(search.PUBLISHED))


class UserSearchSchema(BaseSchema):
    query = QueryField(max_length=200)
    cursor = CursorField(pattern=SEARCH_CURSOR)


class SuggestionsSchema(BaseSchema):
    query = QueryField(max_length=100)
    country = ExitCountryField()


# ---- discovery -------------------------------------------------------------------------

class HashtagSchema(BaseSchema):
    hashtag = HashtagRefField(metadata={"description": "hashtag (with or without #) or tiktok.com/tag/ link"})


class HashtagPostsSchema(HashtagSchema):
    cursor = CursorField()
    country = ExitCountryField()


class MusicSchema(BaseSchema):
    music = MusicRefField(metadata={"description": "sound id or tiktok.com/music/ link"})


class MusicPostsSchema(MusicSchema):
    cursor = CursorField()
    country = ExitCountryField()


class PlaylistSchema(BaseSchema):
    playlist = PlaylistRefField(metadata={"description": "playlist id or tiktok.com/@user/playlist/ link"})


class PlaylistPostsSchema(PlaylistSchema):
    cursor = CursorField()
    country = ExitCountryField()


class CollectionPostsSchema(BaseSchema):
    collection = CollectionRefField(metadata={"description": "collection id or tiktok.com/@user/collection/ link"})
    cursor = CursorField()
    country = ExitCountryField()


class PlaceSchema(BaseSchema):
    place = PlaceRefField(metadata={"description": "place id or tiktok.com/place/ link"})


class PlacePostsSchema(PlaceSchema):
    cursor = CursorField()
    country = ExitCountryField()


class EffectSchema(BaseSchema):
    effect = EffectRefField(metadata={"description": "effect id or tiktok.com/sticker/ link"})


class TrendingSchema(BaseSchema):
    country = ExitCountryField()


class ExploreSchema(BaseSchema):
    category = ChoiceField(list(discovery.EXPLORE_CATEGORIES), load_default="all")
    country = ExitCountryField()


# ---- ads -------------------------------------------------------------------------------

class AdIdField(StrippedString):
    def __init__(self, **kwargs):
        kwargs.setdefault("required", True)
        kwargs.setdefault("validate", validate.Regexp(r"^\d{10,25}$", error="Must be a numeric ad id."))
        super().__init__(**kwargs)


class AdsSearchSchema(BaseSchema):
    query = StrippedString(validate=validate.Length(max=200), load_default=None,
                           metadata={"description": "keyword in the ad (pass this, advertiser, or neither for the newest ads)"})
    advertiser = StrippedString(validate=validate.Length(max=200), load_default=None,
                                metadata={"description": "advertiser name exactly as /tiktok/ads/advertisers returns it"})
    country = CountryCodeField(metadata={"description": "a country from /tiktok/ads/countries (default: all of them)"})
    start_date = DateField(bound="past")
    end_date = DateField(bound="past")
    cursor = CursorField(pattern=ADS_CURSOR)


class AdSchema(BaseSchema):
    ad = AdIdField()


class AdvertiserSearchSchema(BaseSchema):
    query = QueryField(max_length=100)


class TopAdsSchema(BaseSchema):
    country = CountryCodeField(load_default="US")
    period = ChoiceField({str(days): days for days in ads.TOP_PERIODS}, load_default=30)
    sort = ChoiceField(list(ads.TOP_SORTS), load_default="for_you")
    industry = StrippedString(validate=validate.Regexp(r"^\d{8,14}$", error="Must be an industry id from /tiktok/ads/top/filters."),
                              load_default=None)
    objective = ChoiceField(list(ads.TOP_OBJECTIVES))
    language = LanguageCodeField()
    query = StrippedString(validate=validate.Length(max=100), load_default=None)
