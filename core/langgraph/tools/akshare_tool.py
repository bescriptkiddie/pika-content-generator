"""AKShare wrapper — A-share (A股) financial data"""


def fetch_a_stock(
    symbol: str = "000001",
    period: str = "daily",
    days: int = 30,
) -> list[dict]:
    """Fetch A-share historical data via AKShare.

    Args:
        symbol: Stock code (e.g. "000001" for 平安银行)
        period: "daily", "weekly", or "monthly"
        days: Number of recent trading days to return
    """
    try:
        import akshare as ak

        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period=period,
            adjust="qfq",
        )

        if df.empty:
            return []

        records = df.tail(days).to_dict("records")

        return [
            {
                "date": str(r.get("日期", "")),
                "open": r.get("开盘", 0),
                "close": r.get("收盘", 0),
                "high": r.get("最高", 0),
                "low": r.get("最低", 0),
                "volume": r.get("成交量", 0),
                "amount": r.get("成交额", 0),
                "symbol": symbol,
            }
            for r in records
        ]

    except ImportError:
        return [{"error": "akshare not installed. Run: pip install akshare"}]
    except Exception as e:
        return [{"error": str(e), "symbol": symbol}]
