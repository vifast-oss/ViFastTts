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

## V18.44 — Agent 0 (26/10/2026, sau report V18.43)

> Toàn bộ mục này là **ĐĂNG KÝ TRƯỚC**, có hiệu lực trước khi chạy bất kỳ phép đo nào của V18.44.
> Phạm vi: không train, không đổi production.

### A. Quyết định

| Mã | Quyết định | Lý do | Cổng đo | Điều kiện dừng |
|---|---|---|---|---|
| V1844.A1 | ONNX: **ĐÓNG BĂNG** theo luật A3 (người dùng xác nhận không có nhu cầu triển khai không PyTorch). Giữ code, artefact, hash. Test parity ONNX và phần ONNX trong fast test A6 đánh dấu **skip**, lý do "V1844.A1 đóng băng ONNX". `ONNX-EXC-001` chuyển trạng thái "đình chỉ cùng nhánh". Không xoá gì. | Luật A3 đăng ký trước: trượt thì đóng. Theo V1842b.6, acoustic sắp đổi thì cũng không được bật ONNX. Đóng băng lúc này không mất gì và đảo ngược được. | Suite pass với các test ONNX skip có lý do; không có test nào skip im lặng | Không |
| V1844.A1b | Sửa hồ sơ A3: lý do trượt **DUY NHẤT** là p95 câu ngắn **1,2188× > 1,2×**. Vế "ít nhất một trong" đã **ĐẠT** nhờ peak RSS **0,456× ≤ 0,6×**. Cold start và dung lượng **không phải** lý do trượt. Bổ sung hệ số biến thiên (CV) latency từng bucket từ dữ liệu **ĐÃ ĐO**, không đo lại. | Hồ sơ phải phản ánh đúng luật. CV là điều kiện "lạ" của A3 nhưng report chưa ghi. | CV có trong TRANG_THAI.md và V1843 report | CV câu ngắn > 15% thì A3 đổi nhãn từ "trượt" sang "lạ, không kết luận". Trạng thái ONNX vẫn đóng băng như A1, không đo lại. |
| V1844.A2 | Hợp đồng sản phẩm **CHỐT = chunk mode**. Không làm lại A2. Mọi đánh giá chất lượng cuối (nghe, BAK/UTMOS) của acoustic mới từ nay chạy ở **chunk mode**. Ghi chú: ΔBAK +0,099 của sentence có thể do khoảng lặng sạch được chèn vào, không phải bằng chứng ít rè. | Luật V1842b.3: trượt bất kỳ điều kiện nào thì là chunk. Phân xử chunk/sentence không còn ảnh hưởng quyết định nào khi ONNX đã đóng băng. | Không | Không |
| V1844.A3 | Hiệu chuẩn giám khảo, **không chấm thêm audio mới**. (a) Phân tích lại dữ liệu đối chứng âm A2 có sẵn bằng **bootstrap hai tầng**: lấy mẫu lại cả câu VÀ seed (seed là hiệu ứng ngẫu nhiên). (b) Chấm BAK **hai lần** trên 10 file bất kỳ để xác nhận BAK tất định. | Đối chứng âm A2 hỏng cho thấy CI cũ bỏ qua phương sai theo seed. Các kết luận UTMOS cũ có cùng cỡ với nhiễu này. | (a) **ĐẠT** nếu CI95 đối chứng âm theo bootstrap hai tầng **chứa 0** thì giao thức UTMOS mới = bootstrap hai tầng, **≥ 10 seed**, hai điều kiện dùng chung bộ seed, lần chấm nào cũng kèm đối chứng âm. **TRƯỢT** thì UTMOS bị loại khỏi luật quyết định, chỉ còn BAK + tai. (b) **ĐẠT** nếu hai lần chấm bằng nhau tuyệt đối. | (b) BAK lệch giữa hai lần thì là lạ, dừng, báo (A4 V18.43 cần xem lại). Dù (a) ra sao: đánh dấu g1_1k +0,096 và P2 4k −0,070 là **"chưa phân giải được"** trong hồ sơ. |
| V1844.A4 | **Đóng lead g1_1k.** | BAK(C') 3,7318 không tốt hơn BAK(C) 3,7419 ở cùng điều kiện teacher-forcing. UTMOS +0,096 nằm trong vùng nhiễu (xem A3). Không còn bằng chứng nào ủng hộ. | Không | Mở lại chỉ khi có giả thuyết mới cụ thể |
| V1844.A5 | Thay thiết kế nghe mù cũ (P2 vs g1, đã mất ý nghĩa) bằng nghe mù **KIỂM CHỨNG BAK**: tai có nghe thấy tầng C rè hơn tầng B không. 28 lượt: **16 lượt B vs C** (cùng câu, teacher-forcing nên cùng nhịp, chỉ khác phổ); **4 lượt đối chứng dương** (B vs B có thêm nhiễu trắng SNR 30 dB); **4 lượt đối chứng âm** (C vs C giống hệt); **4 lượt lặp** (4 cặp B/C đã nghe, đảo vị trí A/B). Chuẩn −16 LUFS, kiểm peak, vị trí và thứ tự ngẫu nhiên, ẩn tên. Câu hỏi duy nhất: "Bản nào ít rè nền hơn?" (A / B / không phân biệt). Chọn 16 câu có **\|BAK(B) − BAK(C)\| lớn nhất** trong bộ 40 câu A4; ghi danh sách câu vào DECISIONS.md trước khi dựng trang. | BAK chưa từng được kiểm bằng tai. Trước khi tiêu 7 giờ train để kéo BAK lên, phải biết thứ BAK đo có đúng là thứ người dùng gọi là "rè" không. | Phiên hợp lệ khi: đối chứng dương ≥ 3/4 chọn bản không thêm nhiễu; đối chứng âm ≥ 3/4 "không phân biệt"; lặp nhất quán ≥ 3/4. **XÁC NHẬN** khi B thắng, binomial một phía p < 0,05 trên các lượt không hòa (tối thiểu 10 lượt không hòa; 16 lượt thì cần ≥ 12). | Không hợp lệ: làm lại một phiên khác ngày. **KHÔNG XÁC NHẬN** (B không thắng, hoặc < 10 lượt không hòa): không train theo BAK, báo A0; khả năng tiếng rè người dùng nghe nằm ở chỗ khác (chunk/fade/loudness). C thắng rõ: lạ, dừng, báo. |
| V1844.A6 | Chẩn đoán vị trí rè bằng **cấy ghép oracle**, không train. Lấy mel C (P2, teacher-forcing), thay một phần bằng mel B (gốc), vocode rồi chấm BAK trên đúng 40 câu A4. Biến thể: `C_nuc` (thay frame nucleus), `C_onc` (thay onset + coda), `C_sil` (thay frame lặng), `C_hi` (thay bin mel > 4 kHz ở mọi frame), `C_lo` (thay bin ≤ 4 kHz). Đối chứng: `C_all` (thay toàn bộ) phải ra bằng B; `C_none` (không thay gì) phải ra bằng C. `Recovery(X) = (BAK(X) − BAK(C)) / Δac`. Thêm chỉ số phụ: tỉ số phương sai theo thời gian (GV) của C/A theo 3 dải (< 1 kHz, 1–4 kHz, > 4 kHz), chỉ tính frame hữu thanh. Nếu model hỗ trợ teacher-forcing F0 thì thêm `C_f0` (mel P2 với F0 gốc); không hỗ trợ thì ghi rõ, bỏ qua. | Δac cho biết rè ở acoustic nhưng không cho biết ở đâu. Nhiễu khoảng lặng B→C giảm 1,98 dB nhưng BAK lại xấu đi, nên rè nhiều khả năng nằm trong vùng có tiếng nói. Cấy ghép cho câu trả lời trực tiếp, tất định, chỉ tốn thời gian vocode. | Một thành phần là **CHÍNH** khi Recovery ≥ 0,5. Over-smoothing được hỗ trợ khi **GV ratio < 0,8** ở ít nhất một dải VÀ thành phần chính là dải tần (`C_hi` hoặc `C_lo`). Nhiều thành phần cùng ≥ 0,5 thì báo đủ. Không thành phần nào ≥ 0,5 thì báo "phân tán", kèm bảng đầy đủ. | Lạ, dừng, báo khi: `C_all` lệch BAK(B) > 0,02; `C_none` lệch BAK(C) > 0,02; hoặc tổng Recovery của các cặp bù nhau (`nuc + onc + sil`; `hi + lo`) > 1,5 hoặc < 0,5 (đường nối giữa các frame được ghép gây artefact). |
| V1844.A7 | Cổng mở V18.45 (vòng có train). Phải ĐỦ: (1) A5 XÁC NHẬN; (2) A6 chỉ ra ít nhất một thành phần chính; (3) người dùng duyệt ngân sách. Ngân sách theo bậc: probe 100 bước → pilot 2.000 bước (~15 phút) có cổng BAK teacher-forcing đặt trước → mới được chạy dài (trần 60.000 bước ≈ 7 giờ). Giả thuyết và kiến trúc cụ thể của V18.45 do A0 chốt **SAU** khi đọc A5 + A6, không chốt bây giờ. | Tránh lặp lại GAN/v3: train khi chưa biết đích. Ngân sách theo bậc giới hạn thiệt hại nếu giả thuyết sai. | Theo từng điều kiện | Thiếu bất kỳ điều kiện nào thì V18.45 không train |

### B. Việc giao Agent 2 (theo thứ tự)

1. Ghi V1844.* vào DECISIONS.md, cập nhật TRANG_THAI.md (ONNX đóng băng, hợp đồng = chunk, g1_1k đóng, sửa lý do trượt A3). Commit riêng.
2. A1: đánh dấu skip có lý do cho test ONNX; chạy suite, báo số pass/skip.
3. A1b: tính CV latency từ dữ liệu A3 có sẵn, ghi vào hồ sơ.
4. A3: bootstrap hai tầng trên dữ liệu A2 có sẵn + BAK chấm hai lần. Báo CI cũ và CI mới cạnh nhau.
5. A6: viết tool cấy ghép (dùng lại phần tầng C của A4). Chạy các đối chứng C_all/C_none TRƯỚC, đạt thì mới chạy các biến thể. Kiểm khả năng teacher-forcing F0. Đầu ra: bảng BAK + Recovery theo biến thể, bảng GV ratio theo dải, verdict theo luật A6.
6. A5: chọn 16 câu theo luật, ghi vào DECISIONS.md, dựng trang nghe (chạy `tools/serve_listen_demo.sh` hoặc trang mới), gửi link cho người dùng, chấm theo luật khi có CSV.
7. Report: đã xong / số liệu / verdict từng cổng / mục lạ / TỰ QUYẾT KHÁC ĐẶC TẢ / commit hash. Bước 6 có thể báo sau, tách khỏi phần còn lại nếu người dùng chưa nghe.

### C. Việc KHÔNG làm trong V18.44
- Không train, không probe train.
- Không làm gì thêm cho ONNX (không đo lại A3, không port sentence mode).
- Không làm lại A2.
- Không dùng UTMOS cho kết luận nào trước khi A3 (hiệu chuẩn) xong.
- Không đưa hậu xử lý mel (làm nét, GV) vào production, kể cả khi A6 cho kết quả tốt; chỉ được ghi lại làm ứng viên.
- Không đổi ngưỡng đã đăng ký sau khi thấy số.

### D. Rủi ro còn lại và điều kiện xem lại
- Cấy ghép mel có thể tạo artefact ở chỗ nối; đã có đối chứng tổng Recovery, nhưng biến thể `C_sil`/`C_nuc` nhạy nhất với lỗi này.
- Nghe mù chỉ có một người nghe nên kết luận chỉ đúng với tai người dùng.
- Nếu A5 không xác nhận, toàn bộ hướng "kéo BAK lên" phải xem lại; khi đó nguồn rè người dùng nghe có thể nằm ở đường chunk (fade, ghép, chuẩn loudness) chứ không ở acoustic.
- ONNX mở lại khi: người dùng nêu nhu cầu triển khai không PyTorch, hoặc sau khi acoustic mới chốt mà có lý do mới. Mở lại thì phải chạy parity và A3 lại từ đầu với hash mới.

### E. Giả định
- Người dùng không cần triển khai không PyTorch (người dùng xác nhận khi gửi tệp này).
- Mel 100 kênh phủ đến 12 kHz nên tách được ranh giới 4 kHz theo bin (Agent 2 ghi chỉ số bin thực tế).
- Nhãn slot onset/nucleus/coda/lặng có sẵn theo frame khi teacher-forcing (nếu không có, ghi rõ và chỉ chạy `C_hi`/`C_lo`).
- Dữ liệu UTMOS theo từng seed của A2 còn lưu (nếu không còn, A3(a) chấm lại đúng 30 câu chunk với 10 seed, chỉ cho đối chứng âm).
- Chi phí V18.44 dưới nửa ngày máy, chưa tính thời gian người dùng nghe (tin cậy thấp).

### V1844.A5 — 16 câu chọn TRƯỚC khi dựng trang nghe

Chọn 16 câu có `|BAK(B) − BAK(C)|` lớn nhất trong 40 câu A4 (B = Vocos mel gốc, C = Vocos mel P2 TF).
Danh sách dưới đây được ghi **trước** khi sinh audio/trang; seed thiết kế = `1844`.

| # | id | index A4 | BAK(B) | BAK(C) | \|diff\| |
|---:|---|---:|---:|---:|---:|
| 1 | `vEtfty4Cc6Y_0070__s01` | 31 | 3,9251 | 2,5022 | 1,4229 |
| 2 | `2b65WyiFC9k_0162__s02` | 3 | 4,0726 | 2,6695 | 1,4031 |
| 3 | `BD83pScFukQ_0376__s02` | 16 | 3,8826 | 2,4865 | 1,3961 |
| 4 | `4ITcvEa_Acc_0205__s00` | 8 | 4,1328 | 2,9664 | 1,1664 |
| 5 | `o8RjAmBtyZo_0194__s02` | 29 | 3,9536 | 2,9616 | 0,9920 |
| 6 | `vEtfty4Cc6Y_0200__s02` | 33 | 4,0905 | 3,3703 | 0,7202 |
| 7 | `z0zSgR_oie4_0165__s03` | 38 | 3,2799 | 2,7405 | 0,5394 |
| 8 | `BD83pScFukQ_0217__s00` | 13 | 3,9768 | 3,5586 | 0,4182 |
| 9 | `BD83pScFukQ_0016__s02` | 9 | 4,1636 | 3,7745 | 0,3891 |
| 10 | `2b65WyiFC9k_0236__s01` | 4 | 3,9442 | 3,6261 | 0,3181 |
| 11 | `z0zSgR_oie4_0048__s05` | 36 | 3,7194 | 4,0043 | 0,2849 |
| 12 | `EUNlJU1BuzE_0145__s03` | 24 | 3,2099 | 3,4934 | 0,2835 |
| 13 | `EUNlJU1BuzE_0069__s01` | 23 | 4,0257 | 3,7438 | 0,2819 |
| 14 | `EM_ObHWvd94_0131__s02` | 19 | 4,1872 | 3,9626 | 0,2246 |
| 15 | `EM_ObHWvd94_0076__s01` | 18 | 4,1184 | 3,8952 | 0,2232 |
| 16 | `4ITcvEa_Acc_0142__s01` | 7 | 4,0936 | 3,9004 | 0,1932 |

Thiết kế 28 lượt: 16 B-vs-C + 4 dương (B vs B+trắng SNR 30 dB) + 4 âm (C vs C) + 4 lặp
(4 cặp B/C đầu, đảo A/B). Chuẩn −16 LUFS; vị trí/thứ tự ngẫu nhiên seed 1844; ẩn tên.
Câu hỏi duy nhất: "Bản nào ít rè nền hơn?" (A / B / không phân biệt).

## V18.45 — Agent 0 (26/10/2026, sau V18.44 + A5)

> **ĐĂNG KÝ TRƯỚC**, hiệu lực trước mọi phép đo V18.45. Phạm vi: không train, không đổi production.

| Mã | Quyết định | Cổng / điều kiện dừng |
|---|---|---|
| V1845.A0 | Ghi nhận A5 V18.44: **XÁC NHẬN** (B 16/16, p=1,5e-05; dương 4/4, âm 4/4, lặp 4/4). BAK thành thước **ĐỊNH HƯỚNG chính** cho rè nền. Giới hạn: một người nghe, 16 câu có khoảng cách BAK lớn nhất; không suy rộng cho câu có hiệu BAK nhỏ; kết luận production vẫn cần nghe mù. | Không |
| V1845.A1 | Duyệt toàn bộ **TỰ QUYẾT KHÁC ĐẶC TẢ** của V18.44. | Không |
| V1845.A2 | **ĐÓNG họ cấy ghép theo frame** (`C_nuc`, `C_onc`, `C_sil`). **KHÔNG** thiết kế lại bằng overlap/crossfade. Kết quả frame V18.44 **không** dùng để kết luận vị trí rè. Lý do: model không TF F0 ⇒ mel P2 và mel gốc khác cao độ trong cùng frame; ghép frame tạo nhảy cao độ; crossfade trộn hai họa âm ⇒ đúp/phách. Tổng −0,85 và `C_onc` −0,72 khớp cơ chế này. | Không |
| V1845.A3 | Giữ họ cấy ghép **theo dải tần** (tổng `hi+lo` = 0,78 đã đạt). `C_lo` (Recovery gộp 0,97) là **GIẢ THUYẾT** đến khi qua A4. | Xem A4 |
| V1845.A4 | Xác nhận `C_lo` trên **40 câu held-out MỚI**, khác hẳn 40 câu A4 V18.43; có wav gốc, TF thời lượng, cùng pipeline A6. Chạy `C_none`, `C_all`, `C_lo`, `C_hi`. Recovery **GỘP**: `(mean BAK(X) − mean BAK(C)) / Δac` của bộ mới. CI95 bootstrap theo câu 10.000 lần, lấy lại tử và mẫu cùng mẫu câu. Không dùng tỉ số từng câu; báo thêm median hiệu `BAK(C_lo) − BAK(C)` theo câu. | **ĐẠT** khi: Δac mới ≥ 0,15; Recovery(`C_lo`) ≥ 0,5; cận dưới CI95 ≥ 0,3; Recovery(lo)+Recovery(hi) ∈ [0,5; 1,5]. Δac <0,15 ⇒ không xác nhận được, báo (không phải lạ). `C_all` lệch B >0,02 hoặc `C_none` lệch C >0,02 ⇒ lạ, dừng. Tổng lo+hi ngoài khoảng ⇒ lạ, dừng. Recovery(hi) ≥0,5 trong khi Recovery(lo) <0,5 ⇒ lạ, dừng, báo. |
| V1845.A5 | Tách cơ chế dải thấp: **độ mượt theo thời gian hay cao độ**. `C_lo_s`: dải ≤4 kHz lấy từ mel gốc nhưng **làm mượt trục thời gian** (trung bình trượt, cửa sổ lẻ) sao cho GV ratio dải <1 kHz và 1–4 kHz của mel gốc sau làm mượt khớp GV ratio của P2 (sai số ≤0,03). Dải >4 kHz giữ của C. Cửa sổ chỉ chỉnh theo GV, **không** theo BAK; ghi cửa sổ trước khi chấm BAK. Chạy 80 câu (40 cũ + 40 mới). | **Over-smoothing CHÍNH** khi Recovery(`C_lo_s`) ≤ 0,3 × Recovery(`C_lo`). **KHÔNG** phải khi ≥0,7×. Ở giữa: "hỗn hợp". Không có cửa sổ khớp GV ±0,03 ⇒ dùng gần nhất, đánh dấu "xấp xỉ", báo. Recovery(`C_lo_s`) > Recovery(`C_lo`)+0,1 ⇒ lạ, dừng. |
| V1845.A6 | Đo phụ về cao độ trên 80 câu, frame hữu thanh: RMSE F0 C vs A (cent), tỉ lệ sai hữu thanh/vô thanh, tỉ số độ lệch chuẩn F0 theo câu C/A. Spearman giữa `BAK(B)−BAK(C)` theo câu và từng chỉ số; bootstrap CI95. | Một chỉ số "liên quan" khi **ρ ≥ 0,4** và CI95 không chứa 0. Bộ trích F0 lỗi >10% câu ⇒ bỏ chỉ số đó, báo. |
| V1845.A7 | Cổng mở vòng có train (thay V1844.A7). Phải ĐỦ: (1) A5 V18.44 XÁC NHẬN (**đã đạt**); (2) V1845.A4 ĐẠT; (3) V1845.A5 "over-smoothing CHÍNH" hoặc "hỗn hợp", **hoặc** V1845.A6 có ≥1 chỉ số cao độ "liên quan"; (4) người dùng duyệt ngân sách. Ngân sách: probe 100 → pilot 2.000 có cổng BAK TF đặt trước → trần 60.000. Kiến trúc do A0 chốt sau A4–A6. | Thiếu bất kỳ điều kiện nào ⇒ không train. |

### V1845.A4 — 40 câu MỚI, chọn trước khi vocode

Nguồn: `data/codelung/v32/holdout_clean_v2_dur_seg_slot4.jsonl`; loại 40 câu A4 V18.43;
chọn **4 câu/video** (9 video) + 4 câu bổ sung từ video nhiều dòng, step đều trong từng video;
điều kiện có `frame_range`, có gap ≥3, audio tồn tại. Danh sách dưới đây ghi **trước** khi vocode/chấm BAK.
(Đã sửa danh sách nháp trước khi vocode vì bản nháp không khớp file chọn thực tế.)

| # | id | # | id |
|---:|---|---:|---|
| 1 | `2b65WyiFC9k_0004__s02` | 21 | `VeU_85bZlrY_0034__s00` |
| 2 | `2b65WyiFC9k_0069__s00` | 22 | `VeU_85bZlrY_0037__s00` |
| 3 | `2b65WyiFC9k_0154__s00` | 23 | `VeU_85bZlrY_0037__s04` |
| 4 | `2b65WyiFC9k_0237__s02` | 24 | `VeU_85bZlrY_0129__s01` |
| 5 | `4ITcvEa_Acc_0014__s00` | 25 | `o8RjAmBtyZo_0002__s00` |
| 6 | `4ITcvEa_Acc_0055__s01` | 26 | `o8RjAmBtyZo_0075__s02` |
| 7 | `4ITcvEa_Acc_0142__s00` | 27 | `o8RjAmBtyZo_0130__s01` |
| 8 | `4ITcvEa_Acc_0193__s02` | 28 | `o8RjAmBtyZo_0178__s01` |
| 9 | `BD83pScFukQ_0002__s01` | 29 | `vEtfty4Cc6Y_0005__s00` |
| 10 | `BD83pScFukQ_0097__s00` | 30 | `vEtfty4Cc6Y_0068__s00` |
| 11 | `BD83pScFukQ_0214__s00` | 31 | `vEtfty4Cc6Y_0162__s03` |
| 12 | `BD83pScFukQ_0315__s00` | 32 | `vEtfty4Cc6Y_0239__s04` |
| 13 | `EM_ObHWvd94_0002__s00` | 33 | `z0zSgR_oie4_0001__s00` |
| 14 | `EM_ObHWvd94_0085__s03` | 34 | `z0zSgR_oie4_0059__s01` |
| 15 | `EM_ObHWvd94_0177__s00` | 35 | `z0zSgR_oie4_0138__s04` |
| 16 | `EM_ObHWvd94_0259__s00` | 36 | `z0zSgR_oie4_0204__s00` |
| 17 | `EUNlJU1BuzE_0002__s00` | 37 | `BD83pScFukQ_0002__s02` |
| 18 | `EUNlJU1BuzE_0085__s03` | 38 | `vEtfty4Cc6Y_0005__s01` |
| 19 | `EUNlJU1BuzE_0173__s01` | 39 | `2b65WyiFC9k_0004__s03` |
| 20 | `EUNlJU1BuzE_0259__s02` | 40 | `z0zSgR_oie4_0001__s02` |

### V1845.B — Việc giao Agent 2
1. Ghi V1845.* + 40 câu mới; cập nhật TRANG_THAI; commit riêng.
2. A4: đối chứng `C_all`/`C_none` trước, đạt mới chạy `C_lo`/`C_hi`; báo BAK, Δac, Recovery gộp + CI95.
3. A5: chọn cửa sổ theo GV, **commit cửa sổ trước khi chấm BAK**; rồi chấm 80 câu.
4. A6: bảng F0 + Spearman + CI.
5. Report.

### V1845.C — Không làm
Không train/probe; không chạy lại/thiết kế lại cấy ghép frame; không chỉnh cửa sổ theo BAK;
không dùng UTMOS; không đưa hậu xử lý mel vào production; không động ONNX.

### V1845.A5 — cửa sổ làm mượt chốt TRƯỚC khi chấm BAK

- Chọn bằng GV only trên 80 câu (40 A4 V18.43 + 40 mới), **chưa chấm BAK**.
- Mục tiêu GV ratio (var C / var B, frame hữu thanh): `<1k` **0,8332**, `1–4k` **0,8656**.
- Cửa sổ trung bình trượt lẻ được chọn: **5**.
- Đạt được: `<1k` **0,8171**, `1–4k` **0,8519**; `max_abs_diff` **0,0161** ≤ 0,03 ⇒ không xấp xỉ.
- Dải >4 kHz giữ của C; chỉ dải ≤4 kHz lấy từ B (làm mượt) cho `C_lo_s`.
- `C_lo` (không làm mượt) dùng B thô ở dải ≤4 kHz.
- File: `artifacts/bench/v1845_a5/window.json`; mels: `artifacts/bench/v1845_a5/mels.npz`.
