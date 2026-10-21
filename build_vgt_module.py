import json

routes = json.load(open('static/vgt/routes_db.json', encoding='utf-8'))
techs = json.load(open('static/vgt/technicians_db.json', encoding='utf-8'))
drivers = json.load(open('static/vgt/drivers_db.json', encoding='utf-8'))
vehs = json.load(open('static/vgt/vehicles_db.json', encoding='utf-8'))

with open('static/js/vgt_module.js', 'w', encoding='utf-8') as f:
    f.write(f'''// ==============================================================================
// POWERLINK CORP. - MÓDULO INTEGRADO DE PARTES DIARIOS Y CORRELATIVOS VGT
// ==============================================================================

(function() {{
  const DEFAULT_ROUTES = {json.dumps(routes, ensure_ascii=False)};
  const DEFAULT_TECHS = {json.dumps(techs, ensure_ascii=False)};
  const DEFAULT_DRIVERS = {json.dumps(drivers, ensure_ascii=False)};
  const DEFAULT_VEHS = {json.dumps(vehs, ensure_ascii=False)};

  const WEEKDAY_TEAMS = [
    {{ id: "M", letter: "M", type: "AFECTACIONES", active: true, techs: ["JOE FRANCO MACHADO", "GERAL ANDRES ARIAS"], driver: "", vehicle: "RICH ZN", plate: "A00CR8G", rawTickets: "" }},
    {{ id: "E", letter: "E", type: "AFECTACIONES", active: true, techs: ["JORGE MACHADO", "ALEXIS GARCIA OROPEZA", "JEAN CARLOS BURGOS"], driver: "", vehicle: "RICH ZN", plate: "A98DP5K", rawTickets: "" }},
    {{ id: "P", letter: "P", type: "AFECTACIONES", active: true, techs: ["CARLOS JOSÉ BURGOS PINEDA", "DIEGO ANDRÉS MORONTA VIERA"], driver: "", vehicle: "RICH ZN", plate: "A98DP5K", rawTickets: "" }},
    {{ id: "V", letter: "V", type: "SOPORTE TÉCNICO", active: true, techs: ["JESÚS MANUEL ROMERO MUÑOZ"], driver: "", vehicle: "EKXPRESS II 150", plate: "AG2L05E", rawTickets: "" }},
    {{ id: "J", letter: "J", type: "SOPORTE TÉCNICO", active: true, techs: ["JOBER DUGARTE"], driver: "", vehicle: "EMPIRE HORSE", plate: "AK7J67M", rawTickets: "" }},
    {{ id: "G", letter: "G", type: "SOPORTE TÉCNICO", active: true, techs: ["CARLOS GIL"], driver: "", vehicle: "EMPIRE HORSE", plate: "AK7J67M", rawTickets: "" }},
    {{ id: "R", letter: "R", type: "SOPORTE TÉCNICO", active: true, techs: ["RONEL JOSE VARGAS VADEL"], driver: "", vehicle: "EMPIRE HORSE", plate: "AK7J67M", rawTickets: "" }},
    {{ id: "S", letter: "S", type: "SOPORTE TÉCNICO", active: true, techs: ["JOLHAN ANTHONY RODRIGUEZ RODRIGUEZ"], driver: "", vehicle: "EMPIRE HORSE", plate: "AL3Y16G", rawTickets: "" }},
    {{ id: "H", letter: "H", type: "SOPORTE TÉCNICO", active: true, techs: ["HERNÁN JOSÉ LEAL MARTÍNEZ"], driver: "", vehicle: "BERA - KAVAK", plate: "AT2X63D", rawTickets: "" }},
    {{ id: "Y", letter: "Y", type: "SOPORTE TÉCNICO", active: true, techs: ["JUNIOR ARNALDO ORTA JIMENEZ"], driver: "", vehicle: "DT-200 BR ENDUR", plate: "AL3Y16G", rawTickets: "" }}
  ];

  const DEFAULT_WEEKEND_TEAMS = [
    {{ id: "GUARDIA-1", letter: "F", customTitle: '', type: "AFECTACIONES", active: true, techs: [], driver: "", vehicle: "MITSUBISHI PANEL L300", plate: "13HDBA", rawTickets: "" }},
    {{ id: "GUARDIA-2", letter: "xD", customTitle: '', type: "SOPORTE TÉCNICO", active: false, techs: [], driver: "", vehicle: "EMPIRE HORSE", plate: "AK7J67M", rawTickets: "" }}
  ];

  // State Variables
  let routesDB = JSON.parse(localStorage.getItem("powerlink_routes")) || DEFAULT_ROUTES;
  let techniciansDB = JSON.parse(localStorage.getItem("powerlink_techs")) || DEFAULT_TECHS;
  let driversDB = JSON.parse(localStorage.getItem("powerlink_drivers")) || DEFAULT_DRIVERS;
  let vehiclesDB = JSON.parse(localStorage.getItem("powerlink_vehicles")) || DEFAULT_VEHS;

  // Sincronizar técnicos
  DEFAULT_TECHS.forEach(dt => {{
    const idx = techniciansDB.findIndex(t => t.id === dt.id || normalizeText(t.name) === normalizeText(dt.name));
    if (idx === -1) {{
      techniciansDB.push(dt);
    }} else {{
      if (!techniciansDB[idx].cedula || techniciansDB[idx].cedula !== dt.cedula) techniciansDB[idx].cedula = dt.cedula;
      if (!techniciansDB[idx].phone || techniciansDB[idx].phone !== dt.phone) techniciansDB[idx].phone = dt.phone;
      if (!techniciansDB[idx].block) techniciansDB[idx].block = dt.block;
    }}
  }});

  let currentPresetMode = "WEEKDAY"; // WEEKDAY or WEEKEND
  let currentInputMode = "TEAM_MANAGER"; // TEAM_MANAGER or MASSIVE_INPUT
  let currentOutputView = "TEXT"; // TEXT or AUDIT
  let currentPersonnelFilter = "ALL";
  let currentSubTab = "TEAMS"; // TEAMS, MASSIVE, ROUTES, PERSONNEL
  let currentPersonnelSubTab = "TECHS"; // TECHS, DRIVERS, VEHS

  let teamsState = JSON.parse(localStorage.getItem("powerlink_vgt_teams")) || JSON.parse(JSON.stringify(WEEKDAY_TEAMS));
  let parsedActivitiesStore = [];

  const TECH_ALIASES = {{
    "JOE MACHADO": "JOE FRANCO MACHADO",
    "ANDRES ARIAS": "GERAL ANDRES ARIAS",
    "CARLOS JOSÉ BURGOS": "CARLOS JOSÉ BURGOS PINEDA",
    "CARLOS JOSE BURGOS": "CARLOS JOSÉ BURGOS PINEDA",
    "CARLOS BURGOS": "CARLOS JOSÉ BURGOS PINEDA",
    "DIEGO MORONTA": "DIEGO ANDRÉS MORONTA VIERA",
    "JESUS ROMERO": "JESÚS MANUEL ROMERO MUÑOZ",
    "RONEL VARGAS": "RONEL JOSE VARGAS VADEL",
    "ANTHONY RODRIGUEZ": "JOLHAN ANTHONY RODRIGUEZ RODRIGUEZ",
    "HERNAN LEAL": "HERNÁN JOSÉ LEAL MARTÍNEZ",
    "JUNIOR ORTA": "JUNIOR ARNALDO ORTA JIMENEZ",
    "ALEXIS GARCIA": "ALEXIS GARCIA OROPEZA",
    "ELIAS JIMENEZ": "ELIAS MIGUEL JIMENEZ MARMOLET",
    "FRANCISCO REYES": "FRANCISCO RODOLFO REYES URIEPERO",
    "FRANYELO PEREZ": "FRANYELO JOSÉ PEREZ VELASQUEZ",
    "JOYNERKER SUAREZ": "JOYNERKER DAVID SUÁREZ MEJÍAS",
    "KERVIN MARQUEZ": "KERVIN MANUEL MARQUEZ CASTRO",
    "MAIKER PINEDA": "MAIKER GUILLERMO PINEDA RANGEL",
    "NEOMAR GUAINA": "NEOMAR ALBERTO GUAINA GONZÁLEZ",
    "ORLANDO MARRERO": "ORLANDO ANTONIO MARRERO CASTILLO",
    "TOMAS MUJICA": "TOMAS SIMON MUJICA MARMOLE",
    "UDMAR FERNANDEZ": "UDMAR ALEXIS FERNANDEZ PARADA",
    "VICTOR HERNANDEZ": "VICTOR MANUEL HERNANDEZ ORDAZ",
    "WOLFAN BARRIOS": "WOLFAN OLEIDY BARRIOS GARCIA",
    "CESAR CAMPOS": "CESAR AUGUSTO CAMPOS LUQUE",
    "CESAR GOMEZ": "CESAR ENRIQUE GÓMEZ CONTRERAS",
    "DANIEL COLMENARES": "DANIEL ALBERTO COLMENARES LIRA",
    "ERNESTO DELGADO": "ERNESTO GABRIEL DELGADO",
    "GABRIEL ESPINOZA": "GABRIEL VICENTE ESPINOZA DUM",
    "ISAAC SALGADO": "ISAAC RAFAEL SALGADO ALDAMA",
    "JEFFERSON MARRERO": "JEFFERSON DANIEL MARRERO OCHOA",
    "JEFFERSON CASTELLANOS": "JEFFERSON MIGUEL CASTELLANOS HERNANDEZ",
    "JOHAN RODRIGUEZ": "JOHAN RENE RODRIGUEZ MORALES",
    "JOSE LEAL": "JOSE ENRIQUE LEAL CURIEL",
    "KEHISBER CARABALLO": "KEHISBER ANTONIO CARABALLO GARCIA",
    "KEVIN CORTEZ": "KEVIN JOSSUEEP CORTEZ GONZALEZ",
    "LUIS ALTUVE": "LUIS ALBERTO ALTUVE MENESES",
    "MOISES PIÑANGO": "MOISES ALBERTO PIÑANGO RODRÍGUEZ",
    "MOISES MUJICA": "MOISES ALEJANDRO MUJICA BALZA",
    "RANDY MORENO": "RANDY EIDAN MORENO CHACOA",
    "STEVEN MARDACH": "STEVEN RAFAEL MARDACH TORRES"
  }};

  function normalizeText(str) {{
    if (!str) return "";
    return str.normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toUpperCase();
  }}

  function findTechnician(query) {{
    if (!query || typeof query !== "string") return null;
    const cleanQ = query.trim();
    if (!cleanQ) return null;
    const normQ = normalizeText(cleanQ);

    let found = techniciansDB.find(t => normalizeText(t.name) === normQ);
    if (found) return found;

    const digitsQ = cleanQ.replace(/\\D/g, '');
    if (digitsQ.length >= 6) {{
      found = techniciansDB.find(t => {{
        const tDigits = (t.cedula || '').replace(/\\D/g, '');
        return tDigits && tDigits === digitsQ;
      }});
      if (found) return found;
    }}

    for (const [alias, realName] of Object.entries(TECH_ALIASES)) {{
      if (normalizeText(alias) === normQ) {{
        found = techniciansDB.find(t => normalizeText(t.name) === normalizeText(realName));
        if (found) return found;
      }}
    }}

    const qTokens = normQ.split(/\\s+/).filter(w => w.length > 1);
    if (qTokens.length >= 2) {{
      const candidates = techniciansDB.filter(t => {{
        const tTokens = normalizeText(t.name).split(/\\s+/);
        return qTokens.every(qk => tTokens.includes(qk));
      }});
      if (candidates.length === 1) return candidates[0];
    }}

    found = techniciansDB.find(t => {{
      const tn = normalizeText(t.name);
      return normQ.length > 5 && (tn.includes(normQ) || normQ.includes(tn));
    }});
    if (found) return found;

    return null;
  }}

  function sanitizeTeamTechNames(teams) {{
    if (!teams || !Array.isArray(teams)) return;
    teams.forEach(team => {{
      if (team.techs && Array.isArray(team.techs)) {{
        team.techs = team.techs.map(tName => {{
          const found = findTechnician(tName);
          return found ? found.name : tName;
        }});
      }}
    }});
  }}

  sanitizeTeamTechNames(teamsState);

  function getVGTForAddress(address, onu = "", zona = "") {{
    const normAddr = normalizeText(address);
    const normOnu  = normalizeText(onu);
    const normZona = normalizeText(zona);
    const fullContext = `${{normAddr}} ${{normOnu}} ${{normZona}}`;

    if (fullContext.includes("CENTRO LOS TEQUES") || fullContext.includes("CENTRO TEQUES")) return "VGT-2023-P-679";
    if (fullContext.includes("CUMBRE ROJA") || fullContext.includes("TEJERIA") || fullContext.includes("TEJERIAS")) return "VGT-2024-P-429";
    if (fullContext.includes("SAN ANTONIO")) {{
      const exceptions = ["LA MORITA", "CASTORES", "LOS CASTORES", "LAS MINAS", "LA COLINA", "COLISEO", "CLUB DE CAMPO"];
      if (!exceptions.some(exc => fullContext.includes(exc))) return "VGT-2023-P-774";
    }}
    if (fullContext.includes("SAN PEDRO")) return "VGT-2023-P-1142";
    if (fullContext.includes("KM 0") || fullContext.includes("KM0") || fullContext.includes("LAS MAYAS") || fullContext.includes("LA MAYA")) return "VGT-2025-P-131";
    if (fullContext.includes("CATIA") || fullContext.includes("PROPATRIA")) return "VGT-2025-P-2415";
    if (fullContext.includes("VALLE")) return "VGT-2024-P-1750";
    if (fullContext.includes("COCHE")) return "VGT-2025-P-2136";
    if (fullContext.includes("LA VEGA") || fullContext.includes("VEGA")) return "VGT-2025-P-2076";
    if (fullContext.includes("LAGUNETICA")) return "VGT-2024-P-1438";
    if (fullContext.includes("CARRETERA VIEJA") || fullContext.includes("ESPERANZA") || normOnu.includes("ESPERANZA")) return "VGT-2023-P-770";
    if (fullContext.includes("AYACUCHO") || normOnu.includes("AYACUCHO") || fullContext.includes("CHORRITO")) return "VGT-2023-P-676";
    if (fullContext.includes("PIEDRA AZUL") || normOnu.includes("P. AZUL") || normOnu.includes("P.AZUL") || normOnu.includes("PIEDRA AZUL")) return "VGT-2024-P-2270";

    let bestMatch = null;
    let bestScore = 0;

    for (const r of routesDB) {{
      if (!r.vgt || r.vgt === "-" || r.vgt === "PENDIENTE" || r.vgt.includes("NO FACTIBLE")) continue;
      const normDesc = normalizeText(r.description);
      let score = 0;
      if (fullContext.includes(normDesc)) score += 120;
      const terms = normDesc.split(/[\\s\\-\\/\\,]+/).filter(t => 
        t.length > 3 && !['ACTUALIZADA','PROYECTO','COMPLETO','FASE','ETAPA','POR','IMPRIMIR','LOS','LOS TEQUES','TEQUES'].includes(t)
      );
      let matchedCount = 0;
      for (const term of terms) {{
        if (normAddr.includes(term)) {{
          matchedCount++;
          score += 25 + term.length;
        }} else if (normOnu.includes(term) || normZona.includes(term)) {{
          matchedCount++;
          score += 20 + term.length;
        }}
      }}
      if (matchedCount > 0 && score > bestScore) {{
        bestScore = score;
        bestMatch = r.vgt.replace('.-P-', '-P-');
      }}
    }}

    return bestMatch || "SIN NÚMERO";
  }}

  function parseTicketsText(rawText) {{
    if (!rawText || !rawText.trim()) return [];
    const text = rawText.trim();
    const activities = [];
    const isTicketFormat = /(?:UBICACI[ÓO]N|DIRECCI[ÓO]N)\\s*:/i.test(text);

    if (isTicketFormat) {{
      let generalZona = "";
      const zonaMatch = text.match(/ZONA\\s*:\\s*([^\\r\\n=]+)/i);
      if (zonaMatch) generalZona = zonaMatch[1].trim();

      const blocks = text.split(/(?:\\r?\\n)?\\s*={{3,}}\\s*(?:\\r?\\n)?/);
      for (const block of blocks) {{
        const bTrim = block.trim();
        if (!bTrim) continue;
        const uMatch = bTrim.match(/(?:UBICACI[ÓO]N|DIRECCI[ÓO]N)\\s*:\\s*([^\\r\\n]+)/i);
        if (uMatch) {{
          let addr = uMatch[1].trim().replace(/^["'*]+|["'*]+$/g, '').trim();
          let onu = "";
          const onuMatch = bTrim.match(/ONU\\s*:\\s*([^\\r\\n]+)/i);
          if (onuMatch) onu = onuMatch[1].trim();
          let localZona = generalZona;
          const bZonaMatch = bTrim.match(/ZONA\\s*:\\s*([^\\r\\n]+)/i);
          if (bZonaMatch) localZona = bZonaMatch[1].trim();
          if (addr) activities.push({{ address: addr, onu: onu, zona: localZona, manualVgt: null }});
        }}
      }}
      if (activities.length === 0) {{
        const lines = text.split(/\\r?\\n/);
        for (const line of lines) {{
          const lTrim = line.trim();
          if (/(?:UBICACI[ÓO]N|DIRECCI[ÓO]N)\\s*:/i.test(lTrim)) {{
            let addr = lTrim.replace(/.*(?:UBICACI[ÓO]N|DIRECCI[ÓO]N)\\s*:\\s*/i, '').trim();
            if (addr) activities.push({{ address: addr, onu: "", zona: generalZona, manualVgt: null }});
          }}
        }}
      }}
    }} else {{
      const lines = text.split(/\\r?\\n/).map(l => l.trim()).filter(l => l.length > 0);
      for (const line of lines) {{
        let clean = line.replace(/^[\\d\\.\\-\\)\\*\\>\\+\\s]+/, '').trim();
        if (!clean || clean.startsWith("===") || clean.startsWith("---")) continue;
        if (clean.toUpperCase().includes("EQUIPO") || clean.toUpperCase().includes("TECNICO") || clean.toUpperCase().includes("VEHICULO")) continue;
        activities.push({{ address: clean, onu: "", zona: "", manualVgt: null }});
      }}
    }}
    return activities;
  }}

  function saveVgtAll() {{
    localStorage.setItem("powerlink_routes", JSON.stringify(routesDB));
    localStorage.setItem("powerlink_techs", JSON.stringify(techniciansDB));
    localStorage.setItem("powerlink_drivers", JSON.stringify(driversDB));
    localStorage.setItem("powerlink_vehicles", JSON.stringify(vehiclesDB));
    localStorage.setItem("powerlink_vgt_teams", JSON.stringify(teamsState));
    if (typeof window.syncServerDB === "function") {{
      window.syncServerDB();
    }}
  }}

  function showToast(msg) {{
    const toast = document.getElementById("toast");
    if (toast) {{
      toast.innerText = msg;
      toast.classList.remove("translate-y-20", "opacity-0");
      setTimeout(() => toast.classList.add("translate-y-20", "opacity-0"), 3000);
    }} else {{
      console.log(msg);
    }}
  }}

  // ==============================================================================
  // RENDERER PRINCIPAL: VGT
  // ==============================================================================
  function renderVgt(app) {{
    if (!app) app = document.getElementById("app");
    if (!app) return;

    // Calcular estadísticas en tiempo real
    const totalTeams = teamsState.length;
    const soportesTeams = teamsState.filter(t => t.type.includes("SOPORTE")).length;
    const afectacionesTeams = teamsState.filter(t => t.type.includes("AFECTACION")).length;
    const totalRoutes = routesDB.length;

    let totalActivities = 0;
    let totalConVGT = 0;
    let totalSinVGT = 0;

    teamsState.forEach(tm => {{
      const acts = parseTicketsText(tm.rawTickets || "");
      totalActivities += acts.length;
      acts.forEach(a => {{
        const v = a.manualVgt || getVGTForAddress(a.address, a.onu, a.zona);
        if (v && v !== "SIN NÚMERO") totalConVGT++;
        else totalSinVGT++;
      }});
    }});

    app.innerHTML = `
      <div class="space-y-6 fade-in">
        <!-- HEADER PRINCIPAL -->
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div class="flex items-center gap-2.5">
              <h2 class="text-xl sm:text-2xl font-extrabold text-slate-800 dark:text-slate-100">Partes Diarios y Correlativos VGT</h2>
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FFC107]/15 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-700/50">
                ${{currentPresetMode === 'WEEKDAY' ? 'Lunes a Viernes' : 'Guardia / Fin de Semana'}}
              </span>
            </div>
            <p class="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">Generador inteligente de partes de cuadrillas, asignación automática de códigos VGT y exportación a WhatsApp y Excel.</p>
          </div>
          <div class="flex items-center gap-2 flex-wrap self-start sm:self-auto">
            <button onclick="window.VGT.exportToExcel()" class="btn-modern inline-flex items-center gap-2 px-3.5 py-2 text-xs font-bold text-white bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 rounded-xl shadow-md shadow-emerald-500/20">
              <i class="fa-solid fa-file-excel"></i> Exportar Excel
            </button>
            <button onclick="window.VGT.copyToClipboard()" class="btn-modern inline-flex items-center gap-2 px-3.5 py-2 text-xs font-bold text-white bg-gradient-to-r from-brand-600 to-brand-500 hover:from-brand-500 hover:to-brand-400 rounded-xl shadow-md shadow-brand-500/20">
              <i class="fa-brands fa-whatsapp"></i> Copiar WhatsApp
            </button>
          </div>
        </div>

        <!-- STATS CARDS -->
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-slate-200/90 dark:border-slate-800 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Cuadrillas</span>
              <i class="fa-solid fa-users text-slate-400 text-sm"></i>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-slate-800 dark:text-slate-100 mt-1">${{totalTeams}}</p>
          </div>
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-brand-200/70 dark:border-brand-900/40 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Soporte</span>
              <span class="text-xs">🎫</span>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-brand-600 dark:text-brand-400 mt-1">${{soportesTeams}}</p>
          </div>
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-amber-200/70 dark:border-amber-900/40 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Afectaciones</span>
              <span class="text-xs">⚠️</span>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-amber-600 dark:text-amber-400 mt-1">${{afectacionesTeams}}</p>
          </div>
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-cyan-200/70 dark:border-cyan-900/40 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Rutas VGT</span>
              <i class="fa-solid fa-route text-cyan-500 text-sm"></i>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-cyan-600 dark:text-cyan-400 mt-1">${{totalRoutes}}</p>
          </div>
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-emerald-200/70 dark:border-emerald-900/40 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Con VGT</span>
              <i class="fa-solid fa-circle-check text-emerald-500 text-sm"></i>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-1">${{totalConVGT}}</p>
          </div>
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-rose-200/70 dark:border-rose-900/40 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Sin VGT</span>
              <i class="fa-solid fa-circle-question text-rose-500 text-sm"></i>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-rose-600 dark:text-rose-400 mt-1">${{totalSinVGT}}</p>
          </div>
        </div>

        <!-- CONTROL BAR: MODALIDADES Y PESTAÑAS -->
        <div class="bg-white dark:bg-[#0c1427] p-3 sm:p-4 rounded-2xl border border-slate-200/90 dark:border-slate-800 shadow-sm flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <!-- Preset Selector -->
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xs font-bold text-slate-500 uppercase tracking-wider">Modalidad:</span>
            <div class="inline-flex p-1 bg-slate-100 dark:bg-slate-800/80 rounded-xl border border-slate-200/80 dark:border-slate-700/80">
              <button onclick="window.VGT.switchPreset('WEEKDAY')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${{currentPresetMode === 'WEEKDAY' ? 'bg-[#FFC107] text-[#1A1A1A] shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}}">
                🗓️ L-V (10 Equipos Fijos)
              </button>
              <button onclick="window.VGT.switchPreset('WEEKEND')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${{currentPresetMode === 'WEEKEND' ? 'bg-[#FFC107] text-[#1A1A1A] shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}}">
                🛡️ Guardia / Fin de Semana
              </button>
            </div>
            ${{currentPresetMode === 'WEEKEND' ? `
            <button onclick="window.VGT.saveGuardPreset()" class="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-semibold transition-all" title="Guardar la configuración de cuadrillas de guardia">
              💾 Guardar Guardia
            </button>
            <button onclick="window.VGT.loadLastGuardPreset()" class="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-semibold transition-all" title="Cargar guardia previa">
              📂 Cargar Guardia Sábado
            </button>
            ` : `
            <button onclick="window.VGT.resetCurrentPreset()" class="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-semibold transition-all">
              🔄 Restablecer L-V
            </button>
            `}}
          </div>

          <!-- View Tabs Switcher -->
          <div class="inline-flex p-1 bg-slate-100 dark:bg-slate-800/80 rounded-xl border border-slate-200/80 dark:border-slate-700/80 overflow-x-auto custom-scrollbar">
            <button onclick="window.VGT.switchSubTab('TEAMS')" class="px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-all ${{currentSubTab === 'TEAMS' ? 'bg-[#1A1A1A] text-white shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}}">
              👥 Cuadrillas del Día
            </button>
            <button onclick="window.VGT.switchSubTab('MASSIVE')" class="px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-all ${{currentSubTab === 'MASSIVE' ? 'bg-[#1A1A1A] text-white shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}}">
              📋 Pegado Masivo (WhatsApp)
            </button>
            <button onclick="window.VGT.switchSubTab('ROUTES')" class="px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-all ${{currentSubTab === 'ROUTES' ? 'bg-[#1A1A1A] text-white shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}}">
              🛣️ Rutas VGT (${{totalRoutes}})
            </button>
            <button onclick="window.VGT.switchSubTab('PERSONNEL')" class="px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-all ${{currentSubTab === 'PERSONNEL' ? 'bg-[#1A1A1A] text-white shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}}">
              🪪 Personal & Vehículos
            </button>
          </div>
        </div>

        <!-- BANNER DE GUARDIA SI APLICA -->
        ${{currentPresetMode === 'WEEKEND' ? `
        <div class="p-3.5 bg-amber-500/10 border border-amber-300 dark:border-amber-700/50 rounded-2xl flex items-center justify-between gap-3 text-xs text-amber-800 dark:text-amber-200">
          <div class="flex items-center gap-2">
            <span class="text-base">🛡️</span>
            <span><strong>Recordatorio de Cuadrilla de Guardia:</strong> Los equipos, técnicos y vehículos de guardia configurados están listos para el fin de semana o feriado. Los cambios se guardan automáticamente.</span>
          </div>
          <button onclick="window.VGT.loadLastGuardPreset()" class="px-3 py-1 bg-amber-500 text-slate-950 font-bold rounded-lg hover:bg-amber-400 shrink-0">
            Recargar Sábado
          </button>
        </div>
        ` : ''}}

        <!-- WORKSPACE PRINCIPAL (GRID 2 COLUMNAS) -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <!-- COLUMNA IZQUIERDA: ENTRADA / GESTIÓN -->
          <div class="lg:col-span-7 space-y-4">
            ${{renderLeftSubView()}}
          </div>

          <!-- COLUMNA DERECHA: SALIDA GERENCIAL & AUDITORÍA -->
          <div class="lg:col-span-5 space-y-4 lg:sticky lg:top-4">
            ${{renderRightManagerialView()}}
          </div>
        </div>
      </div>
    `;

    setupVgtListeners();
  }}

  function renderLeftSubView() {{
    if (currentSubTab === "TEAMS") {{
      return renderTeamsManagerView();
    }} else if (currentSubTab === "MASSIVE") {{
      return renderMassiveInputView();
    }} else if (currentSubTab === "ROUTES") {{
      return renderRoutesCatalogView();
    }} else if (currentSubTab === "PERSONNEL") {{
      return renderPersonnelCatalogView();
    }}
    return "";
  }}

  function renderTeamsManagerView() {{
    return `
      <div class="bg-white dark:bg-[#0c1427] rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 sm:p-5 shadow-sm space-y-4">
        <!-- HEADER DEL GESTOR -->
        <div class="flex items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div class="flex items-center gap-2">
            <span class="font-extrabold text-sm sm:text-base text-slate-800 dark:text-slate-100">Cuadrillas del Día</span>
            <span class="px-2 py-0.5 rounded-full text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">${{teamsState.length}}</span>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="window.VGT.addNewTeamCard()" class="px-3 py-1.5 text-xs font-bold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl transition-all">
              + Agregar Cuadrilla
            </button>
            <button onclick="window.VGT.clearAllTeamTickets()" class="px-3 py-1.5 text-xs font-bold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-xl transition-all">
              Limpiar Tickets
            </button>
          </div>
        </div>

        <!-- BUSCADOR RÁPIDO DE PERSONAL (TÉCNICOS & CHOFERES) -->
        <div class="bg-slate-50 dark:bg-slate-800/40 rounded-xl p-3 border border-slate-200/80 dark:border-slate-700/80 space-y-2.5">
          <div class="relative">
            <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none"></i>
            <input type="text" id="personnelSearchInput" placeholder="Buscar personal por nombre, cédula o teléfono (ej. Alexis, Machado, 12731...)"
              oninput="window.VGT.handleLivePersonnelSearch(this.value)"
              class="input-modern w-full pl-8 pr-3 py-2 text-xs border border-slate-200 dark:border-slate-700 rounded-xl focus:border-brand-500">
          </div>
          <div class="flex items-center gap-1.5 flex-wrap">
            <button onclick="window.VGT.setPersonnelFilter('ALL', this)" class="px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all ${{currentPersonnelFilter === 'ALL' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300'}}">
              Todos (${{techniciansDB.length + driversDB.length}})
            </button>
            <button onclick="window.VGT.setPersonnelFilter('AFECTACIONES', this)" class="px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all ${{currentPersonnelFilter === 'AFECTACIONES' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300'}}">
              ⚠️ Afectaciones (${{techniciansDB.filter(t => t.block === 'AFECTACIONES').length}})
            </button>
            <button onclick="window.VGT.setPersonnelFilter('SOPORTE', this)" class="px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all ${{currentPersonnelFilter === 'SOPORTE' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300'}}">
              🎫 Soporte (${{techniciansDB.filter(t => t.block !== 'AFECTACIONES').length}})
            </button>
            <button onclick="window.VGT.setPersonnelFilter('CHOFER', this)" class="px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all ${{currentPersonnelFilter === 'CHOFER' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300'}}">
              🚐 Choferes (${{driversDB.length}})
            </button>
          </div>
          <!-- Live floating results panel -->
          <div id="personnelSearchResults" class="hidden max-h-56 overflow-y-auto space-y-1.5 custom-scrollbar pt-2 border-t border-slate-200 dark:border-slate-700"></div>
        </div>

        <!-- LISTADO DE TARJETAS DE CUADRILLA -->
        <div class="space-y-3.5" id="teamsContainer">
          ${{renderTeamCardsHtml()}}
        </div>
      </div>
    `;
  }}

  function renderTeamCardsHtml() {{
    const driverOptions = driversDB.map(d => `<option value="${{d.name}}">${{d.name}} (${{d.cedula}})</option>`).join("");
    const vehOptions = vehiclesDB.map(v => `<option value="${{v.model}}|${{v.plate}}">${{v.model}} · ${{v.plate}}</option>`).join("");

    return teamsState.map((tm, idx) => {{
      const acts = parseTicketsText(tm.rawTickets || "");
      let conVgt = 0;
      acts.forEach(a => {{
        const v = a.manualVgt || getVGTForAddress(a.address, a.onu, a.zona);
        if (v && v !== "SIN NÚMERO") conVgt++;
      }});

      const isAfectacion = tm.type.includes("AFECTACION");

      return `
        <div class="bg-slate-50/60 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800/80 rounded-2xl p-4 space-y-3.5 hover:border-slate-300 dark:hover:border-slate-700 transition-all" id="teamCard_${{idx}}">
          <!-- CABECERA DE LA CUADRILLA -->
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <div class="flex items-center gap-2.5">
              <div class="w-8 h-8 rounded-xl bg-[#1A1A1A] text-[#FFC107] font-black text-xs flex items-center justify-center shadow-xs" id="teamAvatar_${{idx}}">
                ${{(tm.letter || tm.id || 'EQ').substring(0, 3)}}
              </div>
              <div class="flex items-center gap-1.5">
                <span class="text-xs font-bold text-slate-500 uppercase">Equipo:</span>
                <input type="text" value="${{tm.letter || tm.id || ''}}" onchange="window.VGT.handleTeamLetterChange(${{idx}}, this.value)"
                  class="w-16 px-2 py-0.5 text-xs font-black uppercase text-slate-800 dark:text-slate-100 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-center focus:border-brand-500">
              </div>
              <select onchange="window.VGT.handleTeamTypeChange(${{idx}}, this.value)"
                class="text-xs font-bold px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200">
                <option value="AFECTACIONES" ${{isAfectacion ? 'selected' : ''}}>⚠️ Afectaciones</option>
                <option value="SOPORTE TÉCNICO" ${{!isAfectacion ? 'selected' : ''}}>🎫 Soporte Técnico</option>
              </select>
            </div>

            <div class="flex items-center gap-2">
              <span class="text-[11px] font-bold px-2 py-0.5 rounded-full ${{acts.length > 0 ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300' : 'bg-slate-200/60 text-slate-500'}}">
                ${{acts.length}} ${{acts.length === 1 ? 'actividad' : 'actividades'}} (${{conVgt}} con VGT)
              </span>
              <button onclick="window.VGT.clearSingleTeamTickets(${{idx}})" title="Limpiar tickets" class="p-1.5 text-slate-400 hover:text-amber-500 rounded-lg">
                <i class="fa-solid fa-eraser text-xs"></i>
              </button>
              <button onclick="window.VGT.removeTeamCard(${{idx}})" title="Eliminar cuadrilla" class="p-1.5 text-slate-400 hover:text-rose-500 rounded-lg">
                <i class="fa-solid fa-trash-can text-xs"></i>
              </button>
            </div>
          </div>

          <!-- FILA DE TÉCNICOS (CHIPS) -->
          <div class="space-y-1.5">
            <div class="flex items-center justify-between text-xs font-semibold text-slate-600 dark:text-slate-300">
              <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Técnicos Asignados:</span>
              <span class="text-[10px] text-slate-400 font-medium">Escribe y presiona Enter</span>
            </div>
            <div class="flex items-center gap-1.5 flex-wrap">
              ${{(tm.techs || []).map(tName => {{
                const tObj = findTechnician(tName);
                const label = tObj ? `${{tObj.name}} (${{tObj.cedula}})` : tName;
                return `
                  <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 shadow-2xs">
                    <span>${{label}}</span>
                    <button type="button" onclick="window.VGT.removeTechFromTeam(${{idx}}, '${{tName}}')" class="text-slate-400 hover:text-rose-500">×</button>
                  </span>
                `;
              }}).join("")}}
              <div class="relative inline-flex items-center">
                <input type="text" placeholder="+ Agregar técnico..." onkeydown="if(event.key==='Enter') {{ window.VGT.handleInlineTechAdd(${{idx}}, this); }}"
                  class="px-2.5 py-1 text-xs border border-dashed border-slate-300 dark:border-slate-700 rounded-lg bg-transparent focus:border-brand-500 focus:bg-white dark:focus:bg-slate-800">
              </div>
            </div>
          </div>

          <!-- FILA DE CHOFER Y VEHÍCULO -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            <div>
              <label class="block text-[11px] font-bold text-slate-400 uppercase mb-1">Chofer:</label>
              <select onchange="window.VGT.handleTeamDriverChange(${{idx}}, this.value)"
                class="input-modern w-full px-2.5 py-1.5 text-xs border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200">
                <option value="">(Sin chofer asignado)</option>
                ${{driversDB.map(d => `<option value="${{d.name}}" ${{tm.driver === d.name ? 'selected' : ''}}>${{d.name}} (${{d.cedula}})</option>`).join("")}}
              </select>
            </div>
            <div>
              <label class="block text-[11px] font-bold text-slate-400 uppercase mb-1">Vehículo y Placa:</label>
              <select onchange="window.VGT.handleTeamVehicleChange(${{idx}}, this.value)"
                class="input-modern w-full px-2.5 py-1.5 text-xs border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200">
                <option value="|">(Sin vehículo)</option>
                ${{vehiclesDB.map(v => `<option value="${{v.model}}|${{v.plate}}" ${{tm.vehicle === v.model && tm.plate === v.plate ? 'selected' : ''}}>${{v.model}} · ${{v.plate}}</option>`).join("")}}
              </select>
            </div>
          </div>

          <!-- TEXTAREA DE TICKETS / DIRECCIONES -->
          <div>
            <div class="flex items-center justify-between text-xs mb-1">
              <label class="text-[11px] font-bold text-slate-400 uppercase">Tickets / Direcciones del día:</label>
              <span class="text-[10px] text-slate-400 font-medium">Una dirección por línea o formato de ticket</span>
            </div>
            <textarea rows="3" placeholder="Pega aquí los tickets o direcciones del día..."
              oninput="window.VGT.updateTeamTickets(${{idx}}, this.value)"
              class="input-modern w-full p-2.5 text-xs border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 resize-y">${{tm.rawTickets || ''}}</textarea>
          </div>
        </div>
      `;
    }}).join("");
  }}

  function renderMassiveInputView() {{
    return `
      <div class="bg-white dark:bg-[#0c1427] rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 sm:p-5 shadow-sm space-y-4">
        <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div>
            <h3 class="font-extrabold text-sm sm:text-base text-slate-800 dark:text-slate-100">Pegado Masivo de Texto (WhatsApp)</h3>
            <p class="text-xs text-slate-500">Pega el reporte completo enviado por WhatsApp. El sistema detectará equipos, integrantes y direcciones automáticamente.</p>
          </div>
          <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
            Auto-Parser VGT
          </span>
        </div>
        <textarea id="massiveRawInput" rows="16" oninput="window.VGT.handleMassiveInput()" placeholder="Pega aquí el reporte completo con todos los equipos...
Ejemplo:
====================================
EQUIPO 'M' DE AFECTACIONES
NÚMERO DE ACTIVIDADES: 3
TÉCNICO(S):
JOE MACHADO
GERAL ANDRES ARIAS
VEHÍCULO: RICH ZN, PLACA: A00CR8G

LOS TEQUES, EL CABOTAJE
LOS TEQUES, EL PANADERO
===================================="
          class="input-modern w-full p-4 font-mono text-xs border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 resize-y"></textarea>
      </div>
    `;
  }}

  function renderRoutesCatalogView() {{
    return `
      <div class="bg-white dark:bg-[#0c1427] rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 sm:p-5 shadow-sm space-y-4">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div>
            <h3 class="font-extrabold text-sm sm:text-base text-slate-800 dark:text-slate-100">Catálogo de Rutas VGT (${{routesDB.length}})</h3>
            <p class="text-xs text-slate-500">Inventario oficial de rutas, postes en uso y correlativos VGT.</p>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="window.VGT.showAddRouteModal()" class="px-3 py-1.5 text-xs font-bold text-white bg-gradient-to-r from-brand-600 to-brand-500 rounded-xl shadow-xs">
              + Nueva Ruta VGT
            </button>
            <button onclick="window.VGT.resetDefaultRoutes()" class="px-3 py-1.5 text-xs font-bold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 rounded-xl">
              Restablecer
            </button>
          </div>
        </div>

        <div class="relative">
          <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none"></i>
          <input type="text" id="routeSearchInput" oninput="window.VGT.filterRoutesTable(this.value)" placeholder="Buscar por código VGT o descripción..."
            class="input-modern w-full pl-8 pr-3 py-2 text-xs border border-slate-200 dark:border-slate-700 rounded-xl">
        </div>

        <div class="max-h-[460px] overflow-y-auto custom-scrollbar border border-slate-200 dark:border-slate-800 rounded-xl">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 font-bold border-b border-slate-200 dark:border-slate-700 sticky top-0">
              <tr>
                <th class="p-2.5">Código VGT</th>
                <th class="p-2.5">Descripción / Sector</th>
                <th class="p-2.5">Postes</th>
                <th class="p-2.5">Distancia</th>
                <th class="p-2.5 text-right">Acción</th>
              </tr>
            </thead>
            <tbody id="routesTableBody" class="divide-y divide-slate-100 dark:divide-slate-800">
              ${{renderRoutesTableRows(routesDB)}}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }}

  function renderRoutesTableRows(list) {{
    return list.map((r, i) => `
      <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors">
        <td class="p-2.5 font-mono font-bold text-brand-600 dark:text-brand-400">${{r.vgt || '-'}}</td>
        <td class="p-2.5 font-semibold text-slate-800 dark:text-slate-200">${{r.description || '-'}}</td>
        <td class="p-2.5 text-slate-500">${{r.postes || '-'}}</td>
        <td class="p-2.5 text-slate-500">${{r.distancia_km ? r.distancia_km + ' km' : '-'}}</td>
        <td class="p-2.5 text-right">
          <button onclick="window.VGT.editRoute(${{i}})" class="text-slate-400 hover:text-brand-500 p-1"><i class="fa-solid fa-pen-to-square"></i></button>
          <button onclick="window.VGT.deleteRoute(${{i}})" class="text-slate-400 hover:text-rose-500 p-1 ml-1"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>
    `).join("");
  }}

  function renderPersonnelCatalogView() {{
    return `
      <div class="bg-white dark:bg-[#0c1427] rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 sm:p-5 shadow-sm space-y-4">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div>
            <h3 class="font-extrabold text-sm sm:text-base text-slate-800 dark:text-slate-100">Directorio de Personal & Vehículos</h3>
            <p class="text-xs text-slate-500">Gestión de técnicos (${{techniciansDB.length}}), choferes (${{driversDB.length}}) y vehículos (${{vehiclesDB.length}}).</p>
          </div>
          <div class="inline-flex p-1 bg-slate-100 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
            <button onclick="window.VGT.switchPersonnelSubTab('TECHS')" class="px-3 py-1 rounded-lg text-xs font-bold ${{currentPersonnelSubTab === 'TECHS' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'text-slate-600 dark:text-slate-300'}}">Técnicos (${{techniciansDB.length}})</button>
            <button onclick="window.VGT.switchPersonnelSubTab('DRIVERS')" class="px-3 py-1 rounded-lg text-xs font-bold ${{currentPersonnelSubTab === 'DRIVERS' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'text-slate-600 dark:text-slate-300'}}">Choferes (${{driversDB.length}})</button>
            <button onclick="window.VGT.switchPersonnelSubTab('VEHS')" class="px-3 py-1 rounded-lg text-xs font-bold ${{currentPersonnelSubTab === 'VEHS' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'text-slate-600 dark:text-slate-300'}}">Vehículos (${{vehiclesDB.length}})</button>
          </div>
        </div>

        <div class="max-h-[460px] overflow-y-auto custom-scrollbar border border-slate-200 dark:border-slate-800 rounded-xl">
          ${{renderPersonnelTableContent()}}
        </div>
      </div>
    `;
  }}

  function renderPersonnelTableContent() {{
    if (currentPersonnelSubTab === "TECHS") {{
      return `
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 font-bold border-b border-slate-200 dark:border-slate-700 sticky top-0">
            <tr>
              <th class="p-2.5">Nombre</th>
              <th class="p-2.5">Cédula</th>
              <th class="p-2.5">Teléfono</th>
              <th class="p-2.5">Bloque / Cargo</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            ${{techniciansDB.map(t => `
              <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                <td class="p-2.5 font-bold text-slate-800 dark:text-slate-200">${{t.name}}</td>
                <td class="p-2.5 font-mono text-slate-500">${{t.cedula || '-'}}</td>
                <td class="p-2.5 text-slate-500 font-mono">${{t.phone || '-'}}</td>
                <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${{t.block === 'AFECTACIONES' ? 'bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300' : 'bg-brand-100 text-brand-800 dark:bg-brand-950/60 dark:text-brand-300'}}">${{t.cargo || t.block || 'TÉCNICO'}}</span></td>
              </tr>
            `).join("")}}
          </tbody>
        </table>
      `;
    }} else if (currentPersonnelSubTab === "DRIVERS") {{
      return `
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 font-bold border-b border-slate-200 dark:border-slate-700 sticky top-0">
            <tr>
              <th class="p-2.5">Nombre</th>
              <th class="p-2.5">Cédula</th>
              <th class="p-2.5">Teléfono</th>
              <th class="p-2.5">Cargo</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            ${{driversDB.map(d => `
              <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                <td class="p-2.5 font-bold text-slate-800 dark:text-slate-200">${{d.name}}</td>
                <td class="p-2.5 font-mono text-slate-500">${{d.cedula || '-'}}</td>
                <td class="p-2.5 text-slate-500 font-mono">${{d.phone || '-'}}</td>
                <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">${{d.cargo || 'CHOFER'}}</span></td>
              </tr>
            `).join("")}}
          </tbody>
        </table>
      `;
    }} else {{
      return `
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 font-bold border-b border-slate-200 dark:border-slate-700 sticky top-0">
            <tr>
              <th class="p-2.5">Modelo</th>
              <th class="p-2.5">Placa</th>
              <th class="p-2.5">Último Uso</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            ${{vehiclesDB.map(v => `
              <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                <td class="p-2.5 font-bold text-slate-800 dark:text-slate-200">${{v.model}}</td>
                <td class="p-2.5 font-mono font-bold text-brand-600 dark:text-brand-400">${{v.plate}}</td>
                <td class="p-2.5 text-slate-500">${{v.lastSeen || '-'}}</td>
              </tr>
            `).join("")}}
          </tbody>
        </table>
      `;
    }}
  }}

  function renderRightManagerialView() {{
    const outputText = generateManagerialText();

    return `
      <div class="bg-white dark:bg-[#0c1427] rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 sm:p-5 shadow-sm space-y-3.5">
        <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div class="flex items-center gap-2">
            <span class="font-extrabold text-sm sm:text-base text-slate-800 dark:text-slate-100">Formato de Salida Gerencial</span>
          </div>
          <div class="inline-flex p-1 bg-slate-100 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
            <button onclick="window.VGT.setOutputView('TEXT')" class="px-2.5 py-1 text-xs font-bold rounded-lg ${{currentOutputView === 'TEXT' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'text-slate-500'}}">
              WhatsApp
            </button>
            <button onclick="window.VGT.setOutputView('AUDIT')" class="px-2.5 py-1 text-xs font-bold rounded-lg ${{currentOutputView === 'AUDIT' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'text-slate-500'}}">
              Auditoría VGT
            </button>
          </div>
        </div>

        ${{currentOutputView === 'TEXT' ? `
        <div class="relative">
          <pre id="formattedOutput" class="p-3.5 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl font-mono text-[11px] text-slate-800 dark:text-slate-200 overflow-x-auto max-h-[580px] custom-scrollbar whitespace-pre-wrap">${{outputText || '(Sin actividades para mostrar)'}}</pre>
        </div>
        ` : `
        <div class="max-h-[580px] overflow-y-auto custom-scrollbar border border-slate-200 dark:border-slate-800 rounded-xl">
          <table class="w-full text-left text-[11px]">
            <thead class="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold border-b border-slate-200 dark:border-slate-700 sticky top-0">
              <tr>
                <th class="p-2">Eq.</th>
                <th class="p-2">VGT</th>
                <th class="p-2">Dirección</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
              ${{parsedActivitiesStore.map(a => `
                <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                  <td class="p-2 font-bold text-slate-700 dark:text-slate-300">${{a.teamName}}</td>
                  <td class="p-2 font-mono font-bold ${{a.vgt === 'SIN NÚMERO' ? 'text-rose-500' : 'text-emerald-600 dark:text-emerald-400'}}">${{a.vgt}}</td>
                  <td class="p-2 text-slate-600 dark:text-slate-300 line-clamp-1">${{a.address}}</td>
                </tr>
              `).join("")}}
            </tbody>
          </table>
        </div>
        `}}

        <div class="flex items-center gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
          <button onclick="window.VGT.copyToClipboard()" class="btn-modern flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-bold text-white bg-gradient-to-r from-emerald-600 to-emerald-500 rounded-xl shadow-md shadow-emerald-500/20">
            <i class="fa-brands fa-whatsapp text-sm"></i> Copiar Formato WhatsApp
          </button>
          <button onclick="window.VGT.exportToExcel()" class="btn-modern inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-bold text-white bg-gradient-to-r from-brand-600 to-brand-500 rounded-xl shadow-md shadow-brand-500/20">
            <i class="fa-solid fa-file-excel text-sm"></i> Excel
          </button>
        </div>
      </div>
    `;
  }}

  function generateManagerialText() {{
    parsedActivitiesStore = [];
    let blocks = [];

    if (currentInputMode === "TEAM_MANAGER") {{
      teamsState.forEach((team, teamIdx) => {{
        const activities = parseTicketsText(team.rawTickets || "");
        if (activities.length === 0) return;

        let out = [];
        if (blocks.length === 0) {{
          out.push("POWERLINK CORP.");
          out.push("");
        }}

        const headerTitle = team.customTitle || `EQUIPO "${{team.letter || team.id}}"`;
        out.push(`${{headerTitle}} DE ${{team.type}}`);
        out.push("");
        out.push(`NÚMERO DE ACTIVIDADES: ${{activities.length}}`);
        out.push("");

        if (team.techs && team.techs.length > 0) {{
          out.push("TÉCNICO(S):");
          team.techs.forEach(tName => {{
            const tObj = findTechnician(tName);
            if (tObj) out.push(`${{tObj.name}}, ${{tObj.cedula}} (${{tObj.phone}})`);
            else out.push(tName);
          }});
        }}

        if (team.driver) {{
          out.push(`CHOFER: ${{team.driver}}`);
        }}

        if (team.vehicle && team.plate) {{
          out.push(`VEHÍCULO: ${{team.vehicle}}, PLACA: ${{team.plate}}`);
        }}

        out.push("");
        out.push("====================================");
        out.push("");
        out.push("DATOS DE ACTIVIDAD:");
        out.push("");

        activities.forEach((act, actIdx) => {{
          const vgtCode = act.manualVgt || getVGTForAddress(act.address, act.onu, act.zona);
          parsedActivitiesStore.push({{
            teamIdx: teamIdx,
            teamName: headerTitle,
            teamType: team.type,
            actIdx: actIdx,
            address: act.address,
            vgt: vgtCode,
            onu: act.onu,
            zona: act.zona
          }});

          out.push(`N° DE CORRELATIVO (VGT): ${{vgtCode}}`);
          out.push(`TIPO DE ACTIVIDAD: ${{team.type}}`);
          out.push("CANTIDAD DE POSTES A TRABAJAR: 1");
          out.push(`DIRECCIÓN: ${{act.address}}`);
          out.push("====================================");
          if (actIdx < activities.length - 1) {{
            out.push("");
          }}
        }});

        blocks.push(out.join("\\n"));
      }});
    }} else {{
      const rawText = document.getElementById("massiveRawInput") ? document.getElementById("massiveRawInput").value : "";
      const activities = parseTicketsText(rawText);
      if (activities.length > 0) {{
        let out = ["POWERLINK CORP.", "", "ACTIVIDADES PROCESADAS: " + activities.length, "===================================="];
        activities.forEach((act, idx) => {{
          const vgtCode = getVGTForAddress(act.address, act.onu, act.zona);
          parsedActivitiesStore.push({{
            teamIdx: 0,
            teamName: "PROCESADO",
            teamType: "SOPORTE TÉCNICO",
            actIdx: idx,
            address: act.address,
            vgt: vgtCode,
            onu: act.onu,
            zona: act.zona
          }});
          out.push(`N° DE CORRELATIVO (VGT): ${{vgtCode}}`);
          out.push(`DIRECCIÓN: ${{act.address}}`);
          out.push("====================================");
        }});
        blocks.push(out.join("\\n"));
      }}
    }}

    return blocks.join("\\n\\n");
  }}

  function setupVgtListeners() {{
    // Listeners setup
  }}

  // User Actions
  function switchPreset(mode) {{
    currentPresetMode = mode;
    if (mode === "WEEKDAY") {{
      teamsState = JSON.parse(JSON.stringify(WEEKDAY_TEAMS));
      sanitizeTeamTechNames(teamsState);
      showToast("Lunes a Viernes activado (10 equipos)");
    }} else {{
      const saved = localStorage.getItem("powerlink_vgt_guard");
      if (saved) {{
        try {{ teamsState = JSON.parse(saved); }} catch(e) {{ teamsState = JSON.parse(JSON.stringify(DEFAULT_WEEKEND_TEAMS)); }}
      }} else {{
        teamsState = JSON.parse(JSON.stringify(DEFAULT_WEEKEND_TEAMS));
      }}
      showToast("Modo Guardia / Fin de Semana activado");
    }}
    saveVgtAll();
    renderVgt();
  }}

  function switchSubTab(tab) {{
    currentSubTab = tab;
    if (tab === "MASSIVE") currentInputMode = "MASSIVE_INPUT";
    else currentInputMode = "TEAM_MANAGER";
    renderVgt();
  }}

  function switchPersonnelSubTab(tab) {{
    currentPersonnelSubTab = tab;
    renderVgt();
  }}

  function setOutputView(view) {{
    currentOutputView = view;
    renderVgt();
  }}

  function saveGuardPreset() {{
    localStorage.setItem("powerlink_vgt_guard", JSON.stringify(teamsState));
    showToast("Plantilla de Guardia guardada exitosamente");
  }}

  function loadLastGuardPreset() {{
    const saved = localStorage.getItem("powerlink_vgt_guard");
    if (saved) {{
      teamsState = JSON.parse(saved);
      showToast("Guardia cargada");
      renderVgt();
    }} else {{
      showToast("No hay guardia previa guardada");
    }}
  }}

  function resetCurrentPreset() {{
    if (confirm("¿Desea restablecer las cuadrillas a los valores por defecto?")) {{
      teamsState = JSON.parse(JSON.stringify(WEEKDAY_TEAMS));
      sanitizeTeamTechNames(teamsState);
      saveVgtAll();
      renderVgt();
      showToast("Cuadrillas restablecidas");
    }}
  }}

  function handleTeamLetterChange(idx, val) {{
    if (!teamsState[idx]) return;
    teamsState[idx].letter = val.trim().toUpperCase();
    saveVgtAll();
    renderVgt();
  }}

  function handleTeamTypeChange(idx, val) {{
    if (!teamsState[idx]) return;
    teamsState[idx].type = val;
    saveVgtAll();
    renderVgt();
  }}

  function handleTeamDriverChange(idx, val) {{
    if (!teamsState[idx]) return;
    teamsState[idx].driver = val;
    saveVgtAll();
    renderVgt();
  }}

  function handleTeamVehicleChange(idx, val) {{
    if (!teamsState[idx]) return;
    const parts = val.split("|");
    teamsState[idx].vehicle = parts[0] || "";
    teamsState[idx].plate = parts[1] || "";
    saveVgtAll();
    renderVgt();
  }}

  function updateTeamTickets(idx, val) {{
    if (!teamsState[idx]) return;
    teamsState[idx].rawTickets = val;
    saveVgtAll();
    const outPre = document.getElementById("formattedOutput");
    if (outPre) outPre.innerText = generateManagerialText();
  }}

  function clearSingleTeamTickets(idx) {{
    if (!teamsState[idx]) return;
    teamsState[idx].rawTickets = "";
    saveVgtAll();
    renderVgt();
    showToast("Tickets de cuadrilla limpiados");
  }}

  function clearAllTeamTickets() {{
    if (confirm("¿Desea limpiar los tickets de todos los equipos?")) {{
      teamsState.forEach(t => t.rawTickets = "");
      saveVgtAll();
      renderVgt();
      showToast("Todos los tickets han sido vaciados");
    }}
  }}

  function addNewTeamCard() {{
    const letter = prompt("Ingrese la letra o identificador de la nueva cuadrilla (ej: K, Z, NOCTURNA):", "N");
    if (!letter) return;
    const cleanLetter = letter.trim().toUpperCase();
    teamsState.push({{
      id: "EXTRA-" + Date.now(),
      letter: cleanLetter,
      customTitle: `EQUIPO "${{cleanLetter}}"`,
      type: "SOPORTE TÉCNICO",
      active: true,
      techs: [],
      driver: "",
      vehicle: "EMPIRE HORSE",
      plate: "AK7J67M",
      rawTickets: ""
    }});
    saveVgtAll();
    renderVgt();
    showToast(`Cuadrilla EQUIPO "${{cleanLetter}}" agregada`);
  }}

  function removeTeamCard(idx) {{
    if (teamsState.length <= 1) return;
    const team = teamsState[idx];
    if (confirm(`¿Desea eliminar la cuadrilla EQUIPO "${{team.letter || team.id}}"?`)) {{
      teamsState.splice(idx, 1);
      saveVgtAll();
      renderVgt();
      showToast("Cuadrilla eliminada");
    }}
  }}

  function removeTechFromTeam(idx, techName) {{
    if (!teamsState[idx]) return;
    teamsState[idx].techs = (teamsState[idx].techs || []).filter(t => t !== techName);
    saveVgtAll();
    renderVgt();
  }}

  function handleInlineTechAdd(idx, inputEl) {{
    const val = (inputEl.value || "").trim();
    if (!val) return;
    const found = findTechnician(val);
    if (found) {{
      if (!teamsState[idx].techs.includes(found.name)) {{
        teamsState[idx].techs.push(found.name);
        saveVgtAll();
        renderVgt();
      }}
    }} else {{
      teamsState[idx].techs.push(val.toUpperCase());
      saveVgtAll();
      renderVgt();
    }}
    inputEl.value = "";
  }}

  function setPersonnelFilter(cat, btn) {{
    currentPersonnelFilter = cat;
    const input = document.getElementById("personnelSearchInput");
    handleLivePersonnelSearch(input ? input.value : "");
  }}

  function handleLivePersonnelSearch(query) {{
    const resultsPanel = document.getElementById("personnelSearchResults");
    if (!resultsPanel) return;

    const q = normalizeText(query);
    if (!q && currentPersonnelFilter === "ALL") {{
      resultsPanel.classList.add("hidden");
      return;
    }}

    let list = [];
    if (currentPersonnelFilter === "ALL" || currentPersonnelFilter === "AFECTACIONES" || currentPersonnelFilter === "SOPORTE") {{
      techniciansDB.forEach(t => {{
        if (currentPersonnelFilter === "AFECTACIONES" && t.block !== "AFECTACIONES") return;
        if (currentPersonnelFilter === "SOPORTE" && t.block === "AFECTACIONES") return;
        list.push({{
          type: "TECH",
          name: t.name,
          cedula: t.cedula,
          phone: t.phone,
          block: t.block || "SOPORTE",
          cargo: t.cargo || "Técnico"
        }});
      }});
    }}

    if (currentPersonnelFilter === "ALL" || currentPersonnelFilter === "CHOFER") {{
      driversDB.forEach(d => {{
        list.push({{
          type: "DRIVER",
          name: d.name,
          cedula: d.cedula,
          phone: d.phone,
          block: "CHOFER",
          cargo: d.cargo || "Chofer"
        }});
      }});
    }}

    let matches = list;
    if (q) {{
      matches = list.filter(p => 
        normalizeText(p.name).includes(q) ||
        normalizeText(p.cedula).includes(q) ||
        normalizeText(p.phone).includes(q) ||
        normalizeText(p.cargo).includes(q)
      );
    }}

    if (matches.length === 0) {{
      resultsPanel.innerHTML = `<div class="p-3 text-center text-xs text-slate-400">No se encontró personal coincidente</div>`;
      resultsPanel.classList.remove("hidden");
      return;
    }}

    const teamOpts = teamsState.map((tm, i) => `<option value="${{i}}">Equipo "${{tm.letter || tm.id}}"</option>`).join("");

    resultsPanel.innerHTML = matches.slice(0, 15).map(p => {{
      let assignedTeam = null;
      teamsState.forEach(tm => {{
        if (tm.techs && tm.techs.some(t => normalizeText(t) === normalizeText(p.name))) assignedTeam = tm.letter || tm.id;
        if (tm.driver && normalizeText(tm.driver) === normalizeText(p.name)) assignedTeam = `${{tm.letter || tm.id}} (Chofer)`;
      }});

      return `
        <div class="flex items-center justify-between gap-2 p-2 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs">
          <div class="min-w-0">
            <div class="font-bold text-slate-800 dark:text-slate-100 truncate">${{p.name}}</div>
            <div class="text-[10px] text-slate-500 font-mono">${{p.cedula || '-'}} · ${{p.phone || '-'}} · ${{p.cargo}}</div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            ${{assignedTeam ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">Eq. ${{assignedTeam}}</span>` : `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">Disponible</span>`}}
            <select onchange="if(this.value!=='') {{ window.VGT.quickAssignPerson('${{p.name}}', ${{p.type === 'DRIVER'}}, this.value); this.value=''; }}"
              class="px-2 py-1 text-[11px] font-semibold border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-900">
              <option value="">Asignar a...</option>
              ${{teamOpts}}
            </select>
          </div>
        </div>
      `;
    }}).join("");

    resultsPanel.classList.remove("hidden");
  }}

  function quickAssignPerson(name, isDriver, teamIdx) {{
    teamIdx = parseInt(teamIdx);
    if (isNaN(teamIdx) || !teamsState[teamIdx]) return;

    if (isDriver) {{
      teamsState[teamIdx].driver = name;
      showToast(`${{name}} asignado como chofer`);
    }} else {{
      if (!teamsState[teamIdx].techs.includes(name)) {{
        teamsState[teamIdx].techs.push(name);
        showToast(`${{name}} añadido al equipo`);
      }}
    }}
    saveVgtAll();
    renderVgt();
  }}

  function handleMassiveInput() {{
    const outPre = document.getElementById("formattedOutput");
    if (outPre) outPre.innerText = generateManagerialText();
  }}

  function filterRoutesTable(q) {{
    const norm = normalizeText(q);
    const filtered = routesDB.filter(r => normalizeText(r.vgt).includes(norm) || normalizeText(r.description).includes(norm));
    const tbody = document.getElementById("routesTableBody");
    if (tbody) tbody.innerHTML = renderRoutesTableRows(filtered);
  }}

  function copyToClipboard() {{
    const text = document.getElementById("formattedOutput") ? document.getElementById("formattedOutput").innerText : generateManagerialText();
    if (!text || text.includes("(Sin actividades")) {{
      showToast("No hay actividades para copiar");
      return;
    }}
    navigator.clipboard.writeText(text).then(() => {{
      showToast("¡Formato de parte diario copiado para WhatsApp!");
    }});
  }}

  function exportToExcel() {{
    if (parsedActivitiesStore.length === 0) {{
      showToast("No hay actividades para exportar");
      return;
    }}

    if (typeof XLSX === "undefined") {{
      showToast("Biblioteca Excel no cargada todavía");
      return;
    }}

    const rows = [];
    const todayStr = new Date().toISOString().split("T")[0];

    parsedActivitiesStore.forEach((act, idx) => {{
      let techNames = "";
      let vehicleStr = "";

      if (currentInputMode === "TEAM_MANAGER" && teamsState[act.teamIdx]) {{
        techNames = (teamsState[act.teamIdx].techs || []).map(t => {{
          const found = findTechnician(t);
          return found ? `${{found.name}} (${{found.cedula}})` : t;
        }}).join(" / ");
        vehicleStr = `${{teamsState[act.teamIdx].vehicle || ''}} [${{teamsState[act.teamIdx].plate || ''}}]`;
      }}

      rows.push({{
        "Fecha": todayStr,
        "N°": idx + 1,
        "Equipo": act.teamName,
        "Tipo de Actividad": act.teamType,
        "Técnico(s)": techNames,
        "Vehículo y Placa": vehicleStr,
        "N° Correlativo (VGT)": act.vgt,
        "Postes": 1,
        "Dirección / Detalle": act.address
      }});
    }});

    const ws = XLSX.utils.json_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Partes Diarios VGT");
    XLSX.writeFile(wb, `Partes_Diarios_VGT_${{todayStr}}.xlsx`);
    showToast("¡Archivo Excel exportado con éxito!");
  }}

  // Window Exports
  window.VGT = {{
    getRoutes: () => routesDB,
    getTechs: () => techniciansDB,
    getDrivers: () => driversDB,
    getVehicles: () => vehiclesDB,
    getTeams: () => teamsState,
    getVGTForAddress,
    findTechnician,
    parseTicketsText,
    saveVgtAll,
    renderVgt,
    switchPreset,
    switchSubTab,
    switchPersonnelSubTab,
    setOutputView,
    saveGuardPreset,
    loadLastGuardPreset,
    resetCurrentPreset,
    handleTeamLetterChange,
    handleTeamTypeChange,
    handleTeamDriverChange,
    handleTeamVehicleChange,
    updateTeamTickets,
    clearSingleTeamTickets,
    clearAllTeamTickets,
    addNewTeamCard,
    removeTeamCard,
    removeTechFromTeam,
    handleInlineTechAdd,
    setPersonnelFilter,
    handleLivePersonnelSearch,
    quickAssignPerson,
    handleMassiveInput,
    filterRoutesTable,
    copyToClipboard,
    exportToExcel
  }};

  window.renderVgt = renderVgt;

}})();
''')

print('static/js/vgt_module.js fully built successfully!')
