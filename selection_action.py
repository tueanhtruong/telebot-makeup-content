import os
import asyncio
import re
from telethon import TelegramClient
from dotenv import load_dotenv

from telegram_service import (
	parse_channels,
	parse_channel_ids,
	get_required_env,
	resolve_targets,
	poll_media_once,
)
from selection_message_service import (
	create_gemini_model,
	select_most_relevant_media,
	format_selection_result,
)


load_dotenv()


api_id = int(get_required_env("TELEGRAM_API_ID"))
api_hash = get_required_env("TELEGRAM_API_HASH")
session_name = os.getenv("TELEGRAM_SESSION_NAME", "telethon_session").strip() or "telethon_session"

# Text channel configuration
text_channel_usernames = parse_channels(os.getenv("TELEGRAM_CHANNEL_USERNAMES", ""))
raw_text_channel_ids = os.getenv("TELEGRAM_CHANNEL_IDS", "")
single_text_channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
if single_text_channel_id:
	raw_text_channel_ids = f"{raw_text_channel_ids},{single_text_channel_id}" if raw_text_channel_ids else single_text_channel_id
text_channel_ids = parse_channel_ids(raw_text_channel_ids)
text_window_seconds = int(os.getenv("TELEGRAM_WINDOW_SECONDS", "3600"))
text_fetch_limit = int(os.getenv("TELEGRAM_FETCH_LIMIT", "200"))

# Media channel configuration
media_channel_usernames = parse_channels(os.getenv("TELEGRAM_CHANNEL_MEDIA_USERNAME", ""))
raw_media_channel_ids = os.getenv("TELEGRAM_CHANNEL_MEDIA_ID", "")
media_channel_ids = parse_channel_ids(raw_media_channel_ids)
media_window_seconds = int(os.getenv("TELEGRAM_MEDIA_WINDOW_SECONDS", "3600"))
media_fetch_limit = int(os.getenv("TELEGRAM_MEDIA_FETCH_LIMIT", "200"))

gemini_model = create_gemini_model()
client = TelegramClient(session_name, api_id, api_hash)


def sanitize_facebook_message(model: object | None, text: str) -> str:
	"""Remove hashtags and rewrite sensitive wording for Facebook safety using Gemini."""
	if not text:
		return ""
	
    # log original text and length
	print(f"[SANITIZE] Original text ({len(text)} chars): {text[:100]}...")

	# Remove hashtags, then normalize spaces/newlines.
	without_hashtags = re.sub(r"(?<!\w)#\w+", "", text)
	cleaned_text = re.sub(r"[ \t]+", " ", without_hashtags)
	cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

	if model is None:
		print("[WARN] Gemini unavailable, using hashtag-removed text only")
		return cleaned_text

	prompt = f"""Bạn là trợ lý biên tập nội dung cho Facebook.

Nhiệm vụ:
• Hãy tìm những từ ngữ trong đoạn văn này có thể bị thuật toán Facebook quét là vi phạm tiêu chuẩn cộng đồng hoặc nhạy cảm và thay thế bằng từ phù hợp hơn
• Ngôn ngữ Tiếng Việt

Yêu cầu bắt buộc:
- Chỉ trả về đúng đoạn văn đã chỉnh sửa.
- Không thêm giải thích, không thêm nhãn, không thêm tiêu đề.

Đoạn văn:
{cleaned_text}
"""

	try:
		response = model.generate_content(prompt)
		sanitized_text = (getattr(response, "text", "") or "").strip()
		if not sanitized_text:
			print("[WARN] Gemini returned empty sanitized text, using hashtag-removed text")
			return cleaned_text
		return sanitized_text
	except Exception as error:
		print(f"[WARN] Gemini sanitize failed: {error}. Using hashtag-removed text")
		return cleaned_text


async def fetch_text_messages(
	client: TelegramClient,
	targets: list[object],
	window_seconds: int,
	fetch_limit: int,
) -> list[str]:
	"""Fetch raw text messages from text channels."""
	from datetime import datetime, timedelta, timezone
	
	window_start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
	text_messages: list[str] = []
	seen_message_ids: dict[int, set[int]] = {}

	for target in targets:
		try:
			messages = await client.get_messages(target, limit=fetch_limit)
		except Exception as error:
			target_id = getattr(target, 'id', 'unknown')
			print(f"[WARN] get_messages failed for {target_id}: {error}")
			continue

		if not messages:
			continue

		target_id = int(getattr(target, "id", 0) or 0)
		if target_id not in seen_message_ids:
			seen_message_ids[target_id] = set()

		recent_messages = [
			message
			for message in reversed(messages)
			if message.date and message.date >= window_start
		]

		for message in recent_messages:
			if message.id and message.id not in seen_message_ids[target_id]:
				content = message.raw_text or ""
				if content.strip():  # Only add non-empty messages
					timestamp = message.date.astimezone().strftime("%d/%m/%Y %H:%M") if message.date else ""
					print(f"[TEXT] {timestamp} {content[:100]}...")
					text_messages.append(content)
					seen_message_ids[target_id].add(message.id)

	return text_messages


