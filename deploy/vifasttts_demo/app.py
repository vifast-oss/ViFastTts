"""Demo web ONNX cho N0 — research/non-commercial.

Chạy trong Docker; không cần torch. Mặc định model tự nghỉ, alpha 1.5, Vocos pretrained.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import html
import io
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
import wave
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from vifasttts.frontend.chunking import (
    chunk_text,
    pause_seconds,
    split_clauses,
    steady_pause_seconds,
)
from vifasttts.frontend.normalizer import NormalizerOptions, normalize_text
from vifasttts.runtime.onnx_engine import OnnxAcousticModel, OnnxVocoder
from vifasttts.runtime.postprocess import postprocess, sharpen_mel_numpy

ROOT = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("MODEL_DIR", ROOT / "models"))
ACOUSTIC = MODEL_DIR / "acoustic.onnx"
VOCODER = MODEL_DIR / "vocoder.onnx"
def _env_int(name: str, default: int, low: int, high: int) -> int:
    """Đọc số nguyên từ env, kẹp trong [low, high] để tránh cấu hình phá service."""
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(low, min(high, value))


#: Giới hạn request công khai; có thể tăng bằng env (UI đọc /api/config).
MAX_CHARS = _env_int("MAX_CHARS", 3000, 100, 10000)
#: Mỗi đoạn đưa vào model vẫn ngắn (tránh vượt MAX_POSITIONS / RAM); dài hơn sẽ chia.
SYNTH_CHUNK_CHARS = _env_int("SYNTH_CHUNK_CHARS", 300, 100, MAX_CHARS)
RATE_LIMIT = 6
RATE_WINDOW = 60.0
ALPHA = float(os.environ.get("VIFASTT_SHARPEN_ALPHA", "1.5"))
OVERRIDES_PATH = Path(os.environ.get("OVERRIDES_PATH", ROOT / "configs" / "overrides_tech_vi.json"))
MAX_OVERRIDES = 50
MAX_FEEDBACK_CHARS = 1000
MAX_CONTACT_CHARS = 120
FEEDBACK_CATEGORIES = {
    "gop_y": "Góp ý chung",
    "cai_tien": "Đề xuất cải tiến",
    "bao_loi": "Báo lỗi",
}
FEEDBACK_STATUS = {"new": "Chờ xem", "read": "Đã đọc", "resolved": "Đã xử lý"}
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.environ.get("STATS_DB", DATA_DIR / "stats.sqlite3"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
VN_TZ = timezone(timedelta(hours=7))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("vifasttts-demo")

app = FastAPI(title="ViFastTts research demo", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://huggingface.co"],
    allow_origin_regex=r"https://.*\.hf\.space",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Processing-Seconds", "X-Audio-Seconds", "X-RTF", "X-Characters"],
)
_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)
_STATS_LOCK = threading.Lock()
_SALT: str | None = None


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(DB_PATH), timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def _init_stats() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _STATS_LOCK:
        connection = _connect()
        try:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS visitors (
                    visitor TEXT PRIMARY KEY,
                    first_seen REAL NOT NULL,
                    last_seen REAL NOT NULL,
                    page_views INTEGER NOT NULL DEFAULT 0,
                    tts_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    visitor TEXT NOT NULL,
                    chars INTEGER NOT NULL,
                    audio_seconds REAL NOT NULL,
                    elapsed REAL NOT NULL,
                    fixed_pauses INTEGER NOT NULL,
                    speed REAL NOT NULL,
                    source TEXT NOT NULL DEFAULT 'api'
                );
                CREATE INDEX IF NOT EXISTS usage_ts ON usage(ts);
                CREATE TABLE IF NOT EXISTS suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    source TEXT NOT NULL DEFAULT 'web',
                    visitor TEXT NOT NULL,
                    created REAL NOT NULL,
                    updated REAL NOT NULL,
                    UNIQUE(key, value)
                );
                CREATE INDEX IF NOT EXISTS suggestions_status ON suggestions(status);
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL DEFAULT 'gop_y',
                    message TEXT NOT NULL,
                    contact TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'new',
                    source TEXT NOT NULL DEFAULT 'web',
                    visitor TEXT NOT NULL,
                    created REAL NOT NULL,
                    updated REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS feedback_status ON feedback(status);
                CREATE INDEX IF NOT EXISTS feedback_category ON feedback(category);
            """)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(usage)")}
            if "source" not in columns:
                connection.execute("ALTER TABLE usage ADD COLUMN source TEXT NOT NULL DEFAULT 'api'")
            connection.commit()
        finally:
            connection.close()


def _get_salt() -> str:
    global _SALT
    if _SALT:
        return _SALT
    configured = os.environ.get("STATS_SALT", "").strip()
    if configured:
        _SALT = configured
        return _SALT
    with _STATS_LOCK:
        connection = _connect()
        try:
            row = connection.execute("SELECT value FROM meta WHERE key='salt'").fetchone()
            if row:
                _SALT = str(row["value"])
            else:
                _SALT = secrets.token_hex(16)
                connection.execute("INSERT INTO meta(key, value) VALUES('salt', ?)", (_SALT,))
                connection.commit()
        finally:
            connection.close()
    return _SALT


