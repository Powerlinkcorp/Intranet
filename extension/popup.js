// Configuración Inicial
const DEFAULT_SERVER_URL = 'http://localhost:5000';
let currentServerUrl = DEFAULT_SERVER_URL;
let dbCache = {
    reports: [],
    afectaciones: [],
    techs: [],
    assignments: [],
    motivos: [],
    zonas: [],
    users: [],
    logs: []
};
let activeFilter = 'TODOS';
let activeSearchQuery = '';
let currentUser = null;

// Helper Storage Chrome
async function getCurrentUser() {
    return new Promise((resolve) => {
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.get(['currentUser'], (res) => {
                resolve(res.currentUser || null);
            });
        } else {
            try {
                const raw = localStorage.getItem('currentUser');
                resolve(raw ? JSON.parse(raw) : null);
            } catch (e) {
                resolve(null);
            }
        }
    });
}

async function setCurrentUser(user) {
    currentUser = user;
    return new Promise((resolve) => {
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.set({ currentUser: user }, () => resolve(user));
        } else {
            localStorage.setItem('currentUser', JSON.stringify(user));
            resolve(user);
        }
    });
}

async function clearCurrentUser() {
    currentUser = null;
    return new Promise((resolve) => {
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.remove(['currentUser'], () => resolve());
        } else {
            localStorage.removeItem('currentUser');
            resolve();
        }
    });
}

// Helper Storage Tema (Claro / Oscuro)
async function getThemePreference() {
    return new Promise((resolve) => {
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.get(['appTheme'], (res) => {
                resolve(res.appTheme || 'light');
            });
        } else {
            resolve(localStorage.getItem('appTheme') || 'light');
        }
    });
}

function applyTheme(theme) {
    const isDark = theme === 'dark';
    if (isDark) {
        document.documentElement.setAttribute('data-theme', 'dark');
        if (document.body) {
            document.body.classList.add('theme-dark');
            document.body.classList.remove('theme-light');
        }
    } else {
        document.documentElement.setAttribute('data-theme', 'light');
        if (document.body) {
            document.body.classList.add('theme-light');
            document.body.classList.remove('theme-dark');
        }
    }

    const btnLight = document.getElementById('btnThemeLight');
    const btnDark = document.getElementById('btnThemeDark');
    if (btnLight && btnDark) {
        if (isDark) {
            btnDark.classList.add('active');
            btnLight.classList.remove('active');
        } else {
            btnLight.classList.add('active');
            btnDark.classList.remove('active');
        }
    }
}

async function setThemePreference(theme) {
    applyTheme(theme);
    try {
        localStorage.setItem('appTheme', theme);
    } catch (e) {}
    return new Promise((resolve) => {
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.set({ appTheme: theme }, () => resolve(theme));
        } else {
            resolve(theme);
        }
    });
}

function updateAuthUI(user) {
    const loginSection = document.getElementById('loginSection');
    const appSection = document.getElementById('appSection');
    const userBadge = document.getElementById('userHeaderBadge');
    const userAvatarMini = document.getElementById('userAvatarMini');
    const userNameMini = document.getElementById('userNameMini');
    const userRoleMini = document.getElementById('userRoleMini');

    if (user && user.username) {
        if (loginSection) loginSection.style.display = 'none';
        if (appSection) appSection.style.display = 'flex';
        if (userBadge) userBadge.style.display = 'flex';

        const initial = (user.name || user.username || 'U').charAt(0).toUpperCase();
        if (userAvatarMini) userAvatarMini.textContent = initial;
        if (userNameMini) userNameMini.textContent = user.name || user.username;
        if (userRoleMini) userRoleMini.textContent = (user.role || 'OPERADOR').toUpperCase();
    } else {
        if (loginSection) loginSection.style.display = 'flex';
        if (appSection) appSection.style.display = 'none';
        if (userBadge) userBadge.style.display = 'none';
    }
}

async function getServerUrl() {
    return new Promise((resolve) => {
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.get(['serverUrl'], (res) => {
                resolve(res.serverUrl || DEFAULT_SERVER_URL);
            });
        } else {
            resolve(localStorage.getItem('serverUrl') || DEFAULT_SERVER_URL);
        }
    });
}

async function setServerUrl(url) {
    const cleanUrl = url.trim().replace(/\/+$/, '');
    return new Promise((resolve) => {
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.set({ serverUrl: cleanUrl }, () => resolve(cleanUrl));
        } else {
            localStorage.setItem('serverUrl', cleanUrl);
            resolve(cleanUrl);
        }
    });
}

