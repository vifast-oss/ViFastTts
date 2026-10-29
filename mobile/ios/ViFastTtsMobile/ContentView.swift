import AVFoundation
import SwiftUI

struct ContentView: View {
    @State private var text = SharedContract.defaultText(platform: "ios")
    @State private var status = "Sẵn sàng"
    @State private var busy = false
    @State private var error: String?
    @State private var player: AVAudioPlayer?
    @State private var lastAudioURL: URL?
    @State private var lastSrtURL: URL?
    @State private var lastVttURL: URL?
    @State private var lastKaraokeURL: URL?
    @State private var karaokeUnits: [KaraokeUnit] = []
    @State private var timingSummary = ""
    @State private var showModels = false
    @State private var activeModel = TtsEngine.shared.activeModel
    @State private var ready = TtsEngine.shared.isReady
    @AppStorage("vifasttts.mode") private var mode = "local"
    // Điện thoại không có localhost của máy dev: để trống, chỉ gợi ý IP LAN.
    @AppStorage("vifasttts.serverURL") private var serverURL = ""
    @AppStorage("vifasttts.token") private var token = ""
    @AppStorage("vifasttts.speed") private var speed = 1.0
    @AppStorage("vifasttts.alpha") private var alpha = 1.5
    @AppStorage("vifasttts.fixedPauses") private var fixedPauses = false
    @AppStorage("vifasttts.peakNormalize") private var peakNormalize = false
    @AppStorage("vifasttts.maxChars") private var maxChars = 300
    @AppStorage("vifasttts.dialect") private var dialect = "north"
    @AppStorage("vifasttts.resolveOov") private var resolveOov = true
    @AppStorage("vifasttts.dictionary") private var dictionary = ""
    @AppStorage("vifasttts.customReading") private var customReading = ""
    @AppStorage("vifasttts.stream") private var stream = false
    @AppStorage("vifasttts.streamSaveWav") private var streamSaveWav = true
    @State private var streamCancellation: StreamCancellation?
    @State private var streamStartedAt: Date?
    @State private var history = SharedContract.loadHistory()
    @State private var showHistory = false
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                Text(mode == "remote" ? "Remote HTTP · server API" : "Local ONNX · Rust C ABI")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Text(activeModel.isEmpty ? "Chưa có model" : "Model: \(activeModel)")
                    .font(VFTheme.caption)
                    .foregroundStyle(VFTheme.muted)

                Picker("Chế độ", selection: $mode) {
                    Text("Local").tag("local")
                    Text("Remote").tag("remote")
                }
                .pickerStyle(.segmented)
                .tint(VFTheme.accent)

                Toggle("Stream ngay khi tổng hợp", isOn: $stream)
                    .font(VFTheme.caption)
                if stream {
                    Toggle("Lưu WAV + phụ đề khi stream", isOn: $streamSaveWav)
                        .font(VFTheme.caption)
                    Text("Stream không dùng peak normalize; tạm bỏ qua để phát ngay.")
                        .font(.caption2)
                        .foregroundStyle(VFTheme.muted)
                    if mode == "remote" {
                        Text("Remote stream cần server Rust; server cũ sẽ tự chuyển full.")
                            .font(.caption2)
                            .foregroundStyle(VFTheme.muted)
                    }
                }

                if mode == "remote" {
                    TextField("http://192.168.1.100:8000", text: $serverURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textContentType(.URL)
                        .textFieldStyle(.roundedBorder)
                    SecureField("Bearer token (tuỳ chọn)", text: $token)
                        .textFieldStyle(.roundedBorder)
                }

                TextEditor(text: $text)
                    .font(VFTheme.body)
                    .foregroundStyle(VFTheme.ink)
                    .scrollContentBackground(.hidden)
                    .frame(minHeight: 180, maxHeight: 280)
                    .padding(8)
                    .background(VFTheme.surface)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(VFTheme.border)
                    )

