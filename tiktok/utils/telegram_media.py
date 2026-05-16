"""Telegram media download utilities for TikTok pipeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from telethon import TelegramClient

logger = logging.getLogger(__name__)


async def download_message_media(
    client: TelegramClient,
    raw_message: object,
    message_ids: list[int],
    output_dir: str = "/tmp/telegram_media",
) -> list[str]:
    """Download media files from all messages in a grouped Telegram post."""
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


def pick_video_files(media_paths: list[str]) -> list[str]:
    """Filter only likely video files from downloaded media paths."""
    video_exts = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
    selected: list[str] = []
    for path in media_paths:
        ext = Path(path).suffix.lower()
        if ext in video_exts:
            selected.append(path)
    return selected
