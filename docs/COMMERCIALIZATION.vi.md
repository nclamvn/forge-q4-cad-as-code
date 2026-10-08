# FORGE Q4 — từ nền kỹ thuật đến giải pháp kiểm tra nhà xưởng

Cập nhật: 08/10/2026. Đây là phương án triển khai và đặc tả pilot, chưa phải hồ sơ nghiệm thu robot. Các mốc và ngưỡng dưới đây là mục tiêu đề xuất cần chốt với khách hàng. Q4 chưa được chế tạo, chưa có dữ liệu đo phần cứng và chưa chạy ROS 2 trên máy phát triển hiện tại.

## 1. Sản phẩm khách hàng mua

Sản phẩm đầu tiên nên là **dịch vụ thu thập dữ liệu kiểm tra tài sản theo tuyến, có người giám sát**: đến đúng điểm, chụp đúng đối tượng, lưu đúng ngữ cảnh, đưa bất thường cho kỹ thuật viên xác nhận và xuất hồ sơ ca kiểm tra. Giá trị thương mại đến từ dữ liệu đủ tin cậy và quy trình sử dụng dữ liệu đó.

Phạm vi đề xuất: một khu vực nhà xưởng trong nhà, tuyến được khảo sát và phê duyệt, RGB và ảnh nhiệt bên ngoài thiết bị, làm việc cùng đội bảo trì. Bắt đầu với tuyến nhỏ gồm motor, bơm, ổ đỡ, hộp giảm tốc và mặt ngoài tủ điện. Người vận hành quyết định khi nào khởi chạy, dừng, xác nhận bất thường và tạo yêu cầu bảo trì.

Chưa đưa vào pilot đầu tiên: mở tủ điện, thao tác van, vận hành ở khu vực có yêu cầu chống cháy nổ, đi vào vùng xe nâng hỗn hợp chưa đánh giá, tự động xử lý sự cố hay chạy không giám sát. Mở rộng nhiệm vụ phải có đánh giá và phép thử riêng.

Khách hàng mục tiêu là trưởng bảo trì và quản lý nhà máy có tuyến kiểm tra lặp lại, hồ sơ chưa đồng nhất, cần so sánh nhiều ca. Người dùng trực tiếp là kỹ thuật viên bảo trì và người vận hành robot. Trước đầu tư phần cứng, cần một chủ nhà máy cung cấp tuyến, tài sản, dữ liệu hiện trạng và người cùng nghiệm thu.

## 2. Chọn đường thương mại hóa và đường nghiên cứu

Tách hai nhánh có đầu ra cụ thể:

| Nhánh | Đầu ra | Điều kiện lựa chọn |
|---|---|---|
| Giải pháp triển khai | Nền di chuyển có hỗ trợ nhà cung cấp + payload đo + quy trình dữ liệu + dịch vụ pilot | Khách hàng cần kết quả kiểm tra sớm; yêu cầu độ tin cậy vượt mức Q4 hiện tại |
| Q4 tự phát triển | Nền robot riêng, CAD tự động, điều khiển và bộ đo hiệu chuẩn | Có ngân sách R&D, đội cơ điện/điều khiển, bàn thử và lý do cần sở hữu nền di chuyển |

Khuyến nghị hiện tại: xây sản phẩm kiểm tra dùng được trên nền robot mua/thuê/đối tác, đồng thời phát triển Q4 qua từng phép thử cơ điện. Chưa chọn mua nền nào. SDK, tải trọng, nguồn cho payload, hỗ trợ tại Việt Nam, điều kiện bảo hành và sử dụng công nghiệp phải xác nhận theo **đúng SKU và hợp đồng**.

Nếu tuyến bằng phẳng và không cần vượt bậc/cầu thang, phải so sánh nền bánh xe, thiết bị đo cố định và quy trình thủ công. Chân robot chỉ đáng trả chi phí khi đặc điểm tuyến thực sự cần khả năng đó. Đây là quyết định thiết kế dựa trên khảo sát, không phải kết luận rằng một kiểu nền luôn tốt hơn.

## 3. Đối chiếu thị trường có nguồn

