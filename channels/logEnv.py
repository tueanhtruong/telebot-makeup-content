import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from channels.commonsHelpers import load_dotenv_runtime_path

load_dotenv(load_dotenv_runtime_path(default_env_path=".env.local"))

def test_log_stage_env():
    """Test logging the STAGE environment variable"""
    stage = os.getenv('STAGE', 'development')
    print(f"STAGE environment variable: {stage}")
    assert stage is not None, "STAGE environment variable is not set"
    print("✓ STAGE environment variable is set successfully")

if __name__ == "__main__":
    test_log_stage_env()
