import os
from datetime import datetime
from typing import Optional

import google.generativeai as genai


def create_gemini_model() -> Optional[genai.GenerativeModel]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash-lite")


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
1	Phân tích Quân sự: Tập trung vào biến động lực lượng, khí tài, các điểm nóng xung đột và thay đổi học thuyết tác chiến.
2	Phân tích Chính trị: Tập trung vào các liên minh, biến động nội bộ cấp cao, các quyết sách lập pháp ảnh hưởng đến đại cục.
3	Phân tích Kinh tế: Tập trung vào dòng vốn, lạm phát, chuỗi cung ứng chiến lược và các lệnh trừng phạt/áp chế kinh tế.
4	Có thể bỏ qua những thông tin không liên quan đến 3 phần trên
5	Tuyệt đối không đưa ra lời khuyên đầu tư và nhận định, chỉ tóm tắt thông tin.
Tông giọng & Phong cách:
    •	Lạnh lùng, trung lập, sử dụng thuật ngữ chuyên môn (ví dụ: địa chính trị, lưỡng dụng, răn đe, phi đối xứng...).
    •	Định dạng phù hợp với Facebook: Sử dụng bullet points, tiêu đề viết hoa, phân tách rõ ràng để dễ đọc trên di động, không dùng ký tự đặc biệt, chỉ hỗ trợ dấu - để phân tách các dòng
    •	Nội dung trả lời chỉ bao gồm nội dung bài viết, không có câu hỏi nào thêm
Cấu trúc đầu ra (Output Format):
1	TIÊU ĐỀ BÁO CÁO - VIẾT HOA CÓ SỨC NẶNG

    ◦	⚔️ Quân sự: Các điểm nhấn quan trọng nhất
    ◦	🏛️ Chính trị: Các biến động và hệ quả dự kiến
    ◦	📊 Kinh tế: Các chỉ số và tác động chiến lược
    
4	ĐÁNH GIÁ RỦI RO: Dự báo ngắn về diễn biến tiếp theo.
Dữ liệu thô để xử lý:
{joined_messages}"""

    try:
        response = model.generate_content(prompt)
        text = (getattr(response, "text", "") or "").strip()
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
