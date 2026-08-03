# I'd Rather Be Sailing

Find MCA-approved maritime training courses, approved training centres, upcoming dates and prices.

## What this application does

Helps seafarers find courses approved by the Maritime and Coastguard Agency (MCA), the approved training centres offering them, and upcoming dates and prices where that information is publicly available.

## What it does not guarantee

- Schedule data is only as fresh as the last successful pipeline run (daily).
- Many providers do not publish schedules online — those providers still appear with contact details.
- No dates, prices or availability are fabricated or estimated.

## Approval data vs schedule data

**Approval data** (Layer A) comes from official MCA PDF documents on GOV.UK. It tells you which provider is approved to run which course. It is authoritative.

**Schedule data** (Layer B) comes from each provider's own website. It tells you when they are actually running the course and at what price. It varies in availability and freshness.

## Running locally

```bash
# Python pipeline
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pipeline.generate --dry-run

# Frontend
npm install
npm run dev
```

## Refreshing data

```bash
python -m pipeline.generate
# Writes updated JSON to src/data/ and reports to pipeline/output/
```

Or trigger the `refresh` GitHub Actions workflow manually from the Actions tab.

## Adding a provider adapter

1. Create `pipeline/adapters/<provider_slug>.py`
2. Subclass `BaseAdapter` from `pipeline/adapters/base.py`
3. Implement `fetch(provider: Provider) -> list[Offering]`
4. Register the adapter in `pipeline/adapters/__init__.py`
5. Add fixture HTML/JSON to `tests/pipeline/fixtures/`
6. Write tests in `tests/pipeline/test_adapters_<provider_slug>.py`

See `SCRAPING_POLICY.md` before scraping any new site.

## Running tests

```bash
pytest                        # all pipeline tests
pytest --cov=pipeline         # with coverage
npm test                      # frontend tests
```

## Deploying

Push to `main`. GitHub Actions builds the React app and deploys to GitHub Pages automatically.

See `DEPLOYMENT.md` for first-time setup.

## Diagnosing a failed refresh

1. Open the **Actions** tab in GitHub → find the failed `refresh` workflow run
2. Read the step logs — the pipeline logs which source failed and why
3. Check `pipeline/output/coverage_report.json` for per-provider failure details
4. If the MCA page structure changed, update `pipeline/mca_source.py`
5. If a provider's site changed, update or replace its adapter
6. If JSON Schema validation failed, check `pipeline/output/validation_errors.log`
