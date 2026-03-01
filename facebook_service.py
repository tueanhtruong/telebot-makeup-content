import os
import re
import tempfile
import requests
import json
from typing import Optional
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeVideo


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


def sanitize_facebook_message(model: object | None, text: str) -> str:
	"""Remove hashtags and rewrite sensitive wording for Facebook safety using Gemini."""
	if not text:
		return ""
	
	# log original text and length
	print(f"[SANITIZE] Original text ({len(text)} chars): {text[:100]}...")

	# Remove hashtags, then normalize spaces/newlines.
	without_hashtags = re.sub(r"(?<!\w)#\w+", "", text)
	cleaned_text = re.sub(r"[ \t]+", " ", without_hashtags)
	cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

	if model is None:
		print("[WARN] Gemini unavailable, using hashtag-removed text only")
		return cleaned_text

	prompt = f"""Bạn là trợ lý biên tập nội dung cho Facebook.

Nhiệm vụ:
• Hãy tìm những từ ngữ trong đoạn văn này có thể bị thuật toán Facebook quét là vi phạm tiêu chuẩn cộng đồng hoặc nhạy cảm và thay thế bằng từ phù hợp hơn
• Hãy tóm tắt nội dung chính của đoạn văn này thành một câu văn ngắn gọn, có sự châm biếm, sắc sảo, phù hợp để đăng lên Facebook, đồng thời đảm bảo không vi phạm tiêu chuẩn cộng đồng của Facebook.
• Chỉnh sửa các hashtag hiện tại nếu có hoặc thêm mới cho phù hợp với nội dung đã chỉnh sửa, nhưng chỉ sử dụng các hashtag an toàn và phổ biến, tránh các hashtag có thể bị Facebook gắn cờ.
• Không sử dụng bất kỳ ký tự đặc biệt nào khác ngoài dấu chấm câu cơ bản và dấu gạch ngang để phân tách các ý trong đoạn văn.
• Ngôn ngữ Tiếng Việt

Yêu cầu bắt buộc:
- Chỉ trả về đúng đoạn văn đã chỉnh sửa.
- Không thêm giải thích, không thêm nhãn, không thêm tiêu đề.

Đoạn văn:
{cleaned_text}
"""

	try:
		response = model.generate_content(prompt)
		sanitized_text = (getattr(response, "text", "") or "").strip()
		if not sanitized_text:
			print("[WARN] Gemini returned empty sanitized text, using hashtag-removed text")
			return cleaned_text
		return sanitized_text
	except Exception as error:
		print(f"[WARN] Gemini sanitize failed: {error}. Using hashtag-removed text")
		return cleaned_text


def is_video_message(message: object) -> bool:
	"""Detect whether a Telegram message contains video media."""
	media = getattr(message, "media", None)
	if not media:
		return False

	# Fast-path by media class name for common Telethon media wrappers.
	media_class_name = media.__class__.__name__.lower()
	if "video" in media_class_name:
		return True

	document = getattr(media, "document", None)
	if not document:
		return False

	# Most reliable signal for uploaded videos.
	mime_type = (getattr(document, "mime_type", "") or "").lower()
	if mime_type.startswith("video/"):
		return True

	# Telethon stores semantic media flags in document attributes.
	attributes = getattr(document, "attributes", []) or []
	for attribute in attributes:
		if isinstance(attribute, DocumentAttributeVideo):
			return True

	return False


