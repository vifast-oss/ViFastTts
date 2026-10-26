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

## V18.46 — Agent 0 (26/10/2026, sau report V18.45)

> **ĐĂNG KÝ TRƯỚC**, hiệu lực trước mọi phép đo V18.46. Không train, không đổi production.
> **Luật mới (V1846.A0)**: commit đăng ký trước **không được amend/force-push**; muốn sửa phải thêm
> commit "sửa đăng ký" trước commit kết quả đầu tiên.

| Mã | Quyết định | Cổng / điều kiện dừng |
|---|---|---|
| V1846.A0 | Duyệt TỰ QUYẾT V18.45 (gồm sửa danh sách câu trước vocode). Từ nay: commit đăng ký trước **không amend/force-push**; sửa bằng commit mới "sửa đăng ký" trước commit kết quả đầu tiên. | `git log` trong report; không force-push. Vi phạm ⇒ kết quả vòng đó "không đăng ký hợp lệ". |
| V1846.A1 | `C_lo`: **KHÔNG ĐÓNG**, giữ "chưa xác nhận". V1845.A4 trượt vì Δac <0,15 (thiếu lực kiểm), không phải bị bác bỏ. Ghi rõ 0,97 trên bộ cũ chưa tái lập. | Xem A2 |
| V1846.A2 | Xác nhận `C_lo` trên **40 câu DÀI độc lập**: chưa dùng trong A4 V18.43/V18.45; mỗi câu **≥3 s và ≥12 âm tiết**; **tối đa 5 câu/video**; chỉ chọn theo độ dài + video, không xem BAK; ghi danh sách trước khi vocode. Giữ pipeline/cách tính/cổng V1845.A4. | **ĐẠT** khi Δac ≥0,15; Recovery(`C_lo`) ≥0,5; cận dưới CI95 ≥0,3; lo+hi ∈[0,5;1,5]. **Δac <0,15 ⇒ ĐÓNG `C_lo` và toàn bộ hướng "rè do acoustic dải thấp"; không thử bộ câu khác.** `C_all`/`C_none` lệch >0,02 ⇒ lạ, dừng. Thiếu câu đạt: tối thiểu 25, báo rõ. |
| V1846.A3 | Đo phụ độ dài trên **120 câu** (80 cũ + 40 dài): Spearman giữa `BAK(B)−BAK(C)` theo câu và thời lượng câu, bootstrap CI95. | "Liên quan" khi ρ ≥0,3 và CI95 không chứa 0. Chỉ giải thích, không phải cổng. |
| V1846.A4 | Tách cơ chế dải thấp trên 120 câu; chỉ dải ≤4 kHz đổi, >4 kHz giữ C. (a) `C_lo_f`: dải thấp lấy từ B nhưng **làm mượt trục tần số** (trung bình trượt qua bin, cửa sổ lẻ); cửa sổ chọn sao cho **độ tương phản phổ** của B sau mượt khớp C, sai số ≤5% tương đối. Độ tương phản = trung bình (max−min) log-mel trong cửa sổ 5 bin, chỉ frame hữu thanh. Chọn theo độ tương phản, **không theo BAK**; commit trước khi chấm. (b) `C_lo_m`: dải thấp lấy từ C nhưng cộng **độ lệch trung bình theo bin** `mean_t(B)−mean_t(C)` từng câu; chỉ sửa mức năng lượng cố định. | Gọi R = Recovery. Mượt tần số **CHÍNH** khi `R(C_lo_f) ≤ 0,3×R(C_lo)`. Lệch mức **CHÍNH** khi `R(C_lo_m) ≥ 0,7×R(C_lo)`. Cả hai cùng đạt ⇒ báo đủ. Không cái nào ⇒ "không xác định", nguồn còn lại là chi tiết phổ khác. `R(C_lo_f) > R(C_lo)+0,1` hoặc `R(C_lo_m) > R(C_lo)+0,1` ⇒ lạ, dừng. Không cửa sổ nào khớp 5% ⇒ dùng gần nhất, đánh dấu "xấp xỉ". |
| V1846.A5 | Kiểm đường sản phẩm trên 40 câu dài: so BAK của **C** (P2 TF, không qua chunk) với **P** (CLI chunk mode mặc định, thời lượng dự đoán, fade/ghép/loudness). Cả hai −16 LUFS. Báo `BAK(C)−BAK(P)` + CI95. | Đường chunk gây rè THÊM khi hiệu ≥0,10 và cận dưới CI95 >0. Hiệu ≤−0,10 (chunk sạch hơn TF) ⇒ lạ, báo. |
| V1846.A6 | Cổng mở train (thay V1845.A7). Đủ cả: (1) A2 ĐẠT; (2) A4 xác định ≥1 cơ chế CHÍNH; (3) duyệt ngân sách. Ngân sách: probe 100 → pilot 2.000 có cổng BAK TF → trần 60.000. Hướng train do A0 chọn theo cơ chế (mượt tần số ⇒ loss/discriminator độ tương phản phổ dải thấp; lệch mức ⇒ hiệu chỉnh mức/loss theo mức). Nếu A5 ĐẠT ⇒ mở thêm vòng sửa đường chunk, không train, độc lập cổng này. | Thiếu điều kiện nào ⇒ không train. Nếu A2 trượt và A5 không đạt ⇒ **ĐÓNG BĂNG chất lượng acoustic**, chỉ sửa regression, giữ P2. |

### V1846.A2 — 40 câu DÀI, chọn trước khi vocode

Nguồn holdout; loại 40 câu A4 V18.43 + 40 câu A4 V18.45; điều kiện ≥3 s, ≥12 âm tiết,
audio tồn tại, tối đa 5 câu/video; chọn 4 câu dài nhất mỗi video + 4 câu dài nhất còn lại.
Không xem BAK. Danh sách ghi **trước** khi vocode.

