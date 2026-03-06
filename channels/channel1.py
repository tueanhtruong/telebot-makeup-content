"""Clone messages from a single Telegram channel and log them."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from telethon import TelegramClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
	sys.path.insert(0, str(ROOT_DIR))

from services.telegram import clone_messages_from_channels
from services.llm import create_llm_client
from services.facebook import upload_feed


load_dotenv()

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_required_env(name: str) -> str:
	value = os.getenv(name, "").strip()
	if not value:
		raise ValueError(f"Missing required environment variable: {name}")
	return value


def parse_channel_id(raw: str) -> Optional[int]:
	if not raw:
		return None
	try:
		return int(raw)
	except ValueError:
		logger.warning("Invalid TELEGRAM_CHANNEL_1_ID: %s", raw)
		return None


def preview(text: str, limit: int = 120) -> str:
	text = (text or "").strip().replace("\n", " ")
	if len(text) <= limit:
		return text
	return f"{text[:limit]}..."


api_id = int(get_required_env("TELEGRAM_API_ID"))
api_hash = get_required_env("TELEGRAM_API_HASH")
session_name = os.getenv("TELEGRAM_SESSION_NAME", "telethon_session").strip() or "telethon_session"

channel_username = os.getenv("TELEGRAM_CHANNEL_1_USERNAME", "").strip()
channel_id = parse_channel_id(os.getenv("TELEGRAM_CHANNEL_1_ID", "").strip())

window_seconds = int(os.getenv("TELEGRAM_WINDOW_SECONDS", "43200"))
fetch_limit = int(os.getenv("TELEGRAM_FETCH_LIMIT", "500"))
content_filter = os.getenv("TELEGRAM_CONTENT_FILTER", "text").strip().lower() or "text"
# llm_provider = os.getenv("LLM_PROVIDER", "grok").strip().lower() or "grok"
llm_provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower() or "gemini"


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
- xuyên tạc lịch sử, chủ quyền, vai trò lãnh đạo của Nhà nước VN
- vu khống/xúc phạm tổ chức, cá nhân chưa được xác minh
- nghi ngờ → loại bỏ.

YÊU CẦU XỬ LÝ DỮ LIỆU:
- Tự động xác định những chủ đề chính có tác động đến địa chính trị, quân sự, chính trị hoặc kinh tế
- Giữ lại chỉ những thông tin có giá trị chiến lược
- Tóm tắt thành các câu ngắn, mạnh mẽ, dễ hành động

LĨNH VỰC PHÂN TÍCH:
- Tự động nhóm dựa trên dữ liệu, không cần đặt câu hỏi
- Địa chính trị, quân sự, chính trị, kinh tế, sự kiện khác

TÔN GIỌNG & PHONG CÁCH:
- Trung lập nhưng CÓ TÍNH SẮC SẢO, châm biếm tinh tế (cynical undertone)
- Sử dụng thuật ngữ chuyên môn: địa chính trị, lưỡng dụng, răn đe hạt nhân, phi đối xứng, quyền lực mềm, chiến tranh proxy, hiệp lực lệch cân
- Không đặt câu hỏi, chỉ trình bày tổng hợp
- Tránh từ ngữ mạnh/bạo lực thô: thay "chiến tranh" bằng "xung đột vũ trang", "tấn công" bằng "hoạt động quân sự"

ĐỊNH DẠNG CHO FACEBOOK (MOBILE-FIRST):
- Sử dụng dấu gạch ngang (-) để phân tách các dòng thông tin
- Tiêu đề VIẾT HOA, có sức nặng
- Emoji được dùng: ⚔️ 🏛️ 📊 📌 (tránh các emoji có thể bị gắn cờ)
- Bullet points ngắn, mỗi dòng 1-2 câu thông tin giá trị
- Không dùng ký tự đặc biệt phức tạp, không dùng bảng biểu
- Khoảng cách rõ ràng giữa các phần để dễ đọc trên di động

CẤU TRÚC ĐẦU RA:

TIÊU ĐỀ BÁO CÁO - VIẾT HOA, GỢI HỨNG THÚ

Với mỗi chủ đề:
- Sử dụng emoji thích hợp (⚔️ cho quân sự, 🏛️ cho chính trị, 📊 cho kinh tế, 📌 cho sự kiện khác)
- Tiêu đề chủ đề VIẾT HOA
- 2-4 dòng thông tin chi tiết

Nguồn: t.me/{channelName}

HASHTAG (chỉ sử dụng hashtag an toàn, phổ biến, không bị gắn cờ và viết liền không dấu)

NHỮNG GÌ CẦN TRÁNH:
- Không đưa ra lời khuyên đầu tư hoặc khuyến cáo hành động
- Không phán xét về quyền lợi của các bên (trung lập)
- Không sử dụng từ ngữ có thể bị Facebook gắn cờ
- Không đặt câu hỏi - chỉ kết luận
- Không nhận xét chính trị nội bộ

HƯỚNG DẪN CUỐI:
- Tìm và thay thế từ ngữ nhạy cảm bằng từ chuyên môn phù hợp
- Mỗi thông tin phải CÓ CỤ THỂ: con số, tên, địa điểm, thời gian (nếu có)
- Giữ tổng cộng dưới 500 từ, mật độ thông tin cao
- Đảm bảo mỗi câu đều có giá trị

---
BẮT ĐẦU XỬ LÝ DỮ LIỆU:
{joined_messages}"""
	return prompt


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
			logger.info("\nAsking %s for strategic analysis...", llm_provider.upper())
			llm_client = create_llm_client(llm_provider)
			response = llm_client.ask(prompt, max_retries=2)
			
			if response:
				logger.info("\n" + "="*72)
				logger.info("AI ANALYSIS RESULT (%s):", response.provider.upper())
				logger.info("="*72)
				logger.info(response.text)
				logger.info("="*72)
				
				# Post analysis result to Facebook
				logger.info("\nPosting analysis to Facebook...")
				post_id = upload_feed(response.text)
				if post_id:
					logger.info("Successfully posted to Facebook. Post ID: %s", post_id)
				else:
					logger.warning("Failed to post to Facebook")
			else:
				logger.error("Failed to get response from %s", llm_provider.upper())
	else:
		logger.info("No text messages collected for analysis")


if __name__ == "__main__":
	asyncio.run(main())