async def upload_video_to_facebook_resumable(
    file_path: str,
    facebook_token: str,
    facebook_page_id: str,
	app_id: str | None = None,
    title: str = "",
    description: str = "",
) -> str | None:
    try:
        file_size = os.path.getsize(file_path)
        url = f"https://graph-video.facebook.com/v21.0/{facebook_page_id}/videos"

        # --- BƯỚC 1: KHỞI TẠO (PHASE START) ---
        start_params = {
            "upload_phase": "start",
            "file_size": file_size,
            "access_token": facebook_token,
        }
        res_start = requests.post(url, data=start_params).json()
        
        upload_session_id = res_start.get("upload_session_id")
        video_id = res_start.get("video_id") # ID thực tế của video

        if not upload_session_id:
            print(f"[ERROR] Start failed: {res_start}")
            return None

        # --- BƯỚC 2: TẢI LÊN (PHASE TRANSFER) ---
        # Với file nhỏ, ta gửi 1 chunk. Với file > 10MB, nên chia nhỏ (ở đây làm mẫu 1 chunk)
        start_offset = 0
        with open(file_path, "rb") as f:
            video_data = f.read()

        transfer_params = {
            "upload_phase": "transfer",
            "upload_session_id": upload_session_id,
            "start_offset": start_offset,
            "access_token": facebook_token,
        }
        files = {"video_file_chunk": video_data}
        
        res_transfer = requests.post(url, data=transfer_params, files=files).json()
        if "start_offset" not in res_transfer:
            print(f"[ERROR] Transfer failed: {res_transfer}")
            return None

        # --- BƯỚC 3: HOÀN TẤT (PHASE FINISH) ---
        finish_params = {
            "upload_phase": "finish",
            "upload_session_id": upload_session_id,
            "access_token": facebook_token,
            "title": title,
            "description": description,
        }
        
        res_finish = requests.post(url, data=finish_params).json()
        
        if res_finish.get("success"):
            print(f"[SUCCESS] Video uploaded. ID: {video_id}")
            return video_id
        else:
            print(f"[ERROR] Finish failed: {res_finish}")
            return None

    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return None

async def upload_media_to_facebook(
	client: TelegramClient,
	message: object,
	facebook_token: str,
	facebook_page_id: str,
	app_id: str | None = None,
	description: str | None = None,
	max_size: int = 20 * 1024 * 1024,
) -> str | None:
	"""
	Download media from Telegram and upload to Facebook as unpublished.
	
	IMPORTANT: Videos require app_id (for Resumable Upload API). Photos only need token/page_id.
	
	Args:
		client: Telegram client instance
		message: Telegram message object with media
		facebook_token: Facebook page access token
		facebook_page_id: Facebook page ID
		app_id: Facebook app ID (REQUIRED for videos, optional for photos)
		max_size: Maximum file size in bytes (default 20MB)
	
	Returns:
		Facebook media ID if successful, None otherwise
	"""
	# Check if message has media
	if not hasattr(message, "media") or not message.media:
		return None
	
	# Get file size
	file_size = None
	if hasattr(message.media, "document"):
		file_size = getattr(message.media.document, "size", None)
	elif hasattr(message.media, "photo"):
		# For photos, we need to get the largest size
		if hasattr(message.media.photo, "sizes"):
			sizes = message.media.photo.sizes
			if sizes and len(sizes) > 0:
				# Get the biggest size
				biggest = max(sizes, key=lambda s: getattr(s, "size", 0) if hasattr(s, "size") else 0)
				file_size = getattr(biggest, "size", None)
	
	# Check if size is less than max_size
	if file_size and file_size > max_size:
		print(f"[SKIP] Media too large: {file_size / 1024 / 1024:.2f}MB > {max_size / 1024 / 1024:.0f}MB")
		return None
	
	# Download media to temp file
	temp_path = None
	try:
		with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file:
			temp_path = temp_file.name
		
		size_str = f"{file_size / 1024 / 1024:.2f}MB" if file_size else "unknown size"
		print(f"[DOWNLOAD] Downloading media ({size_str})...")
		await client.download_media(message, file=temp_path)
		
		# Verify downloaded file size
		downloaded_size = os.path.getsize(temp_path)
		if downloaded_size > max_size:
			print(f"[SKIP] Downloaded file too large: {downloaded_size / 1024 / 1024:.2f}MB > {max_size / 1024 / 1024:.0f}MB")
			os.unlink(temp_path)
			return None
		
		# Determine media type
		is_video = is_video_message(message)
		
		# For videos, REQUIRE Resumable Upload API with app_id
		if is_video:
			if not app_id:
				print("[SKIP] Videos require FACEBOOK_APP_ID for Resumable Upload API. Set it in your .env file")
				return None
			
			media_caption = (description or "") or (getattr(message, "message", "") or "")
			video_id = await upload_video_to_facebook_resumable(
				file_path=temp_path,
				facebook_token=facebook_token,
				facebook_page_id=facebook_page_id,
				app_id=app_id,
				description=media_caption,
			)
			os.unlink(temp_path)
			return video_id
		
		# For photos, use simple upload
		endpoint = f"https://graph.facebook.com/{facebook_page_id}/photos"
		
		with open(temp_path, "rb") as media_file:
			files = {"source": media_file}
			data = {
				"access_token": facebook_token,
				"published": "false",  # Unpublished mode
			}
			
			print(f"[UPLOAD] Uploading to Facebook as unpublished photo...")
			response = requests.post(endpoint, data=data, files=files)
		
		# Clean up temp file
		os.unlink(temp_path)
		temp_path = None
		
		if response.status_code == 200:
			result = response.json()
			media_fbid = result.get("id")
			print(f"[SUCCESS] Uploaded to Facebook, media_fbid: {media_fbid}")
			return media_fbid
		else:
			print(f"[ERROR] Facebook upload failed: {response.status_code} - {response.text}")
			return None
			
	except Exception as error:
		print(f"[ERROR] Failed to download/upload media: {error}")
		if temp_path and os.path.exists(temp_path):
			os.unlink(temp_path)
		return None


