#requires -Version 5.1
<#
  Quickstart N0 trên Windows PowerShell:
    powershell -ExecutionPolicy Bypass -File .\scripts\run_ngochuyen_demo.ps1
  Mở http://127.0.0.1:8090
#>
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv-demo"
$Models = Join-Path $Root "artifacts\onnx\n0_q"
$Base = "https://huggingface.co/dvchd/vifasttts-ngochuyen-small/resolve/main/onnx"
$AcousticUrl = "$Base/acoustic.onnx"
$VocoderUrl = "$Base/vocoder.onnx"
$AcousticSha = "df61599a15984dccbf61c37d616258d22fc1af79abc681926e74142de7a376a3"
$VocoderSha = "b3eb09cf5c3baac334b1c0bbea070d02e33e55572e3755865b986cd05cf6b03f"

function Resolve-Python {
    $candidates = @()
    if ($env:PYTHON) { $candidates += ,@($env:PYTHON) }
    $candidates += ,@("py", "-3.12")
    $candidates += ,@("py", "-3.11")
    $candidates += ,@("python")
    foreach ($candidate in $candidates) {
        $exe = [string]$candidate[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $prefix = @()
        if ($candidate.Count -gt 1) { $prefix = @($candidate[1..($candidate.Count - 1)]) }
        & $exe @prefix -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @{ Exe = $exe; Prefix = $prefix }
        }
    }
    throw "Cần Python >= 3.11. Cài Python 3.12 rồi đặt PYTHON=C:\path\python.exe nếu cần."
}

Set-Location $Root
$py = Resolve-Python

if (-not ((Test-Path (Join-Path $Models "acoustic.onnx")) -and
          (Test-Path (Join-Path $Models "vocoder.onnx")))) {
    Write-Host "Tải ONNX N0 Q-init từ HuggingFace..."
    $tmp = Join-Path $env:TEMP ("n0_onnx_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    $acoustic = Join-Path $tmp "acoustic.onnx"
    $vocoder = Join-Path $tmp "vocoder.onnx"
    Invoke-WebRequest -Uri $AcousticUrl -OutFile $acoustic
    Invoke-WebRequest -Uri $VocoderUrl -OutFile $vocoder
    if ((Get-FileHash -Path $acoustic -Algorithm SHA256).Hash.ToLower() -ne $AcousticSha) {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
        throw "SHA256 acoustic không khớp. Dừng để an toàn."
    }
    if ((Get-FileHash -Path $vocoder -Algorithm SHA256).Hash.ToLower() -ne $VocoderSha) {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
        throw "SHA256 vocoder không khớp. Dừng để an toàn."
    }
    New-Item -ItemType Directory -Force -Path $Models | Out-Null
    Copy-Item $acoustic (Join-Path $Models "acoustic.onnx") -Force
    Copy-Item $vocoder (Join-Path $Models "vocoder.onnx") -Force
    Remove-Item -Recurse -Force $tmp
    Write-Host "Đã cài ONNX vào $Models"
} else {
    Write-Host "ONNX đã có: $Models"
}

$venvPython = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Tạo venv demo: $Venv"
    $prefix = @($py.Prefix)
    & $py.Exe @prefix -m venv $Venv
}
& $venvPython -m pip install --disable-pip-version-check -q -r (Join-Path $Root "deploy\vifasttts_demo\requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Cài requirements thất bại." }

$env:PYTHONPATH = Join-Path $Root "src"
$env:MODEL_DIR = $Models
$hostAddr = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$port = if ($env:PORT) { $env:PORT } else { "8090" }
Write-Host "Mở http://${hostAddr}:${port}  (Ctrl-C để dừng)"
& (Join-Path $Venv "Scripts\uvicorn.exe") deploy.vifasttts_demo.app:app --host $hostAddr --port $port
