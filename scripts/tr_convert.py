#!/usr/bin/env python3
"""Convert Mevzuat Bilgi Sistemi documents (fetched by tr_fetch.py) to LawCodex Markdown.

Usage: python tr_convert.py [--raw DIR] [--out REPO_DIR] [--only CAT,CAT] [--jobs N]
"""
import argparse
import datetime
import gzip
import json
import multiprocessing as mp
import os
import re
import sys
import unicodedata

from bs4 import BeautifulSoup, NavigableString, Tag

BASE = "https://www.mevzuat.gov.tr"
RETRIEVED = os.environ.get("TR_RETRIEVED", datetime.date.today().isoformat())

TUR = {
    0: ("kanun", "act", "Osmanlı Kanunu"),
    1: ("kanun", "act", "Kanun"),
    2: ("tuzuk", "regulation", "Tüzük"),
    3: ("yonetmelik-bkk", "regulation", "Bakanlar Kurulu Yönetmeliği"),
    4: ("khk", "decree_law", "Kanun Hükmünde Kararname"),
    6: ("tuzuk", "regulation", "Geçici Tüzük"),
    7: ("yonetmelik-kurum", "regulation", "Kurum ve Kuruluş Yönetmeliği"),
    8: ("yonetmelik-universite", "regulation", "Üniversite Yönetmeliği"),
    9: ("teblig", "communique", "Tebliğ"),
    10: ("yonetmelik-bkk", "regulation", "Bakanlar Kurulu Yönetmeliği"),
    17: ("tuzuk", "rules_of_procedure", "İç Tüzük"),
    19: ("cbk", "presidential_decree", "Cumhurbaşkanlığı Kararnamesi"),
    21: ("yonetmelik-cb", "regulation", "Cumhurbaşkanlığı Yönetmeliği"),
}

TR_MAP = str.maketrans({"ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i", "ö": "o",
                        "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u", "â": "a", "Â": "a",
                        "î": "i", "Î": "i", "û": "u", "Û": "u"})


def slugify(s, maxlen=80):
    s = s.translate(TR_MAP)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s or "x"


def iso(d):
    if not d:
        return None
    m = re.match(r"\s*(\d{1,2})[./](\d{1,2})[./](\d{4})", d)
    if not m:
        return None
    try:
        return datetime.date(int(m[3]), int(m[2]), int(m[1])).isoformat()
    except ValueError:
        return None


def clean_title(t):
    return re.sub(r"\s+", " ", t or "").strip()


def year_of(it):
    for k in ("resmiGazeteTarihi", "kabulTarih"):
        d = iso(it.get(k))
        if d:
            return d[:4]
    return "0000"


def rel_path(it):
    p = _rel_path(it)
    if it.get("_dup"):
        p = p[:-3] + f"-t{it['mevzuatTertip']}-{it['mevzuatTur']}.md"
    return p


def _rel_path(it):
    tur = int(it["mevzuatTur"])
    no = str(it["mevzuatNo"]).strip()
    tertip = str(it["mevzuatTertip"])
    slug = slugify(clean_title(it["mevAdi"]))
    y = year_of(it)
    if tur == 1 and no == "2709" and tertip == "5":
        return "anayasa/2709-turkiye-cumhuriyeti-anayasasi.md"
    cat = TUR[tur][0]
    if cat == "kanun":
        return f"kanunlar/{y}/{no}-{slug}.md"
    if cat == "khk":
        return f"khk/{no}-{slug}.md"
    if cat == "cbk":
        return f"cumhurbaskanligi-kararnameleri/{no}-{slug}.md"
    if cat == "tuzuk":
        return f"tuzukler/{y}-{no}-{slug}.md" if not no.startswith(y) else f"tuzukler/{no}-{slug}.md"
    if cat == "yonetmelik-cb":
        return f"yonetmelikler/cumhurbaskanligi/{no}-{slug}.md"
    if cat == "yonetmelik-bkk":
        return f"yonetmelikler/bakanlar-kurulu/{y}/{no}-{slug}.md"
    if cat == "yonetmelik-kurum":
        return f"yonetmelikler/kurum/{y}/{no}-{slug}.md"
    if cat == "yonetmelik-universite":
        return f"yonetmelikler/universite/{y}/{no}-{slug}.md"
    if cat == "teblig":
        return f"tebligler/{y}/{no}-{slug}.md"
    raise ValueError(tur)


