"""
Detection is a rule-based statistical system that filters
suspicious trading patterns before LLM analysis. I plan on using
Ollama for a full analysis im still working on formatting.
three fraud pattern categories:
  1. Event-driven anomalies  (volume/price spikes near known events)
  2. Wash-trading signals    (repetitive price/quantity patterns)
  3. Coordinated manipulation (trade clustering & spoofing)
"""
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
import config



# Helpers
def _parse_ts(ts_str: str) -> float:
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    return dt.timestamp()


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# Pattern 1: Volume / Price Spike Detection

def detect_volume_spikes(trades: list[dict], window_sec: int = 300) -> list[dict]:
    if not trades:
        return []

    # Parse and sort
    parsed = []
    for t in trades:
        ts = _parse_ts(t["created_time"])
        qty = _safe_float(t.get("count_fp", t.get("count", 1)))
        parsed.append({"ts": ts, "qty": qty, "trade": t})
    parsed.sort(key=lambda x: x["ts"])

    # Bucket
    start = parsed[0]["ts"]
    end = parsed[-1]["ts"]
    buckets = defaultdict(lambda: {"qty": 0.0, "trades": []})
    for p in parsed:
        bucket_id = int((p["ts"] - start) // window_sec)
        buckets[bucket_id]["qty"] += p["qty"]
        buckets[bucket_id]["trades"].append(p["trade"])

    if len(buckets) < 3:
        return [] 

    volumes = [b["qty"] for b in buckets.values()]
    mean_v = statistics.mean(volumes)
    stdev_v = statistics.stdev(volumes) if len(volumes) > 1 else 1.0

    flags = []
    for bid, b in buckets.items():
        zscore = (b["qty"] - mean_v) / stdev_v if stdev_v > 0 else 0
        if zscore >= config.VOLUME_ZSCORE_THRESHOLD:
            window_start = start + bid * window_sec
            flags.append({
                "type": "volume_spike",
                "severity": "HIGH" if zscore > 3.0 else "MEDIUM",
                "z_score": round(zscore, 2),
                "window_volume": round(b["qty"], 2),
                "mean_volume": round(mean_v, 2),
                "window_start_utc": datetime.fromtimestamp(
                    window_start, tz=timezone.utc
                ).isoformat(),
                "trade_count_in_window": len(b["trades"]),
                "sample_trades": b["trades"][:5],
            })
    return flags


def detect_price_swings(trades: list[dict]) -> list[dict]:
    """
    Flag consecutive trades where the price changes by more than
    the configured threshold.
    """
    if len(trades) < 2:
        return []

    sorted_trades = sorted(trades, key=lambda t: t["created_time"])
    flags = []

    for i in range(1, len(sorted_trades)):
        prev_price = _safe_float(sorted_trades[i - 1].get("yes_price_dollars"))
        curr_price = _safe_float(sorted_trades[i].get("yes_price_dollars"))
        if prev_price == 0:
            continue
        pct_change = abs(curr_price - prev_price) / prev_price

        if pct_change >= config.PRICE_CHANGE_THRESHOLD:
            flags.append({
                "type": "price_swing",
                "severity": "HIGH" if pct_change > 0.30 else "MEDIUM",
                "pct_change": round(pct_change * 100, 2),
                "prev_price": prev_price,
                "curr_price": curr_price,
                "timestamp": sorted_trades[i]["created_time"],
                "trade": sorted_trades[i],
            })
    return flags


#  Pattern 2: Wash Trading Indicators
def detect_wash_trading(trades: list[dict], window_sec: int = 600) -> list[dict]:
    """
    Repeated identical (price, quantity) pairs within a time window
    Rapid alternation of taker_side (yes/no/yes/no...)
    """
    if len(trades) < 4:
        return []

    sorted_trades = sorted(trades, key=lambda t: t["created_time"])
    flags = []

    # Check for repeated price + qty
    combo_windows = defaultdict(list)
    for t in sorted_trades:
        ts = _parse_ts(t["created_time"])
        price = t.get("yes_price_dollars", "")
        qty = t.get("count_fp", t.get("count", ""))
        key = f"{price}|{qty}"
        combo_windows[key].append({"ts": ts, "trade": t})

    for key, entries in combo_windows.items():
        if len(entries) < 3:
            continue
        # Check if identical combos fall within the window
        entries.sort(key=lambda e: e["ts"])
        for i in range(len(entries) - 2):
            span = entries[i + 2]["ts"] - entries[i]["ts"]
            if span <= window_sec:
                flags.append({
                    "type": "wash_trade_repeated_combo",
                    "severity": "HIGH",
                    "combo": key,
                    "occurrences": len(entries),
                    "time_span_sec": round(span, 1),
                    "sample_trades": [e["trade"] for e in entries[:5]],
                })
                break  

    # Check for rapid side alternation 
    alternation_runs = 0
    for i in range(1, len(sorted_trades)):
        prev_side = sorted_trades[i - 1].get("taker_side", "")
        curr_side = sorted_trades[i].get("taker_side", "")
        if prev_side and curr_side and prev_side != curr_side:
            alternation_runs += 1
        else:
            alternation_runs = 0

        if alternation_runs >= 4:
            flags.append({
                "type": "wash_trade_side_alternation",
                "severity": "MEDIUM",
                "alternation_length": alternation_runs + 1,
                "start_time": sorted_trades[i - alternation_runs]["created_time"],
                "end_time": sorted_trades[i]["created_time"],
                "sample_trades": sorted_trades[
                    i - alternation_runs : i + 1
                ][:5],
            })
            alternation_runs = 0  

    return flags


#  Pattern 3: Coordinated Trade Clustering

def detect_trade_clustering(
    trades: list[dict],
    window_sec: int = None,
    min_count: int = None,
) -> list[dict]:
    """
    Flags trades from a short window, suggesting
    coordinated activity or bot-driven manipulation.
    """
    window_sec = window_sec or config.TRADE_CLUSTER_WINDOW_SEC
    min_count = min_count or config.TRADE_CLUSTER_MIN_COUNT

    if len(trades) < min_count:
        return []

    sorted_trades = sorted(trades, key=lambda t: t["created_time"])
    timestamps = [_parse_ts(t["created_time"]) for t in sorted_trades]

    flags = []
    i = 0
    while i < len(timestamps):
        j = i
        while j < len(timestamps) and timestamps[j] - timestamps[i] <= window_sec:
            j += 1
        cluster_size = j - i
        if cluster_size >= min_count:
            cluster_trades = sorted_trades[i:j]
            
            yes_count = sum(
                1 for t in cluster_trades if t.get("taker_side") == "yes"
            )
            no_count = cluster_size - yes_count
            bias = abs(yes_count - no_count) / cluster_size

            flags.append({
                "type": "trade_cluster",
                "severity": "HIGH" if cluster_size >= min_count * 2 else "MEDIUM",
                "cluster_size": cluster_size,
                "window_sec": round(timestamps[j - 1] - timestamps[i], 1),
                "directional_bias": round(bias, 2),
                "yes_pct": round(yes_count / cluster_size * 100, 1),
                "start_time": sorted_trades[i]["created_time"],
                "end_time": sorted_trades[j - 1]["created_time"],
                "sample_trades": cluster_trades[:5],
            })
            i = j  
        else:
            i += 1

    return flags



#  Master Analysis
def run_all_detectors(trades: list[dict]) -> dict:
    """
    Run every detector and return a consolidated anomaly report.
    """
    volume_flags = detect_volume_spikes(trades)
    price_flags = detect_price_swings(trades)
    wash_flags = detect_wash_trading(trades)
    cluster_flags = detect_trade_clustering(trades)

    all_flags = volume_flags + price_flags + wash_flags + cluster_flags

    # Count by severity
    high = sum(1 for f in all_flags if f["severity"] == "HIGH")
    medium = sum(1 for f in all_flags if f["severity"] == "MEDIUM")

    return {
        "total_trades_analyzed": len(trades),
        "total_flags": len(all_flags),
        "high_severity": high,
        "medium_severity": medium,
        "flags_by_type": {
            "volume_spikes": volume_flags,
            "price_swings": price_flags,
            "wash_trading": wash_flags,
            "trade_clusters": cluster_flags,
        },
        "risk_score": min(
            100, high * 25 + medium * 10
        ),  
    }
