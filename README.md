# London Cartogram

This project generates two related artefacts for London:

- a static SVG cartogram that expands places with stronger TfL rail access and compresses places with weaker access
- an interactive commute-time web app that lets you pin an origin, inspect travel times, toggle the warp and heatmap layers, and share deep links to a view

Live site: [ldn.connoradams.co.uk](https://ldn.connoradams.co.uk/)

## What The Project Uses

- ONS Greater London borough boundaries
- TfL GTFS from Transitland for Tube, DLR, Tram, Thames Clippers, Woolwich Ferry, and Cable Car routes
- TfL OSI interchange data, plus a small tram interchange supplement
- TfL `Stations.csv` and a small reconciliation file for fare-zone tagging
- optional London OSM streets and parks extracts for the basemap
- a distance-based warp for the static SVG
- a station-to-station network plus walking access model for the interactive commute map

This is the first London cut. Overground and Elizabeth Line are intentionally deferred and are not in the commute model yet.

## Requirements

- Python 3
- `pnpm` and Node.js only if you want to run or deploy the Cloudflare Worker

The Python build scripts use the standard library only, so there is no Python dependency install step.

## Generate The Static SVG

Run:

```bash
python3 generate_london_rail_cartogram.py
```

Output:

```text
output/london_rail_cartogram.svg
```

Source files are expected under `data/`. The SVG generator uses the London boundary and TfL GTFS files, and will skip optional London basemap extracts when they are absent.

## Build The Interactive Site Data

Run:

```bash
python3 build_commute_site_data.py
```

Output:

```text
site/data/commute_map_data.json
```

The data bundle is rebuilt manually on demand. There is no scheduled refresh job.

## Local Preview

For a simple static preview:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/site/
```

Useful local-preview notes:

- The site loads its data from `site/data/commute_map_data.json`.
- Postcode search uses [postcodes.io](https://postcodes.io/) at runtime.
- Address search uses OpenStreetMap Nominatim at runtime.
- On plain static localhost, production-style routes like `/@51.51768,-0.08224` are not available. Use query-string sharing there instead.

## Cloudflare Worker Dev And Deploy

Install the Worker tooling:

```bash
pnpm install
```

Run the Worker locally:

```bash
pnpm run dev
```

Deploy:

```bash
pnpm run deploy
```

This repo includes:

- [wrangler.jsonc](wrangler.jsonc): bundles the `site/` directory as Worker assets and routes `ldn.connoradams.co.uk/*`
- [src/worker.js](src/worker.js): serves the Worker assets directly, with no path-prefix rewrite

Deployment behaviour:

- The Worker serves the app at `https://ldn.connoradams.co.uk/`.
- Asset requests are served from `site/`.
- Pretty origin routes like `https://ldn.connoradams.co.uk/@51.51768,-0.08224` fall back to `site/index.html`.

If this is your first local `pnpm` install and Wrangler postinstall steps were blocked, run `pnpm approve-builds` and approve the relevant packages before deploying again.

## Project Layout

- [generate_london_rail_cartogram.py](generate_london_rail_cartogram.py): builds the static SVG cartogram
- [build_commute_site_data.py](build_commute_site_data.py): builds the interactive site data bundle
- [data/](data/): source data used by the build scripts
- [site/index.html](site/index.html): app shell and metadata
- [site/app.js](site/app.js): interactive map, search, sharing, and rendering logic
- [site/styles.css](site/styles.css): site styles
- [site/data/commute_map_data.json](site/data/commute_map_data.json): generated site dataset
- [src/worker.js](src/worker.js): Cloudflare Worker entrypoint

## Current App Behaviour

- hover or tap to choose an origin
- pin an origin and inspect commute times back to that point
- toggle warp and heatmap layers
- zoom and full-screen the map
- search for London postcodes and addresses
- use browser geolocation when available
- export and share views, including deep links
- display a Zone 1 in 30 min reachability score

## Attribution

- Boundaries: [ONS Open Geography Portal](https://geoportal.statistics.gov.uk/)
- Transit feed: [TfL feed via Transitland](https://www.transit.land/feeds/f-transport~for~london)
- Interchanges and station data: [TfL Open Data](https://tfl.gov.uk/info-for/open-data-users/)
- Streets and parks: [OpenStreetMap](https://www.openstreetmap.org/)
- Postcode search: [postcodes.io](https://postcodes.io/)
- Share/UI icon source where still used: [Iconmonstr](https://iconmonstr.com/)

This project is forked from [AntCas/nyc-cartogram](https://github.com/AntCas/nyc-cartogram).
