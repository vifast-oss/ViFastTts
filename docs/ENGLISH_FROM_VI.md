# Đọc tiếng Anh từ kiến trúc tiếng Việt — cơ chế, thí nghiệm, kế hoạch

> **Trạng thái:** nghiên cứu, **chưa triển khai**. · **Ngày đo:** 30/10/2026.
> **Model dùng để đo:** N0 Ngọc Huyền Q-init (`runs/acoustic_ngochuyen_q/init_q.pt`),
> `arch=v2_slot5`, vocab `vi-q25-v1`, ONNX `artifacts/onnx/n0_q/{acoustic,vocoder}.onnx`.
> **Tài liệu liên quan:** `docs/MODEL_FLOW.md`, `docs/FRONTEND.md`, `docs/G2P_VIETNAMESE.md`,
> `docs/ACOUSTIC_V2.md`, `docs/EVAL_TOOLS.md`, `docs/MULTISPEAKER_EXPRESSIVE_RESEARCH.md`.

## 0. TL;DR

- Runtime **không có tầng âm vị**. Mỗi âm tiết là 5 ID rời; onset là **một** token trong 25.
  `syllable_to_phonemes` chỉ để phân tích/IPA, không đi vào model.
- Không thể "ghép 2 onset" ở input: chỉ có một slot O, và nucleus **luôn active**
  (`_active_mask` hard-code `nucleus = 1`). Trong 222.737 âm tiết train, **0** âm tiết có N=0.
- Ghép vector onset không compose: `S+TR` → "Sim", `S+T` → "TEAM" (model chọn một thành phần).
- **Waveform splice** (cắt audio tại biên acoustic, crossfade 5 ms) cho `/st/` + nguyên âm:
  "STREAM", "STING", "STONE". **Mel splice** kém hơn: "Such a", "S T I M", "SKIM".
- **Coda /s/** lấy từ onset `S`/`X` chạy: `cát + /s/` → **"cuts"**. `/z/` từ `D`/`GI`/`R` →
  "Cuz"; `/v/` từ `V` → "leave". `/f/` từ `PH` yếu; `/tʃ/` từ `CH`/`TR` kém.
- Trần hiện tại là **/st/ + nguyên âm**, không phải `/str/`: không có `/ɹ/`, không có coda
  `/l r s z f v b d g/`, không có cụm phụ âm ngoài C+/w/.
- Ba mức triển khai: **M0** từ điển + splice (không retrain) · **M1** unit phụ âm N=NONE +
  dữ liệu cụm + fine-tune · **M2** frontend âm vị / model EN riêng.

## 1. Cơ chế hiện tại (as-built)

### 1.1 Đầu vào

`frontend/vocab.py::ComponentVocabs.default()`:

| Trường | Số token | Ghi chú |
| --- | ---: | --- |
| onset | 25 | `NONE + 24`; Q ở cuối |
| medial | 2 | `NONE, W` |
| nucleus | 15 | **không có NONE** |
| coda | 11 | `NONE + 10` |
| tone | 6 | **không có NONE** |
| boundary | 4 | `NONE, WORD, PHRASE, SENTENCE` |
| punctuation | 6 | `NONE, COMMA, PERIOD, QUESTION, EXCLAMATION, OTHER` |

Mỗi âm tiết → 7 ID. `vocab_hash` là SHA256 của danh sách canonical; đổi token/thứ tự là đổi hash
và mọi checkpoint/ONNX cũ không nạp được (`verify_vocab_hash`).

### 1.2 Slot và thời lượng

`models/v2_slot5.py`:

- Mỗi âm tiết có 4 slot **O/M/N/C** + một slot **G** (gap/silence) sau đó.
- `_active_mask`: onset/medial/coda active theo `!= 0`; **nucleus luôn active**.
- `ratio_mlp` dự đoán tỷ lệ frame cho 4 slot; `distribute_slots` ưu tiên **N > O > C > M**;
  active slot được ≥ 1 frame nếu đủ frame.
- `duration` dự đoán `d_syl`; `seg_durations [N,4]` (từ MFA) là nhãn thời lượng khi train.
- Decoder nhận `slot_expander(h_syl, role, emb_component)` theo từng frame; mel → Vocos.

Hệ quả: **đơn vị nhỏ nhất là âm tiết có nguyên âm**. Không có "âm tiết phụ âm trần".

