"""Cầu nối xử lý công thức MathType OLE (oleObject*.bin / MTEF) theo cơ chế Word COM của MyLT 2026."""
from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import zipfile


@dataclass
class MtefObjectInfo:
    entry_name: str
    size_bytes: int
    is_ole_cfb: bool
    mtef_version: int | None


def inspect_docx_mtef_objects(docx_path: str) -> list[MtefObjectInfo]:
    """Quét toàn bộ word/embeddings/oleObject*.bin trong .docx để nhận diện MathType OLE/MTEF."""
    results: list[MtefObjectInfo] = []
    with zipfile.ZipFile(docx_path, "r") as zf:
        for name in zf.namelist():
            if not (name.startswith("word/embeddings/oleObject") and name.endswith(".bin")):
                continue
            blob = zf.read(name)
            is_cfb = blob.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
            mtef_ver: int | None = None
            if b"Equation Native" in blob or b"MathType" in blob:
                mtef_ver = 5
            results.append(MtefObjectInfo(name, len(blob), is_cfb, mtef_ver))
    return results


def _find_mathtype_addins() -> list[Path]:
    """Tìm các tệp Add-in MathType (.dotm / .dot) trên Windows."""
    dirs = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Word" / "STARTUP",
        Path(r"C:\Program Files (x86)\MathType\Office Support\32"),
        Path(r"C:\Program Files (x86)\MathType\Office Support\64"),
        Path(r"C:\Program Files\MathType\Office Support\64"),
        Path(r"C:\Program Files\MathType\Office Support\32"),
    ]
    found: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.glob("MathType*.dot*")):
            key = p.name.lower()
            if key not in seen:
                seen.add(key)
                found.append(p)
    return found


def _wait_file_unlocked(path: Path, timeout_sec: float = 8.0) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with open(path, "r+b"):
                return
        except OSError:
            time.sleep(0.25)


def _convert_via_pywin32(
    src: Path,
    dst: Path,
    show_word: bool = True,
    mode: str = "convert_eq",
) -> tuple[bool, str]:
    """Gọi trực tiếp Word.Application qua win32com.client (pywin32) — tương đương cơ chế COM trực tiếp của MyLT 2026."""
    import pythoncom
    import win32com.client

    shutil.copy2(src, dst)
    orig_ole = len(inspect_docx_mtef_objects(str(src)))
    pythoncom.CoInitialize()
    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = bool(show_word)
        word.DisplayAlerts = 0
        if show_word:
            try:
                word.Activate()
            except Exception:
                pass

        # Nạp trực tiếp MathType Add-in (.dotm / .dot)
        for addin_path in _find_mathtype_addins():
            try:
                already = False
                for ai in word.AddIns:
                    if str(ai.Name).lower() == addin_path.name.lower():
                        ai.Installed = True
                        already = True
                        break
                if not already:
                    word.AddIns.Add(str(addin_path), True)
            except Exception:
                pass

        doc = word.Documents.Open(str(dst))
        doc.Activate()
        if show_word:
            try:
                word.ActiveWindow.Activate()
            except Exception:
                pass

        before_shapes = int(doc.InlineShapes.Count)

        # Luôn ưu tiên MTCommand_ToggleTeX (đổi trực tiếp không mở hộp thoại chờ bấm như ConvertEqns)
        toggle_macros = [
            "MTCommand_ToggleTeX",
            "MTTeXToggle.Main",
            "UIWrappers.MTCommand_ToggleTeX",
            "MathTypeCommands.UIWrappers.MTCommand_ToggleTeX",
            "MathTypeCommands.MTCommand_ToggleTeX",
        ]

        def _run_toggle_on_selection() -> str:
            for m in toggle_macros:
                try:
                    word.Run(m)
                    return m
                except Exception:
                    continue
            try:
                wshell = win32com.client.Dispatch("WScript.Shell")
                wshell.AppActivate(word.Caption)
                time.sleep(0.35)
                wshell.SendKeys("%\\")
                return "Alt+\\"
            except Exception:
                return ""

        # Bước 1: Chuyển toàn bộ tài liệu (WholeStory)
        word.Selection.WholeStory()
        ran_macro = _run_toggle_on_selection()

        # Bước 2: Nếu tài liệu có bảng (VD: Đáp án, Ma trận) và vẫn còn InlineShapes, chạy Toggle TeX trên từng bảng
        try:
            tbl_count = int(doc.Tables.Count)
            if tbl_count > 0 and int(doc.InlineShapes.Count) > 0:
                for ti in range(1, tbl_count + 1):
                    try:
                        tbl = doc.Tables(ti)
                        if int(tbl.Range.InlineShapes.Count) > 0:
                            tbl.Range.Select()
                            _run_toggle_on_selection()
                            time.sleep(0.3)
                    except Exception:
                        continue
        except Exception:
            pass

        # Chờ MathType chuyển xong toàn bộ công thức (tối đa 120s)
        last_shapes = before_shapes
        stable_ticks = 0
        for tick in range(240):
            time.sleep(0.5)
            try:
                cur_shapes = int(doc.InlineShapes.Count)
            except Exception:
                stable_ticks = 0
                continue

            if before_shapes > 0 and cur_shapes == 0:
                time.sleep(1.0)
                break
            if cur_shapes < before_shapes:
                if cur_shapes == last_shapes:
                    stable_ticks += 1
                    if stable_ticks >= 6:
                        break
                else:
                    stable_ticks = 0
                    last_shapes = cur_shapes
            elif tick >= 24 and cur_shapes == before_shapes:
                break

        doc.Save()
        doc.Close(False)
        doc = None
        word.Quit()
        word = None
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    _wait_file_unlocked(dst, timeout_sec=8.0)
    rem_ole = len(inspect_docx_mtef_objects(str(dst)))
    if orig_ole > 0 and rem_ole >= orig_ole:
        return False, (
            f"Word COM (pywin32) đã chạy ({ran_macro or 'không tìm thấy macro MathType'}) nhưng còn nguyên "
            f"{rem_ole}/{orig_ole} công thức MathType. Hãy kiểm tra MathType Add-in trong Word hoặc chọn 'Dùng Gemini'."
        )
    return True, f"Đã chuyển {orig_ole - rem_ole}/{orig_ole} công thức MathType bằng Word COM ({ran_macro})."


