# -*- coding: utf-8 -*-
"""Scanner principal ELTOPO."""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from motor.datos import obtener_datos
from motor.indicadores import agregar_indicadores, resumen_indicadores
from motor.indicadores_extra import calcular_fuerza_relativa

from .config import (
    MAX_TICKERS, TOP_N_LONG, TOP_N_SHORT, MAX_WORKERS,
    MIN_SCORE_LONG, MIN_SCORE_SHORT, TIMEFRAME,
    PAUSA_CADA_TICKERS, PAUSA_SEGUNDOS,
)
from .filtros import es_operable, es_short_operable
from .scoring_long import calcular_score_long
from .scoring_short import calcular_score_short


def _ruta_resultado():
    return Path(__file__).parent.parent / "data" / "scanner_result.json"


def _ruta_top1000():
    return Path(__file__).parent.parent / "data" / "top_1000.json"


def analizar_ticker_scanner(ticker, df_spy):
    try:
        df = obtener_datos(ticker, TIMEFRAME)
        if df is None:
            return None
        if not es_operable(df, ticker):
            return None

        df = agregar_indicadores(df, motor=TIMEFRAME)
        resumen = resumen_indicadores(df)
        resumen["fuerza_relativa"] = calcular_fuerza_relativa(df, df_spy, ventana=30)
        resumen["precios_historicos"] = df["Close"].tail(50).tolist()

        long_result = calcular_score_long(resumen)
        short_result = calcular_score_short(resumen)

        return {
            "ticker": ticker,
            "score_long": long_result["score"],
            "score_short": short_result["score"],
            "precio": resumen.get("precio"),
            "desglose_long": long_result["desglose"],
            "desglose_short": short_result["desglose"],
        }
    except Exception:
        return None


