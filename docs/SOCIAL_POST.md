# Bài đăng giới thiệu N0 (Facebook)

> Ảnh: https://github.com/dvchd/ViFastTts/releases/download/n0-ngochuyen-research-v1/vifasttts_model_flow.png
> Repo: https://github.com/dvchd/ViFastTts · Demo: https://vifasttts.hoctuthien.com/

---

Mình vừa huấn luyện xong một model **TTS tiếng Việt nhỏ gọn**, và muốn khoe thành quả
cùng toàn bộ mã nguồn.

**6,1 triệu tham số acoustic. 24 kHz. Chạy ONNX trên CPU. Tự train được.**

Mục tiêu của mình không phải làm một model to nhất, mà là một pipeline **mở — nhỏ — đủ nhanh —
có thể tự huấn luyện lại**:

- **Nhỏ:** acoustic small chỉ **6,1M tham số**, không cần GPU khủng.
- **Nhanh:** xuất ONNX, chạy CPU; trang demo tạo âm thanh trực tiếp.
- **Tự train:** từ audio + transcript → MFA alignment → segment → cache → train → eval → ONNX.
  Toàn bộ code và tool nằm trong repo.
- **Dữ liệu sạch:** 21,57 h raw → **19,89 h** sau lọc; train **17,9 h**.
- **Train thật:** 60.000 bước, khoảng **5 h 46 phút** trên Mac mini M6.

Kết quả trên holdout:

- Mel L1: **4,0 dB**
- Free-run 80 câu: **16,57 dB**, độ dài gần như khớp (0,999), pause F1 **0,825**
- Thanh điệu: **0,9743** (trần audio thật 0,9835)
- A/B tai người: **24/24** câu chọn model mới so với P2 zero-shot

Luồng hoạt động:

**Văn bản → frontend âm tiết (âm đầu/đệm/chính/cuối + thanh + dấu câu) → acoustic small dự đoán mel
→ Vocos → WAV 24 kHz**

Model tự ngắt nghỉ theo dữ liệu; nghỉ cố định chỉ là tuỳ chọn (mặc định tắt).
Vocos dùng bản pretrained — mình đã thử fine-tune nhưng còn rè nên loại.

**Mã nguồn + hướng dẫn clone chạy thử:**
https://github.com/dvchd/ViFastTts

Chạy local:

```bash
git clone https://github.com/dvchd/ViFastTts.git
cd ViFastTts
./scripts/run_ngochuyen_demo.sh
```

**Demo online:** https://vifasttts.hoctuthien.com/

Lưu ý quan trọng: model mẫu **Ngọc Huyền** dùng dataset **CC BY-NC 4.0**, nên chỉ dùng cho
**nghiên cứu / phi thương mại**, không dùng giả giọng, lừa đảo hay production thương mại.
Code repo là MIT; quyền của dataset/giọng vẫn giữ nguyên.

Ai quan tâm TTS tiếng Việt, muốn thử, góp ý hoặc tự train giọng của mình — mình để hết
trong repo. Feedback rất welcome 🙌

#TTS #Vietnamese #OpenSource #SpeechSynthesis #ONNX #MachineLearning #ViFastTts

---

## Caption ngắn (nếu cần)

> TTS tiếng Việt **6,1M tham số**, chạy **ONNX CPU**, tự train được: 17,9 h dữ liệu sạch,
> 60k bước, ~5 h 46 trên Mac mini M6. Demo + mã nguồn:
> https://github.com/dvchd/ViFastTts · https://vifasttts.hoctuthien.com/
> Model mẫu dùng dataset CC BY-NC 4.0 — chỉ nghiên cứu/phi thương mại.
