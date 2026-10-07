# FORGE Q4 — phần mềm kỹ thuật từ CAD đến mô phỏng

Mục tiêu là kiểm một thiết kế robot bằng chuỗi dữ liệu có thể tái tạo. Geometry, quán tính, khớp và file trao đổi cùng xuất phát từ đặc tả CAD. Three.js/WebGPU/WebGL2 hiển thị; MuJoCo chịu trách nhiệm vật lý. AI đã hỗ trợ viết phần mềm, không có LLM chạy trong vòng điều khiển.

## Mức sử dụng hiện tại

Có thể sửa tham số CAD, dựng STEP và bản vẽ; tạo robot description; chạy mô phỏng thân tự do; xem lực, trạng thái khớp và IMU; thử nhiễu hoặc motor yếu; xuất dữ liệu để kỹ sư kiểm lại. Đây là một workbench kỹ thuật chạy được, với thiết kế Q4 tham chiếu. Các phép kiểm phần mềm không chứng nhận khả năng chế tạo, độ bền hay robot thật.

Chuỗi hiện thực:

```text
spec.yaml → validation → build123d / Open Cascade
  ├─ 12 solid BREP / 42 instance → STEP / 14 A3 / 48 DXF
  ├─ tích phân volume, COM, inertia từ STEP
  │    → 13 rigid link / 12 revolute joint / SI / ROS
  │    → URDF + MJCF + STL/OBJ + manifest
  └─ quỹ đạo IK → position servo có giới hạn mô-men
       → MuJoCo: free base / gravity / friction / contacts
       → transform thực / lực chân / IMU / telemetry 50 Hz
       → Three.js: hiển thị kết quả đã giải
```

## Chạy và thao tác

Cần Python, Node.js 18+ và dependency trong `requirements-simulation.txt`. Môi trường đã kiểm: Python 3.12.14, Node.js 24.14.1, MuJoCo 3.15.0. Trên macOS chạy `zsh Start.command`; lệnh này cài dependency còn thiếu rồi mở server localhost. Chạy thủ công:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-simulation.txt
.venv/bin/python server.py
```

Mở `http://127.0.0.1:8767/?workspace=physics`. Chọn một quỹ đạo, nhịp và biên độ; chọn nền, hệ số ma sát và giới hạn mô-men; bấm **Dựng và chạy vật lý**. Nút tạm dừng đóng băng thời gian giải. Sửa thông số yêu cầu dựng lại; hệ thống giữ kết quả cũ gắn với profile cũ đến khi phiên mới sẵn sàng. Phải dựng CAD trước nếu đặc tả hình học còn thay đổi chưa áp dụng.

**Đẩy ngang 35 N** tác động lên thân theo trục Y của ROS trong 0,12 s. **Ngắt motor** tắt actuation và tiếp tục giải trọng lực; phải dựng phiên mới để bật lại. Đây là thí nghiệm trong solver, không phải chức năng ngắt khẩn cấp của phần cứng.

Đồng hồ hiển thị thời gian mô phỏng, không phải cam kết chạy đúng thời gian thực. Solver dùng bước 2 ms; UI cập nhật khoảng 25 lần/s tùy máy; telemetry ghi 50 Hz, giữ tối đa 15.000 frame gần nhất. CSV có 12 hàng khớp/frame; report JSON chứa pose, phản lực, IMU, cấu hình và fingerprint mã. Công `∫|τ·ω|dt` là tích phân cơ học gần đúng tại khớp, không phải điện năng pin.

Lịch đặt chân là **lịch lệnh dự kiến**. Ô lực N và trạng thái chân chịu lực lấy từ solver, với ngưỡng 0,5 N. Quỹ đạo hiển thị trong workspace vật lý là đường đi bàn chân đã giải. Mũi tên lực dùng tỷ lệ hiển thị 1 N = 1,2 mm, chiều dài tối đa 160 mm; không phải biến dạng của chân.

## Hình học và quán tính

Revision CAD mới `dcbef445e4b5` sửa hai lỗi được phát hiện nhờ tiếp xúc: vỏ chân dưới kéo quá đầu chân và đầu capsule kim loại chạm nền trước đệm. Vỏ dưới kết thúc phía trên bàn chân; đệm 26 × 24 × 32 mm, R6; tư thế CAD có khoảng hở nền 1 mm. Hồ sơ STEP/A3/DXF/BOM đã dựng lại.

