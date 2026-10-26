#!/usr/bin/env python3
"""Build the two long pages of shrov.com from content/.

  python tools/build.py                 render public/paper/ and public/notebook/ from content/
  python tools/build.py --lab ../ibkr-lab   first refresh content/ from the private lab repo (scrubbed)

content/ holds the publishable copies; the lab repository itself stays private. Refreshing
applies the edits below and refuses to write anything that looks like an account id.
Needs: pip install markdown==3.7
"""
import argparse, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT, PUBLIC = ROOT / "content", ROOT / "public"

# Lab-notebook sections that are only setup instructions for the (unpublished) code, or stale
DROP_SECTIONS = ["Run it now (no TWS required)", "Setup", "Run it against IBKR paper", "Next",
                 "Not investment advice"]
# Regex replacements; each must match, so a changed source fails loudly instead of leaking
NOTEBOOK_EDITS = [
    (r"returned live accounts `[A-Z]+\d+`/`[A-Z]+\d+`\.", "returned live accounts."),   # account ids out
]
PAPER_EDITS = [
    (r"<strong>short selling is a prohibited transaction in an IRA</strong>, which is[^.]*\.",
     "<strong>short selling is not available in an IRA</strong>, the natural home for an account like this."),
    (r"All figures in this paper are produced by scripts in the repository\.",
     "All figures in this paper are produced by scripts in the lab's code repository, which is not published; the <a href=\"/notebook/\">lab notebook</a> records each run."),
]
SECRET = re.compile(r"\b(?:U|DU|DF)\d{5,}\b|api[_-]?key\s*[:=]|chat_id\s*[:=]|bot\d{6,}:", re.I)


def drop_sections(md, titles):
    out, skip = [], False
    for line in md.splitlines(keepends=True):
        m = re.match(r"^## (.*)$", line)
        if m:
            skip = m.group(1).strip() in titles
        if not skip:
            out.append(line)
    return "".join(out)


def apply(text, edits, what):
    for pat, new in edits:
        text, n = re.subn(pat, lambda m: new, text)
        if not n:
            sys.exit(f"{what}: expected text not found — review the edit list:\n  {pat[:80]}…")
    return text


def check_clean(text, what):
    hit = SECRET.search(text)
    if hit:
        sys.exit(f"{what}: refusing to publish, looks like an account id or credential: {hit.group(0)!r}")


def refresh(lab):
    lab = pathlib.Path(lab)
    md = (lab / "README.md").read_text(encoding="utf-8")
    md = md.split("\n## ", 1)[1]                       # drop the repo title and its intro
    md = "## " + md
    md = apply(md, NOTEBOOK_EDITS, "notebook")
    md = drop_sections(md, DROP_SECTIONS)
    check_clean(md, "notebook")
    (CONTENT / "notebook.md").write_text(md, encoding="utf-8")
    paper = (lab / "paper" / "thirty-one-signals-six-bets.html").read_text(encoding="utf-8")
    paper = apply(paper, PAPER_EDITS, "paper")
    check_clean(paper, "paper")
    (CONTENT / "paper.html").write_text(paper, encoding="utf-8")


NAV = """<nav class="site"><a class="mark" href="/">shrov</a><span><a href="/paper/">Paper</a><a href="/notebook/">Notebook</a><a href="/about/">About</a><a href="/about/#contact">Contact</a></span></nav>"""
NAV_CSS = """
nav.site{max-width:1000px;margin:0 auto;padding:18px 28px 0;display:flex;justify-content:space-between;align-items:baseline;gap:16px;font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.06em}
nav.site a{color:var(--muted);text-decoration:none}
nav.site a:hover{color:var(--accent)}
nav.site .mark{color:var(--ink);font-weight:600;letter-spacing:.14em;text-transform:uppercase}
nav.site span{display:flex;gap:20px}
@media (max-width:640px){nav.site{padding:14px 18px 0}nav.site span{gap:14px}}
"""
HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
"""


def build_paper():
    src = (CONTENT / "paper.html").read_text(encoding="utf-8")
    desc = "Thirty-one price signals collapse to about six independent bets — why a retail account cannot detect an edge it might have."
    src = src.replace("</style>", NAV_CSS + "</style>", 1)
    src = src.replace('<div class="wrap">', "</head>\n<body>\n" + NAV + '\n<div class="wrap">', 1)
    out = HEAD.format(title="Thirty-One Signals, Six Bets", desc=desc) + src.rstrip() + "\n</body>\n</html>\n"
    check_clean(out, "paper")
    (PUBLIC / "paper").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "paper" / "index.html").write_text(out, encoding="utf-8")


def build_notebook():
    import markdown
    md = (CONTENT / "notebook.md").read_text(encoding="utf-8")
    conv = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"],
                             extension_configs={"toc": {"toc_depth": "2"}})
    body = conv.convert(md)
    body = re.sub(r"<table>", '<div class="tablewrap"><table>', body)
    body = body.replace("</table>", "</table></div>")
    toc = conv.toc.replace('<div class="toc">', '<nav class="toc" aria-label="Contents"><p class="h">Contents</p>').replace("</div>", "</nav>")
    page = (ROOT / "tools" / "notebook.tmpl.html").read_text(encoding="utf-8")
    out = page.replace("{{toc}}", toc).replace("{{body}}", body)
    check_clean(out, "notebook")
    (PUBLIC / "notebook").mkdir(parents=True, exist_ok=True)
    (PUBLIC / "notebook" / "index.html").write_text(out, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", help="path to the ibkr-lab checkout to refresh content/ from")
    a = ap.parse_args()
    if a.lab:
        refresh(a.lab)
    build_paper()
    build_notebook()
    for p in PUBLIC.rglob("*.html"):
        check_clean(p.read_text(encoding="utf-8"), str(p.relative_to(ROOT)))
    print("built:", ", ".join(str(p.relative_to(ROOT)) for p in sorted(PUBLIC.rglob("*.html"))))


if __name__ == "__main__":
    main()
