"""Hộp thoại Chuyển PDF/ảnh thủ công sang LaTeX chuẩn MyLT 2026."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from ..ai.pdf_ocr import (
    extract_pdf_text_fallback,
    get_pdf_page_count,
    ocr_image_to_extest,
    ocr_mathpix_file,
    ocr_pdf_to_extest,
)
from ..ai.providers import AIConfig
from ..core.config_manager import ConfigManager
from ..exporters.pdfbuild import open_pdf_file
from ..paths import app_root_dir
from .workers import run_in_background


class ManualPdfImageOcrDialog(QDialog):
    def __init__(self, initial_path: str = "", wrap_fn=None, safe_stem_fn=None, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager()
        self.wrap_fn = wrap_fn
        self.safe_stem_fn = safe_stem_fn
        self._worker = None
        self.setWindowTitle("Chuyển PDF / Ảnh sang LaTeX")
        self.resize(860, 620)
        self._build_ui()
        if initial_path and Path(initial_path).exists():
            self._set_file(initial_path)

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Hàng 1: Chọn tệp PDF / Ảnh
        r1 = QHBoxLayout()
        self.ed_file = QLineEdit()
        self.ed_file.setPlaceholderText("Chọn tệp PDF hoặc ảnh (.pdf, .png, .jpg)...")
        b_pick = QPushButton("Chọn tệp...")
        b_pick.clicked.connect(self._pick_file)
        r1.addWidget(QLabel("Tệp nguồn:"))
        r1.addWidget(self.ed_file, 1)
        r1.addWidget(b_pick)
        root.addLayout(r1)

        # Hàng 2: Động cơ chuyển đổi + Khoảng trang + Nút thực thi
        r2 = QHBoxLayout()
        self.cbo_engine = QComboBox()
        self.cbo_engine.addItems([
            "Gemini AI (Khuyên dùng — giữ đầy đủ công thức)",
            "Mathpix API",
            "Trích xuất văn bản nhanh (PyMuPDF, không cần API)",
        ])
        self.sp_from = QSpinBox(); self.sp_from.setRange(1, 9999); self.sp_from.setValue(1)
        self.sp_to = QSpinBox(); self.sp_to.setRange(1, 9999); self.sp_to.setValue(10)
        self.sp_chunk = QSpinBox(); self.sp_chunk.setRange(1, 15); self.sp_chunk.setValue(5)
        self.btn_run = QPushButton("Chuyển sang TeX")
        self.btn_run.setStyleSheet("font-weight: bold; padding: 5px 14px;")
        self.btn_run.clicked.connect(self._run_convert)

        r2.addWidget(QLabel("Chế độ:"))
        r2.addWidget(self.cbo_engine, 1)
        r2.addWidget(QLabel("Từ trang:"))
        r2.addWidget(self.sp_from)
        r2.addWidget(QLabel("Đến:"))
        r2.addWidget(self.sp_to)
        r2.addWidget(QLabel("Cụm:"))
        r2.addWidget(self.sp_chunk)
        r2.addWidget(self.btn_run)
        root.addLayout(r2)

        # Thanh tiến trình & trạng thái
        r3 = QHBoxLayout()
        self.lbl_status = QLabel("Sẵn sàng. Chọn tệp PDF/Ảnh rồi bấm 'Chuyển sang TeX'.")
        self.prog = QProgressBar()
        self.prog.setRange(0, 0)
        self.prog.setVisible(False)
        r3.addWidget(self.lbl_status, 1)
        r3.addWidget(self.prog)
        root.addLayout(r3)

        # Khung kết quả LaTeX
        self.txt_out = QPlainTextEdit()
        self.txt_out.setPlaceholderText("Mã LaTeX chuyển đổi sẽ hiển thị tại đây...")
        root.addWidget(self.txt_out, 1)

        # Thanh nút đáy
        bot = QHBoxLayout()
        b_copy = QPushButton("Copy LaTeX")
        b_copy.clicked.connect(self._copy_out)
        b_save_open = QPushButton("Lưu tệp .tex (ghép Main) & Mở TeXstudio")
        b_save_open.clicked.connect(self._save_and_open)
        b_close = QPushButton("Đóng")
        b_close.clicked.connect(self.accept)
        bot.addWidget(b_copy)
        bot.addStretch()
        bot.addWidget(b_save_open)
        bot.addWidget(b_close)
        root.addLayout(bot)

    def _set_file(self, path_str: str):
        self.ed_file.setText(path_str)
        if path_str.lower().endswith(".pdf"):
            try:
                n = get_pdf_page_count(path_str)
                self.sp_from.setMaximum(max(1, n))
                self.sp_to.setMaximum(max(1, n))
                self.sp_from.setValue(1)
                self.sp_to.setValue(n)
                self.lbl_status.setText(f"Đã nạp PDF ({n} trang). Bấm 'Chuyển sang TeX' để thực thi.")
            except Exception:
                pass
        else:
            self.lbl_status.setText("Đã nạp tệp ảnh. Bấm 'Chuyển sang TeX' để thực thi.")

    def _pick_file(self):
        p, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn tệp PDF hoặc Ảnh",
            str(app_root_dir()),
            "PDF & Ảnh (*.pdf *.png *.jpg *.jpeg);;Tất cả (*.*)",
        )
        if p:
            self._set_file(p)

    def _run_convert(self):
        p_str = self.ed_file.text().strip()
        if not p_str or not Path(p_str).exists():
            QMessageBox.warning(self, "Thiếu tệp", "Hãy chọn tệp PDF hoặc ảnh tồn tại trước khi bấm 'Chuyển sang TeX'.")
            return

        eng_idx = self.cbo_engine.currentIndex()
        is_pdf = p_str.lower().endswith(".pdf")
        p_from = self.sp_from.value()
        p_to = self.sp_to.value()
        chunk_sz = self.sp_chunk.value()

        self.cfg.load()

        if eng_idx == 0:
            gem_key = self.cfg.get("API", "gemini_api_key", "").strip()
            if not gem_key:
                QMessageBox.warning(
                    self,
                    "Thiếu Gemini API Key",
                    "Chưa có Gemini API Key. Hãy mở nút 'Tuỳ chọn' ở khung Word/PDF sang TeX, nhập Gemini API Key rồi bấm 'Lưu'.",
                )
                return
            ai_cfg = AIConfig(
                provider="gemini",
                api_key=gem_key,
                model=self.cfg.get("API", "gemini_model", "gemini-2.5-flash"),
            )

            def _job():
                if is_pdf:
                    res = ocr_pdf_to_extest(
                        p_str,
                        ai_cfg,
                        chunk_pages=chunk_sz,
                        from_page=p_from,
                        to_page=p_to,
                    )
                    return res.full_tex
                return ocr_image_to_extest(p_str, ai_cfg)

        elif eng_idx == 1:
            mp_id = self.cfg.get("API", "mathpix_app_id", "").strip()
            mp_key = self.cfg.get("API", "mathpix_app_key", "").strip()
            if not mp_id or not mp_key:
                QMessageBox.warning(
                    self,
                    "Thiếu Mathpix API",
                    "Chưa có Mathpix App ID / App Key. Hãy nhập trong nút 'Tuỳ chọn' trước.",
                )
                return

            def _job():
                return ocr_mathpix_file(p_str, mp_id, mp_key)

        else:
            if not is_pdf:
                QMessageBox.warning(self, "Chỉ hỗ trợ PDF", "Chế độ trích xuất nhanh PyMuPDF chỉ áp dụng cho tệp PDF. Với ảnh, hãy chọn Gemini AI hoặc Mathpix API.")
                return

            def _job():
                return extract_pdf_text_fallback(p_str, from_page=p_from, to_page=p_to)

        self.btn_run.setEnabled(False)
        self.prog.setVisible(True)
        self.lbl_status.setText("Đang chuyển đổi PDF/Ảnh sang LaTeX, vui lòng chờ...")

        def _on_ok(tex_text: str):
            self.btn_run.setEnabled(True)
            self.prog.setVisible(False)
            self.txt_out.setPlainText(tex_text or "")
            self.lbl_status.setText("Chuyển đổi hoàn tất! Bấm 'Lưu tệp .tex (ghép Main) & Mở TeXstudio' để biên dịch PDF.")

        def _on_err(err_msg: str):
            self.btn_run.setEnabled(True)
            self.prog.setVisible(False)
            self.lbl_status.setText("Có lỗi khi chuyển đổi.")
            QMessageBox.critical(self, "Lỗi chuyển PDF/Ảnh -> TeX", str(err_msg))

        self._worker = run_in_background(_job, on_finished=_on_ok, on_error=_on_err)

    def _copy_out(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.txt_out.toPlainText())
        self.lbl_status.setText("Đã copy mã LaTeX vào clipboard.")

    def _save_and_open(self):
        body = self.txt_out.toPlainText().strip()
        if not body:
            QMessageBox.warning(self, "Chưa có nội dung", "Chưa có mã LaTeX để lưu. Hãy bấm 'Chuyển sang TeX' trước.")
            return
        src = Path(self.ed_file.text().strip()) if self.ed_file.text().strip() else app_root_dir() / "pdf_converted.pdf"
        stem = self.safe_stem_fn(src.stem) if self.safe_stem_fn else src.stem
        default_out = src.with_name(f"{stem}.tex")
        out_path, _ = QFileDialog.getSaveFileName(self, "Lưu tệp LaTeX", str(default_out), "LaTeX (*.tex)")
        if not out_path:
            return
        out_p = Path(out_path)
        full_doc = self.wrap_fn(body, out_p, title=src.stem) if self.wrap_fn else body
        out_p.write_text(full_doc, encoding="utf-8")
        open_pdf_file(str(out_p))
        QMessageBox.information(self, "Đã lưu & Mở TeXstudio", f"Đã lưu tệp LaTeX (kèm khung Main TeX Live 2019):\n{out_p}")
