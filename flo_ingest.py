#!/usr/bin/env python3
"""
FloArena ingester  --  runs in GitHub Actions (open internet), NOT in the chat sandbox.
=======================================================================================
Pulls bracket / bout results for our checkpoint tournaments straight from Flo's
public API host (floarena-api.flowrestling.org) and writes them as engine-ready
bouts. No browser, no carank, no manual step.

WHY THIS RUNS IN THE ACTION, NOT IN CHAT
  The assistant's fetch tool can't send request headers and can only retrieve URLs
  a search already surfaced; its container can't reach flowrestling.org at all.
  A GitHub Action has none of those limits -- it can hit any endpoint with any header.

TWO-STEP BRINGUP (because Flo's exact paths must be confirmed against the live API):
  1. Run with  MODE=discover  once. It probes a set of candidate endpoints for one
     event and prints which return JSON + a sample of their keys. Paste that output
     back and the parser below gets finalized to the real shape.
  2. Run with  MODE=ingest    on the schedule. Writes flo_bouts.json.

Usage:
    MODE=discover EVENT=15175762 python flo_ingest.py     # confirm endpoints
    MODE=ingest python flo_ingest.py                      # produce flo_bouts.json
"""
import os, json, time, urllib.request, urllib.error

API = "https://floarena-api.flowrestling.org"

# Our checkpoint events on Flo. Numeric coreEventIds confirmed from Flo's own QR links;
# the three UUID-only events get their numeric id resolved during discovery.
EVENTS = {
    # name                   coreEventId (numeric)   arena UUID (fallback to resolve)
    "Sonora TOC":            ("14591584", None),
    "Sierra Nevada Classic": ("14610918", None),
    "Five Counties":         ("14591592", None),
    "Temecula Valley B4B":   ("15175762", None),
    "CIT - Sam Boyd":        ("14591598", None),
    "Doc Buchanan":          (None, "a23ff975-3978-4f38-8d49-574f6a4a10ad"),
    "Reno TOC":              (None, "3977de53-74eb-4968-b8d1-8db898f83d2f"),
    "Tim Brown Memorial":    (None, "c12478f4-1fd9-4dd9-b24f-a7c6c1384509"),
}

# Candidate endpoint shapes to probe in discover mode. Flo has reorganized this API
# more than once, so we test several and keep whichever returns JSON.
CANDIDATES = [
    "/core-event/{id}",
    "/core-event/{id}/divisions",
    "/core-event/{id}/weight-classes",
    "/core-event/{id}/bouts",
    "/core-event/{id}/placements",
    "/api/experience/web/core-event/{id}",
    "/api/experience/web/core-event/{id}/brackets",
    "/event/{id}",
    "/event/{id}/results",
]

HEADERS = {
    "User-Agent": "ca-wrestling-rankings/1.0 (+github action)",
    "Accept": "application/json",
}

def get(path):
    url = API + path
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            ct = r.headers.get("Content-Type", "")
            body = r.read().decode("utf-8", "replace")
            if "json" in ct or body[:1] in "[{":
                return json.loads(body), url
            return None, url            # not JSON (HTML shell / image)
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code}, url
    except Exception as e:
        return {"_error": str(e)}, url

def discover(event_id):
    print(f"# probing endpoints for event {event_id}\n")
    for shape in CANDIDATES:
        data, url = get(shape.format(id=event_id))
        if isinstance(data, dict) and ("_http_error" in data or "_error" in data):
            print(f"  [skip {data}]  {url}")
        elif data is None:
            print(f"  [non-json ]  {url}")
        else:
            top = list(data.keys())[:12] if isinstance(data, dict) else f"list[{len(data)}]"
            print(f"  [JSON OK  ]  {url}\n             keys/shape: {top}")
        time.sleep(0.3)
    print("\n# paste the [JSON OK] lines back to finalize the parser")

# ---- FINALIZED ONCE DISCOVERY CONFIRMS THE SHAPE -----------------------------
# Maps Flo's win-type strings to our engine method keys + style. Adjust the
# left-hand strings to whatever Flo actually returns (seen in discovery sample).
WIN_TYPE = {
    "Fall": "fall", "Pin": "fall",
    "Tech Fall": "tech", "TF": "tech",
    "Major Decision": "major", "MD": "major",
    "Decision": "decision", "Dec": "decision", "SV": "decision",
    "Forfeit": "forfeit", "FFT": "forfeit", "Default": "default",
    "Medical Forfeit": "med_forfeit", "Injury Default": "med_forfeit",
}

def normalize_bouts(event_name, raw):
    """TODO: fill in once discovery shows the real field names.
    Must yield dicts: {event_id, day, weight, winner_name, winner_team,
    loser_name, loser_team, result, style}."""
    out = []
    # placeholder -- structure depends on confirmed endpoint
    return out

def ingest():
    all_bouts = []
    for name, (num, uuid) in EVENTS.items():
        eid = num or uuid
        data, url = get(f"/core-event/{eid}/bouts")   # finalize path after discovery
        if not isinstance(data, (list, dict)) or (isinstance(data, dict) and data.get("_http_error")):
            print(f"!! {name}: could not fetch ({url}) -> {data}")
            continue
        bouts = normalize_bouts(name, data)
        print(f"   {name}: {len(bouts)} bouts")
        all_bouts += bouts
    json.dump(all_bouts, open("flo_bouts.json", "w"), indent=2)
    print(f"\nwrote flo_bouts.json ({len(all_bouts)} bouts)")

if __name__ == "__main__":
    mode = os.environ.get("MODE", "discover")
    if mode == "discover":
        discover(os.environ.get("EVENT", "15175762"))
    else:
        ingest()
