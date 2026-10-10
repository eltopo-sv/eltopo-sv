# -*- coding: utf-8 -*-
"""Scoring para REVERSION: rebote en soporte + cambio de tendencia.

Version 3 - Correcciones tras analisis externo (Kimi IA):
- Detector de pendientes corregido (MM50_hoy vs MM50_hace_10d)
- Calculo de objetivo con proyeccion ATR
- Penalizacion a caidas recientes fuertes
- Penalizacion a gran distancia del maximo anual
"""


def _calcular_media_movil(precios, ventana):
    """Calcula la media movil simple de los ultimos 'ventana' precios."""
    if not precios or len(precios) < ventana:
        return None
    return sum(precios[-ventana:]) / ventana


def _calcular_pendiente_media(precios, ventana_media, dias_atras):
    """Pendiente de media movil: MM_hoy vs MM_hace_dias_atras."""
    if not precios or len(precios) < ventana_media + dias_atras:
        return None
    media_hoy = sum(precios[-ventana_media:]) / ventana_media
    media_antes = sum(precios[-ventana_media - dias_atras:-dias_atras]) / ventana_media
    if media_antes <= 0:
        return None
    return (media_hoy / media_antes - 1) * 100


def _detectar_pivotes_altos(precios, ventana=5):
    pivotes = []
    n = len(precios)
    for i in range(ventana, n - ventana):
        es_pivote = True
        for j in range(1, ventana + 1):
            if precios[i] <= precios[i - j] or precios[i] <= precios[i + j]:
                es_pivote = False
                break
        if es_pivote:
            pivotes.append((i, precios[i]))
    return pivotes


def _filtrar_pivotes_significativos(pivotes, retroceso_min_pct=3.0):
    if len(pivotes) < 2:
        return pivotes
    filtrados = [pivotes[0]]
    for i in range(1, len(pivotes)):
        idx_actual, val_actual = pivotes[i]
        idx_prev, val_prev = filtrados[-1]
        if val_prev > 0:
            retroceso = (val_prev - val_actual) / val_prev * 100
            if retroceso >= retroceso_min_pct or val_actual > val_prev:
                filtrados.append((idx_actual, val_actual))
    return filtrados


def _detectar_ruptura_estructura(precios):
    if not precios or len(precios) < 20:
        return False, "Datos insuficientes"
    pivotes = _detectar_pivotes_altos(precios, ventana=5)
    if len(pivotes) < 2:
        return False, "Sin pivotes suficientes"
    pivotes_signif = _filtrar_pivotes_significativos(pivotes, retroceso_min_pct=3.0)
    if len(pivotes_signif) < 2:
        return False, "Sin pivotes significativos"
    ultimos = pivotes_signif[-3:]
    valores = [v for _, v in ultimos]
    es_decreciente = all(valores[i] > valores[i + 1] for i in range(len(valores) - 1))
    precio_actual = precios[-1]
    ultimo_pivote = valores[-1]
    if es_decreciente:
        if precio_actual > ultimo_pivote:
            return True, f"Ruptura de maximo decreciente ({ultimo_pivote:.2f})"
        else:
            return False, f"Estructura bajista sin romper ({ultimo_pivote:.2f})"
    else:
        if precio_actual > ultimo_pivote:
            return True, f"Superando ultimo pivote ({ultimo_pivote:.2f})"
        return False, "Estructura lateral/sin confirmar"


def _calcular_stop_objetivo(precio, precios, mm50, atr):
    """CORREGIDO v3: si max de 60 dias esta muy cerca, usa proyeccion ATR."""
    if not precios or len(precios) < 20 or not precio:
        return None, None, None
    ultimos_10 = precios[-10:]
    stop = min(ultimos_10) * 0.99
    if mm50 and stop < mm50 < precio:
        stop = max(stop, mm50 * 0.98)
    max_60 = max(precios[-60:]) if len(precios) >= 60 else max(precios)
    if max_60 <= precio * 1.02 and atr:
        objetivo = precio + 3 * atr
    else:
        objetivo = max_60
    if precio > stop and objetivo:
        riesgo = precio - stop
        beneficio = objetivo - precio
        rb = beneficio / riesgo if riesgo > 0 else None
    else:
        rb = None
    return round(stop, 2), round(objetivo, 2), round(rb, 2) if rb else None


