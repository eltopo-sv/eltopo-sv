// ELTOPO - Frontend JS

// URL base del API
const API_BASE_URL = window.location.hostname === "localhost"
    ? ""
    : "";

// -- Tema claro/oscuro --
const themeToggle = document.getElementById("themeToggle");
const root = document.documentElement;

const savedTheme = localStorage.getItem("eltopo-theme");
if (savedTheme) {
    root.setAttribute("data-theme", savedTheme);
    themeToggle.textContent = savedTheme === "dark" ? "\u2600\uFE0F" : "\uD83C\uDF19";
} else {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initial = prefersDark ? "dark" : "light";
    root.setAttribute("data-theme", initial);
    themeToggle.textContent = initial === "dark" ? "\u2600\uFE0F" : "\uD83C\uDF19";
}

themeToggle.addEventListener("click", () => {
    const current = root.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("eltopo-theme", next);
    themeToggle.textContent = next === "dark" ? "\u2600\uFE0F" : "\uD83C\uDF19";
});

// -- Modulo activo: "tendencia" | "reversion" | null --
let moduloActual = null;
const MODO_BACKEND = "auto";

const modeBtns = document.querySelectorAll(".mode-btn");
const viewTendencia = document.getElementById("viewTendencia");
const viewReversion = document.getElementById("viewReversion");
const welcomeEl = document.getElementById("welcome");
const resultadoEl = document.getElementById("resultado");

function ocultarModulos() {
    if (viewTendencia) viewTendencia.style.display = "none";
    if (viewReversion) viewReversion.style.display = "none";
}

function mostrarModulo(nombre) {
    ocultarModulos();
    if (welcomeEl) welcomeEl.classList.add("oculto");
    if (resultadoEl) resultadoEl.innerHTML = "";

    if (nombre === "tendencia") {
        if (viewTendencia) viewTendencia.style.display = "block";
        cargarScanner();
    } else if (nombre === "reversion") {
        if (viewReversion) viewReversion.style.display = "block";
        mostrarReversion();
    }
}

modeBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        modeBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        moduloActual = btn.dataset.mode;
        mostrarModulo(moduloActual);
    });
});

// -- Buscador con autocompletado e historial --
const btnEscarbar = document.getElementById("btnEscarbar");
const tickerInput = document.getElementById("tickerInput");

const dropdown = document.createElement("div");
dropdown.className = "autocomplete-dropdown";
dropdown.style.display = "none";
document.querySelector(".search-wrap").appendChild(dropdown);

const HISTORIAL_KEY = "eltopo-historial";
let historial = JSON.parse(localStorage.getItem(HISTORIAL_KEY) || "[]");

function guardarHistorial(ticker) {
    historial = historial.filter(t => t !== ticker);
    historial.unshift(ticker);
    if (historial.length > 8) historial = historial.slice(0, 8);
    localStorage.setItem(HISTORIAL_KEY, JSON.stringify(historial));
}

function mostrarHistorial() {
    if (historial.length === 0) {
        dropdown.style.display = "none";
        return;
    }
    let html = '<div class="autocomplete-titulo">Busquedas recientes</div>';
    for (const t of historial) {
        html += '<div class="autocomplete-item" data-ticker="' + t + '"><span class="ac-symbol">' + t + '</span></div>';
    }
    dropdown.innerHTML = html;
    dropdown.style.display = "block";
    bindSugerencias();
}

function bindSugerencias() {
    dropdown.querySelectorAll(".autocomplete-item").forEach(item => {
        item.addEventListener("click", () => {
            const ticker = item.dataset.ticker;
            tickerInput.value = ticker;
            dropdown.style.display = "none";
            guardarHistorial(ticker);
            analizar(ticker);
        });
    });
}

