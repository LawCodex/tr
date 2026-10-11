#!/usr/bin/env python3
"""Fetch Turkish legislation from Mevzuat Bilgi Sistemi (https://www.mevzuat.gov.tr).

Step 1: list every document of the selected categories via the site's own DataTables
        endpoint (POST /Anasayfa/MevzuatDatatable) -> <raw>/lists/<category>.json
Step 2: download the consolidated text of each document (HTML rendering of the official Word
        file, /anasayfa/MevzuatFihristDetayIframe?...) -> <raw>/html/<tur>/<tertip>.<no>.html.gz
        If the HTML is empty, fall back to the official PDF (/MevzuatMetin/<tur>.<tertip>.<no>.pdf).

Cached: re-runs only download what is missing (use --refresh-lists to re-list).

Usage: python tr_fetch.py [--raw DIR] [--workers N] [--only CAT,CAT] [--refresh-lists]
"""
import argparse
import concurrent.futures as cf
import gzip
import json
import os
import random
import sys
import threading
import time

import requests

BASE = "https://www.mevzuat.gov.tr"
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"

# category key -> (MevzuatTur form value, YonetmelikMevzuatTur)
CATEGORIES = {
    "kanun": ("Kanun", "OsmanliKanunu"),
    "khk": ("KHK", "OsmanliKanunu"),
    "tuzuk": ("Tuzuk", "OsmanliKanunu"),
    "cbk": ("CumhurbaskaniKararnameleri", "OsmanliKanunu"),
    "cb-bkk-yonetmelik": ("CumhurbaskanligiVeBakanlarKuruluYonetmelik", "OsmanliKanunu"),
    "kurum-yonetmelik": ("KurumVeKurulusYonetmeligi", "OsmanliKanunu"),
    "tum-yonetmelik": ("TumYonetmelik", "OsmanliKanunu"),
    "teblig": ("Teblig", "OsmanliKanunu"),
}

_local = threading.local()


def session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = UA
        _local.s = s
    return s


def req(method, url, **kw):
    delay = 2
    for attempt in range(7):
        try:
            r = session().request(method, url, timeout=120, **kw)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return r
            print(f"  HTTP {r.status_code} {url}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  ERR {e.__class__.__name__} {url}", file=sys.stderr)
        time.sleep(delay + random.random())
        delay = min(delay * 2, 120)
    raise RuntimeError(f"giving up on {url}")


def list_category(key, raw, refresh):
    out = os.path.join(raw, "lists", f"{key}.json")
    if os.path.exists(out) and not refresh:
        return json.load(open(out, encoding="utf-8"))
    tur, ytur = CATEGORIES[key]
    session().get(BASE + "/", timeout=60)  # cookies
    items, start, page = [], 0, 200
    while True:
        body = {
            "draw": 1, "start": start, "length": page,
            "parameters": {"MevzuatTur": tur, "YonetmelikMevzuatTur": ytur,
                           "AranacakIfade": "", "AranacakYer": "2", "MevzuatNo": "",
                           "BaslangicTarihi": "", "BitisTarihi": ""},
        }
        for attempt in range(6):
            r = req("POST", BASE + "/Anasayfa/MevzuatDatatable", json=body)
            try:
                j = r.json()
                break
            except ValueError:
                print(f"  non-JSON page at {start}, retrying", file=sys.stderr)
                time.sleep(10 * (attempt + 1))
        else:
            raise RuntimeError("listing failed")
        data = j.get("data") or j.get("Data") or []
        total = j.get("recordsTotal") or j.get("RecordsTotal") or 0
        items.extend(data)
        print(f"  list {key}: {len(items)}/{total}", file=sys.stderr)
        start += page
        if not data or start >= total:
            break
        time.sleep(1)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(items, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return items


def doc_paths(raw, it):
    d = os.path.join(raw, "html", str(it["mevzuatTur"]))
    stem = f"{it['mevzuatTertip']}.{it['mevzuatNo']}"
    return os.path.join(d, stem + ".html.gz"), os.path.join(d, stem + ".pdf")


def fetch_doc(raw, it):
    hp, pp = doc_paths(raw, it)
    if os.path.exists(hp) or os.path.exists(pp):
        return "cached"
    os.makedirs(os.path.dirname(hp), exist_ok=True)
    tur, tertip, no = it["mevzuatTur"], it["mevzuatTertip"], it["mevzuatNo"]
    url = (f"{BASE}/anasayfa/MevzuatFihristDetayIframe?MevzuatTur={tur}"
           f"&MevzuatNo={no}&MevzuatTertip={tertip}")
    r = req("GET", url)
    time.sleep(0.5)
    text = r.content if r.status_code == 200 else b""
    # an empty rendering is ~2-4 KB of boilerplate (styles + scripts)
    if len(text) > 6000 and (b"<p" in text or b"<table" in text or b"<P" in text):
        with gzip.open(hp + ".tmp", "wb") as f:
            f.write(text)
        os.replace(hp + ".tmp", hp)
        return "html"
    r = req("GET", f"{BASE}/MevzuatMetin/{tur}.{tertip}.{no}.pdf")
    time.sleep(0.5)
    if r.status_code == 200 and r.content[:4] == b"%PDF":
        with open(pp + ".tmp", "wb") as f:
            f.write(r.content)
        os.replace(pp + ".tmp", pp)
        return "pdf"
    # remember the miss so that re-runs do not retry endlessly
    with gzip.open(hp, "wb") as f:
        f.write(text)
    return "empty"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.join(os.path.dirname(__file__), "..", "..", "_raw", "tr"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only", default="")
    ap.add_argument("--refresh-lists", action="store_true")
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--tur", default="", help="only these MevzuatTur codes (comma list)")
    a = ap.parse_args()
    raw = os.path.abspath(a.raw)
    keys = a.only.split(",") if a.only else list(CATEGORIES)
    seen, todo = set(), []
    for k in keys:
        for it in list_category(k, raw, a.refresh_lists):
            key = (it["mevzuatTur"], it["mevzuatTertip"], it["mevzuatNo"])
            if a.tur and str(it["mevzuatTur"]) not in a.tur.split(","):
                continue
            if key not in seen:
                seen.add(key)
                todo.append(it)
    print(f"{len(todo)} unique documents", file=sys.stderr)
    if a.list_only:
        return
    stats = {}
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(fetch_doc, raw, it): it for it in todo}
        for i, f in enumerate(cf.as_completed(futs), 1):
            try:
                st = f.result()
            except Exception as e:  # noqa
                st = "error"
                print(f"  FAIL {futs[f]['url']}: {e}", file=sys.stderr)
            stats[st] = stats.get(st, 0) + 1
            if i % 200 == 0:
                print(f"  {i}/{len(todo)} {stats}", file=sys.stderr, flush=True)
    print(stats, file=sys.stderr)


if __name__ == "__main__":
    main()
