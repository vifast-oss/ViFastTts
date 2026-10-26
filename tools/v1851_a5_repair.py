"""v18.51 — A5: sửa thử 40 clip bằng cắt mốc cuối nhãn + đệm 0,05 s.

Chỉ tạo bản sửa trong thư mục riêng; không ghi đè dữ liệu gốc.
Chấm tự động CER ASR vs nhãn; xuất trang 3 nút (khớp / dư / cụt).
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

from tools.v1850_mark_page import lufs16
from tools.v1851_asr_audit import match, transcribe_words

MANIFEST = Path("data/codelung/v32/holdout_clean_v2_dur_seg_slot4.jsonl")
OUT = Path("artifacts/bench/v1851_a5")
PAGE = Path("artifacts/listen_v1851_a5")
KEY = Path("artifacts/bench/v1851_a5/key.json")
PAD_SECONDS = 0.05
HOP = 256
SR = 24000

IDS = [
    "2b65WyiFC9k_0009__s00", "2b65WyiFC9k_0031__s00", "2b65WyiFC9k_0036__s01",
    "2b65WyiFC9k_0065__s02", "2b65WyiFC9k_0140__s01", "2b65WyiFC9k_0155__s01",
    "2b65WyiFC9k_0162__s00", "2b65WyiFC9k_0222__s01", "4ITcvEa_Acc_0033__s01",
    "4ITcvEa_Acc_0042__s00", "4ITcvEa_Acc_0062__s03", "4ITcvEa_Acc_0098__s01",
    "4ITcvEa_Acc_0168__s02", "BD83pScFukQ_0013__s02", "BD83pScFukQ_0085__s02",
    "BD83pScFukQ_0181__s01", "BD83pScFukQ_0204__s02", "BD83pScFukQ_0382__s03",
    "EM_ObHWvd94_0032__s02", "EM_ObHWvd94_0102__s01", "EM_ObHWvd94_0127__s00",
    "EM_ObHWvd94_0241__s00", "EM_ObHWvd94_0330__s01", "EM_ObHWvd94_0352__s01",
    "EUNlJU1BuzE_0003__s01", "EUNlJU1BuzE_0029__s00", "EUNlJU1BuzE_0268__s02",
    "EUNlJU1BuzE_0294__s01", "o8RjAmBtyZo_0084__s03", "vEtfty4Cc6Y_0018__s00",
    "vEtfty4Cc6Y_0057__s02", "vEtfty4Cc6Y_0122__s04", "z0zSgR_oie4_0015__s02",
    "z0zSgR_oie4_0037__s00", "z0zSgR_oie4_0059__s00", "z0zSgR_oie4_0135__s04",
    "z0zSgR_oie4_0143__s03", "z0zSgR_oie4_0166__s01", "z0zSgR_oie4_0167__s02",
    "z0zSgR_oie4_0224__s01",
]


def main() -> None:
    from faster_whisper import WhisperModel

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "repaired").mkdir(parents=True)
    if PAGE.exists():
        shutil.rmtree(PAGE)
    (PAGE / "audio").mkdir(parents=True)
    rows = {json.loads(line)["id"]: json.loads(line)
            for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()}
    model = WhisperModel("small", device="cpu", compute_type="int8")
    results = []
    for index, item_id in enumerate(IDS):
        row = rows[item_id]
        wav, _sr = sf.read(row["audio_path"], dtype="float32")
        wav = np.asarray(wav).reshape(-1)
        label_end_frames = (int(row.get("lead_frames") or 0) + sum(row["durations"])
                            + sum(row["gaps"][:-1]))
        start_sample = int(row["frame_range"][0]) * HOP
        cut_sample = min(wav.size, start_sample + label_end_frames * HOP
                         + int(PAD_SECONDS * SR))
        repaired = lufs16(wav[start_sample:cut_sample])
        path = OUT / "repaired" / f"{item_id}.wav"
        sf.write(path, repaired, SR, subtype="PCM_16")
        words = transcribe_words(model, path)
        hyp = [w["text"] for w in words]
        label = [s["normalized"] for s in row["syllables"]]
        info = match(label, hyp)
        results.append({"id": item_id, "cut_seconds": round((cut_sample - start_sample) / SR, 3),
                        "original_seconds": round((row["frame_range"][1]
                                                   - row["frame_range"][0]) * HOP / SR, 3),
                        "cer": info["cer"], "end_extra": info["end_extra"],
                        "missing": info["missing"], "n_label": len(label),
                        "n_asr": len(hyp),
                        "last_present": bool(label and label[-1] in hyp)})
        print(json.dumps({"done": index + 1, "total": len(IDS), "cer": info["cer"]}),
              flush=True)
    # page
    page = []
    for index, item in enumerate(results):
        page.append({"id": f"c{index + 1:02d}", "source": item["id"]})
        dst = PAGE / "audio" / f"c{index + 1:02d}.wav"
        dst.write_bytes((OUT / "repaired" / f"{item['id']}.wav").read_bytes())
    key = {"padding_seconds": PAD_SECONDS, "items": page}
    KEY.write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    (PAGE / "index.html").write_text(_html(page), encoding="utf-8")
    auto = {"n": len(results),
            "cer_le_0.1": sum(1 for x in results if x["cer"] <= 0.1),
            "cer_le_0.1_frac": round(sum(1 for x in results if x["cer"] <= 0.1) / len(results), 3),
            "no_end_extra": sum(1 for x in results if not x["end_extra"]),
            "last_missing": sum(1 for x in results if not x["last_present"])}
    result = {"padding_seconds": PAD_SECONDS, "rows": results, "auto": auto}
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps(auto, ensure_ascii=False, indent=1))


def _html(items: list[dict]) -> str:
    sections = []
    for item in items:
        cid = item["id"]
        sections.append(f"""