| Giải pháp | Tín hiệu đã kiểm từ nhà cung cấp | Hàm ý cho FORGE |
|---|---|---|
| Boston Dynamics Spot / giải pháp inspection | Có các nhóm đo nhiệt, visual/PTZ, acoustic; phần mềm quản lý và hỗ trợ triển khai | Cần cạnh tranh bằng quy trình thu thập–xác nhận–bảo trì, kèm đào tạo và dịch vụ, không chỉ khả năng đi |
| ANYbotics ANYmal | Nhà cung cấp công bố nền inspection công nghiệp, tích hợp cảm biến và IP67 | Độ kín, độ bền, hiệu chuẩn, vận hành dài và tích hợp là khoảng cách phải đo; Q4 chưa có bằng chứng tương đương |
| Unitree Go2 | Có nhiều phiên bản; khả năng payload và cảm biến khác nhau | Không lấy giá khởi điểm của bản tiêu dùng làm giá robot công nghiệp hoặc hệ inspection hoàn chỉnh |
| Kiểm tra thủ công / nền bánh xe / cảm biến cố định | Phương án đối chiếu tại chính nhà máy; chưa thu thập báo giá và thời gian thực tế | Cần baseline về giờ công, chất lượng ảnh, độ phủ tuyến, công việc phát sinh và tổng chi phí |

