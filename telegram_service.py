import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import PeerChannel

from summary_service import summarize_messages, format_summary_log


def parse_channels(raw: str) -> list[str]:
	return [channel.strip() for channel in raw.split(",") if channel.strip()]


def parse_channel_ids(raw: str) -> list[int]:
	ids: list[int] = []
	for value in raw.split(","):
		item = value.strip()
		if not item:
			continue
		try:
			ids.append(int(item))
		except ValueError:
			print(f"[WARN] Skip invalid channel id: {item}")
	return ids


def normalize_chat_ids(ids: list[int]) -> set[int]:
	normalized: set[int] = set()
	for chat_id in ids:
		normalized.add(chat_id)
		if chat_id > 0:
			normalized.add(int(f"-100{chat_id}"))
	return normalized


def to_peer_channel_id(chat_id: int) -> int:
	if chat_id < 0:
		as_text = str(chat_id)
		if as_text.startswith("-100"):
			return int(as_text[4:])
		return abs(chat_id)
	return chat_id


def get_required_env(name: str) -> str:
	value = os.getenv(name, "").strip()
	if not value:
		raise ValueError(f"Missing required environment variable: {name}")
	return value


async def resolve_targets(
	client: TelegramClient,
	channel_usernames: list[str],
	channel_ids: list[int],
) -> list[object]:
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
			print(f"[WARN] Cannot resolve username {lookup}: {error}")

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
			print(f"[WARN] Cannot resolve channel id {chat_id}: {error}")

	return targets


async def poll_once(
	client: TelegramClient,
	gemini_model: Optional[object],
	targets: list[object],
	seen_message_ids: dict[int, set[int]],
	window_seconds: int,
	fetch_limit: int,
) -> tuple[str, int]:
	"""Execute a single poll cycle and return (summary, message_count)."""
	window_start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
	poll_message_texts: list[str] = []

	for target in targets:
		try:
			messages = await client.get_messages(target, limit=fetch_limit)
		except Exception as error:
			print(f"[WARN] get_messages failed for {getattr(target, 'id', 'unknown')}: {error}")
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

		new_messages = [
			message
			for message in recent_messages
			if message.id and message.id not in seen_message_ids[target_id]
		]

		for message in new_messages:
			timestamp = message.date.astimezone().strftime("%d/%m/%Y %H:%M") if message.date else datetime.now().strftime("%d/%m/%Y %H:%M")
			content = message.raw_text or ""
			print(f"{timestamp} {content}")
			poll_message_texts.append(content)
			seen_message_ids[target_id].add(message.id)

		if len(seen_message_ids[target_id]) > 5000:
			seen_message_ids[target_id] = set(sorted(seen_message_ids[target_id])[-2000:])

	summary = summarize_messages(gemini_model, poll_message_texts)
	print(format_summary_log(summary, len(poll_message_texts)))
	return summary, len(poll_message_texts)


def has_media(message: object) -> bool:
	"""Check if a message contains media (photo, video, or other media types)."""
	return bool(getattr(message, "media", None))


def get_media_types(message: object) -> list[str]:
	"""Extract all media types from a message. Returns list of media types."""
	media_types = []
	
	# Check main message media
	if hasattr(message, "media") and message.media:
		media = message.media
		
		# Check for photo
		if hasattr(media, "__class__"):
			media_class_name = media.__class__.__name__
			
			if "Photo" in media_class_name:
				media_types.append("photo")
			elif "Document" in media_class_name:
				# Check if document is video, audio, etc.
				if hasattr(media, "document") and hasattr(media.document, "attributes"):
					has_video = False
					has_audio = False
					for attr in media.document.attributes:
						attr_name = attr.__class__.__name__
						if "Video" in attr_name:
							media_types.append("video")
							has_video = True
							break
						elif "Audio" in attr_name:
							media_types.append("audio")
							has_audio = True
							break
					if not has_video and not has_audio:
						media_types.append("document")
				else:
					media_types.append("document")
			elif "Video" in media_class_name:
				media_types.append("video")
			elif "Audio" in media_class_name:
				media_types.append("audio")
			elif "Voice" in media_class_name:
				media_types.append("voice")
	
	# Check for grouped media (albums)
	if hasattr(message, "grouped_id") and message.grouped_id:
		# Message is part of a media group/album
		# The actual media types will be detected from the media field above
		# but we can add additional context
		if not media_types:
			media_types.append("grouped_media")
	
	return media_types if media_types else ["unknown"]


