# London Cartogram Port

Backlog for porting the NYC commute cartogram to London. See `prd-london-cartogram.md` for the full spec.

## Status Legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete

## Reference

| Resource | Location |
|----------|----------|
| **PRD** | `prd-london-cartogram.md` |
| **Upstream NYC repo** | `https://github.com/AntCas/nyc-cartogram` |
| **Transitland TfL feed (downloaded)** | `~/Downloads/f-transport~for~london-latest.zip` |
| **Transitland TfL feed (refresh)** | `https://www.transit.land/feeds/f-transport~for~london` |
| **TfL Out-of-Station Interchanges (ODS)** | `https://tfl.gov.uk/corporate/publications-and-reports/out-of-station-interchanges` |
| **TfL Stations.csv (with fare zones)** | `https://api.tfl.gov.uk/stationdata/tfl-stationdata-detailed.csv` (fallback: TfL Open Data portal "Stations" dataset) |
| **ONS Open Geography (UK LAD boundaries)** | `https://geoportal.statistics.gov.uk/` — dataset *Local Authority Districts (May 2024) Boundaries UK BFC* |
| **OSM Overpass (streets / parks)** | Existing fetch logic in build scripts |
| **`postcodes.io`** | `https://postcodes.io/` |
| **Nominatim** | `https://nominatim.openstreetmap.org/` |
| **`playwright-cli` skill** | For visual verification of the interactive map |

## Decisions

Durable decisions that apply across all tasks (see PRD for rationale):

- **Modes in scope:** LUL, DLR, TCL, CV (Thames Clippers), WFF (Woolwich Ferry), CAB (Cable Car). Overground and Elizabeth Line are out-of-scope for v1.
- **Geography:** 33 GLA boroughs (LAD codes starting `E09`); unioned outline is the cartogram warp domain; individual borough polygons retained as graticule.
- **Headline metric:** "% of Zone 1 LUL/DLR stations reachable in 30 min" from pinned origin.
- **Per-agency wait calibration:** LUL/DLR/TCL ~4 min; CV ~18 min; WFF ~12 min; CAB ~8 min.
- **Deploy:** root of `ldn.connoradams.co.uk`, no path prefix; worker simplified to ~10-line passthrough.
- **Search:** UK postcode pattern → `postcodes.io`; otherwise → Nominatim biased to a Greater London viewbox.
- **Rename strategy:** UI strings, filenames, JSON keys, worker name and routes refer to London + rail. Code internals stay generic where the term is still accurate. Staten Island Ferry constants deleted, not commented.
- **Coordinate system:** WGS84 throughout.
- **No automated tests.** Manual verification per task; full visual verification before deploy.
- **British English** in all user-visible copy.

## How to Use This File

Each task follows this pattern. Complete **all** steps:

1. **Read context** — read the files listed in the task and the PRD section it relates to.
2. **Make changes** — follow the "What to do" instructions.
3. **Verify** — follow the verification steps. If verification fails, fix before committing.
4. **Commit** — one coherent commit per task. Commit message style: imperative, lower-case, no trailing period (matching repo history, e.g. `make maximum distance configurable and add outline option`).
5. **Update status** — change `[ ]` to `[x]` in this file as part of the same commit.

Global verification rules:

- `python3 build_commute_site_data.py` must run to completion (or, if explicitly noted in a task, must fail at a specific later point with a documented error).
- `python3 generate_london_rail_cartogram.py` must run to completion once Phase 6 SVG-1 is done; earlier it may still be named `generate_nyc_subway_weighted_projection.py`.
- After UI changes, open `site/index.html` via `python3 -m http.server 8000` and confirm the relevant interaction by eye.

---

## Phase 1 — Foundation

### [x] **CC-1: Worker + wrangler + HTML shell → London at root domain** | **Size: S** | **Deps: none**

**Problem:** The current Worker, `wrangler.jsonc`, and `site/index.html` all hardcode `castrio.me/nyc` and the `/nyc` path prefix. The London deploy lives at the root of `ldn.connoradams.co.uk`, so this scaffolding must be rewritten and the path-prefix logic deleted.

**What to do:**

1. In `src/worker.js`, delete `PATH_PREFIX`, `DIAGNOSTIC_HEADER`, `withoutPrefix`, `withDiagnosticHeader`, `rewriteAssetRedirect`. Reduce the file to the minimal passthrough:
   ```js
   export default {
     async fetch(request, env) {
       return env.ASSETS.fetch(request);
     },
   };
   ```
