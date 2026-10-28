# ONNX Runtime library

Thư mục này chứa thư viện ONNX Runtime **1.31.1** dùng bởi `load-dynamic`
(không commit file nhị phân; đã gitignore).

macOS arm64:

```bash
cp .venv-demo/lib/python3.12/site-packages/onnxruntime/capi/libonnxruntime.1.31.1.dylib \
  rust/lib/libonnxruntime.dylib
```

Linux x64 (tải từ release ONNX Runtime 1.31.1):

```bash
curl -L -o /tmp/ort.tgz \
  https://github.com/microsoft/onnxruntime/releases/download/v1.31.1/onnxruntime-linux-x64-1.31.1.tgz
tar -xzf /tmp/ort.tgz -C /tmp
cp /tmp/onnxruntime-linux-x64-1.31.1/lib/libonnxruntime.so* rust/lib/
```

Windows x64: chép `onnxruntime.dll` vào `rust/lib/`.

Binary tìm theo thứ tự: `VIFASTT_ORT_DYLIB`, `ORT_DYLIB_PATH`, `rust/lib/`,
thư mục chứa binary. Khi phát hành, đóng gói thư viện cạnh binary/app.
