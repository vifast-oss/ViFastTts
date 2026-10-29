import AVFoundation
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

/// Kết quả stream: audio đã phát; WAV/phụ đề chỉ có khi bật lưu.
struct StreamResult {
    let wavURL: URL?
    let srtURL: URL?
    let vttURL: URL?
    let karaokeURL: URL?
    let units: [KaraokeUnit]
    let duration: Double
    let cancelled: Bool
}

/// Nhận callback C trên queue tổng hợp; giữ PCM/WAV và đẩy thẳng vào player.
private final class StreamContext: @unchecked Sendable {
    let player: StreamingAudioPlayer
    let saveWav: Bool
    let cancellation: StreamCancellation
    let progress: ((Double) -> Void)?
    private(set) var pcm = Data()
    private(set) var receivedSamples = 0
    private var lastReport = 0.0

    init(
        player: StreamingAudioPlayer,
        saveWav: Bool,
        cancellation: StreamCancellation,
        progress: ((Double) -> Void)?
    ) {
        self.player = player
        self.saveWav = saveWav
        self.cancellation = cancellation
        self.progress = progress
    }

    func receive(_ samples: UnsafePointer<Float>, count: Int, sampleRate: UInt32) -> Int32 {
        guard !cancellation.isCancelled else { return 1 }
        if saveWav {
            var pcm16 = [Int16](repeating: 0, count: count)
            for index in 0..<count {
                let value = samples[index].clamped(to: -1.0...1.0)
                pcm16[index] = Int16((value * 32767.0).rounded())
            }
            pcm16.withUnsafeBytes { pcm.append(contentsOf: $0) }
        }
        player.feed(samples, count: count)
        receivedSamples += count
        if let progress {
            let seconds = Double(receivedSamples) / Double(max(sampleRate, 1))
            if seconds - lastReport >= 0.5 {
                lastReport = seconds
                progress(seconds)
            }
        }
        return 0
    }
}

/// C callback: trả 1 để FFI dừng stream.
private let vifStreamCallback: @convention(c) (
    UnsafePointer<Float>?,
    Int,
    UInt32,
    UnsafeMutableRawPointer?
) -> Int32 = { samples, count, sampleRate, userData in
    guard let samples, let userData, count > 0 else { return 1 }
    let context = Unmanaged<StreamContext>.fromOpaque(userData).takeUnretainedValue()
    return context.receive(samples, count: count, sampleRate: sampleRate)
}