// UI Toast
function showToast(msg, isError = false) {
    const toast = document.getElementById('toast');
    const toastText = document.getElementById('toastText');
    if (!toast || !toastText) return;

    toastText.textContent = msg;
    toast.className = 'toast show' + (isError ? ' error' : '');
    setTimeout(() => {
        toast.className = 'toast';
    }, 3200);
}

// Actualizar Indicador de Conexión
function setConnectionStatus(online, message = '') {
    const dot = document.getElementById('statusDot');
    const label = document.getElementById('statusLabel');
    if (!dot || !label) return;

    if (online) {
        dot.className = 'status-dot online';
        label.textContent = 'Sistema en línea';
    } else {
        dot.className = 'status-dot offline';
        label.textContent = message || 'Sin conexión';
    }
}

// Cargar Base de Datos
async function fetchDatabase() {
    setConnectionStatus(false, 'Conectando...');
    try {
        const res = await fetch(`${currentServerUrl}/api/db`, { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        dbCache = {
            reports: Array.isArray(data.reports) ? data.reports : [],
            afectaciones: Array.isArray(data.afectaciones) ? data.afectaciones : [],
            techs: Array.isArray(data.techs) ? data.techs : [],
            assignments: Array.isArray(data.assignments) ? data.assignments : [],
            motivos: Array.isArray(data.motivos) ? data.motivos : [],
            zonas: Array.isArray(data.zonas) ? data.zonas : [],
            users: Array.isArray(data.users) ? data.users : [],
            logs: Array.isArray(data.logs) ? data.logs : []
        };

        setConnectionStatus(true);
        populateSelects();
        renderConsultas();
    } catch (err) {
        console.error('Error al conectar con servidor:', err);
        setConnectionStatus(false, 'Desconectado');
        showToast(`No se pudo conectar a ${currentServerUrl}`, true);
    }
}

// Guardar Base de Datos
async function syncDatabase(updatedData, logAction = '', logDetails = '') {
    try {
        if (logAction) {
            const newLog = {
                id: Date.now(),
                timestamp: new Date().toISOString(),
                username: (currentUser && currentUser.username) ? currentUser.username : 'extension',
                action: logAction,
                module: 'EXTENSION',
                details: logDetails
            };
            if (!Array.isArray(updatedData.logs)) updatedData.logs = dbCache.logs || [];
            updatedData.logs.unshift(newLog);
        }

        const res = await fetch(`${currentServerUrl}/api/db`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedData)
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const resp = await res.json();

        // Actualizar caché local
        Object.assign(dbCache, updatedData);
        renderConsultas();
        return true;
    } catch (err) {
        console.error('Error al guardar en el servidor:', err);
        showToast('Error al sincronizar con el servidor', true);
        return false;
    }
}

// Llenar selects de Zonas y Motivos
function populateSelects() {
    const selZona = document.getElementById('sop_zona');
    const selMotivo = document.getElementById('sop_motivo');

    if (selZona) {
        selZona.innerHTML = '<option value="">Seleccionar zona...</option>';
        (dbCache.zonas || []).forEach(z => {
            const opt = document.createElement('option');
            opt.value = z.name;
            opt.textContent = z.name;
            selZona.appendChild(opt);
        });
    }

    if (selMotivo) {
        selMotivo.innerHTML = '<option value="">Seleccionar motivo...</option>';
        (dbCache.motivos || []).forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.name;
            opt.textContent = m.name;
            selMotivo.appendChild(opt);
        });
    }
}

// Determinar el Estatus Efectivo de un Soporte
function getEffectiveStatus(report) {
    const a = (dbCache.assignments || []).find(x => x.reportId === report.id && (x.itemType || 'SOPORTE') === 'SOPORTE');
    if (a && a.status) {
        return a.status.toUpperCase();
    }
    return (report.estatus || 'PENDIENTE').toUpperCase();
}

