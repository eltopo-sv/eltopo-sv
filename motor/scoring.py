"""ELTOPO - Motor de scoring (puntuacion 0-10 por indicador)."""

import pandas as pd
import numpy as np


# ===================================================
# FUNCIONES DE PUNTUACION POR INDICADOR (0-10)
# ===================================================

def puntuar_precio_vs_mm(precio, mm):
    """Puntua el precio respecto a una media movil."""
    if precio is None or mm is None or mm == 0:
        return 5.0
    diff_pct = (precio / mm - 1) * 100
    if diff_pct > 5:
        return 10.0
    elif diff_pct > 2:
        return 9.0
    elif diff_pct > 0:
        return 7.0
    elif diff_pct > -2:
        return 5.0
    elif diff_pct > -5:
        return 3.0
    else:
        return 1.0


def puntuar_rsi(rsi):
    """Puntua el RSI (0-10)."""
    if rsi is None:
        return 5.0
    if 55 <= rsi <= 70:
        return 9.5
    elif 50 <= rsi < 55:
        return 7.5
    elif 45 <= rsi < 50:
        return 5.5
    elif 40 <= rsi < 45:
        return 4.0
    elif 30 <= rsi < 40:
        return 3.0
    elif rsi < 30:
        return 5.0
    elif 70 < rsi <= 75:
        return 6.0
    elif 75 < rsi <= 80:
        return 4.0
    else:
        return 2.0


def puntuar_macd(macd, signal, hist):
    """Puntua el MACD (0-10)."""
    if macd is None or signal is None or hist is None:
        return 5.0
    if macd > signal and hist > 0:
        return 9.0 if hist > 0.5 else 7.5
    elif macd > signal:
        return 6.0
    elif macd < signal and hist < 0:
        return 3.0 if hist > -0.5 else 2.0
    else:
        return 4.5


def puntuar_atr(atr, precio):
    """Puntua el ATR segun porcentaje sobre precio."""
    if atr is None or precio is None or precio == 0:
        return 5.0
    atr_pct = (atr / precio) * 100
    if 1.0 <= atr_pct <= 2.5:
        return 9.0
    elif 0.5 <= atr_pct < 1.0:
        return 7.0
    elif 2.5 < atr_pct <= 4.0:
        return 6.0
    elif atr_pct > 4.0:
        return 3.0
    else:
        return 5.0


def puntuar_adx(adx):
    """Puntua el ADX (0-10)."""
    if adx is None:
        return 5.0
    if adx > 30:
        return 9.5
    elif adx > 25:
        return 8.0
    elif adx > 20:
        return 6.0
    elif adx > 15:
        return 4.5
    else:
        return 3.0


def puntuar_estocastico(stoch_k, stoch_d):
    """Puntua el estocastico (0-10)."""
    if stoch_k is None or stoch_d is None:
        return 5.0
    if stoch_k < 20 and stoch_k > stoch_d:
        return 9.0
    elif stoch_k < 30 and stoch_k > stoch_d:
        return 7.5
    elif 30 <= stoch_k <= 70:
        return 5.5
    elif stoch_k > 80 and stoch_k < stoch_d:
        return 2.0
    elif stoch_k > 70:
        return 4.0
    else:
        return 5.0


def puntuar_bollinger(precio, bb_lower, bb_mid, bb_upper):
    """Puntua la posicion dentro de las Bollinger."""
    if precio is None or bb_lower is None or bb_upper is None:
        return 5.0
    rango = bb_upper - bb_lower
    if rango == 0:
        return 5.0
    pos = (precio - bb_lower) / rango
    if pos < 0.1:
        return 9.0
    elif pos < 0.3:
        return 7.5
    elif pos < 0.7:
        return 5.5
    elif pos < 0.9:
        return 4.0
    else:
        return 2.5


def puntuar_vwap(precio, vwap):
    """Puntua el VWAP."""
    if precio is None or vwap is None or vwap == 0:
        return 5.0
    diff_pct = (precio / vwap - 1) * 100
    if diff_pct > 1.0:
        return 9.0
    elif diff_pct > 0.2:
        return 7.5
    elif diff_pct > -0.2:
        return 5.5
    elif diff_pct > -1.0:
        return 4.0
    else:
        return 2.5


def puntuar_volumen(vol_rel):
    """Puntua el volumen relativo."""
    if vol_rel is None:
        return 5.0
    if vol_rel > 2.5:
        return 10.0
    elif vol_rel > 2.0:
        return 9.0
    elif vol_rel > 1.5:
        return 8.0
    elif vol_rel > 1.2:
        return 7.0
    elif vol_rel > 0.8:
        return 5.5
    elif vol_rel > 0.5:
        return 3.5
    else:
        return 2.0


def puntuar_fuerza_relativa(rs):
    """Puntua la fuerza relativa vs indice."""
    if rs is None:
        return 5.0
    if rs > 10:
        return 10.0
    elif rs > 5:
        return 8.5
    elif rs > 2:
        return 7.0
    elif rs > -2:
        return 5.0
    elif rs > -5:
        return 3.5
    else:
        return 1.5


def puntuar_pivotes(precio, pivotes):
    """Puntua la posicion respecto a pivotes diarios."""
    if precio is None or pivotes is None:
        return 5.0
    r1 = pivotes.get("r1")
    pivot = pivotes.get("pivot")
    s1 = pivotes.get("s1")
    if r1 is None or pivot is None or s1 is None:
        return 5.0
    if precio > r1:
        return 9.5
    elif precio > pivot:
        return 7.5
    elif precio > s1:
        return 5.0
    else:
        return 3.0


