# Shopify Store Speed & Improve Conversion Rate

Shopify theme (Dawn-based) used for **speed optimization and conversion improvements**. Use as a portfolio piece for **Shopify Speed & Conversion** (e.g. Fiverr Gig 1).

## What this is

- **Theme:** Optimized Dawn theme — clean Liquid, preload fonts, lazy-load images, no blocking scripts or heavy third-party CSS.
- **Docs:** Internal notes and assets for delivering “Speed & Conversion” gigs:
  - `docs/gig1-speed-notes.md` — Use Dawn; build a clear before/after case (e.g. slow → optimize → measure).
  - `docs/gig1-import-products.md` — How to import demo products.
  - `docs/gig1-products-import.csv` — CSV template for 10 demo products.

## How to use

1. **Connect to your Shopify store** (Shopify CLI):
   ```bash
   shopify auth login
   shopify theme push
   ```
   Or use **Shopify theme dev** for local preview with live reload.

2. **For a “before/after” case:**  
   Follow `docs/gig1-speed-notes.md`: add some weight (e.g. heavy app, large images), measure with PageSpeed/GTmetrix, then apply optimizations in this theme and measure again. Deliver a short before/after report to the client.

## Optimizations included (portfolio)

- Preload critical fonts.
- Lazy-load images where appropriate.
- No render-blocking external CSS/JS.
- Clean theme code (no leftover app snippets or duplicate scripts).
- Mobile-friendly layout and performance in mind.

## Folder structure

- `assets/`, `layout/`, `sections/`, `snippets/`, `templates/`, `config/`, `locales/`, `blocks/` — Standard Shopify theme.
- `docs/` — Gig 1 notes and import guides (for your reference, not part of the theme).

## License

ISC
