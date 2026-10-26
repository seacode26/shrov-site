# shrov.com

The public site at **https://www.shrov.com**: the paper *Thirty-One Signals, Six Bets*, its lab notebook, and a short home page. Static files, served by a Cloudflare Worker (static assets only, no code).

## Layout
- `public/`: what is served, committed as built. `index.html` and `about/` are hand-written. `paper/` (an overview plus 10 parts) and `notebook/` (7 chapters, split into pages of about three screens) are generated, and no page is long.
- `content/`: the publishable copies of the paper (`paper.html`) and notebook (`notebook.md`). They are drawn from the private lab repository and scrubbed.
- `tools/build.py`: renders `content/` into `public/` (part boundaries: `PAPER_PARTS`; chapters: `NOTEBOOK_CHAPTERS`; page length: `PAGE_CHARS`). It also re-points home-page links to notebook headings at whichever page now holds them. With `--lab <path to ibkr-lab>` it first refreshes `content/`, applying its edit list and refusing anything that looks like an account id or credential.

```bash
pip install markdown==3.7
python tools/build.py                     # after editing content/
python tools/build.py --lab ../ibkr-lab   # pull a newer paper/notebook from the lab
```
CI rebuilds and fails if `public/` is stale, and runs a secret scan.

## Publishing rules
- Pen name only: no personal name, accounts, balances or anything from the retirement-plan repository.
- The lab's code stays private; the notebook says so.
- Every page carries the not-investment-advice note.

## Deploy (Cloudflare, once)
1. Workers & Pages → Create → **Import a repository** → GitHub → `seacode26/shrov-site`.
2. Settings: root directory empty, build command empty, deploy command `npx wrangler deploy`, production branch `main`.
3. Build → Branch control: untick *Builds for non-production branches*.

`wrangler.toml` is set up as follows:
- It serves `public/` as static assets on the custom domain `www.shrov.com`, with `workers.dev` and preview URLs off.
- Security headers come from `public/_headers`.
- To serve the bare `shrov.com` as well, add it as a second custom domain, or add a redirect rule from `shrov.com` to `www`. Check first that no existing DNS record on the apex conflicts.
