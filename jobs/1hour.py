"""Simple hourly scheduler for running channel workflows."""

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


async def _run_channel1() -> None:
	from chanels.chanel1 import main as channel1_main

	await channel1_main()


async def _job_loop(interval_seconds: int, run_once: bool) -> None:
	"""Main async job loop."""
	logger.info("Hourly job started (interval=%ss)", interval_seconds)

	while True:
		start_time = time.time()
		logger.info("Running channel1 job...")
		try:
			await _run_channel1()
			logger.info("Channel1 job finished")
		except Exception as error:
			logger.error("Channel1 job failed: %s", error)

		if run_once:
			logger.info("Run-once mode complete")
			break

		elapsed = time.time() - start_time
		sleep_for = max(0, interval_seconds - elapsed)
		logger.info("Sleeping for %.0f seconds", sleep_for)
		await asyncio.sleep(sleep_for)


def start(interval_seconds: int = 3600, run_once: bool = False) -> None:
	"""Run channel workflows every interval_seconds (default: 1 hour)."""
	logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

	try:
		asyncio.run(_job_loop(interval_seconds, run_once))
	except Exception as error:
		logger.error("Job loop failed: %s", error)
		raise
