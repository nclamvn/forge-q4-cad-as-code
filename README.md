# FORGE Q4 · CAD bằng code

PoC robot bốn chân với CAD thật, bàn bản vẽ A3 và trình diễn 3D đen trắng. Python/build123d dựng BREP, xuất STEP và phát sinh hồ sơ từ cùng một đặc tả. Three.js hiển thị mesh lấy từ chính các khối CAD đó.

[![Xem trailer 60 giây](docs/media/trailer-poster.jpg)](https://github.com/nclamvn/forge-q4-cad-as-code/releases/download/v0.1.0/FORGE-Q4-CAD-trailer-60s.mp4)

**[Tải demo và hồ sơ CAD](https://github.com/nclamvn/forge-q4-cad-as-code/releases/latest)** · **[Bài viết về phương pháp](docs/CAD-BANG-CODE.vi.md)** · **[Chi tiết kỹ thuật và kiểm chứng](docs/engineering-notes.md)**

## Xem ngay

Tải `FORGE-Q4.html` ở Releases rồi mở bằng Chrome/Edge hiện đại. Một file có sẵn 3D, 12 cấu phần, bản vẽ, BOM, bằng chứng và các file tải; không cần CDN hoặc API key. Bản HTML là snapshot để xem và tải hồ sơ. Muốn sửa tham số rồi dựng lại cần chạy Python kernel theo hướng dẫn bên dưới.

Trailer 60 giây có 40 cảnh, 1920×1080/60 fps, chuyển cảnh thẳng, nhạc tổng hợp riêng. [Video trong repo](docs/media/trailer.mp4) · [Thông số và SHA-256](docs/media/trailer.json).

## Chạy bản thiết kế tương tác

Cần Python **3.11–3.14**. Node.js chỉ cần khi đóng gói HTML, không cần để chạy demo. Server chỉ nghe trên `127.0.0.1`.

```sh
git clone https://github.com/nclamvn/forge-q4-cad-as-code.git
cd forge-q4-cad-as-code
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

Mở [studio](http://127.0.0.1:8767/), [bàn CAD](http://127.0.0.1:8767/?workspace=cad) hoặc [hồ sơ xuất của snapshot mặc định](http://127.0.0.1:8767/deliverables.html). macOS có thể chạy `zsh Start.command`. Trên Windows dùng `.venv\Scripts\python` thay cho `.venv/bin/python`.

WebGPU khi khả dụng, dự phòng WebGL2. Thêm `?backend=webgl` để thử WebGL2 hoặc `?workspace=cad&backend=webgl` để mở bàn CAD với backend này. Có thể xoay, tách cụm, xuyên thấu, clipping 3D và chuyển động minh họa. Phím D/X/S/E/Space tương ứng kích thước/xuyên thấu/mặt cắt/tách cụm/chuyển động.

## Thử một thao tác CAD thực sự

1. Mở bàn CAD, chọn **Q4-201 Tay chân trên**. Spec mặc định có hai tâm cách 110 mm, rộng 32 mm, dày 7 mm và lỗ Ø10 mm.
2. Bấm **Thử lỗ Ø14 / dày 5** rồi **Dựng lại CAD và bản vẽ**. Lần đầu cần dựng hình và hồ sơ; thời gian phụ thuộc máy. UI giữ thiết kế hợp lệ trước đó trong lúc chờ.
3. So trước/sau. Khối lượng một tay trên từ **78,8 g → 54,2 g**, thể tích giảm **31,2%**, theo mật độ nhôm giả định 2700 kg/m³. STEP, mặt cắt, hình chiếu, BOM và PDF cập nhật theo revision mới.
4. Thử **vành quá mỏng**. Spec bị từ chối với HTTP 422; thiết kế hợp lệ được giữ lại. Các nút xuất bị khóa khi thông số chưa đồng bộ với hình học.
5. Tải STEP/DXF/PDF mới để kiểm ngoài demo. STEP được kiểm đọc lại bằng Open Cascade; chưa thực hiện phép kiểm import độc lập trong Fusion hoặc Onshape.

## Dữ liệu có trong demo

| Đầu ra | Phạm vi |
| --- | --- |
| CAD 3D | 12 hình học BREP, mỗi hình một solid hợp lệ |
| Lắp ráp | 42 instance có tên riêng và transform |
| STEP | 12 file chi tiết và một assembly 42 solid |
| Bản vẽ | 14 tờ A3 gồm 12 chi tiết, tổng thể và phân rã |
| DXF | 48 hình chiếu, 4 view/chi tiết, đơn vị mm, nét thấy/nét khuất |
| PDF/SVG | Mặt cắt BREP, kích thước, tỷ lệ, số lượng, revision và ghi chú |
| BOM/proof | Volume, khối lượng và cơ sở tính, CoM, các gate kiểm chứng |

DXF xuất cạnh chiếu từ BREP. SVG/PDF lấy mẫu đường cong để hiển thị; STEP giữ BREP gốc. Clipping trong studio là hiệu ứng hiển thị, còn mặt cắt trên bản vẽ lấy từ phép cắt hình học thật.

## Phương pháp và giới hạn

```text
YAML / tham số UI → validation → Python / build123d / Open Cascade
                                  ├─ BREP → STEP → đọc lại, đếm solid, so volume
                                  ├─ HLR + section → DXF / SVG / PDF / BOM
                                  └─ tessellation → Three.js → WebGPU / WebGL2
```

Đặc tả và fingerprint compiler xác định revision hình học. Generator bản vẽ có fingerprint riêng. Các file của một lần dựng đi cùng revision; bản mẫu được giữ trong repo để clone xong có thể mở ngay. Những revision thử nghiệm được sinh vào `artifacts/` và không đưa vào Git.

AI hỗ trợ viết mã trong quá trình phát triển. **Demo không gọi LLM lúc chạy**. Ô nhập ý đồ dùng parser cục bộ với phạm vi tham số định trước. PoC cho thấy khả năng tự động hóa họ chi tiết có quy luật và phát sinh hồ sơ; chưa có sketch tự do, constraint solver tương tác, chỉnh mặt tùy ý hoặc feature history native khi import STEP.

Đây là hồ sơ concept của một thiết kế PoC độc lập. Actuator, pin và camera dùng hình học đại diện; một số khối lượng được gán. Chưa có GD&T, dung sai lắp, CAM, FEA, thiết kế điện, kiểm va chạm toàn bộ, điều khiển động lực học hoặc thử robot thật. Quy tắc vành 6 mm và khoảng hở tay chân 3 mm tại 5 góc mẫu không chứng minh độ bền hay khả năng chế tạo.

## Kiểm chứng và đóng gói

```sh
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python tests/kernel_test.py
.venv/bin/python tests/dossier_test.py
# Chạy khi server đang mở. Có thể chọn cổng với FORGE_TEST_URL.
.venv/bin/python tests/api_test.py
```

Bộ kiểm dùng công thức thể tích capsule độc lập, 7 loại spec lỗi, 4 biến thể thiết kế, STEP round-trip, 42 nhãn lắp ráp, 48 DXF/mm, diện tích mặt cắt và 14 trang A3. Report JSON ở `reports/`; kiểm trình duyệt trước khi phát hành ghi riêng trong `reports/monochrome/dossier-browser.json`.

Đóng gói HTML và ZIP có manifest SHA-256 (Node.js 18+). Hãy chạy các phép kiểm trên trước khi tạo release.

```sh
npm ci
npm run package
.venv/bin/python tools/release.py
```

`tools/release.py` dùng danh sách thư mục công khai cho phép. Môi trường Python, cache phụ, bản ghi màn hình thô, video biên tập, archive và thông tin Git không vào gói chia sẻ.

## Cấu trúc

| Đường dẫn | Vai trò |
| --- | --- |
| `kernel.py`, `spec.yaml` | Hình học và đặc tả tham số |
| `technical.py` | Hình chiếu, mặt cắt, DXF và hồ sơ A3 |
| `server.py`, `launch.py`, `Start.command` | API và khởi chạy cục bộ |
| `web/` | Studio, bàn CAD, snapshot model và Three.js vendored |
| `artifacts/0cbe5809f2e8/` | Bộ CAD mẫu có thể kiểm chứng |
| `tests/`, `reports/` | Phép kiểm và kết quả |
| `docs/` | Bài viết, kỹ thuật và media đã chọn |
| `tools/` | Đóng gói bản phát hành |

Three.js 0.186.1 được giữ kèm [MIT license của thư viện](web/vendor/THREE-LICENSE.txt). Các dependency Python được cài từ PyPI theo requirements.

Tài liệu nền tảng chính thức [build123d](https://build123d.readthedocs.io/en/latest/), [import/export và phép chiếu CAD](https://build123d.readthedocs.io/en/latest/import_export.html), [Three.js WebGPURenderer](https://threejs.org/docs/pages/WebGPURenderer.html).
