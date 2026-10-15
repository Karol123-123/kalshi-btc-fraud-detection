"""
Demo Data Generator — Creates realistic synthetic Kalshi BTC trade data
with intentionally injected fraud patterns for testing.

Generates three scenarios:
  A) Normal baseline trading (organic market behavior)
  B) Injected volume spike near a simulated "event" (Pattern 1)
  C) Injected wash-trading sequence (Pattern 2)
  D) Injected coordinated trade cluster (Pattern 3)
"""
import random
import uuid
from datetime import datetime, timedelta, timezone


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _trade(
    ticker: str,
    price: float,
    qty: float,
    side: str,
    timestamp: datetime,
) -> dict:
    return {
        "trade_id": str(uuid.uuid4())[:12],
        "ticker": ticker,
        "count_fp": f"{qty:.2f}",
        "yes_price_dollars": f"{price:.4f}",
        "no_price_dollars": f"{1 - price:.4f}",
        "taker_side": side,
        "created_time": _ts(timestamp),
    }


def generate_demo_data() -> dict:
    random.seed(42)  # reproducible

    ticker = "KXBTC-26APR25-B100K"
    base_time = datetime(2026, 4, 7, 14, 0, 0, tzinfo=timezone.utc)

    trades = []

  
    #  Phase A: Normal baseline trading
    #  80 organic trades spread over 4 hours
    price = 0.55
    for i in range(80):
        t = base_time + timedelta(minutes=random.uniform(0, 240))
        price += random.gauss(0, 0.008)
        price = max(0.05, min(0.95, price))
        qty = round(random.uniform(1, 15), 2)
        side = random.choice(["yes", "no"])
        trades.append(_trade(ticker, price, qty, side, t))

   
    #  Phase B: event driven vol spike
    #  Simulates a burst of 25 trades in 5 minutes right before
    #  a hypothetical "Fed rate decision leak." All trades push
    #  the YES price up aggressively.
  
    event_time = base_time + timedelta(hours=4, minutes=30)
    spike_price = 0.62
    for i in range(25):
        t = event_time + timedelta(seconds=random.uniform(0, 300))
        spike_price += random.uniform(0.005, 0.02)  
        spike_price = min(0.92, spike_price)
        qty = round(random.uniform(20, 80), 2)  
        trades.append(_trade(ticker, spike_price, qty, "yes", t))

   
    #  Phase C: WASH TRADING 
    #  Repeated identical price + qty combos with alternating
    #  taker_side classic self dealing signature.
    wash_time = base_time + timedelta(hours=6)
    wash_price = 0.70
    wash_qty = 10.00
    for i in range(12):
        t = wash_time + timedelta(seconds=i * 45)
        side = "yes" if i % 2 == 0 else "no"
        trades.append(_trade(ticker, wash_price, wash_qty, side, t))

    for i in range(6):
        t = wash_time + timedelta(minutes=15, seconds=i * 30)
        side = "yes" if i % 2 == 0 else "no"
        trades.append(_trade(ticker, 0.68, 5.00, side, t))

    
    #  Phase D: COORDINATED CLUSTER (hour 8:00–8:02)
    #  15 trades crammed into 2 minutes, all on the YES side,
    #  suggesting bot coordination or spoofing.
   
    cluster_time = base_time + timedelta(hours=8)
    cluster_price = 0.74
    for i in range(15):
        t = cluster_time + timedelta(seconds=random.uniform(0, 120))
        cluster_price += random.uniform(-0.005, 0.015)
        cluster_price = min(0.95, cluster_price)
        qty = round(random.uniform(5, 25), 2)
        trades.append(_trade(ticker, cluster_price, qty, "yes", t))


    #  Phase E: More normal trading after
    
    price = 0.72
    for i in range(40):
        t = base_time + timedelta(hours=8, minutes=random.uniform(10, 120))
        price += random.gauss(0, 0.008)
        price = max(0.05, min(0.95, price))
        qty = round(random.uniform(1, 12), 2)
        side = random.choice(["yes", "no"])
        trades.append(_trade(ticker, price, qty, side, t))

    # Sort everything by timestamp
    trades.sort(key=lambda t: t["created_time"])


    markets = [
        {
            "ticker": ticker,
            "event_ticker": "KXBTC-26APR25",
            "market_type": "binary",
            "yes_sub_title": "Bitcoin above $100,000 by April 26",
            "no_sub_title": "Bitcoin at or below $100,000 by April 26",
            "status": "active",
            "last_price_dollars": f"{trades[-1]['yes_price_dollars']}",
            "volume_fp": f"{sum(float(t['count_fp']) for t in trades):.2f}",
            "volume_24h_fp": f"{sum(float(t['count_fp']) for t in trades):.2f}",
            "open_time": _ts(base_time),
            "close_time": _ts(base_time + timedelta(days=19)),
            "created_time": _ts(base_time - timedelta(days=5)),
        },
    ]

    return {
        "markets": markets,
        "trades": trades,
        "orderbooks": {},
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "demo_annotations": {
            "phase_A": "Normal baseline (80 trades, hours 0–4)",
            "phase_B": "INJECTED volume spike (25 trades, hour 4:30–4:35, all YES, large qty)",
            "phase_C": "INJECTED wash trading (18 trades, hour 6–6:30, repeated combos, alternating sides)",
            "phase_D": "INJECTED coordinated cluster (15 trades, hour 8:00–8:02, all YES)",
            "phase_E": "Normal tail (40 trades, hours 8–10)",
        },
    }


if __name__ == "__main__":
    data = generate_demo_data()
    print(f"Generated {len(data['trades'])} trades across {len(data['markets'])} market(s)")
    print(f"\nAnnotations:")
    for phase, desc in data["demo_annotations"].items():
        print(f"  {phase}: {desc}")
