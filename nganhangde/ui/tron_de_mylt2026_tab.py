"""4 sub-tab Trộn đề chuẩn giao diện & chức năng MyLT 2026 v1.0.3.44:
1. Tạo đề theo ID (Chọn nhanh + Chọn theo ID 12 cột + phân trang + 8 nút ? H A C E D O U)
2. Tạo đề tự chọn (Lọc đa cấp + bảng 5 cột + HDSD/Sửa/Xoá/Chọn/Chọn hết/Xoá chọn/PDF + phân trang)
3. Tạo đề theo file (Bảng STT | Tập tin | Đã có | Lấy + Đã chọn + Xoá chọn)
4. Tạo đề tương tự (File đề gốc + Đề tương tự thứ + Tìm theo/Tỉ lệ tương tự/Số đề tối đa + bảng so sánh 2 cột)
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import random
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ..core.idmap_builtin import GDPT2018_MATH_CATALOG, describe_id6
from ..core.parser import Question, parse_tex_questions, read_tex_with_inputs
from ..core.similarity import jaccard_similarity
from ..paths import app_root_dir


def _qtype_display(qt: str) -> str:
    return {"TN": "TN", "DS": "ĐS", "KQ": "SA", "TL": "TL"}.get(qt, qt)


def _qtype_internal(lbl: str) -> str:
    return {"TN": "TN", "ĐS": "DS", "DS": "DS", "SA": "KQ", "KQ": "KQ", "TL": "TL"}.get(lbl, "")


class TaoDeTheoIdSubTab(QWidget):
    """Sub-tab 1: Tạo đề theo ID chuẩn MyLT 2026 v1.0.3.44."""

    PAGE_SIZE = 50

    def __init__(self, mw, parent=None):
        super().__init__(parent)
        self.mw = mw
        self._all_groups: list[dict] = []
        self._picked_map: dict[tuple[str, str], list[int]] = {}  # (qid, qtype) -> [n, h, v, c]
        self._page = 1
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(6)

        # GroupBox 1: Chọn nhanh
        g_fast = QGroupBox("Chọn nhanh")
        grid = QGridLayout(g_fast)
        grid.setSpacing(5)
        self.cb_fast_lop = QComboBox(); self.cb_fast_lop.addItems(["", "0 - Lớp 10", "1 - Lớp 11", "2 - Lớp 12", "6", "7", "8", "9"])
        self.cb_fast_mon = QComboBox(); self.cb_fast_mon.addItems(["", "D - Đại số / Giải tích", "H - Hình học", "C - Chuyên đề"])
        self.cb_fast_chuong = QComboBox(); self.cb_fast_chuong.addItems([""] + [f"{c['prefix']} - {c['chapter']}" for c in GDPT2018_MATH_CATALOG])
        self.cb_fast_bai = QComboBox(); self.cb_fast_bai.addItems(["", "1", "2", "3", "4", "5", "6", "7"])
        self.cb_fast_dang = QComboBox(); self.cb_fast_dang.addItems(["", "1", "2", "3", "4", "5", "6"])
        self.cb_fast_muc = QComboBox(); self.cb_fast_muc.addItems(["", "N - Nhận biết", "H - Thông hiểu", "V - Vận dụng", "C - Vận dụng cao"])
        self.cb_fast_loai = QComboBox(); self.cb_fast_loai.addItems(["", "TN", "ĐS", "SA", "TL"])
        self.cb_fast_count = QComboBox(); self.cb_fast_count.setEditable(True); self.cb_fast_count.addItems(["1", "2", "3", "4", "5", "10"])
        b_fast_loc = QPushButton("Lọc"); b_fast_loc.clicked.connect(self.refresh_table)
        b_fast_lay = QPushButton("Lấy"); b_fast_lay.clicked.connect(self._quick_pick)

        grid.addWidget(QLabel("Lớp"), 0, 0); grid.addWidget(self.cb_fast_lop, 0, 1)
        grid.addWidget(QLabel("Bài"), 0, 2); grid.addWidget(self.cb_fast_bai, 0, 3)
        grid.addWidget(QLabel("Loại"), 0, 4); grid.addWidget(self.cb_fast_loai, 0, 5)
        grid.addWidget(QLabel("Môn"), 1, 0); grid.addWidget(self.cb_fast_mon, 1, 1)
        grid.addWidget(QLabel("Dạng"), 1, 2); grid.addWidget(self.cb_fast_dang, 1, 3)
        grid.addWidget(QLabel("Số câu"), 1, 4); grid.addWidget(self.cb_fast_count, 1, 5)
        grid.addWidget(QLabel("Chương"), 2, 0); grid.addWidget(self.cb_fast_chuong, 2, 1)
        grid.addWidget(QLabel("Mức độ"), 2, 2); grid.addWidget(self.cb_fast_muc, 2, 3)
        hb_fl = QHBoxLayout(); hb_fl.addWidget(b_fast_loc); hb_fl.addWidget(b_fast_lay)
        grid.addLayout(hb_fl, 2, 4, 1, 2)
        grid.setColumnStretch(1, 3); grid.setColumnStretch(3, 3); grid.setColumnStretch(5, 1)
        lay.addWidget(g_fast)

        # GroupBox 2: Chọn theo ID
        g_id = QGroupBox("Chọn theo ID")
        vid = QVBoxLayout(g_id)
        vid.setSpacing(5)

        fbar = QHBoxLayout()
        self.cb_chuyen_id = QComboBox(); self.cb_chuyen_id.addItems(["", "KNTT", "CTST", "CD", "4 Mức độ"])
        b_loc = QPushButton("Lọc"); b_loc.clicked.connect(self.refresh_table)
        self.cb_id_lop = QComboBox(); self.cb_id_lop.addItems(["", "0", "1", "2", "6", "7", "8", "9"])
        self.cb_id_mon = QComboBox(); self.cb_id_mon.addItems(["", "D", "H", "C"])
        self.cb_id_chuong = QComboBox(); self.cb_id_chuong.setEditable(True); self.cb_id_chuong.addItems(["", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
        self.cb_id_bai = QComboBox(); self.cb_id_bai.setEditable(True); self.cb_id_bai.addItems(["", "1", "2", "3", "4", "5", "6"])
        self.cb_id_loai = QComboBox(); self.cb_id_loai.addItems(["", "TN", "ĐS", "SA", "TL"])
        self.cb_kieu_id = QComboBox(); self.cb_kieu_id.addItems(["ID6", "ID5"])
        self.cb_da_lay = QComboBox(); self.cb_da_lay.addItems(["Tất cả", "Đã lấy", "Chưa lấy"])

        for lbl, wid in [
            ("Chuyển ID", self.cb_chuyen_id),
        ]:
            fbar.addWidget(QLabel(lbl)); fbar.addWidget(wid)
        fbar.addWidget(b_loc)
        for lbl, wid in [
            ("Lớp", self.cb_id_lop),
            ("Môn", self.cb_id_mon),
            ("Chương", self.cb_id_chuong),
            ("Bài", self.cb_id_bai),
            ("Loại", self.cb_id_loai),
            ("Kiểu ID", self.cb_kieu_id),
            ("Đã lấy", self.cb_da_lay),
        ]:
            fbar.addWidget(QLabel(lbl))
            fbar.addWidget(wid, 1 if wid in (self.cb_id_chuong, self.cb_id_bai) else 0)
        vid.addLayout(fbar)

        cols = [
            "STT", "ID", "Lớp", "Môn", "Chương", "Bài, dạng", "Loại",
            "Đã có (N/H/V/C)", "Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao",
        ]
        self.tbl = QTableWidget(0, len(cols))
        self.tbl.setHorizontalHeaderLabels(cols)
        self.tbl.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        for c_idx in (0, 1, 2, 3, 4, 6, 7):
            self.tbl.horizontalHeader().setSectionResizeMode(c_idx, QHeaderView.ResizeToContents)
        for c_idx in (8, 9, 10, 11):
            self.tbl.setColumnWidth(c_idx, 82)
        vid.addWidget(self.tbl, stretch=1)

        # Thanh nút đáy: ? H A C E D O U | Đã chọn: ... | Đầu Trước [1 v] Sau Cuối
        b_foot = QHBoxLayout()
        for sym, tip, fn in [
            ("?", "Hướng dẫn chọn theo ID", self._show_help),
            ("H", "Chọn hết tất cả câu hiện có", self._pick_all),
            ("A", "Chọn mỗi dòng 1 câu đầu tiên còn trống", self._pick_one_each),
            ("C", "Xoá trắng số câu đã chọn", self._clear_all),
            ("E", "Xuất ma trận ID đang chọn ra Excel/CSV", self._export_picked_csv),
            ("D", "Xoá dòng đang chọn khỏi lựa chọn", self._clear_current_row),
            ("O", "Mở tra cứu Map ID6", lambda: self.mw._open_id6() if hasattr(self.mw, "_open_id6") else None),
            ("U", "Cập nhật lại bảng từ ngân hàng", self.refresh_table),
        ]:
            bt = QPushButton(sym); bt.setFixedWidth(28); bt.setToolTip(tip); bt.clicked.connect(fn)
            b_foot.addWidget(bt)

        self.lbl_picked = QLabel("Đã chọn: 0 câu (TN: 0 | ĐS: 0 | SA: 0 | TL: 0)")
        self.lbl_picked.setAlignment(Qt.AlignCenter)
        b_foot.addWidget(self.lbl_picked, stretch=1)

        b_first = QPushButton("Đầu"); b_first.setFixedWidth(50); b_first.clicked.connect(lambda: self._go_page(1))
        b_prev = QPushButton("Trước"); b_prev.setFixedWidth(55); b_prev.clicked.connect(lambda: self._go_page(self._page - 1))
        self.cb_page = QComboBox(); self.cb_page.setFixedWidth(55); self.cb_page.currentIndexChanged.connect(self._on_page_combo)
        b_next = QPushButton("Sau"); b_next.setFixedWidth(50); b_next.clicked.connect(lambda: self._go_page(self._page + 1))
        b_last = QPushButton("Cuối"); b_last.setFixedWidth(50); b_last.clicked.connect(lambda: self._go_page(999999))
        for w_p in (b_first, b_prev, self.cb_page, b_next, b_last):
            b_foot.addWidget(w_p)
        vid.addLayout(b_foot)
        lay.addWidget(g_id, stretch=1)

    def _show_help(self):
        QMessageBox.information(
            self,
            "Hướng dẫn Tạo đề theo ID",
            "- Chọn số lượng câu cần lấy tại 4 cột Nhận biết / Thông hiểu / Vận dụng / Vận dụng cao.\n"
            "- Hoặc dùng khung 'Chọn nhanh' phía trên rồi bấm 'Lấy'.\n"
            "- Các nút tắt: H (chọn hết), A (mỗi dòng 1 câu), C (xoá chọn), E (xuất CSV), D (xoá dòng đang chọn), O (tra cứu ID6), U (tải lại).\n"
            "- Sau khi chọn xong, bấm nút 'Tạo đề' ở góc dưới bên phải.",
        )

    def _source_rows(self) -> list[dict]:
        if self.mw.rb_from_files.isChecked() and getattr(self.mw, "source_file_questions", None):
            out = []
            for q in self.mw.source_file_questions:
                qid = q.primary_id or "CHUA_ID"
                out.append({
                    "qid": qid,
                    "qtype": q.qtype,
                    "lop": qid[0] if len(qid) >= 1 and qid != "CHUA_ID" else "",
                    "mon": qid[1] if len(qid) >= 2 and qid != "CHUA_ID" else "",
                    "chuong": qid[2] if len(qid) >= 3 and qid != "CHUA_ID" else "",
                    "muc_do": qid[3] if len(qid) >= 4 and qid != "CHUA_ID" else "N",
                })
            return out
        return [dict(r) for r in self.mw.db.search(limit=10000)]

    def refresh_table(self):
        rows = self._source_rows()
        want_lop = self.cb_id_lop.currentText().strip() or (self.cb_fast_lop.currentText().split()[0] if self.cb_fast_lop.currentText().strip() else "")
        want_mon = self.cb_id_mon.currentText().strip() or (self.cb_fast_mon.currentText().split()[0] if self.cb_fast_mon.currentText().strip() else "")
        want_ch = self.cb_id_chuong.currentText().strip()
        want_bai = self.cb_id_bai.currentText().strip() or self.cb_fast_bai.currentText().strip()
        want_loai = _qtype_internal(self.cb_id_loai.currentText().strip() or self.cb_fast_loai.currentText().strip())
        da_lay_mode = self.cb_da_lay.currentText()

        groups: dict[tuple[str, str], dict] = {}
        for r in rows:
            qid = str(r.get("qid") or "CHUA_ID")
            qtype = str(r.get("qtype") or "TN")
            lop = str(r.get("lop") or (qid[0] if len(qid) >= 1 and qid != "CHUA_ID" else ""))
            mon = str(r.get("mon") or (qid[1] if len(qid) >= 2 and qid != "CHUA_ID" else ""))
            chuong = str(r.get("chuong") or (qid[2] if len(qid) >= 3 and qid != "CHUA_ID" else ""))
            md = str(r.get("muc_do") or (qid[3] if len(qid) >= 4 and qid != "CHUA_ID" else "N")).upper()
            if md not in ("N", "H", "V", "C"):
                md = "N"

            if want_lop and lop != want_lop:
                continue
            if want_mon and mon != want_mon:
                continue
            if want_ch and chuong != want_ch:
                continue
            if want_bai and len(qid) >= 5 and qid[4] != want_bai:
                continue
            if want_loai and qtype != want_loai:
                continue

            # Gom theo mẫu ID có dấu ? ở vị trí mức độ giống MyLT 2026 (VD: 0D0?1-1)
            pat_id = f"{qid[:3]}?{qid[4:]}" if len(qid) >= 5 and qid != "CHUA_ID" else qid
            key = (pat_id, qtype)
            if key not in groups:
                groups[key] = {
                    "qid": pat_id,
                    "sample_qid": qid,
                    "lop": {"0": "10", "1": "11", "2": "12"}.get(lop, lop),
                    "lop_code": lop,
                    "mon": mon,
                    "chuong": chuong,
                    "desc": describe_id6(qid) if qid != "CHUA_ID" else "Chưa gắn mã ID",
                    "qtype": qtype,
                    "counts": defaultdict(int),
                }
            groups[key]["counts"][md] += 1

        all_g = sorted(groups.values(), key=lambda g: (g["qid"], g["qtype"]))
        if da_lay_mode == "Đã lấy":
            all_g = [g for g in all_g if sum(self._picked_map.get((g["qid"], g["qtype"]), [0, 0, 0, 0])) > 0]
        elif da_lay_mode == "Chưa lấy":
            all_g = [g for g in all_g if sum(self._picked_map.get((g["qid"], g["qtype"]), [0, 0, 0, 0])) == 0]

        self._all_groups = all_g
        total_pages = max(1, (len(all_g) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._page = max(1, min(self._page, total_pages))
        self.cb_page.blockSignals(True)
        self.cb_page.clear()
        for p in range(1, total_pages + 1):
            self.cb_page.addItem(str(p))
        self.cb_page.setCurrentIndex(self._page - 1)
        self.cb_page.blockSignals(False)
        self._render_page()

    def _go_page(self, p: int):
        total_pages = max(1, (len(self._all_groups) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._page = max(1, min(p, total_pages))
        self.cb_page.blockSignals(True)
        self.cb_page.setCurrentIndex(self._page - 1)
        self.cb_page.blockSignals(False)
        self._render_page()

    def _on_page_combo(self, idx: int):
        if idx >= 0:
            self._page = idx + 1
            self._render_page()

    def _render_page(self):
        start = (self._page - 1) * self.PAGE_SIZE
        page_items = self._all_groups[start : start + self.PAGE_SIZE]
        self.tbl.setRowCount(len(page_items))
        for ri, g in enumerate(page_items):
            key = (g["qid"], g["qtype"])
            cnt = g["counts"]
            nhvc = f"{cnt['N']}/{cnt['H']}/{cnt['V']}/{cnt['C']}"
            vals = [
                str(start + ri + 1), g["qid"], g["lop"], g["mon"], g["chuong"],
                g["desc"], _qtype_display(g["qtype"]), nhvc,
            ]
            for ci, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.tbl.setItem(ri, ci, it)

            picked = self._picked_map.get(key, [0, 0, 0, 0])
            for lv_idx, lv_key in enumerate(("N", "H", "V", "C")):
                avail = cnt[lv_key]
                cb = QComboBox()
                cb.addItem("")
                for k in range(1, avail + 1):
                    cb.addItem(str(k))
                if picked[lv_idx] > 0:
                    cb.setCurrentText(str(min(picked[lv_idx], avail)))
                cb.currentTextChanged.connect(
                    lambda txt, _key=key, _li=lv_idx: self._on_pick_changed(_key, _li, txt)
                )
                self.tbl.setCellWidget(ri, 8 + lv_idx, cb)
        self._update_summary()

    def _on_pick_changed(self, key: tuple[str, str], lv_idx: int, txt: str):
        arr = self._picked_map.setdefault(key, [0, 0, 0, 0])
        arr[lv_idx] = int(txt) if txt.isdigit() else 0
        self._update_summary()

    def _update_summary(self):
        by_type = defaultdict(int)
        total = 0
        for (_, qt), arr in self._picked_map.items():
            s = sum(arr)
            if s > 0:
                by_type[qt] += s
                total += s
        self.lbl_picked.setText(
            f"Đã chọn: {total} câu (TN: {by_type['TN']} | ĐS: {by_type['DS']} | SA: {by_type['KQ']} | TL: {by_type['TL']})"
        )

    def _quick_pick(self):
        self.refresh_table()
        if not self._all_groups:
            QMessageBox.information(self, "Chọn nhanh", "Không có câu hỏi phù hợp điều kiện lọc.")
            return
        try:
            need = max(1, int(self.cb_fast_count.currentText().strip() or "1"))
        except ValueError:
            need = 1
        md_sel = self.cb_fast_muc.currentText().split()[0] if self.cb_fast_muc.currentText().strip() else ""
        lv_order = [("N", 0), ("H", 1), ("V", 2), ("C", 3)]
        if md_sel in ("N", "H", "V", "C"):
            lv_order = [(md_sel, "NHVC".index(md_sel))]
        rem = need
        for g in self._all_groups:
            if rem <= 0:
                break
            key = (g["qid"], g["qtype"])
            arr = self._picked_map.setdefault(key, [0, 0, 0, 0])
            for lv_k, lv_i in lv_order:
                free = g["counts"][lv_k] - arr[lv_i]
                if free > 0 and rem > 0:
                    take = min(free, rem)
                    arr[lv_i] += take
                    rem -= take
        self._render_page()

    def _pick_all(self):
        for g in self._all_groups:
            c = g["counts"]
            self._picked_map[(g["qid"], g["qtype"])] = [c["N"], c["H"], c["V"], c["C"]]
        self._render_page()

    def _pick_one_each(self):
        for g in self._all_groups:
            c = g["counts"]
            arr = [0, 0, 0, 0]
            for i, k in enumerate(("N", "H", "V", "C")):
                if c[k] > 0:
                    arr[i] = 1
                    break
            self._picked_map[(g["qid"], g["qtype"])] = arr
        self._render_page()

    def _clear_all(self):
        self._picked_map.clear()
        self._render_page()

    def _clear_current_row(self):
        r = self.tbl.currentRow()
        if r >= 0:
            start = (self._page - 1) * self.PAGE_SIZE
            if start + r < len(self._all_groups):
                g = self._all_groups[start + r]
                self._picked_map.pop((g["qid"], g["qtype"]), None)
                self._render_page()

    def _export_picked_csv(self):
        out, _ = QFileDialog.getSaveFileName(self, "Xuất ma trận ID đã chọn", str(app_root_dir() / "ma_tran_id.csv"), "CSV (*.csv)")
        if not out:
            return
        import csv
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ID", "Loại", "Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao"])
            for (pat_id, qt), arr in sorted(self._picked_map.items()):
                if sum(arr) > 0:
                    w.writerow([pat_id, _qtype_display(qt), *arr])
        QMessageBox.information(self, "Xuất ma trận", f"Đã lưu ma trận ID tại:\n{out}")

    def collect_selected_questions(self, seed: int = 2026) -> list[Question]:
        """Rút ngẫu nhiên đúng số lượng câu hỏi theo 4 mức độ N/H/V/C đã chọn trên bảng."""
        rng = random.Random(seed)
        selected: list[Question] = []
        pool_all: list[Question] = []
        if self.mw.rb_from_files.isChecked() and getattr(self.mw, "source_file_questions", None):
            pool_all = list(self.mw.source_file_questions)
        else:
            for r in self.mw.db.search(limit=10000):
                ps = parse_tex_questions(r["raw"])
                if ps:
                    pool_all.append(ps[0])

        for (pat_id, qt), arr in self._picked_map.items():
            if sum(arr) <= 0:
                continue
            for lv_idx, lv_k in enumerate(("N", "H", "V", "C")):
                need = arr[lv_idx]
                if need <= 0:
                    continue
                cands = []
                for q in pool_all:
                    if q.qtype != qt:
                        continue
                    qid = q.primary_id or "CHUA_ID"
                    q_pat = f"{qid[:3]}?{qid[4:]}" if len(qid) >= 5 and qid != "CHUA_ID" else qid
                    q_lv = qid[3].upper() if len(qid) >= 4 and qid != "CHUA_ID" else "N"
                    if q_lv not in ("N", "H", "V", "C"):
                        q_lv = "N"
                    if q_pat == pat_id and q_lv == lv_k:
                        cands.append(q)
                rng.shuffle(cands)
                selected.extend(cands[:need])
        return selected


class TaoDeTuChonSubTab(QWidget):
    """Sub-tab 2: Tạo đề tự chọn chuẩn MyLT 2026 v1.0.3.44."""

    PAGE_SIZE = 30

    def __init__(self, mw, parent=None):
        super().__init__(parent)
        self.mw = mw
        self._items: list[tuple[int, Question]] = []
        self._checked_ids: set[int] = set()
        self._page = 1
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(5)

        fbar = QHBoxLayout()
        b_loc = QPushButton("Lọc"); b_loc.clicked.connect(self.refresh_table)
        self.cb_lop = QComboBox(); self.cb_lop.addItems(["", "0", "1", "2", "6", "7", "8", "9"])
        self.cb_mon = QComboBox(); self.cb_mon.addItems(["", "D", "H", "C"])
        self.cb_chuong = QComboBox(); self.cb_chuong.setEditable(True); self.cb_chuong.addItems(["", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
        self.cb_bai = QComboBox(); self.cb_bai.setEditable(True); self.cb_bai.addItems(["", "1", "2", "3", "4", "5", "6"])
        self.cb_dang = QComboBox(); self.cb_dang.setEditable(True); self.cb_dang.addItems(["", "1", "2", "3", "4", "5"])
        self.cb_muc = QComboBox(); self.cb_muc.addItems(["", "N", "H", "V", "C"])
        self.cb_loai = QComboBox(); self.cb_loai.addItems(["", "TN", "ĐS", "SA", "TL"])
        self.cb_kieu_id = QComboBox(); self.cb_kieu_id.addItems(["ID6", "ID5"])
        self.cb_da_lay = QComboBox(); self.cb_da_lay.addItems(["Tất cả", "Đã chọn", "Chưa chọn"])

        fbar.addWidget(b_loc)
        for lbl, wid in [
            ("Lớp", self.cb_lop), ("Môn", self.cb_mon), ("Chương", self.cb_chuong),
            ("Bài", self.cb_bai), ("Dạng", self.cb_dang), ("Mức độ", self.cb_muc),
            ("Loại", self.cb_loai), ("Kiểu ID", self.cb_kieu_id), ("Đã lấy", self.cb_da_lay),
        ]:
            fbar.addWidget(QLabel(lbl)); fbar.addWidget(wid)
        lay.addLayout(fbar)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["STT", "Nội dung câu hỏi", "Loại", "ID", "Chọn"])
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for c_i in (0, 2, 3, 4):
            self.tbl.horizontalHeader().setSectionResizeMode(c_i, QHeaderView.ResizeToContents)
        self.tbl.verticalHeader().setDefaultSectionSize(72)
        lay.addWidget(self.tbl, stretch=1)

        bot = QHBoxLayout()
        b_hd = QPushButton("HDSD"); b_hd.clicked.connect(
            lambda: QMessageBox.information(self, "HDSD Tạo đề tự chọn", "Tích chọn từng câu hỏi ở cột 'Chọn' rồi bấm 'Tạo đề' để trộn thành bộ đề hoàn chỉnh.")
        )
        b_edit = QPushButton("Sửa câu hỏi"); b_edit.clicked.connect(self._edit_current)
        b_del = QPushButton("Xoá"); b_del.clicked.connect(self._delete_current)
        b_pick = QPushButton("Chọn"); b_pick.clicked.connect(self._toggle_current)
        self.cb_pick_n = QComboBox(); self.cb_pick_n.setFixedWidth(55); self.cb_pick_n.addItems(["5", "10", "20", "50"])
        b_all = QPushButton("Chọn hết"); b_all.clicked.connect(self._select_all)
        b_none = QPushButton("Xoá chọn"); b_none.clicked.connect(self._clear_selection)
        self.chk_pdf = QCheckBox("PDF")
        self.lbl_count = QLabel("Đã chọn: 0 câu")
        self.lbl_count.setAlignment(Qt.AlignCenter)

        for w_b in (b_hd, b_edit, b_del, b_pick, self.cb_pick_n, b_all, b_none, self.chk_pdf):
            bot.addWidget(w_b)
        bot.addWidget(self.lbl_count, stretch=1)

        b_first = QPushButton("Đầu"); b_first.setFixedWidth(50); b_first.clicked.connect(lambda: self._go_page(1))
        b_prev = QPushButton("Trước"); b_prev.setFixedWidth(55); b_prev.clicked.connect(lambda: self._go_page(self._page - 1))
        self.cb_page = QComboBox(); self.cb_page.setFixedWidth(55); self.cb_page.currentIndexChanged.connect(self._on_page_combo)
        b_next = QPushButton("Sau"); b_next.setFixedWidth(50); b_next.clicked.connect(lambda: self._go_page(self._page + 1))
        b_last = QPushButton("Cuối"); b_last.setFixedWidth(50); b_last.clicked.connect(lambda: self._go_page(999999))
        for w_p in (b_first, b_prev, self.cb_page, b_next, b_last):
            bot.addWidget(w_p)
        lay.addLayout(bot)

    def refresh_table(self):
        want_lop = self.cb_lop.currentText().strip()
        want_mon = self.cb_mon.currentText().strip()
        want_ch = self.cb_chuong.currentText().strip()
        want_bai = self.cb_bai.currentText().strip()
        want_dang = self.cb_dang.currentText().strip()
        want_muc = self.cb_muc.currentText().strip()
        want_loai = _qtype_internal(self.cb_loai.currentText().strip())
        da_lay = self.cb_da_lay.currentText()

        items: list[tuple[int, Question]] = []
        if self.mw.rb_from_files.isChecked() and getattr(self.mw, "source_file_questions", None):
            for idx, q in enumerate(self.mw.source_file_questions, 1):
                items.append((idx, q))
        else:
            for r in self.mw.db.search(limit=2000):
                ps = parse_tex_questions(r["raw"])
                if ps:
                    items.append((int(r["id"]), ps[0]))

        filtered: list[tuple[int, Question]] = []
        for qid_num, q in items:
            code = q.primary_id or ""
            if want_lop and (len(code) < 1 or code[0] != want_lop):
                continue
            if want_mon and (len(code) < 2 or code[1] != want_mon):
                continue
            if want_ch and (len(code) < 3 or code[2] != want_ch):
                continue
            if want_muc and (len(code) < 4 or code[3].upper() != want_muc):
                continue
            if want_bai and (len(code) < 5 or code[4] != want_bai):
                continue
            if want_dang and not code.endswith(f"-{want_dang}"):
                continue
            if want_loai and q.qtype != want_loai:
                continue
            if da_lay == "Đã chọn" and qid_num not in self._checked_ids:
                continue
            if da_lay == "Chưa chọn" and qid_num in self._checked_ids:
                continue
            filtered.append((qid_num, q))

        self._items = filtered
        total_pages = max(1, (len(filtered) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._page = max(1, min(self._page, total_pages))
        self.cb_page.blockSignals(True)
        self.cb_page.clear()
        for p in range(1, total_pages + 1):
            self.cb_page.addItem(str(p))
        self.cb_page.setCurrentIndex(self._page - 1)
        self.cb_page.blockSignals(False)
        self._render_page()

    def _go_page(self, p: int):
        total_pages = max(1, (len(self._items) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._page = max(1, min(p, total_pages))
        self.cb_page.blockSignals(True)
        self.cb_page.setCurrentIndex(self._page - 1)
        self.cb_page.blockSignals(False)
        self._render_page()

    def _on_page_combo(self, idx: int):
        if idx >= 0:
            self._page = idx + 1
            self._render_page()

    def _render_page(self):
        start = (self._page - 1) * self.PAGE_SIZE
        chunk = self._items[start : start + self.PAGE_SIZE]
        self.tbl.setRowCount(len(chunk))
        for ri, (qid_num, q) in enumerate(chunk):
            it_stt = QTableWidgetItem(str(start + ri + 1))
            it_stt.setFlags(it_stt.flags() & ~Qt.ItemIsEditable)
            it_body = QTableWidgetItem((q.raw or q.stem).strip()[:500])
            it_body.setFlags(it_body.flags() & ~Qt.ItemIsEditable)
            it_type = QTableWidgetItem(_qtype_display(q.qtype))
            it_type.setFlags(it_type.flags() & ~Qt.ItemIsEditable)
            it_id = QTableWidgetItem(q.primary_id or "")
            it_id.setFlags(it_id.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(ri, 0, it_stt)
            self.tbl.setItem(ri, 1, it_body)
            self.tbl.setItem(ri, 2, it_type)
            self.tbl.setItem(ri, 3, it_id)

            cb = QCheckBox()
            cb.setChecked(qid_num in self._checked_ids)
            cb.stateChanged.connect(lambda st, _id=qid_num: self._on_check(_id, st))
            wrap = QWidget(); hl = QHBoxLayout(wrap); hl.setContentsMargins(0, 0, 0, 0); hl.setAlignment(Qt.AlignCenter); hl.addWidget(cb)
            self.tbl.setCellWidget(ri, 4, wrap)
        self.lbl_count.setText(f"Đã chọn: {len(self._checked_ids)} câu")

    def _on_check(self, qid_num: int, state: int):
        if state == Qt.Checked.value or state == 2:
            self._checked_ids.add(qid_num)
        else:
            self._checked_ids.discard(qid_num)
        self.lbl_count.setText(f"Đã chọn: {len(self._checked_ids)} câu")

    def _toggle_current(self):
        r = self.tbl.currentRow()
        if r >= 0:
            start = (self._page - 1) * self.PAGE_SIZE
            if start + r < len(self._items):
                qid_num = self._items[start + r][0]
                if qid_num in self._checked_ids:
                    self._checked_ids.remove(qid_num)
                else:
                    self._checked_ids.add(qid_num)
                self._render_page()

    def _select_all(self):
        for qid_num, _ in self._items:
            self._checked_ids.add(qid_num)
        self._render_page()

    def _clear_selection(self):
        self._checked_ids.clear()
        self._render_page()

    def _edit_current(self):
        r = self.tbl.currentRow()
        if r < 0:
            return
        start = (self._page - 1) * self.PAGE_SIZE
        if start + r >= len(self._items):
            return
        qid_num, q = self._items[start + r]
        new_txt, ok = QInputDialog.getMultiLineText(self, "Sửa câu hỏi", "Mã LaTeX câu hỏi:", q.raw or q.stem)
        if ok and new_txt.strip():
            q.raw = new_txt.strip()
            self._render_page()

    def _delete_current(self):
        r = self.tbl.currentRow()
        if r < 0:
            return
        start = (self._page - 1) * self.PAGE_SIZE
        if start + r < len(self._items):
            qid_num, _ = self._items.pop(start + r)
            self._checked_ids.discard(qid_num)
            self._render_page()

    def collect_selected_questions(self) -> list[Question]:
        return [q for qid_num, q in self._items if qid_num in self._checked_ids]


class TaoDeTheoFileSubTab(QWidget):
    """Sub-tab 3: Tạo đề theo file chuẩn MyLT 2026 v1.0.3.44."""

    def __init__(self, mw, parent=None):
        super().__init__(parent)
        self.mw = mw
        self._files: list[tuple[Path, list[Question]]] = []
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(6)

        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["STT", "Tập tin", "Đã có", "Lấy"])
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl.setColumnWidth(3, 90)
        lay.addWidget(self.tbl, stretch=1)

        bot = QHBoxLayout()
        self.lbl_picked = QLabel("Đã chọn: 0 câu / 0 tệp")
        b_add = QPushButton("Thêm file .tex"); b_add.clicked.connect(self.add_files_dialog)
        b_clear = QPushButton("Xoá chọn"); b_clear.clicked.connect(self.clear_files)
        bot.addWidget(self.lbl_picked, stretch=1)
        bot.addWidget(b_add)
        bot.addWidget(b_clear)
        lay.addLayout(bot)

    def add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn một hoặc nhiều file .tex", str(app_root_dir()), "LaTeX (*.tex)")
        if paths:
            self.load_paths([Path(p) for p in paths], append=True)

    def load_paths(self, paths: list[Path], append: bool = False):
        if not append:
            self._files.clear()
        existing = {str(p.resolve()) for p, _ in self._files}
        for p in paths:
            if not p.exists() or str(p.resolve()) in existing:
                continue
            qs = parse_tex_questions(read_tex_with_inputs(p), auto_normalize=True)
            self._files.append((p, qs))
            existing.add(str(p.resolve()))
        self._render()

    def clear_files(self):
        self._files.clear()
        self._render()

    def _render(self):
        self.tbl.setRowCount(len(self._files))
        for ri, (p, qs) in enumerate(self._files):
            it0 = QTableWidgetItem(str(ri + 1)); it0.setFlags(it0.flags() & ~Qt.ItemIsEditable)
            it1 = QTableWidgetItem(str(p)); it1.setFlags(it1.flags() & ~Qt.ItemIsEditable)
            it2 = QTableWidgetItem(str(len(qs))); it2.setFlags(it2.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(ri, 0, it0)
            self.tbl.setItem(ri, 1, it1)
            self.tbl.setItem(ri, 2, it2)
            sp = QSpinBox(); sp.setRange(0, len(qs)); sp.setValue(len(qs))
            sp.valueChanged.connect(self._update_summary)
            self.tbl.setCellWidget(ri, 3, sp)
        self._update_summary()

    def _update_summary(self):
        tot = 0
        for ri in range(self.tbl.rowCount()):
            sp = self.tbl.cellWidget(ri, 3)
            if isinstance(sp, QSpinBox):
                tot += sp.value()
        self.lbl_picked.setText(f"Đã chọn: {tot} câu / {len(self._files)} tệp")

    def collect_selected_questions(self, seed: int = 2026) -> list[Question]:
        rng = random.Random(seed)
        out: list[Question] = []
        for ri, (_, qs) in enumerate(self._files):
            sp = self.tbl.cellWidget(ri, 3)
            need = sp.value() if isinstance(sp, QSpinBox) else len(qs)
            if need <= 0:
                continue
            pool = list(qs)
            if need < len(pool):
                rng.shuffle(pool)
            out.extend(pool[:need])
        return out


class TaoDeTuongTuSubTab(QWidget):
    """Sub-tab 4: Tạo đề tương tự chuẩn MyLT 2026 v1.0.3.44."""

    def __init__(self, mw, parent=None):
        super().__init__(parent)
        self.mw = mw
        self._orig_qs: list[Question] = []
        self._sim_variants: list[list[Question]] = []
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(6)

        # Hàng 1: File đề gốc | Chọn | Xoá
        r1 = QHBoxLayout()
        self.ed_orig = QLineEdit(); self.ed_orig.setPlaceholderText("Chọn tệp đề gốc .tex...")
        b_chon = QPushButton("Chọn"); b_chon.clicked.connect(self._pick_orig)
        b_xoa = QPushButton("Xoá"); b_xoa.clicked.connect(self._clear_orig)
        r1.addWidget(QLabel("File đề gốc")); r1.addWidget(self.ed_orig, 1); r1.addWidget(b_chon); r1.addWidget(b_xoa)
        lay.addLayout(r1)

        # Hàng 2: Đề tương tự thứ | Lưu | Đổi | Sửa | Xem PDF || Tìm theo | Tỉ lệ tương tự | Số đề tối đa | Tìm | HDSD
        r2 = QHBoxLayout()
        self.cb_var = QComboBox(); self.cb_var.setFixedWidth(60); self.cb_var.currentIndexChanged.connect(self._render_variant)
        b_save = QPushButton("Lưu"); b_save.clicked.connect(self._save_current_variant)
        b_swap = QPushButton("Đổi"); b_swap.clicked.connect(self._swap_current_row)
        b_edit = QPushButton("Sửa"); b_edit.clicked.connect(self._edit_current_row)
        self.chk_pdf = QCheckBox("Xem PDF")

        self.cb_find_by = QComboBox(); self.cb_find_by.addItems(["ID", "Nội dung", "ID + Nội dung"])
        self.cb_rate = QComboBox(); self.cb_rate.addItems(["50%", "55%", "60%", "65%", "70%", "75%", "80%", "85%"]); self.cb_rate.setCurrentText("65%")
        self.ed_max_de = QLineEdit("4"); self.ed_max_de.setFixedWidth(45)
        b_tim = QPushButton("Tìm"); b_tim.clicked.connect(self._find_similar_exams)
        b_hd = QPushButton("HDSD"); b_hd.clicked.connect(
            lambda: QMessageBox.information(self, "HDSD Tạo đề tương tự", "1. Chọn 'File đề gốc' (.tex).\n2. Chọn tiêu chí 'Tìm theo', 'Tỉ lệ tương tự', 'Số đề tối đa' rồi bấm 'Tìm'.\n3. Kiểm tra câu tương tự trên bảng, có thể bấm 'Đổi' hoặc 'Sửa', rồi bấm 'Lưu' hoặc 'Tạo đề'.")
        )

        for w in (QLabel("Đề tương tự thứ"), self.cb_var, b_save, b_swap, b_edit, self.chk_pdf):
            r2.addWidget(w)
        r2.addStretch()
        for w in (QLabel("Tìm theo"), self.cb_find_by, QLabel("Tỉ lệ tương tự"), self.cb_rate, QLabel("Số đề tối đa"), self.ed_max_de, b_tim, b_hd):
            r2.addWidget(w)
        lay.addLayout(r2)

        # Bảng so sánh 4 cột: STT | Câu hỏi đề gốc | Câu hỏi đề tương tự | Chọn
        self.tbl = QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels(["STT", "Câu hỏi đề gốc", "Câu hỏi đề tương tự", "Chọn"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tbl.verticalHeader().setDefaultSectionSize(72)
        lay.addWidget(self.tbl, stretch=1)

    def _pick_orig(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn đề gốc .tex", str(app_root_dir()), "LaTeX (*.tex)")
        if p:
            self.ed_orig.setText(p)
            self._orig_qs = parse_tex_questions(read_tex_with_inputs(Path(p)), auto_normalize=True)
            self._sim_variants = []
            self.cb_var.clear()
            self._render_orig_only()

    def _clear_orig(self):
        self.ed_orig.clear()
        self._orig_qs = []
        self._sim_variants = []
        self.cb_var.clear()
        self.tbl.setRowCount(0)

    def _render_orig_only(self):
        self.tbl.setRowCount(len(self._orig_qs))
        for ri, q in enumerate(self._orig_qs):
            it0 = QTableWidgetItem(str(ri + 1)); it0.setFlags(it0.flags() & ~Qt.ItemIsEditable)
            it1 = QTableWidgetItem((q.raw or q.stem).strip()[:400]); it1.setFlags(it1.flags() & ~Qt.ItemIsEditable)
            it2 = QTableWidgetItem("(Bấm 'Tìm' để tìm câu tương tự)"); it2.setFlags(it2.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(ri, 0, it0); self.tbl.setItem(ri, 1, it1); self.tbl.setItem(ri, 2, it2)
            cb = QCheckBox(); cb.setChecked(True)
            wrap = QWidget(); hl = QHBoxLayout(wrap); hl.setContentsMargins(0, 0, 0, 0); hl.setAlignment(Qt.AlignCenter); hl.addWidget(cb)
            self.tbl.setCellWidget(ri, 3, wrap)

    def _find_similar_exams(self):
        if not self._orig_qs:
            self._pick_orig()
            if not self._orig_qs:
                return
        try:
            max_de = max(1, min(20, int(self.ed_max_de.text().strip() or "4")))
        except ValueError:
            max_de = 4
        mode = self.cb_find_by.currentText()
        pool: list[Question] = []
        for r in self.mw.db.search(limit=5000):
            ps = parse_tex_questions(r["raw"])
            if ps:
                pool.append(ps[0])
        if not pool:
            QMessageBox.warning(self, "Kho trống", "Ngân hàng câu hỏi hiện đang trống. Hãy nhập câu hỏi vào kho trước.")
            return

        self._sim_variants = []
        for v_idx in range(max_de):
            rng = random.Random(2026 + v_idx)
            var_qs: list[Question] = []
            for oq in self._orig_qs:
                cands = [pq for pq in pool if pq.qtype == oq.qtype and pq.stem != oq.stem]
                if mode in ("ID", "ID + Nội dung") and oq.primary_id:
                    id_cands = [pq for pq in cands if pq.primary_id == oq.primary_id]
                    if id_cands:
                        cands = id_cands
                if mode in ("Nội dung", "ID + Nội dung") and cands:
                    cands.sort(key=lambda pq: jaccard_similarity(oq.stem.lower(), pq.stem.lower()), reverse=True)
                    top = cands[: max(3, max_de)]
                    pick = top[v_idx % len(top)]
                elif cands:
                    rng.shuffle(cands)
                    pick = cands[0]
                else:
                    pick = oq
                var_qs.append(pick)
            self._sim_variants.append(var_qs)

        self.cb_var.blockSignals(True)
        self.cb_var.clear()
        for i in range(1, len(self._sim_variants) + 1):
            self.cb_var.addItem(str(i))
        self.cb_var.setCurrentIndex(0)
        self.cb_var.blockSignals(False)
        self._render_variant()

    def _render_variant(self):
        idx = self.cb_var.currentIndex()
        if idx < 0 or idx >= len(self._sim_variants):
            return
        sim_qs = self._sim_variants[idx]
        self.tbl.setRowCount(len(self._orig_qs))
        for ri, (oq, sq) in enumerate(zip(self._orig_qs, sim_qs)):
            it0 = QTableWidgetItem(str(ri + 1)); it0.setFlags(it0.flags() & ~Qt.ItemIsEditable)
            it1 = QTableWidgetItem((oq.raw or oq.stem).strip()[:400]); it1.setFlags(it1.flags() & ~Qt.ItemIsEditable)
            it2 = QTableWidgetItem((sq.raw or sq.stem).strip()[:400]); it2.setFlags(it2.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(ri, 0, it0); self.tbl.setItem(ri, 1, it1); self.tbl.setItem(ri, 2, it2)
            cb = QCheckBox(); cb.setChecked(True)
            wrap = QWidget(); hl = QHBoxLayout(wrap); hl.setContentsMargins(0, 0, 0, 0); hl.setAlignment(Qt.AlignCenter); hl.addWidget(cb)
            self.tbl.setCellWidget(ri, 3, wrap)

    def _swap_current_row(self):
        idx = self.cb_var.currentIndex()
        r = self.tbl.currentRow()
        if idx < 0 or r < 0 or idx >= len(self._sim_variants):
            return
        oq = self._orig_qs[r]
        cands = []
        for row in self.mw.db.search(limit=2000):
            ps = parse_tex_questions(row["raw"])
            if ps and ps[0].qtype == oq.qtype and ps[0].stem != self._sim_variants[idx][r].stem:
                cands.append(ps[0])
        if cands:
            self._sim_variants[idx][r] = random.choice(cands)
            self._render_variant()

    def _edit_current_row(self):
        idx = self.cb_var.currentIndex()
        r = self.tbl.currentRow()
        if idx < 0 or r < 0 or idx >= len(self._sim_variants):
            return
        sq = self._sim_variants[idx][r]
        new_txt, ok = QInputDialog.getMultiLineText(self, "Sửa câu tương tự", "Mã LaTeX:", sq.raw or sq.stem)
        if ok and new_txt.strip():
            sq.raw = new_txt.strip()
            self._render_variant()

    def _save_current_variant(self):
        qs = self.collect_selected_questions()
        if not qs:
            QMessageBox.warning(self, "Chưa có đề", "Hãy bấm 'Tìm' để tạo đề tương tự trước.")
            return
        out, _ = QFileDialog.getSaveFileName(self, "Lưu đề tương tự", str(app_root_dir() / "de_tuong_tu.tex"), "LaTeX (*.tex)")
        if out:
            Path(out).write_text("\n\n".join(q.to_latex(True) for q in qs) + "\n", encoding="utf-8")
            QMessageBox.information(self, "Đã lưu", f"Đã lưu đề tương tự tại:\n{out}")

    def collect_selected_questions(self) -> list[Question]:
        idx = self.cb_var.currentIndex()
        if idx < 0 or idx >= len(self._sim_variants):
            return []
        sim_qs = self._sim_variants[idx]
        out: list[Question] = []
        for ri, q in enumerate(sim_qs):
            wrap = self.tbl.cellWidget(ri, 3)
            cb = wrap.findChild(QCheckBox) if wrap else None
            if cb is None or cb.isChecked():
                out.append(q)
        return out
