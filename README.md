# LawCodex — Türkiye (`tr`)

The legislation of the Republic of Türkiye that is in force, as plain Markdown with one file per instrument,
in the original Turkish. The files are generated from the **official consolidated texts** ("tek metin",
i.e. with all amendments incorporated) published by **Mevzuat Bilgi Sistemi (MBS)**,
https://www.mevzuat.gov.tr. MBS is run by the Presidency of the Republic (Cumhurbaşkanlığı İdari İşler
Başkanlığı, Hukuk ve Mevzuat Genel Müdürlüğü).

Retrieved: **2026-10-12**. Each file's front matter also records its own `retrieved` date.

## Coverage

This repository contains every document that MBS lists in the categories below. The lists come from
the site's own search index (all entries, not a sample).

| Directory | Contents (MBS category) | Files |
| --- | --- | ---: |
| `anayasa/` | Türkiye Cumhuriyeti Anayasası (Law No. 2709, 1982, consolidated) | 1 |
| `kanunlar/<year>/` | Kanunlar: laws in force, including 9 Ottoman-era laws (Osmanlı kanunları) still in force | 915 |
| `khk/` | Kanun Hükmünde Kararnameler (decree-laws) in force | 63 |
| `cumhurbaskanligi-kararnameleri/` | Cumhurbaşkanlığı Kararnameleri (presidential decrees, post-2018) in force | 33 |
| `tuzukler/` | Tüzükler (101), Geçici Tüzükler (2), İç Tüzükler (4, e.g. the TBMM rules of procedure) | 107 |
| `yonetmelikler/cumhurbaskanligi/` | Cumhurbaşkanlığı Yönetmelikleri (presidential regulations) | 179 |
| `yonetmelikler/bakanlar-kurulu/<year>/` | Bakanlar Kurulu Yönetmelikleri (Council of Ministers regulations, pre-2018) | 148 |
| `yonetmelikler/kurum/<year>/` | Kurum ve Kuruluş Yönetmelikleri (regulations of ministries and agencies) | 3,655 |
| `yonetmelikler/universite/<year>/` | Üniversite Yönetmelikleri (regulations of universities) | 5,040 |
| `tebligler/<year>/` | Tebliğler (communiqués) | 4,466 |
| **Total** | | **14,607** |

The `<year>` in a path is the year of publication in the Resmî Gazete (Official Gazette), or the
year of adoption when no gazette date is known. Ottoman laws are filed under their Rumi/Hijri year
as given by MBS. Every directory holds fewer than 1,000 files.

### Not covered and known gaps

- **13 documents** are listed by MBS but have no text on the site: the viewer is empty and there
  is no PDF or Word file. They are 1 Kurum yönetmeliği (10391 Elektrik İç Tesisleri Yönetmeliği)
  and 12 Tebliğler (8629, 8631, 7964, 9557, 9570, 10864, 10914, 10986, 9971, 15733, 56, 22698).
- **Repealed laws** (MBS category "Mülga Kanunlar", 185 entries) and earlier versions of
  texts ("önceki metinler") are not included. Only the current consolidated text is included.
- **Cumhurbaşkanı Kararları** (individual presidential decisions), **Cumhurbaşkanlığı Genelgeleri**
  (circulars), the Cumhurbaşkanlığı Kararnameleri index (fihrist), and the original as-published
  texts in the Resmî Gazete are not included.
- **Court decisions** (Anayasa Mahkemesi, Yargıtay, Danıştay) are not included.
- **Images** are not copied. About 2,900 images in 372 files (maps, forms, scanned annex tables) are
  linked to the official files at `https://www.mevzuat.gov.tr/MevzuatMetin/...` and appear as
  `[görsel](url)`.
- A small number of older or irregularly formatted texts, mostly tebliğler, have no "Madde"
  structure. They are kept as plain paragraphs without article headings.

## File format

Each file has YAML front matter followed by the text:

