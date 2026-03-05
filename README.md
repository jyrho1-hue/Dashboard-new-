# Financial Dashboard

A static financial dashboard deployed to GitHub Pages.

## Live Site

The dashboard is available at:

```
https://jyrho1-hue.github.io/Dashboard-new-/
```

> **Note:** The repository name ends with a hyphen (`Dashboard-new-`), so the URL also ends with a trailing slash after the hyphen.

## How It Works

1. **`update_data.py`** – Fetches live market data and writes `dashboard_data.json`.
2. **`build.py`** – Reads `dashboard_data.json`, renders the Jinja2 templates, and writes the static site to `public/`:
   - `public/index.html` – main dashboard page
   - `public/404.html` – fallback page for invalid routes
   - `public/.nojekyll` – prevents GitHub Pages from running Jekyll processing

The GitHub Actions workflow (`.github/workflows/pages.yml`) runs both scripts automatically every day at 23:00 UTC and uploads the `public/` directory as a Pages artifact.

## Running the Workflow Manually

1. Go to the **Actions** tab of this repository on GitHub.
2. Select the **"Deploy to GitHub Pages"** workflow in the left sidebar.
3. Click **"Run workflow"** → choose the `main` branch → click the green **"Run workflow"** button.

## Local Development

```bash
pip install -r requirements.txt
python update_data.py   # fetch data  → dashboard_data.json
python build.py         # build site  → public/
```

Open `public/index.html` in your browser to preview the site locally.
