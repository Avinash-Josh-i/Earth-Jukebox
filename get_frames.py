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
import argparse, io, json, os, re, sys, urllib.parse, urllib.request
from html.parser import HTMLParser

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


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def discover_svs_frames(svs_id, frame_set=None):
    """Return one published SVS frame directory discovered from its API record."""
    api_url = f"https://svs.gsfc.nasa.gov/api/{svs_id}"
    with urllib.request.urlopen(urllib.request.Request(api_url, headers={"User-Agent": "EarthJukebox/1.0"}),
                               timeout=120) as response:
        record = json.loads(response.read().decode("utf-8"))
    candidates = []
    for group in record.get("media_groups", []):
        for item in group.get("items", []):
            instance = item.get("instance") or {}
            if instance.get("media_type") == "Frames" and instance.get("url"):
                candidates.append(instance["url"])
    if frame_set:
        candidates = [url for url in candidates if frame_set.lower() in url.lower()]
    if not candidates:
        available = ", ".join(record.get("title", "unknown visualization") for _ in [0])
        raise ValueError(f"no matching frame directory found for SVS {svs_id} ({available})")
    return candidates[0].replace("http://", "https://", 1)


def svs_frame_urls(directory, numbers):
    """Find the requested numbered PNGs from an SVS directory listing."""
    request = urllib.request.Request(directory, headers={"User-Agent": "EarthJukebox/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        parser = Links()
        parser.feed(response.read().decode("utf-8", errors="replace"))
    files = {}
    for href in parser.hrefs:
        filename = os.path.basename(urllib.parse.urlparse(href).path)
        match = re.search(r"_(\d+)\.png$", filename, re.IGNORECASE)
        if match:
            files[int(match.group(1))] = urllib.parse.urljoin(directory, href)
    missing = [number for number in numbers if number not in files]
    if missing:
        raise ValueError(f"frame(s) not found in {directory}: {', '.join(map(str, missing))}")
    return [(number, files[number]) for number in numbers]


def parse_image(text):
    """Parse 'filename=url' for a one-off EIC/SVS image download."""
    name, separator, url = text.partition("=")
    if not separator or not name.strip() or not url.strip():
        raise ValueError('use "filename.ext=https://example/image.png"')
    name = name.strip()
    if name in (".", "..") or name != os.path.basename(name):
        raise ValueError(f"invalid output filename: {name}")
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"unsupported image URL: {url.strip()}")
    return name, url.strip()


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
    ap.add_argument("--svs-id", type=int, help="discover frame sets from an SVS page, e.g. 5533")
    ap.add_argument("--frame-set", help="substring to select an SVS frame set, e.g. MapWithLabels")
    ap.add_argument("--image", action="append", default=[], metavar="NAME=URL",
                    help="download an additional EIC/SVS image, e.g. "
                         "map.png=https://example/map.png (repeatable)")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    ok = all([save(n, u) for n, u in FRAMES.items()])
    if args.sequence:
        print("\nAir Quality sequence frames:")
        numbers = parse_sequence(args.sequence)
        if args.svs_id:
            try:
                directory = discover_svs_frames(args.svs_id, args.frame_set)
                frame_urls = svs_frame_urls(directory, numbers)
            except (OSError, ValueError, json.JSONDecodeError) as e:
                ap.error(f"SVS frame discovery failed: {e}")
            set_name = os.path.basename(directory.rstrip("/"))
            print(f"Discovered {set_name} from SVS {args.svs_id}")
        else:
            frame_urls = [(n, SEQ_URL.format(n=n)) for n in numbers]
        for n, url in frame_urls:
            name = f"air-quality-{n:04d}.png"
            ok = save(name, url, shrink) and ok
            print(f"""  frames.js entry:
  {{ id: "air-quality-{n:04d}", title: "Air quality, frame {n}", src: "frames/{name}",
    blurb: "A later moment of NASA's air quality model.", description: "", credit: "NASA's Scientific Visualization Studio, svs.gsfc.nasa.gov/5533" }},""")
    for spec in args.image:
        try:
            name, url = parse_image(spec)
        except ValueError as e:
            ap.error(str(e))
        ok = save(name, url) and ok
        print(f"""  frames.js entry:
  {{ id: "{os.path.splitext(name)[0]}", title: "{os.path.splitext(name)[0]}",
    src: "frames/{name}", blurb: "", description: "", credit: "NASA Earth Information Center / NASA SVS" }},""")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
