# -*- coding: utf-8 -*-
"""Configuracion de ELTOPO (lee de .env)."""

import os
from pathlib import Path

# Cargar .env si existe
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass


# API keys (desde variables de entorno, NUNCA escritas aqui)
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")


# Timeframes por motor
TIMEFRAMES = {
    "scalping": "5m",
    "day": "15m",
    "swing": "1d",
}

# Periodos de historico
PERIODOS = {
    "scalping": "7d",
    "day": "60d",
    "swing": "2y",
}

# Limites de cache (segundos)
CACHE_TTL = {
    "scalping": 60,
    "day": 300,
    "swing": 3600,
}

# Numero de velas minimas
MIN_VELAS = {
    "scalping": 50,
    "day": 100,
    "swing": 200,
}
