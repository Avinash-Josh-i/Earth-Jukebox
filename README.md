# Earth Jukebox

Turn NASA Earth data and Earth imagery into sound. Pick a record, press play, and listen to the planet.
Built for the NASA Earth Information Center (EIC) sonification challenge, with accessibility as a core design goal.

## Run it

```
python -m http.server
```
then open http://localhost:8000. A local server is needed so the browser may read image pixels
(opening `index.html` straight from disk works for the air-quality record and uploaded images, but not for image files in `frames/`).

## Records

| Kind | What it is | How it becomes sound |
|---|---|---|
| **Air over a city** (pick it on the globe) | Hourly NASA GEOS-CF surface PM2.5, ozone, CO and NO₂ (via `fetch_data.py` → `data.js`) | PM2.5 health band = chord and beat, ozone = bell pitch, CO = pad, NO₂ = ticks (details below) |
| **NASA EIC frame** | Any image you list in `frames.js` | The picture is scanned left to right as a score (below) |
| **Your own image** | Chosen with the file button | Same as above |

### Image → sound rules
- Average hue → key. Warm images → minor, cool images → major.
- In each of 64 vertical slices, the feature that stands out most (contrast and edges) sets the melody pitch: higher in the picture = higher note.
- Melody pans from the left ear to the right ear in step with the scan line.
- Slice brightness → pad filter and loudness. Dark slices add a low sub tone. Slice hue picks the bass note.
- Sharp edges → light ticks. Detailed images play more notes, smooth ones fewer and longer.
- Drag the position slider while paused to hear any slice (tactile-style exploration by sound).

### Air → sound rules
- **Health bands drive the harmony and the beat.** PM2.5 is placed in its US EPA band (good, moderate, unhealthy for sensitive groups, unhealthy, very unhealthy, hazardous). Each band has its own pad chord (calm major, open, minor, diminished, clashing, dense cluster) and its own kick subdivision (once per two beats, then 1, 2, 3, 4 and 6 hits per beat). Crossing a threshold is a clear step in the sound, not a slow slide. Bands always use the fixed health scale, whatever the Scale setting is.
- **A quiet click marks the beat** (one per second). The kick locks to it on a shared grid, so "twice as fast" is heard as a rhythm. The WHO 24-hour guideline (15 µg/m³) falls in the calmest bands, so the click is the "clean air" reference to compare against.
- Within a band, PM2.5 sets kick loudness; ozone = bell pitch on a pentatonic scale, CO = pad loudness and brightness, NO₂ = tick rate. These four use the Scale setting: fixed health-oriented ranges (PM2.5 0–150 µg/m³, ozone 20–80 ppb, CO 100–1000 ppb, NO₂ 0–10 ppb) by default, or "This window only" to rescale to the data shown.
- A soft low note plays when a new local day begins, so the daily rhythm of the pollution can be heard.
- The chart marks the WHO 24-hour PM2.5 guideline (15 µg/m³). PM2.5 category names follow US EPA bands.

## Accessibility
- Every record has a text description: hand-written (`description` in `frames.js`) plus an automatic one (colours, tone, structure, brightest area, key).
- A live region announces what is happening while playing (can be turned off), and **Describe this moment** (key `D`) speaks on demand.
- Full keyboard control: `Space`/`K` play, `←` `→` seek (Shift = bigger steps), `↑` `↓` volume, `1`–`4` instruments, `D` describe.
- Labelled controls, `aria-pressed` toggles, `aria-valuetext` on the position slider, skip link, visible focus, text alternative for the chart, high-contrast mode.

## Adding NASA EIC frames
Three real frames ship in `frames.js`: **Air Quality Model Runs** (SVS 5533), **Global temperature anomaly 2024** (SVS 5450) and **Arctic Sea Ice Minimum 2024** (SVS 5382), chosen to look very different (dark glowing plumes, smooth red/blue map, white-on-blue polar scene). Run `python get_frames.py` once to download them into `frames/`.

The Air Quality visualization is a numbered image sequence. Pick a few frames with e.g. `python get_frames.py --sequence 0,150,300,450` (each is about 8 MB at full size; install Pillow with `pip install pillow` and they are shrunk to 1920x1080). The script prints a `frames.js` entry for each one. Write a short description of what the frame shows before publishing.

To add more:
1. Save a frame from an EIC or SVS visualization into `frames/`.
2. Add an entry to `frames.js` (title, path, one-line blurb, a short written description for blind users, credit).
3. Reload. Entries that cannot be loaded are skipped.

## The globe and adding cities
Every city in `data.js` that has coordinates is a dot on the globe. Click a dot (or choose the city from the list beside the globe) to play it. Drag the globe to turn it. Dot colour is the record's average PM2.5 in US EPA bands. If a city has more than one time window, a **Time window** menu appears.

`cities.json` lists 84 cities (key, name, country, lat, lon, IANA time zone). Fetch them all, or a few:

```
pip install xarray netCDF4 pandas numpy        # Windows also: pip install tzdata
python fetch_data.py --list                    # see the keys
python fetch_data.py                           # every city, last 7 days
python fetch_data.py --only kathmandu,delhi    # just these
python fetch_data.py --add "Pokhara,28.21,83.99,Asia/Kathmandu" --only pokhara --merge
```

The fetcher caches each finished city in `.fetch_cache/`, so if the connection drops, run the same command again to carry on. Cities that fail or have no data are skipped and listed at the end. Time-zone offsets (including daylight saving) come from each city's IANA zone. `data.js` stores each hourly series compactly (`t0`, `step_min`, `n`); older `data.js` files with full `times` lists still load, and records without `lat`/`lon` stay as cards below the globe.

## Files
- `index.html`: the whole app (Web Audio synthesis, image analysis, UI)
- `data.js`: generated air-quality data
- `cities.json`: the cities the globe and fetcher know about
- `land.js`: world land outline for the globe (Natural Earth 110m, public domain)
- `frames.js`: list of EIC images
- `get_frames.py`: downloads the listed frames from NASA SVS into `frames/`
- `fetch_data.py`: pulls GEOS-CF data from NASA OPeNDAP (resumable, many cities)

## Credits
Air-quality data: NASA GMAO GEOS-CF. Globe land outline: Natural Earth (public domain). Image credits are shown on the page per record.

## Testing
Open `test/runner.html` in a browser (served over HTTP, e.g. `python -m http.server`). It imports `js/core.js` as an ES module and runs plain-JS assertions (no build step, no external dependencies) over the pure helpers: colour conversion, key building, image analysis, PM2.5 EPA bands, and the Intl time-zone formatting.

## Guided tour and matching the picture to the numbers

The **Guided tour** button plays a short sequence on its own: Reykjavik, Kathmandu, then the NASA air-quality frame. It uses whichever of those records exist, and any click on a record or on Play ends it.

The NASA picture (SVS 5533, Air Quality Model Runs) shows **July-August 2024** from GEOS-CF. To hear the same model for the same months, add those months next to the winter records:

    python fetch_data.py --start 2024-07-15 --end 2024-08-15 --label "Jul-Aug 2024" --merge

`--only kathmandu,vancouver` limits it to some cities, and `--merge` keeps what is already in `data.js`.
