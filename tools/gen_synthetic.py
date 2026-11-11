"""Generate synthetic test assets into synthetic/ (deterministic: fixed seeds). Outputs are CC0."""
import json, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "synthetic"
W, H = 1600, 1200
INDEX = []


def save(arr_or_img, rel, tags, notes=""):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    img = arr_or_img if isinstance(arr_or_img, Image.Image) else Image.fromarray(arr_or_img)
    if p.suffix == ".png":
        img.save(p, optimize=True)
    else:
        img.save(p, quality=92)
    INDEX.append(dict(file=f"synthetic/{rel}", tags=tags, resolution="%dx%d" % img.size, notes=notes))


def srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def to8(lin):
    return (srgb(lin) * 255 + 0.5).astype(np.uint8)


def font(size):
    for f in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


# ColorChecker Classic 24 patches, sRGB D65 (approximate published values)
CC24 = [(115, 82, 68), (194, 150, 130), (98, 122, 157), (87, 108, 67), (133, 128, 177), (103, 189, 170),
        (214, 126, 44), (80, 91, 166), (193, 90, 99), (94, 60, 108), (157, 188, 64), (224, 163, 46),
        (56, 61, 150), (70, 148, 73), (175, 54, 60), (231, 199, 31), (187, 86, 149), (8, 133, 161),
        (243, 243, 242), (200, 200, 200), (160, 160, 160), (122, 122, 121), (85, 85, 85), (52, 52, 52)]
# Monk Skin Tone scale (10 tones, sRGB hex from the published MST palette)
MST = ["f6ede4", "f3e7db", "f7ead0", "eadaba", "d7bd96", "a07e56", "825c43", "604134", "3a312a", "292420"]


