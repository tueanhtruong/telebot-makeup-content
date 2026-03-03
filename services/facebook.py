"""Facebook Graph API helpers for posting and listing Page content."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import requests


GRAPH_API_VERSION = os.getenv("FACEBOOK_API_VERSION", "v25.0").strip() or "v25.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
GRAPH_VIDEO_BASE_URL = f"https://graph-video.facebook.com/{GRAPH_API_VERSION}"

logger = logging.getLogger(__name__)


def get_facebook_token() -> Optional[str]:
	"""Return the Facebook page access token from env, if present."""
	token = os.getenv("FACEBOOK_TOKEN", "").strip()
	return token or None


def get_facebook_page_id() -> Optional[str]:
	"""Return the Facebook Page ID from env, if present."""
	page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
	return page_id or None


def _require_env(token: Optional[str], page_id: Optional[str]) -> bool:
	if not token:
		logger.warning("Facebook call skipped: FACEBOOK_TOKEN is missing")
		return False
	if not page_id:
		logger.warning("Facebook call skipped: FACEBOOK_PAGE_ID is missing")
		return False
	return True


def _post(url: str, data: dict[str, Any], files: dict[str, Any] | None = None) -> dict[str, Any] | None:
	try:
		response = requests.post(url, data=data, files=files, timeout=60)
		if response.status_code != 200:
			logger.error("Facebook API error %s: %s", response.status_code, response.text)
			return None
		return response.json()
	except requests.RequestException as error:
		logger.error("Facebook API request failed: %s", error)
		return None


def _get(url: str, params: dict[str, Any]) -> dict[str, Any] | None:
	try:
		response = requests.get(url, params=params, timeout=60)
		if response.status_code != 200:
			logger.error("Facebook API error %s: %s", response.status_code, response.text)
			return None
		return response.json()
	except requests.RequestException as error:
		logger.error("Facebook API request failed: %s", error)
		return None


def upload_feed(message: str, *, token: Optional[str] = None, page_id: Optional[str] = None) -> Optional[str]:
	"""Publish a text-only feed post to the Facebook Page."""
	token = token or get_facebook_token()
	page_id = page_id or get_facebook_page_id()
	if not _require_env(token, page_id):
		return None

	url = f"{GRAPH_BASE_URL}/{page_id}/feed"
	payload = {
		"access_token": token,
		"message": message,
	}
	result = _post(url, payload)
	if not result:
		return None
	return result.get("id")


def _upload_unpublished_photo(
	image_path: str,
	*,
	token: str,
	page_id: str,
) -> Optional[str]:
	url = f"{GRAPH_BASE_URL}/{page_id}/photos"
	try:
		with open(image_path, "rb") as image_file:
			files = {"source": image_file}
			data = {
				"access_token": token,
				"published": "false",
			}
			result = _post(url, data, files=files)
			if not result:
				return None
			return result.get("id")
	except OSError as error:
		logger.error("Failed to read image %s: %s", image_path, error)
		return None


def upload_feed_with_images(
	message: str,
	image_paths: list[str],
	*,
	token: Optional[str] = None,
	page_id: Optional[str] = None,
) -> Optional[str]:
	"""Publish a feed post with multiple local images attached."""
	token = token or get_facebook_token()
	page_id = page_id or get_facebook_page_id()
	if not _require_env(token, page_id):
		return None
	if not image_paths:
		logger.warning("No images provided for multi-image post")
		return None

	media_fbids: list[str] = []
	for image_path in image_paths:
		media_id = _upload_unpublished_photo(image_path, token=token, page_id=page_id)
		if not media_id:
			logger.warning("Skipping image upload failure: %s", image_path)
			continue
		media_fbids.append(media_id)

	if not media_fbids:
		logger.error("All image uploads failed; no post created")
		return None

	url = f"{GRAPH_BASE_URL}/{page_id}/feed"
	attached_media = [{"media_fbid": media_id} for media_id in media_fbids]
	payload = {
		"access_token": token,
		"message": message,
		"attached_media": json_dumps(attached_media),
	}
	result = _post(url, payload)
	if not result:
		return None
	return result.get("id")


def upload_video(
	video_path: str,
	description: str,
	*,
	title: str = "",
	token: Optional[str] = None,
	page_id: Optional[str] = None,
) -> Optional[str]:
	"""Upload a video to the Page with an optional title and description."""
	token = token or get_facebook_token()
	page_id = page_id or get_facebook_page_id()
	if not _require_env(token, page_id):
		return None

	url = f"{GRAPH_VIDEO_BASE_URL}/{page_id}/videos"
	try:
		with open(video_path, "rb") as video_file:
			files = {"source": video_file}
			data = {
				"access_token": token,
				"description": description,
			}
			if title:
				data["title"] = title
			result = _post(url, data, files=files)
			if not result:
				return None
			return result.get("id")
	except OSError as error:
		logger.error("Failed to read video %s: %s", video_path, error)
		return None


def add_comment(
	object_id: str,
	message: str,
	*,
	token: Optional[str] = None,
) -> Optional[str]:
	"""Add a comment to a feed post or video by object ID."""
	token = token or get_facebook_token()
	if not token:
		logger.warning("Facebook call skipped: FACEBOOK_TOKEN is missing")
		return None

	url = f"{GRAPH_BASE_URL}/{object_id}/comments"
	payload = {
		"access_token": token,
		"message": message,
	}
	result = _post(url, payload)
	if not result:
		return None
	return result.get("id")


def list_page_feeds(
	*,
	limit: int = 10,
	token: Optional[str] = None,
	page_id: Optional[str] = None,
) -> list[dict[str, Any]]:
	"""Return a compact list of feed posts for the Page."""
	token = token or get_facebook_token()
	page_id = page_id or get_facebook_page_id()
	if not _require_env(token, page_id):
		return []

	url = f"{GRAPH_BASE_URL}/{page_id}/feed"
	params = {
		"access_token": token,
		"fields": "id,message,story,created_time,permalink_url",
		"limit": max(1, min(limit, 100)),
	}
	result = _get(url, params)
	if not result:
		return []
	return result.get("data", [])


def list_page_videos(
	*,
	limit: int = 10,
	token: Optional[str] = None,
	page_id: Optional[str] = None,
) -> list[dict[str, Any]]:
	"""Return a compact list of videos for the Page."""
	token = token or get_facebook_token()
	page_id = page_id or get_facebook_page_id()
	if not _require_env(token, page_id):
		return []

	url = f"{GRAPH_BASE_URL}/{page_id}/videos"
	params = {
		"access_token": token,
		"fields": "id,description,created_time,permalink_url",
		"limit": max(1, min(limit, 100)),
	}
	result = _get(url, params)
	if not result:
		return []
	return result.get("data", [])


def json_dumps(value: Any) -> str:
	"""Light wrapper to avoid importing json at module import time in hot paths."""
	import json

	return json.dumps(value)
