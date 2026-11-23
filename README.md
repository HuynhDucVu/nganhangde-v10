# Nganhangde_vu (v6.6.0) — Hướng dẫn từ A đến Z

Phần mềm quản lý ngân hàng câu hỏi Toán THPT, trộn đề theo cấu trúc GDPT 2018 (CV 7991 / CV 1239), chuyển đổi Word/PDF/Ảnh ↔ LaTeX (`ex_test`), vẽ hình TikZ/Đồ thị/BBT&XD, tích hợp sẵn tab **HDSD** và **Tự động cập nhật**.

---

## PHẦN A. Cài đặt môi trường Python (chỉ làm 1 lần trên máy phát triển)

> **Khuyến nghị quan trọng:** Dùng **Python 3.12 (64-bit)** để tương thích ổn định nhất với PyInstaller và PySide6 (tránh dùng Python 3.15 vì PyInstaller chưa hỗ trợ đầy đủ DLL).

1. Tải **Python 3.12.x (Windows installer 64-bit)** tại: `https://www.python.org/downloads/release/python-31210/`
2. Khi chạy bộ cài đặt, **bắt buộc tích chọn ô `Add python.exe to PATH`** ở góc dưới rồi bấm **Install Now**.
3. Kiểm tra cài đặt thành công: mở **Command Prompt (CMD)** và gõ:
   ```cmd
   py -3.12 --version
   ```
   Nếu hiện `Python 3.12.x` là đạt.

---

## PHẦN B. Giải nén và chạy trực tiếp từ Python (kiểm tra trước khi xuất bản)

1. Giải nén tệp `Nganhangde_vu_v6.6.zip` vào một thư mục **không dấu tiếng Việt, không khoảng trắng** (ví dụ: `D:\App-NganHangde\Nganhangde_vu_v6.6`).
2. **Cách 1 (Nhanh nhất — 1 cú nháy đúp):**
   * Nháy đúp tệp **`chay_ung_dung.bat`**.
   * Script tự cài các thư viện trong `requirements.txt` và mở giao diện **Nganhangde_vu v6.6.0**.
3. **Cách 2 (Chạy thủ công bằng CMD từng bước):**
   Mở CMD tại thư mục vừa giải nén và gõ lần lượt:
   ```cmd
   py -3.12 -m pip install -r requirements.txt
   py -3.12 run_gui.py
   ```
4. **Kiểm tra nhanh trước khi đóng gói:**
   * Mở tab **Trộn đề** → thử nạp câu hỏi, kiểm tra 5 sub-tab.
   * Mở tab **Tiện ích → Tiện ích 1** → bấm **Tuỳ chọn** nhập Gemini API Key → thử chuyển 1 tệp `.docx` hoặc `.pdf` sang LaTeX.
   * Bấm phím **`F1`** kiểm tra cửa sổ **HDSD**.

---

## PHẦN C. Đóng gói ra tệp `.exe` để gửi cho đồng nghiệp

1. Đóng toàn bộ cửa sổ phần mềm đang mở.
2. Nháy đúp tệp **`build_exe.bat`** trong thư mục mã nguồn và chờ khoảng 1–3 phút.
3. Script tự động thực hiện đủ 4 bước:
   * `[1/4]` Cài đủ thư viện (`PySide6`, `pypdf`, `pymupdf`, `python-docx`, `openpyxl`, `pywin32`, `PyInstaller`...).
   * `[2/4]` Chạy 5 bộ kiểm thử tự động (`pytest`).
   * `[3/4]` Đóng gói thành thư mục chạy độc lập **`dist\Nganhangde_vu\Nganhangde_vu.exe`** (kèm tự bổ sung `python3*.dll` nếu thiếu).
   * `[4/4]` Tự động nén toàn bộ bản phân phối thành 1 tệp duy nhất:
     **`Nganhangde_vu_v6.6_BanTinhPhi.zip`**

### Cách gửi cho đồng nghiệp
* Gửi tệp **`Nganhangde_vu_v6.6_BanTinhPhi.zip`** qua Zalo, Google Drive hoặc USB.
* **Lưu ý quan trọng:** KHÔNG gửi lẻ duy nhất tệp `Nganhangde_vu.exe` vì ứng dụng cần đi kèm thư mục `_internal` nằm cùng cấp (tệp `.zip` ở trên đã gom đủ tất cả).

---

## PHẦN D. Xuất bản lên GitHub & Kích hoạt Tự động cập nhật (Auto-Update)

Khi bạn muốn phát hành bản mới để tất cả đồng nghiệp đang cài **`Nganhangde_vu.exe`** tự động nhận thông báo cập nhật 1 chạm:

1. Cài Git cho Windows (nếu chưa có): `https://git-scm.com/download/win`.
2. Đảm bảo trong `nganhangde\core\updater.py` đã tăng `APP_VERSION` (ví dụ `6.6.0` → `6.6.0`).
3. Nháy đúp tệp **`day_len_github.bat`**:
   * Nhập link kho GitHub (mặc định: `https://github.com/HuynhDucVu/nganhangde-v10.git`).
   * Nhập mã phiên bản phát hành bắt đầu bằng chữ `v` (ví dụ: **`v6.6.0`**).
4. Chờ khoảng 3–5 phút: **GitHub Actions** (`.github/workflows/build-exe.yml`) sẽ tự động chạy trên máy chủ Windows Python 3.12, tạo tệp **`Nganhangde_vu-Windows.zip`** và đăng lên mục **Releases**.
5. Từ lúc đó, đồng nghiệp mở `Nganhangde_vu.exe` (hoặc vào tab **Thông tin → Kiểm tra cập nhật ngay**) sẽ tự tải và nâng cấp lên bản mới mà không cần bạn gửi lại file thủ công.

