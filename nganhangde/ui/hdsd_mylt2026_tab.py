"""Hướng dẫn sử dụng (HDSD) tổng hợp (giữ nguyên bố cục cây mục lục v5.8) + Thanh HDSD riêng cho từng tab chức năng."""
from __future__ import annotations
from typing import Callable
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

_CSS = """
<style>
  body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10.5pt; color: #1f2937; line-height: 1.55; margin: 10px 14px; }
  h2 { color: #15803d; border-bottom: 2px solid #86efac; padding-bottom: 5px; margin-top: 2px; font-size: 13.5pt; }
  h3 { color: #1e40af; margin: 12px 0 4px 0; font-size: 11pt; }
  ol, ul { margin: 4px 0 10px 0; padding-left: 22px; }
  li { margin-bottom: 4px; }
  .btn { background: #eff6ff; border: 1px solid #93c5fd; color: #1d4ed8; padding: 1px 6px; border-radius: 3px; font-weight: 600; font-size: 9.5pt; }
  .tip { background: #f0fdf4; border-left: 4px solid #16a34a; padding: 8px 10px; margin: 10px 0; border-radius: 3px; }
  .warn { background: #fffbeb; border-left: 4px solid #d97706; padding: 8px 10px; margin: 10px 0; border-radius: 3px; }
  code { background: #f3f4f6; padding: 1px 5px; border-radius: 3px; font-family: Consolas, monospace; font-size: 9.5pt; }
</style>
"""

