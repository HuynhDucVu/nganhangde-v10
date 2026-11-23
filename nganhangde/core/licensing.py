"""Hệ thống bản quyền gắn mã máy (Hardware ID) & Mật khẩu mở ứng dụng cho Nganhangde_vu."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import uuid
from ..paths import user_data_dir

# ==============================================================================
# KHÓA BÍ MẬT CẤP BẢN QUYỀN (Tác giả có thể đổi chuỗi này trước khi build .exe)
# Lưu ý: công cụ cấp Key (lưu riêng ngoài repo) dùng chung khóa này từ module nganhangde.core.licensing.
# ==============================================================================
# True  = Bản Tác giả (-pro): mở thẳng không cần nhập Key kích hoạt.
# False = Bản Tính phí gửi khách: bắt buộc kích hoạt theo Mã máy.
AUTHOR_PRO_MODE = True

# Khóa bí mật KHÔNG được lưu trong mã nguồn. Khi build, GitHub Actions hoặc
# build_exe_ban_tinh_phi.bat thay placeholder này bằng biến môi trường
# NGANHANGDE_LICENSE_SECRET (xem tools/set_license_secret.py).
_LICENSE_PLACEHOLDER = "__NGANHANGDE_LICENSE_SECRET__"
_LICENSE_SECRET = "__NGANHANGDE_LICENSE_SECRET__"
LICENSE_FILENAME = "license.json"
APP_PASS_FILENAME = "app_lock.json"


@dataclass
class LicenseStatus:
    valid: bool
    machine_id: str
    license_key: str = ""
    owner: str = ""
    expiry: str = ""          # "PERM" hoặc "YYYYMMDD"
    message: str = ""

    @property
    def expiry_display(self) -> str:
        if self.expiry == "PERM":
            return "Vĩnh viễn"
        if len(self.expiry) == 8 and self.expiry.isdigit():
            return f"{self.expiry[6:8]}/{self.expiry[4:6]}/{self.expiry[0:4]}"
        return self.expiry or "Chưa kích hoạt"


def _read_windows_machine_guid() -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            val, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(val or "").strip()
    except Exception:
        return ""


def _read_windows_board_serial() -> str:
    if os.name != "nt":
        return ""
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_BaseBoard).SerialNumber"],
            stderr=subprocess.DEVNULL,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        txt = out.decode("utf-8", errors="ignore").strip()
        if txt and txt.lower() not in ("default string", "to be filled by o.e.m.", "none", "0"):
            return txt
    except Exception:
        pass
    return ""


def get_machine_id() -> str:
    """Sinh mã máy ổn định duy nhất dạng NHV-XXXX-XXXX-XXXX cho từng máy tính."""
    parts = [
        _read_windows_machine_guid(),
        _read_windows_board_serial(),
        platform.machine(),
        os.environ.get("PROCESSOR_IDENTIFIER", ""),
    ]
    # Chỉ bổ sung MAC node nếu không đọc được MachineGuid (ví dụ chạy trên Linux/macOS)
    if not parts[0]:
        parts.append(str(uuid.getnode()))
        parts.append(platform.node())

    raw = "|".join(p.strip().upper() for p in parts if p and p.strip())
    if not raw:
        raw = f"FALLBACK-{uuid.getnode()}"
    digest = hashlib.sha256(f"NHV-HWID::{raw}".encode("utf-8")).hexdigest().upper()
    return f"NHV-{digest[0:4]}-{digest[4:8]}-{digest[8:12]}"


def normalize_machine_id(mid: str) -> str:
    clean = re.sub(r"[^A-Z0-9]", "", (mid or "").upper())
    if clean.startswith("NHV") and len(clean) == 15:
        return f"NHV-{clean[3:7]}-{clean[7:11]}-{clean[11:15]}"
    return (mid or "").strip().upper()


def generate_license_key(machine_id: str, expiry: str = "PERM") -> str:
    """Tạo mã kích hoạt bản quyền gắn chặt với machine_id và thời hạn ('PERM' hoặc 'YYYYMMDD')."""
    mid = normalize_machine_id(machine_id)
    exp = (expiry or "PERM").strip().upper()
    if exp != "PERM":
        if not re.fullmatch(r"\d{8}", exp):
            raise ValueError("Thời hạn phải là 'PERM' (vĩnh viễn) hoặc định dạng YYYYMMDD (VD: 20271231).")
    payload = f"{mid}|{exp}".encode("utf-8")
    sig = hmac.new(_license_secret_bytes(), payload, hashlib.sha256).hexdigest().upper()[:12]
    return f"PRO-{exp}-{sig}"


def _license_secret_bytes() -> bytes:
    """Lấy khóa bản quyền: đã nhúng lúc build, hoặc đọc từ biến môi trường khi chạy từ mã nguồn."""
    secret = _LICENSE_SECRET
    if secret == _LICENSE_PLACEHOLDER:
        secret = os.environ.get("NGANHANGDE_LICENSE_SECRET", "").strip()
    if not secret:
        raise RuntimeError("Chưa cấu hình khóa bản quyền (biến môi trường NGANHANGDE_LICENSE_SECRET).")
    return secret.encode("utf-8")


def verify_license_key(machine_id: str, license_key: str) -> tuple[bool, str, str]:
    """Kiểm tra mã kích hoạt. Trả về (hợp_lệ, expiry, thông_báo)."""
    mid = normalize_machine_id(machine_id)
    key = (license_key or "").strip().upper()
    m = re.fullmatch(r"PRO-(PERM|\d{8})-([A-F0-9]{12})", key)
    if not m:
        return False, "", "Định dạng mã kích hoạt không hợp lệ (đúng dạng: PRO-PERM-XXXXXXXXXXXX hoặc PRO-YYYYMMDD-XXXXXXXXXXXX)."
    exp, sig = m.group(1), m.group(2)
    expected = generate_license_key(mid, exp)
    if not hmac.compare_digest(key, expected):
        return False, exp, "Mã kích hoạt không khớp với Mã máy này. Vui lòng liên hệ tác giả để cấp đúng mã."
    if exp != "PERM":
        try:
            exp_date = datetime.strptime(exp, "%Y%m%d").date()
        except ValueError:
            return False, exp, "Ngày hết hạn trong mã kích hoạt không hợp lệ."
        if date.today() > exp_date:
            return False, exp, f"Bản quyền đã hết hạn vào ngày {exp_date.strftime('%d/%m/%Y')}. Vui lòng gia hạn."
    return True, exp, "Kích hoạt bản quyền thành công!"


def license_file_path() -> Path:
    return user_data_dir() / LICENSE_FILENAME


def load_license_status() -> LicenseStatus:
    mid = get_machine_id()
    if AUTHOR_PRO_MODE:
        return LicenseStatus(
            valid=True,
            machine_id=mid,
            license_key="PRO-AUTHOR-UNLIMITED",
            owner="Tác giả (Bản Pro)",
            expiry="PERM",
            message="Bản Tác giả Pro — không yêu cầu Key kích hoạt.",
        )
    fp = license_file_path()
    if not fp.exists():
        return LicenseStatus(False, mid, message="Chưa kích hoạt bản quyền trên máy này.")
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return LicenseStatus(False, mid, message="Tệp bản quyền bị lỗi định dạng.")
    key = str(data.get("license_key") or "").strip()
    owner = str(data.get("owner") or "").strip()
    ok, exp, msg = verify_license_key(mid, key)
    return LicenseStatus(ok, mid, key, owner, exp, msg)


def save_license(license_key: str, owner: str = "") -> LicenseStatus:
    mid = get_machine_id()
    ok, exp, msg = verify_license_key(mid, license_key)
    if not ok:
        return LicenseStatus(False, mid, license_key, owner, exp, msg)
    payload = {
        "machine_id": mid,
        "license_key": license_key.strip().upper(),
        "owner": owner.strip(),
        "expiry": exp,
        "activated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    license_file_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return LicenseStatus(True, mid, payload["license_key"], payload["owner"], exp, msg)


# ==============================================================================
# MẬT KHẨU BẢO VỆ MỞ ỨNG DỤNG (APP PASSWORD — tuỳ chọn cài thêm trong tab Thông tin)
# ==============================================================================
def app_pass_file_path() -> Path:
    return user_data_dir() / APP_PASS_FILENAME


def has_app_password() -> bool:
    fp = app_pass_file_path()
    if not fp.exists():
        return False
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        return bool(data.get("hash") and data.get("salt"))
    except Exception:
        return False


def set_app_password(password: str) -> None:
    fp = app_pass_file_path()
    pw = (password or "").strip()
    if not pw:
        if fp.exists():
            fp.unlink(missing_ok=True)
        return
    salt = hashlib.sha256(f"{get_machine_id()}|{datetime.now().isoformat()}".encode("utf-8")).hexdigest()[:16]
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    fp.write_text(json.dumps({"salt": salt, "hash": h}, indent=2), encoding="utf-8")


def verify_app_password(password: str) -> bool:
    fp = app_pass_file_path()
    if not fp.exists():
        return True
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        salt = str(data.get("salt") or "")
        saved_h = str(data.get("hash") or "")
        calc_h = hashlib.pbkdf2_hmac("sha256", (password or "").strip().encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
        return hmac.compare_digest(calc_h, saved_h)
    except Exception:
        return False
