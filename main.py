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


def main() -> None:
	job_module = _load_hourly_job()
	job_module.start()


if __name__ == "__main__":
	main()
