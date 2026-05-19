from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "icon.ico"

BLUE = (22, 50, 79, 255)
WHITE = (253, 254, 254, 255)
FOLD = (217, 233, 242, 255)
TEAL = (0, 167, 165, 255)
YELLOW = (242, 184, 75, 255)


def blend(dst, src):
    sr, sg, sb, sa = src
    if sa == 255:
        return src
    dr, dg, db, da = dst
    a = sa / 255
    return (
        int(sr * a + dr * (1 - a)),
        int(sg * a + dg * (1 - a)),
        int(sb * a + db * (1 - a)),
        255,
    )


def set_px(img, x, y, color):
    if 0 <= x < len(img[0]) and 0 <= y < len(img):
        img[y][x] = blend(img[y][x], color)


def rounded_rect(img, x0, y0, x1, y1, r, color):
    for y in range(y0, y1):
        for x in range(x0, x1):
            dx = max(x0 + r - x, 0, x - (x1 - r - 1))
            dy = max(y0 + r - y, 0, y - (y1 - r - 1))
            if dx * dx + dy * dy <= r * r:
                set_px(img, x, y, color)


def polygon(img, points, color):
    ys = [p[1] for p in points]
    for y in range(min(ys), max(ys) + 1):
        xs = []
        for i, p1 in enumerate(points):
            p2 = points[(i + 1) % len(points)]
            if (p1[1] <= y < p2[1]) or (p2[1] <= y < p1[1]):
                x = p1[0] + (y - p1[1]) * (p2[0] - p1[0]) / (p2[1] - p1[1])
                xs.append(int(round(x)))
        xs.sort()
        for a, b in zip(xs[0::2], xs[1::2]):
            for x in range(a, b + 1):
                set_px(img, x, y, color)


def circle(img, cx, cy, r, color):
    rr = r * r
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= rr:
                set_px(img, x, y, color)


def line(img, x0, y0, x1, y1, width, color):
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    radius = max(1, width // 2)
    for i in range(steps + 1):
        t = i / steps
        x = int(round(x0 + (x1 - x0) * t))
        y = int(round(y0 + (y1 - y0) * t))
        circle(img, x, y, radius, color)


def wave(img, x0, y0, x1, amp, width, color):
    points = []
    for i in range(80):
        t = i / 79
        x = x0 + int((x1 - x0) * t)
        y = y0 + int(math.sin(t * math.pi * 2) * amp)
        points.append((x, y))
    for a, b in zip(points, points[1:]):
        line(img, a[0], a[1], b[0], b[1], width, color)


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(img) -> bytes:
    h = len(img)
    w = len(img[0])
    raw = bytearray()
    for row in img:
        raw.append(0)
        for r, g, b, a in row:
            raw.extend((r, g, b, a))
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + png_chunk(b"IEND", b"")
    )


def make_icon(size: int) -> bytes:
    img = [[(0, 0, 0, 0) for _ in range(size)] for _ in range(size)]
    s = size / 256
    sc = lambda v: int(round(v * s))

    rounded_rect(img, 0, 0, size, size, sc(56), BLUE)

    doc = [
        (sc(86), sc(35)),
        (sc(165), sc(35)),
        (sc(195), sc(72)),
        (sc(195), sc(196)),
        (sc(170), sc(221)),
        (sc(86), sc(221)),
        (sc(61), sc(196)),
        (sc(61), sc(60)),
    ]
    polygon(img, doc, WHITE)
    polygon(img, [(sc(165), sc(35)), (sc(165), sc(72)), (sc(195), sc(72))], FOLD)

    wave(img, sc(90), sc(105), sc(164), sc(25), max(2, sc(13)), TEAL)
    line(img, sc(90), sc(142), sc(166), sc(142), max(2, sc(13)), YELLOW)
    line(img, sc(90), sc(174), sc(146), sc(174), max(2, sc(13)), BLUE)

    circle(img, sc(192), sc(194), sc(31), TEAL)
    line(img, sc(178), sc(194), sc(206), sc(194), max(2, sc(8)), WHITE)
    line(img, sc(192), sc(180), sc(192), sc(208), max(2, sc(8)), WHITE)

    return encode_png(img)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [(size, make_icon(size)) for size in sizes]

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = bytearray()
    data = bytearray()
    for size, png in images:
        width = 0 if size == 256 else size
        height = 0 if size == 256 else size
        entries.extend(struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32, len(png), offset))
        data.extend(png)
        offset += len(png)

    OUT.write_bytes(header + entries + data)
    print(f"Ícone gerado: {OUT}")


if __name__ == "__main__":
    main()
