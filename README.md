# makefun-gta6-trophy-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/mhmdrizzzki/makefun-gta6-trophy-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/mhmdrizzzki/makefun-gta6-trophy-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecast every Grand Theft Auto VI trophy's earn rate on Exophase at a case's target,
as five quantiles, for the lowest pinball loss on the logit scale.

A trophy's rate is `100 x earned / tracked`. Exophase expands the `tracked` panel in
jumps (a refresh), which makes rates fall, while `earned` rises smoothly as players
progress. The program models the two parts apart in log space, because for small rates
`logit(rate)` is close to `ln(earned) - ln(tracked)`:

- per trophy, `earned = clamp(rate)/100 x players_tracked` over every read that lists it
- `g`, the recent slope of `ln(earned)` per day, by least squares over the last day
- `gt`, the recent slope of `ln(tracked)` per day, the same way
- median `logit(last rate) + (g - gt) x horizon_days`, the change clamped
- spread `0.50 + 0.40 x sqrt(horizon_days)`, quantiles from the standard normal levels

Standard library only, no network, deterministic: both runs write the same bytes.

## Run it

```sh
MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=jbtwdd57&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
