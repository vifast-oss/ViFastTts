"""v18.50 — A2: trang đánh dấu rè cục bộ theo âm tiết (66 mục).

20 câu × {P2 chunk, PILOT chunk, B Vocos mel gốc} + 3 lặp + 3 B cấy click 50 ms.
Xáo trộn seed 1850; key ngoài thư mục phục vụ; CSV item_id,syllables.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.v1845_a4_confirm import CFG32, HOLDOUT, P2, render_mel
from vifasttts.data.dataset import TtsDataset
from vifasttts.infer import Synthesizer

PILOT = Path("runs/v1848_pilot/last.pt")
OUT = Path("artifacts/listen_v1850_mark")
KEY = Path("artifacts/bench/v1850_mark/key.json")
SEED = 1850

SENTENCES = [
    "2b65WyiFC9k_0175__s01", "2b65WyiFC9k_0040__s00", "4ITcvEa_Acc_0216__s01",
    "4ITcvEa_Acc_0099__s00", "BD83pScFukQ_0009__s00", "BD83pScFukQ_0093__s00",
    "EM_ObHWvd94_0243__s00", "EM_ObHWvd94_0206__s01", "EUNlJU1BuzE_0196__s00",
    "EUNlJU1BuzE_0300__s00", "o8RjAmBtyZo_0130__s02", "o8RjAmBtyZo_0088__s01",
    "vEtfty4Cc6Y_0310__s01", "vEtfty4Cc6Y_0268__s01", "z0zSgR_oie4_0193__s02",
    "z0zSgR_oie4_0051__s01", "EUNlJU1BuzE_0289__s00", "EUNlJU1BuzE_0069__s00",
    "z0zSgR_oie4_0245__s00", "z0zSgR_oie4_0040__s00",
]
ARTIFICIAL = {
    "2b65WyiFC9k_0175__s01": {"target": 22, "start": 4.267},
    "EM_ObHWvd94_0243__s00": {"target": 21, "start": 4.629},
    "EUNlJU1BuzE_0196__s00": {"target": 26, "start": 4.000},
}
REPEATS = [
    ("2b65WyiFC9k_0175__s01", "P2"),
    ("2b65WyiFC9k_0040__s00", "PILOT"),
    ("4ITcvEa_Acc_0216__s01", "B"),
]


def lufs16(wave: np.ndarray) -> np.ndarray:
    from vifasttts.infer import _apply_target_lufs
    from vifasttts.runtime.postprocess import postprocess

    wave = postprocess(np.asarray(wave, dtype=np.float32), 24000)
    return np.asarray(_apply_target_lufs(wave, 24000, -16.0), dtype=np.float32)


def click_burst(wave: np.ndarray, start_s: float) -> np.ndarray:
    out = np.asarray(wave, dtype=np.float32).copy()
    start = int(start_s * 24000)
    length = int(0.05 * 24000)
    if start + length > out.size:
        length = max(0, out.size - start)
    rng = np.random.default_rng(1850)
    burst = 0.35 * rng.standard_normal(length).astype(np.float32)
    burst *= np.hanning(length).astype(np.float32) if length else 1.0
    out[start:start + length] += burst
    return np.clip(out, -1.0, 1.0).astype(np.float32)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "audio").mkdir(parents=True)
    KEY.parent.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    dataset = TtsDataset(HOLDOUT, cfg, cache_dir=cfg.get("training", {}).get("cache_dir"))
    by_id = {row["id"]: i for i, row in enumerate(dataset.rows)}
    p2 = Synthesizer(cfg, P2, device="cpu")
    p2.model.eval()
    p2.vocoder.eval()
    pilot = Synthesizer(cfg, P2, device="cpu")
    state = torch.load(PILOT, map_location="cpu", weights_only=False)
    pilot.model.load_state_dict(state["ema"], strict=False)
    pilot.model.eval()
    pilot.vocoder.eval()

    main = []
    hop = 256
    for sentence in SENTENCES:
        i = by_id[sentence]
        row = dataset.rows[i]
        item = dataset[i]
        syllables = [s["normalized"] for s in row["syllables"]]
        # A = wav gốc cắt đúng frame_range, -16 LUFS
        wave, _sr = sf.read(row["audio_path"], dtype="float32")
        wave = np.asarray(wave).reshape(-1)
        start, end = (int(x) for x in row["frame_range"])
        path_a = OUT / "audio" / f"main_{len(main):02d}.wav"
        sf.write(path_a, lufs16(wave[start * hop:end * hop]), 24000, subtype="PCM_16")
        main.append({"sentence": sentence, "version": "A", "path": path_a,
                     "syllables": syllables})
        for version, engine in (("P2", p2), ("PILOT", pilot)):
            path = OUT / "audio" / f"main_{len(main):02d}.wav"
            engine.synthesize(row["text"], path, gate_threshold=0.5, sharpen_alpha=0.0,
                              target_lufs=-16, peak_normalize=False, max_chars=400)
            main.append({"sentence": sentence, "version": version, "path": path,
                         "syllables": syllables})
        path_b = OUT / "audio" / f"main_{len(main):02d}.wav"
        render_mel(p2, item["mel"].detach().cpu().numpy(), path_b, 24000)
        main.append({"sentence": sentence, "version": "B", "path": path_b,
                     "syllables": syllables})
        print(json.dumps({"done": sentence}), flush=True)

    # 3 mục B cấy click
    controls = []
    for sentence, info in ARTIFICIAL.items():
        src = next(item for item in main if item["sentence"] == sentence and item["version"] == "B")
        wave, _ = sf.read(src["path"], dtype="float32")
        path = OUT / "audio" / f"ctrl_{len(controls):02d}.wav"
        sf.write(path, lufs16(click_burst(np.asarray(wave).reshape(-1), info["start"])),
                 24000, subtype="PCM_16")
        controls.append({"kind": "artificial", "sentence": sentence, "version": "B",
                         "target": info["target"], "path": path,
                         "syllables": src["syllables"]})
    # 3 mục lặp
    for sentence, version in REPEATS:
        src = next(item for item in main if item["sentence"] == sentence and item["version"] == version)
        path = OUT / "audio" / f"ctrl_{len(controls):02d}.wav"
        path.write_bytes(src["path"].read_bytes())
        controls.append({"kind": "repeat", "sentence": sentence, "version": version,
                         "repeat_of": str(src["path"]), "path": path,
                         "syllables": src["syllables"]})

    items = main + controls
    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(items)).tolist()
    page = []
    key = []
    for page_index, item_index in enumerate(order, start=1):
        item = items[item_index]
        item_id = f"i{page_index:02d}"
        page.append({"id": item_id, "version": item["version"], "syllables": item["syllables"]})
        key.append({"id": item_id, "sentence": item["sentence"], "version": item["version"],
                    "kind": item.get("kind", "main"),
                    "target": item.get("target"),
                    "repeat_of": item.get("repeat_of"),
                    "syllables": item["syllables"], "path": str(item["path"])})
    key_doc = {"seed": SEED, "n": len(key), "items": key,
               "artificial_positions": ARTIFICIAL, "repeats": REPEATS}
    KEY.write_text(json.dumps(key_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    # Chỉ copy audio được phục vụ, đổi tên theo id
    for page_item, key_item in zip(page, key):
        src = Path(key_item["path"])
        dst = OUT / "audio" / f"{page_item['id']}.wav"
        if src != dst:
            dst.write_bytes(src.read_bytes())
    (OUT / "index.html").write_text(_html(page), encoding="utf-8")
    print(json.dumps({"page": str(OUT / "index.html"), "key": str(KEY),
                      "n": len(page), "seed": SEED}, ensure_ascii=False, indent=1))


def _html(items: list[dict]) -> str:
    sections = []
    for item in items:
        item_id = item["id"]
        buttons = "".join(
            f'<button type="button" data-idx="{i + 1}" onclick="toggle(this)">{text}</button>'
            for i, text in enumerate(item["syllables"]))
        sections.append(f"""
