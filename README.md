![TikTok Scraper Featured Image](https://raw.githubusercontent.com/omkarcloud/tiktok-scraper/master/tiktok-scraper-featured-image.png)

# TikTok Scraper API

Get TikTok video details with download URLs (HD + watermark-free), user profiles, trending feeds, and search results via a simple REST API. 200 free requests/month.

## Key Features

- Get video details with direct MP4 download links (standard, watermarked, HD)
- Pull user profiles with follower stats, bio, linked socials, and verification status
- Browse trending videos by region
- Fetch any user's video history with pagination
- Search TikTok videos by keyword
- 30+ data points per video
- **200 requests/month on free tier**
- Example Response:
```json
{
  "video_id": "7577398554101058824",
  "region": "NP",
  "caption": "#fyp #foryoupage #shinchan #dontletthisflop #viral",
  "created_at": 1764250588,
  "duration_seconds": 11,
  "author": {
    "user_id": "7277886691518465026",
    "handle": "giaerra",
    "display_name": "gītaa^̲̲̲",
    "avatar_url": "https://p16-common-sign.tiktokcdn-us.com/..."
  },
  "media": {
    "video_url": "https://v19.tiktokcdn-us.com/.../video.mp4",
    "hd_video_url": "https://v16.tokcdn.com/.../video_hd.mp4",
    "file_size_bytes": 784387,
    "hd_file_size_bytes": 4552303
  },
  "stats": {
    "views": 2152606,
    "likes": 304735,
    "comments": 728,
    "shares": 60542,
    "downloads": 531,
    "saves": 22444
  }
}
```

## Get API Key

Create an account at [omkar.cloud](https://www.omkar.cloud/auth/sign-up?redirect=/api-key) to get your API key.

It takes just 2 minutes to sign up. You get 200 free requests every month for detailed TikTok data.

This is a well built product, and your search for the best TikTok Scraper API ends right here.


## Quick Start

```bash
curl -X GET "https://tiktok-scraper.omkar.cloud/tiktok/videos/details?video_url=https://www.tiktok.com/@giaerra/video/7577398554101058824" \
  -H "API-Key: YOUR_API_KEY"
```

```json
{
  "video_id": "7577398554101058824",
  "region": "NP",
  "caption": "#fyp #foryoupage #shinchan #dontletthisflop #viral",
  "created_at": 1764250588,
  "duration_seconds": 11,
  "author": {
    "handle": "giaerra",
    "display_name": "gītaa^̲̲̲"
  },
  "media": {
    "video_url": "https://v19.tiktokcdn-us.com/.../video.mp4",
    "hd_video_url": "https://v16.tokcdn.com/.../video_hd.mp4",
    "file_size_bytes": 784387,
    "hd_file_size_bytes": 4552303
  },
  "stats": {
    "views": 2152606,
    "likes": 304735,
    "comments": 728,
    "shares": 60542,
    "downloads": 531,
    "saves": 22444
  }
}
```

## Quick Start (Python)

```bash
pip install requests
```

```python
import requests

# Get video details with download URLs
response = requests.get(
    "https://tiktok-scraper.omkar.cloud/tiktok/videos/details",
    params={"video_url": "https://www.tiktok.com/@giaerra/video/7577398554101058824"},
    headers={"API-Key": "YOUR_API_KEY"}
)

print(response.json())
```


## API Reference

### Video Details

```
GET https://tiktok-scraper.omkar.cloud/tiktok/videos/details
```

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `video_url` | Yes | — | TikTok video URL. |

#### Example

```python
import requests

response = requests.get(
    "https://tiktok-scraper.omkar.cloud/tiktok/videos/details",
    params={"video_url": "https://www.tiktok.com/@giaerra/video/7577398554101058824"},
    headers={"API-Key": "YOUR_API_KEY"}
)

print(response.json())
```

#### Response

<details>
<summary>Sample Response (click to expand)</summary>

```json
{
  "video_id": "7577398554101058824",
  "region": "NP",
  "caption": "#fyp #foryoupage #shinchan #dontletthisflop #viral",
  "created_at": 1764250588,
  "duration_seconds": 11,
  "author": {
    "user_id": "7277886691518465026",
    "handle": "giaerra",
    "display_name": "gītaa^̲̲̲",
    "avatar_url": "https://p16-common-sign.tiktokcdn-us.com/..."
  },
  "media": {
    "video_url": "https://v19.tiktokcdn-us.com/.../video.mp4",
    "watermarked_video_url": "https://v19.tiktokcdn-us.com/.../video_wm.mp4",
    "hd_video_url": "https://v16.tokcdn.com/.../video_hd.mp4",
    "file_size_bytes": 784387,
    "watermarked_file_size_bytes": 0,
    "hd_file_size_bytes": 4552303
  },
  "thumbnails": {
    "cover_url": "https://p19-common-sign.tiktokcdn-us.com/.../cover.jpeg",
    "animated_cover_url": "https://p16-common-sign.tiktokcdn-us.com/.../animated.image",
    "original_cover_url": "https://p16-common-sign.tiktokcdn-us.com/.../original.webp"
  },
  "audio": {
    "audio_id": "7468606643236883217",
    "title": "original sound - gwyneth.paita",
    "artist": "gwyn",
    "play_url": "https://v16-ies-music.tiktokcdn-us.com/.../audio.mp3",
    "cover_url": "https://p16-common-sign.tiktokcdn-us.com/.../cover.jpeg",
    "is_original": true,
    "duration_seconds": 25,
    "album": null
  },
  "stats": {
    "views": 2152606,
    "likes": 304735,
    "comments": 728,
    "shares": 60542,
    "downloads": 531,
    "saves": 22444
  },
  "is_advertisement": false,
  "is_pinned": false
}
```

</details>

---

### Trending Videos

```
GET https://tiktok-scraper.omkar.cloud/tiktok/videos/trending
```

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `market` | No | `us` | Two-letter region code. |
| `max_results` | No | `10` | Number of videos to return (max 20). |

#### Example

```python
import requests

response = requests.get(
    "https://tiktok-scraper.omkar.cloud/tiktok/videos/trending",
    params={"market": "us", "max_results": 10},
    headers={"API-Key": "YOUR_API_KEY"}
)

print(response.json())
```

#### Response

<details>
<summary>Sample Response (click to expand)</summary>

```json
{
  "videos": [
    {
      "video_id": "7603384680255081758",
      "region": "US",
      "caption": "Lives in 🇺🇸USA #singlelife",
      "created_at": 1770300964,
      "duration_seconds": 5,
      "author": {
        "user_id": "7586897697803846711",
        "handle": "leeou2011",
        "display_name": "lejack.k",
        "avatar_url": "https://p16-common-sign.tiktokcdn-us.com/..."
      },
      "media": {
        "video_url": "https://v45.tiktokcdn-us.com/.../video.mp4",
        "watermarked_video_url": "https://v45.tiktokcdn-us.com/.../video_wm.mp4",
        "hd_video_url": null,
        "file_size_bytes": 192786,
        "watermarked_file_size_bytes": 505111,
        "hd_file_size_bytes": null
      },
      "thumbnails": {
        "cover_url": "https://p16-common-sign.tiktokcdn-us.com/.../cover.jpeg",
        "animated_cover_url": "https://p16-common-sign.tiktokcdn-us.com/.../animated.image",
        "original_cover_url": "https://p19-common-sign.tiktokcdn-us.com/.../original.webp"
      },
      "audio": {
        "audio_id": "6774345467095451650",
        "title": "I Need Your Love",
        "artist": "Jake Coco & Madilyn Bailey",
        "is_original": false,
        "duration_seconds": 60,
        "album": "The Covers, Vol. 6"
      },
      "stats": {
        "views": 83370,
        "likes": 3289,
        "comments": 600,
        "shares": 20,
        "downloads": 44,
        "saves": null
      },
      "is_advertisement": false,
      "is_pinned": false
    }
  ]
}
```

</details>

---

### User Profile

```
GET https://tiktok-scraper.omkar.cloud/tiktok/users/profile
```

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `handle` | Yes | — | TikTok username (without the `@`). |

#### Example

```python
import requests

response = requests.get(
    "https://tiktok-scraper.omkar.cloud/tiktok/users/profile",
    params={"handle": "marvel"},
    headers={"API-Key": "YOUR_API_KEY"}
)

print(response.json())
```

#### Response

<details>
<summary>Sample Response (click to expand)</summary>

```json
{
  "user": {
    "user_id": "6857582733233931270",
    "handle": "marvel",
    "display_name": "Marvel Entertainment",
    "bio": "Marvel social media manager",
    "avatar_thumbnail_url": "https://p19-common-sign.tiktokcdn-us.com/.../100x100.webp",
    "avatar_medium_url": "https://p16-common-sign.tiktokcdn-us.com/.../720x720.webp",
    "avatar_large_url": "https://p19-common-sign.tiktokcdn-us.com/.../1080x1080.webp",
    "is_verified": true,
    "is_private": false,
    "bio_link": "Marvel.com",
    "instagram_handle": null,
    "twitter_handle": null,
    "youtube_channel_title": null,
    "youtube_channel_id": null,
    "account_created_at": 1596655540
  },
  "stats": {
    "following_count": 0,
    "follower_count": 14969237,
    "total_likes": 207043170,
    "video_count": 1883
  }
}
```

</details>

---

### User Videos

```
GET https://tiktok-scraper.omkar.cloud/tiktok/users/videos
```

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `handle` | Yes | — | TikTok username (without the `@`). |
| `max_results` | No | `10` | Number of videos to return (max 30). |
| `page_cursor` | No | `0` | Pagination cursor from a previous response. |

#### Example

```python
import requests

response = requests.get(
    "https://tiktok-scraper.omkar.cloud/tiktok/users/videos",
    params={"handle": "marvel", "max_results": 10},
    headers={"API-Key": "YOUR_API_KEY"}
)

print(response.json())
```

#### Response

<details>
<summary>Sample Response (click to expand)</summary>

```json
{
  "videos": [
    {
      "video_id": "7609039378899356959",
      "region": "US",
      "caption": "Families across the #MCU ❤️ Stream their stories now on Disney+.",
      "created_at": 1771617567,
      "duration_seconds": 30,
      "author": {
        "user_id": "6857582733233931270",
        "handle": "marvel",
        "display_name": "Marvel Entertainment",
        "avatar_url": "https://p19-common-sign.tiktokcdn-eu.com/..."
      },
      "media": {
        "video_url": "https://v58.tiktokcdn-eu.com/.../video.mp4",
        "hd_video_url": null,
        "file_size_bytes": 2297146
      },
      "audio": {
        "audio_id": "7609044615715670814",
        "title": "original sound - marvel",
        "artist": "Marvel Entertainment",
        "is_original": true
      },
      "stats": {
        "views": 63259,
        "likes": 8504,
        "comments": 132,
        "shares": 258,
        "downloads": 0,
        "saves": 795
      },
      "is_advertisement": true,
      "is_pinned": false
    }
  ]
}
```

</details>

---

### Video Search

```
GET https://tiktok-scraper.omkar.cloud/tiktok/videos/search
```

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `search_query` | Yes | — | Search keyword. |
| `market` | No | `us` | Two-letter region code. |
| `max_results` | No | `10` | Number of results (max 30). |
| `page_cursor` | No | `0` | Pagination cursor from a previous response. |
| `sort_by` | No | `relevance` | Sort order: `relevance`, `most_liked`, `latest`. |
| `publish_time` | No | `all` | Publish time filter: `all`, `past_24_hours`, `this_week`, `this_month`, `last_3_months`, `last_6_months`. |

#### Example

```python
import requests

response = requests.get(
    "https://tiktok-scraper.omkar.cloud/tiktok/videos/search",
    params={"search_query": "shinchan", "market": "us"},
    headers={"API-Key": "YOUR_API_KEY"}
)

print(response.json())
```

#### Response

<details>
<summary>Sample Response (click to expand)</summary>

```json
{
  "videos": [
    {
      "video_id": "7596632332644355346",
      "region": "KR",
      "caption": "title: 짱구는 못말려 fanart timelapse #digitalart #shinchan #timelapse",
      "created_at": 1768728802,
      "duration_seconds": 15,
      "author": {
        "user_id": "7489111776035259410",
        "handle": "official_dongbo",
        "display_name": "officialdongbo",
        "avatar_url": "https://p16-sign-sg.tiktokcdn.com/..."
      },
      "media": {
        "video_url": "https://v16m.tiktokcdn.com/.../video.mp4",
        "file_size_bytes": 1291134
      },
      "audio": {
        "audio_id": "7218208687667316737",
        "title": "Neon-colored City",
        "artist": "Reo",
        "is_original": false,
        "album": "Neon-colored City"
      },
      "stats": {
        "views": 114425,
        "likes": 2527,
        "comments": 121,
        "shares": 369,
        "downloads": 30
      },
      "is_advertisement": false,
      "is_pinned": false
    }
  ]
}
```

</details>

## Error Handling

```python
response = requests.get(
    "https://tiktok-scraper.omkar.cloud/tiktok/videos/details",
    params={"video_url": "https://www.tiktok.com/@giaerra/video/7577398554101058824"},
    headers={"API-Key": "YOUR_API_KEY"}
)

if response.status_code == 200:
    data = response.json()
elif response.status_code == 401:
    # Invalid API key
    pass
elif response.status_code == 429:
    # Rate limit exceeded
    pass
```

## FAQs

### What data does the API return?

**Video Details** returns per video:
- Video ID, caption, region, creation timestamp, duration
- Direct MP4 download URLs (standard, watermarked, HD)
- File sizes for each video quality
- Thumbnail URLs (cover, animated, original)
- Author info (handle, display name, avatar)
- Audio/music details (title, artist, play URL, album)
- Engagement stats (views, likes, comments, shares, downloads, saves)
- Advertisement and pinned flags

**User Profile** returns:
- User ID, handle, display name, bio
- Avatar URLs in 3 sizes (thumbnail, medium, large)
- Verification and privacy status
- Bio link, linked social accounts (Instagram, Twitter, YouTube)
- Account creation date
- Follower count, following count, total likes, video count

**Trending Feed** returns a list of currently trending videos in any region, each with full video data as described above.

**User Videos** returns a paginated list of a user's posted videos with full metadata.

**Video Search** returns videos matching a keyword, with full video data and pagination. Supports sorting by relevance, likes, or date, and filtering by publish time.

All in structured JSON. Ready to use in your app.

### How accurate is the data?

Data is pulled from TikTok in real time. Every API call fetches live data — not cached or stale results. View counts, follower counts, video URLs, and engagement metrics reflect what's on TikTok right now.

### Can I download TikTok videos without watermarks?

Yes. The Video Details endpoint returns multiple MP4 download URLs:
- `video_url` — watermark-free MP4
- `watermarked_video_url` — with TikTok watermark
- `hd_video_url` — highest quality available (when the video supports it)

All URLs are direct CDN links. No redirects, no scraping needed.


### What regions are supported?

Pass any two-letter country code as the `market` parameter. The Trending Feed and Video Search endpoints support regional filtering — get trending content from `us`, `gb`, `jp`, `in`, `br`, or any other TikTok market.

## Rate Limits

| Plan | Price | Requests/Month |
|------|-------|----------------|
| Free | $0 | 200 |
| Starter | $16 | 15,000 |
| Growth | $48 | 75,000 |
| Scale | $148 | 300,000 |

## Questions? We have answers.

Reach out anytime. We will solve your query within 1 working day.

[![Contact Us on WhatsApp about TikTok Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://api.whatsapp.com/send?phone=918178804274&text=I%20have%20a%20question%20about%20the%20TikTok%20Scraper%20API.)

[![Contact Us on Email about TikTok Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=TikTok%20Scraper%20API%20Question)
