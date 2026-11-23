"""Quản lý giao diện nâng cấp v6.9: Đổi màu nền hiện đại & chữ in đậm sắc nét trên toàn ứng dụng."""
from __future__ import annotations

THEMES: dict[str, dict[str, str]] = {
    "Xanh dịu hiện đại (Chữ đậm)": {
        "window_bg": "#e6f0fa",
        "panel_bg": "#f7fbff",
        "input_bg": "#ffffff",
        "text": "#0f172a",
        "title": "#0c4a6e",
        "border": "#93c5fd",
        "btn_bg": "#dbeafe",
        "btn_hover": "#bfdbfe",
        "btn_text": "#0f172a",
        "tab_bg": "#dbeafe",
        "tab_sel": "#ffffff",
        "header_bg": "#dbeafe",
        "sel_bg": "#2563eb",
        "sel_text": "#ffffff",
    },
    "Kem ấm dịu mắt (Chữ đậm)": {
        "window_bg": "#f6efe0",
        "panel_bg": "#fffdf7",
        "input_bg": "#ffffff",
        "text": "#1f2937",
        "title": "#92400e",
        "border": "#d6c3a5",
        "btn_bg": "#efe3cc",
        "btn_hover": "#e5d3b3",
        "btn_text": "#1f2937",
        "tab_bg": "#efe3cc",
        "tab_sel": "#fffdf7",
        "header_bg": "#efe3cc",
        "sel_bg": "#b45309",
        "sel_text": "#ffffff",
    },
    "Xám bạc chuyên nghiệp (Chữ đậm)": {
        "window_bg": "#e2e8f0",
        "panel_bg": "#f8fafc",
        "input_bg": "#ffffff",
        "text": "#0f172a",
        "title": "#1e293b",
        "border": "#94a3b8",
        "btn_bg": "#cbd5e1",
        "btn_hover": "#94a3b8",
        "btn_text": "#0f172a",
        "tab_bg": "#cbd5e1",
        "tab_sel": "#f8fafc",
        "header_bg": "#cbd5e1",
        "sel_bg": "#334155",
        "sel_text": "#ffffff",
    },
    "Tối hiện đại — Dark Mode (Chữ đậm)": {
        "window_bg": "#1e293b",
        "panel_bg": "#0f172a",
        "input_bg": "#1e293b",
        "text": "#f1f5f9",
        "title": "#38bdf8",
        "border": "#475569",
        "btn_bg": "#334155",
        "btn_hover": "#475569",
        "btn_text": "#f8fafc",
        "tab_bg": "#334155",
        "tab_sel": "#0f172a",
        "header_bg": "#334155",
        "sel_bg": "#0284c7",
        "sel_text": "#ffffff",
    },
}

DEFAULT_THEME = "Xanh dịu hiện đại (Chữ đậm)"


def build_theme_qss(theme_name: str = DEFAULT_THEME) -> str:
    p = THEMES.get(theme_name, THEMES[DEFAULT_THEME])
    return f"""
QMainWindow, QDialog {{
    background-color: {p['window_bg']};
    color: {p['text']};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 9.5pt;
    font-weight: 700;
}}
QWidget {{
    color: {p['text']};
    font-family: "Segoe UI", Arial, sans-serif;
    font-weight: 700;
}}
QTabWidget::pane {{
    background-color: {p['window_bg']};
    border: 1px solid {p['border']};
    border-radius: 4px;
}}
QTabBar::tab {{
    background-color: {p['tab_bg']};
    color: {p['text']};
    font-weight: 700;
    border: 1px solid {p['border']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 5px 12px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {p['tab_sel']};
    color: {p['title']};
    font-weight: 800;
}}
QGroupBox {{
    background-color: {p['panel_bg']};
    border: 1px solid {p['border']};
    border-radius: 5px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: 700;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {p['title']};
    font-weight: 800;
}}
QLabel, QCheckBox, QRadioButton {{
    background-color: transparent;
    color: {p['text']};
    font-weight: 700;
}}
QPushButton {{
    background-color: {p['btn_bg']};
    color: {p['btn_text']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    padding: 4px 10px;
    font-weight: 700;
}}
QPushButton:hover {{
    background-color: {p['btn_hover']};
}}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit, QTextBrowser, QTableWidget, QTreeWidget {{
    background-color: {p['input_bg']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 3px;
    font-weight: 700;
    selection-background-color: {p['sel_bg']};
    selection-color: {p['sel_text']};
}}
QHeaderView::section {{
    background-color: {p['header_bg']};
    color: {p['title']};
    border: 1px solid {p['border']};
    padding: 4px;
    font-weight: 800;
}}
"""
