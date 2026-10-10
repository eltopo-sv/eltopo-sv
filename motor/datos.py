# -*- coding: utf-8 -*-
"""ELTOPO - Sistema de datos con failover automatico.

Fuentes por orden de prioridad:
1. Alpaca (primaria - sin rate limit, funciona en datacenter)
2. yfinance (fallback - por si Alpaca falla)
3. Cache antigua
"""

import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

from .config import TIMEFRAMES, PERIODOS, CACHE_TTL, MIN_VELAS
from .cache import guardar_cache, leer_cache


# Sesion global con curl_cffi (impersona Chrome real)
_sesion_curl = None

# Cliente Alpaca (lazy)
_alpaca_client = None


def _get_alpaca():
    """Crea/obtiene el cliente de Alpaca."""
    global _alpaca_client
    if _alpaca_client is None:
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            api_key = os.environ.get("ALPACA_API_KEY", "").strip()
            secret_key = os.environ.get("ALPACA_SECRET_KEY", "").strip()

            if not api_key or not secret_key:
                print("[AVISO] Alpaca keys no configuradas")
                _alpaca_client = False
                return None

            _alpaca_client = StockHistoricalDataClient(
                api_key=api_key,
                secret_key=secret_key,
            )
            print("[OK] Cliente Alpaca creado")
        except Exception as e:
            print("[AVISO] Alpaca no disponible: " + str(e))
            _alpaca_client = False
    return _alpaca_client if _alpaca_client is not False else None


def _get_sesion():
    """Crea/obtiene una sesion de curl_cffi que impersona Chrome."""
    global _sesion_curl
    if _sesion_curl is None:
        try:
            from curl_cffi import requests as curl_requests
            _sesion_curl = curl_requests.Session(impersonate="chrome")
            print("[OK] Sesion curl_cffi creada (impersonate=chrome)")
        except Exception as e:
            print("[AVISO] curl_cffi no disponible: " + str(e))
            _sesion_curl = False
    return _sesion_curl if _sesion_curl is not False else None


def _df_a_registros(df):
    """Convierte DataFrame a lista de dicts serializable en JSON."""
    df_copy = df.copy()
    for col in df_copy.columns:
        if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
            df_copy[col] = df_copy[col].astype(str)
        elif pd.api.types.is_numeric_dtype(df_copy[col]):
            df_copy[col] = df_copy[col].astype(float)
    return df_copy.to_dict("records")


def _mapear_timeframe(motor):
    """Mapea el motor a TimeFrame de Alpaca."""
    from alpaca.data.timeframe import TimeFrame

    mapa = {
        "scalping": TimeFrame.Minute,
        "day": TimeFrame.Minute,
        "swing": TimeFrame.Day,
    }
    return mapa.get(motor, TimeFrame.Day)


def _fecha_inicio(motor):
    """Calcula la fecha de inicio segun el motor."""
    ahora = datetime.now()

    if motor == "scalping":
        return ahora - timedelta(days=10)
    elif motor == "day":
        return ahora - timedelta(days=90)
    else:  # swing
        return ahora - timedelta(days=730)


def obtener_datos(ticker, motor="swing"):
    """Obtiene datos OHLCV con failover.

    Orden:
    1. Cache valida (<TTL)
    2. Alpaca
    3. yfinance
    4. Cache antigua (<999999s)
    """
    ticker = ticker.upper()
    intervalo = TIMEFRAMES[motor]
    cache_key = "ohlcv_" + ticker + "_" + intervalo

    # 1. Cache valida
    cache = leer_cache(cache_key, ttl=CACHE_TTL[motor])
    if cache is not None:
        df = pd.DataFrame(cache)
        if len(df) >= MIN_VELAS[motor]:
            print("[OK] " + ticker + " [" + motor + "] desde cache (" + str(len(df)) + " velas)")
            return df

    # 2. Alpaca (primario)
    df = _obtener_alpaca(ticker, motor)
    if df is not None and len(df) >= MIN_VELAS[motor]:
        print("[OK] " + ticker + " [" + motor + "] desde ALPACA (" + str(len(df)) + " velas)")
        guardar_cache(cache_key, _df_a_registros(df))
        return df

    # 3. yfinance (fallback)
    periodo = PERIODOS[motor]
    df = _obtener_yfinance(ticker, periodo, intervalo)
    if df is not None and len(df) >= MIN_VELAS[motor]:
        print("[OK] " + ticker + " [" + motor + "] desde yfinance (" + str(len(df)) + " velas)")
        guardar_cache(cache_key, _df_a_registros(df))
        return df

    # 4. Cache antigua
    cache = leer_cache(cache_key, ttl=999999)
    if cache is not None:
        print("[AVISO] " + ticker + " [" + motor + "] desde cache ANTIGUA")
        return pd.DataFrame(cache)

    print("[ERROR] " + ticker + " [" + motor + "] sin datos")
    return None


