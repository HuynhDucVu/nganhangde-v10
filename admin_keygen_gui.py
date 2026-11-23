"""CÔNG CỤ CẤP MÃ KÍCH HOẠT BẢN QUYỀN (CHỈ DÀNH CHO TÁC GIẢ — KHÔNG GỬI CHO KHÁCH HÀNG)."""
from __future__ import annotations
import csv
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from nganhangde.core.licensing import generate_license_key, get_machine_id, normalize_machine_id


class AdminKeygenWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ADMIN KEYGEN — Cấp mã bản quyền Nganhangde_vu")
        self.setMinimumWidth(560)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lbl = QLabel(
            "<h3 style='margin:0; color:#991b1b;'>CÔNG CỤ CẤP KEY BẢN QUYỀN (CHỈ DÀNH CHO TÁC GIẢ)</h3>"
            "<p style='margin:4px 0 0 0; color:#475569;'>"
            "Nhập <b>Mã máy</b> người dùng gửi tới → chọn thời hạn → bấm <b>Tạo Mã kích hoạt</b>. "
            "Lịch sử cấp key tự động lưu vào <code>danh_sach_khach_hang_key.csv</code>.</p>"
        )
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        form = QFormLayout()
        mid_row = QHBoxLayout()
        self.ed_mid = QLineEdit()
        self.ed_mid.setPlaceholderText("VD: NHV-A1B2-C3D4-E5F6")
        b_my_mid = QPushButton("Lấy mã máy này")
        b_my_mid.clicked.connect(lambda: self.ed_mid.setText(get_machine_id()))
        mid_row.addWidget(self.ed_mid, 1)
        mid_row.addWidget(b_my_mid)
        form.addRow("Mã máy khách hàng:", mid_row)

        self.cbo_plan = QComboBox()
        self.cbo_plan.addItems([
            "Vĩnh viễn (PERM)",
            "1 năm (365 ngày)",
            "6 tháng (180 ngày)",
            "1 tháng (30 ngày)",
            "Dùng thử 7 ngày",
            "Tuỳ chọn ngày hết hạn (YYYYMMDD)",
        ])
        self.cbo_plan.currentIndexChanged.connect(self._on_plan_changed)
        form.addRow("Gói bản quyền:", self.cbo_plan)

        self.ed_custom_exp = QLineEdit()
        self.ed_custom_exp.setPlaceholderText("VD: 20271231")
        self.ed_custom_exp.setEnabled(False)
        form.addRow("Ngày hết hạn riêng:", self.ed_custom_exp)

        self.ed_customer = QLineEdit()
        self.ed_customer.setPlaceholderText("Họ tên / SĐT / Trường học (lưu sổ theo dõi)...")
        form.addRow("Khách hàng:", self.ed_customer)

        key_row = QHBoxLayout()
        self.ed_key = QLineEdit()
        self.ed_key.setReadOnly(True)
        self.ed_key.setStyleSheet("font-weight: bold; font-size: 11pt; background: #ecfdf5; color: #065f46;")
        b_copy = QPushButton("Copy Key gửi khách")
        b_copy.clicked.connect(self._copy_key)
        key_row.addWidget(self.ed_key, 1)
        key_row.addWidget(b_copy)
        form.addRow("Mã kích hoạt tạo ra:", key_row)
        lay.addLayout(form)

        bot = QHBoxLayout()
        b_gen = QPushButton("Tạo Mã kích hoạt")
        b_gen.setStyleSheet("font-weight: bold; padding: 7px 18px; background: #0f4c81; color: white; border-radius: 4px;")
        b_gen.clicked.connect(self._generate)
        bot.addStretch()
        bot.addWidget(b_gen)
        lay.addLayout(bot)

    def _on_plan_changed(self, idx: int):
        self.ed_custom_exp.setEnabled(idx == 5)

    def _compute_expiry(self) -> str:
        idx = self.cbo_plan.currentIndex()
        today = date.today()
        if idx == 0:
            return "PERM"
        if idx == 1:
            return (today + timedelta(days=365)).strftime("%Y%m%d")
        if idx == 2:
            return (today + timedelta(days=180)).strftime("%Y%m%d")
        if idx == 3:
            return (today + timedelta(days=30)).strftime("%Y%m%d")
        if idx == 4:
            return (today + timedelta(days=7)).strftime("%Y%m%d")
        return self.ed_custom_exp.text().strip()

    def _generate(self):
        mid = normalize_machine_id(self.ed_mid.text())
        if not mid or len(mid) < 12:
            QMessageBox.warning(self, "Thiếu Mã máy", "Hãy nhập đúng Mã máy của khách hàng (VD: NHV-XXXX-XXXX-XXXX).")
            return
        self.ed_mid.setText(mid)
        exp = self._compute_expiry()
        try:
            key = generate_license_key(mid, exp)
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi tạo Key", str(exc))
            return
        self.ed_key.setText(key)
        QApplication.clipboard().setText(key)

        # Ghi sổ theo dõi khách hàng
        log_path = Path(__file__).resolve().parent / "danh_sach_khach_hang_key.csv"
        is_new = not log_path.exists()
        with open(log_path, "a", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["ThoiGian", "KhachHang", "MaMay", "ThoiHan", "MaKichHoat"])
            w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.ed_customer.text().strip(), mid, exp, key])
        QMessageBox.information(self, "Đã tạo & sao chép Key", f"Mã kích hoạt đã được sao chép vào clipboard:\n{key}\n\nĐã lưu vào: {log_path.name}")

    def _copy_key(self):
        if self.ed_key.text().strip():
            QApplication.clipboard().setText(self.ed_key.text().strip())


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = AdminKeygenWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
