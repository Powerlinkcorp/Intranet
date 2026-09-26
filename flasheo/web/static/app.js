// app.js — Controlador Frontend Reactivo con WebSockets para Estación de Flasheo
let currentUser = { username: 'admin', rol: 'admin', nombre_completo: 'Administrador Local' };
let sessionToken = localStorage.getItem('session_token') || '';
let ws = null;
let currentLotes = [];
let allOnusHistory = [];

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initPortsGrid();
  checkAuth();
  loadLotes();
  loadModels();
  loadFirmwares();
  loadOnusHistory();
  updateSyncStatusUI();
  connectWebSocket();
  setInterval(updateSyncStatusUI, 12000);
});

// ============================================================================
// GESTIÓN DE MODO CLARO / MODO OSCURO (HOMOLOGADO CON INTRANET)
// ============================================================================
function initTheme() {
  const savedTheme = localStorage.getItem('powerlink_theme') || 'light';
  applyTheme(savedTheme);
}

function toggleTheme() {
  const isDark = document.body.classList.contains('dark-mode');
  const newTheme = isDark ? 'light' : 'dark';
  applyTheme(newTheme);
}

function applyTheme(theme) {
  const icon = document.getElementById('themeIcon');
  const label = document.getElementById('themeLabel');
  if (theme === 'dark') {
    document.body.classList.add('dark-mode');
    document.documentElement.classList.add('dark-mode');
    if (icon) icon.className = 'fa-solid fa-sun';
    if (label) label.textContent = 'Modo Claro';
  } else {
    document.body.classList.remove('dark-mode');
    document.documentElement.classList.remove('dark-mode');
    if (icon) icon.className = 'fa-solid fa-moon';
    if (label) label.textContent = 'Modo Oscuro';
  }
  localStorage.setItem('powerlink_theme', theme);
}


