# V18.42 / V18.42b — Agent 0: quyết định (nguyên văn)

> **Vòng quyết định, không train, không đổi production.** Ngày 26/10/2026.
> Tệp này lưu nguyên văn đặc tả Agent 0 do người dùng chuyển; bản sao quyết định
> trong `docs/handoff/DECISIONS.md` (chỉ ghi thêm, theo mã).
>
> - V18.42: 8 quyết định A1–A8, giao Agent 2 thực thi ở V18.43–V18.45.
> - V18.42b: chốt 4 điểm trước V18.43 + duyệt 2 mục Agent 2 tự quyết + 2 mục cho V18.44.
> - Mọi nội dung V18.42b là **đăng ký trước**, có hiệu lực trước khi chạy bất kỳ phép đo nào.

---

# V18.42: Agent 0, quyết định

Phạm vi: phiên quyết định, không train, không đổi production. Agent 2 thực thi ở V18.43 và V18.44.

## A. Quyết định

| Mã | Quyết định | Lý do | Cổng đo | Điều kiện dừng |
|---|---|---|---|---|
| V1842.A1 | ONNX: CHƯA DUYỆT chuyển production trong vòng này. Duyệt có điều kiện ở V18.44 nếu A2 (hợp đồng mode) đã chốt và A3 (benchmark) đạt. Production giữ P2 EMA + PyTorch Vocos. | Parity chunk đạt, nhưng chưa có số lợi ích, chưa chốt mode hợp đồng. Chuyển runtime khi chưa biết người dùng nghe mode nào là rủi ro không cần thiết. | A2 + A3 đạt | Benchmark trượt thì áp dụng A3 (đóng nhánh). Hash ONNX khác lúc parity thì dừng, báo. |
| V1842.A1b | Khi ONNX lên production: mặc định chunk mode (hoặc sentence nếu A2 chọn sentence và đã port). Fallback sang PyTorch CHỈ khi lỗi nạp model/exception, có log WARN ghi lý do + bộ đếm, không fallback im lặng, không fallback vì chất lượng. Người theo dõi: bộ test parity chạy trong test suite mỗi vòng + Agent 2 báo trong report. | Fallback im lặng che lỗi. Chunk parity đã chứng minh hai đường tương đương nên fallback không đổi trải nghiệm. | Test: ép lỗi nạp ONNX thì có log WARN + output PyTorch | Fallback xảy ra ngoài lỗi nạp thì dừng, báo. |
| V1842.A1c | Ngoại lệ outlier ghi thành hồ sơ ONNX-EXC-001 trong EXCEPTIONS.md. Phạm vi: chỉ input `2b65WyiFC9k_0030__s03`, chỉ tầng phổ vocoder (real/imag), chỉ chunk mode, chỉ CPU EP, chỉ đúng hash model ONNX + phiên bản onnxruntime hiện tại. Ghi số: max 0,02336 / ngưỡng 0,02 / mean ~1e-05 / waveform max 3,23e-04 / E2E 9,16e-05 / clipping 0. Ngoại lệ HẾT HIỆU LỰC khi đổi hash model, đổi phiên bản ORT, đổi EP hoặc đổi mode. Test parity đọc danh sách ngoại lệ, không đổi ngưỡng chung. | Để audit sau không coi là bug mới và không biến thành "pass toàn bộ". | Test parity pass với ngoại lệ có định danh; input khác vượt 0,02 vẫn FAIL | Một input thứ hai vượt ngưỡng thì không thêm ngoại lệ, dừng, báo. |
| V1842.A2 | Hợp đồng sản phẩm: TẠM THỜI là chunk mode (mặc định CLI hiện hành). Chốt cuối bằng phép đo chunk vs sentence ở V18.43. Nếu sentence tốt hơn có ý nghĩa thì hợp đồng = sentence, ONNX phải dùng sentence qua MỘT module xử lý câu dùng chung cho hai runtime (tách câu, chèn khoảng lặng theo dấu câu, trim), không viết lại hai lần, rồi chạy lại parity cho sentence. Nếu không khác có ý nghĩa thì hợp đồng = chunk, sentence chỉ là công cụ PyTorch, và mọi kết luận chất lượng từ nay đo ở chunk. | Kết luận chất lượng cũ đo ở sentence nhưng người dùng nhận chunk. Cần số để biết khoảng cách này có đáng kể không. | 30 câu có dấu phẩy/chấm giữa câu, P2 PyTorch, hai mode, chuẩn −16 LUFS. BAK + UTMOS 5 seed, bootstrap ghép cặp 10.000 lần. Sentence "tốt hơn" khi CI95 của ΔUTMOS (sentence − chunk) > 0 VÀ CI95 của ΔBAK không nằm hoàn toàn dưới 0. | Lạ: đối chứng âm (cùng audio chunk, hai bộ seed UTMOS khác nhau) có CI95 không chứa 0 thì phép đo hỏng, dừng, báo. |
| V1842.A3 | Benchmark ONNX vs PyTorch, cùng đặt trước ngưỡng. Máy M6, CPU, 2 thread (torch set_num_threads=2; ORT intra_op=2). Câu ngắn (~8 âm tiết), vừa (~40), dài (~250, đoạn văn), mỗi loại 5 câu, chunk mode. Warmup 3, đo 20 lần. Chỉ số: cold start (từ khởi động tiến trình đến khi ghi xong wav, câu ngắn, 5 lần), latency p50/p95, RTF, peak RSS, dung lượng môi trường cài đặt tối thiểu, số dependency. Báo thêm PyTorch MPS làm tham chiếu (không dùng để quyết định). | Lý do tồn tại của ONNX là nhẹ hơn, nên phải có số. | ĐẠT khi: latency p95 ONNX ≤ 1,2× PyTorch ở mọi loại câu VÀ ít nhất một trong: cold start ≤ 0,5×; peak RSS ≤ 0,6×; dung lượng gói ≤ 0,3×. | Trượt: đóng nhánh ONNX (đóng băng artefact + hash, giữ test parity ở trạng thái skip có ghi lý do, bỏ khỏi lộ trình) trừ khi người dùng nêu nhu cầu triển khai không PyTorch. Lạ: hệ số biến thiên latency lặp lại > 15%, hoặc ONNX nhanh hơn > 10×, hoặc output ONNX khác hash parity thì dừng, báo. |
| V1842.A4 | Chất lượng: ĐÓNG BĂNG training, MỞ vòng CHẨN ĐOÁN không train để tách nguồn rè. Ba tầng trên 40 câu held-out có ghi âm gốc: A = wav gốc; B = Vocos(mel trích từ wav gốc); C = Vocos(mel P2), dùng thời lượng gốc (teacher-forcing) nếu model hỗ trợ, nếu không thì dùng thời lượng dự đoán và ghi chú. Thêm C' = g1_1k cùng cách. Tất cả chuẩn −16 LUFS. Đo: BAK, mức nhiễu trong khoảng lặng (dB RMS), spectral flatness 2–8 kHz ở frame hữu thanh. | Đây là phép đo rẻ nhất để biết rè do dữ liệu, vocoder hay acoustic. Thiếu nó thì mọi vòng train tiếp theo đều là đoán. | Δvoc = BAK(A) − BAK(B); Δac = BAK(B) − BAK(C). Vocoder là nguồn chính nếu Δvoc ≥ 0,15 và Δvoc ≥ 2×Δac. Acoustic là nguồn chính nếu Δac ≥ 0,15 và Δac ≥ 2×Δvoc. Cả hai nếu cả hai ≥ 0,15 mà không bên nào gấp đôi bên kia. Dữ liệu nếu cả hai < 0,15 và BAK(A) < 3,8. | Lạ: BAK(B) > BAK(A) + 0,1 hoặc BAK(C) > BAK(B) + 0,1 (thứ tự không đơn điệu), hoặc không rơi vào nhánh nào, thì dừng, báo kèm số từng câu. |
| V1842.A5 | Nghe mù có đối chứng (V18.44, sau A2), làm ở mode hợp đồng. 28 lượt: 16 lượt P2 vs g1_1k; 4 lượt đối chứng dương (wav gốc vs P2); 4 lượt đối chứng âm (P2 vs P2 giống hệt); 4 lượt lặp (lặp 4 cặp P2/G1 đã nghe, đảo vị trí A/B). Chuẩn −16 LUFS, kiểm peak, vị trí A/B ngẫu nhiên, thứ tự ngẫu nhiên, ẩn tên. Câu hỏi DUY NHẤT: "Bản nào ít rè nền hơn?" (A / B / không phân biệt). Trang HTML qua link tunnel như các lần trước, xuất CSV. | Ưu tiên người dùng là giảm rè nền. BAK/UTMOS không thay được tai. Lần trước không kết luận được vì không có đối chứng và không có luật đặt trước. | Phiên hợp lệ khi: đối chứng dương ≥ 3/4 chọn wav gốc; đối chứng âm ≥ 3/4 "không phân biệt"; lặp nhất quán ≥ 3/4. G1 thắng khi binomial một phía p < 0,05 trên các lượt không hòa (tối thiểu 10 lượt không hòa; với 16 lượt không hòa cần ≥ 12). | Phiên không hợp lệ: không kết luận, báo, làm lại một phiên khác ngày. G1 thắng: G1 thành ứng viên production ở vòng sau (cần thêm parity + regression). P2 thắng hoặc không đủ lượt: đóng "lead" G1, giữ P2. |
| V1842.A6 | Chốt chống tái phát: golden set 20 câu (OOV, số, viết tắt, dấu câu, câu dài). Lưu hash mel + wav cho từng runtime × mode, và baseline BAK/UTMOS (5 seed). Test FAIL khi hash đổi mà không có commit cập nhật baseline kèm mã quyết định. | Tất định nên dùng hash được. Chặn việc tệ đi âm thầm trong lúc đóng băng. | Test mới chạy trong suite; cố tình đổi 1 trọng số thì test FAIL | Hash không ổn định giữa 2 lần chạy liên tiếp thì dừng, báo (vi phạm tính tất định). |
| V1842.A7 | Hồ sơ: dọn TỐI THIỂU ngay V18.43, trước mọi thay đổi production. Nguồn sự thật duy nhất: STATUS.md (trạng thái hiện hành) + DECISIONS.md (nhật ký quyết định chỉ ghi thêm, theo mã) + EXCEPTIONS.md. Tài liệu cũ (gồm tổng quan 13/10) chuyển vào docs/archive/ với dòng đầu "LỊCH SỬ, không phải trạng thái hiện hành, xem STATUS.md". Từng mã V11 còn treo được đánh dấu: đóng / chuyển sang mã mới / bỏ, kèm 1 dòng lý do. Nhánh dữ liệu v3 ghi vào STATUS.md là "đã thử, không thắng, đóng". 19 khoảng trống: gắn nhãn P0 (ảnh hưởng vận hành/rollback, lấp ngay) hoặc P1 (backlog). Đầu STATUS.md có mục 5 dòng cho người không kỹ thuật, không tách trang riêng để tránh lệch nội dung. | Ngoại lệ A1c và hợp đồng A2 cần chỗ ghi đáng tin. Dọn nhỏ thì rẻ, dọn toàn bộ thì không đáng lúc này. | STATUS.md tồn tại; không còn mã V11 treo; mọi P0 đã lấp; grep tài liệu ngoài archive không còn trạng thái mâu thuẫn với STATUS.md | Số P0 > 5 thì chỉ lấp phần rollback/vận hành, báo phần còn lại. |
| V1842.A8 | Thứ tự ưu tiên: V18.43 chạy song song các phép đo rẻ (A2, A3, A4, A6, A7). V18.44: nghe mù A5 + quyết định ONNX. V18.45: vòng chất lượng có train, CHỈ mở theo kết quả A4. Chất lượng là mục tiêu chính, ONNX là việc đóng gói cần kết thúc gọn. | Rè nền là vấn đề lớn nhất với người dùng. ONNX gần xong, chỉ thiếu số. Train trước khi biết nguồn rè là lặp lại GAN/v3. | Theo từng mã | Theo từng mã |

