"""Common channel runtime configuration helpers."""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class ChannelRuntimeConfig:
	"""Runtime configuration for channel scripts."""

	channel_username: str
	channel_id: Optional[int]
	window_seconds: int
	fetch_limit: int
	content_filter: str
	llm_provider: str


def parse_channel_id(raw: str, env_name: str, logger: logging.Logger) -> Optional[int]:
	"""Parse Telegram channel ID string into int."""
	value = (raw or "").strip()
	if not value:
		return None
	try:
		return int(value)
	except ValueError:
		logger.warning("Invalid %s: %s", env_name, raw)
		return None


def _parse_int(value: Optional[str], default: int) -> int:
	raw = (value or "").strip()
	if not raw:
		return default
	try:
		return int(raw)
	except ValueError:
		return default


def load_channel_runtime_config(
	default_content_filter: str = "both",
	default_window_seconds: int = 600,
	default_fetch_limit: int = 10,
	default_llm_provider: str = "grok",
	argv: Optional[Sequence[str]] = None,
	logger: Optional[logging.Logger] = None,
) -> ChannelRuntimeConfig:
	"""Load config from CLI first, then environment variables.

	Supported CLI args (required):
	- --channel-username
	- --window-seconds
	- --content-filter
	- --llm-provider

	Optional:
	- --channel-id
	- --fetch-limit
	"""
	active_logger = logger or logging.getLogger(__name__)

	env_channel_username = "TELEGRAM_CHANNEL_USERNAME"
	env_channel_id = "TELEGRAM_CHANNEL_ID"

	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument("--channel-username", dest="channel_username", required=True)
	parser.add_argument("--channel-id", dest="channel_id")
	parser.add_argument("--window-seconds", dest="window_seconds", required=True)
	parser.add_argument("--fetch-limit", dest="fetch_limit")
	parser.add_argument("--content-filter", dest="content_filter", required=True)
	parser.add_argument("--llm-provider", dest="llm_provider", required=True)
	args, _ = parser.parse_known_args(argv)

	channel_username = (
		(args.channel_username or os.getenv(env_channel_username, "")).strip()
	)
	channel_id = parse_channel_id(
		args.channel_id if args.channel_id is not None else os.getenv(env_channel_id, ""),
		env_channel_id,
		active_logger,
	)

	window_seconds = _parse_int(
		args.window_seconds if args.window_seconds is not None else os.getenv("TELEGRAM_WINDOW_SECONDS", ""),
		default_window_seconds,
	)
	fetch_limit = _parse_int(
		args.fetch_limit if args.fetch_limit is not None else os.getenv("TELEGRAM_FETCH_LIMIT", ""),
		default_fetch_limit,
	)
	content_filter = (
		(args.content_filter if args.content_filter is not None else os.getenv("TELEGRAM_CONTENT_FILTER", default_content_filter))
		.strip()
		.lower()
		or default_content_filter
	)
	llm_provider = (
		(args.llm_provider if args.llm_provider is not None else os.getenv("LLM_PROVIDER", default_llm_provider))
		.strip()
		.lower()
		or default_llm_provider
	)

	return ChannelRuntimeConfig(
		channel_username=channel_username,
		channel_id=channel_id,
		window_seconds=window_seconds,
		fetch_limit=fetch_limit,
		content_filter=content_filter,
		llm_provider=llm_provider,
	)