#!/usr/bin/env python3
"""THE MONDAY GLOBE - one picture that sums up the world news of
Monday 23 November 2026, drawn procedurally with the Python standard
library only (no image files, no network, fully deterministic).

The program renders an illustrated newspaper front page at 2x and
box-downsamples it to 1024x1024, then writes a PNG to
$MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png) and to
./entry.png beside the working directory.
"""

import math
import os
import struct
import zlib

W = 1024          # final image width
H = 1024          # final image height
SS = 2            # supersampling factor while drawing
RW = W * SS       # render width
RH = H * SS       # render height


# ---------------------------------------------------------------- PNG out

def write_png(path, width, height, rgb):
    """rgb: bytearray of width*height*3. Filter 0 rows, zlib level 9."""
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- canvas

class Canvas:
    """RGB pixel buffer at render resolution. All public drawing
    coordinates are in final-image units (1024x1024) and are scaled
    by SS internally."""

    def __init__(self):
        self.buf = bytearray(RW * RH * 3)

    # -- low level ----------------------------------------------------
    def _span(self, x0, x1, y, col):
        """Fill render-space pixels x0..x1 on row y with col."""
        if y < 0 or y >= RH:
            return
        if x0 < 0:
            x0 = 0
        if x1 >= RW:
            x1 = RW - 1
        if x1 < x0:
            return
        n = x1 - x0 + 1
        row = bytes(col) * n
        off = (y * RW + x0) * 3
        self.buf[off:off + 3 * n] = row

    def fill_all(self, col):
        self.buf[:] = bytes(col) * (RW * RH)

    # -- shapes (final-image units) -----------------------------------
    def rect(self, x, y, w, h, col):
        x0 = int(round(x * SS)); x1 = int(round((x + w) * SS)) - 1
        y0 = int(round(y * SS)); y1 = int(round((y + h) * SS)) - 1
        for yy in range(y0, y1 + 1):
            self._span(x0, x1, yy, col)

    def circle(self, cx, cy, r, col, clip=None):
        cxr = cx * SS; cyr = cy * SS; rr = r * SS
        y0 = int(math.floor(cyr - rr)); y1 = int(math.ceil(cyr + rr))
        for yy in range(y0, y1 + 1):
            dy = yy - cyr
            rem = rr * rr - dy * dy
            if rem < 0:
                continue
            dx = math.isqrt(int(rem))
            xa = int(cxr - dx); xb = int(cxr + dx)
            if clip is not None:
                ccx, ccy, cr = clip
                cdy = yy - ccy * SS
                crem = (cr * SS) ** 2 - cdy * cdy
                if crem < 0:
                    continue
                cdx = math.isqrt(int(crem))
                xa = max(xa, int(ccx * SS - cdx))
                xb = min(xb, int(ccx * SS + cdx))
            self._span(xa, xb, yy, col)

    def ellipse(self, cx, cy, rx, ry, col, clip=None):
        cxr = cx * SS; cyr = cy * SS
        rxr = rx * SS; ryr = ry * SS
        y0 = int(math.floor(cyr - ryr)); y1 = int(math.ceil(cyr + ryr))
        for yy in range(y0, y1 + 1):
            t = (yy - cyr) / ryr
            rem = 1.0 - t * t
            if rem < 0:
                continue
            dx = rxr * math.sqrt(rem)
            xa = int(cxr - dx); xb = int(cxr + dx)
            if clip is not None:
                ccx, ccy, cr = clip
                cdy = yy - ccy * SS
                crem = (cr * SS) ** 2 - cdy * cdy
                if crem < 0:
                    continue
                cdx = math.isqrt(int(crem))
                xa = max(xa, int(ccx * SS - cdx))
                xb = min(xb, int(ccx * SS + cdx))
            self._span(xa, xb, yy, col)

    def poly(self, pts, col, clip=None):
        """Filled polygon; pts are (x, y) in final-image units."""
        rp = [(x * SS, y * SS) for x, y in pts]
        ys = [p[1] for p in rp]
        y0 = int(math.floor(min(ys))); y1 = int(math.ceil(max(ys)))
        n = len(rp)
        for yy in range(y0, y1 + 1):
            yc = yy + 0.5
            xs = []
            for i in range(n):
                xa, ya = rp[i]
                xb, yb = rp[(i + 1) % n]
                if (ya <= yc < yb) or (yb <= yc < ya):
                    xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
            if len(xs) < 2:
                continue
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                xa = int(math.floor(xs[i])); xb = int(math.ceil(xs[i + 1]))
                if clip is not None:
                    ccx, ccy, cr = clip
                    cdy = yy - ccy * SS
                    crem = (cr * SS) ** 2 - cdy * cdy
                    if crem < 0:
                        continue
                    cdx = math.isqrt(int(crem))
                    xa = max(xa, int(ccx * SS - cdx))
                    xb = min(xb, int(ccx * SS + cdx))
                self._span(xa, xb, yy, col)

    def _stamp(self, cx, cy, r, col):
        """Filled circle in render space (for thick strokes)."""
        y0 = int(math.floor(cy - r)); y1 = int(math.ceil(cy + r))
        for yy in range(y0, y1 + 1):
            dy = yy - cy
            rem = r * r - dy * dy
            if rem < 0:
                continue
            dx = math.isqrt(int(rem)) if rem == int(rem) else int(math.sqrt(rem))
            self._span(int(cx - dx), int(cx + dx), yy, col)

    def line(self, x0, y0, x1, y1, col, wdt=2.0):
        """Thick round-capped line, final-image units."""
        ax, ay = x0 * SS, y0 * SS
        bx, by = x1 * SS, y1 * SS
        r = max(1.0, wdt * SS / 2.0)
        dist = math.hypot(bx - ax, by - ay)
        steps = max(1, int(dist / max(1.0, r * 0.6)))
        for i in range(steps + 1):
            t = i / steps
            self._stamp(ax + (bx - ax) * t, ay + (by - ay) * t, r, col)

    def polyline(self, pts, col, wdt=2.0):
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                      col, wdt)

    def frame(self, x, y, w, h, col, wdt=2.0):
        self.rect(x, y, w, wdt, col)
        self.rect(x, y + h - wdt, w, wdt, col)
        self.rect(x, y, wdt, h, col)
        self.rect(x + w - wdt, y, wdt, h, col)

    def downsample(self):
        """Box-average SS x SS blocks into the final 1024x1024 buffer."""
        out = bytearray(W * H * 3)
        rb = self.buf
        for y in range(H):
            for x in range(W):
                r = g = b = 0
                for dy in range(SS):
                    base = ((y * SS + dy) * RW + x * SS) * 3
                    for dx in range(SS):
                        o = base + dx * 3
                        r += rb[o]; g += rb[o + 1]; b += rb[o + 2]
                n = SS * SS
                o = (y * W + x) * 3
                out[o] = r // n; out[o + 1] = g // n; out[o + 2] = b // n
        return out


# ---------------------------------------------------------------- font
# Hand-drawn stroke font. Glyph space: x 0..6, y 0..9 (y up, 0 = baseline,
# 9 = cap height). Each glyph is a list of polylines. A single-point
# polyline draws a dot. Text is upper-cased before rendering.

