#!/usr/bin/env python3
"""Phát hành bản cập nhật Nganhangde_vu: nhận code mới (thư mục hoặc .zip từ Gemini),
kiểm tra an toàn, tăng APP_VERSION, commit, tạo tag và push. GitHub Actions sẽ tự build
bản tính phí và đăng Release để máy khách tự cập nhật.

Ví dụ:
  python tools/publish_update.py ban_gemini.zip --version 7.9.1 -m "Sua loi xuat PDF"
  python tools/publish_update.py ban_gemini/ --version 7.9.1 -m "..." --dry-run

--dry-run: làm toàn bộ bước trên một bản sao tạm, không đụng repo thật và không push.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LICENSING = Path("nganhangde/core/licensing.py")
UPDATER = Path("nganhangde/core/updater.py")
PLACEHOLDER = "__NGANHANGDE_LICENSE_SECRET__"
VERSION_RE = re.compile(r'^APP_VERSION = "([0-9]+(?:\.[0-9]+)*)"', re.MULTILINE)
SECRET_RE = re.compile(r'^_LICENSE_SECRET = (.*)$', re.MULTILINE)
SKIP_DIRS = {".git", "__pycache__", "dist", "build", ".pytest_cache", ".venv", "venv"}
SKIP_SUFFIXES = {".pyc", ".db", ".db-journal", ".log"}


def die(msg: str) -> None:
    print(f"[LOI] {msg}")
    sys.exit(1)


def git(args: list[str], cwd: Path, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if check and r.returncode != 0:
        die(f"git {' '.join(args)} that bai:\n{r.stdout}{r.stderr}")
    return r.stdout.strip()


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def read_current_version(root: Path) -> str:
    m = VERSION_RE.search((root / UPDATER).read_text(encoding="utf-8"))
    if not m:
        die(f"Khong tim thay APP_VERSION trong {UPDATER}")
    return m.group(1)


def extract_source(src: Path, dest: Path) -> Path:
    """Trả về thư mục gốc chứa code mới. Zip được giải nén an toàn (chặn đường dẫn '..')."""
    if src.is_dir():
        return src
    if not (src.is_file() and zipfile.is_zipfile(src)):
        die(f"Nguon phai la thu muc hoac file .zip: {src}")
    base = dest.resolve()
    with zipfile.ZipFile(src) as z:
        for info in z.infolist():
            target = (dest / info.filename).resolve()
            if target != base and base not in target.parents:
                die(f"File zip co duong dan khong an toan: {info.filename}")
        z.extractall(dest)
    entries = [p for p in dest.iterdir() if p.name != "__MACOSX"]
    return entries[0] if len(entries) == 1 and entries[0].is_dir() else dest


def copy_code(src_root: Path, repo: Path) -> int:
    """Chép code mới vào repo, bỏ qua thư mục build, cache và file dữ liệu cục bộ."""
    count = 0
    for path in src_root.rglob("*"):
        rel = path.relative_to(src_root)
        if any(part in SKIP_DIRS for part in rel.parts) or path.suffix in SKIP_SUFFIXES:
            continue
        if not path.is_file():
            continue
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        count += 1
    return count


def verify_source(work: Path, version: str, skip_tests: bool) -> None:
    text = (work / LICENSING).read_text(encoding="utf-8")
    m = SECRET_RE.search(text)
    if not m:
        die("licensing.py thieu dong _LICENSE_SECRET.")
    if m.group(1).strip() != f'"{PLACEHOLDER}"':
        die("licensing.py dang chua khoa bi mat cung (khong phai placeholder). "
            "Hay xoa khoa do khoi ma nguon truoc khi phat hanh.")
    if "AUTHOR_PRO_MODE = True" not in text:
        die("licensing.py phai giu AUTHOR_PRO_MODE = True trong ma nguon (CI tu chuyen sang ban tinh phi).")

    py = sys.executable
    r = subprocess.run([py, "-m", "compileall", "-q", "nganhangde", "tests", "tools", "run_gui.py"],
                       cwd=work, capture_output=True, text=True)
    if r.returncode != 0:
        die(f"Loi cu phap Python:\n{r.stdout}{r.stderr}")

    if skip_tests:
        print("[CANH BAO] Bo qua test (--skip-tests).")
        return
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    r = subprocess.run([py, "-m", "pytest", "-q",
                        "tests/test_extest_v33.py", "tests/test_shuffler_invariants.py",
                        "tests/test_cv7991_cv1239.py", "tests/test_db_fts5_migration.py",
                        "tests/test_converters_mock.py"],
                       cwd=work, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        die(f"Test that bai, KHONG phat hanh:\n{r.stdout[-3000:]}{r.stderr[-1000:]}")
    print("Test: ", r.stdout.strip().splitlines()[-1])


def set_version(work: Path, version: str) -> None:
    p = work / UPDATER
    text = p.read_text(encoding="utf-8")
    new_text, n = VERSION_RE.subn(f'APP_VERSION = "{version}"', text, count=1)
    if n != 1:
        die("Khong cap nhat duoc APP_VERSION.")
    p.write_text(new_text, encoding="utf-8")


def publish(work: Path, src_root: Path, version: str, message: str, skip_tests: bool, push: bool) -> None:
    tag = f"v{version}"
    copied = copy_code(src_root, work)
    print(f"Da chep {copied} file vao repo.")
    verify_source(work, version, skip_tests)
    set_version(work, version)

    git(["add", "-A"], work)
    if not git(["status", "--porcelain"], work):
        die("Khong co thay doi nao so voi ban hien tai.")
    print("Thay doi:")
    print(git(["diff", "--cached", "--stat"], work))
    git(["commit", "-q", "-m", f"Phien ban {version}: {message}"], work)
    git(["tag", "-a", tag, "-m", f"Nganhangde_vu-pro {version}"], work)
    print(f"Da commit va tao tag {tag}.")

    if push:
        git(["push", "--atomic", "origin", "main", tag], work)
        print(f"DA PUSH {tag}. GitHub Actions dang build va dang Release.")
    else:
        print(f"[DRY-RUN] Khong push. Commit thu: {git(['log', '-1', '--oneline'], work)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="Thu muc hoac file .zip chua code moi")
    ap.add_argument("--version", required=True, help="Phien ban moi, vi du 7.9.1")
    ap.add_argument("-m", "--message", required=True, help="Mo ta ngan cac thay doi")
    ap.add_argument("--dry-run", action="store_true", help="Thu tren ban sao tam, khong push")
    ap.add_argument("--skip-tests", action="store_true", help="Bo qua pytest (khong khuyen khich)")
    args = ap.parse_args()

    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        die("Phien ban phai dang X.Y.Z, vi du 7.9.1")
    if not (REPO / ".git").exists():
        die("Thu muc nay khong phai git repo.")
    if git(["rev-parse", "--abbrev-ref", "HEAD"], REPO) != "main":
        die("Hay chuyen ve nhanh main truoc khi phat hanh.")
    if git(["status", "--porcelain"], REPO):
        die("Repo co thay doi chua commit. Hay commit hoac stash truoc.")

    current = read_current_version(REPO)
    if parse_version(args.version) <= parse_version(current):
        die(f"Phien ban {args.version} phai lon hon phien ban hien tai {current}.")

    tag = f"v{args.version}"
    git(["fetch", "--quiet", "--tags", "origin"], REPO)
    if git(["tag", "--list", tag], REPO):
        die(f"Tag {tag} da ton tai. Hay dung so phien ban moi.")
    if git(["ls-remote", "--tags", "origin", f"refs/tags/{tag}"], REPO):
        die(f"Tag {tag} da ton tai tren GitHub.")
    print(f"Phien ban: {current} -> {args.version}")

    with tempfile.TemporaryDirectory(prefix="publish_") as tmp_name:
        tmp = Path(tmp_name)
        src_root = extract_source(Path(args.source).expanduser().resolve(), tmp / "src")
        if args.dry_run:
            work = tmp / "repo"
            shutil.copytree(REPO, work, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            work = REPO
        try:
            publish(work, src_root, args.version, args.message, args.skip_tests, push=not args.dry_run)
        except SystemExit:
            if not args.dry_run:
                # Repo đã sạch trước khi chạy, nên đưa về đúng trạng thái đó khi lỗi.
                subprocess.run(["git", "reset", "--hard", "-q"], cwd=REPO)
                subprocess.run(["git", "clean", "-fdq"], cwd=REPO)
                print("Da khoi phuc repo ve trang thai truoc khi chay.")
            raise


if __name__ == "__main__":
    main()
