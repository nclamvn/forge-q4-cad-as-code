# Khi bản thiết kế trở thành một chương trình

Đổi đường kính lỗ từ 10 lên 14 mm. Giảm độ dày tay chân robot từ 7 xuống 5 mm. Bấm dựng lại. Khối 3D đổi, khối lượng đổi rồi cả bộ bản vẽ và file STEP đổi theo. Với tôi, đây là đoạn đáng xem nhất trong demo FORGE Q4.

Tôi bắt đầu từ một bài đăng nói rằng mỗi linh kiện có thể là một chương trình Python. Muốn hiểu lời hứa đó đi tới đâu, tôi cùng AI dựng một PoC robot bốn chân và buộc nó phải xuất được dữ liệu CAD thật.

Cách làm khá dễ hình dung. Bản thiết kế trở thành một công thức. YAML giữ kích thước và các giả định. Python dùng build123d trên Open Cascade để dựng khối, khoét lỗ, tạo vỏ và đặt các chi tiết vào cụm lắp. Thay một nguyên liệu trong công thức, hệ thống tính lại những phần phụ thuộc. Khả năng xuất STEP và tạo hình chiếu từ khối CAD có sẵn trong [tài liệu build123d](https://build123d.readthedocs.io/en/latest/import_export.html).

Three.js đưa kết quả lên trình duyệt bằng WebGPU hoặc WebGL2. Phần hình ảnh giúp người xem xoay robot, tách cụm và xem từng cấu phần. Phần quyết định giá trị của cách làm nằm ở pipeline phía sau hình ảnh.

PoC có 12 loại chi tiết, 42 vị trí lắp ráp, 14 tờ A3 và 48 hình chiếu DXF. Các đầu ra gắn với revision. Trong phép thử vừa kể, một tay chân trên giảm từ 78,8 g xuống 54,2 g theo mật độ nhôm giả định. Những con số ấy được tính từ volume CAD.

Tôi cũng muốn biết khi nào chương trình nói sai. Vì vậy, chúng tôi đối chiếu thể tích với công thức giải tích, xuất STEP rồi đọc lại, kiểm số solid và thử cả đặc tả lỗi. Một phương án làm vành quanh lỗ quá mỏng phải bị chặn. Một phương án dùng thép có thể vượt ngân sách khối lượng. Màn demo phải hiện được những kết quả đó.

AI hỗ trợ viết mã trong quá trình xây dựng. Bản demo hiện tại chạy bằng kernel xác định và parser cục bộ, chưa có LLM nhận mọi yêu cầu thiết kế lúc chạy. Robot cũng chưa có dung sai lắp, tính bền hay kiểm chứng chế tạo.

Tôi thấy phương pháp này có chỗ đứng rõ ở các họ chi tiết có quy luật, cần nhiều biến thể và nhiều hồ sơ đi kèm. Người kỹ sư viết được quy luật thiết kế một lần rồi dùng lại. Để mở rộng, cần thêm interface linh kiện, phép kiểm và phản hồi từ chế tạo thực tế.

Câu hỏi tôi muốn tiếp tục thử là phần công việc nào có thể đóng gói thành chương trình để kỹ sư dành nhiều thời gian hơn cho những quyết định khó.

[Code, trailer và bộ CAD mẫu trên GitHub](https://github.com/nclamvn/forge-q4-cad-as-code).