# ---------------------------------------------------------------- HTML -> Markdown

ORD = (r"(?:B[İI]R[İI]NC[İI]|[İI]K[İI]NC[İI]|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞ[İI]NC[İI]|ALTINCI|YED[İI]NC[İI]|"
       r"SEK[İI]Z[İI]NC[İI]|DOKUZUNCU|ONUNCU|ON\s+\S+|Y[İI]RM[İI]NC[İI]|Y[İI]RM[İI]\s+\S+|"
       r"OTUZUNCU|OTUZ\s+\S+|KIRKINCI|KIRK\s+\S+|ELL[İI]NC[İI]|ELL[İI]\s+\S+|SON|ÖN|GENEL|"
       r"[0-9IVXLC]+\.?)")
DIV_WORDS = ["KİTAP", "KISIM", "BÖLÜM", "AYIRIM", "KESİM", "FASIL", "ALT BÖLÜM"]
DIV_RE = re.compile(r"^" + ORD + r"\s+(KİTAP|KITAP|KISIM|BAP|BÖLÜM|AYIRIM|KESİM|KESIM|FASIL|ALT\s+BÖLÜM)"
                    r"(?:\s*\[\^?\d+\]?)*\s*$")
MADDE_RE = re.compile(
    r"^((?:(?:Ek|EK|Geçici|GEÇİCİ|Mükerrer|MÜKERRER|Ek\s+Geçici|EK\s+GEÇİCİ|Geçici\s+Ek|GEÇİCİ\s+EK)\s+)?"
    r"(?:Madde|MADDE)\s+\d+(?:\s*/\s*[A-ZÇĞİÖŞÜa-z]+|\s*\(?[A-Z]\)?(?=\s*[-‐‑‒–—―−])|\s+[a-zçğıöşü](?=\s*[-‐‑‒–—―−]))?)"
    r"\s*(?:[-‐‑‒–—―−]|:|\.(?=\s)|$)\s*")
META_RE = re.compile(
    r"^(?:Kanun\s+Numarası|Kabul\s+Tarihi|Yayımlandığı|Yayımlandığı|Yetki\s+Kanun|Dayandığı|"
    r"Kanun\s+Hükmünde\s+Kararnamenin|Cumhurbaşkanlığı\s+Kararnamesinin|Bakanlar\s+Kurulu\s+Kararının|"
    r"Kararnamenin|Kararname\s+(?:Tarihi|Sayısı|No)|Resm[îi]\s+Gazete|Tertip|Tertibi|Düstur|Cilt|"
    r"Sayfa|Tarih|Sayı|No|Yönetmeliğin|Tebliğin|Tüzüğün|Karar\s+Sayısı|Karar\s+Tarihi|"
    r"Kabul\s+Edildiği)\b", re.I)
DATE_NO_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}\s+No\s*:")

INLINE_SKIP = {"script", "style", "img", "o:p"}


def norm_ws(s):
    s = s.replace(" ", " ").replace("\r", "")
    s = re.sub(r"[ \t\n\f\v]+", " ", s)
    return s


def md_escape(s):
    # minimal escaping so stray characters do not turn into markup
    s = s.replace("\\", "\\\\")
    s = re.sub(r"([*_`])", r"\\\1", s)
    s = s.replace("<", "&lt;").replace(">", "&gt;")
    return s


class Ctx:
    def __init__(self):
        self.images = 0


def is_bold(tag):
    while tag is not None and isinstance(tag, Tag):
        if tag.name in ("b", "strong"):
            return True
        st = tag.get("style") or ""
        if re.search(r"font-weight:\s*(bold|[6-9]00)", st):
            return True
        if tag.name in ("p", "td", "div", "body", "table"):
            return False
        tag = tag.parent
    return False


def is_italic(tag):
    while tag is not None and isinstance(tag, Tag):
        if tag.name in ("i", "em"):
            return True
        if tag.name in ("p", "td", "div", "body", "table"):
            return False
        tag = tag.parent
    return False