def convert_mathtype_via_word_com(
    docx_path: str | Path,
    out_docx: str | Path,
    show_word: bool = True,
    mode: str = "convert_eq",
) -> tuple[bool, str]:
    """Chuyển công thức MathType sang LaTeX bằng Word COM (ưu tiên pywin32 trực tiếp giống MyLT 2026, dự phòng PowerShell)."""
    if os.name != "nt":
        return False, "Word COM chỉ hỗ trợ trên Windows."

    src = Path(docx_path).resolve()
    dst = Path(out_docx).resolve()

    # Nhánh 1: Gọi trực tiếp qua pywin32 (nhanh, ổn định, giống MyLT 2026)
    try:
        import win32com.client  # noqa: F401
        return _convert_via_pywin32(src, dst, show_word=show_word, mode=mode)
    except ImportError:
        pass
    except Exception as exc:
        return False, f"Lỗi pywin32 Word COM: {exc}"

    # Nhánh 2: Dự phòng PowerShell COM nếu máy chưa cài pywin32
    shutil.copy2(src, dst)
    ps = shutil.which("powershell") or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    ps_code = r"""param([string]$DocPath, [string]$ShowWord, [string]$Mode)
$ErrorActionPreference = "Stop"
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = ($ShowWord -eq "1")
    $word.DisplayAlerts = 0
    if ($ShowWord -eq "1") { try { $word.Activate() } catch {} }

    $startupDirs = @(
        (Join-Path $env:APPDATA "Microsoft\Word\STARTUP"),
        "C:\Program Files (x86)\MathType\Office Support\32",
        "C:\Program Files (x86)\MathType\Office Support\64",
        "C:\Program Files\MathType\Office Support\64"
    )
    foreach ($sd in $startupDirs) {
        if (Test-Path $sd) {
            Get-ChildItem -Path $sd -Filter "MathType*.dot*" -ErrorAction SilentlyContinue | ForEach-Object {
                try {
                    $already = $false
                    foreach ($ai in $word.AddIns) {
                        if ($ai.Name -eq $_.Name) { $ai.Installed = $true; $already = $true }
                    }
                    if (-not $already) { $word.AddIns.Add($_.FullName, $true) | Out-Null }
                } catch {}
            }
        }
    }

    $doc = $word.Documents.Open($DocPath)
    $doc.Activate()
    $beforeShapes = $doc.InlineShapes.Count
    $word.Selection.WholeStory()

    $ran = $false
    $macros = if ($Mode -eq "convert_eq") {
        @("MTCommand_ConvertEqns", "MTCommand_ToggleTeX", "MTTeXToggle.Main", "UIWrappers.MTCommand_ToggleTeX")
    } else {
        @("MTCommand_ToggleTeX", "MTTeXToggle.Main", "UIWrappers.MTCommand_ToggleTeX", "MTCommand_ConvertEqns")
    }
    foreach ($m in $macros) {
        try { $word.Run($m); $ran = $true; break } catch {}
    }
    if (-not $ran) {
        $wshell = New-Object -ComObject WScript.Shell
        try { $wshell.AppActivate($word.Caption) | Out-Null } catch {}
        Start-Sleep -Milliseconds 500
        $wshell.SendKeys("%\\")
    }

    $lastShapes = $beforeShapes
    $stableTicks = 0
    for ($t = 0; $t -lt 240; $t++) {
        Start-Sleep -Milliseconds 500
        $curShapes = $lastShapes
        try { $curShapes = $doc.InlineShapes.Count } catch { $stableTicks = 0; continue }
        if ($beforeShapes -gt 0 -and $curShapes -eq 0) { Start-Sleep -Milliseconds 1000; break }
        if ($curShapes -lt $beforeShapes) {
            if ($curShapes -eq $lastShapes) { $stableTicks++; if ($stableTicks -ge 6) { break } }
            else { $stableTicks = 0; $lastShapes = $curShapes }
        } elseif ($t -ge 24 -and $curShapes -eq $beforeShapes) { break }
    }
    $afterShapes = $doc.InlineShapes.Count
    $doc.Save()
    Write-Output "OK:$beforeShapes->$afterShapes"
} finally {
    if ($null -ne $doc) { try { $doc.Close($false) } catch {}; try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) } catch {} }
    if ($null -ne $word) { try { $word.Quit() } catch {}; try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) } catch {} }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
"""
    with tempfile.TemporaryDirectory(prefix="mt_com_") as td:
        ps_file = Path(td) / "mt_toggle.ps1"
        ps_file.write_text(ps_code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_file), str(dst), "1" if show_word else "0", mode],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=180,
            )
            _wait_file_unlocked(dst, timeout_sec=6.0)
            out_s = proc.stdout.decode("utf-8", errors="replace").strip()
            err_s = proc.stderr.decode("utf-8", errors="replace").strip()
            if proc.returncode == 0 and "OK:" in out_s:
                rem_ole = len(inspect_docx_mtef_objects(str(dst)))
                orig_ole = len(inspect_docx_mtef_objects(str(src)))
                if orig_ole > 0 and rem_ole >= orig_ole:
                    return False, f"Word đã chạy nhưng còn nguyên {rem_ole}/{orig_ole} công thức MathType. Hãy chọn 'Dùng Gemini' hoặc cài pywin32."
                return True, f"Đã chuyển {orig_ole - rem_ole}/{orig_ole} công thức MathType ({out_s})."
            return False, err_s or out_s or "Không chạy được MathType trong Word."
        except Exception as exc:
            return False, str(exc)


