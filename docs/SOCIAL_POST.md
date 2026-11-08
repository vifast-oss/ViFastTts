Mình vừa huấn luyện xong một model TTS tiếng Việt từ đầu, và muốn khoe thành quả cùng toàn bộ mã nguồn.

6,1 triệu tham số acoustic. 24 kHz. Chạy ONNX trên CPU. Tự train được.

Mục tiêu của mình không phải làm model to nhất, mà là một pipeline mở, nhỏ, đủ nhanh và có thể tự huấn luyện lại:

- Nhỏ: acoustic small chỉ 6,1M tham số, không cần GPU rời.
- Nhanh: RTF 0,045 khi chạy end-to-end bằng ONNX CPU trên VPS, tức khoảng 22 lần nhanh hơn thời gian thực. 5 câu, tổng 22,44 giây audio chỉ mất 1,01 giây xử lý.
- Tự train từ đầu: audio + transcript, lọc dữ liệu, MFA alignment, cắt segment, cache feature, train, đánh giá, export ONNX. Toàn bộ tool nằm trong repo.
- Dữ liệu sạch: 21,57 giờ raw, còn 19,89 giờ sau lọc; train 17,9 giờ.
- Train thật: 60.000 bước, khoảng 5 giờ 46 phút trên Mac mini M6.

Kết quả trên holdout:

- Mel L1: 4,0 dB
- Free-run 80 câu: 16,57 dB, độ dài gần khớp 0,999, pause F1 0,825
- Thanh điệu: 0,9743, trong khi trần audio thật là 0,9835
- A/B tai người: 24/24 câu chọn model mới so với P2 zero-shot

Luồng hoạt động:

Văn bản, frontend âm tiết (âm đầu, âm đệm, âm chính, âm cuối, thanh điệu và dấu câu), acoustic small dự đoán mel, Vocos, WAV 24 kHz.

Model tự ngắt nghỉ theo dữ liệu. Nghỉ cố định chỉ là tuỳ chọn và mặc định tắt. Vocos dùng bản pretrained, mình có thử fine-tune nhưng còn rè nên đã loại.

Có 2 luồng sử dụng rõ ràng:

1. Người dùng model: chỉ cần tải ONNX và chạy, không cần torch, không cần train.
2. Người train model: cài bộ train đầy đủ, chuẩn bị dữ liệu, MFA, cache, train, đánh giá và export ONNX.

Chạy local trên macOS hoặc Linux:

git clone https://github.com/dvchd/ViFastTts.git
cd ViFastTts
./scripts/run_ngochuyen_demo.sh

Chạy local trên Windows PowerShell:

git clone https://github.com/dvchd/ViFastTts.git
cd ViFastTts
powershell -ExecutionPolicy Bypass -File .\scripts\run_ngochuyen_demo.ps1

Demo online:
https://tts.vifast.org/

Toàn bộ tài nguyên:

- Mã nguồn: https://github.com/dvchd/ViFastTts
- Hugging Face model: https://huggingface.co/dvchd/vifasttts-ngochuyen-small
- Space nghe thử miễn phí: https://huggingface.co/spaces/dvchd/vifasttts-ngochuyen-demo
- Demo: https://tts.vifast.org/
- Release research: https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-research-v1
- Release prod candidate nội bộ: https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-prod-v1
- Hướng dẫn train lại: docs/TRAINING_N0.md trong repo
- Model card: docs/NGOC_HUYEN.md trong repo
- Ảnh sơ đồ: https://github.com/dvchd/ViFastTts/releases/download/n0-ngochuyen-research-v1/vifasttts_model_flow.png

Lưu ý: model mẫu Ngọc Huyền dùng dataset CC BY-NC 4.0, nên chỉ dùng cho nghiên cứu và phi thương mại, không dùng giả giọng, lừa đảo hoặc production thương mại. Code repo là MIT, quyền của dataset và giọng vẫn giữ nguyên.

Ai quan tâm TTS tiếng Việt, muốn thử, góp ý hoặc tự train giọng của mình thì mình để hết trong repo. Feedback rất welcome.

#TTS #Vietnamese #OpenSource #SpeechSynthesis #ONNX #MachineLearning #ViFastTts #HuggingFace
