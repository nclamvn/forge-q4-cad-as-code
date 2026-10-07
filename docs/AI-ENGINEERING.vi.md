# FORGE Q4: thiết kế bằng LLM, quyết định bằng bằng chứng

Bản nâng cấp này đưa ý đồ thiết kế qua một vòng có thể chạy lại: xuất context cho LLM → nhập đề xuất JSON → kiểm đầu vào → dựng baseline/candidate CAD → mô phỏng cùng điều kiện → so sánh → áp dụng hoặc sửa đề xuất. Giao diện không gọi API LLM. LLM được dùng ở công cụ bên ngoài theo lựa chọn của người dùng; đề xuất mẫu trong sản phẩm do người viết, không được gắn nhãn là suy luận trực tiếp từ AI.

## Chạy và thao tác

Chạy `Start.command`, mở `http://127.0.0.1:8767/?workspace=ai&backend=webgl`. Server cần Python với `requirements-simulation.txt` và Node.js 18+. WebGL2 là đường mở đã kiểm trong in-app browser; WebGPU vẫn được hỗ trợ bởi renderer nhưng đã có một lần khởi tạo bị treo trong phiên thử trước.

1. Dựng CAD nếu đang có thông số chưa áp dụng. Mỗi đề xuất phải chỉ đúng revision baseline.
2. Viết mục tiêu, bấm **Xuất prompt cho LLM**. File JSON chứa prompt, đặc tả, khối lượng, giới hạn tham số, quy tắc vành lỗ, giả định vận hành, bộ thử bắt buộc và mẫu đề xuất.
3. Đưa file cho LLM anh đang dùng. Yêu cầu trả JSON theo `forge-design-proposal-v1`; nhập file hoặc dán vào ô đề xuất. Có thể xuất đề xuất JSON để lưu riêng.
4. Bấm **Kiểm đầu vào & diff**. Giới hạn, NaN, trường lạ, revision cũ và vành lỗ quá mỏng bị chặn. Đầu vào hợp lệ chưa có nghĩa là thiết kế đạt.
5. Bấm **Dựng hai CAD & chạy 10 lượt thử**. Server chạy nền; thao tác giao diện không phải chờ một HTTP request kéo dài. Giai đoạn dựng BREP/bản vẽ có thể mất khoảng một phút trên máy đã thử. Có thể yêu cầu hủy, nhưng không thể cắt giữa một phép dựng OCCT.
6. Mở từng trường hợp để xem đồ thị cao độ, bám lệnh, lực, trượt và điện/nhiệt ước tính. Tải bằng chứng hoặc xuất feedback JSON kèm prompt để LLM sửa đề xuất.
7. Chỉ candidate qua tất cả tiêu chí khai báo mới được áp dụng. **Về baseline** khôi phục CAD của lần áp dụng đó; lịch sử vẫn được giữ. Việc áp dụng thay mô hình đang mở, không tự sửa `spec.yaml` hay snapshot mặc định. Xuất YAML/STEP để lưu thiết kế anh chọn.

Đề xuất tham khảo: `docs/examples/proposal-lightweight.json`. Đây là giả thuyết giảm dày tay chân từ 7 xuống 6 mm, còn thiếu kiểm bền/mỏi.

## Phần mềm thay được phần nào của CAD?

Trong không gian tham số Q4 hiện có, phần mềm thay được thao tác nhập kích thước và dựng lại các hình học đã định nghĩa. Một đặc tả sinh BREP, STEP lắp ráp/chi tiết, BOM 42 vị trí, 14 tờ A3, DXF, tensor quán tính, URDF và MJCF. Có thể đề xuất và kiểm thay đổi kích thước, vật liệu đại diện, tải, khối lượng gán và thông số servo thay vì sửa thủ công từng đầu ra.