let timeoutBuscar = null;
tickerInput.addEventListener("input", () => {
    const q = tickerInput.value.trim();
    if (timeoutBuscar) clearTimeout(timeoutBuscar);

    if (q.length < 1) {
        mostrarHistorial();
        return;
    }

    timeoutBuscar = setTimeout(async () => {
        try {
            const res = await fetch(API_BASE_URL + "/api/buscar?q=" + encodeURIComponent(q));
            const data = await res.json();
            const resultados = data.resultados || [];

            if (resultados.length === 0) {
                dropdown.style.display = "none";
                return;
            }

            let html = "";
            for (const r of resultados) {
                html += '<div class="autocomplete-item" data-ticker="' + r.symbol + '"><span class="ac-symbol">' + r.symbol + '</span><span class="ac-nombre">' + r.nombre + '</span></div>';
            }
            dropdown.innerHTML = html;
            dropdown.style.display = "block";
            bindSugerencias();
        } catch (e) {
            dropdown.style.display = "none";
        }
    }, 200);
});

document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-wrap")) {
        dropdown.style.display = "none";
    }
});

tickerInput.addEventListener("focus", () => {
    if (tickerInput.value.trim().length === 0) {
        mostrarHistorial();
    }
});

btnEscarbar.addEventListener("click", () => {
    const ticker = tickerInput.value.trim().toUpperCase();
    if (ticker) {
        guardarHistorial(ticker);
        dropdown.style.display = "none";
        analizar(ticker);
    }
});

tickerInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
        const ticker = tickerInput.value.trim().toUpperCase();
        if (ticker) {
            guardarHistorial(ticker);
            dropdown.style.display = "none";
            analizar(ticker);
        }
    }
});

async function analizar(ticker) {
    const loading = document.getElementById("loading");
    const resultado = document.getElementById("resultado");
    loading.style.display = "block";
    resultado.innerHTML = "";

    ocultarModulos();
    if (welcomeEl) welcomeEl.classList.add("oculto");

    try {
        const res = await fetch(API_BASE_URL + "/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker: ticker, modo: MODO_BACKEND })
        });
        if (!res.ok) throw new Error("Error " + res.status);
        const data = await res.json();
        renderizar(data);
    } catch (error) {
        resultado.innerHTML = '<div class="card"><p>Error: ' + error.message + '</p></div>';
    } finally {
        loading.style.display = "none";
    }
}

const CLASE_COLOR = {
    "verde_fuerte": "color-verde-fuerte",
    "verde": "color-verde",
    "amarillo": "color-amarillo",
    "gris": "color-gris",
    "naranja": "color-naranja",
    "rojo": "color-rojo"
};

const CLASE_DOT = {
    "verde_fuerte": "dot-verde-fuerte",
    "verde": "dot-verde",
    "amarillo": "dot-amarillo",
    "gris": "dot-gris",
    "naranja": "dot-naranja",
    "rojo": "dot-rojo"
};

function fmtPct(v) {
    if (v === null || v === undefined) return "-";
    let pct = v;
    if (Math.abs(v) < 1) {
        pct = v * 100;
    } else if (Math.abs(v) > 500) {
        pct = v / 100;
    }
    return pct.toFixed(2) + "%";
}

function fmtNum(v, dec) {
    if (v === null || v === undefined) return "-";
    if (typeof v !== "number") return String(v);
    return v.toFixed(dec || 2);
}

function fmtBig(v) {
    if (v === null || v === undefined) return "-";
    if (v >= 1e12) return (v / 1e12).toFixed(2) + "T";
    if (v >= 1e9) return (v / 1e9).toFixed(2) + "B";
    if (v >= 1e6) return (v / 1e6).toFixed(2) + "M";
    return v.toString();
}

