"""ELTOPO - Indicadores complementarios (Volume Profile, Fuerza Relativa, Pivotes)."""

import pandas as pd
import numpy as np


def calcular_volume_profile(df, bins=50):
    """Calcula el POC (Point of Control) usando Volume Profile.
    
    El POC es el nivel de precio con mayor volumen acumulado.
    """
    if df is None or df.empty:
        return None, None

    # Precio tipico de cada vela
    tp = (df["High"] + df["Low"] + df["Close"]) / 3

    # Rango de precios
    precio_min = float(tp.min())
    precio_max = float(tp.max())

    if precio_max == precio_min:
        return precio_min, None

    # Crear bins
    bins_edges = np.linspace(precio_min, precio_max, bins + 1)
    bin_centers = (bins_edges[:-1] + bins_edges[1:]) / 2

    # Acumular volumen por bin
    volumen_por_bin = np.zeros(bins)
    for i, precio in enumerate(tp):
        idx = np.searchsorted(bins_edges, precio) - 1
        idx = max(0, min(idx, bins - 1))
        volumen_por_bin[idx] += float(df["Volume"].iloc[i])

    # POC = bin con mas volumen
    idx_poc = int(np.argmax(volumen_por_bin))
    poc = float(bin_centers[idx_poc])

    return poc, volumen_por_bin.tolist()


def calcular_fuerza_relativa(df_ticker, df_indice, ventana=30):
    """Calcula fuerza relativa vs un indice (S&P 500, por ejemplo).
    
    RS = Rendimiento_ticker - Rendimiento_indice (ultimos N dias).
    """
    if df_ticker is None or df_indice is None:
        return None

    try:
        if len(df_ticker) < ventana or len(df_indice) < ventana:
            return None

        ticker_actual = float(df_ticker["Close"].iloc[-1])
        ticker_ayer = float(df_ticker["Close"].iloc[-ventana])
        rend_ticker = (ticker_actual / ticker_ayer - 1) * 100

        indice_actual = float(df_indice["Close"].iloc[-1])
        indice_ayer = float(df_indice["Close"].iloc[-ventana])
        rend_indice = (indice_actual / indice_ayer - 1) * 100

        rs = rend_ticker - rend_indice
        return round(rs, 2)
    except Exception:
        return None


def calcular_pivotes(df):
    """Calcula pivotes diarios clasicos a partir de la ultima vela completa."""
    if df is None or len(df) < 2:
        return None

    try:
        # Usar penultima vela (ultima cerrada)
        high = float(df["High"].iloc[-2])
        low = float(df["Low"].iloc[-2])
        close = float(df["Close"].iloc[-2])

        pivot = (high + low + close) / 3
        r1 = (2 * pivot) - low
        s1 = (2 * pivot) - high
        r2 = pivot + (high - low)
        s2 = pivot - (high - low)

        return {
            "pivot": round(pivot, 2),
            "r1": round(r1, 2),
            "r2": round(r2, 2),
            "s1": round(s1, 2),
            "s2": round(s2, 2),
        }
    except Exception:
        return None


def calcular_fuerza_relativa_sector(df_ticker, df_sector, ventana=30):
    """Fuerza relativa vs su sector (similar a vs indice)."""
    return calcular_fuerza_relativa(df_ticker, df_sector, ventana)


def calcular_posicionamiento_institucional(ticker):
    """Placeholder para posicionamiento institucional.
    
    En el futuro consultara:
    - Insider trading (30d)
    - Flujos institucionales (13F)
    - Short interest
    """
    return {
        "insider": None,
        "flujos_institucionales": None,
        "short_interest": None,
        "nota": "Pendiente de implementar con API externa"
    }
