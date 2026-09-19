"""Builds the single self-contained HTML decision report from
portfolio_sim_results.json. No new dependency: vanilla JS table sort + inline
SVG equity-curve sparklines, no CDN, no build step.
"""
from __future__ import annotations

import json

# Per-trade statistical verdicts from FINDINGS.md (deflate_check.py, §13) --
# hand-maintained here since it's a handful of qualitative facts, not derived
# data. This is what separates "high portfolio Sharpe" from "proven edge."
EDGE_VERDICT = {
    ("gap_reversion", "Mid", 20): ("CONFIRMED", "DSR 0.97, replicates 2020-22 AND 2023+ independently. The only proven edge in this project."),
    ("gap_reversion", "Small", 20): ("CONFIRMED", "DSR-adjacent (ranks #2), replicates 2020-22 AND 2023+ independently."),
    ("gap_reversion", "Large", 20): ("WEAK", "Passes pooled HAC-t but only the 2023+ sub-period actually clears it -- 2020-22 does not. Treat with more suspicion."),
}
DEFAULT_VERDICT = ("NOT PROVEN", "No per-trade statistical edge confirmed (HAC-t/DSR) -- a good portfolio Sharpe here likely reflects market beta (the tier drifting up while often invested), not a real signal. See FINDINGS.md §§13.")


def verdict_for(strategy: str, tier: str, hold_days: int) -> tuple[str, str]:
    return EDGE_VERDICT.get((strategy, tier, hold_days), DEFAULT_VERDICT)


def build(results_path: str, out_path: str, capital_sens_path: str | None = None) -> None:
    with open(results_path) as f:
        rows = json.load(f)
    for r in rows:
        tag, note = verdict_for(r["strategy"], r["tier"], r["hold_days"])
        r["edge_tag"] = tag
        r["edge_note"] = note
    rows.sort(key=lambda r: (r["sharpe"] if r["sharpe"] is not None else -999), reverse=True)
    data_json = json.dumps(rows)

    cap_rows = []
    if capital_sens_path:
        with open(capital_sens_path) as f:
            cap_rows = json.load(f)
        for r in cap_rows:
            tag, note = verdict_for(r["strategy"], r["tier"], r["hold_days"])
            r["edge_tag"] = tag
            r["edge_note"] = note
    cap_json = json.dumps(cap_rows)

    html = (HTML_TEMPLATE
            .replace("__DATA_JSON__", data_json)
            .replace("__CAP_DATA_JSON__", cap_json))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out_path} ({len(rows)} rows, {len(cap_rows)} capital-sensitivity rows)")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>US Swing Strategy Portfolio Report</title>
