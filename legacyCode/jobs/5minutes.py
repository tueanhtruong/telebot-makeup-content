"""Simple 5-minute scheduler for running channel workflows."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))


logger = logging.getLogger(__name__)


async def _run_channel2() -> None:
	from channels.channel2 import main as channel2_main

	await channel2_main()


async def _job_loop(interval_seconds: int, run_once: bool) -> None:
	"""Main async job loop."""
	logger.info("5-minute job started (interval=%ss)", interval_seconds)

	while True:
		if not run_once:
			logger.info("Waiting for %.0f seconds before next run...", interval_seconds)
			await asyncio.sleep(interval_seconds)

		logger.info("Running channel2 job...")
		try:
			await _run_channel2()
			logger.info("Channel2 job finished")
		except Exception as error:
			logger.error("Channel2 job failed: %s", error)

		if run_once:
			logger.info("Run-once mode complete")
			break


def start(interval_seconds: int = 300, run_once: bool = False) -> None:
	"""Run channel workflows every interval_seconds (default: 5 minutes)."""
	logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

	try:
		asyncio.run(_job_loop(interval_seconds, run_once))
	except Exception as error:
		logger.error("Job loop failed: %s", error)
		raise
