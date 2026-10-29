# Scout â€” reusable product-monitoring engine

Runs in GitHub Actions, scores products with YAML rules, and tracks matches in a Google Sheet. No paid AI API required. Python 3.12.

## Current state

The code, tests, Google Sheets integration, RSS and Shopify catalog collectors, deduplication, and optional SMTP alerts are implemented. **No retailer is preconfigured**: `profiles/cycling.yaml` has `sources: []`. This is intentional: live retailer endpoints and permission to fetch them must be verified. Until a source is added, runs produce zero matches. Scores are based on product text and may miss features; 52â€“54 cm or M is not a guaranteed fit across brands. Never treat a score as a verified specification.

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


## Cycling update: Contender source and $5,000 ceiling

The cycling profile now includes a **candidate** Shopify collection endpoint for
Contender Bicycles. Its public availability has **not been verified**. If the
source blocks requests or is not a valid product feed, the workflow will log
`Source Contender Bicycles failed: ...` and continue, possibly with zero results.
A green GitHub Actions run does not guarantee that the source worked.

The hard price ceiling is $5,000. Bikes above $4,000 incur a 5-point penalty
per started $500 band, capped at 10 points. Product text signals are heuristic;
size and technical specifications require manual verification.

To apply this update to an existing repository, replace `profiles/cycling.yaml`
and `scout/scoring.py`, and optionally replace `tests/test_scoring.py`.
Run `python -m pytest -q` before a manual workflow dispatch.


## v0.3: Reusable sources and diagnostics

`profiles/*.yaml` reference source IDs; retailer endpoints live in `sources/retailers.yaml`.
Add new Shopify retailers to the registry and reference their IDs from any profile.
For a different category (e.g. gifts), create a new profile with its own filters and weights.

Run locally with `python -m scout.main --profile cycling --dry-run --debug`.
The workflow supports manual `debug` and `dry_run` inputs. A dry run does not write to Sheets.
All relevant products passing hard filters are stored; only those above the alert threshold trigger email.

**Known limitations:** This first version uses Shopify public feeds and RSS, not
a general web search API. It cannot guarantee that a particular variant is a
correct fit, and bike specification text may be incomplete. The score is a
heuristic, not verified manufacturer data. The Sheets writer performs one
update per variant, so start with `max_pages: 1` and monitor Google API quotas.
The existing Listings sheet is a latest-seen snapshot, not a transaction-level
price history; previous_price records only the immediately preceding price.


### HSA evidence gate
Cycling results require freshly checked retailer evidence before scoring and again before Top 10 publication. Mike's Bikes is matched by product URL against its HSA collection (paginated public feed); OBED is matched against links in its eligible-products section; Priority requires its explicit all-bicycles policy plus a bicycle product type. A generic Truemed partnership or HSA mention is insufficient. Unknown retailers, failed requests, absent evidence, and unrecognized product types are excluded. Collection pagination is bounded to 20 pages; products beyond that bound remain unverified.

Top 10 includes hsa_evidence_url and hsa_checked_at in UTC. Verified means a documented retailer pathway, conditional on personal qualification, not personal HSA approval. Fewer than ten eligible matches produces a shorter list. Existing historical Listings rows remain stored. Run `python -m pytest -q` for offline checks.


### Manufacturer mount evidence
Mount scoring includes reviewed Trek specifications for Checkpoint SL 5 Gen 3 (including AXS) and SL 6 AXS Gen 3. These dated manufacturer snapshots fill missing retailer descriptions and award the full 15-point mounts criterion. The Top 10 evidence JSON includes the manufacturer URL, review date and basis. They do not verify stock, size, drivetrain or HSA eligibility. Other generations, SLR, Checkpoint+, ambiguous titles and explicitly custom builds do not inherit these records. Listed mounting hardware and load limits still depend on the exact size and equipment.

Unknown cycling signals are stored as `Unverified` in Listings rather than false; unknown signals do not enter the Top 10 ranking explanation. Existing historical rows change when a listing is next processed.
