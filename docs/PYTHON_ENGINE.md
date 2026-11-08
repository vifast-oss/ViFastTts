# Python engine & stream API

> Mục đích: Python (web demo, CLI, notebook, service riêng) dùng **cùng một engine
> ONNX cấp cao** thay vì mỗi nơi tự chunk/tính timing/ghép WAV.

## 1. Thư viện

Module: `vifasttts.runtime.tts_engine`.

```python
from vifasttts.runtime.tts_engine import OnnxTtsEngine, TtsSettings

engine = OnnxTtsEngine.from_paths(
    "artifacts/onnx/n0_q/acoustic.onnx",
    "artifacts/onnx/n0_q/vocoder.onnx",
    provider="cpu",
)
result = engine.synthesize("Xin chào các bạn", TtsSettings(speed=1.0, alpha=1.5))
open("out.wav", "wb").write(result.wav)
print(result.sample_rate, len(result.units), result.audio_seconds)
```

Stream:

```python
for chunk in engine.iter_chunks("Câu một. Câu hai!", TtsSettings(max_chars=60)):
    chunk.samples       # numpy float32 mono
    chunk.sample_rate   # 24000
    chunk.units         # timing tuyệt đối, [] với khoảng nghỉ
    chunk.pause         # True nếu là khoảng lặng chèn giữa chunk
```

- `TtsSettings.normalized()` kẹp speed `0.5–2.0`, alpha `0.5–3.0`,
  max chars `50–5000`, dialect `north|central|south`.
- `synthesize()` trả `SynthesisResult(wav, sample_rate, units, elapsed, audio_seconds)`.
- `iter_chunks()` không gom cả file; **không hỗ trợ `peak_normalize`** vì cần đỉnh
  toàn file (giống Rust). Dùng `synthesize()` nếu cần peak normalize.
- `normalizer=NormalizerOptions(...)` cho phép caller truyền từ điển/custom reading
  đã merge; web demo dùng đúng options cho cả full và stream.
- `karaoke_lines`, `srt_from_units`, `vtt_from_units`, `pcm16`, `wav_bytes` export
  cùng module để service khác không tự viết lại.
- `TtsSettings.resolve_oov` nhận từ request `resolve_oov` của cả full và stream;
  UI web/Space có checkbox **Resolve OOV** (`docs/SETTINGS_GLOSSARY.md`).

## 2. Web Python

`deploy/vifasttts_web/app.py` dùng `OnnxTtsEngine` đã nạp sẵn:

| Endpoint | Ý nghĩa |
|---|---|
| `GET /api/config` | giới hạn + defaults + capabilities + endpoint |
| `POST /api/tts` | full WAV hoặc JSON+karaoke (như cũ) |
| `POST /api/tts/stream` | NDJSON: `units` → `audio` từng chunk → `done` |

`/api/config` ví dụ:

```json
{
  "max_chars": 3000,
  "defaults": {"speed": 1.0, "alpha": 1.5, "max_chars": 300,
               "fixed_pauses": false, "peak_normalize": false,
               "dialect": "north", "resolve_oov": true},
  "capabilities": {"stream": true, "karaoke": true, "srt": true, "vtt": true,
                   "peak_normalize_stream": false},
  "endpoints": {"tts": "/api/tts", "stream": "/api/tts/stream", "config": "/api/config"}
}
```

NDJSON giống server Rust (`docs/API_CONTRACT.md` mục 4). PCM là 16-bit mono
little-endian, base64. UI web có checkbox **Stream (phát ngay)**: dùng WebAudio
phát từng chunk, ghép WAV + SRT/VTT để tải lại sau khi xong.

## 3. Giới hạn / lưu ý

- Stream và full dùng **cùng engine**; full giữ lock toàn cục để giới hạn request nặng.
  Stream **không giữ lock** vì ORT `Run` chạy song song được và generator sync có thể bị
  client ngắt trước khi `finally` chạy (giữ lock sẽ làm request sau treo).
- `peak_normalize` + stream trả **422**; UI tự bỏ qua peak khi bật stream.
- `done` của stream có thêm `processing_seconds`, `audio_seconds`, `rtf`; UI hiển thị
  RTF và lưu lịch sử gần đây ở localStorage (không lưu audio).
- ONNX session được nạp một lần lúc app khởi động, không nạp lại mỗi request.
- Python engine là bản song song của Rust FFI; logic âm tiết/timing vẫn lấy từ
  frontend Python hiện tại. Nếu sửa công thức slot/timing phải sửa cả hai và
  chạy test `tests/test_tts_engine.py` + `tests/test_onnx_runtime.py`.
