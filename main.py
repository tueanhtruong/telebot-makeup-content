"""Application entry point."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_hourly_job():
	job_path = Path(__file__).resolve().parent / "jobs" / "1hour.py"
	spec = importlib.util.spec_from_file_location("job_1hour", job_path)
	if spec is None or spec.loader is None:
		raise RuntimeError("Unable to load jobs/1hour.py")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module

def _load_5minute_job():
	job_path = Path(__file__).resolve().parent / "jobs" / "5minutes.py"
	spec = importlib.util.spec_from_file_location("job_5minutes", job_path)
	if spec is None or spec.loader is None:
		raise RuntimeError("Unable to load jobs/5minutes.py")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module

def main() -> None:
	# Load and start the hourly job
	hourly_job_module = _load_hourly_job()
	hourly_job_module.start()
	# Load and start the 5-minute job
	minute_5_job_module = _load_5minute_job()
	minute_5_job_module.start()


if __name__ == "__main__":
	main()
