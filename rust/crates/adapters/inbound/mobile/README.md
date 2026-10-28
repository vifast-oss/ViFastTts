# vifasttts-mobile — mobile runtime

Đây là **composition root** cho iOS/Android, không phải UI và không phải FFI.

```text
UI SwiftUI / Compose / Flutter
  → UniFFI / C ABI
      → vifasttts-mobile::MobileRuntime
          → vifasttts-native::NativeEngine
          → model source / audio sink
```

## Khác gì `vifasttts-ffi`?

| Crate | Vai trò |
|---|---|
| `adapters/inbound/ffi` | C ABI: opaque pointer, functions, callbacks |
| `adapters/inbound/mobile` | lifecycle/composition: model, status, synth, audio sink |

- FFI là **cửa vào**.
- Mobile runtime là **bộ điều phối** phía sau cửa.
- Desktop cũng dùng được FFI; mobile runtime chỉ dành cho app mobile.

## API hiện tại

```rust
MobileRuntime::from_paths(...)
MobileRuntime::from_bytes(...)
MobileRuntime::from_source(&impl ModelSource, ...)
runtime.info()
runtime.status()
runtime.synthesize(text, &SynthesisOptions)
runtime.synthesize_to_sink(text, &SynthesisOptions, &mut impl AudioSink)
```

- `from_bytes` cho model trong app asset/download.
- `ModelSource` port cho cache/asset.
- `AudioSink` port cho AVAudioEngine/AAudio.
- Không biết SwiftUI/Compose/Flutter.

## Build

```bash
cargo build --release -p vifasttts-mobile
```

iOS/Android vẫn cần:

- ORT mobile static/dynamic library;
- `-p vifasttts-ffi` nếu muốn C ABI;
- XCFramework/NDK packaging;
- audio sink adapter cụ thể;
- model asset + quantization.

## Chưa có

- UniFFI/Swift/Kotlin bindings.
- AVAudioEngine/AAudio implementation.
- foreground/background audio session.
- XCFramework/NDK scripts.
- Flutter bridge.
- thiết bị thật/benchmark.
