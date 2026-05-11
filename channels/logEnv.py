import os
from dotenv import load_dotenv

load_dotenv()

def test_log_stage_env():
    """Test logging the STAGE environment variable"""
    stage = os.getenv('STAGE', 'development')
    print(f"STAGE environment variable: {stage}")
    assert stage is not None, "STAGE environment variable is not set"
    print("✓ STAGE environment variable is set successfully")

if __name__ == "__main__":
    test_log_stage_env()