# Từ điển HDSD chi tiết cho TỪNG tab & sub-tab:
# key -> (Tiêu đề cửa sổ HDSD, Gợi ý nhanh 1 dòng, Nội dung HTML chi tiết)
FEATURE_GUIDES: dict[str, tuple[str, str, str]] = {
    "tron_id": (
        "Trộn đề — Tạo đề theo ID",
        "Lọc theo Lớp/Môn/Chương/Bài → chọn số câu ở 4 cột N/H/V/C (hoặc dùng Chọn nhanh → Lấy) → bấm Tạo đề.",
        """
        <h2>Tạo đề theo ID (Rút câu hỏi tự động từ kho)</h2>
        <ol>
          <li><b>Chọn nguồn:</b> Chọn <span class="btn">Từ ngân hàng câu hỏi</span> hoặc <span class="btn">Từ Files</span> → <span class="btn">Chọn files nguồn...</span>.</li>
          <li><b>Chọn trực tiếp trên bảng:</b> Dùng thanh lọc (<code>Lớp</code>, <code>Môn</code>, <code>Chương</code>, <code>Bài</code>, <code>Loại</code>) → bấm <span class="btn">Lọc</span>. Tại mỗi dòng mã ID, bấm ô xổ ở 4 cột <b>Nhận biết / Thông hiểu / Vận dụng / Vận dụng cao</b> để chọn số câu cần lấy.</li>
          <li><b>Chọn nhanh:</b> Chọn tiêu chí ở khung <i>Chọn nhanh</i> + <i>Số câu</i> → bấm <span class="btn">Lấy</span>.</li>
          <li><b>Thanh nút tắt dưới bảng:</b> <code>H</code> (chọn hết), <code>A</code> (mỗi dòng 1 câu), <code>C</code> (xoá chọn), <code>E</code> (xuất CSV), <code>D</code> (xoá dòng đang chọn), <code>O</code> (tra cứu ID6), <code>U</code> (tải lại bảng).</li>
          <li>Chuyển sang tab <span class="btn">Tuỳ chọn đề</span> chỉnh số đề/mã đề rồi bấm <span class="btn">Tạo đề</span> ở góc dưới phải.</li>
        </ol>
        """,
    ),
    "tron_tuchon": (
        "Trộn đề — Tạo đề tự chọn",
        "Lọc câu hỏi → tích chọn từng câu ở cột Chọn (hoặc Chọn hết) → bấm Tạo đề.",
        """
        <h2>Tạo đề tự chọn (Tích chọn từng câu cụ thể)</h2>
        <ol>
          <li>Chọn bộ lọc (<code>Lớp</code>, <code>Môn</code>, <code>Chương</code>, <code>Bài</code>, <code>Dạng</code>, <code>Mức độ</code>, <code>Loại</code>) rồi bấm <span class="btn">Lọc</span>.</li>
          <li>Tích vào cột <b>Chọn</b> ở các câu muốn đưa vào đề (hoặc bấm <span class="btn">Chọn hết</span> / <span class="btn">Xoá chọn</span>).</li>
          <li>Muốn sửa nhanh nội dung câu nào, chọn dòng đó rồi bấm <span class="btn">Sửa câu hỏi</span>.</li>
          <li>Kiểm tra số câu tại dòng <i>Đã chọn: X câu</i> rồi bấm <span class="btn">Tạo đề</span>.</li>
        </ol>
        """,
    ),
    "tron_file": (
        "Trộn đề — Tạo đề theo file",
        "Bấm Thêm file .tex → chỉnh số câu cần rút ở cột Lấy → bấm Tạo đề.",
        """
        <h2>Tạo đề theo file (Trộn trực tiếp từ tệp .tex)</h2>
        <ol>
          <li>Bấm <span class="btn">Thêm file .tex</span> (hoặc <span class="btn">Chọn files nguồn...</span>) để nạp 1 hoặc nhiều tệp đề nguồn chuẩn <code>ex_test</code>.</li>
          <li>Tại cột <b>Lấy</b> của từng tệp, chọn số câu muốn rút ngẫu nhiên (mặc định lấy toàn bộ câu hiện có).</li>
          <li>Bấm <span class="btn">Tạo đề</span> và chọn thư mục lưu bộ đề đã trộn.</li>
        </ol>
        """,
    ),
    "tron_tuongtu": (
        "Trộn đề — Tạo đề tương tự",
        "Chọn File đề gốc (.tex) → chọn Tìm theo & Tỉ lệ tương tự → bấm Tìm → bấm Lưu hoặc Tạo đề.",
        """
        <h2>Tạo đề tương tự theo cấu trúc đề gốc</h2>
        <ol>
          <li>Tại dòng <b>File đề gốc</b>, bấm <span class="btn">Chọn</span> và mở tệp đề mẫu <code>.tex</code>.</li>
          <li>Chọn <b>Tìm theo</b> (<code>ID</code> / <code>Nội dung</code> / <code>ID + Nội dung</code>), <b>Tỉ lệ tương tự</b> (65%) và <b>Số đề tối đa</b> → bấm <span class="btn">Tìm</span>.</li>
          <li>Đối chiếu 2 cột <i>Câu hỏi đề gốc</i> và <i>Câu hỏi đề tương tự</i>; bấm <span class="btn">Đổi</span> để thay câu khác hoặc <span class="btn">Sửa</span> trực tiếp.</li>
          <li>Bấm <span class="btn">Lưu</span> để xuất đề hiện tại, hoặc bấm <span class="btn">Tạo đề</span> để trộn nhiều mã đề.</li>
        </ol>
        """,
    ),
    "tron_tuychon": (
        "Trộn đề — Tuỳ chọn đề",
        "Chọn Số đề, Mã đề, Sắp xếp câu hỏi, Phiếu TLTN 2025, Biên dịch đề & Tiêu đề → bấm Tạo đề.",
        """
        <h2>Tuỳ chọn đề (Số đề · Mã đề · Phiếu 2025 · Biên dịch PDF)</h2>
        <ul>
          <li><b>Số đề &amp; Mã đề:</b> Chọn số mã đề; tích <b>Mã đề 3 số</b> (101, 102...) hoặc bỏ tích cho 4 số (1001, 1002...); hỗ trợ <b>Mã đề cách</b> và <b>Mã đề tự nhập</b> (VD: <code>101, 103, 105</code>).</li>
          <li><b>Sắp xếp câu hỏi:</b> Chọn thứ tự ưu tiên (<i>Theo lớp, môn, chương, mức độ, bài, dạng</i>). Tích <b>Giữ nguyên đề</b> nếu muốn xuất nguyên bản không đảo thứ tự câu.</li>
          <li><b>Phiếu làm bài &amp; Đáp án:</b> Chọn <i>Phiếu TLTN 2025</i> để chèn phiếu tô vào đề; hệ thống tự xuất kèm <b>OMR Excel</b>, <b>CSV BOM</b> và <b>Ma trận &amp; Đặc tả CV 7991</b>.</li>
          <li><b>Biên dịch đề:</b> Tích để tự chạy <code>pdflatex</code> ra PDF ngay sau khi xuất.</li>
        </ul>
        <div class="tip"><b>Mẹo:</b> Phần mềm tự nhớ tab chọn câu hỏi trước khi bạn sang <i>Tuỳ chọn đề</i>, chỉ cần chỉnh xong rồi bấm <span class="btn">Tạo đề</span>.</div>
        """,
    ),
    "cauhoi_mylt": (
        "Quản lý câu hỏi (MyLT 2026)",
        "Chọn nguồn (Ngân hàng / Files) → lọc theo ID/từ khoá → xem, sửa, gắn ID hoặc xuất bộ câu hỏi.",
        """
        <h2>Quản lý câu hỏi chuẩn MyLT 2026</h2>
        <ol>
          <li><b>Nhập đề vào kho:</b> Bấm <span class="btn">Nhập câu hỏi</span> → chọn 1 hoặc nhiều tệp <code>.tex</code> → chạy <b>Rà soát</b> → bấm <b>Nhập vào ngân hàng</b>.</li>
          <li><b>Lọc &amp; duyệt câu hỏi:</b> Lọc nhanh theo Lớp, Môn, Chương, Bài, Dạng, Mức độ hoặc từ khoá.</li>
          <li><b>Chỉnh sửa &amp; kiểm tra PDF:</b> Chọn câu hỏi để sửa mã LaTeX, trỏ tệp <code>Main .tex</code> và xem trước bản PDF trực tiếp.</li>
        </ol>
        """,
    ),
    "cauhoi_fts5": (
        "Kho nâng cao (Cây thư mục · FTS5 · F11)",
        "Gõ từ khoá/ID6 tìm siêu tốc FTS5 → dùng Rà soát CV 1239, Tìm gần trùng hoặc Trình chiếu (F11).",
        """
        <h2>Kho câu hỏi nâng cao (Cây thư mục · FTS5 · Trình chiếu F11)</h2>
        <ol>
          <li><b>Tìm kiếm FTS5:</b> Gõ từ khoá bất kỳ hoặc mã ID6 (VD: <code>1D2H</code>) để lọc tức thì trong toàn kho.</li>
          <li><b>Quản lý cây thư mục:</b> Phân loại câu hỏi theo Năm học / Khối lớp / Đợt kiểm tra ở cột bên trái.</li>
          <li><b>Công cụ kiểm định &amp; giảng dạy:</b> Dùng <b>Rà soát</b> (kiểm tra chuẩn <code>ex_test</code>), <b>Tìm gần trùng</b> (loại câu lặp) và <b>Trình chiếu (F11)</b> để dạy học trực tiếp trên lớp.</li>
        </ol>
        """,
    ),
    "ma_tran": (
        "Ma trận đề thi (CV 7991)",
        "Nạp ma trận Excel (.xlsx) hoặc rút ma trận từ đề .tex → xuất Ma trận & Đặc tả CV 7991 → bấm Tạo đề.",
        """
        <h2>Ma trận &amp; Bản đặc tả chuẩn Công văn 7991</h2>
        <ol>
          <li>Bấm <b>Nạp ma trận Excel (.xlsx)</b> để đọc khung ma trận có sẵn, hoặc bấm <b>Rút ma trận ngược</b> từ tệp đề <code>.tex</code>.</li>
          <li>Bấm <b>Xuất Ma trận &amp; Đặc tả CV 7991</b> để sinh tự động bộ tệp <code>.xlsx</code> và <code>.docx</code> đúng mẫu quy định.</li>
          <li>Sau khi nạp ma trận, bấm <span class="btn">Tạo đề</span> ở góc dưới phải để rút câu hỏi đúng theo cơ cấu ma trận.</li>
        </ol>
        """,
    ),
    "tienich_1": (
        "Tiện ích 1 (Word/PDF ↔ TeX · Lọc · Phiếu 2025 · Trùng · Hoá ảnh)",
        "Chọn tệp trong từng khung chức năng → bấm Tuỳ chọn (nếu cần) → bấm Chuyển / Lọc / Tạo / Tìm.",
        """
        <h2>Tiện ích 1 — Bộ công cụ xử lý đề đa năng</h2>
        <ul>
          <li><b>Chuyển Word/PDF sang TeX:</b> Chọn tệp <code>.docx</code>, <code>.pdf</code> hoặc ảnh → bấm <span class="btn">Chuyển</span>. Bấm <span class="btn">Tuỳ chọn</span> để nhập Gemini API Key (chuyển MathType &amp; PDF chuẩn 100%) hoặc chọn chế độ MathType Word. Với PDF dài, bấm <span class="btn">Chuyển PDF/ảnh thủ công</span> để chọn khoảng trang.</li>
          <li><b>Chuyển TeX sang Word:</b> Chọn tệp <code>.tex</code> → bấm <span class="btn">Chuyển</span> để xuất ra <code>.docx</code> giữ công thức Toán OMML.</li>
          <li><b>Lọc câu hỏi / Lọc hình TikZ / Tìm câu trùng:</b> Chọn nguồn (Từ ngân hàng / Từ Files), nhập từ khoá hoặc tỉ lệ trùng → bấm <span class="btn">Lọc</span> / <span class="btn">Tìm</span>.</li>
          <li><b>Tô phiếu TLTN 2025 &amp; Đề Online:</b> Chọn tệp <code>.tex</code> → xuất phiếu tô 2025 hoặc đề Moodle / Aiken / Quizizz / Microsoft Forms.</li>
          <li><b>Hoá ảnh đề TeX &amp; Đổi cấu trúc gói đề:</b> Xuất hình TikZ sang PNG 300 DPI (<code>Tikz2Img</code>) hoặc đổi <code>ex_test cũ</code> / <code>dethi</code> sang <code>ex_test mới</code>.</li>
        </ul>
        """,
    ),
    "tienich_2": (
        "Tiện ích 2 (Xử lý & Chuẩn hoá mã nguồn LaTeX)",
        "Chọn tệp .tex nguồn → chọn tác vụ chuẩn hoá/xử lý hàng loạt → bấm thực thi.",
        """
        <h2>Tiện ích 2 — Công cụ xử lý tệp LaTeX nâng cao</h2>
        <ol>
          <li>Chọn tệp <code>.tex</code> hoặc thư mục chứa đề cần xử lý.</li>
          <li>Chọn các tuỳ chọn làm sạch, chuẩn hoá ký hiệu (<code>\\dfrac</code>, <code>\\overrightarrow</code>, <code>\\lim\\limits</code>, tách/gộp file, sửa lỗi ngoặc...).</li>
          <li>Bấm nút thực thi để xuất tệp kết quả đã chuẩn hoá.</li>
        </ol>
        """,
    ),
    "tienich_word_ocr": (
        "Word ↔ LaTeX & AI OCR PDF",
        "Chọn tệp PDF/Ảnh → bấm Chuyển PDF → LaTeX → kiểm tra mã rồi bấm Lưu .tex & Mở TeXstudio.",
        """
        <h2>Word ↔ LaTeX &amp; AI OCR PDF</h2>
        <ol>
          <li><b>Chuyển PDF/Ảnh trực tiếp:</b> Bấm <span class="btn">Chọn PDF/Ảnh...</span> → bấm <span class="btn">Chuyển PDF → LaTeX</span> → xem kết quả ở khung dưới → bấm <span class="btn">Lưu .tex &amp; Mở TeXstudio</span>.</li>
          <li><b>Chuyển theo khoảng trang:</b> Bấm <span class="btn">Mở hộp thoại PDF/Ảnh (chọn trang)</span> để chọn <i>Từ trang → Đến trang</i> và động cơ (Gemini AI / Mathpix API / PyMuPDF).</li>
          <li><b>Nhập/Xuất Word với kho:</b> Dùng nút <span class="btn">Nhập Word (.docx) → Kho</span> hoặc <span class="btn">Xuất câu đang lọc → Word (.docx)</span>.</li>
        </ol>
        <div class="tip"><b>Lưu ý:</b> Nhập Gemini API Key tại <i>Tiện ích 1 → Tuỳ chọn</i> để nhận dạng chính xác 100% công thức Toán từ PDF scan/ảnh.</div>
        """,
    ),
    "tienich_online": (
        "Moodle · Online GAS · Đấu trường LAN",
        "Xuất đề Moodle XML / Thi Online Google Apps Script hoặc bấm Khởi chạy Đấu trường LAN để thi qua Wi-Fi.",
        """
        <h2>Thi trực tuyến &amp; Đấu trường mạng nội bộ (LAN)</h2>
        <ul>
          <li><b>Xuất Moodle XML:</b> Xuất bộ câu hỏi đang lọc sang định dạng Moodle (hỗ trợ MathJax + Cloze).</li>
          <li><b>Xuất Thi Online GAS (Code.gs):</b> Tạo mã nguồn Google Apps Script để triển khai phòng thi trực tuyến miễn phí trên Google.</li>
          <li><b>Khởi chạy Đấu trường LAN:</b> Mở máy chủ thi trực tiếp qua Wi-Fi phòng học (học sinh truy cập địa chỉ IP nội bộ trên điện thoại/máy tính, không cần Internet).</li>
          <li><b>Xem trước PDF:</b> Kiểm tra bố cục trang PDF trực quan trước khi in ấn.</li>
        </ul>
        """,
    ),
    "tienich_chuyende": (
        "Biên soạn Chuyên đề (.tex / PDF)",
        "Chọn chương/dạng bài trong kho → cấu hình bố cục tài liệu → xuất tệp chuyên đề .tex / PDF.",
        """
        <h2>Biên soạn tài liệu Chuyên đề dạy học</h2>
        <ol>
          <li>Chọn khối lớp, chuyên đề hoặc các mã ID6 cần gom thành tài liệu.</li>
          <li>Tuỳ chỉnh phân mục (Lý thuyết, Ví dụ minh hoạ, Bài tập tự luyện, Lời giải chi tiết).</li>
          <li>Bấm xuất để tạo tệp <code>.tex</code> (kèm khung chuẩn TeX Live 2019) và biên dịch ra PDF.</li>
        </ol>
        """,
    ),
    "tienich_ai": (
        "Trạm AI (Gán ID · Sinh câu · Chấm tự luận)",
        "Chọn câu hỏi hoặc nhập đề bài → chọn chức năng Gán ID6 / Sinh câu tương tự / Chấm tự luận.",
        """
        <h2>Trạm AI hỗ trợ giáo viên</h2>
        <ul>
          <li><b>Gán mã ID6 tự động:</b> AI phân tích nội dung câu hỏi và đề xuất mã ID6 chuẩn GDPT 2018.</li>
          <li><b>Sinh câu hỏi tương tự:</b> Tạo biến thể đổi số/đổi hàm cùng dạng toán và mức độ nhận thức.</li>
          <li><b>Chấm gợi ý tự luận:</b> Đối chiếu bài làm học sinh với đáp án chuẩn, chỉ ra bước sai và gợi ý thang điểm.</li>
        </ul>
        <div class="warn"><b>Yêu cầu:</b> Nhập API Key (Gemini / OpenAI / Claude...) tại tab <i>Thông tin</i> hoặc <i>Tiện ích 1 → Tuỳ chọn</i>.</div>
        """,
    ),
    "tienich_beamer": (
        "Trình chiếu đề bằng Main Beamer",
        "Chọn nguồn đề (.tex / đề vừa trộn / kho) → chọn Theme, tỉ lệ 16:9, kiểu \\pause → bấm Biên dịch PDF & Trình chiếu ngay.",
        """
        <h2>Trình chiếu đề Toán bằng Main Beamer (TeX Live 2019)</h2>
        <ol>
          <li><b>Chọn nguồn đề:</b> Chọn <i>Từ tệp đề .tex</i> (chuẩn <code>ex_test</code>), <i>Từ đề vừa trộn</i> hoặc <i>Từ câu hỏi đang lọc</i>.</li>
          <li><b>Cấu hình trình chiếu:</b> Nhập tiêu đề/giáo viên, chọn <b>Theme Beamer</b> (Madrid, Warsaw...), <b>Bảng màu</b>, <b>Khung hình 16:9</b> và <b>Kiểu chiếu</b> (dùng <code>\\pause</code> để bấm tới hiện lời giải, hoặc tách 2 slide riêng).</li>
          <li><b>Thực thi:</b>
            <ul>
              <li>Bấm <span class="btn">Tạo mã Main Beamer</span> để xem và chỉnh sửa trực tiếp mã LaTeX.</li>
              <li>Bấm <span class="btn">Xuất .tex &amp; Mở TeXstudio</span> để lưu tệp không dấu và mở trên TeXstudio.</li>
              <li>Bấm <span class="btn">Biên dịch PDF &amp; Trình chiếu ngay</span> để tự chạy <code>pdflatex</code> và mở bản PDF trình chiếu (nhấn <code>Ctrl+L</code> để chiếu toàn màn hình).</li>
            </ul>
          </li>
        </ol>
        """,
    ),
    "tienich_suite": (
        "Phiếu 2025 · Tikz2Pic · Blogger · Config",
        "Cấu hình API Key, chèn Phiếu TLTN 2025, xuất hình Tikz2Pic PNG hoặc tạo form trắc nghiệm Blogger.",
        """
        <h2>Bộ tiện ích mở rộng &amp; Cấu hình hệ thống</h2>
        <ul>
          <li><b>Phiếu TLTN 2025:</b> Gắn nhanh trang phiếu tô trắc nghiệm mới (1 mặt hoặc 2 trang) vào đề <code>.tex</code> / <code>.pdf</code>.</li>
          <li><b>Tikz2Pic:</b> Chuyển hàng loạt đoạn mã TikZ thành ảnh PNG nền trong/trắng 300 DPI.</li>
          <li><b>Blogger:</b> Xuất mã HTML nhúng đề thi trắc nghiệm chấm điểm tự động lên Blogspot/Website.</li>
          <li><b>Config:</b> Lưu cấu hình API Key và tuỳ chọn mặc định của phần mềm.</li>
        </ul>
        """,
    ),
    "ve_hinh": (
        "Tab Vẽ hình (Hình phẳng & Hình không gian TikZ)",
        "Chọn mẫu hình học → nhập thông số đỉnh/cạnh/góc → bấm tạo mã TikZ & xem trước PDF → Copy dán vào TeXstudio.",
        """
        <h2>Vẽ hình phẳng &amp; Hình không gian bằng TikZ</h2>
        <ol>
          <li>Chọn loại hình cần dựng (tam giác, đường tròn, hình chóp, lăng trụ, nón, trụ, cầu...).</li>
          <li>Nhập tên đỉnh, kích thước, góc nhìn và tuỳ chọn nét đứt/tô màu.</li>
          <li>Bấm nút sinh mã để xem mã TikZ (và biên dịch xem thử ảnh PDF ngay trong cửa sổ).</li>
          <li>Bấm <b>Copy mã TikZ</b> rồi dán trực tiếp vào đề thi trong TeXstudio.</li>
        </ol>
        """,
    ),
    "do_thi": (
        "Tab Đồ thị (Vẽ đồ thị hàm số TikZ)",
        "Chọn dạng hàm số → nhập hệ số & miền vẽ → tạo mã TikZ, xem trước PDF rồi Copy.",
        """
        <h2>Vẽ đồ thị hàm số chuẩn sách giáo khoa</h2>
        <ol>
          <li>Chọn dạng hàm số (bậc 2, bậc 3, bậc 4 trùng phương, phân thức bậc 1/1, 2/1, mũ/logarit, lượng giác...).</li>
          <li>Nhập hệ số hàm số và giới hạn trục toạ độ <code>xmin, xmax, ymin, ymax</code>.</li>
          <li>Bấm sinh mã TikZ, xem trước hình ảnh rồi bấm <b>Copy</b> dán vào đề thi.</li>
        </ol>
        """,
    ),
    "bbt_xd": (
        "Tab BBT&XD (Bảng biến thiên & Bảng xét dấu)",
        "Nhập hàm số hoặc nghiệm/dấu đạo hàm → sinh mã tkz-tab chuẩn TeX Live 2019 → xem trước & Copy.",
        """
        <h2>Tạo Bảng biến thiên &amp; Bảng xét dấu (tkz-tab)</h2>
        <ol>
          <li>Chọn kiểu bảng (Bảng xét dấu nhị thức/tam thức hoặc Bảng biến thiên hàm số).</li>
          <li>Nhập danh sách nghiệm, điểm không xác định và dấu các khoảng (hoặc nhập hàm số để tự tính).</li>
          <li>Bấm sinh mã <code>tkz-tab</code>, kiểm tra bản xem trước rồi bấm <b>Copy</b>.</li>
        </ol>
        """,
    ),
    "bieu_dien_nghiem": (
        "Tab Biểu diễn nghiệm (Trục số & Khoảng nghiệm)",
        "Nhập các khoảng/đoạn nghiệm cần biểu diễn → bấm sinh mã TikZ trục số → Copy vào lời giải.",
        """
        <h2>Biểu diễn tập nghiệm trên trục số</h2>
        <ol>
          <li>Nhập các khoảng, đoạn, nửa khoảng nghiệm (hoặc kết hợp giao/hợp nhiều tập nghiệm).</li>
          <li>Bấm sinh mã TikZ để tự vẽ trục số, ngoặc tròn/vuông và gạch bỏ phần loại.</li>
          <li>Bấm <b>Copy mã TikZ</b> dán thẳng vào lời giải LaTeX.</li>
        </ol>
        """,
    ),
    "soan_thao": (
        "Tab Soạn thảo (Chỉnh sửa & Biên dịch nhanh)",
        "Chỉnh sửa mã LaTeX câu hỏi/đề thi trực tiếp → bấm Lưu vào kho hoặc Biên dịch PDF để xem kết quả.",
        """
        <h2>Soạn thảo LaTeX &amp; Biên dịch PDF nhanh</h2>
        <ol>
          <li>Chỉnh sửa trực tiếp mã nguồn câu hỏi <code>\\begin{ex}...\\end{ex}</code> hoặc đề thi.</li>
          <li>Bấm <b>Lưu vào kho</b> để cập nhật câu hỏi vào cơ sở dữ liệu FTS5.</li>
          <li>Bấm <b>Biên dịch PDF</b> để kiểm tra hiển thị công thức và hình vẽ ngay lập tức.</li>
        </ol>
        """,
    ),
    "thong_tin": (
        "Tab Thông tin & Tự động cập nhật",
        "Cấu hình API AI, xem đường dẫn TeX/DB và bấm Kiểm tra cập nhật ngay để tự động nâng cấp phiên bản mới.",
        """
        <h2>Thông tin hệ thống &amp; Tự động cập nhật</h2>
        <ul>
          <li><b>Tự động cập nhật:</b> Giữ tích <i>Tự động kiểm tra cập nhật khi mở phần mềm</i> hoặc bấm <span class="btn">Kiểm tra cập nhật ngay</span>. Khi có bản phát hành mới trên GitHub Releases, phần mềm tự tải, giải nén và khởi động lại phiên bản mới.</li>
          <li><b>Cấu hình AI mặc định:</b> Chọn nhà cung cấp (Gemini / OpenAI / Claude / DeepSeek / Grok), nhập API Key và tên Model.</li>
          <li><b>Thông tin môi trường:</b> Kiểm tra trình biên dịch TeX đang nhận diện và vị trí tệp cơ sở dữ liệu FTS5.</li>
        </ul>
        """,
    ),
}