def convert_docx_to_pdf_via_word_com(docx_path: str | Path, out_pdf: str | Path) -> tuple[bool, str]:
    """Xuất nhanh .docx sang .pdf bằng Microsoft Word COM (ưu tiên pywin32, dự phòng PowerShell)."""
    if os.name != "nt":
        return False, "Word COM chỉ hỗ trợ trên Windows."
    src = Path(docx_path).resolve()
    dst = Path(out_pdf).resolve()
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = None
        try:
            doc = word.Documents.Open(str(src), False, True)
            doc.ExportAsFixedFormat(str(dst), 17)
            return True, str(dst)
        finally:
            if doc is not None:
                try:
                    doc.Close(False)
                except Exception:
                    pass
            try:
                word.Quit()
            except Exception:
                pass
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
    except ImportError:
        pass
    except Exception:
        pass

    ps = shutil.which("powershell") or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    ps_code = r"""param([string]$DocPath, [string]$PdfPath)
$ErrorActionPreference = "Stop"
$word = $null; $doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false; $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($DocPath, $false, $true)
    $doc.ExportAsFixedFormat($PdfPath, 17)
    Write-Output "OK"
} finally {
    if ($null -ne $doc) { try { $doc.Close($false) } catch {} }
    if ($null -ne $word) { try { $word.Quit() } catch {} }
}
"""
    with tempfile.TemporaryDirectory(prefix="w2pdf_") as td:
        ps_file = Path(td) / "w2pdf.ps1"
        ps_file.write_text(ps_code, encoding="utf-8")
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        try:
            proc = subprocess.run(
                [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_file), str(src), str(dst)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                creationflags=creationflags,
            )
            if proc.returncode == 0 and dst.exists():
                return True, str(dst)
            return False, proc.stderr.decode("utf-8", errors="replace").strip() or "Lỗi xuất PDF từ Word."
        except Exception as exc:
            return False, str(exc)


def convert_omml_docx_to_mathtype_ole(in_docx: str, out_docx: str) -> bool:
    """Gọi omml-converter (Python 3.12+) để chuyển OMML -> MathType 5.0 OLE thuần Python."""
    exe = shutil.which("omml-converter")
    if not exe:
        return False
    proc = subprocess.run([exe, in_docx, "-o", out_docx], capture_output=True, text=True)
    return proc.returncode == 0