async def upload_selected_media_to_facebook(
	client: TelegramClient,
	gemini_model: object | None,
	selected_media: dict,
	facebook_token: str,
	facebook_page_id: str,
) -> bool:
	"""
	Download media from Telegram if size < 20MB, upload to Facebook unpublished,
	then create a post with the media and preview text.
	
	Args:
		client: Telegram client instance
		selected_media: Selected media dict from select_most_relevant_media
		facebook_token: Facebook page access token
		facebook_page_id: Facebook page ID
	
	Returns:
		True if successful, False otherwise
	"""
	import tempfile
	import requests
	import json
	
	# Get messages list
	messages = selected_media.get("messages", [])
	if not messages:
		message = selected_media.get("message")
		if message:
			messages = [message]
	
	if not messages:
		print("[ERROR] No messages found in selected_media")
		return False
	
	media_fbids = []
	MAX_SIZE = 20 * 1024 * 1024  # 20MB in bytes
	
	# Process each message in the group (or single message)
	for msg in messages:
		# Check if message has media
		if not hasattr(msg, "media") or not msg.media:
			continue
		
		# Get file size
		file_size = None
		if hasattr(msg.media, "document"):
			file_size = getattr(msg.media.document, "size", None)
		elif hasattr(msg.media, "photo"):
			# For photos, we need to get the largest size
			if hasattr(msg.media.photo, "sizes"):
				sizes = msg.media.photo.sizes
				if sizes and len(sizes) > 0:
					# Get the biggest size
					biggest = max(sizes, key=lambda s: getattr(s, "size", 0) if hasattr(s, "size") else 0)
					file_size = getattr(biggest, "size", None)
		
		# Check if size is less than 20MB
		if file_size and file_size > MAX_SIZE:
			print(f"[SKIP] Media too large: {file_size / 1024 / 1024:.2f}MB > 20MB")
			continue
		
		# Download media to temp file
		temp_path = None
		try:
			with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file:
				temp_path = temp_file.name
			
			size_str = f"{file_size / 1024 / 1024:.2f}MB" if file_size else "unknown size"
			print(f"[DOWNLOAD] Downloading media ({size_str})...")
			await client.download_media(msg, file=temp_path)
			
			# Verify downloaded file size
			downloaded_size = os.path.getsize(temp_path)
			if downloaded_size > MAX_SIZE:
				print(f"[SKIP] Downloaded file too large: {downloaded_size / 1024 / 1024:.2f}MB > 20MB")
				os.unlink(temp_path)
				continue
			
			# Determine media type
			media_types = selected_media.get("media_types", [])
			is_video = "video" in media_types or "Video" in str(msg.media.__class__.__name__)
			
			# Upload to Facebook
			endpoint = f"https://graph.facebook.com/{facebook_page_id}/{'videos' if is_video else 'photos'}"
			
			with open(temp_path, "rb") as media_file:
				files = {"source": media_file}
				data = {
					"access_token": facebook_token,
					"published": "false",  # Unpublished mode
				}
				
				media_type_str = "video" if is_video else "photo"
				print(f"[UPLOAD] Uploading to Facebook as unpublished {media_type_str}...")
				response = requests.post(endpoint, data=data, files=files)
			
			# Clean up temp file
			os.unlink(temp_path)
			temp_path = None
			
			if response.status_code == 200:
				result = response.json()
				media_fbid = result.get("id")
				print(f"[SUCCESS] Uploaded to Facebook, media_fbid: {media_fbid}")
				media_fbids.append(media_fbid)
			else:
				print(f"[ERROR] Facebook upload failed: {response.status_code} - {response.text}")
				
		except Exception as error:
			print(f"[ERROR] Failed to download/upload media: {error}")
			if temp_path and os.path.exists(temp_path):
				os.unlink(temp_path)
			# Continue with next media item
	
	if not media_fbids:
		print("[ERROR] No media items were successfully uploaded")
		return False
	
	# Create Facebook post with attached media
	text_preview = selected_media.get("text_preview", "")
	sanitized_message = sanitize_facebook_message(gemini_model, text_preview)
	post_url = f"https://graph.facebook.com/{facebook_page_id}/feed"
	
	# Prepare attached_media parameter
	attached_media = [{"media_fbid": fbid} for fbid in media_fbids]
	
	payload = {
		"access_token": facebook_token,
		"message": sanitized_message,
		"attached_media": json.dumps(attached_media),
	}
	
	try:
		print(f"[POST] Creating Facebook post with {len(media_fbids)} media item(s)...")
		response = requests.post(post_url, data=payload)
		
		if response.status_code == 200:
			result = response.json()
			post_id = result.get("id")
			print(f"[SUCCESS] Created Facebook post: {post_id}")
			return True
		else:
			print(f"[ERROR] Facebook post creation failed: {response.status_code} - {response.text}")
			return False
			
	except Exception as error:
		print(f"[ERROR] Failed to create Facebook post: {error}")
		return False


