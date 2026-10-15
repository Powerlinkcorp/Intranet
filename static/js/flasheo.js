// flasheo.js — Controlador Frontend Centralizado para Auditoría y Monitoreo de Flasheo
// Exclusivo para Visualización, Trazabilidad y Consulta de Estaciones del Galpón

let allStations = [];
let allOnusHistory = [];
let allLotes = [];
let activeTab = 'tabStations';

document.addEventListener('DOMContentLoaded', () => {
  initDashboard();
});

// ============================================================================
// INICIALIZACIÓN
// ============================================================================
async function initDashboard() {
  await refreshAllData();
}

async function refreshAllData() {
  await Promise.all([
    loadStations(),
    loadOnusHistory(),
    loadLotes(),
    loadModels(),
    loadFirmwares()
  ]);
  loadUsers();
  updateKpiMetrics();
}

// ============================================================================
// NAVEGACIÓN ENTRE PESTAÑAS
// ============================================================================
function switchTab(tabId, btnEl) {
  activeTab = tabId;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  if (btnEl) btnEl.classList.add('active');
  const target = document.getElementById(tabId);
  if (target) target.classList.add('active');

  if (tabId === 'tabStations') loadStations();
  if (tabId === 'tabOnus') loadOnusHistory();
  if (tabId === 'tabLotes') loadLotes();
  if (tabId === 'tabModels') { loadModels(); loadFirmwares(); }
  if (tabId === 'tabUsers') loadUsers();
}

// ============================================================================
// HELPER DE PETICIONES
// ============================================================================
async function apiFetch(url, options = {}) {
  try {
    const res = await fetch(url, options);
    return res;
  } catch (err) {
    console.error(`Error en fetch a ${url}:`, err);
    throw err;
  }
}

// ============================================================================
// 1. ESTACIONES DE FLASHEO (LAPTOPS DEL GALPÓN)
// ============================================================================
async function loadStations() {
  try {
    const res = await apiFetch('/api/flasheo/stations');
    if (!res.ok) return;
    allStations = await res.json();

    renderStationCards(allStations);
    renderStationsTable(allStations);
    updateStationFilterDropdown(allStations);
    updateKpiMetrics();
  } catch (e) {
    console.error("Error al cargar estaciones:", e);
  }
}

