"""Ícone do aplicativo: o próprio sprite do mascote, em vários tamanhos."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap

from .mascot import BLUE, GREEN, OUTLINE, SHINE
from .sprites import FRAME_OPEN, SPRITE_SIZE

ICON_SIZES = (16, 24, 32, 48, 64, 256)
COLORS = {"o": OUTLINE, "b": BLUE, "w": SHINE, "e": GREEN}


def sprite_image() -> QImage:
    image = QImage(SPRITE_SIZE, SPRITE_SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    for y, row in enumerate(FRAME_OPEN):
        for x, char in enumerate(row):
            if char in COLORS:
                image.setPixelColor(x, y, QColor(COLORS[char]))
    return image


def app_icon() -> QIcon:
    base = sprite_image()
    icon = QIcon()
    for size in ICON_SIZES:
        scaled = base.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.FastTransformation)  # vizinho mais próximo
        icon.addPixmap(QPixmap.fromImage(scaled))
    return icon
