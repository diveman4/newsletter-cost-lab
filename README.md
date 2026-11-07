# Newsletter Cost Lab

Static site comparing newsletter platform costs, with prices verified against each vendor's own pricing page.

- `data/platforms.json` — all prices, limits and sources (edit this when prices change; bump `verified_on`)
- `build.py` — generates `site/` (run `GH_USER=... GH_REPO=... python3 build.py --base-url https://USER.github.io/REPO/`)
- `assets/` — CSS and the calculator script
- `publish.sh` — builds and force-pushes `site/` to the `gh-pages` branch, which GitHub Pages serves
