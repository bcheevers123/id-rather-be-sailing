# Architecture

## Overview

Fully static architecture: a Python data pipeline runs daily in GitHub Actions, writes pre-generated JSON, and triggers a React frontend deployment to GitHub Pages.

## Data flow

1. GitHub Actions cron (`refresh.yml`) runs the Python pipeline
2. Pipeline fetches the MCA guidance page and discovers current PDF URLs
3. Pipeline downloads and parses each PDF — extracts provider-course approval records
4. Pipeline visits each provider website via per-provider adapters — extracts dates, prices
5. Pipeline validates all records against JSON Schema in `pipeline/schemas/`
6. Pipeline writes `src/data/*.json`, commits, and pushes
7. Push triggers `deploy.yml`, which builds the React SPA and publishes to GitHub Pages
8. Users load the SPA; it fetches JSON over HTTP from GitHub Pages CDN

## Why static

- £0 hosting
- No server to operate or patch
- Safe failure mode: previous JSON retained when pipeline fails
- All scraping is server-side (Actions), never in the user's browser

## Key directories

| Path | Purpose |
|---|---|
| `pipeline/` | Python data collection, parsing, validation |
| `pipeline/adapters/` | Per-provider schedule scrapers |
| `pipeline/schemas/` | JSON Schema for output validation |
| `src/data/` | Static JSON consumed by the frontend |
| `src/` | React + Vite + TypeScript frontend |
| `.github/workflows/` | CI/CD and data refresh automation |