2. In `wrangler.jsonc`, change `name` from `nyc-cartogram` to `ldn-cartogram`, and the route pattern from `castrio.me/nyc*` (zone_name `castrio.me`) to `ldn.connoradams.co.uk/*` (zone_name `connoradams.co.uk`).
3. In `site/index.html`, replace `<title>`, all `og:*` and `twitter:*` meta values, the `<link rel="canonical">`, and the inline `isSubpathDeploy` JS so there is no `/nyc` prefix logic. Apply these substitutions:
   - Title: `London Commute POV | Tube & Rail Cartogram`
   - OG site name: `London Commute POV`
   - OG/Twitter description: `Explore London by Tube and rail commute time with a warped transit cartogram, click-to-pin origins, and Zone 1 access scores.`
   - Canonical / OG URL: `https://ldn.connoradams.co.uk/`
   - OG image: `https://ldn.connoradams.co.uk/social.png` (file will be updated later; URL is correct)
   - Image alt: `Preview of the London Commute POV transit cartogram.`
   - H1: `London by how long it takes to get there.`
   - Search placeholder (two occurrences): `Search a London postcode or address`
   - Search meta text: `Pin the origin by typing a London postcode or address.`
   - Canvas aria-label: `Warped map of London by transit time`
4. In `site/app.js`, search for `isSubpathDeploy`, `/nyc`, and any path-prefix-aware URL construction. Delete the subpath branch — every URL is computed relative to root.

**Verification:**

- `git grep -nE "nyc|castrio|/nyc/|PATH_PREFIX" -- src site wrangler.jsonc` returns no matches in source files (matches in `data/` or comments referencing the upstream repo URL are fine).
- `pnpm run dev` starts Wrangler without errors. Hit `http://localhost:8787/` (no subpath) and confirm the page loads (it will still render the NYC dataset because we haven't swapped data yet — that's fine for this task).

**Files:** `src/worker.js`, `wrangler.jsonc`, `site/index.html`, `site/app.js`

**Acceptance criteria:** All user-visible NYC strings in the HTML shell are replaced; worker compiled by Wrangler with no errors; no `/nyc` path-prefix logic remains in client or worker code.

---

### [x] **CC-2: Stage new source data files in `data/`** | **Size: S** | **Deps: none**

**Problem:** The build scripts will need four new data inputs (TfL GTFS, TfL OSI, ONS borough boundaries, TfL Stations.csv). They don't exist in `data/` yet. Staging them first means subsequent build tasks can reference them without each task fetching files.

**What to do:**

1. Move `~/Downloads/f-transport~for~london-latest.zip` to `data/tfl_gtfs.zip` (rename to a stable, descriptive name).
2. Download the TfL OSI ODS from https://tfl.gov.uk/corporate/publications-and-reports/out-of-station-interchanges. Save to `data/tfl_osi.ods`. The page links to the latest ODS — pick the most recent file.
3. Download ONS *Local Authority Districts (May 2024) Boundaries UK BFC* from https://geoportal.statistics.gov.uk/ as GeoJSON. Save the raw download to `data/uk_lad_boundaries.geojson`. (Filtering to London happens at build time, not here.)
4. Download TfL `Stations.csv` from https://api.tfl.gov.uk/stationdata/tfl-stationdata-detailed.csv (or the equivalent from the TfL Open Data portal if that URL has changed). Save to `data/tfl_stations.csv`.
5. Create `data/tram_interchanges.json` with the hand-list of 4 tram-rail interchanges as an empty stub for IX-1/BUILD-4 to fill in. Structure: `{"edges": []}`.
6. Create `data/tfl_station_zone_reconciliation.json` as an empty stub `{}` for SCO-1 to populate.
7. Verify each file is non-empty and the OSI ODS opens (`python3 -c "import zipfile; print(zipfile.ZipFile('data/tfl_osi.ods').namelist())"` — ODS is a zip).

**Verification:**

- `ls -la data/tfl_gtfs.zip data/tfl_osi.ods data/uk_lad_boundaries.geojson data/tfl_stations.csv data/tram_interchanges.json data/tfl_station_zone_reconciliation.json` shows all six files with non-zero sizes.
- `python3 -c "import zipfile; z=zipfile.ZipFile('data/tfl_gtfs.zip'); print(z.namelist())"` lists `stop_times.txt`, `routes.txt`, `trips.txt`, `stops.txt`, `agency.txt`, `calendar.txt`, `shapes.txt`, `feed_info.txt`.
- `python3 -c "import json; print(json.load(open('data/uk_lad_boundaries.geojson'))['features'][0]['properties'].keys())"` shows ONS-style property keys (expect `LAD24CD`, `LAD24NM` or similar).

**Files:** `data/` (new files only — no code changes in this task)

**Acceptance criteria:** All six data files exist in `data/` with expected schemas; no source code changes in this commit.

---

## Phase 2 — Build pipeline data swap

### [x] **BUILD-1: Swap GTFS source to Transitland TfL feed** | **Size: M** | **Deps: CC-2**

**Problem:** `build_commute_site_data.py` reads `data/mta_gtfs_subway.zip` and assumes MTA's agency layout (one subway agency + Staten Island Ferry). The new source is `data/tfl_gtfs.zip` with six TfL agencies (LUL, DLR, TCL, CV, WFF, CAB).

