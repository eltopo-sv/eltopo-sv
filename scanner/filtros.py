# -*- coding: utf-8 -*-
"""Filtros previos del scanner."""

from .config import MIN_PRECIO, MIN_VOLUMEN_MEDIO, MIN_VELAS

# ─── ETFs apalancados y fondos a excluir ───
ETFS_EXCLUIR = {
    # Apalancados NASDAQ
    "FNGU", "FNGD", "TQQQ", "SQQQ", "TNA", "TZA", "LABU", "LABD",
    "SOXL", "SOXS", "SPXU", "SPXL", "UPRO", "SPXS", "TECL", "TECS",
    # Apalancados S&P
    "SSO", "SDS", "QLD", "QID", "UDOW", "SDOW",
    # Apalancados sectoriales
    "FAS", "FAZ", "ERX", "ERY", "NUGT", "DUST", "JNUG", "JDST",
    "YINN", "YANG", "CURE", "DRN", "DRV",
    # Inversos bonos
    "TMV", "TMF", "TBT", "TBF", "TMF", "TYO", "TYD", "TBX",
    # Inversos Russell
    "RWM", "UWM", "TWM", "URTY", "SRTY",
    # Inversos crudo / gas
    "SCO", "UCO", "DTO", "GUSH", "DRIP", "BOIL", "KOLD", "OILU", "OILD",
    # Inversos metales
    "AGQ", "UGL", "GLL", "JDST", "JNUG", "DUST", "NUGT",
    # Inversos volatilidad
    "VXX", "UVXY", "SVXY", "VIXY", "VIXM", "VXZ",
    # Índices base (no operables como acción)
    "SPY", "QQQ", "DIA", "IWM", "GLD", "SLV", "USO", "UNG",
    "TLT", "HYG", "LQD", "AGG", "BND",
    # Cripto ETFs
    "BITO", "GBTC", "ETHE",
    # Otros apalancados comunes
    "BULZ", "WEBL", "WEBS", "DFEN", "FNGU", "FNGO", "FNGD", "FNGS",
    "SPYU", "SPYB", "TQQQ", "SQQQ", "SOXL", "SOXS", "LABU", "LABD",
}

# ─── Mega caps excluidas de SHORT ───
MEGA_CAPS = {
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "NVDA",
    "BRK-B", "JPM", "V", "MA", "UNH", "JNJ", "WMT", "PG", "HD",
    "BAC", "XOM", "PEP", "KO", "SBUX", "COST", "CVX", "ABBV",
    "MRK", "LLY", "AVGO", "ADBE", "CRM", "NFLX", "ORCL", "AMD",
    "TMO", "ACN", "MCD", "NKE", "DIS", "CSCO", "WFC", "INTC",
    "INTU", "QCOM", "TXN", "IBM", "GE", "CAT", "BA", "MMM",
}


def es_operable(df, ticker):
    """Devuelve True si el ticker es operable."""
    t = ticker.upper()

    # ─── Excluir ETFs conocidos ───
    if t in ETFS_EXCLUIR:
        return False

    # ─── Excluir preferentes y derivados con $ o . ───
    if "$" in ticker or "." in ticker:
        return False

    # ─── Excluir tickers de prueba (ZTEST, ZZZTX, etc.) ───
    if ticker.endswith("TEST") or ticker.endswith("ZZT"):
        return False
    if ticker in {"ZVZZT", "ZWZZT", "ZXZZT", "ZJZZT", "ZIEXT", 
                  "ZBZX", "ZCZZT", "ZBZZT", "ZEXIT", "ZXIET",
                  "ZZZTX", "ZZZTA", "ZZZ", "ZZZZ"}:
        return False

    if df is None or len(df) < MIN_VELAS:
        return False

    try:
        ultimo = df.iloc[-1]
        precio = float(ultimo["Close"])

        # Precio minimo
        if precio < MIN_PRECIO:
            return False

        # Volumen: NO filtrar aqui
        # El universo ya se filtro con volumen real (yfinance).
        # Alpaca solo da volumen IEX (subestimado ~30x), por lo que
        # filtrar aqui descartaria tickers validos como JPM, TSM, MUFG.
        # Umbral muy bajo solo para descartar tickers muertos.
        volumen_medio = float(df["Volume"].tail(20).mean())
        if volumen_medio < 30_000:
            return False

        return True
    except Exception:
        return False


def es_short_operable(ticker):
    """Devuelve True si el ticker es shorteable (no mega cap)."""
    return ticker.upper() not in MEGA_CAPS