| # | id | giây | âm tiết | # | id | giây | âm tiết |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | `2b65WyiFC9k_0169__s02` | 10,50 | 43 | 21 | `VeU_85bZlrY_0126__s01` | 6,69 | 34 |
| 2 | `2b65WyiFC9k_0006__s00` | 10,47 | 47 | 22 | `VeU_85bZlrY_0034__s03` | 5,05 | 21 |
| 3 | `2b65WyiFC9k_0203__s00` | 10,25 | 48 | 23 | `VeU_85bZlrY_0034__s02` | 4,73 | 17 |
| 4 | `2b65WyiFC9k_0144__s00` | 10,23 | 46 | 24 | `VeU_85bZlrY_0037__s01` | 4,06 | 16 |
| 5 | `4ITcvEa_Acc_0125__s00` | 10,57 | 47 | 25 | `o8RjAmBtyZo_0075__s03` | 8,54 | 32 |
| 6 | `4ITcvEa_Acc_0174__s00` | 10,46 | 47 | 26 | `o8RjAmBtyZo_0178__s00` | 8,31 | 38 |
| 7 | `4ITcvEa_Acc_0196__s00` | 10,34 | 46 | 27 | `o8RjAmBtyZo_0174__s01` | 8,28 | 28 |
| 8 | `4ITcvEa_Acc_0057__s02` | 10,19 | 36 | 28 | `o8RjAmBtyZo_0136__s00` | 7,81 | 38 |
| 9 | `BD83pScFukQ_0203__s00` | 10,54 | 41 | 29 | `vEtfty4Cc6Y_0083__s01` | 10,24 | 43 |
| 10 | `BD83pScFukQ_0169__s00` | 10,13 | 49 | 30 | `vEtfty4Cc6Y_0016__s00` | 9,32 | 43 |
| 11 | `BD83pScFukQ_0322__s00` | 10,13 | 35 | 31 | `vEtfty4Cc6Y_0272__s01` | 9,16 | 32 |
| 12 | `BD83pScFukQ_0096__s01` | 10,10 | 47 | 32 | `vEtfty4Cc6Y_0017__s00` | 9,03 | 35 |
| 13 | `EM_ObHWvd94_0195__s00` | 10,34 | 45 | 33 | `z0zSgR_oie4_0231__s00` | 10,63 | 51 |
| 14 | `EM_ObHWvd94_0084__s00` | 10,17 | 48 | 34 | `z0zSgR_oie4_0122__s01` | 10,53 | 46 |
| 15 | `EM_ObHWvd94_0069__s00` | 10,12 | 49 | 35 | `z0zSgR_oie4_0269__s00` | 10,50 | 46 |
| 16 | `EM_ObHWvd94_0106__s00` | 10,03 | 44 | 36 | `z0zSgR_oie4_0043__s00` | 10,38 | 42 |
| 17 | `EUNlJU1BuzE_0239__s01` | 10,54 | 39 | 37 | `EUNlJU1BuzE_0189__s00` | 10,44 | 47 |
| 18 | `EUNlJU1BuzE_0156__s00` | 10,53 | 52 | 38 | `z0zSgR_oie4_0211__s01` | 10,35 | 46 |
| 19 | `EUNlJU1BuzE_0039__s00` | 10,46 | 49 | 39 | `2b65WyiFC9k_0185__s00` | 10,19 | 47 |
| 20 | `EUNlJU1BuzE_0067__s00` | 10,44 | 50 | 40 | `BD83pScFukQ_0184__s00` | 10,10 | 45 |

### V1846.B — Việc giao Agent 2
1. Ghi V1846.* + 40 câu dài bằng **commit mới**, không amend.
2. A2: đối chứng trước, rồi `C_lo`/`C_hi`; verdict.
3. A4: chọn cửa sổ `C_lo_f`, commit trước khi chấm BAK; rồi chấm `C_lo_f`/`C_lo_m` trên 120 câu.
4. A3 và A5.
5. Report kèm `git log --oneline` của vòng.

### V1846.C — Không làm
Không train/probe; không thử bộ câu khác cho `C_lo` ngoài bộ dài A2; không chọn cửa sổ theo BAK;
không UTMOS; không cấy ghép frame; không động ONNX; không đưa hậu xử lý mel vào production.

### V1846.A4 — cửa sổ `C_lo_f` chốt TRƯỚC khi chấm BAK

- 120 câu (80 cũ + 40 dài); độ tương phản phổ = trung bình (max−min) log-mel trong cửa sổ 5 bin,
  chỉ frame hữu thanh; dải ≤4 kHz (66 bin).
- Độ tương phản C mục tiêu: **1,054477**.
- Cửa sổ làm mượt trục tần số được chọn: **3**; đạt **0,972691**; sai số tương đối **0,077561**.
- Không cửa sổ nào đạt ≤5% ⇒ dùng gần nhất, đánh dấu **"xấp xỉ"** (đúng luật).
- Chọn **chỉ theo độ tương phản**, chưa chấm BAK. File: `artifacts/bench/v1846_a4_mechanism/window.json`.

## V18.47 — Agent 0 (26/10/2026, sau report V18.46)

> **ĐĂNG KÝ TRƯỚC**, hiệu lực trước mọi phép đo V18.47. Không đổi production.
> **Không amend/force-push**; mọi sửa đăng ký phải là commit mới trước commit kết quả đầu tiên.

| Mã | Quyết định | Cổng / điều kiện dừng |
|---|---|---|
| V1847.A0 | Chấp nhận V18.46: `C_lo` đóng theo luật, chất lượng acoustic **ĐÓNG BĂNG**, production giữ P2. Duyệt toàn bộ TỰ QUYẾT V18.46. | Không |
| V1847.A1 | Ghi hồ sơ: cổng **Δac ≥0,15 là LỖI THIẾT KẾ của A0** (dùng tiền điều kiện lực kiểm làm cổng loại bỏ). Từ nay cổng xác nhận dùng **CI của hiệu ứng** (vd. cận dưới CI Recovery); lực kiểm chỉ quyết "đủ/không đủ dữ liệu", không quyết "đóng". Số V1846.A2 **không** dùng để mở lại gì. | Không; không sửa luật hồi tố |
| V1847.A2 | Mở vòng ĐO (không train) cho giả thuyết **"P2 làm nhòe họa âm theo trục tần số ở dải ≤4 kHz"**. Đo TRỰC TIẾP trên mel, không cấy ghép. 40 câu held-out **chưa từng dùng V18.43–V18.46** (≥3 s, ≥12 âm tiết, tối đa 5/video, chọn không xem BAK; thiếu thì tối thiểu 25, báo). Chỉ số: độ tương phản phổ dải ≤4 kHz (trung bình max−min log-mel trong cửa sổ 5 bin, frame hữu thanh) của C (P2 TF) và B. `CR = contrast(C)/contrast(B)` theo câu. Spearman giữa `(1−CR)` và `BAK(B)−BAK(C)`; bootstrap CI95 10.000. | **ĐẠT** khi đủ: (a) trung vị CR ≤0,95 và CI95 trung vị <1; (b) ρ ≥0,3 và CI95 không chứa 0. **CR trung vị >1,0 ⇒ lạ, dừng.** Chỉ (a) đạt ⇒ báo "model mượt nhưng không giải thích BAK", giữ đóng băng. |
| V1847.A3 | Nếu A2 ĐẠT và người dùng duyệt: **chỉ pilot**, không chạy dài. Probe 100 bước, rồi pilot 2.000 bước từ P2 EMA, thêm loss độ tương phản phổ ≤4 kHz (khớp contrast cửa sổ 5 bin giữa mel dự đoán và mel gốc; trọng số do Agent 2 chọn qua probe để loss mới ≤30% tổng loss, ghi trước pilot). Mọi thứ khác giữ P2. | Pilot ĐẠT khi trên 40 câu A2: BAK TF tăng ≥0,05 so P2, cận dưới CI95 >0, và CR trung vị tăng. Đạt chưa đổi production; cần nghe mù + regression, chạy dài cần duyệt riêng. Probe NaN/RAM vượt máy ⇒ dừng. Pilot BAK giảm, cận trên CI <0 ⇒ đóng hướng mượt tần số, giữ đóng băng. |

