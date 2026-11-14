/*
  NASA Earth Information Center frames for the jukebox.

  1. Run `python get_frames.py` (downloads the frames below into frames/), or save your own PNG/JPG there.
  2. Add an entry below. Entries whose image cannot be loaded are skipped automatically.
  3. Serve the folder over HTTP (python -m http.server) so the browser may read the pixels.

  Fields:
    id          short unique id
    title       name shown on the record
    src         path to the image
    blurb       one line shown on the card
    description hand-written description for blind and low-vision users (optional, but strongly recommended).
                It is read before the automatic description.
    credit      image credit shown at the bottom of the page
*/
window.JUKEBOX_FRAMES = [
  {
    id: "air-quality",
    title: "Air Quality Model Runs",
    src: "frames/air-quality.png",
    blurb: "A globe split into PM2.5, nitrogen oxides and ozone.",
    description: "A globe seen over the Americas, cut into three vertical slices on a white background, each labelled in a small rounded box. On the left, in yellow and orange, is fine particle pollution (PM2.5), with darker orange smoke near the top left over western North America. In the middle, in bright green, are nitrogen oxides, with dark spots over cities and coasts and white and black patches towards the south. On the right, in purple and grey, is ozone, with soft swirls. Colours are smooth, with sharp edges only where the slices meet.",
    credit: "NASA's Scientific Visualization Studio / GMAO, GEOS-CF model. Visualization: Helen-Nicole Kostis (USRA), Joseph V. Ardizzone (NASA/GSFC); scientist: Lesley Ott (NASA/GSFC). svs.gsfc.nasa.gov/5533"
  },
  {
    id: "global-temperature",
    title: "Global temperature anomaly, 2024",
    src: "frames/global-temperature.png",
    blurb: "A red and blue world map of how far 2024 ran from normal.",
    description: "A flat world map in the Robinson projection. White means near the 1951-1980 average, red means warmer than that average and blue means cooler. Reds dominate the map for 2024, strongest over land and towards the poles, with only small and pale blue areas. The colours are smooth gradients with very few hard edges.",
    credit: "NASA's Scientific Visualization Studio. Data: Robert B. Schmunk (NASA/GSFC GISS); scientist: Gavin A. Schmidt (NASA/GSFC GISS); visualizer: Mark SubbaRao (NASA/GSFC). GISTEMP. svs.gsfc.nasa.gov/5450"
  },
  {
    id: "arctic-sea-ice",
    title: "Arctic Sea Ice Minimum 2024",
    src: "frames/arctic-sea-ice.jpg",
    blurb: "The shrunken summer ice cap at the top of the world.",
    description: "A view looking down on the Arctic Ocean. Bluish-white sea ice forms an irregular cap around the North Pole, ringed by darker open ocean and the surrounding land of Canada, Greenland, Russia and Alaska. A thin yellow line marks the average minimum ice extent for 1981-2010; the 2024 ice sits well inside it. Mostly white and blue, with a sharp edge where ice meets water.",
    credit: "NASA's Scientific Visualization Studio. Visualization: Trent L. Schindler (USRA); scientist: Walt Meier (NASA/GSFC). Data: JAXA AMSR2, Blue Marble Next Generation. svs.gsfc.nasa.gov/5382"
  }
];
