import AVFoundation
import SwiftUI

struct ContentView: View {
    @State private var text = "Xin chào, đây là bản iOS của ViFastTts."
    @State private var status = "Sẵn sàng"
    @State private var busy = false
    @State private var error: String?
    @State private var player: AVAudioPlayer?
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
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 14) {
                Text("ViFastTts Mobile")
                    .font(VFTheme.title)
                    .fontWeight(.bold)
                    .foregroundStyle(VFTheme.ink)
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
                    .frame(minHeight: 180)
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
                        player?.stop()
                        status = "Đã dừng phát"
                    } label: {
                        Label("Dừng", systemImage: "stop.fill")
                    }
                    .disabled(player == nil)

                    if busy {
                        ProgressView()
                    }
                }

                Text(status)
                    .font(VFTheme.body)
                    .foregroundStyle(VFTheme.ink)
                if let error {
                    Text(error)
                        .font(.callout)
                        .foregroundStyle(.red)
                }
                if mode == "local" && !ready {
                    Text("Chưa có model trong bundle hoặc FFI/ORT chưa nạp.")
                        .font(VFTheme.caption)
                        .foregroundStyle(VFTheme.warning)
                }
                if mode == "remote" {
                    Text("Remote gọi /api/tts; server có thể là desktop local, LAN hoặc online.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
            .padding()
            .background(VFTheme.background.ignoresSafeArea())
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
                    maxChars: $maxChars
                )
            }
            .onChange(of: mode) { value in
                status = value == "remote" ? "Remote: nhập server URL" : "Local: sẵn sàng"
            }
            .onAppear {
                // Bản cũ lưu localhost; xoá để máy thật không gọi nhầm.
                if serverURL == "http://127.0.0.1:8000" || serverURL == "http://localhost:8000" {
                    serverURL = ""
                }
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
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            synthesize()
        }
        #endif
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
        status = mode == "remote" ? "Đang gọi server…" : "Đang tổng hợp local…"
        Task {
            do {
                let url: URL
                if mode == "remote" {
                    let client = try RemoteTtsClient(server: serverURL, token: token)
                    url = try await client.synthesize(
                        text: input,
                        speed: Float(speed),
                        fixedPauses: fixedPauses
                    )
                } else {
                    url = try await TtsEngine.shared.synthesize(
                        text: input,
                        speed: Float(speed),
                        alpha: Float(alpha),
                        maxChars: maxChars,
                        fixedPauses: fixedPauses,
                        peakNormalize: peakNormalize
                    )
                }
                let session = AVAudioSession.sharedInstance()
                try? session.setCategory(.playback, mode: .spokenAudio)
                try? session.setActive(true)
                let audio = try AVAudioPlayer(contentsOf: url)
                audio.prepareToPlay()
                audio.play()
                player = audio
                status = String(format: mode == "remote" ? "Xong remote · %.2f s" : "Xong local · %.2f s", audio.duration)
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

    var body: some View {
        NavigationStack {
            Form {
                Section("Âm thanh") {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(String(format: "Tốc độ: %.2f×", speed))
                            .font(VFTheme.body)
                        Slider(value: $speed, in: 0.5...2.0, step: 0.05)
                            .tint(VFTheme.accent)
                    }
                    VStack(alignment: .leading, spacing: 4) {
                        Text(String(format: "Độ nét mel (alpha): %.2f", alpha))
                            .font(VFTheme.body)
                        Slider(value: $alpha, in: 0.5...3.0, step: 0.05)
                            .tint(VFTheme.accent)
                    }
                    Toggle("Pause cố định theo dấu câu", isOn: $fixedPauses)
                        .tint(VFTheme.accent)
                    Toggle("Peak normalize", isOn: $peakNormalize)
                        .tint(VFTheme.accent)
                }
                Section("Giới hạn") {
                    Stepper("Max ký tự/chunk: \(maxChars)", value: $maxChars, in: 50...5000, step: 50)
                }
                Section("Ghi chú") {
                    Text("Local áp dụng đầy đủ các tùy chọn. Remote chỉ gửi tốc độ và pause cố định; alpha/max do server quyết định.")
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
