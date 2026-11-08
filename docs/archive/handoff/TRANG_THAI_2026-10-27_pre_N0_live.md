> **LỊCH SỬ — không còn hiệu lực (archive từ 27/10/2026).**
> Trạng thái hiện hành: `docs/handoff/TRANG_THAI.md`; mục lục: `docs/README.md`.
> Giữ để audit/tái lập, không dùng để quyết định.

# TRẠNG THÁI (STATUS) — nguồn sự thật duy nhất

> **Cho người không kỹ thuật (5 dòng):**
> 1. Sản phẩm đang chạy bằng **PyTorch** với model **P2**; bản đóng gói ONNX **chưa bật**.
> 2. Chất lượng giọng **đóng băng**; hướng "rè do acoustic dải thấp" đã đóng, chỉ sửa regression.
> 3. Chưa train thêm; mọi thay đổi production phải qua cổng đo đã đăng ký trước.
> 4. ONNX đã **đóng băng**; production giữ P2 + PyTorch Vocos.
> 5. Chi tiết quyết định: `DECISIONS.md`; ngoại lệ có phạm vi: `EXCEPTIONS.md`.

> **N0 (27/10/2026) — ĐÃ TRAIN XONG — CHỜ NGHE.** Dataset mới `ngochuyen_voice` (single speaker, 24 kHz).
> **Không đổi production/ONNX; không ghi đè `data/codelung`, cache cũ, runs cũ.**
> Nguồn **CC-BY-NC-4.0** (phi thương mại); 21,57 h gốc → lọc **19,89 h** (6.989 clip).
> Split 90/5/5: train **17,89 h** · val **1,014 h** · holdout **0,985 h**.
> MFA 6.989/6.989 TextGrid. Train small v2_slot5 60k từ đầu: **val mel 0,2634 · nét 0,7624**;
> **holdout 4,0 dB**; free-run 80 holdout **16,57 dB** (P2 zero-shot 28,31 dB); thanh **0,9743**
> (thật 0,9835); Vocos fine-tune 10k mel **0,1167** (pretrained 0,1432).
> Hồ sơ: `docs/handoff/NGUYEN_DATA.md`; báo cáo `docs/handoff/N0_agent2.md`.
> **Ngắt nghỉ**: mặc định model tự nghỉ (`pause_mode="model"`); nghỉ cố định chỉ khi
> `--fixed-pauses` / `pause_mode="fixed"` (mặc định tắt). Vocos fine-tune đã loại vì rè.
> **Nghe**: https://instant-weblogs-reductions-separated.trycloudflare.com/
> **Releases**: prod candidate nội bộ `n0-ngochuyen-prod-v1` · research
> `n0-ngochuyen-research-v1` — cả hai CC-BY-NC-4.0, **không production thương mại**;
> release audio test cũ đã xoá. Có ONNX FP32 + demo service
> **https://tts.vifast.org/** (VPS JP).
>
> **V18.52 (27/10/2026) — DỪNG — CHỜ NGƯỜI NGHE.** Không train, không đổi production, không ghi đè dữ liệu.
> **Tệp đặc tả**: `V1852_agent0.md` + `DECISIONS.md` mục V18.52. **Commit gốc**: `e915b11`.
> **Bộ dò đuôi không ASR**: hữu thanh ≥0,12 s + đỉnh RMS ≥−15 dB; 3 unit test pass.
> **A2**: 40 segment (20+/20−/10 sát ngưỡng) + 8 đối chứng; trang 48 mục, chờ CSV.
> **Link nghe**: https://centers-alt-higher-leaders.trycloudflare.com/
> **A3**: quét xong 20.837 segment, **chưa tổng hợp**; chỉ báo nếu A2 ĐẠT.
>
> **V18.51 (27/10/2026, lịch sử)** — A3 đuôi gap; A5 trượt auto; A4 chưa chạy. Báo cáo: `V1851_agent2.md`.
>
> **V18.44 (26/10/2026, lịch sử)** — ONNX đóng băng; UTMOS bị loại; A6 frame lạ; A5 xác nhận BAK.
> Test **2.547 pass / 23 skip**. Báo cáo: `V1844_agent2.md`.
>
> **V18.43 (26/10/2026, lịch sử)** — Vòng đo, không train, không đổi production.
> - **A3 TRƯỢT** (lý do duy nhất: p95 short 1,2188×); **A2 phép đo hỏng** (đối chứng âm seed UTMOS lệch 0,0729);
> - **A4 nguồn rè = acoustic** (Δac 0,2481; Δvoc −0,0214); **A6** bit-exact, fast 5,1 s;
> - **A1c** parity 12/12 với `ONNX-EXC-001`; test **2.570 passed**. Báo cáo: `V1843_agent2.md`.
>
> **V18.41 (23/10/2026, lịch sử)** — frontend OOV: ONNX cũ gọi `features_from_text` **không** `resolve_oov` ⇒ `John`/`XYZ` thành fallback trong khi PyTorch production đọc được. Đã sửa mặc định `resolve_oov=True` trong `runtime/onnx_engine.py`, thêm `tests/test_onnx_frontend.py` (9 test); valid **8/8 equal**, smoke **8/8 finite**, `...` báo lỗi đúng. Kết quả v18.40 giữ: acoustic 36/36, E2E 12/12, vocoder 11/12 với **ngoại lệ spectrum A0 chấp nhận có phạm vi** (`ONNX-EXC-001`). **Sẵn sàng chuyển ONNX trong phạm vi chunk mode đã kiểm tra**, config ứng viên `configs/onnx_candidate_v1841.json`; **chưa tự chuyển production**. Chi tiết: `V1841_agent2.md`, `artifacts/bench/v1841_frontend_oov/`.
> **V18.40 (23/10/2026)** — parity ONNX v1837: **acoustic 36/36**, frontend **12/12**, end-to-end chunk **12/12** (max 2,14e-04; RMSE 7,74e-06; RMS ratio ~1; clipping 0; cả hai runtime tất định). **Vocoder 11/12** — một input (`2b65WyiFC9k_0030__s03`) có spectrum max **0,02336** vượt tiêu chí tuyệt đối **0,02** tại bin (20,66); mean ~1e-05, waveform max 3,23e-04 và end-to-end vẫn đạt. Provenance/mel hash khớp; acoustic 180/181 exact, vocoder 63/63 exact. **Chưa tuyên bố sẵn sàng chuyển ONNX; giữ P2 + PyTorch.** Không sửa runtime/tiêu chí sau kết quả. Chi tiết: `V1840_agent2.md`, `artifacts/bench/v1840_onnx_parity/`.
> **V18.39 (23/10/2026)** — audit UTMOSv2: `utmosv2` dùng **random crop + mixup bằng np.random không seed** ở cả prediction; cùng seed **exact**, khác seed mỗi file lệch trung bình **~0,28 điểm** (max 0,45–0,67). Chấm lại 36 WAV cũ bằng **5 seed [0..4]**: UTMOS P2 1,4899 · REC 1,4568 · legacy 1,5207 · fixed 1,4957; ΔUTMOS **fixed−legacy −0,0264 CI [−0,0554, +0,019]** (mất ý nghĩa so với 1 pass), **fixed−rec +0,0176 CI [−0,0003, +0,053]** (chỉ xu hướng), **legacy−P2 +0,0223 CI [+0,0045, +0,0461]** nhưng BAK không xác nhận. BAK/flat/HNR của v18.38 giữ; các ΔUTMOS của v18.38 **hạ mức**. CI bootstrap video **chưa gồm** bất định do giám khảo; seed range báo riêng. **Giữ P2, crop fixed là mặc định vì loại padding, không tuyên bố cải thiện chất lượng.** Chi tiết: `V1839_agent2.md`, `artifacts/bench/v1839_utmos_audit/`.
> **V18.38 (23/10/2026)** — probe crop D **3 nhánh** từ P2 EMA (300 D warm-up + 200 G update; REC 200 G): **không nhánh nào tốt hơn P2** trên bộ 36 câu dev. `gan_fixed` vs `gan_legacy`: ΔBAK +0,0041 CI95 [−0,0112, +0,0084] (không khác), ΔUTMOS −0,0507 (**1 pass chưa seed — xem v18.39**), ΔHNR +0,036 (fixed hơn), Δflat +0,0011 (fixed phẳng hơn = kém hơn). `gan_fixed` vs `rec`: BAK +0,0201, UTMOS +0,1064 (**1 pass chưa seed — xem v18.39**) nhưng **chưa hơn P2**. Crop cũ: 35/3.975 row (0,88%) và 31/500 bước có padding, 1.098 frame; crop fixed: 0. **Giữ P2, không mở training dài.** Chi tiết: `V1838_agent2.md`, `runs/v1838_crop_probe/report.json`.
> **V18.37 (23/10/2026)** — kiểm tra tính đúng pipeline, **không training, không đổi production**. Xác nhận bằng tensor: ONNX acoustic cũ = **P2 EMA** (180/181 tensor exact); ONNX vocoder cũ = **E4-C** (63/63 tensor exact, 0/63 pretrained) ⇒ **mismatch**, đã export bản sửa ở `artifacts/onnx/v1837/` (chưa dùng). Sửa text eval giữ dấu câu (`vifasttts/eval_text.py`); raw-join cũ chỉ còn là legacy. Trace 12 câu: legacy **0 gap**, bản có dấu câu **173 gap**; CLI/ONNX chunk dài hơn sentence mode (ghi rõ, không ép giống). Audit crop D: bản cũ có row 34 frame bị crop 64 ⇒ **33 frame padding**; đã sửa `sample_crops(lengths=...)`, test mới. Bộ split: val∩holdout = **9 video**, nhưng **0 clip cha/segment** ⇒ holdout là unseen-clip, không phải unseen-video. **Luật hiện hành chỉ còn BAK + UTMOS; CER đã bị loại, số cũ giữ trong lịch sử.** Chi tiết: `V1837_agent2.md`, JSON `artifacts/bench/v1837_*.json`.
> **V18.35 (23/10/2026)** — sàng lọc 4 checkpoint còn tồn tại (g1_1k, g2_1k, p2_4k, g2_2k) trên 110 câu/11 video: **không bản nào đạt luật** (trượt điều kiện BAK) ⇒ **giữ P2**, không đổi production, không training. `g1_1k`: UTMOS cải thiện, **BAK chưa xác định được chiều khác biệt**, chưa đạt mục tiêu cải thiện nền — không phải bản thắng, cũng chưa bị chứng minh kém toàn diện. Chi tiết: `A0_V18_GROUP1.md` §26.
> **V18.34 (23/10/2026)** — audit v18.33: sửa nhãn chiều (flat_V G1 thắng 88 %), **loại CER/WER khỏi luật** (macro/micro lệch; "sàn 0,188" là mẫu 8 câu khác tập), "speech frames" = **voiced frames**, UTMOS không đơn điệu từng câu với cắt. **Giữ P2** (BAK+UTMOS CI95 < 0, 0/12 video) nhưng **hạ mức kết luận**: "G1 bị giám khảo tự động đánh giá thấp hơn P2, đặc biệt DNSMOS BAK". Chi tiết: `A0_V18_GROUP1.md` §25.4–25.5, `artifacts/bench/v1834_audit.json`.
> **V18.33 (23/10/2026)** — đánh giá TỰ ĐỘNG 300 câu/12 video: **P2 tốt hơn G1** (BAK −0,40 CI[−0,46,−0,35]; UTMOS −0,10; CER +0,063; 0/12 video G1 hơn BAK) ⇒ **production rollback về P2**, G1 giữ làm thí nghiệm. Nhãn "đánh giá tự động", KHÔNG phải xác nhận tai. Chi tiết: `A0_V18_GROUP1.md` §25, `artifacts/bench/v1833_decision.json`.
> **V18.32 (23/10/2026)** — bộ nghe mù 36 câu (12 video) tại `artifacts/listen_small_filt/v1832_blind/` + chẩn đoán TF/free-run (`artifacts/bench/v1832_tf_free.json`); cơ chế nghịch lý nền **chưa xác định**; G1 vẫn CHƯA XÁC NHẬN TAI.
> **V18.31 (23/10/2026, lịch sử)** — nhánh khi đó là **rè nền / GAN acoustic**; báo cáo đầy đủ ở
> `docs/archive/handoff/A0_V18_GROUP1.md` §20–§23 (mục cũ V11 bên dưới là lịch sử, không còn hiệu lực).
> **Production acoustic (v18.37)**: **P2 EMA** `artifacts/listen_small_filt/adv_progress_p2/_ckpt/step_02000.pt`
> (SHA256 `44dd0da6…`; `model` == `ema` của `runs/adv_p2_20k/ckpt_2000.pt`) ·
> config `configs/small_codelung_v32.yaml` · metadata `configs/production_v1831.json` (đã cập nhật v18.37).
> **Vocoder production**: Vocos pretrained `artifacts/pretrained/vocos-mel-24khz/pytorch_model.bin`
> (SHA256 `97ec976a…`). **ONNX cũ không phải production**: vocoder ONNX cũ khớp E4-C, xem
> `artifacts/bench/v1837_provenance.json`; bản sửa mới ở `artifacts/onnx/v1837/`.
> **Trạng thái lịch sử V18.37**: DỪNG SAU V18.37 — không training; các kết luận BAK/UTMOS cũ bị giới hạn bởi
> punctuation/inference mode/EMA-live/vocoder mismatch; xem `V1837_agent2.md` §9.
> **Trang nghe cũ**: `/v1829_floor/`, `/v1830_gan/` (lịch sử; không phải production).

