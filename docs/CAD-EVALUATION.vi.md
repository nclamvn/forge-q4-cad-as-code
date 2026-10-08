# FORGE CAD Evaluation Lab

Mở `http://127.0.0.1:8767/benchmark.html` sau khi chạy server. Lab đo vòng đề xuất–dựng–kiểm với yêu cầu độc lập và lưu phiên trên đĩa. Đề bài công khai, sinh theo seed; đây chưa phải benchmark mù hoặc nghiên cứu hiệu quả LLM đã hoàn thành.

## Ba bài toán trên máy tính

| Bài toán | Phép kiểm bổ sung ngoài kiểm CAD chung |
| --- | --- |
| Dời sensor và mở đường cáp | Đúng dịch chuyển X/Y; toàn bộ corridor slot quy định phải rỗng xuyên tấm |
| Tạo chi tiết nhẹ có vùng đỡ | Cửa sổ tròn xuyên đúng kích thước; hai vùng probe có ≥98% vật liệu; khối lượng ≤70 g theo mật độ giả định |
| Thiết kế một họ kích thước | Tự dựng lại tại chiều rộng 88/94/98 mm; đo chiều rộng BREP thực; lặp kiểm giao diện và yêu cầu công việc |

Kiểm probe vật liệu không chứng minh khả năng chịu lực. Các bài toán dùng receiving fixture tổng hợp và brief geometry đang có, chưa có tải, FEA, dung sai, supplier qualification hoặc thử robot thật. Có thể dùng reference ID của STEP đã nhập ở Workbench; giao diện receiving vẫn là fixture. Bộ sinh đề hiện chưa bảo đảm mọi reference nhập đều có phương án khả thi, nên cần kỹ sư xác nhận tính khả thi trước khi so sánh model.

## Làm một phiên với LLM bên ngoài

1. Chọn bài, reference, seed và nguồn thực hiện. Khai báo tên model/phiên bản hoặc kỹ sư; nguồn này do người nhập tự khai báo, không được xác thực bởi nhà cung cấp.
2. **Tạo phiên đánh giá**. Task/brief, seed, rules, baseline (chỉ bài chỉnh sửa), version kernel và fingerprint evaluator được giữ nguyên theo phiên.
3. **Bắt đầu / tiếp tục** timer, **Xuất context & feedback**. Dùng LLM ngoài để tạo chương trình `forge-feature-design-v1`, rồi nhập hoặc dán JSON trả về. Đừng ghi task hoặc requirements vào proposal.
4. **Gửi · dựng · kiểm độc lập**. Worker cố định nhận dữ liệu; không thực thi mã model. Mỗi lần gửi lưu raw text, checksum, kết quả và thời gian xử lý, kể cả JSON hỏng hoặc graph ngoài catalog. Worker được giới hạn 90 giây, dùng chung quyền chạy CAD với Workbench.
5. Xem hình thực, bản vẽ, kiểm chưa đạt và xuất feedback cho lượt sửa. Gửi tiếp trong cùng phiên. Chỉ **Chốt phiên** bằng một lượt đủ điều kiện, hoặc dừng mà không chọn phương án. Kết quả không sửa spec Q4 hoặc cho phép sản xuất.
6. **Đối chứng cùng đề** tạo một phiên mới với đúng case, seed, reference và nguồn đã chọn. Phép ghép chỉ dùng task hash giống hệt, phiên đã chốt đạt và evaluator hiện còn khớp. Phiên `software_fixture` bị loại khỏi ghép AI–kỹ sư.

Timer ghi **thời gian phiên gồm chờ, review và thao tác**. Có thể pause giữa các hoạt động; pause bị chặn khi worker đang chạy. Nó không đo thời gian lao động chủ động, token, chi phí hay thời gian AI riêng. Vì vậy tỷ số thời gian của hai phiên không phải tỷ lệ tiết kiệm lao động. Nguồn, pause và cách làm cần được kiểm soát trong một thử nghiệm đối chứng thực sự. Phép ghép hiện chọn cặp thành công gần nhất cho mỗi task hash, chưa là ước lượng thống kê toàn bộ lượt thất bại hoặc nhiều model.

## Tự kiểm hệ thống

