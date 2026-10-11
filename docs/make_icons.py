"""Draw MR.Softie's original icon set into mr_softie/icons/ (dev-only: needs pillow).

    python docs/make_icons.py

Flat glyphs, dark ink with a light halo so they read on both the gray theme and
Blender's dark theme. Drawn at 4x and downsampled for clean edges.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "mr_softie", "icons")
SIZE = 32
S = 4                      # supersampling
W = SIZE * S
INK = (40, 40, 40, 255)
ACCENT = (77, 107, 158, 255)
HALO = (235, 235, 235, 255)


def canvas():
    return Image.new("RGBA", (W, W), (0, 0, 0, 0))


def finish(img, name):
    # Halo: dilate the alpha, paint it light, put the glyph on top.
    alpha = img.split()[3]
    halo_alpha = alpha.filter(ImageFilter.MaxFilter(9))
    halo = Image.new("RGBA", img.size, HALO)
    halo.putalpha(halo_alpha.point(lambda a: int(a * 0.85)))
    out = Image.alpha_composite(halo, img)
    out = out.resize((SIZE, SIZE), Image.LANCZOS)
    out.save(os.path.join(OUT, f"{name}.png"))


def p(x, y):
    return (x * S, y * S)


def line(d, pts, width=2.2, fill=INK):
    d.line([p(*q) for q in pts], fill=fill, width=int(width * S), joint="curve")


def dot(d, x, y, r, fill=INK):
    d.ellipse([p(x - r, y - r), p(x + r, y + r)], fill=fill)


def model():
    img = canvas()
    d = ImageDraw.Draw(img)
    front = [(6, 12), (19, 12), (19, 25), (6, 25)]
    back = [(13, 6), (26, 6), (26, 19), (13, 19)]
    line(d, front + [front[0]])
    line(d, [back[0], back[1], back[2]])
    for a, b in zip(front[:3], back[:3]):
        line(d, [a, b])
    line(d, [back[2], front[2]], fill=ACCENT)
    return img


def animate():
    img = canvas()
    d = ImageDraw.Draw(img)
    pts = [(4 + t, 16 - 9 * math.sin((t / 24) * math.pi * 1.6)) for t in range(0, 25)]
    line(d, pts)
    line(d, [(4, 27), (28, 27)], width=1.6)
    for t in (0, 12, 24):
        x, y = pts[t]
        d.polygon([p(x, y - 3.2), p(x + 3.2, y), p(x, y + 3.2), p(x - 3.2, y)], fill=ACCENT)
    return img


def render():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.ellipse([p(4, 4), p(28, 28)], outline=INK, width=int(2.2 * S))
    cx = cy = 16
    for i in range(6):
        a = math.radians(i * 60)
        b = math.radians(i * 60 + 75)
        line(d, [(cx + 11 * math.cos(a), cy + 11 * math.sin(a)),
                 (cx + 4.5 * math.cos(b), cy + 4.5 * math.sin(b))], width=1.8)
    dot(d, 16, 16, 3, fill=ACCENT)
    return img


def simulate():
    img = canvas()
    d = ImageDraw.Draw(img)
    for x, y, r in ((9, 7, 2.4), (17, 11, 2.8), (24, 6, 2.0), (12, 17, 2.2), (22, 19, 2.6), (16, 25, 3.0)):
        dot(d, x, y, r)
        line(d, [(x, y - r - 1), (x, y - r - 4)], width=1.2)
    line(d, [(4, 29), (28, 29)], width=1.8, fill=ACCENT)
    return img


def ice():
    img = canvas()
    d = ImageDraw.Draw(img)
    line(d, [(10, 10), (22, 16)], width=1.8)
    line(d, [(10, 22), (22, 16)], width=1.8)
    for x, y in ((4, 6), (4, 18)):
        d.rounded_rectangle([p(x, y), p(x + 9, y + 8)], radius=2 * S, fill=INK)
    d.rounded_rectangle([p(19, 12), p(28, 20)], radius=2 * S, fill=ACCENT)
    return img


def select():
    img = canvas()
    d = ImageDraw.Draw(img)
    arrow = [(8, 4), (8, 25), (13, 20), (17, 28), (20, 26.5), (16, 19), (23, 19)]
    d.polygon([p(*q) for q in arrow], fill=INK)
    return img


def explorer():
    img = canvas()
    d = ImageDraw.Draw(img)
    line(d, [(8, 8), (8, 25)], width=1.6)
    for y in (14, 24):
        line(d, [(8, y), (13, y)], width=1.6)
    d.rectangle([p(4, 4), p(12, 10)], fill=INK)
    d.rectangle([p(14, 11), p(28, 17)], fill=INK)
    d.rectangle([p(14, 21), p(28, 27)], fill=ACCENT)
    return img


def schematic():
    img = canvas()
    d = ImageDraw.Draw(img)
    line(d, [(10, 9), (22, 9)], width=1.6)
    line(d, [(10, 9), (16, 23)], width=1.6)
    for (x, y), fill in (((3, 5), INK), ((19, 5), INK), ((10, 20), ACCENT)):
        d.rectangle([p(x, y), p(x + 11, y + 8)], fill=fill)
    return img


def script():
    img = canvas()
    d = ImageDraw.Draw(img)
    line(d, [(11, 7), (5, 16), (11, 25)])
    line(d, [(21, 7), (27, 16), (21, 25)])
    line(d, [(18, 6), (14, 26)], width=2.0, fill=ACCENT)
    return img


def ppg():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([p(6, 3), p(26, 29)], radius=2 * S, outline=INK, width=int(2.0 * S))
    for y in (10, 16, 22):
        line(d, [(10, y), (15, y)], width=1.6)
        d.rectangle([p(17, y - 1.6), p(23, y + 1.6)], fill=ACCENT if y == 10 else INK)
    return img


def layout():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([p(3, 5), p(7, 27)], fill=INK)
    d.rectangle([p(25, 5), p(29, 27)], fill=INK)
    for x, y in ((9, 5), (17, 5), (9, 17), (17, 17)):
        d.rectangle([p(x, y), p(x + 6, y + 10)], outline=INK, width=int(1.6 * S))
    d.rectangle([p(17, 5), p(23, 15)], fill=ACCENT)
    return img


def maximize():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([p(4, 4), p(28, 28)], outline=INK, width=int(2.0 * S))
    line(d, [(10, 22), (22, 10)], width=2.0, fill=ACCENT)
    line(d, [(15, 10), (22, 10), (22, 17)], width=2.0, fill=ACCENT)
    return img


def parent():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([p(11, 3), p(21, 11)], fill=ACCENT)
    line(d, [(16, 11), (16, 17), (8, 17), (8, 21)], width=1.8)
    line(d, [(16, 17), (24, 17), (24, 21)], width=1.8)
    d.rectangle([p(4, 21), p(12, 28)], fill=INK)
    d.rectangle([p(20, 21), p(28, 28)], fill=INK)
    return img


def cut():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([p(11, 3), p(21, 11)], fill=INK)
    line(d, [(16, 11), (16, 14)], width=1.8)
    line(d, [(16, 21), (16, 22)], width=1.8)
    d.rectangle([p(11, 22), p(21, 29)], fill=INK)
    line(d, [(8, 15), (24, 20)], width=2.2, fill=ACCENT)
    line(d, [(8, 20), (24, 15)], width=2.2, fill=ACCENT)
    return img


def freeze():
    img = canvas()
    d = ImageDraw.Draw(img)
    for i in range(3):
        a = math.radians(i * 60 + 90)
        dx, dy = 12 * math.cos(a), 12 * math.sin(a)
        line(d, [(16 - dx, 16 - dy), (16 + dx, 16 + dy)], width=2.0)
        for sgn in (1, -1):
            bx, by = 16 + sgn * dx * 0.6, 16 + sgn * dy * 0.6
            for t in (-0.6, 0.6):
                b = a + t * (1 if sgn > 0 else -1)
                line(d, [(bx, by), (bx + sgn * 4 * math.cos(b), by + sgn * 4 * math.sin(b))], width=1.5)
    dot(d, 16, 16, 3, fill=ACCENT)
    return img


def reset():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.arc([p(5, 5), p(27, 27)], start=-60, end=230, fill=INK, width=int(2.2 * S))
    x, y = 16 + 11 * math.cos(math.radians(-60)), 16 + 11 * math.sin(math.radians(-60))
    d.polygon([p(x + 4, y - 4), p(x + 3, y + 5), p(x - 5, y + 1)], fill=INK)
    dot(d, 16, 16, 3.2, fill=ACCENT)
    return img


ICONS = {"model": model, "animate": animate, "render": render, "simulate": simulate, "ice": ice,
         "select": select, "explorer": explorer, "schematic": schematic, "script": script, "ppg": ppg,
         "layout": layout, "maximize": maximize, "parent": parent, "cut": cut, "freeze": freeze,
         "reset": reset}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, draw in ICONS.items():
        finish(draw(), name)
    # Contact sheet for review (not shipped).
    sheet = Image.new("RGBA", (len(ICONS) * 80, 160), (200, 200, 200, 255))
    dark = Image.new("RGBA", (len(ICONS) * 80, 80), (45, 45, 45, 255))
    sheet.paste(dark, (0, 80))
    for i, name in enumerate(ICONS):
        icon = Image.open(os.path.join(OUT, f"{name}.png")).resize((64, 64), Image.NEAREST)
        for row in (0, 1):
            sheet.alpha_composite(icon, (i * 80 + 8, row * 80 + 8))
    sheet.save(os.path.join(HERE, "_icons_sheet.png"))
    print("wrote", len(ICONS), "icons to", OUT)