**Vòng hiện hành**: **N0** · **Tệp đặc tả**: `docs/handoff/NGUYEN_DATA.md` (dataset/recipe) ·
**Commit gốc của vòng**: `8a2b94f` · **Trạng thái**: **ĐÃ TRAIN XONG — CHỜ NGHE**; không đổi production.
> **V18.52 tạm dừng** (chờ CSV nghe); không xoá kết quả A1–A3.
> Các mục V11/V10 bên dưới là **lịch sử**, không còn hiệu lực cho quyết định production.
> Quy ước V11S.A3 vẫn dùng: HEAD là commit hồ sơ; đọc diff `<gốc>..HEAD`.
**Việc tiếp**: nghe 3 trang (A/B, new, new_vocos); nếu đạt, chốt checkpoint/Vocos. Dùng thương mại
phải xử lý license CC-BY-NC-4.0 trước.

> Agent 1 đọc vòng này theo thông tin ở đầu tệp (không cần hash gửi kèm): diff `0fa26e2..<commit cuối>`,
> đối chiếu `V1851_agent2.md`. Agent 1 **chỉ đọc, không ghi tệp** vào repo.
> Quy ước cũ: commit đầu vòng là tệp đặc tả; vòng này đặc tả nằm trong chat, không có `V1837_agent0.md`.

