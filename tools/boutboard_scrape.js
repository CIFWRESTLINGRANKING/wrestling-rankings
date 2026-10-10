// boutboard_scrape.js - pull every varsity + HS girls bout of a Boutboard
// tournament as a TSV in the tournaments/ format. Run in a browser tab.
//
// STEP 1  Open https://www.boutboard.com/results?tournamentId=<ID>
//         and paste PART A into the console / javascript tool.
// STEP 2  Click any round heading (e.g. "Finals"), then a division under it,
//         so the page makes one results request (PART A captures its headers).
// STEP 3  Run PART B. It returns {counts, tsv}. Save tsv as
//         tournaments/YYYY-MM-DD_<slug>.tsv with the '# key: value' header
//         lines (event, date, source, style, level) on top.
//
// Uses only the page's own public results requests (same calls the results
// page makes), paginated 500 at a time.

// ---------------- PART A ----------------
if (!window.__bbPatched) {
  const of = window.fetch;
  window.__bbReq = [];
  window.fetch = async function (input, init) {
    try {
      const url = typeof input === "string" ? input : input.url;
      if (/rest\/v1\/match/.test(url) && (!init || !init.method || init.method === "GET")) {
        const h = {};
        const hh = (init && init.headers) || input.headers;
        if (hh) { if (hh.forEach) hh.forEach((v, k) => (h[k] = v)); else Object.assign(h, hh); }
        window.__bbReq.push({ url, h });
      }
    } catch (e) {}
    return of.apply(this, arguments);
  };
  window.__bbPatched = true;
}

// ---------------- PART B ----------------
async function bbScrape() {
  const r = window.__bbReq[window.__bbReq.length - 1];
  if (!r) return "no captured request - do STEP 2 first";
  // keep the page's select/joins; drop its round/division/order filters
  const page = async (start) => {
    const u = new URL(r.url);
    for (const k of [...u.searchParams.keys()])
      if (!["select", "tournament", "bout.topCompetitor", "bout.bottomCompetitor"].includes(k))
        u.searchParams.delete(k);
    u.searchParams.set("order", "matchNumber.asc");
    const res = await fetch(u.toString(), {
      headers: { ...r.h, "Range-Unit": "items", Range: `${start}-${start + 499}` },
    });
    return res.json();
  };
  const all = [];
  for (let s = 0; ; s += 500) { const j = await page(s); all.push(...j); if (j.length < 500) break; }

  const VARSITY = /(hs boys|varsity|^high ?school boys$)/i;
  const GIRLS = /(hs girls|high ?school girls|girls varsity)/i;
  const EXCLUDE = /(frosh|soph|jv|junior varsity|middle|ms\b|\d+u\b)/i;
  const CODE = { "Dec": "D", "Fall": "F", "Major Dec": "M", "Tech Fall": "T", "Forfeit": "FF",
                 "Med For": "MF", "INJ": "INJ", "DQ": "DQ" };
  const divs = {};
  const lines = [];
  for (const m of all) {
    const dn = m.competition?.weightclass?.division?.name || "";
    divs[dn] = (divs[dn] || 0) + 1;
    if (EXCLUDE.test(dn)) continue;
    const gender = GIRLS.test(dn) ? "girls" : VARSITY.test(dn) ? "boys" : null;
    if (!gender) continue;
    for (const b of m.bout || []) {
      const t = b.topCompetitor, o = b.bottomCompetitor;
      if (!t || !o || !b.winner) continue;
      const topWon = b.winner === t.id;
      const w = topWon ? t : o, l = topWon ? o : t;
      const ws = topWon ? m.topScore : m.bottomScore, ls = topWon ? m.bottomScore : m.topScore;
      const clean = (x) => String(x ?? "").replace(/[\t\n]/g, " ").trim();
      lines.push([gender, parseInt(m.competition.weightclass.name, 10), m.matchNumber, m.round,
                  m.isConsolation ? 1 : 0, CODE[b.winType] || b.winType, `${ws}-${ls}`,
                  w.firstName, w.lastName, w.teamentry?.name, l.firstName, l.lastName,
                  l.teamentry?.name].map(clean).join("\t"));
    }
  }
  const hdr = "gender\tweight\tmatch\tround\tcons\tresult\tscore\tw_first\tw_last\tw_team\tl_first\tl_last\tl_team";
  return { divisions_seen: divs, bouts_kept: lines.length, tsv: hdr + "\n" + lines.join("\n") + "\n" };
}
// window.__bbResult = await bbScrape();
