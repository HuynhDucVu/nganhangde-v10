"""Hộp thoại Kích hoạt bản quyền theo Mã máy & Mật khẩu mở ứng dụng Nganhangde_vu."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from ..core.licensing import (
    LicenseStatus,
    get_machine_id,
    has_app_password,
    load_license_status,
    save_license,
    set_app_password,
    verify_app_password,
)


class LicenseActivationDialog(QDialog):
    """Cửa sổ hiển thị Mã máy và nhập Mã kích hoạt bản quyền (bản tính phí)."""

    def __init__(self, status: LicenseStatus | None = None, parent=None):
        super().__init__(parent)
        self.status = status or load_license_status()
        self.activated_status: LicenseStatus | None = None
        self.setWindowTitle("Kích hoạt bản quyền — Nganhangde_vu")
        self.setMinimumWidth(520)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lbl_head = QLabel(
            "<h3 style='margin:0; color:#0f4c81;'>KÍCH HOẠT BẢN QUYỀN NGANHANGDE_VU</h3>"
            "<p style='margin:4px 0 0 0; color:#334155;'>"
            "Bản phần mềm tính phí gắn theo <b>Mã máy</b>. "
            "Hãy bấm <b>Sao chép Mã máy</b> gửi cho tác giả để nhận <b>Mã kích hoạt</b>.</p>"
        )
        lbl_head.setWordWrap(True)
        lay.addWidget(lbl_head)

        if self.status.message and not self.status.valid:
            lbl_err = QLabel(f"Trạng thái: {self.status.message}")
            lbl_err.setStyleSheet("color: #b91c1c; font-weight: 600;")
            lbl_err.setWordWrap(True)
            lay.addWidget(lbl_err)

        form = QFormLayout()
        form.setSpacing(8)

        mid_row = QHBoxLayout()
        self.ed_mid = QLineEdit(self.status.machine_id or get_machine_id())
        self.ed_mid.setReadOnly(True)
        self.ed_mid.setStyleSheet("font-weight: bold; font-size: 11pt; background: #f1f5f9; color: #0f172a;")
        b_copy = QPushButton("Sao chép Mã máy")
        b_copy.clicked.connect(self._copy_mid)
        mid_row.addWidget(self.ed_mid, 1)
        mid_row.addWidget(b_copy)
        form.addRow("Mã máy của bạn:", mid_row)

        self.ed_owner = QLineEdit(self.status.owner)
        self.ed_owner.setPlaceholderText("VD: Thầy Nguyễn Văn A — THPT ...")
        form.addRow("Họ tên / Đơn vị:", self.ed_owner)

        self.ed_key = QLineEdit(self.status.license_key)
        self.ed_key.setPlaceholderText("Dán mã kích hoạt (VD: PRO-PERM-XXXXXXXXXXXX)...")
        form.addRow("Mã kích hoạt:", self.ed_key)
        lay.addLayout(form)

        bot = QHBoxLayout()
        b_act = QPushButton("Kích hoạt ngay")
        b_act.setStyleSheet("font-weight: bold; padding: 6px 16px; background: #1d4ed8; color: white; border-radius: 4px;")
        b_act.clicked.connect(self._activate)
        b_cancel = QPushButton("Thoát")
        b_cancel.clicked.connect(self.reject)
        bot.addStretch()
        bot.addWidget(b_act)
        bot.addWidget(b_cancel)
        lay.addLayout(bot)

    def _copy_mid(self):
        QApplication.clipboard().setText(self.ed_mid.text().strip())
        QMessageBox.information(self, "Đã sao chép", f"Đã sao chép Mã máy:\n{self.ed_mid.text().strip()}\n\nHãy dán gửi cho tác giả qua Zalo/Email để nhận Mã kích hoạt.")

    def _activate(self):
        key = self.ed_key.text().strip()
        owner = self.ed_owner.text().strip()
        if not key:
            QMessageBox.warning(self, "Thiếu mã kích hoạt", "Vui lòng dán Mã kích hoạt do tác giả cấp.")
            return
        st = save_license(key, owner)
        if st.valid:
            self.activated_status = st
            QMessageBox.information(
                self,
                "Kích hoạt thành công",
                f"Đã kích hoạt bản quyền thành công!\n- Mã máy: {st.machine_id}\n- Thời hạn: {st.expiry_display}",
            )
            self.accept()
        else:
            QMessageBox.critical(self, "Kích hoạt thất bại", st.message)


class AppPasswordDialog(QDialog):
    """Hộp thoại nhập mật khẩu mở phần mềm (nếu người dùng bật khoá mật khẩu)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Đăng nhập — Nganhangde_vu")
        self.setMinimumWidth(360)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Nhập mật khẩu để mở phần mềm Nganhangde_vu:"))
        self.ed_pw = QLineEdit()
        self.ed_pw.setEchoMode(QLineEdit.Password)
        self.ed_pw.returnPressed.connect(self._check)
        lay.addWidget(self.ed_pw)
        row = QHBoxLayout()
        b_ok = QPushButton("Mở phần mềm"); b_ok.clicked.connect(self._check)
        b_exit = QPushButton("Thoát"); b_exit.clicked.connect(self.reject)
        row.addStretch(); row.addWidget(b_ok); row.addWidget(b_exit)
        lay.addLayout(row)

    def _check(self):
        if verify_app_password(self.ed_pw.text()):
            self.accept()
        else:
            QMessageBox.warning(self, "Sai mật khẩu", "Mật khẩu không chính xác. Vui lòng thử lại.")
            self.ed_pw.clear()
            self.ed_pw.setFocus()


