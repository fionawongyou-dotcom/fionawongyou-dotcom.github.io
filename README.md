# Fiona You WANG Website

This repository is a Markdown-driven static website for GitHub Pages.

## Content

- Keep editing the Markdown files in the repository root.
- `index.md` controls the public site outline and navigation.
- Obsidian links such as `[[About]]` are converted into website links when the matching Markdown file exists.
- Remote images and YouTube links in Markdown are rendered on the generated pages.

## Local Preview

```bash
python3 scripts/build.py
python3 -m http.server 8000 --directory _site
```

Then open `http://localhost:8000`.

## GitHub Pages

The workflow in `.github/workflows/pages.yml` builds and deploys the site:

- on every push to `main`
- once per day at 02:15 Asia/Shanghai
- manually from the GitHub Actions tab

Before the first deployment, create a GitHub repository, push this folder to the `main` branch, and set **Settings -> Pages -> Build and deployment -> Source** to **GitHub Actions**.

## Publishing Local Markdown Updates

After a GitHub remote is configured:

```bash
bash scripts/publish.sh
```

This rebuilds `_site`, commits changed files, and pushes to GitHub. The GitHub Pages workflow will then deploy the updated site.
