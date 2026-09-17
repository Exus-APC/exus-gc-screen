# Grid Connection Screening — Methodology

**Screen first, then let the result choose the deliverable.**

1. **Viability screen.** Pull the DNO heatmap position (GridDataUK for a fast visual read;
   NPg open data / `substation_screen.py` for the authoritative figures). Capture firm
   capacity, generation & demand headroom, RAG, fault level, queue, and the upstream
   BSP→GSP chain.
2. **Apply the rubric** → GO / CONDITIONAL / CONSTRAINED (see README table).
3. **Produce the matching deliverable** — full report on a GO, one-pager otherwise.
4. **Log the site** in the index and record the verdict to Project memory.

## Conventions
- Deliverable ref: `EXR-GC-YYYY-<SITE>` (e.g. `EXR-GC-2026-HARMIRE`).
- Site chat title: `GC Screen — <Site> (EXR-GC-YYYY-<SITE>)`.
- Files: `<REF>_Viability_Screen_R0.pdf/.html`, `<REF>_Feasibility_Report_R0.docx`.

## Data sources
- **GridDataUK** (griddata.uk) — fast consolidated visual (hierarchy, queue, fault, make/break); login for numeric fields.
- **Northern Powergrid open data** — authoritative & free (heatmap, sites list, Appendix G, ECR); LTDS Appendix 5 primary.
- **NESO / NGET** — TEC, ETYS, GSP transmission constraints for the upstream gate.

## Worked precedent — Harmire Bridge (EXR-GC-2026-HARMIRE)
NPg 66/20/0.4 kV, Barnard Castle. Firm 28.0 MVA; gen HR 0.0 MW (Amber); demand HR 14.4 MW;
fault 5.2 kA vs 9.2 kA break. Queue 13 MW accepted / 2.4 MW connected across 8 projects,
dominated by a consented 12.8 MW PV scheme that consumes the firm gen headroom.
→ **CONDITIONAL** (firm export NO; live routes: demand-led/BESS, sub-5 MW). Deliverable: one-pager.
