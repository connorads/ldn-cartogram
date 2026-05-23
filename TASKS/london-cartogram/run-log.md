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

## 2026-05-23T00:21:34Z | BUILD-4 | done

- **Commit:** e02436d
- **Verification:** `python3 build_commute_site_data.py` completed and printed `OSI edges loaded: 304`, `OSI unmatched station names (0): none`, `Tram unmatched station names (0): none`; generated graph has `136` fixed interchange edges; Bank ↔ Monument is `1.5` min each way and Hammersmith H&C → Hammersmith Dist/Picc is `2.0` min; Playwright loaded `http://localhost:8000/site/` with zero console errors.
- **Surprises:** TfL OSI times are tenths of minutes; many OSI rows target out-of-scope National Rail, Overground, Elizabeth line, or other stations and are reported separately from unmatched in-scope names.

## 2026-05-23T00:28:06Z | SCO-1 | done

- **Commit:** a725305
- **Verification:** `python3 build_commute_site_data.py` completed and printed `Zone-tagged stations: 319/359` and `Unmatched LUL/DLR zone stations (0): none`; output check printed `with zones: 319 / 359`; spot checks: Oxford Circus `[1]`, Bank `[1]`, Abbey Road DLR `[2, 3]`, Cutty Sark DLR `[2, 3]`.
- **Surprises:** TfL station zone values use both `+` and `/` as multi-zone separators, so parsing now handles both.

## 2026-05-23T00:35:59Z | SCO-2 | done

- **Commit:** d17537a
- **Verification:** `python3 build_commute_site_data.py` completed and printed `Zone 1 reachability denominator: 69 LUL/DLR stations within 30 min threshold`; JSON check found denominator `69`, threshold `30`, and `zone1ReachabilityScore` on all `15,271` cells; `git grep -nE "60[ -]min|60 minute" -- site/` returned no matches; Chromium loaded `http://localhost:8000/site/?origin=51.51768,-0.08224` and rendered Liverpool Street as `67 / 69` (`97%`), then loaded `?origin=51.65151,-0.14906` and rendered Cockfosters as `0 / 69`.
- **Surprises:** `playwright-cli` could not launch the installed Chrome because that binary rejected one of Playwright's launch flags, so browser smoke verification used headless Chromium directly against the same local HTTP server.

## 2026-05-23T00:46:18Z | UI-1 | done

- **Commit:** 4d3be8d
- **Verification:** `python3 build_commute_site_data.py` completed; JSON check found `20` labels, projected label points, and `0` borough label keys; local HTTP screenshots at `http://localhost:8000/site/` and `?origin=51.51768,-0.08224` showed neighbourhood labels on unwarped and warped maps with no borough-name labels.
- **Surprises:** Central London labels needed cartographic nudges from their literal centroids, plus a small text-size reduction, to stay readable at the default viewport.

## 2026-05-23T00:53:48Z | UI-2 | done

- **Commit:** e40a488
- **Verification:** `python3 build_commute_site_data.py` completed; JSON check found `343` inside-GLA stations, `16` outside-GLA stations, Stanmore/Cockfosters/Upminster inside, Amersham/Chesham outside, `34` outside route segments, `0` outside station references in cell access, and Zone 1 denominator still `69`; local HTTP screenshots showed outside route tails dimmed while the GLA network stayed full strength.
- **Surprises:** `playwright-cli` still could not launch the installed Chrome, so visual verification used headless Chromium screenshots directly.

## 2026-05-23T00:58:59Z | UI-3 | done

- **Commit:** 59ec7c1
- **Verification:** `node --check site/app.js` passed; direct Postcodes.io checks returned `SW1A 1AA` near `51.501,-0.1416` and outcode `E14` near `51.5062,-0.0182`; local browser automation showed `SW1A 1AA` called only `/postcodes/SW1A1AA`, `E14` called only `/outcodes/E14`, `Hampstead` called only bounded Nominatim and pinned near Hampstead Underground, and fake postcode `ZZ99 9ZZ` fell through from Postcodes.io 404 to bounded Nominatim.
- **Surprises:** `playwright-cli` still could not launch the installed Chrome; UI verification used Playwright Core directly with `/snap/bin/chromium`.
