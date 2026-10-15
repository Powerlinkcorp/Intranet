import ozmapRawHistory from "@/data/ozmap_history.json";

export interface OzmapDiscardedRecord {
  id: string;
  fecha_descarte: string;
  hora_descarte: string;
  timestamp: number;
  motivo_descarte: string;
  origen_paso: string;

  // Datos del abonado
  id_servicio: string;
  id_usuario: string;
  nombres: string;
  cedula: string;
  serial_onu: string;
  precinto: string;
  caja_nap: string;
  caja_oficial?: string;
  caja_sugerida?: string;
  codigo_ozmap: string;
  estado_campo?: "completo" | "falta_precinto" | "falta_caja" | "sin_reporte";
  tipo_cliente?: string;

  // Estado de verificación en OZmap
  estado_ozmap: "verificado" | "no_subido" | "reincorporado";
  detalles_verificacion?: {
    metodo: "api_en_vivo" | "bitacora_local" | "historico" | "manual";
    fecha_verificacion: string;
    ozmap_client_id?: string;
    caja_ozmap_registrada?: string;
    observacion?: string;
  };
  restaurado?: boolean;
  fecha_restauracion?: string;
}

export const DISCARDED_AUDIT_STORAGE_KEY = "ozmap_discarded_audit_history_v1";
export const RESTORED_CLIENTS_QUEUE_KEY = "ozmap_restored_clients_queue_v1";

// Helpers de limpieza de datos
function cleanDigits(val: unknown): string {
  if (val === undefined || val === null) return "";
  const s = String(val).trim();
  if (s.endsWith(".0")) return s.slice(0, -2).replace(/\D/g, "");
  return s.replace(/\D/g, "");
}

function cleanId(val: unknown): string {
  if (val === undefined || val === null) return "";
  const s = String(val).trim();
  return s.endsWith(".0") ? s.slice(0, -2) : s;
}

// Datos semilla representativos para el primer inicio
const INITIAL_SEED_DISCARDS: OzmapDiscardedRecord[] = [
  {
    id: "discard-seed-001",
    fecha_descarte: "2026-10-12",
    hora_descarte: "09:42",
    timestamp: 1791800520000,
    motivo_descarte: "Sin precinto reportado en campo",
    origen_paso: "Paso 1: Cotejo de Campo",
    id_servicio: "54890",
    id_usuario: "31820",
    nombres: "Carlos Eduardo Mendoza",
    cedula: "19456782",
    serial_onu: "VSOL00CC1122",
    precinto: "",
    caja_nap: "Montenegro - Mac - 04",
    caja_oficial: "Montenegro - Mac - 04",
    codigo_ozmap: "R-19456782-31820-54890",
    estado_campo: "falta_precinto",
    estado_ozmap: "no_subido",
  },
  {
    id: "discard-seed-002",
    fecha_descarte: "2026-10-12",
    hora_descarte: "11:15",
    timestamp: 1791806100000,
    motivo_descarte: "Caja NAP no encontrada en catálogo oficial",
    origen_paso: "Paso 2: Validación de Cajas",
    id_servicio: "55120",
    id_usuario: "32040",
    nombres: "Maria Alejandra Perez",
    cedula: "22340918",
    serial_onu: "ZTEGC89A1244",
    precinto: "4892011",
    caja_nap: "NAP-DESCONOCIDA-99",
    caja_oficial: "",
    codigo_ozmap: "R-22340918-32040-55120",
    estado_campo: "completo",
    estado_ozmap: "no_subido",
  },
  {
    id: "discard-seed-003",
    fecha_descarte: "2026-10-11",
    hora_descarte: "16:20",
    timestamp: 1791738000000,
    motivo_descarte: "Eliminado manualmente por operador (Datos duplicados)",
    origen_paso: "Paso 1: Cotejo de Campo",
    id_servicio: "54670",
    id_usuario: "31685",
    nombres: "Jabmil Rojas",
    cedula: "18740297",
    serial_onu: "VSOL00BA0982",
    precinto: "58656949",
    caja_nap: "Montenegro - Mac - 02",
    caja_oficial: "Montenegro - Mac - 02",
    codigo_ozmap: "R-18740297-31685-54670",
    estado_campo: "completo",
    estado_ozmap: "verificado",
    detalles_verificacion: {
      metodo: "historico",
      fecha_verificacion: "2026-10-11 16:25",
      ozmap_client_id: "hist-20260902-001",
      caja_ozmap_registrada: "Montenegro - Mac - 02",
      observacion: "Cliente registrado en OZmap históricamente.",
    },
  },
];

