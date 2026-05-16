"""LLM utilities for text sanitization."""

import json
import logging
import re
from typing import Optional

from services.llm import create_llm_client


logger = logging.getLogger(__name__)


def create_sanitization_prompt(text: str, channel_name: str = '') -> str:
    """Create a prompt to ask LLM to sanitize text."""
    return f"""
NHIỆM VỤ
Bạn là chuyên gia dịch thuật cho những nội dung ngắn vui vẻ. Hãy dịch toàn bộ nội dung dưới đây sang tiếng Việt.
LỌC DỮ LIỆU:
- Loại bỏ thông tin không liên quan hoặc trùng lặp
- Loại bỏ ký tự đặc biệt, hashtag, @mentions, liên kết (URLs) và giữ lại các icon cảm xúc (emojis).
ĐỊNH DẠNG ĐẦU RA: văn bản gồm các phần sau
	1. Nội dung dịch
		- Viết lại nội dung tiếng Việt một cách tự nhiên, không có từ ngữ nhạy cảm
		- Tách thành các đoạn ngắn nếu quá dài, mỗi đoạn 2–4 câu
		- Thêm dòng trống giữa các đoạn để dễ đọc
	2. Hashtag
		- Đặt cuối bài, cách nội dung 1 dòng trống
		- Chỉ dùng hashtag phổ biến, an toàn, viết liền không dấu
---
Nội dung cần dịch:
{text}
"""


async def sanitize_text_with_llm(text: str, llm_provider: str = "grok") -> Optional[str]:
    """Use LLM to sanitize the text."""
    if not text or not text.strip():
        return None
    
    try:
        client = create_llm_client(llm_provider)
        prompt = create_sanitization_prompt(text)
        logger.info("\n" + "="*72)
        logger.info("GENERATED LLM PROMPT:")
        logger.info(prompt)
        logger.info("="*72)
        
        response = client.ask(prompt)
        
        if not response or not response.text:
            logger.warning("LLM returned no response")
            return None
        
        sanitized = response.text.strip()
        if sanitized:
            logger.info("Text sanitized by %s", response.provider)
            return sanitized
        return None
    except Exception as error:
        logger.error("Failed to sanitize text with %s: %s", llm_provider, error)
        return None


def remove_tags(text: str) -> str:
    """Remove JUST IN: hashtags and @mentions from text."""
    cleaned = re.sub(r"JUST IN:\s*", "", text or "", flags=re.IGNORECASE)
    cleaned = re.sub(r"#[\w-]+", "", cleaned)
    cleaned = re.sub(r"@[\w-]+", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def remove_links_content(text: str) -> str:
    """Remove link content, including markdown and URLs."""
    cleaned = text or ""
    # Remove markdown links
    cleaned = re.sub(r"\[[^\]]*\]\([^\)]*\)", "", cleaned)
    # Remove HTML links
    cleaned = re.sub(r"<a\s+[^>]*>.*?</a>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    # Remove bare URLs
    cleaned = re.sub(r"(?:https?://|www\.)\S+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def get_text_except_last_line_if_link(text: str) -> str:
    """Return text except the last line if it contains a link."""
    if not text:
        return text
    
    link_pattern = r"(?:https?://|www\.)\S+|\[[^\]]*\]\([^\)]*\)|<a\s+[^>]*>.*?</a>"
    
    if re.search(link_pattern, text, flags=re.IGNORECASE | re.DOTALL):
        lines = text.split('\n')
        return '\n'.join(lines[:-1]) if len(lines) > 1 else text
    else:
        return text


def preview(text: str, limit: int = 12000) -> str:
    """Get a preview of text with character limit."""
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."
