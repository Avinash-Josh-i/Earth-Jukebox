"""
Jukebox data fetcher: pulls GEOS-CF air quality from NASA OPeNDAP, averages it
over a small lat/lon box around each city (surface level), and writes data.js
for index.html. The globe in the app shows every city that is in data.js.

Setup:   pip install xarray netCDF4 pandas numpy        (Windows also: pip install tzdata)
Run:     python fetch_data.py                            (all cities in cities.json, last 7 days)
         python fetch_data.py --list                     (show the available cities)
         python fetch_data.py --only kathmandu,delhi     (just these)
         python fetch_data.py --add "Pokhara,28.21,83.99,Asia/Kathmandu" --only pokhara --merge
         python fetch_data.py --start 2024-07-15 --end 2024-08-15 --label "Jul-Aug 2024" --merge

Notes:
  * A run is resumable. Each finished city is cached in .fetch_cache/, so if the
    connection drops, run the same command again and it carries on where it stopped.
    Use --refresh to ignore the cache.
  * A city that fails (after retries) or has no data is skipped and reported at the
    end; the rest are still written.
  * Time-zone offsets come from each city's IANA time zone (daylight saving included),
    so you no longer set them by hand.
  * --merge adds to the existing data.js (use it to add other time windows or cities).

Match the NASA picture: the SVS 5533 Air Quality animation shows July-August 2024 from GEOS-CF.
"""
import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

# Replace with the exact dataset URL that worked for you in test.py
DEFAULT_URL = "https://opendap.nccs.nasa.gov/dods/gmao/geos-cf/assim/chm_tavg_1hr_g1440x721_v1"

HERE = Path(__file__).resolve().parent

# track id -> GEOS-CF variable name
VARS = {"pm25": "pm25_rh35_gcc", "o3": "o3", "co": "co", "no2": "no2"}
UNITS = {"pm25": "µg/m³", "o3": "ppb", "co": "ppb", "no2": "ppb"}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def as_timestamp(value):
    """Convert NumPy and cftime datetime values to pandas timestamps."""
    try:
        return pd.Timestamp(value)
    except (TypeError, ValueError):
        return pd.Timestamp(str(value))


def format_timestamp(value):
    """Format NumPy and cftime datetime values as UTC ISO timestamps."""
    return as_timestamp(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def naive_utc(value):
    ts = pd.Timestamp(value)
    return ts.tz_convert("UTC").tz_localize(None) if ts.tzinfo else ts


def coordinate_time(value, coordinate):
    """Convert a pandas timestamp to the coordinate's native datetime type."""
    first = coordinate[0]
    if type(first).__module__.startswith("cftime"):
        ts = as_timestamp(value)
        return type(first)(ts.year, ts.month, ts.day, ts.hour, ts.minute, ts.second, ts.microsecond)
    return value


def axis_slice(coord, lo, hi):
    """Slice that works whether the coordinate is ascending or descending."""
    return slice(lo, hi) if float(coord[0]) < float(coord[-1]) else slice(hi, lo)


# cities
def load_cities(path):
    with open(path, encoding="utf-8") as f:
        cities = json.load(f)
    return {c["key"]: c for c in cities}


def parse_added(text):
    """--add "Name,lat,lon[,IANA time zone]" -> city dict."""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 3:
        raise ValueError('use "Name,lat,lon" or "Name,lat,lon,Region/City"')
    name, lat, lon = parts[0], float(parts[1]), float(parts[2])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"{name}: latitude/longitude out of range")
    city = {"key": slug(name).replace("-", "_"), "name": name, "country": "", "lat": lat, "lon": lon}
    if len(parts) > 3 and parts[3]:
        city["tz"] = parts[3]
    return city


