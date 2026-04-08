"""Clone messages from a single Telegram channel and log them."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from telethon import TelegramClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

from channels.commonsHelpers import load_channel_runtime_config
from services.telegram import clone_messages_from_channels
from services.llm import create_llm_client
from services.facebook import upload_feed, upload_feed_with_gradient, add_comment


load_dotenv()

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_required_env(name: str) -> str:
	value = os.getenv(name, "").strip()
	if not value:
		raise ValueError(f"Missing required environment variable: {name}")
	return value


def preview(text: str, limit: int = 120) -> str:
	text = (text or "").strip().replace("\n", " ")
	if len(text) <= limit:
		return text
	return f"{text[:limit]}..."


api_id = int(get_required_env("TELEGRAM_API_ID"))
api_hash = get_required_env("TELEGRAM_API_HASH")
session_name = os.getenv("TELEGRAM_SESSION_NAME", "telethon_session").strip() or "telethon_session"

runtime_config = load_channel_runtime_config(
	default_content_filter="text",
	default_window_seconds=3600,
	default_fetch_limit=500,
	default_llm_provider="openrouter",
	logger=logger,
)

channel_username = runtime_config.channel_username
channel_id = runtime_config.channel_id

window_seconds = runtime_config.window_seconds
fetch_limit = runtime_config.fetch_limit
content_filter = runtime_config.content_filter
llm_provider = runtime_config.llm_provider


client = TelegramClient(session_name, api_id, api_hash)


def _build_analysis_prompt(messages: list[str], channelName: str = '') -> str:
	"""Build the strategic analysis prompt from text messages."""
	if not messages:
		return ""

	joined_messages = "\n".join(f"- {msg}" for msg in messages if msg.strip())
	prompt = f"""
NHIỆM VỤ CHÍNH: Nhận dữ liệu thô không có cấu trúc, lọc bỏ thông tin vô nghĩa 
và nội dung vi phạm pháp luật Việt Nam, sau đó tự động nhóm lại thành các chủ 
đề quan trọng theo nội dung dữ liệu.

LỌC DỮ LIỆU LOẠI BỎ NỘI DUNG:
- thông tin không liên quan, tin đồn, dữ liệu trùng lặp
- liên quan nội bộ chính trị Việt Nam (dù tích cực hay tiêu cực)
- xuyên tạc lịch sử, chủ quyền, vai trò lãnh đạo của Nhà nước Việt Nam
- vu khống/xúc phạm tổ chức, cá nhân chưa được xác minh

YÊU CẦU XỬ LÝ DỮ LIỆU:
- Tự động xác định những chủ đề chính có tác động đến địa chính trị, quân sự, kinh tế, các loại tài sản, các tập đoàn lớn, các cá nhân quan trọng, sự kiện nổi bật
- Tóm tắt thành các câu ngắn, mạnh mẽ, dễ hành động
- Mỗi thông tin được trình bày bằng tiếng Việt có dấu

LĨNH VỰC PHÂN TÍCH:
- Tự động nhóm dựa trên dữ liệu, không cần đặt câu hỏi
- Địa chính trị, quân sự, chính trị, kinh tế, sự kiện khác

TÔN GIỌNG & PHONG CÁCH:
- Trung lập nhưng CÓ TÍNH SẮC SẢO, châm biếm tinh tế (cynical undertone)
- Sử dụng các thuật ngữ chuyên môn, tránh từ ngữ cảm tính
- Không đặt câu hỏi, chỉ trình bày tổng hợp
- Tránh những từ ngữ mạnh/bạo lực thô: ví dụ thay "chiến tranh" bằng "xung đột vũ trang", thay "tấn công" bằng "hoạt động quân sự"

ĐỊNH DẠNG CHO FACEBOOK (MOBILE-FIRST):
- Sử dụng dấu gạch ngang (-) để phân tách các dòng thông tin
- Tiêu đề VIẾT HOA, có sức nặng
- Emoji được dùng: ⚔️ 🏛️ 📊 📌 (tránh các emoji có thể bị gắn cờ)
- Bullet points ngắn, mỗi dòng 1-2 câu thông tin giá trị
- Không dùng ký tự đặc biệt phức tạp, không dùng bảng biểu
- Khoảng cách rõ ràng giữa các phần để dễ đọc trên di động

CẤU TRÚC ĐẦU RA - định dạng JSON với các trường:
- title: Bao gồm 3 dòng, 1 dòng TIÊU ĐỀ NỘI DUNG CHUNG - VIẾT HOA, GỢI HỨNG THÚ, 1 dòng Tổng hợp từ t.me/{channelName} - xem thêm dưới comments, 1 dòng HASHTAG (chỉ sử dụng hashtag an toàn, phổ biến, không bị gắn cờ và viết liền không dấu).
- topics: Một mảng các chủ đề, mỗi chủ đề có:
	- title: Bao gồm emoji thích hợp (⚔️ cho quân sự, 🏛️ cho chính trị, 📊 cho kinh tế, 📌 cho sự kiện khác) và tên chủ đề VIẾT HOA.
	- details: Một mảng các điểm chi tiết, mỗi điểm là một câu ngắn gọn, mạnh mẽ, chứa thông tin giá trị cụ thể (con số, tên, địa điểm, thời gian nếu có).

NHỮNG GÌ CẦN TRÁNH:
- Không đưa ra lời khuyên đầu tư hoặc khuyến cáo hành động
- Không phán xét về quyền lợi của các bên (trung lập)
- Không sử dụng từ ngữ có thể bị Facebook gắn cờ
- Không đặt câu hỏi - chỉ kết luận
- Không nhận xét chính trị nội bộ

