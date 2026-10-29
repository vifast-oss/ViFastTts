param(
    [string]$ModelDir = "",
    [string]$Out = "",
    [string]$Archive = "",
    [string]$OrtVersion = "1.31.1",
    [string]$WebDir = ""
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $Here "..")
if (-not $ModelDir) { $ModelDir = Join-Path $Root "artifacts/onnx/n0_q" }
if (-not $Out) { $Out = Join-Path $Root "desktop/dist/vifasttts-cli-windows-x64" }
if (-not $Archive) { $Archive = Join-Path $Root "desktop/dist/vifasttts-cli-windows-x64.zip" }
if (-not $WebDir) {
    $candidate = Join-Path $Root "web/dist"
    if (Test-Path $candidate) { $WebDir = $candidate }
} elseif (-not [System.IO.Path]::IsPathRooted($WebDir)) {
    $WebDir = Join-Path $Root $WebDir
}
if ($WebDir -and -not (Test-Path $WebDir)) { throw "Thiếu web dir: $WebDir" }
$Acoustic = Join-Path $ModelDir "acoustic.onnx"
$Vocoder = Join-Path $ModelDir "vocoder.onnx"
if (-not (Test-Path $Acoustic)) { throw "Thiếu $Acoustic" }
if (-not (Test-Path $Vocoder)) { throw "Thiếu $Vocoder" }
$Cache = Join-Path $Root "desktop/dist/cache"
New-Item -ItemType Directory -Force -Path $Cache | Out-Null
$Zip = Join-Path $Cache "onnxruntime-win-x64-$OrtVersion.zip"
if (-not (Test-Path $Zip)) {
    Invoke-WebRequest -Uri "https://github.com/microsoft/onnxruntime/releases/download/v$OrtVersion/onnxruntime-win-x64-$OrtVersion.zip" -OutFile $Zip
}
$Extract = Join-Path $Cache "onnxruntime-win-x64-$OrtVersion"
if (-not (Test-Path $Extract)) { Expand-Archive -Path $Zip -DestinationPath $Cache -Force }
Push-Location (Join-Path $Root "rust")
try { cargo build --release -p vifasttts-cli; if ($LASTEXITCODE -ne 0) { throw "cargo build failed" } } finally { Pop-Location }
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path (Join-Path $Out "models") | Out-Null
Copy-Item (Join-Path $Root "rust/target/release/vifasttts.exe") (Join-Path $Out "vifasttts.exe")
Copy-Item (Join-Path $Extract "lib/onnxruntime.dll") (Join-Path $Out "onnxruntime.dll")
Copy-Item $Acoustic (Join-Path $Out "models/acoustic.onnx")
Copy-Item $Vocoder (Join-Path $Out "models/vocoder.onnx")
if ($WebDir -and (Test-Path $WebDir)) {
    Copy-Item -Recurse -Force $WebDir (Join-Path $Out "web")
    Remove-Item -Recurse -Force (Join-Path $Out "web/models") -ErrorAction SilentlyContinue
}
@"
ViFastTts CLI/TUI/server (Windows x64)
Chạy server: .\vifasttts.exe server --acoustic models\acoustic.onnx --vocoder models\vocoder.onnx --port 8000
TUI local: .\vifasttts.exe tui --acoustic models\acoustic.onnx --vocoder models\vocoder.onnx
TUI remote: .\vifasttts.exe tui --server http://127.0.0.1:8000
CLI: .\vifasttts.exe synth --text "..." --output out.wav
Web UI: thêm --web-dir web nếu có thư mục web.
Model: models\acoustic.onnx + models\vocoder.onnx
ORT: onnxruntime.dll 1.31.1
"@ | Set-Content (Join-Path $Out "README.txt")
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Archive) | Out-Null
if (Test-Path $Archive) { Remove-Item -Force $Archive }
Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $Archive
Write-Output "ARCHIVE: $Archive"
