#!/usr/bin/env python3
"""
substation_screen.py  —  Exus Grid Connection Screening tool  (multi-DNO)
=========================================================================

Reusable "substation + upstream chain" lookup + go/no-go screen.

Pulls authoritative, FREE, no-login DNO open data, assembles the screen inputs
(firm capacity, generation/demand headroom, fault level, queue, upstream
hierarchy) and applies the Exus screening rubric to return a
GO / CONDITIONAL / CONSTRAINED verdict and the matching deliverable.

DNO COVERAGE
    Opendatasoft portals (live query supported):  npg, ukpn, spen, enwl
    CKAN portals (documented, not auto-queried):  nged, ssen
    The four Opendatasoft operators share the same Explore API v2.1, so the
    same code screens all of them; you only change --dno.

USAGE
    python3 substation_screen.py "Harmire Bridge" --dno npg --target-mw 5
    python3 substation_screen.py "East Hertford" --dno ukpn --target-mw 10
    python3 substation_screen.py --dno enwl --list-datasets            # discover dataset ids for a DNO
    python3 substation_screen.py "Some Primary" --dno spen --debug     # dump raw record + dataset choice
    python3 substation_screen.py --self-test                           # offline rubric check (no network)
    python3 substation_screen.py "Harmire Bridge" --dno npg --json out.json

FIRST LIVE RUN (per DNO)
    Dataset ids differ between operators and change between refreshes. On the
    first run against a new DNO, the tool AUTO-DISCOVERS the heatmap dataset by
    searching that portal's catalogue. To see/confirm the choice, use
    --list-datasets (lists candidate datasets) and --debug (shows the chosen
    dataset + raw fields). Once confirmed, you can hard-set it in DNO_ENDPOINTS
    ["<dno>"]["dataset"] to skip discovery.
"""
import argparse, json, sys, urllib.parse, urllib.request

# --------------------------------------------------------------------------- #
# DNO endpoints
#   platform "ods"  -> Opendatasoft Explore API v2.1 (auto-query supported)
#   platform "ckan" -> CKAN portal (listing supported; screening not auto-wired)
#   dataset: hard-set heatmap dataset id, or None to auto-discover on first run
# --------------------------------------------------------------------------- #
DNO_ENDPOINTS = {
    "npg":  {"name": "Northern Powergrid",
             "base": "https://northernpowergrid.opendatasoft.com/api/explore/v2.1",
             "platform": "ods", "dataset": "heatmapsubstationareas"},
    "ukpn": {"name": "UK Power Networks",
             "base": "https://ukpowernetworks.opendatasoft.com/api/explore/v2.1",
             "platform": "ods", "dataset": None},
    "spen": {"name": "SP Energy Networks",
             "base": "https://spenergynetworks.opendatasoft.com/api/explore/v2.1",
             "platform": "ods", "dataset": None},
    "enwl": {"name": "Electricity North West",
             "base": "https://electricitynorthwest.opendatasoft.com/api/explore/v2.1",
             "platform": "ods", "dataset": None},
    # ---- non-Opendatasoft: documented, use the portal or add a resource id ----
    "nged": {"name": "National Grid Electricity Distribution",
             "base": "https://connecteddata.nationalgrid.co.uk",
             "platform": "ckan", "dataset": None},
    "ssen": {"name": "Scottish & Southern (SSEN)",
             "base": "https://data.ssen.co.uk",
             "platform": "ckan", "dataset": None},
}

