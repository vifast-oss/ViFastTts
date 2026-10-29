import Foundation

/// Cầu nối mỏng sang C ABI `vifasttts-ffi`.
///
/// Engine không thread-safe; mọi lời gọi đi qua serial queue. UI không gọi
/// trực tiếp C, tránh block main thread khi model/synth chậm.
final class TtsEngine: @unchecked Sendable {
    static let shared = TtsEngine()
    static let activeModelKey = "vifasttts.activeModelPath"

    private let queue = DispatchQueue(label: "com.vifasttts.tts")
    private var engine: UnsafeMutableRawPointer?
    private(set) var isReady = false
    private(set) var activeModel: String = ""
    private var loadError: String?

    private init() {
        let stored = UserDefaults.standard.string(forKey: Self.activeModelKey) ?? ""
        if !stored.isEmpty, FileManager.default.fileExists(atPath: stored) {
            do {
                try loadLocked(at: URL(fileURLWithPath: stored))
                activeModel = URL(fileURLWithPath: stored).lastPathComponent
                return
            } catch {
                loadError = error.localizedDescription
            }
        }
        loadBundled()
    }

    deinit {
        if let engine {
            vifasttts_engine_free(engine)
        }
    }

    func synthesize(
        text: String,
        speed: Float = 1.0,
        alpha: Float = 1.5,
        maxChars: Int = 300,
        fixedPauses: Bool = false,
        peakNormalize: Bool = false
    ) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            queue.async {
                guard let engine = self.engine else {
                    continuation.resume(throwing: self.error(self.loadError ?? "Engine chưa nạp"))
                    return
                }
                var options = VifasttOptions(
                    speed: speed,
                    alpha: alpha,
                    max_chars: maxChars,
                    fixed_pauses: fixedPauses ? 1 : 0,
                    peak_normalize: peakNormalize ? 1 : 0
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

    /// Nạp bundle `.vfa`/`.vfts` đã tải và ghi nhớ cho lần mở app sau.
    func loadModel(at url: URL) async throws {
        try await withCheckedThrowingContinuation { continuation in
            queue.async {
                do {
                    try self.loadLocked(at: url)
                    UserDefaults.standard.set(url.path, forKey: Self.activeModelKey)
                    self.activeModel = url.lastPathComponent
                    self.loadError = nil
                    continuation.resume()
                } catch {
                    self.loadError = error.localizedDescription
                    print("ViFastTts: đổi model lỗi: \(self.loadError)")
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    private func loadBundled() {
        isReady = false
        guard
            let acoustic = Bundle.main.url(forResource: "acoustic", withExtension: "onnx"),
            let vocoder = Bundle.main.url(forResource: "vocoder", withExtension: "onnx")
        else {
            loadError = "Thiếu acoustic.onnx/vocoder.onnx trong app bundle"
            print("ViFastTts: \(loadError)")
            return
        }
        engine = vifasttts_engine_new(acoustic.path, vocoder.path)
        if engine == nil {
            loadError = lastError()
            print("ViFastTts: nạp model lỗi: \(loadError)")
        } else {
            isReady = true
            activeModel = "Bundled acoustic/vocoder"
        }
    }

    private func loadLocked(at url: URL) throws {
        isReady = false
        if let engine {
            vifasttts_engine_free(engine)
            self.engine = nil
        }
        let path = url.path
        if path.hasSuffix(".vfts") {
            engine = vifasttts_engine_new_vfts(path)
        } else if path.hasSuffix(".vfa") {
            guard let vocoder = Bundle.main.url(forResource: "vocoder", withExtension: "onnx") else {
                throw error("Thiếu vocoder.onnx trong app bundle cho .vfa")
            }
            engine = vifasttts_engine_new_vfa(path, vocoder.path)
        } else {
            throw error("Bundle phải là .vfa hoặc .vfts")
        }
        if engine == nil {
            throw error(lastError())
        }
        isReady = true
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
