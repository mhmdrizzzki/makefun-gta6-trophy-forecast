"""Forecast GTA VI trophy earn rates as five quantiles (make.fun gta6-trophy-rarity-forecast-01).

Reads every ``*.in`` case from ``$MAKEFUN_INPUT_DIR`` (default ``/input``), models each
trophy's recent earned/tracked growth separately in log space, and writes ``<id>.out``
to ``$MAKEFUN_OUTPUT_DIR`` (default ``/output``) as ``{"trophies":[{"id":..,"q":[..]}]}``.

The work happens in logit space, where small rates behave like ``ln(earned) - ln(tracked)``:
a trophy's median logit advances by its recent earned slope minus its tracked slope (the
latter dropping rates when Exophase widens its panel), and the spread widens like a random
walk with ``sqrt(horizon_days)``. Standard library only, deterministic, no network.
"""

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
EPOCH = datetime(2026, 11, 19, tzinfo=timezone.utc)

SPREAD_BASE = 1.35
SPREAD_PER_SQRT_DAY = 0.30
SPREAD_MIN = 0.95
SPREAD_MAX = 3.2

WINDOW_DAYS = 1.0
EARNED_GROWTH_CAP = 1.8
EARNED_GROWTH_SCALE = 0.72
TRACKED_GROWTH_CAP = 1.2
TRACKED_GROWTH_SCALE = 0.85
MEDIAN_SHIFT_CAP = 2.6


def clamp(x):
    return min(99.99, max(0.01, x))


def logit(pct):
    p = clamp(pct)
    return math.log(p / (100.0 - p))


def sigmoid(z):
    return 100.0 / (1.0 + math.exp(-z))


def round4(x):
    scaled = x * 10000.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000.0
    return int(value) if value.is_integer() else value


def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        value = float(value)
        if math.isfinite(value):
            return value
    return None


def _parse_time(text):
    if not isinstance(text, str) or not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _days(moment):
    return (moment - EPOCH).total_seconds() / 86400.0


def _slope(points):
    count = len(points)
    if count < 3:
        return 0.0
    mean_x = sum(x for x, _ in points) / count
    mean_y = sum(y for _, y in points) / count
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in points)
    denominator = sum((x - mean_x) ** 2 for x, _ in points)
    if denominator <= 0.0:
        return 0.0
    return numerator / denominator


def _series(case, index):
    history = case.get("history")
    if not isinstance(history, list):
        return []
    rows = []
    for read in history:
        if not isinstance(read, dict):
            continue
        rates = read.get("rates")
        if not isinstance(rates, list) or len(rates) <= index:
            continue
        rate = _number(rates[index])
        tracked = _number(read.get("players_tracked"))
        if rate is None or tracked is None or tracked <= 0.0:
            continue
        moment = _parse_time(read.get("slot", read.get("at")))
        if moment is None:
            continue
        earned = clamp(rate) / 100.0 * tracked
        if earned <= 0.0:
            continue
        rows.append((_days(moment), earned, tracked, rate))
    rows.sort(key=lambda row: row[0])
    return rows


def _forecast_trophy(series, horizon_days):
    if not series:
        median = logit(50.0)
    else:
        last_day = series[-1][0]
        window = [row for row in series if row[0] >= last_day - WINDOW_DAYS]
        earned_growth = _slope([(row[0], math.log(row[1])) for row in window])
        earned_growth = min(EARNED_GROWTH_CAP, max(0.0, earned_growth)) * EARNED_GROWTH_SCALE
        tracked_growth = _slope([(row[0], math.log(row[2])) for row in window])
        tracked_growth = min(TRACKED_GROWTH_CAP, max(0.0, tracked_growth)) * TRACKED_GROWTH_SCALE
        shift = (earned_growth - tracked_growth) * horizon_days
        shift = min(MEDIAN_SHIFT_CAP, max(-MEDIAN_SHIFT_CAP, shift))
        median = logit(series[-1][3]) + shift

    spread = SPREAD_BASE + SPREAD_PER_SQRT_DAY * math.sqrt(max(0.0, horizon_days))
    spread = min(SPREAD_MAX, max(SPREAD_MIN, spread))
    quantiles = [round4(sigmoid(median + z * spread)) for z in Z]
    return sorted(quantiles)


def forecast_case(case):
    trophies = case.get("trophies")
    if not isinstance(trophies, list):
        trophies = []
    horizon_minutes = _number(case.get("horizon_minutes"))
    horizon_days = (horizon_minutes if horizon_minutes is not None else 0.0) / 1440.0

    rows = []
    seen = set()
    for index, trophy in enumerate(trophies):
        if not isinstance(trophy, dict):
            continue
        trophy_id = trophy.get("id")
        if trophy_id in seen:
            continue
        seen.add(trophy_id)
        rows.append({"id": trophy_id, "q": _forecast_trophy(_series(case, index), horizon_days)})
    return {"trophies": rows}


def validate_forecast(forecast, case):
    """Assert the forecast is well formed before it is written; raise ValueError otherwise."""
    trophies = case.get("trophies")
    expected = [t.get("id") for t in trophies if isinstance(t, dict)] if isinstance(trophies, list) else []
    expected = list(dict.fromkeys(expected))

    rows = forecast.get("trophies") if isinstance(forecast, dict) else None
    if not isinstance(rows, list):
        raise ValueError("forecast has no trophies list")
    if len(rows) != len(expected):
        raise ValueError(f"expected {len(expected)} rows, got {len(rows)}")

    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("row is not an object")
        trophy_id = row.get("id")
        if trophy_id not in expected:
            raise ValueError(f"unknown trophy id {trophy_id!r}")
        if trophy_id in seen:
            raise ValueError(f"duplicate trophy id {trophy_id!r}")
        seen.add(trophy_id)
        q = row.get("q")
        if not isinstance(q, list) or len(q) != 5:
            raise ValueError(f"trophy {trophy_id!r} does not have five quantiles")
        previous = None
        for value in q:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"trophy {trophy_id!r} has a non-numeric quantile")
            if not math.isfinite(value) or value < 0.0 or value > 100.0:
                raise ValueError(f"trophy {trophy_id!r} has a quantile outside 0..100")
            if previous is not None and value < previous:
                raise ValueError(f"trophy {trophy_id!r} quantiles are not non-decreasing")
            previous = value
    if seen != set(expected):
        raise ValueError("forecast is missing one or more trophy ids")
    return True


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in"), key=lambda p: p.name):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"{path.name}: skipped ({exc})")
            continue
        if not isinstance(case, dict):
            print(f"{path.name}: skipped (not an object)")
            continue

        forecast = forecast_case(case)
        validate_forecast(forecast, case)
        case_id = case.get("id")
        if isinstance(case_id, (str, int)) and not isinstance(case_id, bool):
            stem = str(case_id)
        else:
            stem = path.stem
        target = OUTPUT_DIR / f"{stem}.out"
        payload = json.dumps(forecast, separators=(",", ":"), allow_nan=False) + "\n"
        target.write_text(payload, encoding="utf-8")
        print(f"{path.name}: {len(forecast['trophies'])} trophies -> {target.name} ({len(payload.encode('utf-8'))} bytes)")


if __name__ == "__main__":
    main()