function renderizar(data) {
    const resultado = document.getElementById("resultado");
    resultado.innerHTML = "";

    const rec = data.recomendacion_final;
    const ganador = rec && rec.mejor_estrategia ? rec.mejor_estrategia : null;

    const header = document.createElement("div");
    header.className = "card card-header-ticker";
    header.innerHTML = '<h2>' + data.ticker + '</h2><p class="fecha">' + data.fecha + ' ' + data.hora + '</p>';
    resultado.appendChild(header);

    if (rec && rec.mejor_estrategia) {
        const cardRec = document.createElement("div");
        cardRec.className = "card recomendacion color-" + rec.color;
        cardRec.innerHTML = '<h2>RECOMENDACION FINAL</h2><div class="estrategia">' + rec.mejor_estrategia.replace("_", " ").toUpperCase() + '</div><div class="confianza">Score: ' + rec.score + ' | Confianza: ' + rec.confianza + '%</div><div class="card-etiqueta etiqueta-' + rec.color + '">' + rec.mensaje + '</div>';
        resultado.appendChild(cardRec);
    }

    const estilosOrden = ["swing", "day_trading", "scalping"];
    const semaforo = document.createElement("div");
    semaforo.className = "card";
    let htmlSemaforo = '<h2>SEMAFORO OPERATIVO</h2><div class="semaforo-lista">';

    for (const nombre of estilosOrden) {
        const estilo = data.estilos[nombre];
        if (!estilo) continue;
        const nombreBonito = nombre.replace("_", " ").toUpperCase();

        if (!estilo.valido) {
            htmlSemaforo += '<div class="semaforo-item semaforo-error"><span class="semaforo-nombre"><span class="dot dot-gris"></span>' + nombreBonito + '</span><span class="semaforo-score">--</span><span class="semaforo-etiqueta">No valido</span></div>';
        } else {
            const dotClase = CLASE_DOT[estilo.color] || "dot-gris";
            const esGanador = (nombre === ganador);
            htmlSemaforo += '<div class="semaforo-item' + (esGanador ? ' semaforo-ganador' : '') + '"><span class="semaforo-nombre"><span class="dot ' + dotClase + '"></span>' + nombreBonito + (esGanador ? ' <span class="star">' + String.fromCharCode(9733) + '</span>' : '') + '</span><span class="semaforo-score">' + estilo.score + '</span><span class="semaforo-etiqueta etiqueta-' + estilo.color + '">' + estilo.etiqueta + '</span></div>';
        }
    }
    htmlSemaforo += '</div>';
    semaforo.innerHTML = htmlSemaforo;
    resultado.appendChild(semaforo);

    for (const nombre of estilosOrden) {
        const estilo = data.estilos[nombre];
        if (!estilo) continue;
        const esGanador = (nombre === ganador);
        const card = document.createElement("div");
        card.className = "card card-estilo";
        if (estilo.valido) card.classList.add(CLASE_COLOR[estilo.color] || "color-gris");
        if (esGanador) card.classList.add("card-ganador");

        if (!estilo.valido) {
            card.innerHTML = '<h2>' + nombre.replace("_", " ").toUpperCase() + '</h2><p class="fecha">' + (estilo.error || "No valido") + '</p>';
        } else {
            const op = estilo.operativa || {};
            card.innerHTML = '<h2>' + nombre.replace("_", " ").toUpperCase() + (esGanador ? ' <span class="star">' + String.fromCharCode(9733) + '</span>' : '') + '</h2><div class="card-score"><span class="numero-grande">' + estilo.score + '</span><span class="numero-pequeno">/ 10</span><span class="card-etiqueta etiqueta-' + estilo.color + '">' + estilo.etiqueta + '</span></div><div class="card-operativa"><div class="op-item"><span class="label">Entrada:</span><span class="valor-grande">' + op.entrada + '</span></div><div class="op-item"><span class="label">Objetivo:</span><span class="valor-grande">' + op.objetivo + '</span></div><div class="op-item"><span class="label">Stop:</span><span class="valor-grande">' + op.stop + '</span></div><div class="op-item"><span class="label">R:R:</span><span class="valor-grande">1:' + op.rr + '</span></div><div class="op-item"><span class="label">Horizonte:</span><span class="valor">' + op.horizonte + '</span></div><div class="op-item"><span class="label">Riesgo:</span><span class="valor">' + op.riesgo_pct + '%</span></div></div>';
        }
        resultado.appendChild(card);
    }

    const estiloGanador = ganador ? data.estilos[ganador] : null;
    if (estiloGanador && estiloGanador.valido && estiloGanador.indicadores) {
        const ind = estiloGanador.indicadores;
        const cardT = document.createElement("div");
        cardT.className = "card card-info color-gris";
        let htmlTec = '<h2>TECNICO DETALLE (' + ganador.replace("_", " ").toUpperCase() + ')</h2><div class="info-grid">';

        const campos = [
            ["Precio", ind.precio],
            ["MM200", ind.mm200],
            ["MM50", ind.mm50],
            ["RSI", ind.rsi],
            ["MACD", ind.macd],
            ["ATR", ind.atr],
            ["ADX", ind.adx],
            ["Estocastico K", ind.stoch_k],
            ["VWAP", ind.vwap],
            ["Vol Relativo", ind.vol_relativo],
            ["Fuerza Rel SPY", ind.fuerza_relativa],
            ["POC", ind.poc]
        ];
        for (const [label, valor] of campos) {
            if (valor !== null && valor !== undefined) {
                htmlTec += '<div class="op-item"><span class="label">' + label + ':</span><span class="valor">' + valor.toFixed(2) + '</span></div>';
            }
        }
        htmlTec += '</div>';

        if (ind.pivotes) {
            const p = ind.pivotes;
            htmlTec += '<div class="pivotes-wrap"><h3 style="font-size:12px; color: var(--text-muted); margin: 12px 0 6px;">PIVOTES DIARIOS</h3><div class="info-grid">';
            htmlTec += '<div class="op-item"><span class="label">R2:</span><span class="valor">' + (p.r2 || "-") + '</span></div>';
            htmlTec += '<div class="op-item"><span class="label">R1:</span><span class="valor">' + (p.r1 || "-") + '</span></div>';
            htmlTec += '<div class="op-item"><span class="label">Pivot:</span><span class="valor">' + (p.pivot || "-") + '</span></div>';
            htmlTec += '<div class="op-item"><span class="label">S1:</span><span class="valor">' + (p.s1 || "-") + '</span></div>';
            htmlTec += '<div class="op-item"><span class="label">S2:</span><span class="valor">' + (p.s2 || "-") + '</span></div>';
            htmlTec += '</div></div>';
        }
        cardT.innerHTML = htmlTec;
        resultado.appendChild(cardT);
    }

    if (data.fundamental && data.fundamental.nombre) {
        const f = data.fundamental;
        const cardF = document.createElement("div");
        cardF.className = "card card-info color-azul";
        cardF.innerHTML = '<h2>FUNDAMENTAL</h2><div class="info-grid">' +
            '<div class="op-item"><span class="label">Empresa:</span><span class="valor">' + (f.nombre || "-") + '</span></div>' +
            '<div class="op-item"><span class="label">Sector:</span><span class="valor">' + (f.sector || "-") + '</span></div>' +
            '<div class="op-item"><span class="label">Ingresos YoY:</span><span class="valor">' + fmtPct(f.ingresos_yoy) + '</span></div>' +
            '<div class="op-item"><span class="label">Beneficios YoY:</span><span class="valor">' + fmtPct(f.beneficios_yoy) + '</span></div>' +
            '<div class="op-item"><span class="label">Margen neto:</span><span class="valor">' + fmtPct(f.margen_neto) + '</span></div>' +
            '<div class="op-item"><span class="label">PER:</span><span class="valor">' + fmtNum(f.per) + '</span></div>' +
            '<div class="op-item"><span class="label">P/S:</span><span class="valor">' + fmtNum(f.ps) + '</span></div>' +
            '<div class="op-item"><span class="label">P/B:</span><span class="valor">' + fmtNum(f.pb) + '</span></div>' +
            '<div class="op-item"><span class="label">ROE:</span><span class="valor">' + fmtPct(f.roe) + '</span></div>' +
            '<div class="op-item"><span class="label">Deuda/Equity:</span><span class="valor">' + fmtNum(f.deuda_equity) + '</span></div>' +
            '<div class="op-item"><span class="label">Dividendo:</span><span class="valor">' + (f.dividend_yield ? f.dividend_yield.toFixed(2) + "%" : "-") + '</span></div>' +
            '<div class="op-item"><span class="label">Market Cap:</span><span class="valor">' + fmtBig(f.market_cap) + '</span></div>' +
            '</div>';
        resultado.appendChild(cardF);
    }

    const s = data.sentimiento || {};
    const cardS = document.createElement("div");
    cardS.className = "card card-info color-violeta";
    let htmlSent = '<h2>SENTIMIENTO</h2><div class="info-grid">';
    if (s.recomendacion_analistas) {
        const r = s.recomendacion_analistas;
        const positivos = (r.strong_buy || 0) + (r.buy || 0);
        const negativos = (r.sell || 0) + (r.strong_sell || 0);
        const total = positivos + (r.hold || 0) + negativos;
        htmlSent += '<div class="op-item"><span class="label">Analistas:</span><span class="valor">' + positivos + ' Buy / ' + (r.hold || 0) + ' Hold / ' + negativos + ' Sell</span></div>';
        htmlSent += '<div class="op-item"><span class="label">Total analistas:</span><span class="valor">' + total + '</span></div>';
        htmlSent += '<div class="op-item"><span class="label">Periodo:</span><span class="valor">' + (r.periodo || "-") + '</span></div>';
    }
    if (s.insider_compras !== null || s.insider_ventas !== null) {
        htmlSent += '<div class="op-item"><span class="label">Insider 90d:</span><span class="valor">' + (s.insider_compras || 0) + ' compras / ' + (s.insider_ventas || 0) + ' ventas</span></div>';
    }
    if (!s.recomendacion_analistas && s.insider_compras === null) {
        htmlSent += '<div class="op-item"><span class="label">Estado:</span><span class="valor">' + (s.nota || "Sin datos") + '</span></div>';
    }
    htmlSent += '</div>';
    cardS.innerHTML = htmlSent;
    resultado.appendChild(cardS);

    const c = data.catalizadores || {};
    const cardC = document.createElement("div");
    cardC.className = "card card-info color-rosa";
    let htmlCat = '<h2>CATALIZADORES</h2><div class="info-grid">';
    if (c.proximos_earnings) {
        htmlCat += '<div class="op-item"><span class="label">Proximos earnings:</span><span class="valor">' + c.proximos_earnings + '</span></div>';
        if (c.dias_hasta_earnings !== null && c.dias_hasta_earnings !== undefined) {
            htmlCat += '<div class="op-item"><span class="label">Dias hasta:</span><span class="valor">' + c.dias_hasta_earnings + '</span></div>';
        }
    } else {
        htmlCat += '<div class="op-item"><span class="label">Proximos earnings:</span><span class="valor">Sin fecha</span></div>';
    }
    if (c.historial_earnings && c.historial_earnings.length > 0) {
        const historialE = c.historial_earnings;
        const beats = historialE.filter(h => (h.sorpresa_pct || 0) > 0).length;
        const misses = historialE.length - beats;
        htmlCat += '<div class="op-item"><span class="label">Historial:</span><span class="valor">' + beats + ' beats / ' + misses + ' miss</span></div>';
        const ultimo = historialE[0];
        if (ultimo) {
            const sorp = ultimo.sorpresa_pct || 0;
            const emoji = sorp > 0 ? "OK" : "MISS";
            htmlCat += '<div class="op-item"><span class="label">Ultimo resultado:</span><span class="valor">' + sorp.toFixed(2) + '% (' + emoji + ')</span></div>';
        }
    }
    if (!c.proximos_earnings && (!c.historial_earnings || c.historial_earnings.length === 0)) {
        htmlCat += '<div class="op-item"><span class="label">Estado:</span><span class="valor">' + (c.nota || "Sin datos") + '</span></div>';
    }
    htmlCat += '</div>';
    cardC.innerHTML = htmlCat;
    resultado.appendChild(cardC);

    if (estiloGanador && estiloGanador.valido) {
        const precios = estiloGanador.indicadores ? estiloGanador.indicadores.precios_historicos : null;
        if (precios && precios.length > 0) {
            dibujarGrafico(precios, data.ticker);
        }
    }
}