def color_charts():
    img = Image.new("RGB", (W, H), (40, 40, 40)); d = ImageDraw.Draw(img)
    pw, ph, g = 230, 230, 30
    for i, c in enumerate(CC24):
        x, y = 70 + (i % 6) * (pw + g), 90 + (i // 6) * (ph + g)
        d.rectangle([x, y, x + pw, y + ph], fill=c)
    save(img, "color/colorchecker24.png", ["color", "white-balance", "lut", "color-match"],
         "ColorChecker-style 24 patches, approximate sRGB D65 values (row-major).")
    ramp = np.tile(np.linspace(0, 255, W)[None, :, None], (H // 4, 1, 3))
    steps = np.tile((np.floor(np.linspace(0, 21, W, endpoint=False)) * 255 / 20)[None, :, None], (H // 4, 1, 3)).clip(0, 255)
    rgb = np.concatenate([ramp, steps, ramp * [1, 0, 0], ramp * [0, 1, 0]], 0).astype(np.uint8)
    save(rgb, "color/gray-ramps.png", ["tone-curve", "banding", "lut"], "rows: smooth ramp, 21-step wedge, R ramp, G ramp")
    img = Image.new("RGB", (W, H // 2), (128, 128, 128)); d = ImageDraw.Draw(img)
    for i, hx in enumerate(MST):
        x = 20 + i * 157
        d.rectangle([x, 60, x + 140, 540], fill=tuple(int(hx[k:k + 2], 16) for k in (0, 2, 4)))
    save(img, "color/skin-tones-mst10.png", ["skin-tone", "retouch-skin", "white-balance"],
         "Monk Skin Tone 10-step scale patches on 18% gray")
    # same chart under several white-balance casts
    base = np.asarray(Image.open(OUT / "color/colorchecker24.png")).astype(np.float32) / 255
    for name, gain in {"tungsten-2800k": (1.0, 0.78, 0.48), "daylight-5500k": (1, 1, 1), "shade-7500k": (0.82, 0.92, 1.0),
                       "fluorescent-green": (0.9, 1.0, 0.85)}.items():
        save((np.clip(base * gain, 0, 1) * 255).astype(np.uint8), f"color/colorchecker-wb-{name}.png",
             ["white-balance", "auto-wb"], f"channel gains {gain} applied in gamma space")


def grids():
    yy, xx = np.mgrid[0:H, 0:W]
    cb = (((xx // 50) + (yy // 50)) % 2 * 255).astype(np.uint8)
    save(np.dstack([cb] * 3), "geometry/checkerboard-50px.png", ["calibration", "lens-distortion", "sharpness"])
    # Siemens star + slanted edge resolution target
    img = Image.new("L", (W, H), 255); d = ImageDraw.Draw(img)
    cx, cy, r = 450, 600, 380
    for k in range(72):
        if k % 2 == 0:
            a0, a1 = 2 * math.pi * k / 72, 2 * math.pi * (k + 1) / 72
            d.polygon([(cx, cy), (cx + r * math.cos(a0), cy + r * math.sin(a0)), (cx + r * math.cos(a1), cy + r * math.sin(a1))], fill=0)
    edge = Image.new("L", (600, 600), 255); ImageDraw.Draw(edge).rectangle([300, 0, 600, 600], fill=20)
    img.paste(edge.rotate(5, resample=Image.BICUBIC, fillcolor=255), (950, 300))
    save(img.convert("RGB"), "geometry/resolution-siemens-slanted-edge.png", ["sharpness", "super-res", "mtf"],
         "72-spoke Siemens star + 5 degree slanted edge")
    # straight-line grid, then barrel / pincushion distorted versions
    img = Image.new("L", (W, H), 255); d = ImageDraw.Draw(img)
    for x in range(0, W + 1, 80):
        d.line([(x, 0), (x, H)], fill=0, width=3)
    for y in range(0, H + 1, 80):
        d.line([(0, y), (W, y)], fill=0, width=3)
    grid = np.asarray(img, np.float32)
    save(img.convert("RGB"), "geometry/line-grid.png", ["lens-distortion", "perspective", "horizon"], "undistorted ground truth")
    for name, k1 in (("barrel", -0.18), ("pincushion", 0.12)):
        nx, ny = (xx - W / 2) / (W / 2), (yy - H / 2) / (W / 2)
        r2 = nx * nx + ny * ny
        s = 1 + k1 * r2
        sx = np.clip(nx * s * (W / 2) + W / 2, 0, W - 1).astype(int)
        sy = np.clip(ny * s * (W / 2) + H / 2, 0, H - 1).astype(int)
        save(np.dstack([grid[sy, sx].astype(np.uint8)] * 3), f"geometry/line-grid-{name}-k1_{k1}.png", ["lens-distortion"],
             f"radial model x_src = x*(1+k1*r^2), k1={k1}, r normalized by half-width")
    for ang in (2, 5):
        save(img.rotate(ang, resample=Image.BICUBIC, fillcolor=255).convert("RGB"), f"geometry/line-grid-tilt-{ang}deg.png",
             ["horizon", "auto-level"], f"rotated {ang} degrees CCW; correct answer is -{ang}")
    quad = (200, 150, 1450, 60, 1550, 1150, 60, 1000)
    save(img.transform((W, H), Image.QUAD, quad, resample=Image.BICUBIC, fillcolor=255).convert("RGB"),
         "geometry/line-grid-keystone.png", ["perspective", "keystone"], f"PIL QUAD source corners {quad}")


def scene(seed=1, w=W, h=H):
    """Linear-light test scene: gradient sky, sun, colored shapes, text, fine texture."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w] / max(w, h)
    img = np.zeros((h, w, 3), np.float32)
    img[...] = np.dstack([0.25 + 0.3 * yy, 0.35 + 0.25 * yy, 0.6 - 0.2 * yy])
    p = Image.new("RGB", (w, h)); d = ImageDraw.Draw(p)
    for _ in range(40):
        x, y, r = rng.integers(0, w), rng.integers(h // 3, h), rng.integers(20, 120)
        d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(v) for v in rng.integers(30, 255, 3)))
    d.text((60, 60), "OPEN CAMERA TEST 0123456789", fill=(250, 250, 250), font=font(64))
    m = np.asarray(p, np.float32) / 255
    mask = m.sum(2, keepdims=True) > 0
    img = np.where(mask, (m ** 2.2) * 0.8, img)
    img += 0.03 * rng.standard_normal((h, w, 1)).astype(np.float32) * (yy[..., None] > 0.5)
    return np.clip(img, 0, None)


def add_noise(lin, iso, rng):
    """Poisson-Gaussian sensor model on linear signal; gain scales with ISO."""
    full_well = 12000 / (iso / 100)
    e = rng.poisson(np.clip(lin, 0, 1) * full_well).astype(np.float32)
    read = rng.normal(0, 3.0, lin.shape).astype(np.float32)
    return np.clip((e + read) / full_well, 0, 1)


def noise_ladder():
    rng = np.random.default_rng(7)
    clean = scene(3) * 0.5
    save(to8(clean), "noise/clean.png", ["denoise", "ground-truth"])
    for iso in (100, 400, 1600, 3200, 6400, 12800):
        save(to8(add_noise(clean, iso, rng)), f"noise/iso{iso:05d}.png", ["denoise", "night-mode", "noise"],
             f"Poisson-Gaussian: full_well=12000*100/ISO e-, read noise 3 e-; ISO {iso}")


def burst():
    rng = np.random.default_rng(11)
    big = scene(5, W * 2, H * 2)  # render 2x, shift, downsample => sub-pixel shifts
    meta = []
    for i in range(8):
        dx, dy = rng.uniform(-6, 6, 2)
        sx, sy = int(round(dx * 2)), int(round(dy * 2))
        f = np.roll(big, (sy, sx), (0, 1))
        f = f.reshape(H, 2, W, 2, 3).mean((1, 3))
        ox = 200 + i * 120  # moving object (red ball) for ghosting tests
        p = Image.fromarray(to8(f)); ImageDraw.Draw(p).ellipse([ox, 700, ox + 140, 840], fill=(220, 20, 20))
        lin = (np.asarray(p, np.float32) / 255) ** 2.2
        save(to8(add_noise(lin * 0.4, 3200, rng)), f"burst/frame{i:02d}.png", ["burst", "align", "merge", "ghost", "night-mode", "super-res"])
        meta.append(dict(frame=i, shift_px=[sx / 2, sy / 2], moving_object_box=[ox, 700, ox + 140, 840]))
    save(to8(big.reshape(H, 2, W, 2, 3).mean((1, 3)) * 0.4), "burst/reference-clean.png", ["ground-truth"], "frame 0 geometry, no noise, no object")
    (OUT / "burst/shifts.json").write_text(json.dumps(meta, indent=1))


def hdr():
    lin = scene(9)
    yy, xx = np.mgrid[0:H, 0:W]
    sun = np.exp(-(((xx - 1300) ** 2 + (yy - 250) ** 2) / (2 * 60 ** 2)))[..., None] * 40
    window = ((xx > 900) & (xx < 1500) & (yy > 450) & (yy < 800))[..., None] * 6.0
    shadow = (xx < 700)[..., None] * 0.04
    radiance = np.where(xx[..., None] < 700, lin * shadow, lin) + sun + window * lin.mean()
    (OUT / "hdr").mkdir(parents=True, exist_ok=True)
    np.save(OUT / "hdr/ground-truth-radiance.npy", radiance.astype(np.float16))
    INDEX.append(dict(file="synthetic/hdr/ground-truth-radiance.npy", tags=["hdr", "ground-truth"], resolution=f"{W}x{H}",
                      notes="float16 linear radiance, EV0 maps 1.0 to white"))
    rng = np.random.default_rng(13)
    for ev in (-2, 0, 2):
        save(to8(add_noise(radiance * 2.0 ** ev, 200, rng)), f"hdr/bracket-ev{ev:+d}.jpg", ["hdr", "bracket", "merge"],
             f"exposure {ev:+d} EV of ground truth radiance, sRGB, clipped")
    tm = radiance / (1 + radiance)
    save(to8(tm * 1.6), "hdr/reference-reinhard.png", ["hdr", "ground-truth"], "Reinhard global tonemap reference")


def moon():
    s = 1024
    yy, xx = np.mgrid[0:s, 0:s]
    r = np.hypot(xx - s / 2, yy - s / 2)
    rng = np.random.default_rng(17)
    tex = Image.fromarray((rng.random((64, 64)) * 255).astype(np.uint8)).resize((s, s), Image.BICUBIC)
    tex = np.asarray(tex.filter(ImageFilter.GaussianBlur(3)), np.float32) / 255
    disc = (r < 300) * (0.75 + 0.25 * tex) * np.clip(np.sqrt(np.clip(1 - (r / 300) ** 2, 0, 1)) + 0.3, 0, 1)
    for _ in range(60):  # craters
        cx, cy, cr = rng.integers(250, 774, 2).tolist() + [int(rng.integers(5, 30))]
        cmask = np.hypot(xx - cx, yy - cy) < cr
        disc = np.where(cmask & (r < 300), disc * 0.7, disc)
    base = Image.fromarray((np.clip(disc, 0, 1) * 255).astype(np.uint8))
    save(base.convert("RGB"), "moon/moon-sharp.png", ["moon", "moon-mode", "ground-truth"], "radius 300 px on black")
    for b in (2, 5):
        save(base.filter(ImageFilter.GaussianBlur(b)).convert("RGB"), f"moon/moon-blur{b}.png", ["moon", "deblur", "super-res"])
    small = base.resize((s // 4, s // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1))
    save(small.convert("RGB"), "moon/moon-small-blurred.png", ["moon", "super-res"], "4x downscaled + blur, as from a 1x lens")
    noisy = np.clip(np.asarray(base, np.float32) / 255 * 0.3 + rng.normal(0, 0.05, (s, s)), 0, 1)
    save((noisy * 255).astype(np.uint8), "moon/moon-noisy-underexposed.png", ["moon", "denoise", "night-mode"])


def document():
    page = Image.new("RGB", (1240, 1754), (250, 248, 240)); d = ImageDraw.Draw(page)
    d.text((100, 90), "INVOICE #2026-1111", fill=(20, 20, 20), font=font(56))
    rng = np.random.default_rng(23)
    words = "lorem ipsum dolor sit amet camera sensor exposure white balance noise lens".split()
    for i in range(38):
        d.text((100, 230 + i * 36), " ".join(rng.choice(words, 9)), fill=(30, 30, 30), font=font(26))
    d.rectangle([100, 1640, 600, 1700], outline=(0, 0, 0), width=3)
    page.save(OUT / "document/_flat.png") if (OUT / "document").mkdir(parents=True, exist_ok=True) is None else None
    INDEX.append(dict(file="synthetic/document/_flat.png", tags=["document", "ground-truth"], resolution="1240x1754", notes="flat A4 @150dpi"))
    bg = Image.new("RGB", (2000, 1500), (95, 70, 50))
    bgarr = np.asarray(bg, np.float32) + rng.normal(0, 8, (1500, 2000, 3))
    bg = Image.fromarray(np.clip(bgarr, 0, 255).astype(np.uint8))
    corners = [(520, 180), (1530, 260), (1650, 1380), (380, 1300)]  # TL, TR, BR, BL in photo
    coeffs = _persp_coeffs(corners, [(0, 0), (1240, 0), (1240, 1754), (0, 1754)])
    warped = page.transform((2000, 1500), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
    mask = Image.new("L", (1240, 1754), 255).transform((2000, 1500), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
    bg.paste(warped, (0, 0), mask)
    shade = np.linspace(1.0, 0.7, 2000)[None, :, None]
    photo = np.clip(np.asarray(bg, np.float32) * shade, 0, 255).astype(np.uint8)
    save(photo, "document/page-perspective.jpg", ["document", "doc-scan", "perspective", "ocr"],
         f"page corners TL,TR,BR,BL = {corners}; uneven illumination")
    (OUT / "document/page-perspective.corners.json").write_text(json.dumps(corners))


def _persp_coeffs(dst, src):
    A, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        b += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(b, float)).tolist()


def panorama():
    pano = to8(scene(29, 4000, 1000))
    p = Image.fromarray(pano)
    for i, x in enumerate(range(0, 4000 - 1300 + 1, 900)):
        save(p.crop((x, 0, x + 1300, 1000)), f"panorama/frame{i}.jpg", ["panorama", "stitch"], f"crop x={x}..{x + 1300} (~30% overlap)")
    save(p, "panorama/ground-truth.jpg", ["panorama", "ground-truth"])


if __name__ == "__main__":
    for fn in (color_charts, grids, noise_ladder, burst, hdr, moon, document, panorama):
        fn()
    (OUT / "index.json").write_text(json.dumps(INDEX, indent=1))
    print(len(INDEX), "synthetic assets")
