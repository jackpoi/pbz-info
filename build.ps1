# One-shot build: frontend -> assets -> single-file exe
#   powershell -ExecutionPolicy Bypass -File build.ps1
# Output: dist\pbz-info.exe
#
# ASCII only on purpose: PowerShell 5.1 reads .ps1 as ANSI unless it has a BOM,
# and non-ASCII strings can swallow their closing quote.

# npm writes warnings to stderr; under 'Stop' PowerShell 5.1 treats that as fatal.
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot

function Step([string]$label, [scriptblock]$action) {
    Write-Host $label
    & $action
    if ($LASTEXITCODE -ne 0) {
        throw "$label failed (exit $LASTEXITCODE)"
    }
}

Step '[1/3] building frontend ...' {
    Push-Location web
    npm run build
    $code = $LASTEXITCODE
    Pop-Location
    $global:LASTEXITCODE = $code
}

Step '[2/3] generating icon and splash ...' {
    python tools\build_assets.py
}

Step '[3/3] packaging exe ...' {
    python -m PyInstaller build\pbz-info.spec --noconfirm
}

$exe = Join-Path $PSScriptRoot 'dist\pbz-info.exe'
if (-not (Test-Path $exe)) {
    throw 'build failed: dist\pbz-info.exe not found'
}

$mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "done: $exe  ($mb MB)"
exit 0
