# Run Log

Entries appended by each iteration of the loop. One entry per completed or blocked task.

## 2026-05-22T23:45:53Z | CC-1 | done

- **Commit:** 095c800
- **Verification:** `git grep -nE "nyc|castrio|/nyc/|PATH_PREFIX" -- src site wrangler.jsonc` returned no matches; `pnpm run dev` served `http://localhost:8787/`; Playwright loaded the root URL with title `London Commute POV | Tube & Rail Cartogram` and zero console errors after generating ignored `site/data/commute_map_data.json`.
- **Surprises:** `site/social.png` contained a random lowercase `nyc` byte sequence, so it was regenerated as a temporary London placeholder for the literal grep gate.

## 2026-05-22T23:52:25Z | CC-2 | done

- **Commit:** aacd79a
- **Verification:** all six staged files are non-empty; `data/tfl_osi.ods` opens as an ODS zip; `data/tfl_gtfs.zip` lists the expected GTFS files; `data/uk_lad_boundaries.geojson` exposes ONS `LAD24CD`/`LAD24NM` properties; generated TfL station CSV has 473 rows, 396 with zones.
- **Surprises:** TfL's documented station CSV URL now returns 404, so the station CSV was generated from current TfL StopPoint mode responses; the ONS BFC GeoJSON is 190 MB and is tracked with Git LFS.

## 2026-05-22T23:56:28Z | BUILD-1 | done

- **Commit:** 1462301
- **Verification:** `python3 build_commute_site_data.py` completed and printed `Loaded 6 agencies, 19 routes, 74093 trips across 4 agencies, 359 stations`; spot-check found `Oxford Circus Underground Station`, `Bank DLR Station`, `Bank Underground Station`, `Stratford DLR Station`, and `Stratford Underground Station`; `git grep -n "mta_gtfs_subway" -- build_commute_site_data.py` returned no matches.
- **Surprises:** the staged Transitland feed has CV and WFF routes but no trips for those agencies; Transitland's current static GTFS URL now requires a token, so the staged feed could not be refreshed anonymously.

## 2026-05-23T00:06:14Z | BUILD-2 | done

- **Commit:** b0f455f
- **Verification:** `python3 build_commute_site_data.py` completed; output has `33` boroughs, `geography.outline`, `geography.boroughs`, and `landMask`; `python3 -c "import json; d=json.load(open('site/data/commute_map_data.json')); print(len(d.get('boroughs', d.get('geography', {}).get('boroughs', []))))"` prints `33`; `python3 -m http.server 8000` served `http://localhost:8000/site/`; Playwright loaded it with title `London Commute POV | Tube & Rail Cartogram`, status `Drag on the map to place an origin.`, and zero console errors; screenshot saved to `/tmp/ldn-cartogram-build2-loaded.png`.
- **Surprises:** ONS GeoJSON is EPSG:27700 and mixes Polygon/MultiPolygon geometries, so the build converts OSGB36 coordinates to WGS84 and normalises both geometry types; `/site/` local verification needed a localhost-only asset base while production remains root-relative.

## 2026-05-23T00:09:33Z | BUILD-3 | done

- **Commit:** b96e46e
- **Verification:** `git grep -nE "STATEN_ISLAND_FERRY|SIF" -- *.py` returned no matches; `python3 build_commute_site_data.py` completed; generated route waits include `CAB-London-Cable-Car: 8.0`, all `CV-*`: `18.0`, and `WFF-Woolwich-Ferry: 12.0`; Oxford Circus to `IFS Cloud Royal Docks` is `51.95` min versus `24.5` min to North Greenwich and `27.5` min to Canning Town.
- **Surprises:** none.