### V1847.A2 — 40 câu DÀI mới, chọn trước khi đo

Nguồn holdout; loại 120 câu đã dùng V18.43–V18.46; ≥3 s, ≥12 âm tiết; tối đa 5/video.
Chọn 4 câu dài nhất mỗi video + 4 câu dài nhất còn lại; **không xem BAK**.

| # | id | giây | âm tiết | # | id | giây | âm tiết |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | `2b65WyiFC9k_0032__s00` | 10,10 | 48 | 21 | `VeU_85bZlrY_0034__s01` | 4,04 | 16 |
| 2 | `2b65WyiFC9k_0202__s01` | 9,93 | 44 | 22 | `VeU_85bZlrY_0129__s04` | 3,66 | 12 |
| 3 | `2b65WyiFC9k_0080__s01` | 9,87 | 36 | 23 | `VeU_85bZlrY_0126__s00` | 3,23 | 16 |
| 4 | `2b65WyiFC9k_0322__s01` | 9,82 | 40 | 24 | `o8RjAmBtyZo_0177__s01` | 7,36 | 27 |
| 5 | `4ITcvEa_Acc_0046__s00` | 10,09 | 45 | 25 | `o8RjAmBtyZo_0208__s02` | 6,52 | 21 |
| 6 | `4ITcvEa_Acc_0204__s00` | 10,07 | 37 | 26 | `o8RjAmBtyZo_0208__s00` | 6,39 | 24 |
| 7 | `4ITcvEa_Acc_0219__s00` | 10,06 | 45 | 27 | `o8RjAmBtyZo_0065__s00` | 6,15 | 22 |
| 8 | `4ITcvEa_Acc_0165__s02` | 9,97 | 34 | 28 | `vEtfty4Cc6Y_0277__s00` | 8,74 | 37 |
| 9 | `BD83pScFukQ_0038__s00` | 9,94 | 52 | 29 | `vEtfty4Cc6Y_0063__s01` | 8,73 | 38 |
| 10 | `BD83pScFukQ_0162__s00` | 9,91 | 45 | 30 | `vEtfty4Cc6Y_0190__s00` | 8,71 | 32 |
| 11 | `BD83pScFukQ_0014__s00` | 9,90 | 40 | 31 | `vEtfty4Cc6Y_0059__s00` | 8,66 | 31 |
| 12 | `BD83pScFukQ_0094__s00` | 9,78 | 43 | 32 | `z0zSgR_oie4_0141__s00` | 10,12 | 46 |
| 13 | `EM_ObHWvd94_0017__s00` | 9,99 | 53 | 33 | `z0zSgR_oie4_0050__s00` | 10,10 | 44 |
| 14 | `EM_ObHWvd94_0140__s00` | 9,89 | 45 | 34 | `z0zSgR_oie4_0230__s00` | 10,07 | 49 |
| 15 | `EM_ObHWvd94_0090__s01` | 9,87 | 46 | 35 | `z0zSgR_oie4_0241__s00` | 10,02 | 46 |
| 16 | `EM_ObHWvd94_0159__s00` | 9,75 | 49 | 36 | `EUNlJU1BuzE_0223__s00` | 10,22 | 44 |
| 17 | `EUNlJU1BuzE_0095__s00` | 10,39 | 50 | 37 | `z0zSgR_oie4_0218__s00` | 9,98 | 48 |
| 18 | `EUNlJU1BuzE_0262__s00` | 10,30 | 49 | 38 | `4ITcvEa_Acc_0226__s00` | 9,94 | 44 |
| 19 | `EUNlJU1BuzE_0044__s01` | 10,30 | 36 | 39 | `2b65WyiFC9k_0089__s00` | 9,76 | 46 |
| 20 | `EUNlJU1BuzE_0116__s00` | 10,27 | 48 | 40 | `BD83pScFukQ_0222__s00` | 9,72 | 48 |

### V1847.B — Việc giao Agent 2
1. Commit V1847.* + 40 câu mới (commit mới, không amend).
2. A2: bảng CR từng câu, trung vị + CI, ρ + CI, verdict.
3. A2 không đạt: dừng, report, giữ đóng băng.
4. A2 đạt: **DỪNG, chờ người dùng duyệt pilot**; có duyệt mới chạy A3.
5. Report: số liệu / verdict / lạ / TỰ QUYẾT / commit / `git log --oneline`.

### V1847.C — Không làm
Không dùng lại số V1846.A2 hay mở lại `C_lo`; không chạy dài; không đổi production;
không động ONNX; không UTMOS; không cấy ghép frame; không đưa hậu xử lý mel vào production.

## V18.48 — Agent 0 (26/10/2026, pilot mượt tần số)

> **ĐĂNG KÝ TRƯỚC**, hiệu lực trước khi chạy probe. Không đổi production.
> V1848 thay thế phần thiết kế pilot của V1847.A3; chỗ mâu thuẫn theo V1848.
> **Không amend/force-push**; mọi sửa là commit mới trước kết quả đầu tiên.