def configure_app_password_dialog(parent=None) -> None:
    """Cho phép người dùng đặt, đổi hoặc gỡ mật khẩu mở ứng dụng trong tab Thông tin."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Cài đặt mật khẩu mở phần mềm")
    dlg.setMinimumWidth(400)
    lay = QVBoxLayout(dlg)
    form = QFormLayout()
    ed_old = QLineEdit(); ed_old.setEchoMode(QLineEdit.Password)
    ed_new = QLineEdit(); ed_new.setEchoMode(QLineEdit.Password); ed_new.setPlaceholderText("Để trống để tắt mật khẩu")
    ed_cfm = QLineEdit(); ed_cfm.setEchoMode(QLineEdit.Password)
    currently_locked = has_app_password()
    if currently_locked:
        form.addRow("Mật khẩu hiện tại:", ed_old)
    form.addRow("Mật khẩu mới:", ed_new)
    form.addRow("Nhập lại mật khẩu mới:", ed_cfm)
    lay.addLayout(form)

    row = QHBoxLayout()
    b_save = QPushButton("Lưu mật khẩu")
    b_cancel = QPushButton("Huỷ"); b_cancel.clicked.connect(dlg.reject)
    row.addStretch(); row.addWidget(b_save); row.addWidget(b_cancel)
    lay.addLayout(row)

    def _save():
        if currently_locked and not verify_app_password(ed_old.text()):
            QMessageBox.warning(dlg, "Sai mật khẩu", "Mật khẩu hiện tại không đúng.")
            return
        if ed_new.text() != ed_cfm.text():
            QMessageBox.warning(dlg, "Không khớp", "Mật khẩu nhập lại không khớp.")
            return
        set_app_password(ed_new.text())
        msg = "Đã tắt mật khẩu mở phần mềm." if not ed_new.text().strip() else "Đã lưu mật khẩu bảo vệ mở phần mềm thành công."
        QMessageBox.information(dlg, "Mật khẩu phần mềm", msg)
        dlg.accept()

    b_save.clicked.connect(_save)
    dlg.exec()


def ensure_licensed_and_unlocked() -> bool:
    """Kiểm tra bản quyền theo Mã máy + Mật khẩu trước khi mở cửa sổ chính."""
    st = load_license_status()
    if not st.valid:
        dlg = LicenseActivationDialog(st)
        if dlg.exec() != QDialog.Accepted:
            return False
    if has_app_password():
        pw_dlg = AppPasswordDialog()
        if pw_dlg.exec() != QDialog.Accepted:
            return False
    return True
