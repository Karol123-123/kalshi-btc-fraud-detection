"""
Configuration for the BTC fraud detection pipeline.
Thresholds match the values described in docs/write_up.pdf.
"""

# Kalshi public market-data API (no key needed for these endpoints)
KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
BTC_SERIES_TICKER = "KXBTC"

# Volume spike detector: flag 5-minute windows with z-score >= this (HIGH if > 3.0)
VOLUME_ZSCORE_THRESHOLD = 2.0

# Price swing detector: flag consecutive-trade YES price changes >= this fraction (HIGH if > 0.30)
PRICE_CHANGE_THRESHOLD = 0.15

# Trade clustering detector: sliding window length and minimum trades per cluster
TRADE_CLUSTER_WINDOW_SEC = 300
TRADE_CLUSTER_MIN_COUNT = 5
