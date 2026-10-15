# Kalshi BTC Prediction Market Fraud Detection

A Python pipeline that pulls Bitcoin prediction-market trades from Kalshi's public API and runs four statistical detectors to flag possible market manipulation: volume spikes, price swings, wash trading, and coordinated trade clusters. Flags are condensed into a short evidence brief designed to be handed to an LLM for a second-pass review.

Built solo, Feb–Apr 2026. Full write-up: [`docs/write_up.pdf`](docs/write_up.pdf).

## Results

**Synthetic validation (178 trades, 3 injected fraud patterns)**
- Caught all 3 injected patterns (100% detection rate)
- 20.6% false positive rate on the organic baseline trades
- Injected volume spike: z-score 7.86 (~28x average window volume)
- Injected wash trading: $0.70 x 10 contracts repeated 12 times in 90 seconds
- Injected cluster: 15 trades in 86 seconds, 100% YES

**Live Kalshi data (5,560 trades across 5 BTC markets, Jan 12 – Feb 27, 2026)**
- 1,231 total flags (614 HIGH, 617 MEDIUM)
- On **Feb 6, 2026**, all four detectors fired together:
  - Volume spike with a z-score of 13.92 (~4,000 contracts in one 5-minute window vs. a typical 30–70)
  - A 900% price swing ($0.01 to $0.10)
  - One price/quantity combo repeated 37 times in 4 minutes
  - A cluster of 162 trades in under 5 minutes

The price swing detector is the noisiest. Contracts trading near $0.01 produce huge percentage changes from tiny moves, so many of those flags are artifacts. Agreement across detectors is the stronger signal.

## How it works

```
Kalshi API  ->  4 detectors  ->  evidence brief (top 5 flags per category)  ->  LLM review
```

| Detector | What it looks for | MEDIUM | HIGH |
|---|---|---|---|
| Volume spike | Contract volume per 5-min window, z-scored against all windows | z >= 2.0 | z > 3.0 |
| Price swing | % change in YES price between consecutive trades | >= 15% | > 30% |
| Wash trading | Same price + quantity 3+ times within 10 min; 5+ trades in a row alternating YES/NO | alternation | repeated combo |
| Trade clustering | 5+ trades inside a 300-second sliding window, with YES/NO directional bias | 5–9 trades | 10+ trades |

Composite risk score = 25 x HIGH flags + 10 x MEDIUM flags, capped at 100.

The detectors are deterministic, so there's no training step and no labeled data needed. That matters here because labeled fraud data for prediction markets basically doesn't exist.

## Run it

```bash
pip install -r requirements.txt

python main.py --demo   # synthetic data with injected fraud, runs offline
python main.py          # live Kalshi data (falls back to demo data if the API call fails)
```

No API key is needed; the pipeline only uses Kalshi's public market-data endpoints.

## Files

| File | Purpose |
|---|---|
| `main.py` | Runs the pipeline end to end |
| `kalshi_client.py` | Kalshi REST client: markets, trades, order books, candlesticks |
| `anomaly_detector.py` | The four detectors and the risk score |
| `evidence_brief.py` | Condenses flags into a short text brief for an LLM |
| `demo_data.py` | Seeded synthetic dataset with three injected fraud patterns |
| `config.py` | API settings and detector thresholds |

## Next steps

- Wire the evidence brief directly into a local LLM (Ollama) in the pipeline. In the write-up the brief was run through Ollama separately, and the model rated the overall risk as high.
- Scale the price swing threshold by price level to cut false positives near $0.01.
- Pull outside event data (news, BTC spot price) to tell real news-driven moves apart from manipulation.
