$ErrorActionPreference = 'Stop'
Write-Host 'PHASE 6: Local QA + warehouse snapshot + assistant'
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed' }
python -m logistics.quality_monitor check
if ($LASTEXITCODE -ne 0) { throw 'Phase 5 quality gate failed' }
python -m logistics.assistant --question 'Which route has the most late deliveries?'
if ($LASTEXITCODE -ne 0) { throw 'Analytics assistant failed' }
Write-Host 'PHASE 6 CHECK: PASS (local only; UI still needs visual verification)'
