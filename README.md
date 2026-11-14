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
| **Air over a city** | Hourly NASA GEOS-CF surface PM2.5, ozone, CO and NO₂ (via `fetch_data.py` → `data.js`) | PM2.5 = kick drum, ozone = bell on a pentatonic scale, CO = pad, NO₂ = ticks |
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
- Fixed, health-oriented scales by default (PM2.5 0–150 µg/m³, ozone 20–80 ppb, CO 100–1000 ppb, NO₂ 0–10 ppb), so a clean week and a polluted week sound different. "This window only" rescales to the data shown.
- When PM2.5 enters the unhealthy range the calm fifth in the pad bends towards a tense tritone and the filter sharpens.
- The chart marks the WHO 24-hour PM2.5 guideline (15 µg/m³). PM2.5 category names follow US EPA bands.

## Accessibility
- Every record has a text description: hand-written (`description` in `frames.js`) plus an automatic one (colours, tone, structure, brightest area, key).
- A live region announces what is happening while playing (can be turned off), and **Describe this moment** (key `D`) speaks on demand.
- Full keyboard control: `Space`/`K` play, `←` `→` seek (Shift = bigger steps), `↑` `↓` volume, `1`–`4` instruments, `D` describe.
- Labelled controls, `aria-pressed` toggles, `aria-valuetext` on the position slider, skip link, visible focus, text alternative for the chart, high-contrast mode.

## Adding NASA EIC frames
1. Save a frame from an EIC visualization into `frames/`.
2. Add an entry to `frames.js` (title, path, one-line blurb, a short written description for blind users, credit).
3. Reload. Entries that cannot be loaded are skipped.

## Adding locations
Add entries to `LOCATIONS` in `fetch_data.py`, then run `python fetch_data.py` (needs `pip install xarray netCDF4 pandas numpy`).
Each location becomes a record automatically.

## Files
- `index.html`: the whole app (Web Audio synthesis, image analysis, UI)
- `data.js`: generated air-quality data
- `frames.js`: list of EIC images
- `fetch_data.py`: pulls GEOS-CF data from NASA OPeNDAP

## Credits
Air-quality data: NASA GMAO GEOS-CF. Image credits are shown on the page per record.