def _obtener_alpaca(ticker, motor):
    """Obtiene datos OHLCV desde Alpaca."""
    try:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = _get_alpaca()
        if client is None:
            return None

        # Mapear timeframe
        if motor == "swing":
            timeframe = TimeFrame.Day
        elif motor == "day":
            # Alpaca no tiene 15min directo; usamos 15Min
            from alpaca.data.timeframe import TimeFrameUnit
            timeframe = TimeFrame(15, TimeFrameUnit.Minute)
        else:  # scalping
            from alpaca.data.timeframe import TimeFrameUnit
            timeframe = TimeFrame(5, TimeFrameUnit.Minute)

        inicio = _fecha_inicio(motor)

        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=timeframe,
            start=inicio,
            feed="iex",  # IEX feed (gratis)
        )

        bars = client.get_stock_bars(request)
        df = bars.df

        if df is None or df.empty:
            return None

        # Reset index para tener symbol y timestamp como columnas
        df = df.reset_index()

        # Renombrar columnas al formato yfinance
        df = df.rename(columns={
            "timestamp": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        })

        # Quedarnos con las columnas importantes
        cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        df = df[[c for c in cols if c in df.columns]]

        return df

    except Exception as e:
        print("  Alpaca fallo: " + str(e))
        return None


def _obtener_yfinance(ticker, periodo, intervalo):
    """Obtiene datos OHLCV desde yfinance (fallback)."""
    try:
        sesion = _get_sesion()
        if sesion is not None:
            df = yf.download(
                ticker,
                period=periodo,
                interval=intervalo,
                progress=False,
                auto_adjust=True,
                session=sesion,
            )
        else:
            df = yf.download(
                ticker,
                period=periodo,
                interval=intervalo,
                progress=False,
                auto_adjust=True,
            )
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        return df
    except Exception as e:
        print("  yfinance fallo: " + str(e))
        return None


# ─── FUNDAMENTALES (siguen con yfinance + Finnhub) ───

def _fundamental_desde_yfinance(ticker):
    """Intenta obtener fundamental desde yfinance con curl_cffi."""
    try:
        sesion = _get_sesion()
        if sesion is not None:
            t = yf.Ticker(ticker, session=sesion)
        else:
            t = yf.Ticker(ticker)

        info = t.info

        if not info or not info.get("longName"):
            return None

        def _safe(key):
            val = info.get(key)
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return val

        return {
            "nombre": info.get("longName"),
            "sector": info.get("sector"),
            "industria": info.get("industry"),
            "pais": info.get("country"),
            "empleados": info.get("fullTimeEmployees"),
            "ingresos_yoy": _safe("revenueGrowth"),
            "beneficios_yoy": _safe("earningsGrowth"),
            "crecimiento_beneficios_q": _safe("earningsQuarterlyGrowth"),
            "margen_bruto": _safe("grossMargins"),
            "margen_operativo": _safe("operatingMargins"),
            "margen_neto": _safe("profitMargins"),
            "per": _safe("trailingPE"),
            "per_forward": _safe("forwardPE"),
            "ps": _safe("priceToSalesTrailing12Months"),
            "pb": _safe("priceToBook"),
            "ev_ebitda": _safe("enterpriseToEbitda"),
            "deuda_equity": _safe("debtToEquity"),
            "current_ratio": _safe("currentRatio"),
            "quick_ratio": _safe("quickRatio"),
            "roe": _safe("returnOnEquity"),
            "roa": _safe("returnOnAssets"),
            "dividend_yield": _safe("dividendYield"),
            "payout_ratio": _safe("payoutRatio"),
            "market_cap": _safe("marketCap"),
            "enterprise_value": _safe("enterpriseValue"),
            "beta": _safe("beta"),
            "precio_objetivo": _safe("targetMeanPrice"),
            "recomendacion": info.get("recommendationKey"),
        }
    except Exception as e:
        print("  yfinance fundamental fallo: " + str(e))
        return None


def _fundamental_desde_finnhub(ticker):
    """Fallback: obtiene fundamental desde Finnhub."""
    try:
        from .sentimiento import obtener_fundamental_finnhub
        return obtener_fundamental_finnhub(ticker)
    except Exception as e:
        print("  finnhub fundamental fallo: " + str(e))
        return None


def obtener_fundamental(ticker):
    """Obtiene datos fundamentales con failover: yfinance -> Finnhub."""
    ticker = ticker.upper()
    cache_key = "fund_" + ticker

    cache = leer_cache(cache_key, ttl=86400)
    if cache and cache.get("nombre"):
        return cache

    data = _fundamental_desde_yfinance(ticker)

    if not data or not data.get("nombre"):
        print("[AVISO] yfinance fundamental vacio, probando Finnhub...")
        data = _fundamental_desde_finnhub(ticker)

    if not data:
        print("[ERROR] fundamental sin datos en todas las fuentes")
        data = {
            "nombre": None, "sector": None, "industria": None, "pais": None,
            "empleados": None, "ingresos_yoy": None, "beneficios_yoy": None,
            "crecimiento_beneficios_q": None, "margen_bruto": None,
            "margen_operativo": None, "margen_neto": None, "per": None,
            "per_forward": None, "ps": None, "pb": None, "ev_ebitda": None,
            "deuda_equity": None, "current_ratio": None, "quick_ratio": None,
            "roe": None, "roa": None, "dividend_yield": None,
            "payout_ratio": None, "market_cap": None, "enterprise_value": None,
            "beta": None, "precio_objetivo": None, "recomendacion": None,
        }

    guardar_cache(cache_key, data)
    print("[OK] " + ticker + " fundamental")
    return data
