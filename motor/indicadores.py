"""ELTOPO - Motor de indicadores tecnicos (usa libreria ta)."""

import pandas as pd
import numpy as np
import ta


def agregar_indicadores(df, motor="swing"):
    """Anade todos los indicadores tecnicos al DataFrame.
    
    Args:
        df: DataFrame con OHLCV
        motor: "scalping" | "day" | "swing"
    """
    if df is None or df.empty:
        return df

    for col in ["Close", "High", "Low", "Volume"]:
        if col not in df.columns:
            raise ValueError("Falta columna: " + col)

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # ── Medias moviles ──
    df["MM200"] = close.rolling(window=200).mean()
    df["MM50"] = close.rolling(window=50).mean()

    # ── RSI ──
    df["RSI"] = ta.momentum.RSIIndicator(close=close, window=14).rsi()

    # ── MACD ──
    macd = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    df["MACD"] = macd.macd()
    df["MACD_signal"] = macd.macd_signal()
    df["MACD_hist"] = macd.macd_diff()

    # ── ATR ──
    df["ATR"] = ta.volatility.AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()

    # ── ADX ──
    df["ADX"] = ta.trend.ADXIndicator(high=high, low=low, close=close, window=14).adx()

    # ── Estocastico ──
    stoch = ta.momentum.StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)
    df["Stoch_K"] = stoch.stoch()
    df["Stoch_D"] = stoch.stoch_signal()

    # ── Bollinger ──
    bb = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
    df["BB_lower"] = bb.bollinger_lband()
    df["BB_mid"] = bb.bollinger_mavg()
    df["BB_upper"] = bb.bollinger_hband()

    # ── VWAP (por estilo) ──
    df["VWAP"] = _calcular_vwap(df, motor)

    # ── Volumen relativo ──
    df["Vol_relativo"] = volume / volume.rolling(window=20).mean()

    return df


def _calcular_vwap(df, motor="swing"):
    """VWAP adaptado al estilo.
    
    - scalping / day: VWAP por sesion (intradia).
    - swing: VWAP movil de 20 velas (referencia ponderada).
    """
    tp = (df["High"] + df["Low"] + df["Close"]) / 3

    if motor in ("scalping", "day"):
        # VWAP por sesion diaria
        # Requiere que el indice sea datetime
        try:
            if "Datetime" in df.columns:
                fechas = pd.to_datetime(df["Datetime"])
            else:
                fechas = pd.to_datetime(df.index)

            # Agrupar por dia
            dia = fechas.date
            tp_vol = tp * df["Volume"]
            vwap = tp_vol.groupby(dia).cumsum() / df["Volume"].groupby(dia).cumsum()
            return vwap
        except Exception:
            # Si falla, usar VWAP movil de 20 velas como fallback
            pass

    # VWAP movil de 20 velas (swing o fallback)
    tp_vol = tp * df["Volume"]
    vwap = tp_vol.rolling(window=20).sum() / df["Volume"].rolling(window=20).sum()
    return vwap


def ultimo_valor(df, columna):
    """Devuelve el ultimo valor no-NaN de una columna."""
    if df is None or columna not in df.columns:
        return None
    serie = df[columna].dropna()
    if serie.empty:
        return None
    return float(serie.iloc[-1])


def resumen_indicadores(df):
    """Devuelve un dict con los valores actuales de cada indicador."""
    return {
        "precio": ultimo_valor(df, "Close"),
        "mm200": ultimo_valor(df, "MM200"),
        "mm50": ultimo_valor(df, "MM50"),
        "rsi": ultimo_valor(df, "RSI"),
        "macd": ultimo_valor(df, "MACD"),
        "macd_signal": ultimo_valor(df, "MACD_signal"),
        "macd_hist": ultimo_valor(df, "MACD_hist"),
        "atr": ultimo_valor(df, "ATR"),
        "adx": ultimo_valor(df, "ADX"),
        "stoch_k": ultimo_valor(df, "Stoch_K"),
        "stoch_d": ultimo_valor(df, "Stoch_D"),
        "bb_lower": ultimo_valor(df, "BB_lower"),
        "bb_mid": ultimo_valor(df, "BB_mid"),
        "bb_upper": ultimo_valor(df, "BB_upper"),
        "vwap": ultimo_valor(df, "VWAP"),
        "vol_relativo": ultimo_valor(df, "Vol_relativo"),
    }
