# Working notes for Claude

- Timestamps: start every reply with `TZ=America/Los_Angeles date '+%m-%d-%y %H%M %Z'` on its own line.
- Public site (www.shrov.com), **pen name only**. Never publish:
  - the owner's name or email;
  - account ids, balances, or anything from the retirement-plan repo.
- Content comes from the private ibkr-lab repo via `python tools/build.py --lab ../ibkr-lab`, which scrubs and checks it. Commit `public/` as built; CI fails if it is stale.
- Keep pages short, about three screens or less. Long material is split by `PAPER_PARTS`, `NOTEBOOK_CHAPTERS` and `PAGE_CHARS` in `tools/build.py`.
- Contact: notes@shrov.com (Cloudflare Email Routing).
- Pushes to `main` deploy through Cloudflare Workers Builds. Validate locally, then open a PR and merge it.
