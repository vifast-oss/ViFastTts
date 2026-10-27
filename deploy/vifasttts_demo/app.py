"""Demo web ONNX cho N0 — research/non-commercial.

Chạy trong Docker; không cần torch. Mặc định model tự nghỉ, alpha 1.5, Vocos pretrained.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
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
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from vifasttts.frontend.chunking import (
    chunk_text,
    pause_seconds,
    split_clauses,
    steady_pause_seconds,
)
from vifasttts.frontend.normalizer import NormalizerOptions
from vifasttts.runtime.onnx_engine import OnnxAcousticModel, OnnxVocoder
from vifasttts.runtime.postprocess import postprocess, sharpen_mel_numpy

ROOT = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("MODEL_DIR", ROOT / "models"))
ACOUSTIC = MODEL_DIR / "acoustic.onnx"
VOCODER = MODEL_DIR / "vocoder.onnx"
MAX_CHARS = 300
RATE_LIMIT = 6
RATE_WINDOW = 60.0
ALPHA = float(os.environ.get("VIFASTT_SHARPEN_ALPHA", "1.5"))
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.environ.get("STATS_DB", DATA_DIR / "stats.sqlite3"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
VN_TZ = timezone(timedelta(hours=7))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("vifasttts-demo")

app = FastAPI(title="ViFastTTS research demo", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://huggingface.co"],
    allow_origin_regex=r"https://.*\.hf\.space",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
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


def _admin_html(stats: dict) -> str:
    rows = "".join(
        f"<tr><td>{item['time']}</td><td>{item['visitor']}</td><td>{item['chars']}</td>"
        f"<td>{item['audio_seconds']:.2f}s</td><td>{item['elapsed']:.2f}s</td>"
        f"<td>{item.get('source', 'api')}</td><td>{'có' if item['fixed_pauses'] else 'không'}</td></tr>"
        for item in stats["recent"]
    ) or "<tr><td colspan='7'>Chưa có lượt tạo nào.</td></tr>"
    auth_note = "Đang mở công khai, chưa đặt ADMIN_PASSWORD." if not ADMIN_PASSWORD else "Đã bật Basic Auth."
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>ViFastTTS · Thống kê</title>
<style>
body{{font-family:Arial,"Helvetica Neue",Helvetica,sans-serif;background:#f4f7f8;color:#18212b;margin:0;padding:28px}}
main{{max-width:980px;margin:0 auto}} h1{{letter-spacing:-.03em;margin:0 0 4px}}
.sub{{color:#637083;margin:0 0 20px}} .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.card{{background:#fff;border:1px solid #dbe3ea;border-radius:12px;padding:14px}}
.card b{{display:block;font-size:1.6rem;color:#0f766e}} .card span{{color:#637083;font-size:.84rem}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #dbe3ea;border-radius:12px;overflow:hidden;margin-top:18px}}
th,td{{text-align:left;padding:9px 12px;border-bottom:1px solid #edf1f3;font-size:.86rem}}
th{{background:#edf3f2;color:#245c57}} a{{color:#0f766e}}
.note{{background:#fff8e8;border:1px solid #f0d49a;padding:10px 12px;border-radius:10px;color:#7a4b00;font-size:.86rem;margin-top:16px}}
@media(max-width:700px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><main>
<h1>ViFastTTS · Thống kê</h1>
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
</div>
<table><thead><tr><th>Thời điểm</th><th>Ẩn danh</th><th>Ký tự</th><th>Audio</th><th>Xử lý</th><th>Nguồn</th><th>Nghỉ cố định</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="note">Số “người dùng” là ước lượng theo hash IP, không lưu IP hay nội dung text. {auth_note}</div>
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


class VisitRequest(BaseModel):
    visitor_id: str | None = None


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


def _synthesize(text: str, speed: float, fixed_pauses: bool) -> tuple[bytes, float, float]:
    started = time.perf_counter()
    options = NormalizerOptions(dialect="north")
    chunks = (split_clauses(text, max_chars=MAX_CHARS) if fixed_pauses
              else chunk_text(text, max_chars=MAX_CHARS))
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


@app.post("/api/visit")
def visit(payload: VisitRequest, request: Request) -> dict:
    _record_page(_visitor_hash(request, payload.visitor_id))
    return {"ok": True}


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


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "sample_rate": SAMPLE_RATE, "arch": acoustic.metadata.get("arch", "?"),
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
        raise HTTPException(status_code=429, detail="Quá nhiều yêu cầu; thử lại sau 1 phút")
    source = payload.source if payload.source in ("web", "space", "api") else "api"
    if not _lock.acquire(timeout=45):
        raise HTTPException(status_code=503, detail="Máy đang bận; thử lại sau")
    try:
        audio, elapsed, audio_seconds = _synthesize(text, speed, bool(payload.fixed_pauses))
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
    return Response(content=audio, media_type="audio/wav", headers={
        "Content-Disposition": 'inline; filename="vifasttts-demo.wav"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })
