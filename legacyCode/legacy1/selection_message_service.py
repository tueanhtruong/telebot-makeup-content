import os
import re
from typing import Any, Optional
import google.generativeai as genai


def create_gemini_model() -> Optional[genai.GenerativeModel]:
	"""Create and configure a Gemini model instance for selection tasks."""
	api_key = os.getenv("GEMINI_API_KEY", "").strip()
	if not api_key:
		return None

	genai.configure(api_key=api_key)
	return genai.GenerativeModel("gemini-3-flash-preview")


def print_gemini_token_usage(
	model: Optional[genai.GenerativeModel],
	prompt: str,
	response: Any,
	label: str,
) -> None:
	usage = getattr(response, "usage_metadata", None)
	prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
	output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
	total_tokens = getattr(usage, "total_token_count", None) if usage else None

	if any(value is not None for value in [prompt_tokens, output_tokens, total_tokens]):
		print(
			f"[TOKEN USAGE][{label}] "
			f"prompt={prompt_tokens if prompt_tokens is not None else 'n/a'}, "
			f"output={output_tokens if output_tokens is not None else 'n/a'}, "
			f"total={total_tokens if total_tokens is not None else 'n/a'}"
		)
		return

	if model is not None:
		try:
			count_result = model.count_tokens(prompt)
			estimated_prompt_tokens = getattr(count_result, "total_tokens", None)
			if estimated_prompt_tokens is not None:
				print(f"[TOKEN USAGE][{label}] prompt≈{estimated_prompt_tokens}, output=n/a, total=n/a")
				return
		except Exception:
			pass

	print(f"[TOKEN USAGE][{label}] unavailable")


def select_most_relevant_media(
	model: Optional[genai.GenerativeModel],
	text_messages: list[str],
	media_messages: list[dict],
) -> Optional[list[dict]]:
	"""
	Compare text messages with media messages and return all relevant media messages.
	
	Args:
		model: Gemini model instance
		text_messages: List of raw text content from text channels
		media_messages: List of media message dictionaries with text_preview, message_id, grouped_id, etc.
	
	Returns:
		A list of relevant media message dicts, or None if no match found
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
	
	prompt = f"""
Bạn là một hệ thống AI chuyên phân tích và so khớp tin nhắn. Nhiệm vụ của bạn là phân tích các tin nhắn văn bản và tin nhắn có media, sau đó xác định tin nhắn media nào phù hợp nhất với nội dung văn bản.
TIN NHẮN VĂN BẢN (từ kênh tổng hợp):
{joined_text_messages}
TIN NHẮN MEDIA (từ kênh media):
{joined_media_messages}
YÊU CẦU:
1. Phân tích ý nghĩa ngữ nghĩa của các tin nhắn văn bản
2. So sánh với nội dung preview của từng tin nhắn media
3. Chọn tất cả tin nhắn media PHÙ HỢP hoặc liên quan đến nội dung tin nhắn văn bản trả về tất cả các số thứ tự của media được chọn cách nhau bằng dấu phẩy ví dụ: 1, 3, 5
4. Nếu KHÔNG có tin nhắn media nào phù hợp, trả về "NONE"
ĐỊNH DẠNG TRẢ LỜI:
Bạn CHỈ được trả về số thứ tự của media ví dụ: 1, 3, 5 hoặc NONE.
Không được giải thích thêm, chỉ trả về SỐ hoặc NONE.

Lựa chọn của bạn:"""

	try:
		print("\n" + "="*72)
		print("AI MODEL PROMPT (SELECTION):")
		print("="*72)
		print(prompt)
		print("="*72 + "\n")
		
		response = model.generate_content(prompt)
		result = (getattr(response, "text", "") or "").strip()
		print_gemini_token_usage(model, prompt, response, "SELECTION")
		
		print("\n" + "="*72)
		print("AI MODEL RAW RESPONSE (SELECTION):")
		print("="*72)
		print(result)
		print("="*72 + "\n")
		
		
		print(f"[GEMINI SELECTION] Raw response: {result}")
		
		# Parse the response using regex to extract all numeric indices
		if result.upper() == "NONE":
			print("[SELECTION] Gemini found no relevant media message, returning last media")
			if not media_messages:
				return None
			fallback_media = dict(media_messages[-1])
			fallback_media["selection_text_context"] = joined_text_messages
			return [fallback_media]
		
		# Use regex to find all numeric indices in the response
		indices_matches = re.findall(r'\d+', result)
		
		if not indices_matches:
			print(f"[WARN] Gemini returned no numeric indices: {result}, returning last media")
			if not media_messages:
				return None
			fallback_media = dict(media_messages[-1])
			fallback_media["selection_text_context"] = joined_text_messages
			return [fallback_media]
		
		# Convert to integers and keep only distinct ones
		selected_indices = sorted(set(int(idx) for idx in indices_matches))
		print(f"[SELECTION] Extracted indices from response: {selected_indices}")
		
		# Filter valid indices and collect corresponding media messages
		selected_medias = []
		for idx in selected_indices:
			media_idx = idx - 1  # Convert to 0-based index
			if 0 <= media_idx < len(media_messages):
				selected = dict(media_messages[media_idx])
				selected["selection_text_context"] = joined_text_messages
				selected_medias.append(selected)
				print(f"[SELECTION] Selected media #{idx}: "
				      f"ID={selected.get('grouped_id') or selected.get('message_id')}, "
				      f"Type={selected.get('media_type')}")
			else:
				print(f"[WARN] Invalid index {idx} (out of range)")
		
		if not selected_medias:
			print("[SELECTION] No valid media indices found, returning last media")
			if not media_messages:
				return None
			fallback_media = dict(media_messages[-1])
			fallback_media["selection_text_context"] = joined_text_messages
			return [fallback_media]
		
		return selected_medias
			
	except Exception as error:
		print(f"[ERROR] Gemini selection error: {error}")
		return None


def format_selection_result(text_message_count: int, media_message_count: int, selected_medias: Optional[list[dict]]) -> str:
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
	
	if selected_medias:
		result.append(f"SELECTED MEDIA: {len(selected_medias)} item(s)")
		
		for i, selected_media in enumerate(selected_medias, 1):
			media_id = selected_media.get("grouped_id") or selected_media.get("message_id")
			media_type = selected_media.get("media_type", "unknown")
			channel_name = selected_media.get("channel_name", "unknown")
			timestamp = selected_media.get("timestamp", "")
			text_preview = selected_media.get("text_preview", "")
			message_ids = selected_media.get("message_ids", [])
			
			result.extend([
				f"  [{i}] Media ID: {media_id}",
				f"      Message IDs: {', '.join(map(str, message_ids))}",
				f"      Type: {media_type.upper()}",
				f"      Channel: {channel_name}",
				f"      Time: {timestamp}",
				f"      Preview: {text_preview}",
			])
			
			if selected_media.get("grouped_id"):
				result.append(f"      Album: {len(message_ids)} items in group")
	else:
		result.append("NO RELEVANT MEDIA FOUND")
	
	result.append(border)
	return "\n".join(result)