## B. Việc giao Agent 2 (theo thứ tự)

### V18.43 (không train, không đổi production)
1. A7: tạo STATUS.md, DECISIONS.md (ghi A1 đến A8), EXCEPTIONS.md (ONNX-EXC-001), chuyển tài liệu cũ vào archive, xử lý mã V11, phân loại 19 khoảng trống. Commit riêng.
2. A6: golden set + test hash + baseline. Commit riêng. Chạy toàn bộ suite, báo số test.
3. A1c: sửa test parity đọc EXCEPTIONS.md; chứng minh input khác vượt 0,02 vẫn FAIL.
4. A3: benchmark. Đầu ra: bảng chỉ số × runtime × loại câu, kèm verdict ĐẠT/TRƯỢT theo ngưỡng A3, kèm cấu hình máy/phiên bản.
5. A2: đo chunk vs sentence + đối chứng âm. Đầu ra: ΔUTMOS, ΔBAK, CI95, verdict.
6. A4: chẩn đoán ba tầng (+ C'). Đầu ra: bảng BAK/mức nhiễu lặng/flatness theo tầng, Δvoc, Δac, nhánh kết luận, 5 câu ví dụ A/B/C để người dùng nghe tham khảo (không dùng để quyết định).
7. Báo cáo theo thứ tự: đã xong / số liệu / verdict từng cổng / mục lạ (nếu có) / commit hash.

### V18.44 (sau khi A0 duyệt report V18.43)
8. A5: dựng trang nghe mù, gửi link, chấm theo luật A5.
9. Nếu A2 chọn sentence: viết module câu dùng chung + parity sentence trên ONNX (đặt trước cùng ngưỡng như chunk).
10. Nếu A3 ĐẠT và parity mode hợp đồng ĐẠT: chuẩn bị bật ONNX theo A1b (bật thật cần A0 duyệt ở report).

## C. Việc KHÔNG làm trong V18.43 đến V18.45
- Không train bất kỳ thứ gì trước khi có kết quả A4 (gồm GAN, dữ liệu v3/v34, chạy tiếp P2 4k/6k).
- Không đổi ngưỡng parity chung; không thêm ngoại lệ thứ hai.
- Không dùng CER/WER hay L1 mel làm tiêu chí quyết định.
- Không fine-tune Vocos, không thay decoder (flow-matching) cho đến khi A4 chỉ ra nguồn VÀ người dùng duyệt riêng.
- Không coi BAK/UTMOS là bằng chứng tai; không tuyên bố "tốt hơn" khi chưa qua cổng đặt trước.
- Không bật ONNX production trong V18.43.

## D. Rủi ro còn lại và điều kiện xem lại
- Ngưỡng 0,15 BAK và 3,8 trong A4 là lựa chọn của A0, chưa hiệu chỉnh. Nếu kết quả nằm sát ngưỡng (±0,03) thì coi là "lạ", báo lại để A0 quyết.
- Mâu thuẫn P2 2k (UTMOS cao hơn) vs P2 4k/6k (độ trôi cao độ gần giọng thật hơn) chưa giải. Xem lại ở V18.45 nếu A4 chỉ ra acoustic là nguồn chính.
- Nghe mù chỉ có một người nghe nên kết luận chỉ đúng với tai người dùng, không suy rộng.
- Nếu A4 kết luận "dữ liệu", vòng V18.45 sẽ là lọc/làm sạch dữ liệu + train lại, chi phí cao (60.000 bước ≈ 7 giờ). Cần người dùng duyệt ngân sách trước.
- Nếu A4 kết luận "vocoder", phương án hợp lý nhất là fine-tune Vocos theo kiểu GTA, nhưng người dùng từng không muốn fine-tune vocoder. Cần người dùng quyết.
- Xem lại A1 khi: A3 xong, A2 xong, hoặc acoustic production đổi (ngoại lệ hết hiệu lực, chạy lại parity).

## E. Giả định
- Không có yêu cầu triển khai bắt buộc phải bỏ PyTorch (tin cậy trung bình). Nếu có, A3 trượt vẫn không đóng nhánh ONNX.
- DNSMOS BAK tất định khi chấm cùng file (tin cậy trung bình). Nếu không, chấm 5 lần như UTMOS.
- Acoustic hỗ trợ teacher-forcing thời lượng (không rõ). Nếu không, C dùng thời lượng dự đoán và Δac gồm cả sai khác nhịp.
- Bộ held-out có đủ 40 câu có wav gốc sạch nhãn (tin cậy cao).
- Chi phí V18.43 ước tính dưới nửa ngày máy, phần lớn là chấm UTMOS 5 seed (tin cậy thấp, Agent 2 báo số thật).
- CPU 2 thread trên M6 phản ánh cách dùng thật (tin cậy trung bình).

---

# V18.42b: Agent 0 chốt 4 điểm trước V18.43

Trả lời report "4 điểm cần chốt". Toàn bộ nội dung dưới đây là ĐĂNG KÝ TRƯỚC, có hiệu lực trước khi chạy bất kỳ phép đo nào của V18.43. Ghi nguyên văn vào DECISIONS.md với mã V1842b.*.

## Chốt 4 điểm

### V1842b.1 (A7, nguồn sự thật): GIỮ TÊN CŨ
- Nguồn trạng thái duy nhất vẫn là `docs/handoff/TRANG_THAI.md`. Đổi tiêu đề thành "TRẠNG THÁI (STATUS), nguồn sự thật duy nhất". KHÔNG tạo `STATUS.md`.
- Thêm `docs/handoff/DECISIONS.md` (chỉ ghi thêm, theo mã) và `docs/handoff/EXCEPTIONS.md`.
- Sửa AGENTS.md §8 trong CÙNG commit: TRANG_THAI.md = trạng thái hiện hành; DECISIONS.md = nhật ký quyết định; EXCEPTIONS.md = ngoại lệ có phạm vi. Hai tệp mới KHÔNG được ghi trạng thái hiện hành, chỉ được trỏ về TRANG_THAI.md.
- Mọi chỗ trong A7/A1c ghi "STATUS.md" thì hiểu là TRANG_THAI.md.
- Lý do: đổi tên làm gãy liên kết và quy ước đang chạy ổn, không thu được gì.

### V1842b.2 (A4): THÊM NHÁNH D, sửa định nghĩa "lạ"
Luật A4 đầy đủ (thay bản cũ):
- Vocoder: Δvoc ≥ 0,15 và Δvoc ≥ 2×Δac.
- Acoustic: Δac ≥ 0,15 và Δac ≥ 2×Δvoc.
- Cả hai: cả hai ≥ 0,15, không bên nào gấp đôi bên kia.
- Dữ liệu: cả hai < 0,15 và BAK(A) < 3,8.
- **D, không phát hiện nguồn trên bộ này**: cả hai < 0,15 và BAK(A) ≥ 3,8. Đây là kết quả hợp lệ, KHÔNG dừng.
- Nhánh còn thiếu: Δvoc ≥ 0,15 hoặc Δac ≥ 0,15, nhưng cả hai còn lại không rơi vào nhánh nào. Không có trường hợp nào như vậy nếu luật đúng; nếu xảy ra thì là lạ, dừng, báo.

Khi rơi vào D, dùng chỉ số phụ (đăng ký trước) để kiểm BAK có bị "điếc" không:
- Nhiễu khoảng lặng tăng ≥ 3 dB giữa A→B hoặc B→C (trung vị 40 câu, ghép cặp), hoặc
- Spectral flatness 2–8 kHz tăng ≥ 20% tương đối giữa A→B hoặc B→C.
Nếu chỉ số phụ chỉ ra một tầng thì báo "BAK không nhạy, chỉ số phụ chỉ ra tầng X", không tự mở train. Nếu chỉ số phụ cũng không chỉ ra gì thì báo D thuần. Ở cả hai trường hợp, A5 (nghe mù) trở thành bằng chứng chính, V18.45 không train cho đến khi A0 xem A5.

Vẫn giữ: kết quả trong ±0,03 quanh ngưỡng 0,15 hoặc 3,8 là "sát ngưỡng", báo để A0 quyết. Thứ tự không đơn điệu (BAK(B) > BAK(A)+0,1 hoặc BAK(C) > BAK(B)+0,1) vẫn là lạ, dừng.

Hai kiểm tra đầu vào bắt buộc trước khi tính A4 (không đạt thì dừng, báo):
1. Tầng B: mel trích từ wav gốc phải dùng ĐÚNG cấu hình mel mà Vocos pretrained mong đợi (sr, n_fft, hop, n_mels, fmin/fmax, log-scale). Ghi cấu hình vào report. Nếu cấu hình training acoustic khác cấu hình Vocos thì báo ngay, vì khi đó B không phải "trần của vocoder".
2. Tool tầng C mới viết: chạy ở chế độ KHÔNG teacher-forcing trên 3 câu, so với output CLI cùng mode; sai khác phải nằm trong ngưỡng parity E2E hiện hành. Không khớp thì tool có lỗi, dừng.

### V1842b.3 (A2): THÊM NON-INFERIORITY BAK
Luật A2 đầy đủ (thay bản cũ). Sentence thắng khi đạt ĐỦ ba điều kiện:
1. CI95 của ΔUTMOS (sentence − chunk) > 0.
2. ΔBAK ước lượng điểm ≥ −0,05.
3. Cận dưới CI95 của ΔBAK ≥ −0,10.
Trượt bất kỳ điều kiện nào thì hợp đồng = chunk.
Trường hợp đặc biệt: nếu ΔBAK có CI95 > 0 (sentence ít rè hơn rõ) nhưng ΔUTMOS không đạt (1) thì là lạ có ích, KHÔNG tự chọn, báo để A0 quyết (vì ưu tiên người dùng là giảm rè).
Đối chứng âm giữ nguyên.

### V1842b.4 (A6): TÁCH FAST/FULL, đồng ý
- Fast test (trong suite mặc định): 3 câu (1 OOV, 1 số/viết tắt, 1 câu nhiều dấu câu), CPU, chunk mode, hash mel + wav, cả PyTorch CPU và ONNX CPU, không UTMOS/BAK, tổng < 30 s.
- Full baseline: 20 câu, marker `slow`, chạy tay; lưu hash + BAK + UTMOS 5 seed.
- Trước khi biến hash thành cổng cứng, kiểm bit-exact theo 2 cách: chạy 2 lần trong cùng tiến trình VÀ 2 tiến trình riêng.
  - Bit-exact thì dùng hash.
  - Không bit-exact thì dùng tolerance: mel max abs ≤ 1e-5, wav max abs ≤ 1e-4. Ghi rõ runtime nào dùng tolerance.
  - PyTorch CPU 2 lần chạy cho kết quả khác nhau là vi phạm tất định, lạ, dừng, báo.
  - MPS: chỉ tolerance, không vào fast test.
- Baseline lưu kèm phiên bản torch, onnxruntime, numpy, OS. Khi phiên bản lệch, test FAIL với thông báo "môi trường đổi, cập nhật baseline kèm mã quyết định", không skip im lặng.

## Phê duyệt phần Agent 2 tự quyết

- **A3 chạy một mình trên máy yên tĩnh, trước các phép đo khác**: DUYỆT. Thêm: tắt mọi tiến trình nặng, ghi nhiệt độ/tải máy nếu đo được, và trước khi bấm giờ phải xác nhận hash output ONNX khớp với hash lúc parity.
- **Dung lượng môi trường = venv sạch**: DUYỆT. Đo `pip install .[onnx]` và `.[train]` (hoặc tương đương PyTorch inference), báo: dung lượng venv, số gói, và **có kéo torch vào hay không**. Nếu bản `.[onnx]` vẫn kéo torch (trực tiếp hoặc gián tiếp) thì là phát hiện quan trọng: báo ngay, đánh dấu tiêu chí dung lượng của A3 là TRƯỢT cho đến khi sửa.
- Ghi cả hai mục trên vào "TỰ QUYẾT KHÁC ĐẶC TẢ" kèm mã V1842b.

## Cho V18.44 (ghi nhận, chưa chặn)

- **V1842b.5 (A1b, hai bản cài)**: DUYỆT. Bản full (có torch) được fallback theo đúng A1b. Bản lite (không torch) KHÔNG fallback: lỗi nạp ONNX thì thoát mã khác 0, thông báo rõ ràng, không sinh audio.
- **V1842b.6 (lịch ONNX)**: chấp nhận V18.44 có thể chỉ ra quyết định. Thêm luật: nếu A4/A5 dẫn tới đổi acoustic ở V18.45 thì KHÔNG bật ONNX trước khi acoustic mới được chốt (tránh chạy parity hai lần, ngoại lệ ONNX-EXC-001 cũng hết hiệu lực khi đổi hash model). Nếu acoustic không đổi thì bật ONNX có thể làm ngay V18.45, độc lập với chất lượng.

## Thứ tự V18.43: DUYỆT như Agent 2 đề xuất
1. A7 (+ DECISIONS.md ghi V1842.* và V1842b.*), commit riêng.
2. A3 một mình.
3. A6 (bit-exact trước, rồi fast test + full baseline).
4. A1c.
5. A2.
6. A4 (2 kiểm tra đầu vào trước, rồi 3 tầng + C').
7. Report: đã xong / số liệu / verdict từng cổng / mục lạ / TỰ QUYẾT KHÁC ĐẶC TẢ / commit hash.

Bắt đầu V18.43.
