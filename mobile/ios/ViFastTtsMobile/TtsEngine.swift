import Foundation

/// Cầu nối mỏng sang C ABI `vifasttts-ffi`.
///
/// Engine không thread-safe; mọi lời gọi đi qua serial queue. UI không gọi
/// trực tiếp C, tránh block main thread khi model/synth chậm.
final class TtsEngine: @unchecked Sendable {
    static let shared = TtsEngine()

    private let queue = DispatchQueue(label: "com.vifasttts.tts")
    private var engine: UnsafeMutableRawPointer?
    private(set) var isReady = false
    private var loadError: String?

    private init() {
        guard
            let acoustic = Bundle.main.url(forResource: "acoustic", withExtension: "onnx"),
            let vocoder = Bundle.main.url(forResource: "vocoder", withExtension: "onnx")
        else {
            loadError = "Thiếu acoustic.onnx/vocoder.onnx trong app bundle"
            return
        }
        engine = vifasttts_engine_new(acoustic.path, vocoder.path)
        if engine == nil {
            loadError = lastError()
        } else {
            isReady = true
        }
    }

    deinit {
        if let engine {
            vifasttts_engine_free(engine)
        }
    }

    func synthesize(text: String, speed: Float = 1.0) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            queue.async {
                guard let engine = self.engine else {
                    continuation.resume(throwing: self.error(self.loadError ?? "Engine chưa nạp"))
                    return
                }
                var options = VifasttOptions(
                    speed: speed,
                    alpha: 1.5,
                    max_chars: 300,
                    fixed_pauses: 0,
                    peak_normalize: 0
                )
                var length = 0
                let pointer = text.withCString { cText in
                    vifasttts_synthesize(engine, cText, &options, &length)
                }
                guard let pointer, length > 0 else {
                    continuation.resume(throwing: self.error(self.lastError()))
                    return
                }
                let data = Data(bytes: pointer, count: length)
                vifasttts_buffer_free(pointer, length)
                let url = FileManager.default.temporaryDirectory
                    .appendingPathComponent("vifasttts-\(UUID().uuidString).wav")
                do {
                    try data.write(to: url, options: .atomic)
                    continuation.resume(returning: url)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    private func lastError() -> String {
        guard let pointer = vifasttts_last_error() else {
            return "FFI error"
        }
        return String(cString: pointer)
    }

    private func error(_ message: String) -> NSError {
        NSError(
            domain: "com.vifasttts.mobile",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: message]
        )
    }
}
