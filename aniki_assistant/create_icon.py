"""
Создание иконки приложения Аники.
Запусти один раз: python create_icon.py
"""

import os

def create_icon():
    """Создать иконку .ico для приложения."""
    resources_dir = os.path.join(os.path.dirname(__file__), "resources")
    os.makedirs(resources_dir, exist_ok=True)

    try:
        from PIL import Image, ImageDraw, ImageFont
        print("Создаю иконку с PIL...")
    except ImportError:
        print("PIL не установлен, создаю иконку через PyQt6...")
        _create_icon_qt(resources_dir)
        return

    sizes = [16, 32,48, 64, 128, 256]
    images = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        bg_color = (26, 26, 46, 255)
        draw.ellipse([2, 2, size - 3, size - 3], fill=bg_color, outline=(255, 158, 68, 255), width=max(1, size // 20))

        try:
            font_size = int(size * 0.5)
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

            text = "A"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x = (size - text_w) // 2
            y = (size - text_h) // 2
            draw.text((x, y), text, fill=(255, 158, 68, 255), font=font)
        except Exception:
            pass

        images.append(img)

    ico_path = os.path.join(resources_dir, "aniki.ico")
    images[0].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"Иконка создана: {ico_path}")


def _create_icon_qt(resources_dir: str):
    """Создать иконку через PyQt6."""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QPixmap, QIcon, QPainter, QColor, QFont
    from PyQt6.QtCore import Qt
    import sys

    app = QApplication.instance() or QApplication(sys.argv)

    pixmap = QPixmap(256, 256)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setBrush(QColor(26, 26, 46))
    painter.setPen(QColor(255, 158, 68))
    painter.drawEllipse(4, 4, 248, 248)

    font = QFont("Arial", 120, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(255, 158, 68))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "A")
    painter.end()

    png_path = os.path.join(resources_dir, "aniki.png")
    pixmap.save(png_path)
    print(f"PNG иконка создана: {png_path}")

    try:
        ico_path = os.path.join(resources_dir, "aniki.ico")
        icon = QIcon(pixmap)
        sizes = icon.availableSizes()
        pixmap.save(ico_path)
        print(f"ICO иконка создана: {ico_path}")
    except Exception as e:
        print(f"ICO не создан: {e} (используем PNG)")


if __name__ == "__main__":
    create_icon()
    print("Done! Let's go!")
