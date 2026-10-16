"""Mascote: componente independente com estados idle, happy e returning."""

from __future__ import annotations

import math
import sys
import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from .sprites import FRAME_CLOSED, FRAME_OPEN, SPRITE_SIZE

IDLE = "idle"
HAPPY = "happy"
RETURNING = "returning"

BLUE = QColor("#cbdbfc")  # azul-bebê do sprite original
GREEN = QColor("#99e550")  # verde-limão: celebração (mesma cor dos olhos do sprite)
OUTLINE = QColor("#000000")
SHINE = QColor("#ffffff")

HAPPY_SECONDS = 2.6
RETURN_SECONDS = 0.8
HOP_SECONDS = 0.6  # um único pulinho no início da comemoração
HOP_HEIGHT = 14
BLINK_PERIOD = 3.4
BLINK_LENGTH = 0.15
CELL = 7  # cada pixel vira um bloco 7x7, sem suavização
TICK_MS = 33


def animations_enabled() -> bool:
    """Respeita 'Mostrar animações do Windows' (desligado = sem movimento)."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        flag = wintypes.BOOL()
        SPI_GETCLIENTAREAANIMATION = 0x1042
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(flag), 0
        )
        return bool(flag.value) if ok else True
    except (OSError, AttributeError):
        return True


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


class CatMascot(QWidget):
    """Mascote que comemora quando um pagamento é salvo.

    Chame `celebrate()` apenas após a gravação do pagamento no banco.
    """

    def __init__(self, parent: QWidget | None = None, animate: bool | None = None):
        super().__init__(parent)
        self._animate = animations_enabled() if animate is None else animate
        self._state = IDLE
        self._state_started = time.monotonic()
        self.setFixedSize(SPRITE_SIZE * CELL + 16, SPRITE_SIZE * CELL + 24)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setToolTip("Seu mascote")
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(TICK_MS)

    @property
    def state(self) -> str:
        return self._state

    def celebrate(self) -> None:
        """Entra em `happy`. Pagamentos seguidos reiniciam a comemoração, sem empilhar."""
        self._set_state(HAPPY)

    def _set_state(self, state: str) -> None:
        self._state = state
        self._state_started = time.monotonic()
        self.update()

    def _tick(self) -> None:
        elapsed = time.monotonic() - self._state_started
        if self._state == HAPPY and elapsed >= HAPPY_SECONDS:
            self._set_state(RETURNING)
        elif self._state == RETURNING and elapsed >= RETURN_SECONDS:
            self._set_state(IDLE)
        else:
            self.update()

    def _body_color(self, elapsed: float) -> QColor:
        if self._state == HAPPY:
            return GREEN
        if self._state == RETURNING:
            return _mix(GREEN, BLUE, elapsed / RETURN_SECONDS)
        return BLUE

    def _vertical_offset(self, elapsed: float) -> int:
        """Pulinho único: sobe e desce uma vez logo no começo da comemoração."""
        if not self._animate or self._state != HAPPY or elapsed >= HOP_SECONDS:
            return 0
        return -round(math.sin(math.pi * elapsed / HOP_SECONDS) * HOP_HEIGHT)

    def _current_frame(self):
        """Olhos fechados durante a comemoração e no piscar do repouso."""
        if self._state == HAPPY:
            return FRAME_CLOSED
        if self._animate and self._state == IDLE and (time.monotonic() % BLINK_PERIOD) < BLINK_LENGTH:
            return FRAME_CLOSED
        return FRAME_OPEN

    def paintEvent(self, _event) -> None:  # noqa: N802 (nome exigido pelo Qt)
        elapsed = time.monotonic() - self._state_started
        colors = {"o": OUTLINE, "b": self._body_color(elapsed), "w": SHINE, "e": GREEN}
        frame = self._current_frame()
        origin_x = (self.width() - SPRITE_SIZE * CELL) // 2
        origin_y = (self.height() - SPRITE_SIZE * CELL) // 2 + self._vertical_offset(elapsed)

        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        for row_index, row in enumerate(frame):
            for col_index, char in enumerate(row):
                if char in colors:
                    painter.setBrush(colors[char])
                    painter.drawRect(
                        origin_x + col_index * CELL, origin_y + row_index * CELL, CELL, CELL
                    )
        painter.end()