def _load_builtin_overrides() -> dict[str, str]:
    try:
        payload = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(key).strip().lower(): str(value).strip()
            for key, value in payload.items() if str(key).strip() and str(value).strip()}


BUILTIN_OVERRIDES = _load_builtin_overrides()

#: Ví dụ các quy tắc STEM nội bộ (không nằm trong 200 overrides tinh gọn). Đọc thực tế
#: được sinh lại bằng normalizer để UI không hiển thị sai.
STEM_GROUPS = (
    ("Hoá học", ("H2O", "CO2", "H2SO4")),
    ("Toán", ("1/2",)),
    ("Vật lý", ("m/s", "km/h")),
    ("LaTeX", (r"\frac{a}{b}",)),
)


def _stem_examples() -> dict:
    groups = []
    for label, samples in STEM_GROUPS:
        items = []
        for text in samples:
            try:
                reading = normalize_text(text)
            except (ValueError, TypeError):
                reading = ""
            if reading and reading != text:
                items.append({"input": text, "reading": reading})
        if items:
            groups.append({"label": label, "items": items})
    return {
        "note": "Quy tắc STEM nội bộ, áp dụng trước từ điển. Quy tắc của bạn được ưu tiên; "
                "NaCl dạng trần, x^2, \\alpha... chưa có quy tắc riêng — thêm vào ô cách đọc.",
        "groups": groups,
    }


def _clean_overrides(raw: dict[str, str] | None, limit: int = MAX_OVERRIDES) -> dict[str, str]:
    if not raw:
        return {}
    if len(raw) > limit:
        raise HTTPException(status_code=422, detail=f"Tối đa {limit} quy tắc đọc")
    clean: dict[str, str] = {}
    for key, value in raw.items():
        key, value = str(key).strip(), str(value).strip()
        if not key or not value or len(key) > 80 or len(value) > 120:
            raise HTTPException(status_code=422, detail="Quy tắc đọc sai độ dài")
        if any(ord(char) < 32 for char in key + value):
            raise HTTPException(status_code=422, detail="Quy tắc đọc chứa ký tự điều khiển")
        clean[key] = value
    return clean


def _visitor_hash(request: Request, visitor_id: str | None = None) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    client = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    if visitor_id and re.fullmatch(r"[A-Za-z0-9_-]{8,80}", visitor_id):
        material = f"id:{visitor_id}"
    else:
        material = f"ip:{client}"
    return hashlib.sha256(f"{_get_salt()}:{material}".encode()).hexdigest()[:24]


def _record_page(visitor: str) -> None:
    now = time.time()
    with _STATS_LOCK:
        connection = _connect()
        try:
            connection.execute(
                "INSERT INTO visitors(visitor, first_seen, last_seen, page_views) VALUES(?,?,?,1) "
                "ON CONFLICT(visitor) DO UPDATE SET last_seen=excluded.last_seen, "
                "page_views=visitors.page_views+1",
                (visitor, now, now),
            )
            connection.commit()
        finally:
            connection.close()


def _record_tts(visitor: str, chars: int, audio_seconds: float, elapsed: float,
                fixed_pauses: bool, speed: float, source: str) -> None:
    now = time.time()
    with _STATS_LOCK:
        connection = _connect()
        try:
            connection.execute(
                "INSERT INTO usage(ts, visitor, chars, audio_seconds, elapsed, fixed_pauses, speed, source) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (now, visitor, chars, audio_seconds, elapsed, int(fixed_pauses), speed, source),
            )
            connection.execute(
                "INSERT INTO visitors(visitor, first_seen, last_seen, tts_count) VALUES(?,?,?,1) "
                "ON CONFLICT(visitor) DO UPDATE SET last_seen=excluded.last_seen, "
                "tts_count=visitors.tts_count+1",
                (visitor, now, now),
            )
            connection.commit()
        finally:
            connection.close()


def _approved_overrides() -> dict[str, str]:
    with _STATS_LOCK:
        connection = _connect()
        try:
            rows = connection.execute(
                "SELECT key, value FROM suggestions WHERE status='approved' ORDER BY id"
            ).fetchall()
        finally:
            connection.close()
    return {str(row["key"]): str(row["value"]) for row in rows}


def _record_suggestions(rules: dict[str, str], visitor: str, source: str) -> int:
    now = time.time()
    with _STATS_LOCK:
        connection = _connect()
        try:
            for key, value in rules.items():
                connection.execute(
                    "INSERT INTO suggestions(key, value, status, source, visitor, created, updated) "
                    "VALUES(?,?, 'pending', ?, ?, ?, ?) "
                    "ON CONFLICT(key, value) DO UPDATE SET updated=excluded.updated, "
                    "source=excluded.source, visitor=excluded.visitor",
                    (key, value, source, visitor, now, now),
                )
            connection.commit()
        finally:
            connection.close()
    return len(rules)


