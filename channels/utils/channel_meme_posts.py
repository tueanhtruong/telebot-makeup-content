"""Posting helpers for channelMeme."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from telethon import TelegramClient

from services.facebook import upload_feed, upload_feed_with_images, upload_video
from tiktok.utils.api import upload_video_to_tiktok
from tiktok.utils.telegram_media import pick_video_files
from tiktok.utils.token import (
	is_token_expired,
	load_token_from_file,
	refresh_access_token,
	save_token_to_file,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)
_LAST_TIKTOK_UPLOAD_AT: float | None = None


async def _wait_for_tiktok_cooldown(delay_seconds: int = 8) -> None:
	"""Keep TikTok uploads spaced apart across the whole run."""
	global _LAST_TIKTOK_UPLOAD_AT

	if _LAST_TIKTOK_UPLOAD_AT is None:
		return

	elapsed = time.monotonic() - _LAST_TIKTOK_UPLOAD_AT
	if elapsed < delay_seconds:
		remaining = delay_seconds - elapsed
		logger.info("Waiting %.1fs before next TikTok upload", remaining)
		await asyncio.sleep(remaining)


async def download_message_media(
	client: TelegramClient,
	raw_message: object,
	message_ids: list[int],
	output_dir: str = "/tmp/telegram_media",
) -> list[str]:
	"""Download media files from all messages in a group."""
	media_paths: list[str] = []

	try:
		Path(output_dir).mkdir(parents=True, exist_ok=True)

		chat_id = getattr(raw_message, "chat_id", None)
		if not chat_id:
			chat_id = getattr(raw_message, "peer_id", None)

		if not chat_id:
			logger.warning("Could not determine chat_id from message")
			return media_paths

		for message_id in message_ids:
			try:
				messages = await client.get_messages(chat_id, ids=[message_id])
				if not messages:
					logger.warning("Could not fetch message %s", message_id)
					continue

				msg = messages[0]
				media = getattr(msg, "media", None)
				if not media:
					logger.debug("Message %s has no media", message_id)
					continue

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


def _resolve_tiktok_token_file() -> str:
	token_file = os.getenv("TIKTOK_TOKEN_FILE", "./tiktok/auth-token.json").strip() or "./tiktok/auth-token.json"
	token_path = Path(token_file)
	if not token_path.is_absolute():
		token_path = ROOT_DIR / token_path
	return str(token_path)


def _refresh_tiktok_token_if_needed(token_data: Optional[dict[str, Any]], token_file: str) -> Optional[dict[str, Any]]:
	if not token_data:
		return None

	if not is_token_expired(token_data):
		return token_data

	refresh_token_value = (token_data.get("refresh_token") or "").strip()
	client_key = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
	client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()

	if not refresh_token_value:
		logger.warning("TikTok token expired and refresh token is missing")
		return None

	if not client_key or not client_secret:
		logger.warning("TikTok token expired but TIKTOK_CLIENT_KEY/TIKTOK_CLIENT_SECRET are missing")
		return None

	try:
		refreshed = refresh_access_token(refresh_token_value, client_key, client_secret)
		if refreshed and refreshed.get("access_token"):
			save_token_to_file(refreshed, token_file)
			logger.info("TikTok access token refreshed")
			return refreshed
		logger.warning("Failed to refresh TikTok access token")
		return None
	except Exception as error:
		logger.warning("Failed to refresh TikTok token: %s", error)
		return None



def _load_tiktok_access_token() -> tuple[Optional[str], Optional[dict[str, Any]], str]:
	token_file = _resolve_tiktok_token_file()
	token_data = load_token_from_file(token_file)
	if not token_data:
		logger.info("TikTok token file not found or invalid at %s; skip TikTok upload", token_file)
		return None, None, token_file

	token_data = _refresh_tiktok_token_if_needed(token_data, token_file)
	if not token_data:
		return None, None, token_file

	access_token = (token_data.get("access_token") or "").strip()
	if not access_token:
		logger.warning("TikTok access token missing in token file")
		return None, token_data, token_file

	return access_token, token_data, token_file


async def _post_videos_to_tiktok(
	text: str,
	video_paths: list[str],
	delay_seconds: int = 8,
	max_attempts: int = 3,
) -> list[str]:
	"""Post local videos to TikTok, retrying failed uploads and pacing successes."""
	if not video_paths:
		return []

	access_token, token_data, token_file = _load_tiktok_access_token()
	if not access_token:
		return []

	posted_ids: list[str] = []
	for video_path in video_paths:
		await _wait_for_tiktok_cooldown(delay_seconds)
		publish_id: Optional[str] = None
		attempt = 0

		while attempt < max_attempts and not publish_id:
			attempt += 1
			try:
				publish_id = upload_video_to_tiktok(video_path, text, access_token)
				if publish_id:
					break

				logger.warning(
					"TikTok upload attempt %d/%d returned no publish_id for %s",
					attempt,
					max_attempts,
					video_path,
				)
			except Exception as error:
				message = str(error)
				if "Token expired" in message:
					token_data = _refresh_tiktok_token_if_needed(token_data, token_file)
					if not token_data:
						logger.warning("TikTok token refresh failed while uploading %s", video_path)
						break

					access_token = (token_data.get("access_token") or "").strip()
					if not access_token:
						logger.warning("TikTok refreshed token did not return access_token")
						break

					logger.info("Retrying TikTok upload after token refresh for %s", video_path)
					continue

				if "Scope not authorized" in message or "Unaudited app restriction" in message:
					logger.warning("TikTok upload blocked for %s: %s", video_path, message)
					break

				if attempt < max_attempts:
					logger.warning(
						"TikTok upload attempt %d/%d failed for %s: %s",
						attempt,
						max_attempts,
						video_path,
						message,
					)
				else:
					logger.warning("TikTok upload failed for %s after %d attempts: %s", video_path, max_attempts, message)

		if publish_id:
			posted_ids.append(publish_id)
			logger.info("Posted video to TikTok: %s", publish_id)
			_LAST_TIKTOK_UPLOAD_AT = time.monotonic()

	return posted_ids


async def post_to_tiktok(
	text: str,
	message: dict[str, Any],
	raw_telegram_message: object,
	client: TelegramClient,
) -> Optional[str]:
	"""Upload videos and post to TikTok."""
	if not text or not text.strip():
		logger.warning("Empty text, skipping TikTok post")
		return None

	media_types = message.get("media_types", [])
	if not media_types or media_types[0] == "none":
		logger.info("No media found, skipping TikTok post")
		return None

	video_types = [t for t in media_types if t == "video"]
	if not video_types:
		logger.info("No video media found, skipping TikTok post")
		return None

	message_ids = message.get("message_ids", [])

	try:
		logger.info("Processing %d video(s) for TikTok", len(video_types))
		media_paths = await download_message_media(client, raw_telegram_message, message_ids)
		video_paths = pick_video_files(media_paths)

		if not video_paths:
			logger.warning("Failed to download video files for TikTok")
			return None

		tiktok_posted_ids = await _post_videos_to_tiktok(text, video_paths)
		if tiktok_posted_ids:
			logger.info("Posted %d video(s) to TikTok", len(tiktok_posted_ids))
			return tiktok_posted_ids[0]

		logger.warning("Failed to post videos to TikTok")
		return None
	except Exception as error:
		logger.error("Error posting to TikTok: %s", error)
		return None


async def post_to_facebook(
	text: str,
	message: dict[str, Any],
	raw_telegram_message: object,
	client: TelegramClient,
) -> Optional[str]:
	"""Upload media and post to Facebook."""
	if not text or not text.strip():
		logger.warning("Empty text, skipping Facebook post")
		return None

	media_types = message.get("media_types", [])
	if not media_types or media_types[0] == "none":
		return upload_feed(text)

	message_ids = message.get("message_ids", [])

	try:
		video_types = [t for t in media_types if t == "video"]
		photo_types = [t for t in media_types if t == "photo"]

		posted_ids: list[str] = []

		if video_types:
			logger.info("Processing %d video(s)", len(video_types))
			media_paths = await download_message_media(client, raw_telegram_message, message_ids)
			video_paths = pick_video_files(media_paths)

			if video_paths:
				for video_path in video_paths:
					try:
						post_id = upload_video(video_path, text)
						if post_id:
							logger.info("Posted video to Facebook: %s", post_id)
							posted_ids.append(post_id)
						else:
							logger.warning("Failed to upload video: %s", video_path)
					except Exception as error:
						logger.error("Error uploading video %s: %s", video_path, error)
			else:
				logger.warning("Failed to download videos")

		if photo_types:
			logger.info("Processing %d photo(s)", len(photo_types))
			media_paths = await download_message_media(client, raw_telegram_message, message_ids)

			if media_paths:
				try:
					post_id = upload_feed_with_images(text, media_paths)
					if post_id:
						logger.info("Posted feed with %d image(s) to Facebook: %s", len(media_paths), post_id)
						posted_ids.append(post_id)
					else:
						logger.warning("Failed to post images to Facebook")
				except Exception as error:
					logger.error("Error uploading images: %s", error)
			else:
				logger.warning("Failed to download images")

		other_types = [t for t in media_types if t not in ["video", "photo", "none"]]
		if other_types and not posted_ids:
			logger.info("Media type(s) %s not supported for Facebook, posting text only", other_types)
			post_id = upload_feed(text)
			if post_id:
				posted_ids.append(post_id)

		if not posted_ids:
			logger.warning("No media posted, posting text only as fallback")
			post_id = upload_feed(text)
			if post_id:
				posted_ids.append(post_id)

		return posted_ids[0] if posted_ids else None

	except Exception as error:
		logger.error("Error posting to Facebook: %s", error)
		return upload_feed(text)
