"""tools/ab_base_vs_small.py — mở A/B blind giữa N0 small và base trên cùng câu holdout.

Sinh:
- `small/<id>.wav`, `base/<id>.wav`, `real/<id>.wav` (không commit; artifacts local)
- `index.html` + `key.json` (A/B đã xáo seed, không lộ bản nào)
- nút tải CSV để gửi kết quả nghe.

Chạy:
  .venv/bin/python tools/ab_base_vs_small.py \
      --out artifacts/listen_ngochuyen/ab_base_vs_small \
      --device mps --clips 24
"""

from __future__ import annotations

import argparse
import html
import json
import random
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

TEXTS = _ROOT / "artifacts" / "ngochuyen" / "demo_texts.json"
MANIFEST = _ROOT / "data" / "ngochuyen" / "manifests" / "holdout_dur_seg_slot4.jsonl"
SMALL_CONFIG = _ROOT / "runs" / "acoustic_ngochuyen_q" / "resolved_config.json"
SMALL_CKPT = _ROOT / "runs" / "acoustic_ngochuyen_q" / "init_q.pt"
BASE_CONFIG = _ROOT / "runs" / "acoustic_ngochuyen_base" / "resolved_config.json"
BASE_CKPT = _ROOT / "runs" / "acoustic_ngochuyen_base" / "best.pt"


def _manifest_audio() -> dict[str, str]:
    """parent clip id → audio path (text demo dùng id clip cha)."""
    result: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        parent = str(row.get("parent") or "")
        audio = str(row.get("audio_path") or "")
        if parent and audio:
            result[parent] = audio
    return result


def _generate(label: str, config_path: Path, checkpoint: Path, texts: list[dict],
              out: Path, device: str, alpha: float, force: bool) -> None:
    import yaml

    from vifasttts.infer import Synthesizer

    target = out / label
    target.mkdir(parents=True, exist_ok=True)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    engine = Synthesizer(config, str(checkpoint), device=device)
    for row in texts:
        rid = str(row["id"])
        path = target / f"{rid}.wav"
        if path.exists() and not force:
            print(f"[{label}] bỏ qua {rid} (đã có)")
            continue
        engine.synthesize(str(row["text"]), path, sharpen_alpha=alpha, gate_threshold=0.5)
        print(f"[{label}] {rid} → {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(_ROOT / "artifacts/listen_ngochuyen/ab_base_vs_small"))
    parser.add_argument("--key", default="", help="mặc định: <out>_key.json nằm ngoài thư mục web")
    parser.add_argument("--texts", default=str(TEXTS))
    parser.add_argument("--small-config", default=str(SMALL_CONFIG))
    parser.add_argument("--small-checkpoint", default=str(SMALL_CKPT))
    parser.add_argument("--base-config", default=str(BASE_CONFIG))
    parser.add_argument("--base-checkpoint", default=str(BASE_CKPT))
    parser.add_argument("--clips", type=int, default=24)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--sharpen-alpha", type=float, default=1.5)
    parser.add_argument("--no-real", action="store_true", help="bỏ audio thật, chỉ A/B")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    key_path = Path(args.key) if args.key else out.parent / f"{out.name}_key.json"
    staging = out.parent / f".{out.name}_src"
    rows = json.loads(Path(args.texts).read_text(encoding="utf-8"))[: args.clips]
    if not args.no_real:
        audio = _manifest_audio()
        rows = [row for row in rows if str(row.get("id")) in audio]
        if not rows:
            raise SystemExit("Không có câu demo nào có audio holdout")
        real = out / "real"
        real.mkdir(parents=True, exist_ok=True)
        for row in rows:
            rid = str(row["id"])
            dst = real / f"{rid}.wav"
            if not dst.exists() or args.force:
                shutil.copyfile(_ROOT / audio[rid], dst)
    else:
        shutil.rmtree(out / "real", ignore_errors=True)

    _generate("small", Path(args.small_config), Path(args.small_checkpoint), rows, staging,
              args.device, args.sharpen_alpha, args.force)
    _generate("base", Path(args.base_config), Path(args.base_checkpoint), rows, staging,
              args.device, args.sharpen_alpha, args.force)

    rng = random.Random(args.seed)
    key: list[dict[str, str]] = []
    for row in rows:
        rid = str(row["id"])
        if not (staging / "small" / f"{rid}.wav").exists() or not (staging / "base" / f"{rid}.wav").exists():
            continue
        if rng.random() < 0.5:
            a, b = "small", "base"
        else:
            a, b = "base", "small"
        key.append({"id": rid, "A": a, "B": b, "text": str(row["text"])})

    # Copy sang tên A/B trung tính: HTML không lộ model nào.
    for label in ("A", "B"):
        shutil.rmtree(out / label, ignore_errors=True)
        (out / label).mkdir(parents=True)
    for item in key:
        rid = item["id"]
        for label in ("A", "B"):
            shutil.copyfile(staging / item[label] / f"{rid}.wav", out / label / f"{rid}.wav")
    # Dọn nguồn và key cũ khỏi thư mục web.
    shutil.rmtree(staging, ignore_errors=True)
    for old in ("small", "base", "key.json"):
        path = out / old
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()
    key_path.write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    sections: list[str] = []
    for item in key:
        rid = html.escape(item["id"])
        real_row = "" if args.no_real else f'<div class="row"><span>Thật</span><audio controls preload="none" src="real/{rid}.wav"></audio></div>'
        sections.append(f"""
<section class="item" data-id="{rid}">
  <p class="text"><b>{rid}</b> — {html.escape(item['text'])}</p>
  {real_row}
  <div class="row"><span>A</span><audio controls preload="none" src="A/{rid}.wav"></audio></div>
  <div class="row"><span>B</span><audio controls preload="none" src="B/{rid}.wav"></audio></div>
  <div class="choices">
    <label><input type="radio" name="{rid}" value="A"> A tốt hơn</label>
    <label><input type="radio" name="{rid}" value="B"> B tốt hơn</label>
    <label><input type="radio" name="{rid}" value="hoa"> Hòa</label>
  </div>
</section>""")

    page = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>N0 — A/B blind: small vs base</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:900px;margin:24px auto;padding:0 14px;line-height:1.45}}
