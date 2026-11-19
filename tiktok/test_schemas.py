"""Request schemas: an empty optional param (`cursor=`, `country=`, `sort=`)
is a normal request, never a 500 (StrippedString hands validators None for
it), and it means what the absent param means.

    python -m pytest tiktok/test_schemas.py -q -p no:seleniumbase
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from marshmallow import Schema  # noqa: E402

from schema_fields import load_query  # noqa: E402
from tiktok import schemas  # noqa: E402

VALID = {
    "user": "nasa",
    "video": "7559056406939946270",
    "comment_id": "7559056406939946271",
    "query": "nasa",
    "hashtag": "nasa",
    "music": "7559056406939946272",
    "playlist": "7559056406939946273",
    "collection": "7559056406939946274",
    "place": "22535865202204928",
    "effect": "7559056406939946275",
    "ad": "7559056406939946276",
}

# the shared DateField answers an empty value with a 400 (not a crash)
EMPTY_IS_REFUSED = {"start_date", "end_date"}

SCHEMAS = [cls for _, cls in inspect.getmembers(schemas, inspect.isclass)
           if issubclass(cls, Schema) and cls.__module__ == schemas.__name__]


@pytest.mark.parametrize("schema_cls", SCHEMAS, ids=lambda c: c.__name__)
def test_every_param_empty_is_a_400_or_ok_never_a_crash(schema_cls):
    names = list(schema_cls().fields)
    base = {n: VALID[n] for n in names if n in VALID}
    assert load_query(schema_cls, base)[1] is None, "VALID no longer loads this schema"
    for name in names:
        query = dict(base, **{name: ""})
        data, error = load_query(schema_cls, query)   # raises (= bottle 500) on a crash
        assert (data is None) != (error is None)
        if name not in VALID and name not in EMPTY_IS_REFUSED:    # an empty optional param is the absent param
            assert error is None and data == load_query(schema_cls, base)[0], name


def test_the_playground_request_that_was_a_500():
    # 2026-11-18 17:55 UTC: /users/videos?sort=latest&user=wazzycazzy&cursor=&country=
    data, error = load_query(schemas.UserPostsSchema, {"sort": "latest", "user": "wazzycazzy", "cursor": "", "country": ""})
    assert error is None
    assert data == {"user": {"username": "wazzycazzy", "sec_uid": None}, "cursor": None, "country": None, "sort": "latest"}


def test_empty_values_keep_the_defaults():
    assert load_query(schemas.UserPostsSchema, {"user": "nasa", "sort": ""})[0]["sort"] == "latest"
    assert load_query(schemas.VideoSearchSchema, {"query": "x", "sort": "", "published": ""})[0]["sort"] == "relevance"
    assert load_query(schemas.ExploreSchema, {"category": ""})[0]["category"] == "all"
    top = load_query(schemas.TopAdsSchema, {"country": "", "period": "", "sort": "", "industry": "", "query": ""})[0]
    assert (top["country"], top["period"], top["sort"], top["industry"], top["query"]) == ("US", 30, "for_you", None, None)


def test_the_validators_still_reject():
    for schema, query in [
        (schemas.UserPageSchema, {"user": "nasa", "cursor": "abc"}),
        (schemas.SearchSchema, {"query": "x", "cursor": "20.short"}),
        (schemas.AdsSearchSchema, {"query": "x" * 201}),
        (schemas.AdsSearchSchema, {"advertiser": "x" * 201}),
        (schemas.TopAdsSchema, {"industry": "12"}),
        (schemas.TopAdsSchema, {"query": "x" * 101}),
        (schemas.TopAdsSchema, {"country": "ZZ"}),
    ]:
        data, error = load_query(schema, query)
        assert data is None and error["error"].startswith("Invalid parameters"), query
