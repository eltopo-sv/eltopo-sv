# -*- coding: utf-8 -*-
"""Genera el universo de ~2000 tickers mas valiosos para trading LONG.

Estrategia:
1. Leer motor/tickers.json (5158 tickers)
2. yfinance (con curl_cffi) -> precio + VOLUMEN REAL de 1 mes
3. Filtrar por precio > $5 Y volumen > 500k -> ~2000-2500
4. Finnhub /stock/profile2 -> market cap + sector (solo a los que pasan 3)
5. Ordenar por market cap y recortar a 2000
6. Guardar motor/universe_swing.json

Uso:
    python -m scripts.generar_universo

IMPORTANTE:
- yfinance necesita curl_cffi para no ser bloqueado por Yahoo
- Delay aleatorio 1.5-3s entre tickers para evitar rate limit
- Guardado de progreso cada 500 tickers
"""

import json
import os
import time
import random
from datetime import datetime
from pathlib import Path

import requests
import yfinance as yf
from curl_cffi import requests as curl_requests
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
FINNHUB_PROFILE_URL = "https://finnhub.io/api/v1/stock/profile2"

MIN_PRECIO = 5.0
MIN_VOLUMEN = 500_000
MIN_MARKET_CAP = 1_000_000_000
TARGET_TICKERS = 2000
PROGRESO_CADA = 500
DELAY_MIN = 1.5
DELAY_MAX = 3.0


def _cargar_tickers():
    ruta = Path(__file__).parent.parent / "motor" / "tickers.json"
    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return list(data.keys())
    return data


def _descargar_datos_yf(symbol, session):
    """Descarga datos de un ticker con yfinance. Devuelve (precio, vol_medio) o (None, None)."""
    try:
        df = yf.download(
            symbol, period="1mo", interval="1d",
            session=session, progress=False, threads=False
        )
        if df is None or df.empty:
            return None, None

        # FIX: aplanar MultiIndex
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)

        if "Close" not in df.columns or "Volume" not in df.columns:
            return None, None

        precio = float(df["Close"].iloc[-1])
        vol_medio = float(df["Volume"].mean())

        if precio <= 0 or vol_medio <= 0:
            return None, None

        return precio, vol_medio
    except Exception:
        return None, None


