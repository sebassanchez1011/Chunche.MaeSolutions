from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .system import ChuncheSystem


class SessionCreate(BaseModel):
    work_id: str = "obra-demo"
    operator: str = "operador"
    notes: str = ""


class ServoMove(BaseModel):
    name: str
    angle: float


class ConfirmAction(BaseModel):
    detection_id: int


class CalibrationPointIn(BaseModel):
    image_x: float
    image_y: float
    label: str = ""


INDEX_HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chunche Control</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f7f4;
      --panel: #ffffff;
      --ink: #1f2933;
      --muted: #667085;
      --line: #d8ddd7;
      --accent: #2563eb;
      --danger: #c2410c;
      --ok: #15803d;
      --warn: #a16207;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
      position: sticky;
      top: 0;
      z-index: 2;
    }
    h1 { font-size: 22px; margin: 0; letter-spacing: 0; }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 360px) 1fr;
      gap: 16px;
      padding: 16px;
    }
    section, aside {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }
    h2 { font-size: 16px; margin: 0 0 12px; }
    label { display: block; font-size: 13px; color: var(--muted); margin: 8px 0 4px; }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      background: #fff;
      color: var(--ink);
    }
    textarea { min-height: 72px; resize: vertical; }
    button {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 9px 11px;
      font: inherit;
      cursor: pointer;
    }
    button.primary { background: var(--accent); color: white; border-color: var(--accent); }
    button.danger { background: var(--danger); color: white; border-color: var(--danger); }
    button.ok { background: var(--ok); color: white; border-color: var(--ok); }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .stack { display: grid; gap: 12px; }
    .viewer {
      min-height: 420px;
      display: grid;
      place-items: center;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #eceeea;
      overflow: hidden;
    }
    .viewer img { width: 100%; height: auto; display: block; }
    .muted { color: var(--muted); font-size: 13px; }
    .status { font-size: 13px; color: var(--muted); }
    .grid { display: grid; grid-template-columns: minmax(500px, 1.25fr) minmax(320px, 0.75fr); gap: 12px; }
    .servo { border-top: 1px solid var(--line); padding-top: 9px; }
    .servo label { display: flex; justify-content: space-between; gap: 8px; }
    input[type="range"] { padding: 0; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; table-layout: fixed; }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 8px 6px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
      word-break: normal;
    }
    th { color: var(--muted); font-weight: 600; }
    #detections th:nth-child(1), #detections td:nth-child(1) { width: 25%; }
    #detections th:nth-child(2), #detections td:nth-child(2) { width: 16%; }
    #detections th:nth-child(3), #detections td:nth-child(3) { width: 14%; }
    #detections th:nth-child(4), #detections td:nth-child(4) { width: 30%; }
    #detections th:nth-child(5), #detections td:nth-child(5) { width: 15%; }
    .tag { display: inline-block; padding: 2px 6px; border-radius: 999px; background: #eef2ff; color: #3730a3; }
    .warn { color: var(--warn); }
    .okText { color: var(--ok); }
    @media (max-width: 920px) {
      main { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Chunche Control</h1>
    <div class="row">
      <span id="mode" class="status">modo</span>
      <button class="danger" onclick="emergencyStop()">Parada</button>
      <button onclick="goHome()">Home</button>
    </div>
  </header>
  <main>
    <aside class="stack">
      <section>
        <h2>Sesion</h2>
        <label>Identificador de obra</label>
        <input id="workId" value="obra-demo">
        <label>Operador</label>
        <input id="operator" value="operador">
        <label>Notas</label>
        <textarea id="notes"></textarea>
        <div class="row" style="margin-top:10px">
          <button class="primary" onclick="createSession()">Nueva sesion</button>
          <span id="sessionLabel" class="status">Sin sesion</span>
        </div>
      </section>

      <section>
        <h2>Captura y analisis</h2>
        <div class="row">
          <button onclick="capture('initial')">Inicial</button>
          <button onclick="capture('final')">Final</button>
          <button class="primary" onclick="analyze()">Analizar</button>
        </div>
        <div class="row" style="margin-top:8px">
          <button class="ok" onclick="downloadReport()">Reporte PDF</button>
        </div>
        <p class="muted">Las acciones fisicas requieren confirmacion manual.</p>
      </section>

      <section>
        <h2>Calibracion</h2>
        <label>X imagen</label>
        <input id="calX" type="number" value="640">
        <label>Y imagen</label>
        <input id="calY" type="number" value="360">
        <label>Etiqueta</label>
        <input id="calLabel" value="punto">
        <button onclick="addCalibration()">Guardar punto actual</button>
        <p id="calStatus" class="muted"></p>
      </section>
    </aside>

    <section class="stack">
      <div class="viewer" id="viewer"><span class="muted">Crea una sesion y captura una imagen.</span></div>
      <div class="grid">
        <section>
          <h2>Detecciones</h2>
          <div id="detections" class="muted">Sin analisis.</div>
        </section>
        <section>
          <h2>Servos</h2>
          <div id="servoPanel"></div>
        </section>
      </div>
      <section>
        <h2>Registro</h2>
        <div id="log" class="muted"></div>
      </section>
    </section>
  </main>

  <script>
    let sessionId = null;
    let statusCache = null;

    function note(text, cls='') {
      const log = document.getElementById('log');
      const line = document.createElement('div');
      line.className = cls;
      line.textContent = new Date().toLocaleTimeString() + ' - ' + text;
      log.prepend(line);
    }

    async function api(path, options={}) {
      const response = await fetch(path, {
        headers: {'Content-Type': 'application/json'},
        ...options
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || response.statusText);
      }
      return response.json();
    }

    async function refreshStatus() {
      statusCache = await api('/api/status');
      document.getElementById('mode').textContent = 'Modo ' + statusCache.mode;
      renderServos(statusCache.servos);
      document.getElementById('calStatus').textContent = statusCache.calibration_points + ' punto(s) guardado(s)';
    }

    function renderServos(data) {
      const panel = document.getElementById('servoPanel');
      panel.innerHTML = '';
      for (const [name, servo] of Object.entries(data.servos)) {
        const value = Math.round(data.positions[name] ?? servo.home_angle);
        const wrap = document.createElement('div');
        wrap.className = 'servo';
        wrap.innerHTML = `
          <label><span>${servo.label}</span><strong id="val_${name}">${value}°</strong></label>
          <input type="range" min="${servo.min_angle}" max="${servo.max_angle}" value="${value}" data-servo="${name}">
        `;
        const input = wrap.querySelector('input');
        input.addEventListener('change', () => moveServo(name, Number(input.value)));
        input.addEventListener('input', () => document.getElementById('val_' + name).textContent = input.value + '°');
        panel.appendChild(wrap);
      }
    }

    async function createSession() {
      const data = await api('/api/sessions', {
        method: 'POST',
        body: JSON.stringify({
          work_id: document.getElementById('workId').value,
          operator: document.getElementById('operator').value,
          notes: document.getElementById('notes').value
        })
      });
      sessionId = data.id;
      document.getElementById('sessionLabel').textContent = 'Sesion #' + sessionId;
      note('Sesion creada para ' + data.work_id, 'okText');
    }

    async function ensureSession() {
      if (!sessionId) await createSession();
    }

    async function capture(kind) {
      await ensureSession();
      const data = await api(`/api/sessions/${sessionId}/capture`, {
        method: 'POST',
        body: JSON.stringify({kind})
      });
      showImage(data.media_url);
      note('Captura ' + kind + ' guardada.');
    }

    async function analyze() {
      await ensureSession();
      const data = await api(`/api/sessions/${sessionId}/analyze`, {method: 'POST'});
      showImage(data.annotated_media_url);
      renderDetections(data.detections);
      note(data.detections.length + ' deteccion(es) registradas.');
    }

    function renderDetections(detections) {
      const target = document.getElementById('detections');
      if (!detections.length) {
        target.innerHTML = '<span class="muted">No hay detecciones sobre el umbral.</span>';
        return;
      }
      const rows = detections.map(det => {
        const label = String(det.label).replaceAll('_', ' ');
        const action = String(det.action).replaceAll('_', ' ');
        const area = det.area_pixels ? Math.round(det.area_pixels).toLocaleString() + ' px' : '-';
        return `
        <tr>
          <td><span class="tag">${label}</span><br>${det.quadrant || ''}</td>
          <td>${Number(det.confidence).toFixed(2)}<br><span class="muted">${action}</span></td>
          <td>${area}</td>
          <td>${det.recommendation}</td>
          <td><button onclick="confirmAction(${det.id})">Validar</button></td>
        </tr>
      `}).join('');
      target.innerHTML = `<table><thead><tr><th>Tipo</th><th>Conf.</th><th>Area</th><th>Recomendacion</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
    }

    async function confirmAction(detectionId) {
      await ensureSession();
      const data = await api(`/api/sessions/${sessionId}/confirm-action`, {
        method: 'POST',
        body: JSON.stringify({detection_id: detectionId})
      });
      note(data.message, data.requires_human ? 'warn' : 'okText');
      await refreshStatus();
    }

    async function moveServo(name, angle) {
      const data = await api('/api/servos/move', {
        method: 'POST',
        body: JSON.stringify({name, angle})
      });
      note(data.message, data.ok ? 'okText' : 'warn');
      await refreshStatus();
    }

    async function goHome() {
      const data = await api('/api/servos/home', {method: 'POST'});
      note(data.message, data.ok ? 'okText' : 'warn');
      await refreshStatus();
    }

    async function emergencyStop() {
      const data = await api('/api/emergency-stop', {method: 'POST'});
      note(data.message, 'warn');
      await refreshStatus();
    }

    async function addCalibration() {
      const data = await api('/api/calibration/points', {
        method: 'POST',
        body: JSON.stringify({
          image_x: Number(document.getElementById('calX').value),
          image_y: Number(document.getElementById('calY').value),
          label: document.getElementById('calLabel').value
        })
      });
      note('Punto de calibracion guardado. Total: ' + data.count, 'okText');
      await refreshStatus();
    }

    async function downloadReport() {
      await ensureSession();
      const data = await api(`/api/sessions/${sessionId}/report`, {method: 'POST'});
      window.open(data.media_url, '_blank');
      note('Reporte generado.');
    }

    function showImage(url) {
      document.getElementById('viewer').innerHTML = `<img src="${url}?t=${Date.now()}" alt="Captura de la obra">`;
    }

    refreshStatus().catch(err => note(err.message, 'warn'));
  </script>
</body>
</html>"""


def create_app(system: ChuncheSystem):
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, HTMLResponse

    app = FastAPI(title="Chunche Control", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return system.status()

    @app.post("/api/sessions")
    def create_session(payload: SessionCreate) -> dict[str, Any]:
        return system.create_session(payload.work_id, payload.operator, payload.notes)

    @app.post("/api/sessions/{session_id}/capture")
    def capture(session_id: int, payload: dict[str, str]) -> dict[str, Any]:
        try:
            return system.capture(session_id, kind=payload.get("kind", "initial"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/analyze")
    def analyze(session_id: int) -> dict[str, Any]:
        try:
            return system.analyze(session_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/confirm-action")
    def confirm_action(session_id: int, payload: ConfirmAction) -> dict[str, Any]:
        try:
            return system.confirm_action(session_id, payload.detection_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/report")
    def report(session_id: int) -> dict[str, Any]:
        try:
            return system.generate_report(session_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/servos/move")
    def move_servo(payload: ServoMove) -> dict[str, Any]:
        result = system.servos.move_servo(payload.name, payload.angle, smooth=True)
        return {"ok": result.ok, "message": result.message, "pose": result.pose}

    @app.post("/api/servos/home")
    def home() -> dict[str, Any]:
        result = system.servos.go_home()
        return {"ok": result.ok, "message": result.message, "pose": result.pose}

    @app.post("/api/emergency-stop")
    def emergency_stop() -> dict[str, Any]:
        result = system.servos.emergency_stop()
        system.storage.log_action(0, "emergency_stop", {"message": result.message}) if False else None
        return {"ok": result.ok, "message": result.message}

    @app.get("/api/calibration")
    def calibration() -> dict[str, Any]:
        return system.calibration.as_dict()

    @app.post("/api/calibration/points")
    def add_calibration_point(payload: CalibrationPointIn) -> dict[str, Any]:
        return system.add_calibration_point(payload.image_x, payload.image_y, payload.label)

    @app.get("/media/{relative_path:path}")
    def media(relative_path: str):
        root = system.data_dir.resolve()
        path = (root / relative_path).resolve()
        if not str(path).startswith(str(root)) or not path.exists():
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        return FileResponse(path)

    return app
