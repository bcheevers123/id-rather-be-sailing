# Deployment

## First-time setup

1. Fork or clone this repository.
2. In GitHub repository Settings → Pages: set Source to "GitHub Actions".
3. In Settings → Actions → General: allow Actions to create and approve pull requests (needed for the pipeline to commit JSON updates).
4. Add the following repository secret: `PIPELINE_TOKEN` — a GitHub Personal Access Token with `repo` scope (needed for the pipeline workflow to push commits).

## Automatic deployment

Every push to `main` triggers `.github/workflows/deploy.yml`, which:
1. Runs `npm run build`
2. Publishes the `dist/` directory to GitHub Pages

The site is available at: `https://bcheevers123.github.io/id-rather-be-sailing/`

## Data refresh

`.github/workflows/refresh.yml` runs daily at 06:00 UTC:
1. Runs the Python pipeline (`python -m pipeline.generate`)
2. Commits any changes to `src/data/`
3. Pushes, which triggers the deploy workflow

Trigger manually: Actions tab → `refresh` workflow → "Run workflow".

## Local preview

```bash
npm run build
npm run preview
```
