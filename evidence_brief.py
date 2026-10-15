"""
Evidence Brief Builder

Takes raw anomaly flags from the statistical detector and compresses
them into a structured, concise brief that the LLM can reason over
efficiently. The LLM never sees raw trade logs only this brief.

Output is capped to the TOP 5 most significant flags per category
to keep terminal output readable. Full details are saved in the
JSON report file.
"""
from datetime import datetime, timezone

# Max flags
MAX_FLAGS_PER_SECTION = 5


def _summarize_trades(sample_trades: list[dict], max_shown: int = 3) -> str:
    """Summarize a few sample trades into a readable line."""
    lines = []
    for t in sample_trades[:max_shown]:
        price = t.get("yes_price_dollars", "?")
        qty = t.get("count_fp", t.get("count", "?"))
        side = t.get("taker_side", "?")
        ts = t.get("created_time", "?")
        lines.append(f"  \u2022 ${price} \u00d7 {qty} contracts ({side}) at {ts}")
    if len(sample_trades) > max_shown:
        lines.append(f"  \u2022 {len(sample_trades) - max_shown} more")
    return "\n".join(lines)


def _truncation_notice(total: int, shown: int) -> str:
    remaining = total - shown
    if remaining > 0:
        return f"\n {remaining} more flags (see full report JSON for details)\n"
    return ""


def build_evidence_brief(
    anomaly_report: dict,
    market_info: list[dict],
    snapshot_time: str = "",
) -> str:
    """
    Build a structured text brief for the LLM.

    Returns a plain-text document with sections for:
      - Market context
      - Each anomaly category (TOP 5 most significant flags)
      - Overall risk assessment numbers
    """
    brief_parts = []
    cap = MAX_FLAGS_PER_SECTION

    # Header
    ts = snapshot_time or datetime.now(timezone.utc).isoformat()
    brief_parts.append(
        "\u2550" * 55 + "\n"
        " FRAUD DETECTION EVIDENCE BRIEF\n"
        f" Generated: {ts}\n"
        + "\u2550" * 55 + "\n"
    )

    # Market Context 
    brief_parts.append("SECTION 1: MARKET CONTEXT")
    if market_info:
        for m in market_info[:5]:
            ticker = m.get("ticker", "?")
            title = m.get("yes_sub_title", m.get("title", "?"))
            vol = m.get("volume_fp", "0")
            price = m.get("last_price_dollars", "?")
            status = m.get("status", "?")
            brief_parts.append(
                f"  Market: {ticker}\n"
                f"    Title : {title}\n"
                f"    Status: {status}  |  Last Price: ${price}  |  Volume: {vol}"
            )
    else:
        brief_parts.append("  No market data available.")
    brief_parts.append("")

    # Summary Dashboard
    brief_parts.append("SECTION 2: ANALYSIS SUMMARY")
    brief_parts.append(
        f"  Total trades analyzed : {anomaly_report['total_trades_analyzed']}\n"
        f"  Total flags raised    : {anomaly_report['total_flags']}\n"
        f"  HIGH severity         : {anomaly_report['high_severity']}\n"
        f"  MEDIUM severity       : {anomaly_report['medium_severity']}\n"
        f"  Composite risk score  : {anomaly_report['risk_score']} / 100"
    )
    brief_parts.append("")

    flags = anomaly_report["flags_by_type"]

    # Volume Spikes (sorted by z-score) 
    vol_flags = flags.get("volume_spikes", [])
    sorted_vol = sorted(vol_flags, key=lambda f: f.get("z_score", 0), reverse=True)
    shown = sorted_vol[:cap]
    brief_parts.append(
        f"SECTION 3: VOLUME SPIKE ANOMALIES  "
        f"({len(vol_flags)} total showing top {min(cap, len(vol_flags))})"
    )
    if shown:
        for i, f in enumerate(shown, 1):
            brief_parts.append(
                f"  [{i}] {f['severity']} \u2014 z-score {f['z_score']}\n"
                f"      Window start : {f['window_start_utc']}\n"
                f"      Window volume: {f['window_volume']}  (mean: {f['mean_volume']})\n"
                f"      Trades in window: {f['trade_count_in_window']}"
            )
        brief_parts.append(_truncation_notice(len(vol_flags), len(shown)))
    else:
        brief_parts.append("  None detected.\n")

    # Price Swings (sorted by % change)
    price_flags = flags.get("price_swings", [])
    sorted_price = sorted(price_flags, key=lambda f: f.get("pct_change", 0), reverse=True)
    shown = sorted_price[:cap]
    brief_parts.append(
        f"SECTION 4: PRICE SWING ANOMALIES  "
        f"({len(price_flags)} total, showing top {min(cap, len(price_flags))})"
    )
    if shown:
        for i, f in enumerate(shown, 1):
            brief_parts.append(
                f"  [{i}] {f['severity']} \u2014 {f['pct_change']}% change\n"
                f"      From ${f['prev_price']} \u2192 ${f['curr_price']}  at {f['timestamp']}"
            )
        brief_parts.append(_truncation_notice(len(price_flags), len(shown)))
    else:
        brief_parts.append("  None detected.\n")

    # Wash Trading (combos sorted by occurrences)
    wash_flags = flags.get("wash_trading", [])
    combo_flags = [f for f in wash_flags if f["type"] == "wash_trade_repeated_combo"]
    alt_flags = [f for f in wash_flags if f["type"] == "wash_trade_side_alternation"]
    sorted_combos = sorted(combo_flags, key=lambda f: f.get("occurrences", 0), reverse=True)
    shown = sorted_combos[:cap]
    brief_parts.append(
        f"SECTION 5: WASH-TRADING INDICATORS  "
        f"({len(wash_flags)} total: {len(combo_flags)} repeated combos, "
        f"{len(alt_flags)} side alternations \u2014 showing top {min(cap, len(combo_flags))} combos)"
    )
    if shown:
        for i, f in enumerate(shown, 1):
            brief_parts.append(
                f"  [{i}] {f['severity']} \u2014 {f.get('combo', '?')}  "
                f"\u00d7{f.get('occurrences', '?')} in {f.get('time_span_sec', '?')}s"
            )
        brief_parts.append(_truncation_notice(len(combo_flags), len(shown)))
    else:
        brief_parts.append("  None detected.\n")

    # Trade Clusters (sorted by cluster size) 
    cluster_flags = flags.get("trade_clusters", [])
    sorted_clusters = sorted(cluster_flags, key=lambda f: f.get("cluster_size", 0), reverse=True)
    shown = sorted_clusters[:cap]
    high_count = sum(1 for f in cluster_flags if f["severity"] == "HIGH")
    brief_parts.append(
        f"SECTION 6: COORDINATED TRADE CLUSTERS  "
        f"({len(cluster_flags)} total, {high_count} HIGH \u2014 "
        f"showing top {min(cap, len(cluster_flags))} by size)"
    )
    if shown:
        for i, f in enumerate(shown, 1):
            brief_parts.append(
                f"  [{i}] {f['severity']} \u2014 {f['cluster_size']} trades "
                f"in {f['window_sec']}s  |  "
                f"Bias: {f['directional_bias']} (YES: {f['yes_pct']}%)\n"
                f"      Period: {f['start_time']} \u2192 {f['end_time']}"
            )
        brief_parts.append(_truncation_notice(len(cluster_flags), len(shown)))
    else:
        brief_parts.append("  None detected.\n")

    brief_parts.append("\u2550" * 55)
    brief_parts.append("END OF EVIDENCE BRIEF")
    brief_parts.append("\u2550" * 55)

    return "\n".join(brief_parts)
