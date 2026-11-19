# Christmas 2026: gifts for parents

Budget: up to $150 per parent, counting the entire prepaid subscription cost. Separate and shared gifts are welcome. Shared physical/food candidates use a conservative $150 item cap; experiences use $300 for the entire outing for two, including fees, parking and travel; this is a shortlist filter, not a guarantee that a multi-item basket fits the $300 combined budget. Account for shared gifts in both parents' allocations before buying.

## Search categories

- Dad: Star Wars LEGO helmets, busts and display models. Explicitly exclude Botanicals. He already collects head/helmet figures and builds his own display shelves in his woodshop: avoid generic shelving and display stands. Owned set numbers are still unknown.
- Dad: Led Zeppelin and Rolling Stones gifts, such as official books, prints or collectible music. Vinyl depends on confirming that he has a turntable.
- Mom: supplies and unusual seed choices for existing AeroGardens. Avoid another countertop garden by default. Model-specific trays, trellises and replacement parts need her model names first.
- Both: plant stands, propagation stations, appropriate lighting and watering accessories. Soil moisture tools and watering globes are for potted plants, not hydroponic reservoirs. Prefer useful additions over more clutter.
- Both: fixed-term surprise food deliveries, such as international snacks, cheese/charcuterie, specialty coffee, olive oil or regional treats. Do not compare a monthly headline price to a full gift budget.

- Both: Jacksonville-area experiences, especially classic-rock shows and Jaguars tickets. Include 2027 events as Christmas 2026 gifts. Jaguars: Jacksonville home games in 2026 and Orlando home games in 2027. Check exact dates/venues and a complete two-seat total; never equate a deposit or single-seat price with an outing.

## Starter sources checked on 2026-11-19

- Star Wars helmets/busts: https://www.lego.com/en-us/themes/star-wars/helmets-busts
- Led Zeppelin: https://store.ledzeppelin.com/
- Rolling Stones official store: https://therollingstones.lnk.to/OfficialStore
- Get The Led Out, Florida Theatre, March 20, 2027 at 8 p.m. (tribute): https://www.floridatheatre.com/events/detail/get-the-led-out-4
- Jaguars 2026: https://www.jaguars.com/tickets/singlegametickets
- Jaguars 2027 Orlando: https://www.jaguars.com/orlando2027 (full home schedule and pricing not set at check time; deposits are not complete tickets)
- AeroGarden Grow Anything kit: https://scottsmiraclegro.com/en-us/brands/aerogarden/products/seed-kits/aerogarden-grow-anything-seed-pod-kit.html
- AeroGarden seed kits: https://scottsmiraclegro.com/en-us/brands/aerogarden/products/seed-kits/
- The Sill plant accessories: https://www.thesill.com/collections/planters-plant-care-accessories
- Universal Yums: https://www.universalyums.com/faq/ (1, 3, 6 or 12-month gifts; FAQ states no automatic gift renewal)
- iGourmet: https://igourmet.com/pages/subscription-boxes (plan and total need verification)

## How the research runs

Cycling is disabled; its code and history remain available. Six enabled profiles populate `Gift shortlist <profile>` and `Gift review <profile>` in the existing Google Sheet. No new credentials are needed. Use GitHub Actions > Scout Daily > Run workflow, with an optional profile such as `dad_lego`; dry_run prints results without Sheets writes. Existing daily scheduling applies, and these profiles stop after Christmas Day in America/New_York.

The initial watchlists contain thirteen curated leads, not an exhaustive internet search. They can grow in sources/gifts.yaml. Each physical product is fetched from its public page subject to robots.txt. Only an exact-name JSON-LD Product with one USD Offer and explicit InStock availability receives a current price. Missing structured data, blocked pages, configurable offers and food plans go to review, so a shortlist can be empty even when a website sells an item. There are no invented prices or stale-price fallbacks. `checked_at` records the attempt time, not a successful verification for review rows.

Shortlist means price and stock checked, not purchase-ready: recipient ZIP, Christmas arrival, final shipping/tax, ownership, compatibility and dietary restrictions still need checking. Subscription leads remain in review until a concrete prepaid plan and full cost are independently verified; monthly price is never ranked. Gift emails are not sent. Historical cycling sheets may still show old entries; gift results are in their separate tabs.

## Preferences still needed

Dad's owned Star Wars set numbers, turntable ownership and music collection; mom's AeroGarden model names; parents' delivery ZIP, food likes/dislikes, allergies, and which previous food subscription they enjoyed. Do not infer that an unknown dietary requirement is safe.

The 2027 event horizon does not extend daily gift scans past Christmas 2026. Event leads stay in review until dates, two-seat all-in costs and practical constraints are checked. No ticket or deposit purchases are made.
