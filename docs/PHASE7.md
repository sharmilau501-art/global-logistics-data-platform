# Phase 7 — reproducible tests, GitHub CI, and portfolio handoff

This project uses entirely synthetic logistics data. All processing runs on a local computer.
No AWS deployment or hosted LLM is included. The default analytics assistant is deterministic.

## Windows PowerShell: verify existing work

From the project root, with the virtual environment activated:

```powershell
python -m pip install -r requirements-stream.txt -r requirements-warehouse.txt -r requirements-dashboard.txt
.\scripts\phase7-check.ps1
```

The script requires a populated Phase 3 data lake and Phase 4 DuckDB warehouse.
If it reports missing data, rerun the earlier ETL/warehouse steps before debugging Phase 7.

## Reproducible tests in Docker (optional, local and free)

```powershell
docker build -f Dockerfile.test -t global-logistics-tests .
docker run --rm --network none global-logistics-tests
```

These Docker tests use temporary test fixtures and do not require Kafka, Spark,
existing warehouse files, AWS, or paid APIs. First build downloads free image/packages.

## GitHub Actions workflow (optional)

`.github/workflows/ci.yml` automatically runs tests on pushes and pull requests to
`main` if you publish this repository on GitHub. No AWS keys are required.
GitHub Actions may be subject to usage limits and billing depending on repository
visibility, plan, runner choice, and policy, so use local Docker CI only if you want
to avoid all cloud-runner usage. Do not enable paid runners or billing just for this portfolio.

## Publishing without generated data

Before committing, review `git status` and `git diff --cached --stat`.
The `.gitignore` excludes `/data/`, `.venv/`, DuckDB databases, and secrets.
Do not force-add datasets, credentials, local output logs or other large artifacts.

```powershell
git init
git add .
git diff --cached --stat
git commit -m "Build local logistics analytics platform with quality gates and CI"
```

If using GitHub's website, create an empty repo called `global-logistics-data-platform`
without checking 'Add a README' or 'Add .gitignore' (both exist locally).
After you have a real repository URL, connect it with:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/global-logistics-data-platform.git
git push -u origin main
```

Use your actual username and repo URL. Git may prompt for credential-manager login.

## Portfolio documentation and screenshots

- Capture Streamlit overview, carrier/route analytics, exception explorer, and quality report.
- Include an architecture diagram that labels Kafka, PySpark, local Parquet lake,
  DuckDB, Streamlit, quality checks, and deterministic assistant.
- Describe the data as synthetic and the platform as local, not AWS-deployed.
- Never claim Kinesis/Redshift/Glue/Bedrock were used unless you actually deploy them.