def _cargar_tickers(tickers_file=None):
    """Carga la lista de tickers."""
    if tickers_file:
        ruta = Path(tickers_file)
        if ruta.exists():
            with open(ruta, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "tickers" in data:
                return data["tickers"]
            elif isinstance(data, list):
                return data
            else:
                print(f"[WARN] Formato desconocido en {ruta}. Usando tickers.json")
        else:
            print(f"[WARN] No existe {ruta}. Usando tickers.json completo")

    tickers_path = Path(__file__).parent.parent / "motor" / "tickers.json"
    with open(tickers_path, "r", encoding="utf-8") as f:
        tickers = json.load(f)
    return list(tickers.keys())


def escanear(
    max_tickers=None,
    top_n_long=None,
    top_n_short=None,
    tickers_file=None,
    save_top_long=1000,
):
    """Ejecuta el scanner con pausas anti rate-limit."""
    top_n_long = top_n_long or TOP_N_LONG
    top_n_short = top_n_short or TOP_N_SHORT

    print(f"\n{'='*70}")
    print(f"  SCANNER ELTOPO")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if tickers_file:
        print(f"  Modo: tickers especificos ({tickers_file})")
    else:
        print(f"  Modo: escaneo completo")
    print(f"  Workers: {MAX_WORKERS}")
    print(f"  Pausa: {PAUSA_SEGUNDOS}s cada {PAUSA_CADA_TICKERS} tickers")
    print(f"{'='*70}\n")

    # Cargar lista de tickers
    if tickers_file:
        lista = _cargar_tickers(tickers_file)
        print(f"Tickers desde archivo: {len(lista)}")
    else:
        todos = _cargar_tickers()
        max_tickers = max_tickers or MAX_TICKERS
        lista = todos[:max_tickers]
        print(f"Tickers disponibles: {len(todos)}")
        print(f"A analizar: {len(lista)}")

    print(f"Top: {top_n_long} LONG + {top_n_short} SHORT\n")

    print("Descargando SPY (referencia)...")
    df_spy = obtener_datos("SPY", TIMEFRAME)

    resultados = []
    inicio = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {executor.submit(analizar_ticker_scanner, t, df_spy): t for t in lista}

        for i, futuro in enumerate(as_completed(futuros), 1):
            try:
                r = futuro.result()
                if r:
                    resultados.append(r)
            except Exception:
                pass

            # Pausa anti rate-limit
            if i % PAUSA_CADA_TICKERS == 0:
                print(f"  [PAUSA] {PAUSA_SEGUNDOS}s despues de {i} tickers...")
                time.sleep(PAUSA_SEGUNDOS)

            if i % 20 == 0:
                elapsed = time.time() - inicio
                print(f"  [{i}/{len(lista)}] {elapsed:.0f}s - {len(resultados)} validos")

    elapsed = time.time() - inicio

    top_long = sorted(
        [r for r in resultados if r["score_long"] >= MIN_SCORE_LONG],
        key=lambda x: x["score_long"],
        reverse=True
    )[:top_n_long]

    top_short = sorted(
        [r for r in resultados
         if r["score_short"] >= MIN_SCORE_SHORT
         and es_short_operable(r["ticker"])],
        key=lambda x: x["score_short"],
        reverse=True
    )[:top_n_short]

    resultado_final = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_analizados": len(resultados),
        "tiempo_segundos": round(elapsed, 1),
        "top_long": top_long,
        "top_short": top_short,
    }

    ruta = _ruta_resultado()
    ruta.parent.mkdir(exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(resultado_final, f, ensure_ascii=False, indent=2)

    # Guardar top N LONG en top_1000.json (solo si save_top_long > 0 y modo full)
    if save_top_long > 0 and not tickers_file:
        mejores_long = sorted(
            [r for r in resultados if r["score_long"] >= MIN_SCORE_LONG],
            key=lambda x: x["score_long"],
            reverse=True
        )[:save_top_long]

        tickers_top = [r["ticker"] for r in mejores_long]

        top1000_data = {
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total": len(tickers_top),
            "tickers": tickers_top,
        }

        ruta_top = _ruta_top1000()
        with open(ruta_top, "w", encoding="utf-8") as f:
            json.dump(top1000_data, f, ensure_ascii=False, indent=2)

        print(f"\n[OK] Guardados {len(tickers_top)} tickers en top_1000.json")

    print(f"\n{'='*70}")
    print(f"  COMPLETADO en {elapsed:.0f}s")
    print(f"{'='*70}\n")

    print(f"--- TOP {top_n_long} LONG ---")
    for i, r in enumerate(top_long, 1):
        print(f"  {i:2d}. {r['ticker']:6s} {r['score_long']:.2f}")

    print(f"\n--- TOP {top_n_short} SHORT ---")
    for i, r in enumerate(top_short, 1):
        print(f"  {i:2d}. {r['ticker']:6s} {r['score_short']:.2f}")

    print(f"\n{'='*70}")
    print(f"Guardado en: {ruta}")
    print(f"{'='*70}\n")

    return resultado_final


# =====================================================
# ESCANEO DE REVERSION (on-demand)
# =====================================================

def analizar_ticker_reversion(ticker, df_spy):
    """Analiza un ticker especificamente para REVERSION (v2)."""
    from .scoring_reversion import calcular_score_reversion

    try:
        df = obtener_datos(ticker, TIMEFRAME)
        if df is None:
            return None
        if not es_operable(df, ticker):
            return None

        df = agregar_indicadores(df, motor=TIMEFRAME)
        resumen = resumen_indicadores(df)
        resumen["fuerza_relativa"] = calcular_fuerza_relativa(df, df_spy, ventana=30)
        resumen["precios_historicos"] = df["Close"].tail(60).tolist()

        rev = calcular_score_reversion(resumen)

        return {
            "ticker": ticker,
            "score_reversion": rev["score"],
            "score_rebote": rev["score_rebote"],
            "score_cambio": rev["score_cambio"],
            "categoria": rev["categoria"],
            "texto": rev["texto"],
            "precio": resumen.get("precio"),
            "estado": rev.get("estado", "DEBIL"),
            "stop": rev.get("stop"),
            "objetivo": rev.get("objetivo"),
            "rb": rev.get("rb"),
        }
    except Exception:
        return None


def escanear_reversion(tickers_file=None, top_n=15, max_tickers=300, progress_callback=None):
    """
    Escaneo especifico para REVERSION.
    Analiza el Top N tickers del ultimo escaneo y calcula score_reversion.
    """
    if progress_callback:
        progress_callback(0, 0, "Cargando lista de tickers...")

    if tickers_file is None:
        # Usar el universo completo (1786 tickers) en vez del top_1000
        tickers_file = _ruta_universo()

    with open(tickers_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "tickers" in data:
        tickers = data["tickers"]
    else:
        tickers = data

    tickers = tickers[:max_tickers]
    total = len(tickers)

    if progress_callback:
        progress_callback(0, total, "Descargando SPY (referencia)...")

    df_spy = obtener_datos("SPY", TIMEFRAME)

    resultados = []
    inicio = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {executor.submit(analizar_ticker_reversion, t, df_spy): t for t in tickers}

        for i, futuro in enumerate(as_completed(futuros), 1):
            try:
                r = futuro.result()
                if r:
                    resultados.append(r)
            except Exception:
                pass

            if i % PAUSA_CADA_TICKERS == 0:
                time.sleep(PAUSA_SEGUNDOS)

            if progress_callback and (i % 10 == 0 or i == total):
                progress_callback(i, total, None)

    elapsed = time.time() - inicio

    top = sorted(
        [r for r in resultados if r["score_reversion"] >= 5.0],
        key=lambda x: x["score_reversion"],
        reverse=True
    )[:top_n]

    return {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_analizados": len(resultados),
        "tiempo_segundos": round(elapsed, 1),
        "top_reversion": top,
    }


# =====================================================
# ESCANEO FULL (universo 1786 tickers)
# =====================================================

def _ruta_universo():
    return Path(__file__).parent.parent / "motor" / "universe_swing.json"


def _ruta_resultado_full():
    return Path(__file__).parent.parent / "data" / "scanner_result_full.json"


def _cargar_universo():
    """Carga la lista de tickers del universo generado."""
    ruta = _ruta_universo()
    if not ruta.exists():
        print(f"[WARN] No existe {ruta}. Usando tickers.json")
        return _cargar_tickers()
    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "tickers" in data:
        return data["tickers"]
    return list(data)


def escanear_full(top_n_long=15, top_n_short=15, save_top_long=0):
    """Escaneo del universo ampliado (1786 tickers).

    Analiza el universo generado y guarda el resultado en
    data/scanner_result_full.json. NO toca top_1000.json.
    """
    print(f"\n{'='*70}")
    print(f"  SCANNER FULL ELTOPO")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    lista = _cargar_universo()
    print(f"Universo cargado: {len(lista)} tickers")
    print(f"Workers: {MAX_WORKERS}")
    print(f"Top: {top_n_long} LONG + {top_n_short} SHORT\n")

    print("Descargando SPY (referencia)...")
    df_spy = obtener_datos("SPY", TIMEFRAME)

    resultados = []
    inicio = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {executor.submit(analizar_ticker_scanner, t, df_spy): t for t in lista}

        for i, futuro in enumerate(as_completed(futuros), 1):
            try:
                r = futuro.result()
                if r:
                    resultados.append(r)
            except Exception:
                pass

            if i % PAUSA_CADA_TICKERS == 0:
                time.sleep(PAUSA_SEGUNDOS)

            if i % 20 == 0 or i == len(lista):
                elapsed = time.time() - inicio
                ritmo = i / elapsed if elapsed > 0 else 0
                print(f"  [{i}/{len(lista)}] {elapsed:.0f}s - {len(resultados)} validos - {ritmo:.2f}/s")

    elapsed = time.time() - inicio

    top_long = sorted(
        [r for r in resultados if r["score_long"] >= MIN_SCORE_LONG],
        key=lambda x: x["score_long"],
        reverse=True
    )[:top_n_long]

    top_short = sorted(
        [r for r in resultados
         if r["score_short"] >= MIN_SCORE_SHORT
         and es_short_operable(r["ticker"])],
        key=lambda x: x["score_short"],
        reverse=True
    )[:top_n_short]

    resultado_final = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_analizados": len(resultados),
        "tiempo_segundos": round(elapsed, 1),
        "universo_usado": len(lista),
        "top_long": top_long,
        "top_short": top_short,
    }

    ruta = _ruta_resultado_full()
    ruta.parent.mkdir(exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(resultado_final, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*70}")
    print(f"  COMPLETADO en {elapsed:.0f}s")
    print(f"  Guardado en: {ruta}")
    print(f"{'='*70}\n")

    print(f"--- TOP {top_n_long} LONG ---")
    for i, r in enumerate(top_long, 1):
        print(f"  {i:2d}. {r['ticker']:6s} {r['score_long']:.2f}")

    print(f"\n--- TOP {top_n_short} SHORT ---")
    for i, r in enumerate(top_short, 1):
        print(f"  {i:2d}. {r['ticker']:6s} {r['score_short']:.2f}")

    return resultado_final
