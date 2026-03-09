import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

from telegram_service import (
	parse_channels,
	parse_channel_ids,
	get_required_env,
	poll_messages,
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

poll_interval_seconds = int(os.getenv("TELEGRAM_POLL_INTERVAL_SECONDS", "1800"))
window_seconds = int(os.getenv("TELEGRAM_WINDOW_SECONDS", "1800"))
fetch_limit = int(os.getenv("TELEGRAM_FETCH_LIMIT", "200"))

gemini_model = create_gemini_model()
client = TelegramClient(session_name, api_id, api_hash)


async def main() -> None:
	print("Server is polling Telegram channel messages...")
	print(f"Channel usernames: {', '.join(channel_usernames) if channel_usernames else '(none)'}")
	print(f"Channel IDs: {', '.join(map(str, channel_ids)) if channel_ids else '(none)'}")
	print(f"Poll interval: {poll_interval_seconds} seconds")
	print(f"Time window: {window_seconds} seconds")
	print(f"Fetch limit each poll: {fetch_limit}")

	await client.start()
	await poll_messages(
		client=client,
		gemini_model=gemini_model,
		channel_usernames=channel_usernames,
		channel_ids=channel_ids,
		poll_interval_seconds=poll_interval_seconds,
		window_seconds=window_seconds,
		fetch_limit=fetch_limit,
		post_callback=post_to_facebook,
	)


if __name__ == "__main__":
	asyncio.run(main())

