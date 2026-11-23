"""Chuyển mã nguồn sang chế độ BẢN TÍNH PHÍ trước khi đóng gói (dùng trong CI).

- licensing.py: AUTHOR_PRO_MODE = True -> False (bắt buộc kích hoạt Key)
- NganHangDe.spec: tên exe Nganhangde_vu-pro -> Nganhangde_vu
"""
from pathlib import Path
import sys

LIC = Path("nganhangde/core/licensing.py")
SPEC = Path("NganHangDe.spec")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) < 1:
        sys.exit(f"[LOI] Khong tim thay '{old}' trong {path}")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"OK: {path}: '{old}' -> '{new}'")


replace_once(LIC, "AUTHOR_PRO_MODE = True", "AUTHOR_PRO_MODE = False")
replace_once(SPEC, 'name="Nganhangde_vu-pro"', 'name="Nganhangde_vu"')
