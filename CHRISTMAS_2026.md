# Christmas 2026: gifts for parents

Budget: up to $150 per parent, counting the entire prepaid subscription cost. Separate and shared gifts are welcome. Shared candidates use a conservative $150 item cap for now; this is a shortlist filter, not a guarantee that a multi-item basket fits the $300 combined budget. Account for shared gifts in both parents' allocations before buying.

## Search categories

- Dad: adult LEGO building projects; start with Botanicals because they also enjoy plants. Expand to Architecture, Ideas, Technic or other themes after learning which sets he likes and owns.
- Mom: supplies and unusual seed choices for existing AeroGardens. Avoid another countertop garden by default. Model-specific trays, trellises and replacement parts need her model names first.
- Both: plant stands, propagation stations, appropriate lighting and watering accessories. Soil moisture tools and watering globes are for potted plants, not hydroponic reservoirs. Prefer useful additions over more clutter.
- Both: fixed-term surprise food deliveries, such as international snacks, cheese/charcuterie, specialty coffee, olive oil or regional treats. Do not compare a monthly headline price to a full gift budget.

## Starter sources checked on 2026-11-19

- LEGO Tiny Plants: https://www.lego.com/en-us/product/tiny-plants-10329
- LEGO Botanicals ideas: https://www.lego.com/en-us/categories/adults-welcome/article/unkillable-plants
- AeroGarden Grow Anything kit: https://scottsmiraclegro.com/en-us/brands/aerogarden/products/seed-kits/aerogarden-grow-anything-seed-pod-kit.html
- AeroGarden seed kits: https://scottsmiraclegro.com/en-us/brands/aerogarden/products/seed-kits/
- The Sill plant accessories: https://www.thesill.com/collections/planters-plant-care-accessories
- Universal Yums: https://www.universalyums.com/faq/ (1, 3, 6 or 12-month gifts; FAQ states no automatic gift renewal)
- iGourmet: https://igourmet.com/pages/subscription-boxes (plan and total need verification)

## How the research runs

Cycling is disabled; its code and history remain available. Four enabled profiles populate `Gift shortlist <profile>` and `Gift review <profile>` in the existing Google Sheet. No new credentials are needed. Use GitHub Actions > Scout Daily > Run workflow, with an optional profile such as `dad_lego`; dry_run prints results without Sheets writes. Existing daily scheduling applies, and these profiles stop after Christmas Day in America/New_York.

The initial watchlists contain nine curated leads, not an exhaustive internet search. They can grow in sources/gifts.yaml. Each physical product is fetched from its public page subject to robots.txt. Only an exact-name JSON-LD Product with one USD Offer and explicit InStock availability receives a current price. Missing structured data, blocked pages, configurable offers and food plans go to review, so a shortlist can be empty even when a website sells an item. There are no invented prices or stale-price fallbacks. `checked_at` records the attempt time, not a successful verification for review rows.

Shortlist means price and stock checked, not purchase-ready: recipient ZIP, Christmas arrival, final shipping/tax, ownership, compatibility and dietary restrictions still need checking. Subscription leads remain in review until a concrete prepaid plan and full cost are independently verified; monthly price is never ranked. Gift emails are not sent. Historical cycling sheets may still show old entries; gift results are in their separate tabs.

## Preferences still needed

Dad's favorite LEGO themes and owned sets; mom's AeroGarden model names; parents' delivery ZIP, food likes/dislikes, allergies, and which previous food subscription they enjoyed. Do not infer that an unknown dietary requirement is safe.
