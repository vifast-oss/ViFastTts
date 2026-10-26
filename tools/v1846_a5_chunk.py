"""v18.46 — A5: so BAK(C teacher-forcing) với P (CLI chunk mode) trên 40 câu dài."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.v1845_a4_confirm import CFG32, P2, bak
from vifasttts.infer import Synthesizer

LONG = Path("artifacts/bench/v1846_a2_long")
OUT = Path("artifacts/bench/v1846_a5_chunk")
HOLDOUT = "data/codelung/v32/holdout_clean_v2_dur_seg_slot4.jsonl"
N_BOOT = 10000


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    a2 = json.loads((LONG / "result.json").read_text(encoding="utf-8"))
    rows = {json.loads(line)["id"]: json.loads(line)
            for line in Path(HOLDOUT).read_text(encoding="utf-8").splitlines() if line.strip()}
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()
    vals = []
    for index, item_id in enumerate(a2["rows"]):
        c_wave, _ = sf.read(LONG / f"{index:02d}_C.wav", dtype="float32")
        c_bak = bak(np.asarray(c_wave).reshape(-1), 24000)
        p_path = OUT / f"{index:02d}_P.wav"
        engine.synthesize(rows[item_id]["text"], p_path, gate_threshold=0.5,
                          sharpen_alpha=0.0, target_lufs=-16, peak_normalize=False,
                          max_chars=400)
        p_wave, _ = sf.read(p_path, dtype="float32")
        p_bak = bak(np.asarray(p_wave).reshape(-1), 24000)
        vals.append({"id": item_id, "c_bak": c_bak, "p_bak": p_bak,
                     "diff": round(c_bak - p_bak, 6)})
        print(json.dumps({"done": index + 1, "total": len(a2["rows"])}), flush=True)
    diffs = np.asarray([row["diff"] for row in vals], dtype=float)
    rng = np.random.default_rng(0)
    means = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, diffs.size, size=diffs.size)
        means.append(float(diffs[idx].mean()))
    ci = [round(float(np.percentile(means, 2.5)), 4),
          round(float(np.percentile(means, 97.5)), 4)]
    mean = float(diffs.mean())
    chunk_adds = bool(mean >= 0.10 and ci[0] > 0)
    weird = bool(mean <= -0.10)
    verdict = ("CHUNK GÂY RÈ THÊM" if chunk_adds else
               ("LẠ — chunk sạch hơn TF" if weird else "KHÔNG KẾT LUẬN — không đủ bằng chứng"))
    result = {"n": len(vals), "mean_diff": round(mean, 6), "ci95": ci,
              "chunk_adds_noise": chunk_adds, "weird": weird,
              "verdict": verdict, "rows": vals}
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("n", "mean_diff", "ci95", "chunk_adds_noise", "weird", "verdict")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
