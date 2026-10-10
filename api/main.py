"""ELTOPO - API REST con FastAPI."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import json
import os
import threading
import uuid
import time
from datetime import datetime

from dotenv import load_dotenv
from motor.motores import analizar_ticker
from scanner.scanner import escanear, escanear_reversion, escanear_full
# --- Configuracion ---
load_dotenv()
SCANNER_TOKEN = os.getenv("SCANNER_TOKEN", "")

app = FastAPI(title="ELTOPO API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = Path(__file__).parent.parent / "web"
TICKERS_FILE = Path(__file__).parent.parent / "motor" / "tickers.json"
SCANNER_FILE = Path(__file__).parent.parent / "data" / "scanner_result.json"


SCANNER_FULL_FILE = Path(__file__).parent.parent / "data" / "scanner_result_full.json"
class AnalyzeRequest(BaseModel):
    ticker: str
    modo: str = "auto"


_tickers_cache = None


def _cargar_tickers():
    global _tickers_cache
    if _tickers_cache is None:
        try:
            with open(TICKERS_FILE, "r", encoding="utf-8") as f:
                _tickers_cache = json.load(f)
        except Exception:
            _tickers_cache = {}
    return _tickers_cache


# --- API endpoints ---

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/buscar")
def buscar(q: str):
    q = q.strip().lower()
    if not q:
        return {"resultados": []}

    tickers = _cargar_tickers()
    resultados = []
    ya_incluidos = set()

    for symbol, nombre in tickers.items():
        if symbol.lower().startswith(q) or nombre.lower().startswith(q):
            resultados.append({"symbol": symbol, "nombre": nombre})
            ya_incluidos.add(symbol)
            if len(resultados) >= 10:
                break

    if len(resultados) < 10:
        for symbol, nombre in tickers.items():
            if symbol in ya_incluidos:
                continue
            if q in symbol.lower() or q in nombre.lower():
                resultados.append({"symbol": symbol, "nombre": nombre})
                if len(resultados) >= 10:
                    break

    return {"resultados": resultados}


@app.post("/api/analyze")
def analizar(req: AnalyzeRequest):
    ticker = req.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker vacio")
    if len(ticker) > 10:
        raise HTTPException(status_code=400, detail="Ticker demasiado largo")
    try:
        resultado = analizar_ticker(ticker)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error: " + str(e))


# --- SCANNER endpoints ---

@app.get("/api/scanner")
def get_scanner():
    """Devuelve el Top 15 LONG + Top 15 SHORT del scanner."""
    if not SCANNER_FILE.exists():
        return {
            "error": "Scanner no ejecutado todavia",
            "hint": "Ejecuta: python -m scanner",
            "top_long": [],
            "top_short": [],
        }
    try:
        with open(SCANNER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error leyendo scanner: " + str(e))


@app.get("/api/scanner/long")
def get_scanner_long():
    """Devuelve solo el Top LONG."""
    if not SCANNER_FILE.exists():
        return {"error": "Scanner no ejecutado", "top_long": []}
    with open(SCANNER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "fecha": data.get("fecha"),
        "total_analizados": data.get("total_analizados"),
        "top_long": data.get("top_long", []),
    }


@app.get("/api/scanner/short")
def get_scanner_short():
    """Devuelve solo el Top SHORT."""
    if not SCANNER_FILE.exists():
        return {"error": "Scanner no ejecutado", "top_short": []}
    with open(SCANNER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "fecha": data.get("fecha"),
        "total_analizados": data.get("total_analizados"),
        "top_short": data.get("top_short", []),
    }


@app.post("/api/scanner/refresh")
def refresh_scanner(
    max_tickers: int = 5158,
    top_n: int = 15,
    token: str = "",
):
    """Ejecuta el scanner de nuevo (tarda ~45s).

    Requiere token si SCANNER_TOKEN esta configurado.
    Se pasa como query param: ?token=XXX
    """
    # Si hay token configurado, exigirlo
    if SCANNER_TOKEN and token != SCANNER_TOKEN:
        raise HTTPException(status_code=403, detail="Token invalido")

    try:
        resultado = escanear(max_tickers=max_tickers, top_n_long=top_n, top_n_short=top_n)
        return {
            "status": "ok",
            "fecha": resultado.get("fecha"),
            "total_analizados": resultado.get("total_analizados"),
            "tiempo_segundos": resultado.get("tiempo_segundos"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error ejecutando scanner: " + str(e))


# --- Frontend ---

@app.get("/")
def raiz():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/index.html")
def index_html():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/style.css")
def style_css():
    return FileResponse(WEB_DIR / "style.css", media_type="text/css")


@app.get("/app.js")
def app_js():
    return FileResponse(WEB_DIR / "app.js", media_type="application/javascript")


app.mount("/images", StaticFiles(directory=str(WEB_DIR / "images")), name="images")

# =====================================================
# REVERSION - Escaneo on-demand con progreso
# =====================================================

_reversion_jobs = {}
_reversion_lock = threading.Lock()
_reversion_job_activo = {"job_id": None}


def _run_reversion(job_id, max_tickers=500, top_n=15):
    """Ejecuta el escaneo de reversion en un hilo de background."""
    try:
        def progress_callback(i, total, msg):
            with _reversion_lock:
                if job_id in _reversion_jobs:
                    _reversion_jobs[job_id]["progreso"] = i
                    _reversion_jobs[job_id]["total"] = total
                    if msg:
                        _reversion_jobs[job_id]["mensaje"] = msg
                    elif total > 0:
                        pct = int(i * 100 / total)
                        _reversion_jobs[job_id]["mensaje"] = f"Analizando {i}/{total} ({pct}%)..."

        resultado = escanear_reversion(
            max_tickers=max_tickers,
            top_n=top_n,
            progress_callback=progress_callback,
        )

        with _reversion_lock:
            if job_id in _reversion_jobs:
                _reversion_jobs[job_id]["completado"] = True
                _reversion_jobs[job_id]["resultado"] = resultado
                _reversion_jobs[job_id]["mensaje"] = "Completado"
                _reversion_jobs[job_id]["tiempo"] = time.time()

    except Exception as e:
        with _reversion_lock:
            if job_id in _reversion_jobs:
                _reversion_jobs[job_id]["completado"] = True
                _reversion_jobs[job_id]["error"] = str(e)
                _reversion_jobs[job_id]["mensaje"] = f"Error: {str(e)}"

    finally:
        with _reversion_lock:
            if _reversion_job_activo["job_id"] == job_id:
                _reversion_job_activo["job_id"] = None


@app.post("/api/reversion/start")
def reversion_start(max_tickers: int = 500, top_n: int = 15):
    """Arranca un escaneo de reversion. Devuelve job_id."""
    with _reversion_lock:
        ahora = time.time()
        viejos = [
            jid for jid, j in _reversion_jobs.items()
            if j.get("tiempo", 0) and (ahora - j["tiempo"]) > 900
        ]
        for jid in viejos:
            del _reversion_jobs[jid]

        activo = _reversion_job_activo["job_id"]
        if activo and activo in _reversion_jobs:
            if not _reversion_jobs[activo].get("completado", False):
                return {
                    "job_id": activo,
                    "ya_en_progreso": True,
                    "mensaje": "Ya hay un escaneo en curso",
                }

        job_id = str(uuid.uuid4())
        _reversion_jobs[job_id] = {
            "progreso": 0,
            "total": 0,
            "mensaje": "Iniciando...",
            "completado": False,
            "resultado": None,
            "tiempo": time.time(),
        }
        _reversion_job_activo["job_id"] = job_id

    thread = threading.Thread(
        target=_run_reversion,
        args=(job_id, max_tickers, top_n),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "ya_en_progreso": False}


@app.get("/api/reversion/status/{job_id}")
def reversion_status(job_id: str):
    """Consulta el estado de un job de reversion."""
    with _reversion_lock:
        if job_id not in _reversion_jobs:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        return dict(_reversion_jobs[job_id])


# =====================================================
# SCANNER FULL (universo 1786 tickers)
# =====================================================

@app.get("/api/scanner/full")
def get_scanner_full():
    """Devuelve el ultimo escaneo del universo completo."""
    if not SCANNER_FULL_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="El scanner full no ha ejecutado todavia"
        )
    with open(SCANNER_FULL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