### 1.3 Dữ liệu

- Manifest train: `data/codelung/train_clean_v2_dur_seg_slot4.jsonl` — 9.763 row,
  **222.737 âm tiết**, **0** âm tiết có `seg_durations[2] == 0`.
- N0: `pnnbao-ump/ngochuyen_voice` (CC BY-NC 4.0), 21,57 h gốc / 19,89 h sau lọc.
- Text tiếng Anh trong manifest đã được **respell** thành âm tiết Việt (`en`, `pi`, `men`...),
  không lưu token tiếng Anh. Audio có thể chứa cách phát âm tiếng Anh của người nói, nhưng nhãn
  không phải nhãn âm vị tiếng Anh.

### 1.4 Frontend tiếng Anh

- `frontend/english_fallback.py`: từ điển respelling (~758 từ + acronym + product).
- `frontend/oov.py`: acronym/product → English fallback → đánh vần chữ cái → `None`
  (`FALLBACK_REQUIRED`).
- Từ OOV không giải được rơi vào placeholder `nucleus=A`; ví dụ `street`, `splash`,
  `strengths` bị đọc thành một nguyên âm /a/ ngắn.

### 1.5 Bất biến

- `MAX_POSITIONS = 4096` frame (~43,7 s @ hop 256).
- ONNX: opset 18, `dynamo=False`; output cũ giữ nguyên tên/thứ tự, chỉ thêm output mới vào cuối.
- `vocab_hash` phải khớp giữa checkpoint, ONNX, Rust resources và HF bundle.

## 2. Vì sao không ghép onset ở input

### 2.1 Onset là category, không phải chuỗi âm vị

`nn.Embedding(25, 64)` là bảng tra vector tự do. `TR` là **một** category (/tɕ/ bắc hoặc /ʈ/ nam),
không phải `T` + `R`. Không có phép cộng vector nào được train để compose.

### 2.2 Chỉ có một slot O

Mỗi âm tiết có đúng một slot onset. Hai onset = hai âm tiết = ít nhất một nguyên âm ở giữa
("xờ trim"). Không có cấu trúc O1/O2.

### 2.3 Thí nghiệm ghép vector

Mở rộng bảng embedding ONNX thêm 1 hàng, gán vector tổ hợp, cho model đọc "trim" với onset mới
(không train):

| Onset đưa vào | ASR |
| --- | --- |
| `TR` (gốc) | "Team" |
| `S+TR` (trung bình) | "Sim." |
| `S+T+R` | "SIEM" |
| `S+T` | "TEAM" |
| `S` | "Sim-" |

Model **collapse về một thành phần**; không ra hai phụ âm. Thời lượng ~0,21–0,26 s = một onset.

### 2.4 Tiền lệ Q = K

`factory.expand_legacy_onset_state` mở rộng embedding 24 → 25 hàng và copy hàng `K` cho `Q`.
Cách này chỉ đúng vì Q và K **cùng một âm** ở phương ngữ hiện tại. `S+TR` không phải một âm
đã có hàng embedding.

## 3. Thí nghiệm ghép âm tiết (30/10/2026)

### 3.1 WER 25 từ tech

Cùng một thước: `faster-whisper medium` int8, `language=en`, `beam_size=5`, cắt im lặng,
chặn pause model (`gate_threshold=1.01`).

| | TTS hiện tại | Giọng bản ngữ macOS (Samantha) |
| --- | ---: | ---: |
| WER | **2,16** (216%, có lỗi chèn) | **0,48** |
| Đúng nguyên từ | **1/25** | **20/25** |

- `quick` → "quích" → **"quick"**; `question` → "quét sần" → **"question"**.
- `stream` → "xờ trim" → "SUCHI M"; `string` → "xờ trinh" → "SUCHING";
  `screen` → "xờ rin" → "Sozine".
- `street`, `splash`, `strengths` (OOV) → placeholder /a/, ASR nghe "Huh."

**Caveat:** ASR trên từ rời 0,1–0,5 s không đáng tin (native cũng chỉ 20/25; Whisper có
hallucination trên clip ngắn). Đây là proxy, không phải test nghe.

### 3.2 N = 0 (bỏ nucleus)

Gọi thẳng model với `seg_durations = [O, 0, 0, 0]`:

