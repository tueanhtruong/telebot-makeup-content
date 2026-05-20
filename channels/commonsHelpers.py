"""Common channel runtime configuration helpers."""

from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime
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
	start_date: Optional[date]
	end_date: Optional[date]


def load_dotenv_runtime_path(
	default_env_path: str = ".env.local",
	argv: Optional[Sequence[str]] = None,
) -> str:
	"""Load dotenv file path from CLI or environment."""
	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument("--env-path", dest="env_path")
	args, _ = parser.parse_known_args(argv)

	return (
		(args.env_path if args.env_path is not None else os.getenv("DOTENV_FILE_PATH", default_env_path))
		.strip()
		or default_env_path
	)


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


def _parse_date(value: Optional[str], field_name: str) -> Optional[date]:
	raw = (value or "").strip()
	if not raw:
		return None
	try:
		return datetime.strptime(raw, "%d/%m/%Y").date()
	except ValueError as error:
		raise ValueError(f"Invalid {field_name} '{raw}'. Expected format DD/MM/YYYY") from error


def load_channel_runtime_config(
	default_content_filter: str = "both",
	default_window_seconds: int = 600,
	default_fetch_limit: int = 10,
	default_llm_provider: str = "openrouter",
	default_start_date: Optional[str] = None,
	default_end_date: Optional[str] = None,
	argv: Optional[Sequence[str]] = None,
	logger: Optional[logging.Logger] = None,
) -> ChannelRuntimeConfig:
	"""Load config from CLI first, then environment variables.

	Supported CLI args (required):
	- --channel-username
	- --window-seconds
	- --content-filter (text|image|video|media|both)
	  - text: messages with only text
	  - image: messages with only image/photo (text optional)
	  - video: messages with only video (text optional)
	  - media: messages with only image or video (text optional)
	  - both: all messages
	- --llm-provider

	Optional:
	- --channel-id
	- --fetch-limit
	- --start-date (DD/MM/YYYY, inclusive)
	- --end-date (DD/MM/YYYY, exclusive)
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
	parser.add_argument("--start-date", dest="start_date")
	parser.add_argument("--end-date", dest="end_date")
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

	start_date_raw = (
		args.start_date
		if args.start_date is not None
		else os.getenv("TELEGRAM_START_DATE", default_start_date or "")
	)
	end_date_raw = (
		args.end_date
		if args.end_date is not None
		else os.getenv("TELEGRAM_END_DATE", default_end_date or "")
	)

	start_date = _parse_date(start_date_raw, "start-date")
	end_date = _parse_date(end_date_raw, "end-date")

	if (start_date is None) != (end_date is None):
		raise ValueError("Both start-date and end-date are required together (format DD/MM/YYYY)")
	if start_date and end_date and start_date >= end_date:
		raise ValueError("start-date must be before end-date")

	return ChannelRuntimeConfig(
		channel_username=channel_username,
		channel_id=channel_id,
		window_seconds=window_seconds,
		fetch_limit=fetch_limit,
		content_filter=content_filter,
		llm_provider=llm_provider,
		start_date=start_date,
		end_date=end_date,
	)