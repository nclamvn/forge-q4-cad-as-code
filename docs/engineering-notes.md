# FORGE Q4 — từ đặc tả đến CAD có bằng chứng

Phiên bản monochrome: thân vát bo góc thấp, mặt cảm biến đặt âm, khớp graphite gọn, vỏ chân ba chiều và bề mặt graphite. Vỏ vai/vỏ chân là CAD thật, nằm trong 42 chi tiết STEP; hiệu ứng bề mặt graphite là finish hiển thị, không khẳng định vật liệu carbon composite.

PoC robot bốn chân: đặc tả tham số → Python/build123d → BREP Open Cascade → STEP → đọc lại STEP → mesh Three.js. Dựng khối CAD thật bằng Python; trình duyệt hiển thị chính mesh tessellate từ các khối ấy.

## Mở ngay

- **`FORGE-Q4.html`**: một file duy nhất, không CDN, không cần mạng. Xoay, tách cụm, mặt cắt, chuyển động minh họa, kích thước, xem mã/BOM/bằng chứng và tải STEP của snapshot đã kiểm chứng. Đổi tham số cần kernel chạy, vì vậy điều khiển dựng lại bị vô hiệu hóa ở bản này.
- **`Start.command`**: nhấp đúp trên macOS để mở bản tương tác đầy đủ ở **http://127.0.0.1:8767**. Lần đầu trên máy khác cần Python 3.11–3.14 và mạng để cài thư viện từ PyPI. Nếu macOS mở file như văn bản, chạy `zsh Start.command` trong Terminal.
- **Trình diễn**: nút trên thanh đầu, 5 cảnh gồm Studio → tách cụm → mặt cắt → chuyển động → kiểm chứng. ESC dừng. Kéo để xoay, cuộn để thu phóng; D = kích thước, X = xuyên thấu, S = mặt cắt, E = tách cụm, Space = chuyển động.

Chạy thủ công:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

WebGPURenderer dùng WebGPU khi khả dụng và dự phòng WebGL2. Có thể ép WebGL2 bằng `http://127.0.0.1:8767/?backend=webgl`; với HTML dùng `FORGE-Q4.html?backend=webgl`.

## Bàn CAD: hồ sơ 12 cấu phần và 42 vị trí

Mở `http://127.0.0.1:8767/?workspace=cad` hoặc bấm **Thử thiết kế CAD**. Bản vẽ A3 là màn chính của bàn thiết kế, liên kết với cùng khối, tham số và revision.

- **12 cấu phần**: khung, nắp, tay trên/dưới, hai vỏ chân, vỏ vai, actuator, đệm chân, giá cảm biến, ống kính và pin. Chọn một cấu phần để xem bản vẽ, khối 3D, đặc tính BREP và vị trí trong robot.
- **14 tờ A3**: 12 tờ chi tiết, một tờ tổng thể và một tờ phân rã. Tờ chi tiết có ba hình chiếu vuông góc cùng tỷ lệ, trục đo minh họa, nét khuất, mặt cắt A–A gạch vật liệu và đường xác định mặt phẳng cắt trên hình chiếu XY. Bố trí hình chiếu góc thứ ba; tỷ lệ áp dụng khi in đúng khổ A3.
- **Dữ liệu thực**: hộp bao XYZ, diện tích bề mặt, thể tích, khối lượng/cơ sở tính, số mặt/cạnh/đỉnh, diện tích mặt cắt; thông số và các bước dựng bằng Python. Kích thước tổng thể đo từ CAD được phân biệt với thông số chương trình, ví dụ tay trên tâm–tâm 110 mm nhưng dài tổng 142 mm.
- **BOM 42 vị trí**: định danh riêng trong STEP, mã chi tiết, XYZ, góc lắp và cơ sở khối lượng. Chọn một dòng BOM để mở bản vẽ tương ứng.
- **Xuất thật**: 12 STEP riêng, STEP lắp ráp 42 solid, 48 DXF (4 hình chiếu/chi tiết), 14 SVG, PDF 14 trang A3 và ZIP hồ sơ. Nút DXF tải hình chiếu chính diện; cả bốn hình chiếu nằm trong ZIP. DXF giữ cạnh CAD theo đơn vị mm với lớp VISIBLE/HIDDEN; kích thước và ghi chú nằm trên SVG/PDF.
- **Phóng to**: 75–250%; bảng và bản vẽ cuộn ngang trên màn nhỏ. Khối 3D sử dụng mesh tessellate từ đúng BREP, có thể xoay/thu phóng riêng từng cấu phần.

