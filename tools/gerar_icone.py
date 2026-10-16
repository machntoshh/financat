"""Gera assets/mascote.ico a partir do sprite do mascote (ui/sprites.py).

Usa escala por vizinho mais próximo (sem suavização) e fundo transparente.
Rode de novo sempre que o sprite mudar: python tools/gerar_icone.py
"""

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui.icon import sprite_image  # noqa: E402

SIZES = (16, 32, 48, 256)


def png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def dib_bytes(image: QImage) -> bytes:
    """Imagem BGRA sem compressão (formato clássico de ícone), para ler em qualquer versão."""
    width, height = image.width(), image.height()
    header = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    pixels = bytearray()
    for y in range(height - 1, -1, -1):  # linhas de baixo para cima
        for x in range(width):
            c = image.pixelColor(x, y)
            pixels += bytes((c.blue(), c.green(), c.red(), c.alpha()))
    mask = bytes((((width + 31) // 32) * 4) * height)  # máscara AND: tudo 0 (usa o alfa)
    return header + bytes(pixels) + mask


def build_ico(destination: Path) -> None:
    base = sprite_image()
    entries = []
    for size in SIZES:
        scaled = base.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.FastTransformation)
        data = png_bytes(scaled) if size >= 256 else dib_bytes(scaled)
        entries.append((size, data))

    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = len(header) + 16 * len(entries)
    directory = b""
    payload = b""
    for size, data in entries:
        dim = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(header + directory + payload)


if __name__ == "__main__":
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 (Qt precisa de app)
    target = ROOT / "assets" / "mascote.ico"
    build_ico(target)
    print("gerado:", target)
