# build.ps1 — QPopCV build and package script
# Usage: .\build.ps1
# Output: dist\QPopCV-vX.Y.Z.zip
#
# The ZIP wraps all exe + DLL files inside a QPopCV\ top-level folder.
# updater.py's _find_source_root() detects this single-folder layout and
# strips the wrapper, so xcopy lands files directly in the user's install dir.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# ── 1. Read version from qpopcv/config.py ──────────────────────────────────
$configContent = Get-Content "qpopcv\config.py" -Raw
if (-not ($configContent -match 'APP_VERSION\s*=\s*"([^"]+)"')) {
    throw "Could not read APP_VERSION from qpopcv\config.py"
}
$version = $Matches[1]
Write-Host "[build] Version: $version"

# ── 2. Run PyInstaller ──────────────────────────────────────────────────────
Write-Host "[build] Running PyInstaller..."
python -m PyInstaller QPopCV.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

# ── 3. Verify the exe exists ────────────────────────────────────────────────
$exePath = "dist\QPopCV\QPopCV.exe"
if (-not (Test-Path $exePath)) {
    throw "Expected exe not found at $exePath after build"
}
Write-Host "[build] Exe verified: $exePath"

# ── 4. Create release ZIP ───────────────────────────────────────────────────
# ZIP structure: QPopCV\QPopCV.exe, QPopCV\*.dll, QPopCV\media\, etc.
# The single top-level folder is what _find_source_root() expects.
$zipName = "QPopCV-v$version.zip"
$zipPath = "dist\$zipName"

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
    Write-Host "[build] Removed existing $zipPath"
}

Write-Host "[build] Creating $zipPath..."
# Compress the dist\QPopCV folder itself (not just its contents)
# This produces a ZIP with a single top-level entry: QPopCV\
Compress-Archive -Path "dist\QPopCV" -DestinationPath $zipPath

$sizeMB = [Math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host "[build] Done: $zipPath ($sizeMB MB)"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Test the exe: dist\QPopCV\QPopCV.exe"
Write-Host "  2. Tag the release: git tag v$version && git push origin v$version"
Write-Host "  3. Create GitHub release and upload: dist\$zipName"
