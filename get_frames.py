"""Download the NASA SVS / Earth Information Center frames listed in frames.js into frames/.

Usage:  python get_frames.py
Standard library only. Existing files are skipped. Re-run any time.
"""
import os, sys, urllib.request

BASE = "https://svs.gsfc.nasa.gov/vis/a000000/"
FRAMES = {
    "air-quality.png":        BASE + "a005500/a005533/AirQuality_Sphere_1920x1080_0000.png",   # SVS 5533
    "global-temperature.png": BASE + "a005400/a005450/2024GISTEMPMap_2K.png",                  # SVS 5450
    "arctic-sea-ice.jpg":     BASE + "a005300/a005382/sea_ice_2024_still_print.jpg",           # SVS 5382
}

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames")
os.makedirs(out, exist_ok=True)
failed = 0
for name, url in FRAMES.items():
    dest = os.path.join(out, name)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print("have ", name); continue
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EarthJukebox/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            f.write(r.read())
        print("saved", name, os.path.getsize(dest) // 1024, "KB")
    except Exception as e:
        failed += 1
        print("FAILED", name, e, "\n  open", url, "and save it as frames/" + name)
sys.exit(1 if failed else 0)
