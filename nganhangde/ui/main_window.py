import os
import sys
import tempfile
import webbrowser
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QRadioButton, QSpinBox,
    QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..ai.pdf_ocr import ocr_pdf_to_extest
from ..ai.providers import AIConfig
from ..converters.moodle_xml import export_moodle_xml
from ..converters.tex_to_word import export_questions_to_docx
from ..converters.word_to_tex import convert_docx_to_questions
from ..core.batch_tracker import list_exam_batches, record_exam_batch
from ..core.db import QuestionBankDB, format_import_type_summary
from ..core.drawgen import (
    IntervalSpec, generate_function_graph_tikz, generate_linear_inequality_region_tikz,
    generate_number_line_tikz, generate_solid_geometry_tikz, generate_variation_table_tikz,
)
from ..core.generator import ExamVariant, generate_exam_batch
from ..core.idmap_builtin import GDPT2018_MATH_CATALOG, describe_id6, export_id6_lookup_html
from ..core.matrix_cv7991 import ExamMatrix, MatrixRule
from ..core.parser import Question, parse_tex_questions
from ..core.review import audit_question
from ..core.similarity import find_similar_questions
from ..exporters.arena_host import LanArenaServer, detect_lan_ip
from ..exporters.omr_excel import OMR_PROFILES, export_answer_csv_bom, export_omr_excel
from ..exporters.online_gas import export_online_exam_bundle
from ..exporters.pdfbuild import compile_tex_to_pdf, detect_tex_compiler
from ..exporters.spec_docx_xlsx import export_cv7991_docx, export_cv7991_excel
from ..exporters.tex_exporter import export_exam_tex_suite
from ..paths import resource_path, user_data_dir
from .data_tree import WorkspaceDataTree
from .mylt_pro_tabs import AIStationTab, TopicBookTab
from .mylt2025_suite_tab import MyLT2025SuiteTab
from .tien_ich_2_tab import TienIch2Tab
from .doi_so_tab import DoiSoTab
from .mylt2026_exact_widgets import TuyChonDePanel, TienIch1Panel, VeHinhMyLT2026Tab, DoThiMyLT2026Tab
from .tron_de_mylt2026_tab import TaoDeTheoIdSubTab, TaoDeTuChonSubTab, TaoDeTheoFileSubTab, TaoDeTuongTuSubTab
from .hdsd_mylt2026_tab import HDSDTab, wrap_tab_with_hdsd
from .theme_manager import DEFAULT_THEME, THEMES, build_theme_qss
from .beamer_presentation_tab import BeamerPresentationTab
from ..core.updater import APP_VERSION, DEFAULT_GITHUB_REPO, check_for_updates, download_and_install_update
from ..core.licensing import load_license_status, get_machine_id
from .license_dialog import LicenseActivationDialog, configure_app_password_dialog, ensure_licensed_and_unlocked
from ..exporters.phieu_tltn_2025 import inject_phieu_into_tex
from .mylt2026_tabs_extra import BBTXDMyLT2026Tab, BieuDienNghiemMyLT2026Tab, SoanThaoMyLT2026Tab
from .cau_hoi_mylt2026_tab import CauHoiMyLT2026Tab
from .pdf_preview import make_qimage_from_pdf_page
from .presentation_mode import PresentationDialog
from .workers import run_in_background