## 1. Mốc & hash ghim (V10.A3: ghim sha256 theo byte TRONG GIT — `git show HEAD:<tệp> | shasum -a 256`)
| Đối tượng | Hash | Ghi chú |
|---|---|---|
| manifest train fixtail | `965b4798…` (full trong `eval/README.md`) | Σgap/row 294,9 · phủ pause 71,4% |
| manifest val fixtail | `cdbbd659…` | Σgap/row 303,0 · phủ 74,0% |
| manifest val CŨ | `19b6e117…` | dùng cho CỔNG CỨNG (không đổi) |
| holdout CŨ (CER) | `3ca7c79b…` | clip-level 842 hàng |
| mốc `eval/baselines/base40k_old.json` | `2bc3ca93…` | val cũ — CỔNG CỨNG (pin theo byte git); rough 60 clip 0,3679 |
| mốc `base40k_fixtail.json` | `e29509d7…` | sinh lại (B7) + `length_ratio_speech/pause`; rough 60 clip 0,3679/0,3419; mel_z_fix 1,3311 · dB_fix 9,879 |
| `base40k_fixgap.json` | `cf770864…` — **KHÔNG DÙNG** | đã gỡ khỏi git: `artifacts/bench/legacy/` (V10.A5) |
| model thước `tone_ruler.pt` | không versioned | train lại: `tools/tone_ruler.py --train` |