private extension FloatingPoint {
    func clamped(to range: ClosedRange<Self>) -> Self {
        min(max(self, range.lowerBound), range.upperBound)
    }
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
        dictionary: String = "",
        customReading: String = ""
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
                let customJSON = self.customReadingJSON(customReading)
                // Gọi bản `_ex2` để có custom reading + timing.
                let code = text.withCString { cText in
                    dialect.withCString { cDialect in
                        dictionary.withCString { cDictionary in
                            customJSON.withCString { cCustom in
                                vifasttts_synthesize_karaoke_ex2(
                                    engine,
                                    cText,
                                    &options,
                                    cDialect,
                                    resolveOov ? 1 : 0,
                                    cDictionary,
                                    cCustom,
                                    &wavPointer,
                                    &wavLength,
                                    &karaokePointer
                                )
                            }
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
                                customJSON.withCString { cCustom in
                                    vifasttts_synthesize_ex2(
                                        engine,
                                        cText,
                                        &options,
                                        cDialect,
                                        resolveOov ? 1 : 0,
                                        cDictionary,
                                        cCustom,
                                        &plainLength
                                    )
                                }
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

    /// Stream PCM local: phát ngay từng chunk; WAV/phụ đề tuỳ `saveWav`.
    ///
    /// Toàn bộ lời gọi FFI chạy trên serial queue như synthesize() để engine
    /// không bị gọi song song. Huỷ bằng `StreamCancellation`.
    func synthesizeStream(
        text: String,
        speed: Float = 1.0,
        alpha: Float = 1.5,
        maxChars: Int = 300,
        fixedPauses: Bool = false,
        peakNormalize: Bool = false,
        dialect: String = "north",
        resolveOov: Bool = true,
        dictionary: String = "",
        customReading: String = "",
        saveWav: Bool = true,
        cancellation: StreamCancellation,
        progress: ((Double) -> Void)? = nil
    ) async throws -> StreamResult {
        try await withCheckedThrowingContinuation { continuation in
            queue.async {
                guard let engine = self.engine else {
                    continuation.resume(throwing: self.error(self.loadError ?? "Engine chưa nạp"))
                    return
                }
                if cancellation.isCancelled {
                    continuation.resume(returning: StreamResult(
                        wavURL: nil, srtURL: nil, vttURL: nil, karaokeURL: nil,
                        units: [], duration: 0, cancelled: true
                    ))
                    return
                }
                let session = AVAudioSession.sharedInstance()
                try? session.setCategory(.playback, mode: .spokenAudio)
                try? session.setActive(true)
                let player: StreamingAudioPlayer
                do {
                    player = try StreamingAudioPlayer()
                } catch {
                    continuation.resume(throwing: error)
                    return
                }
                let context = StreamContext(
                    player: player,
                    saveWav: saveWav,
                    cancellation: cancellation,
                    progress: progress
                )
                var options = VifasttOptions(
                    speed: speed,
                    alpha: alpha,
                    max_chars: maxChars,
                    fixed_pauses: fixedPauses ? 1 : 0,
                    peak_normalize: peakNormalize ? 1 : 0
                )
                let customJSON = self.customReadingJSON(customReading)
                var karaokePointer: UnsafeMutablePointer<CChar>?
                let opaque = Unmanaged.passUnretained(context).toOpaque()
                let code: Int32 = text.withCString { cText in
                    dialect.withCString { cDialect in
                        dictionary.withCString { cDictionary in
                            customJSON.withCString { cCustom in
                                if saveWav {
                                    return vifasttts_synthesize_stream_karaoke_ex2(
                                        engine,
                                        cText,
                                        &options,
                                        cDialect,
                                        resolveOov ? 1 : 0,
                                        cDictionary,
                                        cCustom,
                                        vifStreamCallback,
                                        opaque,
                                        &karaokePointer
                                    )
                                }
                                return vifasttts_synthesize_stream_ex2(
                                    engine,
                                    cText,
                                    &options,
                                    cDialect,
                                    resolveOov ? 1 : 0,
                                    cDictionary,
                                    cCustom,
                                    vifStreamCallback,
                                    opaque
                                )
                            }
                        }
                    }
                }
                if code < 0 {
                    player.stop()
                    if let karaokePointer { vifasttts_string_free(karaokePointer) }
                    continuation.resume(throwing: self.error(self.lastError()))
                    return
                }
                if code == 1 || cancellation.isCancelled {
                    player.stop()
                    if let karaokePointer { vifasttts_string_free(karaokePointer) }
                    continuation.resume(returning: StreamResult(
                        wavURL: nil, srtURL: nil, vttURL: nil, karaokeURL: nil,
                        units: [], duration: Double(context.receivedSamples) / 24_000.0,
                        cancelled: true
                    ))
                    return
                }
                player.finish()
                var karaokeJSON: String?
                if let karaokePointer {
                    karaokeJSON = String(cString: karaokePointer)
                    vifasttts_string_free(karaokePointer)
                }
                let base = FileManager.default.temporaryDirectory
                    .appendingPathComponent("vifasttts-stream-\(UUID().uuidString)")
                var wavURL: URL?
                var srtURL: URL?
                var vttURL: URL?
                var karaokeURL: URL?
                var units: [KaraokeUnit] = []
                do {
                    if saveWav, !context.pcm.isEmpty {
                        guard let wav = self.wavData(
                            pcm: context.pcm,
                            sampleRate: 24_000,
                            channels: 1
                        ) else {
                            throw self.error("Không dựng được WAV stream")
                        }
                        let url = base.appendingPathExtension("wav")
                        try wav.write(to: url, options: .atomic)
                        wavURL = url
                    }
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
                    continuation.resume(returning: StreamResult(
                        wavURL: wavURL,
                        srtURL: srtURL,
                        vttURL: vttURL,
                        karaokeURL: karaokeURL,
                        units: units,
                        duration: Double(context.receivedSamples) / 24_000.0,
                        cancelled: false
                    ))
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    /// Dựng WAV PCM16 bằng Rust để Android/iOS không tự viết header khác nhau.
    private func wavData(pcm: Data, sampleRate: UInt32, channels: UInt16) -> Data? {
        var out: UnsafeMutablePointer<UInt8>?
        var outLen = 0
        let code = pcm.withUnsafeBytes { raw -> Int32 in
            guard let base = raw.bindMemory(to: UInt8.self).baseAddress else { return -1 }
            return vifasttts_wav_from_pcm16(
                base,
                raw.count,
                sampleRate,
                channels,
                &out,
                &outLen
            )
        }
        guard code == 0, let out, outLen > 0 else { return nil }
        defer { vifasttts_buffer_free(out, outLen) }
        return Data(bytes: out, count: outLen)
    }

    /// Parse `cụm = cách đọc` thành JSON map cho C ABI.
    private func customReadingJSON(_ text: String) -> String {
        var map: [String: String] = [:]
        for rawLine in text.split(separator: "\n") {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            if line.isEmpty || line.hasPrefix("#") { continue }
            guard let separator = line.firstIndex(of: "=") else { continue }
            let key = line[..<separator].trimmingCharacters(in: .whitespaces)
            let value = line[line.index(after: separator)...]
                .trimmingCharacters(in: .whitespaces)
            if !key.isEmpty && !value.isEmpty {
                map[key] = value
            }
        }
        guard let data = try? JSONSerialization.data(withJSONObject: map),
              let json = String(data: data, encoding: .utf8) else {
            return "{}"
        }
        return json
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
