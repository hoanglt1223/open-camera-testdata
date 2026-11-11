"""Curate manifest.json from license-filtered sources (Wikimedia Commons, raw.pixls.us, NASA, Met Museum).

Re-running rebuilds the manifest from the query list below; EXCLUDE drops items rejected on visual review.
Only CC0, public domain and CC BY (no SA/NC/ND) pass the license gate.
"""
import functools, hashlib, json, re, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
H = {"User-Agent": "OpenCameraTestdata/0.1 (https://github.com/hoanglt1223/open-camera-testdata) python-requests/2"}
API = "https://commons.wikimedia.org/w/api.php"
# Wikidata license statements: CC0, CC BY 4.0, CC BY 2.0, CC BY 3.0, CC BY 2.5; copyright status: public domain
LIC_FILTER = ("haswbstatement:P275=Q6938433|P275=Q20007257|P275=Q19125117|P275=Q14947546|P275=Q18810333"
              "|P6216=Q19652")
MAX_W = 3000  # larger originals are fetched as Commons thumbnails (keeps each image <= ~9 MP)

# category -> (tags, count, [queries])
PLAN = {
    "portrait": (["portrait", "skin-tone", "face-detect", "bokeh", "retouch-skin", "red-eye", "teeth"], 14, [
        "official portrait photograph -painting", "headshot photograph", "portrait photograph glasses",
        "portrait photograph smiling woman", "portrait photograph man beard", "NASA astronaut official portrait",
        "headshot photograph man", "headshot photograph woman", "official portrait 2023 photograph"]),
    "group": (["group", "multi-face", "face-detect"], 5, ["group photo people smiling", "team photograph group"]),
    "landscape-sky": (["landscape", "sky", "sky-replace", "horizon", "scene-sky", "aesthetic"], 10, [
        "landscape mountains sky clouds", "sunset sky clouds landscape", "seascape horizon", "blue sky field"]),
    "night-city": (["night", "night-mode", "hdr", "scene-night"], 6, ["night city skyline", "city street at night"]),
    "lowlight-indoor": (["low-light", "night-mode", "denoise"], 5, ["dim interior room lamp", "candle light dark room",
                                                                    "restaurant interior evening"]),
    "astro": (["astro", "stars", "milky-way", "night-mode"], 6, ["milky way night sky", "star trails night sky",
                                                                 "starry sky landscape night"]),
    "moon": (["moon", "moon-mode", "super-res"], 6, ["full moon photograph NASA", "moon telescope photograph",
                                                    "crescent moon sky"]),
    "food": (["food", "scene-food", "aesthetic"], 7, ["food dish plate meal", "dessert cake", "fruit bowl", "pho noodle soup"]),
    "plant-macro": (["plant", "macro", "scene-plant", "bokeh"], 7, ["flower macro", "leaf macro dew", "insect on flower macro"]),
    "document": (["document", "doc-scan", "text", "ocr", "perspective"], 5, ["whiteboard", "receipt paper",
                                                                            "handwritten letter page photograph",
                                                                            "printed page book photograph"]),
    "architecture": (["architecture", "perspective", "keystone", "lens-distortion", "lines"], 7, [
        "building facade architecture", "skyscraper looking up", "church interior nave", "bridge architecture"]),
    "backlit-hdr": (["backlit", "hdr", "high-dynamic-range", "silhouette"], 6, ["backlit silhouette sunset", "window light interior bright",
                                                                              "sun flare backlit"]),
    "mixed-lighting": (["white-balance", "mixed-lighting", "auto-enhance"], 5, ["neon lights street", "tungsten light interior",
                                                                               "fluorescent light office"]),
    "skin-closeup": (["skin", "retouch-skin", "blemish"], 3, ["freckles face closeup photograph", "face skin pores macro photograph", "acne skin photograph"]),
    "inpainting": (["inpaint", "object-removal", "unwanted-people"], 6, ["tourists in front of monument", "crowded beach people",
                                                                         "power lines sky", "tourist crowd landmark"]),
    "motion-sports": (["motion", "sports", "action", "burst"], 6, ["football match action", "running race athletes",
                                                                   "cyclist race", "basketball game action"]),
    "panorama": (["panorama", "stitch", "wide"], 3, ["panorama landscape wide"]),
    "style-reference": (["color-match", "style", "film-look", "lut"], 8, ["Kodachrome color photograph 1940s",
                                                                        "color slide 1970s photograph", "Kodachrome slide landscape", "1960s color photograph street"]),
}
VIDEO_PLAN = ("video", ["video", "timelapse", "thumbnail", "stabilization"], 3, ["timelapse", "waves beach video", "city traffic"])
ART_RE = re.compile(r"\bMET\b|Google Art Project|Frans Hals|painting|drawing|engraving|lithograph|Museum of Fine Arts|Art Gallery|Dell'Orto|Getty Museum", re.I)
RAW_PICKS = ["Google|Pixel 3a", "Xiaomi|MI 8", "Apple|iPhone XS", "Pentax|", "Leica|", "Ricoh|"]
EXCLUDE = set(json.loads((ROOT / "tools" / "exclude.json").read_text(encoding="utf-8"))) if (ROOT / "tools" / "exclude.json").exists() else set()


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def license_ok(lic):
    lic = (lic or "").lower()
    if any(x in lic for x in ("-sa", "nc", "nd", "gfdl")):
        return False
    return lic in ("cc0", "pd") or lic.startswith("pd") or re.fullmatch(r"cc-by-\d\.\d", lic) is not None


