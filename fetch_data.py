"""
Jukebox data fetcher: pulls GEOS-CF air quality from NASA OPeNDAP, averages it
over each location's lat/lon box (surface level), and writes data.js for index.html.

Setup:   pip install xarray netCDF4 pandas numpy
Run:     python fetch_data.py                      (last 7 days available)
         python fetch_data.py --start 2026-01-01 --end 2026-01-07
         python fetch_data.py --url <your working OPeNDAP URL>

Match the NASA picture: the SVS 5533 Air Quality animation shows July-August 2024 from GEOS-CF.
Fetch the same months for the cities, and ADD them to data.js without losing what is there:
         python fetch_data.py --start 2024-07-15 --end 2024-08-15 --label "Jul-Aug 2024" --merge
         python fetch_data.py --only kathmandu,vancouver --start 2024-07-15 --end 2024-08-15 --label "Jul-Aug 2024" --merge

To add a city, add one entry to LOCATIONS. Global = a long list of boxes.
"""
import argparse
import json
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import xarray as xr

# Replace with the exact dataset URL that worked for you in test.py
DEFAULT_URL = "https://opendap.nccs.nasa.gov/dods/gmao/geos-cf/assim/chm_tavg_1hr_g1440x721_v1"

# key -> display name, lat/lon box, UTC offset in minutes (Nepal = UTC+5:45)
LOCATIONS = {
    "kathmandu": {"name": "Kathmandu Valley", "lat": (27.4, 28.0), "lon": (85.0, 85.7), "tz_offset_min": 345},
    "delhi": {"name": "Delhi", "lat": (28.4, 28.9), "lon": (76.9, 77.5), "tz_offset_min": 330},
    # a clean-air contrast: the jukebox shows one record per location listed here
    "reykjavik": {"name": "Reykjavik", "lat": (63.9, 64.3), "lon": (-22.3, -21.6), "tz_offset_min": 0},
    # cities for the July-August 2024 window. Vancouver uses summer time (UTC-7).
    "vancouver": {"name": "Vancouver", "lat": (49.0, 49.5), "lon": (-123.4, -122.7), "tz_offset_min": -420},
    "mexico_city": {"name": "Mexico City", "lat": (19.2, 19.7), "lon": (-99.4, -98.8), "tz_offset_min": -360},
    "sao_paulo": {"name": "Sao Paulo", "lat": (-24.0, -23.3), "lon": (-46.9, -46.3), "tz_offset_min": -180},
    "beijing": {"name": "Beijing", "lat": (39.7, 40.2), "lon": (116.1, 116.8), "tz_offset_min": 480},
    "lagos": {"name": "Lagos", "lat": (6.3, 6.8), "lon": (3.1, 3.7), "tz_offset_min": 60},
}

# track id -> GEOS-CF variable name
VARS = {"pm25": "pm25_rh35_gcc", "o3": "o3", "co": "co", "no2": "no2"}
UNITS = {"pm25": "µg/m³", "o3": "ppb", "co": "ppb", "no2": "ppb"}


def axis_slice(coord, lo, hi):
    """Slice that works whether the coordinate is ascending or descending."""
    return slice(lo, hi) if float(coord[0]) < float(coord[-1]) else slice(hi, lo)


def as_timestamp(value):
    """Convert NumPy and cftime datetime values to pandas timestamps."""
    try:
        return pd.Timestamp(value)
    except (TypeError, ValueError):
        return pd.Timestamp(str(value))


def format_timestamp(value):
    """Format NumPy and cftime datetime values as UTC ISO timestamps."""
    return as_timestamp(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def coordinate_time(value, coordinate):
    """Convert a pandas timestamp to the coordinate's native datetime type."""
    first = coordinate[0]
    if type(first).__module__.startswith("cftime"):
        timestamp = as_timestamp(value)
        return type(first)(
            timestamp.year,
            timestamp.month,
            timestamp.day,
            timestamp.hour,
            timestamp.minute,
            timestamp.second,
            timestamp.microsecond,
        )
    return value


def extract(ds, loc, t0, t1):
    out = {}
    times = None
    time_coord = ds.time
    native_t0 = coordinate_time(t0, time_coord.values)
    native_t1 = coordinate_time(t1, time_coord.values)
    is_cftime = type(time_coord.values[0]).__module__.startswith("cftime")
    for track, var in VARS.items():
        da = ds[var].sel(
            lat=axis_slice(ds.lat, *loc["lat"]),
            lon=axis_slice(ds.lon, *loc["lon"]),
        )
        if is_cftime:
            da = da.where((time_coord >= native_t0) & (time_coord <= native_t1), drop=True)
        else:
            da = da.sel(time=slice(native_t0, native_t1))
        if "lev" in da.dims:
            da = da.sel(lev=ds.lev.max())  # surface = highest level index / pressure
        da = da.mean(dim=["lat", "lon"]).load()
        vals = da.values.astype("float64")
        current_times = da["time"].values
        if times is None:
            times = current_times
        elif not np.array_equal(times, current_times):
            raise ValueError(f"Time coordinates differ for {var}; cannot align pollutant series")
        if track != "pm25":
            vals = vals * 1e9  # mol/mol -> ppb
        out[track] = [None if np.isnan(v) else round(float(v), 3) for v in vals]
    if times is None or len(times) == 0:
        raise ValueError(
            f"No data available for {loc['name']} between "
            f"{pd.Timestamp(t0).isoformat()} and {pd.Timestamp(t1).isoformat()}"
        )
    return times, out


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def load_existing(path):
    """Read an earlier data.js so new locations can be added to it."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default="data.js")
    ap.add_argument("--only", help="comma-separated location keys, e.g. kathmandu,vancouver")
    ap.add_argument("--label", help='names this time window, e.g. "Jul-Aug 2024"; added to each record title')
    ap.add_argument("--merge", action="store_true", help="add to the existing data.js instead of replacing it")
    args = ap.parse_args()

    wanted = [k.strip() for k in args.only.split(",")] if args.only else list(LOCATIONS)
    unknown = [k for k in wanted if k not in LOCATIONS]
    if unknown:
        ap.error("unknown location(s): " + ", ".join(unknown) + ". Known: " + ", ".join(LOCATIONS))

    ds = xr.open_dataset(args.url, engine="netcdf4")
    print("Dataset time range:", ds.time.values[0], "->", ds.time.values[-1])
    print("Level values (first/last):", ds.lev.values[:2], ds.lev.values[-2:])

    t1 = pd.Timestamp(args.end) if args.end else as_timestamp(ds.time.values[-1])
    t0 = pd.Timestamp(args.start) if args.start else t1 - pd.Timedelta(days=args.days)
    if t0 > t1:
        ap.error("--start must be earlier than or equal to --end")

    result = (load_existing(args.out) if args.merge else None) or {"locations": {}}
    result["meta"] = {
        "source": "NASA GMAO GEOS-CF via OPeNDAP",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    result["units"] = UNITS
    for key in wanted:
        loc = LOCATIONS[key]
        out_key = key + ("_" + slug(args.label) if args.label else "")
        name = loc["name"] + (", " + args.label if args.label else "")
        print(f"Fetching {name} ...")
        times, series = extract(ds, loc, t0, t1)
        result["locations"][out_key] = {
            "name": name,
            "tz_offset_min": loc["tz_offset_min"],
            "times": [format_timestamp(t) for t in times],
            "series": series,
        }
        print(f"  {len(times)} hourly steps")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("window.JUKEBOX_DATA = " + json.dumps(result) + ";\n")
    print("Wrote", args.out, "with", len(result["locations"]), "locations")


if __name__ == "__main__":
    main()