| Mã | Quyết định | Cổng / điều kiện dừng |
|---|---|---|
| V1848.A0 | Ghi nhận V1847.A2 **ĐẠT** (CR trung vị 0,7067; CI [0,6899; 0,7324]; 40/40 CR<1; ρ 0,4096; CI [0,1202; 0,6407]). Duyệt TỰ QUYẾT V18.47. Chất lượng acoustic **RÃ ĐÔNG CÓ GIỚI HẠN**: chỉ cho pilot vòng này. | Không |
| V1848.A1 | Loss mới: trên mel dự đoán P và mel gốc T, chỉ 66 bin ≤4 kHz, chỉ frame hữu thanh. `contrast_f(X) = trung bình theo bin của [max−min trong cửa sổ 5 bin] tại frame f`. `L_con = trung bình theo frame |contrast_f(P)−contrast_f(T)|`. Khớp **thống kê mức tương phản theo frame**, không khớp từng bin. Dùng max/min trực tiếp (subgradient); nếu probe gradient bất ổn thì được thay logsumexp nhiệt độ 0,1, ghi lại. | Có unit test: P=T ⇒ L_con=0; P=T làm mượt tần số ⇒ L_con>0; gradient hữu hạn. Test hỏng ⇒ dừng. |
| V1848.A2 | Hai lượt **PILOT** (P2 EMA + 2.000 bước + L_con) và **CONTROL** (P2 EMA + 2.000 bước, không L_con). Cùng seed, dữ liệu, thứ tự batch, lr, cấu hình adversarial như P2, EMA decay. Đánh giá bằng **trọng số EMA** tại bước 2.000. | Không |
| V1848.A3 | Probe 100 bước có L_con, chọn w để L_con chiếm **15–30 %** tổng loss (trung bình 50 bước cuối probe). Ghi w vào DECISIONS + commit **trước** khi chạy pilot. | NaN, RAM vượt máy, hoặc không có w trong 15–30 % ⇒ dừng, báo. |
| V1848.A4 | Cổng chính trên 40 câu V1847.A2, TF thời lượng, −16 LUFS. `ΔBAK = BAK(PILOT) − BAK(CONTROL)`, bootstrap theo câu 10.000. | **ĐẠT** khi đủ: (1) ΔBAK ≥0,05 và cận dưới CI95 >0; (2) CR trung vị PILOT > CONTROL và CI95 hiệu số >0; (3) CR trung vị PILOT ≤1,05. Báo thêm BAK/CR của P2. TRƯỢT: ΔBAK cận trên CI95 <0 ⇒ **ĐÓNG hướng mượt tần số**, đóng băng lại. Không kết luận (CI chứa 0) ⇒ đóng băng lại, báo, **không tự thử w khác**. |
| V1848.A5 | Phụ ở đường sản phẩm: 40 câu qua CLI chunk mode (dự đoán thời lượng), `BAK(PILOT)−BAK(CONTROL)` + CI95; L1 mel TF PILOT vs CONTROL. | Chỉ báo cáo, không phải cổng. **LẠ, dừng** khi: TF tăng nhưng chunk giảm với cận trên CI <0; L1 mel PILOT tăng >10 % so CONTROL; CR PILOT >1,05; CONTROL tự tăng BAK ≥0,05 so P2. |
| V1848.A6 | Nếu A4 ĐẠT và A5 không lạ: **CHƯA đổi production**. Vòng sau: nghe mù PILOT vs CONTROL ở chunk mode (28 lượt như V1844.A5), regression golden set, OOV/số/dấu câu. Chạy dài (trần 60.000) cần duyệt riêng sau nghe mù. | Theo luật V1844.A5 |

### V1848.B — Việc giao Agent 2
1. Commit V1848.* (không amend).
2. Viết L_con + unit test; chạy suite; commit.
3. Probe 100 bước, chốt w, commit w.
4. Chạy PILOT rồi CONTROL (nối tiếp, không song song).
5. Chấm A4 rồi A5; bảng P2/CONTROL/PILOT × (BAK TF, BAK chunk, CR median, L1 mel), ΔBAK + CI, verdict.
6. Nếu ĐẠT: dừng, chờ A0; chuẩn bị 16 câu nghe mù nhưng **chưa dựng trang**.
7. Report + `git log --oneline`.

### V1848.C — Không làm
Không đổi production; không quá 2.000 bước; không thử w thứ hai sau kết quả; không UTMOS;
không động ONNX; không cấy ghép frame.

### V1848.A3 — trọng số `w` chốt TRƯỚC pilot

- Probe 100 bước, `--contrast-weight 0.1`, `d_warmup=10`, seed 42, P2 EMA.
- Trung bình 50 bước cuối (log mỗi 10): `rec` **1,52105** · `contrast` **0,39354** ·
  `adv` **−0,39904** · `adv_eff` **0,3**.
- Chọn **`w = 1,0338`** để `L_con` chiếm **22,5 %** tổng loss
  (`w·contrast / (rec + eff·adv + w·contrast)`).
- File probe: `runs/v1848_probe/`; log `train_log.csv`.
- Chưa chạy PILOT/CONTROL tại thời điểm ghi mục này.

## V18.49 — Agent 0 (26/10/2026, sau report V18.48)

> **ĐĂNG KÝ TRƯỚC**, hiệu lực trước mọi phép đo V18.49. **Không train, không đổi production, không thử w khác.**
> Không amend/force-push; mọi sửa là commit mới trước kết quả đầu tiên.

| Mã | Quyết định | Cổng / điều kiện dừng |
|---|---|---|
| V1849.A0 | Chấp nhận V18.48: A4 **không kết luận** theo luật; production giữ P2. Duyệt TỰ QUYẾT V18.48. | Không |
| V1849.A1 | Ghi hồ sơ **lỗi thiết kế A0 thứ hai**: (1) cổng chính đặt ở TF trong khi hợp đồng sản phẩm là chunk (V1844.A2); (2) ngưỡng ΔBAK 0,05 chưa hiệu chỉnh theo liều (CR chỉ lấp ~1/3 thiếu hụt, kỳ vọng ~0,03). Luật mới: cổng chất lượng đo **CHÍNH ở chunk mode**; TF chỉ chẩn đoán; ngưỡng hiệu ứng phải kèm ước lượng kỳ vọng trước khi chạy. Số V18.48 **không** dùng đổi production. | Không sửa hồi tố |
| V1849.A2 | Tái lập trên 40 câu held-out **mới** (chưa dùng V18.43–V18.48; ≥3 s, ≥12 âm tiết; tối đa 5/video; chọn không xem BAK). Dùng nguyên checkpoint EMA 2.000 của `runs/v1848_pilot` và `runs/v1848_control`, **không train lại**. CLI chunk mode, −16 LUFS. `ΔBAK = BAK(PILOT)−BAK(CONTROL)`, bootstrap câu 10.000. Báo CR trung vị (TF). Kỳ vọng đăng ký trước: ΔBAK chunk **+0,03 đến +0,06**. | **ĐẠT** khi cận dưới CI95 ΔBAK >0 **VÀ** ΔCR trung vị >0 với CI95 >0. **Cận trên CI95 ΔBAK <0 ⇒ ĐÓNG L_con.** CI chứa 0 ⇒ không tái lập, đóng băng, không thử thêm. ΔCR ≤0 ⇒ lạ, dừng (checkpoint sai). |
| V1849.A3 | Nghe mù PILOT vs CONTROL ở chunk mode, chạy **song song** A2. 28 lượt: 16 cặp PILOT vs CONTROL trên **16 câu mới** (chọn ngẫu nhiên seed 1849 từ 40 câu A2, không xem BAK; danh sách ghi trước); 4 dương (CONTROL vs CONTROL+trắng SNR 30 dB); 4 âm (CONTROL vs CONTROL); 4 lặp (đảo A/B). −16 LUFS, peak, ngẫu nhiên, ẩn tên, key ngoài thư mục phục vụ. Câu hỏi: "Bản nào ít rè nền hơn?" | Phiên hợp lệ: dương ≥3/4, âm ≥3/4, lặp ≥3/4. **PILOT thắng** khi binomial một phía p<0,05 trên lượt không hòa, tối thiểu 10 lượt. Không hợp lệ ⇒ làm lại ngày khác. <10 lượt không hòa ⇒ "tai không phân biệt", báo. **CONTROL thắng rõ (p<0,05 phía CONTROL) ⇒ ĐÓNG L_con.** |
| V1849.A4 | Kết hợp: **ỨNG VIÊN** khi A2 ĐẠT **và** A3 PILOT thắng. Khi đó V18.50: regression golden set (full 20 câu, hash cập nhật kèm mã), OOV/số/viết tắt/dấu câu, rồi người dùng duyệt đổi production sang PILOT 2k. Chạy dài (trần 60.000) vẫn cần duyệt riêng, không là điều kiện đổi production. Chỉ một trong hai đạt ⇒ không đổi production, báo A0. Cả hai không đạt ⇒ **đóng L_con, đóng băng chất lượng acoustic, kết thúc dòng chẩn đoán rè**. | Theo A2, A3 |