def _pending_suggestions(limit: int = 100) -> list[dict]:
    with _STATS_LOCK:
        connection = _connect()
        try:
            rows = connection.execute(
                "SELECT id, key, value, source, created FROM suggestions "
                "WHERE status='pending' ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            connection.close()
    return [{**dict(row), "time": datetime.fromtimestamp(float(row["created"]), VN_TZ).strftime("%m-%d %H:%M")}
            for row in rows]


def _clean_feedback_text(value: str | None, limit: int, label: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value or "")).strip()
    if len(text) > limit:
        raise HTTPException(status_code=422, detail=f"{label} tối đa {limit} ký tự")
    return text


def _record_feedback(category: str, message: str, contact: str, visitor: str, source: str) -> int:
    now = time.time()
    with _STATS_LOCK:
        connection = _connect()
        try:
            cursor = connection.execute(
                "INSERT INTO feedback(category, message, contact, status, source, visitor, created, updated) "
                "VALUES(?,?,?, 'new', ?, ?, ?, ?)",
                (category, message, contact, source, visitor, now, now),
            )
            connection.commit()
            return int(cursor.lastrowid)
        finally:
            connection.close()


def _feedback_counts() -> dict:
    with _STATS_LOCK:
        connection = _connect()
        try:
            rows = connection.execute(
                "SELECT category, status, COUNT(*) AS n FROM feedback GROUP BY category, status"
            ).fetchall()
        finally:
            connection.close()
    by_category = {key: 0 for key in FEEDBACK_CATEGORIES}
    by_status = {key: 0 for key in FEEDBACK_STATUS}
    for row in rows:
        by_category[str(row["category"])] = by_category.get(str(row["category"]), 0) + int(row["n"])
        by_status[str(row["status"])] = by_status.get(str(row["status"]), 0) + int(row["n"])
    return {
        "total": sum(by_category.values()),
        "new": by_status.get("new", 0),
        "read": by_status.get("read", 0),
        "resolved": by_status.get("resolved", 0),
        "by_category": by_category,
    }


