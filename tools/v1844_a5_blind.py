"""v18.44 — A5: dựng trang nghe mù B vs C (kiểm chứng BAK), 28 lượt.

16 B-vs-C + 4 dương (B vs B+trắng SNR 30 dB) + 4 âm (C vs C) + 4 lặp (đảo A/B).
Chuẩn −16 LUFS; vị trí/thứ tự ngẫu nhiên seed 1844; ẩn tên. Key nằm ngoài thư mục phục vụ.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

A4 = Path("artifacts/bench/v1843_a4")
OUT = Path("artifacts/listen_v1844_a5")
KEY = Path("artifacts/bench/v1844_a5/key.json")
SEED = 1844
SR = 24000

SELECTED = [
    ("vEtfty4Cc6Y_0070__s01", 31),
    ("2b65WyiFC9k_0162__s02", 3),
    ("BD83pScFukQ_0376__s02", 16),
    ("4ITcvEa_Acc_0205__s00", 8),
    ("o8RjAmBtyZo_0194__s02", 29),
    ("vEtfty4Cc6Y_0200__s02", 33),
    ("z0zSgR_oie4_0165__s03", 38),
    ("BD83pScFukQ_0217__s00", 13),
    ("BD83pScFukQ_0016__s02", 9),
    ("2b65WyiFC9k_0236__s01", 4),
    ("z0zSgR_oie4_0048__s05", 36),
    ("EUNlJU1BuzE_0145__s03", 24),
    ("EUNlJU1BuzE_0069__s01", 23),
    ("EM_ObHWvd94_0131__s02", 19),
    ("EM_ObHWvd94_0076__s01", 18),
    ("4ITcvEa_Acc_0142__s01", 7),
]


def read_wav(path: Path) -> np.ndarray:
    wave, sr = sf.read(path, dtype="float32")
    if sr != SR:
        raise RuntimeError(f"{path}: sr {sr} != {SR}")
    return np.asarray(wave).reshape(-1)


def lufs16(wave: np.ndarray) -> np.ndarray:
    from vifasttts.infer import _apply_target_lufs
    from vifasttts.runtime.postprocess import postprocess

    wave = postprocess(np.asarray(wave, dtype=np.float32), SR)
    return np.asarray(_apply_target_lufs(wave, SR, -16.0), dtype=np.float32)


def add_noise(wave: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    noise = rng.standard_normal(wave.size).astype(np.float32)
    speech_rms = float(np.sqrt(np.mean(wave.astype(np.float64) ** 2) + 1e-12))
    noise *= speech_rms / (np.sqrt(np.mean(noise.astype(np.float64) ** 2) + 1e-12)
                           * 10 ** (snr_db / 20.0))
    return np.clip(wave + noise, -1.0, 1.0).astype(np.float32)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--key", default=str(KEY))
    args = parser.parse_args()
    out = Path(args.out)
    key_path = Path(args.key)
    if out.exists():
        shutil.rmtree(out)
    (out / "audio").mkdir(parents=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    base = {}
    for item_id, index in SELECTED:
        b_path = A4 / f"{index:02d}_B.wav"
        c_path = A4 / f"{index:02d}_C.wav"
        base[item_id] = {"index": index, "B": read_wav(b_path), "C": read_wav(c_path)}

    trials = []
    # 16 chính
    for item_id, _index in SELECTED:
        trials.append({"kind": "main", "sentence": item_id,
                       "left": base[item_id]["B"].copy(), "right": base[item_id]["C"].copy(),
                       "left_src": "B", "right_src": "C", "correct_pre": "left"})
    # 4 dương: B sạch vs B + trắng SNR 30 dB
    for item_id, _index in SELECTED[:4]:
        clean = base[item_id]["B"]
        noisy = lufs16(add_noise(clean, 30.0, rng))
        trials.append({"kind": "positive", "sentence": item_id,
                       "left": clean.copy(), "right": noisy,
                       "left_src": "B_clean", "right_src": "B_noisy", "correct_pre": "left"})
    # 4 âm: C vs C
    for item_id, _index in SELECTED[4:8]:
        c = base[item_id]["C"]
        trials.append({"kind": "negative", "sentence": item_id,
                       "left": c.copy(), "right": c.copy(),
                       "left_src": "C", "right_src": "C", "correct_pre": "tie"})
    # 4 lặp: 4 cặp B/C đầu, đảo A/B
    repeat_origin = []
    for item_id, _index in SELECTED[:4]:
        trial = {"kind": "repeat", "sentence": item_id,
                 "left": base[item_id]["C"].copy(), "right": base[item_id]["B"].copy(),
                 "left_src": "C", "right_src": "B", "correct_pre": "right"}
        trials.append(trial)
        repeat_origin.append(item_id)

    order = rng.permutation(len(trials)).tolist()
    page_trials = []
    key_trials = []
    for page_index, trial_index in enumerate(order, start=1):
        trial = trials[trial_index]
        flip = bool(rng.integers(0, 2))
        left = trial["right"] if flip else trial["left"]
        right = trial["left"] if flip else trial["right"]
        left_src = trial["right_src"] if flip else trial["left_src"]
        right_src = trial["left_src"] if flip else trial["right_src"]
        correct_side = {"left": "B" if flip else "A",
                        "right": "A" if flip else "B",
                        "tie": "tie"}[trial["correct_pre"]]
        trial_id = f"t{page_index:02d}"
        sf.write(out / "audio" / f"{trial_id}_A.wav", lufs16(left), SR, subtype="PCM_16")
        sf.write(out / "audio" / f"{trial_id}_B.wav", lufs16(right), SR, subtype="PCM_16")
        page_trials.append({"id": trial_id, "kind": trial["kind"]})
        key_trials.append({
            "id": trial_id, "kind": trial["kind"], "sentence": trial["sentence"],
            "a_source": left_src, "b_source": right_src,
            "correct_side": correct_side,
            "correct_source": "tie" if trial["kind"] == "negative" else "B",
            "repeat_of": trial["sentence"] if trial["kind"] == "repeat" else None,
        })

    key = {"seed": SEED, "n_trials": len(trials), "trials": key_trials,
           "selected": [{"id": item, "index": index} for item, index in SELECTED],
           "repeat_sentences": repeat_origin}
    key_path.write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")

    html = _render_html(page_trials)
    (out / "index.html").write_text(html, encoding="utf-8")
    print(json.dumps({"page": str(out / "index.html"), "key": str(key_path),
                      "n_trials": len(trials), "seed": SEED}, ensure_ascii=False, indent=1))


def _render_html(trials: list[dict]) -> str:
    rows = []
    for trial in trials:
        trial_id = trial["id"]
        rows.append(f"""