def puntuar_tendencia_estructura(precios):
    """Puntua la estructura de maximos/minimos."""
    if precios is None or len(precios) < 20:
        return 5.0
    recientes = precios[-20:]
    primer_tercio = sum(recientes[:7]) / 7
    ultimo_tercio = sum(recientes[-7:]) / 7
    if ultimo_tercio > primer_tercio * 1.03:
        return 9.0
    elif ultimo_tercio > primer_tercio:
        return 7.0
    elif ultimo_tercio > primer_tercio * 0.97:
        return 5.0
    else:
        return 3.0


def puntuar_poc(precio, poc):
    """Puntua posicion respecto al POC."""
    if precio is None or poc is None or poc == 0:
        return 5.0
    diff_pct = (precio / poc - 1) * 100
    if diff_pct > 2:
        return 9.0
    elif diff_pct > 0:
        return 7.0
    elif diff_pct > -2:
        return 5.0
    else:
        return 3.0


# ===================================================
# PESOS POR ESTILO
# ===================================================

PESOS_SWING = {
    "tendencia": 0.115,
    "volumen": 0.109,
    "precio_mm200": 0.104,
    "poc": 0.098,
    "rsi": 0.092,
    "precio_mm50": 0.086,
    "adx": 0.080,
    "fuerza_relativa": 0.075,
    "macd": 0.069,
    "patrones": 0.042,
    "fr_sector": 0.030,
    "institucional": 0.030,
    "atr": 0.030,
    "estocastico": 0.020,
    "bollinger": 0.020,
    "vwap": 0.010,
    "pivotes": 0.010,
}

PESOS_DAY = {
    "precio_mm50": 0.130,
    "tendencia": 0.130,
    "volumen": 0.120,
    "rsi": 0.100,
    "vwap": 0.100,
    "fuerza_relativa": 0.070,
    "macd": 0.060,
    "pivotes": 0.060,
    "patrones": 0.060,
    "volumen_premarket": 0.050,
    "atr": 0.030,
    "adx": 0.030,
    "estocastico": 0.030,
    "bollinger": 0.030,
}

PESOS_SCALPING = {
    "tendencia": 0.130,
    "volumen": 0.120,
    "vwap": 0.110,
    "rsi": 0.100,
    "estocastico": 0.100,
    "bollinger": 0.080,
    "patrones": 0.060,
    "fuerza_relativa": 0.050,
    "macd": 0.040,
    "atr": 0.040,
    "pivotes": 0.040,
    "adx": 0.030,
}


# ===================================================
# MOTOR DE SCORING
# ===================================================

def calcular_score(resultados, motor="swing"):
    """Calcula el score final segun los indicadores y el estilo."""
    if motor == "swing":
        pesos = PESOS_SWING
    elif motor == "day":
        pesos = PESOS_DAY
    elif motor == "scalping":
        pesos = PESOS_SCALPING
    else:
        raise ValueError("Motor desconocido: " + motor)

    scores = {
        "precio_mm200": puntuar_precio_vs_mm(resultados.get("precio"), resultados.get("mm200")),
        "precio_mm50": puntuar_precio_vs_mm(resultados.get("precio"), resultados.get("mm50")),
        "rsi": puntuar_rsi(resultados.get("rsi")),
        "macd": puntuar_macd(resultados.get("macd"), resultados.get("macd_signal"), resultados.get("macd_hist")),
        "atr": puntuar_atr(resultados.get("atr"), resultados.get("precio")),
        "adx": puntuar_adx(resultados.get("adx")),
        "estocastico": puntuar_estocastico(resultados.get("stoch_k"), resultados.get("stoch_d")),
        "bollinger": puntuar_bollinger(resultados.get("precio"), resultados.get("bb_lower"), resultados.get("bb_mid"), resultados.get("bb_upper")),
        "vwap": puntuar_vwap(resultados.get("precio"), resultados.get("vwap")),
        "volumen": puntuar_volumen(resultados.get("vol_relativo")),
        "fuerza_relativa": puntuar_fuerza_relativa(resultados.get("fuerza_relativa")),
        "pivotes": puntuar_pivotes(resultados.get("precio"), resultados.get("pivotes")),
        "poc": puntuar_poc(resultados.get("precio"), resultados.get("poc")),
        "tendencia": puntuar_tendencia_estructura(resultados.get("precios_historicos")),
        "patrones": 5.0,
        "fr_sector": 5.0,
        "institucional": 5.0,
        "volumen_premarket": 5.0,
    }

    score_final = 0.0
    peso_total = 0.0
    for clave, peso in pesos.items():
        if clave in scores:
            score_final += scores[clave] * peso
            peso_total += peso

    if peso_total > 0:
        score_final = score_final / peso_total

    return {
        "score_final": round(score_final, 2),
        "scores_individuales": scores,
        "pesos_aplicados": pesos,
        "motor": motor,
    }


def etiquetar_score(score):
    """Devuelve etiqueta y color segun el score final."""
    if score >= 9.0:
        return "TENDENCIA MUY ALCISTA", "verde_fuerte"
    elif score >= 8.0:
        return "TENDENCIA ALCISTA", "verde"
    elif score >= 6.5:
        return "RANGO ALCISTA", "amarillo"
    elif score >= 5.0:
        return "RANGO", "gris"
    elif score >= 3.0:
        return "TENDENCIA BAJISTA", "naranja"
    else:
        return "TENDENCIA MUY BAJISTA", "rojo"
