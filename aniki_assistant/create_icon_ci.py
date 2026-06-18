"""
Создание иконки для CI/CD (без дисплея, без PyQt6).
Создаёт минимальный валидный .ico файл программно.
"""
import struct
import os
import math


def make_ico(output_path, sizes=(16, 32, 48)):
    """Создать .ico файл без внешних зависимостей."""
    images = []
    for size in sizes:
        images.append(_make_png_bytes(size))

    header = struct.pack('<HHH', 0, 1, len(images))

    image_data_offset = 6 + len(images) * 16
    dir_entries = b''
    offsets = []
    current_offset = image_data_offset
    for i, (img_bytes, s) in enumerate(zip(images, sizes)):
        width = s if s < 256 else 0
        height = s if s < 256 else 0
        color_count = 0
        reserved = 0
        planes = 1
        bit_count = 32
        size_in_bytes = len(img_bytes)
        dir_entries += struct.pack('<BBBBHHII',
            width, height, color_count, reserved,
            planes, bit_count, size_in_bytes, current_offset)
        offsets.append(current_offset)
        current_offset += size_in_bytes

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(header)
        f.write(dir_entries)
        for img_bytes in images:
            f.write(img_bytes)

    print(f"Icon created: {output_path} ({os.path.getsize(output_path)} bytes)")


def _make_png_bytes(size):
    """Создать PNG-байты с простой иконкой (тёмный круг + буква A)."""
    import zlib

    width = height = size
    pixels = []

    cx = cy = size / 2
    r = size * 0.44

    for y in range(height):
        for x in range(width):
            dx = x - cx + 0.5
            dy = y - cy + 0.5
            dist = math.sqrt(dx*dx + dy*dy)
            if dist <= r:
                rel_x = dx / r
                rel_y = dy / r
                letter_x = 0.15 <= rel_x <= 0.35 or -0.35 <= rel_x <= -0.15 or (-0.2 <= rel_x <= 0.2 and -0.05 <= rel_y <= 0.1)
                if letter_x and abs(rel_x) > 0.12:
                    pixels.extend([255, 158, 68, 255])
                elif -0.2 <= rel_x <= 0.2 and -0.05 <= rel_y <= 0.15:
                    pixels.extend([255, 158, 68, 255])
                else:
                    t = 1.0 - (dist / r)
                    bg_r = int(26 + t * 20)
                    bg_g = int(26 + t * 20)
                    bg_b = int(46 + t * 20)
                    pixels.extend([bg_r, bg_g, bg_b, 255])
            else:
                pixels.extend([0, 0, 0, 0])

    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'
        for x in range(width):
            i = (y * width + x) * 4
            raw_data += bytes(pixels[i:i+4])

    compressed = zlib.compress(raw_data, 9)

    def make_chunk(chunk_type, data):
        crc = zlib.crc32(chunk_type + data) & 0xffffffff
        return struct.pack('>I', len(data)) + chunk_type + data + struct.pack('>I', crc)

    png = b'\x89PNG\r\n\x1a\n'
    png += make_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    png += make_chunk(b'IDAT', compressed)
    png += make_chunk(b'IEND', b'')

    return png


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(script_dir, 'resources', 'aniki.ico')
    make_ico(ico_path, sizes=(16, 32, 48, 256))
    print("Done! Let's go!")