### V1849.A2 — 40 câu dài mới (chưa dùng)

Nguồn holdout; loại 160 câu V18.43–V18.48; ≥3 s, ≥12 âm tiết; tối đa 5/video; chọn 4 câu dài nhất/video
+ 4 câu dài nhất còn lại; **không xem BAK**. Còn 8 video (VeU không còn câu dài chưa dùng).

| # | id | giây | âm tiết | # | id | giây | âm tiết |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | `2b65WyiFC9k_0299__s00` | 9,73 | 41 | 21 | `o8RjAmBtyZo_0088__s02` | 5,94 | 25 |
| 2 | `2b65WyiFC9k_0093__s00` | 9,65 | 48 | 22 | `o8RjAmBtyZo_0194__s01` | 5,79 | 19 |
| 3 | `2b65WyiFC9k_0151__s00` | 9,54 | 45 | 23 | `o8RjAmBtyZo_0110__s01` | 5,72 | 24 |
| 4 | `2b65WyiFC9k_0165__s00` | 9,54 | 44 | 24 | `o8RjAmBtyZo_0099__s01` | 5,27 | 22 |
| 5 | `4ITcvEa_Acc_0098__s02` | 9,57 | 39 | 25 | `vEtfty4Cc6Y_0102__s00` | 8,62 | 36 |
| 6 | `4ITcvEa_Acc_0029__s00` | 9,46 | 42 | 26 | `vEtfty4Cc6Y_0257__s01` | 7,95 | 40 |
| 7 | `4ITcvEa_Acc_0097__s01` | 9,38 | 43 | 27 | `vEtfty4Cc6Y_0033__s01` | 7,94 | 27 |
| 8 | `4ITcvEa_Acc_0214__s00` | 9,32 | 47 | 28 | `vEtfty4Cc6Y_0030__s00` | 7,75 | 28 |
| 9 | `BD83pScFukQ_0045__s00` | 9,69 | 48 | 29 | `z0zSgR_oie4_0056__s00` | 9,96 | 40 |
| 10 | `BD83pScFukQ_0037__s00` | 9,37 | 44 | 30 | `z0zSgR_oie4_0078__s00` | 9,93 | 42 |
| 11 | `BD83pScFukQ_0300__s00` | 9,11 | 35 | 31 | `z0zSgR_oie4_0246__s00` | 9,90 | 48 |
| 12 | `BD83pScFukQ_0161__s00` | 8,94 | 43 | 32 | `z0zSgR_oie4_0099__s00` | 9,87 | 46 |
| 13 | `EM_ObHWvd94_0345__s00` | 9,61 | 44 | 33 | `EUNlJU1BuzE_0272__s00` | 10,06 | 51 |
| 14 | `EM_ObHWvd94_0349__s00` | 9,42 | 46 | 34 | `z0zSgR_oie4_0239__s00` | 9,86 | 48 |
| 15 | `EM_ObHWvd94_0006__s00` | 9,28 | 40 | 35 | `2b65WyiFC9k_0035__s00` | 9,50 | 38 |
| 16 | `EM_ObHWvd94_0114__s00` | 9,26 | 49 | 36 | `EM_ObHWvd94_0087__s01` | 9,25 | 37 |
| 17 | `EUNlJU1BuzE_0224__s00` | 10,15 | 44 | 37 | `4ITcvEa_Acc_0092__s01` | 9,23 | 35 |
| 18 | `EUNlJU1BuzE_0113__s01` | 10,14 | 38 | 38 | `BD83pScFukQ_0082__s01` | 8,89 | 42 |
| 19 | `EUNlJU1BuzE_0181__s00` | 10,13 | 38 | 39 | `vEtfty4Cc6Y_0008__s02` | 7,67 | 24 |
| 20 | `EUNlJU1BuzE_0101__s00` | 10,12 | 47 | 40 | `o8RjAmBtyZo_0084__s01` | 5,10 | 16 |

### V1849.A3 — 16 câu nghe mù (seed 1849)

Chọn ngẫu nhiên 16/40 câu A2, seed 1849, không xem BAK; ghi trước khi dựng trang.

| # | id | # | id |
|---:|---|---:|---|
| 1 | `2b65WyiFC9k_0093__s00` | 9 | `vEtfty4Cc6Y_0257__s01` |
| 2 | `4ITcvEa_Acc_0029__s00` | 10 | `vEtfty4Cc6Y_0033__s01` |
| 3 | `4ITcvEa_Acc_0097__s01` | 11 | `z0zSgR_oie4_0078__s00` |
| 4 | `EM_ObHWvd94_0349__s00` | 12 | `z0zSgR_oie4_0246__s00` |
| 5 | `EUNlJU1BuzE_0181__s00` | 13 | `z0zSgR_oie4_0099__s00` |
| 6 | `EUNlJU1BuzE_0101__s00` | 14 | `EUNlJU1BuzE_0272__s00` |
| 7 | `o8RjAmBtyZo_0099__s01` | 15 | `4ITcvEa_Acc_0092__s01` |
| 8 | `vEtfty4Cc6Y_0102__s00` | 16 | `vEtfty4Cc6Y_0008__s02` |

### V1849.B — Việc giao Agent 2
1. Commit V1849.* + danh sách 40 + 16 (commit mới).
2. Sinh audio chunk PILOT/CONTROL trên 40; kiểm hash checkpoint khớp V18.48.
3. Dựng trang A3, gửi link **trước** khi chấm BAK A2.
4. Chấm A2: BAK chunk, ΔBAK + CI, ΔCR + CI, verdict.
5. Có CSV: chấm A3 bằng `tools/v1844_a5_score.py` hoặc bản đổi nhãn.
6. Report + `git log --oneline`.

