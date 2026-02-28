# this file aim to test the facebook post function
import os
from dotenv import load_dotenv
from facebook_service import post_to_facebook   

load_dotenv()

content = f"""

---

### **BÁO CÁO TÌNH HÌNH CHIẾN LƯỢC - KHU VỰC TRUNG ĐÔNG & CÁC TÁC ĐỘNG LAN TỎA**

**BLUF:** Căng thẳng leo thang tại Trung Đông đang gây ra những gián đoạn đáng kể về hậu cần và thương mại, cùng với những động thái ngoại giao gia tăng. Các lực lượng đối đầu có khả năng duy trì áp lực, trong khi các cường quốc khác tìm cách ổn định tình hình.

---

### **CHI TIẾT PHÂN TÍCH:**

⚔️ **QUÂN SỰ:**

*   **Tăng cường hành động quân sự:** Iran tuyên bố sẽ tăng cường độ hành động và coi các căn cứ, cơ sở của Mỹ và Israel là mục tiêu quân sự hợp pháp. Điều này cho thấy sự quyết tâm duy trì áp lực và có thể là mở rộng phạm vi tấn công.
*   **Tấn công phi đối xứng và phòng thủ:** Iran cáo buộc Mỹ và Israel tấn công trường tiểu học, gây thương vong. Israel báo cáo hứng chịu mảnh vỡ tên lửa của Iran. Các vụ nổ được báo cáo tại nhiều địa điểm ở Iran, cho thấy hoạt động phòng không hoặc các cuộc tấn công trả đũa.
*   **Cảnh báo đóng cửa eo biển:** Thông báo về việc đóng cửa Eo biển Hormuz, dù có thể không có giá trị pháp lý quốc tế nếu không được thực thi hợp pháp, cho thấy nỗ lực kiểm soát các tuyến đường thương mại chiến lược và tạo đòn bẩy địa chính trị.
*   **Gián đoạn hàng không:** Nhiều hãng hàng không đã tạm dừng hoặc hủy bỏ đáng kể các chuyến bay đến và đi từ các quốc gia Trung Đông, cho thấy sự đánh giá rủi ro cao đối với các tuyến đường hàng không trong khu vực.

🏛️ **CHÍNH TRỊ:**

*   **Ngoại giao gia tăng:** Ngoại trưởng Nga Lavrov đã điện đàm với người đồng cấp Qatar, cả hai kêu gọi Mỹ, Israel và Iran quay lại các biện pháp chính trị và ngoại giao. Ấn Độ cũng liên lạc với Israel, nhắc lại lời kêu gọi xoa dịu căng thẳng thông qua đối thoại.
*   **Lập trường quốc tế:** Đức khẳng định không tham gia vào các cuộc tấn công vào Iran, đồng thời cam kết hòa bình và an ninh khu vực, cũng như an ninh của Israel.
*   **Quan ngại về chương trình hạt nhân:** Thủ tướng Đức Merz chỉ ra rằng Iran chưa đạt được một thỏa thuận hạt nhân toàn diện, đáng tin cậy và có thể kiểm chứng với Mỹ.
*   **Nội bộ Mỹ:** Hạ viện Hoa Kỳ có thể tiếp tục họp để giải quyết các vấn đề về quyền lực chiến tranh và nghe báo cáo về Iran, cho thấy sự quan tâm và áp lực chính trị nội bộ đối với chính sách Trung Đông.

📊 **KINH TẾ:**

*   **Gián đoạn chuỗi cung ứng chiến lược:** Việc tạm dừng và hủy bỏ các chuyến bay đến các điểm nóng kinh tế và trung tâm trung chuyển ở Trung Đông cho thấy sự ảnh hưởng trực tiếp đến logistic và thương mại, có khả năng tác động đến giá cả hàng hóa và thời gian vận chuyển toàn cầu.
*   **Cơ chế ứng phó khẩn cấp:** Các nền tảng du lịch khởi động cơ chế bảo đảm ứng phó khẩn cấp, cho phép hủy miễn phí các đặt phòng khách sạn và hỗ trợ thủ tục hoàn vé/đổi vé cho các chuyến bay bị ảnh hưởng. Điều này phản ánh rủi ro kinh doanh gia tăng và sự chủ động giảm thiểu thiệt hại.
*   **Không có thông tin trực tiếp về dòng vốn, lạm phát hoặc lệnh trừng phạt:** Dữ liệu thô tập trung vào tác động tức thời của xung đột lên hoạt động kinh tế và thương mại, chứ không đi sâu vào các chỉ số kinh tế vĩ mô phức tạp.

---

### **ĐÁNH GIÁ RỦI RO (Risk Assessment):**

*   **Leo thang quân sự trực tiếp giữa Iran và Mỹ/Israel:** **Xác suất Cao, Tác động Rất Cao.** Các tuyên bố và hành động trả đũa lẫn nhau cho thấy khả năng đối đầu trực tiếp vẫn còn hiện hữu.
*   **Gián đoạn thương mại kéo dài ở Eo biển Hormuz và các tuyến đường biển khác:** **Xác suất Trung bình, Tác động Cao.** Các nỗ lực kiểm soát hoặc phong tỏa các tuyến đường biển chiến lược có thể gây ra những biến động giá năng lượng và hàng hóa.
*   **Tăng cường các nỗ lực ngoại giao và đàm phán:** **Xác suất Cao, Tác động Trung bình.** Các cường quốc khu vực và quốc tế đang nỗ lực tìm kiếm giải pháp hòa bình, có thể dẫn đến các cuộc đàm phán hoặc giảm nhiệt độ căng thẳng tạm thời.

---

### **KẾT LUẬN:**

Cục diện Trung Đông đang chứng kiến sự gia tăng bất ổn, với các động thái quân sự và phản ứng ngoại giao song hành, tiềm ẩn nguy cơ lan tỏa tác động lên các lĩnh vực kinh tế và chiến lược toàn cầu.
========================================================================"""

post_to_facebook(content)