Nguồn chính thức: [Boston Dynamics inspection](https://bostondynamics.com/solutions/inspection/), [ANYmal](https://www.anybotics.com/robotics/anymal/), [Unitree Go2](https://www.unitree.com/go2/). Các thông tin công bố là nguồn nhà cung cấp; chưa phải phép thử độc lập hoặc chứng minh ROI cho khách hàng của FORGE. Chưa có báo giá hệ tích hợp nên chưa xếp hạng theo giá thành.

Cơ hội đề xuất: quy trình inspection tiếng Việt, gắn mã tài sản và hồ sơ ca đo, xuất dữ liệu sang hệ bảo trì của khách hàng, triển khai và hỗ trợ tại hiện trường. Đây là giả thuyết cạnh tranh cần phỏng vấn và pilot; chưa được xác nhận nhu cầu trả tiền.

## 4. Khoảng cách cơ điện đã tính được

Snapshot CAD `dcbef445e4b5` có khối lượng mang tải 6,902 kg; 12 actuator đại diện được gán 0,18 kg/chiếc, hình học Ø48 mm. Mô phỏng dùng giới hạn 8 Nm như một giả định servo.

Một **ứng viên khảo sát**, CubeMars **AK60-6 V3.0 KV80**, được nhà sản xuất công bố 380 g, Ø79 × 43 mm, mô-men định mức 3 Nm, đỉnh 9 Nm và lựa chọn 24/48 V. Giá web quan sát ngày 08/10/2026 là 229,90 USD/chiếc; cấu hình và giá cuối cùng cần xác nhận. [Nguồn datasheet và giá](https://www.cubemars.com/product/ak60-6-v3-0-kv80-robotic-actuator.html).

Suy luận riêng từ hai bộ dữ liệu:

```text
Khối lượng thay riêng actuator
= 6,90249 + 12 × (0,380 − 0,180)
= 9,30249 kg

Subtotal 12 actuator theo giá web
= 12 × 229,90 = 2.758,80 USD
```

9,30 kg vượt mục tiêu 7 kg, chưa tính gá mới, dây, nguồn hoặc bổ sung cảm biến. Ø79 mm không thể được coi là đã lắp vừa hình đại diện Ø48 mm. Subtotal actuator chưa phải tổng BOM, chưa gồm thuế, vận chuyển, phụ tùng, gia công và tích hợp.

Không được coi 8 Nm mô phỏng là mô-men liên tục của ứng viên 3 Nm. Cần phân tích tải từng khớp theo duty cycle, lấy thông số torque–speed/giới hạn thời gian đỉnh từ đúng tài liệu, rồi đo trên bàn thử. Hằng số mô-men motor, dòng phase, dòng bus, tỷ số truyền và mô-men đầu ra phải phân biệt; không chép trực tiếp vào mô hình nhiệt tương đương hiện tại.

Bộ chọn actuator tiếp theo phải xét đồng thời: tải và quán tính, mô-men RMS/đỉnh, tốc độ khớp, nhiệt trong chu kỳ, độ rơ, encoder, bus, khả năng cắt lệnh, kích thước interface, tải ổ đỡ, khối lượng và khả năng thay thế. Chưa đủ cơ sở chọn AK60-6 để mua hoặc chế tạo.

## 5. Kiến trúc để làm thật

```text
LLM ngoài sản phẩm → đề xuất JSON
                        ↓ schema / revision / giới hạn
 CAD kernel ← thử baseline/candidate → báo cáo thiết kế
                        ↓ cấu hình được kỹ sư xác nhận
 Nhiệm vụ → planner trên map → supervisor → controller → hardware interface → motor
    ↓                                      ↑
 Thu ảnh / nhiệt ← pose / clock / sensor ← state estimator và telemetry
    ↓
 Kho dữ liệu → kiểm chất lượng → gợi ý bất thường → người xác nhận → hệ bảo trì
```

**Vòng điều khiển:** servo và estimator chạy độc lập khỏi UI/LLM. Tần số, jitter và trễ phải đo trên máy tính robot cùng bus thật; 500 Hz MuJoCo hiện tại không chứng minh điều khiển phần cứng đạt 500 Hz. Với Q4 tự chế, cần estimator dùng IMU/encoder/contact, điều khiển cân bằng và chuyển trạng thái locomotion. PD bám quỹ đạo đang có chưa đủ cho nhà xưởng.

**Hardware interface:** chọn một phiên bản ROS 2 cụ thể rồi viết và build plugin `ros2_control` có lifecycle, `read()`/`write()`, trạng thái encoder/velocity/effort và đường lỗi rõ ràng. Controller chưa được kích hoạt chỉ vì URDF xuất đúng. Tài liệu chính thức mô tả việc xuất plugin và lifecycle; triển khai phải đối chiếu API của phiên bản đã chọn. [ROS 2 control / writing hardware component](https://control.ros.org/jazzy/doc/ros2_control/hardware_interface/doc/writing_new_hardware_component.html).

**Giám sát:** `robotics/supervisor.py` bổ sung máy trạng thái tham chiếu `DISARMED → ARMED → RUNNING`, cùng `HOLD`, `FAULT`, `ESTOP`. Heartbeat quá 250 ms, SOC dưới 25%, nhiệt từ 70°C hoặc lỗi driver/nghiêng gây chặn quyền phát lệnh theo chính sách mẫu. Các ngưỡng này là cấu hình tham chiếu, chưa phải giới hạn đã đánh giá cho robot thật. Có tick monotonic do caller cung cấp; dữ liệu khỏe trở lại không tự chạy tiếp. Reset rồi arm/start rõ ràng.

Supervisor chưa nối motor, chưa lập luồng thời gian thực, chưa ra lệnh dừng vật lý. Chính sách dừng phải quyết định theo trạng thái cơ thể: cắt mọi mô-men có thể làm robot chân sụp. E-stop phần cứng và watchdog cấp driver phải độc lập, có cách kiểm cắt nguồn/lệnh và điều kiện khôi phục. Cần đo khoảng cách dừng, trễ, tư thế sau dừng và ảnh hưởng tới người/vật gần robot.

**Dữ liệu:** đồng bộ clock, xác định hệ tọa độ map, robot serial, CAD/config revision, firmware, asset ID, pose, vị trí nhìn, thời điểm, cấu hình camera và hiệu chuẩn. Lưu ảnh gốc, ảnh nhiệt radiometric, tham số đo, version thuật toán, kết quả người xác nhận và lịch sử sửa. Ảnh giả màu không đủ thay dữ liệu nhiệt định lượng.

**Quản trị:** bản triển khai nhiều người dùng cần authentication/role, phê duyệt nhiệm vụ, audit, giới hạn quyền lệnh và sao lưu. Server hiện chỉ là localhost; chưa có tài khoản, fleet management hoặc triển khai mạng sản xuất.

## 6. Bàn triển khai đã bổ sung

Mở `/deployment.html` trong server cục bộ. Có bốn phần:

- **Nhiệm vụ:** 1–32 điểm kiểm tra, vị trí theo mét, thời gian dừng, giới hạn tốc độ và pin dự phòng. Tính tuyến có lượt quay về và ngân sách từ giả định. Nhập/xuất JSON có schema; xuất context cho LLM bên ngoài.
- **Phần cứng:** registry SKU có URL, ngày kiểm và nhãn `vendor_datasheet`; đối chiếu khối lượng, kích thước và subtotal actuator. Các nhóm chưa có báo giá giữ trạng thái thiếu, không điền chi phí bằng 0.
- **Dữ liệu nghiệm thu:** nhập CSV và metadata; kiểm timestamp tăng, finite/range, target ID, tham chiếu media, khoảng mẫu, tốc độ, thời gian dừng liên tục, reserve, nhiệt và E-stop. Tích phân V×I bằng quy tắc hình thang.
- **Điều kiện triển khai:** tám nhóm cơ điện, actuator, nguồn, an toàn, điều hướng, đo, field và dịch vụ. Hiện chưa nhóm nào đủ bằng chứng để đóng. Một log đạt không tự thay trạng thái này.

Mẫu tuyến: 6 điểm, tuyến hình học 47,8 m, tốc độ giả định 0,2 m/s, dừng 15 s/điểm. Thời gian danh định khoảng 5,5 phút. Với công suất giả định 115 W, năng lượng khoảng 10,5 Wh. Pin 120 Wh, hệ số hữu dụng 0,8, SOC đầu 0,9 và reserve 0,25 cho ngân sách 62,4 Wh. Các con số là **tính toán lập kế hoạch**, không phải runtime hay công suất đo. Đường nối thẳng không xét vật cản hoặc chứng minh robot đến được điểm.

Không được suy từ một tuyến 5,5 phút rằng robot đủ chạy cả ca. Cần đo công suất, thời gian recover, đổi tuyến, chuyển động, chế độ đứng, payload và suy giảm pin thực.

### Giao thức log

CSV theo template xuất từ UI, tối đa 1 MB và 12.000 dòng. Bộ log pilot nên tổng hợp ở 1–5 Hz; trace servo tốc độ cao lưu riêng để kiểm latency và điều khiển. Không hạ tốc độ log servo rồi dùng log pilot để kết luận an toàn. Cột chính: thời gian giây monotonic từ đầu ca, vị trí X/Y mét trong map, SOC từ BMS ở [0,1], điện áp và dòng bus DC, nhiệt motor khai báo, trạng thái E-stop và permission lệnh, điểm kiểm, capture flag, đường dẫn tương đối ảnh RGB/thermal.

Dòng bus không âm; schema v1 chưa biểu diễn tái sinh năng lượng. Không dùng dòng phase thay dòng bus. Nhiệt là giá trị khai báo lớn nhất trong nhóm motor; cần exporter phần cứng chuyển đúng quy ước. `command_enabled` là quyền lệnh được log, không phải phép đo contactor đã ngắt.

Metadata có nguồn `simulation/bench/field`, hardware ID, firmware, operator, calibration ID, ngày có múi giờ, CAD revision và mission SHA-256 **lúc thu thập**. Khi sửa mission, log cũ phải bị chặn vì lệch hash; không tự đổi hash cũ cho nhiệm vụ mới. UI có trường nhập hash để operator đối chiếu với exporter.

Server lưu `telemetry.csv`, `report.json` và manifest trong `deployment-output/<id>` bằng publish thư mục nguyên tử. Kiểm manifest khi đọc lại và báo nếu source đã đổi. Đây là kiểm toàn vẹn cục bộ, không phải chữ ký số hoặc xác thực provenance. Thư mục runtime không đưa vào Git.

Log kiểm được **số liệu người nhập khai báo**. Chưa đọc byte ảnh, chưa kiểm radiometry/chứng chỉ hiệu chuẩn, chưa xác thực người nhập, chưa đo latency E-stop. Một người vẫn có thể gán nhãn `field` cho dữ liệu không phải hiện trường; report giữ `provenance_verified=false`, `hardware_verified=false`, `deployment_authorized=false`. Nguồn và hạn chế đi cùng report.

Các tiêu chí hiện tại: đầy đủ các điểm có RGB+thermal reference ở trong 0,5 m, đủ stationary dwell liên tục mỗi điểm, khoảng mẫu từ 0,0001 đến 1 s, tốc độ từ vị trí ≤110% giới hạn, SOC ≥ reserve, motor <70°C, không có sample E-stop và lệnh cùng bật, cuối ca cách base ≤0,5 m, ngân sách danh định không vượt. Đây là kiểm hợp đồng log, chưa phải định vị chính xác, ổn định động lực hoặc safety certification.

## 7. AI nào tạo lợi thế thực tế

**Thiết kế:** LLM đề xuất thay đổi theo yêu cầu payload/mass, kernel dựng, mô phỏng kiểm và kỹ sư xem các trade-off. Khi có SKU thật, context phải thêm interface, envelope, torque–speed, nguồn và chứng cứ đo. Chưa nên để LLM nới ngưỡng hoặc thực thi mã tùy ý.

**Nhiệm vụ:** LLM chuyển mô tả kiểm tra thành đề xuất JSON, chỉ trong giới hạn schema. Tọa độ cần map và người chốt; lời nói không tự cho phép robot chạy. Hiện giữ nhập/xuất JSON theo lựa chọn của người dùng, chưa tích hợp API.

**Inspection:** VLM/LLM có thể gợi ý ROI, mô tả hiện tượng, so ca đo và dự thảo báo cáo. Muốn dùng trong hợp đồng phải có tập ảnh của chính site, ground truth từ kỹ thuật viên, đo precision/recall, tỷ lệ từ chối khi ảnh kém và theo dõi drift. Luôn giữ đường dẫn tới ảnh gốc/đo gốc, calibration và quyết định của người. Hiện chưa có model inspection hoặc dataset để khẳng định chất lượng.

**Vận hành:** hỗ trợ tìm SOP, giải thích nguyên nhân gate fail và dựng phiếu công việc. LLM không giữ vòng servo hoặc quyền E-stop. Văn bản trên ảnh/file nhập được xem là dữ liệu, không phải lệnh hệ thống.

Đầu tư dài hạn đáng ưu tiên: dữ liệu ca đo, phép thử có oracle, interface ổn định, quy tắc nghiệm thu, cơ sở tri thức tài sản và quy trình người xác nhận. Model AI có thể thay thế khi tốt hơn; dữ liệu và các phép kiểm cho phép đánh giá việc thay model. Tốc độ tiến hóa AI chưa loại bỏ nhu cầu thử tải, hiệu chuẩn, nhiệt, dây, an toàn hoặc dịch vụ.

## 8. Yêu cầu sản phẩm và tiêu chí pilot đề xuất

| Ưu tiên | User story / yêu cầu | Nghiệm thu |
|---|---|---|
| P0 | Kỹ sư chốt đúng mission và cấu hình | Schema, revision, hash; lệnh không tự phát từ LLM |
| P0 | Operator biết trước khả năng tuyến | Site survey, map, vùng loại trừ, checklist trước ca và bảng lỗi có hành động |
| P0 | Kỹ thuật viên có dữ liệu đủ dùng | Mỗi capture có asset, timestamp, pose, RGB gốc, thermal gốc, calibration và trạng thái chất lượng |
| P0 | Dừng và khôi phục có kiểm soát | Thử E-stop, mất heartbeat, driver lỗi, low SOC; đo thời gian/khoảng dừng, không tự resume |
| P0 | Có thể kiểm lại report | Log gốc, manifest, cấu hình, thuật toán và ghi chú người xác nhận; giữ lỗi không xóa |
| P1 | Giảm công sức lập báo cáo | So nhiều ca theo cùng vị trí và điều kiện, xuất báo cáo/phiếu bảo trì có người duyệt |
| P1 | Hoạt động sau lỗi recoverable | Chỉ recover theo policy đã thử; có manual takeover và ghi sự kiện |
| P1 | Tích hợp quy trình nhà máy | Mã tài sản và yêu cầu bảo trì đi vào hệ đang dùng; quyền và retention chốt với khách hàng |
| P2 | Tăng mức tự động | Docking, scheduling, nhiều robot và AI triage sau khi P0/P1 đủ bằng chứng |

Mục tiêu pilot đề xuất, **chưa đạt**: ≥95% điểm có dữ liệu được kỹ thuật viên chấp nhận; hoàn thành ≥95% tuyến được phép trong 30 ca liên tiếp; không có sự kiện chạy trái permission; mọi thử lỗi đều đưa robot về trạng thái đã định; giảm ≥30% thời gian **thu thập + kiểm lại + lập báo cáo** so baseline thủ công trên cùng tuyến. Các tỷ lệ và 30 ca là tiêu chí thảo luận, không phải chứng minh độ tin cậy dài hạn hoặc an toàn. Cần báo khoảng tin cậy, mẫu lỗi và điều kiện từng ca, không chỉ phần trăm.

## 9. Thứ tự đầu tư theo quyết định, không theo số màn hình

| Giai đoạn | Việc bắt buộc | Bằng chứng để quyết định đi tiếp |
|---|---|---|
| Khảo sát bài toán | 1 site, tuyến, asset, baseline công việc, người nghiệm thu | Khách hàng xác nhận đầu ra có giá trị và cho pilot |
| Chốt architecture | Build-vs-buy, SKU, tải và nguồn payload, BOM, giao thức và support | Interface kiểm được, cấu hình/báo giá đủ, rủi ro lớn có phép thử |
| Bench | Nếu Q4: một chân; actuator, nguồn, heat soak, harness, encoder, fault | Torque/thermal đo được và phản hồi lỗi đúng; thiết kế lại nếu không đạt |
| Tích hợp | Driver/estimator/controller, cảm biến, timestamps, camera calibrations | Test tự động + HIL + hồ sơ tương ứng đúng serial/revision |
| Pilot có giám sát | Tuyến giới hạn, capture thật, lỗi/recover, operator review | Đạt tiêu chí ca đo và công việc; lỗi còn lại có owner và cách xử lý |
| Đề nghị thương mại | SOP, training, phụ tùng, bảo hành, SLA và chi phí | Chứng minh năng lực vận hành và hợp đồng tương ứng phạm vi đã thử |

Chưa ấn định lịch giao robot hoặc ngân sách tổng khi chưa có đội thực hiện, vendor quote và dữ liệu bench. Chủ nhiệm cơ điện chịu interface/tải; điều khiển chịu runtime và lỗi; kỹ sư đo chịu calibration/chất lượng; triển khai chịu site/SOP; khách hàng chịu tiêu chí nhận dữ liệu. Mỗi gate có owner và artifact đo, không đóng bằng cảm nhận rằng demo đẹp.

## 10. Kinh tế phải đo được

Tách tiền nền di chuyển, payload, tích hợp và phí vận hành. Tổng chi phí cần gồm: phần cứng, gia công, phụ tùng, hiệu chuẩn, pin/sạc, đào tạo, triển khai, máy tính/lưu trữ, AI nếu dùng, bảo trì, vận chuyển, thời gian operator và ca lỗi. Dự phòng bảo hành cần có cơ sở từ thử nghiệm/nhà cung cấp.

Tính giá trị trước bằng thời gian tiết kiệm đã đo trên cùng công việc và số lượt kiểm có dữ liệu đạt. Không tự đưa giá trị tránh downtime vào doanh thu tiết kiệm khi chưa có bằng chứng quy kết. Nên thử hợp đồng pilot có đầu ra cụ thể trước lời hứa ROI.

Chỉ so hoàn vốn khi có báo giá và số liệu site:

```text
Lợi ích ròng năm = giá trị công việc tiết kiệm đã đo − chi phí vận hành tăng thêm
Hoàn vốn đơn giản = chi phí đầu tư / lợi ích ròng năm (chỉ khi > 0)
```

Đây là công thức lập mô hình, chưa có dữ liệu đủ để dự báo. Phải có cả kịch bản số ca thấp, lỗi/rework, giá bảo trì và thời gian review lớn hơn dự kiến. Giải pháp cạnh tranh khi khách hàng thấy chi phí cho mỗi hồ sơ kiểm tra đạt chất lượng hợp lý, cùng khả năng hỗ trợ vận hành.

## 11. Phạm vi đã kiểm trong đợt nâng cấp này

`npm run test:deployment`: oracle tuyến 3–4–5 và điện năng; tính lại khối lượng 12 actuator; schema hữu hạn; log hoàn chỉnh tổng hợp; cố tình khai báo field không làm mở quyền; log nhiệt/pin/E-stop lỗi; NaN, timestamp trùng, hash lệch và traversal; supervisor mất heartbeat/latch/reset; manifest bị sửa; HTTP origin/schema và context không gọi LLM. Đây là kiểm phần mềm bằng fixture, không phải đo robot.

Chưa thay CAD motor, chưa thay spec.yaml, chưa gọi AI API, chưa chạy plugin ROS, chưa chế tạo hoặc chạy robot ở nhà xưởng. Các phép thử cũ về CAD/MuJoCo vẫn giữ phạm vi riêng; không dùng chúng để suy ra tính thương mại đã được nghiệm thu.

Trong checkout lúc nâng cấp, STEP assembly, PDF tổng và ZIP dossier của snapshot CAD mặc định đang thiếu từ trước. Chưa dựng lại hoặc đóng gói release mới. Gói ROS sinh tự động bị thiếu mesh/ZIP đã được dựng lại từ CAD chi tiết và kiểm manifest; hồi quy API vật lý và AI Engineering đã qua. Workspace pilot được bàn giao trên server localhost.