                HStack {
                    Button {
                        synthesize()
                    } label: {
                        Label("Đọc", systemImage: "play.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(VFTheme.accent)
                    .disabled(busy || (mode == "local" && !ready))

                    Button {
                        showModels = true
                    } label: {
                        Label("Model", systemImage: "square.stack.3d.up")
                    }
                    .disabled(busy)

                    Button {
                        showSettings = true
                    } label: {
                        Label("Cấu hình", systemImage: "slider.horizontal.3")
                    }
                    .disabled(busy)

                    Button {
                        streamCancellation?.cancel()
                        player?.stop()
                        status = streamCancellation == nil ? "Đã dừng phát" : "Đang dừng stream…"
                    } label: {
                        Label("Dừng", systemImage: "stop.fill")
                    }
                    .disabled(player == nil && streamCancellation == nil)

                    if busy {
                        ProgressView()
                    }
                }

                Text(status)
                    .font(VFTheme.body)
                    .foregroundStyle(VFTheme.ink)
                if !timingSummary.isEmpty {
                    Text(timingSummary)
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.muted)
                }
                if !karaokeUnits.isEmpty {
                    TimelineView(.periodic(from: .now, by: 0.1)) { _ in
                        let active = activeKaraokeText
                        Text(active.isEmpty ? "♪" : active)
                            .font(.title2.weight(.semibold))
                            .foregroundStyle(VFTheme.accent)
                            .frame(maxWidth: .infinity, alignment: .center)
                            .padding(.vertical, 6)
                    }
                }
                if let error {
                    Text(error)
                        .font(.callout)
                        .foregroundStyle(.red)
                }
                if mode == "local" && !ready {
                    HStack(alignment: .firstTextBaseline) {
                        Text("Chưa có model trong bundle hoặc FFI/ORT chưa nạp.")
                            .font(VFTheme.caption)
                            .foregroundStyle(VFTheme.warning)
                        Button("Tải model") { showModels = true }
                            .font(VFTheme.caption)
                    }
                }
                if mode == "remote" {
                    Text("Remote gọi /api/tts; server có thể là desktop local, LAN hoặc online.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                }
                .padding()
                .padding(.bottom, 24)
            }
            .background(VFTheme.background.ignoresSafeArea())
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        showHistory = true
                    } label: {
                        Image(systemName: "clock.arrow.circlepath")
                    }
                    .disabled(history.isEmpty)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    if let lastAudioURL {
                        Menu {
                            ShareLink(item: lastAudioURL) {
                                Label("Chia sẻ WAV", systemImage: "waveform")
                            }
                            if let lastSrtURL {
                                ShareLink(item: lastSrtURL) {
                                    Label("Chia sẻ SRT", systemImage: "captions.bubble")
                                }
                            }
                            if let lastVttURL {
                                ShareLink(item: lastVttURL) {
                                    Label("Chia sẻ VTT", systemImage: "text.bubble")
                                }
                            }
                            if let lastKaraokeURL {
                                ShareLink(item: lastKaraokeURL) {
                                    Label("Chia sẻ JSON karaoke", systemImage: "curlybraces")
                                }
                            }
                        } label: {
                            Image(systemName: "square.and.arrow.up")
                        }
                    }
                }
            }
            .tint(VFTheme.accent)
            .font(VFTheme.body)
            .navigationTitle("ViFastTts")
            .sheet(isPresented: $showModels, onDismiss: {
                ready = TtsEngine.shared.isReady
                activeModel = TtsEngine.shared.activeModel
                status = mode == "remote"
                    ? "Remote: \(serverURL)"
                    : (ready ? "Model sẵn sàng" : "Model chưa sẵn sàng")
            }) {
                ModelBrowserView()
            }
            .sheet(isPresented: $showSettings) {
                SettingsView(
                    speed: $speed,
                    alpha: $alpha,
                    fixedPauses: $fixedPauses,
                    peakNormalize: $peakNormalize,
                    maxChars: $maxChars,
                    dialect: $dialect,
                    resolveOov: $resolveOov,
                    dictionary: $dictionary,
                    customReading: $customReading
                )
            }
            .sheet(isPresented: $showHistory) {
                HistoryView(history: history) { sample in
                    if let value = sample.text, !value.isEmpty {
                        text = value
                    }
                    showHistory = false
                }
            }
            .onChange(of: mode) { value in
                status = value == "remote" ? "Remote: nhập server URL" : "Local: sẵn sàng"
            }
            .onAppear {
                // Bản cũ lưu localhost; xoá để máy thật không gọi nhầm.
                if serverURL == "http://127.0.0.1:8000" || serverURL == "http://localhost:8000" {
                    serverURL = ""
                }
                history = SharedContract.loadHistory()
                runAutoTestIfNeeded()
            }
        }
    }

    private func runAutoTestIfNeeded() {
        #if DEBUG
        let environment = ProcessInfo.processInfo.environment
        guard environment["VIFASTT_AUTOTEST"] == "1" else { return }
        if let value = environment["VIFASTT_MODE"] { mode = value }
        if let value = environment["VIFASTT_SERVER"] { serverURL = value }
        if let value = environment["VIFASTT_TOKEN"] { token = value }
        if let value = environment["VIFASTT_TEXT"] { text = value }
        if let value = environment["VIFASTT_STREAM"] { stream = value == "1" }
        if let value = environment["VIFASTT_STREAM_SAVE"] { streamSaveWav = value == "1" }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            synthesize()
        }
        if let raw = environment["VIFASTT_CANCEL_AFTER"],
           let seconds = Double(raw) {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5 + seconds) {
                streamCancellation?.cancel()
            }
        }
        #endif
    }

    /// Peak normalize cần biết đỉnh cả file; stream chỉ có từng chunk nên bỏ qua.
    private var effectivePeakNormalize: Bool { peakNormalize && !stream }

    private var activeKaraokeText: String {
        let position: Int
        if let streamStartedAt {
            position = Int(Date().timeIntervalSince(streamStartedAt) * 1000)
        } else if let player {
            position = Int(player.currentTime * 1000)
        } else {
            return ""
        }
        return karaokeUnits.first { position >= $0.start_ms && position < $0.end_ms }?.text ?? ""
    }

    private func synthesize() {
        let input = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !input.isEmpty else {
            error = "Chưa có text"
            return
        }
        if mode == "remote" && serverURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            error = "Nhập server URL LAN trước khi đọc remote."
            status = "Thiếu server URL"
            return
        }
        busy = true
        error = nil
        karaokeUnits = []
        timingSummary = ""
        streamStartedAt = nil
        player?.stop()
        let estimate = SharedContract.eta(history: history, mode: mode, chars: input.count)
        let estimateText = estimate.map { String(format: " · ước tính ~%.1fs", Double($0) / 1000.0) } ?? ""
        status = (mode == "remote" ? "Đang gọi server…" : "Đang tổng hợp local…") + estimateText
        let startedAt = Date()
        Task {
            do {
                let result: TtsResult
                if mode == "remote" {
                    let client = try RemoteTtsClient(server: serverURL, token: token)
                    if stream {
                        let cancellation = StreamCancellation()
                        streamCancellation = cancellation
                        streamStartedAt = Date()
                        do {
                            let remote = try await client.stream(
                                text: input,
                                speed: Float(speed),
                                alpha: Float(alpha),
                                maxChars: maxChars,
                                fixedPauses: fixedPauses,
                                peakNormalize: effectivePeakNormalize,
                                dialect: dialect,
                                resolveOov: resolveOov,
                                dictionary: dictionary,
                                customReading: customReading,
                                saveWav: streamSaveWav,
                                cancellation: cancellation
                            )
                            streamCancellation = nil
                            if remote.cancelled {
                                karaokeUnits = []
                                timingSummary = ""
                                status = "Đã dừng stream remote"
                                busy = false
                                return
                            }
                            lastAudioURL = remote.wavURL
                            lastSrtURL = remote.srtURL
                            lastVttURL = remote.vttURL
                            lastKaraokeURL = remote.karaokeURL
                            karaokeUnits = remote.units
                            timingSummary = remote.srtURL == nil
                                ? "Stream · không lưu WAV/phụ đề"
                                : "Stream · đã lưu WAV + SRT/VTT"
                            status = String(format: "Xong stream remote · %.2f s", remote.duration)
                            history = SharedContract.record(
                                mode: "remote-stream",
                                chars: input.count,
                                elapsedMs: Int(Date().timeIntervalSince(startedAt) * 1000),
                                text: input
                            )
                            busy = false
                            return
                        } catch {
                            streamCancellation = nil
                            streamStartedAt = nil
                            self.error = nil
                            status = "Server không stream được (\(error.localizedDescription)); chuyển full…"
                        }
                    }
                    let remote = try await client.synthesize(
                        text: input,
                        speed: Float(speed),
                        alpha: Float(alpha),
                        maxChars: maxChars,
                        fixedPauses: fixedPauses,
                        peakNormalize: effectivePeakNormalize,
                        dialect: dialect,
                        resolveOov: resolveOov,
                        dictionary: dictionary,
                        customReading: customReading
                    )
                    result = TtsResult(
                        wavURL: remote.wavURL,
                        srtURL: remote.srtURL,
                        vttURL: remote.vttURL,
                        karaokeURL: nil,
                        units: remote.units
                    )
                } else if stream {
                    let cancellation = StreamCancellation()
                    streamCancellation = cancellation
                    streamStartedAt = Date()
                    let result = try await TtsEngine.shared.synthesizeStream(
                        text: input,
                        speed: Float(speed),
                        alpha: Float(alpha),
                        maxChars: maxChars,
                        fixedPauses: fixedPauses,
                        peakNormalize: effectivePeakNormalize,
                        dialect: dialect,
                        resolveOov: resolveOov,
                        dictionary: dictionary,
                        customReading: customReading,
                        saveWav: streamSaveWav,
                        cancellation: cancellation
                    )
                    streamCancellation = nil
                    if result.cancelled {
                        karaokeUnits = []
                        timingSummary = ""
                        status = "Đã dừng stream local"
                        busy = false
                        return
                    }
                    lastAudioURL = result.wavURL
                    lastSrtURL = result.srtURL
                    lastVttURL = result.vttURL
                    lastKaraokeURL = result.karaokeURL
                    karaokeUnits = result.units
                    timingSummary = result.srtURL == nil
                        ? "Stream · không lưu WAV/phụ đề"
                        : "Stream · đã lưu WAV + SRT/VTT"
                    status = String(format: "Xong stream local · %.2f s", result.duration)
                    history = SharedContract.record(
                        mode: "local-stream",
                        chars: input.count,
                        elapsedMs: Int(Date().timeIntervalSince(startedAt) * 1000),
                        text: input
                    )
                    busy = false
                    return
                } else {
                    result = try await TtsEngine.shared.synthesize(
                        text: input,
                        speed: Float(speed),
                        alpha: Float(alpha),
                        maxChars: maxChars,
                        fixedPauses: fixedPauses,
                        peakNormalize: effectivePeakNormalize,
                        dialect: dialect,
                        resolveOov: resolveOov,
                        dictionary: dictionary,
                        customReading: customReading
                    )
                }
                player?.stop()
                let session = AVAudioSession.sharedInstance()
                try? session.setCategory(.playback, mode: .spokenAudio)
                try? session.setActive(true)
                let audio = try AVAudioPlayer(contentsOf: result.wavURL)
                audio.prepareToPlay()
                audio.play()
                player = audio
                lastAudioURL = result.wavURL
                lastSrtURL = result.srtURL
                lastVttURL = result.vttURL
                lastKaraokeURL = result.karaokeURL
                karaokeUnits = result.units
                timingSummary = result.srtURL == nil
                    ? "Không có timing/karaoke"
                    : "Có phụ đề SRT + VTT"
                status = String(format: mode == "remote" ? "Xong remote · %.2f s" : "Xong local · %.2f s", audio.duration)
                history = SharedContract.record(
                    mode: mode,
                    chars: input.count,
                    elapsedMs: Int(Date().timeIntervalSince(startedAt) * 1000),
                    text: input
                )
            } catch {
                self.error = error.localizedDescription
                status = "Tổng hợp lỗi"
            }
            busy = false
        }
    }
}


private struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @Binding var speed: Double
    @Binding var alpha: Double
    @Binding var fixedPauses: Bool
    @Binding var peakNormalize: Bool
    @Binding var maxChars: Int
    @Binding var dialect: String
    @Binding var resolveOov: Bool
    @Binding var dictionary: String
    @Binding var customReading: String
    @State private var showOovHelp = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Âm thanh") {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(String(format: "Tốc độ: %.2f×", speed))
                            .font(VFTheme.body)
                        Slider(value: $speed, in: 0.5...2.0, step: 0.05)
                            .tint(VFTheme.accent)
                        Text("1× là bình thường; nhỏ hơn đọc chậm hơn, lớn hơn đọc nhanh hơn.")
                            .font(VFTheme.caption)
                            .foregroundStyle(VFTheme.muted)
                    }
                    VStack(alignment: .leading, spacing: 4) {
                        Text(String(format: "Độ nét mel (alpha): %.2f", alpha))
                            .font(VFTheme.body)
                        Slider(value: $alpha, in: 0.5...3.0, step: 0.05)
                            .tint(VFTheme.accent)
                        Text("1,5 là mặc định; cao hơn nét hơn nhưng dễ làm lộ rè/nhiễu, thấp hơn mềm hơn.")
                            .font(VFTheme.caption)
                            .foregroundStyle(VFTheme.muted)
                    }
                    Toggle("Pause cố định theo dấu câu", isOn: $fixedPauses)
                        .tint(VFTheme.accent)
                    Text("Chèn khoảng lặng theo dấu câu thay vì để model tự nghỉ; mặc định tắt vì model tự nhiên hơn.")
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.muted)
                    Toggle("Peak normalize", isOn: $peakNormalize)
                        .tint(VFTheme.accent)
                    Text("Peak normalize: đưa đỉnh WAV về −3 dBFS, tránh clip và ổn định âm lượng; có thể làm to cả rè/nền. Không dùng khi stream vì cần biết đỉnh toàn file.")
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.muted)
                }
                Section("Giới hạn & ngôn ngữ") {
                    Stepper("Max ký tự/chunk: \(maxChars)", value: $maxChars, in: 50...5000, step: 50)
                    Text("Câu dài tự chia nhỏ; nhỏ = ít RAM nhưng nhiều lần ngắt, lớn = ít ngắt nhưng chậm/nặng hơn.")
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.muted)
                    Picker("Phương ngữ", selection: $dialect) {
                        Text("Bắc").tag("north")
                        Text("Trung").tag("central")
                        Text("Nam").tag("south")
                    }
                    Text("Model N0 hiện là giọng Bắc; đổi mục này chủ yếu đổi một số cách đọc, muốn đổi giọng nền cần model vùng đó.")
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.muted)
                    HStack(alignment: .firstTextBaseline) {
                        Toggle("Resolve OOV", isOn: $resolveOov)
                            .tint(VFTheme.accent)
                        Spacer()
                        Button {
                            showOovHelp = true
                        } label: {
                            Image(systemName: "info.circle")
                                .foregroundStyle(VFTheme.accent)
                        }
                        .buttonStyle(.borderless)
                        .accessibilityLabel("Giải thích Resolve OOV")
                    }
                    .alert("Resolve OOV là gì?", isPresented: $showOovHelp) {
                        Button("Đóng", role: .cancel) {}
                    } message: {
                        Text("OOV = token lạ (tên riêng, viết tắt, tiếng Anh, mã sản phẩm…). Bật để tra từ điển hoặc đánh vần tên chữ cái (VNG → “vê en giê”); tắt để giữ fallback, không tự đoán. Nếu đọc vẫn sai, thêm quy tắc vào Từ điển.")
                    }
                    Text("OOV = token lạ (tên riêng, viết tắt, tiếng Anh, mã sản phẩm…). Bật để tra từ điển hoặc đánh vần tên chữ cái (VNG → “vê en giê”); tắt để giữ fallback, không tự đoán.")
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.muted)
                }
                Section("Từ điển local") {
                    TextEditor(text: $dictionary)
                        .font(.system(.caption, design: .monospaced))
                        .frame(minHeight: 120)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Text("Mỗi dòng `từ = cách đọc`. Local và remote đều nhận từ điển.")
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.muted)
                }
                Section("Cách đọc token-level") {
                    TextEditor(text: $customReading)
                        .font(.system(.caption, design: .monospaced))
                        .frame(minHeight: 100)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Text("Mỗi dòng `cụm = cách đọc`, ví dụ `TP.HCM = thành phố hồ chí minh`.")
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.muted)
                }
                Section("Giải thích thêm") {
                    DisclosureGroup("Local/Remote, stream, peak, RTF") {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Local: model chạy trên máy. Remote: gửi văn bản tới server; server cũ có thể bỏ qua một số tùy chọn.")
                            Text("Stream: phát ngay từng đoạn; không dùng peak normalize; WAV/SRT/VTT chỉ có sau khi xong nếu bật lưu.")
                            Text("Peak normalize: đưa đỉnh toàn bộ WAV về −3 dBFS để tránh clip; có thể làm to cả rè/nền.")
                            Text("RTF = thời gian xử lý / thời lượng audio; nhỏ hơn 1 là nhanh hơn thời gian thực.")
                        }
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.muted)
                    }
                }
                Section("Ghi chú") {
                    Text("Local áp dụng đầy đủ: tốc độ, alpha, max, pause, peak, phương ngữ, OOV và từ điển. Remote gửi cùng bộ tùy chọn; server cũ có thể bỏ qua.")
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.muted)
                    Text("Model base 60k nặng hơn small; nếu máy chậm, dùng small hoặc giảm max ký tự/chunk.")
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.muted)
                }
            }
            .scrollContentBackground(.hidden)
            .background(VFTheme.background.ignoresSafeArea())
            .tint(VFTheme.accent)
            .font(VFTheme.body)
            .navigationTitle("Cấu hình")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Xong") { dismiss() }
                }
            }
        }
    }
}


private struct HistoryView: View {
    let history: [EtaSample]
    let onSelect: (EtaSample) -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                ForEach(Array(history.reversed().enumerated()), id: \.offset) { _, sample in
                    Button {
                        onSelect(sample)
                    } label: {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(sample.text?.isEmpty == false ? sample.text! : "\(sample.chars) ký tự")
                                .lineLimit(2)
                                .foregroundStyle(VFTheme.ink)
                            Text(String(
                                format: "%@ · %d ký tự · %.1fs",
                                sample.mode,
                                sample.chars,
                                Double(sample.elapsed_ms) / 1000
                            ))
                            .font(.caption)
                            .foregroundStyle(VFTheme.muted)
                        }
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(VFTheme.background.ignoresSafeArea())
            .navigationTitle("Lịch sử đọc")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Xong") { dismiss() }
                }
            }
        }
    }
}
