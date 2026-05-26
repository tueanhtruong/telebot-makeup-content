"""Clone messages from a single Telegram channel and log them."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from telethon import TelegramClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

from services.llm import create_llm_client
from channels.commonsHelpers import load_channel_runtime_config, load_dotenv_runtime_path
from services.telegram import clone_messages_from_channels_with_objects
from channels.utils.channel_meme_posts import post_to_facebook, post_to_tiktok


dotenv_file_path = load_dotenv_runtime_path(default_env_path=".env.local")
dotenv_path = Path(dotenv_file_path)
if not dotenv_path.is_absolute():
	dotenv_path = ROOT_DIR / dotenv_path
load_dotenv(dotenv_path=dotenv_path)

print(f"Using dotenv file: {dotenv_path}")
print(f"Loaded Stage: {os.getenv('STAGE') if os.getenv('STAGE') else 'not set'}")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_required_env(name: str) -> str:
	value = os.getenv(name, "").strip()
	if not value:
		raise ValueError(f"Missing required environment variable: {name}")
	return value


def preview(text: str, limit: int = 12000) -> str:
	text = (text or "").strip().replace("\n", " ")
	if len(text) <= limit:
		return text
	return f"{text[:limit]}..."


def _remove_tags(text: str) -> str:
	"""Remove JUST IN: from text for cleaner previews."""
	cleaned = re.sub(r"JUST IN:\s*", "", text or "", flags=re.IGNORECASE)
	"""Remove hashtags and @mentions from text for cleaner previews."""
	cleaned = re.sub(r"#[\w-]+", "", cleaned)
	cleaned = re.sub(r"@[\w-]+", "", cleaned)
	cleaned = re.sub(r"\s{2,}", " ", cleaned)
	return cleaned.strip()

def _remove_dummy_text(text: str) -> str:
	"""Remove some dummy text that often appears in the end of Telegram messages."""
	# Remove phrases like "Nội dung dịch" or "1. Nội dung dịch"
	cleaned = re.sub(r"(?:\d+\.*\s*)?Nội dung dịch*:?\s*", "", text or "", flags=re.IGNORECASE)
	cleaned = re.sub(r"(?:\d+\.*\s*)?Hashtag*:?\s*", "", cleaned, flags=re.IGNORECASE)
	cleaned = re.sub(r"(?:\d+\.*\s*)?CTA*:?\s*", "", cleaned, flags=re.IGNORECASE)
	cleaned = re.sub(r"\*\*\*\**\s*", "", cleaned, flags=re.IGNORECASE)
	return cleaned.strip()


def _remove_links_content(text: str) -> str:
	"""Remove link content, including markdown display text and URLs."""
	cleaned = text or ""
	# Remove markdown links like [display text](https://example.com)
	cleaned = re.sub(r"\[[^\]]*\]\([^\)]*\)", "", cleaned)
	# Remove HTML links like <a href="...">display text</a>
	cleaned = re.sub(r"<a\s+[^>]*>.*?</a>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
	# Remove bare URLs
	cleaned = re.sub(r"(?:https?://|www\.)\S+", "", cleaned, flags=re.IGNORECASE)
	cleaned = re.sub(r"\s{2,}", " ", cleaned)
	return cleaned.strip()


def _get_text_except_last_line_if_link(text: str) -> str:
	"""Check if text includes a link. If yes, return text except the last line. If no, return full text.
	
	Args:
		text: The text to check for links
	
	Returns:
		Text except the last line if link detected, otherwise full text
	"""
	if not text:
		return text
	
	# Pattern to match various link formats
	link_pattern = r"(?:https?://|www\.)\S+|\[[^\]]*\]\([^\)]*\)|<a\s+[^>]*>.*?</a>"
	
	if re.search(link_pattern, text, flags=re.IGNORECASE | re.DOTALL):
		# Link detected - return text except the last line
		lines = text.split('\n')
		return '\n'.join(lines[:-1]) if len(lines) > 1 else text
	else:
		# No link detected - return full text
		return text


api_id = int(get_required_env("TELEGRAM_API_ID"))
api_hash = get_required_env("TELEGRAM_API_HASH")
session_name = os.getenv("TELEGRAM_SESSION_NAME", "telethon_session").strip() or "telethon_session"

runtime_config = load_channel_runtime_config(
	default_content_filter="both",
	logger=logger,
)

channel_username = runtime_config.channel_username
channel_id = runtime_config.channel_id

window_seconds = runtime_config.window_seconds
fetch_limit = runtime_config.fetch_limit
content_filter = runtime_config.content_filter
llm_provider = runtime_config.llm_provider
start_date = runtime_config.start_date
end_date = runtime_config.end_date

client = TelegramClient(session_name, api_id, api_hash)

def _create_sanitization_prompt(text: str, channelName: str = '') -> str:
	"""Create a prompt to ask LLM to sanitize text."""
	return f"""
