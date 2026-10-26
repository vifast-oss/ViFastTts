Mình vừa huấn luyện xong một model TTS tiếng Việt từ đầu, và muốn khoe thành quả cùng toàn bộ mã nguồn.

6,1 triệu tham số acoustic. 24 kHz. Chạy ONNX trên CPU. Tự train được.

Mục tiêu của mình không phải làm model to nhất, mà là một pipeline mở, nhỏ, đủ nhanh và có thể tự huấn luyện lại:

- Nhỏ: acoustic small chỉ 6,1M tham số, không cần GPU rời.
- Nhanh: xuất ONNX, chạy CPU, có web demo tạo âm thanh trực tiếp.
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

Mã nguồn và hướng dẫn clone chạy thử:
https://github.com/dvchd/ViFastTts

Chạy local:

git clone https://github.com/dvchd/ViFastTts.git
cd ViFastTts
./scripts/run_ngochuyen_demo.sh

Demo online:
https://vifasttts.hoctuthien.com/

Lưu ý: model mẫu Ngọc Huyền dùng dataset CC BY-NC 4.0, nên chỉ dùng cho nghiên cứu và phi thương mại, không dùng giả giọng, lừa đảo hoặc production thương mại. Code repo là MIT, quyền của dataset và giọng vẫn giữ nguyên.

Ai quan tâm TTS tiếng Việt, muốn thử, góp ý hoặc tự train giọng của mình thì mình để hết trong repo. Feedback rất welcome.

#TTS #Vietnamese #OpenSource #SpeechSynthesis #ONNX #MachineLearning #ViFastTts