# Cấu trúc cây mục lục của Tab HDSD chung (giữ nguyên bố cục v5.8, bổ sung mục Tự động cập nhật)
HDSD_SECTIONS: list[tuple[str, list[tuple[str, str, str]]]] = [
    (
        "0. Bắt đầu nhanh & Cấu hình",
        [
            (
                "Thiết lập lần đầu (TeX Live 2019 & API)",
                "cai dat texlive 2019 texstudio api key gemini mathpix bat dau",
                """
                <h2>Thiết lập lần đầu để chạy ổn định</h2>
                <ol>
                  <li><b>Thư mục cài đặt:</b> Giải nén phần mềm vào đường dẫn <b>không dấu, không khoảng trắng</b> (VD: <code>D:\\App-NganHangde\\toan11</code>).</li>
                  <li><b>Cấu hình TeXstudio (TeX Live 2019):</b> Mở TeXstudio → <i>Tùy chọn → Cấu hình TeXstudio → Lệnh</i> → tại dòng <code>PdfLaTeX</code> trỏ đúng tới <code>C:\\texlive\\2019\\bin\\win32\\pdflatex.exe -synctex=1 -interaction=nonstopmode %.tex</code>.</li>
                  <li><b>Nhập Gemini API Key (để chuyển PDF/Ảnh/Word MathType chuẩn 100%):</b> Vào tab <span class="btn">Tiện ích</span> → <span class="btn">Tiện ích 1</span> → khung <i>Chuyển đổi file Word/PDF sang TeX</i> → bấm <span class="btn">Tuỳ chọn</span> → dán API Key vào ô <code>API</code> → bấm <span class="btn">Lưu</span>.</li>
                </ol>
                <div class="tip"><b>Mẹo:</b> Phím tắt <code>F1</code> ở bất kỳ đâu sẽ mở nhanh cửa sổ <b>HDSD</b>; cuối mỗi tab chức năng đều có thanh <b>HDSD chi tiết</b> riêng.</div>
                """,
            ),
            (
                "Tự động cập nhật phiên bản mới",
                "cap nhat tu dong update github releases phien ban moi",
                FEATURE_GUIDES["thong_tin"][2],
            ),
        ],
    ),
    (
        "1. Tab Trộn đề",
        [
            ("1.1. Tạo đề theo ID", "tron de tao de theo id chon nhanh nhan biet thong hieu van dung", FEATURE_GUIDES["tron_id"][2]),
            ("1.2. Tạo đề tự chọn", "tao de tu chon tich chon cau hoi sua xoa", FEATURE_GUIDES["tron_tuchon"][2]),
            ("1.3. Tạo đề theo file (.tex)", "tao de theo file tex tron truc tiep", FEATURE_GUIDES["tron_file"][2]),
            ("1.4. Tạo đề tương tự", "tao de tuong tu de goc doi cau hoi", FEATURE_GUIDES["tron_tuongtu"][2]),
            ("1.5. Tuỳ chọn đề & Xuất bộ đề", "tuy chon de so de ma de phieu tltn 2025 bien dich pdf sap xep", FEATURE_GUIDES["tron_tuychon"][2]),
        ],
    ),
    (
        "2. Tab Câu hỏi & Ma trận",
        [
            ("2.1. Quản lý câu hỏi (MyLT 2026)", "cau hoi nhap cau hoi ngan hang ra soat", FEATURE_GUIDES["cauhoi_mylt"][2]),
            ("2.2. Kho nâng cao (FTS5 · F11)", "kho nang cao cay thu muc fts5 trinh chieu f11", FEATURE_GUIDES["cauhoi_fts5"][2]),
            ("2.3. Ma trận đề thi (CV 7991)", "ma tran cv 7991 excel dac ta", FEATURE_GUIDES["ma_tran"][2]),
        ],
    ),
    (
        "3. Tab Tiện ích (Word · PDF · Online · AI)",
        [
            ("3.1. Tiện ích 1 (Word/PDF ↔ TeX · Lọc · Phiếu · Trùng)", "tien ich 1 word pdf sang latex mathtype loc phieu 2025 trung hoa anh", FEATURE_GUIDES["tienich_1"][2]),
            ("3.2. Tiện ích 2 (Chuẩn hoá mã LaTeX)", "tien ich 2 chuan hoa latex", FEATURE_GUIDES["tienich_2"][2]),
            ("3.3. Word ↔ LaTeX & AI OCR PDF", "word ocr pdf anh gemini mathpix pymupdf chon trang", FEATURE_GUIDES["tienich_word_ocr"][2]),
            ("3.4. Moodle · Online GAS · Đấu trường LAN", "moodle online gas dau truong lan", FEATURE_GUIDES["tienich_online"][2]),
            ("3.5. Biên soạn Chuyên đề (.tex / PDF)", "bien soan chuyen de", FEATURE_GUIDES["tienich_chuyende"][2]),
            ("3.6. Trạm AI (Gán ID · Sinh câu · Chấm TL)", "tram ai gan id sinh cau cham tu luan", FEATURE_GUIDES["tienich_ai"][2]),
            ("3.7. Phiếu 2025 · Tikz2Pic · Blogger · Config", "phieu 2025 tikz2pic blogger config", FEATURE_GUIDES["tienich_suite"][2]),
            ("3.8. Trình chiếu đề bằng Main Beamer", "trinh chieu beamer slide pause 16:9", FEATURE_GUIDES["tienich_beamer"][2]),
        ],
    ),
    (
        "4. Tab Vẽ hình · Đồ thị · BBT&XD · Soạn thảo",
        [
            ("4.1. Vẽ hình (Hình phẳng & Không gian)", "ve hinh khong gian phang tikz", FEATURE_GUIDES["ve_hinh"][2]),
            ("4.2. Đồ thị hàm số", "do thi ham so tikz", FEATURE_GUIDES["do_thi"][2]),
            ("4.3. BBT&XD (Bảng biến thiên & Xét dấu)", "bbt xd bang bien thien xet dau tkz-tab", FEATURE_GUIDES["bbt_xd"][2]),
            ("4.4. Biểu diễn nghiệm (Trục số)", "bieu dien nghiem truc so", FEATURE_GUIDES["bieu_dien_nghiem"][2]),
            ("4.5. Soạn thảo & Biên dịch PDF", "soan thao bien dich pdf", FEATURE_GUIDES["soan_thao"][2]),
        ],
    ),
    (
        "5. Xử lý nhanh lỗi thường gặp",
        [
            (
                "Các lỗi phổ biến & Cách khắc phục trong 10 giây",
                "loi thuong gap khong bien dich duoc texlive 2019 mathtype api key",
                """
                <h2>Khắc phục nhanh các lỗi thường gặp</h2>
                <ul>
                  <li><b>TeXstudio báo <i>Không thể khởi chạy Build &amp; View:PdfLaTeX</i>:</b> Kiểm tra tên tệp <code>.tex</code> không có dấu tiếng Việt/dấu phẩy, và trỏ đúng đường dẫn <code>pdflatex.exe</code> trong <i>Tùy chọn → Cấu hình TeXstudio → Lệnh</i>.</li>
                  <li><b>TeXstudio báo lỗi <i>Missing \\begin{document}</i>:</b> Bạn đang bấm F5 trên tệp ngân hàng câu hỏi rời (VD: <code>de_mau_toan11_2026.tex</code>) thay vì tệp đề đã ghép khung Main. Hãy bấm chuột vào đúng tab tệp đề cần biên dịch.</li>
                  <li><b>Chuyển Word báo <i>còn nguyên X/X công thức MathType</i>:</b> Word trên máy đang chặn Add-in MathType khi mở qua COM. Chuyển sang chế độ <b>Dùng Gemini</b> trong <i>Tuỳ chọn</i>, hoặc mở tệp bằng Word bấm <i>MathType → Convert Equations</i> rồi lưu lại trước khi đưa vào phần mềm.</li>
                  <li><b>Chuyển PDF/Ảnh báo thiếu API Key:</b> Mở <span class="btn">Tiện ích 1</span> → <span class="btn">Tuỳ chọn</span> → nhập Gemini API Key vào ô <code>API</code> → bấm <span class="btn">Lưu</span>.</li>
                </ul>
                <div class="warn"><b>Mẹo bảo trì:</b> Khi cập nhật phiên bản mới, luôn tắt hoàn toàn cửa sổ <code>Nganhangde_vu.exe</code> cũ trước khi chạy <code>build_exe.bat</code>.</div>
                """,
            ),
        ],
    ),
]


