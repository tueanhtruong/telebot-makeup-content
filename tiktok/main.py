# pip install requests telethon python-dotenv

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from dotenv import load_dotenv
from telethon import TelegramClient

# Add parent directory to path for imports
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tiktok.utils.config import load_tiktok_config, TikTokConfig
from tiktok.utils.job import load_tiktok_runtime_config, TikTokJobConfig
from tiktok.utils.auth import (
    generate_code_verifier,
    generate_code_challenge,
    build_auth_url,
    get_access_token,
    start_local_server,
    open_browser_and_wait,
    get_auth_code,
    reset_auth_state,
)
from tiktok.utils.token import (
    load_token_from_file,
    save_token_to_file,
    refresh_access_token,
)
from tiktok.utils.api import fetch_user_info, upload_video_to_tiktok
from tiktok.utils.llm import (
    sanitize_text_with_llm,
    remove_tags,
    remove_links_content,
    get_text_except_last_line_if_link,
    preview,
)
from tiktok.utils.telegram_media import download_message_media, pick_video_files
from services.telegram import clone_messages_from_channels_with_objects

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def setup_env():
    """Load environment variables."""
    env_file = os.getenv("ENV_FILE", "").strip()
    if env_file:
        dotenv_path = Path(env_file)
    else:
        # Prefer TikTok-specific env file when ENV_FILE is not set.
        candidates = [".env.tiktok", ".env.local", ".env"]
        dotenv_path = None
        for candidate in candidates:
            candidate_path = ROOT_DIR / candidate
            if candidate_path.exists():
                dotenv_path = candidate_path
                break

        if dotenv_path is None:
            load_dotenv()
            print("Using default .env file")
            stage = os.getenv('STAGE', 'not set')
            print(f"Loaded Stage: {stage}")
            return

    if not dotenv_path.is_absolute():
        dotenv_path = ROOT_DIR / dotenv_path

    print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path)
    print(f"Using dotenv file: {dotenv_path}")
    
    stage = os.getenv('STAGE', 'not set')
    print(f"Loaded Stage: {stage}")


def parse_cli_arguments(argv: Optional[Sequence[str]] = None) -> dict[str, Any]:
    """Parse CLI arguments into runtime config.
    
    Supported arguments:
        --env-path: Path to .env file
        --channel-username: Telegram channel username (required)
        --channel-id: Telegram channel ID (optional)
        --window-seconds: Time window for fetching messages (required)
        --fetch-limit: Max messages to fetch (optional)
        --content-filter: Message filter type - text|photo|video|both (required)
        --llm-provider: LLM provider - grok|openrouter (required)
    
    Returns:
        Dict with parsed configuration values
    """
    parser = argparse.ArgumentParser(
        description="TikTok content posting job",
        add_help=False,  # Don't auto-add -h/--help to avoid conflicts
    )
    
    # Environment file
    parser.add_argument("--env-path", dest="env_path", help="Path to .env file")
    
    # Telegram configuration (required)
    parser.add_argument(
        "--channel-username",
        dest="channel_username",
        required=True,
        help="Telegram channel username",
    )
    parser.add_argument(
        "--channel-id",
        dest="channel_id",
        help="Telegram channel ID (numeric)",
    )
    parser.add_argument(
        "--window-seconds",
        dest="window_seconds",
        required=True,
        help="Time window in seconds for fetching messages",
    )
    parser.add_argument(
        "--fetch-limit",
        dest="fetch_limit",
        help="Maximum number of messages to fetch",
    )
    parser.add_argument(
        "--content-filter",
        dest="content_filter",
        required=True,
        choices=["text", "photo", "video", "both"],
        help="Type of messages to fetch",
    )
    parser.add_argument(
        "--llm-provider",
        dest="llm_provider",
        required=True,
        choices=["grok", "openrouter"],
        help="LLM provider for text sanitization",
    )
    
    # Parse arguments
    args, _ = parser.parse_known_args(argv)
    
    # Build runtime config from CLI arguments
    runtime_config = {}
    
    # Set env-path if provided
    if args.env_path:
        os.environ["ENV_FILE"] = args.env_path
    
    # Add parsed arguments to runtime config
    if args.channel_username:
        runtime_config["telegram_channel_username"] = args.channel_username
    
    if args.channel_id:
        try:
            runtime_config["telegram_channel_id"] = int(args.channel_id)
        except ValueError:
            logger.warning("Invalid channel_id: %s, ignoring", args.channel_id)
    
    if args.window_seconds:
        try:
            runtime_config["window_seconds"] = int(args.window_seconds)
        except ValueError:
            logger.warning("Invalid window_seconds: %s, using default", args.window_seconds)
    
    if args.fetch_limit:
        try:
            runtime_config["fetch_limit"] = int(args.fetch_limit)
        except ValueError:
            logger.warning("Invalid fetch_limit: %s, using default", args.fetch_limit)
    
    if args.content_filter:
        runtime_config["content_filter"] = args.content_filter
    
    if args.llm_provider:
        runtime_config["llm_provider"] = args.llm_provider
    
    logger.info("Parsed CLI arguments: %s", runtime_config)
    return runtime_config


