"""Purged + embargoed walk-forward splitting (Lopez de Prado, AFML ch. 7).

Why this exists: any model fitted on overlapping forward-return labels leaks
information across a naive train/test boundary. Purge removes training rows
whose label window overlaps the test set; embargo removes a further slice after
the test set to kill residual serial correlation. Without both, an in-sample fit
looks predictive when it is only memorizing the overlap.

`PurgedKFold` yields (train_idx, test_idx) over integer positions of a label
series whose `t1` (label end) is known per row.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PurgedKFold:
    n_splits: int = 5
    embargo_pct: float = 0.01

    def split(self, t0: pd.Series, t1: pd.Series):
        """Yield (train_positions, test_positions) as numpy int arrays.

        t0, t1: label start / end timestamps, aligned, monotonic by t0.
        """
        n = len(t0)
        if n < self.n_splits * 2:
            raise ValueError("not enough samples for the requested n_splits")
        t0 = pd.Series(t0).reset_index(drop=True)
        t1 = pd.Series(t1).reset_index(drop=True)
        idx = np.arange(n)
        embargo = int(n * self.embargo_pct)

        for k in range(self.n_splits):
            lo = k * n // self.n_splits
            hi = (k + 1) * n // self.n_splits
            test = idx[lo:hi]
            test_start, test_end = t0.iloc[lo], t1.iloc[hi - 1]

            # purge: drop train rows whose label window overlaps the test window
            overlap = (t0 <= test_end) & (t1 >= test_start)
            # embargo: drop the slice immediately after the test set
            emb = idx[hi:hi + embargo]
            drop = set(idx[overlap].tolist()) | set(emb.tolist())
            train = np.array([i for i in idx if i not in drop])
            if train.size and test.size:
                yield train, test


def walk_forward_blocks(t0: pd.Series, n_folds: int = 5, embargo_pct: float = 0.01):
    """Expanding-window walk-forward: train on everything before each test
    block (purged + embargoed), test on the block. This is the *sequential*
    variant — closer to how a live signal would actually be deployed.
    """
    n = len(t0)
    fold_size = n // (n_folds + 1)
    embargo = int(n * embargo_pct)
    for k in range(1, n_folds + 1):
        train_end = k * fold_size
        test_lo = train_end + embargo
        test_hi = min(n, test_lo + fold_size)
        if test_lo >= test_hi:
            continue
        yield np.arange(0, train_end), np.arange(test_lo, test_hi)


if __name__ == "__main__":
    dates = pd.date_range("2020-01-01", periods=100, freq="B")
    t0 = pd.Series(dates)
    t1 = pd.Series(dates + pd.Timedelta(days=20))
    cv = PurgedKFold(n_splits=5, embargo_pct=0.02)
    folds = list(cv.split(t0, t1))
    assert len(folds) == 5
    for tr, te in folds:
        # no training row may overlap the test window
        te_start, te_end = t0.iloc[te[0]], t1.iloc[te[-1]]
        assert not ((t0.iloc[tr] <= te_end) & (t1.iloc[tr] >= te_start)).any()
    wf = list(walk_forward_blocks(t0, n_folds=4))
    assert len(wf) == 4
    assert (wf[0][1] > wf[0][0].max()).all()
    print("walkforward self-check ok")