def show_feature_hdsd_dialog(
    parent: QWidget | None,
    guide_key: str,
    open_full_fn: Callable[[], None] | None = None,
) -> None:
    """Mở hộp thoại HDSD chi tiết cho đúng chức năng đang thao tác."""
    title, _short, html = FEATURE_GUIDES.get(
        guide_key,
        ("Hướng dẫn sử dụng", "", "<h2>Hướng dẫn sử dụng</h2><p>Xem mục HDSD tổng hợp (phím F1).</p>"),
    )
    dlg = QDialog(parent.window() if parent is not None else None)
    dlg.setWindowTitle(f"HDSD — {title}")
    dlg.resize(700, 440)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(8, 8, 8, 8)
    lay.setSpacing(6)

    br = QTextBrowser()
    br.setOpenExternalLinks(True)
    br.setHtml(_CSS + html)
    lay.addWidget(br, 1)

    bot = QHBoxLayout()
    b_copy = QPushButton("Sao chép")
    b_copy.clicked.connect(lambda: QApplication.clipboard().setText(br.toPlainText().strip()))
    bot.addWidget(b_copy)
    if open_full_fn is not None:
        b_all = QPushButton("Mở HDSD tổng hợp (F1)")
        b_all.setStyleSheet(
            "QPushButton { background-color: #16a34a; border: 1px solid #15803d; color: #ffffff; "
            "font-weight: 700; padding: 4px 10px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #15803d; }"
        )
        b_all.clicked.connect(lambda: (dlg.accept(), open_full_fn()))
        bot.addWidget(b_all)
    bot.addStretch()
    b_close = QPushButton("Đóng")
    b_close.clicked.connect(dlg.accept)
    bot.addWidget(b_close)
    lay.addLayout(bot)
    dlg.exec()