## 2. Cổng A2 (tương đối so mốc cùng bản val)
- **CỨNG** (None = TRƯỢT): mel_l1_z(tf@cũ) ≤ mốc×1,01 · mel_db ≤ mốc+0,10 · rough(từ checkpoint@cũ) ≥ mốc−0,01 ·
  tone_C(@cũ) ≥ mốc−0,01 · CER(holdout cũ) ≤ mốc+0,03 · F0 NGÃ ≤ mốc+5¢ · syl_z(tf@fixtail) ≤ mốc×1,01 ·
  mel_gap(free@fixtail) ≤ mốc.
- **MỤC TIÊU**: pause_f1_all ≥ mốc+0,073 · gap_sum_mae_all ≤ mốc×0,714 ·
  length_ratio(free) theo V10.A9: |1 − lr| ≤ 0,5×|1 − mốc| (≥0,8833 & ≤1,1168) · gap_z(tf) ≤ mốc×0,85.
- **THEO DÕI (V10.A9)**: length_ratio_speech (mốc 0,9343) · length_ratio_pause (mốc 0,5332) @ val fixtail free-run.
- Kết luận bench: TỪ CHỐI / ĐẠT CỨNG–TRƯỢT MỤC TIÊU / ĐẠT CỨNG–MỤC TIÊU CHƯA ĐỦ SỐ / CHẤP NHẬN.

