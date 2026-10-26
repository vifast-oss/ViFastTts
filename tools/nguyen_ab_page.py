"""N0 — trang nghe A/B: giọng thật · model mới · P2 zero-shot.

Mỗi mục: 1 câu holdout. Phát lần lượt (1) audio THẬT, (2) A, (3) B (A/B xáo seed).
Nghe xong chọn A / B / hòa; CSV `item_id,choice`.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--texts", required=True)
    parser.add_argument("--real-dir", required=True)
    parser.add_argument("--new-dir", required=True)
    parser.add_argument("--p2-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    out, key_path = Path(args.out), Path(args.key)
    if out.exists():
        shutil.rmtree(out)
    (out / "audio").mkdir(parents=True)
    rows = json.loads(Path(args.texts).read_text(encoding="utf-8"))
    rng = random.Random(args.seed)
    key = []
    for row in rows:
        rid = str(row["id"])
        real = Path(args.real_dir) / f"{rid}.wav"
        new = Path(args.new_dir) / f"{rid}.wav"
        p2 = Path(args.p2_dir) / f"{rid}.wav"
        if not (real.exists() and new.exists() and p2.exists()):
            continue
        for name, src in (("real", real), ("new", new), ("p2", p2)):
            shutil.copyfile(src, out / "audio" / f"{rid}_{name}.wav")
        swap = rng.random() < 0.5
        a, b = ("p2", "new") if swap else ("new", "p2")
        key.append({"id": rid, "A": a, "B": b, "text": row["text"]})
    key_path.write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    sections = []
    for item in key:
        rid = item["id"]
        sections.append(f"""
<section class="item" data-id="{rid}">
  <p><b>Câu {rid[-5:]}</b> — {item['text']}</p>
  <div class="row"><span>Thật</span><audio controls preload="none" src="audio/{rid}_real.wav"></audio></div>
  <div class="row"><span>A</span><audio controls preload="none" src="audio/{rid}_{item['A']}.wav"></audio></div>
  <div class="row"><span>B</span><audio controls preload="none" src="audio/{rid}_{item['B']}.wav"></audio></div>
  <div class="choices">
    <label><input type="radio" name="{rid}" value="A"> A tốt hơn</label>
    <label><input type="radio" name="{rid}" value="B"> B tốt hơn</label>
    <label><input type="radio" name="{rid}" value="hoa"> Hòa</label>
  </div>
</section>""")
    html = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>N0 — nghe A/B</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:860px;margin:24px auto;padding:0 14px;line-height:1.45}}
.item{{border:1px solid #ddd;border-radius:12px;padding:12px 14px;margin:14px 0}}
.row{{display:flex;gap:10px;align-items:center}} .row span{{width:44px;font-weight:600}}
audio{{width:100%;margin:5px 0}} .choices{{display:flex;gap:18px;flex-wrap:wrap;margin-top:6px}}
#bar{{position:sticky;bottom:0;background:#fff;padding:10px 0;border-top:1px solid #ddd;display:flex;gap:12px}}
button{{padding:8px 14px;border-radius:8px;border:1px solid #333;background:#111;color:#fff;font-weight:600}}
</style></head><body>
<h1>Nghe A/B — giọng mới so với P2 zero-shot</h1>
<p>Mỗi câu có <b>audio thật</b> để tham chiếu, rồi A và B (xáo). Chọn bản nghe tự nhiên / đúng giọng hơn.</p>
{''.join(sections)}
<div id="bar"><span id="p">0/{len(key)}</span><button onclick="dl()">Tải CSV</button></div>
<script>
const ids={json.dumps([x['id'] for x in key])};
function v(id){{const e=document.querySelector(`input[name="${{id}}"]:checked`);return e?e.value:''}}
function upd(){{document.getElementById('p').textContent=ids.filter(i=>v(i)).length+'/'+ids.length}}
document.querySelectorAll('input[type=radio]').forEach(e=>e.addEventListener('change',upd));
function dl(){{let L=['item_id,choice'];for(const i of ids)L.push(i+','+v(i));const b=new Blob([L.join('\\n')+'\\n'],{{type:'text/csv'}});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='n0_ab.csv';a.click();}}
upd();
</script></body></html>"""
    (out / "index.html").write_text(html, encoding="utf-8")
    print(json.dumps({"page": str(out / "index.html"), "key": str(key_path), "n": len(key)}))


if __name__ == "__main__":
    main()
