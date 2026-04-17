"""CCXT wrapper — 100+ crypto exchange unified API"""


def fetch_crypto(
    pair: str = "BTC/USDT",
    exchange_id: str = "binance",
    timeframe: str = "1h",
    limit: int = 100,
) -> list[dict]:
    """Fetch OHLCV data from a crypto exchange via CCXT.

    Args:
        pair: Trading pair (e.g. "BTC/USDT", "ETH/USDT")
        exchange_id: Exchange name (e.g. "binance", "okx", "bybit")
        timeframe: Candle timeframe (e.g. "1m", "5m", "1h", "1d")
        limit: Number of candles to fetch
    """
    try:
        import ccxt

        exchange_class = getattr(ccxt, exchange_id, None)
        if not exchange_class:
            return [{"error": f"Unknown exchange: {exchange_id}"}]

        exchange = exchange_class()
        ohlcv = exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)

        return [
            {
                "timestamp": r[0],
                "open": r[1],
                "high": r[2],
                "low": r[3],
                "close": r[4],
                "volume": r[5],
                "pair": pair,
                "exchange": exchange_id,
            }
            for r in ohlcv
        ]

    except ImportError:
        return [{"error": "ccxt not installed. Run: pip install ccxt"}]
    except Exception as e:
        return [{"error": str(e), "pair": pair, "exchange": exchange_id}]