async def perform_login(config: TikTokConfig) -> Optional[dict]:
    """Perform TikTok OAuth login flow."""
    print("\n🔐 Starting TikTok login flow...")
    
    # PKCE
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    state = os.urandom(16).hex()
    
    # Start local server before opening browser
    start_local_server(port=8080)
    
    auth_url = build_auth_url(
        code_challenge,
        state,
        config.client_key,
        config.redirect_uri,
        config.scopes,
    )
    
    # Open browser and wait for callback
    if not open_browser_and_wait(auth_url, timeout=120):
        print("No auth code received. Did you authorize?")
        return None
    
    auth_code = get_auth_code()
    if not auth_code:
        print("Failed to get auth code")
        return None
    
    print("\n✅ Auth code received. Exchanging for token...")
    token_data = get_access_token(
        auth_code,
        code_verifier,
        config.client_key,
        config.client_secret,
        config.redirect_uri,
    )
    
    if not token_data or not token_data.get("access_token"):
        print("Failed to get access token.")
        print("Response:", json.dumps(token_data, indent=2))
        return None
    
    save_token_to_file(token_data, config.token_file)
    reset_auth_state()
    return token_data


async def fetch_telegram_content(config: TikTokConfig) -> tuple[TelegramClient, list[tuple]]:
    """Fetch content from Telegram channel and keep client connected for media downloads."""
    logger.info("Cloning messages from Telegram channel")
    logger.info("Content filter: %s", config.content_filter)
    logger.info("Window seconds: %s", config.window_seconds)
    logger.info("Fetch limit: %s", config.fetch_limit)
    
    # Create Telegram client
    telegram_client = TelegramClient(config.telegram_session_name, config.telegram_api_id, config.telegram_api_hash)
    
    await telegram_client.start()
    
    channel_usernames = [config.telegram_channel_username] if config.telegram_channel_username else []
    channel_ids = [config.telegram_channel_id] if config.telegram_channel_id is not None else []
    
    if not channel_usernames and not channel_ids:
        raise ValueError("Set TELEGRAM_CHANNEL_USERNAME or TELEGRAM_CHANNEL_ID in environment")
    
    results = await clone_messages_from_channels_with_objects(
        telegram_client,
        channel_usernames=channel_usernames,
        channel_ids=channel_ids,
        window_seconds=config.window_seconds,
        fetch_limit=config.fetch_limit,
        content_filter=config.content_filter,
    )
    
    return telegram_client, results