def _calcular_rebote(ind):
    scores = {}
    precio = ind.get("precio")
    rsi = ind.get("rsi")
    vol_rel = ind.get("vol_relativo")
    macd = ind.get("macd")
    macd_signal = ind.get("macd_signal")
    mm200 = ind.get("mm200")
    precios = ind.get("precios_historicos")

    if precios and len(precios) >= 60:
        ultimos_60 = precios[-60:]
        max_60 = max(ultimos_60)
        min_60 = min(ultimos_60)
        if min_60 > 0:
            rango_pct = (max_60 - min_60) / min_60 * 100
            if rango_pct < 15:
                scores["rango"] = 10.0
            elif rango_pct < 20:
                scores["rango"] = 8.0
            elif rango_pct < 25:
                scores["rango"] = 6.0
            else:
                scores["rango"] = 3.0
            distancia_min_pct = (precio - min_60) / min_60 * 100 if min_60 > 0 else 100
            if distancia_min_pct < 3:
                scores["cerca_minimo"] = 10.0
            elif distancia_min_pct < 5:
                scores["cerca_minimo"] = 8.0
            elif distancia_min_pct < 8:
                scores["cerca_minimo"] = 6.0
            else:
                scores["cerca_minimo"] = 3.0
            distancia_max_pct = (max_60 - precio) / precio * 100 if precio > 0 else 0
            penalizacion_recorrido = -1.0 if distancia_max_pct < 10 else 0.0
        else:
            scores["rango"] = 5.0
            scores["cerca_minimo"] = 5.0
            penalizacion_recorrido = 0.0
    else:
        scores["rango"] = 5.0
        scores["cerca_minimo"] = 5.0
        penalizacion_recorrido = 0.0

    if rsi:
        if 30 <= rsi <= 45:
            scores["rsi"] = 10.0
        elif 45 < rsi <= 55:
            scores["rsi"] = 7.0
        elif rsi < 30:
            scores["rsi"] = 5.0
        else:
            scores["rsi"] = 3.0
    else:
        scores["rsi"] = 5.0

    if vol_rel:
        if vol_rel > 1.5:
            scores["volumen"] = 10.0
        elif vol_rel > 1.2:
            scores["volumen"] = 7.0
        elif vol_rel > 0.8:
            scores["volumen"] = 5.0
        else:
            scores["volumen"] = 3.0
    else:
        scores["volumen"] = 5.0

    if macd and macd_signal:
        scores["macd"] = 10.0 if macd > macd_signal else 4.0
    else:
        scores["macd"] = 5.0

    penalizacion_mm200 = 0.0
    if precio and mm200 and precio < mm200:
        penalizacion_mm200 = -1.0

    pesos = {"rango": 0.25, "cerca_minimo": 0.25, "rsi": 0.20, "volumen": 0.15, "macd": 0.10}
    score = sum(scores[k] * pesos[k] for k in pesos)
    score += penalizacion_recorrido + penalizacion_mm200
    score = max(0.0, min(10.0, score))

    textos = []
    if scores["rango"] >= 8.0:
        textos.append("rango lateral estrecho")
    if scores["cerca_minimo"] >= 8.0:
        textos.append("cerca del minimo del rango")
    if scores["rsi"] >= 8.0:
        textos.append("RSI en zona de rebote")
    if scores["volumen"] >= 7.0:
        textos.append("volumen comprador")
    if scores["macd"] >= 8.0:
        textos.append("MACD girando al alza")
    texto = " + ".join(textos) if textos else "setup debil"
    if texto:
        texto = texto[0].upper() + texto[1:]

    return {"score": round(score, 2), "desglose": scores, "texto": texto}


