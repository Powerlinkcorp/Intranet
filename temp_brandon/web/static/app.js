/**
 * app.js — Controlador del Aprovisionamiento Automático en 3 Pasos
 * Powerlink Corp • Gestión Inteligente de ONUs & SmartOLT
 * 
 * Paso 1: Aceptación en SmartOLT (SN, Nombre por defecto, Buscador DBA ➔ VLAN 3 obligatoria)
 * Paso 2: Configuración de la ONU VSOL (IP, Wi-Fi 2.4G/5G, Buscador de VLAN según HUB con 100 cupos)
 * Paso 3: Liberación en SmartOLT (Borrado de configuradas para retornar a desconfiguradas y habilitar aprovisionamiento por Rubpi)
 * Seguridad: Autenticación con roles (admin, aprovisionador, lectura) y filtro de IPs
 */

// =============================================================================
// ESTADO GLOBAL DE LA APLICACIÓN
// =============================================================================
let currentWizardStep = 1;
let step1Done = false;
let step2Done = false;
let step3Done = false;

// Usuario y Sesión
let currentUser = {
  username: "",
  role: "lectura"
};
let authToken = localStorage.getItem("powerlink_auth_token") || "";

// Datos del equipo actual en el asistente
let sessionData = {
  sn: "",
  name: "Configurada manualmente",
  dba_profile: "100M",
  ip: "3.3.",
  target_vlan: "100",
  hub_name: "",
  olt_id: "",
  olt_name: "",
  ssid_2g: "",
  pass_2g: "",
  ssid_5g: "",
  pass_5g: "",
  mac: "",
  model: ""
};

// Catálogos
let vlanCatalog = [];
let dbaProfilesCatalog = [];
let currentIpWhitelist = [];

let activeJobId = null;
let pollInterval = null;

// =============================================================================
// HELPER DE PETICIONES CON AUTENTICACIÓN (apiFetch)
// =============================================================================
async function apiFetch(url, options = {}) {
  const headers = options.headers || {};
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  if (!headers["Content-Type"] && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  options.headers = headers;

  try {
    const res = await fetch(url, options);
    if (res.status === 401) {
      // Sesión expirada o no autorizada
      showLoginModal(true);
      throw new Error("Sesión no válida o expirada");
    }
    return res;
  } catch (err) {
    throw err;
  }
}

// =============================================================================
// INICIALIZACIÓN Y CONTROL DE SESIÓN
// =============================================================================
document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  bindEvents();
  const sessionOk = await checkSession();
  if (sessionOk) {
    await loadInitialData();
  }
}

