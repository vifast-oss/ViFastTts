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
$Url = "https://github.com/dvchd/ViFastTts/releases/download/n0-ngochuyen-prod-v1/n0_onnx_fp32.zip"
$Sha = "c613b1206cb8b57140d9429564da71c969c71b2491ae4d0da87becc2c89ba98a"

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
    Write-Host "Tải ONNX N0 Q-init..."
    $zip = Join-Path $env:TEMP "n0_onnx_fp32.zip"
    Invoke-WebRequest -Uri $Url -OutFile $zip
    $actual = (Get-FileHash -Path $zip -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $Sha) {
        Remove-Item $zip -Force -ErrorAction SilentlyContinue
        throw "SHA256 không khớp. Dừng để an toàn."
    }
    $tmp = Join-Path $env:TEMP ("n0_onnx_" + [guid]::NewGuid().ToString("N"))
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    New-Item -ItemType Directory -Force -Path $Models | Out-Null
    Copy-Item (Join-Path $tmp "n0_onnx_fp32\*.onnx") $Models -Force
    Remove-Item -Recurse -Force $tmp
    Remove-Item $zip -Force
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
