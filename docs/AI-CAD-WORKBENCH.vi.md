# FORGE AI CAD Workbench: tạo cấu trúc, sửa thiết kế, giữ bằng chứng

Mở `http://127.0.0.1:8767/feature-cad.html` sau khi chạy server. Workbench bổ sung một compiler feature graph tổng quát cho chi tiết gá cảm biến. Nó dựng BREP bằng build123d/Open Cascade, cho xem hình trung gian từng feature, kiểm giao diện lắp độc lập và xuất hồ sơ cùng revision. Không cần API key.

## Phép thử người dùng có thể thực hiện

1. Bấm **Mẫu kỹ sư**, **Kiểm và dựng CAD**, chờ worker hoàn thành. Mẫu có 16 feature, một solid, 90 × 70 × 16 mm; khối lượng khoảng 72,6 g theo mật độ giả định 2700 kg/m³. Bấm **Chọn làm baseline**.
2. Bấm **Thử dời −12 mm**, rồi **Thêm rãnh cáp**, dựng lại. Các lỗ cảm biến đi cùng vị trí mới; bốn lỗ của tấm nhận gá giữ nguyên. Cây tăng lên 19 feature với sketch, extrusion và boolean cut mới. Khối lượng khoảng 70,7 g; diff ghi tham số và node thêm/sửa/xóa. Bật **So baseline** để xem BREP trước dưới dạng wireframe.
3. Mở **Cây feature**, chọn sketch hoặc solid trung gian để hiểu cách hình được tạo. Bấm **Trục đo** để trở lại kết quả cuối.
4. Bấm **Thử lệch gá** và dựng. Một lỗ gá lệch 5 mm khiến phép kiểm BREP không đạt. Candidate vẫn lưu để xem, nhưng không được chọn làm baseline. Baseline trước được giữ và có thể trở về.
5. Mở bản vẽ A3, tải STEP hoặc ZIP. ZIP chứa part STEP, assembly STEP, STEP tham chiếu, bốn DXF, PDF/SVG, chương trình JSON, brief, kết quả kiểm, compiler và script tái dựng có manifest SHA-256.

Các nút mẫu là chương trình do kỹ sư viết. Chúng không gọi LLM và không chứng minh chất lượng của một model AI.

## Vòng làm việc với LLM bên ngoài

Nhập yêu cầu, bấm **Xuất context LLM**. JSON xuất gồm brief độc lập, catalog operation, chương trình đang sửa và feedback của candidate gần nhất nếu có: từng gate, metrics và chương trình đã kiểm. Đưa file này cho LLM đang dùng. Yêu cầu model trả riêng chương trình theo `forge-feature-design-v1`, sau đó nhập JSON vào Workbench, khai báo nguồn/model và dựng lại.

Nguồn `external_llm` là lời khai của người nhập, chưa có xác thực từ nhà cung cấp. Không có parser ý đồ tự động giả làm AI; không gửi dữ liệu ra dịch vụ ngoài. API LLM có thể tích hợp sau trên server mà giữ nguyên hợp đồng đề xuất–kiểm chứng–áp dụng.

Compiler nhận dữ liệu, không thực thi Python hoặc JavaScript từ model. Kết quả hình học và yêu cầu độc lập quyết định candidate có đủ điều kiện làm baseline; ghi chú của model không phải kết quả kiểm.

## Hợp đồng thiết kế

```json
{
  "format": "forge-feature-design-v1",
  "name": "Sensor bracket",
  "units": "mm",
  "brief_sha256": "USE_CURRENT_CONTEXT_BRIEF_SHA256",
  "parameters": { "width": 90, "thickness": 4 },
  "features": [
    { "id": "profile", "op": "sketch", "plane": "XY", "origin": [0, 0, 0],
      "profile": { "kind": "rectangle", "width": "width", "height": 70 } },
    { "id": "plate", "op": "extrude", "sketch": "profile", "amount": "thickness" }
  ],
  "result": "plate"
}
```

Ví dụ tối giản trên đúng schema nhưng chưa có lỗ lắp nên không qua brief gá cảm biến. Lấy `brief_sha256` hiện tại từ context. Bộ 20 chương trình tham khảo ở [feature-scenarios.json](examples/feature-scenarios.json) cũng cần thay hash placeholder này.

Catalog hiện có:

| Operation | Khả năng |
| --- | --- |
| `sketch` | Rectangle, circle, slot, polygon; mặt phẳng XY/XZ/YZ và gốc tọa độ khai báo |
| `extrude` | Tạo solid theo pháp tuyến sketch; hướng đùn không phụ thuộc chiều quấn polygon |
| `boolean` | Hợp, trừ, giao hai solid |
| `pattern` | Nhân bản và dịch theo danh sách tọa độ |
| `transform` | Dịch và xoay solid |
| `fillet`, `chamfer` | Chọn cạnh bằng loại đường, hướng và mặt tọa độ; thiếu cạnh thì báo lỗi |

Biểu thức nhận số, tên tham số, `+ - * /`, dấu âm/dương và ngoặc; không có lời gọi hàm, thuộc tính, indexing hay thực thi mã. Graph chỉ tham chiếu node trước; mọi node phải đóng góp vào result. Giới hạn 60 feature, 24 tham số và 16 instance/pattern. Độ phức tạp topology, dung lượng STEP và thời gian worker đều có giới hạn. Một worker CAD chạy tại một thời điểm, tối đa 90 giây; lịch sử lưu tối đa 100 job. Giao diện chỉ hiện 30 job gần nhất. Khi hết dung lượng cần lưu gói hồ sơ và quản lý thư mục job cục bộ; chưa có màn quản trị lưu trữ.