def inline(el, ctx, plain=False):
    """Return (markdown_text, plain_text, bold_chars, total_chars) for a block element."""
    runs = []  # (text, bold, italic, kind)

    def walk(node):
        for ch in node.children:
            if isinstance(ch, NavigableString):
                if type(ch).__name__ in ("Comment", "Doctype", "Declaration", "ProcessingInstruction"):
                    continue
                t = norm_ws(str(ch))
                if t:
                    runs.append((t, is_bold(ch.parent), is_italic(ch.parent), "t"))
            elif isinstance(ch, Tag):
                if ch.name in INLINE_SKIP:
                    if ch.name == "img":
                        ctx.images += 1
                        src = (ch.get("src") or "").strip()
                        if src and not src.startswith(("http:", "https:", "data:")):
                            src = BASE + "/MevzuatMetin/" + src.lstrip("/")
                        if src.startswith("http"):
                            runs.append((f"[görsel]({src.replace(' ', '%20')})", False, False, "img"))
                        else:
                            runs.append(("[görsel]", False, False, "img"))
                    continue
                if ch.name == "br":
                    runs.append(("\n", False, False, "br"))
                    continue
                if ch.name == "a" and (ch.get("href") or "").startswith("#_ftn") and \
                        not (ch.get("href") or "").startswith("#_ftnref"):
                    m = re.search(r"(\d+)", ch.get("href"))
                    if m:
                        runs.append((f"[^{m[1]}]", False, False, "fn"))
                        continue
                if ch.name == "a" and (ch.get("href") or "").startswith("#_ftnref"):
                    continue  # back-link inside a footnote
                walk(ch)

    walk(el)
    plain_txt = "".join(r[0] for r in runs)
    plain_txt = re.sub(r"[ ]*\n[ ]*", "\n", plain_txt).strip()
    total = sum(len(r[0].strip()) for r in runs if r[3] == "t")
    boldc = sum(len(r[0].strip()) for r in runs if r[3] == "t" and r[1])
    italc = sum(len(r[0].strip()) for r in runs if r[3] == "t" and r[2])
    if plain:
        return plain_txt, plain_txt, boldc, italc, total
    # merge runs with same formatting
    out, cur, curfmt = [], "", None
    for t, b, i, kind in runs:
        if kind != "t":
            if cur:
                out.append((cur, curfmt))
                cur, curfmt = "", None
            out.append((t, ("raw",)))
            continue
        fmt = (b, i)
        if fmt == curfmt:
            cur += t
        else:
            if cur:
                out.append((cur, curfmt))
            cur, curfmt = t, fmt
    if cur:
        out.append((cur, curfmt))
    md = []
    for t, fmt in out:
        if fmt == ("raw",):
            md.append(t)
            continue
        b, i = fmt
        core = t.strip()
        if not core:
            md.append(t)
            continue
        if not re.search(r"\w", core):
            md.append(md_escape(t))
            continue
        lead = t[: len(t) - len(t.lstrip())]
        trail = t[len(t.rstrip()):]
        core = md_escape(core)
        if b and i:
            core = f"***{core}***"
        elif b:
            core = f"**{core}**"
        elif i:
            core = f"*{core}*"
        md.append(lead + core + trail)
    md_txt = "".join(md)
    md_txt = re.sub(r"[ ]*\n[ ]*", "  \n", md_txt).strip()
    return md_txt, plain_txt, boldc, italc, total


def table_md(tbl, ctx):
    rows = []
    complex_ = False
    for tr in tbl.find_all("tr"):
        if tr.find_parent("table") is not tbl:
            complex_ = True
            continue
        cells = []
        for td in tr.find_all(["td", "th"], recursive=False):
            if td.get("colspan") not in (None, "1") or td.get("rowspan") not in (None, "1"):
                complex_ = True
            parts = []
            for p in td.find_all(["p", "div", "li"], recursive=True) or [td]:
                if p.find(["p", "div"]) and p.name == "div":
                    continue
                t = inline(p, ctx)[0]
                if t:
                    parts.append(t)
            if not parts:
                t = inline(td, ctx)[0]
                parts = [t] if t else []
            cells.append(" <br> ".join(x.replace("  \n", " <br> ") for x in parts))
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    if len(rows) == 1 and len(rows[0]) == 1:
        return rows[0][0]
    if complex_:
        return html_table(tbl, ctx)
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    esc = lambda c: c.replace("|", "\\|")
    lines = ["| " + " | ".join(esc(c) for c in rows[0]) + " |", "|" + " --- |" * n]
    for r in rows[1:]:
        lines.append("| " + " | ".join(esc(c) for c in r) + " |")
    return "\n".join(lines)