async function checkSession() {
  if (!authToken) {
    window.location.replace("/login");
    return false;
  }

  try {
    const res = await fetch("/api/auth/session", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    const data = await res.json();
    if (data.success) {
      currentUser.username = data.username;
      currentUser.role = data.role;
      updateUserUI();
      hideLoginModal();
      return true;
    } else {
      localStorage.removeItem("powerlink_auth_token");
      window.location.replace("/login");
      return false;
    }
  } catch (e) {
    localStorage.removeItem("powerlink_auth_token");
    window.location.replace("/login");
    return false;
  }
}

function updateUserUI() {
  const userBadge = document.getElementById("userBadge");
  const lblUsername = document.getElementById("lblUsername");
  const lblUserRole = document.getElementById("lblUserRole");
  const btnOpenAdminModal = document.getElementById("btnOpenAdminModal");
  const btnOpenSmartOltModal = document.getElementById("btnOpenSmartOltModal");
  const btnLogout = document.getElementById("btnLogout");
  const readonlyAlert = document.getElementById("readonlyAlert");

  lblUsername.innerText = currentUser.username;
  lblUserRole.innerText = currentUser.role.toUpperCase();
  userBadge.style.display = "inline-flex";
  btnLogout.style.display = "inline-flex";

  // Estilo según rol
  userBadge.className = "badge";
  if (currentUser.role === "admin") {
    userBadge.classList.add("badge-role-admin");
    btnOpenAdminModal.style.display = "inline-flex";
    if (btnOpenSmartOltModal) btnOpenSmartOltModal.style.display = "inline-flex";
    readonlyAlert.style.display = "none";
    enableActionButtons(true);
  } else if (currentUser.role === "aprovisionador") {
    userBadge.classList.add("badge-role-aprovisionador");
    btnOpenAdminModal.style.display = "none";
    if (btnOpenSmartOltModal) btnOpenSmartOltModal.style.display = "none";
    readonlyAlert.style.display = "none";
    enableActionButtons(true);
  } else {
    // Lectura
    userBadge.classList.add("badge-role-lectura");
    btnOpenAdminModal.style.display = "none";
    if (btnOpenSmartOltModal) btnOpenSmartOltModal.style.display = "none";
    readonlyAlert.style.display = "flex";
    enableActionButtons(false);
  }
}

function enableActionButtons(enable) {
  document.querySelectorAll(".action-btn").forEach(btn => {
    btn.disabled = !enable;
    if (!enable) {
      btn.title = "Acción no permitida en modo Solo Lectura";
    } else {
      btn.removeAttribute("title");
    }
  });
}

function showLoginModal(isExpired = false) {
  const modal = document.getElementById("loginModal");
  modal.style.display = "flex";
  const errorMsg = document.getElementById("loginErrorMsg");
  if (isExpired) {
    errorMsg.innerText = "Su sesión ha expirado. Por favor ingrese sus credenciales nuevamente.";
    errorMsg.style.display = "block";
  } else {
    errorMsg.style.display = "none";
  }
}

function hideLoginModal() {
  const modal = document.getElementById("loginModal");
  if (modal) modal.style.display = "none";
  const passIn = document.getElementById("loginPass");
  if (passIn) passIn.value = "";
}

async function loadInitialData() {
  await loadConfig();
  await loadHistory();
  await loadSmartOltProfiles();
  await loadVlansCatalog();
}

// =============================================================================
// VINCULACIÓN DE EVENTOS
// =============================================================================
function bindEvents() {
  // Login Form
  document.getElementById("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const u = document.getElementById("loginUser").value.trim();
    const p = document.getElementById("loginPass").value.trim();
    const errorEl = document.getElementById("loginErrorMsg");

    if (!u || !p) {
      errorEl.innerText = "Por favor ingrese usuario y contraseña";
      errorEl.style.display = "block";
      return;
    }

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p })
      });
      const data = await res.json();
      if (data.success) {
        authToken = data.token;
        localStorage.setItem("powerlink_auth_token", authToken);
        currentUser.username = data.username;
        currentUser.role = data.role;
        updateUserUI();
        hideLoginModal();
        showToast(`Bienvenido ${data.username} (${data.role})`, "success");
        await loadInitialData();
      } else {
        errorEl.innerText = data.error || "Credenciales incorrectas";
        errorEl.style.display = "block";
      }
    } catch (err) {
      errorEl.innerText = `Error de conexión: ${err.message}`;
      errorEl.style.display = "block";
    }
  });

  // Toggle visibilidad de clave en modal de login (si se abre)
  const btnToggleLoginPass = document.getElementById("btnToggleLoginPass");
  const loginPassIn = document.getElementById("loginPass");
  if (btnToggleLoginPass && loginPassIn) {
    btnToggleLoginPass.addEventListener("click", () => {
      if (loginPassIn.type === "password") {
        loginPassIn.type = "text";
        btnToggleLoginPass.innerText = "🙈";
      } else {
        loginPassIn.type = "password";
        btnToggleLoginPass.innerText = "👁️";
      }
    });
  }

  // Logout
  document.getElementById("btnLogout").addEventListener("click", async () => {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } catch (e) {}
    localStorage.removeItem("powerlink_auth_token");
    authToken = "";
    window.location.replace("/login");
  });

  // Navegación de pestañas del Wizard
  document.getElementById("navStep1").addEventListener("click", () => goToStep(1));
  document.getElementById("navStep2").addEventListener("click", () => goToStep(2));
  document.getElementById("navStep3").addEventListener("click", () => goToStep(3));

  // Botón Detectar ONU en SmartOLT (Paso 1)
  document.getElementById("btnDetectUnconfigured").addEventListener("click", detectUnconfiguredSmartOlt);

  // Al escribir en el SN, resetear validación de Paso 1 si ya estaba validado
  document.getElementById("onuSn").addEventListener("input", () => {
    if (step1Done) {
      step1Done = false;
      document.getElementById("navStep2").disabled = true;
      document.getElementById("navStep3").disabled = true;
      document.getElementById("step1SuccessBanner").style.display = "none";
    }
  });

  // Botón Aceptar ONU (Paso 1)
  document.getElementById("btnStep1Accept").addEventListener("click", step1AcceptOnu);
  document.getElementById("btnGoToStep2").addEventListener("click", () => goToStep(2));

  // Botón Copiar MAC (Paso 2)
  const btnCopyStep2Mac = document.getElementById("btnCopyStep2Mac");
  if (btnCopyStep2Mac) {
    btnCopyStep2Mac.addEventListener("click", () => {
      const mac = document.getElementById("step2LearnedMac").innerText.trim();
      if (mac && mac !== "--:--:--:--:--:--") {
        navigator.clipboard.writeText(mac).then(() => {
          showToast(`MAC copiada al portapapeles: ${mac}`, "info");
        }).catch(() => {
          showToast(`MAC: ${mac}`, "info");
        });
      }
    });
  }

  // Botón Consultar MAC ahora (Paso 2)
  const btnRetryMacNow = document.getElementById("btnRetryMacNow");
  if (btnRetryMacNow) {
    btnRetryMacNow.addEventListener("click", () => {
      const sn = sessionData.sn || document.getElementById("onuSn").value.trim().toUpperCase();
      if (sn) {
        showToast("Consultando MAC en SmartOLT...", "info");
        checkMacNow(sn);
      } else {
        showToast("No se ha definido el serial PON", "warning");
      }
    });
  }

  // Botón Refrescar Historial
  const btnRefreshHistory = document.getElementById("btnRefreshHistory");
  if (btnRefreshHistory) {
    btnRefreshHistory.addEventListener("click", async () => {
      await loadHistory();
      showToast("Historial actualizado", "info");
    });
  }

  // Buscador interactivo de Perfiles DBA (Paso 1)
  const dbaSearchInput = document.getElementById("dbaSearchInput");
  const dbaDropdownList = document.getElementById("dbaDropdownList");
  const btnToggleDbaList = document.getElementById("btnToggleDbaList");

  dbaSearchInput.addEventListener("focus", () => {
    renderDbaList(filterDbaProfiles(dbaSearchInput.value));
    dbaDropdownList.style.display = "block";
  });

  dbaSearchInput.addEventListener("input", () => {
    renderDbaList(filterDbaProfiles(dbaSearchInput.value));
    dbaDropdownList.style.display = "block";
  });

  btnToggleDbaList.addEventListener("click", () => {
    if (dbaDropdownList.style.display === "block") {
      dbaDropdownList.style.display = "none";
    } else {
      renderDbaList(filterDbaProfiles(dbaSearchInput.value));
      dbaDropdownList.style.display = "block";
    }
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".dba-combobox-wrapper")) {
      dbaDropdownList.style.display = "none";
    }
  });

  // Botón Volver a Paso 1
  document.getElementById("btnBackToStep1").addEventListener("click", () => goToStep(1));

  // Botón Diagnosticar / Consultar ONU (Paso 2)
  document.getElementById("btnProbe").addEventListener("click", () => {
    const ip = document.getElementById("onuIp").value.trim();
    if (ip) probeOnu(ip);
    else showToast("Ingrese la dirección IP de la ONU", "warning");
  });

  // Buscador de VLANs según HUB (Paso 2)
  const vlanSearchInput = document.getElementById("vlanSearchInput");
  const vlanDropdownList = document.getElementById("vlanDropdownList");
  const btnToggleVlanList = document.getElementById("btnToggleVlanList");

  vlanSearchInput.addEventListener("focus", () => {
    const currentVlan = document.getElementById("targetVlan").value;
    const currentSelected = vlanCatalog.find(v => String(v.vlan) === currentVlan);
    if (currentSelected && vlanSearchInput.value === currentSelected.label) {
      renderVlanList(vlanCatalog);
    } else {
      renderVlanList(filterVlans(vlanSearchInput.value));
    }
    vlanDropdownList.style.display = "block";
    vlanSearchInput.select();
  });

  vlanSearchInput.addEventListener("input", () => {
    renderVlanList(filterVlans(vlanSearchInput.value));
    vlanDropdownList.style.display = "block";
  });

  btnToggleVlanList.addEventListener("click", (e) => {
    e.stopPropagation();
    if (vlanDropdownList.style.display === "block") {
      vlanDropdownList.style.display = "none";
    } else {
      renderVlanList(vlanCatalog);
      vlanDropdownList.style.display = "block";
      vlanSearchInput.focus();
      vlanSearchInput.select();
    }
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".vlan-combobox-wrapper")) {
      vlanDropdownList.style.display = "none";
    }
  });

  // Generador de clave segura Wi-Fi
  document.getElementById("btnGenPass").addEventListener("click", () => {
    const pass = generateSecurePassword();
    document.getElementById("pass2g").value = pass;
    document.getElementById("pass5g").value = pass;
    showToast("Contraseña segura generada para ambas bandas", "info");
  });

  // Clonar 2.4G a 5G
  document.getElementById("btnCloneTo5G").addEventListener("click", () => {
    const ssid2g = document.getElementById("ssid2g").value.trim();
    const pass2g = document.getElementById("pass2g").value.trim();
    if (ssid2g) {
      document.getElementById("ssid5g").value = ssid2g.endsWith("_5G") ? ssid2g : `${ssid2g}_5G`;
    }
    if (pass2g) {
      document.getElementById("pass5g").value = pass2g;
    }
    showToast("Configuración 2.4G clonada a 5G con sufijo '_5G'", "info");
  });

  // Botón Configurar Router ONU (Paso 2)
  document.getElementById("btnStep2Configure").addEventListener("click", step2ConfigureOnu);
  document.getElementById("btnGoToStep3").addEventListener("click", () => goToStep(3));

  // Botón Volver a Paso 2
  document.getElementById("btnBackToStep2").addEventListener("click", () => goToStep(2));

  // Botón Liberar ONU en SmartOLT (Paso 3)
  document.getElementById("btnStep3Release").addEventListener("click", step3ReleaseOnu);

  // Botón Aprovisionar Siguiente ONU
  document.getElementById("btnRestartWizard").addEventListener("click", restartWizard);

  // Modal SmartOLT
  const smartOltModal = document.getElementById("smartOltModal");
  document.getElementById("btnOpenSmartOltModal").addEventListener("click", () => {
    smartOltModal.style.display = "flex";
  });
  document.getElementById("btnCloseSmartOltModal").addEventListener("click", () => {
    smartOltModal.style.display = "none";
  });

  document.getElementById("btnSaveSmartOltKey").addEventListener("click", async () => {
    if (currentUser.role === "lectura") {
      showToast("Operación no permitida en modo Solo Lectura", "warning");
      return;
    }
    const key = document.getElementById("smartOltKey").value.trim();
    const url = document.getElementById("smartOltUrl").value.trim();
    if (!key) {
      showToast("Por favor ingrese la clave de API de SmartOLT", "warning");
      return;
    }
    try {
      const res = await apiFetch("/api/smartolt/config", {
        method: "POST",
        body: JSON.stringify({ api_key: key, base_url: url })
      });
      const data = await res.json();
      if (data.success) {
        showToast("Configuración de SmartOLT guardada con éxito", "success");
        smartOltModal.style.display = "none";
        loadSmartOltProfiles();
      } else {
        showToast(data.error || "Error al guardar", "danger");
      }
    } catch (e) {
      showToast(`Error de conexión: ${e.message}`, "danger");
    }
  });

  // Modal Panel de Administrador
  const adminModal = document.getElementById("adminModal");
  document.getElementById("btnOpenAdminModal").addEventListener("click", () => {
    adminModal.style.display = "flex";
    loadAdminUsers();
    loadAdminIps();
  });
  document.getElementById("btnCloseAdminModal").addEventListener("click", () => {
    adminModal.style.display = "none";
  });

  // Pestañas del Panel Admin
  document.querySelectorAll(".admin-tab-btn").forEach(tabBtn => {
    tabBtn.addEventListener("click", () => {
      document.querySelectorAll(".admin-tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".admin-tab-content").forEach(c => c.classList.remove("active"));
      tabBtn.classList.add("active");
      const target = tabBtn.dataset.tab;
      document.getElementById(target).classList.add("active");
    });
  });

  // Crear usuario en panel admin
  document.getElementById("btnCreateUser").addEventListener("click", createAdminUser);

  // Agregar IP a lista blanca
  document.getElementById("btnAddIp").addEventListener("click", addIpTag);
  document.getElementById("btnSaveIps").addEventListener("click", saveAdminIps);

  // Refrescar historial
  document.getElementById("btnRefreshHistory").addEventListener("click", loadHistory);
}

