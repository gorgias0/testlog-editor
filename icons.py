from PySide6.QtCore import QByteArray, Qt, QBuffer, QIODevice
from PySide6.QtGui import QIcon, QPainter, QPixmap, QImage
from PySide6.QtSvg import QSvgRenderer


APP_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120">
  <rect x="0" y="8" width="100" height="112" rx="8" fill="#2280e0"/>
  <rect x="25" y="0" width="50" height="18" rx="5" fill="#1a6fc4"/>
  <rect x="35" y="3" width="30" height="10" rx="3" fill="#0f4a8a"/>
  <line x1="14" y1="36" x2="86" y2="36" stroke="white" stroke-width="2.5" stroke-linecap="round" opacity="0.5"/>
  <line x1="14" y1="50" x2="86" y2="50" stroke="white" stroke-width="2.5" stroke-linecap="round" opacity="0.5"/>
  <line x1="14" y1="64" x2="60" y2="64" stroke="white" stroke-width="2.5" stroke-linecap="round" opacity="0.5"/>
  <circle cx="66" cy="90" r="18" fill="#22c55e"/>
  <polyline points="56,90 63,98 78,82" fill="none" stroke="white" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''

TESTLOG_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 66">
  <path d="M0 0 L36 0 L48 12 L48 60 Q48 66 42 66 L6 66 Q0 66 0 60 Z" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
  <path d="M36 0 L36 12 L48 12 Z" fill="#93c5fd"/>
  <circle cx="30" cy="46" r="10" fill="#22c55e"/>
  <polyline points="24,46 28,51 37,40" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''

FOLDER_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 56">
  <path d="M0 10 Q0 4 6 4 L20 4 L26 0 L58 0 Q64 0 64 6 L64 50 Q64 56 58 56 L6 56 Q0 56 0 50 Z" fill="#f59e0b"/>
  <path d="M0 16 L64 16 L64 50 Q64 56 58 56 L6 56 Q0 56 0 50 Z" fill="#fbbf24"/>
</svg>'''

FOLDER_PINNED_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 56">
  <path d="M0 10 Q0 4 6 4 L20 4 L26 0 L58 0 Q64 0 64 6 L64 50 Q64 56 58 56 L6 56 Q0 56 0 50 Z" fill="#f59e0b"/>
  <path d="M0 16 L64 16 L64 50 Q64 56 58 56 L6 56 Q0 56 0 50 Z" fill="#fbbf24"/>
  <circle cx="54" cy="10" r="9" fill="#ef4444"/>
  <line x1="54" y1="5" x2="54" y2="15" stroke="white" stroke-width="2" stroke-linecap="round"/>
  <line x1="49" y1="10" x2="59" y2="10" stroke="white" stroke-width="2" stroke-linecap="round"/>
</svg>'''

TESTLOG_PINNED_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 66">
  <path d="M0 0 L36 0 L48 12 L48 60 Q48 66 42 66 L6 66 Q0 66 0 60 Z" fill="#dbeafe" stroke="#93c5fd" stroke-width="1"/>
  <path d="M36 0 L36 12 L48 12 Z" fill="#93c5fd"/>
  <circle cx="30" cy="46" r="10" fill="#22c55e"/>
  <polyline points="24,46 28,51 37,40" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="40" cy="8" r="9" fill="#ef4444"/>
  <line x1="40" y1="3" x2="40" y2="13" stroke="white" stroke-width="2" stroke-linecap="round"/>
  <line x1="35" y1="8" x2="45" y2="8" stroke="white" stroke-width="2" stroke-linecap="round"/>
</svg>'''


def icon_from_svg(svg_text, size=64):
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def multi_icon_from_svg(svg_text, sizes=(16, 24, 32, 48, 64, 128, 256)):
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    icon = QIcon()

    for size in sizes:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)

    return icon


def ico_bytes_from_svg(svg_text, sizes=(16, 24, 32, 48, 64, 128, 256)):
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    images = []

    for size in sizes:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        images.append((size, bytes(buffer.data())))

    icon_dir_size = 6 + (16 * len(images))
    data_offset = icon_dir_size
    directory_entries = bytearray()
    image_data = bytearray()

    for size, png_data in images:
        width = 0 if size >= 256 else size
        height = 0 if size >= 256 else size
        directory_entries.extend(width.to_bytes(1, "little"))
        directory_entries.extend(height.to_bytes(1, "little"))
        directory_entries.extend((0).to_bytes(1, "little"))
        directory_entries.extend((0).to_bytes(1, "little"))
        directory_entries.extend((1).to_bytes(2, "little"))
        directory_entries.extend((32).to_bytes(2, "little"))
        directory_entries.extend(len(png_data).to_bytes(4, "little"))
        directory_entries.extend(data_offset.to_bytes(4, "little"))
        image_data.extend(png_data)
        data_offset += len(png_data)

    header = bytearray()
    header.extend((0).to_bytes(2, "little"))
    header.extend((1).to_bytes(2, "little"))
    header.extend(len(images).to_bytes(2, "little"))

    return bytes(header + directory_entries + image_data)
