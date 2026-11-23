"""Bộ đọc & chuyển đổi SIÊU TỐC tệp ngân hàng Bank.mylt (Microsoft Access Jet 4.0) sang nganhang.db / .tex."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from typing import Callable
from ..core.parser import parse_tex_questions


def _rc4(key: bytes, buf: bytes) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) & 0xFF
        s[i], s[j] = s[j], s[i]
    i = j = 0
    out = bytearray()
    for b in buf:
        i = (i + 1) & 0xFF
        j = (j + s[i]) & 0xFF
        s[i], s[j] = s[j], s[i]
        out.append(b ^ s[(s[i] + s[j]) & 0xFF])
    return bytes(out)


def extract_jet4_password(mdb_path: Path) -> str:
    """Tự động giải mã mật khẩu database lưu trong header chuẩn Jet 4.0 (.mylt / .mdb)."""
    try:
        with open(mdb_path, "rb") as f:
            data = f.read(0xA0)
        if len(data) < 0x98 or data[0x14] != 1:
            return ""
        dec = _rc4(bytes([0xC7, 0xDA, 0x39, 0x6B]), data[0x18:0x98])
        pw_raw = dec[0x2A:0x52]
        mask_even = struct.unpack_from("<H", pw_raw, 36)[0]
        chars: list[str] = []
        for idx in range(20):
            val = struct.unpack_from("<H", pw_raw, idx * 2)[0]
            if idx % 2 == 0:
                val ^= mask_even
            if val == 0:
                break
            chars.append(chr(val))
        return "".join(chars)
    except Exception:
        return ""


def _read_quest_rows_ps32(mdb_path: Path, password: str = "") -> list[tuple[str, str]]:
    """Đọc siêu tốc tệp Jet 4.0 (.mylt/.mdb) bằng C# (Add-Type) chạy trên PowerShell 32-bit có sẵn của Windows."""
    if os.name != "nt":
        raise RuntimeError("PowerShell 32-bit chỉ hỗ trợ trên Windows.")

    ps32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if not ps32.exists():
        ps32 = Path(shutil.which("powershell") or "powershell")

    out_dump = mdb_path.parent / "quest_dump.dat"
    pw_file = mdb_path.parent / "pw.txt"
    ps_script = mdb_path.parent / "read_mylt_fast.ps1"

    pw_file.write_text(password, encoding="utf-8")

    # Biên dịch vòng đọc bằng C# (.NET có sẵn trên Windows) + bộ đệm 128KB -> nhanh gấp 30-50 lần vòng lặp PowerShell!
    ps_code = r"""param([string]$MdbPath, [string]$OutFile, [string]$PwFile)
$ErrorActionPreference = "Stop"
$PwdStr = ""
if (Test-Path $PwFile) {
    $PwdStr = [System.IO.File]::ReadAllText($PwFile, [System.Text.Encoding]::UTF8)
}

$csCode = @"
using System;
using System.Data.OleDb;
using System.IO;
using System.Text;

public static class FastMyltReader {
    public static int Dump(string mdbPath, string outFile, string pwd) {
        string[] providers = new string[] { "Microsoft.Jet.OLEDB.4.0", "Microsoft.ACE.OLEDB.12.0" };
        OleDbConnection conn = null;
        string lastErr = "";
        foreach (var prov in providers) {
            try {
                string cs = "Provider=" + prov + ";Data Source=" + mdbPath + ";";
                if (!string.IsNullOrEmpty(pwd)) cs += "Jet OLEDB:Database Password=" + pwd + ";";
                var c = new OleDbConnection(cs);
                c.Open();
                conn = c;
                break;
            } catch (Exception ex) {
                lastErr = ex.Message;
            }
        }
        if (conn == null) throw new Exception("OLEDB-32bit Open failed: " + lastErr);
        int count = 0;
        try {
            using (var cmd = conn.CreateCommand()) {
                cmd.CommandText = "SELECT NoiDung, IDCauHoi FROM QUEST";
                using (var reader = cmd.ExecuteReader())
                using (var sw = new StreamWriter(outFile, false, new UTF8Encoding(false), 131072)) {
                    while (reader.Read()) {
                        string nd = reader.IsDBNull(0) ? "" : Convert.ToString(reader.GetValue(0));
                        string cid = reader.IsDBNull(1) ? "" : Convert.ToString(reader.GetValue(1));
                        sw.Write(cid);
                        sw.Write('\x1f');
                        sw.Write(nd);
                        sw.Write('\x1e');
                        count++;
                    }
                }
            }
        } finally {
            conn.Close();
        }
        return count;
    }
}
"@

Add-Type -TypeDefinition $csCode -ReferencedAssemblies "System.Data"
[FastMyltReader]::Dump($MdbPath, $OutFile, $PwdStr) | Out-Null
"""
    ps_script.write_text(ps_code, encoding="utf-8")

    creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    proc = subprocess.run(
        [
            str(ps32),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps_script),
            str(mdb_path),
            str(out_dump),
            str(pw_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
        creationflags=creationflags,
    )
    if proc.returncode != 0 or not out_dump.exists():
        err = proc.stderr.decode("utf-8", errors="replace").strip() or proc.stdout.decode("utf-8", errors="replace").strip()
        raise RuntimeError(err or "PowerShell 32-bit không xuất được dữ liệu.")

    rows: list[tuple[str, str]] = []
    raw_dump = out_dump.read_text(encoding="utf-8", errors="replace")
    if "\x1e" in raw_dump or "\x1f" in raw_dump:
        for rec in raw_dump.split("\x1e"):
            if not rec:
                continue
            if "\x1f" in rec:
                cid, nd = rec.split("\x1f", 1)
            else:
                cid, nd = "", rec
            if nd.strip():
                rows.append((nd, cid.strip()))
    else:
        for line in raw_dump.splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            rows.append((str(item.get("NoiDung") or ""), str(item.get("IDCauHoi") or "")))
    return rows


def _read_quest_rows_pyodbc(mdb_path: Path, password: str = "") -> list[tuple[str, str]]:
    import pyodbc

    drivers = [
        "{Microsoft Access Driver (*.mdb, *.accdb)}",
        "{Microsoft Access Driver (*.mdb)}",
    ]
    last_err: Exception | None = None
    for drv in drivers:
        conn_str = f"DRIVER={drv};DBQ={mdb_path};"
        if password:
            conn_str += f"PWD={password};"
        try:
            conn = pyodbc.connect(conn_str, autocommit=True)
            try:
                cur = conn.cursor()
                cur.execute("SELECT NoiDung, IDCauHoi FROM QUEST")
                return [(str(r[0] or ""), str(r[1] or "")) for r in cur.fetchall()]
            finally:
                conn.close()
        except Exception as exc:
            last_err = exc
    if last_err:
        raise last_err
    return []


def read_mylt_bank_rows(mylt_path: str | Path, password: str = "") -> list[tuple[str, str]]:
    """Đọc toàn bộ (NoiDung, IDCauHoi) từ bảng QUEST trong tệp .mylt (ưu tiên mật khẩu giải mã tự động trước)."""
    src = Path(mylt_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp: {src}")

    with tempfile.TemporaryDirectory(prefix="mylt_imp_") as td:
        tmp_mdb = Path(td) / "bank_copy.mdb"
        shutil.copy2(src, tmp_mdb)

        auto_pw = extract_jet4_password(tmp_mdb)
        pw_candidates: list[str] = []
        raw_cands = [password] if password else []
        raw_cands.extend([auto_pw, "MyLT@2018", "MyLT123", ""])
        for cand in raw_cands:
            if cand is not None and cand not in pw_candidates:
                pw_candidates.append(cand)

        ole_errors: list[str] = []
        for pw in pw_candidates:
            try:
                return _read_quest_rows_ps32(tmp_mdb, password=pw)
            except Exception as exc:
                ole_errors.append(f"pw='{pw}': {exc}")

        for pw in pw_candidates:
            try:
                return _read_quest_rows_pyodbc(tmp_mdb, password=pw)
            except Exception:
                break

        raise RuntimeError(
            f"Không đọc được tệp .mylt (auto_pw='{auto_pw}').\n"
            "Chi tiết OLEDB 32-bit:\n" + "\n".join(ole_errors[:2])
        )


def convert_mylt_to_tex(mylt_path: str | Path, output_tex: str | Path, password: str = "") -> int:
    """Chuyển toàn bộ câu hỏi trong Bank.mylt sang 1 tệp .tex chuẩn ex_test."""
    rows = read_mylt_bank_rows(mylt_path, password=password)
    blocks: list[str] = []
    for nd, cid in rows:
        txt = nd.strip()
        if not txt:
            continue
        if cid.strip() and f"%[{cid.strip()}]" not in txt:
            txt = f"%[{cid.strip()}]\n{txt}"
        blocks.append(txt)
    out = Path(output_tex)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
    return len(blocks)


def import_mylt_into_db(
    mylt_path: str | Path,
    db,
    password: str = "",
    on_status: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """Nhập siêu tốc toàn bộ câu hỏi từ Bank.mylt vào kho SQLite nganhang.db."""
    if on_status:
        on_status("Bước 1/3: Đang đọc bảng QUEST từ Bank.mylt (C# OLEDB 32-bit)...")
    rows = read_mylt_bank_rows(mylt_path, password=password)
    if on_status:
        on_status(f"Bước 2/3: Đã đọc {len(rows):,} dòng. Đang phân tích cấu trúc câu hỏi...")
    blocks: list[str] = []
    for nd, cid in rows:
        txt = nd.strip()
        if not txt:
            continue
        if cid.strip() and f"%[{cid.strip()}]" not in txt:
            txt = f"%[{cid.strip()}]\n{txt}"
        blocks.append(txt)
    combined = "\n\n".join(blocks)
    questions = parse_tex_questions(combined, auto_normalize=False)
    if on_status:
        on_status(f"Bước 3/3: Đang nạp {len(questions):,} câu vào SQLite & lập chỉ mục FTS5...")
    stat = db.bulk_import(questions)
    stat["total_rows"] = len(rows)
    return stat


def import_mylt_into_db_path(
    mylt_path: str | Path,
    db_path: str,
    password: str = "",
    on_status: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """Nhập siêu tốc Bank.mylt trên luồng nền (tự mở kết nối SQLite riêng để không treo giao diện)."""
    from ..core.db import QuestionBankDB
    db = QuestionBankDB(db_path)
    try:
        return import_mylt_into_db(mylt_path, db, password=password, on_status=on_status)
    finally:
        db.close()
