"""tools/sync_space_static.py — đồng bộ landing/demo sang HF Space tĩnh.

VPS phục vụ `static/index.html` + `static/demo.html`; Space tĩnh chỉ có file.
Hai bên dùng cùng HTML (đường dẫn `brand/...` tương đối, API tự chọn host),
nên bản Space phải là **bản sao byte-for-byte** để tránh lệch tính năng.

  .venv/bin/python tools/sync_space_static.py          # chép
  .venv/bin/python tools/sync_space_static.py --check  # chỉ kiểm tra (CI)
"""

from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "deploy" / "vifasttts_demo" / "static"
DEST = ROOT / "huggingface" / "space-static"
PAGES = ("index.html", "demo.html")
ASSET_DIRS = ("brand",)
ASSET_REF = re.compile(r'(?:src|href)="(brand/[^"#?]+)"')


def _dirs_differ(left: Path, right: Path) -> list[str]:
    """Danh sách file nguồn thiếu/lệch ở đích (rỗng nếu khớp).

    Chỉ so file có trong nguồn; file thừa ở đích không bị xoá tự động.
    """
    names: set[str] = set()
    if left.exists():
        names.update(str(path.relative_to(left)) for path in left.rglob("*") if path.is_file())
    stale: list[str] = []
    for name in sorted(names):
        left_file, right_file = left / name, right / name
        if not right_file.is_file() or not filecmp.cmp(left_file, right_file, shallow=False):
            stale.append(name)
    return stale


def _validate_assets() -> list[str]:
    """Bắt link brand gãy trước khi deploy."""
    missing: list[str] = []
    for page in PAGES:
        path = SOURCE / page
        if not path.is_file():
            missing.append(f"thiếu {path.relative_to(ROOT)}")
            continue
        for reference in ASSET_REF.findall(path.read_text(encoding="utf-8")):
            if not (SOURCE / reference).is_file():
                missing.append(f"{page} → {reference}")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="chỉ kiểm tra, không ghi file")
    args = parser.parse_args()

    missing = _validate_assets()
    if missing:
        print("Link brand gãy:\n  " + "\n  ".join(missing), file=sys.stderr)
        return 2

    stale_pages = [name for name in PAGES
                   if not (DEST / name).is_file()
                   or not filecmp.cmp(SOURCE / name, DEST / name, shallow=False)]
    stale_assets = {name: _dirs_differ(SOURCE / name, DEST / name) for name in ASSET_DIRS}
    stale_assets = {name: files for name, files in stale_assets.items() if files}

    if args.check:
        if stale_pages or stale_assets:
            if stale_pages:
                print("Trang lệch: " + ", ".join(stale_pages))
            for name, files in stale_assets.items():
                print(f"{name}/ lệch: " + ", ".join(files))
            print("Chạy lại không có --check để đồng bộ.")
            return 1
        print("Space static đã khớp.")
        return 0

    for page in stale_pages:
        DEST.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / page, DEST / page)
        print(f"Đã chép {page}")
    for name, files in stale_assets.items():
        target = DEST / name
        target.mkdir(parents=True, exist_ok=True)
        for relative in files:
            source_file = SOURCE / name / relative
            if source_file.is_file():
                (target / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, target / relative)
        print(f"Đã chép {name}/ ({len(files)} file)")
    if not stale_pages and not stale_assets:
        print("Space static đã khớp.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
