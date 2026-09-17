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
python3 substation_screen.py "Harmire Bridge" --dno npg  --target-mw 5
python3 substation_screen.py "East Hertford"  --dno ukpn --target-mw 10
python3 substation_screen.py --dno enwl --list-datasets      # discover dataset ids for a DNO
python3 substation_screen.py "Some Primary" --dno spen --debug   # show chosen dataset + raw fields
python3 substation_screen.py --self-test                     # offline rubric + discovery check
python3 substation_screen.py "Harmire Bridge" --dno npg --json harmire.json
```

No install needed — standard library only (Python 3.9+).

## The rubric

| Verdict | Condition | Deliverable |
|---|---|---|
| **GO** | firm gen headroom ≥ target MW · RAG Green (or Amber ≥ target) · GSP not hard-constrained · fault < break rating | Full BCC-style feasibility report (Exus `.docx`) |
| **CONDITIONAL** | firm gen < target, but a live route exists: non-firm/ANM, demand-led/BESS on demand headroom, or sub-5 MW CMP446 | One-page screen (HTML + A4 PDF) + flag the route |
| **CONSTRAINED** | firm gen ≈ 0 or fully allocated to a consented queue, no route within target | One-page screen (HTML + A4 PDF) |

## DNO coverage

| `--dno` | Operator | Platform | Live query |
|---|---|---|---|
| `npg`  | Northern Powergrid | Opendatasoft | ✅ |
| `ukpn` | UK Power Networks | Opendatasoft | ✅ |
| `spen` | SP Energy Networks | Opendatasoft | ✅ |
| `enwl` | Electricity North West | Opendatasoft | ✅ |
| `nged` | National Grid Electricity Distribution | CKAN | ⚠️ documented (use portal / add resource id) |
| `ssen` | Scottish & Southern (SSEN) | CKAN | ⚠️ documented (use portal / add resource id) |

The four Opendatasoft operators share the same Explore API v2.1, so one code path screens
all of them — you only change `--dno`. NGED and SSEN publish via CKAN portals with a
different API; they are documented in `docs/METHODOLOGY.md` and return a guided message
rather than a silent failure. To wire one fully, find its resource with
`--dno <nged|ssen> --list-datasets` and add the id.

## Dataset discovery (first live run)

Dataset ids differ between operators and change between refreshes, so the tool
**auto-discovers** the substation heatmap dataset by searching the portal's catalogue
(keyword-scored, see `DISCOVER_KEYWORDS`). To confirm the choice:

```bash
python3 substation_screen.py --dno ukpn --list-datasets      # list candidates
python3 substation_screen.py "X Primary" --dno ukpn --debug  # show chosen dataset + raw record
```

Once confirmed, hard-set it to skip discovery next time:
`DNO_ENDPOINTS["ukpn"]["dataset"] = "<dataset-id>"`.
If a value comes back `None`, adjust the fuzzy `FIELDS` fragments for that operator's columns.

## Power Automate / PowerBI

`--json PATH` writes a machine-readable result. In Power Automate: HTTP (run the script via
a hosted runner or replicate the API call) → Parse JSON → write to Dataverse/SharePoint;
point PowerBI at that table for a scheduled portfolio sweep.

## Files

- `substation_screen.py` — the tool
- `docs/METHODOLOGY.md` — the screening method, rubric & GB DNO data-source table
- `docs/project_instructions.md` — paste-ready text for the Claude Project instructions field
