Mình vừa train xong một model TTS tiếng Việt từ đầu và muốn chia sẻ với mọi người.

Điểm chính: model acoustic chỉ 6,1 triệu tham số, chạy 24 kHz, xuất ONNX để chạy trên CPU. Mục tiêu không phải làm model lớn nhất, mà là một pipeline nhỏ, mở và có thể tự huấn luyện lại.

Mình làm toàn bộ từ đầu:

- Thu và lọc dữ liệu: 21,57 giờ raw, còn 19,89 giờ sạch.
- Chia train, validation, holdout theo hash văn bản.
- Chạy MFA alignment thật, cắt segment 3 đến 10 giây.
- Cache feature, train 60.000 bước với batch 8.
- Đánh giá trên holdout, sau đó export ONNX và dựng web demo.

Thời gian train thật: khoảng 5 giờ 46 phút trên Mac mini M6. Dữ liệu train là 17,9 giờ.

Kết quả trên holdout:

- Mel L1: 4,0 dB.
- Free-run 80 câu: 16,57 dB, độ dài gần khớp 0,999, pause F1 0,825.
- Thanh điệu: 0,9743, trong khi trần audio thật là 0,9835.
- A/B tai người: 24/24 câu chọn model mới so với P2 zero-shot.
- RTF thực tế của web demo trên VPS CPU: 0,045, tức khoảng 22 lần nhanh hơn thời gian thực. 5 câu, tổng 22,44 giây audio chỉ mất 1,01 giây xử lý.

Luồng hoạt động:

Văn bản, frontend âm tiết (âm đầu, âm đệm, âm chính, âm cuối, thanh điệu và dấu câu), acoustic small dự đoán mel, Vocos, WAV 24 kHz.

Model tự ngắt nghỉ theo dữ liệu. Nghỉ cố định chỉ là tuỳ chọn và mặc định tắt. Vocos dùng bản pretrained, mình có thử fine-tune nhưng còn rè nên đã loại.

Mình tách rõ 2 luồng:

1. Người dùng model: chỉ cần ONNX và chạy, không cần torch, không cần train.
2. Người train model: cài bộ train đầy đủ, chuẩn bị dữ liệu, MFA, cache, train, đánh giá và export ONNX.

Mã nguồn, model card, hướng dẫn train lại, bản ONNX, model trên kho model cộng đồng và Space nghe thử miễn phí mình đã để sẵn. Bài này mình không gắn link để đỡ bị hội nhóm ẩn bài. Ai cần link thì comment hoặc nhắn mình, mình gửi.

Lưu ý: model mẫu dùng dataset CC BY-NC 4.0, nên chỉ dùng cho nghiên cứu và phi thương mại, không dùng giả giọng, lừa đảo hoặc production thương mại. Code repo là MIT, quyền của dataset và giọng vẫn giữ nguyên.

Ai đang làm TTS tiếng Việt, muốn góp ý hoặc tự train giọng của mình, mình rất muốn trao đổi thêm.