Thử thay đổi có thể kiểm chứng:

1. Chọn **Q4-201 Tay chân trên**: tâm–tâm 110 mm, rộng 32 mm, dày 7 mm, hai lỗ Ø10 mm.
2. Bấm **Thử lỗ Ø14 / dày 5**, rồi **Dựng lại CAD và bản vẽ**. Kernel dựng lại khối, hình chiếu, mặt cắt và toàn bộ hồ sơ. Lần đầu có thể mất khoảng 40–90 giây trên máy hiện tại; kết quả lặp lại dùng cache.
3. Khối lượng tay trên từ 78,8 g xuống 54,2 g theo mật độ nhôm giả định; thể tích giảm 31,2%. Bảng trước/sau đọc dữ liệu CAD. PDF, STEP và DXF tải đúng kết quả mới.
4. Bấm **Thử vành quá mỏng** rồi dựng lại. Python chặn spec không giữ vành tối thiểu 6 mm. Khối và bản vẽ hợp lệ cũ được giữ; xuất bị khóa khi tham số chưa đồng bộ.
5. Chọn khung/nắp/vỏ chân/giá cảm biến để sửa các tham số được liệt kê. Cấu phần cố định vẫn có đủ bản vẽ và STEP nhưng không có tham số sửa trong UI.

Ở HTML snapshot, toàn bộ bản vẽ/BOM và các tệp tải được nhúng sẵn, không cần mạng. Sửa/dựng cần `Start.command`. Quy trình dựng hiển thị là diễn giải chương trình, chưa phải feature tree có thể sắp xếp bằng chuột.

| Công việc | Phạm vi PoC hiện tại |
| --- | --- |
| Sketch theo tham số, boolean, extrude, loft | Compiler thực hiện thật với build123d/OCCT |
| Sửa kích thước, cập nhật các cấu phần phụ thuộc và lắp ráp | Có, trong họ robot Q4 đã lập trình |
| Hình chiếu có nét khuất và mặt cắt vật liệu | Có, lấy từ BREP qua OCCT HLR và phép section |
| Hồ sơ A3, DXF, STEP riêng/lắp ráp, BOM định danh | Có, cùng revision CAD và kiểm đọc lại |
| Sketch tự do, constraint solver tương tác, chọn/sửa mặt | Chưa có |
| History native của Fusion/Onshape khi import STEP | Không xuất; nguồn tham số là YAML và Python |
| GD&T, dung sai/độ nhám, CAM, FEA hoặc chứng nhận chế tạo | Chưa có |
| Đặt ý đồ bất kỳ bằng LLM trong lúc chạy | Chưa có; parser intent chỉ dùng whitelist cục bộ |

Đây là hồ sơ kỹ thuật concept, **chưa phát hành để chế tạo**. Actuator, pin và ống kính là hình học đại diện: không tự nhận đã thiết kế rotor/stator, gearbox, cell/BMS hay quang học. Chưa có bearing, vít giữ, dây hoặc PCB. Cách này thay được một phần công việc dựng biến thể và phát sinh tài liệu cho họ chi tiết có quy luật; không có cơ sở gán phần trăm thay thế toàn bộ CAD.

`technical.py` dùng phép chiếu BREP của build123d để loại nét khuất, rồi xuất cạnh CAD ra DXF. SVG/PDF lấy mẫu đường cong để hiển thị (bước theo chiều dài mục tiêu 0,6 mm, giới hạn 320 đoạn/cạnh; đường cắt mục tiêu 0,4 mm, giới hạn 1200 đoạn/wire). Bản vẽ hiển thị không phải nguồn hình học gia công; STEP giữ BREP gốc. Font Arial trên macOS hoặc DejaVu Sans trên Linux được nhúng vào PDF tiếng Việt. Fingerprint riêng của trình sinh bản vẽ được lưu trong documentation bên cạnh revision hình học.

## Kiểm chứng nhiều phương pháp

