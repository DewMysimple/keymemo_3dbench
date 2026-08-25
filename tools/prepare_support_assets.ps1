param(
    [string]$Python312 = "C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
)

$ErrorActionPreference = "Stop"
$workbench = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$generated = Join-Path $workbench "generated"
$tooling = Join-Path $generated "tooling"
$converted = Join-Path $generated "converted"
$ktxHome = Join-Path $tooling "KTX-Software"
$ktxExe = Join-Path $ktxHome "bin\ktx.exe"
$installer = Join-Path $tooling "KTX-Software-4.4.2-Windows-x64.exe"
$fontTools = Join-Path $tooling "fonttools"

New-Item -ItemType Directory -Path $tooling, $converted -Force | Out-Null

if (-not (Test-Path -LiteralPath $ktxExe)) {
    $url = "https://github.com/KhronosGroup/KTX-Software/releases/download/v4.4.2/KTX-Software-4.4.2-Windows-x64.exe"
    if (-not (Test-Path -LiteralPath $installer)) {
        Invoke-WebRequest -Uri $url -Headers @{"User-Agent" = "GwayLoo-scene-workbench"} -OutFile $installer
    }
    $process = Start-Process -FilePath $installer -ArgumentList "/S", "/D=$ktxHome" -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "KTX-Software installer failed with exit code $($process.ExitCode)"
    }
}

$ktxBin = Split-Path -Parent $ktxExe
$env:PATH = "$ktxBin;$env:PATH"
$groundInput = Join-Path $workbench "source_snapshot\assets\textures\grounds\atlas.ktx2"
$groundOutput = Join-Path $converted "ground_atlas.png"
& $ktxExe extract --transcode rgba8 $groundInput $groundOutput
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $groundOutput)) {
    throw "KTX2 conversion failed"
}

if (-not (Test-Path -LiteralPath $Python312)) {
    throw "Python 3.12 was not found at $Python312"
}
if (-not (Test-Path -LiteralPath (Join-Path $fontTools "fontTools"))) {
    & $Python312 -m pip install --disable-pip-version-check --no-input --target $fontTools "fonttools==4.59.2"
    if ($LASTEXITCODE -ne 0) {
        throw "fonttools installation failed"
    }
}

$env:PYTHONPATH = $fontTools
$fontInput = Join-Path $workbench "source_snapshot\fonts\CanelaText-Light.woff"
$fontOutput = Join-Path $converted "CanelaText-Light.ttf"
$fontScript = "from fontTools.ttLib import TTFont; f=TTFont(r'$fontInput'); f.flavor=None; f.save(r'$fontOutput')"
& $Python312 -c $fontScript
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $fontOutput)) {
    throw "Font conversion failed"
}

Write-Output "Prepared support assets in $converted"
