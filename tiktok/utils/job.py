"""TikTok job configuration and runtime helpers."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class TikTokJobConfig:
	"""Runtime configuration for TikTok job."""

	# TikTok config
	client_key: str
	client_secret: str
	redirect_uri: str
	scopes: str
	
	# Telegram config
	telegram_api_id: int
	telegram_api_hash: str
	telegram_channel_username: Optional[str]
	telegram_channel_id: Optional[int]
	telegram_session_name: str
	
	# Job parameters
	window_seconds: int
	fetch_limit: int
	content_filter: str
	llm_provider: str
	
	# LLM config (optional)
	grok_api_key: Optional[str] = None
	
	# Token file path
	token_file: str = ".tiktok_token.json"


def load_tiktok_runtime_config(
	runtime_config: Optional[dict[str, Any]] = None,
	logger: Optional[logging.Logger] = None,
) -> TikTokJobConfig:
	"""Load TikTok job config from runtime dict + environment variables.
	
	Runtime config takes precedence over environment variables.
	
	Args:
		runtime_config: Optional dict with job-specific overrides
		logger: Optional logger instance
	
	Returns:
		TikTokJobConfig with merged configuration
	
	Raises:
		ValueError: If required config is missing
	"""
	active_logger = logger or logging.getLogger(__name__)
	
	runtime_config = runtime_config or {}
	
	def get_config(key: str, env_var: str, required: bool = False, default: Any = None) -> Any:
		"""Get config from runtime_config first, then environment, then default."""
		if key in runtime_config:
			return runtime_config[key]
		
		env_value = os.getenv(env_var, "").strip() if env_var else None
		if env_value:
			return env_value
		
		if required and default is None:
			raise ValueError(f"Missing required configuration: {key} (set {env_var} or pass in runtime_config)")
		
		return default
	
	def parse_int(value: Any, default: int = 0) -> int:
		"""Parse integer value."""
		if isinstance(value, int):
			return value
		if isinstance(value, str):
			try:
				return int(value.strip())
			except ValueError:
				return default
		return default
	
	# TikTok configuration
	client_key = get_config("client_key", "TIKTOK_CLIENT_KEY", required=True)
	client_secret = get_config("client_secret", "TIKTOK_CLIENT_SECRET", required=True)
	redirect_uri = get_config("redirect_uri", "TIKTOK_REDIRECT_URI", required=True)
	scopes = get_config("scopes", "TIKTOK_SCOPES", required=True)
	
	# Telegram configuration
	telegram_api_id_str = get_config("telegram_api_id", "TELEGRAM_API_ID", required=True)
	telegram_api_id = parse_int(telegram_api_id_str)
	if not telegram_api_id:
		raise ValueError(f"Invalid TELEGRAM_API_ID: {telegram_api_id_str}")
	
	telegram_api_hash = get_config("telegram_api_hash", "TELEGRAM_API_HASH", required=True)
	telegram_channel_username = get_config("telegram_channel_username", "TELEGRAM_CHANNEL_USERNAME")
	
	telegram_channel_id_str = get_config("telegram_channel_id", "TELEGRAM_CHANNEL_ID")
	telegram_channel_id = parse_int(telegram_channel_id_str) if telegram_channel_id_str else None
	
	telegram_session_name = get_config(
		"telegram_session_name",
		"TELEGRAM_SESSION_NAME",
		default="telethon_session",
	)
	
	# Job parameters
	window_seconds_str = get_config("window_seconds", "WINDOW_SECONDS", default="3600")
	window_seconds = parse_int(window_seconds_str, default=3600)
	
	fetch_limit_str = get_config("fetch_limit", "FETCH_LIMIT", default="10")
	fetch_limit = parse_int(fetch_limit_str, default=10)
	
	content_filter = get_config("content_filter", "CONTENT_FILTER", default="video").lower()
	llm_provider = get_config("llm_provider", "LLM_PROVIDER", default="grok").lower()
	
	# LLM configuration
	grok_api_key = get_config("grok_api_key", "GROK_API_KEY")
	
	# Token file
	token_file = get_config("token_file", "TIKTOK_TOKEN_FILE", default=".tiktok_token.json")
	
	active_logger.info("TikTok Job Config loaded:")
	active_logger.info("  Channel: %s (ID: %s)", telegram_channel_username or "unknown", telegram_channel_id or "unknown")
	active_logger.info("  Window: %d sec | Fetch limit: %d", window_seconds, fetch_limit)
	active_logger.info("  Filter: %s | LLM: %s", content_filter, llm_provider)
	
	return TikTokJobConfig(
		client_key=client_key,
		client_secret=client_secret,
		redirect_uri=redirect_uri,
		scopes=scopes,
		telegram_api_id=telegram_api_id,
		telegram_api_hash=telegram_api_hash,
		telegram_channel_username=telegram_channel_username,
		telegram_channel_id=telegram_channel_id,
		telegram_session_name=telegram_session_name,
		window_seconds=window_seconds,
		fetch_limit=fetch_limit,
		content_filter=content_filter,
		llm_provider=llm_provider,
		grok_api_key=grok_api_key,
		token_file=token_file,
	)