**Tạo phiên tự kiểm phần mềm** tạo actor riêng, bật timer và nạp chương trình do phần mềm viết. Nó không gọi LLM và không giả lập thời gian kỹ sư. Dùng chức năng này để kiểm đường đi của sản phẩm hoặc làm quen thao tác, không để công bố năng lực AI.

Có thể cố tình bỏ rãnh hoặc sửa sai vị trí trong proposal. Một BREP đạt các gate chung vẫn phải bị từ chối khi không đáp ứng đề bài độc lập. Ở bài họ kích thước, giữ `width` trong JSON nhưng thay sketch width bằng hằng số không được tính là tham số hóa thành công.

## Chẩn đoán lỗi

- `invalid_json`: raw text không phải JSON hợp lệ, hoặc chứa hằng số không hữu hạn.
- `outside_catalog`: proposal dùng operation chưa hỗ trợ; không kết luận tự động rằng bài toán không thể giải bằng catalog.
- `input_schema`: sai hợp đồng chương trình, biểu thức, kiểu dữ liệu hoặc hash.
- `kernel_execution`: dựng hình thất bại. Cần xem feature/log để phân biệt hình học proposal sai với lỗi compiler; category này chưa quy trách nhiệm.
- `requirements_rejected`: dựng được CAD nhưng chưa đạt một hoặc nhiều kiểm chung, kiểm đề bài hoặc kiểm họ tham số.
- `infrastructure` / `interrupted`: lỗi worker hoặc server restart; lượt này không phải kết luận về năng lực model.

Source/version thay đổi làm phiên cũ không đủ điều kiện chốt hoặc ghép đối chứng hiện tại. Có thể xem và xuất bằng chứng cũ. Các kiểm thành công cũ được giữ là lịch sử, không âm thầm chấm lại bằng evaluator mới.

## Lưu trữ và tái kiểm

`benchmark-output/<trial>/` lưu task, session, chuỗi event có hash liên kết, raw proposals, outcomes, logs và snapshot source evaluator. Thư mục runtime bị loại khỏi Git. Giới hạn 100 phiên, 20 đề xuất/phiên; quản lý lưu trữ hiện vẫn cần làm ở filesystem sau khi lưu gói bằng chứng. Baseline của CAD Workbench vẫn là trạng thái riêng; Lab lưu phương án được chốt của từng phiên trên đĩa.

Digest/manifest phát hiện hỏng hoặc sửa file không nhất quán, **không phải chữ ký chống một người có quyền ghi lại toàn bộ dữ liệu local**. Đừng coi actor label hoặc hash là chứng thực LLM, người dùng hoặc thử nghiệm phần cứng.

ZIP bằng chứng gồm task, trial/outcomes, proposal text, source evaluator đã dùng, từng gói CAD có manifest và `verify.py`. Giải nén, cài dependencies như dự án rồi chạy:

```sh
python verify.py
```

Script kiểm manifest, dựng lại chương trình của lượt được chốt (hoặc CAD gần nhất nếu chưa chốt), so volume với STEP, tính lại kiểm geometry/task và họ kích thước. Nó ghi `verification.json`; exit code 1 nếu kiểm không đạt. Source trong gói là source tin cậy của sản phẩm; proposal vẫn là dữ liệu JSON.

`npm run test:benchmark` chạy oracle số độc lập, HTTP/worker thật, trường hợp lỗi, lưu phiên, hash/source thay đổi và tái chạy ZIP trong thư mục riêng. Report ở `reports/robotics/benchmark-tests.json`; kiểm giao diện ghi riêng trong `benchmark-browser.json`. Các lượt trong bộ kiểm là fixture phần mềm; `llm_quality_benchmarked=false`.

## Muốn công bố mức thay thế CAD

Cần bộ đề khả thi được kỹ sư duyệt, task giữ ngoài mẫu luyện/tự kiểm, các phiên LLM thật và kỹ sư thật có quy trình thời gian nhất quán, ghi cả lượt thất bại và can thiệp. Chấm công năng bằng yêu cầu độc lập; không ép mọi thiết kế hợp lệ giống một hình mẫu duy nhất. Sau đó mới thử chế tạo và công bố theo phạm vi công việc đã đo.
