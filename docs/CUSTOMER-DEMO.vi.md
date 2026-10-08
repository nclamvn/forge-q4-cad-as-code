# FORGE — bản kiểm chứng kỹ thuật cho khách hàng

Mở `http://127.0.0.1:8767/customer.html`. Trang này đi qua CAD robot, chi tiết do LLM đề xuất, bài đánh giá, tích hợp và vật lý, sau đó đến kế hoạch pilot.

## Mẫu LLM thật trong bản này

Trial `1015243d1fe54232890fc3d92283ba95` là đề xuất do LLM trong phiên Codex viết, không gọi hàm sinh fixture. JSON nằm ở `docs/examples/llm-lightweight-proposal.json`. LLM đọc context, catalog, schema và quy tắc công khai; trong quá trình xem mã cũng thấy helper fixture. Đây là lượt có hỗ trợ và tiếp cận mã nguồn, không phải đánh giá mù. Không có biên nhận API từ nhà cung cấp, model ID xác thực, số token hoặc chi phí. Không gán kết quả cho một phiên bản model chưa được ghi nhận.

Đề bài yêu cầu tạo chi tiết mới: tám lỗ gá, vùng đỡ hai bên, cửa sổ Ø20 và khối lượng ≤70 g. LLM viết tấm 88 ×68 ×4 mm, hai rail 3 ×24 ×12 mm, 17 node. Đạt ngay lượt đầu: 64,3839 g theo mật độ nhôm giả định, 24 kiểm geometry và 4 kiểm công việc. Thời gian phiên bao gồm đọc nguồn, viết JSON, chờ worker và review; không dùng nó như thời gian lao động chuẩn hoặc tỷ lệ tăng năng suất.

Lượt kỹ sư `30cd3cb38db541c1b82355e305809990` có cùng task hash và đồng hồ chưa chạy. Kỹ sư chọn bắt đầu, thiết kế riêng, gửi JSON, đọc kết quả, sửa nếu cần, rồi chốt. Không sao chép mẫu LLM nếu muốn so sánh khả năng thiết kế độc lập. Chỉ sau khi cả hai lượt hoàn tất mới có đối chứng. Chưa có tỷ lệ thay thế CAD, số đo năng suất hoặc kết luận AI tốt hơn con người.

## Chi tiết thực sự đi vào robot

Cấu hình `88b2de0745b9`: gá AI, sensor tham chiếu, adapter 120 ×90 ×8 mm, bốn spacer Ø10/Ø5.2 cao 6 mm. Khoan nắp Q4 thực trong BREP tại X20/90, Y±25, Ø5.2. Kiểm vòng đỡ 2 mm, xuyên lỗ, giao thoa thể tích ở home pose và STEP đọc lại 49 solid. Sensor vẫn là hình học tổng hợp, không phải một SKU đã xác nhận.

Compiler robot dùng đúng STEP mới để tích phân trọng tâm/quán tính, gắn bảy instance bổ sung vào base_link, xuất mesh SI, URDF và MJCF. Hai lượt stand/trot 3 giây dùng MuJoCo thật. Báo cáo ghi rõ phản ứng và ngã nếu xuất hiện; chạy ngắn không chứng minh độ bền vận hành.

Ngân sách tải tổng giữ nguyên 7 kg. Khối lượng thêm không được ẩn: cấu hình vượt ngân sách và tính tải mang còn lại từ ngân sách. Giá trị này chưa phải tải cho phép theo độ bền. Không tự giảm payload 1 kg hoặc nới target để biến kết quả thành đạt.

Bản vẽ Q4 14 trang tiếp tục mô tả robot gốc. Gá có PDF/DXF riêng; thay đổi lắp có STEP và báo cáo tích hợp riêng. Không relabel bản vẽ cũ thành bản vẽ đã kiểm cho robot mới. Còn cần bản vẽ cụm lắp đầy đủ, dung sai, vít/đai ốc, FEM, cable/FOV và thử lắp để phát hành chế tạo.

## Tái lập bản phát hành

`tools/customer_release.py` chỉ đóng khi các kiểm số và browser review mới khớp source. Báo cáo browser cũ được giữ làm lịch sử, không thay hash để giả thành kiểm mới. ZIP chọn đúng hai trial trên, sensor reference gốc, CAD candidate, cấu hình robot và mô hình SI; không gom toàn bộ lịch sử cục bộ.

Giải nén vào thư mục mới. Dùng Python 3.12, tạo venv và cài `requirements-lock.txt` (bản khóa đã thử trên Python 3.12 / macOS arm64). Chạy `python server.py --port 8768`, mở `/customer.html`. Gói chứa STEP/PDF/DXF và vendor Three.js nên xem đồ họa không cần CDN. MuJoCo cần thư viện đã cài. Có thể chạy `python tests/integration_test.py ea345ca303a25fdc` và giải nén gói bằng chứng LLM, chạy `python verify.py`.

Chép ZIP gốc vừa tải vào thư mục `customer-release/FORGE-Q4-Customer.zip` bên trong bản giải nén để nút tải lại source vẫn phục vụ chính gói đó. ZIP không thể chứa bản thân nó; các gói CAD/bằng chứng nhỏ hơn đã nằm sẵn bên trong. Nếu cổng 8768 đã dùng, chọn cổng khác. Kiểm cài sạch của bản này dùng cổng riêng 18767 và một venv mới, không dùng server ở 8767.

Manifest SHA-256 kiểm tính toàn vẹn, không phải chữ ký xác nhận nguồn con người/AI. Dữ liệu kiểm cài sạch được ghi trong báo cáo release riêng sau khi gói đã đóng; source snapshot trong ZIP giữ trạng thái ở thời điểm đóng.

## Phạm vi dùng với khách hàng

Phù hợp buổi đánh giá kỹ thuật có kịch bản, kiểm file và thử tham số. Chưa đủ điều kiện sản xuất robot, kiểm chứng phần cứng hoặc tuyên bố thay thế CAD tổng quát. Chưa thực thi ROS 2 launch/RViz, chưa có hardware driver, điều khiển cân bằng hoàn chỉnh, xác thực nhiều người dùng hoặc tích hợp API LLM.