async def main() -> None:
	print("Selection Message Service: Running single selection cycle...")
	print("=" * 80)
	print("TEXT CHANNELS:")
	print(f"  Usernames: {', '.join(text_channel_usernames) if text_channel_usernames else '(none)'}")
	print(f"  IDs: {', '.join(map(str, text_channel_ids)) if text_channel_ids else '(none)'}")
	print(f"  Time window: {text_window_seconds} seconds ({text_window_seconds/60:.0f} minutes)")
	print(f"  Fetch limit: {text_fetch_limit}")
	print()
	print("MEDIA CHANNELS:")
	print(f"  Usernames: {', '.join(media_channel_usernames) if media_channel_usernames else '(none)'}")
	print(f"  IDs: {', '.join(map(str, media_channel_ids)) if media_channel_ids else '(none)'}")
	print(f"  Time window: {media_window_seconds} seconds ({media_window_seconds/60:.0f} minutes)")
	print(f"  Fetch limit: {media_fetch_limit}")
	print("=" * 80)

	await client.start()
	
	# Resolve text channel targets
	text_targets = await resolve_targets(client, text_channel_usernames, text_channel_ids)
	if not text_targets:
		print("[ERROR] No valid text channel targets found. Check TELEGRAM_CHANNEL_USERNAMES / TELEGRAM_CHANNEL_ID(S).")
		return

	print("\nResolved TEXT channels:")
	for target in text_targets:
		name = getattr(target, "title", None) or getattr(target, "username", None) or str(getattr(target, "id", "unknown"))
		print(f"  - {name} (id: {getattr(target, 'id', 'unknown')})")

	# Resolve media channel targets
	media_targets = await resolve_targets(client, media_channel_usernames, media_channel_ids)
	if not media_targets:
		print("[ERROR] No valid media channel targets found. Check TELEGRAM_CHANNEL_MEDIA_USERNAME / TELEGRAM_CHANNEL_MEDIA_ID.")
		return

	print("\nResolved MEDIA channels:")
	for target in media_targets:
		name = getattr(target, "title", None) or getattr(target, "username", None) or str(getattr(target, "id", "unknown"))
		print(f"  - {name} (id: {getattr(target, 'id', 'unknown')})")
	print("=" * 80)

	# Fetch text messages
	print("\nFetching text messages...")
	text_messages = await fetch_text_messages(
		client=client,
		targets=text_targets,
		window_seconds=text_window_seconds,
		fetch_limit=text_fetch_limit,
	)
	print(f"Found {len(text_messages)} text messages")

	# Fetch media messages
	print("\nFetching media messages...")
	seen_message_ids: dict[int, set[int]] = {}
	media_messages = await poll_media_once(
		client=client,
		targets=media_targets,
		seen_message_ids=seen_message_ids,
		window_seconds=media_window_seconds,
		fetch_limit=media_fetch_limit,
	)
	print(f"Found {len(media_messages)} media messages")

	if not media_messages:
		print("[ERROR] No media messages found in the specified time window")
		return

	# Select most relevant media
	print("\nSelecting most relevant media using Gemini AI...")
	selected_media = select_most_relevant_media(
		model=gemini_model,
		text_messages=text_messages,
		media_messages=media_messages,
	)

	# Display results
	result = format_selection_result(
		text_message_count=len(text_messages),
		media_message_count=len(media_messages),
		selected_media=selected_media,
	)
	print(result)

	# Upload to Facebook if media was selected and credentials are available
	if selected_media:
		facebook_token = os.getenv("FACEBOOK_TOKEN", "").strip()
		facebook_page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
		
		if facebook_token and facebook_page_id:
			print("\n" + "=" * 80)
			print("Uploading selected media to Facebook...")
			print("=" * 80)
			success = await upload_selected_media_to_facebook(
				client=client,
				gemini_model=gemini_model,
				selected_media=selected_media,
				facebook_token=facebook_token,
				facebook_page_id=facebook_page_id,
			)
			if success:
				print("\n✓ Successfully uploaded to Facebook!")
			else:
				print("\n✗ Failed to upload to Facebook")
		else:
			print("\n[INFO] Facebook upload skipped (FACEBOOK_TOKEN or FACEBOOK_PAGE_ID not set)")
	
	print("\nSelection cycle complete.")


if __name__ == "__main__":
	asyncio.run(main())
