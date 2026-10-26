"""v18.52 — A2: trang hiệu chỉnh bộ dò đuôi (40 segment + 8 đối chứng).

Chỉ phát vùng đuôi + 1 s trước; vạch đánh dấu chỗ bắt đầu đuôi.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from vifasttts.data.tail_detect import tail_start_frame

MANIFESTS = ["data/codelung/v32/train_clean_v2_dur_seg_slot4.jsonl",
             "data/codelung/v32/holdout_clean_v2_dur_seg_slot4.jsonl"]
OUT = Path("artifacts/listen_v1852_tail")
KEY = Path("artifacts/bench/v1852_tail/key.json")
SEED = 1852
HOP = 256
SR = 24000

SELECTED = [
    "4kyqfOypVWI_0437__s00", "4kyqfOypVWI_0346__s02", "5KnS0TGxWLg_0314__s01",
    "5KnS0TGxWLg_0117__s00", "4kyqfOypVWI_0041__s01", "4kyqfOypVWI_0258__s04",
    "4kyqfOypVWI_0024__s02", "4kyqfOypVWI_0190__s00", "5KnS0TGxWLg_0015__s00",
    "4kyqfOypVWI_0177__s01", "4kyqfOypVWI_0289__s01", "4kyqfOypVWI_0128__s02",
    "4kyqfOypVWI_0227__s03", "5KnS0TGxWLg_0617__s03", "4kyqfOypVWI_0354__s01",
    "5KnS0TGxWLg_0326__s00", "5KnS0TGxWLg_0096__s00", "4kyqfOypVWI_0166__s02",
    "5KnS0TGxWLg_0309__s02", "4kyqfOypVWI_0149__s02", "4kyqfOypVWI_0224__s02",
    "5KnS0TGxWLg_0409__s02", "4kyqfOypVWI_0019__s05", "4kyqfOypVWI_0193__s02",
    "5KnS0TGxWLg_0408__s00", "5KnS0TGxWLg_0354__s02", "4kyqfOypVWI_0369__s02",
    "5KnS0TGxWLg_0380__s01", "5KnS0TGxWLg_0015__s01", "5KnS0TGxWLg_0009__s00",
    "4kyqfOypVWI_0336__s04", "5KnS0TGxWLg_0078__s00", "4kyqfOypVWI_0188__s00",
    "4kyqfOypVWI_0242__s02", "4kyqfOypVWI_0252__s01", "5KnS0TGxWLg_0020__s01",
    "4kyqfOypVWI_0215__s02", "4kyqfOypVWI_0244__s04", "4kyqfOypVWI_0024__s04",
    "5KnS0TGxWLg_0298__s01",
]
CTRL_POS = [
    ("4kyqfOypVWI_0289__s01", "4kyqfOypVWI_0001__s03"),
    ("4kyqfOypVWI_0128__s02", "4kyqfOypVWI_0002__s05"),
    ("4kyqfOypVWI_0227__s03", "4kyqfOypVWI_0004__s00"),
    ("5KnS0TGxWLg_0617__s03", "4kyqfOypVWI_0004__s01"),
]
CTRL_NEG = ["4kyqfOypVWI_0354__s01", "5KnS0TGxWLg_0326__s00",
            "5KnS0TGxWLg_0096__s00", "4kyqfOypVWI_0166__s02"]


def lufs16(wave: np.ndarray) -> np.ndarray:
    from vifasttts.infer import _apply_target_lufs
    from vifasttts.runtime.postprocess import postprocess

    wave = postprocess(np.asarray(wave, dtype=np.float32), SR)
    return np.asarray(_apply_target_lufs(wave, SR, -16.0), dtype=np.float32)


def load_rows() -> dict:
    rows = {}
    for path in MANIFESTS:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["id"]] = row
    return rows


def segment(row: dict) -> tuple[np.ndarray, int]:
    wav, sr = sf.read(row["audio_path"], dtype="float32")
    if sr != SR:
        raise RuntimeError(f"{row['audio_path']}: sr {sr}")
    wav = np.asarray(wav).reshape(-1)
    start, end = (int(x) for x in row["frame_range"])
    return wav[start * HOP:end * HOP], tail_start_frame(
        int(row.get("lead_frames") or 0), row["durations"], row["gaps"])


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "audio").mkdir(parents=True)
    KEY.parent.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    scores = {json.loads(line)["id"]: json.loads(line)
              for line in Path("artifacts/bench/v1852_tail/scan.jsonl").read_text(
                  encoding="utf-8").splitlines() if line.strip()}
    rng = np.random.default_rng(SEED)
    items = []
    for item_id in SELECTED:
        seg, tail = segment(rows[item_id])
        start = max(0, tail * HOP - SR)
        audio = lufs16(seg[start:])
        items.append({"kind": "calib", "id": item_id, "audio": audio,
                      "marker": (tail * HOP - start) / max(audio.size, 1),
                      "detector_positive": bool(scores.get(item_id, {}).get("positive"))})
    for base, source in CTRL_POS:
        seg, tail = segment(rows[base])
        src, src_tail = segment(rows[source])
        tail_samples = seg[tail * HOP:].copy()
        speech = src[src_tail * HOP:src_tail * HOP + int(0.4 * SR)]
        if speech.size:
            tail_samples[:min(speech.size, tail_samples.size)] = speech[:min(speech.size, tail_samples.size)]
        full = np.concatenate([seg[max(0, tail * HOP - SR):tail * HOP], tail_samples])
        items.append({"kind": "control_positive", "id": base, "audio": lufs16(full),
                      "marker": SR / max(full.size, 1), "detector_positive": True})
    for base in CTRL_NEG:
        seg, tail = segment(rows[base])
        full = np.concatenate([seg[max(0, tail * HOP - SR):tail * HOP],
                               np.zeros(seg.size - tail * HOP, dtype=np.float32)])
        items.append({"kind": "control_negative", "id": base, "audio": lufs16(full),
                      "marker": SR / max(full.size, 1), "detector_positive": False})
    order = rng.permutation(len(items)).tolist()
    page, key = [], []
    for page_index, item_index in enumerate(order, start=1):
        item = items[item_index]
        pid = f"t{page_index:02d}"
        sf.write(OUT / "audio" / f"{pid}.wav", item["audio"], SR, subtype="PCM_16")
        page.append({"id": pid, "marker": round(item["marker"], 4)})
        key.append({"id": pid, "source": item["id"], "kind": item["kind"],
                    "detector_positive": item["detector_positive"]})
    KEY.write_text(json.dumps({"seed": SEED, "items": key}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    (OUT / "index.html").write_text(_html(page), encoding="utf-8")
    print(json.dumps({"page": str(OUT / "index.html"), "key": str(KEY), "n": len(page)},
                     ensure_ascii=False, indent=1))


def _html(items: list[dict]) -> str:
    sections = []
    for item in items:
        iid = item["id"]
        left = round(item["marker"] * 100, 2)
        sections.append(f"""
