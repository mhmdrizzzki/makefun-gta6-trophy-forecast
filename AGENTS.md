# Entry: GTA VI trophy rarity forecast

An entry for make.fun's `gta6-trophy-rarity-forecast-01`.

- `main.py` — Python 3.13, standard library only, no network. Reads every `*.in`
  case file from `$MAKEFUN_INPUT_DIR` (else `/input`), forecasts each trophy's
  earn rate at the case's target as five quantiles, and writes `<id>.out` to
  `$MAKEFUN_OUTPUT_DIR` (else `/output`). Must be deterministic and finish in 8 s.

Run locally:

    MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 main.py