@functools.lru_cache(maxsize=None)
def commons_search(query, media, limit=40):
    ft = "filetype:video filesize:<15000" if media == "video" else "filetype:bitmap filemime:image/jpeg filew:>1500"
    r = requests.get(API, headers=H, timeout=60, params=dict(
        action="query", format="json", generator="search", gsrsearch=f"{query} {LIC_FILTER} {ft}",
        gsrnamespace=6, gsrlimit=limit, prop="imageinfo", iiurlwidth=MAX_W,
        iiprop="url|size|extmetadata|mime", iiextmetadatafilter="License|LicenseShortName|LicenseUrl|Artist|Credit|Restrictions|AttributionRequired"))
    pages = r.json().get("query", {}).get("pages", {})
    return sorted(pages.values(), key=lambda p: p.get("index", 0))


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        for attempt in range(5):
            r = requests.get(url, headers=H, timeout=180)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("retry-after", 10)) * (attempt + 1)); continue
            r.raise_for_status()
            dest.write_bytes(r.content); break
        else:
            raise RuntimeError(f"rate limited: {url}")
        time.sleep(1.0)
    return sha256(dest), dest.stat().st_size


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def add_commons(entries, seen, cat, tags, n, queries, media="image"):
    got = 0
    per_query = -(-n // len(queries))  # spread picks across queries for diversity
    for round_ in range(2):  # second round fills remaining slots without the per-query cap
        for q in queries:
          taken = 0
          for p in commons_search(q, media):
            if got >= n:
                return
            if round_ == 0 and taken >= per_query:
                break
            title = p["title"]
            if title in seen or title in EXCLUDE or "unsplash" in title.lower() or "imageinfo" not in p:
                continue
            if cat != "style-reference" and ART_RE.search(title):
                continue
            ii = p["imageinfo"][0]; m = ii.get("extmetadata", {})
            lic = m.get("License", {}).get("value", "")
            if not license_ok(lic):
                continue
            restr = m.get("Restrictions", {}).get("value", "")
            if cat in ("portrait", "skin-closeup") and "personality" in restr and not lic.startswith("pd"):
                continue  # living-person CC images with personality rights: keep portraits to PD only when flagged
            use_thumb = media == "image" and ii["width"] > MAX_W
            url = ii["thumburl"] if use_thumb else ii["url"]
            w, h = (ii["thumbwidth"], ii["thumbheight"]) if use_thumb else (ii["width"], ii["height"])
            ext = Path(url.split("?")[0]).suffix.lower() or ".jpg"
            fid = f"{cat}-{slug(title[5:].rsplit('.', 1)[0])}"
            rel = f"data/{cat}/{fid}{ext}"
            try:
                digest, size = download(url, ROOT / rel)
            except Exception as e:
                print("skip", title, e); continue
            seen.add(title); got += 1; taken += 1
            entries.append(dict(
                id=fid, category=cat, tags=tags, file=rel,
                source_page=ii["descriptionurl"], source_url=url, original_url=ii["url"],
                author=strip_html(m.get("Artist", {}).get("value")) or "unknown",
                credit=strip_html(m.get("Credit", {}).get("value")),
                license=m.get("LicenseShortName", {}).get("value", lic), license_code=lic,
                license_url=m.get("LicenseUrl", {}).get("value", ""),
                attribution_required=lic.startswith("cc-by"),
                sha256=digest, size=size, resolution=f"{w}x{h}", mime=ii.get("mime"),
                notes=("Commons thumbnail (scaled from %dx%d original). " % (ii["width"], ii["height"]) if use_thumb else "")
                      + (f"Restrictions: {restr}. " if restr else "") + f"query: {q}"))
            print(cat, got, title)
    if got < n:
        print(f"GAP {cat}: {got}/{n}")


def add_raw(entries):
    rows = requests.get("https://raw.pixls.us/json/getrepository.php?set=all", headers=H, timeout=120).json()["data"]
    for pick in RAW_PICKS:
        make, model = pick.split("|")
        for r in rows:
            if r[0] != make or (model and r[1] != model) or "publicdomain/zero" not in r[5]:
                continue
            m = re.search(r"href='(https://raw\.pixls\.us/getfile\.php/(\d+)/nice/[^']+\.dng)'", r[7], re.I)
            mb = re.search(r"\(([\d.]+)MB\)", r[7])
            if not m or not mb or float(mb.group(1)) > 25:
                continue
            want = re.search(r"sha256 Checksum'>([0-9a-f]{64})", r[7]).group(1)
            fid = f"raw-{slug(make + '-' + r[1])}"
            rel = f"data/raw-dng/{fid}.dng"
            url = m.group(1).replace(" ", "%20")
            digest, size = download(url, ROOT / rel)
            assert digest == want, f"sha mismatch {url}"
            entries.append(dict(
                id=fid, category="raw-dng", tags=["raw", "dng", "pro-mode", "phone" if make in ("Google", "Xiaomi", "Apple") else "camera"],
                file=rel, source_page="https://raw.pixls.us/", source_url=url, original_url=url,
                author="raw.pixls.us contributor", credit="raw.pixls.us", license="CC0 1.0", license_code="cc0",
                license_url="https://creativecommons.org/publicdomain/zero/1.0/", attribution_required=False,
                sha256=digest, size=size, resolution=f"{r[3]} MP", mime="image/x-adobe-dng",
                notes=f"{make} {r[1]} {r[2]}; {strip_html(r[4])}".strip("; ")))
            print("raw", fid); break


def add_met(entries, n=4):
    base = "https://collectionapi.metmuseum.org/public/collection/v1"
    ids = requests.get(f"{base.replace('/v1', '/v1.1')}/search", headers=H, timeout=60,
                       params=dict(q="sunset landscape", hasImages="true", isPublicDomain="true", limit=60)).json()["objectIDs"]
    got = 0
    for oid in ids[:60]:
        o = requests.get(f"{base}/objects/{oid}", headers=H, timeout=60).json()
        if not o.get("isPublicDomain") or not o.get("primaryImage"):
            continue
        fid = f"style-reference-met-{oid}"
        rel = f"data/style-reference/{fid}.jpg"
        url = o.get("primaryImageSmall") or o["primaryImage"]
        try:
            digest, size = download(url, ROOT / rel)
        except Exception as e:
            print("skip met", oid, e); continue
        from PIL import Image
        with Image.open(ROOT / rel) as im:
            w, h = im.size
        entries.append(dict(
            id=fid, category="style-reference", tags=["color-match", "style", "painting-palette"], file=rel,
            source_page=o["objectURL"], source_url=url, original_url=url,
            author=o.get("artistDisplayName") or "unknown", credit="The Metropolitan Museum of Art, Open Access",
            license="CC0 1.0 (Met Open Access)", license_code="cc0",
            license_url="https://creativecommons.org/publicdomain/zero/1.0/", attribution_required=False,
            sha256=digest, size=size, resolution=f"{w}x{h}", mime="image/jpeg", notes=o.get("title", "")))
        got += 1
        if got >= n:
            break


def add_nasa(entries, n=3):
    r = requests.get("https://images-api.nasa.gov/search", headers=H, timeout=60,
                     params=dict(q="full moon", media_type="image")).json()
    got = 0
    for it in r["collection"]["items"]:
        d = it["data"][0]
        if d.get("center") not in ("GSFC", "JSC", "MSFC", "HQ", "ARC", "KSC") or "moon" not in d.get("title", "").lower():
            continue
        assets = requests.get(it["href"], headers=H, timeout=60).json()
        url = next((a for a in assets if a.endswith("~large.jpg")), None) or next((a for a in assets if a.endswith("~orig.jpg")), None)
        if not url:
            continue
        url = url.replace("http://", "https://").replace(" ", "%20")
        nid = d["nasa_id"]
        fid = f"moon-nasa-{slug(nid)}"
        rel = f"data/moon/{fid}.jpg"
        try:
            digest, size = download(url, ROOT / rel)
        except Exception as e:
            print("skip nasa", nid, e); continue
        from PIL import Image
        with Image.open(ROOT / rel) as im:
            w, h = im.size
        entries.append(dict(
            id=fid, category="moon", tags=["moon", "moon-mode", "super-res"], file=rel,
            source_page=f"https://images.nasa.gov/details/{nid}", source_url=url, original_url=url,
            author=d.get("photographer") or d.get("secondary_creator") or f"NASA {d.get('center')}",
            credit="NASA", license="Public domain (NASA media usage guidelines)", license_code="pd-nasa",
            license_url="https://www.nasa.gov/nasa-brand-center/images-and-media/", attribution_required=False,
            sha256=digest, size=size, resolution=f"{w}x{h}", mime="image/jpeg",
            notes=f"{d.get('title')}; NASA content is not copyrighted; NASA logo/endorsement restrictions apply."))
        got += 1
        if got >= n:
            break


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    entries, seen = [], set()
    for cat, (tags, n, queries) in PLAN.items():
        add_commons(entries, seen, cat, tags, n, queries)
    add_nasa(entries)
    add_met(entries)
    cat, tags, n, queries = VIDEO_PLAN
    add_commons(entries, seen, cat, tags, n, queries, media="video")
    add_raw(entries)
    (ROOT / "manifest.json").write_text(json.dumps(dict(version=1, assets=entries), indent=1, ensure_ascii=False), encoding="utf-8")
    print("total", len(entries), "bytes", sum(e["size"] for e in entries))


if __name__ == "__main__":
    main()