def _finnhub_profile(symbol):
    """Obtiene market cap y sector de Finnhub."""
    try:
        r = requests.get(
            FINNHUB_PROFILE_URL,
            params={"symbol": symbol, "token": FINNHUB_API_KEY},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if not data or not data.get("marketCapitalization"):
            return None
        return {
            "market_cap": data.get("marketCapitalization", 0) * 1_000_000,
            "sector": data.get("finnhubIndustry", "Unknown"),
            "nombre": data.get("name", symbol),
            "exchange": data.get("exchange", ""),
        }
    except Exception:
        return None


def generar_universo():
    print("=" * 70)
    print("  GENERADOR DE UNIVERSO - ELTOPO (yfinance)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    ruta_progreso = Path(__file__).parent.parent / "data" / "universo_progreso.json"
    ruta_progreso.parent.mkdir(exist_ok=True)

    # Cargar progreso previo (si existe)
    progreso_previo = {}
    if ruta_progreso.exists():
        try:
            with open(ruta_progreso, "r", encoding="utf-8") as f:
                progreso_previo = json.load(f)
            print(f"\n[INFO] Progreso previo encontrado: {len(progreso_previo)} tickers procesados")
        except Exception:
            progreso_previo = {}

    # 1. Cargar tickers
    tickers = _cargar_tickers()
    print(f"\n[1/5] Tickers cargados: {len(tickers)}")

    # 2. Descargar datos con yfinance
    print(f"\n[2/5] Descargando datos de yfinance (~{len(tickers)*2//60} min)...")
    print(f"  Delay: {DELAY_MIN}-{DELAY_MAX}s entre tickers")
    print(f"  Progreso: guardado cada {PROGRESO_CADA} tickers\n")

    session = curl_requests.Session(impersonate="chrome")
    con_datos = dict(progreso_previo)  # {ticker: {precio, volumen_medio}}

    inicio = time.time()
    nuevos = 0

    for i, sym in enumerate(tickers, 1):
        if sym in con_datos:
            continue

        precio, vol_medio = _descargar_datos_yf(sym, session)
        if precio and vol_medio:
            con_datos[sym] = {
                "precio": round(precio, 2),
                "volumen_medio": int(vol_medio),
            }
            nuevos += 1

        # Progreso
        if i % 50 == 0:
            elapsed = time.time() - inicio
            ritmo = i / elapsed if elapsed > 0 else 0
            restantes = (len(tickers) - i) / ritmo if ritmo > 0 else 0
            print(f"  [{i}/{len(tickers)}] {len(con_datos)} validos | "
                  f"{ritmo:.1f} tickers/s | ~{restantes/60:.0f} min restantes")

        # Guardar progreso cada N tickers
        if i % PROGRESO_CADA == 0:
            with open(ruta_progreso, "w", encoding="utf-8") as f:
                json.dump(con_datos, f, ensure_ascii=False)
            print(f"  [PROGRESO guardado: {len(con_datos)} tickers]")

        # Delay anti-bloqueo
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # Guardar progreso final
    with open(ruta_progreso, "w", encoding="utf-8") as f:
        json.dump(con_datos, f, ensure_ascii=False)

    print(f"\n  Total con datos validos: {len(con_datos)}")

    # 3. Filtrar por precio + volumen
    print(f"\n[3/5] Filtrando por precio > ${MIN_PRECIO} y volumen > {MIN_VOLUMEN:,}...")
    filtrados = [
        {"ticker": sym, **datos}
        for sym, datos in con_datos.items()
        if datos["precio"] > MIN_PRECIO and datos["volumen_medio"] > MIN_VOLUMEN
    ]
    print(f"  Tras filtro precio+volumen: {len(filtrados)}")

    # 4. Finnhub: market cap + sector
    print(f"\n[4/5] Consultando Finnhub para {len(filtrados)} tickers (~{len(filtrados)//60} min)...")
    enriquecidos = []
    total = len(filtrados)

    for i, t in enumerate(filtrados, 1):
        perfil = _finnhub_profile(t["ticker"])
        if perfil and perfil["market_cap"] > MIN_MARKET_CAP:
            t["market_cap"] = perfil["market_cap"]
            t["sector"] = perfil["sector"]
            t["nombre"] = perfil["nombre"]
            t["exchange"] = perfil["exchange"]
            enriquecidos.append(t)
        if i % 100 == 0 or i == total:
            print(f"  [{i}/{total}] {len(enriquecidos)} validos")
        time.sleep(1.05)  # 60/min Finnhub

    print(f"  Total tras filtro market cap > $1B: {len(enriquecidos)}")

    # 5. Ordenar y recortar
    print(f"\n[5/5] Ordenando por market cap y recortando a {TARGET_TICKERS}...")
    enriquecidos.sort(key=lambda x: x["market_cap"], reverse=True)
    final = enriquecidos[:TARGET_TICKERS]

    ruta = Path(__file__).parent.parent / "motor" / "universe_swing.json"
    output = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(final),
        "criterios": {
            "precio_min": MIN_PRECIO,
            "volumen_min": MIN_VOLUMEN,
            "market_cap_min": MIN_MARKET_CAP,
        },
        "tickers": [t["ticker"] for t in final],
        "detalles": final,
    }

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print(f"  COMPLETADO")
    print(f"  Universo guardado: {len(final)} tickers")
    print(f"  Ruta: {ruta}")
    print(f"{'=' * 70}")

    # Distribucion por sector
    sectores = {}
    for t in final:
        s = t.get("sector", "Unknown")
        sectores[s] = sectores.get(s, 0) + 1
    print("\nDistribucion por sector (top 10):")
    for s, c in sorted(sectores.items(), key=lambda x: -x[1])[:10]:
        print(f"  {s}: {c}")

    return output


if __name__ == "__main__":
    generar_universo()