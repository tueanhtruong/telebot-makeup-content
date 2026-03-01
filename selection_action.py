import os
import asyncio
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
from facebook_service import upload_selected_media_to_facebook


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
media_window_seconds = int(os.getenv("TELEGRAM_MEDIA_WINDOW_SECONDS", "600"))
media_fetch_limit = int(os.getenv("TELEGRAM_MEDIA_FETCH_LIMIT", "100"))

gemini_model = create_gemini_model()
client = TelegramClient(session_name, api_id, api_hash)


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
		facebook_app_id = os.getenv("FACEBOOK_APP_ID", "").strip() or None
		
		if facebook_token and facebook_page_id:
			print("\n" + "=" * 80)
			print("Uploading selected media to Facebook...")
			if facebook_app_id:
				print(f"Using Resumable Upload API (App ID: {facebook_app_id})")
			print("=" * 80)
			success = await upload_selected_media_to_facebook(
				client=client,
				gemini_model=gemini_model,
				selected_media=selected_media,
				facebook_token=facebook_token,
				facebook_page_id=facebook_page_id,
				facebook_app_id=facebook_app_id,
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
