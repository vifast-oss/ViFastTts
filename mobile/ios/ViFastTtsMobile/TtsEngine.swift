import Foundation

struct KaraokeUnit: Decodable, Identifiable {
    let text: String
    let start_ms: Int
    let end_ms: Int
    var id: String { "\(start_ms)-\(end_ms)-\(text)" }
}

struct KaraokeDoc: Decodable {
    let units: [KaraokeUnit]
}

/// Kết quả một lần tổng hợp: WAV + phụ đề + timing karaoke.
struct TtsResult {
    let wavURL: URL
    let srtURL: URL?
    let vttURL: URL?
    let karaokeURL: URL?
    let units: [KaraokeUnit]
}

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
        peakNormalize: Bool = false,
        dialect: String = "north",
        resolveOov: Bool = true,
        dictionary: String = ""
    ) async throws -> TtsResult {
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
                var wavPointer: UnsafeMutablePointer<UInt8>?
                var wavLength = 0
                var karaokePointer: UnsafeMutablePointer<CChar>?
                // Gọi bản `_ex` để có đủ phương ngữ/OOV/từ điển và timing.
                let code = text.withCString { cText in
                    dialect.withCString { cDialect in
                        dictionary.withCString { cDictionary in
                            vifasttts_synthesize_karaoke_ex(
                                engine,
                                cText,
                                &options,
                                cDialect,
                                resolveOov ? 1 : 0,
                                cDictionary,
                                &wavPointer,
                                &wavLength,
                                &karaokePointer
                            )
                        }
                    }
                }

                var wavData: Data?
                var karaokeJSON: String?
                if code == 0, let pointer = wavPointer, wavLength > 0 {
                    wavData = Data(bytes: pointer, count: wavLength)
                    vifasttts_buffer_free(pointer, wavLength)
                    if let jsonPointer = karaokePointer {
                        karaokeJSON = String(cString: jsonPointer)
                        vifasttts_string_free(jsonPointer)
                    }
                } else {
                    if let jsonPointer = karaokePointer {
                        vifasttts_string_free(jsonPointer)
                    }
                    // Model không xuất timing vẫn đọc được; chỉ thiếu phụ đề.
                    var plainLength = 0
                    let plain = text.withCString { cText in
                        dialect.withCString { cDialect in
                            dictionary.withCString { cDictionary in
                                vifasttts_synthesize_ex(
                                    engine,
                                    cText,
                                    &options,
                                    cDialect,
                                    resolveOov ? 1 : 0,
                                    cDictionary,
                                    &plainLength
                                )
                            }
                        }
                    }
                    guard let plain, plainLength > 0 else {
                        continuation.resume(throwing: self.error(self.lastError()))
                        return
                    }
                    wavData = Data(bytes: plain, count: plainLength)
                    vifasttts_buffer_free(plain, plainLength)
                }

                guard let wavData, !wavData.isEmpty else {
                    continuation.resume(throwing: self.error(self.lastError()))
                    return
                }

                let base = FileManager.default.temporaryDirectory
                    .appendingPathComponent("vifasttts-\(UUID().uuidString)")
                let wavURL = base.appendingPathExtension("wav")
                do {
                    try wavData.write(to: wavURL, options: .atomic)
                    var srtURL: URL?
                    var vttURL: URL?
                    var karaokeURL: URL?
                    var units: [KaraokeUnit] = []
                    if let karaokeJSON {
                        if let data = karaokeJSON.data(using: .utf8),
                           let doc = try? JSONDecoder().decode(KaraokeDoc.self, from: data) {
                            units = doc.units
                        }
                        srtURL = self.writeSubtitle(karaokeJSON, base: base, extension: "srt", srt: true)
                        vttURL = self.writeSubtitle(karaokeJSON, base: base, extension: "vtt", srt: false)
                        let jsonURL = base.appendingPathExtension("karaoke.json")
                        if (try? karaokeJSON.write(to: jsonURL, atomically: true, encoding: .utf8)) != nil {
                            karaokeURL = jsonURL
                        }
                    }
                    continuation.resume(returning: TtsResult(
                        wavURL: wavURL,
                        srtURL: srtURL,
                        vttURL: vttURL,
                        karaokeURL: karaokeURL,
                        units: units
                    ))
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    private func writeSubtitle(
        _ json: String,
        base: URL,
        extension ext: String,
        srt: Bool
    ) -> URL? {
        let pointer = json.withCString { cJSON in
            srt ? vifasttts_karaoke_to_srt(cJSON) : vifasttts_karaoke_to_vtt(cJSON)
        }
        guard let pointer else { return nil }
        defer { vifasttts_string_free(pointer) }
        let text = String(cString: pointer)
        guard !text.isEmpty else { return nil }
        let url = base.appendingPathExtension(ext)
        do {
            try text.write(to: url, atomically: true, encoding: .utf8)
            return url
        } catch {
            return nil
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