Nó chưa thay việc thiết kế hình học tùy ý, sketch constraint solver, sửa topology trực tiếp, quản lý drawing annotation tùy ý, GD&T, FEM, mỏi, dây điện, CAM hay nghiệm thu lắp ráp thực. JSON không thực thi Python do LLM gửi. Muốn mở rộng sang một cơ cấu khác, kỹ sư vẫn phải xây thêm compiler, ràng buộc và bộ kiểm. Không có cơ sở để nói đã thay được một tỷ lệ phần trăm của mọi công việc CAD.

Điểm có thể phát triển thành lợi thế là chuỗi dữ liệu thiết kế → thử nghiệm → revision, chứ không phải một mô hình 3D biết chuyển động. LLM mạnh hơn có thể tạo giả thuyết tốt hơn mà không phải thay cơ chế kiểm. Nhưng chất lượng sản phẩm robot vẫn phụ thuộc vào dữ liệu vật liệu, motor, tải và hiệu chuẩn từ phần cứng thật.

## Vận hành được mô tả như thế nào?

MuJoCo giải thân tự do, trọng lực, khớp, servo và tiếp xúc từ khối lượng/quán tính dẫn xuất CAD. Khi bật **Motor, nhiệt và pin**, mô hình vận hành dùng mô-men và tốc độ thực đã giải để tích phân thêm:

- Mô-men khả dụng giảm theo tốc độ khớp, nhiệt, điện áp ước tính và sức khỏe motor được chọn. Giới hạn này được đưa vào `actuator_forcerange` trước bước giải; nó thay đổi chuyển động thực, không chỉ một thanh trạng thái.
- Mô hình nhiệt RC tương đương: `C·dT/dt = I²R − (T−Tamb)/Rthermal`, với `I = torque / Kt_output`. Các hệ số mô tả một drive tương đương ở đầu ra khớp, chưa được nhận dạng từ motor thật.
- Điện năng: tải phụ + công suất cơ dương/hiệu suất + tổn hao đồng. Không tính tái sinh; công suất hãm được coi là tiêu tán. Pin giảm theo tích phân năng lượng, điện áp dùng mô hình tuyến tính và sụt áp điện trở đơn giản.
- Mặc định giả định pin 120 Wh, điện áp 24 V, tốc độ không tải 32 rad/s, giảm mô-men từ 70°C, ngắt drive ở 90°C hoặc mức dự trữ pin 10%. Có thể khởi tạo motor nóng, pin thấp và một motor suy giảm. Ngắt bảo vệ được giữ cho đến lần dựng mới.

Không được dùng các con số trên để công bố thời lượng pin hoặc định mức motor. Mô hình chưa có BMS, nhiệt nhiều nút, gearbox efficiency map, mô hình cell, cơ chế hãm riêng hay thông số cảm biến hiệu chuẩn. Nhiệt và điện được gắn nhãn **ước tính** trên màn hình, JSON và CSV.

RMS bám lệnh lấy từ góc khớp giải thực so với lệnh servo. Trượt lấy tốc độ ngang của site bàn chân đang chịu lực. Biên CoM là khoảng cách chiếu XY đến đa giác của ít nhất ba chân có lực >0.5 N; với hai chân nó trả `null`. Đây là chỉ báo hình học tĩnh, không phải ZMP hoặc chứng minh ổn định động. Robot vẫn dùng quỹ đạo tham chiếu và servo khớp; chưa có bộ điều khiển cân bằng toàn thân/MPC.

## Bộ thử và điều kiện đạt

Baseline và candidate dùng cùng profile vận hành, biên độ 0.6 và nhịp 0.6, ở năm điều kiện: đứng 6 s, chạy chéo 8 s, đi trên dốc 5° 6 s, chạy với ma sát 0.25 trong 6 s, đứng chịu đẩy ngang 35 N trong 0.12 s tại giây thứ 3 của lượt 6 s. Chỉ thông số CAD và servo mà đề xuất nêu mới khác nhau.