function dibujarGrafico(precios, ticker) {
    const viejo = document.getElementById("chartContainer");
    if (viejo) viejo.remove();
    if (!precios || precios.length === 0) return;

    const card = document.createElement("div");
    card.className = "card card-info color-azul";
    card.id = "chartContainer";
    card.innerHTML = '<h2>GRAFICO DE PRECIO (ultimos ' + precios.length + ' dias)</h2><canvas id="precioChart" height="120"></canvas>';

    const resultado = document.getElementById("resultado");
    const header = resultado.querySelector(".card-header-ticker");
    if (header && header.nextSibling) {
        resultado.insertBefore(card, header.nextSibling);
    } else {
        resultado.appendChild(card);
    }

    const ctx = document.getElementById("precioChart").getContext("2d");
    new Chart(ctx, {
        type: "line",
        data: {
            labels: precios.map((_, i) => i + 1),
            datasets: [{
                label: ticker,
                data: precios,
                borderColor: "#2563EB",
                backgroundColor: "rgba(37, 99, 235, 0.1)",
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: false },
                y: { ticks: { color: "#6B7280" }, grid: { color: "rgba(0,0,0,0.05)" } }
            }
        }
    });
}

async function cargarScanner() {
    const longDiv = document.getElementById("scannerLong");
    const shortDiv = document.getElementById("scannerShort");
    const meta = document.getElementById("scannerMeta");

    if (!longDiv || !shortDiv) return;

    longDiv.innerHTML = '<div class="scanner-loading">Cargando...</div>';
    shortDiv.innerHTML = '<div class="scanner-loading">Cargando...</div>';
    if (meta) meta.textContent = "Cargando...";

    try {
        const res = await fetch(API_BASE_URL + "/api/scanner");
        const data = await res.json();

        if (data.error) {
            if (meta) meta.textContent = data.hint || data.error;
            longDiv.innerHTML = '<div class="scanner-loading">No hay datos. Ejecuta el scanner.</div>';
            shortDiv.innerHTML = '<div class="scanner-loading">No hay datos. Ejecuta el scanner.</div>';
            return;
        }

        if (meta) {
            meta.textContent =
                "Ultima actualizacion: " + (data.fecha || "N/A") +
                " - " + (data.total_analizados || 0) + " tickers - " +
                (data.tiempo_segundos || "?") + "s";
        }

        renderScannerList(longDiv, data.top_long || [], "long");
        renderScannerList(shortDiv, data.top_short || [], "short");

    } catch (e) {
        console.error("Error cargando scanner:", e);
        if (meta) meta.textContent = "Error de conexion";
        longDiv.innerHTML = '<div class="scanner-loading">Error de conexion</div>';
        shortDiv.innerHTML = '<div class="scanner-loading">Error de conexion</div>';
    }
}

