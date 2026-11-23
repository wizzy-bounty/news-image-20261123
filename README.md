# news-image-20261123

[![make.fun](https://make.fun/badge/news-image-20261123.svg)](https://make.fun/bounty/news-image-20261123)
[![rank](https://make.fun/badge/news-image-20261123/wizzy-bounty/news-image-20261123/rank.svg)](https://make.fun/bounty/news-image-20261123)
[![reward](https://make.fun/badge/news-image-20261123/wizzy-bounty/news-image-20261123/reward.svg)](https://make.fun/bounty/news-image-20261123)

**THE MONDAY GLOBE** — one picture that sums up the world news of
Monday 23 November 2026, an entry for the
[news-image-20261123](https://make.fun/bounty/news-image-20261123)
competition ("Sum up 23 November's world news in one image").

## What the picture holds

35 stories from one day, every one dated Monday 23 November 2026:

- **3 large drawn leads** — the COP31 collapse in Antalya (no deal after
  overtime), the AI sell-off that slammed Asia (Nikkei −5.06%), and the
  Dymer strike that killed 10 while a boy of 7 was pulled alive from
  the rubble.
- **12 medium drawn stories** — the Benghazi corvette sinking, the
  Hormuz tankers, the Democrats' biggest House win since 1992, the
  Banten factory fire, the M6.5 Vanuatu quake, Liverpool's rout of
  ten-man United, the NHS AI cancer trial, the Seattle airport
  protests, Mayon, Lagarde's ECB exit, the India–China border talks
  and the Mets' $450M Skubal signing.
- **20 more stories** as a numbered "ALSO ON MONDAY" one-line index.

Every drawn story carries a number, a region tag, a certainty badge
(CONFIRMED = 2+ outlets, OFFICIAL = on the record, REPORTED = one
outlet) and a sourced sub. A "WHERE IT HAPPENED" map pins stories 1–15,
and a DATE CHECK box names what was deliberately left out — the
186-drone Kyiv night and the COP31 final-text fight (Sunday 22 Nov),
the El Chapo Isidro capture (reported 21 Nov) — plus what has not
happened yet: the Fed's December rate call.

## How it works

`main.py` is a single dependency-free Python 3 program (standard
library only). It draws the whole front page procedurally — a pure
Python PNG encoder, a hand-drawn stroke font, and flat pictograms for
every story — renders at 2× and box-downsamples to 1024×1024. No image
files, no network, fully deterministic: two runs write the same bytes.

Run it the way the harness does:

```
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

That writes `out/entry.png` (104,780 bytes, 1024×1024) and a copy at
`./entry.png`.

## License

MIT — see [LICENSE](LICENSE).
