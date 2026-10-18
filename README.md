# Scout — reusable product-monitoring engine

Runs in GitHub Actions, scores products with YAML rules, and tracks matches in a Google Sheet. No paid AI API required. Python 3.12.

## Current state

The code, tests, Google Sheets integration, RSS and Shopify catalog collectors, deduplication, and optional SMTP alerts are implemented. **No retailer is preconfigured**: `profiles/cycling.yaml` has `sources: []`. This is intentional: live retailer endpoints and permission to fetch them must be verified. Until a source is added, runs produce zero matches. Scores are based on product text and may miss features; 52–54 cm or M is not a guaranteed fit across brands. Never treat a score as a verified specification.

## 1. GitHub

Create a private GitHub repository named `scout` and upload the contents of this folder, preserving `.github/workflows/scout.yml`. GitHub Actions > Scout Daily > Run workflow can launch a run manually. The schedule is 12:17 UTC daily (8:17 AM EDT / 7:17 AM EST), and scheduled workflows may be delayed.

## 2. Google Sheets

Create a blank Google Sheet. Copy the ID from its URL between `/d/` and `/edit`. In Google Cloud Console create a project, enable the Google Sheets API, create a service account and a JSON key. Share the spreadsheet with the service account's `client_email` as Editor. Keep the JSON key private.

In GitHub repository Settings > Secrets and variables > Actions, create:

- `GOOGLE_SERVICE_ACCOUNT_JSON`: entire JSON key content
- `GOOGLE_SHEET_ID`: spreadsheet ID

The program creates a `Listings` worksheet automatically and stores rows keyed by profile + listing ID. On subsequent runs, it updates last-seen and price fields. Rows not seen again are retained as history. The `previous_price` column records the preceding observed price (not necessarily the original price).

## 3. Add an actual data source

Use only permitted, public endpoints. Example **format**, not a verified retailer endpoint:

```yaml
sources:
  - name: Example Store
    type: shopify
    url: https://example.com/products.json?limit=250
```

Or for a public RSS feed:

```yaml
sources:
  - name: Example Feed
    type: rss
    url: https://example.com/feed.xml
```

A Shopify feed may be inaccessible, paginated, or may not represent inventory accurately. This starter only fetches the single configured URL; it does not paginate. RSS entries without structured prices are skipped by design. The engine does not scrape JavaScript-only pages, log in to marketplaces, bypass anti-bot measures, or automatically infer unavailable product specifications. Use verified sources and test them before relying on coverage.

## 4. Optional email notifications

Create GitHub Actions secrets `SMTP_HOST`, `SMTP_PORT` (optional, defaults 465), `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_TO`. For Gmail SMTP, use `smtp.gmail.com` with an app password where supported, not your Google password. If these are absent, results are stored but no email is sent. No email is sent when there are no new matches or threshold-crossing price drops.

## 5. Local tests and dry run

```bash
pip install -r requirements.txt
pytest -q
python -m scout.main --dry-run --profile cycling
```

Dry run doesn't need Google credentials. A normal run requires the two Google secrets.

## 6. Future searches

Copy `profiles/gifts.example.yaml` to `profiles/dad_gifts.yaml`, set `enabled: true`, fill keywords, budget, and verified sources. Generic matching scores keyword presence and sale wording. More sophisticated gift logic can be added as a scoring module without changing collectors or storage. Keep separate profile names for each use case.

## Operational notes

- GitHub free Actions limits, Google API quotas, retailer access policies, and GitHub scheduled-workflow behavior can change.
- This initial implementation updates Sheet rows individually, suitable for small catalogs but not large-scale crawls.
- Sheets access uses a Google Cloud service account. If you prefer to avoid a JSON key, workload identity federation could be added later.
- No secret files should be committed to GitHub.
- Price-drop alerts compare the current price to the previous successful observation of that listing; listings reappearing after an absence retain history.
- Treat scoring as shortlist triage. Confirm size, drivetrain, battery type, rack mounting and price on the seller's page.
