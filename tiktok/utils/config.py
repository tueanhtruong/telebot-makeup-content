"""Configuration utilities for TikTok app."""

import logging
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass
class TikTokConfig:
    """Configuration for TikTok app."""
    
    client_key: str
    client_secret: str
    redirect_uri: str
    scopes: str
    token_file: str
    user_file: str
    telegram_api_id: int
    telegram_api_hash: str
    telegram_session_name: str
    telegram_channel_username: Optional[str]
    telegram_channel_id: Optional[int]
    window_seconds: int
    fetch_limit: int
    content_filter: str
    llm_provider: str
    stage: str


def load_env(dotenv_path: Optional[str] = None) -> None:
    """Load environment variables from .env file."""
    if dotenv_path:
        load_dotenv(dotenv_path=dotenv_path)
    else:
        load_dotenv()


def get_required_env(name: str) -> str:
    """Get required environment variable."""
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def get_optional_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get optional environment variable."""
    value = os.getenv(name, "").strip()
    return value if value else default


def load_tiktok_config(logger: Optional[logging.Logger] = None) -> TikTokConfig:
    """Load TikTok configuration from environment variables."""
    
    # TikTok API configuration
    client_key = get_required_env("TIKTOK_CLIENT_KEY")
    client_secret = get_required_env("TIKTOK_CLIENT_SECRET")
    redirect_uri = get_optional_env("TIKTOK_REDIRECT_URI", "https://j1mwp3kl-8080.asse.devtunnels.ms/")
    scopes = get_optional_env("TIKTOK_SCOPES", "user.info.basic,video.list")
    
    # File paths
    token_file = get_optional_env("TIKTOK_TOKEN_FILE", "./tiktok/auth-token.json")
    user_file = get_optional_env("TIKTOK_USER_FILE", "./tiktok/user.json")
    
    # Telegram configuration
    telegram_api_id = int(get_required_env("TELEGRAM_API_ID"))
    telegram_api_hash = get_required_env("TELEGRAM_API_HASH")
    telegram_session_name = get_optional_env("TELEGRAM_SESSION_NAME", "telethon_session")
    telegram_channel_username = get_optional_env("TELEGRAM_CHANNEL_USERNAME")
    telegram_channel_id_str = get_optional_env("TELEGRAM_CHANNEL_ID")
    telegram_channel_id = int(telegram_channel_id_str) if telegram_channel_id_str else None
    
    # Content filtering
    window_seconds = int(get_optional_env("WINDOW_SECONDS", "3600"))
    fetch_limit = int(get_optional_env("FETCH_LIMIT", "10"))
    content_filter = get_optional_env("CONTENT_FILTER", "both")
    
    # LLM configuration
    llm_provider = get_optional_env("LLM_PROVIDER", "grok")
    
    # Stage
    stage = get_optional_env("STAGE", "dev")
    
    if logger:
        logger.info("Loaded TikTok Configuration:")
        logger.info(f"  Client Key: {client_key[:10]}...")
        logger.info(f"  Redirect URI: {redirect_uri}")
        logger.info(f"  Token File: {token_file}")
        logger.info(f"  Telegram Channel: {telegram_channel_username or telegram_channel_id}")
        logger.info(f"  Content Filter: {content_filter}")
        logger.info(f"  Window Seconds: {window_seconds}")
        logger.info(f"  LLM Provider: {llm_provider}")
        logger.info(f"  Stage: {stage}")
    
    return TikTokConfig(
        client_key=client_key,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
        token_file=token_file,
        user_file=user_file,
        telegram_api_id=telegram_api_id,
        telegram_api_hash=telegram_api_hash,
        telegram_session_name=telegram_session_name,
        telegram_channel_username=telegram_channel_username,
        telegram_channel_id=telegram_channel_id,
        window_seconds=window_seconds,
        fetch_limit=fetch_limit,
        content_filter=content_filter,
        llm_provider=llm_provider,
        stage=stage,
    )