def html_table(tbl, ctx):
    """Simplified HTML table (keeps colspan/rowspan, drops styling)."""
    def cell_html(td):
        parts = []
        for p in td.find_all(["p"]) or [td]:
            t = inline(p, ctx, plain=True)[1]
            if t:
                parts.append(t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                             .replace("\n", "<br>"))
        return "<br>".join(parts)

    out = ["<table>"]
    for tr in tbl.find_all("tr"):
        if tr.find_parent("table") is not tbl:
            continue
        cells = []
        for td in tr.find_all(["td", "th"], recursive=False):
            attrs = ""
            for a in ("colspan", "rowspan"):
                v = td.get(a)
                if v and v != "1":
                    attrs += f' {a}="{v}"'
            if td.find("table"):
                inner = " ".join(html_table(t, ctx) for t in td.find_all("table", recursive=True)
                                 if t.find_parent("td") is td)
                cells.append(f"<td{attrs}>{inner}</td>")
            else:
                cells.append(f"<td{attrs}>{cell_html(td)}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def blocks_of(body):
    """Yield top-level content blocks (p/h*/li/table) in document order, excluding footnotes."""
    layout = {}

    def is_layout(t):
        if id(t) not in layout:
            rows = [tr for tr in t.find_all("tr") if tr.find_parent("table") is t]
            layout[id(t)] = bool(rows) and all(
                len(r.find_all(["td", "th"], recursive=False)) == 1 for r in rows)
        return layout[id(t)]

    for el in body.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "table", "li", "pre"]):
        if el.name == "table" and is_layout(el):
            continue
        if any(not is_layout(t) for t in el.find_parents("table")):
            continue
        if el.find_parent(["p", "li"]) is not None and el.name != "table":
            continue
        fp = el.find_parent("div", id=re.compile(r"^ftn\d+$"))
        if fp is not None:
            continue
        if el.find_parent("div", id=re.compile(r"^(edn\d+|ftn)$")) is not None:
            continue
        yield el


def footnotes_of(body, ctx):
    notes = []
    for div in body.find_all("div", id=re.compile(r"^ftn\d+$")):
        n = re.search(r"\d+", div["id"])[0]
        parts = []
        for p in div.find_all(["p", "table"]):
            if p.find_parent("table") is not None:
                continue
            if p.name == "table":
                parts.append(table_md(p, ctx).replace("\n", " "))
                continue
            t = inline(p, ctx)[0]
            t = re.sub(r"^\[\d+\]\s*", "", t.strip())
            if t:
                parts.append(t)
        txt = " ".join(parts).strip()
        txt = re.sub(r"^\*{1,3}\s*\*{1,3}", "", txt).strip()
        notes.append((n, txt))
    return notes


def classify_div(word):
    w = word.upper().replace("I", "İ") if word.upper() in ("KITAP", "KESIM") else word.upper()
    w = re.sub(r"\s+", " ", w)
    return {"KİTAP": 0, "KISIM": 1, "BAP": 1.5, "BÖLÜM": 2, "AYIRIM": 3, "KESİM": 3, "FASIL": 3,
            "ALT BÖLÜM": 3}.get(w, 3)


