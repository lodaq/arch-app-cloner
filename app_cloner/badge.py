"""Icon badging and badge rendering for cloned applications."""

import os
from pathlib import Path
from typing import Optional


def ensure_gui_app():
    """Ensure a QGuiApplication exists in offscreen mode."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance()
    if not app:
        app = QGuiApplication(["-platform", "offscreen"])
    return app


def create_badged_icon(
    src_icon_path: Optional[str],
    dest_path: Path,
    badge_color: str = "#3b82f6",
    badge_text: str = "",
    size: int = 256,
    app_name: str = "App",
) -> Path:
    """Generate a badged version of an icon with a colored identifier chip."""
    ensure_gui_app()
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QFont,
        QImage,
        QPainter,
        QPainterPath,
        QPen,
    )
    from PySide6.QtSvg import QSvgRenderer

    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    target = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    target.fill(Qt.GlobalColor.transparent)

    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    icon_drawn = False

    if src_icon_path and Path(src_icon_path).exists():
        src_lower = src_icon_path.lower()
        if src_lower.endswith(".svg"):
            try:
                renderer = QSvgRenderer(src_icon_path)
                if renderer.isValid():
                    renderer.render(painter, QRectF(16, 16, size - 32, size - 32))
                    icon_drawn = True
            except Exception:
                pass
        else:
            try:
                img = QImage(src_icon_path)
                if not img.isNull():
                    scaled = img.scaled(
                        size - 32,
                        size - 32,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    # Center the base image
                    x_offset = (size - scaled.width()) / 2
                    y_offset = (size - scaled.height()) / 2
                    painter.drawImage(QPointF(x_offset, y_offset), scaled)
                    icon_drawn = True
            except Exception:
                pass

    if not icon_drawn:
        # Generate an elegant fallback app icon
        bg_color = QColor("#1e293b")
        accent_color = QColor(badge_color)

        rect_path = QPainterPath()
        rect_path.addRoundedRect(QRectF(16, 16, size - 32, size - 32), 48, 48)

        painter.fillPath(rect_path, QBrush(bg_color))
        painter.setPen(QPen(accent_color, 6))
        painter.drawPath(rect_path)

        # Draw first letter of app name
        painter.setPen(QColor("#f8fafc"))
        font = QFont("sans-serif", int(size * 0.35), QFont.Weight.Bold)
        painter.setFont(font)
        letter = (app_name.strip()[:1] or "A").upper()
        painter.drawText(QRectF(16, 16, size - 32, size - 32), Qt.AlignmentFlag.AlignCenter, letter)

    # Now draw the badge in bottom-right corner
    badge_text = badge_text.strip()
    badge_diameter = int(size * 0.34)  # ~87px on 256px
    pad = 8

    # Determine shape: circle if text <= 2 chars, pill if longer
    if len(badge_text) > 2:
        badge_width = int(size * 0.48)
        badge_height = int(size * 0.28)
        bx = size - badge_width - pad
        by = size - badge_height - pad
        badge_rect = QRectF(bx, by, badge_width, badge_height)
        corner_radius = badge_height / 2
    else:
        bx = size - badge_diameter - pad
        by = size - badge_diameter - pad
        badge_rect = QRectF(bx, by, badge_diameter, badge_diameter)
        corner_radius = badge_diameter / 2

    # Draw dark shadow / outline ring for high contrast
    shadow_pen = QPen(QColor(15, 23, 42, 230), 6)
    painter.setPen(shadow_pen)
    fill_color = QColor(badge_color)
    painter.setBrush(QBrush(fill_color))
    painter.drawRoundedRect(badge_rect, corner_radius, corner_radius)

    # Draw inner badge text or symbol
    painter.setPen(QColor("white"))
    if badge_text:
        # Scale font to fit badge
        font_size = int(corner_radius * 1.1) if len(badge_text) <= 2 else int(corner_radius * 0.8)
        font = QFont("sans-serif", font_size, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)
    else:
        # Draw a small duplicate/clone icon indicator (two overlapping squares)
        inner_w = corner_radius * 0.8
        cx = badge_rect.center().x()
        cy = badge_rect.center().y()
        painter.setPen(QPen(QColor("white"), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(cx - inner_w * 0.6, cy - inner_w * 0.6, inner_w, inner_w), 3, 3)
        painter.drawRoundedRect(QRectF(cx - inner_w * 0.2, cy - inner_w * 0.2, inner_w, inner_w), 3, 3)

    painter.end()

    target.save(str(dest_path), "PNG")
    return dest_path