GLYPHS = {
    'A': [[(0, 0), (3, 9), (6, 0)], [(1.15, 3.1), (4.85, 3.1)]],
    'B': [[(0, 0), (0, 9)],
          [(0, 9), (3.1, 9), (4.3, 8.1), (4.3, 7.2), (3.1, 6.3), (0, 6.3)],
          [(0, 6.3), (3.5, 6.3), (4.9, 5.2), (4.9, 1.1), (3.5, 0), (0, 0)]],
    'C': [[(5.7, 7.5), (4.5, 8.8), (2.9, 9.1), (1.3, 8.3), (0.4, 6.5),
           (0.4, 2.5), (1.3, 0.7), (2.9, -0.1), (4.5, 0.2), (5.7, 1.5)]],
    'D': [[(0, 0), (0, 9)],
          [(0, 9), (2.9, 9), (4.6, 7.9), (5.4, 6), (5.4, 3), (4.6, 1.1),
           (2.9, 0), (0, 0)]],
    'E': [[(5.6, 9), (0, 9), (0, 0), (5.6, 0)], [(0, 4.6), (4.3, 4.6)]],
    'F': [[(5.6, 9), (0, 9), (0, 0)], [(0, 4.6), (4.2, 4.6)]],
    'G': [[(5.7, 7.5), (4.5, 8.8), (2.9, 9.1), (1.3, 8.3), (0.4, 6.5),
           (0.4, 2.5), (1.3, 0.7), (2.9, -0.1), (4.7, 0.1), (5.8, 1.3),
           (5.8, 3.7), (3.7, 3.7)]],
    'H': [[(0, 0), (0, 9)], [(5.9, 0), (5.9, 9)], [(0, 4.6), (5.9, 4.6)]],
    'I': [[(0, 0), (0, 9)]],
    'J': [[(5.3, 9), (5.3, 1.9), (4.3, 0.4), (2.5, 0), (1.1, 0.9),
           (0.5, 2.4)]],
    'K': [[(0, 0), (0, 9)], [(5.7, 9), (0.7, 3.8)], [(1.8, 5.1), (5.9, 0)]],
    'L': [[(0, 9), (0, 0), (5.6, 0)]],
    'M': [[(0, 0), (0, 9), (3, 3.2), (6, 9), (6, 0)]],
    'N': [[(0, 0), (0, 9), (6, 0), (6, 9)]],
    'O': [[(2.95, 9.1), (1.2, 8.3), (0.35, 6.3), (0.35, 2.7), (1.2, 0.7),
           (2.95, -0.1), (4.7, 0.7), (5.55, 2.7), (5.55, 6.3), (4.7, 8.3),
           (2.95, 9.1)]],
    'P': [[(0, 0), (0, 9)],
          [(0, 9), (3.3, 9), (4.7, 7.9), (4.7, 6), (3.3, 4.9), (0, 4.9)]],
    'Q': [[(2.95, 9.1), (1.2, 8.3), (0.35, 6.3), (0.35, 2.7), (1.2, 0.7),
           (2.95, -0.1), (4.7, 0.7), (5.55, 2.7), (5.55, 6.3), (4.7, 8.3),
           (2.95, 9.1)], [(3.6, 2.4), (6.1, -0.2)]],
    'R': [[(0, 0), (0, 9)],
          [(0, 9), (3.3, 9), (4.7, 7.9), (4.7, 6), (3.3, 4.9), (0, 4.9)],
          [(2.4, 4.9), (6, 0)]],
    'S': [[(5.5, 7.7), (4.1, 9), (2.3, 9), (0.9, 7.9), (1.2, 6.3),
           (4.9, 4.9), (5.6, 3.5), (4.7, 0.9), (2.9, 0), (1.1, 0.3),
           (0.3, 1.7)]],
    'T': [[(0, 9), (6, 9)], [(3, 9), (3, 0)]],
    'U': [[(0, 9), (0, 2.5), (1, 0.6), (2.9, 0), (4.8, 0.6), (5.8, 2.5),
           (5.8, 9)]],
    'V': [[(0, 9), (2.95, 0), (5.9, 9)]],
    'W': [[(0, 9), (1.35, 0), (2.95, 6.2), (4.55, 0), (5.9, 9)]],
    'X': [[(0, 0), (5.9, 9)], [(0, 9), (5.9, 0)]],
    'Y': [[(0, 9), (2.95, 4.7), (5.9, 9)], [(2.95, 4.7), (2.95, 0)]],
    'Z': [[(0, 9), (5.9, 9), (0, 0), (5.9, 0)]],
    '$': [[(5.5, 7.7), (4.1, 9), (2.3, 9), (0.9, 7.9), (1.2, 6.3),
           (4.9, 4.9), (5.6, 3.5), (4.7, 0.9), (2.9, 0), (1.1, 0.3),
           (0.3, 1.7)], [(2.9, -1.2), (2.9, 10.2)]],
    '\u00dc': [[(0, 9), (0, 2.5), (1, 0.6), (2.9, 0), (4.8, 0.6),
                (5.8, 2.5), (5.8, 9)], [(1.2, 10.4)], [(4.6, 10.4)]],
    '0': [[(2.9, 9.1), (1.3, 8.3), (0.5, 6.3), (0.5, 2.7), (1.3, 0.7),
           (2.9, -0.1), (4.5, 0.7), (5.3, 2.7), (5.3, 6.3), (4.5, 8.3),
           (2.9, 9.1)]],
    '1': [[(1.3, 7.1), (3.1, 9), (3.1, 0)], [(1.1, 0), (5.1, 0)]],
    '2': [[(0.5, 7.3), (1.6, 8.8), (3.4, 9.1), (4.9, 7.9), (4.7, 6.1),
           (0.4, 0), (5.7, 0)]],
    '3': [[(0.5, 7.7), (2.1, 9), (3.9, 8.7), (4.3, 7.1), (2.7, 6)],
          [(2.7, 6), (4.3, 5.6), (5.1, 4.2), (4.6, 1.6), (3, 0),
           (1.1, 0.4), (0.4, 1.9)]],
    '4': [[(4.3, 0), (4.3, 9), (0.2, 2.7), (6, 2.7)]],
    '5': [[(5.5, 9), (0.9, 9), (0.7, 5.7), (2.6, 6.5), (4.4, 5.9),
           (5.1, 4.3), (4.5, 1.4), (2.7, 0), (0.9, 0.6), (0.4, 2.1)]],
    '6': [[(4.9, 8.5), (3.3, 9.1), (1.5, 7.7), (0.6, 5.1), (0.6, 2.7),
           (1.4, 0.7), (3, 0), (4.6, 0.9), (5, 2.9), (4.3, 4.7),
           (2.7, 5.1), (0.9, 4.2)]],
    '7': [[(0.4, 9), (5.8, 9), (2.9, 0)]],
    '8': [[(2.9, 5.3), (1.5, 6.2), (1.4, 7.7), (2.2, 8.9), (3.6, 8.9),
           (4.4, 7.7), (4.3, 6.2), (2.9, 5.3)],
          [(2.9, 5.3), (1.3, 4.3), (1.1, 2.3), (1.9, 0.6), (2.9, 0),
           (3.9, 0.6), (4.7, 2.3), (4.5, 4.3), (2.9, 5.3)]],
    '9': [[(1, 0.5), (2.7, 0), (4.5, 1.4), (5.3, 4.1), (5.3, 6.5),
           (4.5, 8.4), (2.9, 9.1), (1.3, 8.2), (0.9, 6.3), (1.6, 4.5),
           (3.2, 4.1), (5, 4.9)]],
    '.': [[(0.5, 0.5)]],
    ',': [[(0.6, 0.8), (0.2, -1.4)]],
    "'": [[(0.5, 9), (0.3, 6.7)]],
    '-': [[(0.7, 4.3), (4.7, 4.3)]],
    '\u2013': [[(0.7, 4.3), (4.7, 4.3)]],
    '\u2014': [[(0.2, 4.3), (5.8, 4.3)]],
    ':': [[(0.5, 1.1)], [(0.5, 6.6)]],
    ';': [[(0.5, 6.6)], [(0.6, 0.8), (0.2, -1.3)]],
    '!': [[(0.5, 9), (0.5, 2.3)], [(0.5, 0.5)]],
    '?': [[(0.6, 7.5), (1.8, 9), (3.8, 8.9), (4.9, 7.3), (4.3, 5.5),
           (2.8, 4.5), (2.8, 3.1)], [(2.8, 0.5)]],
    '%': [[(0.9, 0), (5.1, 9)],
          [(1.5, 7.4), (0.7, 8.2), (1.5, 9), (2.3, 8.2), (1.5, 7.4)],
          [(4.5, 0.2), (3.7, 1), (4.5, 1.8), (5.3, 1), (4.5, 0.2)]],
    '+': [[(2.9, 1.7), (2.9, 7.3)], [(0.5, 4.5), (5.3, 4.5)]],
    '/': [[(0.7, 0), (5.2, 9)]],
    '(': [[(4.4, 9.2), (2.7, 6.9), (2.1, 4.5), (2.7, 2.1), (4.4, -0.2)]],
    ')': [[(1.6, 9.2), (3.3, 6.9), (3.9, 4.5), (3.3, 2.1), (1.6, -0.2)]],
    '\u00b7': [[(0.5, 4.3)]],
    '\u00b0': [[(2.9, 7.3), (1.9, 8), (2.9, 8.7), (3.9, 8), (2.9, 7.3)]],
}

