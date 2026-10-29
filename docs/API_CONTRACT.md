# Hợp đồng HTTP & model API

> Mục đích: mọi client (web/extension/Android/iOS/desktop) dùng cùng field,
> endpoint và default. Phần UI/audio/storage vẫn native.

## 1. Endpoint

| Method | Path | Ý nghĩa |
|---|---|---|
| GET | `/healthz` | model/sample rate/arch/vocab/hash |
| GET | `/api/config` | max chars/rate limit |
| POST | `/api/tts` | tổng hợp WAV hoặc JSON+karaoke |
| POST | `/api/tts/stream` | NDJSON: `units`, `audio`, `done`, `error` |
| GET | `/api/models/search?q=&limit=` | tìm repo HuggingFace qua server |
| GET | `/api/models/files?repo=` | file `.vfa/.vfts` |
| GET | `/api/models/download?repo=&path=` | bytes bundle |

Contract version hiện tại: **1** (`vifasttts_api_contract_json`).

## 2. Request `/api/tts`

```json
{
  "text": "Xin chào",
  "speed": 1.0,
  "alpha": 1.5,
  "max_chars": 300,
  "fixed_pauses": false,
  "peak_normalize": false,
  "dialect": "north",
  "resolve_oov": true,
  "dictionary": "AI = ây ai",
  "custom_reading": {"TP.HCM": "thành phố hồ chí minh"},
  "karaoke": true
}
```

- `speed` kẹp `0.5..2.0`.
- `alpha` kẹp `0.5..3.0`.
- `max_chars` kẹp `50..5000`; `0` được hiểu là default 300 ở UI cũ.
- `dialect`: `north|central|south`.
- `dictionary`: text `key = cách đọc`, parser Rust.
- `custom_reading`: map token-level, ưu tiên theo parser.
- `karaoke=true`: response JSON; ngược lại response WAV bytes.

## 3. Response JSON

```json
{
  "sample_rate": 24000,
  "duration_ms": 2000,
  "audio_base64": "UklGR...",
  "karaoke": {
    "version": 1,
    "sample_rate": 24000,
    "duration_ms": 2000,
    "units": [],
    "lines": []
  },
  "srt": "1\n00:00:00,000 --> ...",
  "vtt": "WEBVTT\n\n...",
  "vtt_karaoke": "WEBVTT\n\n..."
}
```

`karaoke` có thể `null` nếu model không xuất slot durations; client vẫn phát
`audio_base64` và bỏ phụ đề.

## 4. Stream NDJSON

```text
{"type":"units","units":[...]}
{"type":"audio","sample_rate":24000,"pcm_base64":"..."}
{"type":"done","samples":48000,"chunks":3,"cancelled":false,"sample_rate":24000}
```

- PCM là 16-bit mono little-endian, base64.
- `units` có `TimedUnit`; dùng để dựng SRT/VTT sau stream.
- Client tự chọn có ghi WAV hay không; server không quyết định.
- Huỷ stream: đóng kết nối/không đọc tiếp; server dừng ở chunk kế.

## 5. Model endpoints

`GET /api/models/search` trả mảng model HuggingFace (`id`, `siblings`, ...).
`GET /api/models/files` trả `[{path,size,type}]`, chỉ `.vfa/.vfts`.
`GET /api/models/download` trả raw bundle; server kiểm manifest/hash trước khi trả.

Client trực tiếp HuggingFace dùng cùng shape:
- search: `/api/models?search=&limit=&full=true`
- files: `/api/models/{repo}/tree/main?recursive=true`
- download: `/{repo}/resolve/main/{path}`

Không dùng raw `acoustic.onnx`/`vocoder.onnx` qua model endpoint; chỉ bundle.

## 6. Quy tắc tương thích

1. Chỉ thêm field có default; không đổi tên field cũ.
2. `contract_version` tăng khi bỏ/đổi nghĩa field.
3. Client cũ gửi thiếu field → server dùng default canonical.
4. `resolve_oov` default **true** cho UI mới; server vẫn chấp nhận false.
5. `max_chars=0` chỉ là legacy; normalize thành 300.