// Renderizar la Pestaña de Consultas
function renderConsultas() {
    const list = document.getElementById('reportsList');
    if (!list) return;

    const reports = dbCache.reports || [];
    const query = activeSearchQuery.trim().toLowerCase();

    // Contadores
    let cTodos = 0;
    let cPendientes = 0;
    let cProceso = 0;
    let cEspera = 0;
    let cRealizadas = 0;
    let cAnuladas = 0;

    const enriched = reports.map(r => {
        const st = getEffectiveStatus(r);
        cTodos++;
        if (st.includes('PENDIENTE')) cPendientes++;
        else if (st.includes('PROCESO')) cProceso++;
        else if (st.includes('ESPERA')) cEspera++;
        else if (st.includes('REALIZADA') || st.includes('RESUELTO')) cRealizadas++;
        else if (st.includes('ANULADA') || st.includes('CANCELADO')) cAnuladas++;
        return { ...r, status: st };
    });

    if (document.getElementById('countTodos')) document.getElementById('countTodos').textContent = cTodos;
    if (document.getElementById('countPendientes')) document.getElementById('countPendientes').textContent = cPendientes;
    if (document.getElementById('countProceso')) document.getElementById('countProceso').textContent = cProceso;
    if (document.getElementById('countEspera')) document.getElementById('countEspera').textContent = cEspera;
    if (document.getElementById('countRealizadas')) document.getElementById('countRealizadas').textContent = cRealizadas;
    if (document.getElementById('countAnuladas')) document.getElementById('countAnuladas').textContent = cAnuladas;

    // Filtrado
    const filtered = enriched.filter(r => {
        // Filtro de estado
        if (activeFilter !== 'TODOS') {
            if (activeFilter === 'PENDIENTE' && !r.status.includes('PENDIENTE')) return false;
            if (activeFilter === 'EN PROCESO' && !r.status.includes('PROCESO')) return false;
            if (activeFilter === 'ESPERA' && !r.status.includes('ESPERA')) return false;
            if (activeFilter === 'REALIZADA' && !r.status.includes('REALIZADA') && !r.status.includes('RESUELTO')) return false;
            if (activeFilter === 'ANULADA' && !r.status.includes('ANULADA') && !r.status.includes('CANCELADO')) return false;
        }
        // Filtro de texto
        if (query) {
            const searchStr = `${r.cedula || ''} ${r.motivo || ''} ${r.caja_nap || ''} ${r.onu || ''} ${r.ubicacion || ''} ${r.zona || ''}`.toLowerCase();
            return searchStr.includes(query);
        }
        return true;
    });

    if (filtered.length === 0) {
        list.innerHTML = `
            <div style="text-align: center; padding: 30px 10px; color: var(--text-dim);">
                <svg style="width: 36px; height: 36px; margin: 0 auto 8px auto; display: block; opacity: 0.5;" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                No se encontraron soportes con el criterio actual.
            </div>
        `;
        return;
    }

    list.innerHTML = filtered.map(r => {
        let badgeClass = 'badge-pendiente';
        if (r.status.includes('PROCESO')) badgeClass = 'badge-proceso';
        else if (r.status.includes('ESPERA')) badgeClass = 'badge-espera';
        else if (r.status.includes('REALIZADA') || r.status.includes('RESUELTO')) badgeClass = 'badge-realizada';
        else if (r.status.includes('ANULADA') || r.status.includes('CANCELADO')) badgeClass = 'badge-anulada';
        else if (r.status.includes('REAGENDADA')) badgeClass = 'badge-reagendada';

        const fechaStr = r.created_at ? new Date(r.created_at).toLocaleDateString() : 'N/A';

        return `
            <div class="report-item" data-id="${r.id}">
                <div class="item-header">
                    <span class="item-id">#${r.id}</span>
                    <span class="badge ${badgeClass}">${r.status}</span>
                </div>
                <div class="item-body">
                    <div class="item-motivo">${escapeHtml(r.motivo || 'Sin motivo')}</div>
                    <div class="item-cliente">
                        <strong>C.I:</strong> ${escapeHtml(r.cedula || 'N/A')} &bull; <span>${escapeHtml(r.zona || 'N/A')}</span>
                    </div>
                    <div class="item-location" title="${escapeHtml(r.ubicacion || '')}">
                        📍 ${escapeHtml(r.ubicacion || 'Sin ubicación')}
                    </div>
                </div>
                <div class="item-date">Registrado: ${fechaStr}</div>
            </div>
        `;
    }).join('');

    // Listener para abrir detalles
    list.querySelectorAll('.report-item').forEach(el => {
        el.addEventListener('click', () => {
            const id = Number(el.getAttribute('data-id'));
            const item = enriched.find(x => x.id === id);
            if (item) openDetailModal(item);
        });
    });
}

