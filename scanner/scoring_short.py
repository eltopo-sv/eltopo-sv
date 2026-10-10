# -*- coding: utf-8 -*-
"""Scoring para SHORT con filtros de calidad."""


def calcular_score_short(ind):
    """Score 0-10 para SHORT con filtros anti-extendido."""
    scores = {}

    precio = ind.get("precio")
    mm200 = ind.get("mm200")
    mm50 = ind.get("mm50")
    rsi = ind.get("rsi")
    macd = ind.get("macd")
    macd_signal = ind.get("macd_signal")
    vol_rel = ind.get("vol_relativo")
    atr = ind.get("atr")
    precios = ind.get("precios_historicos")
    rs = ind.get("fuerza_relativa")

    # 1. Tendencia bajista (25%)
    if precio and mm200 and mm50:
        if precio < mm200 and precio < mm50:
            scores["tendencia"] = 10.0
        elif precio < mm200:
            scores["tendencia"] = 8.0
        elif precio < mm50:
            scores["tendencia"] = 6.0
        else:
            scores["tendencia"] = 2.0

        # Penalizar si está MUY extendido a la baja sobre MM50
        dist_mm50_pct = (precio / mm50 - 1) * 100
        if dist_mm50_pct < -20:
            scores["tendencia"] -= 4.0
        elif dist_mm50_pct < -15:
            scores["tendencia"] -= 3.0
        elif dist_mm50_pct < -10:
            scores["tendencia"] -= 1.5

        scores["tendencia"] = max(0.0, scores["tendencia"])
    else:
        scores["tendencia"] = 5.0

    # 2. Momentum bajista (20%)
    momentum = 5.0
    if rsi:
        if 30 <= rsi <= 45:
            momentum = 9.5
        elif 45 <= rsi < 50:
            momentum = 7.0
        elif rsi < 30:
            momentum = 5.0
        elif 50 <= rsi < 60:
            momentum = 4.0
        elif rsi >= 60:
            momentum = 2.0
        else:
            momentum = 5.0

    if macd and macd_signal and macd > macd_signal:
        momentum -= 1.5

    scores["momentum"] = max(0.0, momentum)

    # 3. Volumen (15%)
    if vol_rel:
        if vol_rel > 2.5:
            scores["volumen"] = 10.0
        elif vol_rel > 2.0:
            scores["volumen"] = 9.0
        elif vol_rel > 1.5:
            scores["volumen"] = 8.0
        elif vol_rel > 1.2:
            scores["volumen"] = 7.0
        elif vol_rel > 0.8:
            scores["volumen"] = 5.5
        else:
            scores["volumen"] = 3.0
    else:
        scores["volumen"] = 5.0

    # 4. Estructura bajista (15%)
    if precios and len(precios) >= 20:
        primer = sum(precios[:7]) / 7
        ultimo = sum(precios[-7:]) / 7
        if ultimo < primer * 0.95:
            scores["estructura"] = 10.0
        elif ultimo < primer * 0.98:
            scores["estructura"] = 8.0
        elif ultimo < primer:
            scores["estructura"] = 6.0
        else:
            scores["estructura"] = 3.0
    else:
        scores["estructura"] = 5.0

    # 5. Fuerza relativa negativa (10%)
    if rs:
        if rs < -10:
            scores["fuerza_relativa"] = 10.0
        elif rs < -5:
            scores["fuerza_relativa"] = 8.5
        elif rs < -2:
            scores["fuerza_relativa"] = 7.0
        elif rs < 2:
            scores["fuerza_relativa"] = 5.0
        elif rs < 5:
            scores["fuerza_relativa"] = 3.0
        else:
            scores["fuerza_relativa"] = 1.0
    else:
        scores["fuerza_relativa"] = 5.0

    # 6. ATR (5%)
    if atr and precio:
        atr_pct = (atr / precio) * 100
        if 1.5 <= atr_pct <= 3.0:
            scores["volatilidad"] = 9.0
        elif 1.0 <= atr_pct < 1.5:
            scores["volatilidad"] = 7.5
        elif atr_pct > 4.5:
            scores["volatilidad"] = 3.0
        else:
            scores["volatilidad"] = 5.0
    else:
        scores["volatilidad"] = 5.0

    scores["catalizadores"] = 5.0
    scores["fundamental"] = 5.0

    pesos = {
        "tendencia": 0.25,
        "momentum": 0.20,
        "volumen": 0.15,
        "estructura": 0.15,
        "fuerza_relativa": 0.10,
        "volatilidad": 0.05,
        "catalizadores": 0.05,
        "fundamental": 0.05,
    }

    score = sum(scores[k] * pesos[k] for k in pesos)
    return {"score": round(score, 2), "desglose": scores}
