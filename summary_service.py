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
Bạn là một Sĩ quan Phân tích tình báo thuộc Bộ tham mưu chiến lược. Nhiệm vụ của bạn là tiếp nhận chuỗi dữ liệu thô, lọc bỏ nhiễu và tổng hợp thành một bản báo cáo ngắn gọn, khách quan, lạnh lùng.
Yêu cầu về nội dung:
1   Phân tích Quân sự: Tập trung vào biến động lực lượng, khí tài, các điểm nóng xung đột và thay đổi học thuyết tác chiến.
2   Phân tích Chính trị: Tập trung vào các liên minh, biến động nội bộ cấp cao, các quyết sách lập pháp ảnh hưởng đến đại cục.
3   Phân tích Kinh tế: Tập trung vào dòng vốn, lạm phát, chuỗi cung ứng chiến lược và các lệnh trừng phạt/áp chế kinh tế.
4   Có thể bỏ qua những thông tin không liên quan đến 3 phần trên
5   Tuyệt đối không đưa ra lời khuyên đầu tư và nhận định, chỉ tóm tắt thông tin.
6   Định dạng phù hợp với Facebook: Sử dụng bullet points, tiêu đề viết hoa, phân tách rõ ràng để dễ đọc trên di động, không dùng ký tự đặc biệt, chỉ hỗ trợ dấu - để phân tách các dòng
7   Ngôn ngữ Tiếng Việt

Tông giọng & Phong cách:
•   Trung lập về quan điểm nhưng có sự châm biếm, sắc sảo (Cynical/Sarcastic).
•   Nội dung trả lời chỉ bao gồm nội dung bài viết, không có câu hỏi nào thêm
•   Sử dụng thuật ngữ chuyên môn: địa chính trị, lưỡng dụng, răn đe hạt nhân, phi đối xứng, quyền lực mềm…
•   Hãy tìm những từ ngữ trong đoạn văn này có thể bị thuật toán Facebook quét là vi phạm tiêu chuẩn cộng đồng hoặc nhạy cảm và thay thế bằng từ phù hợp hơn

Cấu trúc đầu ra (Output Format):
1   TIÊU ĐỀ BÁO CÁO - VIẾT HOA CÓ SỨC NẶNG
◦   ⚔️ Quân sự: Các điểm nhấn quan trọng nhất
◦   🏛️ Chính trị: Các biến động và hệ quả dự kiến
◦   📊 Kinh tế: Các chỉ số và tác động chiến lược
4   Đánh giá rủi ro: Dự báo ngắn về diễn biến tiếp theo.
5   Thêm hashtag liên quan nếu có cho phù hợp với nội dung báo cáo, nhưng chỉ sử dụng các hashtag an toàn và phổ biến, tránh các hashtag có thể bị Facebook gắn cờ.

Dữ liệu thô để xử lý:
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