Các operation tạo hình không hard-code tên hoặc cấu trúc bracket. Brief hiện áp riêng cho giao diện gá cảm biến; đây là phạm vi kiểm chứng ban đầu, chưa là CAD đa ngành.

## Yêu cầu độc lập và kiểm chứng

Fixture ban đầu là sensor tổng hợp 50 × 30 × 22 mm với bốn lỗ xuyên Ø4,2; không phải linh kiện nhà cung cấp. Tấm nhận gá thử có bốn lỗ Ø5,2 tại tọa độ cố định. Chưa xác nhận gá này lắp lên nắp Q4.

Có thể import STEP Part 21 tối đa 2 MB, một solid. Người nhập khai báo lỗ xuyên và mặt lắp nằm ở Z=0. Worker đối chiếu vị trí lỗ với khoảng rỗng trong BREP, kiểm topology và kích thước, lưu SHA-256 của bytes gốc. Model không được sửa brief qua proposal. Hash brief gắn với reference và yêu cầu; đổi reference làm candidate cũ không đủ điều kiện áp dụng.

Đối với candidate, bộ kiểm đọc hình thực: solid hợp lệ và liên thông, envelope, mặt chuẩn, dịch cảm biến, khối lượng theo mật độ giả định, giao thể tích với sensor, lỗ đúng vị trí/đường kính, vành vật liệu 2 mm quanh lỗ, vùng tiếp cận vít gá và STEP đọc lại. Đường kính lỗ candidate lấy từ cạnh tròn BREP ở mặt trên kết hợp probe xuyên. Hình dùng để tessellation là bản sao để preview không thay đổi topology hoặc phép chọn cạnh của hình gốc.

Revision gắn với chương trình, brief, compiler/drawing source, version kernel và provenance. Manifest phát hiện file hồ sơ bị sửa. Khi source hoặc brief thay đổi, phải dựng lại trước khi chọn baseline. Baseline là trạng thái geometry đủ điều kiện trong phiên trình duyệt, không phải lệnh ghi vào spec Q4 hay cấp quyền sản xuất.

## Đầu ra và tái dựng

STEP giữ BREP, không mang feature history native của Fusion/Onshape. JSON và compiler giữ trình tự dựng. DXF gồm hình chiếu cạnh thực từ BREP; PDF/SVG có hình chiếu, mặt cắt hình học, kích thước bao, bảng lỗ, revision và ghi chú phạm vi. Assembly gồm bracket, sensor và tấm nhận thử, chưa có vít/washer/thread.

Giải nén gói, cài `build123d==0.13.0`, chạy `python reproduce.py`. Script kiểm hash brief và chương trình rồi xuất `reproduced.step`. Manifest chứa fingerprint source và hồ sơ. Muốn chỉnh sửa bằng code, sửa tham số/feature JSON rồi dùng compiler; bộ hồ sơ tái dựng không phải project native CAD.

## Bằng chứng hiện có và phần còn thiếu

`npm run test:features` đã kiểm 10 cấu trúc khác nhau và 10 lần sửa. Oracle số độc lập kiểm thể tích tấm/lỗ/fillet/chamfer, hệ tọa độ, và tính bất biến BREP khi preview. Bộ adversarial kiểm mã chèn, NaN, sai đơn vị, hash cũ, node không được dùng, selector rỗng và hình sai interface. Gói xuất được đọc lại, kiểm ZIP/hash, A3, DXF và script tái dựng độc lập.

`npm run test:feature-api` chạy HTTP và worker thật: proposal/import, tải gói, feedback context, gate adoption, candidate sai, manifest sửa, brief cũ, Origin/Host và giới hạn dữ liệu. Báo cáo số và trình duyệt ở `reports/robotics/feature-*`.

**20 trường hợp là bộ hồi quy do kỹ sư viết, không phải benchmark LLM.** Chưa đo tỷ lệ model tạo graph đúng lần đầu, số vòng sửa hay thời gian so với kỹ sư CAD. Chưa có thử nghiệm vật lý. Các gate hiện không chứng minh chịu tải, mỏi, va đập, dung sai lắp, bend radius dây, chống nước, quy trình gia công hoặc an toàn robot.

Mức thay CAD đã minh chứng: tự động dựng và sửa một lớp chi tiết có thể biểu diễn bằng catalog, giữ quan hệ tham số, kiểm giao diện và phát sinh hồ sơ. Chưa có sketch constraint solver tự do, loft/sweep, sheet-metal, CAM, FEA, GD&T, chỉnh sửa mặt tùy ý hoặc import feature history.

Bước tiếp theo để chứng minh AI là lấy STEP/datasheet sensor thật, giao bộ đề bài mới chưa có trong regression cho các model bên ngoài và một kỹ sư CAD đối chứng, chấm bằng cùng brief/gate độc lập, ghi số lượt sửa và thời gian. Sau đó gia công một bracket, đo kích thước và thử lắp/tải. Chỉ công bố tỷ lệ thay thế CAD theo công việc đã đo, không suy từ một hình render hay bộ test tự viết.