### V1849.C — Không làm
Không train, không thử w khác, không chạy dài; không đổi production dù cả hai cổng đạt;
không dùng lại số V18.48 để tuyên bố; không UTMOS; không động ONNX.

### V1849.D — Rủi ro
Hiệu ứng nhỏ (~0,03–0,05 BAK) có thể dưới ngưỡng nghe; "tai không phân biệt" là kết quả có khả năng cao,
khi đó PILOT không đáng đổi production. Một người nghe; không suy rộng.

### V1849.E — Giả định
Checkpoint EMA PILOT/CONTROL 2.000 còn lưu; còn ≥25 câu held-out dài chưa dùng; chi phí ~1 giờ máy
cộng ~15 phút nghe.

## V18.50 — Agent 0 (27/10/2026, sau report V18.49)

> **ĐĂNG KÝ TRƯỚC**, hiệu lực trước mọi phép đo V18.50. **Không train, không đổi production.**
> Không amend/force-push; mọi sửa là commit mới trước kết quả đầu tiên.

| Mã | Quyết định | Cổng / điều kiện dừng |
|---|---|---|
| V1850.A0 | Chấp nhận V18.49: A2 ĐẠT, A3 "tai không phân biệt", PILOT không thành ứng viên, P2 giữ. **Đóng dòng L_con/rè nền**: không thử thêm w, không chạy dài. Giữ checkpoint PILOT/CONTROL để tham chiếu. Duyệt TỰ QUYẾT V18.49. | Không |
| V1850.A1 | Ghi nhận quan sát mới: nền đã sạch ở một số câu nhưng **vẫn có rè cục bộ ở một số từ**. Đây là hiện tượng khác rè nền; BAK (toàn câu) và câu hỏi "rè nền" không nhắm tới nó. Mở dòng **"rè cục bộ theo âm tiết"**. | Không |
| V1850.A2 | Trang **ĐÁNH DẤU** rè cục bộ (không A/B). 20 câu held-out dài chưa dùng V18.43–V18.49 (≥3 s, ≥12 âm tiết, tối đa 4 câu/video, chọn không xem số liệu). Mỗi câu 3 bản: **P2 chunk, PILOT chunk, B** (Vocos mel gốc, thời lượng gốc) = 60 mục, xáo trộn seed 1850, ẩn tên, −16 LUFS. Thêm 6 đối chứng: **3 lặp** (cùng file, xuất hiện 2 lần) + **3 B cấy click/buzz 50 ms** vào 1 âm tiết biết trước. Mỗi mục hiển thị văn bản tách nút theo âm tiết; bấm nhiều hoặc không bấm; nghe lại tự do; CSV (id mục, chỉ số âm tiết). | Phiên hợp lệ khi: cấy nhân tạo bấm đúng ±1 âm tiết ở ≥2/3 mục; lặp có Jaccard tập bấm ≥0,5 ở ≥2/3 cặp. Không hợp lệ ⇒ làm lại khác ngày. |
| V1850.A3 | Phân tích nguồn: tỉ lệ âm tiết bị bấm `r(X)` cho X∈{B,P2,PILOT}, bootstrap theo câu 10.000. **Acoustic** khi `r(P2)−r(B)` cận dưới CI95 >0 **và** `r(B) ≤0,5×r(P2)`. **Vocoder/dữ liệu** khi `r(B) ≥0,7×r(P2)`. Ở giữa: "hỗn hợp". Báo `r(PILOT)−r(P2)` + CI để tham khảo, không phải cổng. | `r(P2) <2%` ⇒ "hiếm", báo, không làm A4. |
| V1850.A4 | Đặc trưng âm tiết bị bấm (chỉ P2): HNR, flatness 2–8 kHz, CR cục bộ ≤4 kHz, bước nhảy F0 tại biên, thời lượng (dự đoán/gốc), vị trí so với biên chunk, loại vần (coda tắc p/t/c/ch), thanh điệu, OOV/viết tắt/số. Mỗi đặc trưng AUC + CI95 bootstrap theo câu. | "Liên quan" khi AUC ≥0,70 và cận dưới CI95 >0,55 (hoặc ≤0,30 chiều ngược). **Số âm tiết bị bấm <30 ⇒ chỉ bảng mô tả, không kết luận.** |
| V1850.A5 | Hướng xử lý chỉ A0 chốt **sau** A3+A4; **không train trong vòng này**. | Không |

### V1850.A2 — 20 câu dài mới

Nguồn holdout; loại 200 câu V18.43–V18.49; ≥3 s, ≥12 âm tiết; tối đa 4/video; chọn 2 câu dài nhất/video
+ 4 câu dài nhất còn lại; không xem số liệu.

| # | id | giây | âm tiết | # | id | giây | âm tiết |
|---:|---|---:|---:|---:|---|---:|---:|
| 1 | `2b65WyiFC9k_0175__s01` | 9,44 | 43 | 11 | `o8RjAmBtyZo_0130__s02` | 4,91 | 14 |
| 2 | `2b65WyiFC9k_0040__s00` | 9,42 | 38 | 12 | `o8RjAmBtyZo_0088__s01` | 4,86 | 17 |
| 3 | `4ITcvEa_Acc_0216__s01` | 9,13 | 39 | 13 | `vEtfty4Cc6Y_0310__s01` | 7,19 | 34 |
| 4 | `4ITcvEa_Acc_0099__s00` | 9,10 | 43 | 14 | `vEtfty4Cc6Y_0268__s01` | 7,04 | 32 |
| 5 | `BD83pScFukQ_0009__s00` | 8,81 | 32 | 15 | `z0zSgR_oie4_0193__s02` | 9,71 | 36 |
| 6 | `BD83pScFukQ_0093__s00` | 8,73 | 44 | 16 | `z0zSgR_oie4_0051__s01` | 9,65 | 37 |
| 7 | `EM_ObHWvd94_0243__s00` | 9,24 | 42 | 17 | `EUNlJU1BuzE_0289__s00` | 9,98 | 44 |
| 8 | `EM_ObHWvd94_0206__s01` | 9,00 | 39 | 18 | `EUNlJU1BuzE_0069__s00` | 9,96 | 48 |
| 9 | `EUNlJU1BuzE_0196__s00` | 10,05 | 51 | 19 | `z0zSgR_oie4_0245__s00` | 9,60 | 46 |
| 10 | `EUNlJU1BuzE_0300__s00` | 10,04 | 48 | 20 | `z0zSgR_oie4_0040__s00` | 9,59 | 39 |

**Vị trí cấy nhân tạo** (lưu ngoài thư mục phục vụ, không hiện trên trang):

| Câu | id | âm tiết (1-based) | start (s) | burst |
|---|---:|---:|---:|---|
| 1 | `2b65WyiFC9k_0175__s01` | 22 | 4,267 | click/buzz 50 ms |
| 7 | `EM_ObHWvd94_0243__s00` | 21 | 4,629 | click/buzz 50 ms |
| 9 | `EUNlJU1BuzE_0196__s00` | 26 | 4,000 | click/buzz 50 ms |

