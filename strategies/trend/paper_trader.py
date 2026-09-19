"""Forward paper trial of the FROZEN gap-down reversion rule (Mid + Small).

The only out-of-sample test available: rule frozen in paper_trial/PREREG.json,
run on data that did not exist when it was frozen, graded against the live
matched base rate with the same HAC-t as the backtest. NOTHING here may change
the rule; any change restarts the trial (delete paper_trial/ and re-init).

Design: bars.csv is the immutable raw record (append-only). Every other file
(events, pool, books, reports) is a deterministic function of it, so missed runs
are recovered by simply running again (backfill).

    python -m strategies.trend.paper_trader init     # once: write PREREG.json
    python -m strategies.trend.paper_trader run      # daily: fetch + rebuild + report
    python -m strategies.trend.paper_trader grade    # print the gate status

Gate: N>=200 unconstrained events per tier, HAC-t>=2 vs live base, same sign as
in-sample, excess >= half of in-sample excess. ~2-month check is plumbing only.
Price-only returns (raw Yahoo closes, no dividends) -- slightly below the
total-return backtest; immaterial at 20d.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ._common import COST_BPS, UNIVERSES, hstats
from .backtest_gap_reversion import GAP_THRESHOLD

ROOT = Path(__file__).parent / "paper_trial"
BARS, PREREG = ROOT / "bars.csv", ROOT / "PREREG.json"
TIERS = ("Mid", "Small")
SLOTS = {"Mid": 5, "Small": 10}
CAPITAL = 5000.0          # paper $ per book
HOLD = 20                 # trading days
TBILL = 0.035             # idle-cash yield, reported as a separate line (not edge)
MKT_GAP_SHARE = 0.15      # >=15% of the 45-name universe gapping down = selloff day
DELIST_DAYS = 5           # no bar for this many days = treat as delisted
GATE_N = 200
KILL_N = 20               # at N>=20 resolved, negative excess => investigate (not a verdict)
COLS = ["date", "symbol", "open", "high", "low", "close", "volume", "split"]


# ------------------------------------------------------------------ data

def _cutoff() -> pd.Timestamp:
    """Last date whose bar is final: yesterday ET, or today ET after 20:00."""
    now = datetime.now(ZoneInfo("America/New_York"))
    d = now.date() if now.hour >= 20 else (now - pd.Timedelta(days=1)).date()
    return pd.Timestamp(d)


def _fetch(sym: str, start: pd.Timestamp, cutoff: pd.Timestamp) -> pd.DataFrame:
    import yfinance as yf
    h = yf.Ticker(sym).history(start=start.strftime("%Y-%m-%d"), auto_adjust=False, actions=True)
    if h is None or h.empty:
        raise RuntimeError("no data")
    h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
    out = pd.DataFrame({"date": h.index, "symbol": sym, "open": h["Open"].values,
                        "high": h["High"].values, "low": h["Low"].values,
                        "close": h["Close"].values, "volume": h["Volume"].values,
                        "split": (h["Stock Splits"].values > 0)})
    return out[out["date"] <= cutoff].dropna(subset=["open", "close"])


def load_bars() -> pd.DataFrame:
    if not BARS.exists():
        return pd.DataFrame(columns=COLS)
    return pd.read_csv(BARS, parse_dates=["date"])


def update_bars(start: pd.Timestamp) -> list[str]:
    """Append only new (symbol,date) rows; never rewrite history. Returns problems."""
    have, cutoff, problems, new = load_bars(), _cutoff(), [], []
    last = have.groupby("symbol")["date"].max() if len(have) else pd.Series(dtype="datetime64[ns]")
    for sym in [s for t in TIERS for s in UNIVERSES[t]]:
        since = (last[sym] - pd.Timedelta(days=7)) if sym in last else start - pd.Timedelta(days=45)
        try:
            df = _fetch(sym, since, cutoff)
        except Exception as e:                       # logged, never silent
            problems.append(f"{sym}: fetch failed ({e})")
            continue
        if sym in last:
            df = df[df["date"] > last[sym]]
        new.append(df)
    add = pd.concat(new) if new else pd.DataFrame(columns=COLS)
    if len(add):
        ROOT.mkdir(parents=True, exist_ok=True)
        add.sort_values(["date", "symbol"]).to_csv(BARS, mode="a", header=not BARS.exists(),
                                                   index=False, columns=COLS)
    allb = load_bars()
    lastd = allb.groupby("symbol")["date"].max()
    stale = lastd[lastd < lastd.max() - pd.Timedelta(days=DELIST_DAYS)]
    problems += [f"{s}: last bar {d.date()} (stale/delisted?)" for s, d in stale.items()]
    return problems


# ------------------------------------------------------------------ derive

def derive(bars: pd.DataFrame, tier_of: dict[str, str], start: pd.Timestamp):
    """-> (events, pool). Both unconstrained by slots/capital. Pure function."""
    ev, pool, gaps = [], [], []
    cal_last = bars["date"].max()
    for sym, g in bars.sort_values("date").groupby("symbol"):
        d, o, c, sp = g["date"].values, g["open"].values, g["close"].values, g["split"].values
        n, delisted = len(g), pd.Timestamp(d[-1]) < cal_last - pd.Timedelta(days=DELIST_DAYS)
        for i in range(1, n):
            date = pd.Timestamp(d[i])
            if date <= start:
                continue
            gap = o[i] / c[i - 1] - 1.0
            gaps.append((date, sym, gap <= GAP_THRESHOLD))
            split = bool(sp[i - 1:i + HOLD + 1].any())
            if i + HOLD < n:
                xd, xp, st = pd.Timestamp(d[i + HOLD]), c[i + HOLD], "closed"
            elif delisted:
                xd, xp, st = pd.Timestamp(d[-1]), c[-1], "delisted"
            else:
                xd, xp, st = pd.NaT, np.nan, "open"
            if split:
                st = "split_excluded"
            ret = xp / c[i] - 1.0 if st in ("closed", "delisted") else np.nan
            if st in ("closed", "delisted"):
                pool.append((date, sym, tier_of[sym], ret))
            if gap <= GAP_THRESHOLD:
                ev.append(dict(date=date, symbol=sym, tier=tier_of[sym], gap_pct=gap, entry_price=c[i],
                               exit_date=xd, exit_price=xp, ret=ret, status=st))
    events = pd.DataFrame(ev, columns=["date", "symbol", "tier", "gap_pct", "entry_price",
                                       "exit_date", "exit_price", "ret", "status"])
    pool = pd.DataFrame(pool, columns=["date", "symbol", "tier", "ret"])
    gp = pd.DataFrame(gaps, columns=["date", "symbol", "gd"])
    share = gp.groupby("date")["gd"].mean() if len(gp) else pd.Series(dtype=float)
    events["market_gap_day"] = events["date"].map(share >= MKT_GAP_SHARE).fillna(False).astype(bool)
    return events.sort_values(["date", "symbol"]).reset_index(drop=True), pool


def simulate_book(events: pd.DataFrame, tier: str) -> pd.DataFrame:
    """Slot-limited, whole-share book. Adds filled/skip_reason/shares/pnl to a tier's events."""
    e = events[events["tier"] == tier].copy()
    slot_usd, cost = CAPITAL / SLOTS[tier], COST_BPS[tier] / 1e4
    held, filled, why, sh, pnl = [], [], [], [], []
    for r in e.itertuples():
        held = [x for x in held if pd.isna(x) or x > r.date]   # exits free slots same day
        if r.status == "split_excluded":
            filled.append(False), why.append("split_excluded"), sh.append(0), pnl.append(np.nan)
        elif len(held) >= SLOTS[tier]:
            filled.append(False), why.append("slots_full"), sh.append(0), pnl.append(np.nan)
        elif int(slot_usd // r.entry_price) < 1:
            filled.append(False), why.append("cant_afford_1_share"), sh.append(0), pnl.append(np.nan)
        else:
            k = int(slot_usd // r.entry_price)
            held.append(r.exit_date)
            filled.append(True), why.append(""), sh.append(k)
            pnl.append(k * (r.exit_price - r.entry_price) - cost * k * r.entry_price
                       if r.status in ("closed", "delisted") else np.nan)
    e["filled"], e["skip_reason"], e["shares"], e["pnl_net"] = filled, why, sh, pnl
    return e


def equity_curve(book: pd.DataFrame, bars: pd.DataFrame, tier: str, start: pd.Timestamp) -> pd.DataFrame:
    px = bars.pivot(index="date", columns="symbol", values="close").sort_index().ffill()
    px = px[px.index > start]
    f = book[book["filled"]]
    rows, tb = [], 0.0
    for d in px.index:
        realized = f.loc[f["exit_date"].notna() & (f["exit_date"] <= d), "pnl_net"].sum()
        live = f[(f["date"] <= d) & (f["exit_date"].isna() | (f["exit_date"] > d))]
        unreal = sum(r.shares * (px.at[d, r.symbol] - r.entry_price) for r in live.itertuples())
        invested = float((live["shares"] * live["entry_price"]).sum())
        tb += max(CAPITAL + realized - invested, 0.0) * TBILL / 252
        base = px.iloc[0][UNIVERSES[tier]]
        bench = CAPITAL * float((px.loc[d, UNIVERSES[tier]] / base).mean())
        rows.append((d, CAPITAL + realized + unreal, tb, bench))
    return pd.DataFrame(rows, columns=["date", "equity_ex_tbill", "tbill_cum", "benchmark_ew_bh"])


# ------------------------------------------------------------------ grading

def grade(events: pd.DataFrame, pool: pd.DataFrame, pre: dict) -> dict:
    out = {}
    for t in TIERS:
        sig = events[(events["tier"] == t) & events["status"].isin(["closed", "delisted"])].sort_values("date")
        base = pool[pool["tier"] == t]["ret"].to_numpy()
        allev = events[(events["tier"] == t) & (events["status"] != "split_excluded")]
        r = dict(n_resolved=len(sig), n_total=len(allev), base_pct=None, signal_pct=None, excess_pct=None,
                 hac_t=None, hac_t_excl_selloff=None, verdict="too early (plumbing check only)")
        ins = pre["in_sample"][t]
        if len(sig) and len(base):
            b = base.mean()
            r.update(base_pct=100 * b, signal_pct=100 * sig["ret"].mean(), excess_pct=100 * (sig["ret"].mean() - b))
            if len(sig) >= 4:
                r["hac_t"] = float(hstats.newey_west_tstat(sig["ret"].to_numpy() - b)[0])
            q = sig[~sig["market_gap_day"]]
            if len(q) >= 4:
                r["hac_t_excl_selloff"] = float(hstats.newey_west_tstat(q["ret"].to_numpy() - b)[0])
            if len(sig) >= GATE_N:
                ok = (r["hac_t"] or 0) >= 2 and r["excess_pct"] >= 0.5 * ins["excess_pct"]
                r["verdict"] = "GATE PASSED" if ok else "GATE NOT PASSED"
            elif len(sig) >= KILL_N and r["excess_pct"] < 0:
                r["verdict"] = "KILL FLAG: excess < 0 at N>=20 -> investigate (not a verdict)"
        days = max((events["date"].max() - pd.Timestamp(pre["start_date"])).days, 1) if len(events) else 1
        rate = len(allev) / days
        r["events_per_year"] = round(365 * rate, 1)
        r["projected_gate_date"] = (str((pd.Timestamp.today() + pd.Timedelta(days=(GATE_N - len(allev)) / rate)).date())
                                    if rate > 0 else "n/a")
        out[t] = r
    return out


def _fmt(x, nd=2):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def report(events, pool, books, curves, pre, problems) -> str:
    g, today = grade(events, pool, pre), pd.Timestamp.today().date()
    L = [f"# Gap-down reversion - forward paper trial  ({today})",
         f"Trial start {pre['start_date']}. **Out-of-sample** = everything below marked OOS; "
         "**in-sample** = frozen PREREG numbers. 2-month readings are plumbing checks, never a go-live gate.", ""]
    if problems:
        L += ["## Data problems (logged, not hidden)"] + [f"- {p}" for p in problems] + [""]
    for t in TIERS:
        r, ins = g[t], pre["in_sample"][t]
        L += [f"## {t}",
              f"| | in-sample (frozen) | OOS live |", "|---|---|---|",
              f"| events (resolved) | {ins['n']} | {r['n_resolved']} of {r['n_total']} seen |",
              f"| signal mean 20d % | {ins['signal_ret_pct']} | {_fmt(r['signal_pct'])} |",
              f"| base mean 20d % | {ins['base_ret_pct']} | {_fmt(r['base_pct'])} |",
              f"| excess % | {ins['excess_pct']:.2f} | {_fmt(r['excess_pct'])} |",
              f"| HAC-t vs base | {ins['hac_t']} | {_fmt(r['hac_t'])} (ex-selloff days: {_fmt(r['hac_t_excl_selloff'])}) |",
              f"| net-of-cost % | {ins['net_of_cost_pct']} | {_fmt(None if r['signal_pct'] is None else r['signal_pct'] - COST_BPS[t] / 100)} |",
              f"**Status:** {r['verdict']}. Rate ~{r['events_per_year']} events/yr; N={GATE_N} projected ~{r['projected_gate_date']}.", ""]
        b, c = books[t], curves[t]
        wk = events[(events["tier"] == t) & (events["date"] > pd.Timestamp(today) - pd.Timedelta(days=7))]
        op = b[b["filled"] & (b["status"] == "open")]
        L += [f"Signals last 7d: {len(wk)} | book fills: {int(b['filled'].sum())} | "
              f"skipped: slots_full {int((b['skip_reason'] == 'slots_full').sum())}, "
              f"cant_afford {int((b['skip_reason'] == 'cant_afford_1_share').sum())}"]
        for x in op.itertuples():
            L.append(f"- open {x.symbol}: entered {x.date.date()}, age {(pd.Timestamp(today) - x.date).days}d, {x.shares} sh @ {x.entry_price:.2f}")
        if len(c):
            z = c.iloc[-1]
            L.append(f"\nBook equity (OOS, ex T-bill): ${z.equity_ex_tbill:,.0f} | T-bill line: +${z.tbill_cum:,.2f} | "
                     f"benchmark EW buy&hold: ${z.benchmark_ew_bh:,.0f}")
        L.append("")
    return "\n".join(L)


# ------------------------------------------------------------------ commands

def _tier_of() -> dict[str, str]:
    return {s: t for t in TIERS for s in UNIVERSES[t]}


def init() -> None:
    if PREREG.exists():
        sys.exit("PREREG.json exists - trial already frozen. Changing the rule = delete paper_trial/ and restart.")
    from .backtest_gap_reversion import run_tier
    ins = {}
    for t in TIERS:
        r = run_tier(t, UNIVERSES[t])
        ins[t] = dict(n=r.n_events[20], signal_ret_pct=r.signal_ret_pct[20], base_ret_pct=r.base_ret_pct[20],
                      excess_pct=round(r.signal_ret_pct[20] - r.base_ret_pct[20], 2), hac_t=r.hac_t[20],
                      net_of_cost_pct=r.net_of_cost_pct[20])
    here = Path(__file__).parent
    ROOT.mkdir(parents=True, exist_ok=True)
    PREREG.write_text(json.dumps(dict(
        frozen_at=datetime.now().isoformat(timespec="seconds"), start_date=str(pd.Timestamp.today().date()),
        rule=dict(gap=GAP_THRESHOLD, entry="same-day close", exit=f"close +{HOLD} trading days", stop="none",
                  slots=SLOTS, capital_per_book=CAPITAL, cost_bps={t: COST_BPS[t] for t in TIERS},
                  market_gap_day_share=MKT_GAP_SHARE, tbill=TBILL),
        universe={t: UNIVERSES[t] for t in TIERS},
        in_sample=ins,
        gates=dict(kill=f"N>={KILL_N} resolved and signal-base<0 -> investigate",
                   go_live=f"N>={GATE_N} per tier, HAC-t>=2 vs live base, same sign, excess>=0.5x in-sample excess",
                   note="~2-month review is plumbing only; no money before go_live gate"),
        sha256={f: hashlib.sha256((here / f).read_bytes()).hexdigest()
                for f in ("_common.py", "backtest_gap_reversion.py", "paper_trader.py")}), indent=2))
    print("frozen:", PREREG)


def run() -> None:
    if not PREREG.exists():
        sys.exit("run `init` first")
    pre = json.loads(PREREG.read_text())
    start = pd.Timestamp(pre["start_date"])
    problems = update_bars(start)
    bars = load_bars()
    events, pool = derive(bars, _tier_of(), start)
    books = {t: simulate_book(events, t) for t in TIERS}
    curves = {t: equity_curve(books[t], bars, t, start) for t in TIERS}
    pd.concat(books.values()).to_csv(ROOT / "events_log.csv", index=False)   # graded set + book columns
    pool.to_csv(ROOT / "day_pool.csv", index=False)
    for t in TIERS:
        curves[t].to_csv(ROOT / f"equity_{t}.csv", index=False)
    md = report(events, pool, books, curves, pre, problems)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "latest.md").write_text(md, encoding="utf-8")
    if datetime.now().weekday() == 5:                                       # Saturday SGT = after Fri US close
        (ROOT / "reports" / f"weekly_{datetime.now().date()}.md").write_text(md, encoding="utf-8")
    with open(ROOT / "runs.log", "a") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} bars={len(bars)} events={len(events)} problems={len(problems)}\n")
    print(md)


if __name__ == "__main__":
    {"init": init, "run": run, "grade": run}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
