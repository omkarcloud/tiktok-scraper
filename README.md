# 🎵 TikTok Scraper

TikTok Scraper is a **free and open-source** scraper that gets you **unlimited** detailed TikTok data for free.

## ✨ What Can I Get?

- 🎬 **Full details on any video** — play / like / comment / share counts, every MP4 quality, sound, hashtags & captions
- 👤 **Profiles, videos & followers of 1B+ users** — bio, follower counts, latest / popular videos, playlists
- 🔍 **Search videos, users, hashtags, sounds & live streams** — plus trending and Explore feeds for any country
- 📢 **Ads intelligence** — TikTok's EU/UK ad library with targeting & reach, and Creative Center's top ads

## 🎥 Example: A Full TikTok Video

```json
{
  "id": "7692114317151423775",
  "link": "https://www.tiktok.com/@tiktok/video/7692114317151423775",
  "type": "video",
  "description": "ATEEZ on the FYF. BTS on tour. dance challenges on repeat. @rachelszero and friends reminisce on K-Pop Summer on TikTok",
  "language": "en",
  "created_at": "2026-10-02T16:52:37Z",
  "is_ad": false,
  "stats": { "play_count": 279100, "like_count": 4696, "comment_count": 2041, "share_count": 457, "save_count": 438, "repost_count": 0 },
  "author": { "id": "107955", "username": "tiktok", "nickname": "TikTok", "link": "https://www.tiktok.com/@tiktok", "is_verified": true },
  "author_stats": { "follower_count": 96100000, "like_count": 465100000, "video_count": 1510 },
  "music": { "id": "7692114426937346847", "title": "original sound", "author_name": "TikTok", "duration_seconds": 65, "play_link": "https://v16m.tiktokcdn-us.com/..." },
  "video": {
    "duration_seconds": 65,
    "width": 720,
    "height": 1280,
    "cover": "https://p19-common-sign.tiktokcdn-us.com/...",
    "play_link": "https://www.tiktok.com/aweme/v1/play/?...",
    "qualities": [
      { "quality": "1080p", "codec": "h265_hvc1", "width": 1080, "height": 1920, "play_link": "https://www.tiktok.com/aweme/v1/play/?..." },
      { "quality": "720p", "codec": "h264", "width": 720, "height": 1280, "play_link": "https://www.tiktok.com/aweme/v1/play/?..." }
    ],
    "subtitles": [ { "language": "eng-US", "is_auto_generated": true, "format": "webvtt", "link": "https://v16m-webapp.tiktokcdn-us.com/..." } ]
  },
  "mentions": [ { "id": "6805952240777085958", "username": "rachelszero", "link": "https://www.tiktok.com/@rachelszero" } ],
  "suggested_searches": ["dance", "dance tiktoks", "kpop dance"]
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free TikTok Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/tiktok-scraper
cd tiktok-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/videos/details?video=7692114317151423775"
```

```json
{
  "id": "7692114317151423775",
  "link": "https://www.tiktok.com/@tiktok/video/7692114317151423775",
  "type": "video",
  "description": "ATEEZ on the FYF. BTS on tour. dance challenges on repeat. @rachelszero and friends reminisce on K-Pop Summer on TikTok",
  "created_at": "2026-10-02T16:52:37Z",
  "stats": { "play_count": 279100, "like_count": 4696, "comment_count": 2041, "share_count": 457, "save_count": 438, "repost_count": 0 },
  "author": { "id": "107955", "username": "tiktok", "nickname": "TikTok", "link": "https://www.tiktok.com/@tiktok", "is_verified": true },
  "author_stats": { "follower_count": 96100000, "like_count": 465100000, "video_count": 1510 },
  "music": { "id": "7692114426937346847", "title": "original sound", "author_name": "TikTok", "duration_seconds": 65 },
  "video": {
    "duration_seconds": 65,
    "width": 720,
    "height": 1280,
    "play_link": "https://www.tiktok.com/aweme/v1/play/?...",
    "qualities": [ { "quality": "1080p", "codec": "h265_hvc1", "play_link": "https://www.tiktok.com/aweme/v1/play/?..." } ]
  }
}
```