<section class="item" data-id="{cid}">
  <h3>Clip {cid[1:]}</h3>
  <audio controls preload="none" src="audio/{cid}.wav"></audio>
  <div class="choices">
    <label><input type="radio" name="{cid}" value="khop"> Khớp</label>
    <label><input type="radio" name="{cid}" value="du"> Dư</label>
    <label><input type="radio" name="{cid}" value="cut"> Cụt</label>
  </div>
</section>""")
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>V18.51 A5 — kiểm bản sửa mốc cuối</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:760px;margin:24px auto;padding:0 14px;line-height:1.45}}
h1{{font-size:1.35rem}} .note{{background:#f4f6f8;padding:12px 14px;border-radius:10px}}
.item{{border:1px solid #ddd;border-radius:12px;padding:12px 14px;margin:14px 0}}
audio{{width:100%;margin:8px 0}} .choices{{display:flex;gap:18px;flex-wrap:wrap}}
button{{padding:8px 14px;border-radius:8px;border:1px solid #333;background:#111;color:#fff;font-weight:600}}
#bar{{position:sticky;bottom:0;background:#fff;padding:10px 0;border-top:1px solid #ddd;display:flex;gap:12px;align-items:center}}
</style></head><body>
<h1>Kiểm bản sửa mốc cuối</h1>
<div class="note">Nghe từng clip đã sửa. Chọn <b>Khớp</b> nếu đọc đúng hết chữ trong nhãn,
<b>Dư</b> nếu còn đọc thêm từ, <b>Cụt</b> nếu mất chữ cuối. Nghe lại tự do.</div>
{''.join(sections)}
<div id="bar"><span id="progress">0/{len(items)}</span><button onclick="downloadCsv()">Tải CSV</button></div>
<script>
const ids = {json.dumps([x['id'] for x in items])};
function val(id){{const el=document.querySelector(`input[name="${{id}}"]:checked`); return el?el.value:'';}}
function update(){{document.getElementById('progress').textContent=ids.filter(id=>val(id)).length+'/'+ids.length;}}
document.querySelectorAll('input[type=radio]').forEach(el=>el.addEventListener('change',update));
function downloadCsv(){{let lines=['item_id,label']; for(const id of ids) lines.push(id+','+val(id));
 const b=new Blob([lines.join('\\n')+'\\n'],{{type:'text/csv;charset=utf-8'}}); const a=document.createElement('a');
 a.href=URL.createObjectURL(b); a.download='v1851_a5_answers.csv'; a.click();}}
update();
</script></body></html>"""


if __name__ == "__main__":
    main()