def _feedback_rows(limit: int = 200) -> list[dict]:
    with _STATS_LOCK:
        connection = _connect()
        try:
            rows = connection.execute(
                "SELECT id, category, message, contact, status, source, created "
                "FROM feedback ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            connection.close()
    return [{**dict(row),
             "time": datetime.fromtimestamp(float(row["created"]), VN_TZ).strftime("%m-%d %H:%M")}
            for row in rows]


def _stats_payload() -> dict:
    now = time.time()
    local_now = datetime.fromtimestamp(now, VN_TZ)
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    week_start = (local_now - timedelta(days=7)).timestamp()
    with _STATS_LOCK:
        connection = _connect()
        try:
            users = connection.execute("SELECT COUNT(*) AS n FROM visitors").fetchone()["n"]
            pages = connection.execute("SELECT COALESCE(SUM(page_views),0) AS n FROM visitors").fetchone()["n"]
            tts = connection.execute("SELECT COUNT(*) AS n FROM usage").fetchone()["n"]
            users_today = connection.execute(
                "SELECT COUNT(*) AS n FROM visitors WHERE last_seen >= ?", (day_start,)
            ).fetchone()["n"]
            users_week = connection.execute(
                "SELECT COUNT(*) AS n FROM visitors WHERE last_seen >= ?", (week_start,)
            ).fetchone()["n"]
            tts_today = connection.execute(
                "SELECT COUNT(*) AS n FROM usage WHERE ts >= ?", (day_start,)
            ).fetchone()["n"]
            by_source = {row["source"]: row["n"] for row in connection.execute(
                "SELECT source, COUNT(*) AS n FROM usage GROUP BY source"
            ).fetchall()}
            suggestions_pending = connection.execute(
                "SELECT COUNT(*) AS n FROM suggestions WHERE status='pending'"
            ).fetchone()["n"]
            suggestions_approved = connection.execute(
                "SELECT COUNT(*) AS n FROM suggestions WHERE status='approved'"
            ).fetchone()["n"]
            feedback_total = connection.execute(
                "SELECT COUNT(*) AS n FROM feedback"
            ).fetchone()["n"]
            feedback_new = connection.execute(
                "SELECT COUNT(*) AS n FROM feedback WHERE status='new'"
            ).fetchone()["n"]
            totals = connection.execute(
                "SELECT COALESCE(SUM(audio_seconds),0) AS audio, "
                "COALESCE(SUM(chars),0) AS chars, "
                "COALESCE(AVG(elapsed),0) AS elapsed FROM usage"
            ).fetchone()
            recent = [dict(row) for row in connection.execute(
                "SELECT ts, visitor, chars, audio_seconds, elapsed, fixed_pauses, speed, source "
                "FROM usage ORDER BY id DESC LIMIT 20"
            ).fetchall()]
        finally:
            connection.close()
    return {
        "generated_at": datetime.fromtimestamp(now, VN_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "UTC+07:00",
        "users_total": int(users),
        "users_today": int(users_today),
        "users_7d": int(users_week),
        "page_views": int(pages),
        "tts_total": int(tts),
        "tts_today": int(tts_today),
        "tts_web": int(by_source.get("web", 0)),
        "tts_space": int(by_source.get("space", 0)),
        "tts_api": int(by_source.get("api", 0)),
        "suggestions_pending": int(suggestions_pending),
        "suggestions_approved": int(suggestions_approved),
        "feedback_total": int(feedback_total),
        "feedback_new": int(feedback_new),
        "audio_seconds": round(float(totals["audio"]), 2),
        "chars_total": int(totals["chars"]),
        "avg_chars": round(float(totals["chars"]) / tts, 1) if tts else 0.0,
        "avg_elapsed": round(float(totals["elapsed"]), 3) if tts else 0.0,
        "recent": [
            {**row, "time": datetime.fromtimestamp(float(row["ts"]), VN_TZ).strftime("%m-%d %H:%M:%S"),
             "visitor": str(row["visitor"])[:10], "audio_seconds": round(float(row["audio_seconds"]), 2),
             "elapsed": round(float(row["elapsed"]), 3)}
            for row in recent
        ],
    }


def _admin_authorized(request: Request) -> bool:
    if not ADMIN_PASSWORD:
        return True
    header = request.headers.get("authorization", "")
    expected = "Basic " + base64.b64encode(f"admin:{ADMIN_PASSWORD}".encode()).decode("ascii")
    return hmac.compare_digest(header, expected)


def _feedback_admin_rows(items: list[dict]) -> str:
    rows = []
    for item in items:
        message = html.escape(str(item["message"])).replace("\n", "<br>")
        contact = html.escape(str(item["contact"])) or "—"
        category = html.escape(FEEDBACK_CATEGORIES.get(str(item["category"]), str(item["category"])))
        status = FEEDBACK_STATUS.get(str(item["status"]), str(item["status"]))
        status_key = str(item["status"])
        actions = []
        if status_key != "read":
            actions.append(
                f"<form method='post' action='/admin/feedback/{item['id']}/read' style='display:inline'>"
                f"<button class='tiny'>Đã đọc</button></form>"
            )
        if status_key != "resolved":
            actions.append(
                f"<form method='post' action='/admin/feedback/{item['id']}/resolved' style='display:inline'>"
                f"<button class='tiny ok'>Đã xử lý</button></form>"
            )
        if not actions:
            actions.append("<span class='done'>Đã xử lý</span>")
        rows.append(
            f"<tr><td>{item['time']}</td><td><span class='cat'>{category}</span></td>"
            f"<td class='msg'>{message}</td><td>{contact}</td><td>{html.escape(str(item['source']))}</td>"
            f"<td><span class='st st-{status_key}'>{status}</span></td>"
            f"<td class='actions'>{' '.join(actions)}</td></tr>"
        )
    return "".join(rows) or "<tr><td colspan='7'>Chưa có góp ý nào.</td></tr>"


def _admin_html(stats: dict) -> str:
    rows = "".join(
        f"<tr><td>{item['time']}</td><td>{item['visitor']}</td><td>{item['chars']}</td>"
        f"<td>{item['audio_seconds']:.2f}s</td><td>{item['elapsed']:.2f}s</td>"
        f"<td>{item.get('source', 'api')}</td><td>{'có' if item['fixed_pauses'] else 'không'}</td></tr>"
        for item in stats["recent"]
    ) or "<tr><td colspan='7'>Chưa có lượt tạo nào.</td></tr>"
    auth_note = "Đang mở công khai, chưa đặt ADMIN_PASSWORD." if not ADMIN_PASSWORD else "Đã bật Basic Auth."
    pending = _pending_suggestions()
    if ADMIN_PASSWORD:
        suggestion_rows = "".join(
            f"<tr><td>{item['time']}</td><td>{html.escape(item['key'])}</td>"
            f"<td>{html.escape(item['value'])}</td><td>{html.escape(item['source'])}</td>"
            f"<td><form method='post' action='/admin/suggestions/{item['id']}/approve' style='display:inline'>"
            f"<button class='tiny ok'>Duyệt</button></form> "
            f"<form method='post' action='/admin/suggestions/{item['id']}/reject' style='display:inline'>"
            f"<button class='tiny no'>Từ chối</button></form></td></tr>"
            for item in pending
        ) or "<tr><td colspan='5'>Không có đề xuất chờ duyệt.</td></tr>"
    else:
        suggestion_rows = "".join(
            f"<tr><td>{item['time']}</td><td>{html.escape(item['key'])}</td>"
            f"<td>{html.escape(item['value'])}</td><td>{html.escape(item['source'])}</td>"
            f"<td><button class='tiny' disabled title='Đặt ADMIN_PASSWORD để duyệt'>Duyệt</button></td></tr>"
            for item in pending
        ) or "<tr><td colspan='5'>Không có đề xuất chờ duyệt.</td></tr>"
    review_note = ("Đã bật duyệt vì có ADMIN_PASSWORD." if ADMIN_PASSWORD
                   else "Đang tạm khoá duyệt: chưa đặt ADMIN_PASSWORD. Đề xuất vẫn được xếp hàng.")
    feedback_counts = _feedback_counts()
    if ADMIN_PASSWORD:
        feedback_rows = _feedback_admin_rows(_feedback_rows(limit=100))
        feedback_note = ("Đã bật xem nội dung và cập nhật trạng thái · "
                         "<a href='/admin/feedback.csv'>Tải CSV</a>")
    else:
        feedback_rows = ("<tr><td colspan='7'>Nội dung góp ý đang khoá: đặt "
                         "<code>ADMIN_PASSWORD</code> để xem.</td></tr>")
        feedback_note = "Đang khoá nội dung: đặt ADMIN_PASSWORD để xem và cập nhật góp ý."
    feedback_summary = (f"{feedback_counts['total']} góp ý · "
                        f"{feedback_counts['new']} mới · "
                        f"Góp ý {feedback_counts['by_category'].get('gop_y', 0)} · "
                        f"Cải tiến {feedback_counts['by_category'].get('cai_tien', 0)} · "
                        f"Báo lỗi {feedback_counts['by_category'].get('bao_loi', 0)} · "
                        f"Đã đọc {feedback_counts['read']} · Đã xử lý {feedback_counts['resolved']}")
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>ViFastTts · Thống kê</title>
<link rel="icon" href="/static/brand/favicon.ico" sizes="any">
<style>
body{{font-family:Arial,"Helvetica Neue",Helvetica,sans-serif;background:#FBF6EE;color:#1F2430;margin:0;padding:28px}}
main{{max-width:980px;margin:0 auto}} h1{{letter-spacing:-.03em;margin:0 0 4px;display:flex;align-items:center;gap:9px}}
.mark{{width:38px;height:38px;border-radius:9px;flex:0 0 auto}}
.sub{{color:#637083;margin:0 0 20px}} .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.card{{background:#fff;border:1px solid #dbe3ea;border-radius:12px;padding:14px}}
.card b{{display:block;font-size:1.6rem;color:#C6281E}} .card span{{color:#637083;font-size:.84rem}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #dbe3ea;border-radius:12px;overflow:hidden;margin-top:18px}}
th,td{{text-align:left;padding:9px 12px;border-bottom:1px solid #edf1f3;font-size:.86rem}}
th{{background:#FDF0EB;color:#9B2C20}} a{{color:#C6281E}}
.note{{background:#fff8e8;border:1px solid #f0d49a;padding:10px 12px;border-radius:10px;color:#7a4b00;font-size:.86rem;margin-top:16px}}
.tiny{{padding:4px 8px;font-size:.78rem;border-radius:7px;border:1px solid #cbd6df;background:#f4f7f8;cursor:pointer}}
.tiny.ok{{background:#e5f5ec;border-color:#b8e2c8;color:#166534}} .tiny.no{{background:#fff0f0;border-color:#f0c4c4;color:#9b1c1c}}
.tiny:disabled{{opacity:.45;cursor:not-allowed}}
.msg{{max-width:390px;white-space:normal;line-height:1.45;overflow-wrap:anywhere}}
.cat,.st{{display:inline-block;padding:2px 7px;border-radius:999px;font-size:.76rem;white-space:nowrap}}
.cat{{background:#FDF0EB;color:#9B2C20}} .st-new{{background:#FFF4D6;color:#7A4B00}}
.st-read{{background:#EAF2FF;color:#1D4ED8}} .st-resolved{{background:#E5F5EC;color:#166534}}
.actions{{white-space:nowrap}} .actions form{{margin:0 2px 0 0}} .done{{color:#166534;font-size:.8rem;font-weight:700}}
@media(max-width:700px){{.grid{{grid-template-columns:repeat(2,1fr)}} table{{display:block;overflow-x:auto}}}}
</style></head><body><main>
<h1><img class="mark" src="/static/brand/vifasttts-icon.svg" alt=""> ViFastTts · Thống kê</h1>
<p class="sub">Cập nhật {stats['generated_at']} ({stats['timezone']}) · tự làm mới 30 giây · <a href="/">về trang chủ</a></p>
<div class="grid">
  <div class="card"><b>{stats['users_total']}</b><span>người dùng (hash IP)</span></div>
  <div class="card"><b>{stats['tts_total']}</b><span>lượt tạo audio</span></div>
  <div class="card"><b>{stats['page_views']}</b><span>lượt xem trang</span></div>
  <div class="card"><b>{stats['tts_today']}</b><span>lượt tạo hôm nay</span></div>
  <div class="card"><b>{stats['tts_web']}</b><span>tạo trên web</span></div>
  <div class="card"><b>{stats['tts_space']}</b><span>tạo qua Space</span></div>
  <div class="card"><b>{stats['tts_api']}</b><span>tạo qua API</span></div>
  <div class="card"><b>{stats['audio_seconds'] / 60:.1f} phút</b><span>audio đã tạo</span></div>
  <div class="card"><b>{stats['avg_chars']}</b><span>ký tự / lượt</span></div>
  <div class="card"><b>{stats['suggestions_pending']}</b><span>đề xuất chờ duyệt</span></div>
  <div class="card"><b>{stats['suggestions_approved']}</b><span>quy tắc đã duyệt</span></div>
  <div class="card"><b>{stats['feedback_total']}</b><span>góp ý / báo lỗi</span></div>
  <div class="card"><b>{stats['feedback_new']}</b><span>góp ý mới</span></div>
</div>
<h2 style="margin:24px 0 4px">Đề xuất cách đọc</h2>
<p class="sub">{review_note}</p>
<table><thead><tr><th>Thời điểm</th><th>Từ</th><th>Cách đọc</th><th>Nguồn</th><th>Duyệt</th></tr></thead>
<tbody>{suggestion_rows}</tbody></table>
<h2 style="margin:24px 0 4px">Góp ý & báo lỗi</h2>
<p class="sub">{feedback_note}</p>
<p class="sub">{feedback_summary}</p>
<table><thead><tr><th>Thời điểm</th><th>Loại</th><th>Nội dung</th><th>Liên hệ</th><th>Nguồn</th><th>Trạng thái</th><th>Cập nhật</th></tr></thead>
<tbody>{feedback_rows}</tbody></table>
<h2 style="margin:24px 0 4px">Lượt tạo gần đây</h2>
<table><thead><tr><th>Thời điểm</th><th>Ẩn danh</th><th>Ký tự</th><th>Audio</th><th>Xử lý</th><th>Nguồn</th><th>Nghỉ cố định</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="note">Số “người dùng” là ước lượng theo hash visitor/IP, không lưu IP/text TTS.
Góp ý chỉ lưu nội dung bạn gửi và liên hệ (nếu có), chỉ admin đã đặt mật khẩu mới xem được. {auth_note}</div>
</main></body></html>"""


_init_stats()

if not ACOUSTIC.exists() or not VOCODER.exists():
    raise RuntimeError(f"Thiếu ONNX: {ACOUSTIC} / {VOCODER}")

acoustic = OnnxAcousticModel(ACOUSTIC, provider="cpu")
vocoder = OnnxVocoder(VOCODER, provider="cpu")
SAMPLE_RATE = vocoder.sample_rate or int(acoustic.metadata.get("sample_rate", 24000))


class TtsRequest(BaseModel):
    text: str
    speed: float = 1.0
    fixed_pauses: bool = False
    visitor_id: str | None = None
    source: str = "api"
    overrides: dict[str, str] | None = None


class VisitRequest(BaseModel):
    visitor_id: str | None = None


class SuggestRequest(BaseModel):
    rules: dict[str, str]
    visitor_id: str | None = None
    source: str = "web"


class FeedbackRequest(BaseModel):
    category: str = "gop_y"
    message: str
    contact: str | None = None
    visitor_id: str | None = None
    source: str = "web"
    website: str | None = None


def _wav_bytes(waveform: np.ndarray, sample_rate: int) -> bytes:
    pcm = (np.clip(np.asarray(waveform, dtype=np.float32), -1.0, 1.0) * 32767.0).round().astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


def _rate_ok(client: str) -> bool:
    now = time.monotonic()
    bucket = _hits[client]
    while bucket and now - bucket[0] > RATE_WINDOW:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT:
        return False
    bucket.append(now)
    return True


def _synthesize(text: str, speed: float, fixed_pauses: bool,
                overrides: dict[str, str]) -> tuple[bytes, float, float]:
    started = time.perf_counter()
    user_lower = {key.lower(): value for key, value in overrides.items() if key.isascii()}
    approved = _approved_overrides()
    approved_lower = {key.lower(): value for key, value in approved.items() if key.isascii()}
    # Key có dấu chấm/khoảng trắng (TP.HCM, v.v., hugging face) phải vào
    # exact_overrides để _apply_phrase_overrides chạy trước tokenizer. Nếu chỉ
    # đặt trong english_overrides, các key nhiều token sẽ không bao giờ khớp.
    builtin_phrases = {
        key: value for key, value in BUILTIN_OVERRIDES.items()
        if not re.fullmatch(r"[A-Za-zÀ-ỹĐđ]+", key)
    }
    options = NormalizerOptions(
        dialect="north",
        exact_overrides={**builtin_phrases, **overrides},
        english_overrides={**BUILTIN_OVERRIDES, **approved_lower, **user_lower},
    )
    chunks = (split_clauses(text, max_chars=SYNTH_CHUNK_CHARS) if fixed_pauses
              else chunk_text(text, max_chars=SYNTH_CHUNK_CHARS))
    if not chunks:
        raise HTTPException(status_code=422, detail="Không có nội dung để đọc")
    pieces: list[np.ndarray] = []
    for index, chunk in enumerate(chunks):
        features = acoustic.features_from_text(chunk, options=options)
        outputs = acoustic.run(features, speed=speed, gate_threshold=1.01 if fixed_pauses else 0.5)
        mel = np.asarray(outputs["mel"], dtype=np.float32)
        mel = sharpen_mel_numpy(mel, ALPHA)
        pieces.append(np.asarray(vocoder.waveform(mel), dtype=np.float32))
        if index < len(chunks) - 1:
            seconds = (steady_pause_seconds(chunk) if fixed_pauses else pause_seconds(chunk))
            pause = int(SAMPLE_RATE * seconds)
            if pause:
                pieces.append(np.zeros(pause, dtype=np.float32))
    waveform = postprocess(np.concatenate(pieces), SAMPLE_RATE)
    return _wav_bytes(waveform, SAMPLE_RATE), time.perf_counter() - started, waveform.size / SAMPLE_RATE


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((ROOT / "static" / "index.html").read_text(encoding="utf-8"),
                        headers={"Cache-Control": "no-store"})


@app.get("/api/config")
def public_config() -> dict:
    """Cấu hình công khai để UI hiển thị đúng giới hạn (không lộ secret)."""
    return {"max_chars": MAX_CHARS, "rate_limit": RATE_LIMIT, "rate_window": RATE_WINDOW}


@app.post("/api/visit")
def visit(payload: VisitRequest, request: Request) -> dict:
    _record_page(_visitor_hash(request, payload.visitor_id))
    return {"ok": True}


@app.get("/api/overrides")
def overrides() -> dict:
    return {
        "builtin": BUILTIN_OVERRIDES,
        "approved": _approved_overrides(),
        "stem": _stem_examples(),
        "max_rules": MAX_OVERRIDES,
        "note": "Bảng đọc có sẵn + quy tắc đã duyệt + ví dụ STEM nội bộ. Quy tắc người dùng "
                "lưu localStorage hoặc gửi theo request; server chỉ lưu bản đề xuất khi gửi.",
    }


@app.post("/api/overrides/suggest")
def suggest_overrides(payload: SuggestRequest, request: Request) -> dict:
    rules = _clean_overrides(payload.rules, limit=10)
    if not rules:
        raise HTTPException(status_code=422, detail="Không có quy tắc để gửi")
    try:
        visitor = _visitor_hash(request, payload.visitor_id)
    except Exception:
        logger.exception("visitor stats failed")
        visitor = "unknown"
    if not _rate_ok(f"suggest:{visitor}"):
        raise HTTPException(status_code=429, detail="Gửi quá nhiều; thử lại sau 1 phút")
    source = payload.source if payload.source in ("web", "space", "api") else "api"
    count = _record_suggestions(rules, visitor, source)
    logger.info("suggestion queued count=%d source=%s", count, source)
    return {"ok": True, "queued": count, "status": "pending"}


@app.post("/api/feedback")
def feedback(payload: FeedbackRequest, request: Request) -> dict:
    if (payload.website or "").strip():
        return {"ok": True, "queued": 0}
    category = payload.category if payload.category in FEEDBACK_CATEGORIES else "gop_y"
    message = _clean_feedback_text(payload.message, MAX_FEEDBACK_CHARS, "Nội dung")
    if len(message) < 5:
        raise HTTPException(status_code=422, detail="Nội dung cần ít nhất 5 ký tự")
    contact = _clean_feedback_text(payload.contact, MAX_CONTACT_CHARS, "Liên hệ")
    try:
        visitor = _visitor_hash(request, payload.visitor_id)
    except Exception:
        logger.exception("feedback visitor failed")
        visitor = "unknown"
    if not _rate_ok(f"feedback:{visitor}"):
        raise HTTPException(status_code=429, detail="Gửi quá nhiều; thử lại sau 1 phút")
    source = payload.source if payload.source in ("web", "space", "api") else "api"
    feedback_id = _record_feedback(category, message, contact, visitor, source)
    logger.info("feedback stored id=%d category=%s source=%s", feedback_id, category, source)
    return {"ok": True, "queued": 1}


def _admin_denied() -> Response:
    return Response(status_code=401, content="Cần đăng nhập admin.",
                    headers={"WWW-Authenticate": 'Basic realm="vifasttts-admin"'})


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request) -> Response:
    if not _admin_authorized(request):
        return _admin_denied()
    return HTMLResponse(_admin_html(_stats_payload()), headers={"Cache-Control": "no-store"})


@app.get("/admin.json")
def admin_json(request: Request) -> Response:
    if not _admin_authorized(request):
        return _admin_denied()
    return Response(content=json.dumps(_stats_payload(), ensure_ascii=False),
                    media_type="application/json", headers={"Cache-Control": "no-store"})


def _csv_cell(value: object) -> str:
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@app.get("/admin/feedback.csv")
def feedback_csv(request: Request) -> Response:
    if not _admin_authorized(request):
        return _admin_denied()
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Chưa đặt ADMIN_PASSWORD; nội dung góp ý đang khoá")
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow(["id", "thoi_gian", "loai", "noi_dung", "lien_he", "nguon", "trang_thai"])
    for item in _feedback_rows(limit=10000):
        writer.writerow([
            item["id"], item["time"], FEEDBACK_CATEGORIES.get(item["category"], item["category"]),
            _csv_cell(item["message"]), _csv_cell(item["contact"]), item["source"],
            FEEDBACK_STATUS.get(item["status"], item["status"]),
        ])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="vifasttts-feedback.csv"',
                 "Cache-Control": "no-store"},
    )


@app.post("/admin/feedback/{feedback_id}/{status}")
def update_feedback(feedback_id: int, status: str, request: Request) -> Response:
    if not _admin_authorized(request):
        return _admin_denied()
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Chưa đặt ADMIN_PASSWORD; không thể cập nhật")
    if status not in FEEDBACK_STATUS:
        raise HTTPException(status_code=400, detail="Trạng thái không hợp lệ")
    with _STATS_LOCK:
        connection = _connect()
        try:
            connection.execute(
                "UPDATE feedback SET status=?, updated=? WHERE id=?",
                (status, time.time(), feedback_id),
            )
            connection.commit()
        finally:
            connection.close()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/suggestions/{suggestion_id}/{action}")
def review_suggestion(suggestion_id: int, action: str, request: Request) -> Response:
    if not _admin_authorized(request):
        return _admin_denied()
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Chưa đặt ADMIN_PASSWORD; tạm khoá duyệt")
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Hành động không hợp lệ")
    status = "approved" if action == "approve" else "rejected"
    with _STATS_LOCK:
        connection = _connect()
        try:
            connection.execute(
                "UPDATE suggestions SET status=?, updated=? WHERE id=? AND status='pending'",
                (status, time.time(), suggestion_id),
            )
            connection.commit()
        finally:
            connection.close()
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return FileResponse(ROOT / "static" / "brand" / "favicon.ico", media_type="image/x-icon")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "sample_rate": SAMPLE_RATE, "arch": acoustic.metadata.get("arch", "?"),
            "onset_has_q": acoustic.metadata.get("onset_has_q") == "true",
            "alpha": ALPHA, "pause": "model"}


@app.post("/api/tts")
def tts(payload: TtsRequest, request: Request) -> Response:
    text = " ".join(str(payload.text).replace("\x00", " ").split()).strip()
    if not text:
        raise HTTPException(status_code=422, detail="Nhập câu cần đọc")
    if len(text) > MAX_CHARS:
        raise HTTPException(status_code=422, detail=f"Tối đa {MAX_CHARS} ký tự")
    if not any(char.isalpha() for char in text):
        raise HTTPException(status_code=422, detail="Cần ít nhất một chữ cái")
    speed = min(1.2, max(0.8, float(payload.speed)))
    try:
        visitor = _visitor_hash(request, payload.visitor_id)
    except Exception:
        logger.exception("visitor stats failed")
        visitor = "unknown"
    if not _rate_ok(visitor):
        raise HTTPException(status_code=429, detail="Quá nhiều yêu cầu; thử lại sau 1 phút", headers={"Retry-After": "60"})
    source = payload.source if payload.source in ("web", "space", "api") else "api"
    overrides = _clean_overrides(payload.overrides)
    if not _lock.acquire(timeout=45):
        raise HTTPException(status_code=503, detail="Máy đang bận; thử lại sau", headers={"Retry-After": "10"})
    try:
        audio, elapsed, audio_seconds = _synthesize(text, speed, bool(payload.fixed_pauses), overrides)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("synthesis failed")
        raise HTTPException(status_code=500, detail="Lỗi tổng hợp; thử câu khác") from exc
    finally:
        _lock.release()
    try:
        _record_tts(visitor, len(text), audio_seconds, elapsed, bool(payload.fixed_pauses), speed, source)
    except Exception:
        logger.exception("tts stats failed")
    logger.info("tts ok %.2fs chars=%d fixed=%s", elapsed, len(text), payload.fixed_pauses)
    rtf = elapsed / audio_seconds if audio_seconds > 0 else 0.0
    return Response(content=audio, media_type="audio/wav", headers={
        "Content-Disposition": 'inline; filename="vifasttts-demo.wav"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Processing-Seconds": f"{elapsed:.3f}",
        "X-Audio-Seconds": f"{audio_seconds:.2f}",
        "X-RTF": f"{rtf:.4f}",
        "X-Characters": str(len(text)),
    })
