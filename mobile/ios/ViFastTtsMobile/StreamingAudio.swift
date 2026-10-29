import AVFoundation
import Foundation

/// Huỷ stream từ UI trong khi FFI đang chạy trên serial queue.
final class StreamCancellation: @unchecked Sendable {
    private let lock = NSLock()
    private var value = false

    func cancel() {
        lock.lock()
        value = true
        lock.unlock()
    }

    var isCancelled: Bool {
        lock.lock()
        defer { lock.unlock() }
        return value
    }
}

/// Phát PCM float32 24 kHz theo buffer ngay khi FFI trả chunk.
///
/// Không gom toàn bộ audio vào RAM; WAV (nếu bật) do caller tự gom PCM16.
/// AVAudioEngine tự resample 24 kHz -> sample rate phần cứng.
final class StreamingAudioPlayer {
    private let engine = AVAudioEngine()
    private let player = AVAudioPlayerNode()
    private let format: AVAudioFormat
    private let pending = DispatchGroup()
    private let lock = NSLock()
    private var stopped = false

    init(sampleRate: Double = 24_000) throws {
        guard let format = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: sampleRate,
            channels: 1,
            interleaved: false
        ) else {
            throw StreamAudioError.message("Không tạo được định dạng PCM 24 kHz")
        }
        self.format = format
        engine.attach(player)
        engine.connect(player, to: engine.mainMixerNode, format: format)
        engine.prepare()
        try engine.start()
        player.play()
    }

    /// Nhận đúng số sample float32 từ callback C.
    func feed(_ samples: UnsafePointer<Float>, count: Int) {
        guard count > 0 else { return }
        lock.lock()
        let isStopped = stopped
        lock.unlock()
        guard !isStopped else { return }
        guard let buffer = AVAudioPCMBuffer(
            pcmFormat: format,
            frameCapacity: AVAudioFrameCount(count)
        ) else {
            return
        }
        buffer.frameLength = AVAudioFrameCount(count)
        if let channel = buffer.floatChannelData?[0] {
            channel.update(from: samples, count: count)
        }
        pending.enter()
        player.scheduleBuffer(buffer) { [weak self] in
            self?.pending.leave()
        }
    }

    /// Chờ các buffer đã schedule phát hết rồi đóng engine.
    func finish(timeout: TimeInterval = 8) {
        _ = pending.wait(timeout: .now() + timeout)
        stop()
    }

    /// Dừng ngay (nút Dừng hoặc callback trả cancel).
    func stop() {
        lock.lock()
        if stopped {
            lock.unlock()
            return
        }
        stopped = true
        lock.unlock()
        player.stop()
        engine.stop()
    }

    deinit {
        stop()
    }
}

enum StreamAudioError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let message): return message
        }
    }
}
