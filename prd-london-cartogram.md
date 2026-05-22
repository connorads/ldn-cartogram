# PRD: London Cartogram

**Date:** 2026-05-22

---

## Problem Statement

### What problem are we solving?

The upstream NYC commute-time cartogram is a fun, sharable, locally-resonant piece of urban data art. No equivalent exists for London. This fork ports it.

### Why now?

Author lives in London. The codebase is already named `ldn-cartogram` and partway-iterated. The Transitland TfL feed and TfL open datasets are mature enough to make a port tractable in days.

### Who is affected?

- **Primary user:** the author (personal project / portfolio).
- **Secondary users:** Londoners who'll find a warp-cartogram of their city fun to play with and share. Transit hobbyists. Urbanist Twitter.

### Cost of inaction

None material. This is a hobby project. The cost of *over-investment* (e.g. blocking on Overground / Elizabeth Line data) is higher than the cost of shipping a known-incomplete first cut.

---

## Proposed Solution

### Overview

Replace the NYC subway commute cartogram with a London Tube + DLR + Tram + ferry + cable-car commute cartogram, served at `ldn.connoradams.co.uk`. Same interactive concept (pin an origin, see commute times warp the map) and same static SVG output, adapted to London's geography, modes, and fare-zone-based reachability framing.

### User Experience

Identical interaction model to the NYC version:

- Click or tap to choose an origin; click again to pin.
- Toggle warp and heatmap layers.
- Search by postcode or address.
- Share a deep link to a chosen origin.
- See a single headline metric: % of Zone 1 LUL/DLR stations reachable in 30 minutes.

Click-to-pin remains the centrepiece interaction; search is a fallback.

### Design Considerations

- Visual identity carries over from the NYC version (same layout, controls, share affordances).
- Accessibility parity with upstream — no regression. No new audit committed.
- Mobile drawer pattern already iterated by author; preserve it.

---

## End State

When this PRD is complete, the following will be true:

- [ ] The site at `ldn.connoradams.co.uk` shows an interactive London commute cartogram, served from a simplified Cloudflare Worker at the apex of that subdomain.
- [ ] The map covers the 33 GLA boroughs as the warp domain, with stations outside the GLA rendered at reduced opacity for context.
- [ ] Commute times route through Tube, DLR, Tram, Thames Clippers, Woolwich Ferry, and Emirates Air Line, using per-agency wait calibration so infrequent modes are not over-recommended.
- [ ] The headline metric is "% of Zone 1 LUL/DLR stations reachable in 30 minutes" from the chosen origin.
- [ ] Postcode search (via `postcodes.io`) and biased Nominatim address search both work.
- [ ] The static SVG cartogram produces a recognisable warped London silhouette with faint borough internal lines.
- [ ] ~20 curated neighbourhood labels replace the NYC borough labels.
- [ ] The About section honestly notes that Overground and Elizabeth Line are not yet modelled.
- [ ] No NYC-specific copy, asset, URL, or hardcoded constant remains in user-visible places.

---

## Acceptance Criteria

### Feature: Interactive commute map

- [ ] Loading the root URL renders the warped London map with no origin pinned.
- [ ] Hovering / tapping a map cell shows a transient origin preview; tapping pins it; tapping again or pressing escape unpins.
- [ ] A pinned origin produces a heatmap of commute times to every routable station in the model.
- [ ] Travel times account for walking access, board wait, ride time, and OSI / transfer penalties.
- [ ] Per-agency wait constants apply: LUL/DLR/TCL ~4 min; CV (Clipper) ~18 min; WFF (Ferry) ~12 min; CAB (Cable Car) ~8 min. Tunable post-build if distribution looks wrong.
- [ ] Sharing a pinned view produces a deep link that restores the same origin and view state on load.

### Feature: Zone 1 reachability score

- [ ] The headline number reads "X% of central London reachable in 30 min" (or equivalent wording) where X is the percentage of Zone 1 LUL/DLR stations reachable from the pinned origin within 30 minutes.
- [ ] With no origin pinned, the score area shows an explanatory placeholder.
- [ ] Station→zone assignment is derived by joining TfL `Stations.csv` to GTFS `stops.txt` by station name, with a small manual reconciliation file for mismatches.

### Feature: Postcode and address search

- [ ] Typing a valid UK postcode resolves via `postcodes.io` and pins that point.
- [ ] Typing free-text (e.g. "Hampstead") resolves via Nominatim biased to a Greater London viewbox and pins the top result.
- [ ] The search placeholder communicates both inputs are supported.

### Feature: Static SVG cartogram

