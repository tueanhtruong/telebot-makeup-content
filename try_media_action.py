import os
import asyncio
import json
from telethon import TelegramClient
from dotenv import load_dotenv

from telegram_service import (
	parse_channels,
	parse_channel_ids,
	get_required_env,
	resolve_targets,
	poll_media_once,
)


load_dotenv()


api_id = int(get_required_env("TELEGRAM_API_ID"))
api_hash = get_required_env("TELEGRAM_API_HASH")
session_name = os.getenv("TELEGRAM_SESSION_NAME", "telethon_session").strip() or "telethon_session"

channel_usernames = parse_channels(os.getenv("TELEGRAM_CHANNEL_MEDIA_USERNAME", ""))

raw_channel_ids = os.getenv("TELEGRAM_CHANNEL_MEDIA_ID", "")

channel_ids = parse_channel_ids(raw_channel_ids)

window_seconds = int(os.getenv("TELEGRAM_MEDIA_WINDOW_SECONDS", "3600"))
fetch_limit = int(os.getenv("TELEGRAM_MEDIA_FETCH_LIMIT", "100"))

client = TelegramClient(session_name, api_id, api_hash)


async def main() -> None:
	print("Media Action: Running single poll cycle for media messages...")
	print(f"Channel usernames: {', '.join(channel_usernames) if channel_usernames else '(none)'}")
	print(f"Channel IDs: {', '.join(map(str, channel_ids)) if channel_ids else '(none)'}")
	print(f"Time window: {window_seconds} seconds")
	print(f"Fetch limit: {fetch_limit}")
	print("-" * 80)

	await client.start()
	
	targets = await resolve_targets(client, channel_usernames, channel_ids)
	if not targets:
		print("[ERROR] No valid channel targets found. Check TELEGRAM_CHANNEL_MEDIA_USERNAME / TELEGRAM_CHANNEL_ID(S).")
		return

	print("Resolved channels:")
	for target in targets:
		name = getattr(target, "title", None) or getattr(target, "username", None) or str(getattr(target, "id", "unknown"))
		print(f"- {name} (id: {getattr(target, 'id', 'unknown')})")
	print("-" * 80)

	seen_message_ids: dict[int, set[int]] = {}
	media_messages = await poll_media_once(
		client=client,
		targets=targets,
		seen_message_ids=seen_message_ids,
		window_seconds=window_seconds,
		fetch_limit=fetch_limit,
	)

	# Print summary
	print("-" * 80)
	print(f"Media Action: Poll cycle complete. Found {len(media_messages)} messages with media.")
	
	if media_messages:
		print("\nMedia Messages Summary:")
		media_by_type = {}
		messages_with_multiple_media = 0
		grouped_messages = 0
		total_items_in_groups = 0
		
		for msg in media_messages:
			media_types = msg.get("media_types", [msg.get("media_type", "unknown")])
			
			# Count if message has multiple media types
			if isinstance(media_types, list) and len(media_types) > 1:
				messages_with_multiple_media += 1
			
			# Count grouped messages
			if msg.get("grouped_id"):
				grouped_messages += 1
				total_items_in_groups += len(msg.get("message_ids", []))
			
			# Count each media type
			if isinstance(media_types, list):
				for media_type in media_types:
					if media_type not in media_by_type:
						media_by_type[media_type] = 0
					media_by_type[media_type] += 1
			else:
				# Fallback for string format
				if media_types not in media_by_type:
					media_by_type[media_types] = 0
				media_by_type[media_types] += 1
		
		for media_type, count in sorted(media_by_type.items()):
			print(f"  - {media_type.upper()}: {count}")
		
		if messages_with_multiple_media > 0:
			print(f"\nMessages with multiple media types: {messages_with_multiple_media}")
		
		if grouped_messages > 0:
			print(f"Grouped messages (albums): {grouped_messages} ({total_items_in_groups} total items)")
		
		# Optional: Save to JSON file for further processing
		output_file = "media_messages.json"
		messages_for_json = [
			{
				"message_id": msg["message_id"],
				"message_ids": msg.get("message_ids", [msg["message_id"]]),
				"channel_id": msg["channel_id"],
				"channel_name": msg["channel_name"],
				"timestamp": msg["timestamp"],
				"media_types": msg.get("media_types", []),
				"media_type": msg.get("media_type", ""),
				"grouped_id": msg.get("grouped_id"),
				"is_grouped": bool(msg.get("grouped_id")),
				"group_item_count": len(msg.get("message_ids", [])),
				"text_preview": msg["text_preview"],
			}
			for msg in media_messages
		]
		
		with open(output_file, "w", encoding="utf-8") as f:
			json.dump(messages_for_json, f, ensure_ascii=False, indent=2)
		print(f"\nMedia messages saved to {output_file}")


if __name__ == "__main__":
	asyncio.run(main())