function renderScannerList(container, lista, tipo) {
    if (!lista.length) {
        container.innerHTML = '<div class="scanner-loading">Sin resultados</div>';
        return;
    }

    const scoreKey = tipo === "long" ? "score_long" : "score_short";
    const rowClass = tipo === "long" ? "scanner-row-long" : "scanner-row-short";

    container.innerHTML = lista.map((t, i) => {
        const score = t[scoreKey] != null ? Number(t[scoreKey]).toFixed(2) : "-";
        const precio = t.precio != null ? "$" + Number(t.precio).toFixed(2) : "-";
        return `
            <div class="scanner-row ${rowClass}" data-ticker="${t.ticker}">
                <span class="scanner-rank">${i + 1}</span>
                <span class="scanner-ticker">${t.ticker}</span>
                <span class="scanner-score">${score}</span>
                <span class="scanner-precio">${precio}</span>
            </div>
        `;
    }).join("");

    container.querySelectorAll(".scanner-row").forEach(row => {
        row.addEventListener("click", () => {
            const ticker = row.dataset.ticker;
            tickerInput.value = ticker;
            guardarHistorial(ticker);
            analizar(ticker);
        });
    });
}

const btnRefresh = document.getElementById("btnRefreshScanner");
if (btnRefresh) {
    btnRefresh.addEventListener("click", async () => {
        const original = btnRefresh.innerHTML;
        btnRefresh.innerHTML = "&#9203; Ejecutando...";
        btnRefresh.disabled = true;

        try {
            await fetch(API_BASE_URL + "/api/scanner/refresh", { method: "POST" });
            await cargarScanner();
        } catch (e) {
            console.error("Error refrescando:", e);
            alert("Error al actualizar el scanner. Mira la consola.");
        } finally {
            btnRefresh.innerHTML = original;
            btnRefresh.disabled = false;
        }
    });
}

