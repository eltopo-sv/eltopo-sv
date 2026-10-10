"""ELTOPO - Motores de trading (scalping, day, swing) + coordinador."""

from datetime import datetime

from .datos import obtener_datos, obtener_fundamental
from .indicadores import agregar_indicadores, resumen_indicadores, ultimo_valor
from .indicadores_extra import (
    calcular_volume_profile,
    calcular_fuerza_relativa,
    calcular_pivotes,
)
from .scoring import calcular_score, etiquetar_score
from .sentimiento import obtener_sentimiento
from .catalizadores import obtener_catalizadores


UMBRALES = {
    "scalping": {"volumen_min": 50_000, "precio_min": 10},
    "day":      {"volumen_min": 50_000, "precio_min": 5},
    "swing":    {"volumen_min": 20_000, "precio_min": 5},
}


def aplicar_filtros(df, ticker, motor="swing"):
    if df is None or df.empty:
        return False, "Sin datos"
    precio = ultimo_valor(df, "Close")
    volumen_medio = df["Volume"].tail(20).mean() if "Volume" in df.columns else 0
    if precio is None:
        return False, "Sin precio"
    umbral = UMBRALES.get(motor, UMBRALES["swing"])
    if precio < umbral["precio_min"]:
        return False, "Precio bajo"
    if volumen_medio < umbral["volumen_min"]:
        return False, "Volumen bajo"
    return True, "OK"


def calcular_operativa(df, motor="swing"):
    precio = ultimo_valor(df, "Close")
    atr = ultimo_valor(df, "ATR")
    if precio is None or atr is None:
        return None
    config = {
        "scalping": {"mult_stop": 1.0, "mult_obj": 2.5, "horizonte": "5-30 min",  "riesgo_pct": 0.5},
        "day":      {"mult_stop": 1.5, "mult_obj": 3.0, "horizonte": "1-6 horas", "riesgo_pct": 1.0},
        "swing":    {"mult_stop": 2.0, "mult_obj": 6.0, "horizonte": "3-15 dias", "riesgo_pct": 2.0},
    }
    c = config.get(motor, config["swing"])
    stop = precio - (c["mult_stop"] * atr)
    objetivo = precio + (c["mult_obj"] * atr)
    rr = (objetivo - precio) / (precio - stop) if (precio - stop) > 0 else 0
    return {
        "entrada": round(precio, 2),
        "objetivo": round(objetivo, 2),
        "stop": round(stop, 2),
        "rr": round(rr, 2),
        "horizonte": c["horizonte"],
        "riesgo_pct": c["riesgo_pct"],
    }


def analizar_motor(ticker, motor="swing", df_spy=None):
    df = obtener_datos(ticker, motor)
    if df is None:
        return {"motor": motor, "valido": False, "error": "Sin datos"}

    ok, razon = aplicar_filtros(df, ticker, motor)
    if not ok:
        return {"motor": motor, "valido": False, "error": "Filtro: " + razon}

    df = agregar_indicadores(df, motor=motor)
    resumen = resumen_indicadores(df)

    poc, _ = calcular_volume_profile(df)
    rs = calcular_fuerza_relativa(df, df_spy, ventana=30) if df_spy is not None else None
    pivotes = calcular_pivotes(df)

    resumen["poc"] = poc
    resumen["fuerza_relativa"] = rs
    resumen["pivotes"] = pivotes
    resumen["precios_historicos"] = df["Close"].tail(50).tolist()

    resultado = calcular_score(resumen, motor=motor)
    etiqueta, color = etiquetar_score(resultado["score_final"])

    operativa = calcular_operativa(df, motor=motor)

    indicadores_limpios = {}
    for k, v in resumen.items():
        if k == "precios_historicos":
            # Preservar la lista tal cual (la usa el grafico)
            indicadores_limpios[k] = v
        elif isinstance(v, (int, float)) and v is not None:
            indicadores_limpios[k] = round(float(v), 2)
        elif isinstance(v, dict):
            indicadores_limpios[k] = v
        elif isinstance(v, list):
            indicadores_limpios[k] = None
        elif v is None:
            indicadores_limpios[k] = None

    return {
        "motor": motor,
        "valido": True,
        "score": resultado["score_final"],
        "etiqueta": etiqueta,
        "color": color,
        "operativa": operativa,
        "scores_individuales": {k: round(v, 2) for k, v in resultado["scores_individuales"].items()},
        "indicadores": indicadores_limpios,
    }


def coordinar_motores(resultados):
    validos = [r for r in resultados.values() if r.get("valido") and r.get("score", 0) >= 5.0]

    if not validos:
        return {
            "mejor_estrategia": None,
            "score": 0,
            "confianza": 0,
            "mensaje": "No operar - ninguna estrategia valida",
            "color": "rojo",
        }

    validos.sort(key=lambda x: x["score"], reverse=True)
    mejor = validos[0]
    confianza = min(100, int(mejor["score"] * 10))

    if mejor["score"] < 5.5:
        return {"mejor_estrategia": mejor["motor"], "score": mejor["score"], "confianza": confianza, "mensaje": "NO OPERAR - Score bajo", "color": "rojo"}
    if mejor["score"] < 7.0:
        return {"mejor_estrategia": mejor["motor"], "score": mejor["score"], "confianza": confianza, "mensaje": "Precaucion - Setup mediocre", "color": "amarillo"}
    if mejor["score"] < 8.5:
        return {"mejor_estrategia": mejor["motor"], "score": mejor["score"], "confianza": confianza, "mensaje": "Setup valido", "color": "verde"}
    return {"mejor_estrategia": mejor["motor"], "score": mejor["score"], "confianza": confianza, "mensaje": "Setup premium", "color": "verde_fuerte"}


def analizar_ticker(ticker):
    ticker = ticker.upper()
    df_spy = obtener_datos("SPY", "swing")
    resultados = {
        "scalping": analizar_motor(ticker, "scalping", df_spy),
        "day_trading": analizar_motor(ticker, "day", df_spy),
        "swing": analizar_motor(ticker, "swing", df_spy),
    }
    recomendacion = coordinar_motores(resultados)
    fundamental = obtener_fundamental(ticker)
    sentimiento = obtener_sentimiento(ticker)
    catalizadores = obtener_catalizadores(ticker)
    return {
        "ticker": ticker,
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "hora": datetime.now().strftime("%H:%M"),
        "recomendacion_final": recomendacion,
        "estilos": resultados,
        "fundamental": fundamental,
        "sentimiento": sentimiento,
        "catalizadores": catalizadores,
    }
