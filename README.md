# open-camera-testdata

Reusable, openly licensed test images for the Open Camera project: film looks / LUTs and color match,
multi-frame HDR / Night / Astro / Super-Res, Pro / RAW, portrait bokeh and segmentation, scene detection,
aesthetic scoring, denoise, retouch (skin, blemish/object removal, red-eye, teeth, white balance,
perspective / horizon / lens distortion), moon mode, panorama, document scanning and video.

Real photos are **not committed**. `manifest.json` lists each one with source, author, exact license
and sha256; `tools/fetch.py` downloads them into `data/`. Synthetic assets (authored here, CC0) are
committed under `synthetic/`.

## Quick start

```sh
pip install requests pillow numpy
python tools/fetch.py                        # all assets -> data/<category>/, sha256 verified
python tools/fetch.py --category moon,food   # subset
python tools/fetch.py --verify-only          # check local copies
python tools/gen_synthetic.py                # regenerate synthetic/ (deterministic seeds)
python tools/push_to_device.py -s <serial> --per-category 3 --synthetic --raw 2 --video 1
```

`push_to_device.py` copies to `/sdcard/Pictures/OpenCameraTest/<category>/` and triggers a MediaStore
scan. `tools/build_manifest.py` re-curates the manifest from the source APIs (Wikimedia Commons,
NASA Image Library, Met Museum Open Access, raw.pixls.us); `tools/gen_attribution.py` regenerates
`ATTRIBUTION.md`.

## Categories

| Category | Tests |
|---|---|
| portrait | face detection, skin tones, bokeh/segmentation, skin smoothing, red-eye, teeth |
| group | multi-face detection, group portrait |
| landscape-sky | sky segmentation/replacement, horizon, aesthetic scoring |
| night-city | Night mode, HDR, night scene detection |
| lowlight-indoor | low-light, denoise |
| astro | star field / Milky Way, Astro mode |
| moon | Moon mode, super-resolution (NASA PD + Commons) |
| food | food scene detection, aesthetics |
| plant-macro | plant scene detection, macro, bokeh |
| document | document scan, OCR, perspective |
| architecture | perspective/keystone, lens distortion, straight lines |
| backlit-hdr | backlit/high dynamic range, silhouettes |
| mixed-lighting | white balance, auto-enhance |
| skin-closeup | skin retouch, blemish removal |
| inpainting | object/people removal |
| motion-sports | motion, action, burst |
| panorama | wide panoramas (real); overlapping frame sequences are synthetic |
| style-reference | color match / LUT / film-look references (Commons PD photos, Met CC0 paintings) |
| raw-dng | Pro/RAW pipeline: phone and camera DNGs from raw.pixls.us (CC0) |
| video | video, timelapse, thumbnails (Commons CC0/PD/CC BY) |

### Synthetic (`synthetic/`, CC0, see `synthetic/index.json`)

| Folder | Content |
|---|---|
| color | ColorChecker-style 24 patches (+ WB casts), gray ramps / step wedge, Monk 10 skin-tone patches |
| geometry | checkerboard, Siemens star + slanted edge, line grid (straight, barrel, pincushion, tilted 2/5 deg, keystone) |
| noise | clean reference + Poisson-Gaussian noise ladder ISO 100..12800 |
| burst | 8 noisy frames with known sub-pixel shifts (`shifts.json`) + moving object, clean reference |
| hdr | -2/0/+2 EV brackets, float16 ground-truth radiance (`.npy`), tonemapped reference |
| moon | synthetic moon disc: sharp, blurred, small, noisy/underexposed |
| document | page photographed with perspective + uneven light, corner ground truth, flat original |
| panorama | 3 overlapping frames (~30%) + ground-truth strip |

## License policy

Accepted: **CC0**, **public domain** (incl. US federal government / NASA works), **CC BY** (2.0-4.0,
attribution recorded). Rejected: CC BY-SA, NC, ND, GFDL, Unsplash/Pexels licenses, research-only
datasets (MIT-Adobe FiveK, DIV2K, FFHQ, USC-SIPI, Kodak). The license gate is enforced in
`tools/build_manifest.py` from each file's source metadata (Commons `extmetadata.License`, raw.pixls.us
CC0 column, Met `isPublicDomain`, NASA media guidelines).

Caveats: public domain covers copyright only. Portraits of identifiable people may carry personality
rights; NASA images may not be used to imply endorsement. Use these assets for testing, not advertising.
Commons files wider than 3000 px are fetched as Commons-generated thumbnails (noted per entry).

Attribution for CC BY items: see [ATTRIBUTION.md](ATTRIBUTION.md). Repository license: [LICENSE](LICENSE)
(MIT for scripts, CC0 for synthetic assets and metadata).
