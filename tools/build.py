#!/usr/bin/env python3
"""Build the two long pages of shrov.com from content/.

  python tools/build.py                 render public/paper/ (parts) and public/notebook/ (chapters of short pages) from content/
  python tools/build.py --lab ../ibkr-lab   first refresh content/ from the private lab repo (scrubbed)

content/ holds the publishable copies; the lab repository itself stays private. Refreshing
applies the edits below and refuses to write anything that looks like an account id.
Needs: pip install markdown==3.7
"""
import argparse, pathlib, re, shutil, sys

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


# ---------------------------------------------------------------- page shell

FONTS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,300;0,400;0,500;0,600;1,400&family=IBM+Plex+Mono:wght@400;500;600&display=swap">"""


def nav(current):
    links = [("/paper/", "Paper"), ("/notebook/", "Notebook"), ("/about/", "About"), ("/about/#contact", "Contact")]
    items = "".join(f'<a href="{h}"{" aria-current=\"page\"" if t == current else ""}>{t}</a>' for h, t in links)
    return f'<nav class="site"><a class="mark" href="/">shrov</a><span>{items}</span></nav>'


def shell(title, desc, body, css=(), scripts=(), current=None):
    links = "".join(f'<link rel="stylesheet" href="{c}">\n' for c in ("/style.css",) + tuple(css))
    js = "".join(f'<script src="{s}" defer></script>\n' for s in scripts)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{FONTS}
{links}{js}</head>
<body>
{nav(current)}
<div class="wrap">
{body}
</div>
</body>
</html>
"""


DISCLAIMER = """<footer class="slim"><p><strong>Not investment advice.</strong> Research on simulated capital; the author is not a licensed adviser. · <a href="/about/#contact">Questions or corrections</a></p></footer>"""


def pager(parts, i, base):
    """Previous / next links and a numbered strip of all parts."""
    prev = parts[i - 1] if i > 0 else None
    nxt = parts[i + 1] if i + 1 < len(parts) else None
    url = lambda p: f"{base}{p['slug']}/" if p["slug"] else base
    strip = "".join(f'<a href="{url(p)}"{" aria-current=\"page\"" if j == i else ""} title="{p["title"]}">{j + 1 if base == "/notebook/" else p.get("num", j)}</a>'
                    for j, p in enumerate(parts))
    pn = '<nav class="pn" aria-label="Previous and next">'
    pn += f'<a class="prev" href="{url(prev)}"><small>← Previous</small>{prev["title"]}</a>' if prev else "<span></span>"
    pn += f'<a class="next" href="{url(nxt)}"><small>Next →</small>{nxt["title"]}</a>' if nxt else "<span></span>"
    pn += "</nav>"
    return f'<nav class="parts" aria-label="Parts">{strip}</nav>', pn


def write(path, html):
    check_clean(html, str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------- paper: one page per part

PAPER_PARTS = [  # slug, title, first marker, end marker (exclusive); markers are exact substrings of the paper body
    ("", "Overview", '<header class="mast">', '<section id="question">'),
    ("harness", "§1 · Why it needed a harness", '<section id="question">', '<section id="results">'),
    ("agents", "§2 · Agents and strategy selection", '<section id="results">', '<h3><span class="tag">2.4 '),
    ("costs", "§2 · Costs and capacity", '<h3><span class="tag">2.4 ', '<h3><span class="tag">2.6 '),
    ("turnover", "§2 · Turnover, replication, market-neutral", '<h3><span class="tag">2.6 ', '<section id="breadth">'),
    ("breadth", "§3 · No signal has an edge", '<section id="breadth">', '<h3><span class="tag">3.2</span>'),
    ("clusters", "§3 · Thirty-one signals are six bets", '<h3><span class="tag">3.2</span>', '<section id="arithmetic">'),
    ("arithmetic", "§4 · The arithmetic that ends it", '<section id="arithmetic">', '<section id="errata">'),
    ("errata", "§5 · Errors the harness caught", '<section id="errata">', '<section id="limits">'),
    ("limits", "§6–7 · Limits, and what would change the answer", '<section id="limits">', '<section id="conclusion">'),
    ("conclusion", "§8 · Conclusion", '<section id="conclusion">', "</div>\n\n<script>"),
]


def build_paper():
    src = (CONTENT / "paper.html").read_text(encoding="utf-8")
    css = src[src.index("<style>") + 7:src.index("</style>")]
    css = css.replace("*{box-sizing:border-box}", "")            # shared rules live in /style.css
    js = src[src.index("<script>") + 8:src.rindex("</script>")]
    body = src[src.index('<div class="wrap">') + len('<div class="wrap">'):]
    out = PUBLIC / "paper"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    (out / "paper.css").write_text("/* generated from content/paper.html */\n" + css.strip() + "\n", encoding="utf-8")
    (out / "figures.js").write_text("/* generated from content/paper.html */\n" + js.strip() + "\n", encoding="utf-8")
    parts = [{"slug": s, "title": t, "num": "◆" if not s else str(i)} for i, (s, t, _, _) in enumerate(PAPER_PARTS)]
    for i, (slug, title, a, b) in enumerate(PAPER_PARTS):
        if a not in body or b not in body:
            sys.exit(f"paper: marker not found for part {slug or 'overview'} — content/paper.html changed shape")
        chunk = body[body.index(a):body.index(b)]
        if chunk.startswith("<h3"):   # a part that starts inside a section gets that section's heading again
            num = title.split(" ·")[0].replace("§", "§ ")
            sec = {"§ 2": "Nine experiments, continued", "§ 3": "The central result, continued"}[num]
            chunk = f'<section><div class="sechead"><div class="secnum">{num}</div><h2 class="title">{sec}</h2></div>\n' + chunk
        chunk += "</section>" * (chunk.count("<section") - chunk.count("</section>"))
        if slug == "conclusion":
            chunk += body[body.index("<footer"):body.index("</footer>") + 9]
        strip, pn = pager(parts, i, "/paper/")
        head = (f'<p class="crumb">Thirty-One Signals, Six Bets · overview and contents</p>' if not slug else
                f'<p class="crumb"><a href="/paper/">Thirty-One Signals, Six Bets</a> · part {i} of {len(parts) - 1}</p>')
        if not slug:
            toc = "".join(f'<li><a href="/paper/{p["slug"]}/"><span>{j}</span>{p["title"]}</a></li>'
                          for j, p in enumerate(parts) if p["slug"])
            chunk += f'<section class="paper-toc"><div class="sechead"><div class="secnum">Contents</div><h2 class="title">Read it in {len(parts) - 1} short parts</h2></div><ol class="partlist">{toc}</ol></section>'
        page = f'{head}{strip}<div class="paperbody">{chunk}</div>{pn}' + ("" if slug == "conclusion" else DISCLAIMER)
        name = "Thirty-One Signals, Six Bets" + ("" if not slug else f" — {title}")
        html = shell(name, "Thirty-one price signals collapse to about six independent bets — why a retail account cannot detect an edge it might have.",
                     page, css=("/paper/paper.css",), scripts=("/paper/figures.js",) if 'id="fig-' in chunk else (), current="Paper")
        write(out / slug / "index.html" if slug else out / "index.html", html)


# ---------------------------------------------------------------- notebook: one page per chapter

NOTEBOOK_CHAPTERS = [  # slug, title, one-line summary, the "## " sections it holds (in order)
    ("harness", "The harness", "One design rule, the broker connection, paper-only safeguards, risk limits and alerting.",
     ["The one design decision", "First connection: run preflight", "Paper-only enforcement", "What the sandbox lies about", "Risk limits", "Alerting"]),
    ("costs", "Backtesting and costs", "Timing, the shared risk gate, the execution model, and spreads measured from live quotes.",
     ["Backtesting (milestone 4)"]),
    ("selection", "Choosing strategies", "Walk-forward selection on two universes, and the overnight-versus-intraday split.",
     ["Walk-forward (the thing that makes comparisons mean anything)", "Overnight vs intraday"]),
    ("agents", "LLM agents", "Scout the picker, what the API costs, and the veto that lost 112 points.",
     ["Scout (milestone 5)", "The veto agent (`labtrader/veto.py`)"]),
    ("capacity", "Small caps and turnover", "Why the capacity argument defeats itself, and what slowing down revealed.",
     ["The small-cap test", "Low turnover: the cost problem is solved, the signal problem replaces it"]),
    ("neutral", "Market-neutral", "Long/short construction, two bugs it exposed, and negative alpha.",
     ["Market-neutral construction (`labtrader/neutral.py`)"]),
    ("breadth", "Breadth", "Are 31 signals 31 signals? Controls, the correlation matrix, and the small-cap replication.",
     ["Breadth: are 31 signals actually 31 signals? (`labtrader/signals.py`, `labtrader/factors.py`)"]),
]


def split_h2(md):
    secs, cur, title = {}, [], None
    for line in md.splitlines(keepends=True):
        m = re.match(r"^## (.*)$", line)
        if m:
            if title is not None:
                secs[title] = "".join(cur)
            title, cur = m.group(1).strip(), []
        cur.append(line)
    if title is not None:
        secs[title] = "".join(cur)
    return secs


PAGE_CHARS = 3200   # markdown characters per notebook page (about three screens); pages break only at ## / ### headings


def paginate(md):
    """Split chapter markdown at ## / ### headings (never inside a code fence) into pages of about PAGE_CHARS."""
    blocks, cur, fence = [], [], False
    for line in md.splitlines(keepends=True):
        if line.startswith("```"):
            fence = not fence
        if not fence and re.match(r"^#{2,3} ", line) and cur:
            blocks.append("".join(cur))
            cur = []
        cur.append(line)
    blocks.append("".join(cur))
    pages, page = [], ""
    for blk in blocks:
        if page and len(page) + len(blk) > PAGE_CHARS:
            pages.append(page)
            page = ""
        page += blk
    pages.append(page)
    return pages