Mô hình dùng X tiến, Y trái, Z lên; m, kg, rad và kg·m². `robotics/model.py` đọc từng STEP để lấy volume, COM và tensor quán tính bằng tích phân OCCT, rồi đổi từ mm sang SI. Khối lượng của từng chi tiết giữ theo cơ sở đã công bố trong CAD; các vật đại diện motor/pin có khối lượng gán. Quán tính gán giả định mật độ đồng nhất trên khối đại diện. Link ghép nhiều chi tiết dùng định lý trục song song.

Electronics và payload không có CAD riêng: giả định một khối hộp trung tâm, cao hơn gốc thân 5 mm. Việc chia vỏ motor vào các rigid link là mô hình cơ cấu khái niệm; chưa mô tả rotor/stator và quán tính trục motor đo thực tế. Tổng khối lượng có tải là **6,90249 kg**, được đối chiếu với CAD và tổng body mass trong MuJoCo.

Zero của 12 khớp là tư thế lắp ráp CAD, không phải vị trí encoder đã hiệu chuẩn. URDF dùng 13 link, 12 khớp revolute, 42 visual và 42 collision. MJCF thêm floating base. Model JSON giữ đầy đủ origin, axis, COM, inertia, allocation chi tiết và các hash STEP.

## Vật lý và điều khiển

MuJoCo dùng `implicitfast`, trọng lực 9,81 m/s², bước 0,002 s, tiếp xúc có ma sát và servo vị trí có giới hạn lực trong solver. Profile mặc định: giới hạn 8 Nm, kp 65 Nm/rad, kv 1,5 Nm·s/rad, armature 0,0002 kg·m². Tất cả là giả định phục vụ mô phỏng, chưa đối chiếu datasheet motor.

Quỹ đạo từ `web/motion-engine.js` được biên dịch bằng `tools/motion-reference.mjs`, dùng chung kích thước CAD. Có một giây settle, 0,8 s chuyển vào lệnh, và giới hạn tốc độ thay đổi lệnh 12 rad/s. Giới hạn đó không chứng minh vận tốc khớp thực tế luôn nhỏ hơn 12 rad/s. Thân tự do được giải từ lực và tiếp xúc; không có phép dịch thân định sẵn hoặc teleport để giả chuyển động tiến.

Cữ góc trong MuJoCo là ràng buộc mềm, nên góc thực có thể vượt nhẹ khi va chạm hoặc ngắt motor. Bảng khớp hiển thị góc thực, dùng đúng cữ dạng chân ±28,6° và cữ hông/gối của CAD, gạch dưới giá trị vượt cữ; tooltip có mô-men, vận tốc và cữ. Giới hạn mô-men servo là force clamp, khác với cữ mềm này.

Collision dùng convex hull của mesh CAD. MuJoCo lọc va chạm giữa body cha/con theo mặc định; các tiếp xúc giữa cụm không liền kề được ghi nếu xuyên trên 0,2 mm. Chỉ số này không chứng minh toàn bộ thiết kế không va chạm BREP. Lỗ, chi tiết lõm và mặt vỏ không giữ chính xác trong hull. Muốn kiểm lắp ráp cần thêm kiểm hình học chính xác và collision decomposition phù hợp.

Dốc 5° được dựng theo cùng normal giữa solver và renderer; robot bắt đầu ở tư thế home nghiêng theo dốc để không xuyên nền ngay lúc khởi tạo. Bậc 30/60/90 mm là vật cản thật. Có mặt bậc không có nghĩa controller hiện tại leo được ba bậc.

Controller hiện là servo theo quỹ đạo mở. Chưa có state estimator, phản hồi cân bằng toàn thân, MPC, planner bước thích ứng, tối ưu tiếp xúc, mô hình motor/pin đã nhận dạng, gearbox/backlash, cảm biến có nhiễu hoặc driver phần cứng. Detector ngã dùng thân thấp hơn 90 mm hoặc nghiêng trên 45°; đây là heuristic phần mềm.

## File xuất và ROS 2

Trong **Mô hình và dữ liệu chạy**, tải `FORGE-Q4-Robotics.zip`. ZIP chứa thư mục `forge_q4_description`, URDF, MJCF, 12 STL + 12 OBJ theo SI, `robot-model.json`, `profile.yaml`, `MANIFEST.json`, CMake, package metadata và launch file. Hash mô hình phụ thuộc revision CAD, hash của STEP/mesh/khối lượng/transform đầu vào, mã compiler robot và profile; mã simulation và quỹ đạo có fingerprint riêng trong report chạy.

