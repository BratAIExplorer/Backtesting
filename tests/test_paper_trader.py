"""Offline self-check: gap detection, split exclusion, slot/whole-share skips, open positions."""
import numpy as np
import pandas as pd

from strategies.trend import paper_trader as pt

START = pd.Timestamp("2026-01-01")


def bars(sym, closes, opens=None, splits=()):
    d = pd.bdate_range("2026-01-02", periods=len(closes))
    o = closes if opens is None else opens
    return pd.DataFrame(dict(date=d, symbol=sym, open=o, high=o, low=o, close=closes, volume=1,
                             split=[i in splits for i in range(len(closes))]))


def _series(gap_at=3, n=30, px=100.0):
    c = [px] * n
    o = list(c)
    o[gap_at] = px * 0.95                 # -5% open vs prior close
    return c, o


def test_gap_event_and_20d_return():
    c, o = _series()
    c[23:] = [110.0] * len(c[23:]); o[23:] = c[23:]
    ev, pool = pt.derive(bars("AAA", c, o), {"AAA": "Mid"}, START)
    assert len(ev) == 1 and ev.status[0] == "closed" and abs(ev.ret[0] - 0.10) < 1e-9
    assert len(pool) > 1


def test_unresolved_is_open_and_split_is_excluded():
    c, o = _series(gap_at=15, n=25)
    ev, _ = pt.derive(bars("AAA", c, o), {"AAA": "Mid"}, START)
    assert ev.status[0] == "open"
    c, o = _series()
    ev, pool = pt.derive(bars("AAA", c, o, splits=(10,)), {"AAA": "Mid"}, START)
    assert ev.status[0] == "split_excluded" and pool.empty


def test_slots_and_whole_share_skips():
    c, o = _series(px=2000.0)             # $1000 Mid slot cannot buy one $2000 share
    ev, _ = pt.derive(bars("AAA", c, o), {"AAA": "Mid"}, START)
    assert pt.simulate_book(ev, "Mid").skip_reason[0] == "cant_afford_1_share"
    frames = [bars(s, *_series()[:1], opens=_series()[1]) for s in "ABCDEFG"]
    ev, _ = pt.derive(pd.concat(frames), {s: "Mid" for s in "ABCDEFG"}, START)
    b = pt.simulate_book(ev, "Mid")
    assert b.filled.sum() == 5 and (b.skip_reason == "slots_full").sum() == 2
    assert np.isfinite(b[b.filled].pnl_net).all()
