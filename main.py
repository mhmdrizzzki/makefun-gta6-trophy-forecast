import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
REFERENCE = datetime(2026, 11, 19, tzinfo=timezone.utc)


def clamp(x):
    return min(99.99, max(0.01, x))


def logit(pct):
    p = clamp(pct)
    return math.log(p / (100.0 - p))


def sigmoid(z):
    return 100.0 / (1.0 + math.exp(-z))


def round4(x):
    value = round(x, 4)
    if value == 0.0:
        return 0.0
    return value


def time_days(text):
    if not isinstance(text, str):
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (moment - REFERENCE).total_seconds() / 86400.0


def slope_ls(points):
    n = len(points)
    if n < 2:
        return None
    mean_x = sum(p[0] for p in points) / n
    mean_y = sum(p[1] for p in points) / n
    num = 0.0
    den = 0.0
    for x, y in points:
        dx = x - mean_x
        num += dx * (y - mean_y)
        den += dx * dx
    if den <= 1e-12:
        return None
    return num / den


def as_float(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def forecast_case(case):
    history = case.get("history") or []
    trophies = case.get("trophies") or []

    horizon_days = as_float(case.get("horizon_minutes"))
    horizon_days = max(0.0, horizon_days if horizon_days is not None else 0.0) / 1440.0

    times = []
    tracked = []
    for read in history:
        times.append(time_days(read.get("at")))
        value = as_float(read.get("players_tracked"))
        tracked.append(value if value is not None else 0.0)

    readable = [t for t in times if t is not None]
    gt = 0.0
    if readable:
        last_tracked_time = readable[-1]
        points = []
        for i in range(len(history)):
            t = times[i]
            if t is None or tracked[i] <= 0.0:
                continue
            if t >= last_tracked_time - 1.0:
                points.append((t, math.log(tracked[i])))
        if len(points) >= 3:
            slope = slope_ls(points)
            if slope is not None:
                gt = min(1.2, max(0.0, slope)) * 0.85

    spread = 0.50 + 0.40 * math.sqrt(max(0.0, horizon_days))
    spread = min(3.0, max(0.18, spread))

    rows = []
    for index, trophy in enumerate(trophies):
        series = []
        for i, read in enumerate(history):
            if times[i] is None or tracked[i] <= 0.0:
                continue
            rates = read.get("rates") or []
            rate = as_float(rates[index]) if index < len(rates) else None
            if rate is None:
                continue
            earned = clamp(rate) / 100.0 * tracked[i]
            series.append((times[i], earned, rate))

        if not series:
            median = 0.0
        else:
            last_t, last_earned, last_rate = series[-1]
            points = []
            for t, earned, _ in series:
                if earned > 0.0 and t >= last_t - 1.0:
                    points.append((t, math.log(earned)))
            g = 0.0
            if len(points) >= 3:
                slope = slope_ls(points)
                if slope is not None:
                    g = min(1.8, max(0.0, slope)) * 0.72
            change = (g - gt) * horizon_days
            change = min(2.6, max(-2.6, change))
            median = logit(last_rate) + change

        quantiles = sorted(round4(sigmoid(median + z * spread)) for z in Z)
        rows.append({"id": trophy.get("id"), "q": quantiles})

    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        with path.open("r", encoding="utf-8") as handle:
            case = json.load(handle)
        forecast = forecast_case(case)
        out_path = OUTPUT_DIR / (path.stem + ".out")
        out_path.write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        print(f"{path.stem}: {len(forecast['trophies'])} trophies")


if __name__ == "__main__":
    main()
