import os
from typing import Optional
import google.generativeai as genai


def create_gemini_model() -> Optional[genai.GenerativeModel]:
	"""Create and configure a Gemini model instance for selection tasks."""
	api_key = os.getenv("GEMINI_API_KEY", "").strip()
	if not api_key:
		return None

	genai.configure(api_key=api_key)
	return genai.GenerativeModel("gemini-2.5-flash-lite")


def select_most_relevant_media(
	model: Optional[genai.GenerativeModel],
	text_messages: list[str],
	media_messages: list[dict],
) -> Optional[dict]:
	"""
	Compare text messages with media messages and return the most relevant media message.
	
	Args:
		model: Gemini model instance
		text_messages: List of raw text content from text channels
		media_messages: List of media message dictionaries with text_preview, message_id, grouped_id, etc.
	
	Returns:
		The most relevant media message dict, or None if no match found
	"""
	if not text_messages or not media_messages:
		return None

	if model is None:
		print("[WARN] Gemini is disabled (missing GEMINI_API_KEY). Selection cannot proceed.")
		return None

	# Prepare text messages content
	joined_text_messages = "\n".join(f"{i+1}. {msg}" for i, msg in enumerate(text_messages))
	
	# Prepare media messages with their metadata (simplified: ID and preview only)
	media_list = []
	for i, media_msg in enumerate(media_messages):
		media_id = media_msg.get("grouped_id") or media_msg.get("message_id")
		text_preview = media_msg.get("text_preview", "")
		
		media_list.append(
			f"Media #{i+1}:\n"
			f"  ID: {media_id}\n"
			f"  Nội dung: {text_preview}"
		)
	
	joined_media_messages = "\n\n".join(media_list)
	
	prompt = f"""Bạn là một hệ thống AI chuyên phân tích và so khớp tin nhắn. Nhiệm vụ của bạn là phân tích các tin nhắn văn bản và tin nhắn có media, sau đó xác định tin nhắn media nào phù hợp nhất với nội dung văn bản.

TIN NHẮN VĂN BẢN (từ kênh tổng hợp):
{joined_text_messages}

TIN NHẮN MEDIA (từ kênh media):
{joined_media_messages}

YÊU CẦU:
1. Phân tích ý nghĩa ngữ nghĩa của các tin nhắn văn bản
2. So sánh với nội dung preview của từng tin nhắn media
3. Chọn tin nhắn media PHÙ HỢP NHẤT hoặc liên quan nhất đến nội dung văn bản
4. Nếu KHÔNG có tin nhắn media nào phù hợp, trả về "NONE"

ĐỊNH DẠNG TRẢ LỜI:
Bạn CHỈ được trả về số thứ tự của media (ví dụ: "1", "2", "3", v.v.) hoặc "NONE".
Không được giải thích thêm, chỉ trả về SỐ hoặc "NONE".

Lựa chọn của bạn:"""

	try:
		response = model.generate_content(prompt)
		result = (getattr(response, "text", "") or "").strip()
		
		print(f"[GEMINI SELECTION] Raw response: {result}")
		
		# Parse the response
		if result.upper() == "NONE":
			print("[SELECTION] Gemini found no relevant media message")
			return None
		
		try:
			selected_index = int(result) - 1  # Convert to 0-based index
			if 0 <= selected_index < len(media_messages):
				selected = media_messages[selected_index]
				print(f"[SELECTION] Gemini selected media #{selected_index + 1}: "
				      f"ID={selected.get('grouped_id') or selected.get('message_id')}, "
				      f"Type={selected.get('media_type')}")
				return selected
			else:
				print(f"[WARN] Gemini returned invalid index: {selected_index + 1}")
				return None
		except ValueError:
			print(f"[WARN] Gemini returned unparseable response: {result}")
			return None
			
	except Exception as error:
		print(f"[ERROR] Gemini selection error: {error}")
		return None


def format_selection_result(text_message_count: int, media_message_count: int, selected_media: Optional[dict]) -> str:
	"""Format selection results for display."""
	border = "=" * 72
	result = [
		f"\n{border}",
		"SELECTION MESSAGE SERVICE - RESULTS",
		f"{border}",
		f"Text messages analyzed: {text_message_count}",
		f"Media messages analyzed: {media_message_count}",
		f"{border}",
	]
	
	if selected_media:
		media_id = selected_media.get("grouped_id") or selected_media.get("message_id")
		media_type = selected_media.get("media_type", "unknown")
		channel_name = selected_media.get("channel_name", "unknown")
		timestamp = selected_media.get("timestamp", "")
		text_preview = selected_media.get("text_preview", "")
		message_ids = selected_media.get("message_ids", [])
		
		result.extend([
			"SELECTED MEDIA:",
			f"  Media ID: {media_id}",
			f"  Message IDs: {', '.join(map(str, message_ids))}",
			f"  Type: {media_type.upper()}",
			f"  Channel: {channel_name}",
			f"  Time: {timestamp}",
			f"  Preview: {text_preview}",
		])
		
		if selected_media.get("grouped_id"):
			result.append(f"  Album: {len(message_ids)} items in group")
	else:
		result.append("NO RELEVANT MEDIA FOUND")
	
	result.append(border)
	return "\n".join(result)