h1{{font-size:1.35rem}} .note{{color:#555;font-size:.92rem}}
.item{{border:1px solid #ddd;border-radius:12px;padding:12px 14px;margin:14px 0}}
.text{{margin:0 0 8px}} .row{{display:flex;gap:10px;align-items:center}} .row span{{width:44px;font-weight:600}}
audio{{width:100%;margin:5px 0}} .choices{{display:flex;gap:18px;flex-wrap:wrap;margin-top:6px}}
#bar{{position:sticky;bottom:0;background:#fff;padding:10px 0;border-top:1px solid #ddd;display:flex;gap:12px;align-items:center}}
button{{padding:8px 14px;border-radius:8px;border:1px solid #333;background:#111;color:#fff;font-weight:600}}
</style></head><body>
<h1>Nghe A/B blind — N0 small vs base</h1>
<p class="note">A/B đã xáo ngẫu nhiên. {'' if args.no_real else 'Nghe <b>Thật</b> để tham chiếu, rồi '}chọn bản A/B nghe tự nhiên, rõ và ít rè hơn. Kết quả chỉ tải CSV ở máy bạn.</p>
{''.join(sections)}
<div id="bar"><span id="p">0/{len(key)}</span><button onclick="downloadCsv()">Tải CSV kết quả</button></div>
<script>
const ids = {json.dumps([item['id'] for item in key])};
function valueOf(id) {{ const e = document.querySelector(`input[name="${{id}}"]:checked`); return e ? e.value : ''; }}
function update() {{ document.getElementById('p').textContent = ids.filter(i => valueOf(i)).length + '/' + ids.length; }}
document.querySelectorAll('input[type=radio]').forEach(e => e.addEventListener('change', update));
function downloadCsv() {{
  let lines = ['item_id,choice'];
  for (const id of ids) lines.push(id + ',' + valueOf(id));
  const blob = new Blob([lines.join('\\n') + '\\n'], {{type: 'text/csv;charset=utf-8'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'n0_ab_small_vs_base.csv';
  a.click();
}}
update();
</script></body></html>"""
    (out / "index.html").write_text(page, encoding="utf-8")
    print(json.dumps({"page": str(out / "index.html"), "key": str(key_path), "n": len(key)}))


if __name__ == "__main__":
    main()
