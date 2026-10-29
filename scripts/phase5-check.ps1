# Run from the repository root, using the activated .venv.
# Local quality gate: no AWS services, remote runners, paid accounts or credentials.
$ErrorActionPreference = 'Stop'
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed with exit code $LASTEXITCODE" }
python -m logistics.warehouse_runner --max-attempts 3 --retry-delay 1
if ($LASTEXITCODE -ne 0) { throw "Warehouse build/quality gate failed with exit code $LASTEXITCODE" }
Write-Host 'PASS: Phase 5 local tests, warehouse refresh, and quality checks.'
