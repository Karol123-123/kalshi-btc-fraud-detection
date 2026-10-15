"""
BTC Fraud Detection Main Pipeline
full flow:
  1. Fetch data from Kalshi API
  2. Run anomaly detectors
  3. Build evidence brief
  4. Print results

Usage:
  python main.py            # live Kalshi data
  python main.py --demo     # synthetic demo data
"""
import argparse

from kalshi_client import fetch_btc_snapshot
from anomaly_detector import run_all_detectors
from evidence_brief import build_evidence_brief
from demo_data import generate_demo_data


def run_pipeline(use_demo: bool = False):
    """Execute the full fraud-detection pipeline."""

    print("BTC FRAUD DETECTION — Kalshi Markets\n")

    # Step 1
    if use_demo:
        snapshot = generate_demo_data()
        print("[1/4] Data loaded (demo)")
    else:
        try:
            snapshot = fetch_btc_snapshot()
        except Exception as e:
            print(f"[1/4] Kalshi API error: {e} — using demo data")
            snapshot = generate_demo_data()
        else:
            print(f"[1/4] Data loaded ({len(snapshot['trades'])} trades, {len(snapshot['markets'])} markets)")

    # ── Step 2 ──
    anomaly_report = run_all_detectors(snapshot["trades"])
    print(f"[2/4] Anomalies detected ({anomaly_report['total_flags']} flags — "
          f"{anomaly_report['high_severity']} HIGH, {anomaly_report['medium_severity']} MEDIUM)")

    # ── Step 3 ──
    brief = build_evidence_brief(
        anomaly_report,
        snapshot["markets"],
        snapshot.get("fetched_at", ""),
    )
    print(f"[3/4] Evidence brief built")

    # Step 4
    print(f"[4/4] Risk score: {anomaly_report['risk_score']} / 100")
    print()

    # Print the evidence brief
    print(brief)


def main():
    parser = argparse.ArgumentParser(description="BTC Fraud Detection")
    parser.add_argument("--demo", action="store_true", help="Use synthetic demo data")
    args = parser.parse_args()
    run_pipeline(use_demo=args.demo)


if __name__ == "__main__":
    main()