<section class="item" data-id="{iid}">
  <h3>Mục {iid[1:]}</h3>
  <audio controls preload="none" src="audio/{iid}.wav"></audio>
  <div class="bar"><div class="marker" style="left:{left}%"></div></div>
  <div class="choices">
    <label><input type="radio" name="{iid}" value="co"> Có</label>
    <label><input type="radio" name="{iid}" value="khong"> Không</label>
    <label><input type="radio" name="{iid}" value="khong_chac"> Không chắc</label>
  </div>
</section>""")
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>V18.52 — kiểm đuôi</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:760px;margin:24px auto;padding:0 14px;line-height:1.45}}
h1{{font-size:1.3rem}} .note{{background:#f4f6f8;padding:12px 14px;border-radius:10px}}
.item{{border:1px solid #ddd;border-radius:12px;padding:12px 14px;margin:14px 0}}
audio{{width:100%;margin:8px 0}} .bar{{position:relative;height:12px;background:#eee;border-radius:6px;margin:8px 0}}
.marker{{position:absolute;top:-4px;width:3px;height:20px;background:#d00}}
.choices{{display:flex;gap:18px;flex-wrap:wrap}}
#bar{{position:sticky;bottom:0;background:#fff;padding:10px 0;border-top:1px solid #ddd;display:flex;gap:12px;align-items:center}}
button{{padding:8px 14px;border-radius:8px;border:1px solid #333;background:#111;color:#fff;font-weight:600}}
</style></head><body>
<h1>Kiểm tiếng nói ở đuôi segment</h1>
<div class="note">Mỗi mục phát <b>1 giây trước + vùng đuôi</b>; vạch đỏ là chỗ bắt đầu đuôi.
Hỏi: <b>Sau vạch có tiếng nói không?</b> Chọn Có / Không / Không chắc. Nghe lại tự do.</div>
{''.join(sections)}
<div id="bar"><span id="progress">0/{len(items)}</span><button onclick="downloadCsv()">Tải CSV</button></div>
<script>
const ids={json.dumps([x['id'] for x in items])};
function val(id){{const e=document.querySelector(`input[name="${{id}}"]:checked`);return e?e.value:''}}
function update(){{document.getElementById('progress').textContent=ids.filter(id=>val(id)).length+'/'+ids.length}}
document.querySelectorAll('input[type=radio]').forEach(e=>e.addEventListener('change',update));
function downloadCsv(){{let L=['item_id,answer'];for(const id of ids)L.push(id+','+val(id));
const b=new Blob([L.join('\\n')+'\\n'],{{type:'text/csv;charset=utf-8'}});const a=document.createElement('a');
a.href=URL.createObjectURL(b);a.download='v1852_tail_answers.csv';a.click();}}
update();
</script></body></html>"""


if __name__ == "__main__":
    main()
