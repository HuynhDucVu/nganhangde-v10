"""Nhúng hoặc khôi phục khóa bản quyền trong nganhangde/core/licensing.py.

Dùng:
  NGANHANGDE_LICENSE_SECRET=<khóa> python tools/set_license_secret.py inject
  python tools/set_license_secret.py restore

- inject : thay placeholder bằng khóa lấy từ biến môi trường (dùng khi build bản phát hành).
- restore: đưa lại placeholder để khóa không còn nằm trong thư mục làm việc sau khi build.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys

TARGET = Path(__file__).resolve().parent.parent / "nganhangde" / "core" / "licensing.py"
PLACEHOLDER = "__NGANHANGDE_LICENSE_SECRET__"
LINE_RE = re.compile(r"^_LICENSE_SECRET = .*$", re.MULTILINE)


def inject() -> None:
    secret = os.environ.get("NGANHANGDE_LICENSE_SECRET", "").strip()
    if not secret:
        sys.exit("[LOI] Chua dat bien moi truong NGANHANGDE_LICENSE_SECRET.")
    text = TARGET.read_text(encoding="utf-8")
    new_text, n = LINE_RE.subn(lambda _m: f"_LICENSE_SECRET = {secret!r}", text, count=1)
    if n != 1:
        sys.exit("[LOI] Khong tim thay dong _LICENSE_SECRET trong licensing.py.")
    TARGET.write_text(new_text, encoding="utf-8")
    print("Da nhung khoa ban quyen vao licensing.py (tam thoi).")


def restore() -> None:
    text = TARGET.read_text(encoding="utf-8")
    new_text, n = LINE_RE.subn(f'_LICENSE_SECRET = "{PLACEHOLDER}"', text, count=1)
    if n != 1:
        sys.exit("[LOI] Khong tim thay dong _LICENSE_SECRET trong licensing.py.")
    TARGET.write_text(new_text, encoding="utf-8")
    print("Da khoi phuc placeholder trong licensing.py.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"inject", "restore"}:
        sys.exit("Dung: python tools/set_license_secret.py inject|restore")
    inject() if sys.argv[1] == "inject" else restore()