**What to do:**

1. In `build_commute_site_data.py`, change `GTFS_PATH = DATA_DIR / "mta_gtfs_subway.zip"` to `GTFS_PATH = DATA_DIR / "tfl_gtfs.zip"`.
2. The script currently filters routes/trips/stops to subway only by route type or by a hardcoded predicate. Update the filter to include all six TfL agencies (route types in the TfL feed: 0 = Tram, 1 = Subway/Tube, 2 = DLR/Cable Car, 4 = Ferry). Read the feed's `agency.txt` and use `agency_id` membership directly rather than route_type.
3. Where the script references MTA-specific column conventions or station ID prefixes (e.g. assumptions about NYC complex IDs), generalise to use the feed's actual values. Inspect `data/tfl_gtfs.zip:stops.txt` for the `parent_station` and `location_type` patterns and adapt accordingly.
4. Do NOT touch the Staten Island Ferry constants in this task (BUILD-3 deletes them). Leave the constants in place; they'll be no-ops because the route id `SIF` won't appear in the TfL feed.

**Verification:**

- `python3 build_commute_site_data.py` runs end-to-end without raising.
- The output `site/data/commute_map_data.json` contains stations with names like `Oxford Circus`, `Bank`, `Stratford` (spot-check via `python3 -c "import json; d=json.load(open('site/data/commute_map_data.json')); print([s['name'] for s in d['stations'][:20]])"`).
- The script's printed stats show 6 agencies and roughly 400+ stations (TfL Tube ~272 + DLR ~45 + TCL ~39 + CV ~24 + WFF ~2 + CAB ~3).

**Files:** `build_commute_site_data.py`

**Acceptance criteria:** Build produces a JSON containing London stations from the Transitland feed. No remaining `mta_gtfs_subway` path references in the build script.

---

### [x] **BUILD-2: Swap NYC boroughs → ONS 33 GLA boroughs (unioned outline + graticule)** | **Size: M** | **Deps: CC-2**

**Problem:** The build and SVG scripts load `data/borough_boundaries.geojson` expecting 5 NYC borough MultiPolygons. The London equivalent is 33 LAD polygons in `data/uk_lad_boundaries.geojson`, filtered to `LAD24CD` codes starting `E09`. The cartogram warp must operate on the unioned outline; individual polygons stay available for graticule rendering.

**What to do:**

1. In `build_commute_site_data.py`, change `BOROUGHS_PATH = DATA_DIR / "borough_boundaries.geojson"` to `BOROUGHS_PATH = DATA_DIR / "uk_lad_boundaries.geojson"`.
2. Update the loader (`extract_boroughs` or equivalent) to filter features where `properties['LAD24CD'].startswith('E09')` (33 London boroughs incl. City of London). Confirm the count is 33.
3. Add a unioned-outline computation: produce a single MultiPolygon that is the geometric union of all 33 borough polygons. This becomes the warp domain. Keep the individual 33 polygons available for later graticule rendering. A pragmatic union approach without `shapely` (since the project uses standard library only): collect all outer rings, drop ring-edges that are shared between adjacent boroughs (i.e. appear twice with reversed orientation). If that's too fiddly without `shapely`, accept `shapely` as a dependency — note this in the commit and update the README.
4. Update `average_borough_latitude` (or equivalent projection origin computation) to use the GLA latitude (~51.5). Confirm the projection produces sensible metres-from-origin for stations.
5. Update borough label placement logic: in NYC it placed a label per borough's largest polygon. For London, *delete* the borough-label rendering entirely from the data bundle — UI-1 will populate neighbourhood labels separately. Comment a single line noting the labels source has moved.

**Verification:**

- `python3 build_commute_site_data.py` runs end-to-end.
- The output `commute_map_data.json` includes a `geography` (or equivalent) section with both the unioned outline and the 33 individual borough polygons.
- `python3 -c "import json; d=json.load(open('site/data/commute_map_data.json')); print(len(d.get('boroughs', d.get('geography', {}).get('boroughs', []))))"` prints `33`.
- Open `site/index.html` via `python3 -m http.server 8000`; the map renders a recognisable Greater London outline (not NYC) — the warp+routing may look odd because other tasks aren't done yet, that's fine.

**Files:** `build_commute_site_data.py`, possibly `README.md` if `shapely` is added

**Acceptance criteria:** Build outputs use 33 London boroughs; the unioned outline is computed and exported; the front-end renders a London silhouette.

---

## Phase 3 — Model adaptations

### [x] **BUILD-3: Per-agency wait calibration + delete Staten Island Ferry constants** | **Size: S** | **Deps: BUILD-1**

**Problem:** The model currently uses a flat `DEFAULT_BOARD_WAIT = 4.0` plus a hardcoded override for the Staten Island Ferry route. For London, infrequent modes (Thames Clippers, Woolwich Ferry, Cable Car) need higher wait penalties so the algorithm doesn't over-recommend them. The NYC ferry constants are now dead code that the rename strategy (Q11) says to delete outright.

