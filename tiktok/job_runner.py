"""Example job runner for TikTok posting.

This demonstrates how to use the runtime_config pattern to run TikTok jobs
with custom configuration parameters, similar to channelMeme.py.

Usage:
    python tiktok/job_runner.py
    
Or programmatically:
    from tiktok.job_runner import run_tiktok_job
    
    job_config = {
        "telegram_channel_username": "animals_funny_videos",
        "window_seconds": 7200,
        "fetch_limit": 5,
        "content_filter": "video",
        "llm_provider": "grok",
    }
    
    asyncio.run(run_tiktok_job(job_config))
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from tiktok.main import main

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def run_tiktok_job(
    runtime_config: Optional[dict[str, Any]] = None,
    job_name: str = "default",
) -> None:
    """Run a TikTok posting job with optional runtime configuration.
    
    Args:
        runtime_config: Optional dict with job-specific config overrides.
                       Common keys:
                       - telegram_channel_username: Telegram channel to fetch from
                       - telegram_channel_id: Telegram channel ID
                       - window_seconds: Time window for fetching messages (default: 3600)
                       - fetch_limit: Max messages to fetch (default: 10)
                       - content_filter: 'video', 'photo', 'text', or 'both'
                       - llm_provider: 'grok' or other providers
                       - client_key: TikTok API client key
                       - client_secret: TikTok API client secret
                       - redirect_uri: TikTok OAuth redirect URI
                       - scopes: TikTok API scopes
        job_name: Name of the job for logging
    """
    logger.info("Starting TikTok job: %s", job_name)
    
    try:
        await main(runtime_config=runtime_config)
        logger.info("✅ TikTok job '%s' completed successfully", job_name)
    except Exception as e:
        logger.error("❌ TikTok job '%s' failed: %s", job_name, e)
        raise


async def run_multiple_jobs(jobs: list[dict[str, Any]]) -> None:
    """Run multiple TikTok jobs sequentially.
    
    Args:
        jobs: List of job configs, each with:
              - name: Job name (string)
              - config: Runtime config dict
    """
    for job in jobs:
        job_name = job.get("name", "unnamed")
        job_config = job.get("config", {})
        
        try:
            await run_tiktok_job(job_config, job_name=job_name)
        except Exception as e:
            logger.warning("Job '%s' failed: %s (continuing with next job)", job_name, e)
            continue


if __name__ == "__main__":
    # Example 1: Run with environment configuration (default)
    logger.info("=" * 72)
    logger.info("Example 1: Running with environment configuration")
    logger.info("=" * 72)
    asyncio.run(run_tiktok_job())
    
    # Example 2: Run with custom runtime configuration
    # Uncomment to test with custom config:
    # logger.info("=" * 72)
    # logger.info("Example 2: Running with custom runtime configuration")
    # logger.info("=" * 72)
    # custom_config = {
    #     "telegram_channel_username": "animals_funny_videos",
    #     "window_seconds": 7200,
    #     "fetch_limit": 5,
    #     "content_filter": "video",
    # }
    # asyncio.run(run_tiktok_job(custom_config, job_name="custom_fetch"))
