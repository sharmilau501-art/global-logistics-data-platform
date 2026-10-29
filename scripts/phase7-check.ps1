# Local-only end-to-end verification: run from project root with .venv active.
$ErrorActionPreference = 'Stop'
function Run-Step([string]$Description, [string]$Command, [string[]]$Arguments) {
    Write-Host "`n== $Description =="
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "FAILED ($LASTEXITCODE): $Description" }
}
Run-Step 'Automated tests' 'python' @('-m','pytest','-q')
Run-Step 'Warehouse reconciliation and quality gate' 'python' @('-m','logistics.quality_monitor','check')
Run-Step 'Warehouse report' 'python' @('-m','logistics.warehouse','report')
Run-Step 'Grounded analytics assistant' 'python' @('-m','logistics.assistant','--question','Which carrier has the most late deliveries?')
Write-Host "`nPHASE 7 LOCAL VERIFICATION: PASS"
Write-Host 'Screenshots and remote GitHub workflows still require manual verification.'
