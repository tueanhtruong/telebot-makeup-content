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
from services.facebook import upload_feed, upload_feed_with_images, upload_video
from services.telegram import clone_messages_from_channels_with_objects


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
		logger.warning("Invalid TELEGRAM_CHANNEL_3_ID: %s", raw)
		return None


def preview(text: str, limit: int = 1200) -> str:
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


api_id = int(get_required_env("TELEGRAM_API_ID"))
api_hash = get_required_env("TELEGRAM_API_HASH")
session_name = os.getenv("TELEGRAM_SESSION_NAME", "telethon_session").strip() or "telethon_session"

channel_username = os.getenv("TELEGRAM_CHANNEL_3_USERNAME", "").strip()
channel_id = parse_channel_id(os.getenv("TELEGRAM_CHANNEL_3_ID", "").strip())

window_seconds = int(os.getenv("TELEGRAM_WINDOW_SECONDS", "600"))
fetch_limit = int(os.getenv("TELEGRAM_FETCH_LIMIT", "10"))
content_filter = os.getenv("TELEGRAM_CONTENT_FILTER", "both").strip().lower() or "both"

client = TelegramClient(session_name, api_id, api_hash)

def _create_sanitization_prompt(text: str, channelName: str = '') -> str:
	"""Create a prompt to ask LLM to sanitize text."""
	return f"""
Bạn là một chuyên gia dịch thuật tài chính, kinh tế, chính trị sang tiếng Việt.

LỌC DỮ LIỆU LOẠI BỎ NỘI DUNG:

- thông tin không liên quan, dữ liệu trùng lặp
- liên quan nội bộ chính trị Việt Nam (dù tích cực hay tiêu cực)
- xuyên tạc lịch sử, chủ quyền, vai trò lãnh đạo của Nhà nước VN
- vu khống/xúc phạm tổ chức, cá nhân chưa được xác minh

CẤU TRÚC ĐẦU RA:

	(nội dung đã được dịch)

	Nguồn: t.me/{channelName}

	(hashtag - chỉ sử dụng hashtag an toàn, phổ biến, không bị gắn cờ và viết liền không dấu)

NHỮNG GÌ CẦN TRÁNH:

- Không đưa ra lời khuyên đầu tư hoặc khuyến cáo hành động
- Không phán xét về quyền lợi của các bên (trung lập)
- Không sử dụng từ ngữ có thể bị Facebook gắn cờ
- Không đặt câu hỏi - chỉ kết luận
- Không nhận xét chính trị nội bộ

Nội dung gốc cần dịch:
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


async def _download_message_media(
	client: TelegramClient,
	raw_message: object,
	message_ids: list[int],
	output_dir: str = "/tmp/telegram_media",
) -> list[str]:
	"""Download media files from all messages in a group.
	
	Args:
		client: Telegram client instance
		raw_message: A message object from the group (used to get chat info)
		message_ids: List of all message IDs in the group
		output_dir: Directory to save media files
	
	Returns:
		List of paths to downloaded media files
	"""
	media_paths: list[str] = []
	
	try:
		Path(output_dir).mkdir(parents=True, exist_ok=True)
		
		# Get chat info from the message
		chat_id = getattr(raw_message, "chat_id", None)
		if not chat_id:
			chat_id = getattr(raw_message, "peer_id", None)
		
		if not chat_id:
			logger.warning("Could not determine chat_id from message")
			return media_paths
		
		# Download media from all messages in the group
		for message_id in message_ids:
			try:
				# Fetch the specific message by ID
				messages = await client.get_messages(chat_id, ids=[message_id])
				if not messages:
					logger.warning("Could not fetch message %s", message_id)
					continue
				
				msg = messages[0]
				media = getattr(msg, "media", None)
				
				if not media:
					logger.debug("Message %s has no media", message_id)
					continue
				
				# Download the media
				output_file = await client.download_media(
					msg,
					file=f"{output_dir}/msg_{message_id}",
				)
				
				if output_file:
					media_paths.append(str(output_file))
					logger.info("Downloaded media to %s", output_file)
				else:
					logger.warning("Failed to download media for message %s", message_id)
			
			except Exception as error:
				logger.warning("Failed to download media for message %s: %s", message_id, error)
	
	except Exception as error:
		logger.warning("Failed to setup media download: %s", error)
	
	return media_paths


async def _post_to_facebook(
	text: str,
	message: dict[str, Any],
	raw_telegram_message: object,
	client: TelegramClient,
) -> Optional[str]:
	"""Upload media and post to Facebook.
	
	For videos: post each video separately with text as description
	For photos: group all photos and attach to single feed post with text
	For other media: post text only
	"""
	if not text or not text.strip():
		logger.warning("Empty text, skipping Facebook post")
		return None
	
	media_types = message.get("media_types", [])
	if not media_types or media_types[0] == "none":
		# Text-only post
		return upload_feed(text)
	
	# Get message IDs for grouped media download
	message_ids = message.get("message_ids", [])
	
	try:
		# Separate videos and photos from media_types
		video_types = [t for t in media_types if t == "video"]
		photo_types = [t for t in media_types if t == "photo"]
		
		posted_ids = []
		
		# Handle videos - post each video separately
		if video_types:
			logger.info("Processing %d video(s)", len(video_types))
			media_paths = await _download_message_media(client, raw_telegram_message, message_ids)
			
			if media_paths:
				for video_path in media_paths:
					try:
						post_id = upload_video(video_path, text)
						if post_id:
							logger.info("Posted video to Facebook: %s", post_id)
							posted_ids.append(post_id)
						else:
							logger.warning("Failed to upload video: %s", video_path)
					except Exception as e:
						logger.error("Error uploading video %s: %s", video_path, e)
			else:
				logger.warning("Failed to download videos")
		
		# Handle photos - group all photos into one feed post
		if photo_types:
			logger.info("Processing %d photo(s)", len(photo_types))
			media_paths = await _download_message_media(client, raw_telegram_message, message_ids)
			
			if media_paths:
				try:
					post_id = upload_feed_with_images(text, media_paths)
					if post_id:
						logger.info("Posted feed with %d image(s) to Facebook: %s", len(media_paths), post_id)
						posted_ids.append(post_id)
					else:
						logger.warning("Failed to post images to Facebook")
				except Exception as e:
					logger.error("Error uploading images: %s", e)
			else:
				logger.warning("Failed to download images")
		
		# If only non-video/non-photo media, post text only
		other_types = [t for t in media_types if t not in ["video", "photo", "none"]]
		if other_types and not posted_ids:
			logger.info("Media type(s) %s not supported for Facebook, posting text only", other_types)
			post_id = upload_feed(text)
			if post_id:
				posted_ids.append(post_id)
		
		# If no videos or photos but also no posts yet, post text as fallback
		if not posted_ids:
			logger.warning("No media posted, posting text only as fallback")
			post_id = upload_feed(text)
			if post_id:
				posted_ids.append(post_id)
		
		# Return the first posted ID
		return posted_ids[0] if posted_ids else None
	
	except Exception as error:
		logger.error("Error posting to Facebook: %s", error)
		# Fallback to text-only post
		return upload_feed(text)


# def _remove_prefix(text: str, prefix: str = 'JUST IN:') -> str:
# 	"""Remove a specific prefix from text."""
# 	if text.startswith(prefix):
# 		return text[len(prefix):]
# 	return text

async def main() -> None:
	channel_usernames = [channel_username] if channel_username else []
	channel_ids = [channel_id] if channel_id is not None else []

	if not channel_usernames and not channel_ids:
		raise ValueError("Set TELEGRAM_CHANNEL_3_USERNAME or TELEGRAM_CHANNEL_3_ID")

	logger.info("Cloning messages from channel 2")
	logger.info("Content filter: %s", content_filter)
	logger.info("Window seconds: %s", window_seconds)
	logger.info("Fetch limit: %s", fetch_limit)

	await client.start()
	results_with_messages = await clone_messages_from_channels_with_objects(
		client,
		channel_usernames=channel_usernames,
		channel_ids=channel_ids,
		window_seconds=window_seconds,
		fetch_limit=fetch_limit,
		content_filter=content_filter,
	)

	logger.info("Cloned %s message(s)", len(results_with_messages))
	
	# Determine LLM provider to use
	llm_provider = os.getenv("LLM_PROVIDER", "grok").strip().lower() or "grok"
	
	for cloned_data, raw_message in results_with_messages:
		message_id = cloned_data.get("message_id")
		media_types = ", ".join(cloned_data.get("media_types", [])) or "none"
		raw_text = cloned_data.get("text", "")
		text_preview = preview(_remove_tags(raw_text))
		
		logger.info(
			"[MSG %s] Original text preview: %s | media=%s",
			message_id,
			text_preview,
			media_types,
		)
		
		# Sanitize text using LLM
		# if raw_text and raw_text.strip():
		# 	sanitized_text = await _sanitize_text_with_llm(_remove_tags(raw_text), llm_provider=llm_provider)
		# 	if sanitized_text:
		# 		logger.info(
		# 			"[MSG %s] Sanitized text: %s",
		# 			message_id,
		# 			preview(sanitized_text),
		# 		)
				
		# 		# Post to Facebook with media
		# 		facebook_id = await _post_to_facebook(sanitized_text, cloned_data, raw_message, client)
		# 		if facebook_id:
		# 			logger.info("[MSG %s] Successfully posted to Facebook: %s", message_id, facebook_id)
		# 		else:
		# 			logger.warning("[MSG %s] Failed to post to Facebook", message_id)
		# 	else:
		# 		logger.warning("[MSG %s] Failed to sanitize text", message_id)
		# else:
		# 	logger.warning("[MSG %s] No text content to process", message_id)


if __name__ == "__main__":
	asyncio.run(main())