Kiểm cao độ/bám lệnh/nghiêng/giới hạn khớp từ giây 1.8 sau đoạn ổn định đầu. Xuyên nền lấy đỉnh của cả lượt. Kiểm ngã, tự tiếp xúc và drive cutoff cũng được lưu. Mặc định: tải toàn bộ ≤7 kg, nghiêng ≤25°, RMS góc ≤0.35 rad, xuyên nền ≤5 mm, cao độ ≥0.75×home; không ngã/drive cutoff/tự tiếp xúc; cữ mềm cho phép vượt tối đa 0.035 rad. Đây là các tiêu chí sàng lọc khai báo, không phải tiêu chuẩn an toàn hay định mức vận hành. Có thể đặt ngưỡng chặt hơn trong JSON và xem chúng trên bảng kết quả.

Một thiết kế qua các lượt ngắn này chưa chứng minh leo bậc, tải động, vận hành dài, phản ứng trước môi trường chưa biết hay tự hành. Tốc độ X trung bình là quãng dịch chuyển X chia toàn thời gian lượt, gồm ổn định đầu; không phải tốc độ cruise điều khiển theo mục tiêu.

## Bằng chứng thực hiện trên máy này

Thử nghiệm mẫu `ae205bf2b6ac480fb5d5cbf7c029db9d`, baseline `dcbef445e4b5`, candidate `ce45351f06ae`:

| Kết quả | Baseline | Candidate |
|---|---:|---:|
| Khối lượng có tải | 6.902 kg | 6.838 kg |
| Mô-men đỉnh, lượt chạy chéo 8 s | 3.55 Nm | 3.07 Nm |
| RMS bám lệnh, lượt chạy chéo | 0.017 rad | 0.016 rad |
| Trượt chân chịu tải trung bình | 0.054 m/s | 0.059 m/s |
| Điện năng ước tính, lượt chạy chéo | 0.0348 Wh | 0.0345 Wh |

Cả hai qua năm điều kiện khai báo. Candidate nhẹ hơn khoảng 64 g nhưng trượt cao hơn trong lượt chạy chéo, và giảm dày cần kiểm bền. Không suy ra phương án này tốt hơn toàn diện. Dữ liệu đầy đủ nằm trong `reports/robotics/engineering-example.json`.

Bộ kiểm độc lập xác nhận công thức điện/nhiệt, dấu biên đa giác, giới hạn tốc độ–nhiệt–motor suy giảm, cutoff có lực thực gần 0 và làm thân hạ xuống, pause không tiêu hao thêm năng lượng và mô hình vận hành tắt không thay kết quả plant cũ. API kiểm revision cũ, trường lạ, NaN, origin khác, hủy job, đồng thời và cấm áp dụng kết quả chưa đạt. Đường áp dụng kiểm hash báo cáo, candidate và source; baseline/candidate STEP bị đổi cũng yêu cầu chạy lại.

## Lưu trữ và kiểm lại

`engineering-output/<id>/` chứa báo cáo đang chạy, candidate CAD và dấu hash bằng chứng sau hoàn tất. Giữ qua restart; lượt đang chạy khi server tắt sẽ được đọc là `interrupted`. Thư mục này bị loại khỏi Git và gói chia sẻ mặc định để không phát hành lịch sử ý đồ của người dùng. Gói nguồn chỉ kèm ví dụ/báo cáo được chọn. Bản HTML offline vẫn xem CAD/động học, nhưng dựng CAD, bàn thử và mô phỏng cần server.

Chạy `npm run test:operations`, `npm run test:engineering`, `npm run test:engineering-api`, `npm run test:robotics`, `npm run test:physics-api`. Engineering test tự chạy ví dụ nếu chưa có một thử nghiệm hoàn tất cùng source. ROS 2/RViz, robot thật và hiệu chuẩn chưa được kiểm trong môi trường này.

Tài liệu nền: [MuJoCo XML/actuator](https://mujoco.readthedocs.io/en/stable/XMLreference.html). Khi tích hợp API sau, [Structured Outputs của OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs) có thể ràng buộc định dạng trả về; kiểm schema và các phép thử vật lý vẫn phải nằm ở server.