function escapeHtml(str) {
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Modal Detalle de Soporte
function openDetailModal(item) {
    const modal = document.getElementById('detailModal');
    const title = document.getElementById('detailTitle');
    const body = document.getElementById('detailBody');
    if (!modal || !body) return;

    title.textContent = `Soporte #${item.id} - ${item.status}`;

    body.innerHTML = `
        <div class="detail-row">
            <span class="detail-label">C.I. / RIF:</span>
            <span class="detail-val">${escapeHtml(item.cedula || 'N/A')}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Zona:</span>
            <span class="detail-val">${escapeHtml(item.zona || 'N/A')}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Motivo:</span>
            <span class="detail-val" style="color: var(--primary);">${escapeHtml(item.motivo || 'N/A')}</span>
        </div>
        ${item.a_disponibilidad ? `
        <div class="detail-row">
            <span class="detail-label">Modalidad:</span>
            <span class="detail-val" style="color: #f59e0b; font-weight: 800;">⚡ A Disponibilidad</span>
        </div>` : (item.fecha_visita ? `
        <div class="detail-row">
            <span class="detail-label">Fecha de Visita:</span>
            <span class="detail-val" style="color: #0284c7; font-weight: 800;">📅 ${escapeHtml(item.fecha_visita)}</span>
        </div>` : '')}
        <div class="detail-row">
            <span class="detail-label">Ubicación:</span>
            <span class="detail-val" style="max-width: 60%;">${escapeHtml(item.ubicacion || 'N/A')}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">ONU:</span>
            <span class="detail-val">${escapeHtml(item.onu || 'N/A')}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Caja NAP:</span>
            <span class="detail-val">${escapeHtml(item.caja_nap || 'N/A')}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Precinto:</span>
            <span class="detail-val">${escapeHtml(item.precinto || 'N/A')}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Coordenadas:</span>
            <span class="detail-val">${escapeHtml(item.coordenadas || 'N/A')}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Teléfono 1:</span>
            <span class="detail-val">${escapeHtml(item.telefono1 || 'N/A')}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Teléfono 2:</span>
            <span class="detail-val">${escapeHtml(item.telefono2 || 'N/A')}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Fecha:</span>
            <span class="detail-val">${item.created_at ? new Date(item.created_at).toLocaleString() : 'N/A'}</span>
        </div>
        <button class="btn-secondary" style="margin-top: 10px;" id="btnCopyDetail">📋 Copiar Resumen</button>
    `;

    document.getElementById('btnCopyDetail').onclick = () => {
        const txt = `SOPORTE #${item.id}
C.I: ${item.cedula}
ZONA: ${item.zona}
MOTIVO: ${item.motivo}${item.a_disponibilidad ? '\nMODALIDAD: A DISPONIBILIDAD' : (item.fecha_visita ? `\nFECHA DE VISITA: ${item.fecha_visita}` : '')}
UBICACION: ${item.ubicacion}
ONU: ${item.onu || 'N/A'} | CAJA-NAP: ${item.caja_nap || 'N/A'} | PRECINTO: ${item.precinto || 'N/A'}
COORDENADAS: ${item.coordenadas || 'N/A'}
CONTACTO: ${item.telefono1 || ''} / ${item.telefono2 || ''}`;
        navigator.clipboard.writeText(txt).then(() => {
            showToast('Copiado al portapapeles');
        });
    };

    modal.classList.add('active');
}

function closeDetailModal() {
    const modal = document.getElementById('detailModal');
    if (modal) modal.classList.remove('active');
}

// Inicialización de la Extensión
document.addEventListener('DOMContentLoaded', async () => {
    // Inicializar tema guardado (Claro u Oscuro)
    const savedTheme = await getThemePreference();
    applyTheme(savedTheme);

    const btnThemeLight = document.getElementById('btnThemeLight');
    const btnThemeDark = document.getElementById('btnThemeDark');
    if (btnThemeLight) {
        btnThemeLight.addEventListener('click', async () => {
            await setThemePreference('light');
            showToast('☀️ Modo Claro activado');
        });
    }
    if (btnThemeDark) {
        btnThemeDark.addEventListener('click', async () => {
            await setThemePreference('dark');
            showToast('🌙 Modo Oscuro activado');
        });
    }

    currentServerUrl = await getServerUrl();
    const cfgInput = document.getElementById('cfg_server_url');
    if (cfgInput) cfgInput.value = currentServerUrl;

    const loginServerInput = document.getElementById('login_server_url');
    if (loginServerInput) loginServerInput.value = currentServerUrl;

    // Verificar sesión existente
    currentUser = await getCurrentUser();
    updateAuthUI(currentUser);

    // Conectar y sincronizar con base de datos del servidor
    await fetchDatabase();

    // Re-verificar si la sesión sigue siendo válida en users
    if (currentUser && dbCache.users && dbCache.users.length > 0) {
        const stillValid = dbCache.users.find(u => u.username && u.username.toLowerCase() === currentUser.username.toLowerCase());
        if (!stillValid) {
            await clearCurrentUser();
            updateAuthUI(null);
            showToast('La sesión anterior ya no es válida', true);
        }
    }

    // Toggle Configuración Servidor en Pantalla de Login
    const btnToggleServerConfig = document.getElementById('btnToggleServerConfig');
    const loginServerBox = document.getElementById('loginServerBox');
    if (btnToggleServerConfig && loginServerBox) {
        btnToggleServerConfig.addEventListener('click', () => {
            const isHidden = loginServerBox.style.display === 'none' || !loginServerBox.style.display;
            loginServerBox.style.display = isHidden ? 'block' : 'none';
        });
    }

    // Guardar Servidor desde Pantalla de Login
    const btnSaveLoginServer = document.getElementById('btnSaveLoginServer');
    if (btnSaveLoginServer) {
        btnSaveLoginServer.addEventListener('click', async () => {
            const val = document.getElementById('login_server_url').value.trim();
            if (!val) {
                showToast('Ingresa una URL válida', true);
                return;
            }
            currentServerUrl = await setServerUrl(val);
            if (cfgInput) cfgInput.value = currentServerUrl;
            showToast('Servidor actualizado. Conectando...');
            await fetchDatabase();
        });
    }

    // Manejo de Inicio de Sesión
    const formLoginExt = document.getElementById('formLoginExt');
    if (formLoginExt) {
        formLoginExt.addEventListener('submit', async (e) => {
            e.preventDefault();
            const usernameInput = document.getElementById('login_user');
            const passwordInput = document.getElementById('login_pass');
            const username = usernameInput ? usernameInput.value.trim() : '';
            const password = passwordInput ? passwordInput.value : '';

            if (!username || !password) {
                showToast('Ingresa usuario y contraseña', true);
                return;
            }

            const btnSubmit = document.getElementById('btnLoginSubmit');
            if (btnSubmit) {
                btnSubmit.disabled = true;
                btnSubmit.innerHTML = '<span>Verificando...</span>';
            }

            let authenticatedUser = null;

            // 1. Intentar autenticar mediante endpoint del servidor principal
            try {
                const res = await fetch(`${currentServerUrl}/api/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });

                if (res.ok) {
                    const data = await res.json();
                    if (data && data.success && data.user) {
                        authenticatedUser = data.user;
                    }
                }
            } catch (err) {
                console.warn('Endpoint /api/login no disponible o error de red, probando con dbCache.users:', err);
            }

            // 2. Fallback con dbCache.users (mismos usuarios del servidor y sistema)
            if (!authenticatedUser && dbCache.users && dbCache.users.length > 0) {
                const matched = dbCache.users.find(u =>
                    u.username && u.username.toLowerCase() === username.toLowerCase() &&
                    String(u.password) === String(password)
                );
                if (matched) {
                    authenticatedUser = {
                        id: matched.id,
                        username: matched.username,
                        name: matched.name || matched.username,
                        role: matched.role || 'OPERADOR',
                        permissions: matched.permissions || []
                    };
                }
            }

            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = `<span>Acceder al Sistema</span>
                    <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3"></path>
                    </svg>`;
            }

            if (authenticatedUser) {
                await setCurrentUser(authenticatedUser);
                updateAuthUI(authenticatedUser);
                showToast(`¡Bienvenido, ${authenticatedUser.name || authenticatedUser.username}!`);
                if (passwordInput) passwordInput.value = '';

                // Registrar en la bitácora
                syncDatabase({}, 'LOGIN_EXTENSION', `Usuario ${authenticatedUser.username} inició sesión desde la extensión`);
            } else {
                showToast('Usuario o contraseña incorrectos', true);
            }
        });
    }

    // Botón Cerrar Sesión
    const btnLogoutExt = document.getElementById('btnLogoutExt');
    if (btnLogoutExt) {
        btnLogoutExt.addEventListener('click', async () => {
            const prevUser = currentUser ? currentUser.username : 'desconocido';
            await clearCurrentUser();
            updateAuthUI(null);
            showToast('Sesión cerrada correctamente');
            syncDatabase({}, 'LOGOUT_EXTENSION', `Usuario ${prevUser} cerró sesión en la extensión`);
        });
    }

    // Event Listeners de Pestañas
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const targetId = btn.getAttribute('data-tab');
            const targetContent = document.getElementById(targetId);
            if (targetContent) targetContent.classList.add('active');

            if (targetId === 'tab-consultar') {
                renderConsultas();
            }
        });
    });

    // Píldoras de Filtro
    const pillBtns = document.querySelectorAll('.pill-btn');
    pillBtns.forEach(p => {
        p.addEventListener('click', () => {
            pillBtns.forEach(x => x.classList.remove('active'));
            p.classList.add('active');
            activeFilter = p.getAttribute('data-filter');
            renderConsultas();
        });
    });

    // Búsqueda en vivo
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            activeSearchQuery = e.target.value;
            renderConsultas();
        });
    }

    // Modal Detalle
    document.getElementById('btnCloseDetail').addEventListener('click', closeDetailModal);
    document.getElementById('detailModal').addEventListener('click', (e) => {
        if (e.target.id === 'detailModal') closeDetailModal();
    });

    // Botón Refrescar Conexión
    document.getElementById('btnCheckStatus').addEventListener('click', () => {
        fetchDatabase();
    });

    // Helper fecha actual YYYY-MM-DD
    function getTodayDateString() {
        const d = new Date();
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    }

    function getTomorrowDateString() {
        const d = new Date();
        d.setDate(d.getDate() + 1);
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    }

    // Configuración y restricción de Fecha de Visita y Disponibilidad
    let sopIsDisponibilidad = false;
    const btnSopDisp = document.getElementById('btn_sop_disponibilidad');
    const extDispDot = document.getElementById('ext_disp_dot');
    const extDispLabel = document.getElementById('ext_disp_label');
    const extDispHelp = document.getElementById('ext_disp_help');
    const extFechaContainer = document.getElementById('ext_fecha_container');
    const extFechaBadge = document.getElementById('ext_fecha_badge');
    const extFechaNotice = document.getElementById('ext_fecha_notice');
    const sopFechaVisitaInput = document.getElementById('sop_fecha_visita');

    function updateExtDisponibilidadUI() {
        if (!btnSopDisp) return;
        if (sopIsDisponibilidad) {
            btnSopDisp.style.background = '#f59e0b';
            btnSopDisp.style.borderColor = '#d97706';
            btnSopDisp.style.color = '#ffffff';
            if (extDispDot) extDispDot.style.background = '#ffffff';
            if (extDispLabel) extDispLabel.textContent = 'SÍ (A Disponibilidad)';
            if (extDispHelp) extDispHelp.textContent = '✓ Visita a disponibilidad (sin fecha fija)';
            if (sopFechaVisitaInput) {
                sopFechaVisitaInput.value = '';
                sopFechaVisitaInput.disabled = true;
            }
            if (extFechaContainer) extFechaContainer.style.opacity = '0.5';
            if (extFechaBadge) {
                extFechaBadge.textContent = 'A Disponibilidad';
                extFechaBadge.style.color = '#f59e0b';
            }
            if (extFechaNotice) extFechaNotice.textContent = '⚡ Esta visita quedará registrada a disponibilidad.';
        } else {
            btnSopDisp.style.background = 'var(--bg-card)';
            btnSopDisp.style.borderColor = 'var(--border-color)';
            btnSopDisp.style.color = 'var(--text-muted)';
            if (extDispDot) extDispDot.style.background = '#94a3b8';
            if (extDispLabel) extDispLabel.textContent = 'NO';
            if (extDispHelp) extDispHelp.textContent = 'No (se planifica para mañana o fecha fija)';
            if (sopFechaVisitaInput) {
                sopFechaVisitaInput.disabled = false;
            }
            if (extFechaContainer) extFechaContainer.style.opacity = '1';
            if (extFechaBadge) {
                extFechaBadge.textContent = 'Por defecto: Mañana';
                extFechaBadge.style.color = '#38bdf8';
            }
            if (extFechaNotice) extFechaNotice.textContent = 'Si no seleccionas fecha, se planificará para mañana.';
        }
    }

    if (btnSopDisp) {
        btnSopDisp.addEventListener('click', () => {
            sopIsDisponibilidad = !sopIsDisponibilidad;
            updateExtDisponibilidadUI();
        });
    }

    if (sopFechaVisitaInput) {
        sopFechaVisitaInput.min = getTodayDateString();
        sopFechaVisitaInput.addEventListener('change', (e) => {
            const todayStr = getTodayDateString();
            if (e.target.value && e.target.value < todayStr) {
                showToast('No se pueden seleccionar días anteriores al actual', true);
                e.target.value = '';
            }
        });
    }

    // Restricción C.I. numérica
    const cedulaInput = document.getElementById('sop_cedula');
    if (cedulaInput) {
        cedulaInput.addEventListener('input', (e) => {
            e.target.value = e.target.value.replace(/[^0-9]/g, '');
        });
    }

    // FORMULARIO: CREAR SOPORTE
    const formSoporte = document.getElementById('formSoporte');
    if (formSoporte) {
        formSoporte.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Bloquear si no hay sesión iniciada
            if (!currentUser) {
                showToast('Debes iniciar sesión para registrar soportes', true);
                updateAuthUI(null);
                return;
            }

            const cedula = document.getElementById('sop_cedula').value.trim();
            const zona = document.getElementById('sop_zona').value.trim();
            const motivo = document.getElementById('sop_motivo').value.trim();
            const ubicacion = document.getElementById('sop_ubicacion').value.trim();
            let fechaVisita = document.getElementById('sop_fecha_visita') ? (document.getElementById('sop_fecha_visita').value || null) : null;
            const aDisponibilidad = sopIsDisponibilidad;

            if (aDisponibilidad) {
                fechaVisita = null;
            } else if (!fechaVisita) {
                // Si no se especifica fecha, se planifica para el siguiente día
                fechaVisita = getTomorrowDateString();
            }

            if (!cedula || !zona || !motivo || !ubicacion) {
                showToast('Por favor completa todos los campos requeridos (*)', true);
                return;
            }

            if (fechaVisita && fechaVisita < getTodayDateString()) {
                showToast('La fecha de visita no puede ser anterior al día actual', true);
                return;
            }

            const newReport = {
                id: Date.now(),
                zona,
                cedula,
                motivo,
                fecha_visita: fechaVisita,
                a_disponibilidad: aDisponibilidad,
                onu: document.getElementById('sop_onu').value.trim() || null,
                caja_nap: document.getElementById('sop_caja_nap').value.trim() || null,
                precinto: document.getElementById('sop_precinto').value.trim() || null,
                ubicacion,
                coordenadas: document.getElementById('sop_coordenadas').value.trim() || null,
                telefono1: document.getElementById('sop_tel1').value.trim() || null,
                telefono2: document.getElementById('sop_tel2').value.trim() || null,
                usuario: currentUser.username,
                usuario_nombre: currentUser.name || currentUser.username,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            };

            const updatedReports = [newReport, ...(dbCache.reports || [])];
            const ok = await syncDatabase(
                { reports: updatedReports },
                'CREAR_REPORTE',
                `Soporte #${newReport.id} (C.I: ${cedula}, Motivo: ${motivo}) registrado por ${currentUser.username} desde extensión`
            );

            if (ok) {
                showToast(`✅ Soporte #${newReport.id} guardado con éxito`);
                formSoporte.reset();
                sopIsDisponibilidad = false;
                updateExtDisponibilidadUI();
                // Cambiar a la pestaña de consulta para ver el reporte creado
                const btnConsultar = document.querySelector('[data-tab="tab-consultar"]');
                if (btnConsultar) btnConsultar.click();
            }
        });
    }

    // FORMULARIO: CREAR ACTIVIDAD
    const formActividad = document.getElementById('formActividad');
    if (formActividad) {
        formActividad.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Bloquear si no hay sesión iniciada
            if (!currentUser) {
                showToast('Debes iniciar sesión para registrar actividades', true);
                updateAuthUI(null);
                return;
            }

            const zona = document.getElementById('act_zona').value.trim();
            const caja_nap = document.getElementById('act_caja_nap').value.trim();
            const ubicacion = document.getElementById('act_ubicacion').value.trim();
            const estatus = document.getElementById('act_estatus').value.trim();

            if (!zona || !caja_nap || !ubicacion || !estatus) {
                showToast('Por favor completa los campos requeridos (*)', true);
                return;
            }

            const newAct = {
                id: Date.now(),
                tipo: 'ACTIVIDAD',
                zona,
                caja_nap,
                potencia: document.getElementById('act_potencia').value.trim() || null,
                puertos: document.getElementById('act_puertos').value.trim() || null,
                ubicacion,
                coordenadas: document.getElementById('act_coordenadas').value.trim() || null,
                estatus,
                referencias: document.getElementById('act_referencias').value.trim() || null,
                olt: document.getElementById('act_olt').value.trim() || null,
                tarjeta: document.getElementById('act_tarjeta').value.trim() || null,
                port: document.getElementById('act_port').value.trim() || null,
                usuario: currentUser.username,
                usuario_nombre: currentUser.name || currentUser.username,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            };

            const updatedAfec = [newAct, ...(dbCache.afectaciones || [])];
            const ok = await syncDatabase(
                { afectaciones: updatedAfec },
                'CREAR_ACTIVIDAD',
                `Actividad #${newAct.id} (Caja: ${caja_nap}, Zona: ${zona}) registrada por ${currentUser.username} desde extensión`
            );

            if (ok) {
                showToast(`✅ Actividad #${newAct.id} guardada con éxito`);
                formActividad.reset();
            }
        });
    }

    // FORMULARIO: CREAR AFECTACIÓN
    const formAfectacion = document.getElementById('formAfectacion');
    if (formAfectacion) {
        // Auto-llenar fecha y hora actual
        const now = new Date();
        const fInput = document.getElementById('afec_fecha');
        const hInput = document.getElementById('afec_hora');
        if (fInput && !fInput.value) {
            fInput.value = now.toLocaleDateString();
        }
        if (hInput && !hInput.value) {
            hInput.value = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }

        formAfectacion.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Bloquear si no hay sesión iniciada
            if (!currentUser) {
                showToast('Debes iniciar sesión para registrar afectaciones', true);
                updateAuthUI(null);
                return;
            }

            const fecha = document.getElementById('afec_fecha').value.trim();
            const hora = document.getElementById('afec_hora').value.trim();
            const olt = document.getElementById('afec_olt').value.trim();
            const tarjeta = document.getElementById('afec_tarjeta').value.trim();
            const port = document.getElementById('afec_port').value.trim();
            const ubicacion = document.getElementById('afec_ubicacion').value.trim();
            const afectados = parseInt(document.getElementById('afec_afectados').value.trim()) || 1;

            if (!fecha || !hora || !olt || !tarjeta || !port || !ubicacion) {
                showToast('Por favor completa todos los campos requeridos (*)', true);
                return;
            }

            const newAfec = {
                id: Date.now(),
                tipo: 'AFECTACION',
                fecha,
                hora,
                olt,
                tarjeta,
                port,
                ubicacion,
                afectados,
                caja_nap: document.getElementById('afec_caja_nap').value.trim() || null,
                coordenadas: document.getElementById('afec_coordenadas').value.trim() || null,
                usuario: currentUser.username,
                usuario_nombre: currentUser.name || currentUser.username,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            };

            const updatedAfec = [newAfec, ...(dbCache.afectaciones || [])];
            const ok = await syncDatabase(
                { afectaciones: updatedAfec },
                'CREAR_AFECTACION',
                `Afectación #${newAfec.id} (${afectados} afectados en ${ubicacion}) registrada por ${currentUser.username} desde extensión`
            );

            if (ok) {
                showToast(`✅ Afectación #${newAfec.id} guardada con éxito`);
                formAfectacion.reset();
            }
        });
    }

    // CONFIGURACIÓN: GUARDAR URL DEL SERVIDOR
    const btnSaveConfig = document.getElementById('btnSaveConfig');
    if (btnSaveConfig) {
        btnSaveConfig.addEventListener('click', async () => {
            const val = document.getElementById('cfg_server_url').value.trim();
            if (!val) {
                showToast('Ingresa una URL válida', true);
                return;
            }
            currentServerUrl = await setServerUrl(val);
            showToast('Guardando y verificando conexión...');
            await fetchDatabase();
        });
    }

    // Modo Ventana Flotante Redimensionable (resizable: true)
    const isWindowMode = window.location.search.includes('mode=window');
    const btnFloat = document.getElementById('btnOpenFloating');
    if (isWindowMode) {
        document.body.classList.remove('mode-popup');
        if (btnFloat) btnFloat.style.display = 'none';
    } else {
        document.body.classList.add('mode-popup');
        if (btnFloat) {
            btnFloat.addEventListener('click', () => {
                const url = chrome.runtime.getURL('popup.html?mode=window');
                window.open(url, 'SoporteTecnicoFlotante', 'width=480,height=680,resizable=yes,scrollbars=yes');
                window.close();
            });
        }
    }
});
