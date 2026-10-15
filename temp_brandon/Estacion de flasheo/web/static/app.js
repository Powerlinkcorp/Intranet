// app.js — Controlador Frontend Reactivo con WebSockets para Estación de Flasheo
let currentUser = { username: 'admin', rol: 'admin', nombre_completo: 'Administrador Local' };
let sessionToken = localStorage.getItem('session_token') || '';
let ws = null;
let currentLotes = [];
let allOnusHistory = [];

document.addEventListener('DOMContentLoaded', () => {
  initPortsGrid();
  checkAuth();
  loadLotes();
  loadModels();
  loadFirmwares();
  loadOnusHistory();
  connectWebSocket();
});

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

  // Estado del proceso
  const isRunning = data.process && data.process.running;
  const btnStart = document.getElementById('btnStartAction');
  const btnReset = document.getElementById('btnActionReset');
  const btnAudit = document.getElementById('btnActionAudit');
  const btnStop = document.getElementById('btnStop');
  if (btnStart) btnStart.style.display = isRunning ? 'none' : 'inline-flex';
  if (btnReset) btnReset.style.display = isRunning ? 'none' : 'inline-flex';
  if (btnAudit) btnAudit.style.display = isRunning ? 'none' : 'inline-flex';
  if (btnStop) btnStop.style.display = isRunning ? 'inline-flex' : 'none';

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
  const statusOnus = (data.status && data.status.onus) || [];
  const onuMap = {};
  statusOnus.forEach(o => { onuMap[String(o.puerto)] = o; });

  for (let p = 1; p <= 20; p++) {
    const card = document.getElementById(`portCard-${p}`);
    const dot = document.getElementById(`portDot-${p}`);
    const stateEl = document.getElementById(`portState-${p}`);
    const ipEl = document.getElementById(`portIp-${p}`);
    const macEl = document.getElementById(`portMac-${p}`);
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
    } else {
      stateEl.textContent = hasLink ? 'ENLACE OK' : 'LIBRE';
      card.className = `port-card ${hasLink ? 'has-link' : ''}`;
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
    tbody.innerHTML = '<tr><td colspan="10" class="text-center">No hay registros de flasheo.</td></tr>';
    return;
  }

  rows.forEach((r, idx) => {
    const tr = document.createElement('tr');
    const isExito = r.resultado === 'EXITO' || r.resultado === 'YA_CONFIGURADA';
    tr.innerHTML = `
      <td>${idx + 1}</td>
      <td>${r.fecha_hora}</td>
      <td><b>P${r.puerto_mikrotik || '-'}</b></td>
      <td>${r.ip || '-'}</td>
      <td><code>${r.mac || '-'}</code></td>
      <td><b>${r.pon_sn || r.pon_original || '-'}</b></td>
      <td>${r.codigo_lote || '-'} (${r.numero_caja || '-'})</td>
      <td><code>${r.credenciales ? r.credenciales.clave : '-'}</code></td>
      <td><span style="color:${isExito ? '#10b981' : '#ef4444'}; font-weight:700;">${r.resultado}</span></td>
      <td>${r.vlan3_ok === 'SI' ? '✅ SI' : '❌ NO'}</td>
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
