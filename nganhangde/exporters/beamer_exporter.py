"""Bộ xuất trình chiếu đề Toán sang Main Beamer LaTeX chuẩn TeX Live 2019 (hỗ trợ ex_test)."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata
from ..core.parser import Question, parse_tex_questions, read_tex_with_inputs

BEAMER_THEMES = [
    "Madrid",
    "Boadilla",
    "Warsaw",
    "CambridgeUS",
    "Berlin",
    "Singapore",
    "default",
]

BEAMER_COLOR_THEMES = [
    "default",
    "whale",
    "seahorse",
    "dolphin",
    "beaver",
    "crane",
    "spruce",
]


@dataclass
class BeamerOptions:
    title: str = "TRÌNH CHIẾU ĐỀ KIỂM TRA TOÁN"
    subtitle: str = "Chương trình GDPT 2018"
    author: str = "Tổ Toán"
    institute: str = "Trường THPT"
    theme: str = "Madrid"
    color_theme: str = "default"
    aspect_ratio: str = "169"        # "169" (16:9) hoặc "43" (4:3)
    font_size: str = "11pt"          # "10pt", "11pt", "12pt", "14pt"
    slide_mode: str = "pause"        # "pause" | "split" | "question_only"
    include_title_slide: bool = True
    show_id_tag: bool = False


def safe_beamer_stem(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "trinh_chieu_beamer")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("đ", "d").replace("Đ", "D")
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_")
    return s or "trinh_chieu_beamer"


def _clean_opt_text(opt: str) -> tuple[str, bool]:
    s = (opt or "").strip()
    is_true = bool(re.search(r"\\True\b", s))
    s = re.sub(r"\\True\b\s*", "", s).strip()
    return s, is_true


def _format_question_for_beamer(q: Question, idx: int, opts: BeamerOptions) -> str:
    id_suffix = f" \\hfill {{\\scriptsize\\texttt{{[{q.primary_id}]}}}}" if (opts.show_id_tag and q.primary_id) else ""
    qtype_label = {"TN": "Trắc nghiệm", "DS": "Đúng / Sai", "KQ": "Trả lời ngắn", "TL": "Tự luận"}.get(q.qtype, "")
    frame_title = f"Câu {idx}" + (f" ({qtype_label})" if qtype_label else "") + id_suffix

    stem = (q.stem or "").strip()
    sol = (q.solution or "").strip()

    # Xây dựng phần phương án
    ans_lines: list[str] = []
    answer_summary = ""

    if q.qtype == "TN" and q.choices:
        labels = ["A", "B", "C", "D"]
        true_lbls: list[str] = []
        ans_lines.append("\\begin{enumerate}[A.]")
        for i, raw_opt in enumerate(q.choices[:4]):
            txt, is_t_txt = _clean_opt_text(raw_opt)
            is_t = (q.correct[i] if i < len(q.correct) else False) or is_t_txt
            if is_t:
                true_lbls.append(labels[i])
            ans_lines.append(f"  \\item {txt}")
        ans_lines.append("\\end{enumerate}")
        if true_lbls:
            answer_summary = f"\\textbf{{\\color{{green!50!black}}Đáp án đúng: {', '.join(true_lbls)}}}"

    elif q.qtype == "DS" and q.choices:
        labels = ["a", "b", "c", "d"]
        tf_summary: list[str] = []
        ans_lines.append("\\begin{enumerate}[a)]")
        for i, raw_opt in enumerate(q.choices[:4]):
            txt, is_t_txt = _clean_opt_text(raw_opt)
            is_t = (q.correct[i] if i < len(q.correct) else False) or is_t_txt
            tf_summary.append(f"{labels[i]}) {'Đúng' if is_t else 'Sai'}")
            ans_lines.append(f"  \\item {txt}")
        ans_lines.append("\\end{enumerate}")
        tf_joined = " \\quad ".join(tf_summary)
        answer_summary = f"\\textbf{{\\color{{green!50!black}}Đáp án: {tf_joined}}}"

    elif q.qtype == "KQ":
        sa = (q.short_ans or "").strip()
        if sa:
            answer_summary = f"\\textbf{{\\color{{green!50!black}}Đáp số: ${sa}$}}"

    q_block = stem
    if ans_lines:
        q_block += "\n\n" + "\n".join(ans_lines)

    sol_parts: list[str] = []
    if answer_summary:
        sol_parts.append(answer_summary)
    if sol:
        sol_parts.append(f"\\textbf{{\\color{{blue!75!black}}Lời giải:}}\n\n{sol}")
    sol_block = "\n\n".join(sol_parts).strip()

    if opts.slide_mode == "question_only" or not sol_block:
        return (
            f"\\begin{{frame}}[allowframebreaks]{{{frame_title}}}\n"
            f"{q_block}\n"
            f"\\end{{frame}}\n"
        )

    if opts.slide_mode == "split":
        f1 = (
            f"\\begin{{frame}}[allowframebreaks]{{{frame_title}}}\n"
            f"{q_block}\n"
            f"\\end{{frame}}\n"
        )
        f2 = (
            f"\\begin{{frame}}[allowframebreaks]{{Lời giải — Câu {idx}}}\n"
            f"{sol_block}\n"
            f"\\end{{frame}}\n"
        )
        return f1 + "\n" + f2

    # Mặc định: slide_mode == "pause" (Hiện đề -> bấm tới hiện đáp án & lời giải)
    return (
        f"\\begin{{frame}}[allowframebreaks]{{{frame_title}}}\n"
        f"{q_block}\n"
        f"\\pause\n"
        f"\\medskip\\hrule\\medskip\n"
        f"{sol_block}\n"
        f"\\end{{frame}}\n"
    )


def build_beamer_main_tex(questions: list[Question], opts: BeamerOptions | None = None) -> str:
    """Sinh mã nguồn LaTeX Main Beamer hoàn chỉnh, biên dịch trực tiếp trên TeX Live 2019 (pdflatex)."""
    o = opts or BeamerOptions()
    ar = f"aspectratio={o.aspect_ratio}," if o.aspect_ratio else ""
    color_line = f"\\usecolortheme{{{o.color_theme}}}\n" if o.color_theme and o.color_theme != "default" else ""

    preamble = (
        f"\\documentclass[{ar}{o.font_size},hyperref={{unicode}}]{{beamer}}\n"
        f"\\usepackage[utf8]{{vietnam}}\n"
        f"\\usepackage{{amsmath,amssymb,mathrsfs,graphicx,tabularx,array}}\n"
        f"\\usepackage{{tikz,tkz-tab,pgfplots}}\n"
        f"\\pgfplotsset{{compat=1.15}}\n"
        f"\\usetikzlibrary{{calc,intersections,angles,quotes,patterns}}\n"
        f"\\usetheme{{{o.theme}}}\n"
        f"{color_line}"
        f"\\setbeamertemplate{{navigation symbols}}{{}}\n"
        f"\\usefonttheme{{professionalfonts}}\n"
        f"\\providecommand{{\\heva}}[1]{{\\left\\{{\\begin{{aligned}}#1\\end{{aligned}}\\right.}}\n"
        f"\\providecommand{{\\hoac}}[1]{{\\left[\\begin{{aligned}}#1\\end{{aligned}}\\right.}}\n"
        f"\\providecommand{{\\True}}{{}}\n"
        f"\\providecommand{{\\immini}}[2]{{\\begin{{columns}}[T]\\begin{{column}}{{0.62\\textwidth}}#1\\end{{column}}\\begin{{column}}{{0.36\\textwidth}}\\centering #2\\end{{column}}\\end{{columns}}}}\n"
        f"\\newenvironment{{itemchoice}}{{\\begin{{enumerate}}[a)]}}{{\\end{{enumerate}}}}\n"
        f"\\providecommand{{\\itemch}}{{\\item }}\n\n"
        f"\\title{{{o.title}}}\n"
        f"\\subtitle{{{o.subtitle}}}\n"
        f"\\author{{{o.author}}}\n"
        f"\\institute{{{o.institute}}}\n"
        f"\\date{{\\today}}\n\n"
        f"\\begin{{document}}\n\n"
    )

    body_parts: list[str] = []
    if o.include_title_slide:
        body_parts.append("\\begin{frame}\n  \\titlepage\n\\end{frame}\n")

    for idx, q in enumerate(questions, 1):
        body_parts.append(_format_question_for_beamer(q, idx, o))

    return preamble + "\n".join(body_parts) + "\n\\end{document}\n"


def load_questions_from_tex_file(tex_path: str | Path) -> list[Question]:
    p = Path(tex_path)
    raw = read_tex_with_inputs(p)
    return parse_tex_questions(raw, auto_normalize=True)


def build_beamer_main_and_body(
    questions: list[Question],
    opts: BeamerOptions | None = None,
    body_filename: str = "noidung_beamer.tex",
) -> tuple[str, str]:
    """Tách thành 2 tệp chuẩn: main_beamer.tex (khung Main dùng \\input) và noidung_beamer.tex (các slide câu hỏi)."""
    o = opts or BeamerOptions()
    ar = f"aspectratio={o.aspect_ratio}," if o.aspect_ratio else ""
    color_line = f"\\usecolortheme{{{o.color_theme}}}\n" if o.color_theme and o.color_theme != "default" else ""

    main_tex = (
        f"\\documentclass[{ar}{o.font_size},hyperref={{unicode}}]{{beamer}}\n"
        f"\\usepackage[utf8]{{vietnam}}\n"
        f"\\usepackage{{amsmath,amssymb,mathrsfs,graphicx,tabularx,array}}\n"
        f"\\usepackage{{tikz,tkz-tab,pgfplots}}\n"
        f"\\pgfplotsset{{compat=1.15}}\n"
        f"\\usetikzlibrary{{calc,intersections,angles,quotes,patterns}}\n"
        f"\\usetheme{{{o.theme}}}\n"
        f"{color_line}"
        f"\\setbeamertemplate{{navigation symbols}}{{}}\n"
        f"\\usefonttheme{{professionalfonts}}\n"
        f"\\providecommand{{\\heva}}[1]{{\\left\\{{\\begin{{aligned}}#1\\end{{aligned}}\\right.}}\n"
        f"\\providecommand{{\\hoac}}[1]{{\\left[\\begin{{aligned}}#1\\end{{aligned}}\\right.}}\n"
        f"\\providecommand{{\\True}}{{}}\n"
        f"\\providecommand{{\\immini}}[2]{{\\begin{{columns}}[T]\\begin{{column}}{{0.62\\textwidth}}#1\\end{{column}}\\begin{{column}}{{0.36\\textwidth}}\\centering #2\\end{{column}}\\end{{columns}}}}\n"
        f"\\newenvironment{{itemchoice}}{{\\begin{{enumerate}}[a)]}}{{\\end{{enumerate}}}}\n"
        f"\\providecommand{{\\itemch}}{{\\item }}\n\n"
        f"\\title{{{o.title}}}\n"
        f"\\subtitle{{{o.subtitle}}}\n"
        f"\\author{{{o.author}}}\n"
        f"\\institute{{{o.institute}}}\n"
        f"\\date{{\\today}}\n\n"
        f"\\begin{{document}}\n\n"
        + ("\\begin{frame}\n  \\titlepage\n\\end{frame}\n\n" if o.include_title_slide else "")
        + f"\\input{{{body_filename}}}\n\n"
        f"\\end{{document}}\n"
    )

    body_parts = [_format_question_for_beamer(q, idx, o) for idx, q in enumerate(questions, 1)]
    body_tex = "\n".join(body_parts) + "\n"
    return main_tex, body_tex
