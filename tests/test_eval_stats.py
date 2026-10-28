"""Test nhỏ cho hàm đếm thắng/thua/hòa (v18.34 audit)."""

from vifasttts.eval_stats import outcome_counts


def test_chieu_cao_hon_tot():
    out = outcome_counts([0.5, -0.2, 0.0, float("nan")], higher_better=True)
    assert out == {"n": 3, "wins": 1, "losses": 1, "ties": 1,
                   "win_pct": 33.33, "loss_pct": 33.33, "tie_pct": 33.33}


def test_chieu_thap_hon_tot():
    out = outcome_counts([0.5, -0.2, 0.0], higher_better=False)
    assert out["wins"] == 1 and out["losses"] == 1 and out["ties"] == 1


def test_rong():
    out = outcome_counts([], higher_better=True)
    assert out["n"] == 0 and out["win_pct"] is None