def _calcular_cambio_tendencia(ind):
    scores = {}
    precio = ind.get("precio")
    mm200 = ind.get("mm200")
    mm50 = ind.get("mm50")
    rsi = ind.get("rsi")
    macd = ind.get("macd")
    macd_signal = ind.get("macd_signal")
    adx = ind.get("adx")
    rs = ind.get("fuerza_relativa")
    vol_rel = ind.get("vol_relativo")
    precios = ind.get("precios_historicos")

    if precio and mm50:
        d = (precio / mm50 - 1) * 100
        if 0 < d < 5:
            scores["cruce_mm50"] = 10.0
        elif 5 <= d < 10:
            scores["cruce_mm50"] = 8.0
        elif d >= 10:
            scores["cruce_mm50"] = 6.0
        elif -3 < d <= 0:
            scores["cruce_mm50"] = 6.0
        else:
            scores["cruce_mm50"] = 2.0
    else:
        scores["cruce_mm50"] = 5.0

    if precio and mm200:
        d = (precio / mm200 - 1) * 100
        if 0 < d < 8:
            scores["cruce_mm200"] = 10.0
        elif d >= 8:
            scores["cruce_mm200"] = 7.0
        elif -5 < d <= 0:
            scores["cruce_mm200"] = 6.0
        else:
            scores["cruce_mm200"] = 2.0
    else:
        scores["cruce_mm200"] = 5.0

    pend_mm50 = _calcular_pendiente_media(precios, 50, 10)
    if pend_mm50 is not None:
        if pend_mm50 > 2:
            scores["pendiente_mm50"] = 10.0
        elif pend_mm50 > 0.5:
            scores["pendiente_mm50"] = 8.0
        elif pend_mm50 > -0.5:
            scores["pendiente_mm50"] = 5.0
        else:
            scores["pendiente_mm50"] = 2.0
    else:
        scores["pendiente_mm50"] = 5.0

    pend_mm200 = _calcular_pendiente_media(precios, 200, 20)
    if pend_mm200 is not None:
        if pend_mm200 > 0.5:
            scores["pendiente_mm200"] = 10.0
        elif pend_mm200 > -0.5:
            scores["pendiente_mm200"] = 7.0
        elif pend_mm200 > -2:
            scores["pendiente_mm200"] = 4.0
        else:
            scores["pendiente_mm200"] = 2.0
    else:
        scores["pendiente_mm200"] = 5.0

    if rsi:
        if 45 <= rsi <= 65:
            scores["rsi"] = 10.0
        elif 40 <= rsi < 45 or 65 < rsi <= 70:
            scores["rsi"] = 7.0
        elif rsi < 40:
            scores["rsi"] = 5.0
        else:
            scores["rsi"] = 3.0
    else:
        scores["rsi"] = 5.0

    if macd and macd_signal:
        scores["macd"] = 10.0 if macd > macd_signal else 3.0
    else:
        scores["macd"] = 5.0

    if rs:
        if rs > 5:
            scores["fuerza_relativa"] = 10.0
        elif rs > 0:
            scores["fuerza_relativa"] = 7.0
        else:
            scores["fuerza_relativa"] = 3.0
    else:
        scores["fuerza_relativa"] = 5.0

    if adx:
        if adx > 20:
            scores["adx"] = 10.0
        elif adx > 15:
            scores["adx"] = 7.0
        else:
            scores["adx"] = 5.0
    else:
        scores["adx"] = 5.0

    if vol_rel:
        if vol_rel > 1.5:
            scores["volumen"] = 10.0
        elif vol_rel > 1.2:
            scores["volumen"] = 7.0
        elif vol_rel > 0.8:
            scores["volumen"] = 5.0
        else:
            scores["volumen"] = 3.0
    else:
        scores["volumen"] = 5.0

    tiene_ruptura, desc_ruptura = _detectar_ruptura_estructura(precios)
    scores["ruptura_estructura"] = 10.0 if tiene_ruptura else 3.0

    penal_vertical = 0.0
    if precios and len(precios) >= 6:
        if precios[-6] > 0:
            subida_5d = (precios[-1] / precios[-6] - 1) * 100
            if subida_5d > 15:
                penal_vertical = -2.0

    penal_caida = 0.0
    if precios and len(precios) >= 4:
        if precios[-4] > 0:
            caida_3d = (precios[-1] / precios[-4] - 1) * 100
            if caida_3d < -8:
                penal_caida = -2.0
            elif caida_3d < -5:
                penal_caida = -1.5

    penal_rsi = -2.0 if (rsi and rsi > 75) else 0.0

    penal_lejos = 0.0
    if precios and len(precios) >= 200 and precio:
        max_anual = max(precios[-250:])
        if max_anual > 0:
            d = (precio / max_anual - 1) * 100
            if d < -40:
                penal_lejos = -1.5
            elif d < -30:
                penal_lejos = -1.0

    pesos = {
        "cruce_mm50": 0.12, "cruce_mm200": 0.08,
        "pendiente_mm50": 0.10, "pendiente_mm200": 0.05,
        "rsi": 0.07, "macd": 0.06, "fuerza_relativa": 0.08,
        "adx": 0.05, "volumen": 0.17, "ruptura_estructura": 0.22,
    }
    score = sum(scores[k] * pesos[k] for k in pesos)
    score += penal_vertical + penal_rsi + penal_caida + penal_lejos
    score = max(0.0, min(10.0, score))

    textos = []
    if scores["ruptura_estructura"] >= 8.0:
        textos.append("ruptura de estructura")
    if scores["cruce_mm50"] >= 8.0:
        textos.append("precio superando MM50")
    if scores["cruce_mm200"] >= 8.0:
        textos.append("recuperando MM200")
    if scores["pendiente_mm50"] >= 8.0:
        textos.append("MM50 girando al alza")
    if scores["pendiente_mm200"] >= 8.0:
        textos.append("MM200 girando al alza")
    if scores["rsi"] >= 8.0:
        textos.append("RSI en zona optima")
    if scores["macd"] >= 8.0:
        textos.append("MACD cruzado al alza")
    if scores["volumen"] >= 7.0:
        textos.append("volumen de ruptura")
    if scores["fuerza_relativa"] >= 8.0:
        textos.append("fuerza relativa positiva")
    texto = " + ".join(textos) if textos else "setup debil"
    if texto:
        texto = texto[0].upper() + texto[1:]

    return {"score": round(score, 2), "desglose": scores, "texto": texto,
            "tiene_ruptura": tiene_ruptura, "desc_ruptura": desc_ruptura}