```markdown
---
title: "TÜRK CEZA KANUNU"
identifier: "1.5.5237"            # MBS id: <MevzuatTur>.<Düstur tertibi>.<MevzuatNo>
number: "5237"                    # law / decree / MBS number
type: act                         # constitution | act | decree_law | presidential_decree | regulation | rules_of_procedure | communique
category: "Kanun"                 # MBS category name
jurisdiction: tr
language: tr
date: 2004-09-26                  # adoption date (Kabul Tarihi), else Resmî Gazete date
official_gazette_date: 2004-10-12
official_gazette_number: "25611"
dustur_tertip: "5"
status: in_force
consolidated: true
source: "https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=5237&MevzuatTur=1&MevzuatTertip=5"
retrieved: 2026-10-12
---

# TÜRK CEZA KANUNU[^1]

## BİRİNCİ KİTAP — Genel Hükümler
### BİRİNCİ KISIM — Temel İlkeler, Tanımlar ve Uygulama Alanı
#### BİRİNCİ BÖLÜM — Temel İlkeler ve Tanımlar
##### Madde 1 — Ceza Kanununun amacı
(1) Ceza Kanununun amacı; ...
```

- Divisions (KİTAP > KISIM > BAP > BÖLÜM > AYIRIM/KESİM/FASIL) become headings. The levels are
  assigned per document based on which division types it uses. Each division's name line is joined
  to its heading.
- Articles (`Madde N`, `Ek Madde N`, `Geçici Madde N`, `Madde N/A`...) are headings at the deepest
  level. The article's caption ("madde başlığı"), which precedes the article in Turkish texts, is
  appended to the heading after "—".
- Amendment notes inside the text, such as "(Değişik: 3/10/2001-4709/2 md.)", are kept verbatim.
  MBS's editorial footnotes are kept as Markdown footnotes (`[^n]`) at the end of each file.
- Bold and italic are preserved. Simple tables become Markdown tables. Tables with merged cells
  are kept as simplified HTML `<table>` markup.
- The header block of the official document (law number, adoption date, Resmî Gazete and Düstur
  references) goes into the front matter and is removed from the body.
- File names are `<number>-<slug>.md`, where the slug is an ASCII transliteration of the title
  (ç→c, ğ→g, ı→i, ö→o, ş→s, ü→u) cut at about 80 characters. Tüzük file names are prefixed with
  the year when the number does not already start with it.

## Source and licence

- Source: Mevzuat Bilgi Sistemi, https://www.mevzuat.gov.tr (official, Presidency of the
  Republic of Türkiye). MBS describes its service as offered "ücretsiz ve koşulsuz olarak herkesin
  kullanımına" (free and unconditionally to everyone). See https://www.mevzuat.gov.tr/hakkimizda.
  The site's robots.txt contains no `Disallow` rules and no crawl delay.
- Copyright: under Article 31 of Law No. 5846 (Fikir ve Sanat Eserleri Kanunu), laws,
  regulations, by-laws, notices, circulars and court decisions that are officially published or
  announced are **not protected** by copyright. The texts here are therefore in the public
  domain. The MBS consolidation is an official service. These Markdown files are an unofficial
  conversion: for legal purposes, rely on the Resmî Gazete and MBS.

## How to regenerate

```sh
pip install -r scripts/requirements.txt
python scripts/tr_fetch.py --workers 3   # lists every category, downloads texts into ../_raw/tr (cached)
python scripts/tr_convert.py             # writes the Markdown tree into this repository
```

`tr_fetch.py` uses the same endpoints as the MBS web interface:

- `POST /Anasayfa/MevzuatDatatable` returns the category listings, in pages of 200.
- `GET /anasayfa/MevzuatFihristDetayIframe?MevzuatTur=..&MevzuatNo=..&MevzuatTertip=..` returns
  the consolidated text, as an HTML rendering of the official Word file.

If a document has no HTML text, the script falls back to the official PDF
(`/MevzuatMetin/<tur>.<tertip>.<no>.pdf`). It identifies itself as
`LawCodex/1.0 (+https://github.com/LawCodex)`, keeps concurrency at 4 or less, and retries with
backoff. Use `--only kanun,khk,...` and `--tur` to refresh a subset, and `--refresh-lists` to
re-list the categories.