<style>
  :root {
    --bg: #0f1115; --panel: #171a21; --border: #2a2e38; --text: #e6e8ec; --muted: #9399a8;
    --green: #3ecf8e; --red: #ef5f6a; --amber: #e8b649; --accent: #5b9dff;
  }
  @media (prefers-color-scheme: light) {
    :root { --bg:#f6f7f9; --panel:#ffffff; --border:#e2e5ea; --text:#1a1d23; --muted:#5b6270;
            --green:#1f9e6a; --red:#c9414c; --amber:#a9750a; --accent:#2266d3; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 24px 16px 64px; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: var(--muted); font-size: 13px; margin-bottom: 20px; }
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; margin-bottom: 20px; }
  .panel h2 { font-size: 15px; margin: 0 0 10px; }
  .params { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
  .param { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; }
  .param .k { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }
  .param .v { font-size: 15px; font-weight: 600; margin-top: 2px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 8px 10px; color: var(--muted); font-weight: 600; cursor: pointer; user-select: none; white-space: nowrap; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--panel); }
  th:hover { color: var(--accent); }
  th.sorted::after { content: " \25BE"; }
  td { padding: 7px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  tr:hover td { background: rgba(91,157,255,0.06); }
  .tag { display:inline-block; padding:2px 8px; border-radius: 999px; font-size:11px; font-weight:700; letter-spacing:.02em; }
  .tag-confirmed { background: rgba(62,207,142,0.15); color: var(--green); }
  .tag-weak { background: rgba(232,182,73,0.15); color: var(--amber); }
  .tag-notproven { background: rgba(147,153,168,0.15); color: var(--muted); }
  .num-pos { color: var(--green); } .num-neg { color: var(--red); }
  .filters { display:flex; gap:8px; margin-bottom: 12px; flex-wrap: wrap; }
  .filters button { background: var(--bg); border:1px solid var(--border); color: var(--text); padding:6px 12px; border-radius:999px; font-size:12px; cursor:pointer; }
  .filters button.active { background: var(--accent); color:#fff; border-color: var(--accent); }
  .tablewrap { max-height: 640px; overflow: auto; border: 1px solid var(--border); border-radius: 8px; }
  .curves { display:grid; grid-template-columns: repeat(auto-fit, minmax(300px,1fr)); gap:14px; }
  .curve-card { background: var(--bg); border:1px solid var(--border); border-radius:8px; padding:10px 12px; }
  .curve-card .title { font-size:13px; font-weight:600; margin-bottom:2px; }
  .curve-card .meta { font-size:11px; color: var(--muted); margin-bottom:6px; }
  svg.curve { width:100%; height:70px; display:block; }
  .callout { border-left: 3px solid var(--amber); padding: 10px 14px; background: rgba(232,182,73,0.08); border-radius: 0 8px 8px 0; font-size: 13px; line-height:1.5; }
  .callout b { color: var(--amber); }
  footer { color: var(--muted); font-size: 12px; margin-top: 24px; }
  code { background: var(--bg); border:1px solid var(--border); border-radius:4px; padding:1px 5px; }
</style>
</head>
<body>

<h1>US Swing Strategy &mdash; Portfolio Simulation Report</h1>
<div class="sub">9 strategies &times; 4 cap tiers &times; 3 hold periods = 108 simulated accounts. Generated for decision-making, not a live recommendation.</div>

<div class="panel">
  <h2>Simulation parameters (same for every row below)</h2>
  <div class="params">
    <div class="param"><div class="k">Starting capital</div><div class="v">$5,000</div></div>
    <div class="param"><div class="k">Position sizing</div><div class="v">10 equal-weight slots (10% of current equity each)</div></div>
    <div class="param"><div class="k">Stop-loss</div><div class="v">None (tested, made results worse &mdash; see note below)</div></div>
    <div class="param"><div class="k">Profit target</div><div class="v">None (same reason)</div></div>
    <div class="param"><div class="k">Exit rule</div><div class="v">Fixed hold period (5, 10, or 20 trading days), whichever column</div></div>
    <div class="param"><div class="k">Trading cost</div><div class="v">10/20/35/150 bps round-trip by tier (Large/Mid/Small/Penny)</div></div>
    <div class="param"><div class="k">Slot conflicts</div><div class="v">Extra signals skipped when all 10 slots are full (no cherry-picking)</div></div>
  </div>
</div>

<div class="panel">
  <div class="callout">
    <b>Read this before the table.</b> A high portfolio Sharpe here does not by itself mean a real trading edge &mdash;
    it can also come from just being invested often in stocks that drift up anyway (market beta). Only
    <b>gap-down reversion (Mid/Small caps, 20-day hold)</b> has passed the separate, stricter per-trade statistical
    test (beats its own tier's base rate, survives deflation for every variant tried, replicates across two market
    regimes &mdash; see <code>FINDINGS.md</code> &sect;13). Every row is tagged accordingly:
    <span class="tag tag-confirmed">CONFIRMED</span> proven edge,
    <span class="tag tag-weak">WEAK</span> passes loosely but with caveats,
    <span class="tag tag-notproven">NOT PROVEN</span> good portfolio numbers with no confirmed underlying edge &mdash;
    treat those as "the market carried it," not "the strategy worked."
  </div>
</div>

<div class="panel">
  <h2>All 108 combinations</h2>
  <div class="filters" id="filters"></div>
  <div class="tablewrap">
    <table id="tbl">
      <thead><tr id="thead"></tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</div>

<div class="panel">
  <h2>Equity curves &mdash; top 6 by Sharpe</h2>
  <div class="curves" id="curves"></div>
</div>

<div class="panel">
  <h2>Capital sensitivity &mdash; Penny / Mid / Small at $1k / $2.5k / $5k / $10k / $25k</h2>
  <div class="callout" style="margin-bottom:12px;">
    Real brokers sell whole shares, not fractions. With few slots and small
    capital, a slot too small to afford even 1 share of a signal's stock is
    <b>skipped</b>, not silently filled. <code>Skipped %</code> below is how
    often that happened &mdash; the real cost of trading these tiers on a small
    account, on top of the round-trip cost already in the P&amp;L. Large caps
    are excluded here: at $50-500+ share prices they're least exposed to this
    effect and weren't the tier of interest anyway.
  </div>
  <div class="filters" id="cap-filters"></div>
  <div class="tablewrap">
    <table id="cap-tbl">
      <thead><tr id="cap-thead"></tr></thead>
      <tbody id="cap-tbody"></tbody>
    </table>
  </div>
</div>

<div class="panel">
  <h2>Summary &mdash; approach, parameters, and why this exists</h2>
  <p style="font-size:13px; line-height:1.6;">
  <b>End goal:</b> find out whether there is a real, statistically defensible swing-trading edge in US equities
  that could actually be traded with a modest retail account &mdash; not just a pattern that looks good on a
  chart. Most "obvious" swing setups (buy the dip, buy the breakout, buy strength) are folklore with no
  edge once tested properly; the point of this whole exercise was to find out which, if any, survive rigorous
  testing, and at what account size they're actually usable.
  </p>
  <p style="font-size:13px; line-height:1.6;"><b>Approach, in stages:</b></p>
  <ol style="font-size:13px; line-height:1.7;">
    <li><b>Define each strategy as a precise, pre-registered rule</b> (entry condition, exit timing) before
      looking at results &mdash; 9 strategies total: RSI pullback, volume breakout, RSI+MACD combo, gap-down
      reversion, 5-day-low reversion, 52-week-high, cross-sectional momentum, short-term reversal, and
      sustained relative strength.</li>
    <li><b>Build an honest, systematic stock universe</b> instead of hand-picking familiar names &mdash;
      randomly sampled from real S&amp;P 500/400/600 and NASDAQ listings, then filtered for liquidity and
      volatility. 4 tiers: Large (30 names), Mid (25), Small (20), Penny (15).</li>
    <li><b>Grade every signal against its own tier's base rate</b> (not a coin flip) using HAC t-statistics
      and block-bootstrap confidence intervals, so a strategy that just rides a rising tier doesn't get
      credited with "skill."</li>
    <li><b>Deflate for every variant tried</b> (Deflated Sharpe Ratio) across all 9&times;4&times;3 = 108
      strategy/tier/horizon combinations, so a lucky-looking result out of 108 tries isn't mistaken for a
      real edge.</li>
    <li><b>Check sub-period stability</b> (pre-2020 / 2020-2022 / 2023+) &mdash; a result only counts if it
      replicates across independent market regimes, not just one lucky stretch.</li>
    <li><b>Test exit rules</b> (stop-loss, profit-target, and combinations) against the plain fixed-day exit,
      instead of assuming a stop-loss always helps.</li>
    <li><b>Simulate an actual portfolio</b> (this report): real starting capital, 10 equal-weight position
      slots, whole-share rounding (you can't buy 0.4 of a stock), signals skipped when slots are full or a
      slot can't afford 1 share &mdash; turning "beats the base rate" into "here's what your account would
      look like."</li>
    <li><b>Test capital sensitivity</b> on the tiers most exposed to the whole-share problem (Penny/Small/Mid)
      across 5 account sizes ($1k&ndash;$25k), because a signal that works fine at $25k can quietly fail at
      $1k once most of its trades can't even be filled.</li>
  </ol>
  <p style="font-size:13px; line-height:1.6;">
  <b>What came out of it:</b> gap-down reversion (Mid/Small caps, 20-day hold) is the only strategy of the 9
  that survives every gate above. The capital-sensitivity check adds one more condition: it needs at least
  roughly $2,500-$5,000 to avoid the whole-share penalty eating the edge on Mid caps, and should <b>not</b> be
  run on Penny stocks at any capital level tested &mdash; drawdowns there are catastrophic (-88% to -92%)
  regardless of account size.
  </p>
</div>

<footer>
  Generated by <code>strategies/trend/portfolio_sim.py</code> + <code>capital_sensitivity.py</code> +
  <code>build_report.py</code>. Per-trade signal definitions reused verbatim from each <code>backtest_*.py</code>
  module &mdash; see <code>FINDINGS.md</code> for the full research trail, caveats (one-regime bias pre-2020,
  survivorship in screened universes, daily-close-only fills) and what's still pending.
</footer>

<script>
const DATA = __DATA_JSON__;

const COLS = [
  {k:"strategy", label:"Strategy"},
  {k:"tier", label:"Tier"},
  {k:"hold_days", label:"Hold (d)"},
  {k:"edge_tag", label:"Edge?"},
  {k:"cagr_pct", label:"CAGR %", num:true},
  {k:"sharpe", label:"Sharpe", num:true},
  {k:"max_drawdown_pct", label:"Max DD %", num:true},
  {k:"total_return_pct", label:"Total Return %", num:true},
  {k:"final_equity", label:"Final Equity ($)", num:true},
  {k:"win_rate_pct", label:"Win Rate %", num:true},
  {k:"n_trades", label:"# Trades", num:true},
  {k:"avg_positions_held", label:"Avg Slots Used", num:true},
];

let sortKey = "sharpe", sortDir = -1;
let tierFilter = "All";

function fmt(v, num) {
  if (v === null || v === undefined) return "&mdash;";
  if (!num) return v;
  return typeof v === "number" ? v.toLocaleString(undefined, {maximumFractionDigits: 2}) : v;
}

function tagClass(tag) {
  if (tag === "CONFIRMED") return "tag-confirmed";
  if (tag === "WEAK") return "tag-weak";
  return "tag-notproven";
}

function renderFilters() {
  const tiers = ["All", "Large", "Mid", "Small", "Penny"];
  const el = document.getElementById("filters");
  el.innerHTML = "";
  tiers.forEach(t => {
    const b = document.createElement("button");
    b.textContent = t;
    if (t === tierFilter) b.classList.add("active");
    b.onclick = () => { tierFilter = t; render(); };
    el.appendChild(b);
  });
}

function renderHead() {
  const tr = document.getElementById("thead");
  tr.innerHTML = "";
  COLS.forEach(c => {
    const th = document.createElement("th");
    th.textContent = c.label;
    if (c.k === sortKey) th.classList.add("sorted");
    th.onclick = () => {
      if (sortKey === c.k) sortDir *= -1; else { sortKey = c.k; sortDir = -1; }
      render();
    };
    tr.appendChild(th);
  });
}

function renderBody() {
  const tbody = document.getElementById("tbody");
  tbody.innerHTML = "";
  let rows = DATA.filter(r => tierFilter === "All" || r.tier === tierFilter);
  rows.sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey];
    if (av === null) return 1; if (bv === null) return -1;
    if (av < bv) return -1 * sortDir; if (av > bv) return 1 * sortDir; return 0;
  });
  rows.forEach(r => {
    const tr = document.createElement("tr");
    tr.title = r.edge_note;
    COLS.forEach(c => {
      const td = document.createElement("td");
      if (c.k === "edge_tag") {
        td.innerHTML = `<span class="tag ${tagClass(r.edge_tag)}">${r.edge_tag}</span>`;
      } else if (c.k === "cagr_pct" || c.k === "total_return_pct" || c.k === "max_drawdown_pct") {
        const v = r[c.k];
        td.textContent = v === null ? "—" : v + "%";
        td.className = v > 0 ? "num-pos" : (v < 0 ? "num-neg" : "");
      } else if (c.k === "final_equity") {
        td.textContent = "$" + Math.round(r[c.k]).toLocaleString();
      } else {
        td.textContent = fmt(r[c.k], c.num);
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function sparkline(values) {
  const w = 300, h = 60, pad = 4;
  const mn = Math.min(...values), mx = Math.max(...values);
  const range = (mx - mn) || 1;
  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - 2*pad);
    const y = h - pad - ((v - mn) / range) * (h - 2*pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const startColor = "#9399a8";
  const lineColor = values[values.length-1] >= values[0] ? "#3ecf8e" : "#ef5f6a";
  return `<svg class="curve" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <polyline points="${pts}" fill="none" stroke="${lineColor}" stroke-width="1.6" />
  </svg>`;
}

function renderCurves() {
  const top = [...DATA].filter(r => r.sharpe !== null).sort((a,b) => b.sharpe - a.sharpe).slice(0, 6);
  const el = document.getElementById("curves");
  el.innerHTML = "";
  top.forEach(r => {
    const card = document.createElement("div");
    card.className = "curve-card";
    card.innerHTML = `<div class="title">${r.strategy} &middot; ${r.tier} &middot; ${r.hold_days}d
        <span class="tag ${tagClass(r.edge_tag)}" style="margin-left:6px;">${r.edge_tag}</span></div>
      <div class="meta">CAGR ${r.cagr_pct}% &middot; Sharpe ${r.sharpe} &middot; Max DD ${r.max_drawdown_pct}% &middot; $100k &rarr; $${Math.round(r.final_equity).toLocaleString()}</div>
      ${sparkline(r.equity_values)}`;
    el.appendChild(card);
  });
}

function render() { renderFilters(); renderHead(); renderBody(); renderCurves(); }
render();

// ---- Capital sensitivity section ------------------------------------------
const CAP_DATA = __CAP_DATA_JSON__;
const CAP_COLS = [
  {k:"capital", label:"Capital ($)"},
  {k:"strategy", label:"Strategy"},
  {k:"tier", label:"Tier"},
  {k:"hold_days", label:"Hold (d)"},
  {k:"edge_tag", label:"Edge?"},
  {k:"cagr_pct", label:"CAGR %", num:true},
  {k:"sharpe", label:"Sharpe", num:true},
  {k:"max_drawdown_pct", label:"Max DD %", num:true},
  {k:"final_equity", label:"Final Equity ($)", num:true},
  {k:"signals_skipped_too_small_pct", label:"Skipped % (too small)", num:true},
  {k:"n_trades", label:"# Trades", num:true},
];
let capTierFilter = "All";
let capSortKey = "sharpe", capSortDir = -1;

function renderCapFilters() {
  const tiers = ["All", "Penny", "Small", "Mid"];
  const el = document.getElementById("cap-filters");
  if (!el) return;
  el.innerHTML = "";
  tiers.forEach(t => {
    const b = document.createElement("button");
    b.textContent = t;
    if (t === capTierFilter) b.classList.add("active");
    b.onclick = () => { capTierFilter = t; renderCap(); };
    el.appendChild(b);
  });
}

function renderCapHead() {
  const tr = document.getElementById("cap-thead");
  if (!tr) return;
  tr.innerHTML = "";
  CAP_COLS.forEach(c => {
    const th = document.createElement("th");
    th.textContent = c.label;
    if (c.k === capSortKey) th.classList.add("sorted");
    th.onclick = () => {
      if (capSortKey === c.k) capSortDir *= -1; else { capSortKey = c.k; capSortDir = -1; }
      renderCap();
    };
    tr.appendChild(th);
  });
}

function renderCapBody() {
  const tbody = document.getElementById("cap-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  let rows = CAP_DATA.filter(r => capTierFilter === "All" || r.tier === capTierFilter);
  rows.sort((a, b) => {
    const av = a[capSortKey], bv = b[capSortKey];
    if (av === null) return 1; if (bv === null) return -1;
    if (av < bv) return -1 * capSortDir; if (av > bv) return 1 * capSortDir; return 0;
  });
  rows.forEach(r => {
    const tr = document.createElement("tr");
    tr.title = r.edge_note;
    CAP_COLS.forEach(c => {
      const td = document.createElement("td");
      if (c.k === "edge_tag") {
        td.innerHTML = `<span class="tag ${tagClass(r.edge_tag)}">${r.edge_tag}</span>`;
      } else if (c.k === "capital" || c.k === "final_equity") {
        td.textContent = "$" + Math.round(r[c.k]).toLocaleString();
      } else if (c.k === "cagr_pct" || c.k === "max_drawdown_pct") {
        const v = r[c.k];
        td.textContent = v === null ? "—" : v + "%";
        td.className = v > 0 ? "num-pos" : (v < 0 ? "num-neg" : "");
      } else if (c.k === "signals_skipped_too_small_pct") {
        const v = r[c.k];
        td.textContent = v + "%";
        td.className = v >= 15 ? "num-neg" : (v >= 5 ? "" : "num-pos");
      } else {
        td.textContent = fmt(r[c.k], c.num);
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function renderCap() { renderCapFilters(); renderCapHead(); renderCapBody(); }
if (CAP_DATA.length) renderCap();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build("portfolio_sim_results.json", "portfolio_report.html", "capital_sensitivity_results.json")