def create_facebook_post_with_media(
	facebook_token: str,
	facebook_page_id: str,
	message: str,
	media_fbids: list[str],
) -> bool:
	"""
	Create a Facebook post with attached media.
	
	Args:
		facebook_token: Facebook page access token
		facebook_page_id: Facebook page ID
		message: Post message text
		media_fbids: List of Facebook media IDs
	
	Returns:
		True if successful, False otherwise
	"""
	if not media_fbids:
		print("[ERROR] No media IDs provided")
		return False
	
	post_url = f"https://graph.facebook.com/{facebook_page_id}/feed"
	
	# Prepare attached_media parameter
	attached_media = [{"media_fbid": fbid} for fbid in media_fbids]
	
	payload = {
		"access_token": facebook_token,
		"message": message,
		"attached_media": json.dumps(attached_media),
	}
	
	try:
		print(f"[POST] Creating Facebook post with {len(media_fbids)} media item(s)...")
		response = requests.post(post_url, data=payload)
		
		if response.status_code == 200:
			result = response.json()
			post_id = result.get("id")
			print(f"[SUCCESS] Created Facebook post: {post_id}")
			return True
		else:
			print(f"[ERROR] Facebook post creation failed: {response.status_code} - {response.text}")
			return False
			
	except Exception as error:
		print(f"[ERROR] Failed to create Facebook post: {error}")
		return False


async def upload_selected_media_to_facebook(
	client: TelegramClient,
	gemini_model: object | None,
	selected_media: dict,
	facebook_token: str,
	facebook_page_id: str,
	facebook_app_id: str | None = None,
) -> bool:
	"""
	Download media from Telegram if size < 20MB, upload to Facebook unpublished,
	then create a post with the media and preview text.
	
	Args:
		client: Telegram client instance
		gemini_model: Gemini model for text sanitization
		selected_media: Selected media dict from select_most_relevant_media
		facebook_token: Facebook page access token
		facebook_page_id: Facebook page ID
		facebook_app_id: Facebook app ID (optional, enables Resumable Upload API for videos)
	
	Returns:
		True if successful, False otherwise
	"""
	# Get messages list
	messages = selected_media.get("messages", [])
	if not messages:
		message = selected_media.get("message")
		if message:
			messages = [message]
	
	if not messages:
		print("[ERROR] No messages found in selected_media")
		return False
	
	text_preview = selected_media.get("text_preview", "")
	sanitized_message = sanitize_facebook_message(gemini_model, text_preview)
	media_fbids = []
	
	# Process each message in the group (or single message)
	for msg in messages:
		media_fbid = await upload_media_to_facebook(
			client=client,
			message=msg,
			facebook_token=facebook_token,
			facebook_page_id=facebook_page_id,
			app_id=facebook_app_id,
			description=sanitized_message,
		)
		
		if media_fbid:
			media_fbids.append(media_fbid)
	
	if not media_fbids:
		print("[ERROR] No media items were successfully uploaded")
		return False
	
	# Create Facebook post with attached media
	return create_facebook_post_with_media(
		facebook_token=facebook_token,
		facebook_page_id=facebook_page_id,
		message=sanitized_message,
		media_fbids=media_fbids,
	)