/* ====================================================== */
/* REVERSION - Escaneo on-demand con progreso             */
/* ====================================================== */

const REVERSION_CACHE_KEY = "eltopo-reversion-cache";
const REVERSION_CACHE_TTL = 15 * 60 * 1000; // 15 minutos en ms

let reversionPollInterval = null;
let reversionJobActual = null;

function mostrarReversion() {
    const viewRev = document.getElementById("viewReversion");
    if (!viewRev) return;

    // Buscar contenedores (los creamos dinamicamente si no existen)
    let contenedor = document.getElementById("reversionContenido");
    if (!contenedor) {
        contenedor = document.createElement("div");
        contenedor.id = "reversionContenido";
        viewRev.appendChild(contenedor);
    }

    // Comprobar cache
    const cache = localStorage.getItem(REVERSION_CACHE_KEY);
    if (cache) {
        try {
            const data = JSON.parse(cache);
            const edad = Date.now() - (data.timestamp || 0);
            if (edad < REVERSION_CACHE_TTL) {
                renderReversion(data.resultado);
                return;
            }
        } catch (e) {}
    }

    // No hay cache valida -> arrancar escaneo
    arrancarReversion();
}

async function arrancarReversion() {
    const contenedor = document.getElementById("reversionContenido");
    if (!contenedor) return;

    // Mostrar spinner + barra
    contenedor.innerHTML = `
        <div class="reversion-progress">
            <div class="spinner"></div>
            <p id="reversionMsg">Iniciando escaneo...</p>
            <div class="progress-bar">
                <div class="progress-fill" id="reversionProgress" style="width: 0%"></div>
            </div>
            <p class="progress-pct" id="reversionPct">0%</p>
        </div>
    `;

    try {
        const res = await fetch(API_BASE_URL + "/api/reversion/start?max_tickers=500&top_n=15", { method: "POST" });
        const data = await res.json();

        if (data.error) {
            contenedor.innerHTML = '<p class="error">Error: ' + data.error + '</p>';
            return;
        }

        reversionJobActual = data.job_id;

        if (data.ya_en_progreso) {
            console.log("Reutilizando job activo:", data.job_id);
        }

        // Empezar polling
        if (reversionPollInterval) clearInterval(reversionPollInterval);
        reversionPollInterval = setInterval(() => pollReversion(data.job_id), 3000);

        // Primera consulta inmediata
        pollReversion(data.job_id);

    } catch (e) {
        contenedor.innerHTML = '<p class="error">Error de conexion: ' + e.message + '</p>';
    }
}