def convert_html(html, title):
    ctx = Ctx()
    # some documents have tag names mangled by Turkish case mapping (e.g. "<dıv")
    html = re.sub(r"<(/?)([A-Za-zıİ]*[ıİ][A-Za-zıİ]*)",
                  lambda m: "<" + m[1] + m[2].replace("ı", "i").replace("İ", "I"), html)
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    for t in body.find_all(["script", "style"]):
        t.decompose()
    blocks = list(blocks_of(body))
    items = []  # (kind, md, plain, boldfrac)
    for el in blocks:
        if el.name == "table":
            items.append(("table", el, None, 0))
            continue
        md, plain, b, i, tot = inline(el, ctx)
        if not plain.strip():
            continue
        cls = " ".join(el.get("class") or []).lower()
        items.append(("p", md, plain, (b / tot if tot else 0, i / tot if tot else 0, cls)))

    # fallback for documents whose text is not in block elements (e.g. <br>-separated)
    covered = sum(len(it[2]) for it in items if it[0] == "p") + sum(
        len(it[1].get_text()) for it in items if it[0] == "table")
    full = norm_ws(body.get_text(" ")).strip()
    if len(full) > 200 and covered < 0.5 * len(full):
        for br in body.find_all("br"):
            br.replace_with("\n")
        for blk in body.find_all(["p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
            blk.insert_before("\n")
            blk.insert_after("\n")
        for fn in body.find_all("div", id=re.compile(r"^ftn\d+$")):
            fn.extract()
        items = []
        for line in body.get_text().split("\n"):
            line = norm_ws(line).strip()
            if line:
                items.append(("p", md_escape(line), line, (0, 0, "")))

    # ---- header (title + metadata) removal
    title_fns = []
    start = 0
    seen_meta = False
    title_norm = re.sub(r"[^A-ZÇĞİÖŞÜ0-9]", "", title.upper().replace("I", "I"))
    for idx, it in enumerate(items[:40]):
        kind = it[0]
        if kind == "table":
            txt = it[1].get_text(" ", strip=True)
            if idx <= 3 and len(txt) < 2500 and re.search(r"Numarası|Resm[îi] Gazete|Kabul Tarihi|Sayısı|Tertip", txt) \
                    and not MADDE_RE.match(norm_ws(txt).strip()):
                title_fns += re.findall(r"\[(\d+)\]", txt[:600])
                start = idx + 1
                seen_meta = True
                continue
            tn = re.sub(r"\[\d+\]", "", txt)
            tn = re.sub(r"[^A-ZÇĞİÖŞÜ0-9]", "", tn.upper())
            if idx <= 3 and tn and tn in title_norm:
                title_fns += re.findall(r"\[(\d+)\]", txt[:600])
                start = idx + 1
                continue
            break
        plain = norm_ws(it[2]).strip()
        cls = it[3][2]
        if MADDE_RE.match(plain) or DIV_RE.match(plain.upper()):
            break
        if META_RE.match(plain) or DATE_NO_RE.match(plain) or "kantab" in cls or \
                re.match(r"^(Tertip|Cilt|Sayfa)\s*:", plain):
            seen_meta = True
            start = idx + 1
            continue
        if seen_meta:
            break
        letters = re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]", "", plain)
        upperish = letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.8
        pnorm = re.sub(r"\[\^?\d+\]", "", plain)
        pnorm = re.sub(r"[^A-ZÇĞİÖŞÜ0-9]", "", pnorm.upper())
        if ("baslk" in cls or upperish) and pnorm and pnorm in title_norm and idx < 12:
            title_fns += re.findall(r"\[\^(\d+)\]", it[1])
            start = idx + 1
            continue
        break
    items = items[start:]

    # ---- division levels
    present = set()
    for it in items:
        if it[0] == "p":
            m = DIV_RE.match(norm_ws(it[2]).strip().upper().replace("İ", "İ"))
            if m:
                present.add(classify_div(m.group(1)))
    order = sorted(present)
    lvl = {d: 2 + i for i, d in enumerate(order)}
    art_level = min(6, 2 + len(order))

    out = []
    i = 0
    n = len(items)
    pending_title = None  # index in out of a candidate article title

    def flush_pending():
        nonlocal pending_title
        pending_title = None

    while i < n:
        it = items[i]
        if it[0] == "table":
            t = table_md(it[1], ctx)
            if t:
                out.append(t)
            flush_pending()
            i += 1
            continue
        md, plain = it[1], norm_ws(it[2]).strip()
        bfrac, ifrac, cls = it[3]
        up = plain.upper()
        m = DIV_RE.match(up)
        if m and len(plain) < 80:
            d = classify_div(m.group(1))
            head = re.sub(r"\*+", "", md).replace("  \n", " ").strip()
            head = re.sub(r"\\([*_`])", r"\1", head)
            # following line is the division name if short and not an article/division
            if i + 1 < n and items[i + 1][0] == "p":
                nxt = norm_ws(items[i + 1][2]).strip()
                if len(nxt) < 200 and not MADDE_RE.match(nxt) and not DIV_RE.match(nxt.upper()) \
                        and not nxt.endswith((".", ";", ",")) and not nxt.startswith("("):
                    nmd = re.sub(r"\*+", "", items[i + 1][1]).replace("  \n", " ").strip()
                    nmd = re.sub(r"\\([*_`])", r"\1", nmd)
                    head = f"{head} — {nmd}"
                    i += 1
            out.append("#" * lvl.get(d, 2) + " " + head)
            flush_pending()
            i += 1
            continue
        mm = MADDE_RE.match(plain)
        if mm:
            label = re.sub(r"\s+", " ", mm.group(1)).strip()
            # article title = previous short emphasised paragraph
            heading_title = None
            if pending_title is not None and pending_title == len(out) - 1:
                heading_title = out.pop()
            # remove label from markdown text
            rest = strip_label(md, mm.group(0))
            h = "#" * art_level + " " + label
            if heading_title:
                ht = re.sub(r"\*+", "", heading_title).replace("  \n", " ").strip()
                ht = re.sub(r"\\([*_`])", r"\1", ht)
                h += " — " + ht
            out.append(h)
            if rest:
                out.append(rest)
            flush_pending()
            i += 1
            continue
        # candidate article title?
        if len(plain) < 250 and (bfrac > 0.9 or ifrac > 0.9) and not plain.endswith((".", ";", ",")) \
                and not plain.startswith("(") and i + 1 < n and items[i + 1][0] == "p" \
                and MADDE_RE.match(norm_ws(items[i + 1][2]).strip()):
            out.append(md)
            pending_title = len(out) - 1
            i += 1
            continue
        out.append(md)
        flush_pending()
        i += 1

    notes = footnotes_of(body, ctx)
    return out, notes, title_fns, ctx


def strip_label(md, label_plain):
    """Remove the 'Madde N –' prefix (plain text) from a markdown paragraph, keeping emphasis balanced."""
    target = re.sub(r"\s+", "", label_plain)
    consumed = 0
    j = 0
    while j < len(md) and consumed < len(target):
        c = md[j]
        if c == "*" or c.isspace():
            j += 1
            continue
        if c == "\\" and j + 1 < len(md):
            j += 2
            consumed += 1
            continue
        j += 1
        consumed += 1
    # swallow trailing whitespace / markers immediately after the label
    prefix, rest = md[:j], md[j:]
    stack = []
    for tok in re.findall(r"\*+", prefix):
        if stack and stack[-1] == tok:
            stack.pop()
        else:
            stack.append(tok)
    rest = rest.lstrip()
    while True:
        m = re.match(r"^(\*+)", rest)
        if m and stack and stack[-1] == m.group(1):
            stack.pop()
            rest = rest[len(m.group(1)):].lstrip()
        else:
            break
    if stack:
        rest = "".join(stack) + rest
    rest = rest.strip()
    if re.fullmatch(r"\**", rest):
        return ""
    return rest


def pdf_text(path):
    from pypdf import PdfReader
    r = PdfReader(path)
    paras = []
    for pg in r.pages:
        t = pg.extract_text() or ""
        paras.append(t)
    txt = "\n".join(paras)
    lines = [norm_ws(l).strip() for l in txt.split("\n")]
    return [md_escape(l) for l in lines if l]


def yaml_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def front_matter(it):
    tur = int(it["mevzuatTur"])
    cat, typ, turname = TUR[tur]
    if tur == 1 and str(it["mevzuatNo"]) == "2709":
        typ = "constitution"
    title = clean_title(it["mevAdi"])
    no = str(it["mevzuatNo"]).strip()
    tertip = str(it["mevzuatTertip"])
    fm = [("title", yaml_str(title)),
          ("identifier", yaml_str(f"{tur}.{tertip}.{no}")),
          ("number", yaml_str(no)),
          ("type", typ),
          ("category", yaml_str(turname)),
          ("jurisdiction", "tr"),
          ("language", "tr")]
    kd = iso(it.get("kabulTarih"))
    rg = iso(it.get("resmiGazeteTarihi"))
    if kd or rg:
        fm.append(("date", kd or rg))
    if rg:
        fm.append(("official_gazette_date", rg))
    if it.get("resmiGazeteSayisi"):
        fm.append(("official_gazette_number", yaml_str(clean_title(it["resmiGazeteSayisi"]))))
    fm.append(("dustur_tertip", yaml_str(tertip)))
    fm.append(("status", "in_force"))
    fm.append(("consolidated", "true"))
    fm.append(("source", yaml_str(f"{BASE}/mevzuat?MevzuatNo={no}&MevzuatTur={tur}&MevzuatTertip={tertip}")))
    fm.append(("retrieved", RETRIEVED))
    return "---\n" + "\n".join(f"{k}: {v}" for k, v in fm) + "\n---\n"


def convert_one(args):
    raw, outdir, it = args
    tur, tertip, no = it["mevzuatTur"], it["mevzuatTertip"], str(it["mevzuatNo"]).strip()
    d = os.path.join(raw, "html", str(tur))
    hp = os.path.join(d, f"{tertip}.{no}.html.gz")
    pp = os.path.join(d, f"{tertip}.{no}.pdf")
    rel = rel_path(it)
    title = clean_title(it["mevAdi"])
    body_lines, notes, title_fns, images, src = None, [], [], 0, "html"
    try:
        if os.path.exists(hp) and os.path.getsize(hp) > 0:
            html = gzip.open(hp).read().decode("utf-8", "replace")
            if len(html) > 6000:
                body_lines, notes, title_fns, ctx = convert_html(html, title)
                images = ctx.images
        if not body_lines and os.path.exists(pp):
            body_lines = pdf_text(pp)
            src = "pdf"
    except Exception as e:  # noqa
        return rel, "error", f"{e.__class__.__name__}: {e}", 0
    if not body_lines:
        return rel, "missing", "", 0
    h1 = "# " + md_escape(title) + "".join(f"[^{n}]" for n in dict.fromkeys(title_fns))
    parts = [front_matter(it), h1, ""]
    if src == "pdf":
        parts += ["*Metin resmî PDF dosyasından otomatik olarak çıkarılmıştır.*", ""]
    text = "\n\n".join(body_lines)
    parts.append(text)
    used = set(re.findall(r"\[\^(\d+)\]", text + h1))
    fn_lines = []
    for nn, t in notes:
        if t:
            fn_lines.append(f"[^{nn}]: {t}")
    if fn_lines:
        parts += ["", "---", "", "\n".join(fn_lines)]
    md = "\n".join(parts).rstrip() + "\n"
    md = re.sub(r"\n{3,}", "\n\n", md)
    path = os.path.join(outdir, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(md)
    return rel, "ok" if src == "html" else "pdf", "", len(md)


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--raw", default=os.path.join(here, "..", "..", "_raw", "tr"))
    ap.add_argument("--out", default=os.path.join(here, ".."))
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--ids", default="", help="comma list of tur.tertip.no to convert")
    a = ap.parse_args()
    raw, out = os.path.abspath(a.raw), os.path.abspath(a.out)
    seen, todo = set(), []
    keys = a.only.split(",") if a.only else sorted(f[:-5] for f in os.listdir(os.path.join(raw, "lists")))
    for k in keys:
        for it in json.load(open(os.path.join(raw, "lists", f"{k}.json"), encoding="utf-8")):
            key = (it["mevzuatTur"], str(it["mevzuatTertip"]), str(it["mevzuatNo"]).strip())
            if key in seen or int(it["mevzuatTur"]) not in TUR:
                continue
            if a.ids and ".".join(map(str, key)) not in a.ids.split(","):
                continue
            seen.add(key)
            todo.append(it)
    # disambiguate path collisions
    paths = {}
    for it in todo:
        p = rel_path(it)
        paths.setdefault(p, []).append(it)
    jobs = []
    for p, its in paths.items():
        if len(its) > 1:
            for it in its:
                it["_dup"] = True
        jobs += [(raw, out, it) for it in its]
    stats, results = {}, []
    with mp.Pool(a.jobs) as pool:
        for rel, st, msg, size in pool.imap_unordered(convert_one, jobs, chunksize=4):
            stats[st] = stats.get(st, 0) + 1
            results.append({"path": rel, "status": st, "msg": msg, "size": size})
            if st in ("error",):
                print(f"  {st} {rel} {msg}", file=sys.stderr)
    print(stats, file=sys.stderr)
    json.dump(sorted(results, key=lambda r: r["path"]),
              open(os.path.join(raw, "convert-results.json"), "w"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