<section class="trial" data-id="{trial_id}">
  <h3>Câu {trial_id[1:]}</h3>
  <div class="audio"><span>A</span><audio controls preload="none" src="audio/{trial_id}_A.wav"></audio></div>
  <div class="audio"><span>B</span><audio controls preload="none" src="audio/{trial_id}_B.wav"></audio></div>
  <div class="choices">
    <label><input type="radio" name="{trial_id}" value="A"> A</label>
    <label><input type="radio" name="{trial_id}" value="B"> B</label>
    <label><input type="radio" name="{trial_id}" value="tie"> Không phân biệt</label>
  </div>
</section>""")
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>V18.44 A5 — nghe mù B vs C</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:760px;margin:24px auto;padding:0 14px;line-height:1.45}}
h1{{font-size:1.35rem}} .note{{background:#f4f6f8;padding:12px 14px;border-radius:10px}}
.trial{{border:1px solid #ddd;border-radius:12px;padding:12px 14px;margin:14px 0}}
.audio{{display:flex;gap:10px;align-items:center;margin:8px 0}} .audio span{{width:20px;font-weight:700}}
audio{{width:100%}} .choices{{display:flex;gap:18px;flex-wrap:wrap;margin-top:8px}}
label{{cursor:pointer}} #bar{{position:sticky;bottom:0;background:#fff;padding:10px 0;border-top:1px solid #ddd;display:flex;gap:12px;align-items:center}}
button{{padding:8px 14px;border-radius:8px;border:1px solid #333;background:#111;color:#fff;font-weight:600}}
</style></head><body>
<h1>Nghe mù — bản nào ít rè nền hơn?</h1>
<div class="note">28 lượt, mỗi lượt nghe A và B rồi chọn <b>A</b>, <b>B</b> hoặc <b>Không phân biệt</b>.
Đây là bài kiểm chứng BAK, không phải chọn bản production. Vui lòng nghe bằng tai nghe và ở mức âm lượng vừa phải.</div>
{''.join(rows)}
<div id="bar"><span id="progress">0/28</span><button onclick="downloadCsv()">Tải CSV</button></div>
<script>
const ids = {json.dumps([t['id'] for t in trials])};
function answered(){{return ids.filter(id=>document.querySelector(`input[name="${{id}}"]:checked`)).length}}
function update(){{document.getElementById('progress').textContent=answered()+'/'+ids.length}}
document.querySelectorAll('input[type=radio]').forEach(el=>el.addEventListener('change',update));
function downloadCsv(){{
  let lines=['trial_id,answer'];
  for (const id of ids) {{
    const el=document.querySelector(`input[name="${{id}}"]:checked`);
    lines.push(id+','+(el?el.value:''));
  }}
  const blob=new Blob([lines.join('\\n')+ '\\n'],{{type:'text/csv;charset=utf-8'}});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='v1844_a5_answers.csv'; a.click();
}}
update();
</script></body></html>"""


if __name__ == "__main__":
    main()