async function pollReversion(jobId) {
    try {
        const res = await fetch(API_BASE_URL + "/api/reversion/status/" + jobId);
        if (!res.ok) return;
        const status = await res.json();

        actualizarProgreso(status);

        if (status.completado) {
            if (reversionPollInterval) {
                clearInterval(reversionPollInterval);
                reversionPollInterval = null;
            }

            if (status.error) {
                const contenedor = document.getElementById("reversionContenido");
                contenedor.innerHTML = '<p class="error">Error: ' + status.error + '</p>';
                return;
            }

            // Guardar en cache
            const cacheData = {
                timestamp: Date.now(),
                resultado: status.resultado,
            };
            localStorage.setItem(REVERSION_CACHE_KEY, JSON.stringify(cacheData));

            renderReversion(status.resultado);
        }
    } catch (e) {
        console.error("Error en polling:", e);
    }
}

function actualizarProgreso(status) {
    const msg = document.getElementById("reversionMsg");
    const bar = document.getElementById("reversionProgress");
    const pct = document.getElementById("reversionPct");

    if (msg) msg.textContent = status.mensaje || "Analizando...";

    if (status.total > 0) {
        const porcentaje = Math.round((status.progreso / status.total) * 100);
        if (bar) bar.style.width = porcentaje + "%";
        if (pct) pct.textContent = porcentaje + "%";
    }
}