def build_notebook():
    import markdown
    secs = split_h2((CONTENT / "notebook.md").read_text(encoding="utf-8"))
    used = [t for _, _, _, ts in NOTEBOOK_CHAPTERS for t in ts]
    missing = [t for t in secs if t not in used]
    unknown = [t for t in used if t not in secs]
    if missing or unknown:
        sys.exit(f"notebook: chapter map out of date — unassigned {missing}, not found {unknown}")
    out = PUBLIC / "notebook"
    shutil.rmtree(out, ignore_errors=True)
    # every page of every chapter, in reading order
    pages = []
    for ci, (slug, title, summary, titles) in enumerate(NOTEBOOK_CHAPTERS):
        chunks = paginate("".join(secs[t] for t in titles))
        for pi, md in enumerate(chunks):
            conv = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"])
            body = conv.convert(md)
            body = body.replace("<table>", '<div class="tablewrap"><table>').replace("</table>", "</table></div>")
            heads = re.findall(r'<h([23]) id="([^"]+)">(.*?)</h\1>', body)
            first = re.sub("<[^>]+>", "", heads[0][2]) if heads else title
            pages.append({"ci": ci, "pi": pi, "n": len(chunks), "slug": slug, "chapter": title, "summary": summary,
                          "url": f"/notebook/{slug}/" + (f"{pi + 1}/" if pi else ""), "title": first, "body": body,
                          "ids": [h[1] for h in heads]})
    anchors = {hid: p["url"] for p in pages for hid in p["ids"]}
    chapters = [{"slug": s, "title": t} for s, t, _, _ in NOTEBOOK_CHAPTERS]
    for k, p in enumerate(pages):
        strip = "".join(f'<a href="/notebook/{c["slug"]}/"{" aria-current=\"page\"" if j == p["ci"] else ""} title="{c["title"]}">{j + 1}</a>'
                        for j, c in enumerate(chapters))
        prev, nxt = (pages[k - 1] if k else None), (pages[k + 1] if k + 1 < len(pages) else None)
        lab = lambda q: q["title"] if q["ci"] == p["ci"] else f'{q["chapter"]}: {q["title"]}'
        pn = '<nav class="pn" aria-label="Previous and next">'
        pn += f'<a class="prev" href="{prev["url"]}"><small>← Previous</small>{lab(prev)}</a>' if prev else "<span></span>"
        pn += f'<a class="next" href="{nxt["url"]}"><small>Next →</small>{lab(nxt)}</a>' if nxt else "<span></span>"
        pn += "</nav>"
        dots = ""
        if p["n"] > 1:
            dots = '<nav class="pages" aria-label="Pages in this chapter">' + "".join(
                f'<a href="{q["url"]}"{" aria-current=\"page\"" if q is p else ""}>{q["pi"] + 1}</a>' for q in pages if q["ci"] == p["ci"]) + "</nav>"
        where = f'chapter {p["ci"] + 1} of {len(chapters)}' + (f' · page {p["pi"] + 1} of {p["n"]}' if p["n"] > 1 else "")
        head = (f'<header class="chap"><h1>{p["chapter"]}</h1><p class="deck">{p["summary"]}</p></header>' if p["pi"] == 0
                else f'<header class="chap"><h1 class="cont">{p["chapter"]} <span>continued</span></h1></header>')
        page = (f'<p class="crumb"><a href="/notebook/">Lab notebook</a> · {where}</p><nav class="parts" aria-label="Chapters">{strip}</nav>'
                f'{head}{dots}<article class="nbody">{p["body"]}</article>{pn}{DISCLAIMER}')
        name = f'{p["chapter"]}' + (f' ({p["pi"] + 1}/{p["n"]})' if p["n"] > 1 else "") + " — Lab notebook — shrov"
        write(PUBLIC / p["url"].strip("/") / "index.html", shell(name, p["summary"], page, current="Notebook"))
    cards = "".join(f'<li><a href="/notebook/{s}/"><span class="n">{i + 1:02d} · {sum(1 for q in pages if q["ci"] == i)} page{"s" if sum(1 for q in pages if q["ci"] == i) > 1 else ""}</span><b>{t}</b><span class="s">{d}</span></a></li>'
                    for i, (s, t, d, _) in enumerate(NOTEBOOK_CHAPTERS))
    index = ('<header class="hero"><p class="eyebrow">Lab notebook · Sep 2026</p><h1>The workings</h1>'
             '<p class="deck">The running record the paper was drawn from, in seven chapters of short pages — each experiment, the number it produced, and the corrections. '
             'Read <a href="/paper/">the paper</a> for the argument; read this for the arithmetic.</p></header>'
             f'<ol class="chapters">{cards}</ol>'
             '<p class="note">Names in <code>code</code> refer to the lab\'s software — a paper-trading harness against an Interactive Brokers <em>paper</em> account and a replay backtester. '
             'The code is not published; this notebook records what it measured. All capital is simulated.</p>' + DISCLAIMER)
    write(out / "index.html", shell("Lab notebook — shrov", "The working notebook behind Thirty-One Signals, Six Bets, in seven chapters.", index, current="Notebook"))
    return anchors


