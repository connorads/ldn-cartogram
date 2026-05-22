# Run Log

Entries appended by each iteration of the loop. One entry per completed or blocked task.

## 2026-05-22T23:45:53Z | CC-1 | done

- **Commit:** 9b630c2
- **Verification:** `git grep -nE "nyc|castrio|/nyc/|PATH_PREFIX" -- src site wrangler.jsonc` returned no matches; `pnpm run dev` served `http://localhost:8787/`; Playwright loaded the root URL with title `London Commute POV | Tube & Rail Cartogram` and zero console errors after generating ignored `site/data/commute_map_data.json`.
- **Surprises:** `site/social.png` contained a random lowercase `nyc` byte sequence, so it was regenerated as a temporary London placeholder for the literal grep gate.

## 2026-05-22T23:52:25Z | CC-2 | done

- **Commit:** 0edb2b4
- **Verification:** all six staged files are non-empty; `data/tfl_osi.ods` opens as an ODS zip; `data/tfl_gtfs.zip` lists the expected GTFS files; `data/uk_lad_boundaries.geojson` exposes ONS `LAD24CD`/`LAD24NM` properties; generated TfL station CSV has 473 rows, 396 with zones.
- **Surprises:** TfL's documented station CSV URL now returns 404, so the station CSV was generated from current TfL StopPoint mode responses; the ONS BFC GeoJSON is 190 MB and is tracked with Git LFS.
