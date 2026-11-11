"""Push a subset of the corpus to an Android device and trigger a media scan.

usage: python tools/push_to_device.py -s <serial> [--categories portrait,food] [--per-category N]
                                      [--synthetic] [--raw N] [--video N] [--dry-run]
"""
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = "/sdcard/Pictures/OpenCameraTest"


def adb(serial, *args):
    r = subprocess.run(["adb", "-s", serial, *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"adb {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-s", "--serial", required=True)
    ap.add_argument("--categories", help="comma-separated image categories (default: all image categories)")
    ap.add_argument("--per-category", type=int, default=3)
    ap.add_argument("--synthetic", action="store_true", help="also push synthetic/ (png/jpg only)")
    ap.add_argument("--raw", type=int, default=0, help="number of DNGs to push")
    ap.add_argument("--video", type=int, default=0, help="number of videos to push")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    assets = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["assets"]
    cats = set(a.categories.split(",")) if a.categories else None
    picks, count = [], {}
    for e in assets:
        c = e["category"]
        limit = a.raw if c == "raw-dng" else a.video if c == "video" else a.per_category
        if c not in ("raw-dng", "video") and cats and c not in cats:
            continue
        if count.get(c, 0) >= limit:
            continue
        p = ROOT / e["file"]
        if not p.exists():
            print("not fetched, skipping:", e["file"]); continue
        count[c] = count.get(c, 0) + 1
        picks.append((p, f"{DEST}/{c}/{p.name}"))
    if a.synthetic:
        for p in sorted((ROOT / "synthetic").rglob("*")):
            if p.suffix.lower() in (".png", ".jpg"):
                rel = p.relative_to(ROOT / "synthetic").as_posix().replace("/", "_")
                picks.append((p, f"{DEST}/synthetic/{rel}"))
    print(f"{len(picks)} files:", {k: v for k, v in count.items()}, "+ synthetic" if a.synthetic else "")
    if a.dry_run:
        return
    if adb(a.serial, "get-state").strip() != "device":
        sys.exit("device not ready")
    dirs = sorted({d.rsplit("/", 1)[0] for _, d in picks})
    adb(a.serial, "shell", "mkdir", "-p", *dirs)
    for src, dst in picks:
        adb(a.serial, "push", str(src), dst)
    # Android 11+: scan the folder via the media scanner; older builds accept the broadcast
    out = subprocess.run(["adb", "-s", a.serial, "shell", "content", "call", "--uri", "content://media/none",
                          "--method", "scan_volume", "--arg", "external_primary"], capture_output=True, text=True)
    if out.returncode != 0 or "Exception" in out.stdout + out.stderr:
        for _, dst in picks:
            adb(a.serial, "shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{dst}")
    print("pushed", len(picks), "files to", DEST)


if __name__ == "__main__":
    main()
