"""Clone messages from a single Telegram channel and log them."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from telethon import TelegramClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

from services.telegram import clone_messages_from_channels


load_dotenv()

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_required_env(name: str) -> str:
	value = os.getenv(name, "").strip()
	if not value:
		raise ValueError(f"Missing required environment variable: {name}")
	return value


def parse_channel_id(raw: str) -> Optional[int]:
	if not raw:
		return None
	try:
		return int(raw)
	except ValueError:
		logger.warning("Invalid TELEGRAM_CHANNEL_2_ID: %s", raw)
		return None


def preview(text: str, limit: int = 120) -> str:
	text = (text or "").strip().replace("\n", " ")
	if len(text) <= limit:
		return text
	return f"{text[:limit]}..."


api_id = int(get_required_env("TELEGRAM_API_ID"))
api_hash = get_required_env("TELEGRAM_API_HASH")
session_name = os.getenv("TELEGRAM_SESSION_NAME", "telethon_session").strip() or "telethon_session"

channel_username = os.getenv("TELEGRAM_CHANNEL_2_USERNAME", "").strip()
channel_id = parse_channel_id(os.getenv("TELEGRAM_CHANNEL_2_ID", "").strip())

window_seconds = int(os.getenv("TELEGRAM_WINDOW_SECONDS", "3600"))
fetch_limit = int(os.getenv("TELEGRAM_FETCH_LIMIT", "200"))
content_filter = os.getenv("TELEGRAM_CONTENT_FILTER", "both").strip().lower() or "both"

client = TelegramClient(session_name, api_id, api_hash)


async def main() -> None:
	channel_usernames = [channel_username] if channel_username else []
	channel_ids = [channel_id] if channel_id is not None else []

	if not channel_usernames and not channel_ids:
		raise ValueError("Set TELEGRAM_CHANNEL_2_USERNAME or TELEGRAM_CHANNEL_2_ID")

	logger.info("Cloning messages from channel 1")
	logger.info("Content filter: %s", content_filter)
	logger.info("Window seconds: %s", window_seconds)
	logger.info("Fetch limit: %s", fetch_limit)

	await client.start()
	results = await clone_messages_from_channels(
		client,
		channel_usernames=channel_usernames,
		channel_ids=channel_ids,
		window_seconds=window_seconds,
		fetch_limit=fetch_limit,
		content_filter=content_filter,
	)

	logger.info("Cloned %s message(s)", len(results))
	for item in results:
		message_id = item.get("message_id")
		media_types = ", ".join(item.get("media_types", [])) or "none"
		text_preview = preview(item.get("text", ""))
		logger.info("%s | media=%s | text=%s", message_id, media_types, text_preview)


if __name__ == "__main__":
	asyncio.run(main())