## 3. Hằng số & quyết định đang hiệu lực
- **C_TAIL = 67 frame** (trần lặng đuôi, chỉ đoạn cuối clip; cắt cả nhãn lẫn `frame_range[1]`) — §44.8.
- `--reset-val-state` + `INIT_RESUME/INIT_RESET_VAL_STATE` (watchdog chỉ dùng khi `OUT/last.pt` chưa có).
- sh25 **giữ toàn cục** (không gated) — đóng mục 5c.
- Batch 8 + `SameNBatchSampler`; patience 0 cho cosine dài; `max_steps = lr_decay_steps = 60000`.
- **V10.A7 (đã quyết bằng đo)**: NHÁNH NHIỄU — f0p/f0/f0_delta **+0,000%** giữa 3 manifest; mọi thành phần probe
  trong ±2σ của 500 bước cuối base ⇒ probe fixtail **ĐẠT**; tiêu chí probe ±5% → **±2σ**.
- **V10.A8**: history.csv ghi từng thành phần loss + tỉ phần pause (train & validate).
- **V10.A11**: A2 thật chạy khi đủ 6 điều kiện (không cần chờ Agent 0).

## 4. Việc đang chờ (theo mã vòng)

### 4.1 V18.52 — kết quả tạm
| Mã | Việc | Trạng thái |
|---|---|---|
| V1852.A1 | Bộ dò đuôi + 3 unit test | ✅ xong |
| V1852.A2 | 40 segment + 8 đối chứng, trang 48 mục | ⏳ **CHỜ CSV** |
| V1852.A3 | Quét toàn bộ **xong 20.837 segment**, chưa tổng hợp | ✅ scan — chờ A2 |
| V1852.A4 | Manifest loại bỏ (chỉ khi P0) | ⛔ chờ |
| — | Báo cáo `V1852_agent2.md` | ✅ commit hồ sơ |

### 4.2 V18.51 — kết quả (lịch sử)
| Mã | Việc | Trạng thái |
|---|---|---|
| V1851.A1 | Key cấy vs ASR | ✅ key khớp 0–0,15 s; invalid do không bấm burst |
| V1851.A2 | ASR 20 câu | ⚪ 18/20 tai–ASR đồng thuận; **0/18** dư cuối khớp segment kế |
| V1851.A3 | Code + offset | ✅ **9/20** dư cuối >0,1 s; offset không drift; code `gaps[-1]`/`frame_range` |
| V1851.A4 | Quét toàn bộ | ⏳ **CHƯA CHẠY** — 18,54 h audio, ước tính 3–4 h |
| V1851.A5 | Sửa 40 clip | ❌ **TRƯỢT TỰ ĐỘNG** — CER≤0,1 0/40; 16/40 mất âm cuối |
| — | Báo cáo `V1851_agent2.md` | ✅ commit hồ sơ |

### 4.2 V18.50 — kết quả (lịch sử)
| Mã | Việc | Trạng thái |
|---|---|---|
| V1850.A2 | Trang 86 mục + mismatch | ❌ **PHIÊN KHÔNG HỢP LỆ** — cấy 0/3; A 18/20 + B 20/20 mismatch |
| V1850.A3 | Tỉ lệ âm tiết bị bấm | ⛔ **KHÔNG KẾT LUẬN** |
| V1850.A4 | Bảng đặc trưng + creak | ⛔ **KHÔNG CHẤM** — phiên invalid |
| V1850.A5 | Hướng xử lý | ⏳ |
| — | Báo cáo `V1850_agent2.md` | ✅ commit hồ sơ |

