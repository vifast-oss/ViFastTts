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

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 14) {
                Text("ViFastTts Mobile")
                    .font(.largeTitle.bold())
                Text("Local ONNX · Rust C ABI")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Text(activeModel.isEmpty ? "Chưa có model" : "Model: \(activeModel)")
                    .font(.footnote)
                    .foregroundStyle(.secondary)

                TextEditor(text: $text)
                    .frame(minHeight: 180)
                    .padding(8)
                    .overlay(
                        RoundedRectangle(cornerRadius: 10)
                            .stroke(.secondary.opacity(0.3))
                    )

                HStack {
                    Button {
                        synthesize()
                    } label: {
                        Label("Đọc", systemImage: "play.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(busy || !ready)

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
                    .font(.callout)
                if let error {
                    Text(error)
                        .font(.callout)
                        .foregroundStyle(.red)
                }
                if !ready {
                    Text("Chưa có model trong bundle hoặc FFI/ORT chưa nạp.")
                        .font(.footnote)
                        .foregroundStyle(.orange)
                }
                Spacer()
            }
            .padding()
            .navigationTitle("ViFastTts")
            .sheet(isPresented: $showModels, onDismiss: {
                ready = TtsEngine.shared.isReady
                activeModel = TtsEngine.shared.activeModel
                status = ready ? "Model sẵn sàng" : "Model chưa sẵn sàng"
            }) {
                ModelBrowserView()
            }
        }
    }

    private func synthesize() {
        let input = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !input.isEmpty else {
            error = "Chưa có text"
            return
        }
        busy = true
        error = nil
        status = "Đang tổng hợp…"
        Task {
            do {
                let url = try await TtsEngine.shared.synthesize(text: input)
                let audio = try AVAudioPlayer(contentsOf: url)
                audio.prepareToPlay()
                audio.play()
                player = audio
                status = String(format: "Xong · %.2f s", audio.duration)
            } catch {
                self.error = error.localizedDescription
                status = "Tổng hợp lỗi"
            }
            busy = false
        }
    }
}
