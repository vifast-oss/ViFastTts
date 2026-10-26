# DECISIONS — nhật ký quyết định (chỉ ghi thêm, theo mã)

> **Không phải trạng thái hiện hành.** Trạng thái duy nhất nằm ở
> `docs/handoff/TRANG_THAI.md`. Tệp này chỉ ghi quyết định đã chốt, theo mã,
> để audit về sau; không sửa mục cũ, chỉ thêm mục mới.
>
> - Quyết định của Agent 0: mã `V<NN>.A<k>` (trong vòng) hoặc `V<NN>b.<k>` (bổ sung).
> - Ngoại lệ có phạm vi: `docs/handoff/EXCEPTIONS.md`.
> - Đặc tả nguyên văn: `docs/handoff/V1842_agent0.md`.

---

## V18.42 — Agent 0 (26/10/2026)

Phạm vi: phiên quyết định, không train, không đổi production. Agent 2 thực thi V18.43–V18.45.

| Mã | Quyết định (tóm tắt có ràng buộc) | Cổng / điều kiện dừng |
|---|---|---|
| V1842.A1 | **Chưa duyệt** chuyển ONNX production trong V18.43. Chỉ duyệt có điều kiện ở V18.44 nếu A2 (hợp đồng mode) và A3 (benchmark) đạt. Production giữ P2 EMA + PyTorch Vocos. | A2 + A3 đạt. Benchmark trượt ⇒ đóng nhánh ONNX. Hash ONNX khác lúc parity ⇒ dừng, báo. |
| V1842.A1b | Khi ONNX lên production: mặc định mode hợp đồng (chunk, hoặc sentence nếu A2 chọn và đã port). Fallback PyTorch **chỉ** khi lỗi nạp model/exception; log WARN + bộ đếm; không fallback im lặng, không fallback vì chất lượng. | Test ép lỗi nạp ONNX phải có WARN + output PyTorch. Fallback ngoài lỗi nạp ⇒ dừng, báo. |
| V1842.A1c | Outlier `2b65WyiFC9k_0030__s03` thành hồ sơ **ONNX-EXC-001** trong `EXCEPTIONS.md`: chỉ input đó, chỉ phổ vocoder, chỉ chunk, chỉ CPU EP, chỉ đúng hash model + phiên bản ORT. Hết hiệu lực khi đổi hash/ORT/EP/mode. Test parity đọc danh sách ngoại lệ; không đổi ngưỡng chung. | Test pass với ngoại lệ có định danh; input khác vượt 0,02 vẫn FAIL. Ngoại lệ thứ hai ⇒ dừng, báo. |
| V1842.A2 | Hợp đồng sản phẩm **tạm thời = chunk mode**; chốt cuối bằng đo chunk vs sentence. Nếu sentence thắng: ONNX phải dùng **một module xử lý câu dùng chung** cho hai runtime, rồi chạy lại parity sentence. Nếu không khác có ý nghĩa: hợp đồng = chunk; sentence chỉ là công cụ PyTorch; kết luận chất lượng từ nay đo ở chunk. | 30 câu có dấu câu, P2 PyTorch, 2 mode, −16 LUFS, BAK + UTMOS 5 seed, bootstrap ghép cặp 10.000. Sentence thắng khi CI95 ΔUTMOS > 0 **và** ΔBAK không nằm hoàn toàn dưới 0 (sau V1842b.3: thêm non-inferiority). Đối chứng âm CI95 không chứa 0 ⇒ phép đo hỏng, dừng. |
| V1842.A3 | Benchmark ONNX vs PyTorch trên M6, CPU 2 thread, chunk mode; câu ngắn/vừa/dài, mỗi loại 5 câu; warmup 3, đo 20 lần. Đo cold start, latency p50/p95, RTF, peak RSS, dung lượng cài tối thiểu, số dependency; báo PyTorch MPS làm tham chiếu. | ĐẠT khi p95 ONNX ≤ 1,2× PyTorch ở mọi loại câu **và** ít nhất một: cold start ≤ 0,5×; peak RSS ≤ 0,6×; dung lượng ≤ 0,3×. Trượt ⇒ đóng nhánh ONNX (trừ khi có nhu cầu triển khai không PyTorch). CV latency > 15% hoặc ONNX nhanh > 10× hoặc output khác hash parity ⇒ dừng, báo. |
| V1842.A4 | **Đóng băng training**, mở vòng chẩn đoán không train để tách nguồn rè: A = wav gốc; B = Vocos(mel từ wav gốc); C = Vocos(mel P2) với thời lượng gốc (TF) nếu hỗ trợ; thêm C' = g1_1k. 40 câu held-out, chuẩn −16 LUFS. Đo BAK, nhiễu khoảng lặng (dB RMS), spectral flatness 2–8 kHz. | Δvoc = BAK(A) − BAK(B); Δac = BAK(B) − BAK(C). Vocoder nếu Δvoc ≥ 0,15 và ≥ 2×Δac; acoustic nếu Δac ≥ 0,15 và ≥ 2×Δvoc; cả hai nếu cả hai ≥ 0,15 và không bên nào gấp đôi; dữ liệu nếu cả hai < 0,15 và BAK(A) < 3,8; **D** nếu cả hai < 0,15 và BAK(A) ≥ 3,8 (hợp lệ, không dừng). Thứ tự không đơn điệu (B > A + 0,1 hoặc C > B + 0,1) ⇒ lạ, dừng. |
| V1842.A5 | Nghe mù có đối chứng ở mode hợp đồng (V18.44): 16 lượt P2 vs g1_1k; 4 đối chứng dương (wav gốc vs P2); 4 đối chứng âm (P2 vs P2); 4 lượt lặp đảo A/B. Chuẩn −16 LUFS, ẩn tên, ngẫu nhiên. Câu hỏi duy nhất: "Bản nào ít rè nền hơn?" | Phiên hợp lệ: dương ≥ 3/4 chọn wav gốc; âm ≥ 3/4 "không phân biệt"; lặp ≥ 3/4 nhất quán. G1 thắng khi binomial một phía p < 0,05, tối thiểu 10 lượt không hòa (16 lượt cần ≥ 12). Không hợp lệ ⇒ không kết luận, làm lại ngày khác. |
| V1842.A6 | Golden set 20 câu (OOV, số, viết tắt, dấu câu, câu dài), lưu hash mel + wav theo runtime × mode và baseline BAK/UTMOS 5 seed. Test FAIL khi hash đổi mà không có commit cập nhật baseline kèm mã quyết định. | Test mới chạy trong suite; cố tình đổi 1 trọng số ⇒ FAIL. Hash không ổn định giữa 2 lần chạy ⇒ dừng, báo. |
| V1842.A7 | Dọn hồ sơ tối thiểu ngay V18.43, trước mọi thay đổi production. Nguồn trạng thái duy nhất: `TRANG_THAI.md` (sau V1842b.1); thêm `DECISIONS.md` (chỉ ghi thêm) và `EXCEPTIONS.md`. Tài liệu cũ vào `docs/archive/` với dòng đầu "LỊCH SỬ...". Đánh dấu từng mã V11 còn treo; ghi nhánh dữ liệu v3 là đã đóng; phân loại 19 khoảng trống P0/P1. | `TRANG_THAI.md` tồn tại; không còn mã V11 treo; mọi P0 đã lấp; không còn tài liệu ngoài archive mâu thuẫn trạng thái. |
| V1842.A8 | Thứ tự: V18.43 đo song song các phép đo rẻ (A2, A3, A4, A6, A7); V18.44 nghe mù A5 + quyết định ONNX; V18.45 vòng chất lượng có train, chỉ mở theo A4. Chất lượng là mục tiêu chính; ONNX là việc đóng gói cần kết thúc gọn. | Theo từng mã. |

---

## V18.42b — Agent 0 chốt 4 điểm trước V18.43 (26/10/2026)

> Toàn bộ mục này là **ĐĂNG KÝ TRƯỚC**, có hiệu lực trước khi chạy bất kỳ phép đo nào của V18.43.

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
