"""Download every manifest asset into data/ and verify sha256.

usage: python tools/fetch.py [--category portrait,moon ...] [--verify-only]
"""
import argparse, hashlib, json, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
H = {"User-Agent": "OpenCameraTestdata/0.1 (https://www.mediawiki.org/wiki/API:Etiquette) python-requests/2"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", help="comma-separated categories (default: all)")
    ap.add_argument("--verify-only", action="store_true")
    a = ap.parse_args()
    cats = set(a.category.split(",")) if a.category else None
    assets = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["assets"]
    bad = 0
    for e in assets:
        if cats and e["category"] not in cats:
            continue
        p = ROOT / e["file"]
        if p.exists() and sha256(p) == e["sha256"]:
            continue
        if a.verify_only:
            print("MISSING/BAD", e["file"]); bad += 1; continue
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".part")
        ok = False
        for attempt in range(4):
            try:
                with requests.get(e["source_url"], headers=H, timeout=180, stream=True) as r:
                    if r.status_code == 429:
                        time.sleep(int(r.headers.get("retry-after", 10)) * (attempt + 1)); continue
                    r.raise_for_status()
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_content(1 << 20):
                            f.write(chunk)
                ok = True; break
            except requests.RequestException as ex:
                print("retry", e["id"], ex); time.sleep(3)
        if not ok:
            print("FAILED", e["id"]); bad += 1; continue
        got = sha256(tmp)
        if got != e["sha256"]:
            print(f"SHA MISMATCH {e['id']}: {got}"); tmp.unlink(); bad += 1; continue
        tmp.replace(p)
        print("ok", e["file"])
    print("errors:", bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
