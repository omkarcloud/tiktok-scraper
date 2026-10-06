"""Cache TTL per /tiktok/* endpoint (cache.py, keyed on the validated params
— `user=nasa`, `user=@NASA` and a pasted profile link all validate to the
same key).

TikTok counters move by the second on popular videos and the feeds are
regenerated per call, so the tiers stay short; ids and static facts
(resolvers, hashtag / sound / place pages, the ads library) change slowly.
Cursor pages are cached per cursor. The media links inside a video expire
(x-expires, a few hours out), which caps every video-bearing TTL well below
that. The trending and explore feeds are NOT cached: "call again for a new
batch" is their paging.
"""
from datetime import timedelta

RESOLVE_CACHE = timedelta(hours=24)          # username <-> id, share link -> video
PROFILE_CACHE = timedelta(minutes=30)
USER_VIDEOS_CACHE = timedelta(minutes=10)    # videos, reposts
FOLLOW_CACHE = timedelta(minutes=30)         # followers / following pages
USER_LISTS_CACHE = timedelta(hours=1)        # playlists, collections
VIDEO_CACHE = timedelta(minutes=10)          # details, media, related
COMMENTS_CACHE = timedelta(minutes=10)
TRANSCRIPT_CACHE = timedelta(hours=24)       # captions never change
SEARCH_CACHE = timedelta(minutes=10)
USER_SEARCH_CACHE = timedelta(hours=1)
SUGGEST_CACHE = timedelta(hours=6)
ENTITY_CACHE = timedelta(hours=1)            # hashtag / sound / playlist / place / effect pages
ENTITY_VIDEOS_CACHE = timedelta(minutes=10)  # their video lists
LIVE_CACHE = timedelta(seconds=30)
ADS_SEARCH_CACHE = timedelta(hours=1)
AD_CACHE = timedelta(hours=6)
ADS_REFERENCE_CACHE = timedelta(hours=24)    # library countries, top-ad filters
TOP_ADS_CACHE = timedelta(hours=1)