export function getDiscardedAuditRecords(): OzmapDiscardedRecord[] {
  if (typeof window === "undefined") return INITIAL_SEED_DISCARDS;
  try {
    const raw = localStorage.getItem(DISCARDED_AUDIT_STORAGE_KEY);
    if (!raw) {
      localStorage.setItem(DISCARDED_AUDIT_STORAGE_KEY, JSON.stringify(INITIAL_SEED_DISCARDS));
      return INITIAL_SEED_DISCARDS;
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : INITIAL_SEED_DISCARDS;
  } catch (e) {
    console.error("Error al leer descartes de OZmap:", e);
    return INITIAL_SEED_DISCARDS;
  }
}

export function saveDiscardedRecord(
  record: Omit<OzmapDiscardedRecord, "id" | "fecha_descarte" | "hora_descarte" | "timestamp" | "estado_ozmap"> & {
    id?: string;
    fecha_descarte?: string;
    hora_descarte?: string;
    timestamp?: number;
    estado_ozmap?: "verificado" | "no_subido" | "reincorporado";
  }
): OzmapDiscardedRecord {
  const current = getDiscardedAuditRecords();
  const now = new Date();
  const fecha = record.fecha_descarte || now.toISOString().slice(0, 10);
  const hora = record.hora_descarte || now.toTimeString().slice(0, 5);
  const timestamp = record.timestamp || Date.now();
  const uniqueId =
    record.id ||
    `discard-${Date.now()}-${cleanDigits(record.cedula) || cleanId(record.id_servicio) || Math.random().toString(36).slice(2, 6)}`;

  // Comprobar preliminarmente si ya está verificado en el histórico local o en bitácora
  let initialStatus: "verificado" | "no_subido" | "reincorporado" = record.estado_ozmap || "no_subido";
  let detalles: OzmapDiscardedRecord["detalles_verificacion"] | undefined = undefined;

  const localCheck = checkClientInLocalDatasets(record.cedula, record.id_servicio);
  if (localCheck.found) {
    initialStatus = "verificado";
    detalles = {
      metodo: localCheck.source === "bitacora" ? "bitacora_local" : "historico",
      fecha_verificacion: `${fecha} ${hora}`,
      caja_ozmap_registrada: localCheck.caja || "",
      observacion: `Encontrado en ${localCheck.source === "bitacora" ? "Bitácora local de subidas" : "Histórico consolidado de OZmap"}.`,
    };
  }

  const newRecord: OzmapDiscardedRecord = {
    ...record,
    id: uniqueId,
    fecha_descarte: fecha,
    hora_descarte: hora,
    timestamp,
    estado_ozmap: initialStatus,
    detalles_verificacion: detalles,
  };

  // Evitar duplicados exactos por cédula o id_servicio si ya estaba registrado
  const filtered = current.filter(
    (c) =>
      !(
        (record.cedula && cleanDigits(c.cedula) === cleanDigits(record.cedula)) &&
        (record.id_servicio && cleanId(c.id_servicio) === cleanId(record.id_servicio))
      )
  );

  const updated = [newRecord, ...filtered];
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(DISCARDED_AUDIT_STORAGE_KEY, JSON.stringify(updated));
      window.dispatchEvent(new Event("ozmap-discarded-updated"));
    } catch (e) {
      console.warn("Error guardando descarte en localStorage:", e);
    }
  }

  return newRecord;
}

