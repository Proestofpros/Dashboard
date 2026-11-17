# Auto-updating job dashboard

Every day at 08:00 IST a GitHub Action runs `scripts/scrape.py`, which searches LinkedIn, Naukri and
Foundit through Apify, scores the results, and saves them to `jobs.json`. `index.html` reads
`jobs.json`, so the page is current whenever it is opened.

## One-time setup (about 10 minutes)
1. **Apify token:** Apify Console -> Settings -> API & Integrations -> create a token and copy it.
2. **GitHub repo:** create a new repository and upload everything in this folder
   (keep the `.github/workflows/refresh.yml` and `scripts/` paths exactly).
3. **Secret:** repo -> Settings -> Secrets and variables -> Actions -> New repository secret.
   Name `APIFY_TOKEN`, value = your token.
4. **Hosting:** repo -> Settings -> Pages -> Deploy from a branch -> `main` / root. Your link will be
   `https://<your-username>.github.io/<repo-name>/`.
5. **First run:** repo -> Actions -> "Refresh jobs" -> Run workflow. After it finishes (a few minutes),
   `jobs.json` updates and the page shows the new date in its banner.

## Notes
- The repo and page are public on the free plan. The page has no name on it, but anyone with the link can see it.
- Each daily run uses Apify credits (the scrapers charge per result). Check your Apify usage after a few days.
- Edit the `SEARCHES` list in `scripts/scrape.py` to change keywords, or `role()` / `score()` to change scoring.
- If one source fails on a day, its previous rows are kept and the others still update.