- [ ] Running the build script produces an SVG warped on the unioned GLA outline.
- [ ] Internal borough boundaries render as a faint graticule layer over the warped shape.
- [ ] Stations outside the GLA render at full opacity in the static SVG (visual contrast against the warp).
- [ ] No NYC borough labels remain; ~20 curated neighbourhood labels appear instead.

### Feature: Worker and deploy

- [ ] The Worker serves assets from `ldn.connoradams.co.uk/*` with no path prefix.
- [ ] All NYC-only worker logic (path stripping, redirect rewriting, diagnostic header) is removed.
- [ ] `wrangler.jsonc` routes correctly and the worker name is `ldn-cartogram`.

### Feature: Outside-GLA station handling

- [ ] Interactive map: stations outside the GLA polygon render at ~40% opacity with their route lines visible but no warp/heatmap influence.
- [ ] Static SVG: same stations and route shapes render at full opacity.

### Feature: Honest scope copy

- [ ] The About section contains a one-line note acknowledging Overground and Elizabeth Line are not yet modelled, with intent to backfill.
- [ ] The OG description mentions "Tube and rail" (not the full TfL network), avoiding implied promises.
- [ ] No "coming soon" banner clutter on the map itself.

---

## Durable Architectural Decisions

These do not depend on implementation order.

- **Hosting:** `ldn.connoradams.co.uk` apex. Single-zone Cloudflare Worker, simplified to a static-asset passthrough. No path prefix.
- **GTFS source:** Transitland `f-transport~for~london` feed (Tube + DLR + Tram + Thames Clippers + Woolwich Ferry + Cable Car). Manual rebuild cadence; no scheduled job.
- **Geography source:** ONS Open Geography 33-borough polygons (LAD codes starting `E09`). Union for warp domain; individual polygons retained for graticule.
- **Auxiliary data:** OSM Overpass for major streets and parks (`leisure=park`); same parsing approach as the NYC version.
- **Interchange model:** TfL Out-of-Station Interchange (OSI) ODS file as authoritative interchange edges. Hand-list of ~4 tram interchanges as supplement. Existing walking-radius proximity as third-tier fallback.
- **Headline metric:** "% of Zone 1 LUL/DLR stations reachable in 30 minutes from origin". Denominator excludes Clipper piers, Cable Car stations, ferry terminals.
- **Search:** `postcodes.io` for UK postcode pattern matches; Nominatim biased to Greater London viewbox for free-text.
- **Rename policy:** UI strings, filenames, JSON keys, worker name and routes refer to London + rail. Internal helper / variable names stay generic (e.g. `extract_boroughs`, `station_complex`) where the term is still accurate. Staten Island Ferry constants deleted, not commented out.
- **Static SVG identity:** the iconic recognisable shape is the GLA outline as a whole, not individual borough silhouettes. Warp operates on the union; borough internals are decoration.
- **Coordinate system:** WGS84 throughout. No conversion to British National Grid.

---

## Modules

Described by responsibility, not file location.

- **Transit feed loader.** Reads the Transitland TfL zip; produces stops, routes, trips, calendar, stop_times in memory. Filters to in-scope agencies (configurable; default is all six).
- **Station–zone joiner.** Loads TfL `Stations.csv`, attaches a `zone` attribute to GTFS stops by name match, with a small reconciliation table for mismatches. Provides "is Zone 1?" predicate to the scoring module.
- **Interchange model.** Parses the TfL OSI ODS file into a graph of inter-station walking edges with asymmetric times. Adds a hand-coded tram interchange supplement. Replaces the NYC "complex" abstraction conceptually but reuses the existing routing graph wiring.
- **Routing graph builder.** Combines on-network station-to-station travel times (from `stop_times`) with interchange edges, applies per-agency board-wait calibration, produces a static graph the front-end can shortest-path against from any cell origin.
- **Reachability score.** Given a pinned origin's travel-time map, computes the percentage of Zone 1 LUL/DLR stations reachable within 30 minutes. Returns a single number + the contributing/excluded station counts.
- **Boundary geometry.** Loads the 33 LAD polygons, unions them for the warp domain, retains the originals for graticule rendering. Computes the bounding box used by the warp grid.
- **Cartogram warp.** Distance-based warp parameterised by station accessibility. For the static SVG it operates on the unioned outline. For the interactive map it operates on a regular grid bounded by the unioned outline.
- **Outside-GLA renderer.** Renders stations and route shapes that lie outside the GLA outline. Reduced opacity on the interactive map; full opacity on the static SVG. These stations do not participate in the warp or reachability score.
- **Neighbourhood label set.** A small curated JSON file: ~20 entries of `{name, lon, lat}` covering well-known London places (Soho, Shoreditch, Brixton, Canary Wharf, Stratford, Wimbledon, etc.). Author-maintained.
- **Postcode-aware search.** Client-side detection of UK postcode pattern; routes either to `postcodes.io` or to a Greater-London-biased Nominatim query. Single search input, smart routing under the hood.
- **Worker.** Static-asset passthrough at the root of `ldn.connoradams.co.uk`. ~10 lines. No path-prefix logic; no redirect rewriting; no diagnostic header.
- **About section copy.** Honest note about Overground/Elizabeth Line scope; updated attribution and source links (ONS, TfL OSI, Transitland, OSM).