export function saveDiscardedRecordsBatch(
  records: Array<
    Omit<OzmapDiscardedRecord, "id" | "fecha_descarte" | "hora_descarte" | "timestamp" | "estado_ozmap"> & {
      id?: string;
      fecha_descarte?: string;
      hora_descarte?: string;
      timestamp?: number;
      estado_ozmap?: "verificado" | "no_subido" | "reincorporado";
    }
  >
): OzmapDiscardedRecord[] {
  const current = getDiscardedAuditRecords();
  const now = new Date();
  const fecha = now.toISOString().slice(0, 10);
  const hora = now.toTimeString().slice(0, 5);
  const timestamp = Date.now();

  const createdRecords: OzmapDiscardedRecord[] = [];

  for (let i = 0; i < records.length; i++) {
    const r = records[i];
    const uniqueId =
      r.id ||
      `discard-${timestamp + i}-${cleanDigits(r.cedula) || cleanId(r.id_servicio) || Math.random().toString(36).slice(2, 6)}`;

    let status: "verificado" | "no_subido" | "reincorporado" = r.estado_ozmap || "no_subido";
    let detalles: OzmapDiscardedRecord["detalles_verificacion"] | undefined = undefined;

    const localCheck = checkClientInLocalDatasets(r.cedula, r.id_servicio);
    if (localCheck.found) {
      status = "verificado";
      detalles = {
        metodo: localCheck.source === "bitacora" ? "bitacora_local" : "historico",
        fecha_verificacion: `${fecha} ${hora}`,
        caja_ozmap_registrada: localCheck.caja || "",
        observacion: `Encontrado en ${localCheck.source === "bitacora" ? "Bitácora local de subidas" : "Histórico consolidado de OZmap"}.`,
      };
    }

    createdRecords.push({
      ...r,
      id: uniqueId,
      fecha_descarte: r.fecha_descarte || fecha,
      hora_descarte: r.hora_descarte || hora,
      timestamp: timestamp + i,
      estado_ozmap: status,
      detalles_verificacion: detalles,
    });
  }

  const existingMap = new Map<string, OzmapDiscardedRecord>();
  current.forEach((item) => {
    const key = `${cleanDigits(item.cedula)}_${cleanId(item.id_servicio)}`;
    existingMap.set(key, item);
  });

  createdRecords.forEach((item) => {
    const key = `${cleanDigits(item.cedula)}_${cleanId(item.id_servicio)}`;
    existingMap.set(key, item);
  });

  const updated = Array.from(existingMap.values()).sort((a, b) => b.timestamp - a.timestamp);

  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(DISCARDED_AUDIT_STORAGE_KEY, JSON.stringify(updated));
      window.dispatchEvent(new Event("ozmap-discarded-updated"));
    } catch (e) {
      console.warn("Error guardando lote de descartes:", e);
    }
  }

  return createdRecords;
}

export function updateDiscardedRecord(id: string, updates: Partial<OzmapDiscardedRecord>) {
  const current = getDiscardedAuditRecords();
  const updated = current.map((item) => (item.id === id ? { ...item, ...updates } : item));
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(DISCARDED_AUDIT_STORAGE_KEY, JSON.stringify(updated));
      window.dispatchEvent(new Event("ozmap-discarded-updated"));
    } catch (e) {
      console.warn("Error actualizando descarte:", e);
    }
  }
}

export function deleteDiscardedRecordPermanently(id: string) {
  const current = getDiscardedAuditRecords();
  const updated = current.filter((item) => item.id !== id);
  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(DISCARDED_AUDIT_STORAGE_KEY, JSON.stringify(updated));
      window.dispatchEvent(new Event("ozmap-discarded-updated"));
    } catch (e) {
      console.warn("Error eliminando descarte:", e);
    }
  }
}

export function clearDiscardedAuditRecords() {
  if (typeof window !== "undefined") {
    try {
      localStorage.removeItem(DISCARDED_AUDIT_STORAGE_KEY);
      window.dispatchEvent(new Event("ozmap-discarded-updated"));
    } catch (e) {
      console.warn("Error vaciando descartes:", e);
    }
  }
}

// Queue para restaurar clientes de vuelta a OZmap
export function queueClientForRestoration(client: OzmapDiscardedRecord) {
  if (typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem(RESTORED_CLIENTS_QUEUE_KEY);
    const list = raw ? JSON.parse(raw) : [];
    list.push(client);
    localStorage.setItem(RESTORED_CLIENTS_QUEUE_KEY, JSON.stringify(list));
    updateDiscardedRecord(client.id, {
      estado_ozmap: "reincorporado",
      restaurado: true,
      fecha_restauracion: new Date().toISOString(),
    });
  } catch (e) {
    console.error("Error encolando restauración:", e);
  }
}