async def process_and_upload_to_tiktok(
    config: TikTokConfig,
    access_token: str,
    token_data: Optional[dict],
    telegram_client: TelegramClient,
    telegram_content: list[tuple],
) -> Optional[dict]:
    """Process Telegram content and upload to TikTok."""
    logger.info("Processing %d message(s) from Telegram", len(telegram_content))
    
    uploaded_count = 0
    scope_reauth_attempted = False
    
    for cloned_data, raw_message in telegram_content:
        message_id = cloned_data.get("message_id")
        media_types = ", ".join(cloned_data.get("media_types", [])) or "none"
        raw_text = cloned_data.get("text", "")
        
        # Clean up text
        first_line_or_full = get_text_except_last_line_if_link(raw_text)
        cleaned_raw_text = remove_links_content(first_line_or_full)
        text_preview = preview(remove_tags(cleaned_raw_text))
        
        logger.info(
            "[MSG %s] Original text preview: %s | media=%s",
            message_id,
            text_preview,
            media_types,
        )
        
        # Process based on media type
        if media_types and media_types != "none":
            logger.info("[MSG %s] Detected media types: %s", message_id, media_types)

            # Sanitize text using LLM (fallback to preview if LLM unavailable)
            sanitized_text = text_preview
            # temp: disable LLM sanitization to save tokens during testing
            # if sanitized_text and sanitized_text.strip():
            #     llm_text = await sanitize_text_with_llm(
            #         remove_tags(sanitized_text),
            #         llm_provider=config.llm_provider,
            #     )
            #     if llm_text:
            #         sanitized_text = llm_text
            
            logger.info("[MSG %s] Sanitized text: %s", message_id, sanitized_text)

            message_ids = cloned_data.get("message_ids", [])
            downloaded_media = await download_message_media(
                telegram_client,
                raw_message,
                message_ids,
                output_dir="/tmp/telegram_media",
            )
            video_paths = pick_video_files(downloaded_media)

            if not video_paths:
                logger.warning("[MSG %s] No video files downloaded, skipping", message_id)
                continue

            publish_count = 0
            for video_path in video_paths:
                try:
                    publish_id = upload_video_to_tiktok(
                        video_file_path=video_path,
                        description=sanitized_text,
                        access_token=access_token,
                    )
                except Exception as upload_error:
                    if "Unaudited app restriction" in str(upload_error):
                        logger.error(
                            "[MSG %s] TikTok blocked publish for unaudited app. "
                            "Set TikTok account to private or pass TikTok Content Posting audit.",
                            message_id,
                        )
                        continue
                    if "Scope not authorized" in str(upload_error):
                        if not scope_reauth_attempted:
                            logger.warning(
                                "[MSG %s] Scope missing on current token, forcing re-login and retrying once",
                                message_id,
                            )
                            scope_reauth_attempted = True
                            token_data = await perform_login(config)
                            if not token_data:
                                logger.error("[MSG %s] Re-login failed while recovering publish scope", message_id)
                                continue
                            access_token = token_data.get("access_token")
                            try:
                                publish_id = upload_video_to_tiktok(
                                    video_file_path=video_path,
                                    description=sanitized_text,
                                    access_token=access_token,
                                )
                            except Exception as scope_retry_error:
                                logger.error(
                                    "[MSG %s] Upload failed after re-login: %s",
                                    message_id,
                                    scope_retry_error,
                                )
                                continue
                        else:
                            logger.error(
                                "[MSG %s] Missing TikTok scope for publish. "
                                "Ensure app has video.publish approval and token is re-consented.",
                                message_id,
                            )
                            continue
                    elif "Token expired" in str(upload_error):
                        logger.warning("[MSG %s] Token expired during upload, refreshing/login and retrying", message_id)
                        refreshed = None
                        if token_data and token_data.get("refresh_token"):
                            try:
                                refreshed = refresh_access_token(
                                    token_data.get("refresh_token"),
                                    config.client_key,
                                    config.client_secret,
                                )
                            except Exception:
                                refreshed = None

                        if refreshed:
                            token_data = refreshed
                            save_token_to_file(token_data, config.token_file)
                            access_token = token_data.get("access_token")
                        else:
                            token_data = await perform_login(config)
                            if not token_data:
                                logger.error("[MSG %s] Re-login failed during upload", message_id)
                                continue
                            access_token = token_data.get("access_token")

                        # Retry once after new token
                        try:
                            publish_id = upload_video_to_tiktok(
                                video_file_path=video_path,
                                description=sanitized_text,
                                access_token=access_token,
                            )
                        except Exception as retry_error:
                            if "Unaudited app restriction" in str(retry_error):
                                logger.error(
                                    "[MSG %s] TikTok blocked publish for unaudited app after retry. "
                                    "Set account private or pass TikTok Content Posting audit.",
                                    message_id,
                                )
                                continue
                            if "Scope not authorized" in str(retry_error):
                                logger.error(
                                    "[MSG %s] Missing TikTok scope for publish after retry. "
                                    "Update TIKTOK_SCOPES to include video.publish and re-login.",
                                    message_id,
                                )
                                continue
                            logger.error(
                                "[MSG %s] Upload retry failed after refresh/login: %s",
                                message_id,
                                retry_error,
                            )
                            continue
                    else:
                        logger.error("[MSG %s] Upload failed: %s", message_id, upload_error)
                        continue

                if publish_id:
                    publish_count += 1
                    logger.info("[MSG %s] Published to TikTok with publish_id=%s", message_id, publish_id)

            if sanitized_text:
                uploaded_count += publish_count
        else:
            logger.warning("[MSG %s] No media content to process", message_id)
    
    logger.info("✅ Processing complete. %d uploaded video(s)", uploaded_count)
    return token_data