// =============================================================================
// NAVEGACIÓN ENTRE PASOS (WIZARD)
// =============================================================================
function goToStep(step) {
  if (step === 2 && !step1Done) {
    showToast("Debe completar el Paso 1 (Aceptar ONU en SmartOLT) primero", "warning");
    return;
  }
  if (step === 3 && !step2Done) {
    showToast("Debe completar el Paso 2 (Configurar Router ONU) primero", "warning");
    return;
  }

  currentWizardStep = step;

  document.querySelectorAll(".wizard-panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".wizard-step-btn").forEach(b => b.classList.remove("active"));

  const panel = document.getElementById(`panelStep${step}`);
  const navBtn = document.getElementById(`navStep${step}`);

  if (panel) panel.classList.add("active");
  if (navBtn) {
    navBtn.classList.add("active");
    navBtn.disabled = false;
  }

  if (step === 2) {
    const targetSn = sessionData.sn || document.getElementById("onuSn").value.trim().toUpperCase();
    if (targetSn && !sessionData.mac) {
      startMacPolling(targetSn);
    } else if (sessionData.mac) {
      setLearnedMac(sessionData.mac);
    }
    fetchFlasheoTraceability(targetSn || sessionData.mac);
  } else if (step === 3) {
    updateStep3Summary();
    stopMacPolling();
  }
}

function updateWizardNavBadges() {
  const btn2 = document.getElementById("navStep2");
  const btn3 = document.getElementById("navStep3");
  if (step1Done) btn2.disabled = false;
  if (step2Done) btn3.disabled = false;
}

// =============================================================================
// PASO 1: DETECCIÓN, BUSCADOR DBA Y ACEPTACIÓN EN SMARTOLT (VLAN 3)
// =============================================================================
async function detectUnconfiguredSmartOlt() {
  const btn = document.getElementById("btnDetectUnconfigured");
  btn.disabled = true;
  btn.innerHTML = '⏳ Escaneando...';
  appendLog("[Paso 1] Consultando ONUs no configuradas en SmartOLT (filtrando solo VSOL)...", "info");

  try {
    const res = await apiFetch("/api/smartolt/unconfigured");
    const data = await res.json();
    btn.disabled = false;
    btn.innerHTML = '📡 Detectar';

    if (data.success && data.onus && data.onus.length > 0) {
      const onu = data.onus[0];
      const snVal = onu.sn || onu.serial_number || "";
      document.getElementById("onuSn").value = snVal;
      sessionData.sn = snVal;
      if (onu.olt_id) {
        sessionData.olt_id = onu.olt_id;
        sessionData.olt_name = onu.olt_name || "";
        loadVlansCatalog(onu.olt_id);
      }

      const modelVal = onu.onu_type_name || onu.model || "VSOLVD64";
      document.getElementById("diagModel").innerText = modelVal;
      document.getElementById("diagPon").innerText = snVal;

      const infoText = `Detectada ONU VSOL: <strong>${snVal}</strong> (${modelVal}) en OLT: <strong>${onu.olt_name || onu.olt_id || 'Chasis 01'}</strong> Board: ${onu.board} / Port: ${onu.port}`;
      document.getElementById("step1StatusBox").innerHTML = `🟢 ${infoText}`;
      appendLog(`[Paso 1] ${infoText.replace(/<[^>]*>?/gm, '')}`, "ok");
      showToast(`ONU VSOL detectada en SmartOLT: ${snVal}`, "success");
    } else {
      const discarded = (data.total_raw && data.total_raw > 0) ? ` (se descartaron ${data.total_raw} equipos de otros fabricantes/modelos no VSOL)` : '';
      document.getElementById("step1StatusBox").innerHTML = `⚠️ No se encontraron ONUs VSOL no configuradas en SmartOLT${discarded}.`;
      appendLog(`[Paso 1] No se encontraron ONUs VSOL pendientes en SmartOLT${discarded}.`, "warning");
      showToast("No hay ONUs VSOL pendientes detectadas en SmartOLT", "warning");
    }
  } catch (e) {
    btn.disabled = false;
    btn.innerHTML = '📡 Detectar';
    showToast(`Error al consultar SmartOLT: ${e.message}`, "danger");
  }
}

// Lógica del Buscador de Perfiles DBA
function filterDbaProfiles(query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return dbaProfilesCatalog;
  return dbaProfilesCatalog.filter(p => {
    const name = (p.name || p.id || "").toLowerCase();
    return name.includes(q);
  });
}

function renderDbaList(items) {
  const listEl = document.getElementById("dbaDropdownList");
  listEl.innerHTML = "";

  if (!items || items.length === 0) {
    listEl.innerHTML = '<div style="padding: 12px; color: var(--text-muted); font-size: 13px; text-align: center;">No se encontraron perfiles</div>';
    return;
  }

  items.forEach(p => {
    const div = document.createElement("div");
    div.className = "dba-item";
    const currentSelected = document.getElementById("dbaProfile").value;
    if (currentSelected === p.name) {
      div.classList.add("selected");
    }

    div.innerHTML = `
      <div>
        <span style="font-weight: 600; color: #fff;">${p.name}</span>
        ${p.speed ? `<span style="font-size: 11px; color: #94a3b8; margin-left: 6px;">(${p.speed} kbps)</span>` : ""}
      </div>
      <span class="badge badge-step" style="font-size: 10px;">${p.direction || 'Simétrico'}</span>
    `;

    div.addEventListener("click", () => {
      selectDbaProfile(p);
      listEl.style.display = "none";
    });

    listEl.appendChild(div);
  });
}

function selectDbaProfile(p) {
  sessionData.dba_profile = p.name;
  document.getElementById("dbaProfile").value = p.name;
  document.getElementById("dbaSearchInput").value = p.name;
  document.getElementById("dbaSelectedText").innerText = p.name;
}

async function loadSmartOltProfiles() {
  try {
    const res = await apiFetch("/api/smartolt/profiles");
    const data = await res.json();
    if (data.success) {
      dbaProfilesCatalog = data.dba_profiles || data.speed_profiles || [];
      if (dbaProfilesCatalog.length > 0) {
        // Seleccionar primer perfil si no hay uno seleccionado
        const defaultProfile = dbaProfilesCatalog.find(p => p.name === "100M") || dbaProfilesCatalog[0];
        selectDbaProfile(defaultProfile);
      }
    }
  } catch (e) {
    console.warn("No se pudieron cargar los perfiles de SmartOLT:", e.message);
  }
}

async function step1AcceptOnu() {
  if (currentUser.role === "lectura") {
    showToast("Operación denegada en modo Solo Lectura", "warning");
    return;
  }

  const sn = document.getElementById("onuSn").value.trim().toUpperCase();
  const name = document.getElementById("onuName").value.trim() || "Configurada manualmente";
  const dba = document.getElementById("dbaProfile").value.trim() || document.getElementById("dbaSearchInput").value.trim();

  if (!sn) {
    showToast("Ingrese el número de serie PON (SN)", "warning");
    document.getElementById("onuSn").focus();
    return;
  }
  if (!name) {
    showToast("Ingrese el nombre descriptivo de la ONU", "warning");
    document.getElementById("onuName").focus();
    return;
  }
  if (!dba) {
    showToast("Seleccione el perfil de velocidad / DBA", "warning");
    document.getElementById("dbaSearchInput").focus();
    return;
  }

  const btn = document.getElementById("btnStep1Accept");
  btn.disabled = true;
  btn.innerHTML = '⏳ Aceptando y Verificando en SmartOLT...';

  clearTerminal();
  appendLog(`[Paso 1] Autorizando ONU ${sn} en SmartOLT con VLAN 3 y Perfil ${dba}...`, "info");
  updateProgress(15);

  try {
    const res = await apiFetch("/api/smartolt/authorize", {
      method: "POST",
      body: JSON.stringify({ sn, name, dba_profile: dba })
    });

    const data = await res.json();
    btn.disabled = false;
    btn.innerHTML = '✅ Aceptar ONU';

    if (data.success) {
      step1Done = true;
      sessionData.sn = sn;
      sessionData.name = name;
      sessionData.dba_profile = dba;

      updateWizardNavBadges();
      appendLog(`[Paso 1] ¡ONU ${sn} autorizada exitosamente en SmartOLT con VLAN 3!`, "ok");
      updateProgress(35);

      document.getElementById("step1SuccessBanner").style.display = "block";
      document.getElementById("step1SummaryText").innerHTML = 
        `Serial PON: <strong>${sn}</strong> | Nombre: <strong>${name}</strong> | VLAN: <strong>3 (Confirmada)</strong> | Plan: <strong>${dba}</strong>`;

      showToast("Paso 1 completado: ONU aceptada en VLAN 3 ✅", "success");

      // Consultar telemetría y MAC en VLAN 3
      fetchSmartOltStatus(sn);
      fetchLearnedMac(sn);

    } else {
      appendLog(`[Paso 1] Error: ${data.error}`, "error");
      showToast(data.error || "Fallo al autorizar ONU en SmartOLT", "danger");
    }
  } catch (e) {
    btn.disabled = false;
    btn.innerHTML = '✅ Aceptar ONU';
    appendLog(`[Paso 1] Error de conexión: ${e.message}`, "error");
    showToast(`Error de conexión: ${e.message}`, "danger");
  }
}

// =============================================================================
// PASO 2: CATÁLOGO DE VLANS, BUSCADOR HUB Y CONFIGURACIÓN ROUTER
// =============================================================================
async function loadVlansCatalog(oltId = null) {
  try {
    const url = oltId ? `/api/vlans/catalog?olt_id=${encodeURIComponent(oltId)}` : "/api/vlans/catalog";
    const res = await apiFetch(url);
    const data = await res.json();
    if (data.success && (data.catalog || data.vlans)) {
      vlanCatalog = data.catalog || data.vlans || [];
      if (vlanCatalog.length > 0) {
        const exists = vlanCatalog.find(v => String(v.vlan) === String(sessionData.target_vlan));
        if (exists) {
          selectVlan(exists);
        } else if (!sessionData.target_vlan) {
          selectVlan(vlanCatalog[0]);
        }
      }
    }
  } catch (e) {
    console.warn("No se pudo cargar el catálogo de VLANs:", e.message);
  }
}

function filterVlans(query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return vlanCatalog;
  return vlanCatalog.filter(item => {
    const hub = (item.hub || "").toLowerCase();
    const vlan = String(item.vlan || "").toLowerCase();
    const desc = (item.description || "").toLowerCase();
    const label = (item.label || "").toLowerCase();
    const olt = (item.olt_name || "").toLowerCase();
    return hub.includes(q) || vlan.includes(q) || desc.includes(q) || label.includes(q) || olt.includes(q);
  });
}

function renderVlanList(items) {
  const listEl = document.getElementById("vlanDropdownList");
  listEl.innerHTML = "";

  if (!items || items.length === 0) {
    listEl.innerHTML = '<div style="padding: 12px; color: var(--text-muted); font-size: 13px; text-align: center;">No se encontraron VLANs o planes con ese criterio</div>';
    return;
  }

  items.forEach(item => {
    const div = document.createElement("div");
    div.className = "vlan-option-item";
    const badgeClass = item.available <= 5 ? "vlan-badge-full" : "vlan-badge-available";
    const currentSelected = document.getElementById("targetVlan").value;
    if (currentSelected === String(item.vlan)) {
      div.classList.add("selected");
    }

    div.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 3px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="vlan-opt-title">${item.label}</span>
          ${item.description ? `<span class="vlan-plan-tag">${item.description}</span>` : ''}
        </div>
        <div class="vlan-opt-subtitle">
          VLAN ID: <strong>${item.vlan}</strong>
          ${item.olt_name ? ` • OLT: ${item.olt_name}` : ''}
        </div>
      </div>
      <div class="vlan-badge-count ${badgeClass}">
        Usada: ${item.used} veces (${item.available} disp.)
      </div>
    `;

    div.addEventListener("click", () => {
      selectVlan(item);
      listEl.style.display = "none";
    });

    listEl.appendChild(div);
  });
}

function selectVlan(item) {
  sessionData.target_vlan = item.vlan;
  sessionData.hub_name = item.hub;
  document.getElementById("targetVlan").value = item.vlan;
  document.getElementById("vlanSearchInput").value = item.label || `${item.vlan} - ${item.description || item.hub}`;

  const banner = document.getElementById("vlanSelectedBanner");
  banner.style.display = "flex";
  document.getElementById("vlanSelectedHubName").innerText = item.description ? `Plan / Nombre: ${item.description}` : item.hub;
  document.getElementById("vlanSelectedBadge").innerText = `VLAN ${item.vlan}`;
  document.getElementById("vlanSelectedUsage").innerText = `Usada: ${item.used} veces (${item.available} de ${item.max_capacity} disponibles)`;
}

async function step2ConfigureOnu() {
  if (currentUser.role === "lectura") {
    showToast("Operación denegada en modo Solo Lectura", "warning");
    return;
  }

  const ip = document.getElementById("onuIp").value.trim();
  let vlan = document.getElementById("targetVlan").value.trim();
  const searchVal = document.getElementById("vlanSearchInput").value.trim();
  const ssid2g = document.getElementById("ssid2g").value.trim();
  const pass2g = document.getElementById("pass2g").value.trim();
  const ssid5g = document.getElementById("ssid5g").value.trim();
  const pass5g = document.getElementById("pass5g").value.trim();

  // Si el usuario escribió un número de VLAN manual
  if (!vlan && /^\d+$/.test(searchVal)) {
    vlan = searchVal;
    sessionData.target_vlan = vlan;
    sessionData.hub_name = `VLAN ${vlan}`;
  }

  const isNoWifi = (sessionData.has_wifi === false);

  if (!ip) {
    showToast("Ingrese la dirección IP de gestión de la ONU", "warning");
    document.getElementById("onuIp").focus();
    return;
  }
  if (!vlan) {
    showToast("Seleccione o ingrese la nueva VLAN según el HUB correspondiente", "warning");
    document.getElementById("vlanSearchInput").focus();
    return;
  }

  if (!isNoWifi) {
    if (!ssid2g) {
      showToast("Ingrese el nombre de la red Wi-Fi 2.4 GHz (SSID)", "warning");
      document.getElementById("ssid2g").focus();
      return;
    }
    if (!pass2g || pass2g.length < 8) {
      showToast("La contraseña Wi-Fi 2.4G debe tener al menos 8 caracteres", "warning");
      document.getElementById("pass2g").focus();
      return;
    }
  }

  const finalSsid2g = isNoWifi ? "N/A" : ssid2g;
  const finalPass2g = isNoWifi ? "N/A" : pass2g;
  const finalSsid5g = isNoWifi ? "N/A" : ssid5g;
  const finalPass5g = isNoWifi ? "N/A" : pass5g;

  const btn = document.getElementById("btnStep2Configure");
  btn.disabled = true;
  btn.innerHTML = '⚡ Configurando Router ONU...';

  clearTerminal();
  appendLog(`[Paso 2] Iniciando configuración de router en ${ip} con VLAN ${vlan}...`, "info");
  updateProgress(45);

  try {
    const res = await apiFetch("/api/provision/onu_only", {
      method: "POST",
      body: JSON.stringify({
        ip,
        vlan,
        ssid_2g: finalSsid2g,
        pass_2g: finalPass2g,
        ssid_5g: finalSsid5g,
        pass_5g: finalPass5g,
        sn: sessionData.sn,
        mac: sessionData.mac,
        has_wifi: !isNoWifi
      })
    });

    const data = await res.json();
    if (data.success && data.job_id) {
      pollJob(data.job_id, (result) => {
        btn.disabled = false;
        btn.innerHTML = '⚡ Configurar ONU';
        
        step2Done = true;
        sessionData.ip = ip;
        sessionData.target_vlan = vlan;
        sessionData.ssid_2g = ssid2g;
        sessionData.pass_2g = pass2g;
        sessionData.ssid_5g = ssid5g;
        sessionData.pass_5g = pass5g;

        updateWizardNavBadges();
        updateProgress(75);
        document.getElementById("step2SuccessBanner").style.display = "block";
        showToast("Paso 2 completado: Router ONU configurado con éxito ✅", "success");

      }, (error) => {
        btn.disabled = false;
        btn.innerHTML = '⚡ Configurar ONU';
        showToast(`Error al configurar la ONU: ${error}`, "danger");
      });
    } else {
      btn.disabled = false;
      btn.innerHTML = '⚡ Configurar ONU';
      showToast(data.error || "Fallo al iniciar configuración", "danger");
    }
  } catch (e) {
    btn.disabled = false;
    btn.innerHTML = '⚡ Configurar ONU';
    showToast(`Error de conexión: ${e.message}`, "danger");
  }
}

// =============================================================================
// PASO 3: LIBERACIÓN EN SMARTOLT (RETORNAR A DESCONFIGURADAS PARA RUBPI)
// =============================================================================
function updateStep3Summary() {
  document.getElementById("summaryPon").innerText = sessionData.sn || "--";
  document.getElementById("summaryName").innerText = sessionData.name || "--";
  const hubTitle = sessionData.hub_name ? ` (${sessionData.hub_name})` : "";
  document.getElementById("summaryTargetVlan").innerText = `VLAN ${sessionData.target_vlan}${hubTitle}`;
}

async function step3ReleaseOnu() {
  if (currentUser.role === "lectura") {
    showToast("Operación denegada en modo Solo Lectura", "warning");
    return;
  }

  const sn = sessionData.sn;
  const targetVlan = sessionData.target_vlan;
  const btn = document.getElementById("btnStep3Release");

  if (!sn) {
    showToast("Falta el serial PON para liberar la ONU", "danger");
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '⏳ Liberando ONU en SmartOLT...';
  appendLog(`[Paso 3] Solicitando a SmartOLT la eliminación/liberación de la ONU ${sn}...`, "info");
  updateProgress(85);

  try {
    const res = await apiFetch("/api/smartolt/release_onu", {
      method: "POST",
      body: JSON.stringify({
        sn,
        target_vlan: targetVlan,
        ip: sessionData.ip,
        mac: sessionData.mac,
        ssid_2g: sessionData.ssid_2g,
        ssid_5g: sessionData.ssid_5g
      })
    });

    const data = await res.json();
    btn.disabled = false;
    btn.innerHTML = '🗑️ Liberar ONU en SmartOLT (Retornar a Desconfiguradas)';

    if (data.success) {
      step3Done = true;
      updateWizardNavBadges();
      updateProgress(100);
      appendLog(`[Paso 3] ¡ONU ${sn} liberada con éxito en SmartOLT! Lista para el sistema Rubpi.`, "ok");

      document.getElementById("step3CompleteCard").style.display = "block";
      document.getElementById("step3FinalDetails").innerText = 
        `La ONU ${sn} ha quedado configurada con la VLAN ${targetVlan} y fue liberada de SmartOLT. Ya aparece como pendiente/no configurada para su aprovisionamiento en Rubpi.`;
      
      showToast("¡ONU liberada exitosamente para aprovisionamiento por Rubpi! 🎉", "success");

      // Actualizar catálogos e historial
      await loadVlansCatalog();
      await loadHistory();

    } else {
      appendLog(`[Paso 3] Error en SmartOLT: ${data.error}`, "error");
      showToast(data.error || "Fallo al liberar la ONU en SmartOLT", "danger");
    }
  } catch (e) {
    btn.disabled = false;
    btn.innerHTML = '🗑️ Liberar ONU en SmartOLT (Retornar a Desconfiguradas)';
    showToast(`Error de conexión: ${e.message}`, "danger");
  }
}

function restartWizard() {
  step1Done = false;
  step2Done = false;
  step3Done = false;

  sessionData = {
    sn: "",
    name: "Configurada manualmente",
    dba_profile: "100M",
    ip: "3.3.",
    target_vlan: "100",
    hub_name: "",
    ssid_2g: "",
    pass_2g: "",
    ssid_5g: "",
    pass_5g: "",
    mac: "",
    model: ""
  };

  document.getElementById("onuSn").value = "";
  document.getElementById("onuName").value = "Configurada manualmente";
  document.getElementById("onuIp").value = "3.3.";
  document.getElementById("ssid2g").value = "";
  document.getElementById("pass2g").value = "";
  document.getElementById("ssid5g").value = "";
  document.getElementById("pass5g").value = "";

  document.getElementById("step1SuccessBanner").style.display = "none";
  document.getElementById("step2SuccessBanner").style.display = "none";
  document.getElementById("step3CompleteCard").style.display = "none";

  document.getElementById("navStep2").disabled = true;
  document.getElementById("navStep3").disabled = true;

  updateProgress(0);
  goToStep(1);
  showToast("Asistente reiniciado. Listo para una nueva ONU.", "info");
}

// =============================================================================
// ADMINISTRACIÓN: USUARIOS Y FILTRO DE IPS
// =============================================================================
async function loadAdminUsers() {
  const tbody = document.getElementById("usersTableBody");
  tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">Cargando usuarios...</td></tr>';

  try {
    const res = await apiFetch("/api/auth/users");
    const data = await res.json();
    if (data.success && data.users) {
      tbody.innerHTML = "";
      data.users.forEach(u => {
        const tr = document.createElement("tr");
        const roleBadge = u.role === "admin" ? "badge-role-admin" : (u.role === "aprovisionador" ? "badge-role-aprovisionador" : "badge-role-lectura");
        const isSelfOrRoot = (u.username === "admin" || u.username === currentUser.username);

        tr.innerHTML = `
          <td><strong>${u.username}</strong></td>
          <td><span class="badge ${roleBadge}">${u.role.toUpperCase()}</span></td>
          <td style="color: var(--text-muted); font-size: 12px;">${u.created_at || '--'}</td>
          <td>
            ${isSelfOrRoot ? '<span style="color: var(--text-muted); font-size: 11px;">Protegido</span>' : `<button type="button" class="btn btn-danger btn-sm" onclick="deleteAdminUser('${u.username}')">🗑️ Eliminar</button>`}
          </td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4" style="color: #ef4444; text-align: center;">Error al cargar usuarios: ${e.message}</td></tr>`;
  }
}

async function createAdminUser() {
  const u = document.getElementById("newUsername").value.trim();
  const p = document.getElementById("newPassword").value.trim();
  const r = document.getElementById("newUserRole").value;

  if (!u || !p) {
    showToast("Ingrese usuario y contraseña", "warning");
    return;
  }

  try {
    const res = await apiFetch("/api/auth/users", {
      method: "POST",
      body: JSON.stringify({ username: u, password: p, role: r })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, "success");
      document.getElementById("newUsername").value = "";
      document.getElementById("newPassword").value = "";
      loadAdminUsers();
    } else {
      showToast(data.error || "Fallo al crear usuario", "danger");
    }
  } catch (e) {
    showToast(`Error: ${e.message}`, "danger");
  }
}

async function deleteAdminUser(username) {
  if (!confirm(`¿Está seguro de eliminar al usuario '${username}'?`)) return;

  try {
    const res = await apiFetch(`/api/auth/users/${username}`, {
      method: "DELETE"
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, "success");
      loadAdminUsers();
    } else {
      showToast(data.error || "Fallo al eliminar usuario", "danger");
    }
  } catch (e) {
    showToast(`Error: ${e.message}`, "danger");
  }
}

async function loadAdminIps() {
  try {
    const res = await apiFetch("/api/auth/ips");
    const data = await res.json();
    if (data.success) {
      currentIpWhitelist = data.ip_whitelist || [];
      renderIpTags();
    }
  } catch (e) {
    console.warn("Error al cargar lista blanca de IPs:", e.message);
  }
}

function renderIpTags() {
  const container = document.getElementById("ipTagsContainer");
  const notice = document.getElementById("ipEmptyNotice");
  container.innerHTML = "";

  if (currentIpWhitelist.length === 0) {
    notice.style.display = "block";
    return;
  }
  notice.style.display = "none";

  currentIpWhitelist.forEach((ip, idx) => {
    const tag = document.createElement("span");
    tag.className = "ip-tag";
    tag.innerHTML = `
      <span>${ip}</span>
      <button type="button" class="ip-tag-remove" onclick="removeIpTag(${idx})">✕</button>
    `;
    container.appendChild(tag);
  });
}

function addIpTag() {
  const input = document.getElementById("newIpInput");
  const val = input.value.trim();
  if (!val) return;
  if (!currentIpWhitelist.includes(val)) {
    currentIpWhitelist.push(val);
    renderIpTags();
  }
  input.value = "";
}

function removeIpTag(idx) {
  currentIpWhitelist.splice(idx, 1);
  renderIpTags();
}

async function saveAdminIps() {
  try {
    const res = await apiFetch("/api/auth/ips", {
      method: "POST",
      body: JSON.stringify({ ip_whitelist: currentIpWhitelist })
    });
    const data = await res.json();
    if (data.success) {
      showToast("Configuración de IPs guardada exitosamente", "success");
    } else {
      showToast(data.error || "Error al guardar IPs", "danger");
    }
  } catch (e) {
    showToast(`Error: ${e.message}`, "danger");
  }
}

// =============================================================================
// DIAGNÓSTICO & SONDEO DE SMARTOLT
// =============================================================================
let macCountdownTimer = null;
let macCountdownSeconds = 5;
let isMacPollingActive = false;

function applyWifiVisibility(hasWifi, modelName) {
  sessionData.has_wifi = (hasWifi !== false);
  const wifiCard = document.getElementById("wifiConfigCard");
  const noWifiCard = document.getElementById("noWifiNoticeCard");
  const modelBadge = document.getElementById("noWifiModelBadge");
  const ssid2g = document.getElementById("ssid2g");
  const pass2g = document.getElementById("pass2g");

  if (hasWifi === false) {
    if (wifiCard) wifiCard.style.display = "none";
    if (noWifiCard) noWifiCard.style.display = "block";
    if (modelBadge && modelName) modelBadge.innerText = modelName;
    if (ssid2g) ssid2g.removeAttribute("required");
    if (pass2g) pass2g.removeAttribute("required");
  } else {
    if (wifiCard) wifiCard.style.display = "block";
    if (noWifiCard) noWifiCard.style.display = "none";
    if (ssid2g) ssid2g.setAttribute("required", "required");
    if (pass2g) pass2g.setAttribute("required", "required");
  }
}

function setLearnedMac(mac, ip, hasWifi, model) {
  if (!mac || mac === "--:--:--:--:--:--") return;
  sessionData.mac = mac;
  stopMacPolling();

  const lbl2 = document.getElementById("step2LearnedMac");
  const card = document.getElementById("step2MacCard");
  const waitingText = document.getElementById("step2MacWaitingText");
  const spinner = document.getElementById("step2MacSpinner");
  const copyBtn = document.getElementById("btnCopyStep2Mac");
  const diagMac = document.getElementById("diagMac");

  if (card) card.style.display = "block";
  if (waitingText) waitingText.style.display = "none";
  if (spinner) spinner.style.display = "none";
  if (lbl2) {
    lbl2.innerText = mac;
    lbl2.style.display = "block";
  }
  if (copyBtn) copyBtn.style.display = "inline-flex";
  if (diagMac) diagMac.innerText = mac;

  // Auto-completar IP si está disponible
  if (ip && ip !== "0.0.0.0" && ip !== "N/A") {
    const elIp = document.getElementById("onuIp");
    if (elIp) {
      elIp.value = ip;
      sessionData.ip = ip;
    }
  }

  // Discriminar Wi-Fi
  if (typeof hasWifi === "boolean") {
    applyWifiVisibility(hasWifi, model || sessionData.model);
  }

  appendLog(`[SmartOLT] MAC detectada en VLAN 3: ${mac}${ip ? ` | IP WAN: ${ip}` : ''}`, "ok");
  fetchFlasheoTraceability(mac);
}

async function fetchFlasheoTraceability(query) {
  if (!query || query === "--:--:--:--:--:--") return;
  try {
    const res = await apiFetch(`/api/flasheo/onu_traceability?query=${encodeURIComponent(query)}`);
    const data = await res.json();
    const card = document.getElementById("step2FlasheoCard");
    if (!card) return;

    if (data && data.encontrado) {
      card.style.display = "block";
      const lote = data.lote || {};
      const creds = data.credenciales || {};
      
      const elLote = document.getElementById("step2FlasheoLote");
      const elCaja = document.getElementById("step2FlasheoCaja");
      const elUser = document.getElementById("step2FlasheoUser");
      const elClave = document.getElementById("step2FlasheoClave");
      const elFw = document.getElementById("step2FlasheoFw");
      const elBadge = document.getElementById("step2FlasheoBadge");

      if (elLote) elLote.innerText = lote.codigo_lote || "Lote S/N";
      if (elCaja) elCaja.innerText = lote.numero_caja || "Caja N/A";
      if (elUser) elUser.innerText = creds.usuario || "Powerlink";
      if (elClave) elClave.innerText = creds.clave || "********";
      if (elFw) elFw.innerText = data.firmware || data.modelo || "Firmware Oficial";
      if (elBadge) {
        const origen = data.origen_datos === "API_REST_8080" ? "API Estación" : "Base de Datos";
        elBadge.innerText = `Sincronizado (${origen})`;
        elBadge.style.background = "#059669";
      }

      appendLog(`[Flasheo] ONU vinculada a ${lote.codigo_lote || 'Lote'} (Caja: ${lote.numero_caja || 'N/A'}). Clave de lote inyectada: ${creds.usuario} / ********`, "ok");
    } else {
      card.style.display = "none";
    }
  } catch (err) {
    console.warn("Error al consultar trazabilidad de flasheo:", err);
  }
}

function startMacPolling(sn) {
  if (!sn) return;
  if (sessionData.mac) {
    setLearnedMac(sessionData.mac, sessionData.ip, sessionData.has_wifi, sessionData.model);
    return;
  }
  if (isMacPollingActive) return;

  isMacPollingActive = true;
  stopMacPolling();

  const card = document.getElementById("step2MacCard");
  const waitingText = document.getElementById("step2MacWaitingText");
  const spinner = document.getElementById("step2MacSpinner");
  const lbl2 = document.getElementById("step2LearnedMac");
  const copyBtn = document.getElementById("btnCopyStep2Mac");
  const countdownEl = document.getElementById("step2MacCountdown");

  if (card) card.style.display = "block";
  if (waitingText) waitingText.style.display = "block";
  if (spinner) spinner.style.display = "inline-block";
  if (lbl2) lbl2.style.display = "none";
  if (copyBtn) copyBtn.style.display = "none";

  macCountdownSeconds = 5;
  if (countdownEl) countdownEl.innerText = `${macCountdownSeconds}s`;

  // Consulta inmediata
  checkMacNow(sn);

  macCountdownTimer = setInterval(async () => {
    macCountdownSeconds--;
    if (countdownEl) countdownEl.innerText = `${macCountdownSeconds}s`;

    if (macCountdownSeconds <= 0) {
      macCountdownSeconds = 5;
      if (countdownEl) countdownEl.innerText = `${macCountdownSeconds}s`;
      await checkMacNow(sn);
    }
  }, 1000);
}

async function checkMacNow(sn) {
  if (!sn) sn = sessionData.sn;
  if (!sn) return false;
  try {
    const res = await apiFetch(`/api/smartolt/mac_vlan3?sn=${encodeURIComponent(sn)}`);
    const data = await res.json();
    
    // Auto-completar IP si se detectó
    if (data.ip && data.ip !== "0.0.0.0" && data.ip !== "N/A") {
      const elIp = document.getElementById("onuIp");
      if (elIp) {
        elIp.value = data.ip;
        sessionData.ip = data.ip;
      }
    }

    // Discriminar Wi-Fi
    if (typeof data.has_wifi === "boolean") {
      applyWifiVisibility(data.has_wifi, data.model || sessionData.model);
    }

    if (data.success && data.mac && data.mac !== "--:--:--:--:--:--") {
      setLearnedMac(data.mac, data.ip, data.has_wifi, data.model);
      showToast(`¡MAC detectada en VLAN 3: ${data.mac}!`, "success");
      return true;
    }
  } catch (e) {
    console.warn("Consulta MAC:", e.message);
  }
  return false;
}

function stopMacPolling() {
  if (macCountdownTimer) {
    clearInterval(macCountdownTimer);
    macCountdownTimer = null;
  }
  isMacPollingActive = false;
}

async function fetchLearnedMac(sn) {
  startMacPolling(sn);
}

async function fetchSmartOltStatus(sn) {
  if (!sn) return;
  try {
    const res = await apiFetch(`/api/smartolt/status?sn=${encodeURIComponent(sn)}`);
    const data = await res.json();
    if (data.success && data.onu) {
      const o = data.onu;
      document.getElementById("diagModel").innerText = o.onu_type_name || o.model || "VSOLVD64";
      document.getElementById("diagPon").innerText = o.sn || sn;
      document.getElementById("diagRx").innerText = o.signal_1490 ? `${o.signal_1490} dBm` : (o.signal || "--");

      if (o.ip && o.ip !== "0.0.0.0" && o.ip !== "N/A") {
        const elIp = document.getElementById("onuIp");
        if (elIp) {
          elIp.value = o.ip;
          sessionData.ip = o.ip;
        }
      }

      if (typeof o.has_wifi === "boolean") {
        applyWifiVisibility(o.has_wifi, o.detected_model || o.onu_type_name || o.model);
      }

      const macVal = o.mac || o.mac_vlan3 || data.mac_vlan3;
      if (macVal && macVal !== "N/A") {
        setLearnedMac(macVal, o.ip, o.has_wifi, o.detected_model || o.onu_type_name);
      }
    }
  } catch (e) {
    console.warn("No se pudo consultar estado de SmartOLT:", e.message);
  }
}

async function probeOnu(ip) {
  appendLog(`[Acceso] Probando conectividad hacia la ONU en ${ip}...`, "info");
  const targetSn = sessionData.sn || document.getElementById("onuSn")?.value?.trim()?.toUpperCase();
  const rawMac = sessionData.mac || document.getElementById("step2LearnedMac")?.innerText?.trim();
  const targetMac = (rawMac && rawMac !== "--:--:--:--:--:--") ? rawMac : undefined;

  try {
    const res = await apiFetch("/api/probe", {
      method: "POST",
      body: JSON.stringify({
        ip,
        sn: targetSn || undefined,
        mac: targetMac
      })
    });
    const data = await res.json();
    if (data.success) {
      appendLog(`[Acceso] Conexión establecida con la ONU en ${ip} (${data.model || 'VSOL'}).`, "ok");
      document.getElementById("diagModel").innerText = data.model || "--";
      document.getElementById("diagMac").innerText = data.mac || "--";
      document.getElementById("diagRx").innerText = data.optical_rx ? `${data.optical_rx} dBm` : "--";
      showToast(`ONU conectada: ${data.model || ip}`, "success");
    } else {
      appendLog(`[Acceso] No se pudo conectar con la ONU en ${ip}: ${data.error}`, "warning");
      showToast(`No se pudo conectar: ${data.error}`, "warning");
    }
  } catch (e) {
    appendLog(`[Acceso] Error de conexión hacia ${ip}: ${e.message}`, "error");
    showToast(`Error de red: ${e.message}`, "danger");
  }
}

// =============================================================================
// SONDEO DE PROGRESO (BACKGROUND JOBS)
// =============================================================================
function pollJob(jobId, onComplete, onError) {
  if (pollInterval) clearInterval(pollInterval);
  activeJobId = jobId;
  let lastLogIndex = 0;

  pollInterval = setInterval(async () => {
    try {
      const res = await apiFetch(`/api/progress?job_id=${jobId}`);
      const data = await res.json();
      if (!data) return;

      const progressVal = data.progress !== undefined ? data.progress : data.pct;
      if (progressVal !== undefined) {
        updateProgress(progressVal);
      }

      if (data.logs && data.logs.length > lastLogIndex) {
        for (let i = lastLogIndex; i < data.logs.length; i++) {
          const l = data.logs[i];
          const msg = l.msg || l.message || l.text || "";
          if (msg) {
            appendLog(msg, l.level || "info");
          }
        }
        lastLogIndex = data.logs.length;
      }

      if (data.status === "completed") {
        clearInterval(pollInterval);
        pollInterval = null;
        if (onComplete) onComplete(data.result);
      } else if (data.status === "failed") {
        clearInterval(pollInterval);
        pollInterval = null;
        if (onError) onError(data.error || "Tarea fallida");
      }
    } catch (e) {
      console.error("Error en sondeo de tarea:", e);
    }
  }, 1000);
}

// =============================================================================
// HISTORIAL & CONFIGURACIÓN
// =============================================================================
async function loadHistory() {
  const tbody = document.getElementById("historyTableBody");
  if (!tbody) return;
  try {
    const res = await apiFetch("/api/history?limit=30");
    const data = await res.json();
    const records = data.records || data.history || [];
    if (data.success && Array.isArray(records)) {
      tbody.innerHTML = "";
      if (records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 20px;">No hay registros históricos aún.</td></tr>';
        return;
      }

      records.forEach(row => {
        const tr = document.createElement("tr");
        const resText = row.Resultado || "";
        let resBadge = "badge-step";
        if (resText.includes("EXITO")) resBadge = "badge-success";
        else if (resText.includes("ERROR") || resText.includes("FALLO")) resBadge = "badge-role-admin";

        tr.innerHTML = `
          <td style="font-size: 12px; color: var(--text-secondary);">${row.FechaHora || '--'}</td>
          <td><span class="badge badge-step" style="font-size: 11px;">👤 ${row.Usuario || 'admin'}</span></td>
          <td><code>${row.IP || '--'}</code></td>
          <td style="font-size: 12px;">${row.PON_Serial || row.MAC || '--'}</td>
          <td><strong style="color: #818cf8;">${row.VLAN ? `VLAN ${row.VLAN}` : '--'}</strong></td>
          <td style="font-size: 12px;">${row.SSID_2G || '--'}</td>
          <td style="font-size: 12px;">${row.SSID_5G || '--'}</td>
          <td><span class="badge ${resBadge}">${resText}</span></td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (e) {
    console.warn("No se pudo cargar el historial:", e.message);
  }
}

async function loadConfig() {
  try {
    const res = await apiFetch("/api/config");
    const data = await res.json();
    if (data.success && data.config) {
      const cfg = data.config;
      if (cfg.smartolt) {
        if (cfg.smartolt.base_url) document.getElementById("smartOltUrl").value = cfg.smartolt.base_url;
        if (cfg.smartolt.api_key) document.getElementById("smartOltKey").value = cfg.smartolt.api_key;
      }
    }
  } catch (e) {
    console.warn("No se pudo cargar configuración inicial:", e.message);
  }
}

// =============================================================================
// UTILIDADES UI: LOGS, PROGRESS Y TOASTS
// =============================================================================
function appendLog(msg, level = "info") {
  const terminal = document.getElementById("terminalLogs");
  const line = document.createElement("div");
  const time = new Date().toTimeString().split(" ")[0];

  let cls = "term-info";
  if (level === "ok" || level === "success") cls = "term-ok";
  else if (level === "warning") cls = "term-warn";
  else if (level === "error" || level === "danger") cls = "term-err";

  line.className = `term-line ${cls}`;
  line.innerHTML = `<span class="term-time">[${time}]</span> ${msg}`;
  terminal.appendChild(line);
  terminal.scrollTop = terminal.scrollHeight;
}

function clearTerminal() {
  document.getElementById("terminalLogs").innerHTML = "";
}

function updateProgress(pct) {
  const bar = document.getElementById("progressBar");
  bar.style.width = `${pct}%`;

  const s1 = document.getElementById("step1");
  const s2 = document.getElementById("step2");
  const s3 = document.getElementById("step3");
  const s4 = document.getElementById("step4");
  const s5 = document.getElementById("step5");

  [s1, s2, s3, s4, s5].forEach(s => s.classList.remove("active", "completed"));

  if (pct >= 15) s1.classList.add("completed"); else s1.classList.add("active");
  if (pct >= 40) s2.classList.add("completed"); else if (pct >= 20) s2.classList.add("active");
  if (pct >= 60) s3.classList.add("completed"); else if (pct >= 45) s3.classList.add("active");
  if (pct >= 80) s4.classList.add("completed"); else if (pct >= 65) s4.classList.add("active");
  if (pct >= 100) s5.classList.add("completed"); else if (pct >= 85) s5.classList.add("active");
}

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerText = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(40px)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function generateSecurePassword(length = 10) {
  const chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*";
  let pass = "";
  for (let i = 0; i < length; i++) {
    pass += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return pass;
}