---

## Testing Strategy

The upstream NYC repo has no automated tests. This port does not add a test suite either — the cost outweighs the value for a single-author hobby project. Verification is manual and structured.

- **Build smoke test.** Running both Python build scripts succeeds end-to-end, producing a non-empty SVG and a non-empty `commute_map_data.json`. Run by hand after each meaningful change.
- **Routing sanity checks.** A small in-repo notes file lists 5–10 known origin→destination journeys with expected travel-time ranges (e.g. "King's Cross → Canary Wharf via Jubilee from Westminster: 18–28 min"). Eyeball the score against these after each build.
- **Visual regression.** Open the site locally before deploying; check warp aesthetic, hovers, pins, share links, mobile drawer, search.
- **Production smoke test.** Post-deploy, hit the root URL, pin one origin, view a Zone 1 score, share a link.

Prior art: the upstream project's manual-verification workflow. No CI is added.

---

## Technical Context

### Existing patterns

- **Build-once, serve-static.** Python scripts produce assets committed into `site/`; the runtime is purely static. Keep this.
- **Single composite JSON data bundle.** Front-end loads one JSON file at startup. Keep this; rename the file if helpful.
- **Cloudflare Worker fronting `site/` assets.** Stays — simplified to a passthrough.
- **Client-side Nominatim usage with no server proxy.** Stays. Add `postcodes.io` as a sibling.

### System dependencies

- Cloudflare Workers + custom domain on `connoradams.co.uk`. Subdomain `ldn` must be created in the Cloudflare zone before deploy.
- Transitland API key (Hobbyist tier) for refreshing the GTFS zip when needed.
- `postcodes.io` (no key, no cost).
- OpenStreetMap Nominatim (no key; respect rate limits and user-agent policy).
- Node + `pnpm` for Wrangler tooling; Python 3 standard library for build scripts. No new packages.

### Data model changes

- New shape: `stops` enriched with `zone: int | null`.
- New artefact: a small `tfl_station_zone_reconciliation.json` mapping names that don't match cleanly between Transitland `stops.txt` and TfL `Stations.csv`.
- New artefact: `osi_edges.json`, derived from the TfL OSI ODS file at build time.
- New artefact: `neighbourhood_labels.json`, the ~20-entry curated label set.
- Removed: any NYC-specific constants (Staten Island Ferry route id, terminals, travel minutes).

---

## Boundary Tiers

### Always (conventions to follow)

- British English in user-visible copy.
- Conservative diff against the upstream NYC structure where doing so does not cost user-facing quality; this keeps a future rebase against `AntCas/nyc-cartogram` feasible.
- WGS84 lon/lat throughout. No silent CRS conversions.
- Manual verification before each deploy.

### Ask first (decisions needing human input)

- Adding any new transit mode beyond the six already agreed (e.g. National Rail, buses).
- Changing the headline metric from Zone 1 in 30 min.
- Switching off the manual rebuild cadence (e.g. introducing a cron / GitHub Actions job).
- Introducing a new vendor dependency or service (e.g. Mapbox, OS Names API).
- Altering the share-link URL format in a backwards-incompatible way.

### Never (must not be touched)

- The author's other unrelated config or sites — this PRD covers only the `ldn-cartogram` repo and its `ldn.connoradams.co.uk` subdomain.
- The upstream `castrio.me/nyc` deployment — out of scope, owned by AntCas.
- Adding test infrastructure / CI for the sake of it without a concrete failure mode it'd prevent.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Transitland feed schema changes or feed is removed | Low | High | Author keeps a downloaded snapshot of the working feed; build script's GTFS parser is the same as upstream MTA, so any future swap to UK2GTFS-generated GTFS is a drop-in. |
| TfL OSI ODS format changes | Low | Medium | Parse defensively (named columns, not positional); commit a snapshot of the working file. |
| Zone 1 in 30 min produces an ugly distribution (e.g. outer zones flatlining at 0%) | Medium | Medium | Threshold is a single constant. Tune to 45 min after first build if needed; bump back later. |
| Cartogram warp on the unioned GLA outline produces a less-iconic silhouette than expected (no recognisable Thames bend, etc.) | Medium | Low | The Thames itself isn't a borough boundary; keep the Thames as an explicit overlay layer if it gets lost in the warp. |
| Trailing stations outside GLA look broken at the visual edge | Medium | Low | Reduced opacity (40%) hides clipping artefacts; tune after first build. |
| Overground/Elizabeth Line omission attracts comment | High | Low | About-section honesty note. Accept the criticism; backfill is a known follow-up. |
| Postcode pattern regex misclassifies edge cases (e.g. partial postcodes like `SW1`) | Low | Low | Fall back to Nominatim on `postcodes.io` 404. |