async def poll_media_once(
	client: TelegramClient,
	targets: list[object],
	seen_message_ids: dict[int, set[int]],
	window_seconds: int,
	fetch_limit: int,
) -> list[dict]:
	"""Execute a single poll cycle for media messages and return list of media message info."""
	window_start = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
	media_messages: list[dict] = []
	grouped_media: dict[int, dict] = {}  # Track grouped media by grouped_id

	for target in targets:
		try:
			messages = await client.get_messages(target, limit=fetch_limit)
		except Exception as error:
			print(f"[WARN] get_messages failed for {getattr(target, 'id', 'unknown')}: {error}")
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

		new_messages = [
			message
			for message in recent_messages
			if message.id and message.id not in seen_message_ids[target_id]
		]

		for message in new_messages:
			seen_message_ids[target_id].add(message.id)
			
			# Check if message has media content
			if has_media(message):
				timestamp = message.date.astimezone().strftime("%d/%m/%Y %H:%M") if message.date else datetime.now().strftime("%d/%m/%Y %H:%M")
				
				# Get all media types in this message
				media_types = get_media_types(message)
				
				target_name = getattr(target, "title", None) or getattr(target, "username", None) or str(target_id)
				text_preview = (message.raw_text or "")[:100]  # First 100 chars as preview
				
				# Check if part of grouped media (album)
				grouped_id = getattr(message, "grouped_id", None)
				
				if grouped_id:
					# This message is part of a media group
					if grouped_id not in grouped_media:
						# Create new group entry
						grouped_media[grouped_id] = {
							"message_ids": [message.id],
							"channel_id": target_id,
							"channel_name": target_name,
							"timestamp": timestamp,
							"media_types": media_types.copy(),
							"grouped_id": grouped_id,
							"text_preview": text_preview,
							"messages": [message],
						}
					else:
						# Add to existing group
						grouped_media[grouped_id]["message_ids"].append(message.id)
						# Combine media types (avoid duplicates)
						for media_type in media_types:
							if media_type not in grouped_media[grouped_id]["media_types"]:
								grouped_media[grouped_id]["media_types"].append(media_type)
						grouped_media[grouped_id]["messages"].append(message)
						# Update text_preview if current group has empty text but this message has text
						if not grouped_media[grouped_id]["text_preview"] and text_preview:
							grouped_media[grouped_id]["text_preview"] = text_preview
				else:
					# Individual media message (not grouped)
					media_msg_info = {
						"message_id": message.id,
						"message_ids": [message.id],
						"channel_id": target_id,
						"channel_name": target_name,
						"timestamp": timestamp,
						"media_types": media_types,
						"media_type": ", ".join(media_types),
						"grouped_id": None,
						"text_preview": text_preview,
						"message": message,
						"messages": [message],
					}
					media_messages.append(media_msg_info)
					print(f"[MEDIA] {timestamp} {target_name} - {', '.join(media_types).upper()}: {text_preview}")

		if len(seen_message_ids[target_id]) > 5000:
			seen_message_ids[target_id] = set(sorted(seen_message_ids[target_id])[-2000:])

	# Add all grouped media to the results
	for grouped_id, group_info in grouped_media.items():
		media_type_str = ", ".join(group_info["media_types"])
		group_info["media_type"] = media_type_str
		group_info["message_id"] = group_info["message_ids"][0]  # Use first message ID as primary
		media_messages.append(group_info)
		
		print(f"[MEDIA GROUP] {group_info['timestamp']} {group_info['channel_name']} - "
		      f"{media_type_str.upper()} [Album: {grouped_id}, {len(group_info['message_ids'])} items]: "
		      f"{group_info['text_preview']}")

	return media_messages


async def poll_messages(
	client: TelegramClient,
	gemini_model: Optional[object],
	channel_usernames: list[str],
	channel_ids: list[int],
	poll_interval_seconds: int,
	window_seconds: int,
	fetch_limit: int,
	post_callback: Optional[callable] = None,
) -> None:
	targets = await resolve_targets(client, channel_usernames, channel_ids)
	if not targets:
		print("[ERROR] No valid channel targets found. Check TELEGRAM_CHANNEL_USERNAMES / TELEGRAM_CHANNEL_ID(S).")
		return

	seen_message_ids: dict[int, set[int]] = {}

	print("Polling with get_messages every", poll_interval_seconds, "seconds")
	print("Each poll fetches messages from the last", window_seconds, "seconds")
	print("Resolved channels:")
	for target in targets:
		name = getattr(target, "title", None) or getattr(target, "username", None) or str(getattr(target, "id", "unknown"))
		print(f"- {name} (id: {getattr(target, 'id', 'unknown')})")

	while True:
		summary, message_count = await poll_once(
			client=client,
			gemini_model=gemini_model,
			targets=targets,
			seen_message_ids=seen_message_ids,
			window_seconds=window_seconds,
			fetch_limit=fetch_limit,
		)
		if post_callback:
			post_callback(summary)
		await asyncio.sleep(poll_interval_seconds)