// ============================================================================
// WEBSOCKET TELEMETRÍA EN VIVO
// ============================================================================
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/status`;
  const indicator = document.getElementById('wsIndicator');

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    indicator.textContent = '● En Vivo (WS)';
    indicator.className = 'badge-status connected';
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'telemetry') {
        updateTelemetry(data.status);
        updateTerminal(data.logs);
      }
    } catch (e) {}
  };

  ws.onclose = () => {
    indicator.textContent = '● Reconectando...';
    indicator.className = 'badge-status disconnected';
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => {
    ws.close();
  };
}

function updateTelemetry(data) {
  if (!data) return;
  
  // Contadores
  if (data.counts) {
    document.getElementById('cntListas').textContent = data.counts.listas || 0;
    document.getElementById('cntEnCurso').textContent = data.counts.en_curso || 0;
    document.getElementById('cntErrores').textContent = data.counts.errores || 0;
    document.getElementById('cntTotal').textContent = data.counts.total || 20;
  }

  // Estado del proceso y Banner en Vivo
  const isRunning = data.process && data.process.running;
  const btnStart = document.getElementById('btnStartAction');
  const btnReset = document.getElementById('btnActionReset');
  const btnAudit = document.getElementById('btnActionAudit');
  const btnStop = document.getElementById('btnStop');
  if (btnStart) btnStart.style.display = isRunning ? 'none' : 'inline-flex';
  if (btnReset) btnReset.style.display = isRunning ? 'none' : 'inline-flex';
  if (btnAudit) btnAudit.style.display = isRunning ? 'none' : 'inline-flex';
  if (btnStop) btnStop.style.display = isRunning ? 'inline-flex' : 'none';

  // Banner dinámico de estado en vivo del flasheo
  const liveBanner = document.getElementById('liveProcessBanner');
  const liveTitle = document.getElementById('liveStatusTitle');
  const liveMode = document.getElementById('liveMetaMode');
  const liveModel = document.getElementById('liveMetaModel');
  const liveList = document.getElementById('liveActiveList');
  const liveDot = document.getElementById('livePulseDot');

  const statusOnus = (data.status && data.status.onus) || [];
  const ACTIVE_STATES = ['FLASHEANDO', 'REINICIANDO', 'VERIFICANDO', 'ESTABILIZANDO', 'CONECTADO', 'LOGIN', 'WIZARD', 'ESPERANDO'];
  const activeOnus = statusOnus.filter(o => ACTIVE_STATES.includes(o.estado) && o.estado !== 'SIN_ONU');

  if (liveBanner) {
    if (isRunning || activeOnus.length > 0) {
      liveBanner.style.display = 'flex';
      const modeText = data.process && data.process.mode ? data.process.mode.toUpperCase() : (document.getElementById('flashModeSelect') ? document.getElementById('flashModeSelect').value.toUpperCase() : 'CONTINUO');
      const modelText = (data.process && data.process.model) || (document.getElementById('activeModelSelect') ? document.getElementById('activeModelSelect').value : 'V2801D-B');
      
      if (liveTitle) liveTitle.textContent = isRunning ? `Flasheo en Ejecución — Modo ${modeText}` : `Proceso Finalizado — Estado de Puertos`;
      if (liveMode) liveMode.textContent = `Modo: ${modeText}`;
      if (liveModel) liveModel.textContent = `Modelo: ${modelText}`;
      if (liveDot) liveDot.style.background = isRunning ? '#10b981' : '#f59e0b';

      if (liveList) {
        liveList.innerHTML = '';
        const listToRender = activeOnus.length > 0 ? activeOnus : statusOnus.filter(o => o.estado && o.estado !== 'SIN_ONU');
        if (listToRender.length === 0) {
          liveList.innerHTML = '<div style="font-size:12px; color:var(--texto-gris); padding:6px 0;">Esperando conexión de ONUs en los puertos...</div>';
        } else {
          listToRender.forEach(o => {
            const cardDiv = document.createElement('div');
            cardDiv.className = 'live-active-card';
            const pct = o.progreso != null ? Math.min(100, Math.max(0, o.progreso)) : (o.estado === 'FLASHEANDO' ? 45 : (o.estado === 'REINICIANDO' ? 70 : (o.estado === 'VERIFICANDO' ? 90 : (o.estado === 'EXITO' ? 100 : 20))));
            cardDiv.innerHTML = `
              <div class="live-card-top">
                <span class="live-port-tag">Puerto P${o.puerto} (${o.ip || '10.100.' + o.puerto + '.1'})</span>
                <span class="live-state-tag" style="${o.estado === 'EXITO' || o.estado === 'YA_CONFIGURADA' ? 'background:rgba(16,185,129,0.15);color:#10b981;' : (o.estado === 'ERROR' ? 'background:rgba(239,68,68,0.15);color:#ef4444;' : '')}">${o.icono || '⚡'} ${o.estado || 'EN PROCESO'}</span>
              </div>
              <div class="live-detail-text">${o.detalle || 'Procesando ONU...'}</div>
              <div class="live-progress-container">
                <div class="live-progress-bar">
                  <div class="live-progress-fill" style="width:${pct}%"></div>
                </div>
                <span class="live-progress-pct">${pct.toFixed(0)}%</span>
              </div>
              ${o.mac || o.pon ? `<div style="font-size:10px; font-family:monospace; color:var(--texto-gris); margin-top:2px;">MAC: ${o.mac || '-'} | PON: ${o.pon || '-'}</div>` : ''}
            `;
            liveList.appendChild(cardDiv);
          });
        }
      }
    } else {
      liveBanner.style.display = 'none';
    }
  }

  // Alerta dinámica de enlace en Modo Directo
  const alertEl = document.getElementById('directConnectionAlert');
  const flashMode = document.getElementById('flashModeSelect') ? document.getElementById('flashModeSelect').value : 'direct';
  if (alertEl) {
    if (flashMode === 'direct') {
      alertEl.style.display = 'block';
      if (data.onu_direct_online) {
        alertEl.style.background = 'rgba(16, 185, 129, 0.15)';
        alertEl.style.color = '#10b981';
        alertEl.style.border = '1px solid rgba(16, 185, 129, 0.3)';
        alertEl.innerHTML = '🟢 <b>ONU detectada en 192.168.1.1:</b> Enlace de red listo para flashear.';
      } else {
        alertEl.style.background = 'rgba(239, 68, 68, 0.15)';
        alertEl.style.color = '#f87171';
        alertEl.style.border = '1px solid rgba(239, 68, 68, 0.3)';
        alertEl.innerHTML = '⚠️ <b>Sin conexión con 192.168.1.1:</b> Ejecuta como Administrador el acceso directo <code>CONFIGURAR_IP_MODO_DIRECTO.bat</code> en el Escritorio (fijará IP 192.168.1.100 en Ethernet 3).';
      }
    } else {
      alertEl.style.display = 'none';
    }
  }

  // Puertos
  const mtkPorts = data.mikrotik_active_ports || {};
  const onuMap = {};
  statusOnus.forEach(o => { onuMap[String(o.puerto)] = o; });

  for (let p = 1; p <= 20; p++) {
    const card = document.getElementById(`portCard-${p}`);
    const dot = document.getElementById(`portDot-${p}`);
    const stateEl = document.getElementById(`portState-${p}`);
    const ipEl = document.getElementById(`portIp-${p}`);
    const macEl = document.getElementById(`portMac-${p}`);
    const detailEl = document.getElementById(`portDetail-${p}`);
    const progressWrap = document.getElementById(`portProgressWrap-${p}`);
    const progressFill = document.getElementById(`portProgressFill-${p}`);
    const progressPct = document.getElementById(`portProgressPct-${p}`);
    if (!card) continue;

    const hasLink = mtkPorts.hasOwnProperty(p);
    dot.className = hasLink ? 'port-link-dot active' : 'port-link-dot';
    dot.title = hasLink ? 'Link Ethernet activo' : 'Sin cable conectado';

    const info = onuMap[String(p)];
    if (info) {
      stateEl.textContent = `${info.icono || '⚡'} ${info.estado || 'ESPERANDO'}`;
      card.className = `port-card state-${info.estado || 'ESPERANDO'} ${hasLink ? 'has-link' : ''}`;
      if (info.ip) ipEl.textContent = info.ip;
      if (info.mac) macEl.textContent = info.mac;
      if (info.pon) macEl.textContent = info.pon;

      // Detalle del estado actual (actividad en curso)
      if (detailEl) {
        detailEl.textContent = info.detalle || '';
        detailEl.style.display = info.detalle ? 'block' : 'none';
      }

      // Barra de progreso (solo en FLASHEANDO con campo progreso)
      const showProgress = info.estado === 'FLASHEANDO' && info.progreso != null;
      if (progressWrap) progressWrap.style.display = showProgress ? 'flex' : 'none';
      if (showProgress && progressFill && progressPct) {
        const pct = Math.min(100, Math.max(0, info.progreso));
        progressFill.style.width = pct + '%';
        progressPct.textContent = pct.toFixed(0) + '%';
      }
    } else {
      stateEl.textContent = hasLink ? 'ENLACE OK' : 'LIBRE';
      card.className = `port-card ${hasLink ? 'has-link' : ''}`;
      if (detailEl) { detailEl.textContent = ''; detailEl.style.display = 'none'; }
      if (progressWrap) progressWrap.style.display = 'none';
    }
  }
}

function updateTerminal(logs) {
  if (!logs || !logs.length) return;
  const term = document.getElementById('terminalLogs');
  term.textContent = logs.join('\n');
  if (document.getElementById('autoScrollCheck').checked) {
    term.scrollTop = term.scrollHeight;
  }
}

// ============================================================================
// GENERACIÓN DE LA MATRIZ DE 20 PUERTOS
// ============================================================================
function initPortsGrid() {
  const grid = document.getElementById('portsGrid');
  grid.innerHTML = '';
  for (let i = 1; i <= 20; i++) {
    const div = document.createElement('div');
    div.id = `portCard-${i}`;
    div.className = 'port-card';
    div.innerHTML = `
      <div class="port-header">
        <span class="port-num">P${i}</span>
        <span id="portDot-${i}" class="port-link-dot" title="Sin enlace"></span>
      </div>
      <div class="port-body">
        <div id="portState-${i}" class="port-state">LIBRE</div>
        <div id="portDetail-${i}" class="port-detail"></div>
        <div class="port-progress-wrap" id="portProgressWrap-${i}" style="display:none;">
          <div class="port-progress-bar">
            <div class="port-progress-fill" id="portProgressFill-${i}" style="width:0%"></div>
          </div>
          <span class="port-progress-pct" id="portProgressPct-${i}">0%</span>
        </div>
        <div id="portIp-${i}" class="port-ip">10.100.${i}.1</div>
        <div id="portMac-${i}" class="port-mac">-</div>
      </div>
    `;
    grid.appendChild(div);
  }
}

// ============================================================================
// PESTAÑAS
// ============================================================================
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById(tabId).classList.add('active');

  if (tabId === 'tabOnus') loadOnusHistory();
  if (tabId === 'tabLotes') loadLotes();
  if (tabId === 'tabModels') loadFirmwares();
  if (tabId === 'tabUsers') loadUsers();
}

// ============================================================================
// PETICIONES API CON AUTENTICACIÓN
// ============================================================================
async function apiFetch(url, options = {}) {
  options.headers = options.headers || {};
  if (sessionToken) {
    options.headers['Authorization'] = 'Bearer ' + sessionToken;
    options.headers['X-Session-Token'] = sessionToken;
  }
  const res = await fetch(url, options);
  if (res.status === 401) {
    openModalLogin();
  }
  return res;
}

// ============================================================================
// AUTENTICACIÓN Y ROLES (RBAC)
// ============================================================================
async function checkAuth() {
  try {
    const res = await apiFetch('/api/v1/auth/me');
    const d = await res.json();
    currentUser = d.user || { username: 'admin', rol: 'admin' };
    applyUserRoleUI();
  } catch (e) {}
}

function applyUserRoleUI() {
  document.getElementById('topUserName').textContent = currentUser.nombre_completo || currentUser.username;
  const rBadge = document.getElementById('topUserRole');
  rBadge.textContent = currentUser.rol;
  rBadge.className = `role-badge role-${currentUser.rol}`;

  const isVisualizer = (currentUser.rol === 'visualizador');
  const isAdmin = (currentUser.rol === 'admin');

  document.querySelectorAll('.oper-only').forEach(el => {
    el.disabled = isVisualizer;
    if (isVisualizer) el.title = 'Acceso deshabilitado para rol visualizador';
  });

  document.querySelectorAll('.admin-only').forEach(el => {
    el.style.display = isAdmin ? 'inline-flex' : 'none';
  });

  document.getElementById('btnLoginLogout').textContent = sessionToken ? 'Cerrar Sesión' : 'Iniciar Sesión';
}

function handleAuthAction() {
  if (sessionToken) {
    apiFetch('/api/v1/auth/logout', { method: 'POST' });
    sessionToken = '';
    localStorage.removeItem('session_token');
    showToast('Sesión finalizada.');
    checkAuth();
  } else {
    openModalLogin();
  }
}

function openModalLogin() { document.getElementById('modalLogin').style.display = 'flex'; }
function closeModalLogin() { document.getElementById('modalLogin').style.display = 'none'; }

async function submitLogin() {
  const u = document.getElementById('loginUser').value.trim();
  const p = document.getElementById('loginPass').value.trim();
  if (!u || !p) return showToast('Ingrese usuario y contraseña');

  try {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: u, password: p })
    });
    const d = await res.json();
    if (res.ok && d.success) {
      sessionToken = d.token;
      localStorage.setItem('session_token', sessionToken);
      currentUser = d.user;
      closeModalLogin();
      showToast(d.message);
      applyUserRoleUI();
      loadLotes();
    } else {
      showToast(d.detail || 'Credenciales incorrectas');
    }
  } catch (e) {
    showToast('Error de conexión');
  }
}

// ============================================================================
// LOTES Y CAJAS
// ============================================================================
async function loadLotes() {
  try {
    const res = await apiFetch('/api/v1/lotes');
    currentLotes = await res.json();
    
    // Select de barra superior
    const select = document.getElementById('activeLoteSelect');
    select.innerHTML = '';
    
    // Tabla de lotes
    const tbody = document.getElementById('lotesTbody');
    tbody.innerHTML = '';

    currentLotes.forEach(l => {
      const opt = document.createElement('option');
      opt.value = l.id;
      opt.textContent = `${l.codigo_lote} (${l.numero_caja}) - ${l.modelo_nombre || l.modelo_id}`;
      if (l.es_activo) opt.selected = true;
      select.appendChild(opt);

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><b>${l.codigo_lote}</b></td>
        <td>${l.numero_caja}</td>
        <td>${l.modelo_nombre || l.modelo_id}</td>
        <td><code>${l.firmware_asignado}</code></td>
        <td><code>${l.clave_asignada}</code></td>
        <td>${l.cantidad_procesadas} / ${l.cantidad_total} (✅ ${l.cantidad_exitosas})</td>
        <td><span class="badge-status ${l.es_activo ? 'connected' : ''}">${l.estado}</span></td>
        <td>
          ${l.es_activo 
            ? '<b>ACTIVO</b>' 
            : `<button class="btn btn-sm btn-outline oper-only" onclick="activateLote(${l.id})">Activar</button>`}
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {}
}

async function changeActiveLote() {
  const id = document.getElementById('activeLoteSelect').value;
  if (!id) return;
  await activateLote(id);
}

async function activateLote(id) {
  try {
    const res = await apiFetch(`/api/v1/lotes/${id}/activate`, { method: 'POST' });
    const d = await res.json();
    if (res.ok) {
      showToast(d.message);
      loadLotes();
    } else {
      showToast(d.detail || 'Error activando lote');
    }
  } catch (e) {
    showToast('Error de conexión');
  }
}

async function handleCreateLote(e) {
  e.preventDefault();
  const codigo = document.getElementById('newLoteCodigo').value.trim();
  const caja = document.getElementById('newLoteCaja').value.trim();
  const modelo = document.getElementById('newLoteModelo').value;
  const firmware = document.getElementById('newLoteFirmware').value;
  const clave = document.getElementById('newLoteClave').value.trim();
  const qty = parseInt(document.getElementById('newLoteQty').value) || 20;

  try {
    const res = await apiFetch('/api/v1/lotes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codigo_lote: codigo,
        numero_caja: caja,
        modelo_id: modelo,
        firmware_asignado: firmware,
        clave_asignada: clave,
        cantidad_total: qty
      })
    });
    const d = await res.json();
    if (res.ok) {
      showToast(d.message);
      e.target.reset();
      loadLotes();
    } else {
      showToast(d.detail || 'Error creando lote');
    }
  } catch (e) {
    showToast('Error de conexión');
  }
}

// ============================================================================
// HISTORIAL DE ONUs
// ============================================================================
async function loadOnusHistory() {
  try {
    const res = await apiFetch('/api/v1/onus?limit=300');
    allOnusHistory = await res.json();
    renderOnusTable(allOnusHistory);
  } catch (e) {}
}

function renderOnusTable(rows) {
  const tbody = document.getElementById('onusTbody');
  tbody.innerHTML = '';
  if (!rows || !rows.length) {
    tbody.innerHTML = '<tr><td colspan="11" class="text-center" style="padding:20px; text-align:center; color:#64748b;">No hay registros de flasheo en esta estación.</td></tr>';
    return;
  }

  rows.forEach((r, idx) => {
    const tr = document.createElement('tr');
    const isExito = r.resultado === 'EXITO' || r.resultado === 'YA_CONFIGURADA';
    const isSynced = (r.sync_status === 'SYNCED');
    tr.innerHTML = `
      <td>${idx + 1}</td>
      <td style="font-size:12px; color:var(--texto-gris);">${r.fecha_hora || '-'}</td>
      <td><b>P${r.puerto_mikrotik || '-'}</b></td>
      <td><code>${r.ip || '-'}</code></td>
      <td><code>${r.mac || '-'}</code></td>
      <td><b>${r.pon_sn || r.pon_original || '-'}</b></td>
      <td>${r.codigo_lote || '-'} (${r.numero_caja || '-'})</td>
      <td><code>${r.credenciales ? r.credenciales.clave : '-'}</code></td>
      <td><span style="color:${isExito ? '#10b981' : '#ef4444'}; font-weight:700;">${r.resultado}</span></td>
      <td>${r.vlan3_ok === 'SI' ? '✅ SI' : '❌ NO'}</td>
      <td><span class="badge" style="background:${isSynced ? '#ecfdf5' : '#fef3c7'}; color:${isSynced ? '#059669' : '#b45309'}; font-weight:700; font-size:11px; padding:3px 8px; border-radius:4px;">${isSynced ? '☁️ Sincronizada' : '⏳ Pendiente'}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function filterOnusTable() {
  const q = document.getElementById('filterOnus').value.toLowerCase().trim();
  if (!q) return renderOnusTable(allOnusHistory);
  const filtered = allOnusHistory.filter(o => 
    (o.mac && o.mac.toLowerCase().includes(q)) ||
    (o.pon_sn && o.pon_sn.toLowerCase().includes(q)) ||
    (o.pon_original && o.pon_original.toLowerCase().includes(q)) ||
    (o.codigo_lote && o.codigo_lote.toLowerCase().includes(q))
  );
  renderOnusTable(filtered);
}