**3 mục lặp** (cùng file, xuất hiện 2 lần): P2 câu 1 · PILOT câu 2 · B câu 3.

### V1850.B — Việc giao Agent 2
1. Commit V1850.* + danh sách 20 + vị trí cấy (commit mới).
2. Sinh audio P2/PILOT/B + controls, dựng trang đánh dấu, gửi link.
3. Chuẩn bị bảng đặc trưng A4 (căn chỉnh theo thời lượng), chưa nối nhãn.
4. Có CSV: chấm hợp lệ, A3, A4; report + `git log --oneline`.

### V1850.C — Không làm
Không train, không đổi production, không thử L_con; không UTMOS; không động ONNX.

### V1850.D — Rủi ro
Một người nghe; đánh dấu theo âm tiết lặp lại thấp hơn A/B (đã có đối chứng lặp + cấy).
Căn chỉnh âm tiết trên đường chunk dựa vào thời lượng dự đoán, có thể lệch ±1.

### V1850.E — Giả định
Còn ≥20 câu held-out dài chưa dùng (thiếu thì tối thiểu 12, báo). Thời gian nghe 25–35 phút cho 66 mục.

## V18.50b — Agent 0: sửa đăng ký V18.50 (trước khi có dữ liệu nghe)

> **Commit mới "sửa đăng ký V1850", không amend**, trước khi người dùng nghe và trước mọi kết quả.
> Phạm vi không đổi: không train, không đổi production, không ONNX, không UTMOS.

| Mã | Sửa đổi | Lý do |
|---|---|---|
| V1850b.1 | Trang thêm phiên bản **A = wav gốc** cùng 20 câu, −16 LUFS. Tổng **80 mục chính** (A, B, P2, PILOT) + 6 đối chứng = **86 mục**; xáo lại seed 1850. | Phải biết giọng thật có rè/creak ở âm tiết đó không; không có A thì không tách "đặc điểm giọng" với "lỗi vocoder". |
| V1850b.2 | Luật nguồn A3 thay bản cũ: `r(X)` cho X∈{A,B,P2,PILOT}, bootstrap câu 10.000. **Đặc điểm giọng**: `r(A) ≥0,7×r(P2)` (báo, không sửa). **Vocoder**: `r(A) ≤0,5×r(B)` **và** `r(B) ≥0,7×r(P2)`. **Acoustic**: `r(B) ≤0,5×r(P2)` **và** cận dưới CI95 `r(P2)−r(B) >0`. Không nhánh nào: "hỗn hợp", báo đầy đủ. `r(PILOT)−r(P2)` chỉ tham khảo. | Tách đặc điểm giọng thật khỏi lỗi vocoder/acoustic. |
| V1850b.3 | A4 thêm **điểm creak theo âm tiết** (dùng `tools/eval_creak.py`, ghi phiên bản) trên **A, B, P2**; tách riêng thanh **NGÃ** và **NẶNG** khỏi các thanh khác; so sánh âm tiết bị bấm ở P2 có creak cao hơn chính âm tiết đó ở A không (hiệu P2−A theo âm tiết, kèm CI). | Kiểm creak — đúng hiện tượng người dùng nghe — không chỉ BAK/flatness. |

**Không đổi**: không train, không đổi production, không ONNX, không UTMOS. Hướng xử lý (GTA, vocoder source-filter,
refine mel 2 bước) chỉ A0 chốt sau A3/A4.

## V18.50c — Agent 0: bổ sung trước khi nghe

| Mã | Sửa đổi | Ghi chú |
|---|---|---|
| V1850c.1 | Mỗi mục trang có thêm ô tick **"Văn bản không khớp âm thanh"**; CSV thêm cột `mismatch`. Mục A bị tick ⇒ câu đó "nhãn nghi sai", **loại khỏi A3/A4**, báo riêng. Báo cả trường hợp chỉ tick ở P2/PILOT (model đọc sai chữ). Không phải cổng; chỉ làm sạch phân tích và ước lượng tỉ lệ nhãn sai held-out. | Trang 86 mục (20×A/B/P2/PILOT + 3 lặp + 3 cấy). |

## V18.51 — dự kiến (chạy sau V18.50, KHÔNG train)

| Mã | Việc | Cổng / luật (đăng ký trước) |
|---|---|---|
| V1851.A1 | ASR tiếng Việt có sẵn (hoặc PhoWhisper/Whisper, ghi phiên bản) trên toàn bộ clip train + held-out; CER theo âm tiết giữa nhãn và ASR từng clip. Thêm 2 tín hiệu không ASR: tốc độ đọc lệch >3 MAD so trung vị; loss L1 từng clip của P2 (TF) top 2%. | CER chỉ để **lọc dữ liệu**, không đánh giá model. |
| V1851.A2 | Người dùng nghe xác nhận 40 clip: 30 CER cao nhất + 10 ngẫu nhiên CER>0,3; 3 nút khớp / sai một phần / sai hoàn toàn. | Precision ngưỡng CER>0,3; <0,6 ⇒ không dùng được, báo. |
| V1851.A3 | Ước lượng tỉ lệ nhãn sai toàn data = (số clip CER>0,3) × precision; báo theo video nguồn. | ≥2% clip hoặc ≥2% giờ ⇒ mở pilot làm sạch (A4). <2% ⇒ ghi hồ sơ, đóng giả thuyết cho rè nền, vẫn loại clip đó khỏi held-out. |
| V1851.A4 | (Chỉ khi A3 ≥2% + duyệt) PILOT = P2 EMA + 2.000 bước trên data loại clip nghi sai; CONTROL = data đầy đủ; cùng seed/cấu hình V1848. | Cổng chính **chunk**: ΔBAK cận dưới CI95 >0 **và** ΔCR >0; rồi nghe mù đánh dấu âm tiết. Kỳ vọng ước lượng trước khi chạy. |
| V1851.A5 | Tính lại Δac V18.43/45/46 sau khi loại câu held-out nghi sai nhãn. | Chỉ giải thích; **không** mở lại `C_lo` hay cổng cũ. |

## V18.51 — Agent 0 (27/10/2026, thay bản dự kiến trong V1850c)

> **ĐĂNG KÝ TRƯỚC**, hiệu lực trước mọi phép đo V18.51. Không train, không đổi production.
> Bản V18.51 dự kiến trong V1850c bị **thay thế toàn bộ**; ngưỡng 2% cũ không còn phù hợp.