NHIỆM VỤ
Bạn là chuyên gia dịch thuật cho những nội dung ngắn vui vẻ. Hãy dịch nội dung văn bản dưới đây sang tiếng Việt nếu có.
LỌC DỮ LIỆU:
- Loại bỏ thông tin không liên quan hoặc trùng lặp
- Loại bỏ ký tự đặc biệt, hashtag, @mentions, liên kết (URLs).
ĐỊNH DẠNG ĐẦU RA: 1 đoạn văn gồm các phần sau
	1. Nội dung dịch
		- Viết lại nội dung tiếng Việt nếu có một cách tự nhiên, không có từ ngữ nhạy cảm
		- Tách thành các đoạn ngắn nếu dài, mỗi đoạn 2–4 câu, thêm dòng trống giữa các đoạn để dễ đọc
	2. CTA
		- Đặt cuối bài, cách nội dung 1 dòng trống
		- Viết một câu kêu gọi theo dõi kênh để xem thêm nhiều nội dung hài hước
	3. Hashtag
		- Đặt cuối bài, cách nội dung 1 dòng trống
		- Chỉ dùng hashtag phổ biến, an toàn, viết liền không dấu
---
Nội dung cần dịch:
{text}
"""


async def _sanitize_text_with_llm(text: str, llm_provider: str = "grok") -> Optional[str]:
	"""Use LLM to sanitize the text."""
	if not text or not text.strip():
		return None
	
	try:
		client = create_llm_client(llm_provider)
		prompt = _create_sanitization_prompt(text, channelName=channel_username)
		logger.info("\n" + "="*72)
		logger.info("GENERATED LLM PROMPT:")
		logger.info(prompt)
		logger.info("="*72)
		response = client.ask(prompt)
		
		if not response or not response.text:
			logger.warning("LLM returned no response")
			return None
		
		sanitized = response.text.strip()
		if sanitized:
			logger.info("Text sanitized by %s", response.provider)
			return sanitized
		return None
	except Exception as error:
		logger.error("Failed to sanitize text with %s: %s", llm_provider, error)
		return None


async def main() -> None:
	channel_usernames = [channel_username] if channel_username else []
	channel_ids = [channel_id] if channel_id is not None else []

	if not channel_usernames and not channel_ids:
		raise ValueError("Set TELEGRAM_CHANNEL_6_USERNAME or TELEGRAM_CHANNEL_6_ID")

	logger.info("Cloning messages from channel 2")
	logger.info("Content filter: %s", content_filter)
	logger.info("Window seconds: %s", window_seconds)
	logger.info("Fetch limit: %s", fetch_limit)
	logger.info("Date range: %s -> %s", start_date, end_date)

	await client.start()
	results_with_messages = await clone_messages_from_channels_with_objects(
		client,
		channel_usernames=channel_usernames,
		channel_ids=channel_ids,
		window_seconds=window_seconds,
		fetch_limit=fetch_limit,
		content_filter=content_filter,
		start_date=start_date,
		end_date=end_date,
	)

	logger.info("Cloned %s message(s)", len(results_with_messages))
	
	for cloned_data, raw_message in results_with_messages:
		message_id = cloned_data.get("message_id")
		media_types = ", ".join(cloned_data.get("media_types", [])) or "none"
		raw_text = cloned_data.get("text", "")
		first_line_or_full = _get_text_except_last_line_if_link(raw_text)
		cleaned_raw_text = _remove_links_content(first_line_or_full)
		text_preview = preview(_remove_tags(cleaned_raw_text))
		
		logger.info(
			"[MSG %s] Original text preview: %s | media=%s",
			message_id,
			text_preview,
			media_types,
		)
		if media_types and media_types != "none":
			logger.info("[MSG %s] Detected media types: %s", message_id, media_types)
			# For media posts, we will rely more on LLM to sanitize and summarize the text.
			sanitized_text = text_preview
			if sanitized_text and sanitized_text.strip():
				sanitized_text = await _sanitize_text_with_llm(_remove_tags(sanitized_text), llm_provider=llm_provider)
				sanitized_text = _remove_dummy_text(sanitized_text or "")
				print(f"\n{'='*72}\nSanitized Text:\n{sanitized_text}\n{'='*72}")

			facebook_id = await post_to_facebook(sanitized_text, cloned_data, raw_message, client)
			if facebook_id:
				logger.info("[MSG %s] Successfully posted to Facebook: %s", message_id, facebook_id)
			else:
				logger.warning("[MSG %s] Failed to post to Facebook", message_id)

			# tiktok_id = await post_to_tiktok(sanitized_text, cloned_data, raw_message, client)
			# if tiktok_id:
			# 	logger.info("[MSG %s] Successfully posted to TikTok: %s", message_id, tiktok_id)
			# else:
			# 	logger.warning("[MSG %s] Failed to post to TikTok", message_id)

		else:
			logger.warning("[MSG %s] No text content to process", message_id)


if __name__ == "__main__":
	asyncio.run(main())
