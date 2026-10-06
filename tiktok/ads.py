"""Ads endpoints.

COMMERCIAL CONTENT LIBRARY (library.tiktok.com — TikTok's public archive of
every ad shown in the EU / EEA, Switzerland, the UK and Türkiye, kept for
one year):
  * search    POST /api/v1/search?region=<code|all>&type=1&start_time&end_time
              12 ads a page; later pages need the first page's search id,
              so both ride one opaque cursor "<page index>.<search id>".
              By keyword (query_type 1), or by advertiser: the upstream only
              matches an advertiser by its exact registered name AND its
              business id together, so `advertiser` is looked up through
              the suggestion endpoint first.
  * details   GET /api/v1/items/<ad id>/details -> the ad, who paid for it,
              targeting and per-country reach by age and gender
  * advertisers  POST /api/v1/suggestion -> advertiser names + ids
  * countries    GET /api/v1/support-regions
  Impressions and audience sizes are published as ranges ("10K-100K") and
  stay strings. The `order` field of the search body is accepted but has no
  effect on the result (probed 2026-10-05), so no sort is exposed.

CREATIVE CENTER TOP ADS (ads.tiktok.com "Top Ads" inspiration gallery):
  * top       GET /creative_radar_api/v1/top_ads/v2/list — 20 best-performing
              ads for a country / period / ranking; logged out only the
              first page is served
  * details   GET /creative_radar_api/v1/top_ads/v2/detail
  * filters   GET /creative_radar_api/v1/top_ads/v2/filters (industries,
              objectives, languages, countries)
"""
from datetime import date, datetime, timedelta, timezone

from . import parsers as P
from .fetch import TikTokBadRequest, TikTokNotFound, ads_library, ads_library_regions, creative_center

LIBRARY_PAGE = 12
TOP_ADS_PAGE = 20
TOP_AD_NOT_FOUND = (40004,)
TOP_SORTS = {"for_you": "for_you", "likes": "like", "ctr": "ctr", "impressions": "impression",
             "watch_2s_rate": "play_2s_rate", "watch_6s_rate": "play_6s_rate", "conversion_rate": "cvr"}
TOP_OBJECTIVES = {"traffic": 1, "app_installs": 2, "conversions": 3, "video_views": 4, "reach": 5,
                  "lead_generation": 8, "product_sales": 15}
TOP_PERIODS = (7, 30, 180)


def _epoch(day, end=False):
    parsed = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end:
        parsed += timedelta(days=1) - timedelta(seconds=1)
    return int(parsed.timestamp())


def _advertiser(name):
    """An advertiser's exact (name, business ids) from the suggestion list."""
    for row in search_advertisers(name)["advertisers"]:
        if row["name"].lower() == name.lower():
            return row["name"], row["id"]
    raise TikTokNotFound(f"advertiser {name!r} not found — pass a name exactly as /tiktok/ads/advertisers returns it")


def search_library(query=None, advertiser=None, country=None, start_date=None, end_date=None, cursor=None):
    """Ads from the Commercial Content Library, most recently shown first:
    by keyword, by advertiser, or — with neither — the newest ads overall."""
    if query and advertiser:
        raise ValueError("pass query (ad keyword) or advertiser (advertiser name), not both")
    end_date = end_date or date.today().isoformat()
    start_date = start_date or (date.fromisoformat(end_date) - timedelta(days=30)).isoformat()
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    page, _, search_id = (cursor or "0.").partition(".")
    body = {"query": query or "", "query_type": "1", "adv_biz_ids": "", "order": "last_shown_date,desc",
            "offset": int(page), "search_id": search_id, "limit": LIBRARY_PAGE, "ad_type": 0, "ad_status": 1,
            "ages": ["all"], "ad_reach": ["all"], "gender": "ALL"}
    if advertiser:
        name, ids = _advertiser(advertiser)
        body.update(query=name, query_type="2", adv_biz_ids=ids)
    params = {"region": country or "all", "type": "1", "start_time": _epoch(start_date), "end_time": _epoch(end_date, end=True)}
    try:
        payload = ads_library("POST", "/api/v1/search", params=params, body=body)
    except TikTokBadRequest:
        if cursor:
            raise TikTokBadRequest("invalid cursor: pass the next_cursor value from the previous page unchanged")
        raise TikTokBadRequest(f"the ads library does not cover country {country!r} — see /tiktok/ads/countries"
                               if country else "the ads library refused these parameters")
    ads = [ad for ad in (P.library_ad(row) for row in payload.get("data") or []) if ad]
    more = bool(payload.get("has_more")) and bool(payload.get("search_id"))
    return {
        "query": query,
        "advertiser": advertiser,
        "country": country,
        "start_date": start_date,
        "end_date": end_date,
        "total_count": P.to_int(payload.get("total")),
        "ad_count": len(ads),
        "ads": ads,
        "next_cursor": f"{int(page) + 1}.{payload['search_id']}" if more else None,
        "has_more": more,
    }


