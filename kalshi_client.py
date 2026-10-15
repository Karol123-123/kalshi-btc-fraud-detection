"""
Kalshi API Client fetches BTC prediction market data.
Targets public endpoints.
"""
import requests
import time
from datetime import datetime, timezone
from typing import Optional
import config


class KalshiClient:
   

    def __init__(self):
        self.base_url = config.KALSHI_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    # Market discovery

    def get_btc_markets(self, status: str = "open", limit: int = 200) -> list[dict]:
        """Fetch all BTC related markets from the KXBTC series."""
        url = f"{self.base_url}/markets"
        params = {
            "series_ticker": config.BTC_SERIES_TICKER,
            "limit": limit,
        }
        if status:
            params["status"] = status

        all_markets = []
        cursor = None

        while True:
            if cursor:
                params["cursor"] = cursor
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            markets = data.get("markets", [])
            all_markets.extend(markets)
            cursor = data.get("cursor", "")
            if not cursor or not markets:
                break
            time.sleep(0.25)  

        return all_markets

    def get_market(self, ticker: str) -> dict:
        """Fetch a single market by ticker."""
        url = f"{self.base_url}/markets/{ticker}"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json().get("market", {})

    # Trade data 

    def get_trades(
        self,
        ticker: Optional[str] = None,
        limit: int = 1000,
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        max_pages: int = 10,
    ) -> list[dict]:
        """
        Fetch trades
        """
        url = f"{self.base_url}/markets/trades"
        params = {"limit": min(limit, 1000)}
        if ticker:
            params["ticker"] = ticker
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts

        all_trades = []
        cursor = None

        for _ in range(max_pages):
            if cursor:
                params["cursor"] = cursor
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            trades = data.get("trades", [])
            all_trades.extend(trades)
            cursor = data.get("cursor", "")
            if not cursor or not trades:
                break
            time.sleep(0.25)

        return all_trades

    # Order book snapshot

    def get_orderbook(self, ticker: str) -> dict:
        """Fetch current order book for a market."""
        url = f"{self.base_url}/markets/{ticker}/orderbook"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    # Candlestick / historical price data 

    def get_candlesticks(
        self,
        series_ticker: str,
        market_ticker: str,
        period: str = "1h",
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> list[dict]:
        """Fetch candlestick data for a market."""
        url = f"{self.base_url}/series/{series_ticker}/markets/{market_ticker}/candlesticks"
        params = {"period_interval": period}
        if start_ts:
            params["start_ts"] = start_ts
        if end_ts:
            params["end_ts"] = end_ts
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json().get("candlesticks", [])


# Convenience

def fetch_btc_snapshot() -> dict:
    """
    One call convenience: returns a dict with current BTC markets,
    recent trades, and order books.
    """
    client = KalshiClient()

    # Discover BTC markets open + recently settled for context
    markets = client.get_btc_markets(status="")
    btc_markets = [m for m in markets if "btc" in m.get("ticker", "").lower()
                   or "bitcoin" in m.get("yes_sub_title", "").lower()
                   or "bitcoin" in m.get("no_sub_title", "").lower()]

    if not btc_markets:
        btc_markets = markets  

    # Pull trades for the top markets by volume
    sorted_markets = sorted(
        btc_markets,
        key=lambda m: float(m.get("volume_fp", "0")),
        reverse=True,
    )
    top_markets = sorted_markets[:5]

    all_trades = []
    orderbooks = {}
    for m in top_markets:
        ticker = m["ticker"]
        trades = client.get_trades(ticker=ticker, limit=1000, max_pages=5)
        all_trades.extend(trades)
        try:
            ob = client.get_orderbook(ticker)
            orderbooks[ticker] = ob
        except Exception:
            pass
        time.sleep(0.25)

    return {
        "markets": top_markets,
        "trades": all_trades,
        "orderbooks": orderbooks,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
