import Foundation

/// Cầu nối Swift ↔ hợp đồng Rust `vifasttts-app` (sample/ETA).
///
/// Không chứa logic UI; chỉ đọc/ghi JSON qua C ABI để defaults/sample/ETA không
/// bị viết lại lần thứ tư trong Swift.
struct EtaSample: Codable {
    let mode: String
    let chars: Int
    let elapsed_ms: Int
    /// Chỉ phục vụ lịch sử UI; Rust EtaSample bỏ qua field lạ.
    let text: String?
}

struct SharedSampleText: Decodable {
    let id: String
    let label: String
    let text: String
    let isDefault: Bool

    enum CodingKeys: String, CodingKey {
        case id, label, text
        case isDefault = "default"
    }
}

struct SharedSamples: Decodable {
    let defaultText: String
    let samples: [SharedSampleText]

    enum CodingKeys: String, CodingKey {
        case samples
        case defaultText = "default"
    }
}

enum SharedContract {
    private static let historyKey = "vifasttts.history.v1"
    private static let historyLimit = 20

    private static func take(_ pointer: UnsafeMutablePointer<CChar>?) -> String? {
        guard let pointer else { return nil }
        defer { vifasttts_string_free(pointer) }
        return String(cString: pointer)
    }

    static func samplePayload(platform: String) -> SharedSamples? {
        let raw = platform.withCString { value in
            take(vifasttts_sample_texts_json(value))
        }
        guard let raw else { return nil }
        return try? JSONDecoder().decode(SharedSamples.self, from: Data(raw.utf8))
    }

    static func defaultText(platform: String) -> String {
        samplePayload(platform: platform)?.defaultText
            ?? "Xin chào, đây là bản iOS của ViFastTts."
    }

    static func eta(history: [EtaSample], mode: String, chars: Int) -> Int? {
        guard chars > 0,
              let data = try? JSONEncoder().encode(history),
              let json = String(data: data, encoding: .utf8) else {
            return nil
        }
        let raw = json.withCString { historyJSON in
            mode.withCString { modeJSON in
                take(vifasttts_eta_estimate_json(
                    historyJSON,
                    modeJSON,
                    UInt32(chars),
                    UInt32(historyLimit)
                ))
            }
        }
        guard let raw, raw != "null" else { return nil }
        return Int(raw)
    }

    static func loadHistory() -> [EtaSample] {
        guard let data = UserDefaults.standard.data(forKey: historyKey) else { return [] }
        return (try? JSONDecoder().decode([EtaSample].self, from: data)) ?? []
    }

    static func saveHistory(_ samples: [EtaSample]) {
        let trimmed = Array(samples.suffix(historyLimit))
        guard let data = try? JSONEncoder().encode(trimmed) else { return }
        UserDefaults.standard.set(data, forKey: historyKey)
    }

    static func record(mode: String, chars: Int, elapsedMs: Int, text: String) -> [EtaSample] {
        var history = loadHistory()
        history.append(EtaSample(
            mode: mode,
            chars: chars,
            elapsed_ms: elapsedMs,
            text: String(text.prefix(500))
        ))
        history = Array(history.suffix(historyLimit))
        saveHistory(history)
        return history
    }
}