def wrap_tab_with_hdsd(
    inner: QWidget,
    guide_key: str,
    open_full_fn: Callable[[], None] | None = None,
    position: str = "bottom",
) -> QWidget:
    """Bọc 1 tab/sub-tab kèm thanh HDSD ngắn gọn + nút 'HDSD chi tiết' ở cuối (hoặc đầu) để dễ thao tác."""
    _title, short_hint, _html = FEATURE_GUIDES.get(guide_key, ("HDSD", "Bấm nút HDSD để xem hướng dẫn chi tiết.", ""))

    container = QWidget()
    lay = QVBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)

    bar = QFrame()
    bar.setFrameShape(QFrame.StyledPanel)
    bar.setStyleSheet(
        "QFrame { background-color: #dcfce7; border: 1px solid #22c55e; border-radius: 4px; }"
    )
    hb = QHBoxLayout(bar)
    hb.setContentsMargins(8, 3, 8, 3)
    hb.setSpacing(8)

    lbl = QLabel(f"<b style='color:#15803d;'>HDSD nhanh:</b> {short_hint}")
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #14532d; font-size: 9.5pt; border: none; background: transparent;")

    btn = QPushButton("HDSD chi tiết")
    btn.setToolTip("Mở hướng dẫn từng bước chi tiết cho chức năng này")
    btn.setStyleSheet(
        "QPushButton { background-color: #16a34a; border: 1px solid #15803d; color: #ffffff; "
        "font-weight: 700; padding: 3px 12px; border-radius: 4px; }"
        "QPushButton:hover { background-color: #15803d; }"
        "QPushButton:pressed { background-color: #166534; }"
    )
    btn.clicked.connect(lambda: show_feature_hdsd_dialog(container, guide_key, open_full_fn))

    hb.addWidget(lbl, 1)
    hb.addWidget(btn, 0)

    if position == "top":
        lay.addWidget(bar)
        lay.addWidget(inner, 1)
    else:
        lay.addWidget(inner, 1)
        lay.addWidget(bar)

    return container