### 4.2 V18.49 — kết quả (lịch sử)
| Mã | Việc | Trạng thái |
|---|---|---|
| V1849.A2 | Tái lập chunk 40 câu mới | ✅ **ĐẠT** — ΔBAK +0,1121; ΔCR +0,0841; `9e9df51` |
| V1849.A3 | Nghe mù 28 lượt | ⚪ **TAI KHÔNG PHÂN BIỆT** — PILOT 1 · CONTROL 0 · hòa 15; `9d917e7` |
| V1849.A4 | Kết hợp A2 + A3 | ⛔ **KHÔNG ĐỔI PRODUCTION** — chỉ A2 đạt |
| — | Báo cáo `V1849_agent2.md` | ✅ commit hồ sơ |

### 4.2 V18.48 — kết quả (lịch sử)
| Mã | Việc | Trạng thái |
|---|---|---|
| V1848.A1 | L_con + 5 unit test | ✅ `8a0ec8a` |
| V1848.A3 | Probe 100, chốt w=1,0338 (22,5 %) | ✅ `8f25e85` |
| V1848.A2 | PILOT + CONTROL 2.000 bước | ✅ `runs/v1848_{pilot,control}` |
| V1848.A4 | ΔBAK TF +0,0229; CI [−0,0198; 0,0600] | ❌ **KHÔNG KẾT LUẬN** — đóng băng; `338bd47` |
| V1848.A5 | Chunk +0,0537 [0,0143; 0,0939]; L1 +0,14 % | ⚪ **tín hiệu phụ** |
| V1848.A6 | Nghe mù/regression/ngân sách | ⛔ **không mở** |
| — | Báo cáo `V1848_agent2.md` | ✅ commit hồ sơ |

### 4.2 V18.47 — kết quả (lịch sử)
| Mã | Việc | Trạng thái |
|---|---|---|
| V1847.A2 | CR độ tương phản ≤4 kHz trên 40 câu dài + Spearman BAK | ✅ **ĐẠT** — CR 0,7067; ρ 0,4096; `da95507` |
| V1847.A3 | Pilot 2.000 bước | ⛔ **CHƯA CHẠY — chờ duyệt** |
| — | Báo cáo `V1847_agent2.md` | ✅ commit hồ sơ |

### 4.2 V18.46 — kết quả (lịch sử)
| Mã | Việc | Trạng thái |
|---|---|---|
| V1846.A2 | `C_lo` trên 40 câu dài | ❌ **ĐÓNG** — Δac 0,149456 < 0,15 (thiếu 0,000544); `7f181fa` |
| V1846.A4 | Cơ chế dải thấp 120 câu | ✅ **mượt tần số** — R_f −1,969; R_m −0,535; chỉ thông tin; `75399ea`, `67e2401` |
| V1846.A3 | Spearman độ dài | ❌ **không liên quan** — ρ 0,0788; `1b2462f` |
| V1846.A5 | C vs P chunk | ⚪ **không đủ bằng chứng** — +0,0328; CI [−0,0260; 0,0919]; `90ceda1` |
| V1846.A6 | Cổng train | ⛔ **ĐÓNG BĂNG CHẤT LƯỢNG ACOUSTIC** |
| — | Báo cáo `V1846_agent2.md` | ✅ commit hồ sơ |

### 4.2 V18.45 — kết quả (lịch sử)
| Mã | Việc | Trạng thái |
|---|---|---|
| V1845.A4 | Xác nhận `C_lo` trên 40 câu mới | ❌ **TRƯỢT** — Δac 0,0568 < 0,15; CI [−0,77; 2,90]; `9e03ed6` |
| V1845.A5 | Cửa sổ 5 theo GV → 80 câu | ❌ **KHÔNG phải over-smoothing** — tỉ lệ 0,789; `f5bd672`, `1fbd269` |
| V1845.A6 | F0 80 câu | ❌ **Không chỉ số liên quan** — ρ 0,021–0,088; `66f2ac2` |
| V1845.A7 | Cổng train: (2)(3)(4) | ⛔ **ĐÓNG** |
| — | Báo cáo `V1845_agent2.md` | ✅ commit hồ sơ |