---

## PHẦN E. Hướng dẫn gửi kèm cho đồng nghiệp khi nhận phần mềm

1. **Giải nén:** Tải tệp `Nganhangde_vu_v6.6_BanTinhPhi.zip` và giải nén vào thư mục không dấu (ví dụ: `D:\Nganhangde_vu`). **Không chạy trực tiếp bên trong cửa sổ ZIP.**
2. **Mở phần mềm:** Nháy đúp **`Nganhangde_vu.exe`**.
   * Nếu Windows hiện màn hình xanh *Windows protected your PC*: bấm **`More info`** → **`Run anyway`** (chỉ cần làm 1 lần đầu).
   * Có thể nháy chuột phải vào `Nganhangde_vu.exe` → *Send to → Desktop (create shortcut)* để tạo biểu tượng ngoài màn hình chính.
3. **Cấu hình TeXstudio (TeX Live 2019) để bấm F5 ra PDF:**
   * Mở TeXstudio → *Tùy chọn → Cấu hình TeXstudio → Lệnh* → dòng `PdfLaTeX` trỏ tới:
     `C:\texlive\2019\bin\win32\pdflatex.exe -synctex=1 -interaction=nonstopmode %.tex`
4. **Cấu hình chuyển Word/PDF/Ảnh sang LaTeX chuẩn 100%:**
   * Lấy Gemini API Key miễn phí tại `https://aistudio.google.com/apikey`.
   * Trong phần mềm, vào **Tiện ích → Tiện ích 1 → Tuỳ chọn** (khung *Word/PDF sang TeX*) → chọn **`Dùng Gemini`** → dán API Key → bấm **`Lưu`** → **`Lưu & Đóng`**.
5. **Xem hướng dẫn chi tiết từng chức năng:** Nhấn phím **`F1`** hoặc mở tab **`HDSD`**, hoặc bấm nút **`HDSD chi tiết`** ở cuối mỗi tab.

---

## PHẦN F. Xử lý nhanh các lỗi thường gặp

| Hiện tượng | Nguyên nhân & Cách khắc phục |
|---|---|
| `Failed to load Python DLL ... python315.dll` | Máy đóng gói dùng Python 3.15 quá mới. Cài **Python 3.12 64-bit** rồi chạy lại `build_exe.bat` (script mới sẽ tự ưu tiên `py -3.12` và tự chép DLL). |
| Windows Defender xoá/chặn `Nganhangde_vu.exe` | Vào *Windows Security → Virus & threat protection → Exclusions* và thêm thư mục `D:\Nganhangde_vu`. |
| TeXstudio báo `Không thể khởi chạy PdfLaTeX` | Kiểm tra tên tệp `.tex` không dấu tiếng Việt và đường dẫn `pdflatex.exe` trong cấu hình TeXstudio. |
| Chuyển Word bằng MathType bị mất công thức | Chuyển sang chế độ **`Dùng Gemini`** trong *Tuỳ chọn*, hoặc mở tệp bằng Word chạy *MathType → Convert Equations (LaTeX 2.09)* rồi lưu lại trước khi đưa vào phần mềm. |

---

## PHẦN G. Quản lý Bản tính phí (Mã máy, Key kích hoạt & Mật khẩu)

1. **Khoá bí mật bản quyền KHÔNG nằm trong mã nguồn:**
   * Mã nguồn chỉ giữ placeholder `_LICENSE_SECRET = "__NGANHANGDE_LICENSE_SECRET__"` trong `nganhangde\core\licensing.py`.
   * Trên GitHub: vào **Settings → Secrets and variables → Actions → New repository secret**, tên `NGANHANGDE_LICENSE_SECRET`, giá trị là khoá bí mật của bạn. Workflow sẽ tự nhúng khoá khi build bản phát hành.
   * Trên máy build/cấp key (Windows): đặt biến môi trường trước khi chạy `build_exe_ban_tinh_phi.bat` hoặc công cụ cấp Key (lưu riêng ngoài repo), ví dụ `set NGANHANGDE_LICENSE_SECRET=gia_tri_khoa_cua_ban`.
   * Lưu ý: giữ đúng giá trị khoá cũ thì các Key đã cấp cho khách vẫn dùng được. Đổi khoá sẽ làm mất hiệu lực toàn bộ Key đã cấp.
2. **Quy trình bán / cấp bản quyền cho khách hàng:**
   * Gửi tệp **`Nganhangde_vu_v6.6_BanTinhPhi.zip`** (chỉ gồm `Nganhangde_vu.exe`, `_internal`, và `HUONG_DAN_SU_DUNG.txt` — tuyệt đối KHÔNG gửi `admin_keygen_gui.py`).
   * Khách hàng mở `Nganhangde_vu.exe` → bấm **`Sao chép Mã máy`** (dạng `NHV-XXXX-XXXX-XXXX`) gửi cho bạn.
   * Trên máy bạn, mở công cụ cấp Key (lưu riêng, không có trong repo) → dán Mã máy của khách → chọn gói (`Vĩnh viễn` / `1 năm` / `6 tháng` / `1 tháng` / `7 ngày`) → bấm **`Tạo Mã kích hoạt`**.
   * Gửi Key đó cho khách dán vào cửa sổ kích hoạt. Mọi Key đã cấp tự động lưu lịch sử vào `danh_sach_khach_hang_key.csv`.
3. **Cài mật khẩu mở phần mềm:**
   * Người dùng có thể vào tab **`Thông tin`** → bấm **`Cài / Đổi mật khẩu mở app`** để đặt mật khẩu cá nhân mỗi khi khởi động.
