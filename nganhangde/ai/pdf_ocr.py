import base64
import json
import mimetypes
import os
import re
import shutil
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable
from .providers import AIConfig, AIProviderClient, AIResult, AIUsage

OCR_EXTEST_PROMPT = (
    "Trích xuất toàn bộ câu hỏi Toán trong tài liệu sang mã nguồn LaTeX chuẩn gói ex_test:\n"
    "- Mỗi câu bọc trong \\begin{ex}...\\end{ex}.\n"
    "- Trắc nghiệm 4 phương án dùng \\choice{...}{...}{...}{...} (đánh dấu \\True trước đáp án đúng nếu có).\n"
    "- Đúng/Sai dùng \\choiceTF{...}{...}{...}{...}, lời giải dùng \\begin{itemchoice}\\itemch ...\\end{itemchoice}.\n"
    "- Trả lời ngắn dùng \\shortans{...} (dấu phẩy thập phân, VD: 2,5).\n"
    "- Lời giải bọc trong \\loigiai{...}.\n"
    "- Dùng \\dfrac thay \\frac, \\displaystyle\\int\\limits, \\lim\\limits, \\overrightarrow cho vector hai điểm.\n"
    "- Công thức trong dòng bọc trong $...$, không dùng \\[...\\] cho công thức trong dòng.\n"
    "- Chỉ xuất mã LaTeX thuần (không thêm \\documentclass, \\begin{document} hay giải thích thừa)."
)


