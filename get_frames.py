"""Download NASA SVS / Earth Information Center frames into frames/.

Usage:
  python get_frames.py                        # the fixed frames listed below
  python get_frames.py --sequence 0,150,300   # also pick frames from the Air Quality animation
  python get_frames.py --sequence 0-600:150   # same idea: start-end:step  (0,150,300,450,600)

The Air Quality animation (SVS 5533) is a numbered image sequence, one PNG per video frame at
5760x3240 (about 8 MB each), so only download the few frames you want. With Pillow installed
(pip install pillow) each one is shrunk to 1920x1080 and flattened onto white. Existing files
are skipped. Re-run any time.
"""
import argparse, io, os, sys, urllib.request

BASE = "https://svs.gsfc.nasa.gov/vis/a000000/"
SEQ_URL = BASE + "a005500/a005533/frames/5760x3240_16x9_30p/AirQuality_SphereWithLabels/AirQuality_Sphere_5760x3240_{n:04d}.png"
FRAMES = {
    "air-quality.png":        BASE + "a005500/a005533/AirQuality_Sphere_1920x1080_0000.png",   # SVS 5533
    "global-temperature.png": BASE + "a005400/a005450/2024GISTEMPMap_2K.png",                  # SVS 5450
    "arctic-sea-ice.jpg":     BASE + "a005300/a005382/sea_ice_2024_still_print.jpg",           # SVS 5382
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "EarthJukebox/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def shrink(data):
    """Return PNG bytes at 1920x1080 on a white background, or the original bytes if Pillow is missing."""
    try:
        from PIL import Image
    except ImportError:
        print("  (Pillow not installed: keeping full size. pip install pillow to shrink)")
        return data
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    out = io.BytesIO()
    bg.convert("RGB").resize((1920, 1080), Image.LANCZOS).save(out, "PNG", optimize=True)
    return out.getvalue()


def parse_sequence(text):
    """'0,150,300' or '0-600:150' -> [0, 150, 300, ...]"""
    nums = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            span, _, step = part.partition(":")
            a, b = span.split("-")
            nums += list(range(int(a), int(b) + 1, int(step or 1)))
        elif part:
            nums.append(int(part))
    return sorted(set(nums))


def save(name, url, post=None):
    dest = os.path.join(OUT, name)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print("have ", name)
        return True
    try:
        data = fetch(url)
        if post:
            data = post(data)
        with open(dest, "wb") as f:
            f.write(data)
        print("saved", name, len(data) // 1024, "KB")
        return True
    except Exception as e:
        print("FAILED", name, e, "\n  open", url, "and save it as frames/" + name)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sequence", help="Air Quality frame numbers, e.g. 0,150,300 or 0-600:150")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    ok = all([save(n, u) for n, u in FRAMES.items()])
    if args.sequence:
        print("\nAir Quality sequence frames:")
        for n in parse_sequence(args.sequence):
            name = f"air-quality-{n:04d}.png"
            ok = save(name, SEQ_URL.format(n=n), shrink) and ok
            print(f"""  frames.js entry:
  {{ id: "air-quality-{n:04d}", title: "Air quality, frame {n}", src: "frames/{name}",
    blurb: "A later moment of NASA's air quality model.", description: "", credit: "NASA's Scientific Visualization Studio, svs.gsfc.nasa.gov/5533" }},""")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
