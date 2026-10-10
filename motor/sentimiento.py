"""ELTOPO - Modulo de sentimiento (Finnhub)."""

import finnhub

from .config import FINNHUB_API_KEY
from .cache import guardar_cache, leer_cache


def obtener_sentimiento(ticker):
    """Obtiene datos de sentimiento desde Finnhub."""
    ticker = ticker.upper()
    cache_key = "sent_" + ticker

    cache = leer_cache(cache_key, ttl=21600)
    if cache:
        return cache

    data = {
        "recomendacion_analistas": None,
        "precio_objetivo": None,
        "insider_compras": None,
        "insider_ventas": None,
        "nota": "Pendiente",
    }

    if not FINNHUB_API_KEY:
        data["nota"] = "Sin API key"
        return data

    try:
        client = finnhub.Client(api_key=FINNHUB_API_KEY)

        # Recomendaciones de analistas
        try:
            reco = client.recommendation_trends(ticker)
            if reco and len(reco) > 0:
                ult = reco[0]
                data["recomendacion_analistas"] = {
                    "strong_buy": ult.get("strongBuy", 0),
                    "buy": ult.get("buy", 0),
                    "hold": ult.get("hold", 0),
                    "sell": ult.get("sell", 0),
                    "strong_sell": ult.get("strongSell", 0),
                    "periodo": ult.get("period", ""),
                }
        except Exception as e:
            print("  reco fallo: " + str(e))

        # Insider transactions (ultimos 90 dias)
        try:
            from datetime import datetime, timedelta
            hoy = datetime.now()
            hace_90 = hoy - timedelta(days=90)
            insider = client.stock_insider_transactions(
                ticker,
                hace_90.strftime("%Y-%m-%d"),
                hoy.strftime("%Y-%m-%d"),
            )
            if insider and insider.get("data"):
                trans = insider["data"]
                compras = sum(1 for t in trans if t.get("change", 0) > 0)
                ventas = sum(1 for t in trans if t.get("change", 0) < 0)
                data["insider_compras"] = compras
                data["insider_ventas"] = ventas
        except Exception as e:
            print("  insider fallo: " + str(e))

        data["nota"] = "OK"

    except Exception as e:
        print("  sentimiento fallo: " + str(e))
        data["nota"] = "Error: " + str(e)

    guardar_cache(cache_key, data)
    return data



def _ajustar_crecimiento(v):
    """Ajusta valores de crecimiento de Finnhub.

    Dividir entre 10 o 100 segun el tamano hasta que sea razonable.
    """
    if v is None:
        return None
    try:
        v = float(v)
        # Si es < 1, es decimal -> x100
        if abs(v) < 1:
            return round(v * 100, 2)
        # Si es > 100, dividir sucesivamente
        while abs(v) > 100:
            v = v / 10
            if abs(v) <= 100:
                break
        return round(v, 2)
    except (ValueError, TypeError):
        return v


def obtener_fundamental_finnhub(ticker):
    """Obtiene datos fundamentales desde Finnhub (fallback)."""
    ticker = ticker.upper()

    if not FINNHUB_API_KEY:
        return None

    try:
        client = finnhub.Client(api_key=FINNHUB_API_KEY)

        # 1. Perfil de la empresa
        perfil = client.company_profile2(symbol=ticker)
        if not perfil or not perfil.get("name"):
            return None

        # 2. Metricas financieras
        try:
            metricas = client.company_basic_financials(ticker, "all")
            m = metricas.get("metric", {}) if metricas else {}
        except Exception:
            m = {}

        def _safe(key):
            val = m.get(key)
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return val

        # Finnhub devuelve los ratios como porcentaje o decimal
        # Normalizamos los que están como decimal
        def _norm_pct(v):
            """Normaliza porcentajes de Finnhub.

            Finnhub devuelve valores en escalas caoticas:
            - 0.28 (decimal) -> 28%
            - 25.63 (porcentaje) -> 25.63%
            - 2563 (x100) -> 25.63%
            - 87877 (x10000) -> 8.79%
            - 142400 (x100000) -> 1.42%

            Estrategia: dividir entre 100 hasta que el valor sea razonable.
            """
            if v is None:
                return None
            try:
                v = float(v)
                # Si es < 1, es decimal -> x100
                if abs(v) < 1:
                    return round(v * 100, 2)
                # Dividir sucesivamente entre 100 hasta que sea < 100
                # (excepto si ya esta en rango normal)
                while abs(v) > 100 and abs(v) >= 100:
                    v = v / 100
                    if abs(v) <= 100:
                        break
                return round(v, 2)
            except (ValueError, TypeError):
                return v

        data = {
            "nombre": perfil.get("name"),
            "sector": perfil.get("finnhubIndustry"),
            "industria": perfil.get("finnhubIndustry"),
            "pais": perfil.get("country"),
            "empleados": None,

            # Crecimiento
            # Finnhub devuelve revenueGrowthTTMYoy en escalas distintas
            # Si > 100, dividir entre 10 (probable x10)
            "ingresos_yoy": _ajustar_crecimiento(m.get("revenueGrowthTTMYoy")),
            "beneficios_yoy": _ajustar_crecimiento(m.get("epsGrowthTTMYoy")),
            "crecimiento_beneficios_q": _norm_pct(m.get("epsGrowthQuarterlyYoy")),

            # Margenes
            "margen_bruto": _norm_pct(m.get("grossMarginTTM")),
            "margen_operativo": _norm_pct(m.get("operatingMarginTTM")),
            "margen_neto": _norm_pct(m.get("netProfitMarginTTM")),

            # Valoracion
            "per": _safe("peTTM") or _safe("peBasicExclExtraTTM"),
            "per_forward": _safe("peForward"),
            "ps": _safe("psTTM"),
            "pb": _safe("pbQuarterly") or _safe("pbAnnual"),
            "ev_ebitda": _safe("currentEv/freeCashFlowTTM"),

            # Solvencia
            "deuda_equity": _safe("totalDebt/totalEquityQuarterly"),
            "current_ratio": _safe("currentRatioQuarterly"),
            "quick_ratio": _safe("quickRatioQuarterly"),

            # Rentabilidad
            "roe": _norm_pct(m.get("roeTTM")),
            "roa": _norm_pct(m.get("roaTTM")),

            # Dividendos
            "dividend_yield": _safe("dividendYieldIndicatedAnnual"),
            "payout_ratio": _norm_pct(m.get("payoutRatioTTM")),

            # Tamano
            "market_cap": (perfil.get("marketCapitalization") or 0) * 1_000_000,
            "enterprise_value": None,

            # Otros
            "beta": _safe("beta"),
            "precio_objetivo": None,
            "recomendacion": None,

            # Metadata
            "_fuente": "finnhub",
        }

        print("[OK] " + ticker + " fundamental desde Finnhub")
        return data

    except Exception as e:
        print("  finnhub fundamental fallo: " + str(e))
        return None