def fix_deep_links(anchors):
    """Point hand-written links like /notebook/...#some-heading at the page that now holds that heading."""
    for f in [PUBLIC / "index.html", PUBLIC / "about" / "index.html"]:
        s = f.read_text(encoding="utf-8")
        def repl(m):
            hid = m.group(1)
            if hid not in anchors:
                sys.exit(f"{f.relative_to(ROOT)}: link to notebook heading #{hid} that no longer exists")
            return f'href="{anchors[hid]}#{hid}"'
        f.write_text(re.sub(r'href="/notebook/[^"#]*#([^"]+)"', repl, s), encoding="utf-8")


SITE = "https://www.shrov.com"


def write_sitemap():
    """sitemap.xml for search engines: every page (index.html), no dates so the build stays reproducible."""
    urls = sorted(SITE + "/" + str(p.parent.relative_to(PUBLIC)).replace(".", "").strip("/") for p in PUBLIC.rglob("index.html"))
    urls = [u if u.endswith("/") else u + "/" for u in urls]
    body = "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
    (PUBLIC / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", help="path to the ibkr-lab checkout to refresh content/ from")
    a = ap.parse_args()
    if a.lab:
        refresh(a.lab)
    build_paper()
    fix_deep_links(build_notebook())
    write_sitemap()
    for p in PUBLIC.rglob("*.html"):
        check_clean(p.read_text(encoding="utf-8"), str(p.relative_to(ROOT)))
    print("built:", ", ".join(str(p.relative_to(ROOT)) for p in sorted(PUBLIC.rglob("*.html"))))


if __name__ == "__main__":
    main()