Trên máy đã có ROS 2 và các package robot_state_publisher, joint_state_publisher_gui, RViz2, launch_ros, ament_index_python:

```sh
mkdir -p ~/q4_ws/src
# Giải nén forge_q4_description vào ~/q4_ws/src
cd ~/q4_ws
colcon build --packages-select forge_q4_description
source install/setup.bash
ros2 launch forge_q4_description display.launch.py
```

Trong RViz đặt Fixed Frame = `base_link`, thêm RobotModel. GUI khớp phát joint_states để xem cơ cấu. URDF đứng riêng có base cố định; MJCF có floating base. Gói này chưa bao gồm ros2_control, trajectory controller, bridge telemetry hoặc hardware interface.

**URDF đã được kiểm XML và đọc độc lập bằng MuJoCo**, sau đó đối chiếu pose 13 link ở góc khớp khác zero với MJCF. **ROS 2/colcon/RViz chưa chạy trong môi trường hiện tại**; launch file cần được nghiệm thu trên máy có ROS. Không coi phép đọc URDF là bằng chứng toàn bộ ROS stack đã chạy.

MuJoCo riêng: vào thư mục package, dùng `python -m mujoco.viewer --mjcf=forge_q4.xml`. XML có plant và actuator; mở viewer riêng không tự nạp quỹ đạo của FORGE. Server FORGE cung cấp controller và run/report API.

## Kiểm chứng có thể tái tạo

```sh
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python tests/kernel_test.py
.venv/bin/python tests/dossier_test.py
.venv/bin/python tests/api_test.py       # server đang mở
npm run test:motion
.venv/bin/python tests/robotics_test.py
.venv/bin/python tests/physics_api_test.py
```

`model-tests.json` kiểm tổng khối lượng, COM độc lập từ 42 instance, quán tính dương/thỏa bất đẳng thức tam giác, pose home, clearance đệm, URDF độc lập, pause, gravity/zero-gravity, motor cutoff, lực giới hạn, tái chạy xác định và đứng 60 s. `qualification.json` ghi 15 quỹ đạo trong bài thử 10 s ở biên độ/nhịp 0,6; thêm trot mặc định, dốc, bậc, ma sát thấp, nhiễu ngang và motor yếu. Ma trận ghi đúng kết quả ngã, chuyển vị, xuyên tiếp xúc và solver warnings; nó không phải chứng nhận mọi gait, mọi tốc độ hay khả năng nhảy/leo bậc.

Các kiểm CAD và động học vẫn chạy riêng: bốn biến thể hình học, STEP round-trip, 14 A3/48 DXF, 27.000 tư thế và 225 cặp chuyển tiếp. Physics API kiểm lifecycle, report, tải gói và từ chối input không hợp lệ. Browser review ghi riêng các thao tác đã thử và screenshot. Release tool từ chối đóng gói nếu revision hoặc hash mã đã đổi sau phép kiểm.

Để tiến tới robot cụ thể: thay hình đại diện bằng actuator/pin thật; nhập khối lượng/quán tính/torque-speed và transmission đã đo; nghiệm thu cơ cấu/dung sai; xây estimator và controller phản hồi; kiểm mô hình với dữ liệu bench; rồi mới thực hiện thử robot có quy trình riêng. Kiến trúc hiện tại hỗ trợ thay các mô-đun đó mà giữ chuỗi truy vết CAD và report.

Nguồn kỹ thuật chính thức: [MuJoCo Python](https://mujoco.readthedocs.io/en/stable/python.html), [MJCF và actuator](https://mujoco.readthedocs.io/en/stable/XMLreference.html), [build123d import/export](https://build123d.readthedocs.io/en/latest/import_export.html).

## Bàn AI Engineering và mô hình vận hành bổ sung

[AI-ENGINEERING.vi.md](AI-ENGINEERING.vi.md) mô tả luồng context JSON → đề xuất LLM bên ngoài → dựng hai CAD → 10 lượt thử → bằng chứng → áp dụng/khôi phục. Bàn Vật lý có thể bật mô hình drive tương đương gồm torque-speed, nhiệt RC, tổn hao đồng và năng lượng pin. Các giá trị điện/nhiệt là ước tính chưa hiệu chuẩn.

Mô hình vận hành nằm trong runtime Python `robotics/operations.py`; URDF/MJCF trong gói ROS chứa định mức và cấu hình servo danh định, không chứa một plugin BMS/nhiệt. Báo cáo JSON giữ operating profile và hash source để chạy lại cùng điều kiện.
