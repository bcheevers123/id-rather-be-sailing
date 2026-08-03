# Operations

## Daily pipeline

Runs at 06:00 UTC via GitHub Actions. Completes in under 10 minutes for a full refresh.

## Monitoring

- Check the Actions tab for failed runs.
- `src/data/coverage_report.json` contains per-provider failure details.
- GitHub Actions sends email notifications to the repo owner on workflow failure (configure in Settings → Notifications).

## Freshness thresholds

| Data | Verified | Recently checked | Stale |
|---|---|---|---|
| Provider schedules | < 24 hours | 1–7 days | > 7 days |
| MCA approval PDFs | < 32 days | — | > 32 days |

## Common issues

**Pipeline fails with HTTP 403 on MCA PDF:** The PDF URL has changed (monthly update). Check that `pipeline/mca_source.py` is correctly discovering URLs from the guidance page rather than using hardcoded paths.

**Provider returns 0 offerings (was non-zero before):** Change detector flags this. Check `coverage_report.json`. The provider may have changed their site structure — update the adapter.

**GitHub Pages deploy fails:** Check that the `GITHUB_TOKEN` permissions in `deploy.yml` include `pages: write` and `id-token: write`.

## Adding a new provider adapter

See `README.md` → "Adding a provider adapter".