def calcular_score_reversion(ind):
    precio = ind.get("precio")
    mm50 = ind.get("mm50")
    atr = ind.get("atr")
    precios = ind.get("precios_historicos")

    rebote = _calcular_rebote(ind)
    cambio = _calcular_cambio_tendencia(ind)

    if rebote["score"] >= cambio["score"]:
        categoria = "REBOTE"
        score_final = rebote["score"]
        texto = rebote["texto"]
        tiene_ruptura = False
    else:
        categoria = "CAMBIO"
        score_final = cambio["score"]
        texto = cambio["texto"]
        tiene_ruptura = cambio.get("tiene_ruptura", False)

    pend_mm200 = _calcular_pendiente_media(precios, 200, 20)
    pend_mm200_pos = pend_mm200 is not None and pend_mm200 > 0

    pend_mm50 = _calcular_pendiente_media(precios, 50, 10)
    pend_mm50_pos = pend_mm50 is not None and pend_mm50 > 0.5

    vol_rel = ind.get("vol_relativo")
    vol_alto = vol_rel is not None and vol_rel > 1.5

    dist_max = None
    if precios and len(precios) >= 200 and precio:
        max_anual = max(precios[-250:])
        if max_anual > 0:
            dist_max = (precio / max_anual - 1) * 100

    muy_lejos = dist_max is not None and dist_max < -30

    if tiene_ruptura and vol_alto and pend_mm200_pos and pend_mm50_pos:
        estado = "TENDENCIA_CONSOLIDADA"
    elif tiene_ruptura and vol_alto and not muy_lejos:
        estado = "CAMBIO_CONFIRMADO"
    elif tiene_ruptura or score_final >= 7.5:
        estado = "GIRO_TEMPRANO"
    else:
        estado = "DEBIL"

    stop, objetivo, rb = _calcular_stop_objetivo(precio, precios, mm50, atr)

    return {
        "score": score_final,
        "score_rebote": rebote["score"],
        "score_cambio": cambio["score"],
        "categoria": categoria,
        "texto": texto,
        "estado": estado,
        "stop": stop,
        "objetivo": objetivo,
        "rb": rb,
        "distancia_max_anual": round(dist_max, 1) if dist_max is not None else None,
        "desglose_rebote": rebote["desglose"],
        "desglose_cambio": cambio["desglose"],
    }