### 4.2 V18.44 — kết quả (lịch sử)
| Mã | Việc | Trạng thái |
|---|---|---|
| V1844.A1 | ONNX đóng băng; 23 test ONNX skip có lý do | ✅ `dc4398a` |
| V1844.A1b | CV latency + sửa lý do trượt A3 | ✅ `3e1ae46` |
| V1844.A2 | Hợp đồng = chunk (chốt, không đo lại) | ✅ `3e1ae46` |
| V1844.A3 | Bootstrap hai tầng vẫn lệch; UTMOS bị loại; BAK tất định | ✅ `441b1de` |
| V1844.A4 | Đóng lead g1_1k | ✅ `3e1ae46` |
| V1844.A6 | Cấy ghép oracle — đối chứng đạt, tổng frame −0,85 ⇒ LẠ, dừng | ✅ `09cb383` |
| V1844.A5 | **XÁC NHẬN** — B thắng 16/16; phiên hợp lệ | ✅ `161a599` |
| V1844.A7 | Cổng V18.45: A5 đạt, A6 lạ, chưa duyệt ngân sách | ⛔ **CHƯA MỞ** |
| — | Báo cáo `V1844_agent2.md` | ✅ commit hồ sơ |

### 4.2 V18.43 — kết quả (lịch sử)
| Mã | Việc | Trạng thái |
|---|---|---|
| V1842.A7 | hồ sơ: TRANG_THAI + DECISIONS + EXCEPTIONS + archive + đóng mã V11 + phân loại 19 khoảng trống | ✅ `208b0c2` |
| V1842.A3 | benchmark ONNX vs PyTorch | ❌ **TRƯỢT** — short 1,2188×; cold 0,632; size 0,318; RSS 0,456; `2e28c55` |
| V1842.A6 | bit-exact → fast 3 câu (5,1 s) + full 20 câu (BAK/UTMOS) | ✅ `13c3ef6` |
| V1842.A1c | parity đọc `EXCEPTIONS.md`; 12/12 với ONNX-EXC-001; input khác vẫn FAIL | ✅ `72dc937`, `1be3cf6` |
| V1842.A2 | chunk vs sentence + đối chứng âm | ⛔ **PHÉP ĐO HỎNG** — seed UTMOS lệch 0,0729; giữ chunk; `49bb2e7` |
| V1842.A4 | chẩn đoán 3 tầng + C' (40 câu) | ✅ **acoustic** — Δac 0,2481; Δvoc −0,0214; `f78e042` |
| — | báo cáo `V1843_agent2.md` + cập nhật TRANG_THAI | ✅ commit hồ sơ |

### 4.2 Mã V11 còn treo — đã đóng (V1842b.1)
| Mã | Kết luận | Lý do |
|---|---|---|
| V11.B1 | **đóng** | đặc tả V11 đã thành lịch sử; vòng hiện hành dùng V1842 |
| V11.B2 | **đóng** | probe/σ đã hoàn tất ở V10.A7; không còn dùng để quyết định |
| V11.B3 | **đóng** | split hiện tại theo video; val_calib/val_lock không còn trong lộ trình |
| V11.B4 | **đóng** | `gate_threshold` đã có; `cer_prod` bị loại khỏi luật (v18.34/v18.37) |
| V11.B5 | **đóng** | UTMOSv2 đã dùng; audit seed ở v18.39 |
| V11.B6 | **đóng** | bench 45–60k đã được thay bằng base 40k/60k và các vòng V18 |
| V11.B7–B8, B10–B11 | **đóng** | cây quyết định/theo dõi/hồ sơ V11 đã bị V18 kế thừa |
| V11.B9 | **chuyển backlog chất lượng** | SẮC-tắc chưa làm; chỉ mở lại nếu A4 chỉ ra acoustic và có giả thuyết mới |
| V10.A10 | **gộp vào backlog V11.B9** | cùng nội dung SẮC-tắc |

### 4.3 Nhánh dữ liệu v3/v34 — đã đóng
- Đã thử coda/onset (v34) và các biến thể v3; **không tạo ứng viên thắng** so với mốc `b8_filt`/`v32 small`.
- Không đưa vào production; không chạy tiếp nếu không có giả thuyết mới cụ thể.
- Số liệu lịch sử: `docs/handoff/DATA_V3*.md`, `DATA_V34_CODA_21_10.md` (chỉ đọc, không dùng để quyết định).

