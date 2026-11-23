"""Sub-tab Trình chiếu đề bằng Main Beamer chuẩn TeX Live 2019 — Xuất main_beamer.tex + biên dịch & mở PDF trực tiếp."""
from __future__ import annotations
import os
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from ..exporters.beamer_exporter import (
    BEAMER_COLOR_THEMES,
    BEAMER_THEMES,
    BeamerOptions,
    build_beamer_main_and_body,
    load_questions_from_tex_file,
    safe_beamer_stem,
)
from ..exporters.pdfbuild import compile_tex_to_pdf, open_pdf_file
from ..paths import app_root_dir
from .workers import run_in_background


class BeamerPresentationTab(QWidget):
    """Tab tạo Main Beamer (main_beamer.tex + noidung_beamer.tex), biên dịch PDF vào out/ và mở trình chiếu."""

    def __init__(self, mw, parent=None):
        super().__init__(parent)
        self.mw = mw
        self._last_pdf_path: str = ""
        self._last_body_tex: str = ""
        self._last_body_name: str = "noidung_beamer.tex"
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # Khối 1: Chọn nguồn đề & thư mục xuất (tự tạo thư mục con out)
        g_src = QGroupBox("1. Nguồn đề trình chiếu & Thư mục xuất (tự tạo thư mục out)")
        v_src = QVBoxLayout(g_src)
        r_mode = QHBoxLayout()
        self.rb_file = QRadioButton("Từ tệp đề .tex")
        self.rb_last = QRadioButton("Từ đề vừa trộn (Tab Trộn đề)")
        self.rb_bank = QRadioButton("Từ câu hỏi đang lọc (Tab Câu hỏi)")
        self.rb_file.setChecked(True)
        for rb in (self.rb_file, self.rb_last, self.rb_bank):
            r_mode.addWidget(rb)
        r_mode.addStretch()
        v_src.addLayout(r_mode)

        r_file = QHBoxLayout()
        self.ed_tex = QLineEdit()
        self.ed_tex.setPlaceholderText("Chọn tệp đề .tex chuẩn ex_test cần trình chiếu...")
        b_pick = QPushButton("Chọn tệp .tex...")
        b_pick.clicked.connect(self._pick_tex)
        r_file.addWidget(QLabel("Tệp đề:"))
        r_file.addWidget(self.ed_tex, 1)
        r_file.addWidget(b_pick)
        v_src.addLayout(r_file)

        r_out = QHBoxLayout()
        self.ed_out_dir = QLineEdit(str(app_root_dir()))
        self.ed_out_dir.setPlaceholderText("Thư mục chứa kết quả (phần mềm tự tạo thư mục con 'out' bên trong)...")
        b_pick_out = QPushButton("Chọn thư mục xuất...")
        b_pick_out.clicked.connect(self._pick_out_dir)
        b_open_out = QPushButton("Mở thư mục out")
        b_open_out.clicked.connect(self._open_out_folder)
        r_out.addWidget(QLabel("Thư mục xuất:"))
        r_out.addWidget(self.ed_out_dir, 1)
        r_out.addWidget(b_pick_out)
        r_out.addWidget(b_open_out)
        v_src.addLayout(r_out)
        root.addWidget(g_src)

        # Khối 2: Cấu hình Main Beamer
        g_cfg = QGroupBox("2. Cấu hình Main Beamer (TeX Live 2019 — tách main_beamer.tex & noidung_beamer.tex)")
        grid = QGridLayout(g_cfg)
        self.ed_title = QLineEdit("TRÌNH CHIẾU ĐỀ KIỂM TRA TOÁN")
        self.ed_sub = QLineEdit("Chương trình GDPT 2018")
        self.ed_author = QLineEdit("Tổ Toán")
        self.ed_inst = QLineEdit("Trường THPT")

        self.cbo_theme = QComboBox(); self.cbo_theme.addItems(BEAMER_THEMES)
        self.cbo_color = QComboBox(); self.cbo_color.addItems(BEAMER_COLOR_THEMES)
        self.cbo_ratio = QComboBox(); self.cbo_ratio.addItems(["16:9 (Màn hình rộng)", "4:3 (Máy chiếu chuẩn)"])
        self.cbo_font = QComboBox(); self.cbo_font.addItems(["11pt", "10pt", "12pt", "14pt"])
        self.cbo_slide_mode = QComboBox()
        self.cbo_slide_mode.addItems([
            "Hiện đề → bấm tới hiện lời giải (\\pause)",
            "Tách 2 slide riêng (Slide đề | Slide lời giải)",
            "Chỉ chiếu đề bài (không kèm lời giải)",
        ])
        self.chk_title_slide = QCheckBox("Tạo slide bìa (Title page)"); self.chk_title_slide.setChecked(True)
        self.chk_show_id = QCheckBox("Hiện mã ID6 góc phải mỗi câu")

        grid.addWidget(QLabel("Tiêu đề:"), 0, 0); grid.addWidget(self.ed_title, 0, 1)
        grid.addWidget(QLabel("Phụ đề / Môn:"), 0, 2); grid.addWidget(self.ed_sub, 0, 3)
        grid.addWidget(QLabel("Giáo viên:"), 1, 0); grid.addWidget(self.ed_author, 1, 1)
        grid.addWidget(QLabel("Đơn vị / Trường:"), 1, 2); grid.addWidget(self.ed_inst, 1, 3)

        grid.addWidget(QLabel("Theme Beamer:"), 2, 0); grid.addWidget(self.cbo_theme, 2, 1)
        grid.addWidget(QLabel("Bảng màu:"), 2, 2); grid.addWidget(self.cbo_color, 2, 3)
        grid.addWidget(QLabel("Khung hình:"), 3, 0); grid.addWidget(self.cbo_ratio, 3, 1)
        grid.addWidget(QLabel("Cỡ chữ:"), 3, 2); grid.addWidget(self.cbo_font, 3, 3)

        grid.addWidget(QLabel("Kiểu chiếu:"), 4, 0); grid.addWidget(self.cbo_slide_mode, 4, 1, 1, 3)
        chk_row = QHBoxLayout()
        chk_row.addWidget(self.chk_title_slide)
        chk_row.addWidget(self.chk_show_id)
        chk_row.addStretch()
        grid.addLayout(chk_row, 5, 0, 1, 4)
        root.addWidget(g_cfg)

        # Hàng nút thực thi
        act = QHBoxLayout()
        b_gen = QPushButton("Tạo mã Main Beamer")
        b_gen.clicked.connect(self._generate_code)
        b_tex = QPushButton("Lưu vào out/ & Mở TeXstudio")
        b_tex.clicked.connect(self._export_tex_and_open)
        self.b_pdf = QPushButton("Biên dịch PDF trực tiếp (vào out/)")
        self.b_pdf.clicked.connect(self._compile_and_present)
        self.b_open_pdf = QPushButton("Mở PDF trình chiếu")
        self.b_open_pdf.clicked.connect(self._open_pdf_now)

        act.addWidget(b_gen)
        act.addWidget(b_tex)
        act.addWidget(self.b_pdf)
        act.addWidget(self.b_open_pdf)
        act.addStretch()
        root.addLayout(act)

        # Khung chia đôi: Trái là Mã Main Beamer, Phải là Nhật ký biên dịch trực tiếp
        split = QSplitter(Qt.Horizontal)
        self.txt_code = QPlainTextEdit()
        self.txt_code.setPlaceholderText("Mã nguồn main_beamer.tex sẽ hiển thị tại đây (có thể chỉnh sửa trước khi biên dịch)...")
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("Nhật ký biên dịch PDF trực tiếp sẽ hiển thị tại đây...")
        split.addWidget(self.txt_code)
        split.addWidget(self.txt_log)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        root.addWidget(split, 1)

    def _pick_tex(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn tệp đề .tex", str(app_root_dir()), "LaTeX (*.tex)")
        if p:
            self.ed_tex.setText(p)
            self.rb_file.setChecked(True)
            self.ed_out_dir.setText(str(Path(p).parent))

    def _pick_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất (tự tạo thư mục con out)", self.ed_out_dir.text().strip() or str(app_root_dir()))
        if d:
            self.ed_out_dir.setText(d)

    def _resolve_out_folder(self) -> Path:
        base = Path(self.ed_out_dir.text().strip() or str(app_root_dir()))
        out_dir = base if base.name.lower() == "out" else (base / "out")
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def _open_out_folder(self):
        out_dir = self._resolve_out_folder()
        if os.name == "nt":
            os.startfile(str(out_dir))
        else:
            open_pdf_file(str(out_dir))

    def _open_pdf_now(self):
        """Mở ngay tệp PDF trình chiếu mới biên dịch (hoặc tự tìm PDF mới nhất trong thư mục out/)."""
        if self._last_pdf_path and Path(self._last_pdf_path).exists():
            open_pdf_file(self._last_pdf_path)
            return
        out_dir = self._resolve_out_folder()
        pdfs = sorted(out_dir.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True)
        if pdfs:
            self._last_pdf_path = str(pdfs[0])
            open_pdf_file(self._last_pdf_path)
            return
        QMessageBox.information(
            self,
            "Chưa có tệp PDF trình chiếu",
            f"Chưa tìm thấy tệp .pdf nào trong thư mục:\n{out_dir}\n\nHãy bấm 'Biên dịch PDF trực tiếp (vào out/)' trước.",
        )

    def _collect_questions(self):
        if self.rb_file.isChecked():
            p = self.ed_tex.text().strip()
            if not p or not Path(p).exists():
                self._pick_tex()
                p = self.ed_tex.text().strip()
            if not p or not Path(p).exists():
                return [], "noidung_beamer"
            return load_questions_from_tex_file(p), safe_beamer_stem(Path(p).stem + "_noidung")

        if self.rb_last.isChecked():
            vars_list = getattr(self.mw, "last_variants", None) or []
            if not vars_list:
                QMessageBox.warning(self, "Chưa có đề vừa trộn", "Hãy bấm 'Tạo đề' ở tab Trộn đề trước, hoặc chọn nguồn từ tệp .tex.")
                return [], "noidung_beamer"
            return list(vars_list[0].questions), f"de_{vars_list[0].code}_noidung"

        qs = getattr(self.mw, "current_questions", None) or []
        if not qs:
            QMessageBox.warning(self, "Kho đang trống", "Chưa có câu hỏi nào trong danh sách lọc ở tab Câu hỏi.")
            return [], "noidung_beamer"
        return list(qs), "cau_hoi_kho_noidung"

    def _get_options(self) -> BeamerOptions:
        sm_idx = self.cbo_slide_mode.currentIndex()
        sm = "pause" if sm_idx == 0 else ("split" if sm_idx == 1 else "question_only")
        return BeamerOptions(
            title=self.ed_title.text().strip() or "TRÌNH CHIẾU ĐỀ TOÁN",
            subtitle=self.ed_sub.text().strip(),
            author=self.ed_author.text().strip(),
            institute=self.ed_inst.text().strip(),
            theme=self.cbo_theme.currentText(),
            color_theme=self.cbo_color.currentText(),
            aspect_ratio="169" if self.cbo_ratio.currentIndex() == 0 else "43",
            font_size=self.cbo_font.currentText(),
            slide_mode=sm,
            include_title_slide=self.chk_title_slide.isChecked(),
            show_id_tag=self.chk_show_id.isChecked(),
        )

    def _generate_code(self) -> tuple[str, str]:
        qs, body_stem = self._collect_questions()
        if not qs:
            return "", ""
        self._last_body_name = f"{body_stem}.tex"
        main_tex, body_tex = build_beamer_main_and_body(qs, self._get_options(), body_filename=self._last_body_name)
        self._last_body_tex = body_tex
        self.txt_code.setPlainText(main_tex)
        self.txt_log.setPlainText(
            f"[OK] Đã tạo bộ Main Beamer cho {len(qs)} câu hỏi:\n"
            f"- Tệp Main: main_beamer.tex\n"
            f"- Tệp nội dung: {self._last_body_name}"
        )
        return main_tex, body_tex

    def _save_main_into_out(self) -> Path | None:
        main_tex = self.txt_code.toPlainText().strip()
        if not main_tex or not self._last_body_tex:
            main_tex, _ = self._generate_code()
            if not main_tex:
                return None
        out_dir = self._resolve_out_folder()
        body_path = out_dir / self._last_body_name
        body_path.write_text(self._last_body_tex, encoding="utf-8")
        main_path = out_dir / "main_beamer.tex"
        main_path.write_text(main_tex, encoding="utf-8")
        return main_path

    def _export_tex_and_open(self):
        p = self._save_main_into_out()
        if p:
            self.txt_log.appendPlainText(f"[LƯU] Đã lưu main_beamer.tex và {self._last_body_name} vào:\n{p.parent}")
            open_pdf_file(str(p))
            QMessageBox.information(self, "Xuất Main Beamer", f"Đã lưu vào thư mục out và mở tệp Main:\n{p}")

    @staticmethod
    def _extract_log_tail(bres) -> str:
        parts: list[str] = []
        if getattr(bres, "stderr", ""):
            parts.append(str(bres.stderr).strip())
        diags = getattr(bres, "diagnostics", None) or []
        if diags:
            parts.append("Chẩn đoán lỗi:")
            for d in diags[:8]:
                ln = f"Dòng {d.line_no}: " if d.line_no else ""
                parts.append(f"- {ln}{d.summary} ({d.suggestion_vi})")
        lp = getattr(bres, "log_path", None)
        if lp and Path(lp).exists():
            try:
                raw = Path(lp).read_text(encoding="utf-8", errors="replace")
                parts.append(raw[-2000:])
            except Exception:
                pass
        return "\n".join(parts).strip()

    def _compile_and_present(self):
        p = self._save_main_into_out()
        if not p:
            return
        self.txt_log.setPlainText(
            f"[1/2] Đã lưu main_beamer.tex + {self._last_body_name} vào thư mục out:\n{p.parent}\n"
            f"[2/2] Đang chạy pdflatex (2 lượt) biên dịch trực tiếp main_beamer.tex..."
        )
        self.b_pdf.setEnabled(False)

        dlg = QProgressDialog(f"Đang biên dịch trực tiếp {p.name} sang PDF trong thư mục out/...", None, 0, 0, self)
        dlg.setWindowTitle("Biên dịch PDF Main Beamer")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.show()

        def _job():
            return compile_tex_to_pdf(str(p), compiler="pdflatex", passes=2)

        def _on_ok(bres):
            dlg.close()
            self.b_pdf.setEnabled(True)
            log_tail = self._extract_log_tail(bres)
            pdf_out = bres.pdf_path or str(p.with_suffix(".pdf"))
            if bres.success and Path(pdf_out).exists():
                self._last_pdf_path = pdf_out
                self.txt_log.setPlainText(
                    f"[THÀNH CÔNG] Đã biên dịch PDF trực tiếp!\n"
                    f"- Thư mục out: {p.parent}\n"
                    f"- Tệp Main: {p.name}\n"
                    f"- Tệp PDF: {pdf_out}\n\n"
                    f"--- Nhật ký pdflatex ---\n{log_tail}"
                )
                open_pdf_file(pdf_out)
                QMessageBox.information(
                    self,
                    "Biên dịch Main Beamer thành công",
                    f"Đã biên dịch trực tiếp và mở bản trình chiếu PDF:\n{pdf_out}\n\n"
                    "Mẹo: Nhấn Ctrl + L (hoặc F11) trong trình đọc PDF để chiếu toàn màn hình.",
                )
            else:
                self.txt_log.setPlainText(
                    f"[CHƯA THÀNH CÔNG] Biên dịch gặp lỗi.\n"
                    f"- Tệp Main: {p}\n\n"
                    f"--- Chi tiết Log pdflatex ---\n{log_tail}"
                )
                QMessageBox.warning(
                    self,
                    "Biên dịch PDF chưa thành công",
                    f"Tệp Main đã lưu tại: {p}\nXem chi tiết lỗi ở khung Nhật ký biên dịch bên phải.",
                )

        def _on_err(err_msg: str):
            dlg.close()
            self.b_pdf.setEnabled(True)
            self.txt_log.appendPlainText(f"\n[LỖI] {err_msg}")
            QMessageBox.critical(self, "Lỗi biên dịch Beamer", str(err_msg))

        self._beamer_worker = run_in_background(_job, on_finished=_on_ok, on_error=_on_err)