All 41 endpoints are now live at `http://localhost:8000`.

TikTok answers plain requests from an ordinary residential IP in a country where TikTok is available, so no proxy is needed. If TikTok is blocked where you run (India, for example), set `TIKTOK_PROXY=http://user:pass@host:port` — put `{country}` in the URL where your provider takes a country code and the scraper asks each request from the country it needs (TikTok answers user search only from Europe and video search only from the US).

## 📚 Endpoints

41 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Video Details | `/videos/details` | Everything about one video or photo post in a single call |
| Video Media | `/videos/media` | Every MP4 quality, photos, covers, subtitles & the sound |
| Video Comments / Replies | `/videos/comments`, `/videos/comment-replies` | Comments with likes, reply counts & authors, 50 per page |
| Video Transcript | `/videos/transcript` | Captions as timed segments plus the full text |
| Related Videos | `/videos/related` | What TikTok recommends next to a video |
| Resolve Video | `/videos/resolve` | Any link or share link → video ID, canonical link & author |
| User Profile | `/users/profile` | Bio, bio link, follower / like / video counts, verification, live status |
| User Videos / Reposts | `/users/videos`, `/users/reposts` | Latest, popular or oldest videos, 35 per page |
| User Followers / Following | `/users/followers`, `/users/following` | 30 accounts per page, each with counters |
| User Playlists / Collections | `/users/playlists`, `/users/collections` | Playlists and public collections with covers & counts |
| Resolve User | `/users/resolve` | Username ↔ ID ↔ secUid with follower count |
| Search Videos | `/search/videos` | 20 per page; sort by relevance or likes, filter by date |
| Search Users / Top / Live | `/search/users`, `/search/top`, `/search/live` | Accounts, TikTok's Top tab, live streams with viewer counts |
| Search Suggestions | `/search/suggestions` | What the search box suggests while typing |
| Hashtag Details / Videos | `/hashtags/details`, `/hashtags/videos` | Video count, total views; videos in ranked order |
| Music Details / Videos | `/music/details`, `/music/videos` | Sound info with Apple Music / Spotify ids; videos using it |
| Playlist / Collection Videos | `/playlists/details`, `/playlists/videos`, `/collections/videos` | Playlists and collections, 30 videos per page |
| Place Details / Videos | `/places/details`, `/places/videos` | Address, category, photos; videos tagged there |
| Effect Details | `/effects/details` | Effect name, icon & creator |
| Trending / Explore Feeds | `/feed/trending`, `/feed/explore`, `/feed/explore/categories` | For You and Explore feeds for any country, 30 videos per call |
| Live Room | `/live/details` | Is the account live now: title, viewers, category, stream links |
| Ad Library | `/ads/search`, `/ads/details`, `/ads/advertisers`, `/ads/countries` | EU/UK ads with advertiser, targeting & reach by age and gender |
| Top Ads | `/ads/top`, `/ads/top/details`, `/ads/top/filters` | Creative Center's best-performing ads by country, period & metric |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-tiktok-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-tiktok-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-tiktok-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/videos/details",
    params={"video": "7692114317151423775"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about TikTok Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://api.whatsapp.com/send?phone=918178804274&text=I%20need%20help%20using%20the%20TikTok%20Scraper%20API.)

[![Ask Us by Email about TikTok Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20TikTok%20Scraper%20API&body=I%20need%20help%20using%20the%20TikTok%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**IMDb Scraper**](https://github.com/omkarcloud/imdb-scraper) — movies, TV shows, ratings, cast & box office
- [**Threads Scraper**](https://github.com/omkarcloud/threads-scraper) — Threads posts, profiles, replies & search
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper) — live product details, SKU variants, stock & shipping

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/tiktok-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/tiktok-scraper)
