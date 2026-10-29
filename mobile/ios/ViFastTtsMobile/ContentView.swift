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
    @AppStorage("vifasttts.serverURL") private var serverURL = "http://127.0.0.1:8000"
    @AppStorage("vifasttts.token") private var token = ""

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
                    TextField("Server URL", text: $serverURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
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
            .onChange(of: mode) { value in
                status = value == "remote" ? "Remote: nhập server URL" : "Local: sẵn sàng"
            }
            .onAppear(perform: runAutoTestIfNeeded)
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
        busy = true
        error = nil
        status = mode == "remote" ? "Đang gọi server…" : "Đang tổng hợp local…"
        Task {
            do {
                let url: URL
                if mode == "remote" {
                    let client = try RemoteTtsClient(server: serverURL, token: token)
                    url = try await client.synthesize(text: input)
                } else {
                    url = try await TtsEngine.shared.synthesize(text: input)
                }
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
