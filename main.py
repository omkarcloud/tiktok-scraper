"""Use the scraper straight from Python — no server needed.

    python main.py

Every function returns the same JSON the API does; results are written to
output/*.json. See README.md → "Use it from Python" for the full function list.
"""
import json
import os

from tiktok import refs
from tiktok.search import search_videos
from tiktok.users import get_profile
from tiktok.videos import get_details

os.makedirs("output", exist_ok=True)


def save(name, data):
    path = os.path.join("output", name)
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"saved {path}")


if __name__ == "__main__":
    # a video id or any tiktok.com video / share link
    save("video_7692114317151423775.json",
         get_details(refs.resolve_video("https://www.tiktok.com/@tiktok/video/7692114317151423775")))

    # a username, @username or profile link
    save("profile_mrbeast.json", get_profile(refs.resolve_user("mrbeast")))

    # 20 videos per page, most liked of the last month
    save("search_nasa.json", search_videos("nasa", sort="likes", published="month"))