function renderReversion(resultado) {
    const contenedor = document.getElementById("reversionContenido");
    if (!contenedor) return;

    if (!resultado || !resultado.top_reversion || resultado.top_reversion.length === 0) {
        contenedor.innerHTML = '<p class="scanner-loading">Sin resultados con score suficiente.</p>';
        return;
    }

    let html = `
        <div class="scanner-header">
            <div class="scanner-titulo-wrap">
                <h2 class="scanner-titulo">Reversion</h2>
                <p class="scanner-subtitulo">
                    ${resultado.total_analizados} tickers analizados en ${resultado.tiempo_segundos}s
                    &middot; ${resultado.fecha}
                </p>
            </div>
            <button class="btn-refresh" id="btnRefreshReversion">&#128260; Actualizar</button>
        </div>
        <div class="reversion-list">
    `;

    for (let i = 0; i < resultado.top_reversion.length; i++) {
        const t = resultado.top_reversion[i];
        const categoriaClass = t.categoria === "REBOTE" ? "cat-rebote" : "cat-cambio";
        const estadoInfo = formatearEstado(t.estado);

        // Linea de stop/objetivo/RB (solo si hay datos)
        let lineaRB = "";
        if (t.stop || t.objetivo || t.rb) {
            lineaRB = '<div class="reversion-linea-rb">';
            if (t.stop) lineaRB += `Stop: <strong>$${Number(t.stop).toFixed(2)}</strong>`;
            if (t.objetivo) lineaRB += ` &middot; Objetivo: <strong>$${Number(t.objetivo).toFixed(2)}</strong>`;
            if (t.rb) lineaRB += ` &middot; R:B <strong>1:${Number(t.rb).toFixed(2)}</strong>`;
            lineaRB += '</div>';
        }

        // Linea de estado (solo si no es DEBIL)
        let lineaEstado = "";
        if (estadoInfo) {
            lineaEstado = `<div class="reversion-linea-estado ${estadoInfo.clase}">${estadoInfo.icono} ${estadoInfo.texto}</div>`;
        }

        html += `
            <div class="reversion-row" data-ticker="${t.ticker}">
                <span class="reversion-rank">${i + 1}</span>
                <div class="reversion-info">
                    <div class="reversion-linea-1">
                        <span class="reversion-ticker">${t.ticker}</span>
                        <span class="reversion-categoria ${categoriaClass}">${t.categoria}</span>
                        <span class="reversion-precio">${t.precio != null ? "$" + Number(t.precio).toFixed(2) : ""}</span>
                        <span class="reversion-score">${Number(t.score_reversion).toFixed(2)}</span>
                    </div>
                    <div class="reversion-linea-2">
                        Rebote: <strong>${Number(t.score_rebote).toFixed(2)}</strong>
                        &nbsp;&middot;&nbsp;
                        Cambio: <strong>${Number(t.score_cambio).toFixed(2)}</strong>
                    </div>
                    <div class="reversion-linea-3">${t.texto}</div>
                    ${lineaRB}
                    ${lineaEstado}
                </div>
            </div>
        `;
    }

    html += '</div>';
    contenedor.innerHTML = html;

    // Click en fila -> analizar ticker
    contenedor.querySelectorAll(".reversion-row").forEach(row => {
        row.addEventListener("click", () => {
            const ticker = row.dataset.ticker;
            tickerInput.value = ticker;
            guardarHistorial(ticker);
            analizar(ticker);
        });
    });

    // Boton refrescar
    const btnRef = document.getElementById("btnRefreshReversion");
    if (btnRef) {
        btnRef.addEventListener("click", () => {
            localStorage.removeItem(REVERSION_CACHE_KEY);
            arrancarReversion();
        });
    }
}

function formatearEstado(estado) {
    if (!estado || estado === "DEBIL") return null;
    if (estado === "TENDENCIA_CONSOLIDADA") {
        return { icono: "\uD83D\uDD35", texto: "Tendencia alcista consolidada", clase: "estado-consolidada" };
    }
    if (estado === "CAMBIO_CONFIRMADO") {
        return { icono: "\uD83D\uDFE2", texto: "Cambio de tendencia confirmado", clase: "estado-confirmado" };
    }
    if (estado === "GIRO_TEMPRANO") {
        return { icono: "\uD83D\uDFE1", texto: "Giro temprano (sin confirmar)", clase: "estado-temprano" };
    }
    return null;
}
