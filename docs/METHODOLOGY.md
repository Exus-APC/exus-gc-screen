# Grid Connection Screening — Methodology

**Screen first, then let the result choose the deliverable.**

1. **Viability screen.** Pull the DNO heatmap position (GridDataUK for a fast visual read;
   the operator's open data / `substation_screen.py` for the authoritative figures). Capture firm
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

**GridDataUK** (griddata.uk) — cross-DNO aggregator; fast consolidated visual read
(hierarchy, queue, fault, make/break). Login for numeric fields. Good first look for any GB site.

**GB DNO open data (authoritative, free) — use the operator for the site's licence area:**

| DNO group | Licence area(s) | Open-data portal | Platform | Capacity / heat-map resource |
|---|---|---|---|---|
| **Northern Powergrid** (NPg) | North East, Yorkshire | `northernpowergrid.opendatasoft.com` | ODS | Heat Map Data – Substation Areas (`heatmapsubstationareas`); Network Availability Heat Maps; ECR; Appendix G. LTDS Appendix 5 primary. |
| **National Grid Electricity Distribution** (NGED) | East Mids, West Mids, South West, South Wales | `connecteddata.nationalgrid.co.uk` | CKAN | Network Opportunity & Development Map; Network Capacity dataset; ECR; DFES. |
| **UK Power Networks** (UKPN) | East, London, South East | `ukpowernetworks.opendatasoft.com` | ODS | Network Infrastructure & Usage Map (NIUM); Primary Substation Headroom; DFES NSHR; ECR. |
| **SP Energy Networks** (SPEN) | SP Distribution (S/Central Scotland), SP Manweb (Merseyside, Cheshire, N Wales) | `spenergynetworks.opendatasoft.com` | ODS | Capacity Heatmaps Information Model SPD / SPM; ECR; LTDS CIM. |
| **Scottish & Southern** (SSEN) | SHEPD (N Scotland), SEPD (S Central England) | `data.ssen.co.uk` | CKAN | Generation Availability & Network Capacity map + heat-map spreadsheets (GSP/BSP ratings, fault level, contracted/quoted gen); ECR; LTDS; NeRDA. |
| **Electricity North West** (ENWL) | North West England | `electricitynorthwest.opendatasoft.com` | ODS | GSP / BSP / Primary Capacity Heatmap datasets; downloadable Heatmap Tool (xlsx); GSP Connection Queue; ECR. |

> **Tool note:** four of six (NPg, UKPN, SPEN, ENWL) run on the **Opendatasoft** platform, so
> `substation_screen.py` can extend to them with the same Explore API v2.1 pattern — add each
> base URL + dataset ids to `DNO_ENDPOINTS` and call with `--dno <key>`. NGED (CKAN) and SSEN
> (`data.ssen.co.uk`) use different APIs and need their own handler. Confirm dataset ids on the
> first live run with `--debug`.

**NESO / NGET** — TEC register, ETYS, GSP transmission constraints for the upstream gate (all DNOs).

> All figures are **indicative** — verify with the DNO before any connection decision.

## Worked precedent — Harmire Bridge (EXR-GC-2026-HARMIRE)
NPg 66/20/0.4 kV, Barnard Castle. Firm 28.0 MVA; gen HR 0.0 MW (Amber); demand HR 14.4 MW;
fault 5.2 kA vs 9.2 kA break. Queue 13 MW accepted / 2.4 MW connected across 8 projects,
dominated by a consented 12.8 MW PV scheme that consumes the firm gen headroom.
→ **CONDITIONAL** (firm export NO; live routes: demand-led/BESS, sub-5 MW). Deliverable: one-pager.