def utc_offset_minutes(city, when):
    """UTC offset in minutes at `when` (daylight saving included) from the city's IANA zone."""
    tz = city.get("tz")
    if tz and ZoneInfo is not None:
        try:
            off = when.tz_localize("UTC").astimezone(ZoneInfo(tz)).utcoffset()
            return int(off.total_seconds() // 60)
        except Exception:  # unknown zone, or tzdata missing on Windows
            print(f"  ! time zone {tz!r} unavailable (pip install tzdata); using longitude")
    if "tz_offset_min" in city:
        return int(city["tz_offset_min"])
    return int(round(city["lon"] / 15 * 4) * 15)  # nearest 15 minutes of solar time


# extraction
def time_indices(ds, t0, t1):
    """Contiguous slice of time steps inside [t0, t1], computed once for all cities."""
    values = ds.time.values
    if type(values[0]).__module__.startswith("cftime"):
        keep = (values >= coordinate_time(t0, values)) & (values <= coordinate_time(t1, values))
    else:
        index = pd.DatetimeIndex(values)
        keep = (index >= t0) & (index <= t1)
    hits = np.flatnonzero(np.asarray(keep))
    if len(hits) == 0:
        raise ValueError(
            f"No data between {t0.isoformat()} and {t1.isoformat()} "
            f"(dataset covers {as_timestamp(values[0])} to {as_timestamp(values[-1])})"
        )
    return slice(int(hits[0]), int(hits[-1]) + 1)


def extract(ds, city, tslice, half_box):
    """Mean over the city's box at the surface level, for every track."""
    sub = ds[list(VARS.values())].isel(time=tslice)
    box = sub.sel(
        lat=axis_slice(ds.lat, city["lat"] - half_box, city["lat"] + half_box),
        lon=axis_slice(ds.lon, city["lon"] - half_box, city["lon"] + half_box),
    )
    if box.sizes["lat"] == 0 or box.sizes["lon"] == 0:  # box fell between grid points
        box = sub.sel(lat=[city["lat"]], lon=[city["lon"]], method="nearest")
    if "lev" in box.dims:
        box = box.sel(lev=ds.lev.max())  # surface = highest level index / pressure
    box = box.mean(dim=["lat", "lon"]).load()
    times = box["time"].values
    series = {}
    for track, var in VARS.items():
        vals = box[var].values.astype("float64")
        if track != "pm25":
            vals = vals * 1e9  # mol/mol -> ppb
        series[track] = [None if np.isnan(v) else round(float(v), 2) for v in vals]
    return times, series


def fetch_city(ds, city, tslice, half_box, retries):
    last = None
    for attempt in range(retries + 1):
        try:
            return extract(ds, city, tslice, half_box)
        except Exception as e:  # network hiccups are common on OPeNDAP
            last = e
            if attempt < retries:
                wait = 2 ** (attempt + 1)
                print(f"  ! {type(e).__name__}: {str(e)[:90]} - retry in {wait}s")
                time.sleep(wait)
    raise last


def compact_times(times):
    """Hourly (regular) time axis -> t0/step/n; irregular -> full list."""
    stamps = [as_timestamp(t) for t in times]
    steps = {int((b - a).total_seconds() // 60) for a, b in zip(stamps, stamps[1:])}
    if len(steps) == 1:
        return {"t0": format_timestamp(stamps[0]), "step_min": steps.pop(), "n": len(stamps)}
    return {"times": [format_timestamp(t) for t in stamps]}


# files
def load_existing(path):
    """Read an earlier data.js so new locations can be added to it."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except (OSError, ValueError):
        return None


def write_data(path, result):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text("window.JUKEBOX_DATA = " + json.dumps(result, ensure_ascii=False, separators=(",", ":")) + ";\n",
                   encoding="utf-8")
    tmp.replace(path)


def main():
    ap = argparse.ArgumentParser(description="Fetch GEOS-CF air quality for the Earth Jukebox globe.")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default=str(HERE / "data.js"))
    ap.add_argument("--cities", default=str(HERE / "cities.json"), help="city list (default: cities.json)")
    ap.add_argument("--only", help="comma-separated city keys, e.g. kathmandu,vancouver")
    ap.add_argument("--add", action="append", default=[], metavar="NAME,LAT,LON[,TZ]",
                    help='extra city, e.g. "Pokhara,28.21,83.99,Asia/Kathmandu" (repeatable)')
    ap.add_argument("--list", action="store_true", help="list the available cities and exit")
    ap.add_argument("--half-box", type=float, default=0.25, help="half-width of the averaging box in degrees")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--cache-dir", default=str(HERE / ".fetch_cache"))
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and fetch again")
    ap.add_argument("--label", help='names this time window, e.g. "Jul-Aug 2024"; added to each record title')
    ap.add_argument("--merge", action="store_true", help="add to the existing data.js instead of replacing it")
    args = ap.parse_args()

    try:
        cities = load_cities(args.cities)
        for text in args.add:
            c = parse_added(text)
            cities[c["key"]] = c
    except (OSError, ValueError, KeyError) as e:
        ap.error(f"city list problem: {e}")

    if args.list:
        for k, c in cities.items():
            print(f"{k:16s} {c['name']:22s} {c.get('country', ''):16s} {c['lat']:7.2f} {c['lon']:8.2f}")
        return 0

    wanted = [k.strip() for k in args.only.split(",")] if args.only else list(cities)
    unknown = [k for k in wanted if k not in cities]
    if unknown:
        ap.error("unknown city key(s): " + ", ".join(unknown) + ". Use --list to see them.")

    ds = xr.open_dataset(args.url, engine="netcdf4")
    print("Dataset time range:", ds.time.values[0], "->", ds.time.values[-1])

    t1 = naive_utc(args.end) if args.end else as_timestamp(ds.time.values[-1])
    t0 = naive_utc(args.start) if args.start else t1 - pd.Timedelta(days=args.days)
    if t0 > t1:
        ap.error("--start must be earlier than or equal to --end")
    tslice = time_indices(ds, t0, t1)
    window = args.label or (f"{t0:%Y-%m-%d} to {t1:%Y-%m-%d}" if (args.start or args.end)
                            else f"Last {args.days} days")
    mid = t0 + (t1 - t0) / 2

    result = (load_existing(args.out) if args.merge else None) or {"locations": {}}
    result["meta"] = {
        "source": "NASA GMAO GEOS-CF via OPeNDAP",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    result["units"] = UNITS

    cache = Path(args.cache_dir) / hashlib.md5(
        f"{args.url}|{t0.isoformat()}|{t1.isoformat()}|{args.half_box}".encode()).hexdigest()[:10]
    cache.mkdir(parents=True, exist_ok=True)

    failed, skipped = [], []
    for n, key in enumerate(wanted, 1):
        city = cities[key]
        out_key = key + ("_" + slug(args.label) if args.label else "")
        name = city["name"] + (", " + args.label if args.label else "")
        label = f"[{n}/{len(wanted)}] {city['name']}"
        cfile = cache / f"{key}.json"
        data = None
        if cfile.exists() and not args.refresh:
            try:
                data = json.loads(cfile.read_text(encoding="utf-8"))
                if (data["lat"], data["lon"]) != (city["lat"], city["lon"]):
                    data = None
            except (OSError, ValueError, KeyError):
                data = None
        if data is not None:
            print(f"{label} (cached)")
        else:
            print(f"{label} ...")
            try:
                times, series = fetch_city(ds, city, tslice, args.half_box, args.retries)
            except Exception as e:
                print(f"  x failed: {type(e).__name__}: {str(e)[:120]}")
                failed.append(key)
                continue
            data = {"lat": city["lat"], "lon": city["lon"], **compact_times(times), "series": series}
            cfile.write_text(json.dumps(data), encoding="utf-8")
        if not any(v is not None for v in data["series"]["pm25"]):
            print("  - no data here (outside model coverage?); skipped")
            skipped.append(key)
            continue
        steps = data.get("n") or len(data["times"])
        pm = [v for v in data["series"]["pm25"] if v is not None]
        print(f"  {steps} hourly steps, PM2.5 {min(pm):.0f}-{max(pm):.0f} µg/m³")
        record = {
            "name": name,
            "city": key,
            "window": window,
            "country": city.get("country", ""),
            "lat": city["lat"],
            "lon": city["lon"],
            "tz_offset_min": utc_offset_minutes(city, mid),
        }
        for k in ("t0", "step_min", "n", "times"):
            if k in data:
                record[k] = data[k]
        record["series"] = data["series"]
        result["locations"][out_key] = record

    write_data(Path(args.out), result)
    print(f"Wrote {args.out} with {len(result['locations'])} records")
    if skipped:
        print("No data for:", ", ".join(skipped))
    if failed:
        print("Failed (run the same command again to retry just these):", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