### 4.4 19 khoảng trống hồ sơ (dossier v18.36 §7) — phân loại
| # | Khoảng trống | Nhãn | Xử lý |
|---|---|---|---|
| 1 | C5/V18 chưa có định nghĩa + 30 câu người thật | P1 | backlog; A5 là bước gần nhất |
| 2 | RAM inference, cold start, latency first-chunk | **P0** | **đã lấp** — A3: cold 0,632; RSS 0,456; p95 short 1,2188× |
| 3 | Ma trận 2×2 EMA/live cho P2/G1 | P1 | backlog; ghi nhận confound |
| 4 | Free-run có dấu câu | P1 | eval text giữ dấu câu từ v18.37; chưa chạy lại toàn bộ |
| 5 | Tỉ lệ crop D chứa padding | P1 | đã sửa `sample_crops(lengths=...)`; ảnh hưởng chưa đo |
| 6 | Frame-level vuv/phonation target | P1 | backlog kiến trúc |
| 7 | Residual waveform A−B/B−C/C−D | P1 | A4 đo BAK/flatness; residual để sau |
| 8 | ONNX `mel_hash` | **P0** | **đã lấp** (metadata v18.40 có `mel_hash`, khớp) |
| 9 | Quyết định vocoder production | **P0** | **đã lấp** (Vocos pretrained; `production_v1831.json`) |
| 10 | D checkpoint cho P2/G1/G2 | P1 | không resume D; ghi nhận |
| 11 | P2 `last.pt` + lý do dừng 7.600 | P1 | lịch sử, không cần cho quyết định |
| 12 | Số người nói / diarization đầy đủ | P1 | backlog dữ liệu |
| 13 | Tỉ lệ lỗi transcript so bản gõ tay | P1 | backlog dữ liệu |
| 14 | Đánh giá tai G1 | P1 | **A5 ở V18.44** |
| 15 | Loudness per-video sau v32 | P1 | backlog |
| 16 | flat_V/HNR cùng 300 câu cho A/B/C/D | P1 | A4 dùng 40 câu; mở rộng nếu cần |
| 17 | Script sinh `v1831_*` không có trong `tools/` | P1 | không tái lập được; ghi nhận |
| 18 | Không có log/commit lần chạy v1831 | P1 | lịch sử |
| 19 | P2/G1/G2 không log đủ thành phần loss | P1 | muốn có phải sửa logger; không làm khi đóng băng |

- **Không còn P0 mở**: #2 đã lấp bằng A3 (kết quả TRƯỢT); #8/#9 đã lấp trước đó.


## 4b. A2 đang chạy (số kiểm đầu)
- `runs/acoustic_v2_A2_fixtail` · log `artifacts/dataset_v2/train_v2_A2_fixtail.log` (watchdog resume).
- Dòng đầu history: `# X3 resume: resumed_from=runs/acoustic_v2_base/last.pt@40000` ✅ · cột thành phần loss ✅ · không NaN.
- Bước 41000: val 8,8516 (mel hữu thanh 0,5972 · nét 0,355) · **val_pause_gate 0,934 vs train_pause_gate 0,124 (7,5×)** · val_pause_frac 12,0% vs train 2,6%.
- Nhịp: ~0,43 s/bước · mps 13–15G · validate_every 1000 · save_every 5000 (checkpoint 45/50/55/60k cho B10).

## 5. Bẫy đã gặp (đừng lặp)
probe no-op (thiếu `--stop-at-step`) · lệnh thật train từ số 0 (thiếu INIT_RESUME) · sha256 ghim trước khi sửa tệp ·
JSON thô lọt lại vào `eval/baselines` · đổi bên đối chứng mà không báo trước · thước yếu che kết luận (§34.3→§36.4) ·
**pin sha256 theo byte ĐĨA** (máy khác checkout autocrlf → lệch) → từ V10.A3 ghim theo byte trong git + `.gitattributes -text` ·
**tài liệu ghi "đã sửa" khi code chưa sửa** (V09.A3) → chỉ ghi khi kèm tên test xanh.