WIDTHS = {'I': 1.2, '1': 5.2, '.': 1.2, ',': 1.4, "'": 1.2, ':': 1.2,
          ';': 1.4, '!': 1.2, '\u00b7': 1.2, ' ': 3.4, '(': 4.8, ')': 4.8,
          '/': 5.6, '\u00b0': 4.2}
ADV = 1.7  # inter-letter gap, glyph units


def _norm(s):
    return (s.replace('\u2212', '-').replace('\u2019', "'")
             .replace('\u201c', "'").replace('\u201d', "'").upper())


def text_width(s, size):
    s = _norm(s)
    unit = size / 9.0
    w = 0.0
    for ch in s:
        w += WIDTHS.get(ch, 6.0) + ADV
    return (w - ADV) * unit if s else 0.0


def draw_text(cv, x, y_top, s, size, col, bold=False, align='left'):
    """Draw text with its cap-height box top at y_top. Returns width."""
    s = _norm(s)
    unit = size / 9.0
    total = text_width(s, size)
    if align == 'center':
        x -= total / 2.0
    elif align == 'right':
        x -= total
    lw = size * (0.16 if bold else 0.115)
    cx = x
    for ch in s:
        if ch == ' ':
            cx += (WIDTHS[' '] + ADV) * unit
            continue
        glyph = GLYPHS.get(ch)
        if glyph is None:
            cx += (6.0 + ADV) * unit
            continue
        for stroke in glyph:
            pts = [(cx + gx * unit, y_top + (9.0 - gy) * unit)
                   for gx, gy in stroke]
            if len(pts) == 1:
                cv.circle(pts[0][0], pts[0][1], lw * 0.62, col)
            else:
                cv.polyline(pts, col, lw)
        cx += (WIDTHS.get(ch, 6.0) + ADV) * unit
    return total