function renderStationCards(stations) {
  const container = document.getElementById('stationCardsGrid');
  if (!container) return;
  container.innerHTML = '';

  if (!stations || !stations.length) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 25px; text-align: center; background: #fff; border: 1px dashed #cbd5e1; border-radius: 12px; color: #64748b;">
        <i class="fa-solid fa-laptop" style="font-size: 32px; color: #cbd5e1; margin-bottom: 8px;"></i>
        <p style="margin: 0; font-weight: 600;">No hay estaciones registradas aún.</p>
        <p style="margin: 4px 0 0 0; font-size: 12px;">En cuanto una laptop inicie sesión y sincronice registros, aparecerá aquí automáticamente.</p>
      </div>
    `;
    return;
  }

  stations.forEach(st => {
    const card = document.createElement('div');
    card.className = 'station-card-box';

    const isActive = st.is_active;
    const total = st.total_flashed || 0;

    card.innerHTML = `
      <div class="station-card-header">
        <div>
          <div class="station-card-title">
            <i class="fa-solid fa-laptop" style="color:var(--acento);"></i>
            <span>${st.station_name || st.station_id}</span>
          </div>
          <span style="font-family:monospace; font-size:11px; color:#64748b; font-weight:600;">${st.station_id}</span>
        </div>
        <span class="badge-status ${isActive ? 'connected' : 'disconnected'}" style="font-size:11px;">
          ${isActive ? '🟢 Activa' : '⚪ Inactiva'}
        </span>
      </div>

      <div class="station-card-meta">
        <div>
          <span style="font-size:10px; text-transform:uppercase; color:#94a3b8; font-weight:700;">IP Conexión</span>
          <div style="font-weight:600; font-family:monospace;">${st.ip_address || '127.0.0.1'}</div>
        </div>
        <div>
          <span style="font-size:10px; text-transform:uppercase; color:#94a3b8; font-weight:700;">Hostname</span>
          <div style="font-weight:600; font-family:monospace;">${st.hostname || 'Laptop'}</div>
        </div>
      </div>

      <div style="display:flex; justify-content:space-between; align-items:center; background:#f8fafc; padding:8px 12px; border-radius:8px; border:1px solid #e2e8f0;">
        <span style="font-size:12px; font-weight:600; color:#475569;">ONUs Procesadas:</span>
        <span style="font-size:18px; font-weight:800; color:var(--cabeceras);">${total}</span>
      </div>

      <div class="station-card-footer">
        <span><i class="fa-regular fa-clock"></i> Última sincronización:</span>
        <b>${st.last_sync || 'Nunca'}</b>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderStationsTable(stations) {
  const tbody = document.getElementById('stationsTbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!stations || !stations.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="padding:20px; text-align:center; color:#64748b;">No hay estaciones registradas.</td></tr>';
    return;
  }

  stations.forEach(s => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong><code>${s.station_id}</code></strong></td>
      <td><b>${s.station_name || s.station_id}</b></td>
      <td><span style="color:#64748b; font-family:monospace;">${s.hostname || '-'}</span></td>
      <td><code>${s.ip_address || '-'}</code></td>
      <td><span class="badge" style="background:#e0f2fe; color:#0369a1; font-weight:700; padding:3px 10px; border-radius:4px;">${s.total_flashed}</span></td>
      <td style="font-size:12px; color:#475569;">${s.last_sync || 'Nunca'}</td>
      <td><span class="badge-status ${s.is_active ? 'connected' : 'disconnected'}">${s.is_active ? '🟢 Activa' : '⚪ Inactiva'}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function updateStationFilterDropdown(stations) {
  const select = document.getElementById('filterStation');
  if (!select) return;

  const currentVal = select.value;
  select.innerHTML = '<option value="TODAS">💻 Todas las Estaciones</option>';
  stations.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.station_id;
    opt.innerText = `💻 ${s.station_name || s.station_id} (${s.total_flashed} ONUs)`;
    select.appendChild(opt);
  });

  if (currentVal) select.value = currentVal;
}

// ============================================================================
// 2. HISTORIAL CENTRAL DE ONUs
// ============================================================================
async function loadOnusHistory() {
  try {
    const stFilter = document.getElementById('filterStation')?.value;
    let url = '/api/flasheo/onus?limit=500';
    if (stFilter && stFilter !== 'TODAS') {
      url += `&station_id=${encodeURIComponent(stFilter)}`;
    }
    const res = await apiFetch(url);
    if (!res.ok) return;
    allOnusHistory = await res.json();
    filterOnusTable();
    updateKpiMetrics();
  } catch (e) {
    console.error("Error al cargar historial de ONUs:", e);
  }
}

function filterOnusTable() {
  const q = (document.getElementById('filterOnus')?.value || '').toLowerCase().trim();
  const stFilter = document.getElementById('filterStation')?.value || 'TODAS';
  const resFilter = document.getElementById('filterResult')?.value || 'TODOS';

  let filtered = allOnusHistory;

  if (stFilter && stFilter !== 'TODAS') {
    filtered = filtered.filter(o => o.station_id === stFilter);
  }

  if (resFilter && resFilter !== 'TODOS') {
    filtered = filtered.filter(o => o.resultado === resFilter);
  }

  if (q) {
    filtered = filtered.filter(o =>
      (o.mac && o.mac.toLowerCase().includes(q)) ||
      (o.pon_sn && o.pon_sn.toLowerCase().includes(q)) ||
      (o.pon_original && o.pon_original.toLowerCase().includes(q)) ||
      (o.station_id && o.station_id.toLowerCase().includes(q)) ||
      (o.codigo_lote && o.codigo_lote.toLowerCase().includes(q)) ||
      (o.numero_caja && o.numero_caja.toLowerCase().includes(q))
    );
  }

  renderOnusTable(filtered);
}

function renderOnusTable(rows) {
  const tbody = document.getElementById('onusTbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const badge = document.getElementById('onusTotalBadge');
  if (badge) {
    badge.innerHTML = `<i class="fa-solid fa-list-check"></i> Mostrando ${rows.length} de ${allOnusHistory.length} registros`;
  }

  if (!rows || !rows.length) {
    tbody.innerHTML = '<tr><td colspan="11" class="text-center" style="padding:25px; text-align:center; color:#64748b;">No se encontraron registros de flasheo para los filtros seleccionados.</td></tr>';
    return;
  }

  rows.forEach((r, idx) => {
    const tr = document.createElement('tr');
    const isExito = r.resultado === 'EXITO' || r.resultado === 'YA_CONFIGURADA';
    const stationName = r.station_id || 'ESTACION-GALPON';
    const clave = (r.credenciales && r.credenciales.clave) ? r.credenciales.clave : '-';

    tr.innerHTML = `
      <td>${idx + 1}</td>
      <td><span class="badge" style="background:#e0e7ff; color:#3730a3; font-weight:700; font-size:11px; padding:3px 8px; border-radius:4px;"><i class="fa-solid fa-laptop"></i> ${stationName}</span></td>
      <td style="font-size:12px; color:#475569;">${r.fecha_hora || '-'}</td>
      <td><b>P${r.puerto_mikrotik || '-'}</b></td>
      <td><code style="color:#0284c7;">${r.ip || '-'}</code></td>
      <td><code style="font-weight:700;">${r.mac || '-'}</code></td>
      <td><b style="color:var(--cabeceras);">${r.pon_sn || r.pon_original || '-'}</b></td>
      <td>${r.codigo_lote || '-'} <span style="font-size:11px; color:#64748b;">(${r.numero_caja || '-'})</span></td>
      <td><code style="background:#f1f5f9; padding:2px 6px; border-radius:4px;">${clave}</code></td>
      <td><span style="color:${isExito ? '#10b981' : '#ef4444'}; font-weight:800;">${r.resultado}</span></td>
      <td>${r.vlan3_ok === 'SI' ? '<span style="color:#10b981; font-weight:700;">✅ SI</span>' : '<span style="color:#ef4444; font-weight:700;">❌ NO</span>'}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ============================================================================
// 3. CONSULTA DE TRAZABILIDAD RÁPIDA
// ============================================================================
async function executeTraceSearch() {
  const input = document.getElementById('traceInput');
  const query = (input ? input.value : '').trim();
  const container = document.getElementById('traceResultContainer');
  if (!container) return;

  if (!query) {
    showToast('Ingresa una MAC o Serial GPON para consultar.');
    return;
  }

  container.style.display = 'block';
  container.innerHTML = `
    <div style="padding:20px; text-align:center; color:#64748b;">
      <i class="fa-solid fa-spinner fa-spin" style="font-size:24px; color:var(--acento);"></i>
      <p style="margin-top:8px;">Buscando trazabilidad en la base de datos central...</p>
    </div>
  `;

  try {
    const res = await apiFetch(`/api/flasheo/onu_traceability?query=${encodeURIComponent(query)}`);
    const data = await res.json();

    if (!data || !data.encontrado) {
      container.innerHTML = `
        <div style="padding:25px; text-align:center; background:#fff; border:1px solid #fee2e2; border-radius:12px; color:#991b1b;">
          <i class="fa-solid fa-circle-xmark" style="font-size:32px; color:#ef4444; margin-bottom:8px;"></i>
          <h4 style="margin:0;">No se encontraron registros de flasheo</h4>
          <p style="margin:6px 0 0 0; font-size:13px; color:#64748b;">El identificador "<b>${query}</b>" no ha sido reportado aún por ninguna estación de flasheo.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="trace-result-card">
        <div class="trace-header">
          <div style="display:flex; align-items:center; gap:10px;">
            <i class="fa-solid fa-microchip" style="font-size:24px; color:var(--acento);"></i>
            <div>
              <h4 style="margin:0; font-size:17px; color:var(--cabeceras);">Ficha de Trazabilidad: ${data.pon_sn || data.mac}</h4>
              <span style="font-size:12px; color:#64748b;">Estación origen: <b>${data.station_id}</b> | Fecha: <b>${data.fecha_flasheo || 'Reciente'}</b></span>
            </div>
          </div>
          <span class="badge-status connected" style="font-size:12px;">
            <i class="fa-solid fa-check-double"></i> Registro Auditado
          </span>
        </div>

        <div class="trace-grid">
          <div class="trace-item">
            <span class="trace-item-label">Dirección MAC</span>
            <span class="trace-item-value"><code>${data.mac || '-'}</code></span>
          </div>

          <div class="trace-item">
            <span class="trace-item-label">GPON Serial Number (SN)</span>
            <span class="trace-item-value"><b>${data.pon_sn || '-'}</b></span>
          </div>

          <div class="trace-item">
            <span class="trace-item-label">Serial Original de Fábrica</span>
            <span class="trace-item-value">${data.pon_original || '-'}</span>
          </div>

          <div class="trace-item">
            <span class="trace-item-label">Modelo de Equipo</span>
            <span class="trace-item-value">${data.modelo || 'VSOL V2801S-B'}</span>
          </div>

          <div class="trace-item">
            <span class="trace-item-label">Firmware Programado</span>
            <span class="trace-item-value"><code>${data.firmware || 'V2801S_v3.bin'}</code></span>
          </div>

          <div class="trace-item">
            <span class="trace-item-label">Lote y Caja</span>
            <span class="trace-item-value">${data.lote?.codigo_lote || '-'} (${data.lote?.numero_caja || '-'})</span>
          </div>

          <div class="trace-item">
            <span class="trace-item-label">Credencial de Acceso (Usuario)</span>
            <span class="trace-item-value"><span class="trace-cred-box">${data.credenciales?.usuario || 'Powerlink'}</span></span>
          </div>

          <div class="trace-item">
            <span class="trace-item-label">Credencial de Acceso (Clave)</span>
            <span class="trace-item-value"><span class="trace-cred-box" style="font-weight:700; color:#d97706;">${data.credenciales?.clave || '********'}</span></span>
          </div>

          <div class="trace-item">
            <span class="trace-item-label">Verificación VLAN 3 TR-069</span>
            <span class="trace-item-value">${data.vlan3_verificada === 'SI' ? '<b style="color:#10b981;">✅ Verificada Correctamente</b>' : '<b style="color:#ef4444;">❌ No Confirmada</b>'}</span>
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `
      <div style="padding:20px; text-align:center; color:#ef4444;">
        <p>Error consultando trazabilidad: ${err}</p>
      </div>
    `;
  }
}

// ============================================================================
// 4. LOTES Y CAJAS
// ============================================================================
async function loadLotes() {
  try {
    const res = await apiFetch('/api/v1/lotes');
    if (!res.ok) return;
    allLotes = await res.json();
    renderLotesTable(allLotes);
    updateKpiMetrics();
  } catch (e) {
    console.error("Error al cargar lotes:", e);
  }
}

function renderLotesTable(lotes) {
  const tbody = document.getElementById('lotesTbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!lotes || !lotes.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="padding:20px; text-align:center; color:#64748b;">No hay lotes registrados.</td></tr>';
    return;
  }

  lotes.forEach(l => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><b>${l.codigo_lote}</b></td>
      <td>${l.numero_caja}</td>
      <td>${l.modelo_nombre || l.modelo_id}</td>
      <td><code>${l.firmware_asignado}</code></td>
      <td><code>${l.clave_asignada}</code></td>
      <td><b>${l.cantidad_procesadas} / ${l.cantidad_total}</b> (✅ ${l.cantidad_exitosas})</td>
      <td><span class="badge-status ${l.es_activo ? 'connected' : ''}">${l.estado}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ============================================================================
// 5. MODELOS Y FIRMWARES
// ============================================================================
async function loadModels() {
  try {
    const res = await apiFetch('/api/v1/models');
    if (!res.ok) return;
    const models = await res.json();

    const list = document.getElementById('modelsCardsList');
    if (!list) return;
    list.innerHTML = '';

    models.forEach(m => {
      const card = document.createElement('div');
      card.style = 'background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px 14px; display:flex; justify-content:space-between; align-items:center;';
      card.innerHTML = `
        <div>
          <b style="font-size:14px; color:var(--cabeceras);">${m.name || m.modelo}</b>
          <div style="font-size:11px; color:#64748b; font-family:monospace;">ID: ${m.id}</div>
        </div>
        <span class="badge" style="background:#e0f2fe; color:#0369a1; font-weight:700; font-size:11px; padding:4px 8px; border-radius:4px;">
          ${m.marca || 'VSOL'}
        </span>
      `;
      list.appendChild(card);
    });
  } catch (e) {}
}

async function loadFirmwares() {
  try {
    const res = await apiFetch('/api/v1/firmwares');
    if (!res.ok) return;
    const firmwares = await res.json();

    const list = document.getElementById('firmwaresList');
    if (!list) return;
    list.innerHTML = '';

    if (!firmwares || !firmwares.length) {
      list.innerHTML = '<li style="color:#64748b; font-size:13px;">No hay archivos .bin cargados en el repositorio central.</li>';
      return;
    }

    firmwares.forEach(f => {
      const li = document.createElement('li');
      li.style = 'padding:10px 14px; border:1px solid #e2e8f0; border-radius:8px; background:#f8fafc; font-family:monospace; font-size:12px; color:#1e293b; display:flex; align-items:center; gap:8px;';
      li.innerHTML = `<span>💾</span> <b>${f}</b>`;
      list.appendChild(li);
    });
  } catch (e) {}
}

// ============================================================================
// 6. USUARIOS Y OPERADORES (ADMIN)
// ============================================================================
async function loadUsers() {
  try {
    const res = await apiFetch('/api/v1/auth/users');
    if (!res.ok) return;
    const users = await res.json();

    const tbody = document.getElementById('usersTbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    users.forEach(u => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${u.id}</td>
        <td><b>${u.username}</b></td>
        <td>${u.nombre_completo || '-'}</td>
        <td><span class="role-badge role-${u.rol}">${u.rol}</span></td>
        <td><span class="badge-status ${u.activo ? 'connected' : 'disconnected'}">${u.activo ? 'Activo' : 'Inactivo'}</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {}
}

// ============================================================================
// 7. CÁLCULO DE KPIS CENTRALES
// ============================================================================
function updateKpiMetrics() {
  const elStations = document.getElementById('kpiStationsCount');
  const elTotalOnus = document.getElementById('kpiTotalOnus');
  const elSuccessOnus = document.getElementById('kpiSuccessOnus');
  const elSuccessPct = document.getElementById('kpiSuccessPercent');
  const elTotalLotes = document.getElementById('kpiTotalLotes');

  const stationsCount = allStations.length;
  const activeStations = allStations.filter(s => s.is_active).length;
  if (elStations) elStations.textContent = stationsCount;
  const subSt = document.getElementById('kpiStationsSub');
  if (subSt) subSt.textContent = `${activeStations} Activas en Galpón`;

  const totalOnus = allOnusHistory.length;
  if (elTotalOnus) elTotalOnus.textContent = totalOnus;

  const successOnus = allOnusHistory.filter(o => o.resultado === 'EXITO' || o.resultado === 'YA_CONFIGURADA').length;
  if (elSuccessOnus) elSuccessOnus.textContent = successOnus;

  if (elSuccessPct) {
    const pct = totalOnus > 0 ? Math.round((successOnus / totalOnus) * 100) : 0;
    elSuccessPct.textContent = `${pct}% Efectividad`;
  }

  if (elTotalLotes) elTotalLotes.textContent = allLotes.length;
}

// ============================================================================
// TOAST NOTIFICATIONS
// ============================================================================
function showToast(msg) {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => {
    t.remove();
  }, 3500);
}