def get_library_ad(ad):
    """One library ad with its advertiser, targeting and reach breakdown."""
    payload = ads_library("GET", f"/api/v1/items/{ad}/details", params={"lang": "en"}, not_found=f"ad {ad}")
    parsed = P.library_ad_details(payload.get("data"))
    if parsed is None:
        raise TikTokNotFound(f"ad {ad} not found")
    return parsed


def search_advertisers(query):
    """Advertisers whose registered name matches — the names /tiktok/ads/search
    accepts as `advertiser`."""
    payload = ads_library("POST", "/api/v1/suggestion", body={"query": query, "limit": 20, "suggest_type": "1"})
    rows = []
    for row in (payload.get("data") or {}).get("adv_names") or []:
        name = P.clean((row or {}).get("name"))
        if name:
            rows.append({"id": P.clean(row.get("ids")), "name": name})
    return {"query": query, "advertiser_count": len(rows), "advertisers": rows}


def get_library_countries():
    """The countries the Commercial Content Library covers."""
    rows = [{"code": P.clean(r.get("code")), "name": P.clean(r.get("name"))} for r in ads_library_regions() if isinstance(r, dict)]
    return {"country_count": len(rows), "countries": rows}


def get_top_ads(country="US", period=30, sort="for_you", industry=None, objective=None, language=None,
                query=None):
    """The Creative Center's best-performing ads for a country and period."""
    params = {"period": period, "page": 1, "limit": TOP_ADS_PAGE, "order_by": TOP_SORTS[sort], "country_code": country}
    if industry:
        params["industry"] = industry
    if objective:
        params["objective"] = TOP_OBJECTIVES[objective]
    if language:
        params["ad_language"] = language
    if query:
        params["keyword"] = query
    data = creative_center("/creative_radar_api/v1/top_ads/v2/list", params)
    ads = [ad for ad in (P.top_ad(row) for row in data.get("materials") or []) if ad]
    return {
        "country": country,
        "period_days": period,
        "sort": sort,
        "total_count": P.to_int((data.get("pagination") or {}).get("total_count")),
        "ad_count": len(ads),
        "ads": ads,
    }


def get_top_ad(ad):
    """One top ad: caption, landing page, countries, objectives, engagement."""
    data = creative_center("/creative_radar_api/v1/top_ads/v2/detail", {"material_id": ad}, not_found=TOP_AD_NOT_FOUND)
    parsed = P.top_ad(data)
    if parsed is None:
        raise TikTokNotFound(f"ad {ad} not found")
    return parsed


def get_top_ad_filters():
    """The industries, objectives, languages and countries /tiktok/ads/top accepts."""
    data = creative_center("/creative_radar_api/v1/top_ads/v2/filters", {})

    def options(key):
        return [{"id": str(row.get("id")), "name": P.clean(row.get("value"))}
                for row in data.get(key) or [] if isinstance(row, dict) and row.get("id") is not None]

    return {
        "industries": options("industry"),
        "countries": options("country"),
        "languages": [{"id": row["id"], "name": (row["name"] or "").replace("language_", "")} for row in options("ad_language")],
        "objectives": [{"id": key} for key in TOP_OBJECTIVES],
        "periods": list(TOP_PERIODS),
        "sorts": list(TOP_SORTS),
    }