| Mã | Quyết định | Cổng / điều kiện dừng |
|---|---|---|
| V1851.A0 | Chấp nhận V18.50: phiên **KHÔNG HỢP LỆ**, A3/A4 không kết luận. Duyệt TỰ QUYẾT. Ghi nhận mismatch A 18/20, B 20/20, P2 1/21, PILOT 1/21 (một người nghe, chưa xác nhận khách quan). | Không |
| V1851.A1 | Kiểm vị trí click 3 mục cấy: so âm tiết người dùng bấm với âm tiết cấy; xác định lại vị trí click **theo thời gian** và ánh xạ sang âm tiết bằng ASR timestamp, không dùng thời lượng gốc. | Báo lệch bao nhiêu âm tiết; key mới có khớp ±1 không. **Không đổi verdict V18.50.** |
| V1851.A2 | Xác nhận khách quan trên 20 câu V18.50: ASR có timestamp từng từ (faster-whisper small 1.2.1, `small`, int8, ghi rõ) trên wav gốc. Căn chữ ASR vs nhãn; đếm âm tiết dư đầu/giữa/cuối. Phần dư cuối: so 15 âm tiết đầu của segment kế tiếp cùng parent/video (CER âm tiết). | **LỆCH MỐC CUỐI** khi ≥70% câu mismatch có dư cuối VÀ dư khớp đầu segment kế với CER ≤0,3. Báo tương quan tai–ASR. ASR và tai bất đồng >30% ⇒ báo, chưa quét toàn bộ. |
| V1851.A3 | Truy nguyên code tạo segment: mốc thời gian, tách sNN, padding/trim đầu/cuối, đơn vị, làm tròn frame/sample. Báo file/dòng và lệch là **offset cố định** hay **drift**. | Có cơ chế + tái hiện trên ≥3 câu A2. Không tìm ra ⇒ báo, tiếp A4. |
| V1851.A4 | Quét toàn bộ train + held-out bằng ASR như A2: dư đầu/cuối, thiếu, CER; thống kê video/sNN/độ dài. | **P0** khi ≥10% clip có dư cuối ≥2 âm tiết ⇒ **chặn mọi vòng chất lượng acoustic** tới khi sửa. Ước tính >12h ⇒ mẫu phân tầng ≥15%, báo. |
| V1851.A5 | Đề xuất sửa (chỉ mẫu, không ghi đè gốc). Ưu tiên sửa nguồn A3; nếu không: cắt mốc cuối theo ASR timestamp âm tiết cuối có trong nhãn + **đệm lặng 0,05 s** (chốt trước), áp lên 40 clip ngẫu nhiên chưa dùng. | Tự động: CER ASR vs nhãn ≤0,1 ở ≥90% clip, không cụt âm cuối. Tai: 40 clip, 3 nút khớp/dư/cụt; ĐẠT khi ≥36/40 "khớp" và ≤2 clip "cụt". Trượt ⇒ không áp toàn bộ, báo A0. |
| V1851.A6 | Ghi hồ sơ: số V18.43–18.49 dùng mel/thời lượng gốc trên held-out được đánh dấu **"có thể nhiễm lệch mốc cắt"**; so sánh chunk ít bị hơn. **Không mở lại cổng cũ.** Dòng rè cục bộ tạm dừng, chỉ làm lại trên held-out đã sửa. | Không |
| V1851.A7 | **Không train** trong vòng này. Nếu A4 xác nhận P0 và A5 ĐẠT, V18.52 mới đề xuất áp sửa toàn bộ, dựng lại held-out, tính lại alignment, rồi train (ngân sách duyệt riêng). | Theo A4/A5 |

### V1851.A5 — 40 clip ngẫu nhiên (seed 1851), chưa dùng

Chọn 40 segment holdout chưa dùng V18.43–V18.50, ≥3 s, ≥12 âm tiết; 8 video.

| # | id | # | id |
|---:|---|---:|---|
| 1 | `2b65WyiFC9k_0009__s00` | 21 | `EM_ObHWvd94_0127__s00` |
| 2 | `2b65WyiFC9k_0031__s00` | 22 | `EM_ObHWvd94_0241__s00` |
| 3 | `2b65WyiFC9k_0036__s01` | 23 | `EM_ObHWvd94_0330__s01` |
| 4 | `2b65WyiFC9k_0065__s02` | 24 | `EM_ObHWvd94_0352__s01` |
| 5 | `2b65WyiFC9k_0140__s01` | 25 | `EUNlJU1BuzE_0003__s01` |
| 6 | `2b65WyiFC9k_0155__s01` | 26 | `EUNlJU1BuzE_0029__s00` |
| 7 | `2b65WyiFC9k_0162__s00` | 27 | `EUNlJU1BuzE_0268__s02` |
| 8 | `2b65WyiFC9k_0222__s01` | 28 | `EUNlJU1BuzE_0294__s01` |
| 9 | `4ITcvEa_Acc_0033__s01` | 29 | `o8RjAmBtyZo_0084__s03` |
| 10 | `4ITcvEa_Acc_0042__s00` | 30 | `vEtfty4Cc6Y_0018__s00` |
| 11 | `4ITcvEa_Acc_0062__s03` | 31 | `vEtfty4Cc6Y_0057__s02` |
| 12 | `4ITcvEa_Acc_0098__s01` | 32 | `vEtfty4Cc6Y_0122__s04` |
| 13 | `4ITcvEa_Acc_0168__s02` | 33 | `z0zSgR_oie4_0015__s02` |
| 14 | `BD83pScFukQ_0013__s02` | 34 | `z0zSgR_oie4_0037__s00` |
| 15 | `BD83pScFukQ_0085__s02` | 35 | `z0zSgR_oie4_0059__s00` |
| 16 | `BD83pScFukQ_0181__s01` | 36 | `z0zSgR_oie4_0135__s04` |
| 17 | `BD83pScFukQ_0204__s02` | 37 | `z0zSgR_oie4_0143__s03` |
| 18 | `BD83pScFukQ_0382__s03` | 38 | `z0zSgR_oie4_0166__s01` |
| 19 | `EM_ObHWvd94_0032__s02` | 39 | `z0zSgR_oie4_0167__s02` |
| 20 | `EM_ObHWvd94_0102__s01` | 40 | `z0zSgR_oie4_0224__s01` |

### V1851.B — Việc giao Agent 2
1. Commit V1851.* + 40 clip + đệm 0,05 s (commit mới).
2. A1 + A2 trên 20 câu V18.50 (chạy trước).
3. A3 đọc code song song.
4. A2 không dừng: A4 (ước tính thời gian trước; >12h thì mẫu ≥15%).
5. A5: sửa 40 clip, chấm tự động, trang 3 nút, gửi link.
6. Report + `git log --oneline`; phần tai A5 có thể báo sau.

### V1851.C — Không làm
Không train/đổi production/ghi đè dữ liệu gốc; không dùng CER/ASR đánh giá model; không mở C_lo/L_con;
không UTMOS; không ONNX.
