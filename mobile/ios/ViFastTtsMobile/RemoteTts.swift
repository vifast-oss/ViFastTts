import Foundation

struct RemoteTtsResult {
    let wavURL: URL
    let srtURL: URL?
    let vttURL: URL?
    let units: [KaraokeUnit]
}

struct RemoteStreamResult {
    let wavURL: URL?
    let srtURL: URL?
    let vttURL: URL?
    let karaokeURL: URL?
    let units: [KaraokeUnit]
    let duration: Double
    let cancelled: Bool
}

/// Gọi server Rust/Python qua `/api/tts`, trả WAV + phụ đề tạm để phát/chia sẻ.
struct RemoteTtsClient {
    let baseURL: URL
    let token: String

    init(server: String, token: String) throws {
        let trimmed = server.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: trimmed), !trimmed.isEmpty else {
            throw RemoteTtsError.message("Server URL không hợp lệ")
        }
        self.baseURL = url
        self.token = token.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var endpoint: URL {
        if baseURL.path.hasSuffix("/api/tts") {
            return baseURL
        }
        return baseURL.appendingPathComponent("api").appendingPathComponent("tts")
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
    ) async throws -> RemoteTtsResult {
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.timeoutInterval = 120
        request.setValue("application/json; charset=utf-8", forHTTPHeaderField: "Content-Type")
        if !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let body: [String: Any] = [
            "text": text,
            "speed": Double(speed),
            "alpha": Double(alpha),
            "max_chars": maxChars,
            "fixed_pauses": fixedPauses,
            "peak_normalize": peakNormalize,
            "dialect": dialect,
            "resolve_oov": resolveOov,
            "dictionary": dictionary,
            "custom_reading": parseCustomReading(customReading),
            "karaoke": true,
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw RemoteTtsError.message("Server không trả HTTP")
        }
        guard (200..<300).contains(http.statusCode) else {
            let detail = String(data: data, encoding: .utf8) ?? ""
            throw RemoteTtsError.message("HTTP \(http.statusCode): \(detail)")
        }

        let base = FileManager.default.temporaryDirectory
            .appendingPathComponent("vifasttts-remote-\(UUID().uuidString)")
        let contentType = http.value(forHTTPHeaderField: "Content-Type") ?? ""
        if contentType.contains("application/json") {
            struct Payload: Decodable {
                let audio_base64: String
                let srt: String?
                let vtt: String?
                let vtt_karaoke: String?
                let karaoke: KaraokeDoc?
            }
            let payload = try JSONDecoder().decode(Payload.self, from: data)
            guard let wav = Data(base64Encoded: payload.audio_base64) else {
                throw RemoteTtsError.message("audio_base64 hỏng")
            }
            let wavURL = base.appendingPathExtension("wav")
            try wav.write(to: wavURL, options: .atomic)
            var srtURL: URL?
            var vttURL: URL?
            if let srt = payload.srt, !srt.isEmpty {
                let url = base.appendingPathExtension("srt")
                try srt.write(to: url, atomically: true, encoding: .utf8)
                srtURL = url
            }
            let vttText = payload.vtt ?? payload.vtt_karaoke ?? ""
            if !vttText.isEmpty {
                let url = base.appendingPathExtension("vtt")
                try vttText.write(to: url, atomically: true, encoding: .utf8)
                vttURL = url
            }
            return RemoteTtsResult(
                wavURL: wavURL,
                srtURL: srtURL,
                vttURL: vttURL,
                units: payload.karaoke?.units ?? []
            )
        }

        // Server cũ trả WAV trực tiếp.
        guard !data.isEmpty else {
            throw RemoteTtsError.message("Server trả audio rỗng")
        }
        let wavURL = base.appendingPathExtension("wav")
        try data.write(to: wavURL, options: .atomic)
        return RemoteTtsResult(wavURL: wavURL, srtURL: nil, vttURL: nil, units: [])
    }
    /// Stream NDJSON từ server Rust; server Python cũ trả 404 thì caller fallback.
    func stream(
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
    ) async throws -> RemoteStreamResult {
        var request = URLRequest(url: endpoint.appendingPathComponent("stream"))
        request.httpMethod = "POST"
        request.timeoutInterval = 180
        request.setValue("application/json; charset=utf-8", forHTTPHeaderField: "Content-Type")
        if !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let body: [String: Any] = [
            "text": text,
            "speed": Double(speed),
            "alpha": Double(alpha),
            "max_chars": maxChars,
            "fixed_pauses": fixedPauses,
            "peak_normalize": peakNormalize,
            "dialect": dialect,
            "resolve_oov": resolveOov,
            "dictionary": dictionary,
            "custom_reading": parseCustomReading(customReading),
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw RemoteTtsError.message("Server không trả HTTP")
        }
        guard (200..<300).contains(http.statusCode) else {
            throw RemoteTtsError.message("HTTP \(http.statusCode): server không hỗ trợ stream")
        }

        let player = try StreamingAudioPlayer()
        var pcm = Data()
        var rawUnits: [Any] = []
        var duration = 0.0
        var cancelled = false
        for try await line in bytes.lines {
            if cancellation.isCancelled {
                cancelled = true
                break
            }
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty { continue }
            guard let data = trimmed.data(using: .utf8),
                  let event = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let type = event["type"] as? String else {
                continue
            }
            switch type {
            case "audio":
                guard let encoded = event["pcm_base64"] as? String,
                      let chunk = Data(base64Encoded: encoded), !chunk.isEmpty else {
                    continue
                }
                if saveWav { pcm.append(chunk) }
                let floats = Self.floats(fromPCM16: chunk)
                floats.withUnsafeBufferPointer { buffer in
                    if let base = buffer.baseAddress {
                        player.feed(base, count: buffer.count)
                    }
                }
                let rate = Double(event["sample_rate"] as? Int ?? 24_000)
                duration += Double(chunk.count / 2) / max(rate, 1)
                progress?(duration)
            case "units":
                if let units = event["units"] as? [Any] {
                    rawUnits.append(contentsOf: units)
                }
            case "done":
                if let samples = event["samples"] as? Int,
                   let rate = event["sample_rate"] as? Int, rate > 0 {
                    duration = Double(samples) / Double(rate)
                }
            case "error":
                player.stop()
                throw RemoteTtsError.message(event["message"] as? String ?? "Server stream lỗi")
            default:
                break
            }
        }
        if cancelled || cancellation.isCancelled {
            player.stop()
            return RemoteStreamResult(
                wavURL: nil, srtURL: nil, vttURL: nil, karaokeURL: nil,
                units: [], duration: duration, cancelled: true
            )
        }
        player.finish()
        let base = FileManager.default.temporaryDirectory
            .appendingPathComponent("vifasttts-remote-stream-\(UUID().uuidString)")
        var wavURL: URL?
        var srtURL: URL?
        var vttURL: URL?
        var karaokeURL: URL?
        var units: [KaraokeUnit] = []
        var karaokeJSON: String?
        if !rawUnits.isEmpty {
            let unitsData = try JSONSerialization.data(withJSONObject: rawUnits)
            let unitsJSON = String(data: unitsData, encoding: .utf8) ?? "[]"
            karaokeJSON = unitsJSON.withCString {
                guard let pointer = vifasttts_karaoke_from_units_json(
                    $0, 24_000, UInt64(duration * 1000), 80
                ) else { return nil }
                defer { vifasttts_string_free(pointer) }
                return String(cString: pointer)
            }
        }
        if saveWav, !pcm.isEmpty, let wav = Self.wavData(pcm: pcm) {
            let url = base.appendingPathExtension("wav")
            try wav.write(to: url, options: .atomic)
            wavURL = url
        }
        if let karaokeJSON {
            if let data = karaokeJSON.data(using: .utf8),
               let doc = try? JSONDecoder().decode(KaraokeDoc.self, from: data) {
                units = doc.units
            }
            srtURL = Self.writeSubtitle(karaokeJSON, base: base, ext: "srt", srt: true)
            vttURL = Self.writeSubtitle(karaokeJSON, base: base, ext: "vtt", srt: false)
            let jsonURL = base.appendingPathExtension("karaoke.json")
            if (try? karaokeJSON.write(to: jsonURL, atomically: true, encoding: .utf8)) != nil {
                karaokeURL = jsonURL
            }
        }
        return RemoteStreamResult(
            wavURL: wavURL,
            srtURL: srtURL,
            vttURL: vttURL,
            karaokeURL: karaokeURL,
            units: units,
            duration: duration,
            cancelled: false
        )
    }

