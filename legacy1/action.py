import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

from telegram_service import (
	parse_channels,
	parse_channel_ids,
	get_required_env,
	resolve_targets,
	poll_once,
)
from summary_service import create_gemini_model
from facebook_service import post_to_facebook


load_dotenv()


api_id = int(get_required_env("TELEGRAM_API_ID"))
api_hash = get_required_env("TELEGRAM_API_HASH")
session_name = os.getenv("TELEGRAM_SESSION_NAME", "telethon_session").strip() or "telethon_session"

channel_usernames = parse_channels(os.getenv("TELEGRAM_CHANNEL_USERNAMES", "vietnam_wallstreet"))

raw_channel_ids = os.getenv("TELEGRAM_CHANNEL_IDS", "")
single_channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
if single_channel_id:
	raw_channel_ids = f"{raw_channel_ids},{single_channel_id}" if raw_channel_ids else single_channel_id

channel_ids = parse_channel_ids(raw_channel_ids)

window_seconds = int(os.getenv("TELEGRAM_WINDOW_SECONDS", "7200"))
fetch_limit = int(os.getenv("TELEGRAM_FETCH_LIMIT", "400"))

gemini_model = create_gemini_model()
client = TelegramClient(session_name, api_id, api_hash)


async def main() -> None:
	print("Action: Running single poll cycle...")
	print(f"Channel usernames: {', '.join(channel_usernames) if channel_usernames else '(none)'}")
	print(f"Channel IDs: {', '.join(map(str, channel_ids)) if channel_ids else '(none)'}")
	print(f"Time window: {window_seconds} seconds")
	print(f"Fetch limit: {fetch_limit}")

	await client.start()
	
	targets = await resolve_targets(client, channel_usernames, channel_ids)
	if not targets:
		print("[ERROR] No valid channel targets found. Check TELEGRAM_CHANNEL_USERNAMES / TELEGRAM_CHANNEL_ID(S).")
		return

	print("Resolved channels:")
	for target in targets:
		name = getattr(target, "title", None) or getattr(target, "username", None) or str(getattr(target, "id", "unknown"))
		print(f"- {name} (id: {getattr(target, 'id', 'unknown')})")

	seen_message_ids: dict[int, set[int]] = {}
	summary, message_count = await poll_once(
		client=client,
		gemini_model=gemini_model,
		targets=targets,
		seen_message_ids=seen_message_ids,
		window_seconds=window_seconds,
		fetch_limit=fetch_limit,
	)
	post_to_facebook(summary)
	print("Action: Poll cycle complete.")


if __name__ == "__main__":
	asyncio.run(main())