1. **Hợp lệ BREP:** 12 hình học khác nhau, mỗi hình là một solid hợp lệ; assembly có 42 chi tiết.
2. **Công thức riêng:** thể tích tay chân dạng capsule với hai lỗ xuyên được tính giải tích và đối chiếu với volume CAD; không sử dụng thể tích CAD làm đầu vào công thức.
3. **STEP round-trip:** xuất assembly rồi import bằng kernel, đếm solid và so tổng thể tích. Đây là kiểm trao đổi STEP trong Open Cascade, chưa phải kiểm import vào Fusion hay Onshape.
4. **Vành vật liệu:** đặc tả phải giữ ít nhất 6 mm quanh lỗ theo quy tắc PoC; đây không phải kết luận chịu lực.
5. **Khe hở BREP:** đo khoảng cách hai tay chân ở 5 góc, với khoảng cách tách mặt 3 mm. Chưa bao quát va chạm của các vỏ bọc hoặc cả robot hoặc mọi góc liên tục.
6. **Khối lượng:** volume × mật độ giả định với kết cấu; actuator, pin, điện tử và một số thiết bị dùng khối lượng gán. Kiểm cả tải bổ sung so với mục tiêu 7 kg.

Các gate hiện kết quả thật. Chọn thép có thể làm ngân sách khối lượng không đạt; không tô xanh mọi phương án. Nút **Thử đặc tả lỗi** gửi thông số vi phạm tới Python và nhận HTTP 422; thiết kế hợp lệ đang xem được giữ lại.

Revision là hash của đặc tả và fingerprint mã compiler. STEP, model, spec và proof được lưu cùng revision trong `artifacts/`. JSON báo cáo chứa phương pháp, số đo, sai lệch và giả định. Điểm trọng tâm hiển thị dùng CoM từng khối và vị trí/khối lượng bổ sung giả định; đa giác đỡ là minh họa tĩnh, chưa đánh giá ổn định khi bước.

## AI nằm ở đâu?

Agent AI đã viết mã PoC này. **Không có lời gọi LLM lúc chạy**, không có API key và không gửi đặc tả ra ngoài. Ô “Nhập ý đồ thiết kế” dùng parser cục bộ với từ khóa và khoảng giá trị, ví dụ `thân 360 mm, chân dưới 180 mm, vật liệu PA12`. Parser chỉ cập nhật spec, sau đó người dùng bấm dựng CAD. Muốn nối LLM về sau: cho model trả JSON theo schema, kiểm whitelist/range và các gate rồi mới dựng; không chạy Python tùy ý do model trả về.

## Phạm vi

Robot này là thiết kế PoC độc lập, không tái tạo hoặc chứng nhận robot trong bài đăng. Actuator và sensor là hình học đại diện. Các vân, nẹp, decal và đèn là trang trí render, không tính vào STEP/BOM CAD. Mặt cắt trong chế độ robot 3D là clipping hiển thị; mặt cắt trên tờ A3 lấy từ phép cắt BREP thật. Chuyển động là quỹ đạo minh họa, chưa có mô phỏng tiếp xúc, điều khiển, FEA, dung sai lắp ghép, fatigue, torque actuator hay thử robot thật. Các con số mật độ/khối lượng đều được ghi rõ cơ sở trong BOM.

## Tái lập

```sh
.venv/bin/python tests/kernel_test.py
.venv/bin/python tests/dossier_test.py
# Khi server đang chạy:
.venv/bin/python tests/api_test.py
```

Kiểm nhiều kích thước capsule, 7 loại spec sai và 4 thiết kế (mặc định, PA12 nhẹ, chân dài, thép). Kết quả trong `reports/kernel-tests.json`. Bộ kiểm hồ sơ đọc lại 12 STEP riêng, kiểm 42 nhãn lắp, DXF/mm, mặt cắt giải tích của hai tay chân, số trang/khổ A3 và nội dung ZIP. Sai lệch thể tích STEP riêng cho phép dưới 0,0002%, bao gồm sai số tích phân bề mặt NURBS. Các ảnh WebGPU/WebGL2 và kiểm chức năng trình duyệt lưu tại `reports/`.

Đóng gói lại HTML sau khi sửa frontend:

```sh
npm install
npm run package
```

`kernel.py` là compiler; `spec.yaml` là spec mặc định; `server.py` là API cục bộ; `web/app.js` là renderer/interaction. Three.js 0.186.1 được vendor sẵn với MIT license; build123d 0.13.0, PyYAML 6.0.3 và ReportLab 4.4.9 được pin trong requirements. API chỉ nghe trên 127.0.0.1.

Tài liệu nền: [build123d](https://build123d.readthedocs.io/en/latest/), [STEP import/export](https://build123d.readthedocs.io/en/latest/import_export.html), [Three.js WebGPURenderer](https://threejs.org/docs/pages/WebGPURenderer.html).