class HDSDTab(QWidget):
    """Tab Hướng dẫn sử dụng (HDSD) tổng hợp giữ nguyên giao diện cây mục lục v5.8."""

    def __init__(self, parent=None, is_popup: bool = False):
        super().__init__(parent)
        self._is_popup = is_popup
        self._popup_win: QDialog | None = None
        self._items_data: list[tuple[QTreeWidgetItem, str, str, str]] = []
        self._build_ui()
        self._populate_tree()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        top = QHBoxLayout()
        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText("Tìm nhanh chức năng (VD: trộn đề, mathtype, pdf, phiếu 2025, cập nhật, lỗi texlive)...")
        self.ed_search.setClearButtonEnabled(True)
        self.ed_search.textChanged.connect(self._filter_tree)

        b_copy = QPushButton("Sao chép nội dung")
        b_copy.clicked.connect(self._copy_current)

        top.addWidget(QLabel("Tìm kiếm:"))
        top.addWidget(self.ed_search, 1)
        top.addWidget(b_copy)
        if not self._is_popup:
            b_pop = QPushButton("Mở cửa sổ HDSD riêng")
            b_pop.setStyleSheet(
                "QPushButton { background-color: #16a34a; border: 1px solid #15803d; color: #ffffff; "
                "font-weight: 700; padding: 4px 12px; border-radius: 4px; }"
                "QPushButton:hover { background-color: #15803d; }"
            )
            b_pop.clicked.connect(self.open_standalone_window)
            top.addWidget(b_pop)
        root.addLayout(top)

        split = QSplitter(Qt.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Danh mục chức năng (HDSD)")
        self.tree.setMinimumWidth(270)
        self.tree.currentItemChanged.connect(self._on_select)

        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)

        split.addWidget(self.tree)
        split.addWidget(self.viewer)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        root.addWidget(split, 1)

    def _populate_tree(self):
        self.tree.clear()
        self._items_data.clear()
        first_leaf: QTreeWidgetItem | None = None
        for group_title, entries in HDSD_SECTIONS:
            g_item = QTreeWidgetItem([group_title])
            font = g_item.font(0)
            font.setBold(True)
            g_item.setFont(0, font)
            self.tree.addTopLevelItem(g_item)
            for title, keywords, html in entries:
                leaf = QTreeWidgetItem([title])
                leaf.setData(0, Qt.UserRole, html)
                g_item.addChild(leaf)
                self._items_data.append((leaf, title.lower(), keywords.lower(), html))
                if first_leaf is None:
                    first_leaf = leaf
            g_item.setExpanded(True)
        if first_leaf is not None:
            self.tree.setCurrentItem(first_leaf)

    def _on_select(self, cur: QTreeWidgetItem | None, _prev: QTreeWidgetItem | None):
        if cur is None:
            return
        html = cur.data(0, Qt.UserRole)
        if not html and cur.childCount() > 0:
            html = cur.child(0).data(0, Qt.UserRole)
        if html:
            self.viewer.setHtml(_CSS + html)

    def _filter_tree(self, query: str):
        q = query.strip().lower()
        first_visible: QTreeWidgetItem | None = None
        for i in range(self.tree.topLevelItemCount()):
            g_item = self.tree.topLevelItem(i)
            any_child = False
            for j in range(g_item.childCount()):
                ch = g_item.child(j)
                html = ch.data(0, Qt.UserRole) or ""
                match = (not q) or (q in ch.text(0).lower()) or (q in html.lower())
                if not match:
                    for item, _t, kw, _h in self._items_data:
                        if item is ch and q in kw:
                            match = True
                            break
                ch.setHidden(not match)
                if match:
                    any_child = True
                    if first_visible is None:
                        first_visible = ch
            g_item.setHidden(not any_child)
            if any_child:
                g_item.setExpanded(True)
        if first_visible is not None:
            self.tree.setCurrentItem(first_visible)

    def _copy_current(self):
        txt = self.viewer.toPlainText().strip()
        if txt:
            QApplication.clipboard().setText(txt)

    def open_standalone_window(self):
        """Mở cửa sổ Hướng dẫn sử dụng độc lập mang tên 'HDSD' giống MyLT 2026."""
        if self._popup_win is None:
            dlg = QDialog(self.window())
            dlg.setWindowTitle("HDSD")
            dlg.resize(940, 620)
            v = QVBoxLayout(dlg)
            v.setContentsMargins(4, 4, 4, 4)
            v.addWidget(HDSDTab(dlg, is_popup=True))
            self._popup_win = dlg
        self._popup_win.show()
        self._popup_win.raise_()
        self._popup_win.activateWindow()
