param(
    [string]$ModelDir = "",
    [string]$Out = "",
    [string]$Archive = "",
    [string]$OrtVersion = "1.31.1"
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $Here "..")
if (-not $ModelDir) { $ModelDir = Join-Path $Root "artifacts/onnx/n0_q" }
if (-not $Out) { $Out = Join-Path $Root "desktop/dist/vifasttts-server-windows-x64" }
if (-not $Archive) { $Archive = Join-Path $Root "desktop/dist/vifasttts-server-windows-x64.zip" }
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
try { cargo build --release -p vifasttts-http-server; if ($LASTEXITCODE -ne 0) { throw "cargo build failed" } } finally { Pop-Location }
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path (Join-Path $Out "models") | Out-Null
Copy-Item (Join-Path $Root "rust/target/release/vifasttts-server.exe") (Join-Path $Out "vifasttts-server.exe")
Copy-Item (Join-Path $Extract "lib/onnxruntime.dll") (Join-Path $Out "onnxruntime.dll")
Copy-Item $Acoustic (Join-Path $Out "models/acoustic.onnx")
Copy-Item $Vocoder (Join-Path $Out "models/vocoder.onnx")
@"
ViFastTts HTTP server (Windows x64)
Chạy: .\vifasttts-server.exe --acoustic models\acoustic.onnx --vocoder models\vocoder.onnx --port 8000
Model: models\acoustic.onnx + models\vocoder.onnx
ORT: onnxruntime.dll 1.31.1
"@ | Set-Content (Join-Path $Out "README.txt")
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Archive) | Out-Null
if (Test-Path $Archive) { Remove-Item -Force $Archive }
Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $Archive
Write-Output "ARCHIVE: $Archive"