def strip_markdown_fences(text: str) -> str:
    """Loại bỏ cặp ```latex ... ``` nếu AI trả về kèm khối markdown."""
    s = (text or "").strip()
    s = re.sub(r"^```(?:latex|tex)?\s*\n?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


@dataclass
class OCRChunkResult:
    chunk_index: int
    start_page: int
    end_page: int
    tex: str
    truncated: bool = False
    usage: AIUsage = field(default_factory=AIUsage)


@dataclass
class PDFOCRSessionResult:
    full_tex: str
    chunks: list[OCRChunkResult]
    total_usage: AIUsage
    truncated_chunks: list[int] = field(default_factory=list)


def get_pdf_page_count(pdf_path: str) -> int:
    try:
        from pypdf import PdfReader
        return len(PdfReader(pdf_path).pages)
    except Exception:
        import fitz
        doc = fitz.open(pdf_path)
        try:
            return len(doc)
        finally:
            doc.close()


def split_pdf_into_chunks(
    pdf_path: str,
    chunk_pages: int = 4,
    work_dir: str | None = None,
    from_page: int | None = None,
    to_page: int | None = None,
) -> list[tuple[int, int, str]]:
    out_dir = work_dir or tempfile.mkdtemp(prefix="toan11_ocr_")
    os.makedirs(out_dir, exist_ok=True)

    # Ưu tiên pypdf (thuần Python, không bao giờ lỗi DLL/lazy_import trong bản .exe)
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(pdf_path)
        total = len(reader.pages)
        p_start = max(1, from_page or 1)
        p_end = min(total, to_page or total)
        if p_start > p_end:
            return []
        slices: list[tuple[int, int, str]] = []
        step = max(1, chunk_pages)
        for start in range(p_start - 1, p_end, step):
            end = min(start + step, p_end)
            writer = PdfWriter()
            for idx in range(start, end):
                writer.add_page(reader.pages[idx])
            fp = os.path.join(out_dir, f"chunk_{start + 1:04d}_{end:04d}.pdf")
            with open(fp, "wb") as f:
                writer.write(f)
            slices.append((start + 1, end, fp))
        return slices
    except Exception:
        pass

    # Dự phòng PyMuPDF (fitz)
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Thiếu pypdf hoặc PyMuPDF. Chạy: pip install pypdf pymupdf") from exc
    doc = fitz.open(pdf_path)
    total = len(doc)
    p_start = max(1, from_page or 1)
    p_end = min(total, to_page or total)
    if p_start > p_end:
        doc.close()
        return []
    slices = []
    step = max(1, chunk_pages)
    for start in range(p_start - 1, p_end, step):
        end = min(start + step, p_end)
        sub = fitz.open()
        sub.insert_pdf(doc, from_page=start, to_page=end - 1)
        fp = os.path.join(out_dir, f"chunk_{start + 1:04d}_{end:04d}.pdf")
        sub.save(fp)
        sub.close()
        slices.append((start + 1, end, fp))
    doc.close()
    return slices


def ocr_pdf_to_extest(
    pdf_path: str,
    ai_config: AIConfig,
    chunk_pages: int = 4,
    max_concurrency: int = 2,
    checkpoint_path: str | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
    chunk_processor: Callable[[str, str], AIResult] | None = None,
    from_page: int | None = None,
    to_page: int | None = None,
) -> PDFOCRSessionResult:
    tmp_work = tempfile.mkdtemp(prefix="toan11_ocr_")
    try:
        slices = split_pdf_into_chunks(
            pdf_path,
            chunk_pages=chunk_pages,
            work_dir=tmp_work,
            from_page=from_page,
            to_page=to_page,
        )
        if not slices:
            return PDFOCRSessionResult("", [], AIUsage(), [])

        completed: dict[int, OCRChunkResult] = {}
        if checkpoint_path and os.path.exists(checkpoint_path):
            for it in json.load(open(checkpoint_path, encoding="utf-8")).get("chunks", []):
                u = it.get("usage", {})
                completed[it["chunk_index"]] = OCRChunkResult(
                    it["chunk_index"],
                    it["start_page"],
                    it["end_page"],
                    it["tex"],
                    it.get("truncated", False),
                    AIUsage(u.get("input_tokens", 0), u.get("output_tokens", 0), u.get("total_tokens", 0)),
                )

        client = AIProviderClient(ai_config) if chunk_processor is None else None

        def _run_one(idx: int, sp: int, ep: int, fp: str) -> OCRChunkResult:
            if chunk_processor is not None:
                res = chunk_processor(fp, OCR_EXTEST_PROMPT)
            else:
                res = client.generate_gemini_multimodal_file(fp, OCR_EXTEST_PROMPT, mime_type="application/pdf")
            clean_tex = strip_markdown_fences(res.text)
            return OCRChunkResult(idx, sp, ep, clean_tex, "MAX_TOKENS" in (res.finish_reason or "").upper(), res.usage)

        pending = [(i, sp, ep, fp) for i, (sp, ep, fp) in enumerate(slices) if i not in completed]
        for i, sp, ep, fp in pending:
            cr = _run_one(i, sp, ep, fp)
            completed[cr.chunk_index] = cr
            if checkpoint_path:
                with open(checkpoint_path, "w", encoding="utf-8") as cf:
                    json.dump(
                        {
                            "source_pdf": pdf_path,
                            "chunks": [
                                {
                                    "chunk_index": c.chunk_index,
                                    "start_page": c.start_page,
                                    "end_page": c.end_page,
                                    "tex": c.tex,
                                    "truncated": c.truncated,
                                    "usage": c.usage.__dict__,
                                }
                                for _, c in sorted(completed.items())
                            ],
                        },
                        cf,
                        ensure_ascii=False,
                        indent=2,
                    )
            if on_progress:
                on_progress(len(completed), len(slices), f"Xong trang {cr.start_page}-{cr.end_page}")

        ordered = [completed[i] for i in sorted(completed)]
        tot_u = AIUsage(
            sum(c.usage.input_tokens for c in ordered),
            sum(c.usage.output_tokens for c in ordered),
            sum(c.usage.total_tokens for c in ordered),
        )
        return PDFOCRSessionResult(
            "\n\n".join(f"% === TRANG {c.start_page}-{c.end_page} ===\n{c.tex}" for c in ordered),
            ordered,
            tot_u,
            [c.chunk_index for c in ordered if c.truncated],
        )
    finally:
        shutil.rmtree(tmp_work, ignore_errors=True)


def ocr_image_to_extest(image_path: str, ai_config: AIConfig) -> str:
    """Nhận dạng trực tiếp 1 tệp ảnh (.png/.jpg) sang LaTeX ex_test bằng Gemini REST API."""
    client = AIProviderClient(ai_config)
    res = client.generate_gemini_multimodal_file(image_path, OCR_EXTEST_PROMPT)
    return strip_markdown_fences(res.text)


def ocr_mathpix_file(file_path: str, app_id: str, app_key: str) -> str:
    """Chuyển ảnh (.png/.jpg) hoặc PDF sang LaTeX bằng Mathpix API (v3/text)."""
    ext = os.path.splitext(file_path)[1].lower()
    headers = {
        "app_id": app_id.strip(),
        "app_key": app_key.strip(),
        "Content-Type": "application/json",
    }

    def _ocr_img_bytes(img_bytes: bytes, mime: str = "image/png") -> str:
        b64 = base64.b64encode(img_bytes).decode("ascii")
        payload = {
            "src": f"data:{mime};base64,{b64}",
            "formats": ["text", "latex_styled"],
            "math_inline_delimiters": ["$", "$"],
            "math_display_delimiters": ["$$", "$$"],
        }
        req = urllib.request.Request(
            "https://api.mathpix.com/v3/text",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("error"):
            raise RuntimeError(f"Mathpix API lỗi: {data.get('error')}")
        return str(data.get("text") or data.get("latex_styled") or "").strip()

    if ext == ".pdf":
        import fitz
        doc = fitz.open(file_path)
        parts: list[str] = []
        try:
            for idx, page in enumerate(doc, 1):
                pix = page.get_pixmap(dpi=180)
                txt = _ocr_img_bytes(pix.tobytes("png"), "image/png")
                parts.append(f"% === TRANG {idx} ===\n{txt}")
                time.sleep(0.2)
        finally:
            doc.close()
        return "\n\n".join(parts)

    mime = mimetypes.guess_type(file_path)[0] or "image/png"
    with open(file_path, "rb") as f:
        return _ocr_img_bytes(f.read(), mime)


def extract_pdf_text_fallback(pdf_path: str, from_page: int | None = None, to_page: int | None = None) -> str:
    """Trích xuất văn bản nhanh từ PDF dạng chữ (ưu tiên pypdf, dự phòng PyMuPDF)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        total = len(reader.pages)
        p_start = max(1, from_page or 1)
        p_end = min(total, to_page or total)
        chunks: list[str] = []
        for pno in range(p_start - 1, p_end):
            t = (reader.pages[pno].extract_text() or "").strip()
            if t:
                chunks.append(f"% === TRANG {pno + 1} ===\n{t}")
        if chunks:
            return "\n\n".join(chunks)
    except Exception:
        pass

    import fitz
    doc = fitz.open(pdf_path)
    total = len(doc)
    p_start = max(1, from_page or 1)
    p_end = min(total, to_page or total)
    chunks = []
    try:
        for pno in range(p_start - 1, p_end):
            t = doc[pno].get_text("text").strip()
            if t:
                chunks.append(f"% === TRANG {pno + 1} ===\n{t}")
    finally:
        doc.close()
    return "\n\n".join(chunks)
