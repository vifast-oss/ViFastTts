# Đóng gói desktop Windows x64: binary + ORT + model.
[CmdletBinding()]
param(
    [string]$ModelDir = "",
    [string]$Out = "",
    [string]$Archive = "",
    [string]$OrtLib = "",
    [string]$OrtVersion = "1.31.1",
    # Bắt buộc có để CI truyền -WebDir; thiếu tham số này gói desktop Windows
    # từng bị rơi mất web/ (v0.3.4) và nhỏ hơn gói CLI.
    [string]$WebDir = ""
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $Here "../../../../..")
if (-not $ModelDir) { $ModelDir = Join-Path $Root "artifacts/onnx/n0_q" }
if (-not $Out) { $Out = Join-Path $Root "desktop/dist/vifasttts-desktop-windows-x64" }
if (-not $Archive) { $Archive = Join-Path $Root "desktop/dist/vifasttts-desktop-windows-x64.zip" }
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

if (-not $OrtLib -or -not (Test-Path $OrtLib)) {
    $Cache = Join-Path $Root "desktop/dist/cache"
    New-Item -ItemType Directory -Force -Path $Cache | Out-Null
    $Zip = Join-Path $Cache "onnxruntime-win-x64-$OrtVersion.zip"
    if (-not (Test-Path $Zip)) {
        Invoke-WebRequest -Uri "https://github.com/microsoft/onnxruntime/releases/download/v$OrtVersion/onnxruntime-win-x64-$OrtVersion.zip" -OutFile $Zip
    }
    $Extract = Join-Path $Cache "onnxruntime-win-x64-$OrtVersion"
    if (-not (Test-Path $Extract)) {
        Expand-Archive -Path $Zip -DestinationPath $Cache -Force
    }
    $OrtLib = Join-Path $Extract "lib/onnxruntime.dll"
}
if (-not (Test-Path $OrtLib)) { throw "Thiếu ORT: $OrtLib" }

Push-Location (Join-Path $Root "rust")
try {
    cargo build --release -p vifasttts-desktop -p vifasttts-cli
    if ($LASTEXITCODE -ne 0) { throw "cargo build failed" }
} finally {
    Pop-Location
}

if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force -Path (Join-Path $Out "models") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Out "licenses") | Out-Null
Copy-Item (Join-Path $Root "rust/target/release/vifasttts-desktop.exe") (Join-Path $Out "vifasttts-desktop.exe")
Copy-Item (Join-Path $Root "rust/target/release/vifasttts.exe") (Join-Path $Out "vifasttts.exe")
if ($WebDir -and (Test-Path $WebDir)) {
    Copy-Item -Recurse -Force $WebDir (Join-Path $Out "web")
    Remove-Item -Recurse -Force (Join-Path $Out "web/models") -ErrorAction SilentlyContinue
    if (-not (Test-Path (Join-Path $Out "web/index.html"))) {
        throw "Gói desktop Windows thiếu web/index.html sau khi copy"
    }
}
Copy-Item $OrtLib (Join-Path $Out "onnxruntime.dll")
Copy-Item $Acoustic (Join-Path $Out "models/acoustic.onnx")
Copy-Item $Vocoder (Join-Path $Out "models/vocoder.onnx")
Copy-Item (Join-Path $Root "resources/brand/vifasttts-icon-512.png") (Join-Path $Out "icon.png")
Copy-Item (Join-Path $Root "resources/fonts/BeVietnamPro-OFL.txt") (Join-Path $Out "licenses/BeVietnamPro-OFL.txt")
@"
ViFastTts Desktop + unified CLI/TUI/server sidecar (Windows x64)
Chạy GUI: vifasttts-desktop.exe
TUI (terminal): vifasttts.exe tui --acoustic models\acoustic.onnx --vocoder models\vocoder.onnx
Server + web: vifasttts.exe server --acoustic models\acoustic.onnx --vocoder models\vocoder.onnx --port 8000
CLI: vifasttts.exe synth --text "..." --output out.wav
Kiểm tra headless: vifasttts-desktop.exe --smoke
Model: models\acoustic.onnx + models\vocoder.onnx
ORT: onnxruntime.dll (1.31.1, load-dynamic)
"@ | Set-Content (Join-Path $Out "README.txt")

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Archive) | Out-Null
if (Test-Path $Archive) { Remove-Item -Force $Archive }
Compress-Archive -Path (Join-Path $Out "*") -DestinationPath $Archive
Write-Output "ARCHIVE: $Archive"
Write-Output "DIR: $Out"
