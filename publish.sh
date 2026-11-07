#!/usr/bin/env bash
# Build the site and push it to the gh-pages branch (GitHub Pages serves that branch).
set -euo pipefail
cd "$(dirname "$0")"
GH_USER=diveman4 GH_REPO=newsletter-cost-lab python3 build.py --base-url https://diveman4.github.io/newsletter-cost-lab/
tmp=$(mktemp -d); cp -r site/. "$tmp"/
cd "$tmp" && git init -q -b gh-pages && git add -A && \
  git -c user.name="TA" -c user.email="noreply@users.noreply.github.com" commit -qm "Deploy site" && \
  git push -f "https://github.com/diveman4/newsletter-cost-lab" gh-pages