**What to do:**

1. In `build_commute_site_data.py`, delete these constants and any code referring to them:
   - `STATEN_ISLAND_FERRY_ROUTE_ID`
   - `STATEN_ISLAND_FERRY_WAIT`
   - `STATEN_ISLAND_FERRY_TRAVEL_MINUTES`
   - `STATEN_ISLAND_FERRY_TERMINALS`
   - Any conditional branches keyed on `route_id == "SIF"` or those terminal ids.
2. Add a per-agency wait override:
   ```python
   AGENCY_WAIT_OVERRIDES = {
       "CV": 18.0,   # Thames Clippers
       "WFF": 12.0,  # Woolwich Ferry
       "CAB": 8.0,   # Cable Car
       # LUL/DLR/TCL fall back to DEFAULT_BOARD_WAIT
   }
   ```
3. Wherever the model consumes `DEFAULT_BOARD_WAIT`, replace with `AGENCY_WAIT_OVERRIDES.get(agency_id, DEFAULT_BOARD_WAIT)`. The agency lookup may need to be threaded through the routing graph builder — extend the relevant route/trip records with their `agency_id` if it isn't already there.

**Verification:**

- `git grep -nE "STATEN_ISLAND_FERRY|SIF" -- *.py` returns no matches.
- `python3 build_commute_site_data.py` runs end-to-end.
- Spot-check the output: pick a station served by the Cable Car (e.g. `Emirates Royal Docks` or `Emirates Greenwich Peninsula`) and confirm its onward commute time from a central origin like `Oxford Circus` is significantly higher than the Jubilee-line-only alternative would suggest (i.e. the model isn't choosing Cable Car as a fast option).

**Files:** `build_commute_site_data.py`

**Acceptance criteria:** Per-agency waits calibrated; SIF constants gone; build still produces a JSON.

---

### [x] **BUILD-4: TfL OSI interchange edges + tram hand-list** | **Size: M** | **Deps: BUILD-1, CC-2**

**Problem:** The NYC pipeline models out-of-station interchanges using a `260m walking radius + 7min penalty` heuristic on GTFS "complexes". TfL publishes an authoritative OSI ODS with 152 named interchange pairs and asymmetric walk times. Use the official data; keep the heuristic only as fallback. Also supplement with a small hand-list of tram-rail interchanges (East Croydon, Wimbledon, Elmers End, Beckenham Junction) since the OSI list omits trams.

**What to do:**

1. Add a parser for `data/tfl_osi.ods`. The ODS is a zip — read `content.xml` and extract rows from the relevant sheet. Columns of interest: `Station_A`, `Station_B`, `InterchangeTimeAB`, `InterchangeTimeBA`. Produce a list of directed edges `(station_a_name, station_b_name, minutes)`. Asymmetric: emit two edges per row.
2. Populate `data/tram_interchanges.json` with the four tram-rail interchanges using a structure like:
   ```json
   { "edges": [
     { "from": "East Croydon Tram Stop", "to": "East Croydon", "minutes": 1.5 },
     { "from": "East Croydon", "to": "East Croydon Tram Stop", "minutes": 1.5 },
     { "from": "Wimbledon Tram Stop", "to": "Wimbledon", "minutes": 2.0 },
     ... (Elmers End, Beckenham Junction both directions)
   ] }
   ```
   Use the actual station names as they appear in `data/tfl_gtfs.zip:stops.txt` (case-sensitive). If a name doesn't match an existing stop, leave a TODO comment and surface in the build script's reconciliation output.
3. In `build_commute_site_data.py`, replace the NYC complex-walking logic with a routine that:
   - Reads OSI edges into the routing graph as inter-station walking edges.
   - Reads `data/tram_interchanges.json` and adds those edges.
   - Joins by station name to GTFS `stop_name`. Edges referencing a name that doesn't match any stop should be reported (printed warning) but not crash the build.
   - Retains the existing `INTER_COMPLEX_WALK_RADIUS = 260m` heuristic as third-tier fallback only — applied for station pairs not already linked by an OSI or tram edge.
4. Update or delete `INTER_COMPLEX_TRANSFER_PENALTY` — replaced by OSI's measured walk time per pair.

**Verification:**

- `python3 build_commute_site_data.py` runs end-to-end.
- The build prints "OSI edges loaded: N" where N is at least 280 (152 OSI rows × 2 directions, before name-match drops).
- Spot-check Bank ↔ Monument and Hammersmith H&C ↔ Hammersmith Picc/Dist: pin Bank as origin and verify Monument is reachable in 1–3 min (not via the rail network).
- The build prints any unmatched station names; the count should be small (under 20). Manually add reconciliations to `data/tfl_station_zone_reconciliation.json` (or a sibling reconciliation file specific to OSI) if needed.

**Files:** `build_commute_site_data.py`, `data/tram_interchanges.json`

**Acceptance criteria:** OSI edges integrated; tram hand-list applied; walking-radius heuristic relegated to fallback role; bank/monument-type pairs work in commute model.

---

## Phase 4 — Score

### [x] **SCO-1: Station→zone enrichment via TfL Stations.csv join** | **Size: M** | **Deps: BUILD-1, CC-2**

**Problem:** GTFS `stops.txt` doesn't include fare zones; the Zone 1 reachability metric (Q12) needs each station tagged with its zone. TfL publishes a CSV with name + zone; we join by name with a small reconciliation table for mismatches.

**What to do:**

1. Add a loader for `data/tfl_stations.csv` to `build_commute_site_data.py`. Identify the columns containing station name and zone (column names vary across TfL CSV releases — inspect the file's header row). Some stations are in multiple zones (e.g. "2/3"); store these as a list of ints or keep as a tuple `(min_zone, max_zone)`.
2. Build a name → zones index.
3. For each GTFS stop, attach a `zones` attribute by name match. Track unmatched stops.
4. For unmatched stops, consult `data/tfl_station_zone_reconciliation.json` for explicit overrides. The reconciliation file maps GTFS stop_name → CSV station name. After applying reconciliations, the build should warn for any still-unmatched LUL/DLR stop (Clippers/Cable Car/Ferry can be unmatched silently since they don't participate in the score).
5. Populate `data/tfl_station_zone_reconciliation.json` with whatever overrides are needed to bring unmatched LUL/DLR count to zero.
6. Export each station's zone(s) in the JSON output (e.g. `station.zones: [1]` or `[2, 3]`).

**Verification:**

- `python3 build_commute_site_data.py` runs end-to-end.
- Output JSON has zone-tagged stations: `python3 -c "import json; d=json.load(open('site/data/commute_map_data.json')); zones = [s.get('zones') for s in d['stations']]; print('with zones:', sum(z is not None for z in zones), '/', len(zones))"`. Expect at least 90% of LUL+DLR stops to be tagged.
- The build prints zero unmatched LUL/DLR stations after reconciliation.

**Files:** `build_commute_site_data.py`, `data/tfl_station_zone_reconciliation.json`

**Acceptance criteria:** Every LUL and DLR station in the output has a `zones` attribute; reconciliation table covers all GTFS↔CSV name mismatches.

---

### [x] **SCO-2: Replace 60-min reachability with "Zone 1 in 30 min"** | **Size: M** | **Deps: SCO-1**

**Problem:** The NYC site shows "% of subway stations reachable in 60 min". For London the headline is "% of Zone 1 LUL/DLR stations reachable in 30 min" (Q12). Both the build-side score computation and the front-end display copy must change.

**What to do:**

1. In `build_commute_site_data.py`, locate the reachability-score computation. Replace it with:
   - Denominator = count of stations where `agency_id in {LUL, DLR}` AND `1 in zones`.
   - Threshold = 30 minutes (was 60).
   - For each origin cell, numerator = count of Zone-1 LUL/DLR stations reachable within 30 min.
   - Score = numerator / denominator (0.0 – 1.0).
2. Export the score per cell in the JSON output. Also export the denominator (a single integer) so the front-end can show "X of N central London stations".
3. In `site/app.js`, find every reference to the old reachability metric — search for `reachScore`, `reachScoreMeta`, `60-minute`, `60 minutes`, etc. Update the display logic to render the new metric.
4. In `site/index.html`, update the copy in any `reach-score` area that says "60-minute reachability" or similar:
   - Headline near the score: `Zone 1 in 30 min`
   - Subtext: `% of central London you can reach`
   - Empty-state copy: `Choose an origin to see how much of central London you can reach in 30 min.`

**Verification:**

- `python3 build_commute_site_data.py` runs end-to-end and the output JSON contains the new score field per cell.
- Open `site/index.html` via local HTTP server; pin Liverpool Street as origin and confirm the score is high (>70%, since Liverpool Street has direct access to most of Zone 1). Pin Cockfosters and confirm the score is much lower (well under 30%).
- `git grep -nE "60[ -]min|60 minute" -- site/` returns no matches.

**Files:** `build_commute_site_data.py`, `site/app.js`, `site/index.html`

**Acceptance criteria:** New metric computed correctly per cell; UI displays it; outer-zone origins show appropriately lower scores than central ones.

---

## Phase 5 — UI polish

### [x] **UI-1: Curated neighbourhood labels replace borough labels** | **Size: S** | **Deps: BUILD-2**

**Problem:** With 33 GLA boroughs, labelling each is illegible noise (Q5). Replace with ~20 curated neighbourhood labels that Londoners actually orient by.

**What to do:**

1. Create `data/neighbourhood_labels.json` with the following ~20 entries. Coordinates are approximate `[lon, lat]` centroids of the named area. Adjust if any look misplaced after rendering.
   ```json
   { "labels": [
     {"name": "Soho", "lon": -0.1335, "lat": 51.5137},
     {"name": "Shoreditch", "lon": -0.0784, "lat": 51.5246},
     {"name": "Brixton", "lon": -0.1148, "lat": 51.4626},
     {"name": "Canary Wharf", "lon": -0.0235, "lat": 51.5054},
     {"name": "Stratford", "lon": -0.0042, "lat": 51.5416},
     {"name": "Wimbledon", "lon": -0.2050, "lat": 51.4214},
     {"name": "Camden", "lon": -0.1426, "lat": 51.5413},
     {"name": "Hampstead", "lon": -0.1786, "lat": 51.5563},
     {"name": "Notting Hill", "lon": -0.2058, "lat": 51.5090},
     {"name": "Greenwich", "lon": 0.0098, "lat": 51.4826},
     {"name": "Peckham", "lon": -0.0696, "lat": 51.4742},
     {"name": "Clapham", "lon": -0.1376, "lat": 51.4625},
     {"name": "Hackney", "lon": -0.0570, "lat": 51.5450},
     {"name": "Islington", "lon": -0.1029, "lat": 51.5362},
     {"name": "Kensington", "lon": -0.1936, "lat": 51.4988},
     {"name": "Richmond", "lon": -0.3037, "lat": 51.4613},
     {"name": "Croydon", "lon": -0.0982, "lat": 51.3762},
     {"name": "Walthamstow", "lon": -0.0211, "lat": 51.5836},
     {"name": "Ealing", "lon": -0.3014, "lat": 51.5130},
     {"name": "Bermondsey", "lon": -0.0810, "lat": 51.4979}
   ] }
   ```
2. In `build_commute_site_data.py`, load this file and export `labels` (or equivalent key) in the JSON bundle, replacing whatever borough-label section currently exists.
3. In `site/app.js`, find the borough label rendering pass; rename and re-aim it at the new label set. Same render style (text positioned at the projected coordinate) — no styling overhaul.
4. Project the labels using the same WGS84→metres projection as the stations/boundaries so they align after the warp.

**Verification:**

- Open `site/index.html` locally; confirm ~20 neighbourhood labels appear at their expected positions, both with and without the warp applied. Visually check that none collide badly.

**Files:** `data/neighbourhood_labels.json`, `build_commute_site_data.py`, `site/app.js`

**Acceptance criteria:** Neighbourhood labels render on both the unwarped and warped map; no borough-name labels remain.

---

### [x] **UI-2: Outside-GLA station rendering at reduced opacity** | **Size: S** | **Deps: BUILD-2**

**Problem:** Stations and route shapes outside the 33 boroughs (Watford, Reading-bound Elizabeth Line stops that we'd have if backfilled, Epping, Epsom, etc.) should still render so the network reads honestly, but at reduced opacity so the GLA stays the focus (Q18). This applies to the interactive map only — the static SVG (SVG-1) uses full opacity.

**What to do:**

1. In `build_commute_site_data.py`, for each station emit a boolean `inside_gla` (or equivalent) based on a point-in-polygon test against the unioned GLA outline produced in BUILD-2. Likewise for each route shape polyline segment.
2. In `site/app.js`, when drawing the station/route layers, multiply the alpha by `inside_gla ? 1.0 : 0.4`.
3. Ensure the warp computation and the reachability score continue to ignore outside-GLA stations entirely — they're cosmetic only. (BUILD-4 / SCO-2 should already exclude them; double-check.)

**Verification:**

- Open the site locally; outer-zone stations (e.g. Stanmore, Cockfosters, Upminster — these are inside Greater London) should render at full opacity. Stations like Watford Junction or Amersham (outside Greater London) should render dim.
- The cartogram warp should not deform around outside-GLA stations.

**Files:** `build_commute_site_data.py`, `site/app.js`

**Acceptance criteria:** Inside-GLA = full opacity; outside-GLA = ~40%; warp and score are unaffected by outside-GLA stations.

---

### [x] **UI-3: Postcode-first search** | **Size: M** | **Deps: CC-1**

**Problem:** NYC's free-text Nominatim search misroutes London queries to non-London matches. Add UK postcode handling (via `postcodes.io`, no API key) as the first path, and bias Nominatim to Greater London for everything else (Q13).

**What to do:**

1. In `site/app.js`, locate the existing Nominatim search handler.
2. Add a postcode-pattern regex matching UK postcodes. Use the well-tested pattern: `^[A-Z]{1,2}[0-9][A-Z0-9]?\s*[0-9][A-Z]{2}$` (case-insensitive). Also accept partial postcodes (`SW1`, `E14`) by detecting the prefix half.
3. If a query matches a full postcode pattern, call `https://api.postcodes.io/postcodes/{POSTCODE}` and use the returned `result.latitude` / `result.longitude`. On 404, fall through to Nominatim.
4. If a query matches a partial-postcode pattern only, call `https://api.postcodes.io/outcodes/{OUTCODE}` and use `result.latitude` / `result.longitude` (outcode-level precision).
5. For all other queries, call Nominatim with a Greater London viewbox bias: append `&viewbox=-0.51,51.69,0.33,51.28&bounded=1` to the existing query.
6. Update the placeholder text already set in CC-1 (`Search a London postcode or address`) — no change needed if CC-1 was applied correctly.

**Verification:**

- Open the site locally. Type `SW1A 1AA` (Buckingham Palace) — pin should land at correct location. Type `E14` — pin should land near Canary Wharf. Type `Hampstead` — pin should land in north London, not Hampstead, NJ.
- Throttle network in DevTools to verify the fallback to Nominatim doesn't fire when `postcodes.io` succeeds.

**Files:** `site/app.js`

**Acceptance criteria:** Full + partial UK postcodes resolve via `postcodes.io`; free text resolves via biased Nominatim; placeholder text accurate.

---

### [x] **UI-4: About section scope note for Overground / Elizabeth Line** | **Size: XS** | **Deps: CC-1**

**Problem:** v1 ships without Overground and Elizabeth Line. The About section should acknowledge this honestly (Q10/Q17).

**What to do:**

1. In `site/index.html`, locate the About / explanatory section (the long-form text near the footer that explains the data sources). At the top of that section, add a single bold sentence:
   > **Heads up:** this is the first London cut. Overground and Elizabeth Line are coming next — they aren't in the commute model yet.
2. Update the source-attribution list to point at: ONS Open Geography (boundaries), TfL Open Data + Transitland (transit), TfL OSI (interchanges), OpenStreetMap (parks + streets), `postcodes.io` (search).
3. Update the GitHub link in the footer to point to this fork's repo URL (https://github.com/connorads/ldn-cartogram).
4. Remove or replace the Twitter / @AnthonyCastrio link with the author's preferred social link (or remove if none).

**Verification:**

- Open the site locally; the About section displays the bold notice; attribution links resolve.

**Files:** `site/index.html`

**Acceptance criteria:** Scope note visible in About; attributions accurate to the new data sources; upstream personal links removed.

---

## Phase 6 — Static SVG + cleanup

### [ ] **SVG-1: Static SVG generator port (rename, union outline, graticule)** | **Size: M** | **Deps: BUILD-2, BUILD-4** *(uses the same boundary + interchange logic as the interactive build)*

**Problem:** `generate_nyc_subway_weighted_projection.py` produces a static SVG by warping each of NYC's 5 boroughs individually. The London equivalent needs to warp the unioned GLA outline and render internal borough lines as faint graticule (Q9). Filename should change per the rename strategy (Q11).

**What to do:**

1. Rename `generate_nyc_subway_weighted_projection.py` → `generate_london_rail_cartogram.py` (use `git mv` so rename detection works). In the same commit, update any other repo references (the existing README mentions the file; `RM-2` will rewrite the README in detail, but at minimum keep the build instructions runnable).
2. Update the script to load `data/uk_lad_boundaries.geojson` (filtered to `E09*`) and `data/tfl_gtfs.zip` instead of MTA/NYC equivalents. Drop the Staten Island Ferry constants.
3. Compute the unioned GLA outline (reuse the same approach as BUILD-2; ideally factor out a small shared helper into a module if the duplication gets ugly, otherwise tolerate duplication for now).
4. Change the warp loop so it operates on the *single* unioned outline rather than per-borough.
5. After the warped outline is rendered, draw the original 33 borough polygons (post-warp transformation) on top at ~25% opacity as a graticule layer.
6. Update the output path constant from `output/nyc_subway_weighted_projection.svg` to `output/london_rail_cartogram.svg`.
7. Render stations outside the GLA at full opacity (per Q18, static piece uses full opacity for outsiders — different from the interactive map).
8. Update the legend/footer text in the SVG to read "London — Tube, DLR, Tram, Clippers, Woolwich Ferry, Cable Car" or similar honest summary.

**Verification:**

- `python3 generate_london_rail_cartogram.py` runs end-to-end.
- `output/london_rail_cartogram.svg` exists. Open it in a browser; a recognisable distorted London silhouette is visible, with faint borough internal lines.
- `git log --follow generate_london_rail_cartogram.py` shows the file history including the original NYC commits (rename detection worked).

**Files:** `generate_london_rail_cartogram.py` (renamed from `generate_nyc_subway_weighted_projection.py`), possibly a shared helper module

**Acceptance criteria:** Static SVG produces a warped London outline with borough graticule; file renamed cleanly; output filename matches.

---

### [ ] **RM-1: Delete NYC-specific data files** | **Size: S** | **Deps: BUILD-1, BUILD-2, SVG-1** *(can only delete after all consumers swapped)*

**Problem:** After Phase 2 + 3 + 6 swaps, the old NYC data files are unreferenced. Deleting them prevents confusion and reduces repo size.

**What to do:**

1. Confirm `git grep -nE "mta_gtfs_subway|borough_boundaries\.geojson|cb_2024_us_county_500k|parks_open_space|parks_properties|street_centerline|subway_stations\.json|osm_major_streets\.json"` produces matches only for files about to be deleted or for historical commit messages (not in source). If any source file still references one of these, fix that first.
2. Delete:
   - `data/mta_gtfs_subway.zip`
   - `data/borough_boundaries.geojson` (NYC; replaced by `uk_lad_boundaries.geojson`)
   - `data/cb_2024_us_county_500k.zip`
   - `data/parks_open_space.geojson`
   - `data/parks_properties.geojson`
   - `data/street_centerline.geojson`
   - `data/subway_stations.json`
   - `data/osm_major_streets.json` — **only if** an updated London streets/parks pipeline has fetched London data; otherwise leave this file and add a TODO. (The PRD's data-source decision was OSM for both streets and parks. If you've kept the same filename and re-fetched, leave the file; if you've moved to a new filename, delete the old.)
3. Run `python3 build_commute_site_data.py && python3 generate_london_rail_cartogram.py` to confirm nothing broke.

**Verification:**

- `ls data/` shows only London-relevant files.
- Both build scripts run end-to-end.
- `git status` shows the expected deletions and no untracked files.

**Files:** Multiple deletions in `data/`

**Acceptance criteria:** No NYC data files remain; both build scripts succeed.

---

### [ ] **RM-2: Update README for London** | **Size: S** | **Deps: all prior tasks**

**Problem:** `README.md` describes the NYC project, references NYC URLs, NYC file paths, MTA data, the upstream's Desktop paths, etc. Rewrite for London.

**What to do:**

1. Replace the title, intro paragraph, and live-site URL.
2. Update "What The Project Uses" to: GLA borough boundaries (ONS), TfL GTFS (Transitland), OSM streets + parks, TfL OSI interchanges, TfL Stations.csv.
3. Update the static-SVG instructions to reference `generate_london_rail_cartogram.py` and the new output filename.
4. Update the Cloudflare Worker section: the URL is `https://ldn.connoradams.co.uk/`, no path prefix, deploy via `pnpm run deploy`.
5. Remove the Desktop-path references in the project layout section (`/Users/primaryuser/Desktop/nyc-projection/`) — these were stale upstream paths. Replace with repo-relative paths.
6. Update Current App Behavior bullets: "search for London postcodes and addresses", "display a Zone 1 in 30 min reachability score", and otherwise preserve the existing list.
7. Add a brief note about manual rebuild cadence (Q16) and the soft-launched scope (Overground + Elizabeth deferred).
8. Update attribution: ONS, TfL, OSM, Transitland, Iconmonstr (if still used), and a note that the project is forked from `AntCas/nyc-cartogram`.

**Verification:**

- Read the README top-to-bottom; every URL, file path, and command works as documented.
- `git grep -nE "NYC|nyc|MTA|mta|castrio|Staten Island" README.md` only matches places where mentioning NYC is intentional (e.g. the upstream attribution line).

**Files:** `README.md`

**Acceptance criteria:** README accurately describes the London project; no stale NYC instructions remain.

---

## Dependency Graph

```text
CC-1 (worker/HTML scaffold) ───┬── UI-3 (postcode search)
                                └── UI-4 (about scope note)

CC-2 (stage data) ──┬── BUILD-1 (GTFS swap) ──┬── BUILD-3 (wait calibration)
                    │                          ├── BUILD-4 (OSI interchanges)
                    │                          └── SCO-1 (zone enrichment) ── SCO-2 (Zone 1 score)
                    └── BUILD-2 (boroughs) ───┬── UI-1 (neighbourhoods)
                                              ├── UI-2 (outside-GLA opacity)
                                              └── SVG-1 (static SVG port)

BUILD-1, BUILD-2, SVG-1 ─── RM-1 (delete NYC data) ─── RM-2 (README)
```

## Priority Order

**Phase 1 — Foundation (parallel-safe):**

- CC-1, CC-2

**Phase 2 — Build pipeline data swap:**

- BUILD-1, BUILD-2 (both depend on CC-2 only; can run in either order)

**Phase 3 — Model adaptations:**

- BUILD-3 (after BUILD-1)
- BUILD-4 (after BUILD-1, CC-2)

**Phase 4 — Score:**

- SCO-1 (after BUILD-1, CC-2)
- SCO-2 (after SCO-1)

**Phase 5 — UI polish (most are parallel-safe):**

- UI-1 (after BUILD-2)
- UI-2 (after BUILD-2)
- UI-3 (after CC-1)
- UI-4 (after CC-1)

**Phase 6 — Static SVG + cleanup:**

- SVG-1 (after BUILD-2, BUILD-4)
- RM-1 (after BUILD-1, BUILD-2, SVG-1)
- RM-2 (last)
