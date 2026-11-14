/*
  NASA Earth Information Center frames for the jukebox.

  1. Save a frame (PNG or JPG) from an EIC visualization into the frames/ folder.
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
  // {
  //   id: "sst-anomaly",
  //   title: "Sea surface temperature anomaly",
  //   src: "frames/sst-anomaly.png",
  //   blurb: "Warm and cool ocean patches.",
  //   description: "A world map. Reds mark ocean water warmer than average, concentrated along the equatorial Pacific.",
  //   credit: "NASA Earth Information Center"
  // },
];