<section class="item" data-id="{item_id}">
  <h3>Mục {item_id[1:]}</h3>
  <audio controls preload="none" src="audio/{item_id}.wav"></audio>
  <div class="syllables">{buttons}</div>
  <label class="mismatch"><input type="checkbox" class="mm" data-id="{item_id}"> Văn bản không khớp âm thanh</label>
</section>""")
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>V18.50 — đánh dấu rè cục bộ</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:820px;margin:24px auto;padding:0 14px;line-height:1.45}}
h1{{font-size:1.35rem}} .note{{background:#f4f6f8;padding:12px 14px;border-radius:10px}}
.item{{border:1px solid #ddd;border-radius:12px;padding:12px 14px;margin:14px 0}}
audio{{width:100%;margin:8px 0}} .syllables{{display:flex;gap:6px;flex-wrap:wrap}}
button{{padding:5px 9px;border-radius:8px;border:1px solid #bbb;background:#fff;cursor:pointer}}
button.on{{background:#111;color:#fff;border-color:#111}}
.mismatch{{display:block;margin-top:9px;color:#a33;font-size:.92rem}}
#bar{{position:sticky;bottom:0;background:#fff;padding:10px 0;border-top:1px solid #ddd;display:flex;gap:12px;align-items:center}}
#save{{padding:8px 14px;border-radius:8px;border:1px solid #333;background:#111;color:#fff;font-weight:600}}
</style></head><body>
<h1>Đánh dấu chỗ nghe thấy rè/rít/vỡ cục bộ</h1>
<div class="note">Bấm vào <b>âm tiết</b> nghe thấy rè/rít/vỡ riêng ở chỗ đó; có thể bấm nhiều âm tiết,
hoặc không bấm nếu không nghe rõ. <b>Không chắc thì đừng bấm.</b> Nếu chữ hiển thị không khớp với
giọng đọc, tick ô <b>"Văn bản không khớp âm thanh"</b>. Nghe lại tự do trước khi sang mục khác.</div>
{''.join(sections)}
<div id="bar"><span id="progress">0/{len(items)}</span><button id="save" onclick="downloadCsv()">Tải CSV</button></div>
<script>
const ids = {json.dumps([item['id'] for item in items])};
function selected(id){{return [...document.querySelectorAll(`section[data-id="${{id}}"] button.on`)].map(b=>Number(b.dataset.idx));}}
function mismatch(id){{const el=document.querySelector(`input.mm[data-id="${{id}}"]`); return el && el.checked ? 1 : 0;}}
function toggle(btn){{btn.classList.toggle('on'); update();}}
function update(){{document.getElementById('progress').textContent=ids.filter(id=>selected(id).length).length+'/'+ids.length;}}
function downloadCsv(){{
  let lines=['item_id,syllables,mismatch'];
  for (const id of ids) lines.push(id+','+selected(id).join(';')+','+mismatch(id));
  const blob=new Blob([lines.join('\\n')+'\\n'],{{type:'text/csv;charset=utf-8'}});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='v1850_mark_answers.csv'; a.click();
}}
update();
</script></body></html>"""


if __name__ == "__main__":
    main()