def wrap_text(s, size, max_w):
    """Greedy word wrap; returns a list of lines that fit max_w."""
    words = s.split()
    lines = []
    cur = ''
    for wd in words:
        trial = wd if not cur else cur + ' ' + wd
        if text_width(trial, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def draw_block(cv, x, y_top, s, size, col, max_w, leading=1.28,
               bold=False, align='left'):
    """Wrap and draw a paragraph; returns the y just below it."""
    lines = wrap_text(s, size, max_w)
    for ln in lines:
        draw_text(cv, x, y_top, ln, size, col, bold=bold, align=align)
        y_top += size * leading
    return y_top


# ---------------------------------------------------------------- palette

PAPER = (248, 243, 231)
INK = (26, 24, 20)
FAINT = (110, 102, 88)
RED = (178, 34, 27)
DARKRED = (140, 26, 20)
BLUE = (29, 78, 137)
OCEAN = (62, 116, 172)
LAND = (74, 148, 84)
SAND = (226, 199, 141)
NAVY = (15, 30, 52)
NAVY2 = (27, 51, 84)
SKY = (196, 220, 240)
GREY = (128, 124, 116)
LGREY = (196, 190, 176)
ORANGE = (232, 119, 34)
FLAME = (244, 164, 38)
YELLOW = (252, 214, 90)
GREEN = (38, 140, 74)
PINK = (214, 84, 138)
WHITE = (255, 255, 255)
CHART_RED = (255, 84, 66)
CHART_GREEN = (64, 214, 130)


# ---------------------------------------------------------------- scenes

def flame(cv, x, y, w, h):
    """Layered teardrop flame with base at (x, y), width w, height h."""
    outer = [(x, y), (x + w * 0.12, y - h * 0.35), (x + w * 0.34, y - h * 0.62),
             (x + w * 0.5, y - h), (x + w * 0.66, y - h * 0.62),
             (x + w * 0.88, y - h * 0.35), (x + w, y)]
    cv.poly(outer, ORANGE)
    inner = [(x + w * 0.24, y), (x + w * 0.36, y - h * 0.3),
             (x + w * 0.5, y - h * 0.62), (x + w * 0.64, y - h * 0.3),
             (x + w * 0.76, y)]
    cv.poly(inner, FLAME)
    core = [(x + w * 0.38, y), (x + w * 0.5, y - h * 0.34),
            (x + w * 0.62, y)]
    cv.poly(core, YELLOW)


def smoke(cv, cx, cy, r, col=(176, 170, 158)):
    cv.circle(cx - r * 0.7, cy + r * 0.25, r * 0.62, col)
    cv.circle(cx + r * 0.65, cy + r * 0.3, r * 0.55, col)
    cv.circle(cx, cy - r * 0.25, r * 0.8, col)
    cv.circle(cx + r * 0.2, cy + r * 0.35, r * 0.6, col)


def globe(cv, cx, cy, r):
    clip = (cx, cy, r)
    cv.circle(cx, cy, r, OCEAN)
    # stylised continents, clipped to the sphere
    cv.ellipse(cx - r * 0.52, cy - r * 0.42, r * 0.34, r * 0.24, LAND, clip)
    cv.ellipse(cx - r * 0.38, cy + r * 0.18, r * 0.2, r * 0.3, LAND, clip)
    cv.ellipse(cx + r * 0.16, cy - r * 0.5, r * 0.4, r * 0.22, LAND, clip)
    cv.ellipse(cx + r * 0.34, cy - r * 0.05, r * 0.26, r * 0.3, LAND, clip)
    cv.ellipse(cx + r * 0.58, cy + r * 0.42, r * 0.2, r * 0.14, LAND, clip)
    cv.ellipse(cx - r * 0.05, cy + r * 0.62, r * 0.34, r * 0.1, LAND, clip)
    # polar cap
    cv.ellipse(cx, cy - r * 0.92, r * 0.4, r * 0.12, WHITE, clip)
    # the crack: the deal breaking apart
    crack = [(cx - r * 0.55, cy - r * 0.75), (cx - r * 0.28, cy - r * 0.4),
             (cx - r * 0.42, cy - r * 0.08), (cx - r * 0.1, cy + r * 0.22),
             (cx - r * 0.24, cy + r * 0.55), (cx - r * 0.02, cy + r * 0.85)]
    cv.polyline(crack, INK, 3.4)
    crack2 = [(cx - r * 0.42, cy - r * 0.08), (cx + r * 0.16, cy + r * 0.05),
              (cx + r * 0.38, cy - r * 0.2)]
    cv.polyline(crack2, INK, 2.6)
    # outline
    for i in range(73):
        a0 = i * 2 * math.pi / 72
        a1 = (i + 1) * 2 * math.pi / 72
        cv.line(cx + r * math.cos(a0), cy + r * math.sin(a0),
                cx + r * math.cos(a1), cy + r * math.sin(a1), INK, 3.0)


def thermometer(cv, x, y_top, h):
    wdt = 15
    cv.rect(x, y_top, wdt, h, WHITE)
    cv.frame(x, y_top, wdt, h, INK, 2.2)
    bulb_y = y_top + h + 12
    cv.circle(x + wdt / 2, bulb_y, 16.5, INK)
    cv.circle(x + wdt / 2, bulb_y, 14, RED)
    cv.rect(x + 3.5, y_top + h * 0.18, wdt - 7, h * 0.82 + 10, RED)
    for i in range(5):
        ty = y_top + 8 + i * (h - 16) / 4
        cv.line(x + wdt + 3, ty, x + wdt + 11, ty, INK, 2.0)


def dome_hall(cv, cx, base_y, w):
    """Conference hall: shallow dome on a colonnade."""
    cv.ellipse(cx, base_y - 26, w / 2, 34, (214, 205, 182))
    cv.rect(cx - w / 2, base_y - 28, w, 8, (196, 186, 162))
    for i in range(7):
        px = cx - w / 2 + 12 + i * (w - 24) / 6
        cv.rect(px - 3, base_y - 20, 6, 20, (196, 186, 162))
    cv.rect(cx - w / 2 - 6, base_y, w + 12, 6, (178, 168, 144))
    cv.line(cx, base_y - 58, cx, base_y - 78, INK, 2.2)
    cv.poly([(cx, base_y - 78), (cx + 20, base_y - 71), (cx, base_y - 64)], RED)


def waves(cv, x0, x1, y, col, amp=5, wl=34, wdt=3.0):
    pts = []
    n = int((x1 - x0) / 6)
    for i in range(n + 1):
        xx = x0 + i * 6
        pts.append((xx, y + amp * math.sin((xx - x0) * 2 * math.pi / wl)))
    cv.polyline(pts, col, wdt)


def ship_hull(cv, cx, cy, w, h, col, tilt=-0.16):
    ca, sa = math.cos(tilt), math.sin(tilt)

    def rot(px, py):
        return (cx + px * ca - py * sa, cy + px * sa + py * ca)

    hull = [rot(-w / 2, 0), rot(w / 2, 0), rot(w / 2 - 14, h), rot(-w / 2 + 6, h)]
    cv.poly(hull, col)
    return rot


def flame_row(cv, x, y, n, w, h, gap):
    for i in range(n):
        flame(cv, x + i * (w + gap), y, w, h * (0.75 + 0.25 * ((i * 7) % 3) / 2))



# ---------------------------------------------------------------- stories
# Winning-form structure: every drawn story carries a number, a region
# tag, a certainty badge, a bold headline and a sourced factual sub.

CONFIRMED = (38, 140, 74)     # 2+ outlets
OFFICIAL = (29, 78, 137)      # on the record
REPORTED = (156, 110, 26)     # one outlet
SUBCOL = (84, 78, 66)
CARD = (253, 250, 243)


def badge(cv, x_right, y, text, col, size=9.0):
    w = text_width(text, size) + 11
    cv.rect(x_right - w, y, w, size + 6, col)
    draw_text(cv, x_right - w + 5.5, y + 3, text, size, WHITE, bold=True)
    return w


def num_chip(cv, cx, cy, n, r=11):
    cv.circle(cx, cy, r, RED)
    size = r * 1.12
    draw_text(cv, cx, cy - size * 0.52, str(n), size, WHITE, bold=True,
              align='center')


def lead(cv, x, y, w, h, num, region, btext, bcol, illo, headline, sub):
    cv.rect(x, y, w, h, CARD)
    cv.frame(x, y, w, h, INK, 1.6)
    illo(cv, x, y, w)
    num_chip(cv, x + 19, y + 117, num, 11.5)
    draw_text(cv, x + 38, y + 110, region, 11.5, INK, bold=True)
    badge(cv, x + w - 10, y + 109, btext, bcol, 9.5)
    hy = y + 134
    for ln in wrap_text(headline, 20.5, w - 22):
        draw_text(cv, x + 11, hy, ln, 20.5, INK, bold=True)
        hy += 25
    draw_block(cv, x + 11, y + 186, sub, 11, SUBCOL, w - 22,
               leading=1.22)


def lead_cop31(cv, x, y, w):
    globe(cv, x + 84, y + 54, 40)
    thermometer(cv, x + 158, y + 14, 56)
    draw_text(cv, x + 184, y + 12, 'HOT', 11, RED, bold=True)
    cv.rect(x + 216, y + 28, 72, 50, WHITE)
    cv.frame(x + 216, y + 28, 72, 50, INK, 1.6)
    for i in range(3):
        cv.rect(x + 226, y + 38 + i * 13, 52 - (i % 2) * 16, 4, LGREY)
    cv.line(x + 216, y + 28, x + 288, y + 78, RED, 4.5)
    cv.line(x + 288, y + 28, x + 216, y + 78, RED, 4.5)
    smoke(cv, x + 254, y + 14, 11)


def lead_markets(cv, x, y, w):
    cv.rect(x + 8, y + 6, w - 16, 94, NAVY)
    for gy in (30, 56, 82):
        cv.rect(x + 16, y + gy, w - 32, 1.1, NAVY2)
    pts = [(x + 20, y + 30), (x + 70, y + 38), (x + 120, y + 52),
           (x + 170, y + 58), (x + 220, y + 76), (x + 282, y + 88)]
    cv.polyline(pts, CHART_RED, 4.2)
    for px, py in pts[1:-1]:
        cv.circle(px, py, 4.4, WHITE)
        cv.circle(px, py, 3.2, CHART_RED)
    cv.poly([(x + 282, y + 88), (x + 262, y + 85), (x + 270, y + 68)],
            CHART_RED)
    draw_text(cv, x + 196, y + 14, '-5.06%', 19, CHART_RED, bold=True)
    draw_text(cv, x + 18, y + 80, '+3% US FUTURES', 10.5, CHART_GREEN,
              bold=True)
    draw_text(cv, x + 18, y + 12, 'NIKKEI', 10, WHITE, bold=True)


def lead_dymer(cv, x, y, w):
    bx, by = x + 34, y + 28
    cv.rect(bx, by, 88, 58, (146, 140, 130))
    cv.rect(bx, by, 88, 7, (110, 104, 96))
    for i in range(3):
        cv.rect(bx + 10 + i * 26, by + 16, 13, 13, (84, 80, 74))
    cv.polyline([(bx + 34, by + 7), (bx + 42, by + 26), (bx + 35, by + 42),
                 (bx + 46, by + 58)], INK, 2.6)
    cv.poly([(bx + 62, by), (bx + 88, by), (bx + 88, by + 20),
             (bx + 70, by + 11)], CARD)
    cv.poly([(bx - 6, by + 58), (bx + 24, by + 46), (bx + 34, by + 58)],
            (120, 114, 106))
    cv.poly([(bx + 50, by + 58), (bx + 72, by + 47), (bx + 92, by + 58)],
            (120, 114, 106))
    smoke(cv, x + 66, y + 16, 12, (188, 182, 170))
    cv.line(x + 196, y + 12, x + 196, y + 88, INK, 3.4)
    cv.line(x + 196, y + 12, x + 146, y + 12, INK, 3.4)
    cv.line(x + 156, y + 12, x + 156, y + 32, INK, 2.0)
    cv.rect(x + 143, y + 32, 27, 5, RED)
    cv.circle(x + 224, y + 50, 6.5, ORANGE)
    cv.line(x + 224, y + 57, x + 224, y + 72, ORANGE, 4.6)
    cv.line(x + 224, y + 63, x + 211, y + 70, ORANGE, 3.8)
    cv.line(x + 224, y + 72, x + 215, y + 86, ORANGE, 3.8)
    cv.line(x + 224, y + 72, x + 234, y + 86, ORANGE, 3.8)
    # denser rubble field along the building's base
    cv.poly([(bx + 14, by + 58), (bx + 38, by + 47), (bx + 54, by + 58)],
            (138, 132, 124))
    cv.poly([(bx + 46, by + 58), (bx + 64, by + 50), (bx + 80, by + 58)],
            (104, 98, 92))
    cv.poly([(bx + 84, by + 58), (bx + 100, by + 51), (bx + 110, by + 58)],
            (146, 140, 130))
    cv.polyline([(bx + 92, by + 58), (bx + 104, by + 38)],
                (110, 104, 96), 4.2)
    smoke(cv, x + 108, y + 88, 6, (198, 192, 180))
    # scattered debris chunks on the ground strip
    cv.poly([(x + 14, y + 96), (x + 26, y + 92), (x + 30, y + 97),
             (x + 18, y + 99)], (120, 114, 106))
    cv.poly([(x + 52, y + 99), (x + 60, y + 94), (x + 68, y + 99)],
            (104, 98, 92))
    cv.rect(x + 88, y + 95, 12, 4, (146, 140, 130))
    cv.poly([(x + 118, y + 98), (x + 128, y + 93), (x + 134, y + 98)],
            (120, 114, 106))
    cv.poly([(x + 168, y + 97), (x + 178, y + 93), (x + 184, y + 97),
             (x + 174, y + 100)], (138, 132, 124))
    cv.circle(x + 42, y + 97, 2.2, (104, 98, 92))
    cv.circle(x + 148, y + 96, 2.6, (120, 114, 106))
    cv.circle(x + 200, y + 95, 2.2, (138, 132, 124))
    cv.circle(x + 76, y + 92, 1.8, (146, 140, 130))
    # second rescuer, kneeling in the rubble, working a chunk free
    cv.circle(x + 158, y + 62, 5.5, BLUE)
    cv.line(x + 158, y + 68, x + 152, y + 82, BLUE, 4.4)
    cv.line(x + 155, y + 74, x + 143, y + 86, BLUE, 3.6)
    cv.line(x + 155, y + 74, x + 164, y + 84, BLUE, 3.6)
    cv.line(x + 152, y + 82, x + 163, y + 90, BLUE, 3.8)
    cv.line(x + 152, y + 82, x + 146, y + 91, BLUE, 3.8)
    # stretcher waiting beside the standing rescuer
    cv.rect(x + 172, y + 90, 34, 4.5, RED)
    cv.line(x + 176, y + 95, x + 176, y + 99, INK, 2.0)
    cv.line(x + 202, y + 95, x + 202, y + 99, INK, 2.0)
    draw_text(cv, x + 252, y + 40, 'BOY, 7,', 13, RED, bold=True)
    draw_text(cv, x + 252, y + 58, 'RESCUED', 13, RED, bold=True)


# -- flat pictograms, drawn in a ~76x34 box centred on (cx, cy) ---------

def icon_ship(cv, cx, cy):
    cv.poly([(cx - 30, cy + 2), (cx + 30, cy + 2), (cx + 22, cy + 12),
             (cx - 24, cy + 12)], (52, 58, 66))
    cv.rect(cx - 6, cy - 10, 20, 12, (52, 58, 66))
    cv.line(cx + 18, cy + 2, cx + 18, cy - 14, INK, 2.6)
    cv.circle(cx + 27, cy - 13, 3, INK)
    cv.line(cx + 24, cy - 10, cx + 30, cy - 10, INK, 1.6)
    cv.line(cx + 24, cy - 16, cx + 30, cy - 16, INK, 1.6)


def icon_tanker(cv, cx, cy):
    cv.rect(cx - 33, cy + 3, 66, 10, (60, 54, 48))
    cv.rect(cx - 12, cy - 3, 20, 6, (60, 54, 48))
    flame(cv, cx + 12, cy + 3, 13, 21)
    cv.circle(cx - 26, cy + 8, 2.6, DARKRED)


def icon_dome(cv, cx, cy):
    cv.ellipse(cx, cy + 3, 20, 12.5, BLUE)
    cv.line(cx, cy - 9, cx, cy - 15, BLUE, 2.6)
    cv.circle(cx, cy - 16, 2.4, BLUE)
    cv.rect(cx - 27, cy + 7, 54, 5, (226, 224, 216))
    cv.rect(cx - 31, cy + 12, 62, 3.5, (206, 204, 196))


def icon_factory(cv, cx, cy):
    cv.rect(cx - 28, cy - 2, 44, 15, (150, 144, 134))
    cv.rect(cx + 21, cy - 15, 8, 28, (128, 122, 112))
    flame(cv, cx - 20, cy - 2, 12, 17)
    smoke(cv, cx + 25, cy - 20, 7)


def icon_seismo(cv, cx, cy):
    cv.line(cx - 34, cy + 12, cx + 34, cy + 12, INK, 1.8)
    cv.polyline([(cx - 32, cy + 4), (cx - 11, cy + 4), (cx - 5, cy - 11),
                 (cx + 2, cy + 12), (cx + 9, cy - 5), (cx + 15, cy + 4),
                 (cx + 32, cy + 4)], RED, 3.2)


def icon_ball(cv, cx, cy):
    cv.circle(cx, cy, 13.5, WHITE)
    for i in range(29):
        a0 = i * 2 * math.pi / 28
        a1 = (i + 1) * 2 * math.pi / 28
        cv.line(cx + 13.5 * math.cos(a0), cy + 13.5 * math.sin(a0),
                cx + 13.5 * math.cos(a1), cy + 13.5 * math.sin(a1), INK, 1.7)
    pent = [(cx + 5.5 * math.cos(-math.pi / 2 + i * 2 * math.pi / 5),
             cy + 5.5 * math.sin(-math.pi / 2 + i * 2 * math.pi / 5))
            for i in range(5)]
    cv.poly(pent, INK)


def icon_ribbon(cv, cx, cy):
    cv.ellipse(cx, cy - 5, 6.5, 9, PINK)
    cv.ellipse(cx, cy - 5, 3, 4.8, CARD)
    cv.poly([(cx - 5, cy + 1), (cx + 2, cy + 1), (cx + 9, cy + 16),
             (cx + 1, cy + 16)], PINK)
    cv.poly([(cx + 5, cy + 1), (cx - 2, cy + 1), (cx - 9, cy + 16),
             (cx - 1, cy + 16)], (190, 62, 116))


def icon_plane(cv, cx, cy):
    cv.line(cx - 30, cy + 7, cx + 25, cy - 7, (70, 70, 70), 5.2)
    cv.poly([(cx - 2, cy - 1), (cx - 17, cy + 11), (cx - 7, cy + 11),
             (cx + 7, cy + 1)], (70, 70, 70))
    cv.poly([(cx - 26, cy + 5), (cx - 33, cy - 4), (cx - 27, cy - 4),
             (cx - 20, cy + 3)], (70, 70, 70))
    for dx in (-16, 0, 16):
        cv.circle(cx + dx, cy + 14, 2.6, ORANGE)


def icon_volcano(cv, cx, cy):
    cv.poly([(cx - 31, cy + 14), (cx - 10, cy - 12), (cx + 10, cy - 12),
             (cx + 31, cy + 14)], (122, 110, 98))
    flame(cv, cx - 5, cy - 11, 10, 13)
    smoke(cv, cx + 4, cy - 19, 7.5)


def icon_bank(cv, cx, cy):
    cv.poly([(cx - 29, cy - 8), (cx + 29, cy - 8), (cx, cy - 19)], BLUE)
    for i in range(3):
        cv.rect(cx - 23 + i * 19, cy - 4, 7.5, 16, (198, 200, 206))
    cv.rect(cx - 29, cy + 12, 58, 4, BLUE)


def icon_flags(cv, cx, cy):
    cv.polyline([(cx - 33, cy + 14), (cx - 13, cy - 3), (cx + 1, cy + 8),
                 (cx + 15, cy - 5), (cx + 33, cy + 14)], GREY, 3)
    cv.line(cx - 15, cy - 15, cx - 15, cy + 1, INK, 2.2)
    cv.poly([(cx - 15, cy - 15), (cx - 4, cy - 11.5), (cx - 15, cy - 8)],
            RED)
    cv.line(cx + 17, cy - 16, cx + 17, cy + 0, INK, 2.2)
    cv.poly([(cx + 17, cy - 16), (cx + 28, cy - 12.5), (cx + 17, cy - 9)],
            BLUE)


def icon_baseball(cv, cx, cy):
    cv.circle(cx, cy, 13.5, WHITE)
    for i in range(29):
        a0 = i * 2 * math.pi / 28
        a1 = (i + 1) * 2 * math.pi / 28
        cv.line(cx + 13.5 * math.cos(a0), cy + 13.5 * math.sin(a0),
                cx + 13.5 * math.cos(a1), cy + 13.5 * math.sin(a1), INK, 1.7)
    cv.polyline([(cx - 8, cy - 9), (cx - 3.5, cy), (cx - 8, cy + 9)],
                RED, 1.9)
    cv.polyline([(cx + 8, cy - 9), (cx + 3.5, cy), (cx + 8, cy + 9)],
                RED, 1.9)


def medium(cv, x, y, w, h, num, btext, bcol, icon, headline, sub):
    cv.rect(x, y, w, h, CARD)
    cv.frame(x, y, w, h, INK, 1.3)
    num_chip(cv, x + 16, y + 16, num, 9.5)
    badge(cv, x + w - 7, y + 7, btext, bcol, 8.5)
    icon(cv, x + w / 2, y + 24)
    hy = y + 42
    for ln in wrap_text(headline, 14, w - 16):
        draw_text(cv, x + 8, hy, ln, 14, INK, bold=True)
        hy += 17
    draw_block(cv, x + 8, y + 79, sub, 9.8, SUBCOL, w - 16,
               leading=1.18)


MEDIUMS = [
    (4, 'CONFIRMED', CONFIRMED, icon_ship, 'RUSSIAN CORVETTE SUNK',
     'BENGHAZI, LIBYA \u00b7 SEA-DRONE HIT \u00b7 THE HINDU'),
    (5, 'CONFIRMED', CONFIRMED, icon_tanker, '2 TANKERS ABLAZE AT HORMUZ',
     'STRAIT OF HORMUZ \u00b7 TRUMP WARNS IRAN \u00b7 FEEDCAST'),
    (6, 'CONFIRMED', CONFIRMED, icon_dome, "DEMOCRATS' BIGGEST HOUSE WIN",
     'WASHINGTON \u00b7 258 SEATS, BEST SINCE 1992 \u00b7 BBC'),
    (7, 'REPORTED', REPORTED, icon_factory, 'FACTORY FIRE: DOZENS MISSING',
     'BANTEN, INDONESIA \u00b7 CANDY PLANT \u00b7 ONE TURN'),
    (8, 'OFFICIAL', OFFICIAL, icon_seismo, 'M6.5 QUAKE ROCKS VANUATU',
     'VANUATU \u00b7 598 KM DEEP \u00b7 NO TSUNAMI \u00b7 USGS'),
    (9, 'CONFIRMED', CONFIRMED, icon_ball, 'LIVERPOOL ROUT TEN-MAN UNITED',
     "ANFIELD \u00b7 POCHETTINO DEBUT SPOILED \u00b7 HINDU"),
    (10, 'OFFICIAL', OFFICIAL, icon_ribbon, 'AI TO SPOT CANCER EARLIER',
     "LONDON \u00b7 NHS WORLD'S LARGEST TRIAL \u00b7 BBC"),
    (11, 'CONFIRMED', CONFIRMED, icon_plane, 'PROTESTS AT SEATTLE AIRPORT',
     'SEA-TAC \u00b7 ICE HELD FATHER, DAUGHTER \u00b7 HINDU'),
    (12, 'REPORTED', REPORTED, icon_volcano, 'MAYON ERUPTION FEARS GROW',
     'PHILIPPINES \u00b7 BIGGER EVENT FEARED \u00b7 MUNICH EYE'),
    (13, 'REPORTED', REPORTED, icon_bank, 'LAGARDE TO LEAVE THE ECB',
     'FRANKFURT \u00b7 STEPS DOWN FEB 2027 \u00b7 MUNICH EYE'),
    (14, 'CONFIRMED', CONFIRMED, icon_flags,
     'INDIA, CHINA TALK BORDER CALM',
     'ARUNACHAL \u00b7 10 DAYS OF LAC TALKS \u00b7 THE HINDU'),
    (15, 'REPORTED', REPORTED, icon_baseball, 'METS SIGN SKUBAL FOR $450M',
     'NEW YORK \u00b7 9-YEAR RECORD DEAL \u00b7 FEEDCAST'),
]


# ---------------------------------------------------------------- map

def world_map(cv, x, y, w, h):
    cv.rect(x, y, w, h, (203, 226, 240))
    cv.frame(x, y, w, h, INK, 1.2)
    land = (110, 172, 104)
    arid = (172, 188, 118)

    def P(lon, lat):
        """Project lon/lat exactly like the pins below."""
        return (x + (lon + 170) / 360.0 * w, y + (78 - lat) / 140.0 * h)

    def mass(pts, col):
        cv.poly([P(lo, la) for lo, la in pts], col)

    # North America: Alaska, Hudson notch, Florida, Mexico taper
    mass([(-168, 66), (-155, 71), (-138, 70), (-122, 70), (-108, 68),
          (-95, 67), (-87, 63), (-81, 59), (-86, 53), (-92, 50),
          (-94, 46), (-89, 43), (-84, 42), (-79, 40), (-74, 40),
          (-70, 42), (-65, 44), (-60, 46), (-64, 43), (-69, 39),
          (-74, 36), (-76, 33), (-79, 32), (-80, 30), (-81, 26),
          (-83, 28), (-86, 30), (-90, 29), (-94, 29), (-97, 26),
          (-97, 21), (-94, 18), (-90, 15), (-85, 12), (-83, 9),
          (-87, 13), (-92, 15), (-97, 16), (-102, 19), (-105, 23),
          (-108, 27), (-111, 30), (-114, 32), (-118, 34), (-122, 38),
          (-124, 44), (-124, 48), (-129, 53), (-135, 58), (-145, 60),
          (-155, 59), (-163, 61)], land)
    # Greenland + Iceland
    mass([(-46, 60), (-42, 63), (-36, 66), (-28, 68), (-21, 70),
          (-19, 74), (-24, 77), (-35, 77.5), (-48, 77), (-54, 72),
          (-54, 66), (-52, 61)], land)
    mass([(-22, 64), (-18, 63), (-14, 64), (-13, 66), (-17, 66),
          (-21, 65)], land)
    # South America: Brazil bulge tapering to Patagonia
    mass([(-79, 9), (-73, 11), (-66, 10), (-60, 8), (-54, 6),
          (-50, 1), (-44, -3), (-38, -6), (-37, -11), (-39, -15),
          (-40, -21), (-45, -24), (-49, -29), (-52, -33), (-56, -36),
          (-59, -39), (-62, -41), (-65, -44), (-66, -48), (-68, -52),
          (-70, -54), (-72, -52), (-73, -47), (-73, -41), (-73, -35),
          (-71, -29), (-70, -22), (-72, -18), (-76, -15), (-79, -9),
          (-80, -5), (-81, 0), (-80, 4)], land)
    # Europe: Iberia, Scandinavia, Greece; UK, Ireland, Italy apart
    mass([(-9, 37), (-10, 40), (-9, 43), (-3, 44), (-1, 46),
          (-5, 48), (-1, 50), (2, 51), (5, 53), (8, 55), (8, 57),
          (12, 56), (18, 56), (20, 59), (23, 59), (27, 61), (30, 63),
          (25, 65), (18, 64), (14, 67), (18, 69), (25, 71), (33, 70),
          (41, 67), (45, 64), (42, 60), (40, 55), (39, 51), (41, 47),
          (36, 46), (32, 46), (28, 45), (29, 42), (26, 41), (23, 40),
          (23, 37), (21, 38), (19, 40), (15, 40), (12, 42), (10, 44),
          (7, 44), (3, 43), (3, 41), (0, 39), (-2, 37)], land)
    mass([(-5, 50), (-2, 50), (0, 51), (1, 52), (0, 54), (-1, 56),
          (-2, 58), (-4, 58), (-5, 56), (-3, 54), (-5, 52)], land)
    mass([(-10, 52), (-8, 51), (-6, 52), (-6, 54), (-7, 55),
          (-9, 54), (-10, 53)], land)
    mass([(8, 44), (11, 44), (13, 43), (14, 42), (16, 41), (18, 40),
          (17, 39), (16, 38), (15, 39), (14, 40), (12, 42), (10, 43)],
         land)
    # Africa: Sahara shoulder, Horn, Madagascar
    mass([(-6, 35), (-2, 35), (3, 37), (9, 37), (11, 34), (15, 32),
          (20, 32), (25, 32), (30, 31), (33, 30), (35, 28), (37, 24),
          (38, 21), (39, 17), (41, 14), (43, 12), (46, 11), (50, 12),
          (51, 10), (48, 5), (44, 0), (41, -4), (40, -9), (39, -14),
          (38, -19), (36, -23), (34, -27), (31, -30), (27, -33),
          (22, -34), (18, -34), (17, -31), (15, -27), (14, -22),
          (12, -17), (13, -12), (12, -7), (10, -2), (9, 2), (7, 4),
          (3, 6), (-2, 5), (-7, 4), (-11, 6), (-14, 8), (-16, 11),
          (-17, 15), (-16, 19), (-16, 23), (-15, 27), (-12, 29),
          (-9, 31), (-6, 34)], arid)
    mass([(44, -13), (47, -14), (49, -17), (50, -20), (48, -23),
          (46, -25), (44, -24), (43, -20), (43, -16)], arid)
    # Asia: Siberia, Arabia, India triangle, Malay spur, Pacific rim
    mass([(30, 36), (33, 36), (36, 36), (36, 33), (34, 30), (34, 28),
          (38, 22), (40, 15), (43, 12), (45, 12), (49, 14), (52, 15),
          (55, 17), (58, 19), (59, 22), (57, 24), (56, 26), (51, 27),
          (49, 30), (53, 29), (57, 27), (61, 25), (66, 25), (68, 23),
          (72, 21), (73, 17), (75, 12), (77, 8), (80, 10), (80, 14),
          (83, 18), (86, 20), (89, 22), (91, 22), (92, 19), (94, 17),
          (95, 16), (97, 14), (98, 9), (99, 5), (100, 2), (101, 4),
          (101, 8), (103, 10), (105, 9), (107, 11), (109, 13),
          (108, 16), (107, 18), (107, 20), (108, 21), (110, 21),
          (113, 22), (116, 23), (118, 25), (120, 27), (121, 30),
          (120, 33), (122, 35), (122, 37), (119, 38), (118, 39),
          (121, 40), (124, 40), (126, 41), (128, 42), (130, 42),
          (132, 43), (135, 45), (138, 46), (140, 48), (141, 51),
          (142, 54), (142, 58), (148, 60), (153, 59), (157, 61),
          (162, 62), (166, 64), (170, 66), (176, 65), (178, 67),
          (178, 70), (172, 70), (165, 70), (158, 71), (150, 72),
          (142, 72), (135, 72), (128, 72), (122, 73), (115, 73),
          (110, 74), (105, 77), (98, 76), (92, 75), (85, 73),
          (78, 72), (71, 72), (65, 70), (58, 69), (51, 68), (45, 67),
          (40, 64), (38, 58), (39, 52), (42, 47), (47, 44), (44, 42),
          (40, 41), (36, 41), (33, 42), (31, 41), (29, 38), (27, 37)],
         land)
    # Japan, the Philippines, Indonesia chain, New Guinea
    mass([(130, 31), (132, 33), (135, 34), (138, 35), (140, 35),
          (141, 38), (141, 41), (140, 43), (142, 44), (144, 44),
          (143, 42), (141, 40), (140, 37), (139, 35), (136, 33),
          (133, 32), (131, 31)], land)
    mass([(119, 18), (121, 18), (122, 16), (122, 14), (121, 13),
          (120, 14), (119, 16)], land)
    mass([(122, 12), (124, 11), (125, 12), (123, 13), (122, 13)],
         land)
    mass([(122, 9), (124, 8), (126, 7), (126, 9), (124, 10),
          (122, 10)], land)
    mass([(95, 5), (100, 0), (104, -3), (106, -6), (103, -4),
          (99, 1), (95, 4)], land)
    mass([(105, -6), (108, -6), (111, -7), (114, -7), (114, -9),
          (110, -8), (106, -7)], land)
    mass([(109, 1), (113, 4), (117, 3), (119, 0), (117, -3),
          (112, -3), (109, -1)], land)
    mass([(119, 0), (121, 1), (123, 0), (120, -2), (119, -1)], land)
    mass([(131, -1), (136, -2), (141, -3), (146, -6), (150, -9),
          (147, -9), (141, -8), (136, -4), (132, -3)], land)
    # Australia + New Zealand + Vanuatu dots
    mass([(113, -22), (113, -26), (114, -30), (115, -33), (117, -35),
          (121, -34), (126, -32), (130, -32), (133, -32), (135, -34),
          (137, -35), (139, -36), (141, -38), (144, -38), (147, -38),
          (149, -37), (150, -36), (152, -33), (153, -29), (153, -25),
          (151, -22), (149, -19), (147, -18), (144, -14), (142, -11),
          (141, -14), (141, -17), (139, -18), (136, -16), (135, -13),
          (134, -11), (132, -11), (130, -13), (128, -15), (125, -15),
          (122, -17), (119, -19), (116, -20), (113, -21)], arid)
    mass([(167, -45), (170, -44), (172, -42), (174, -39), (176, -38),
          (174, -37), (172, -40), (169, -43), (167, -44)], land)
    vx, vy = P(166, -15)
    cv.circle(vx, vy, 2.2, land)
    vx, vy = P(169, -17.5)
    cv.circle(vx, vy, 1.8, land)

    def pin(lon, lat, n, dx=0, dy=0):
        px = x + (lon + 170) / 360.0 * w + dx
        py = y + (78 - lat) / 140.0 * h + dy
        cv.circle(px, py, 8, RED)
        draw_text(cv, px, py - 4.1, str(n), 8.2, WHITE, bold=True,
                  align='center')

    pin(30.7, 36.9, 1, 6, 13)        # Antalya
    pin(139.7, 35.7, 2)             # Tokyo markets
    pin(30.3, 50.9, 3, 14, -7)      # Dymer
    pin(20.0, 32.1, 4, -4, 9)       # Benghazi
    pin(56.3, 26.6, 5)              # Hormuz
    pin(-77.0, 38.9, 6, -8, 5)      # Washington
    pin(106.6, -6.1, 7)             # Banten
    pin(167.0, -16.0, 8)            # Vanuatu
    pin(-3.0, 53.4, 9, -14, -5)     # Liverpool
    pin(-0.1, 51.5, 10, 2, 10)      # London
    pin(-122.3, 47.4, 11)           # Seattle
    pin(123.7, 13.3, 12)            # Mayon
    pin(8.7, 50.1, 13, 12, -2)      # Frankfurt
    pin(92.0, 28.2, 14)             # Arunachal
    pin(-74.0, 40.7, 15, 7, -4)     # New York


# ---------------------------------------------------------------- page

ALSO = [
    (16, 'FRANCE: STUDENT PROTESTS'),
    (17, 'EU-CANADA AI PACT GROWS'),
    (18, 'GERMAN JOBLESS EDGES DOWN'),
    (19, 'AUDI PROFIT FALLS ON CHINA'),
    (20, 'NEPAL PM MEETS MODI'),
    (21, 'INDIA EYE TEST WIN VS NZ'),
    (22, 'FIDE: SINDAROV HAS WHITE'),
    (23, 'CO-OP LIVE ARENA EVACUATED'),
    (24, 'ANTHROPIC DIPS AFTER IPO'),
    (25, 'LARKIN TRADED TO MONTREAL'),
    (26, 'PAOLO BULGARI DIES AT 89'),
    (27, "UK TO HOST 2035 WOMEN'S WC"),
    (28, 'TRUMP URGES HUANG RETURN'),
    (29, 'AID REACHES OLESHKY'),
    (30, 'MYANMAR BALKS AT ASEAN'),
    (31, 'US FLAGS CHINA NUKE GROWTH'),
    (32, 'BISLERI FACES PROSECUTION'),
    (33, 'KASSEL FIRE: ARSON PROBE'),
    (34, 'JEE MAIN 2027 DEADLINE DAY'),
    (35, 'UK ENERGY BILLS TO SOAR'),
]


def build_page():
    cv = Canvas()
    cv.fill_all(PAPER)
    cv.frame(10, 10, W - 20, H - 20, INK, 3.2)
    cv.frame(19, 19, W - 38, H - 38, INK, 1.1)

    # ---- masthead: the date is the headline
    draw_text(cv, W / 2, 27, 'THE MONDAY GLOBE', 27, INK, bold=True,
              align='center')
    draw_text(cv, W / 2, 60, 'MONDAY 23 NOVEMBER 2026', 46, INK,
              bold=True, align='center')
    cv.rect(28, 112, W - 56, 1.8, RED)
    draw_text(cv, W / 2, 118,
              '35 STORIES \u00b7 7 REGIONS \u00b7 15 DRAWN \u00b7 EVERY '
              'ONE DATED MONDAY 23 NOVEMBER 2026',
              12.5, RED, bold=True, align='center')
    cv.rect(28, 136, W - 56, 1.8, RED)

    # ---- big numbers strip
    by = 144
    cv.rect(28, by, W - 56, 44, (244, 238, 224))
    cv.frame(28, by, W - 56, 44, INK, 1.2)
    stats = [('-5.06%', 'NIKKEI ROUT', CHART_RED),
             ('M6.5', 'VANUATU QUAKE', INK),
             ('258', 'US HOUSE SEATS', INK),
             ('$450M', 'SKUBAL TO METS', INK),
             ('10', 'DEAD IN DYMER', INK),
             ('0', 'COP31 DEALS', RED)]
    cw = (W - 56) / 6.0
    for i, (val, lab, col) in enumerate(stats):
        cx = 28 + cw * (i + 0.5)
        if i:
            cv.rect(28 + cw * i, by + 6, 1.1, 32, LGREY)
        draw_text(cv, cx, by + 5, val, 20, col, bold=True, align='center')
        draw_text(cv, cx, by + 29, lab, 8.8, FAINT, align='center')

    # ---- three large leads
    ly0, lh = 196, 232
    lead(cv, 28, ly0, 317, lh, 1, 'ANTALYA, T\u00dcRKIYE',
         'CONFIRMED', CONFIRMED, lead_cop31,
         'COP31 TALKS COLLAPSE: NO DEAL',
         'EU AND 130 NATIONS REJECT A FINAL TEXT WITH NO FOSSIL-FUEL '
         'PHASE-OUT \u00b7 BBC, THE HINDU')
    lead(cv, 354, ly0, 317, lh, 2, 'TOKYO \u00b7 MARKETS',
         'CONFIRMED', CONFIRMED, lead_markets,
         'AI SELL-OFF SLAMS ASIA',
         'NIKKEI -5.06% AND KOSPI -5% AS AI STOCKS SELL OFF; US '
         'FUTURES REBOUND +3% \u00b7 FORTUNE')
    lead(cv, 679, ly0, 317, lh, 3, 'DYMER, UKRAINE \u00b7 WAR',
         'CONFIRMED', CONFIRMED, lead_dymer,
         'STRIKE KILLS 10 IN DYMER',
         'APARTMENT BLOCK HIT NORTH OF KYIV; A BOY OF 7 IS PULLED '
         'ALIVE FROM THE RUBBLE \u00b7 BBC')

    # ---- twelve medium stories, 3 rows x 4
    mw, mh, gx = 236, 103, [28, 272, 516, 760]
    for i, (num, bt, bc, icon, head, sub) in enumerate(MEDIUMS):
        medium(cv, gx[i % 4], 436 + (i // 4) * 111, mw, mh, num, bt, bc,
               icon, head, sub)

    # ---- date check
    dy = 769
    cv.rect(28, dy, W - 56, 56, (250, 241, 228))
    cv.frame(28, dy, W - 56, 56, RED, 1.6)
    cv.rect(40, dy + 8, 104, 17, RED)
    draw_text(cv, 48, dy + 11.5, 'DATE CHECK', 11, WHITE, bold=True)
    draw_text(cv, 156, dy + 9.5,
              'EVERY STORY ABOVE BROKE OR PEAKED ON MONDAY 23 NOVEMBER '
              '2026.', 11, INK, bold=True)
    draw_block(cv, 40, dy + 29,
               'LEFT OUT (OTHER DAYS): THE 186-DRONE KYIV NIGHT AND '
               'THE COP31 FINAL-TEXT FIGHT \u2014 SUNDAY 22 NOV \u00b7 '
               'EL CHAPO ISIDRO CAPTURE \u2014 REPORTED 21 NOV \u00b7 '
               'NOT YET: THE FED\u2019S DECEMBER RATE CALL',
               10.3, SUBCOL, W - 96, leading=1.25)

    # ---- bottom band: map + also-on-Monday
    ty = 833
    draw_text(cv, 28, ty, 'WHERE IT HAPPENED', 12.5, INK, bold=True)
    world_map(cv, 28, ty + 18, 442, 72)
    draw_text(cv, 28, ty + 96,
              'EUROPE 13 \u00b7 ASIA 9 \u00b7 AMERICAS 8 \u00b7 MIDDLE '
              'EAST 2', 9.8, SUBCOL)
    draw_text(cv, 28, ty + 110,
              'AFRICA 1 \u00b7 OCEANIA 1 \u00b7 GLOBAL 1 \u00b7 PINS '
              '1-15 = DRAWN STORIES', 9.8, SUBCOL)
    draw_text(cv, 482, ty, 'ALSO ON MONDAY', 12.5, INK, bold=True)
    draw_text(cv, 482 + text_width('ALSO ON MONDAY', 12.5) + 10, ty + 1.5,
              '\u2014 THE REST OF THE DAY, ONE LINE EACH', 10, FAINT)
    for j, (n, txt) in enumerate(ALSO):
        colx = 482 if j < 10 else 740
        rowy = ty + 20 + (j % 10) * 10.8
        draw_text(cv, colx, rowy, str(n), 9.8, RED, bold=True)
        draw_text(cv, colx + 24, rowy, txt, 9.8, INK)

    # ---- footer
    cv.rect(28, 963, W - 56, 1.6, INK)
    draw_text(cv, W / 2, 969,
              'SOURCES: BBC \u00b7 THE HINDU \u00b7 FEEDCAST \u00b7 '
              'ONE TURN \u00b7 MUNICH EYE \u00b7 USGS',
              10, INK, bold=True, align='center')
    draw_text(cv, W / 2, 984,
              'CONFIRMED = 2+ OUTLETS \u00b7 OFFICIAL = ON THE RECORD '
              '\u00b7 REPORTED = ONE OUTLET \u00b7 ORIGINAL DRAWINGS, '
              'DRAWN IN CODE', 9.8, FAINT, align='center')
    return cv


def main():
    cv = build_page()
    final = cv.downsample()
    outdir = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    try:
        os.makedirs(outdir, exist_ok=True)
        write_png(os.path.join(outdir, 'entry.png'), W, H, final)
    except OSError:
        pass
    n = write_png(os.path.join(os.getcwd(), 'entry.png'), W, H, final)
    print('entry.png written:', n, 'bytes')


if __name__ == '__main__':
    main()