// ============================================================================
// MODELOS Y FIRMWARES
// ============================================================================
async function loadModels() {
  try {
    const res = await apiFetch('/api/v1/models');
    const models = await res.json();
    const selTop = document.getElementById('activeModelSelect');
    const selLote = document.getElementById('newLoteModelo');
    selTop.innerHTML = '';
    selLote.innerHTML = '';

    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = `${m.name || m.modelo} (${m.id})`;
      selTop.appendChild(opt);
      selLote.appendChild(opt.cloneNode(true));
    });
  } catch (e) {}
}

async function loadFirmwares() {
  try {
    const res = await apiFetch('/api/v1/firmwares');
    const firmwares = await res.json();
    const sel = document.getElementById('newLoteFirmware');
    const list = document.getElementById('firmwaresList');
    sel.innerHTML = '';
    list.innerHTML = '';

    firmwares.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f;
      opt.textContent = f;
      sel.appendChild(opt);

      const li = document.createElement('li');
      li.style = 'padding:6px 0; border-bottom:1px solid #1f293d; font-family:monospace; font-size:12px;';
      li.textContent = `💾 ${f}`;
      list.appendChild(li);
    });
  } catch (e) {}
}

async function handleUploadFirmware() {
  const fileInput = document.getElementById('firmwareFileInput');
  if (!fileInput.files || !fileInput.files.length) return showToast('Seleccione un archivo .bin');

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  try {
    const res = await apiFetch('/api/v1/firmwares/upload', {
      method: 'POST',
      body: formData
    });
    const d = await res.json();
    if (res.ok) {
      showToast(d.message);
      fileInput.value = '';
      loadFirmwares();
    } else {
      showToast(d.detail || 'Error subiendo firmware');
    }
  } catch (e) {
    showToast('Error de conexión');
  }
}

