# Exus GC Screen

Reusable **grid-connection screening** tool for the Exus Renewables Development Team.
Given a primary substation, it pulls the authoritative, free, no-login DNO open data,
assembles the screen inputs (firm capacity, generation & demand headroom, fault level,
queue, upstream BSP→GSP chain) and applies the Exus rubric to return a
**GO / CONDITIONAL / CONSTRAINED** verdict and the matching deliverable.

This repo is the **single source of truth** for the screening logic. Site chats in the
Claude Project reference the raw URL below; the same file runs in your own Python
environment and in Power Automate.

## Quick start

```bash
python3 substation_screen.py "Harmire Bridge" --target-mw 5
python3 substation_screen.py "Harmire Bridge" --debug     # confirm dataset field names (first live run)
python3 substation_screen.py --self-test                  # offline rubric check, no network
python3 substation_screen.py "Harmire Bridge" --json harmire.json
```

No install needed — standard library only (Python 3.9+).

## The rubric

| Verdict | Condition | Deliverable |
|---|---|---|
| **GO** | firm gen headroom ≥ target MW · RAG Green (or Amber ≥ target) · GSP not hard-constrained · fault < break rating | Full BCC-style feasibility report (Exus `.docx`) |
| **CONDITIONAL** | firm gen < target, but a live route exists: non-firm/ANM, demand-led/BESS on demand headroom, or sub-5 MW CMP446 | One-page screen (HTML + A4 PDF) + flag the route |
| **CONSTRAINED** | firm gen ≈ 0 or fully allocated to a consented queue, no route within target | One-page screen (HTML + A4 PDF) |

## Data source

Uses the **Northern Powergrid** Opendatasoft Explore API v2.1 (free, no auth):
`heatmapsubstationareas`, `substation_sites_list`, `gsp-appendix-g-information`, and the
Embedded Capacity Register. These carry the same figures GridDataUK shows behind its login
(origin: NPg LTDS Appendix 5). GridDataUK remains the fast visual layer.

> All figures are **indicative** — verify with the DNO before any connection decision.

## First-run field mapping (important)

DNOs rename dataset columns between refreshes. Field extraction is deliberately fuzzy
(substring match, see `FIELDS` in the script), but on the **first live run** use `--debug`
to dump the raw record and confirm the column names resolve. Adjust the `FIELDS`
fragments if a value comes back `None`.

## Extending to other DNOs

The tool is NPg-only today. Add other operators to `DNO_ENDPOINTS` with their base URL and
dataset ids (NGED, SSEN, SPEN and ENWL all publish equivalent Connected-Data / Opendatasoft
portals), then call with `--dno <key>`.

## Power Automate / PowerBI

`--json PATH` writes a machine-readable result. In Power Automate: HTTP (run the script via
a hosted runner or replicate the API call) → Parse JSON → write to Dataverse/SharePoint;
point PowerBI at that table for a scheduled portfolio sweep.

## Files

- `substation_screen.py` — the tool
- `docs/METHODOLOGY.md` — the screening method & rubric (mirror of the Project hub)
- `docs/project_instructions.md` — paste-ready text for the Claude Project instructions field