async def main(runtime_config: Optional[dict[str, Any]] = None):
    """Main execution flow.
    
    Args:
        runtime_config: Optional dict with job-specific configuration overrides.
                       Takes precedence over environment variables.
    """
    setup_env()
    
    try:
        # Load configuration from runtime_config (if provided) or environment
        if runtime_config:
            config_obj = load_tiktok_runtime_config(runtime_config=runtime_config, logger=logger)
            logger.info("Using runtime config")
        else:
            config_obj = load_tiktok_runtime_config(logger=logger)
            logger.info("Using environment config")
        
        # Convert TikTokJobConfig to TikTokConfig for backward compatibility
        config = TikTokConfig(
            client_key=config_obj.client_key,
            client_secret=config_obj.client_secret,
            redirect_uri=config_obj.redirect_uri,
            scopes=config_obj.scopes,
            telegram_api_id=config_obj.telegram_api_id,
            telegram_api_hash=config_obj.telegram_api_hash,
            telegram_channel_username=config_obj.telegram_channel_username,
            telegram_channel_id=config_obj.telegram_channel_id,
            telegram_session_name=config_obj.telegram_session_name,
            window_seconds=config_obj.window_seconds,
            fetch_limit=config_obj.fetch_limit,
            content_filter=config_obj.content_filter,
            llm_provider=config_obj.llm_provider,
            token_file=config_obj.token_file,
            user_file=".tiktok_user.json",
            stage=os.getenv("STAGE", "dev"),
        )
        
        # Step 1: Load or refresh TikTok access token
        logger.info("Loading token from file...")
        token_data = load_token_from_file(config.token_file)
        access_token = None
        
        if token_data:
            access_token = token_data.get("access_token")
            logger.info("✅ Token loaded from file")
            
            # Try to fetch content with current token
            try:
                logger.info("👤 Fetching user info...")
                user_info = fetch_user_info(access_token)
                if user_info:
                    logger.info("✅ User info retrieved: %s", user_info.get('display_name', 'Unknown'))
                else:
                    logger.warning("Failed to fetch user info")
            except Exception as e:
                if "Token expired" in str(e):
                    logger.info("Token expired, attempting refresh...")
                    
                    # Try to refresh token
                    if token_data.get("refresh_token"):
                        try:
                            refreshed_token = refresh_access_token(
                                token_data.get("refresh_token"),
                                config.client_key,
                                config.client_secret,
                            )
                            if refreshed_token:
                                token_data = refreshed_token
                                save_token_to_file(token_data, config.token_file)
                                access_token = token_data.get("access_token")
                                logger.info("✅ Token refreshed successfully")
                            else:
                                logger.warning("Token refresh failed, starting login...")
                                access_token = None
                        except Exception as refresh_err:
                            logger.warning("Token refresh failed: %s", refresh_err)
                            access_token = None
                    else:
                        access_token = None
        
        # If no valid token, perform login
        if not access_token:
            token_data = await perform_login(config)
            if not token_data:
                logger.error("❌ Login failed")
                return
            access_token = token_data.get("access_token")
        
        # Step 2: Fetch Telegram content
        logger.info("\n📱 Fetching content from Telegram...")
        telegram_client, telegram_content = await fetch_telegram_content(config)
        logger.info("✅ Fetched %d message(s) from Telegram", len(telegram_content))
        
        # Step 3: Process and upload to TikTok
        logger.info("\n🎬 Processing and uploading to TikTok...")
        try:
            token_data = await process_and_upload_to_tiktok(
                config,
                access_token,
                token_data,
                telegram_client,
                telegram_content,
            )
        finally:
            await telegram_client.disconnect()
        
        logger.info("\n✅ All done!")
    
    except Exception as e:
        logger.error("❌ Error: %s", e)
        raise


if __name__ == "__main__":
    # Parse CLI arguments if provided
    cli_config = {}
    if len(sys.argv) > 1:
        try:
            cli_config = parse_cli_arguments()
        except SystemExit as e:
            # argparse raises SystemExit on error; let it propagate
            raise
    
    # Support running as:
    #   python tiktok/main.py
    #   python tiktok/main.py --channel-username ... --window-seconds ... --content-filter ... --llm-provider ...
    # Or programmatically: asyncio.run(main(runtime_config={...}))
    asyncio.run(main(runtime_config=cli_config if cli_config else None))
