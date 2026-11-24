"""Hệ thống tự động kiểm tra và cập nhật phiên bản mới qua GitHub Releases (bảo toàn bản quyền & dữ liệu)."""
from __future__ import annotations
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
import zipfile
from typing import Callable

APP_VERSION = "9.1.6"
DEFAULT_GITHUB_REPO = "HuynhDucVu/nganhangde-v10"

# Các tệp dữ liệu cá nhân của người dùng KHÔNG BAO GIỜ bị ghi đè khi tự động cập nhật
_PRESERVE_USER_FILES = {
    "license.json",
    "app_lock.json",
    "config.ini",
    "nganhang_mylt2026.db",
}


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str
    has_update: bool
    release_url: str = ""
    download_url: str = ""
    asset_name: str = ""
    release_notes: str = ""


def parse_version(ver: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", ver or "0")
    return tuple(int(x) for x in nums) if nums else (0,)


def _pick_best_asset(assets: list[dict]) -> tuple[str, str]:
    """Ưu tiên chọn đúng gói phát hành Windows/BanTinhPhi (.zip), sau đó mới tới .zip bất kỳ hoặc .exe."""
    zips = [
        (str(a.get("name") or ""), str(a.get("browser_download_url") or ""))
        for a in assets
        if str(a.get("name") or "").lower().endswith(".zip") and a.get("browser_download_url")
    ]
    for priority_kw in ("bantinhphi", "windows", "nganhangde_vu"):
        for name, url in zips:
            if priority_kw in name.lower():
                return url, name
    if zips:
        return zips[0][1], zips[0][0]
    for a in assets:
        name = str(a.get("name") or "")
        url = str(a.get("browser_download_url") or "")
        if name.lower().endswith(".exe") and url:
            return url, name
    return "", ""


def check_for_updates(repo: str = DEFAULT_GITHUB_REPO, timeout: int = 12) -> UpdateInfo:
    """Kiểm tra bản phát hành mới nhất trên GitHub Releases."""
    repo_clean = (repo or DEFAULT_GITHUB_REPO).strip().strip("/")
    api_url = f"https://api.github.com/repos/{repo_clean}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Nganhangde_vu/{APP_VERSION}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))

    tag = str(data.get("tag_name") or data.get("name") or "").lstrip("vV").strip()
    html_url = str(data.get("html_url") or f"https://github.com/{repo_clean}/releases")
    notes = str(data.get("body") or "").strip()

    dl_url, asset_name = _pick_best_asset(data.get("assets") or [])
    has_upd = parse_version(tag) > parse_version(APP_VERSION)
    return UpdateInfo(
        current_version=APP_VERSION,
        latest_version=tag or APP_VERSION,
        has_update=has_upd,
        release_url=html_url,
        download_url=dl_url,
        asset_name=asset_name,
        release_notes=notes,
    )


def download_and_install_update(
    info: UpdateInfo,
    on_progress: Callable[[int, str], None] | None = None,
) -> tuple[bool, str]:
    """Tải bản cập nhật, giữ nguyên bản quyền/dữ liệu người dùng và tự khởi động lại Nganhangde_vu.exe."""
    if not info.download_url:
        if info.release_url:
            webbrowser.open(info.release_url)
        return False, "Bản phát hành chưa đính kèm tệp .zip/.exe. Đã mở trang GitHub Releases trên trình duyệt."

    if os.name != "nt" or not getattr(sys, "frozen", False):
        if info.release_url:
            webbrowser.open(info.release_url)
        return False, (
            "Đang chạy từ mã nguồn Python (không phải Nganhangde_vu.exe). "
            "Đã mở trang tải bản mới trên trình duyệt."
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="nganhangde_update_"))
    dl_file = tmp_dir / (info.asset_name or "update.zip")

    if on_progress:
        on_progress(5, f"Đang tải {dl_file.name}...")

    req = urllib.request.Request(
        info.download_url,
        headers={"User-Agent": f"Nganhangde_vu/{APP_VERSION}"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dl_file, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if on_progress and total > 0:
                    pct = min(85, int(5 + (done / total) * 80))
                    on_progress(pct, f"Đang tải {done // 1024} / {total // 1024} KB...")

    app_dir = Path(sys.executable).resolve().parent
    exe_name = Path(sys.executable).name

    if dl_file.suffix.lower() == ".zip":
        if on_progress:
            on_progress(90, "Đang giải nén bản cập nhật (bảo toàn bản quyền & dữ liệu)...")
        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dl_file, "r") as zf:
            zf.extractall(extract_dir)

        src_root = extract_dir
        found_exes = list(extract_dir.rglob("*.exe"))
        if found_exes:
            src_root = found_exes[0].parent

        # Xoá các tệp cấu hình/dữ liệu mẫu trong gói mới nếu máy khách đã có sẵn để không bị mất Key/API/DB
        for fname in _PRESERVE_USER_FILES:
            if (app_dir / fname).exists():
                cand = src_root / fname
                if cand.exists():
                    cand.unlink(missing_ok=True)

        bat_path = tmp_dir / "apply_update.bat"
        bat_code = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            f'xcopy /E /Y /I "{src_root}\\*" "{app_dir}\\" >nul\r\n'
            f'start "" "{app_dir}\\{exe_name}"\r\n'
            "exit\r\n"
        )
        bat_path.write_text(bat_code, encoding="utf-8")
        subprocess.Popen(["cmd.exe", "/c", str(bat_path)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True, "Đã tải xong bản cập nhật (giữ nguyên bản quyền và dữ liệu của bạn). Phần mềm sẽ tự khởi động lại."

    bat_path = tmp_dir / "apply_update.bat"
    bat_code = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f'copy /Y "{dl_file}" "{app_dir}\\{exe_name}" >nul\r\n'
        f'start "" "{app_dir}\\{exe_name}"\r\n'
        "exit\r\n"
    )
    bat_path.write_text(bat_code, encoding="utf-8")
    subprocess.Popen(["cmd.exe", "/c", str(bat_path)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True, "Đã tải xong tệp .exe mới. Phần mềm sẽ tự đóng và khởi động lại phiên bản mới."
