"""Cores e folha de estilo do aplicativo (tema escuro minimalista)."""

COLORS = {
    "bg": "#121212",
    "sidebar": "#171717",
    "card": "#1E1E1E",
    "control": "#252525",
    "border": "#2C2C2C",
    "text": "#EDEDED",
    "muted": "#8E8E8E",
    "accent": "#C5F452",  # verde-lima: ações positivas e destaques
    "accent_text": "#101010",
    "paid": "#5BC48A",
    "pending": "#E3B54E",
    "overdue": "#E26D6D",
}

STYLESHEET = """
QWidget {{
    background: {bg};
    color: {text};
    font-family: "Segoe UI", "Helvetica Neue", Arial;
    font-size: 13px;
}}
QMainWindow, QDialog {{ background: {bg}; }}
QWidget#sidebar {{
    background: {sidebar};
    border-right: 1px solid {border};
}}
QFrame#card {{
    background: {card};
    border: 1px solid {border};
    border-radius: 14px;
}}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 22px; font-weight: 600; }}
QLabel#section {{ font-size: 15px; font-weight: 600; }}
QLabel#muted {{ color: {muted}; }}
QLabel#statValue {{ font-size: 20px; font-weight: 600; }}
QLabel#statTitle {{ color: {muted}; font-size: 12px; }}
QLabel#toast {{
    background: {card};
    border: 1px solid {accent};
    border-radius: 10px;
    padding: 8px 14px;
    color: {accent};
}}
QPushButton {{
    background: {control};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 7px 14px;
}}
QPushButton:hover {{ border-color: {muted}; }}
QPushButton:disabled {{ color: {muted}; }}
QPushButton#primary {{
    background: {accent};
    color: {accent_text};
    border: none;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: #D4FF6A; }}
QPushButton#ghost {{
    background: transparent;
    border: none;
    color: {muted};
    padding: 4px 8px;
}}
QPushButton#ghost:hover {{ color: {text}; }}
QPushButton#danger {{ color: {overdue}; }}
QPushButton#nav {{
    background: transparent;
    border: none;
    border-radius: 10px;
    text-align: left;
    padding: 10px 14px;
    color: {muted};
}}
QPushButton#nav:hover {{ color: {text}; background: {control}; }}
QPushButton#nav:checked {{ color: {accent}; background: {control}; font-weight: 600; }}
QPushButton#pill {{
    border-radius: 14px;
    padding: 5px 14px;
    color: {muted};
}}
QPushButton#pill:checked {{
    background: {accent};
    color: {accent_text};
    border-color: {accent};
    font-weight: 600;
}}
QPushButton#rowAction {{ padding: 6px 12px; }}
QPushButton#rowPay {{ background: {accent}; color: {accent_text}; border: none; font-weight: 600; }}
QPushButton#rowPay:hover {{ background: #D4FF6A; }}
QLineEdit, QComboBox, QDateEdit, QTextEdit, QDoubleSpinBox {{
    background: {control};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {accent};
    selection-color: {accent_text};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus {{ border-color: {accent}; }}
QComboBox QAbstractItemView {{
    background: {card};
    border: 1px solid {border};
    selection-background-color: {control};
    outline: none;
}}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 20px; }}
QCheckBox {{ spacing: 8px; }}
QTableWidget {{
    background: {card};
    border: 1px solid {border};
    border-radius: 14px;
    gridline-color: transparent;
    selection-background-color: {control};
    selection-color: {text};
    outline: none;
}}
QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {border}; }}
QHeaderView::section {{
    background: {card};
    color: {muted};
    border: none;
    border-bottom: 1px solid {border};
    padding: 8px;
    font-size: 12px;
}}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QToolTip {{ background: {card}; color: {text}; border: 1px solid {border}; }}
"""


def stylesheet() -> str:
    return STYLESHEET.format(**COLORS)