---

## Alternatives Considered

### Schedule data source: UK2GTFS pipeline now

- **Description:** Run the R-based `itsleeds/UK2GTFS` pipeline to convert TfL TransXChange + ATOC CIF into a single GTFS covering all five TfL rail modes including Overground and Elizabeth Line.
- **Pros:** Complete network in scope from day one. No "coming soon" copy needed.
- **Cons:** Adds R to the toolchain; pipeline is more complex; weekly source refresh; risk of blocking launch on tooling issues.
- **Decision:** Rejected for v1. Backfill candidate.

### Schedule data source: TfL Unified API pre-compute

- **Description:** Hit the TfL Journey Planner API for all O/D pairs in a one-shot precompute.
- **Pros:** Authoritative TfL data; covers all modes.
- **Cons:** ~360k pairs at 500 rpm → ~12 hour run; rate-limit risk; outputs aren't GTFS-shaped, so the pipeline diverges from upstream more.
- **Decision:** Rejected. Not a clean fit for the existing pipeline.

### Geography: travelcard zones instead of boroughs

- **Description:** Use Zones 1–9 polygons as the cartogram domain.
- **Pros:** Native to London, fare-relevant, matches the headline metric (Q12).
- **Cons:** No clean published polygon dataset; derived polygons from stations have ambiguous edges; loses the "city outline" silhouette that makes the static SVG work.
- **Decision:** Rejected. Use 33-borough union for geometry; zones live only inside the score.

### Static SVG: per-borough warp of all 33

- **Description:** Preserve the upstream NYC structure of warping each borough independently.
- **Cons:** Most London boroughs are not recognisable by silhouette; the visual story collapses into noise.
- **Decision:** Rejected in favour of unioned-outline warp + internal borders as graticule.

### Mode scope: all six modes from the Transitland feed

- **Description:** Initially considered filtering to LUL+DLR+TCL only for cleanliness.
- **Decision:** Accepted all six modes after weighing the per-agency wait-calibration fix (one constants block, ~10 minutes) against the artificial-line cost of excluding modes the user technically can take. Wait calibration prevents over-recommendation of Clipper/Cable routes.

### Deploy path: subpath like `connoradams.co.uk/london`

- **Description:** Mirror upstream's `castrio.me/nyc` shape on the author's domain.
- **Decision:** Rejected. Root deploy eliminates the path-prefix worker logic. Subdomain `ldn.connoradams.co.uk` is cleaner.

### Banner: dismissible "Overground + Elizabeth coming soon"

- **Description:** Persistent dismissible banner at the top of the site.
- **Decision:** Rejected. Banners apologise; they age badly; an honest sentence in the About section reaches the audience who'd notice the omission anyway.

---

## Non-Goals (v1)

Explicitly out of scope:

- **Overground and Elizabeth Line in the commute model.** Soft-launch deferral; honest copy in the About section. Backfill candidate via UK2GTFS or equivalent.
- **National Rail beyond Overground / Elizabeth Line.** Not in the project ambition.
- **Buses.** Explosive graph size for limited additional accuracy in the warped-cartogram visual.
- **Real-time service data.** Schedules only.
- **Mobile-native app.** Web only.
- **Multi-city generalisation.** This repo is London; no generic city abstraction.
- **Automated tests / CI.** Manual verification only.
- **Scheduled data refresh.** Manual rebuild on demand.
- **A11y audit / WCAG conformance work** beyond what the upstream already supplies.
- **Custom basemap tiles.** Keep the existing render-from-vectors approach.

---

## Open Questions

- Final per-agency wait constants (Clipper ~18, Ferry ~12, Cable ~8 are starting estimates; calibrate post-first-build).
- The exact 20-ish neighbourhood label list and their coordinates.
- Whether the Thames needs a dedicated overlay layer to remain visible after the warp.
- Timing and approach for the Overground + Elizabeth Line backfill (revisit UK2GTFS; no commitment yet).
- Whether to keep the upstream's GitHub link in the footer, replace it with this fork's URL, or list both.
