# this file aim to test the facebook post function
import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

from facebook_service import post_to_facebook, is_video_message
from selection_action import upload_selected_media_to_facebook
from selection_message_service import create_gemini_model
from telegram_service import (
  parse_channels,
  parse_channel_ids,
  get_required_env,
  resolve_targets,
  poll_media_once,
)

load_dotenv()

"""
SELECTED MEDIA:
  Media ID: 189976
  Message IDs: 189976
  Type: VIDEO
  Channel: Quán Tin | Kênh Thông tin chính trị quốc tế | Vietnam Information Corner
  Time: 01/03/2026 16:48
  Preview: 🇧🇭🇮🇷Khách sạn Crowne Plaza ở Manama, Bahrain sau cuộc tấn công của Iran.



"""

async def post_selected_media_from_telegram() -> None:
  """Fetch media from Telegram and upload the selected item to Facebook."""
  api_id = int(get_required_env("TELEGRAM_API_ID"))
  api_hash = get_required_env("TELEGRAM_API_HASH")
  session_name = os.getenv("TELEGRAM_SESSION_NAME", "telethon_session").strip() or "telethon_session"

  media_channel_usernames = parse_channels(os.getenv("TELEGRAM_CHANNEL_MEDIA_USERNAME", ""))
  raw_media_channel_ids = os.getenv("TELEGRAM_CHANNEL_MEDIA_ID", "")
  media_channel_ids = parse_channel_ids(raw_media_channel_ids)
  media_window_seconds = int(os.getenv("TELEGRAM_MEDIA_WINDOW_SECONDS", "3600"))
  media_fetch_limit = int(os.getenv("TELEGRAM_MEDIA_FETCH_LIMIT", "100"))

  facebook_token = os.getenv("FACEBOOK_TOKEN", "").strip()
  facebook_page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
  gemini_model = create_gemini_model()
  if not facebook_token or not facebook_page_id:
    print("[WARN] Missing FACEBOOK_TOKEN or FACEBOOK_PAGE_ID, skipping media upload")
    return

  client = TelegramClient(session_name, api_id, api_hash)
  await client.start()

  try:
    targets = await resolve_targets(client, media_channel_usernames, media_channel_ids)
    if not targets:
      print("[ERROR] No valid media channel targets found")
      return

    seen_message_ids: dict[int, set[int]] = {}
    
    # Fetch media messages from Telegram to get the actual message object
    print("[INFO] Fetching messages from Telegram...")
    media_messages = await poll_media_once(
      client=client,
      targets=targets,
      seen_message_ids=seen_message_ids,
      window_seconds=media_window_seconds,
      fetch_limit=media_fetch_limit,
    )

    if not media_messages:
      print("[ERROR] No media messages found")
      return

    # Pick the last video media message from the fetched list
    selected_media = None
    selected_message = None
    for media_msg in reversed(media_messages):
      messages = media_msg.get("messages", [])
      if not messages:
        msg = media_msg.get("message")
        if msg:
          messages = [msg]

      if not messages:
        continue

      if is_video_message(messages[0]):
        selected_message = messages[0]
        selected_media = media_msg
        break

    if not selected_media or not selected_message:
      print("[ERROR] No video media message found in fetched media")
      return

    # Ensure the selected media structure includes message fields
    selected_media["message"] = selected_message
    selected_media["messages"] = [selected_message]

    print("\n[INFO] Using hardcoded selected media:")
    print(f"  Media ID: {selected_media['message_id']}")
    print(f"  Type: {', '.join(selected_media['media_types']).upper()}")
    print(f"  Preview: {selected_media['text_preview'][:100]}...")
    print()
    print("[INFO] Uploading selected media to Facebook...")
    
    facebook_app_id = os.getenv("FACEBOOK_APP_ID", "").strip() or None
    await upload_selected_media_to_facebook(
      client=client,
      gemini_model=gemini_model,
      selected_media=selected_media,
      facebook_token=facebook_token,
      facebook_page_id=facebook_page_id,
      facebook_app_id=facebook_app_id,
    )
  finally:
    await client.disconnect()


# Post selected media from Telegram (uses TELEGRAM_* and FACEBOOK_* env vars)
asyncio.run(post_selected_media_from_telegram())


"""
SELECTED MEDIA:
  Media ID: 189916
  Message IDs: 189916
  Type: VIDEO
  Channel: Quán Tin | Kênh Thông tin chính trị quốc tế | Vietnam Information Corner
  Time: 01/03/2026 15:00
  Preview: Một lá cờ màu đỏ, biểu tượng cho sự báo thù cho máu của lãnh đạo tối cao Ali Khamenei, đã được treo lên ở Iran.

Lá cờ này xuất hiện trên mái vòm màu xanh dương của nhà thờ Hồi giáo Jamkaran, nằm gần thành phố Qom. Hình ảnh này được đăng bởi cơ quan Fars.

#Thời_sự
"""