// ============================================================================
// USUARIOS (ADMIN)
// ============================================================================
async function loadUsers() {
  try {
    const res = await apiFetch('/api/v1/auth/users');
    const users = await res.json();
    const tbody = document.getElementById('usersTbody');
    tbody.innerHTML = '';

    users.forEach(u => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${u.id}</td>
        <td><b>${u.username}</b></td>
        <td>${u.nombre_completo || '-'}</td>
        <td><span class="role-badge role-${u.rol}">${u.rol}</span></td>
        <td>${u.activo ? '✅ Activo' : '❌ Inactivo'}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {}
}

// ============================================================================
// ACCIONES DE FLASHEO Y CONTROL
// ============================================================================
function onModeChange() {
  const mode = document.getElementById('flashModeSelect').value;
  if (mode === 'direct') {
    showToast('Modo Conexión Directa seleccionado (192.168.1.1)');
    const p1 = document.getElementById('portIp-1');
    if (p1) p1.textContent = '192.168.1.1 (Directo)';
  } else {
    showToast('Modo Switch MikroTik seleccionado (20 Puertos)');
    const p1 = document.getElementById('portIp-1');
    if (p1) p1.textContent = '10.100.1.1';
  }
}

async function executeMainAction() {
  const mode = document.getElementById('flashModeSelect').value;
  const model = document.getElementById('activeModelSelect').value;

  if (mode === 'switch') {
    try {
      const res = await apiFetch('/api/v1/flasheo/start_continuo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: model, parallel: 20 })
      });
      const d = await res.json();
      showToast(d.message || d.detail);
    } catch (e) {
      showToast('Error iniciando flasheo continuo');
    }
  } else {
    // Conexión Directa a la ONU (192.168.1.1)
    try {
      const res = await apiFetch('/api/v1/flasheo/start_single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip: '192.168.1.1', model: model, direct: true, action: 'full' })
      });
      const d = await res.json();
      showToast(d.message || d.detail);
    } catch (e) {
      showToast('Error iniciando flasheo directo');
    }
  }
}

