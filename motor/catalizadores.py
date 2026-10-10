"""ELTOPO - Modulo de catalizadores (Finnhub)."""

import finnhub
from datetime import datetime, timedelta

from .config import FINNHUB_API_KEY
from .cache import guardar_cache, leer_cache


def obtener_catalizadores(ticker):
    """Obtiene catalizadores desde Finnhub."""
    ticker = ticker.upper()
    cache_key = "cat_" + ticker

    cache = leer_cache(cache_key, ttl=21600)
    if cache:
        return cache

    data = {
        "proximos_earnings": None,
        "dias_hasta_earnings": None,
        "historial_earnings": None,
        "nota": "Pendiente",
    }

    if not FINNHUB_API_KEY:
        data["nota"] = "Sin API key"
        return data

    try:
        client = finnhub.Client(api_key=FINNHUB_API_KEY)

        hoy = datetime.now()
        futuro = hoy + timedelta(days=90)

        # Proximos earnings
        try:
            cal = client.earnings_calendar(
                _from=hoy.strftime("%Y-%m-%d"),
                to=futuro.strftime("%Y-%m-%d"),
                symbol=ticker,
            )
            if cal and cal.get("earningsCalendar"):
                proximo = cal["earningsCalendar"][0]
                fecha_earn = proximo.get("date")
                data["proximos_earnings"] = fecha_earn
                if fecha_earn:
                    try:
                        fecha_dt = datetime.strptime(fecha_earn, "%Y-%m-%d")
                        data["dias_hasta_earnings"] = (fecha_dt - hoy).days
                    except Exception:
                        pass
        except Exception as e:
            print("  earnings calendar fallo: " + str(e))

        # Historial de earnings (ultimos 4 trimestres)
        try:
            hist = client.company_earnings(ticker, limit=4)
            if hist:
                data["historial_earnings"] = [
                    {
                        "periodo": h.get("period"),
                        "actual": h.get("actual"),
                        "estimado": h.get("estimate"),
                        "sorpresa_pct": h.get("surprisePercent"),
                    }
                    for h in hist
                ]
        except Exception as e:
            print("  earnings historial fallo: " + str(e))

        data["nota"] = "OK"

    except Exception as e:
        print("  catalizadores fallo: " + str(e))
        data["nota"] = "Error: " + str(e)

    guardar_cache(cache_key, data)
    return data