    private static func floats(fromPCM16 data: Data) -> [Float] {
        var values = [Float](repeating: 0, count: data.count / 2)
        data.withUnsafeBytes { raw in
            let samples = raw.bindMemory(to: Int16.self)
            for index in 0..<values.count {
                values[index] = Float(samples[index]) / 32768.0
            }
        }
        return values
    }

    private static func wavData(pcm: Data) -> Data? {
        var out: UnsafeMutablePointer<UInt8>?
        var outLen = 0
        let code = pcm.withUnsafeBytes { raw -> Int32 in
            guard let base = raw.bindMemory(to: UInt8.self).baseAddress else { return -1 }
            return vifasttts_wav_from_pcm16(base, raw.count, 24_000, 1, &out, &outLen)
        }
        guard code == 0, let out, outLen > 0 else { return nil }
        defer { vifasttts_buffer_free(out, outLen) }
        return Data(bytes: out, count: outLen)
    }

    private static func writeSubtitle(
        _ json: String,
        base: URL,
        ext: String,
        srt: Bool
    ) -> URL? {
        let pointer = json.withCString {
            srt ? vifasttts_karaoke_to_srt($0) : vifasttts_karaoke_to_vtt($0)
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

    private func parseCustomReading(_ text: String) -> [String: String] {
        var map: [String: String] = [:]
        for rawLine in text.split(separator: "\n") {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            if line.isEmpty || line.hasPrefix("#") { continue }
            guard let separator = line.firstIndex(of: "=") else { continue }
            let key = line[..<separator].trimmingCharacters(in: .whitespaces)
            let value = line[line.index(after: separator)...]
                .trimmingCharacters(in: .whitespaces)
            if !key.isEmpty && !value.isEmpty { map[key] = value }
        }
        return map
    }
}

enum RemoteTtsError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let message): return message
        }
    }
}