| Input | ASR | Ghi chú |
| --- | --- | --- |
| `sa` N=0, 12 frame | "S-" | decoder render được phụ âm trần |
| `tra` N=0, 12 frame | "" | closure/affricate không rõ |
| `a` N=12 (đối chứng) | "Uh" | vowel-only |
| `s + tr + im` (tr=10) | "Steam." | có cụm, không schwa |
| `s + tr + inh` (tr=4/6/8) | "SING" | **mất /tr/** |
| `s + tr + it` | "See?" | mất /tr/ |
| `s + tr + ong` | "So-" / "S'chao" | hỏng |

Kết luận: **một unit N=0 chạy**, nhưng **chuỗi O→O không ổn định** vì training không có
một ca O→O nào (0/222.737). Muốn dùng N=0 phải train với dữ liệu cụm.

### 3.3 Mel splice vs waveform splice

Cùng cụm `/s + tr + im/`:

| Cách | ASR |
| --- | --- |
| **Waveform** + crossfade 5 ms | **"STREAM"** / "STING" / "STONE" |
| Mel, hard splice | "Such a" |
| Mel, crossfade 2 frame | "S T I M" |
| Mel, crossfade 3 frame | "SKIM" |
| Mel, chuẩn hoá energy rồi hard splice | "Such. A." |

Waveform thắng. Lý do: Vocos là mel → waveform; mel splice buộc vocoder tự tạo phase cho chỗ nối
(và Vocos yếu về phase — xem §9). Waveform đã có phase/coarticulation; crossfade chỉ che chỗ nối.

### 3.4 Cắt theo slot model vs cắt theo acoustic

`sa`: slot O = 15 frame; nhưng vowel thật bắt đầu ở frame 13:

```
frame 11: ZCR 0,76 · lo/hi 0,013   ← còn /s/
frame 12: ZCR 0,41 · lo/hi 0,202   ← transition
frame 13: ZCR 0,14 · lo/hi 0,435   ← vowel bắt đầu
frame 14: ZCR 0,02 · lo/hi 4,549   ← /a/ rõ
```

- Cắt ở 15 (biên slot) → "SACHIM" (dính transition).
- Cắt ở 13 (biên acoustic) → **"Steam"**.
- `xa`: O = 11, vowel @ 10 → **"Steam"**.

Biên slot là biên **ngôn ngữ**, không phải biên **âm học**. Dùng ZCR + band energy để tìm vowel
onset; không cần model duration (model vốn đã tất định).

### 3.5 `s + trim` vs `s + t + r`

| Cách | ASR |
| --- | --- |
| `s(sa) + trim` | **"Steam"** |
| `s + t(ta) + rim` | "S I M" |
| `s + t(ta) + r(ra) + im` | "Subzim" |
| `s + t[4:8] + rim` | "S P Z I M" |
| `s + t[6:8] + r + im` | "S-S-S-Y-" |

`trim` đã có `/tr/ + /i/ + /m/` với coarticulation tự nhiên; chỉ cần xử lý `/s/`. `ta - a` chủ yếu
là closure im lặng + burst; `ra - a` là /z/ (bắc) hoặc /ʐ/ (nam), **không phải /ɹ/**.

### 3.6 `tall` và coda /l/

- `tall` OOV → parser đánh vần **"tê a lờ lờ"**.
- `thô + /l/` (l từ `la - a`) → "Cool." / "Boom." / "PUM".
- `tho + /l/` → "Come." / "Tom." / "POM".
- Kéo speed 0,5 → vẫn "Come."; `/l/` là onset approximant, không phải coda /l/.
- Hướng tốt hơn: **coda W** (L-vocalization): `thoou` = `TH + OO + W` = /tʰɔːw/;
  `thou` = `TH + O + W`; `thôu` = `TH + Ô + W` (hợp "toll").
  Spectrogram `thoou` khớp hướng burst → vowel mở → glide F2 tụt; ASR từ rời không kết luận
  ("pow"/"How?"), cần nghe A/B.

### 3.7 Coda fricative

| Base + coda | ASR |
| --- | --- |
| `cát` + /s/ từ `sa` | **"cuts"** |
| `cát` + /s/ từ `xa` | **"CUTS"** |
| `cát` + /z/ từ `za` | "cutse" (devoice sau /t/) |
| `cát` + /z/ từ `da`/`ra` | "Cuz" |
| `cát` + /f/ từ `pha` | "cut" (mất /f/) |
| `cát` + /v/ từ `va` | "cut" (mất /v/) |
| `li` + /v/ từ `va` | **"leave"** |
| `li` + /f/ từ `pha` | "LEAVE" (nghe thành /v/) |
| `ca` + /tʃ/ từ `cha`/`tra` | "CUT" (mất affricate) |

Kết luận: **xát → xát** là hướng tốt nhất (/s/, /z/, /v/); /f/ yếu; affricate kém.

## 4. Inventory dùng cho tiếng Anh

### 4.1 Onset

**Tốt:**

| Token | IPA bắc | Dùng cho | Cắt |
| --- | --- | --- | --- |
| `M` | /m/ | /m/ | khó (mũi) |
| `N` | /n/ | /n/ | khó |
| `L` | /l/ | /l/ onset | khó |
| `PH` | /f/ | /f/ | dễ (xát) |
| `V` | /v/ | /v/ | trung bình |
| `H` | /h/ | /h/ | dễ |
| `X` | /s/ | /s/ | **dễ** |
| `S` | /s/ (bắc) | /s/ | **dễ** |
| `D`/`GI`/`R` | /z/ (bắc) | /z/ | trung bình |
| `TH` | /tʰ/ | /t/ đầu (aspirated) | khó (tắc) |
| `Q`+`W` | /kw/ | /kw/ | — |
| `NONE`+`W` | /w/ | /w/ | — |

**Gần (phải nghe):** `T` /t/ (sau /s/, cuối; thiếu bật hơi) · `K` /k/ · `P` /p/ ·
`B` /ɓ/ (implosive) · `Đ` /ɗ/ (implosive) · `G` /ɣ/ (xát, không phải stop) ·
`TR` /tɕ/ (cho /tʃ/) · `CH` /tɕ/ (cho /tʃ/) · `NH` /ɲ/ (cho /nj/).

**Không dùng:** `KH` /x/ · `NG` /ŋ/ (onset) · `R` /z/ cho /r/ · `TH` cho /θ/.

**Thiếu hẳn:** /θ ð ʃ ʒ dʒ ɹ j/ (bắc) + cụm ngoài C+/w/.

### 4.2 Coda

**Có sẵn:** `M` /m/ · `N` /n/ · `NG` /ŋ/ · `P` /p/ (không bung hơi) · `T` /t/ (không bung hơi) ·
`C` /k/ (không bung hơi) · `CH` [c] (gần /tʃ/, nhưng là stop) · `J` /j/ · `W` /w/.

**Thiếu:** /s z f v θ ð ʃ ʒ l r b d g dʒ/.

**Bù bằng splice:** /s/ ← `S`/`X` (tốt) · /z/ ← `D`/`GI`/`R` (được) · /v/ ← `V` (được) ·
/f/ ← `PH` (yếu) · /tʃ/ ← `CH`/`TR` (kém) · /l/ ← `W` (L-vocalization) · /r/ ← `W` hoặc bỏ ·
/b d g/ ← `B`/`Đ`/`G` (không đáng tin).

### 4.3 Cắt được hay không — theo manner

| Lớp | Ví dụ | Cắt | Vì sao |
| --- | --- | --- | --- |
| Xát vô thanh | S, X, PH, H | **dễ** | noise liên tục, ZCR/band rõ |
| Xát hữu thanh | V, D/GI/R | trung bình | voicing làm biên kém rõ |
| Tắc | T, TH, K, P, B, Đ, G | khó | closure im lặng + burst chớp nhoáng |
| Affricate | TR, CH | trung bình | cắt phần frication, tránh closure |
| Mũi | M, N, NG, NH | khó | formant giống vowel |
| Tiếp cận | L, R | khó | formant giống vowel |
| Glide | medial W, coda J/W | không cắt rời | là một phần của vần |

### 4.4 Phương ngữ

Bảng trên là **bắc** (model live). Nam đổi: `D`/`GI` = /j/, `R` = /ʐ/, `S` = /ʂ/,
`TR` = /ʈ/, `CH` = /c/. Nam có /j/ onset (tốt cho "yes") nhưng /z/ và /s/ khó hơn.

## 5. Recipe splice (M0 — không retrain)

### 5.1 Nguyên tắc

1. **Cắt waveform**, không cắt mel. **Waveform = audio** (chuỗi mẫu thời gian); "cắt trước phổ"
   nghĩa là cắt audio **trước khi** tính spectrogram, không phải một thứ khác với "cắt audio".
   "Cắt trong phổ" = cắt frame mel/STFT sau khi đã tính. Mel splice làm vocoder tự tạo phase
   và hỏng chỗ nối.
2. **Cắt tại biên acoustic**, không dùng biên slot model.
3. **Crossfade 5 ms**; không chuẩn hoá energy toàn đoạn.
4. **Chỉ xử lý /s/** cho `/st/`; giữ `trim`/`trinh` nguyên vẹn.
5. **Không ghép /l/ coda**; dùng coda `W` (`thoou`) cho L-vocalization.

### 5.2 Code tham chiếu

```python
HOP = 256  # 24 kHz, hop 256

def vowel_start(wav, sr=24000):
    """Frame đầu tiên có ZCR thấp + năng lượng thấp tần trội."""
    import numpy as np
    for i in range(2, len(wav) // HOP):
        x = wav[i * HOP:(i + 1) * HOP]
        spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        freqs = np.fft.rfftfreq(len(x), 1 / sr)
        lo = spec[freqs < 1000].sum()
        hi = spec[freqs >= 2000].sum()
        zcr = np.mean(np.abs(np.diff(np.sign(x))) > 0)
        if zcr < 0.2 and lo / (hi + 1e-9) > 0.3:
            return i
    return len(wav) // HOP

def xfade(a, b, n=120):
    import numpy as np
    n = min(n, len(a), len(b))
    ramp = np.linspace(0, 1, n, dtype=np.float32)
    return np.concatenate([a[:-n], a[-n:] * (1 - ramp) + b[:n] * ramp, b[n:]])

# Giả mã: render(text) → object có .wav (float32) và .slot_durations.
# Trong repo, dùng OnnxAcousticModel + OnnxVocoder (xem runtime/onnx_engine.py).
# stream ≈ cut_s("sa") + "trim"
s = render("sa"); cut = vowel_start(s.wav)
s_part = s.wav[: cut * HOP]
stream = xfade(s_part, render("trim").wav)
```

### 5.3 Giới hạn

- Chỉ đúng khi phần đuôi là âm tiết Việt có thật (`trim`, `trinh`); `trít`, `tròng` hỏng.
- Cut point nhạy: `s=11–13`, `tr=2–4` mới ra "STREAM"; `s=15` ra "Such a".
- Không có `/ɹ/`: kết quả là `/st/ + /i/ + /m/` ("Steam"), không phải `/str/`.
- Là post-process ngoài ONNX graph; không dùng được cho streaming/batch chuẩn.
- Phải nghe kiểm chứng; ASR "STREAM" có thể là lexical filling.

## 6. Kế hoạch triển khai

### 6.1 M0 — từ điển + splice (1–2 ngày, không retrain)

**Việc làm:**

1. Bổ sung `english_fallback.py`:
   - `tall` → `thoou` (TH + OO + W = /tʰɔːw/); `toll` → `thôu` (TH + Ô + W);
     `call` → `koou` (K + OO + W; K không bật hơi, chỉ gần);
   - các từ `/str/` phổ biến: `stream` → `xờ trim`, `string` → `xờ trinh`, ...
2. Sửa OOV: từ EN không có trong từ điển không được rơi vào placeholder /a/; thêm G2P EN →
   respelling Việt gần nhất (greedy theo bảng âm vị), hoặc đánh vần có kiểm soát.
3. (Tuỳ chọn) Post-processor splice `/s/ + tail` cho danh sách từ cố định; chỉ dùng offline/demo.

**Cổng:** 50 từ EN + 20 câu; WER (ASR) + nghe A/B; không đụng đường tiếng Việt.
**Trần:** `/st/`, không `/str/`; không giải quyết coda /s z/ phổ quát.

### 6.2 M1 — unit phụ âm N=NONE + dữ liệu cụm (1–2 tuần + data)

**Code phải sửa:**

| File | Thay đổi |
| --- | --- |
| `frontend/vocab.py` | thêm `NONE` cho nucleus (và tone `NONE`); bump `VOCAB_VERSION`/hash |
| `models/v2_slot5.py::_active_mask` | `nucleus = (features[..., 2] != NUCLEUS_NONE)` thay vì `ones` |
| `data/v2_targets.py::structural_active` | nucleus = `abstract != "NONE"` thay vì `True` |
| `data/v2_targets.py::ratio_targets` | target N=0, mask N=false cho unit N=NONE |
| `data/v2_targets.py::f0_targets` | unit N=0: weight N=0; bỏ qua F0/vuv/energy |
| `data/v2_targets.py::segment_pools` | mask energy/vuv cho unit N=0 |
| `models/slot_ops.distribute_slots` | N inactive → O/C/M nhận frame; kiểm bất biến Σ=d_syl |
| gate/pause | `gaps=0` giữa các unit trong cùng cụm; boundary `NONE` hoặc token `CLUSTER` mới |

**Dữ liệu:**

- Cần **unit phụ âm trần + timing**. Ba nguồn:
  1. English phone-level alignment (MFA EN) trên cùng giọng;
  2. cắt onset từ audio Việt hiện có (coarticulated; chỉ đáng cho fricative);
  3. thu 100–200 từ/cụm với người nói mục tiêu (sạch nhất).
- Tạo row: `[sa(N=0, O=d), tra(N=0, O=d), im(N=I, C=M)]` hoặc `[sa(N=0), trim]`.
- Không dùng `seg_durations` cũ để suy ra cụm: onset là **một** slot, không có timing con.

**Train:**

- Warm-start N0; fine-tune; batch 8 + `SameNBatchSampler`; LR theo `max_steps`.
- Theo dõi: EN WER, VI holdout CER, nghe A/B, F0/energy của unit N=0.
- Cổng đề xuất: EN WER ≤ 1,0 (hiện 2,16; native 0,48) · VI CER delta ≤ +0,01 ·
  MOS ≥ 3,5. Trượt VI → dừng.

**Export/deploy:**

- ONNX opset 18, `dynamo=False`; output cũ giữ nguyên; `vocab_hash` mới.
- Sync Rust resources, HF bundle, web/Space; kiểm tải thật.

**Rủi ro:** quên tiếng Việt (catastrophic forgetting), lệch timbre nếu dùng giọng khác,
thiếu `/ɹ/` và coda `/s z/`, chi phí data.

### 6.3 M2 — frontend âm vị / model EN riêng (dự án riêng)

- Bộ âm vị chung Việt–Anh (tham khảo arXiv 2508.19270: bilingual phoneme set cho
  Vietnamese–English).
- Frontend: EN G2P (CMUdict/sea-g2p/viG2P) → IPA; VI rule-based → IPA; chuẩn hoá về bộ chung.
- Acoustic: chuỗi phoneme + duration (hoặc hybrid syllable + phoneme); Vocos dùng lại
  (mel → wave là language-agnostic).
- Data: code-switch Việt–Anh cùng giọng; hoặc shared latent space (tham khảo Lao–English
  code-switched TTS, ACL 2025).
- Cổng: EN WER ≤ 0,3–0,5 · MOS ≥ 4,0 · VI không đổi.

### 6.4 So sánh

| | M0 | M1 | M2 |
| --- | --- | --- | --- |
| Retrain | không | có | có (kiến trúc mới) |
| Vocab/hash | không đổi | đổi | đổi |
| `/st/` | splice | học | học |
| `/str/` | không | gần (thiếu /ɹ/) | có |
| Coda /s z/ | splice /s/ | học | có |
| Công sức | ngày | tuần + data | dự án |
| Rủi ro VI | 0 | trung bình | cao |

## 7. Thước đo và cổng

1. **Bộ EN:** 50 từ tech + 20 câu + 20 từ thường; ghi âm/ASR + nghe A/B mù.
2. **WER:** `faster-whisper medium` (theo mẫu `tools/audit_real_cer.py`), nhưng **không**
   dùng một mình: từ rời ngắn có hallucination; native cũng 20/25.
3. **Nghe:** ABX/MOS cho `/s/`, `/str/`, `/l/`, `/r/`, coda /s z/; spectrogram kiểm F3 /r/,
   formant /l/.
4. **VI regression:** holdout CER + nghe; so B0/N0.
5. **Ablation:** dictionary-only → splice → N=0 → M1 → M2.

## 8. Rủi ro

- ASR không đo được `/ɹ/`; "STREAM" có thể là lexical filling.
- Splice không tổng quát; cut point hand-tuned; không streaming.
- Single speaker, dataset CC BY-NC, không có EN cùng giọng.
- Đổi vocab/hash → mọi artifact cũ invalid; sync Rust/HF/web.
- Prosody syllable-timed; thiếu stress/giảm âm; coda inventory hẹp.
- Catastrophic forgetting khi fine-tune EN.

## 9. Bối cảnh nghiên cứu (web)

- **Unit selection / concatenative TTS:** chọn đơn vị + join cost + smoothing; PSOLA
  (Moulines & Charpentier 1990) và TD-PSOLA là chuẩn để ghép waveform và chỉnh F0/duration.
  Splice của chúng ta là một "unit selection mini" — nhưng đơn vị là cả âm tiết, không phải
  phoneme, nên join cost không cứu được coarticulation.
- **Spectral smoothing:** Chappell & Hansen (ICSLP 1998), Vepa & King (2006) — discontinuity
  ở chỗ nối là vấn đề đo được; smoothing giúp nhưng không tạo transition chưa có.
- **Vocos / phase:** arXiv 2607.24323 — Vocos mạnh về magnitude, yếu về phase; mel splice
  buộc vocoder tái tạo phase nên dễ hỏng. Đây là lý do waveform splice thắng.
- **Vietnamese phonology:** Wikipedia — 19 consonant phonemes; syllable có nucleus + tone
  bắt buộc; cluster duy nhất là /Cw/; coda /p t k/ không bung hơi. Khớp với `vocab.py`
  (nucleus/tone không có NONE) và `CODA_BROAD`.
- **L-vocalization:** Wikipedia — /l/ cuối → [w]/[o]/[ʊ] ở Cockney, Estuary, AusNZ, một số
  US; "tall" nằm trong nhóm /ɑul/ → /ɔː/ (all, ball, call, fall, tall...). Cơ sở cho `thoou`.
- **Vietnamese learners & clusters:** IJSSHR 2025 — người Việt thường **xóa** phụ âm đầu
  trong cluster hoặc đổi voicing; epenthesis ít hơn các nhóm L1 khác. Vì vậy "trim" (xóa /s/)
  và "xờ trim" (epenthesis) là hai chiến lược tự nhiên; cả hai đều không cho /str/.
- **Bilingual phoneme set / code-switch TTS:** arXiv 2508.19270 (Việt–Anh), ACL 2025
  (Lao–English shared latent) — nền cho M2.
- **Whisper:** paper gốc + các phân tích WER — WER phạt khác biệt format và có hallucination
  trên clip ngắn; dùng ASR làm proxy, không làm cổng duy nhất.

## 10. Tài liệu tham khảo

- Vietnamese phonology — https://en.wikipedia.org/wiki/Vietnamese_phonology
- L-vocalization — https://en.wikipedia.org/wiki/L-vocalization
- Vocos phase — https://arxiv.org/abs/2607.24323
- Bilingual Vietnamese–English phoneme set — https://arxiv.org/abs/2508.19270
- Hunt & Black, unit selection — https://www.ee.columbia.edu/~dpwe/e6820/papers/HuntB96-speechsynth.pdf
- PSOLA — https://en.wikipedia.org/wiki/PSOLA
- Chappell & Hansen, spectral smoothing — https://www.isca-archive.org/icslp_1998/chappell98_icslp.pdf
- Vepa & King, join cost/smoothing — https://infoscience.epfl.ch/entities/publication/ba074aa6-01d7-4350-b7b9-b87166e36214
- Vietnamese learners & English clusters — https://ijsshr.in/v8i9/Doc/77.pdf
- Whisper paper — https://cdn.openai.com/papers/whisper.pdf
- Lao–English code-switched TTS — https://aclanthology.org/2025.ccl-1.80.pdf

## 11. Ghi chú tái lập

Các probe trong tài liệu này chạy từ `/private/tmp/opencode/` (không nằm trong repo):
`en_wer_probe2.py`, `native_wer.py`, `nucleus_none_probe.py`, `n0_str_probe.py`,
`mel_splice_probe.py`, `wave_splice_probe.py`, `acoustic_cut.py`, `s_plus_trim.py`,
`tall_probe.py`, `str_compose.py`.

Theo quy ước repo, trước khi dùng lại cho sản phẩm phải **promote vào `tools/`** (kèm test)
hoặc chuyển thành hàm trong `src/vifasttts/runtime/`. Code tham chiếu ở §5.2 đủ để dựng lại
recipe splice; các thí nghiệm N=0/M1 cần script train riêng.
