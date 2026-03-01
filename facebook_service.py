import os
from typing import Optional


def get_facebook_token() -> Optional[str]:
	token = os.getenv("FACEBOOK_TOKEN", "").strip()
	return token if token else None


def post_to_facebook(message: str) -> bool:
	token = get_facebook_token()
	if not token:
		print("[WARN] Facebook posting disabled: FACEBOOK_TOKEN not set in .env")
		return False

	page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
	if not page_id:
		print("[WARN] Facebook posting disabled: FACEBOOK_PAGE_ID not set in .env")
		return False

	import requests

	url = f"https://graph.facebook.com/{page_id}/feed"
	payload = {
		"access_token": token,
		"message": message,
	}

	try:
		response = requests.post(url, data=payload)
		if response.status_code == 200:
			print(f"[SUCCESS] Posted to Facebook (Page ID: {page_id})")
			return True
		else:
			print(f"[ERROR] Facebook post failed: {response.status_code} - {response.text}")
			return False
	except Exception as error:
		print(f"[ERROR] Facebook post exception: {error}")
		return False
