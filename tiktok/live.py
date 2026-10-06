"""Live endpoint: one account's live room.

Upstream (unsigned, probed 2026-10-05):
  * /api-live/user/room/?uniqueId=<username>&sourceType=54
      -> {user (roomId, status 2 = live / 4 = offline), stats, liveRoom
      (title, startTime, viewer counts, stream links)}. Status 19881007 is
      the answer for an account that does not exist or has never gone live.
  * https://webcast.tiktok.com/webcast/room/info/?aid=1988&room_id=<id>
      adds what the first call lacks while the room is live: like count,
      category, game, shopping / age-restriction flags.
"""
from . import parsers as P
from .fetch import WEBCAST, TikTokNotFound, TikTokUpstreamError, api

NO_LIVE_ROOM = 19881007


def get_room(user):
    """Whether the account is live right now, and its room: title, viewers,
    category and stream links."""
    username = user.get("username")
    if not username:
        raise ValueError("live rooms are looked up by username or profile link, not by secUid")
    payload = api("/api-live/user/room/", {"uniqueId": username, "sourceType": 54}, signed=False,
                  ok=(0, NO_LIVE_ROOM), label=f"live room of @{username}")
    data = payload.get("data")
    if payload.get("statusCode") == NO_LIVE_ROOM or not isinstance(data, dict) or not data.get("user"):
        raise TikTokNotFound(f"@{username} has no live room (the account does not exist or has never gone live)")
    room_info = None
    room_id = (data.get("user") or {}).get("roomId")
    if room_id and (data.get("liveRoom") or {}).get("status") == 2:
        try:
            room_info = api("/webcast/room/info/", {"aid": 1988, "room_id": room_id}, signed=False, base=False,
                            host=WEBCAST, label=f"live room {room_id}").get("data")
        except TikTokUpstreamError:
            room_info = None        # the room page data above is enough on its own
    return P.live_room(data, room_info)
