"""Telegram helpers for cloning messages with optional media filtering."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo, PeerChannel


logger = logging.getLogger(__name__)


def parse_channels(raw: str) -> list[str]:
	"""Parse a comma-separated list of channel usernames."""
	return [channel.strip() for channel in raw.split(",") if channel.strip()]


def parse_channel_ids(raw: str) -> list[int]:
	"""Parse a comma-separated list of channel IDs."""
	ids: list[int] = []
	for value in raw.split(","):
		item = value.strip()
		if not item:
			continue
		try:
			ids.append(int(item))
		except ValueError:
			logger.warning("Skip invalid channel id: %s", item)
	return ids


def to_peer_channel_id(chat_id: int) -> int:
	"""Normalize chat IDs to PeerChannel-compatible IDs."""
	if chat_id < 0:
		as_text = str(chat_id)
		if as_text.startswith("-100"):
			return int(as_text[4:])
		return abs(chat_id)
	return chat_id


async def resolve_targets(
	client: TelegramClient,
	channel_usernames: list[str],
	channel_ids: list[int],
) -> list[object]:
	"""Resolve channel usernames and IDs into Telethon entities."""
	targets: list[object] = []
	seen_entity_ids: set[int] = set()

	for username in channel_usernames:
		lookup = username if username.startswith("@") else f"@{username}"
		try:
			entity = await client.get_entity(lookup)
			entity_id = getattr(entity, "id", None)
			if entity_id is not None and entity_id in seen_entity_ids:
				continue
			if entity_id is not None:
				seen_entity_ids.add(entity_id)
			targets.append(entity)
		except Exception as error:
			logger.warning("Cannot resolve username %s: %s", lookup, error)

	for chat_id in channel_ids:
		try:
			peer = PeerChannel(to_peer_channel_id(chat_id))
			entity = await client.get_entity(peer)
			entity_id = getattr(entity, "id", None)
			if entity_id is not None and entity_id in seen_entity_ids:
				continue
			if entity_id is not None:
				seen_entity_ids.add(entity_id)
			targets.append(entity)
		except Exception as error:
			logger.warning("Cannot resolve channel id %s: %s", chat_id, error)

	return targets


def _message_text(message: object) -> str:
	return (getattr(message, "raw_text", None) or getattr(message, "message", None) or "").strip()


def _extract_document_metadata(document: object) -> dict[str, Any]:
	file_name = None
	for attr in getattr(document, "attributes", []) or []:
		file_name = getattr(attr, "file_name", None) or file_name
	return {
		"mime_type": getattr(document, "mime_type", None),
		"size": getattr(document, "size", None),
		"file_name": file_name,
	}


def _detect_media_type(message: object) -> str:
	media = getattr(message, "media", None)
	if not media:
		return "none"

	media_class_name = media.__class__.__name__.lower()
	if "photo" in media_class_name:
		return "photo"
	if "video" in media_class_name:
		return "video"
	if "audio" in media_class_name:
		return "audio"
	if "voice" in media_class_name:
		return "voice"

	document = getattr(media, "document", None)
	if document:
		for attr in getattr(document, "attributes", []) or []:
			if isinstance(attr, DocumentAttributeVideo):
				return "video"
			if isinstance(attr, DocumentAttributeAudio):
				return "audio" if not getattr(attr, "voice", False) else "voice"
		return "document"

	return "unknown"


def _extract_media_info(message: object) -> list[dict[str, Any]]:
	media = getattr(message, "media", None)
	if not media:
		return []

	media_type = _detect_media_type(message)
	document = getattr(media, "document", None)
	metadata = _extract_document_metadata(document) if document else {}

	return [
		{
			"message_id": getattr(message, "id", None),
			"type": media_type,
			"mime_type": metadata.get("mime_type"),
			"file_name": metadata.get("file_name"),
			"size": metadata.get("size"),
		}
	]


def _passes_filter(has_text: bool, has_media: bool, content_filter: str) -> bool:
	if content_filter == "text":
		return has_text
	if content_filter == "media":
		return has_media
	return has_text or has_media


def _format_message_entry(
	message: object,
	*,
	chat_id: int,
	chat_title: Optional[str],
	chat_username: Optional[str],
) -> dict[str, Any]:
	text = _message_text(message)
	media = _extract_media_info(message)
	media_types = [item["type"] for item in media]
	grouped_id = getattr(message, "grouped_id", None)
	date = getattr(message, "date", None)

	return {
		"message_id": getattr(message, "id", None),
		"message_ids": [getattr(message, "id", None)],
		"grouped_id": grouped_id,
		"chat_id": chat_id,
		"chat_title": chat_title,
		"chat_username": chat_username,
		"date": date.astimezone(timezone.utc).isoformat() if date else None,
		"text": text,
		"has_text": bool(text),
		"media": media,
		"media_types": media_types,
		"has_media": bool(media),
		"is_grouped": bool(grouped_id),
	}


def _merge_group_entry(group: dict[str, Any], entry: dict[str, Any]) -> None:
	group["message_ids"].extend(entry.get("message_ids", []))
	group["media"].extend(entry.get("media", []))
	for media_type in entry.get("media_types", []):
		if media_type not in group["media_types"]:
			group["media_types"].append(media_type)
	if not group.get("text") and entry.get("text"):
		group["text"] = entry["text"]
		group["has_text"] = True
	group["has_media"] = bool(group["media"])


async def clone_messages(
	client: TelegramClient,
	targets: Iterable[object],
	*,
	window_seconds: Optional[int] = None,
	fetch_limit: int = 200,
	content_filter: str = "both",
) -> list[dict[str, Any]]:
	"""
	Clone recent messages with text and media info from the given targets.

	Args:
		client: Telegram client instance.
		targets: Resolved channel entities.
		window_seconds: Optional look-back window in seconds.
		fetch_limit: Max messages per target.
		content_filter: "text", "media", or "both".
	"""
	window_start = None
	if window_seconds is not None:
		window_start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)

	results: list[dict[str, Any]] = []
	grouped: dict[int, dict[str, Any]] = {}

	for target in targets:
		try:
			messages = await client.get_messages(target, limit=fetch_limit)
		except Exception as error:
			logger.warning("get_messages failed for %s: %s", getattr(target, "id", "unknown"), error)
			continue

		if not messages:
			continue

		chat_id = int(getattr(target, "id", 0) or 0)
		chat_title = getattr(target, "title", None)
		chat_username = getattr(target, "username", None)

		recent_messages = [
			message
			for message in reversed(messages)
			if not window_start or (message.date and message.date >= window_start)
		]

		for message in recent_messages:
			entry = _format_message_entry(
				message,
				chat_id=chat_id,
				chat_title=chat_title,
				chat_username=chat_username,
			)

			grouped_id = entry.get("grouped_id")
			if grouped_id:
				group = grouped.get(grouped_id)
				if not group:
					grouped[grouped_id] = entry
				else:
					_merge_group_entry(group, entry)
				continue

			if _passes_filter(entry["has_text"], entry["has_media"], content_filter):
				results.append(entry)

	for group in grouped.values():
		if _passes_filter(group.get("has_text", False), group.get("has_media", False), content_filter):
			results.append(group)

	return results


async def clone_messages_from_channels(
	client: TelegramClient,
	*,
	channel_usernames: list[str],
	channel_ids: list[int],
	window_seconds: Optional[int] = None,
	fetch_limit: int = 200,
	content_filter: str = "both",
) -> list[dict[str, Any]]:
	"""Resolve channels and clone messages with the same options as clone_messages."""
	targets = await resolve_targets(client, channel_usernames, channel_ids)
	if not targets:
		logger.warning("No valid channel targets found")
		return []
	return await clone_messages(
		client,
		targets,
		window_seconds=window_seconds,
		fetch_limit=fetch_limit,
		content_filter=content_filter,
	)
