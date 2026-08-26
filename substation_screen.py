#!/usr/bin/env python3
"""
substation_screen.py  —  Exus Grid Connection Screening tool
============================================================

Reusable "substation + upstream chain" lookup + go/no-go screen.

Pulls the authoritative, FREE, no-login DNO open data (Northern Powergrid
Opendatasoft Explore API v2.1) for a named primary substation, assembles the
screen inputs (firm capacity, generation/demand headroom, fault level, queue,
upstream hierarchy) and applies the Exus screening rubric to return a
GO / CONDITIONAL / CONSTRAINED verdict and the matching deliverable.

Why NPg open data rather than griddata.uk?
    griddata.uk is an excellent quick visual layer, but the numeric fields are
    behind a login. The same figures originate from NPg LTDS Appendix 5 /
    the NPg heatmap datasets, which are free and unauthenticated — so an
    automatable tool should hit those directly.

USAGE
    python3 substation_screen.py "Harmire Bridge" --target-mw 5
    python3 substation_screen.py "Harmire Bridge" --debug          # dump raw fields to confirm schema on first run
    python3 substation_screen.py --self-test                       # verify rubric logic offline (no network)
    python3 substation_screen.py "Harmire Bridge" --json out.json  # machine-readable for Power Automate / PowerBI

NOTES
  * NPg-specific for now. Other DNOs expose equivalent Opendatasoft / NGED
    Connected Data portals — add their base URL + dataset ids to DNO_ENDPOINTS.
  * On the FIRST live run against a dataset, use --debug and confirm the field
    names below (DNOs rename columns between refreshes). Extraction is
    deliberately fuzzy (substring match) to survive minor renames.
"""
import argparse, json, sys, urllib.parse, urllib.request

# --------------------------------------------------------------------------- #
# DNO endpoints (extend as coverage grows)
# --------------------------------------------------------------------------- #
DNO_ENDPOINTS = {
    "npg": {
        "base": "https://northernpowergrid.opendatasoft.com/api/explore/v2.1",
        "datasets": {
            "heatmap":    "heatmapsubstationareas",     # firm cap, gen/demand headroom, fault level
            "sites":      "substation_sites_list",       # voltages, transformer ratings
            "appendix_g": "gsp-appendix-g-information",   # GSP contracted position / constraint
            # ECR dataset id — confirm on first run with --debug (portal: /pages/ecr/)
            "ecr":        "embedded-capacity-register",
        },
    },
}

# Candidate field-name fragments (lowercased substring match), most-specific first
FIELDS = {
    "name":            ["substation_name", "sitename", "site_name", "name"],
    "firm_capacity":   ["firm_capacity", "firmcapacity"],
    "gen_headroom":    ["generation_headroom", "gen_headroom", "genheadroom"],
    "demand_headroom": ["demand_headroom", "demandheadroom"],
    "fault_3ph":       ["fault_level", "faultlevel", "3ph", "shortcircuit"],
    "break_rating":    ["break_rating", "breakrating"],
    "gen_rag":         ["generation_rag", "gen_rag", "rag"],
    "voltage":         ["voltage"],
    "bsp":             ["bsp", "bulk_supply"],
    "gsp":             ["gsp", "grid_supply"],
}

def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "exus-screen/1.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())

def ods_query(base, dataset, where, limit=20):
    q = urllib.parse.urlencode({"where": where, "limit": limit})
    return _get(f"{base}/catalog/datasets/{dataset}/records?{q}")

def _pick(record, key):
    """Fuzzy-extract a field from an ODS record dict by candidate substrings."""
    for frag in FIELDS[key]:
        for k, v in record.items():
            if frag in k.lower():
                return v
    return None

def _num(x):
    try:
        return float(str(x).replace(",", "").split()[0])
    except (TypeError, ValueError, IndexError):
        return None

# --------------------------------------------------------------------------- #
# Rubric  (mirrors saved Exus screening workflow)
# --------------------------------------------------------------------------- #
def apply_rubric(inp, target_mw):
    fg   = inp.get("gen_headroom_mw")
    rag  = (inp.get("gen_rag") or "").lower()
    dh   = inp.get("demand_headroom_mw")
    f3   = inp.get("fault_3ph_ka")
    brk  = inp.get("break_rating_ka")
    gsp_constrained = inp.get("gsp_constrained")   # True / False / None(unknown)

    fault_ok = (f3 is not None and brk is not None and f3 < brk)
    firm_export_ok = (
        fg is not None and fg >= target_mw
        and rag in ("green", "amber")
        and gsp_constrained is not True
        and fault_ok
    )
    # routes that keep a sub-target site alive
    demand_route = (dh is not None and dh >= target_mw)
    sub5_route   = (target_mw <= 5.0 and fault_ok)
    nonfirm_route = inp.get("non_firm_available", None) is True

    if firm_export_ok:
        verdict, deliverable = "GO", "Full BCC-style feasibility report (Exus .docx)"
        firm_export = "YES"
    elif demand_route or sub5_route or nonfirm_route:
        verdict = "CONDITIONAL"
        deliverable = "One-page viability screen (HTML + A4 PDF) + flag the live route"
        firm_export = "NO"
    else:
        verdict = "CONSTRAINED"
        deliverable = "One-page viability screen (HTML + A4 PDF)"
        firm_export = "NO"

    routes = []
    if firm_export_ok: routes.append("firm export")
    if nonfirm_route:  routes.append("non-firm / ANM")
    if demand_route:   routes.append(f"demand-led / BESS (demand HR {dh} MW)")
    if sub5_route:     routes.append("sub-5 MW (CMP446)")
    return {
        "verdict": verdict, "firm_export": firm_export,
        "deliverable": deliverable, "fault_ok": fault_ok,
        "live_routes": routes or ["none within target"],
    }