# Keywords used to auto-discover the substation heatmap dataset in an ODS catalogue.
# Scored most-specific first.
DISCOVER_KEYWORDS = [
    ("heatmapsubstation", 6), ("substationheatmap", 6), ("heatmapsubstationareas", 7),
    ("heat map", 4), ("heatmap", 4), ("headroom", 3),
    ("primary", 2), ("substation", 2), ("capacity", 1),
]

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
    req = urllib.request.Request(url, headers={"User-Agent": "exus-screen/2.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())

# --------------------------------------------------------------------------- #
# Opendatasoft helpers
# --------------------------------------------------------------------------- #
def ods_catalog(base, limit=100):
    """Return [(dataset_id, title), ...] from an ODS Explore v2.1 catalogue."""
    url = f"{base}/catalog/datasets?" + urllib.parse.urlencode({"limit": limit})
    data = _get(url)
    out = []
    for d in data.get("results", []):
        did = d.get("dataset_id") or d.get("datasetid") or ""
        title = ""
        metas = d.get("metas") or {}
        if isinstance(metas, dict):
            default = metas.get("default") or {}
            title = default.get("title") or ""
        out.append((did, title))
    return out

def rank_datasets(catalog, keywords=DISCOVER_KEYWORDS):
    """Score catalogue entries by keyword hits; return [(score, id, title), ...] desc."""
    ranked = []
    for did, title in catalog:
        hay = f"{did} {title}".lower()
        score = sum(w for kw, w in keywords if kw in hay)
        if score > 0:
            ranked.append((score, did, title))
    ranked.sort(reverse=True)
    return ranked

def resolve_dataset(ep, debug=False):
    """Return the heatmap dataset id for an ODS DNO (hard-set or discovered)."""
    if ep.get("dataset"):
        return ep["dataset"], []
    catalog = ods_catalog(ep["base"])
    ranked = rank_datasets(catalog)
    if debug:
        print("---- dataset discovery (top candidates) ----")
        for score, did, title in ranked[:8]:
            print(f"  [{score:>2}] {did}   {title}")
    if not ranked:
        return None, catalog
    return ranked[0][1], [r[1] for r in ranked[:8]]

def ods_query(base, dataset, term, limit=20):
    q = urllib.parse.urlencode({"where": f'"{term}"', "limit": limit})
    return _get(f"{base}/catalog/datasets/{dataset}/records?{q}")

# --------------------------------------------------------------------------- #
# CKAN helpers (listing only)
# --------------------------------------------------------------------------- #
def ckan_search(base, q, rows=50):
    """Return [(name, title), ...] from a CKAN portal package search."""
    url = f"{base}/api/3/action/package_search?" + urllib.parse.urlencode({"q": q, "rows": rows})
    data = _get(url)
    res = (data.get("result") or {}).get("results", [])
    return [(p.get("name", ""), p.get("title", "")) for p in res]

# --------------------------------------------------------------------------- #
def _pick(record, key):
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
    gsp_constrained = inp.get("gsp_constrained")

    fault_ok = (f3 is not None and brk is not None and f3 < brk)
    firm_export_ok = (
        fg is not None and fg >= target_mw
        and rag in ("green", "amber")
        and gsp_constrained is not True
        and fault_ok
    )
    demand_route  = (dh is not None and dh >= target_mw)
    sub5_route    = (target_mw <= 5.0 and fault_ok)
    nonfirm_route = inp.get("non_firm_available", None) is True

    if firm_export_ok:
        verdict, deliverable, firm_export = "GO", "Full BCC-style feasibility report (Exus .docx)", "YES"
    elif demand_route or sub5_route or nonfirm_route:
        verdict, firm_export = "CONDITIONAL", "NO"
        deliverable = "One-page viability screen (HTML + A4 PDF) + flag the live route"
    else:
        verdict, firm_export = "CONSTRAINED", "NO"
        deliverable = "One-page viability screen (HTML + A4 PDF)"

    routes = []
    if firm_export_ok: routes.append("firm export")
    if nonfirm_route:  routes.append("non-firm / ANM")
    if demand_route:   routes.append(f"demand-led / BESS (demand HR {dh} MW)")
    if sub5_route:     routes.append("sub-5 MW (CMP446)")
    return {"verdict": verdict, "firm_export": firm_export, "deliverable": deliverable,
            "fault_ok": fault_ok, "live_routes": routes or ["none within target"]}

# --------------------------------------------------------------------------- #
def screen(site, dno="npg", target_mw=5.0, debug=False):
    ep = DNO_ENDPOINTS[dno]
    out = {"site": site, "dno": dno.upper(), "dno_name": ep["name"], "target_mw": target_mw}

    if ep["platform"] == "ckan":
        out["error"] = (f"{ep['name']} uses a CKAN portal ({ep['base']}), not auto-queried by this "
                        f"tool. Screen from the portal / GridDataUK, or run --list-datasets to find "
                        f"the resource, then add its id. See docs/METHODOLOGY.md.")
        return out

    dataset, _cands = resolve_dataset(ep, debug=debug)
    if not dataset:
        out["error"] = (f"Could not resolve a heatmap dataset for {dno}. Run "
                        f"`--dno {dno} --list-datasets` and set DNO_ENDPOINTS['{dno}']['dataset'].")
        return out
    out["dataset"] = dataset

    hm = ods_query(ep["base"], dataset, site)
    recs = hm.get("results", [])
    if debug:
        print("---- RAW heatmap fields ----")
        print(json.dumps(recs[0] if recs else {}, indent=2)[:2000])
    if not recs:
        out["error"] = (f"No record matched '{site}' in {dataset}. Try a shorter name, confirm the "
                        f"dataset with --list-datasets, or --debug.")
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

def list_datasets(dno, contains=None):
    ep = DNO_ENDPOINTS[dno]
    print(f"# {ep['name']}  ({dno})  [{ep['platform'].upper()}]  {ep['base']}")
    try:
        if ep["platform"] == "ods":
            cat = ods_catalog(ep["base"])
        else:
            cat = ckan_search(ep["base"], contains or "capacity heatmap")
    except Exception as e:
        print(f"  [error] {e}")
        return
    rows = [(i, t) for (i, t) in cat if not contains or contains.lower() in f"{i} {t}".lower()]
    for did, title in sorted(rows):
        print(f"  {did}   {title}")
    print(f"  ({len(rows)} datasets)")

def render(o):
    if o.get("error"):
        return f"{o.get('dno_name', o['dno'])} — {o['site']}: {o['error']}"
    s = o["screen"]
    return "\n".join([
        f"  SITE            {o.get('matched_name') or o['site']}  ({o['dno']} · {o['dno_name']})",
        f"  Dataset         {o.get('dataset')}",
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
    ])

# --------------------------------------------------------------------------- #
def self_test():
    """Offline verification of the rubric + discovery ranking (no network)."""
    harmire = {"matched_name": "Harmire Bridge", "dno": "NPG", "voltage": "20kV",
        "firm_capacity_mva": 28.0, "gen_headroom_mw": 0.0, "demand_headroom_mw": 14.4,
        "fault_3ph_ka": 5.2, "break_rating_ka": 9.2, "gen_rag": "Amber",
        "bsp": "Toronto", "gsp": "Spennymoor GSP", "target_mw": 5.0, "site": "Harmire Bridge",
        "dno_name": "Northern Powergrid", "dataset": "heatmapsubstationareas"}
    harmire["screen"] = apply_rubric(harmire, 5.0)
    print(render(harmire))
    s = harmire["screen"]
    assert s["verdict"] == "CONDITIONAL" and s["firm_export"] == "NO", s
    assert "demand-led / BESS (demand HR 14.4 MW)" in s["live_routes"], s
    # clear GO
    go = dict(harmire, gen_headroom_mw=30.0, gen_rag="green"); go["screen"] = apply_rubric(go, 5.0)
    assert go["screen"]["verdict"] == "GO", go["screen"]
    # hard CONSTRAINED
    hard = dict(harmire, demand_headroom_mw=0.0, fault_3ph_ka=9.9, break_rating_ka=9.2)
    hard["screen"] = apply_rubric(hard, 20.0)
    assert hard["screen"]["verdict"] == "CONSTRAINED", hard["screen"]
    # discovery ranking picks the substation heatmap over noise
    mock = [("enwl-gsp-heatmap", "GSP Heatmap"),
            ("heatmapsubstationareas", "Heat Map Data - Substation Areas"),
            ("outages", "Live outages")]
    top = rank_datasets(mock)[0][1]
    assert top == "heatmapsubstationareas", top
    print("\nself-test: PASSED  (rubric + discovery ranking)")

def main():
    ap = argparse.ArgumentParser(description="Exus substation grid-connection screen (multi-DNO)")
    ap.add_argument("site", nargs="?", help='Substation name, e.g. "Harmire Bridge"')
    ap.add_argument("--dno", default="npg", choices=list(DNO_ENDPOINTS))
    ap.add_argument("--target-mw", type=float, default=5.0, help="Target export capacity (MW)")
    ap.add_argument("--json", metavar="PATH", help="Write full result as JSON")
    ap.add_argument("--debug", action="store_true", help="Dump dataset discovery + raw fields")
    ap.add_argument("--list-datasets", action="store_true", help="List datasets for --dno (discovery)")
    ap.add_argument("--contains", metavar="TEXT", help="Filter --list-datasets by text")
    ap.add_argument("--self-test", action="store_true", help="Run offline checks (no network)")
    a = ap.parse_args()
    if a.self_test:
        self_test(); return
    if a.list_datasets:
        list_datasets(a.dno, a.contains); return
    if not a.site:
        ap.error("provide a substation name, or use --list-datasets / --self-test")
    o = screen(a.site, a.dno, a.target_mw, a.debug)
    print(render(o))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(o, f, indent=2)
        print(f"\n[written] {a.json}")

if __name__ == "__main__":
    main()