HƯỚNG DẪN CUỐI:
- Tìm và thay thế từ ngữ nhạy cảm bằng từ chuyên môn phù hợp
- Mỗi thông tin phải CÓ CỤ THỂ: con số, tên, địa điểm, thời gian (nếu có)
- Đảm bảo mỗi câu đều có giá trị
- Đảm bảo nhiều chủ đề khác nhau nếu dữ liệu có nhiều khía cạnh
- Chỉ trả về kết quả đã được định dạng JSON, không giải thích gì thêm

---
BẮT ĐẦU XỬ LÝ DỮ LIỆU:
{joined_messages}"""
	return prompt


def _strip_json_code_fences(text: str) -> str:
	"""Remove markdown code fences from JSON response text if present."""
	value = (text or "").strip()
	if not value:
		return ""

	if value.startswith("```"):
		lines = value.splitlines()
		if lines and lines[0].strip().lower().startswith("```json"):
			lines = lines[1:]
		elif lines and lines[0].strip().startswith("```"):
			lines = lines[1:]

		if lines and lines[-1].strip() == "```":
			lines = lines[:-1]

		return "\n".join(lines).strip()

	return value


def _post_analysis_to_facebook(analysis_json: str) -> Optional[str]:
	"""Parse analysis JSON and post to Facebook with gradient background and topic comments.
	
	Args:
		analysis_json: JSON string with 'title' and 'topics' fields
	
	Returns:
		Post ID if successful, None otherwise
	"""
	try:
		# Parse JSON response
		cleaned_json = _strip_json_code_fences(analysis_json)
		data = json.loads(cleaned_json)
		title = data.get("title", "")
		topics = data.get("topics", [])
		
		if not title:
			logger.warning("No title found in analysis JSON")
			return None
		
		# Post title with gradient background
		logger.info("Posting title to Facebook with gradient background...")
		post_id = upload_feed_with_gradient(title)
		
		if not post_id:
			logger.warning("Failed to post title to Facebook")
			return None
		
		logger.info("Successfully posted title. Post ID: %s", post_id)
		
		# Add comments for each topic
		for idx, topic in enumerate(topics):
			topic_title = topic.get("title", "")
			topic_details = topic.get("details", [])
			
			if not topic_title:
				logger.warning("Skipping topic %d: no title", idx + 1)
				continue
			
			# Format comment: title + details as bullet points
			comment_lines = [topic_title, ""]
			for detail in topic_details:
				if detail and detail.strip():
					comment_lines.append(f"- {detail}")
			
			comment_text = "\n".join(comment_lines)
			
			logger.info("Adding comment %d/%d to post...", idx + 1, len(topics))
			comment_id = add_comment(post_id, comment_text)
			
			if comment_id:
				logger.info("Successfully added comment %d. Comment ID: %s", idx + 1, comment_id)
			else:
				logger.warning("Failed to add comment %d", idx + 1)
		
		return post_id
	
	except json.JSONDecodeError as error:
		logger.error("Failed to parse analysis JSON: %s", error)
		return None
	except Exception as error:
		logger.error("Error posting analysis to Facebook: %s", error)
		return None


async def main() -> None:
	channel_usernames = [channel_username] if channel_username else []
	channel_ids = [channel_id] if channel_id is not None else []

	if not channel_usernames and not channel_ids:
		raise ValueError("Set TELEGRAM_CHANNEL_1_USERNAME or TELEGRAM_CHANNEL_1_ID")

	logger.info("Cloning messages from channel 1")
	logger.info("Content filter: %s", content_filter)
	logger.info("Window seconds: %s", window_seconds)
	logger.info("Fetch limit: %s", fetch_limit)

	await client.start()
	results = await clone_messages_from_channels(
		client,
		channel_usernames=channel_usernames,
		channel_ids=channel_ids,
		window_seconds=window_seconds,
		fetch_limit=fetch_limit,
		content_filter=content_filter,
	)
	
	# Collect all text messages for LLM analysis
	text_messages = [item.get("text", "") for item in results if item.get("has_text")]
	if text_messages:
		logger.info("Collected %s text message(s) for analysis", len(text_messages))
		prompt = _build_analysis_prompt(text_messages, channelName=channel_username)
 		
		######################################################################################
		# Post analysis result to Facebook temporarily without LLM analysis					 
		# logger.info("\nPosting analysis to Facebook...")                                   
		# post_id = upload_feed(prompt)
		# if post_id:
		# 	logger.info("Successfully posted to Facebook. Post ID: %s", post_id)
		# else:
		# 	logger.warning("Failed to post to Facebook")
		######################################################################################

		if prompt:
			logger.info("\n" + "="*72)
			logger.info("GENERATED LLM PROMPT:")
			logger.info(prompt)
			logger.info("="*72)
			
			# Ask LLM for analysis
			# logger.info("\nAsking %s for strategic analysis...", llm_provider.upper())
			llm_client = create_llm_client(llm_provider)
			response = llm_client.ask(prompt, max_retries=2)
			
			if response:
				logger.info("\n" + "="*72)
				logger.info("AI ANALYSIS RESULT (%s):", response.provider.upper())
				logger.info("="*72)
				logger.info(response.text)
				logger.info("="*72)

			logger.info("\nPosting analysis to Facebook...")
			post_id = _post_analysis_to_facebook(response.text)
			if post_id:
				logger.info("Successfully posted analysis to Facebook. Post ID: %s", post_id)
			else:
				logger.warning("Failed to post analysis to Facebook")
		else:
			logger.error("Failed to get response from %s", llm_provider.upper())
	else:
		logger.info("No text messages collected for analysis")


if __name__ == "__main__":
	asyncio.run(main())
