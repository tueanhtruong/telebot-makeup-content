import os
from datetime import datetime
from typing import Any, Optional

import google.generativeai as genai


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


def create_gemini_model() -> Optional[genai.GenerativeModel]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-3-flash-preview")


def summarize_messages(
    model: Optional[genai.GenerativeModel],
    messages: list[str],
) -> str:
    if not messages:
        return "No new messages in this poll."

    if model is None:
        return "Gemini is disabled (missing GEMINI_API_KEY)."

    joined_messages = "\n".join(f"- {message}" for message in messages)
    prompt = f"""
BẠN LÀ MỘT SĨ QUAN PHÂN TÍCH TÌNH BÁO CHIẾN LƯỢC

NHIỆM VỤ CHÍNH:
Nhận dữ liệu thô không có cấu trúc, lọc bỏ thông tin vô nghĩa, và tự động nhóm lại thành các chủ đề quan trọng theo nội dung dữ liệu.

YÊU CẦU XỬ LÝ DỮ LIỆU:
- Lọc bỏ thông tin không liên quan, tin đồn, dữ liệu trùng lặp
- Tự động xác định những chủ đề chính có tác động đến địa chính trị, quân sự, chính trị hoặc kinh tế
- Giữ lại chỉ những thông tin có giá trị chiến lược
- Tóm tắt thành các câu ngắn, mạnh mẽ, dễ hành động

LĨNH VỰC PHÂN TÍCH (nếu dữ liệu chứa):
- Biến động quân lực, khí tài, học thuyết tác chiến
- Thay đổi liên minh, lãnh đạo, quyết sách ngoại giao
- Dòng vốn, lạm phát, chuỗi cung ứng, trừng phạt kinh tế
- Kiểm soát tài nguyên, địa bàn chiến lược
- Bất kỳ sự kiện nào có tác động đến cân bằng quyền lực

TÔN GIỌNG & PHONG CÁCH:
- Trung lập nhưng CÓ TÍNH SẮC SẢO, châm biếm tinh tế (cynical undertone)
- Sử dụng thuật ngữ chuyên môn: địa chính trị, lưỡng dụng, răn đe hạt nhân, phi đối xứng, quyền lực mềm, chiến tranh proxy, hiệp lực lệch cân
- Không đặt câu hỏi, chỉ trình bày tổng hợp
- Tránh từ ngữ mạnh/bạo lực thô: thay "chiến tranh" bằng "xung đột vũ trang", "tấn công" bằng "hoạt động quân sự"

ĐỊNH DẠNG CHO FACEBOOK (MOBILE-FIRST):
- Sử dụng dấu gạch ngang (-) để phân tách các dòng thông tin
- Tiêu đề VIẾT HOA, có sức nặng
- Emoji được dùng: ⚔️ 🏛️ 📊 📌 (tránh các emoji có thể bị gắn cờ)
- Bullet points ngắn, mỗi dòng 1-2 ý chính
- Không dùng ký tự đặc biệt phức tạp, không dùng bảng biểu
- Khoảng cách rõ ràng giữa các phần để dễ đọc trên di động

CẤU TRÚC ĐẦU RA:

[1] TIÊU ĐỀ BÁO CÁO - VIẾT HOA, GỢI HỨNG THÚ

[2] CÁC CHỦ ĐỀ CHÍNH (tự động nhóm dựa trên dữ liệu):
Với mỗi chủ đề:
- Sử dụng emoji thích hợp (⚔️ cho quân sự, 🏛️ cho chính trị, 📊 cho kinh tế, 📌 cho sự kiện khác)
- Tiêu đề chủ đề VIẾT HOA
- 2-4 dòng thông tin chi tiết

[3] HASHTAG (chỉ sử dụng hashtag an toàn, phổ biến, không bị gắn cờ)

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

    try:
        print("\n" + "="*72)
        print("AI MODEL PROMPT:")
        print("="*72)
        print(prompt)
        print("="*72 + "\n")
        
        response = model.generate_content(prompt)
        text = (getattr(response, "text", "") or "").strip()
        print_gemini_token_usage(model, prompt, response, "SUMMARY")
        
        print("\n" + "="*72)
        print("AI MODEL RAW RESPONSE:")
        print("="*72)
        print(text)
        print("="*72 + "\n")
        
        if text:
            return text
        return "Gemini returned an empty summary."
    except Exception as error:
        return f"Gemini summary error: {error}"


def format_summary_log(summary: str, total_messages: int) -> str:
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    border = "=" * 72
    return (
        f"\n{border}\n"
        f"{timestamp} POLL SUMMARY\n"
        f"Messages processed: {total_messages}\n"
        f"{border}\n"
        f"{summary}\n"
        f"{border}\n"
    )