# --------------------------------------------------------------------------- #
def screen(site, dno="npg", target_mw=5.0, debug=False):
    ep = DNO_ENDPOINTS[dno]
    where = f'"{site}"'                     # ODS full-text search
    out = {"site": site, "dno": dno.upper(), "target_mw": target_mw}

    hm = ods_query(ep["base"], ep["datasets"]["heatmap"], where)
    recs = hm.get("results", [])
    if debug:
        print("---- RAW heatmap fields ----")
        print(json.dumps(recs[0] if recs else {}, indent=2)[:2000])
    if not recs:
        out["error"] = "No heatmap record matched. Try a shorter/simpler name or --debug."
        return out
    r = recs[0]
    out.update({
        "matched_name":       _pick(r, "name"),
        "voltage":            _pick(r, "voltage"),
        "firm_capacity_mva":  _num(_pick(r, "firm_capacity")),
        "gen_headroom_mw":    _num(_pick(r, "gen_headroom")),
        "demand_headroom_mw": _num(_pick(r, "demand_headroom")),
        "fault_3ph_ka":       _num(_pick(r, "fault_3ph")),
        "break_rating_ka":    _num(_pick(r, "break_rating")),
        "gen_rag":            _pick(r, "gen_rag"),
        "bsp":                _pick(r, "bsp"),
        "gsp":                _pick(r, "gsp"),
    })
    out["screen"] = apply_rubric(out, target_mw)
    return out

def render(o):
    if o.get("error"):
        return f"{o['site']}: {o['error']}"
    s = o["screen"]
    L = [
        f"  SITE            {o.get('matched_name') or o['site']}  ({o['dno']})",
        f"  Voltage         {o.get('voltage')}",
        f"  Upstream        {o.get('bsp')} (BSP) -> {o.get('gsp')} (GSP)",
        f"  Firm capacity   {o.get('firm_capacity_mva')} MVA",
        f"  Gen headroom    {o.get('gen_headroom_mw')} MW    (RAG: {o.get('gen_rag')})",
        f"  Demand headroom {o.get('demand_headroom_mw')} MW",
        f"  Fault 3ph       {o.get('fault_3ph_ka')} kA  vs break {o.get('break_rating_ka')} kA  (ok: {s['fault_ok']})",
        f"  Target export   {o['target_mw']} MW",
        "  " + "-"*46,
        f"  VERDICT         {s['verdict']}   (firm export: {s['firm_export']})",
        f"  Live routes     {', '.join(s['live_routes'])}",
        f"  Deliverable     {s['deliverable']}",
    ]
    return "\n".join(L)

# --------------------------------------------------------------------------- #
def self_test():
    """Offline verification of the rubric against known Harmire Bridge values."""
    harmire = {
        "matched_name": "Harmire Bridge", "dno": "NPG", "voltage": "20kV",
        "firm_capacity_mva": 28.0, "gen_headroom_mw": 0.0, "demand_headroom_mw": 14.4,
        "fault_3ph_ka": 5.2, "break_rating_ka": 9.2, "gen_rag": "Amber",
        "bsp": "Toronto", "gsp": "Spennymoor GSP", "target_mw": 5.0, "site": "Harmire Bridge",
    }
    harmire["screen"] = apply_rubric(harmire, 5.0)
    print(render(harmire))
    s = harmire["screen"]
    assert s["verdict"] == "CONDITIONAL", s
    assert s["firm_export"] == "NO", s
    assert "demand-led / BESS (demand HR 14.4 MW)" in s["live_routes"], s
    # A hypothetical clear GO
    go = dict(harmire, gen_headroom_mw=30.0, gen_rag="green")
    go["screen"] = apply_rubric(go, 5.0)
    assert go["screen"]["verdict"] == "GO", go["screen"]
    # A hard CONSTRAINED (no demand HR, target > 5, no fault headroom)
    hard = dict(harmire, demand_headroom_mw=0.0, fault_3ph_ka=9.9, break_rating_ka=9.2)
    hard["screen"] = apply_rubric(hard, 20.0)
    assert hard["screen"]["verdict"] == "CONSTRAINED", hard["screen"]
    print("\nself-test: PASSED")

def main():
    ap = argparse.ArgumentParser(description="Exus substation grid-connection screen")
    ap.add_argument("site", nargs="?", help="Substation name, e.g. \"Harmire Bridge\"")
    ap.add_argument("--dno", default="npg", choices=list(DNO_ENDPOINTS))
    ap.add_argument("--target-mw", type=float, default=5.0, help="Target export capacity (MW)")
    ap.add_argument("--json", metavar="PATH", help="Write full result as JSON")
    ap.add_argument("--debug", action="store_true", help="Dump raw dataset fields")
    ap.add_argument("--self-test", action="store_true", help="Run offline rubric checks")
    a = ap.parse_args()
    if a.self_test:
        self_test(); return
    if not a.site:
        ap.error("provide a substation name, or use --self-test")
    o = screen(a.site, a.dno, a.target_mw, a.debug)
    print(render(o))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(o, f, indent=2)
        print(f"\n[written] {a.json}")

if __name__ == "__main__":
    main()