class MyLT2026MainWindow(QMainWindow):
    """Giao diện 10 tab chuẩn bố cục MyLT 2026:
    Trộn đề | Câu hỏi | Ma trận | Tiện ích | Vẽ hình | Đồ thị | BBT&XD | Biểu diễn nghiệm | Soạn thảo | Thông tin
    """

    def __init__(self, db_path: str | None = None):
        super().__init__()
        self.setWindowTitle(f"Nganhangde_vu-pro v{APP_VERSION}")
        self.setMinimumSize(960, 620)
        self.resize(1240, 740)
        ico = resource_path("nganhangde/assets/app.ico")
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))

        self.db = QuestionBankDB(db_path or str(user_data_dir() / "nganhang_mylt2026.db"))
        self.current_questions: list[Question] = []
        self.source_file_questions: list[Question] = []
        self.last_variants: list[ExamVariant] = []
        self.loaded_matrix: ExamMatrix | None = None
        self.custom_omr_template: str | None = None
        self.arena_server: LanArenaServer | None = None
        self._id_groups: list[dict] = []

        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(6, 6, 6, 6)
        main_lay.setSpacing(6)

        self.tabs = QTabWidget()
        main_lay.addWidget(self.tabs, stretch=1)

        # Thanh nút dưới cùng bên phải (Tạo đề | Thoát) giống MyLT 2026
        bottom_bar = QHBoxLayout()
        self.lbl_status_global = QLabel("Sẵn sàng — Kho FTS5 đang hoạt động.")
        btn_create = QPushButton("Tạo đề")
        btn_create.setMinimumWidth(95)
        btn_create.clicked.connect(self._create_and_export_exam)
        btn_exit = QPushButton("Thoát")
        btn_exit.setMinimumWidth(85)
        btn_exit.clicked.connect(self.close)
        bottom_bar.addWidget(self.lbl_status_global, stretch=1)
        bottom_bar.addWidget(btn_create)
        bottom_bar.addWidget(btn_exit)
        main_lay.addLayout(bottom_bar)

        # 10 Tab chính theo đúng thứ tự MyLT 2026
        self._build_tab_1_tron_de()
        self._build_tab_2_cau_hoi()
        self._build_tab_3_ma_tran()
        self._build_tab_4_tien_ich()
        self._build_tab_5_ve_hinh()
        self._build_tab_6_do_thi()
        self._build_tab_7_bbt_xd()
        self._build_tab_8_bieu_dien_nghiem()
        self._build_tab_9_soan_thao()
        self._build_tab_10_thong_tin()
        self._build_tab_11_hdsd()
        self._apply_app_theme()
        from PySide6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence(Qt.Key_F1), self).activated.connect(self._open_hdsd_window)

        self._refresh_bank()
        self._refresh_tree()
        self._refresh_id_matrix_table()
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self._check_updates(silent=True))

    def closeEvent(self, event):
        if self.arena_server:
            self.arena_server.stop()
        self.db.close()
        super().closeEvent(event)

    def _get_ai_config(self) -> AIConfig:
        return AIConfig(
            provider=self.cb_prov.currentText(),
            api_key=self.inp_key.text().strip(),
            model=self.inp_model.text().strip(),
            thinking_budget=(self.sp_think.value() or None),
        )

    # ==========================================================================
    # TAB 1: TRỘN ĐỀ (5 sub-tabs giống hệt bố cục ảnh mẫu MyLT 2026)
    # ==========================================================================
    def _build_tab_1_tron_de(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setSpacing(6)

        # Khối chọn nguồn phía trên chuẩn MyLT 2026 v1.0.3.44
        src_box = QGroupBox()
        src_v = QVBoxLayout(src_box)
        src_v.setContentsMargins(8, 6, 8, 6)
        r_row = QHBoxLayout()
        self.rb_from_bank = QRadioButton("Từ ngân hàng câu hỏi")
        self.rb_from_files = QRadioButton("Từ Files. Chọn một hoặc nhiều file nguồn chứa câu hỏi")
        self.rb_from_bank.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self.rb_from_bank)
        bg.addButton(self.rb_from_files)
        r_row.addWidget(self.rb_from_bank)
        r_row.addWidget(self.rb_from_files)
        r_row.addStretch()
        src_v.addLayout(r_row)

        b_row = QHBoxLayout()
        b_open_bank = QPushButton("Mở ngân hàng")
        b_imp_q = QPushButton("Nhập câu hỏi")
        b_pick_files = QPushButton("Chọn files nguồn...")
        b_open_bank.clicked.connect(self._open_bank_db)
        b_imp_q.clicked.connect(self._import_tex)
        b_pick_files.clicked.connect(self._pick_source_tex_files)
        b_row.addWidget(b_open_bank)
        b_row.addWidget(b_imp_q)
        b_row.addWidget(b_pick_files)
        b_row.addStretch()
        src_v.addLayout(b_row)
        lay.addWidget(src_box)

        # 5 sub-tab chuẩn MyLT 2026 v1.0.3.44
        self.sub_tron = QTabWidget()
        lay.addWidget(self.sub_tron, stretch=1)

        self.tab_theo_id = TaoDeTheoIdSubTab(self)
        self.tab_tu_chon = TaoDeTuChonSubTab(self)
        self.tab_theo_file = TaoDeTheoFileSubTab(self)
        self.tab_tuong_tu = TaoDeTuongTuSubTab(self)
        self.tuy_chon_panel = TuyChonDePanel()

        # Giữ bí danh tương thích với các phương thức khác trong MainWindow
        self.tbl_id_pick = self.tab_theo_id.tbl
        self.lbl_picked_summary = self.tab_theo_id.lbl_picked
        self.tbl_manual = self.tab_tu_chon.tbl
        self.inp_title = self.tuy_chon_panel.ed_ky_thi
        self.sp_n = QSpinBox(); self.sp_n.setRange(1, 50); self.sp_n.setValue(4)
        self.sp_seed = QSpinBox(); self.sp_seed.setRange(1, 999999); self.sp_seed.setValue(2026)
        self.chk_balance = QCheckBox(); self.chk_balance.setChecked(True)
        self.chk_sort_level = QCheckBox()
        self.chk_qr = QCheckBox()
        self.cb_omr = QComboBox()
        for k, prof in OMR_PROFILES.items():
            self.cb_omr.addItem(f"{prof.label} ({k})", k)
        self.txt_file_list = QPlainTextEdit()
        self.txt_sim_log = QPlainTextEdit()

        self.sub_tron.addTab(wrap_tab_with_hdsd(self.tab_theo_id, "tron_id", self._open_hdsd_window), "Tạo đề theo ID")
        self.sub_tron.addTab(wrap_tab_with_hdsd(self.tab_tu_chon, "tron_tuchon", self._open_hdsd_window), "Tạo đề tự chọn")
        self.sub_tron.addTab(wrap_tab_with_hdsd(self.tab_theo_file, "tron_file", self._open_hdsd_window), "Tạo đề theo file")
        self.sub_tron.addTab(wrap_tab_with_hdsd(self.tab_tuong_tu, "tron_tuongtu", self._open_hdsd_window), "Tạo đề tương tự")
        self.sub_tron.addTab(wrap_tab_with_hdsd(self.tuy_chon_panel, "tron_tuychon", self._open_hdsd_window), "Tuỳ chọn đề")

        self._last_pick_subtab = 0
        self.sub_tron.currentChanged.connect(lambda idx: setattr(self, "_last_pick_subtab", idx) if idx < 4 else None)
        self.rb_from_bank.toggled.connect(lambda _: self._refresh_id_matrix_table())
        self.tabs.addTab(tab, "Trộn đề")

    # ==========================================================================
    # TAB 2: CÂU HỎI (FTS5, Cây dữ liệu, Rà soát CV 1239, Tìm gần trùng, F11)
    # ==========================================================================
    def _build_tab_2_cau_hoi(self):
        tab = QWidget()
        lay = QHBoxLayout(tab)
        sp = QSplitter(Qt.Horizontal)
        left, right = QWidget(), QWidget()
        lv, rv = QVBoxLayout(left), QVBoxLayout(right)

        self.tree = WorkspaceDataTree()
        self.tree.action_triggered.connect(self._on_tree_act)
        b_add = QPushButton("+ Thêm thư mục đề")
        b_add.clicked.connect(lambda: (self.db.add_workspace_node("Thư mục đề mới"), self._refresh_tree()))
        lv.addWidget(b_add); lv.addWidget(self.tree)

        bar = QHBoxLayout()
        self.inp_kw = QLineEdit(); self.inp_kw.setPlaceholderText("Tìm FTS5 không dấu (VD: tich phan, cap so cong)...")
        self.inp_id = QLineEdit(); self.inp_id.setPlaceholderText("Lọc ID (VD: 1D2*)")
        self.cb_qt = QComboBox(); self.cb_qt.addItems(["", "TN", "DS", "KQ", "TL"])
        bar.addWidget(self.inp_kw, stretch=2); bar.addWidget(self.inp_id, stretch=1); bar.addWidget(self.cb_qt)
        for lbl, fn in [
            ("Tìm", self._refresh_bank), ("Nhập .tex", self._import_tex), ("Xóa câu", self._delete_selected),
            ("Rà soát CV 1239", self._audit_qs), ("Tìm gần trùng", self._find_similar),
            ("Trình chiếu F11", self._present), ("Tra cứu ID6", self._open_id6),
        ]:
            b = QPushButton(lbl); b.clicked.connect(fn); bar.addWidget(b)
        rv.addLayout(bar)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["DB ID", "Mã ID6", "Loại", "Đã dùng", "Trích nội dung"])
        self.tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tbl.cellClicked.connect(self._on_row)
        self.lbl_id = QLabel("Chọn 1 câu để xem giải nghĩa ID6.")
        self.txt_tex = QPlainTextEdit(); self.txt_tex.setReadOnly(True)
        rv.addWidget(self.tbl, stretch=2); rv.addWidget(self.lbl_id); rv.addWidget(self.txt_tex, stretch=1)
        sp.addWidget(left); sp.addWidget(right); sp.setSizes([230, 1050])
        lay.addWidget(sp)
        cau_hoi_tabs = QTabWidget()
        self.cau_hoi_mylt = CauHoiMyLT2026Tab(self.db)
        cau_hoi_tabs.addTab(wrap_tab_with_hdsd(self.cau_hoi_mylt, "cauhoi_mylt", self._open_hdsd_window), "Quản lý câu hỏi (MyLT 2026)")
        cau_hoi_tabs.addTab(wrap_tab_with_hdsd(tab, "cauhoi_fts5", self._open_hdsd_window), "Kho nâng cao (Cây thư mục · FTS5 · F11)")
        self.tabs.addTab(cau_hoi_tabs, "Câu hỏi")

    # ==========================================================================
    # TAB 3: MA TRẬN (CV 7991 Excel/Word, Tạo ma trận ngược)
    # ==========================================================================
    def _build_tab_3_ma_tran(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        hb = QHBoxLayout()
        for lbl, fn in [
            ("Nạp Ma trận Excel (.xlsx)", self._load_matrix_xlsx),
            ("Tạo Ma trận ngược từ Kho", self._export_reverse_matrix),
            ("Xuất Phụ lục 1 & 2 CV 7991 (.xlsx / .docx)", self._export_cv7991_docs),
        ]:
            b = QPushButton(lbl); b.clicked.connect(fn); hb.addWidget(b)
        hb.addStretch()
        lay.addLayout(hb)
        self.txt_matrix_log = QPlainTextEdit(); self.txt_matrix_log.setReadOnly(True)
        lay.addWidget(self.txt_matrix_log)
        self.tabs.addTab(wrap_tab_with_hdsd(tab, "ma_tran", self._open_hdsd_window), "Ma trận")

    # ==========================================================================
    # TAB 4: TIỆN ÍCH (Word 2 chiều, AI OCR PDF, Trạm AI, Moodle, GAS, LAN, Chuyên đề)
    # ==========================================================================
    def _build_tab_4_tien_ich(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        sub = QTabWidget()

        # Sub 1: Word & OCR PDF
        w_conv = QWidget(); vc = QVBoxLayout(w_conv)
        hc = QHBoxLayout()
        for lbl, fn in [
            ("Nhập Word (.docx) → Kho", self._imp_word),
            ("Xuất câu đang lọc → Word (.docx)", self._exp_word),
            ("Mở hộp thoại PDF/Ảnh (chọn trang)", self._open_ocr_dialog),
        ]:
            b = QPushButton(lbl); b.clicked.connect(fn); hc.addWidget(b)
        hc.addStretch(); vc.addLayout(hc)

        hpdf = QHBoxLayout()
        self.ed_ocr_pdf = QLineEdit()
        self.ed_ocr_pdf.setPlaceholderText("Chọn tệp PDF hoặc Ảnh (.pdf, .png, .jpg) cần chuyển sang LaTeX...")
        b_pick_pdf = QPushButton("Chọn PDF/Ảnh...")
        b_pick_pdf.clicked.connect(self._pick_ocr_pdf)
        self.btn_run_pdf_tex = QPushButton("Chuyển PDF → LaTeX")
        self.btn_run_pdf_tex.setStyleSheet("font-weight: bold; padding: 4px 12px;")
        self.btn_run_pdf_tex.clicked.connect(self._run_ocr)
        b_save_ocr = QPushButton("Lưu .tex & Mở TeXstudio")
        b_save_ocr.clicked.connect(self._save_ocr_tex)
        for w_item in (QLabel("Tệp PDF/Ảnh:"), self.ed_ocr_pdf, b_pick_pdf, self.btn_run_pdf_tex, b_save_ocr):
            hpdf.addWidget(w_item, 1 if w_item is self.ed_ocr_pdf else 0)
        vc.addLayout(hpdf)

        self.txt_ocr_out = QPlainTextEdit()
        self.txt_ocr_out.setPlaceholderText("Kết quả chuyển PDF/Ảnh sang LaTeX sẽ hiển thị tại đây...")
        vc.addWidget(self.txt_ocr_out)
        # Hiển thị trực tiếp đầy đủ cả 8 tab chức năng như bản 7.3 với nhãn ngắn gọn để không bị tràn/ẩn
        sub.tabBar().setUsesScrollButtons(False)
        sub.tabBar().setStyleSheet(
            "QTabBar::tab { padding: 5px 8px; margin-right: 2px; font-weight: 700; }"
        )

        self.tien_ich_1 = TienIch1Panel(self)

        w_on = QWidget(); vo = QVBoxLayout(w_on)
        ho = QHBoxLayout()
        self.b_arena = QPushButton("Khởi chạy Đấu trường LAN (SSE)")
        self.b_arena.clicked.connect(self._toggle_arena)
        for lbl, fn in [("Xuất Moodle XML (MathJax + Cloze)", self._exp_moodle), ("Xuất Thi Online GAS (Code.gs)", self._exp_gas), ("Xem trước PDF (chống xé hình)", self._preview_pdf)]:
            b = QPushButton(lbl); b.clicked.connect(fn); ho.addWidget(b)
        ho.insertWidget(2, self.b_arena); ho.addStretch(); vo.addLayout(ho)
        self.lbl_arena = QLabel("Đấu trường LAN: Đang tắt.")
        self.lbl_pdf = QLabel("Khung xem trước trang PDF."); self.lbl_pdf.setAlignment(Qt.AlignCenter)
        vo.addWidget(self.lbl_arena); vo.addWidget(self.lbl_pdf, stretch=1)

        tien_ich_items = [
            (wrap_tab_with_hdsd(self.tien_ich_1, "tienich_1", self._open_hdsd_window), "Tiện ích 1", "Tiện ích 1 — Chuyển Word/PDF sang TeX, công cụ xử lý đề"),
            (wrap_tab_with_hdsd(TienIch2Tab(), "tienich_2", self._open_hdsd_window), "Tiện ích 2", "Tiện ích 2 — Tách file, gộp file, đổi ID, chuẩn hoá TeX"),
            (wrap_tab_with_hdsd(w_conv, "tienich_word_ocr", self._open_hdsd_window), "Word/PDF ↔ TeX", "Word ↔ LaTeX & AI OCR PDF"),
            (wrap_tab_with_hdsd(w_on, "tienich_online", self._open_hdsd_window), "Thi Online", "Moodle XML · Thi Online GAS · Đấu trường LAN · Xem PDF"),
            (wrap_tab_with_hdsd(TopicBookTab(self.db), "tienich_chuyende", self._open_hdsd_window), "Chuyên đề", "Biên soạn Chuyên đề có mục lục (.tex / PDF)"),
            (wrap_tab_with_hdsd(AIStationTab(self.db, self._get_ai_config), "tienich_ai", self._open_hdsd_window), "Trạm AI", "Trạm AI — Gán ID6 · Sinh câu tương tự · Chấm tự luận"),
            (wrap_tab_with_hdsd(MyLT2025SuiteTab(self.db), "tienich_suite", self._open_hdsd_window), "Phiếu 2025 · TikZ", "Phiếu 2025 · Tikz2Pic · Blogger · Config"),
            (wrap_tab_with_hdsd(BeamerPresentationTab(self), "tienich_beamer", self._open_hdsd_window), "Beamer", "Trình chiếu đề bằng Main Beamer (xuất out/ & biên dịch PDF)"),
        ]
        for idx_t, (w_tab, short_lbl, tip_lbl) in enumerate(tien_ich_items):
            sub.addTab(w_tab, short_lbl)
            sub.setTabToolTip(idx_t, tip_lbl)

        lay.addWidget(sub)
        self.tabs.addTab(tab, "Tiện ích")

    # ==========================================================================
    # TAB 5, 6, 7, 8: BỐN CÔNG CỤ TOÁN HỌC TIKZ TÁCH RIÊNG NHƯ MYLT 2026
    # ==========================================================================
    def _make_tikz_workspace(self, form_widget: QWidget, gen_fn):
        w = QWidget()
        lay = QHBoxLayout(w)
        left, right = QVBoxLayout(), QVBoxLayout()
        code_box = QPlainTextEdit()
        img_lbl = QLabel("Khung xem trước hình TikZ sau khi biên dịch.")
        img_lbl.setAlignment(Qt.AlignCenter); img_lbl.setMinimumWidth(420)
        b_gen = QPushButton("Sinh mã TikZ")
        b_prev = QPushButton("Biên dịch xem trước")
        b_gen.clicked.connect(lambda: code_box.setPlainText(gen_fn()))
        b_prev.clicked.connect(lambda: self._compile_tikz_preview(code_box, img_lbl, gen_fn))
        hb = QHBoxLayout(); hb.addWidget(b_gen); hb.addWidget(b_prev)
        left.addWidget(form_widget); left.addLayout(hb); left.addWidget(code_box, stretch=1)
        right.addWidget(img_lbl, stretch=1)
        lay.addLayout(left, stretch=3); lay.addLayout(right, stretch=2)
        return w

    def _compile_tikz_preview(self, code_box: QPlainTextEdit, img_lbl: QLabel, gen_fn):
        code = code_box.toPlainText().strip() or gen_fn()
        code_box.setPlainText(code)
        tmp_dir = Path(tempfile.mkdtemp(prefix="tikz_prev_"))
        tex_f = tmp_dir / "fig.tex"
        tex_f.write_text(r"\documentclass[border=4pt]{standalone}\usepackage{amsmath,amssymb,tikz,tkz-tab}\usetikzlibrary{calc,patterns}\begin{document}" + "\n" + code + "\n\\end{document}\n", encoding="utf-8")
        img_lbl.setText("Đang biên dịch hình TikZ...")

        def _done(res):
            if res.success and res.pdf_path:
                qimg, _ = make_qimage_from_pdf_page(res.pdf_path, 0, 2.0)
                img_lbl.setPixmap(QPixmap.fromImage(qimg).scaled(img_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                img_lbl.setText("Lỗi biên dịch TikZ:\n" + "\n".join(d.summary for d in res.diagnostics))

        run_in_background(compile_tex_to_pdf, str(tex_f), on_finished=_done, on_error=lambda e: img_lbl.setText(e))

    def _build_tab_5_ve_hinh(self):
        fw = QWidget(); f = QFormLayout(fw)
        self.s_type = QComboBox(); self.s_type.addItems(["pyramid_sabcd_perp", "pyramid_sabc_perp", "prism_triangular"])
        self.s_h = QDoubleSpinBox(); self.s_h.setRange(1, 10); self.s_h.setValue(3.5)
        self.s_w = QDoubleSpinBox(); self.s_w.setRange(1, 10); self.s_w.setValue(4.2)
        f.addRow("Loại khối 3D:", self.s_type); f.addRow("Chiều cao:", self.s_h); f.addRow("Độ rộng đáy:", self.s_w)
        self.tabs.addTab(wrap_tab_with_hdsd(VeHinhMyLT2026Tab(), "ve_hinh", self._open_hdsd_window), "Vẽ hình")

    def _build_tab_6_do_thi(self):
        fw = QWidget(); f = QFormLayout(fw)
        self.g_expr = QLineEdit("(\\x+1)/(\\x-1)")
        self.g_xmin = QDoubleSpinBox(); self.g_xmin.setRange(-20, 20); self.g_xmin.setValue(-4)
        self.g_xmax = QDoubleSpinBox(); self.g_xmax.setRange(-20, 20); self.g_xmax.setValue(5)
        self.g_ax = QLineEdit("1"); self.g_ay = QLineEdit("1"); self.g_sh = QLineEdit("2, 4")
        f.addRow("Biểu thức (dùng \\x):", self.g_expr); f.addRow("x min:", self.g_xmin); f.addRow("x max:", self.g_xmax)
        f.addRow("Tiệm cận đứng x =:", self.g_ax); f.addRow("Tiệm cận ngang/xiên y =:", self.g_ay); f.addRow("Tô miền tích phân [a, b]:", self.g_sh)
        gen = lambda: generate_function_graph_tikz(
            self.g_expr.text(), xmin=self.g_xmin.value(), xmax=self.g_xmax.value(),
            asymptote_x=(float(self.g_ax.text()) if self.g_ax.text().strip() else None),
            asymptote_y_expr=(self.g_ay.text().strip() or None),
            shade_integral=(tuple(float(x.strip()) for x in self.g_sh.text().split(",", 1)) if "," in self.g_sh.text() else None),
        )
        self.tabs.addTab(wrap_tab_with_hdsd(DoThiMyLT2026Tab(), "do_thi", self._open_hdsd_window), "Đồ thị")

    def _build_tab_7_bbt_xd(self):
        fw = QWidget(); f = QFormLayout(fw)
        self.b_x = QLineEdit(r"$-\infty$, $0$, $2$, $+\infty$")
        self.b_yp = QLineEdit(r", +, 0, -, 0, +, ")
        self.b_y = QLineEdit(r"-/$-\infty$, +/$4$, -/$0$, +/$+\infty$")
        f.addRow("Dòng x:", self.b_x); f.addRow("Dòng y' (tkzTabLine):", self.b_yp); f.addRow("Dòng y (tkzTabVar):", self.b_y)
        gen = lambda: generate_variation_table_tikz([x.strip() for x in self.b_x.text().split(",")], [x.strip() for x in self.b_yp.text().split(",")], [x.strip() for x in self.b_y.text().split(",")])
        self.tabs.addTab(wrap_tab_with_hdsd(BBTXDMyLT2026Tab(), "bbt_xd", self._open_hdsd_window), "BBT&XD")

    def _build_tab_8_bieu_dien_nghiem(self):
        fw = QWidget(); f = QFormLayout(fw)
        self.n_iv = QLineEdit("-2, 3")
        self.n_ineq = QLineEdit("1,1,2,<=; 1,0,0,>=")
        f.addRow("Khoảng trục số [a, b):", self.n_iv); f.addRow("Hệ BPT (a,b,c,op cách ';'):", self.n_ineq)

        def _gen():
            a, b = [float(x.strip()) for x in self.n_iv.text().split(",", 1)]
            ineqs = [(float(p[0]), float(p[1]), float(p[2]), p[3].strip()) for s in self.n_ineq.text().split(";") if s.strip() for p in [s.split(",")]]
            return generate_number_line_tikz([IntervalSpec(a, b, True, False)]) + "\n\n" + generate_linear_inequality_region_tikz(ineqs)

        self.tabs.addTab(wrap_tab_with_hdsd(BieuDienNghiemMyLT2026Tab(), "bieu_dien_nghiem", self._open_hdsd_window), "Biểu diễn nghiệm")

    # ==========================================================================
    # TAB 9: SOẠN THẢO (Soạn ex_test nhanh + biên dịch PDF + chẩn đoán .log)
    # ==========================================================================
    def _build_tab_9_soan_thao(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        hb = QHBoxLayout()
        for lbl, snip in [
            ("+ Câu TN", "\\begin{ex}\nNội dung câu hỏi\n\\choice[4]\n{\\True Đáp án A}\n{Đáp án B}\n{Đáp án C}\n{Đáp án D}\n\\loigiai{\nLời giải.\n}\n\\end{ex}\n"),
            ("+ Câu Đ/S", "\\begin{ex}\nNội dung câu hỏi\n\\choiceTF[1t]\n{\\True Mệnh đề a}\n{Mệnh đề b}\n{\\True Mệnh đề c}\n{Mệnh đề d}\n\\loigiai{\n\\begin{itemchoice}\n\\itemch Đúng.\n\\itemch Sai.\n\\itemch Đúng.\n\\itemch Sai.\n\\end{itemchoice}\n}\n\\end{ex}\n"),
            ("+ Câu TLN", "\\begin{ex}\nNội dung câu hỏi\n\\shortans[oly]{$1{,}5$}\n\\loigiai{\nLời giải.\n}\n\\end{ex}\n"),
        ]:
            b = QPushButton(lbl); b.clicked.connect(lambda _=False, s=snip: self.txt_editor.insertPlainText(s)); hb.addWidget(b)
        b_save_bank = QPushButton("Lưu vào Ngân hàng")
        b_save_bank.clicked.connect(self._save_editor_to_bank)
        b_comp = QPushButton("Biên dịch PDF & Chẩn đoán .log")
        b_comp.clicked.connect(self._compile_pdf)
        hb.addWidget(b_save_bank); hb.addWidget(b_comp); hb.addStretch()
        lay.addLayout(hb)
        self.txt_editor = QPlainTextEdit()
        lay.addWidget(self.txt_editor, stretch=1)
        self.tabs.addTab(wrap_tab_with_hdsd(SoanThaoMyLT2026Tab(tab), "soan_thao", self._open_hdsd_window), "Soạn thảo")

    # ==========================================================================
    # TAB 10: THÔNG TIN (Cài đặt AI đa nền tảng & Hệ thống)
    # ==========================================================================
    def _build_tab_10_thong_tin(self):
        from ..core.config_manager import ConfigManager as _CfgUpd
        _cu = _CfgUpd()
        tab = QWidget()
        f = QFormLayout(tab)
        self.cb_prov = QComboBox(); self.cb_prov.addItems(["gemini", "openai", "claude", "deepseek", "grok"])
        self.inp_key = QLineEdit(); self.inp_key.setEchoMode(QLineEdit.Password)
        self.inp_model = QLineEdit("gemini-2.5-flash")
        self.sp_think = QSpinBox(); self.sp_think.setRange(0, 24576); self.sp_think.setValue(0); self.sp_think.setSpecialValueText("Mặc định (tự động)")

        self.ed_update_repo = QLineEdit(_cu.get("Update", "github_repo", DEFAULT_GITHUB_REPO))
        self.chk_auto_update = QCheckBox("Tự động kiểm tra cập nhật khi mở phần mềm")
        self.chk_auto_update.setChecked(_cu.get("Update", "auto_check", "1") == "1")
        self.chk_auto_update.stateChanged.connect(self._save_update_prefs)
        self.ed_update_repo.editingFinished.connect(self._save_update_prefs)

        upd_row = QHBoxLayout()
        self.btn_check_upd = QPushButton("Kiểm tra cập nhật ngay")
        self.btn_check_upd.clicked.connect(lambda: self._check_updates(silent=False))
        self.lbl_upd_status = QLabel(f"Phiên bản hiện tại: v{APP_VERSION}")
        upd_row.addWidget(self.btn_check_upd)
        upd_row.addWidget(self.lbl_upd_status, 1)

        _lic = load_license_status()
        lic_row = QHBoxLayout()
        self.lbl_lic_info = QLabel(f"Mã máy: {_lic.machine_id} | Hạn dùng: {_lic.expiry_display}" + (f" | Chủ sở hữu: {_lic.owner}" if _lic.owner else ""))
        b_copy_mid = QPushButton("Copy Mã máy")
        b_copy_mid.clicked.connect(lambda: (QApplication.clipboard().setText(get_machine_id()), QMessageBox.information(self, "Mã máy", f"Đã sao chép Mã máy: {get_machine_id()}")))
        b_change_key = QPushButton("Kích hoạt / Đổi Key")
        b_change_key.clicked.connect(self._open_license_dialog)
        b_set_pw = QPushButton("Cài / Đổi mật khẩu mở app")
        b_set_pw.clicked.connect(lambda: configure_app_password_dialog(self))
        lic_row.addWidget(self.lbl_lic_info, 1)
        lic_row.addWidget(b_copy_mid)
        lic_row.addWidget(b_change_key)
        lic_row.addWidget(b_set_pw)

        f.addRow("Phiên bản:", QLabel(f"Nganhangde_vu-pro v{APP_VERSION} — Bản Tác giả (GDPT 2018 · CV 7991 · CV 1239)"))
        f.addRow("Bản quyền & Bảo mật:", lic_row)
        self.cbo_theme = QComboBox()
        self.cbo_theme.addItems(list(THEMES.keys()))
        saved_theme = _cu.get("UI", "theme", DEFAULT_THEME)
        if saved_theme in THEMES:
            self.cbo_theme.setCurrentText(saved_theme)
        self.cbo_theme.currentTextChanged.connect(self._on_theme_changed)

        f.addRow("Giao diện & Màu nền:", self.cbo_theme)
        f.addRow("Kho GitHub cập nhật:", self.ed_update_repo)
        f.addRow("Tự động cập nhật:", self.chk_auto_update)
        f.addRow("Cập nhật phần mềm:", upd_row)
        f.addRow("Nhà cung cấp AI:", self.cb_prov)
        f.addRow("API Key:", self.inp_key)
        f.addRow("Model:", self.inp_model)
        f.addRow("Ngân sách suy luận (thinking_budget):", self.sp_think)
        f.addRow("Trình biên dịch TeX:", QLabel(detect_tex_compiler() or "Chưa phát hiện MiKTeX / TeX Live"))
        f.addRow("Cơ sở dữ liệu FTS5:", QLabel(self.db.db_path))
        self.tabs.addTab(wrap_tab_with_hdsd(tab, "thong_tin", self._open_hdsd_window), "Thông tin")

    def _open_license_dialog(self):
        from PySide6.QtWidgets import QDialog
        dlg = LicenseActivationDialog(load_license_status(), self)
        if dlg.exec() == QDialog.Accepted:
            st = load_license_status()
            self.lbl_lic_info.setText(f"Mã máy: {st.machine_id} | Hạn dùng: {st.expiry_display}" + (f" | Chủ sở hữu: {st.owner}" if st.owner else ""))

    def _save_update_prefs(self):
        from ..core.config_manager import ConfigManager as _CfgUpd
        c = _CfgUpd()
        c.set("Update", "github_repo", self.ed_update_repo.text().strip() or DEFAULT_GITHUB_REPO)
        c.set("Update", "auto_check", "1" if self.chk_auto_update.isChecked() else "0")
        c.save()

    def _check_updates(self, silent: bool = False):
        if silent and hasattr(self, "chk_auto_update") and not self.chk_auto_update.isChecked():
            return
        repo = self.ed_update_repo.text().strip() if hasattr(self, "ed_update_repo") else DEFAULT_GITHUB_REPO
        if not silent and hasattr(self, "lbl_upd_status"):
            self.lbl_upd_status.setText("Đang kiểm tra bản mới trên GitHub...")
            self.btn_check_upd.setEnabled(False)

        def _on_ok(info):
            if hasattr(self, "btn_check_upd"):
                self.btn_check_upd.setEnabled(True)
            if info.has_update:
                if hasattr(self, "lbl_upd_status"):
                    self.lbl_upd_status.setText(f"Có phiên bản mới: v{info.latest_version}!")
                notes_preview = (info.release_notes[:400] + "...") if len(info.release_notes) > 400 else info.release_notes
                ans = QMessageBox.question(
                    self,
                    "Có bản cập nhật mới",
                    f"Phiên bản hiện tại: v{info.current_version}\n"
                    f"Phiên bản mới nhất: v{info.latest_version}\n\n"
                    + (f"Nội dung cập nhật:\n{notes_preview}\n\n" if notes_preview else "")
                    + "Bạn có muốn tải và tự động cập nhật ngay bây giờ không?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if ans == QMessageBox.Yes:
                    self._apply_update(info)
            else:
                if hasattr(self, "lbl_upd_status"):
                    self.lbl_upd_status.setText(f"Bạn đang dùng phiên bản mới nhất (v{info.current_version}).")
                if not silent:
                    QMessageBox.information(self, "Kiểm tra cập nhật", f"Bạn đang sử dụng phiên bản mới nhất (v{info.current_version}).")

        def _on_err(err_msg: str):
            if hasattr(self, "btn_check_upd"):
                self.btn_check_upd.setEnabled(True)
            if not silent:
                if hasattr(self, "lbl_upd_status"):
                    self.lbl_upd_status.setText("Chưa kết nối được tới GitHub Releases.")
                QMessageBox.warning(self, "Không thể kiểm tra cập nhật", f"Không kiểm tra được bản mới từ GitHub ({repo}):\n{err_msg}")

        self._upd_worker = run_in_background(check_for_updates, repo, on_finished=_on_ok, on_error=_on_err)

    def _apply_update(self, info):
        from PySide6.QtWidgets import QProgressDialog
        dlg = QProgressDialog(f"Đang tải bản cập nhật v{info.latest_version}...", None, 0, 0, self)
        dlg.setWindowTitle("Đang cập nhật phần mềm")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.show()

        def _on_done(res):
            dlg.close()
            ok, msg = res
            if ok:
                QMessageBox.information(self, "Cập nhật thành công", msg)
                self.close()
            else:
                QMessageBox.information(self, "Cập nhật phần mềm", msg)

        def _on_err(err_msg: str):
            dlg.close()
            QMessageBox.critical(self, "Lỗi cập nhật", str(err_msg))

        self._upd_dl_worker = run_in_background(download_and_install_update, info, on_finished=_on_done, on_error=_on_err)

    def _build_tab_11_hdsd(self):
        from PySide6.QtGui import QColor
        self.hdsd_tab = HDSDTab(self)
        idx = self.tabs.addTab(self.hdsd_tab, "HDSD")
        self.tabs.tabBar().setTabTextColor(idx, QColor("#ffffff"))
        # Tô nổi bật tab HDSD (tab cuối cùng) bằng màu xanh lá để người dùng nhận diện ngay
        self.tabs.tabBar().setObjectName("MainTopTabBar")
        self.tabs.tabBar().setStyleSheet(
            "QTabBar::tab:last {"
            "  background-color: #16a34a;"
            "  color: #ffffff;"
            "  font-weight: bold;"
            "  border: 1px solid #15803d;"
            "  border-top-left-radius: 4px;"
            "  border-top-right-radius: 4px;"
            "  padding: 5px 14px;"
            "}"
            "QTabBar::tab:last:hover {"
            "  background-color: #15803d;"
            "}"
            "QTabBar::tab:last:selected {"
            "  background-color: #15803d;"
            "  color: #ffffff;"
            "}"
        )
        self._style_all_hdsd_buttons()

    def _apply_app_theme(self, theme_name: str | None = None):
        from ..core.config_manager import ConfigManager as _CfgTheme
        name = theme_name or _CfgTheme().get("UI", "theme", DEFAULT_THEME)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_theme_qss(name))
        self._style_all_hdsd_buttons()

    def _on_theme_changed(self, theme_name: str):
        from ..core.config_manager import ConfigManager as _CfgTheme
        c = _CfgTheme()
        c.set("UI", "theme", theme_name)
        c.save()
        self._apply_app_theme(theme_name)

    def _style_all_hdsd_buttons(self):
        """Tô màu xanh lá đồng bộ cho toàn bộ các nút HDSD trong các tab chức năng."""
        green_btn_css = (
            "QPushButton { background-color: #16a34a; border: 1px solid #15803d; color: #ffffff; "
            "font-weight: 700; padding: 3px 10px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #15803d; }"
            "QPushButton:pressed { background-color: #166534; }"
        )
        for btn in self.findChildren(QPushButton):
            t = btn.text().strip()
            if t == "HDSD" or t.startswith("HDSD "):
                btn.setStyleSheet(green_btn_css)

    def _open_hdsd_window(self):
        if hasattr(self, "hdsd_tab"):
            self.hdsd_tab.open_standalone_window()

    # ==========================================================================
    # NGHIỆP VỤ BẢNG CHỌN ID & TẠO ĐỀ
    # ==========================================================================
    def _refresh_id_matrix_table(self):
        if hasattr(self, "tab_theo_id"):
            self.tab_theo_id.refresh_table()
        if hasattr(self, "tab_tu_chon"):
            self.tab_tu_chon.refresh_table()

    def _collect_rules_from_id_table(self) -> list[MatrixRule]:
        return []

    @staticmethod
    def _sort_questions_by_mylt_order(qs: list[Question], sort_order: list[str]) -> list[Question]:
        if not sort_order:
            return qs
        lv_rank = {"N": 0, "H": 1, "V": 2, "C": 3}

        def _key(q: Question):
            code = (q.primary_id or "").upper()
            parts = []
            for crit in sort_order:
                if crit == "Theo lớp":
                    parts.append(code[0] if len(code) >= 1 else "Z")
                elif crit == "Theo môn":
                    parts.append(code[1] if len(code) >= 2 else "Z")
                elif crit == "Theo chương":
                    parts.append(code[2] if len(code) >= 3 else "Z")
                elif crit == "Theo mức độ":
                    parts.append(str(lv_rank.get(code[3] if len(code) >= 4 else "N", 9)))
                elif crit == "Theo bài":
                    parts.append(code[4] if len(code) >= 5 else "Z")
                elif crit == "Theo dạng":
                    parts.append(code.split("-")[-1] if "-" in code else "Z")
            return tuple(parts)

        return sorted(qs, key=_key)

    def _create_and_export_exam(self):
        """Nút Tạo đề ở góc dưới phải — thực thi đầy đủ 5 sub-tab chuẩn MyLT 2026."""
        try:
            opts = self.tuy_chon_panel.get_options() if hasattr(self, "tuy_chon_panel") else {}
            n_exams = opts.get("num_exams", self.sp_n.value())
            c_digits = opts.get("code_digits", 4)
            code_step = max(1, int(opts.get("code_step", 1)))
            custom_codes = opts.get("custom_codes", [])
            start_c = 101 if c_digits == 3 else 1001
            bal_abcd = opts.get("balance_abcd", self.chk_balance.isChecked())
            sort_order = opts.get("sort_order", [])
            sort_lv = opts.get("sort_by_level", self.chk_sort_level.isChecked())
            keep_original = opts.get("keep_original", False)
            exam_title = opts.get("title", self.inp_title.text())

            cur_sub = self.sub_tron.currentIndex()
            active_pick_tab = cur_sub if cur_sub < 4 else getattr(self, "_last_pick_subtab", 0)
            seed_val = self.sp_seed.value()

            def _collect_from_tab(idx: int) -> list[Question]:
                if idx == 0 and hasattr(self, "tab_theo_id"):
                    return self.tab_theo_id.collect_selected_questions(seed=seed_val)
                if idx == 1 and hasattr(self, "tab_tu_chon"):
                    return self.tab_tu_chon.collect_selected_questions()
                if idx == 2 and hasattr(self, "tab_theo_file"):
                    return self.tab_theo_file.collect_selected_questions(seed=seed_val)
                if idx == 3 and hasattr(self, "tab_tuong_tu"):
                    return self.tab_tuong_tu.collect_selected_questions()
                return []

            sub_selected = _collect_from_tab(active_pick_tab)
            if not sub_selected:
                for fallback_idx in (0, 1, 2, 3):
                    if fallback_idx != active_pick_tab:
                        sub_selected = _collect_from_tab(fallback_idx)
                        if sub_selected:
                            break

            if sub_selected:
                if sort_order:
                    sub_selected = self._sort_questions_by_mylt_order(sub_selected, sort_order)
                self.last_variants = generate_exam_batch(
                    n_exams, seed_val, base_questions=sub_selected,
                    code_digits=c_digits, start_code=start_c, balance_abcd=bal_abcd, sort_by_level=sort_lv,
                )
            elif self.rb_from_files.isChecked() and self.source_file_questions:
                base_qs = self._sort_questions_by_mylt_order(list(self.source_file_questions), sort_order) if sort_order else list(self.source_file_questions)
                self.last_variants = generate_exam_batch(
                    n_exams, seed_val, base_questions=base_qs,
                    code_digits=c_digits, start_code=start_c, balance_abcd=bal_abcd, sort_by_level=sort_lv,
                )
            elif self.loaded_matrix is not None:
                self.last_variants = generate_exam_batch(
                    n_exams, seed_val, db=self.db, matrix=self.loaded_matrix,
                    code_digits=c_digits, start_code=start_c, balance_abcd=bal_abcd, sort_by_level=sort_lv,
                )
            elif self.current_questions:
                base_qs = self._sort_questions_by_mylt_order(list(self.current_questions), sort_order) if sort_order else list(self.current_questions)
                self.last_variants = generate_exam_batch(
                    n_exams, seed_val, base_questions=base_qs,
                    code_digits=c_digits, start_code=start_c, balance_abcd=bal_abcd, sort_by_level=sort_lv,
                )
            else:
                QMessageBox.warning(self, "Tạo đề", "Chưa có câu hỏi nào được chọn. Hãy chọn câu hỏi ở tab Tạo đề theo ID / Tự chọn / Theo file / Tương tự trước.")
                return

            # Áp dụng Mã đề tự nhập / Mã đề cách / Giữ nguyên đề chuẩn MyLT 2026
            for vi, var in enumerate(self.last_variants):
                if custom_codes and vi < len(custom_codes):
                    var.code = custom_codes[vi]
                elif code_step > 1:
                    var.code = str(start_c + vi * code_step)
                if keep_original and sub_selected:
                    var.questions = list(sub_selected)

            from ..paths import app_root_dir
            d = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất trọn bộ đề thi", str(app_root_dir()))
            if not d:
                return
            tpl_custom = opts.get("header_file", "")
            tpl = Path(tpl_custom) if (tpl_custom and Path(tpl_custom).exists()) else resource_path("nganhangde/templates/de_thi.tex")
            embed_qr = opts.get("embed_qr", False) or self.chk_qr.isChecked()
            tres = export_exam_tex_suite(self.last_variants, d, exam_title, str(tpl) if tpl.exists() else None, embed_qr_in_solution=embed_qr)

            # Tự động nhúng Phiếu TLTN 2025 nếu người dùng chọn
            phieu_mode = opts.get("phieu_mode", "")
            if "2025" in phieu_mode:
                pkey = "full" if "2 trang" in phieu_mode else "1mat"
                for fp_str in tres.created_files:
                    fp = Path(fp_str)
                    if fp.suffix.lower() == ".tex" and "loi_giai" not in fp.stem.lower():
                        try:
                            updated = inject_phieu_into_tex(fp.read_text(encoding="utf-8", errors="replace"), template_key=pkey, copy_to_dir=fp.parent)
                            fp.write_text(updated, encoding="utf-8")
                        except Exception:
                            pass

            # Tự động biên dịch PDF nếu tick "Biên dịch đề"
            compiled_pdfs = 0
            if opts.get("compile_pdf", False):
                for fp_str in tres.created_files:
                    fp = Path(fp_str)
                    if fp.suffix.lower() == ".tex":
                        bres = compile_tex_to_pdf(str(fp), compiler="pdflatex", passes=1)
                        if bres.success:
                            compiled_pdfs += 1

            prefix = opts.get("output_name", "").strip()
            csv_name = f"{prefix}_dap_an_utf8_bom.csv" if prefix else "dap_an_utf8_bom.csv"
            omr_name = f"{prefix}_dap_an_omr_2025.xlsx" if prefix else "dap_an_omr_2025.xlsx"
            export_answer_csv_bom(self.last_variants, os.path.join(d, csv_name))
            ow = export_omr_excel(self.last_variants, os.path.join(d, omr_name), exam_title, self.cb_omr.currentData(), template_xlsx=self.custom_omr_template)
            mat_out = self.loaded_matrix or ExamMatrix.from_exam_questions(self.last_variants[0].questions, exam_title)
            export_cv7991_excel(mat_out, os.path.join(d, "ma_tran_dac_ta_cv7991.xlsx"))
            try:
                export_cv7991_docx(mat_out, os.path.join(d, "ma_tran_dac_ta_cv7991.docx"))
            except RuntimeError:
                pass
            record_exam_batch(self.db, exam_title, seed_val, self.last_variants, mat_out)
            self._refresh_bank()
            self.lbl_status_global.setText(f"Đã xuất {len(self.last_variants)} mã đề tại: {d}")
            QMessageBox.information(
                self,
                "Tạo đề thành công",
                f"Đã xuất {len(tres.created_files)} tệp (.tex, OMR, CSV BOM, Ma trận & Đặc tả CV 7991) và biên dịch {compiled_pdfs} tệp PDF vào:\n{d}"
                + ("\n\nCảnh báo:\n- " + "\n- ".join(tres.warnings + ow) if (tres.warnings or ow) else ""),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Lỗi tạo đề", str(exc))

    def _open_bank_db(self):
        p, _ = QFileDialog.getOpenFileName(self, "Mở kho SQLite (.db)", "", "SQLite DB (*.db)")
        if p:
            self.db.close()
            self.db = QuestionBankDB(p)
            self._refresh_bank(); self._refresh_tree(); self._refresh_id_matrix_table()
            self.lbl_status_global.setText(f"Đang mở kho: {p}")

    def _pick_source_tex_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn file .tex nguồn", "", "LaTeX (*.tex)")
        if not paths:
            return
        self.rb_from_files.setChecked(True)
        self.source_file_questions = []
        for p in paths:
            self.source_file_questions.extend(parse_tex_questions(Path(p).read_text(encoding="utf-8", errors="ignore"), auto_normalize=True))
        if hasattr(self, "tab_theo_file"):
            self.tab_theo_file.load_paths([Path(p) for p in paths], append=False)
        self._refresh_id_matrix_table()
        self.lbl_status_global.setText(f"Đã nạp {len(self.source_file_questions)} câu từ {len(paths)} file .tex.")

    def _build_similar_from_tex(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn đề gốc .tex", "", "LaTeX (*.tex)")
        if not p:
            return
        qs = parse_tex_questions(Path(p).read_text(encoding="utf-8", errors="ignore"))
        self.loaded_matrix = ExamMatrix.from_exam_questions(qs, f"Tương tự {Path(p).stem}")
        self.txt_sim_log.setPlainText(f"Đã phân tích {len(qs)} câu từ {Path(p).name}.\nCơ cấu rút đề tương tự: {self.loaded_matrix.total_by_type()}\nBấm nút 'Tạo đề' bên dưới để rút đề tương tự từ kho.")

    def _refresh_tree(self):
        nodes = self.db.list_workspace_nodes()
        if not nodes:
            rid = self.db.add_workspace_node("Năm học 2026–2027")
            self.db.add_workspace_node("Lớp 11 / Học kì I", parent_id=rid)
            nodes = self.db.list_workspace_nodes()
        self.tree.load_nodes(nodes)

    def _on_tree_act(self, key: str, nid: int):
        if key == "delete_node":
            self.db.delete_workspace_node(nid); self._refresh_tree()
        elif key == "open_view":
            bs = list_exam_batches(self.db, limit=10)
            msg = "\n".join(f"- {b['name']} ({len(b['codes'])} mã đề, {b['question_count']} câu)" for b in bs)
            QMessageBox.information(self, "Lịch sử đợt ra đề", msg or "Chưa có đợt ra đề nào.")

    def _refresh_bank(self):
        rows = self.db.search(self.inp_kw.text(), self.inp_id.text(), self.cb_qt.currentText(), limit=400)
        self.current_questions = []
        self.tbl.setRowCount(len(rows))
        if hasattr(self, 'tab_tu_chon'):
            self.tab_tu_chon.refresh_table()
        for ri, row in enumerate(rows):
            ps = parse_tex_questions(row["raw"])
            if ps:
                self.current_questions.append(ps[0])
            stem_short = (row["stem"] or "")[:100].replace("\n", " ")
            for ci, v in enumerate([str(row["id"]), row["qid"], row["qtype"], str(row["used_count"]), stem_short]):
                self.tbl.setItem(ri, ci, QTableWidgetItem(v))
            chk = QTableWidgetItem(); chk.setCheckState(Qt.Checked)
            self.tbl_manual.setItem(ri, 0, chk)
            for ci, v in enumerate([row["qid"], row["qtype"], str(row["used_count"]), stem_short], 1):
                self.tbl_manual.setItem(ri, ci, QTableWidgetItem(v))

    def _on_row(self, ri: int, _ci: int):
        if 0 <= ri < len(self.current_questions):
            q = self.current_questions[ri]
            self.lbl_id.setText(describe_id6(q.primary_id) if q.primary_id else "Chưa gắn mã ID6")
            self.txt_tex.setPlainText(q.to_latex(True))

    def _import_tex(self):
        from .import_bank_dialog import ImportBankDialog
        dlg = ImportBankDialog(self.db, self)
        dlg.exec()
        if dlg.imported_count > 0:
            self._refresh_bank()
            self._refresh_id_matrix_table()
            if hasattr(self, "cau_hoi_mylt") and self.cau_hoi_mylt.rb_bank.isChecked():
                self.cau_hoi_mylt._load_questions()

    def _load_sample(self):
        sp = resource_path("sample_data/de_mau_toan11_2026.tex")
        if not sp.exists():
            QMessageBox.warning(self, "Dữ liệu mẫu", "Không tìm thấy sample_data/de_mau_toan11_2026.tex.")
            return
        st = self.db.bulk_import(parse_tex_questions(sp.read_text(encoding="utf-8"), auto_normalize=True), asset_base_dir=str(sp.parent))
        self._refresh_bank(); self._refresh_id_matrix_table()
        QMessageBox.information(self, "Nạp mẫu Toán 11", f"Đã nạp {st['added']} câu mẫu ({format_import_type_summary(st)}) — trùng bỏ qua: {st['duplicates']}.")

    def _delete_selected(self):
        r = self.tbl.currentRow()
        if r >= 0:
            self.db.delete_question(int(self.tbl.item(r, 0).text()))
            self._refresh_bank(); self._refresh_id_matrix_table()

    def _audit_qs(self):
        out = [f"Câu {i} [{q.primary_id}] ({iss.level}): {iss.message}" for i, q in enumerate(self.current_questions, 1) for iss in audit_question(q)]
        QMessageBox.information(self, "Rà soát CV 1239", "\n".join(out[:80]) if out else "Tất cả câu hỏi đang lọc đều hợp lệ!")

    def _find_similar(self):
        r = self.tbl.currentRow()
        if not (0 <= r < len(self.current_questions)):
            return
        q = self.current_questions[r]
        cands = [{"qid": x.primary_id, "stem": x.stem} for i, x in enumerate(self.current_questions) if i != r]
        hits = find_similar_questions(q.stem, cands, threshold=0.3)
        msg = "\n".join(f"- Tương đồng {score:.0%} [{it['qid']}]: {it['stem'][:80]}" for score, it in hits)
        QMessageBox.information(self, "Tìm câu gần trùng", msg or "Không có câu nào tương đồng ≥ 30%.")

    def _present(self):
        if self.current_questions:
            PresentationDialog(self.current_questions, max(0, self.tbl.currentRow()), self).exec()

    def _open_id6(self):
        out = str(user_data_dir() / "tra_cuu_id6_gdpt2018.html")
        export_id6_lookup_html(out)
        webbrowser.open(Path(out).as_uri())

    def _load_matrix_xlsx(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn Ma trận Excel", "", "Excel (*.xlsx)")
        if p:
            self.loaded_matrix = ExamMatrix.load_from_excel(p, name=Path(p).stem)
            ws = self.loaded_matrix.validate_cv7991()
            self.txt_matrix_log.setPlainText(f"Đã nạp '{self.loaded_matrix.name}': {self.loaded_matrix.total_by_type()}\n" + ("\n".join(ws) if ws else "Đạt chuẩn CV 7991."))

    def _export_reverse_matrix(self):
        if not self.current_questions:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Lưu Ma trận ngược", "ma_tran_nguoc.xlsx", "Excel (*.xlsx)")
        if p:
            ExamMatrix.from_exam_questions(self.current_questions, self.inp_title.text()).save_to_excel(p)
            self.txt_matrix_log.appendPlainText(f"Đã lưu ma trận ngược tại: {p}")

    def _export_cv7991_docs(self):
        mat = self.loaded_matrix or (ExamMatrix.from_exam_questions(self.current_questions, self.inp_title.text()) if self.current_questions else None)
        if not mat:
            return
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu Phụ lục 1 & 2 CV 7991")
        if d:
            export_cv7991_excel(mat, os.path.join(d, "ma_tran_dac_ta_cv7991.xlsx"))
            try:
                export_cv7991_docx(mat, os.path.join(d, "ma_tran_dac_ta_cv7991.docx"))
            except RuntimeError:
                pass
            self.txt_matrix_log.appendPlainText(f"Đã xuất Phụ lục 1 & 2 CV 7991 tại: {d}")

    def _pick_omr_template(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file mẫu OMR Excel", "", "Excel (*.xlsx)")
        if p:
            self.custom_omr_template = p
            self.lbl_status_global.setText(f"Mẫu OMR riêng: {os.path.basename(p)}")

    def _save_editor_to_bank(self):
        qs = parse_tex_questions(self.txt_editor.toPlainText(), auto_normalize=True)
        if qs:
            st = self.db.bulk_import(qs)
            self._refresh_bank(); self._refresh_id_matrix_table()
            QMessageBox.information(self, "Soạn thảo", f"Đã lưu {st['added']} câu vào kho ({format_import_type_summary(st)}) — trùng: {st['duplicates']}.")

    def _compile_pdf(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn tệp .tex biên dịch", "", "LaTeX (*.tex)")
        if p:
            self.lbl_status_global.setText(f"Đang biên dịch nền: {os.path.basename(p)}...")
            run_in_background(
                compile_tex_to_pdf, p,
                on_finished=lambda r: QMessageBox.information(self, "Biên dịch PDF", f"THÀNH CÔNG: {r.pdf_path}" if r.success else "LỖI:\n" + "\n".join(f"- Dòng {d.line_no}: {d.summary} -> {d.suggestion_vi}" for d in r.diagnostics)),
                on_error=lambda e: QMessageBox.warning(self, "Lỗi biên dịch", e),
            )

    def _imp_word(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn tệp Word", "", "Word (*.docx)")
        if p:
            qs, tr = convert_docx_to_questions(p)
            st = self.db.bulk_import(qs)
            self._refresh_bank(); self._refresh_id_matrix_table()
            QMessageBox.information(self, "Nhập Word", f"Đã thêm {st['added']} câu ({format_import_type_summary(st)}) | Trùng: {st['duplicates']}\nOMML={tr.omml_count}, MathType OLE={tr.mathtype_ole_count}, Ảnh={tr.media_image_count}")

    def _exp_word(self):
        if not self.current_questions:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Lưu Word", "de_xuat.docx", "Word (*.docx)")
        if p:
            rep = export_questions_to_docx(self.current_questions, p, self.inp_title.text())
            QMessageBox.information(self, "Xuất Word", f"Xong! Công thức OMML: {rep.direct_omml}/{rep.total_equations}")

    def _pick_ocr_pdf(self):
        from ..paths import app_root_dir
        p, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn PDF / Ảnh đề thi",
            str(app_root_dir()),
            "PDF & Ảnh (*.pdf *.png *.jpg *.jpeg);;Tất cả (*.*)",
        )
        if p:
            self.ed_ocr_pdf.setText(p)

    def _open_ocr_dialog(self):
        from .manual_pdf_ocr_dialog import ManualPdfImageOcrDialog
        init_p = self.ed_ocr_pdf.text().strip()
        dlg = ManualPdfImageOcrDialog(
            initial_path=init_p,
            wrap_fn=self.tien_ich_1._wrap_with_main_template,
            safe_stem_fn=self.tien_ich_1._safe_tex_stem,
            parent=self,
        )
        dlg.exec()

    def _run_ocr(self):
        from ..ai.pdf_ocr import extract_pdf_text_fallback, ocr_image_to_extest, ocr_mathpix_file
        from ..core.config_manager import ConfigManager as _CfgOcr
        p = self.ed_ocr_pdf.text().strip()
        if not p or not Path(p).exists():
            self._pick_ocr_pdf()
            p = self.ed_ocr_pdf.text().strip()
            if not p or not Path(p).exists():
                return

        cfg = _CfgOcr()
        gem_key = cfg.get("API", "gemini_api_key", "").strip()
        mp_id = cfg.get("API", "mathpix_app_id", "").strip()
        mp_key = cfg.get("API", "mathpix_app_key", "").strip()
        is_pdf = p.lower().endswith(".pdf")

        if gem_key:
            ai_cfg = AIConfig(
                provider="gemini",
                api_key=gem_key,
                model=cfg.get("API", "gemini_model", "gemini-2.5-flash"),
            )
            self.txt_ocr_out.setPlainText("Đang chuyển PDF/Ảnh sang LaTeX bằng Gemini AI trên luồng nền...")

            def _job():
                return ocr_pdf_to_extest(p, ai_cfg, chunk_pages=5).full_tex if is_pdf else ocr_image_to_extest(p, ai_cfg)

        elif mp_id and mp_key:
            self.txt_ocr_out.setPlainText("Đang chuyển PDF/Ảnh sang LaTeX bằng Mathpix API trên luồng nền...")

            def _job():
                return ocr_mathpix_file(p, mp_id, mp_key)

        elif is_pdf:
            self.txt_ocr_out.setPlainText("Chưa có API Key -> đang trích xuất nhanh văn bản từ PDF bằng PyMuPDF...")

            def _job():
                return extract_pdf_text_fallback(p)

        else:
            QMessageBox.warning(self, "Thiếu API Key", "Hãy nhập Gemini API Key (hoặc Mathpix API) trong 'Tiện ích 1 -> Tuỳ chọn' để nhận dạng ảnh.")
            return

        self.btn_run_pdf_tex.setEnabled(False)

        def _done(tex_str: str):
            self.btn_run_pdf_tex.setEnabled(True)
            self.txt_ocr_out.setPlainText(tex_str or "")

        def _fail(err_str: str):
            self.btn_run_pdf_tex.setEnabled(True)
            self.txt_ocr_out.setPlainText(f"Lỗi chuyển PDF/Ảnh:\n{err_str}")

        self._ocr_worker = run_in_background(_job, on_finished=_done, on_error=_fail)

    def _save_ocr_tex(self):
        body = self.txt_ocr_out.toPlainText().strip()
        if not body:
            QMessageBox.warning(self, "Chưa có mã LaTeX", "Hãy bấm 'Chuyển PDF → LaTeX' trước khi lưu.")
            return
        src = Path(self.ed_ocr_pdf.text().strip()) if self.ed_ocr_pdf.text().strip() else Path("pdf_converted.pdf")
        stem = self.tien_ich_1._safe_tex_stem(src.stem)
        default_out = src.with_name(f"{stem}.tex")
        out_p, _ = QFileDialog.getSaveFileName(self, "Lưu tệp LaTeX", str(default_out), "LaTeX (*.tex)")
        if not out_p:
            return
        out_path = Path(out_p)
        full_doc = self.tien_ich_1._wrap_with_main_template(body, out_path, title=src.stem)
        out_path.write_text(full_doc, encoding="utf-8")
        from ..exporters.pdfbuild import open_pdf_file
        open_pdf_file(str(out_path))
        QMessageBox.information(self, "Đã lưu & Mở TeXstudio", f"Đã lưu tệp LaTeX (kèm khung Main TeX Live 2019):\n{out_path}")

    def _exp_moodle(self):
        if not self.current_questions:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Lưu Moodle XML", "moodle_quiz.xml", "XML (*.xml)")
        if p:
            export_moodle_xml(self.current_questions, p)
            QMessageBox.information(self, "Moodle XML", f"Đã xuất tại: {p}")

    def _exp_gas(self):
        if not self.last_variants and self.current_questions:
            self.last_variants = generate_exam_batch(1, self.sp_seed.value(), base_questions=self.current_questions)
        if not self.last_variants:
            return
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất gói GAS Online")
        if d:
            b = export_online_exam_bundle(self.last_variants[0], d, server_only_key=True)
            QMessageBox.information(self, "Thi Online GAS", f"Đã xuất Code.gs + ExamClient.html tại:\n{d}\nThư mục Drive: {b['folder_id']}")

    def _toggle_arena(self):
        if self.arena_server:
            self.arena_server.stop(); self.arena_server = None
            self.b_arena.setText("Khởi chạy Đấu trường LAN (SSE)")
            self.lbl_arena.setText("Đấu trường LAN: Đang tắt.")
            return
        if not self.last_variants and self.current_questions:
            self.last_variants = generate_exam_batch(1, self.sp_seed.value(), base_questions=self.current_questions)
        if not self.last_variants:
            return
        self.arena_server = LanArenaServer(self.last_variants[0], "0.0.0.0", 8765)
        _, port = self.arena_server.start()
        ip = detect_lan_ip()
        self.b_arena.setText("Dừng Đấu trường LAN")
        self.lbl_arena.setText(f"ĐANG CHẠY — Học sinh: http://{ip}:{port}/ | Xếp hạng SSE: http://{ip}:{port}/host")
        webbrowser.open(f"http://127.0.0.1:{port}/host")

    def _preview_pdf(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn PDF xem trước", "", "PDF (*.pdf)")
        if p:
            qimg, tot = make_qimage_from_pdf_page(p, 0, 1.4)
            self.lbl_pdf.setPixmap(QPixmap.fromImage(qimg).scaled(self.lbl_pdf.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.lbl_arena.setText(f"Xem trước trang 1/{tot}: {os.path.basename(p)}")


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv or sys.argv)
    app.setStyle("Fusion")
    if not ensure_licensed_and_unlocked():
        return 0
    win = MyLT2026MainWindow()
    win.show()
    return app.exec()