async function executeSubAction(actionType) {
  const mode = document.getElementById('flashModeSelect').value;
  const model = document.getElementById('activeModelSelect').value;
  const isDirect = (mode === 'direct');
  const ip = isDirect ? '192.168.1.1' : '10.100.1.1';

  try {
    const res = await apiFetch('/api/v1/flasheo/start_single', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip: ip, model: model, direct: isDirect, action: actionType })
    });
    const d = await res.json();
    showToast(d.message || d.detail);
  } catch (e) {
    showToast('Error ejecutando ' + actionType);
  }
}

async function stopProcess() {
  try {
    const res = await apiFetch('/api/v1/flasheo/stop', { method: 'POST' });
    const d = await res.json();
    showToast(d.message);
  } catch (e) {
    showToast('Error deteniendo proceso');
  }
}

function showToast(msg) {
  if (!msg) return;
  const container = document.getElementById('toastContainer');
  const div = document.createElement('div');
  div.className = 'toast';
  div.textContent = msg;
  container.appendChild(div);
  setTimeout(() => div.remove(), 4000);
}


// ============================================================================
// SINCRONIZACIÓN CON INTRANET CENTRAL (OFFLINE / MULTI-ESTACIÓN)
// ============================================================================
async function updateSyncStatusUI() {
  try {
    const res = await fetch('/api/v1/sync/status');
    const d = await res.json();
    const badge = document.getElementById('syncStatusBadge');
    const stBadge = document.getElementById('stationIdBadge');
    
    if (stBadge) stBadge.innerText = d.station_id || 'ESTACION';
    
    if (badge) {
      if (d.is_online) {
        if (d.pending_count > 0) {
          badge.className = 'badge-status warning';
          badge.innerText = `● En Línea (${d.pending_count} pendientes)`;
          badge.style.background = '#fef3c7';
          badge.style.color = '#92400e';
        } else {
          badge.className = 'badge-status connected';
          badge.innerText = `● Intranet: Sincronizada`;
          badge.style.background = '#ecfdf5';
          badge.style.color = '#065f46';
        }
      } else {
        badge.className = 'badge-status disconnected';
        badge.innerText = `● Modo Offline (${d.pending_count} en cola)`;
        badge.style.background = '#fee2e2';
        badge.style.color = '#991b1b';
      }
    }
    
    const sumOnline = document.getElementById('cfgSummaryOnline');
    const sumPending = document.getElementById('cfgSummaryPending');
    const sumLastSync = document.getElementById('cfgSummaryLastSync');
    if (sumOnline) sumOnline.innerText = d.is_online ? 'En Línea (Conectado)' : 'Desconectado (Offline)';
    if (sumPending) sumPending.innerText = `${d.pending_count} registros`;
    if (sumLastSync) sumLastSync.innerText = d.last_sync || 'Nunca';
  } catch (e) {
  }
}