// Verificación en fuentes de datos locales (Bitácora + ozmap_history.json)
export function checkClientInLocalDatasets(
  cedula: string,
  idServicio: string
): { found: boolean; source?: "bitacora" | "historico"; caja?: string; details?: Record<string, unknown> } {
  const cleanCed = cleanDigits(cedula);
  const cleanServ = cleanId(idServicio);

  if (!cleanCed && !cleanServ) return { found: false };

  // 1. Revisar bitácora en vivo de localStorage
  if (typeof window !== "undefined") {
    try {
      const rawBitacora = localStorage.getItem("ozmap_live_upload_history");
      if (rawBitacora) {
        const bitacora = JSON.parse(rawBitacora);
        if (Array.isArray(bitacora)) {
          const match = bitacora.find(
            (b: Record<string, unknown>) =>
              (cleanCed && cleanDigits(b.cedula) === cleanCed) ||
              (cleanServ && cleanId(b.id_servicio) === cleanServ)
          );
          if (match) {
            return {
              found: true,
              source: "bitacora",
              caja: (match.caja_nap as string) || (match.caja_oficial as string),
              details: match,
            };
          }
        }
      }
    } catch (e) {
      console.warn("Error leyendo bitácora local:", e);
    }
  }

  // 2. Revisar historial de 600 registros
  if (Array.isArray(ozmapRawHistory)) {
    const matchHist = (ozmapRawHistory as Record<string, unknown>[]).find(
      (h) =>
        (cleanCed && cleanDigits(h.cedula) === cleanCed) ||
        (cleanServ && cleanId(h.id_servicio) === cleanServ)
    );
    if (matchHist) {
      return {
        found: true,
        source: "historico",
        caja: (matchHist.caja_nap as string) || (matchHist.caja_original as string),
        details: matchHist,
      };
    }
  }

  return { found: false };
}

// Verificación en vivo contra la API de OZmap
export async function verifyClientInOzmapApi(
  client: OzmapDiscardedRecord,
  serverUrl: string,
  authHeader: string
): Promise<{
  found: boolean;
  ozmapId?: string;
  code?: string;
  observation?: string;
  source: string;
}> {
  try {
    const cleanServ = cleanId(client.id_servicio);
    const clientCode = client.codigo_ozmap;

    // 1. Buscar por código exacto
    if (clientCode) {
      const filterExact = JSON.stringify([{ property: "code", operator: "=", value: clientCode }]);
      const checkRes = await fetch(`${serverUrl}/api/v2/clients?filter=${encodeURIComponent(filterExact)}`, {
        headers: { Authorization: authHeader, "Content-Type": "application/json" },
      });
      if (checkRes.ok) {
        const checkData = await checkRes.json();
        const rows: Array<{ id?: string; _id?: string; code?: string; observation?: string }> = checkData.rows || [];
        const match = rows.find((r) => r.code === clientCode);
        if (match && (match.id || match._id)) {
          return {
            found: true,
            ozmapId: match.id || match._id,
            code: match.code,
            observation: match.observation || "",
            source: "API OZmap (Código exacto)",
          };
        }
      }
    }

    // 2. Buscar por sufijo de servicio (-ID_SERVICIO)
    if (cleanServ) {
      const filterService = JSON.stringify([{ property: "code", operator: "like", value: `-${cleanServ}` }]);
      const checkServRes = await fetch(`${serverUrl}/api/v2/clients?filter=${encodeURIComponent(filterService)}`, {
        headers: { Authorization: authHeader, "Content-Type": "application/json" },
      });
      if (checkServRes.ok) {
        const servData = await checkServRes.json();
        const servRows: Array<{ id?: string; _id?: string; code?: string; observation?: string }> = servData.rows || [];
        const match = servRows.find((r) => r.code && r.code.endsWith(`-${cleanServ}`));
        if (match && (match.id || match._id)) {
          return {
            found: true,
            ozmapId: match.id || match._id,
            code: match.code,
            observation: match.observation || "",
            source: "API OZmap (ID de Servicio)",
          };
        }
      }
    }

    // 3. Fallback a datasets locales
    const local = checkClientInLocalDatasets(client.cedula, client.id_servicio);
    if (local.found) {
      return {
        found: true,
        ozmapId: local.details?.id ? String(local.details.id) : "local",
        code: client.codigo_ozmap,
        observation: local.details?.caja_nap ? `Caja: ${String(local.details.caja_nap)}` : "",
        source: local.source === "bitacora" ? "Bitácora Local" : "Histórico Consolidado",
      };
    }

    return { found: false, source: "No encontrado" };
  } catch (err) {
    console.warn("Fallo verificando cliente en API OZmap:", err);
    // Si la API falla por CORS o red, al menos verificamos contra el dataset local
    const local = checkClientInLocalDatasets(client.cedula, client.id_servicio);
    if (local.found) {
      return {
        found: true,
        ozmapId: local.details?.id ? String(local.details.id) : "local",
        code: client.codigo_ozmap,
        observation: local.details?.caja_nap ? `Caja: ${String(local.details.caja_nap)}` : "",
        source: local.source === "bitacora" ? "Bitácora Local" : "Histórico Consolidado",
      };
    }
    return { found: false, source: "Error de conexión" };
  }
}
