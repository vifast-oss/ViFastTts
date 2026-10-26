"""v18.49 — A3: trang nghe mù PILOT vs CONTROL (28 lượt, chunk mode).

16 PILOT-vs-CONTROL + 4 dương (CONTROL vs CONTROL+nhiễu) + 4 âm (CONTROL vs CONTROL)
+ 4 lặp đảo A/B. Seed 1849; key ngoài thư mục phục vụ.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

META = Path("artifacts/bench/v1849_a2_chunk/meta.json")
AUDIO = Path("artifacts/bench/v1849_a2_chunk")
OUT = Path("artifacts/listen_v1849_a3")
KEY = Path("artifacts/bench/v1849_a3/key.json")
SEED = 1849

LISTEN16 = [
    "2b65WyiFC9k_0093__s00", "4ITcvEa_Acc_0029__s00", "4ITcvEa_Acc_0097__s01",
    "EM_ObHWvd94_0349__s00", "EUNlJU1BuzE_0181__s00", "EUNlJU1BuzE_0101__s00",
    "o8RjAmBtyZo_0099__s01", "vEtfty4Cc6Y_0102__s00", "vEtfty4Cc6Y_0257__s01",
    "vEtfty4Cc6Y_0033__s01", "z0zSgR_oie4_0078__s00", "z0zSgR_oie4_0246__s00",
    "z0zSgR_oie4_0099__s00", "EUNlJU1BuzE_0272__s00", "4ITcvEa_Acc_0092__s01",
    "vEtfty4Cc6Y_0008__s02",
]


def read(path: Path) -> np.ndarray:
    wave, sr = sf.read(path, dtype="float32")
    if sr != 24000:
        raise RuntimeError(f"{path}: sr {sr}")
    return np.asarray(wave).reshape(-1)


def lufs16(wave: np.ndarray) -> np.ndarray:
    from vifasttts.infer import _apply_target_lufs
    from vifasttts.runtime.postprocess import postprocess

    wave = postprocess(np.asarray(wave, dtype=np.float32), 24000)
    return np.asarray(_apply_target_lufs(wave, 24000, -16.0), dtype=np.float32)


def add_noise(wave: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    noise = rng.standard_normal(wave.size).astype(np.float32)
    speech_rms = float(np.sqrt(np.mean(wave.astype(np.float64) ** 2) + 1e-12))
    noise *= speech_rms / (np.sqrt(np.mean(noise.astype(np.float64) ** 2) + 1e-12)
                           * 10 ** (snr_db / 20.0))
    return np.clip(wave + noise, -1.0, 1.0).astype(np.float32)


def main() -> None:
    meta = json.loads(META.read_text(encoding="utf-8"))
    index = {item_id: i for i, item_id in enumerate(meta["ids"])}
    rng = np.random.default_rng(SEED)
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "audio").mkdir(parents=True)
    KEY.parent.mkdir(parents=True, exist_ok=True)

    trials = []
    for item_id in LISTEN16:
        i = index[item_id]
        trials.append({"kind": "main", "sentence": item_id,
                       "left": read(AUDIO / "pilot" / f"{i:02d}.wav"),
                       "right": read(AUDIO / "control" / f"{i:02d}.wav"),
                       "left_src": "PILOT", "right_src": "CONTROL", "correct_pre": "left"})
    for item_id in LISTEN16[:4]:
        i = index[item_id]
        clean = read(AUDIO / "control" / f"{i:02d}.wav")
        noisy = lufs16(add_noise(clean, 30.0, rng))
        trials.append({"kind": "positive", "sentence": item_id,
                       "left": clean.copy(), "right": noisy,
                       "left_src": "CONTROL_clean", "right_src": "CONTROL_noisy",
                       "correct_pre": "left"})
    for item_id in LISTEN16[4:8]:
        i = index[item_id]
        c = read(AUDIO / "control" / f"{i:02d}.wav")
        trials.append({"kind": "negative", "sentence": item_id,
                       "left": c.copy(), "right": c.copy(),
                       "left_src": "CONTROL", "right_src": "CONTROL", "correct_pre": "tie"})
    for item_id in LISTEN16[:4]:
        i = index[item_id]
        trials.append({"kind": "repeat", "sentence": item_id,
                       "left": read(AUDIO / "control" / f"{i:02d}.wav"),
                       "right": read(AUDIO / "pilot" / f"{i:02d}.wav"),
                       "left_src": "CONTROL", "right_src": "PILOT", "correct_pre": "right"})

    order = rng.permutation(len(trials)).tolist()
    page = []
    key = []
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
        sf.write(OUT / "audio" / f"{trial_id}_A.wav", lufs16(left), 24000, subtype="PCM_16")
        sf.write(OUT / "audio" / f"{trial_id}_B.wav", lufs16(right), 24000, subtype="PCM_16")
        page.append({"id": trial_id, "kind": trial["kind"]})
        key.append({"id": trial_id, "kind": trial["kind"], "sentence": trial["sentence"],
                    "a_source": left_src, "b_source": right_src,
                    "correct_side": correct_side,
                    "correct_source": "PILOT" if trial["kind"] in ("main", "repeat")
                    else ("CONTROL" if trial["kind"] == "negative" else "CONTROL_clean"),
                    "repeat_of": trial["sentence"] if trial["kind"] == "repeat" else None})
    KEY.write_text(json.dumps({"seed": SEED, "trials": key, "n": len(key),
                               "listen16": LISTEN16}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    (OUT / "index.html").write_text(_html(page), encoding="utf-8")
    print(json.dumps({"page": str(OUT / "index.html"), "key": str(KEY),
                      "n": len(page), "seed": SEED}, ensure_ascii=False, indent=1))


def _html(trials: list[dict]) -> str:
    sections = []
    for trial in trials:
        trial_id = trial["id"]
        sections.append(f"""
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
<title>V18.49 A3 — PILOT vs CONTROL</title>
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
Đây là kiểm chứng PILOT vs CONTROL, không phải chọn production. Nghe bằng tai nghe, âm lượng vừa phải.</div>
{''.join(sections)}
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
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='v1849_a3_answers.csv'; a.click();
}}
update();
</script></body></html>"""


if __name__ == "__main__":
    main()