async function triggerManualSync() {
  const btn = document.getElementById('btnManualSync');
  if (btn) btn.innerText = 'Subiendo...';
  try {
    const res = await fetch('/api/v1/sync/trigger', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      alert(`✅ Sincronización exitosa: ${data.synced_count} registros subidos a la Intranet Central.`);
    } else if (data.status === 'idle') {
      alert(`ℹ️ No hay registros pendientes. Toda la información ya está sincronizada.`);
    } else {
      alert(`⚠️ ${data.message || 'No se pudo sincronizar en este momento. Verifique conectividad con el servidor.'}`);
    }
  } catch (err) {
    alert(`❌ Error al conectar con el servicio local de sincronización: ${err}`);
  } finally {
    if (btn) btn.innerText = '🔄 Sincronizar';
    updateSyncStatusUI();
    if (typeof loadOnusHistory === 'function') loadOnusHistory();
  }
}

function openStationConfigModal() {
  fetch('/api/v1/sync/status')
    .then(r => r.json())
    .then(d => {
      document.getElementById('cfgStationId').value = d.station_id || '';
      document.getElementById('cfgStationName').value = d.station_name || '';
      document.getElementById('cfgServerUrl').value = d.server_url || '';
      document.getElementById('cfgAutoSync').checked = d.auto_sync !== false;
      document.getElementById('modalStationConfig').style.display = 'flex';
      updateSyncStatusUI();
    });
}

function closeStationConfigModal() {
  document.getElementById('modalStationConfig').style.display = 'none';
}

async function saveStationConfig() {
  const body = {
    station_id: document.getElementById('cfgStationId').value.trim(),
    station_name: document.getElementById('cfgStationName').value.trim(),
    server_url: document.getElementById('cfgServerUrl').value.trim(),
    auto_sync: document.getElementById('cfgAutoSync').checked
  };
  
  if (!body.station_id || !body.server_url) {
    alert('Por favor complete el ID de la estación y la URL del servidor.');
    return;
  }
  
  try {
    const res = await fetch('/api/v1/sync/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const d = await res.json();
    if (d.ok) {
      alert('Configuración guardada correctamente.');
      closeStationConfigModal();
      updateSyncStatusUI();
    }
  } catch (err) {
    alert(`Error guardando configuración: ${err}`);
  }
}
