"""v18.44 — A3: hiệu chuẩn giám khảo trên dữ liệu A2 có sẵn (không chấm audio mới).

(a) Bootstrap HAI TẦNG cho đối chứng âm A2: lấy mẫu lại cả câu VÀ seed.
    - CI cũ (A2): paired bootstrap trên trung bình 5 seed, bỏ qua phương sai seed.
    - CI mới: hai tầng, seed là hiệu ứng ngẫu nhiên.
    ĐẠT nếu CI mới chứa 0 => giao thức UTMOS mới = hai tầng, ≥10 seed, dùng chung bộ seed,
    lần chấm nào cũng kèm đối chứng âm. TRƯỢT => UTMOS bị loại khỏi luật quyết định.
(b) BAK chấm 2 lần trên 10 file A4 để xác nhận tất định.

Không train, không đổi production.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

A2 = Path("artifacts/bench/v1843_a2/result.json")
A4_DIR = Path("artifacts/bench/v1843_a4")
OUT = Path("artifacts/bench/v1844_a3_calibration")
N_BOOT = 10000


def ci95(values: np.ndarray) -> list[float]:
    return [round(float(np.percentile(values, 2.5)), 4),
            round(float(np.percentile(values, 97.5)), 4)]


def old_paired_bootstrap(rows: list[dict], n_boot: int = N_BOOT, seed: int = 0) -> dict:
    diffs = np.array([np.mean(row["chunk_utmos_neg"]) - np.mean(row["chunk_utmos"])
                      for row in rows], dtype=float)
    rng = np.random.default_rng(seed)
    draws = diffs[rng.integers(0, diffs.size, size=(n_boot, diffs.size))]
    means = draws.mean(axis=1)
    return {"mean": round(float(diffs.mean()), 4), "ci95": ci95(means), "n": int(diffs.size),
            "method": "paired bootstrap trên trung bình seed (CI cũ A2)"}


def two_level_bootstrap(rows: list[dict], n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """Resample câu, rồi resample seed trong từng nhóm A/B của câu được chọn."""
    rng = np.random.default_rng(seed)
    n = len(rows)
    a = np.asarray([row["chunk_utmos"] for row in rows], dtype=float)       # [N,5]
    b = np.asarray([row["chunk_utmos_neg"] for row in rows], dtype=float)   # [N,5]
    draws = np.empty(n_boot, dtype=float)
    for k in range(n_boot):
        sentence_idx = rng.integers(0, n, size=n)
        # seed index [N,5] cho mỗi nhóm, độc lập
        seed_a = rng.integers(0, a.shape[1], size=(n, a.shape[1]))
        seed_b = rng.integers(0, b.shape[1], size=(n, b.shape[1]))
        a_sel = np.take_along_axis(a[sentence_idx], seed_a, axis=1).mean(axis=1)
        b_sel = np.take_along_axis(b[sentence_idx], seed_b, axis=1).mean(axis=1)
        draws[k] = float(np.mean(b_sel - a_sel))
    point = float(np.mean(b.mean(axis=1) - a.mean(axis=1)))
    return {"mean": round(point, 4), "ci95": ci95(draws), "n": int(n),
            "method": "hai tầng: câu + seed (seed là hiệu ứng ngẫu nhiên)"}


def score_bak(path: Path) -> float:
    from speechmos import dnsmos

    wave, sr = sf.read(path, dtype="float32")
    wave = np.asarray(wave).reshape(-1)
    wave16 = resample_poly(wave.astype(np.float64), 16000, sr).astype(np.float32)
    return round(float(dnsmos.run(wave16, sr=16000)["bak_mos"]), 6)


def bak_determinism(n_files: int = 10) -> dict:
    files = sorted(A4_DIR.glob("*_C.wav"))[:n_files]
    if len(files) < n_files:
        files = sorted(A4_DIR.glob("*.wav"))[:n_files]
    rows = []
    for path in files:
        first = score_bak(path)
        second = score_bak(path)
        rows.append({"file": path.name, "first": first, "second": second,
                     "equal": first == second, "diff": round(abs(first - second), 9)})
    return {"n": len(rows), "all_equal": all(row["equal"] for row in rows),
            "max_diff": max((row["diff"] for row in rows), default=None), "rows": rows}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads(A2.read_text(encoding="utf-8"))
    rows = data["rows"]
    old = old_paired_bootstrap(rows)
    new = two_level_bootstrap(rows)
    contains_zero = new["ci95"][0] <= 0 <= new["ci95"][1]
    bak = bak_determinism(10)
    result = {
        "input": str(A2),
        "n_sentences": len(rows),
        "seeds_per_condition": len(rows[0]["chunk_utmos"]),
        "negative_control": {"old_ci": old, "two_level_ci": new,
                             "contains_zero": bool(contains_zero)},
        "bak_determinism": bak,
        "verdict": {
            "utmoss_protocol": ("ĐẠT — dùng bootstrap hai tầng, ≥10 seed, chung bộ seed, "
                                "kèm đối chứng âm mỗi lần chấm"
                                if contains_zero else
                                "TRƯỢT — loại UTMOS khỏi luật quyết định; chỉ còn BAK + tai"),
            "bak": "ĐẠT — BAK tất định" if bak["all_equal"] else "LẠ — BAK lệch, dừng, báo",
            "unresolved": {
                "g1_1k_utmos_plus_0.096": "chưa phân giải được (nằm trong vùng nhiễu seed)",
                "p2_4k_utmos_minus_0.070": "chưa phân giải được (nằm trong vùng nhiễu seed)",
            },
        },
    }
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
