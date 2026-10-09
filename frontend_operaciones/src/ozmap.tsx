"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import * as XLSX from "xlsx";
import {
  Globe2,
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronLeft,
  ChevronRight,
  Eye,
  Check,
  Settings,
  Brain,
  Download,
  Upload,
  RefreshCw,
  FileSpreadsheet,
  Trash2,
  SlidersHorizontal,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  Zap,
  AlertTriangle,
  Database,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

// Dataset histórico de 600 registros
import ozmapRawHistory from "@/data/ozmap_history.json";

// --- TIPOS Y MODELOS ---

export type ProcessType =
  | "whatsapp_rubpi_cruce"
  | "validador_cajas_ozmap"
  | "auditoria_rubpi_ozmap"
  | "ozmap_rubpi_cruce";

export interface BoxMatchCandidate {
  box: string;
  score: number;
}

export interface ComparisonRow {
  id: string;
  codigo_ozmap?: string;
  id_servicio?: string;
  id_usuario?: string;
  nombres?: string;
  cedula?: string;
  serial_onu?: string;
  precinto?: string;
  caja_nap?: string;
  caja_original?: string;
  caja_sugerida?: string;
  caja_candidatas?: BoxMatchCandidate[];
  caja_seleccionada?: string;
  caja_manual_input?: boolean;
  caja_match_score?: number;
  caja_oficial?: string;
  caja_estado_tipo?: "valida" | "autocorregida" | "aprendida" | "no_encontrada" | "sin_caja" | "sin_base";
  estado_campo?: "completo" | "falta_precinto" | "falta_caja" | "sin_reporte";
  estado_caja_ozmap?: string;
  estado_rubpi?: string;
  coincide_onu?: string;
  match_method?: string;
  matched?: boolean;
  deleted?: boolean;
  tipo_cliente?: string;
  caja_archivo?: string;
  caja_match_score_str?: string;
  estado_auditoria?: string;
  caja_ozmap?: string;
  propiedad_ozmap?: boolean;
  subido_ozmap?: boolean;
}

export interface OzmapBoxRecord {
  "Caja NAP"?: string;
  Nombre?: string;
  nombre?: string;
  name?: string;
  code?: string;
  id?: string;
  _id?: string;
  coords?: [number, number];
  lng?: number;
  lat?: number;
  project?: string;
  pole?: string;
}

export interface LearnedBoxItem {
  rawOriginal: string;
  officialBox: string;
  date: string;
  isPrimary?: boolean;
}

export interface BitacoraEntry {
  id: string;
  fecha: string;
  hora: string;
  id_servicio?: string;
  id_usuario?: string;
  cliente: string;
  cedula: string;
  serial_onu?: string;
  precinto?: string;
  caja_nap: string;
  caja_original?: string;
  tipo_accion: "nuevo" | "actualizado";
  codigo_ozmap: string;
  georreferenciado: boolean;
  estado: string;
  timestamp?: number;
}

// Constantes de configuración
const GOOGLE_SHEETS_WP_ID = "1UZvhPyYhw8NV-_wwPESWQiGfqnwkASABr4JSBPRJoUw";
const GOOGLE_SHEETS_BOXES_ID = "14Qiaf8xwYtSc5Xjdcd8zsOGqKPTCKvlXFgcymkX8sDE";
const GOOGLE_SHEETS_BOXES_GID = "503177434";

const DEFAULT_SERVER_URL = "https://powerlink.ozmap.com.br:9994";
const DEFAULT_USER = "api.powerlink";
const DEFAULT_PASS = "gxgq459n";

// --- HELPERS DE NORMALIZACIÓN & LEVENSHTEIN ---

function normalizeText(txt: unknown): string {
  if (!txt) return "";
  return String(txt)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

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

function cleanKey(k: string): string {
  return String(k || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, "");
}

function isCedulaKey(k: string): boolean {
  const ck = cleanKey(k);
  return ck.includes("cedula") || ck.includes("cdula") || ck.includes("rif");
}

function isIdServicioKey(k: string): boolean {
  const ck = cleanKey(k);
  if (ck.includes("asociado")) return false;
  return ck.includes("idservicio") || ck.includes("iddeservicio") || ck === "servicio" || ck === "id";
}

function isIdUsuarioKey(k: string): boolean {
  const ck = cleanKey(k);
  return ck.includes("idusuario") || ck === "usuario";
}

function isNombresKey(k: string): boolean {
  const ck = cleanKey(k);
  return (
    ck === "nombres" ||
    ck === "nombre" ||
    ck === "cliente" ||
    ck.includes("nombredelcliente") ||
    ck.includes("nombredelusuari") ||
    ck.includes("razonsocial") ||
    ck.includes("razon") ||
    ck.includes("social")
  );
}

function formatOzmapClientCode(client: Partial<ComparisonRow>): string {
  if (!client) return "";
  const rawCed = cleanDigits(client.cedula);
  const rawUser = cleanDigits(client.id_usuario);
  const rawServ = cleanDigits(client.id_servicio);
  return `R-${rawCed}-${rawUser}-${rawServ}`;
}

function isNameMatch(nameA: string, nameB: string): boolean {
  const normA = normalizeText(nameA);
  const normB = normalizeText(nameB);
  if (!normA || !normB) return false;
  if (normA === normB) return true;

  const wordsA = normA.split(" ").filter((w) => w.length > 2);
  const wordsB = normB.split(" ").filter((w) => w.length > 2);

  if (wordsA.length >= 2 && wordsB.length >= 2) {
    const allAInB = wordsA.every((w) => wordsB.includes(w));
    const allBInA = wordsB.every((w) => wordsA.includes(w));
    if (allAInB || allBInA) return true;
  }
  return false;
}

function levenshteinDistance(s1: string, s2: string): number {
  const m = s1.length;
  const n = s2.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));

  for (let i = 0; i <= m; i++) dp[i][0] = i;
  for (let j = 0; j <= n; j++) dp[0][j] = j;

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      const cost = s1[i - 1] === s2[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
    }
  }
  return dp[m][n];
}

function stringSimilarityRatio(s1: string, s2: string): number {
  if (!s1 && !s2) return 100;
  if (!s1 || !s2) return 0;
  if (s1 === s2) return 100;
  const maxLen = Math.max(s1.length, s2.length);
  if (maxLen === 0) return 100;
  const dist = levenshteinDistance(s1, s2);
  return Math.round((1 - dist / maxLen) * 100);
}

function tokenSortRatio(s1: string, s2: string): number {
  if (!s1 || !s2) return 0;
  const clean1 = String(s1).toLowerCase().replace(/[^a-z0-9\s]/g, " ").trim().split(/\s+/).filter(Boolean).sort().join(" ");
  const clean2 = String(s2).toLowerCase().replace(/[^a-z0-9\s]/g, " ").trim().split(/\s+/).filter(Boolean).sort().join(" ");
  return stringSimilarityRatio(clean1, clean2);
}

function getBoxName(b: unknown): string {
  if (!b) return "";
  if (typeof b === "string") return b.trim();
  const obj = b as Record<string, unknown>;
  return String(obj["Caja NAP"] || obj["Nombre"] || obj["nombre"] || obj["Box"] || obj.name || obj.code || obj.box || "").trim();
}

function parseInstallDate(val: unknown): Date | null {
  if (!val) return null;
  if (val instanceof Date) {
    return new Date(val.getFullYear(), val.getMonth(), val.getDate(), 12, 0, 0);
  }
  if (typeof val === "number") {
    const d = new Date((val - 25569) * 86400 * 1000);
    const offset = d.getTimezoneOffset() * 60000;
    const localD = new Date(d.getTime() + offset);
    return new Date(localD.getFullYear(), localD.getMonth(), localD.getDate(), 12, 0, 0);
  }
  const str = String(val).trim();
  if (!str) return null;
  const ymd = str.match(/^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})/);
  if (ymd) return new Date(parseInt(ymd[1], 10), parseInt(ymd[2], 10) - 1, parseInt(ymd[3], 10), 12, 0, 0);
  const dmy = str.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})/);
  if (dmy) {
    let y = parseInt(dmy[3], 10);
    if (y < 100) y += 2000;
    return new Date(y, parseInt(dmy[2], 10) - 1, parseInt(dmy[1], 10), 12, 0, 0);
  }
  const parsed = new Date(str);
  if (!isNaN(parsed.getTime())) {
    return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate(), 12, 0, 0);
  }
  return null;
}

function parseGoogleSheetDate(dateStr: unknown): Date | null {
  if (!dateStr) return null;
  if (dateStr instanceof Date) {
    return new Date(dateStr.getFullYear(), dateStr.getMonth(), dateStr.getDate(), 12, 0, 0);
  }
  if (typeof dateStr === "number") {
    const d = new Date((dateStr - 25569) * 86400 * 1000);
    const offset = d.getTimezoneOffset() * 60000;
    const localD = new Date(d.getTime() + offset);
    return new Date(localD.getFullYear(), localD.getMonth(), localD.getDate(), 12, 0, 0);
  }
  const cleanStr = String(dateStr).trim();
  const match = cleanStr.match(/^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})/);
  if (match) {
    const day = parseInt(match[1], 10);
    const month = parseInt(match[2], 10) - 1;
    let year = parseInt(match[3], 10);
    if (year < 100) year += 2000;
    return new Date(year, month, day, 12, 0, 0);
  }
  const ymd = cleanStr.match(/^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})/);
  if (ymd) {
    return new Date(parseInt(ymd[1], 10), parseInt(ymd[2], 10) - 1, parseInt(ymd[3], 10), 12, 0, 0);
  }
  const parsed = new Date(cleanStr);
  if (!isNaN(parsed.getTime())) {
    return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate(), 12, 0, 0);
  }
  return null;
}

function cedMatch(cedRubpi: string, cedWp: string): boolean {
  if (!cedRubpi || !cedWp) return false;
  if (cedRubpi === cedWp) return true;
  if (Math.abs(cedRubpi.length - cedWp.length) <= 1) {
    if (cedRubpi.includes(cedWp) || cedWp.includes(cedRubpi)) return true;
  }
  return false;
}

interface ConsolidateWpClient {
  cedula: string;
  nombres: string;
  precinto: string;
  caja_nap: string;
  onu: string;
  plan: string;
  date: Date | null;
}

function consolidateWpReportSheets(
  activacionRows: Record<string, unknown>[],
  instalacionRows: Record<string, unknown>[],
  dateStart: Date | null,
  dateEnd: Date | null,
  filterDateActive: boolean
): ConsolidateWpClient[] {
  const clientsMap: Record<string, ConsolidateWpClient> = {};
  const clientsByName: Record<string, ConsolidateWpClient> = {};

  function processRow(row: Record<string, unknown>) {
    // 1. Verificar fecha del reporte
    const dateVal = row["Fecha"] || row["Fecha Timestamp"] || "";
    const rowDate = parseGoogleSheetDate(dateVal);
    if (filterDateActive) {
      if (!rowDate) return;
      const checkDate = new Date(rowDate.getFullYear(), rowDate.getMonth(), rowDate.getDate(), 12, 0, 0);
      if (dateStart) {
        const compareStart = new Date(dateStart.getFullYear(), dateStart.getMonth(), dateStart.getDate(), 0, 0, 0);
        if (checkDate < compareStart) return;
      }
      if (dateEnd) {
        const compareEnd = new Date(dateEnd.getFullYear(), dateEnd.getMonth(), dateEnd.getDate(), 23, 59, 59);
        if (checkDate > compareEnd) return;
      }
    }

    // 2. Extraer datos
    const nombres = String(row["Cliente"] || "").trim();
    const rawCed = row["Cédula"] || row["Cdula"] || "";
    const cleanCed = cleanDigits(rawCed);
    const precinto = String(row["Precinto"] || "").trim();
    const caja = String(row["Caja Nap"] || row["Caja-Nap"] || row["CAJA-NAP"] || "").trim();
    const onu = String(row["ONU"] || row["PON/ONU"] || "").trim();
    const plan = String(row["Plan"] || row["PLAN"] || "").trim();

    if (!nombres && !cleanCed) return;

    const record: ConsolidateWpClient = {
      cedula: cleanCed,
      nombres,
      precinto,
      caja_nap: caja,
      onu,
      plan,
      date: rowDate,
    };

    if (cleanCed) {
      if (!clientsMap[cleanCed]) {
        clientsMap[cleanCed] = record;
      } else {
        const existing = clientsMap[cleanCed];
        if (!existing.precinto && record.precinto) existing.precinto = record.precinto;
        if (!existing.caja_nap && record.caja_nap) existing.caja_nap = record.caja_nap;
        if (!existing.onu && record.onu) existing.onu = record.onu;
        if (!existing.plan && record.plan) existing.plan = record.plan;
        if (record.nombres.length > existing.nombres.length) existing.nombres = record.nombres;
      }
    } else {
      const normName = normalizeText(nombres);
      if (normName) {
        if (!clientsByName[normName]) {
          clientsByName[normName] = record;
        } else {
          const existing = clientsByName[normName];
          if (!existing.precinto && record.precinto) existing.precinto = record.precinto;
          if (!existing.caja_nap && record.caja_nap) existing.caja_nap = record.caja_nap;
          if (!existing.onu && record.onu) existing.onu = record.onu;
          if (!existing.plan && record.plan) existing.plan = record.plan;
        }
      }
    }
  }

  if (Array.isArray(activacionRows)) activacionRows.forEach(processRow);
  if (Array.isArray(instalacionRows)) instalacionRows.forEach(processRow);

  const finalList = Object.values(clientsMap);
  Object.keys(clientsByName).forEach((normName) => {
    const record = clientsByName[normName];
    const matchesExisting = finalList.find((c) => normalizeText(c.nombres) === normName);
    if (matchesExisting) {
      if (!matchesExisting.precinto && record.precinto) matchesExisting.precinto = record.precinto;
      if (!matchesExisting.caja_nap && record.caja_nap) matchesExisting.caja_nap = record.caja_nap;
      if (!matchesExisting.onu && record.onu) matchesExisting.onu = record.onu;
      if (!matchesExisting.plan && record.plan) matchesExisting.plan = record.plan;
    } else {
      finalList.push(record);
    }
  });

  return finalList;
}

function fuzzyMatchBox(
  rawBox: string,
  officialBoxList: string[],
  learnedMap: Record<string, LearnedBoxItem>,
  threshold = 70
): {
  matchedBox: string;
  score: number;
  status: ComparisonRow["caja_estado_tipo"];
  label: string;
  candidates: BoxMatchCandidate[];
} {
  if (!rawBox || !String(rawBox).trim()) {
    return { matchedBox: "", score: 0, status: "sin_caja", label: "⚠️ Sin Caja", candidates: [] };
  }

  const rawTrim = String(rawBox).trim();
  const rawUpper = rawTrim.toUpperCase();
  const rawNorm = rawUpper.replace(/[^A-Z0-9]/g, "");

  // 0. Base de aprendizaje previo
  if (learnedMap) {
    const learnedEntry = learnedMap[rawUpper] || (rawNorm ? learnedMap[rawNorm] : null);
    if (learnedEntry && learnedEntry.officialBox) {
      return {
        matchedBox: learnedEntry.officialBox,
        score: 100,
        status: "aprendida",
        label: "🧠 Aprendida",
        candidates: [{ box: learnedEntry.officialBox, score: 100 }],
      };
    }
  }

  if (!Array.isArray(officialBoxList) || officialBoxList.length === 0) {
    return { matchedBox: "", score: 0, status: "sin_base", label: "⚠️ Sin Base OZmap", candidates: [] };
  }

  // 1. Exacto
  for (const offName of officialBoxList) {
    if (offName && offName.trim().toUpperCase() === rawUpper) {
      return {
        matchedBox: offName,
        score: 100,
        status: "valida",
        label: "✅ OZmap (100%)",
        candidates: [{ box: offName, score: 100 }],
      };
    }
  }

  // 2. Coincidencias alfanuméricas y Token Sort Ratio
  const candidateScores: BoxMatchCandidate[] = [];
  let bestMatch = "";
  let bestScore = 0;

  for (const offName of officialBoxList) {
    if (!offName) continue;
    const offUpper = offName.trim().toUpperCase();
    const offNorm = offUpper.replace(/[^A-Z0-9]/g, "");

    let score = 0;
    if (offNorm === rawNorm && offNorm !== "") {
      score = 95;
    } else {
      score = tokenSortRatio(rawTrim, offName);
    }

    if (score >= threshold) {
      candidateScores.push({ box: offName, score });
      if (score > bestScore) {
        bestScore = score;
        bestMatch = offName;
      }
    }
  }

  // Ordenar candidatos por puntaje descendente y eliminar duplicados
  candidateScores.sort((a, b) => b.score - a.score);
  const seenCandidates = new Set<string>();
  const topCandidates: BoxMatchCandidate[] = [];
  for (const c of candidateScores) {
    const u = c.box.toUpperCase();
    if (!seenCandidates.has(u)) {
      seenCandidates.add(u);
      topCandidates.push(c);
      if (topCandidates.length >= 5) break;
    }
  }

  if (bestScore >= threshold && bestMatch) {
    return {
      matchedBox: bestMatch,
      score: bestScore,
      status: "autocorregida",
      label: `⚠️ Sugerida (${bestScore}%)`,
      candidates: topCandidates,
    };
  }

  return { matchedBox: "", score: 0, status: "no_encontrada", label: "❌ No Existe", candidates: [] };
}

// Descargar Google Sheets via GViz JSON API
async function fetchGvizSheet(spreadsheetId: string, sheetName: string): Promise<Record<string, unknown>[]> {
  const url = `https://docs.google.com/spreadsheets/d/${spreadsheetId}/gviz/tq?tqx=out:json&sheet=${encodeURIComponent(sheetName)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`No se pudo conectar con la pestaña ${sheetName} de Google Sheets.`);

  const rawText = await res.text();
  const startIdx = rawText.indexOf("setResponse(");
  if (startIdx === -1) throw new Error(`Formato de respuesta inválido en la pestaña ${sheetName}.`);

  const jsonStart = startIdx + 12;
  const jsonEnd = rawText.lastIndexOf(")");
  if (jsonEnd === -1) throw new Error(`Formato de respuesta inválido en ${sheetName}.`);

  const rawData = JSON.parse(rawText.substring(jsonStart, jsonEnd));
  if (rawData.status === "error") {
    throw new Error(rawData.errors?.[0]?.detailed_message || `Error en pestaña ${sheetName}`);
  }

  const table = rawData.table;
  if (!table || !table.cols || !table.rows) throw new Error(`La pestaña ${sheetName} no tiene datos.`);

  const cols = table.cols.map((c: { label?: string }) => c.label || "");
  const rows: Record<string, unknown>[] = [];

  table.rows.forEach((r: { c?: { f?: string; v?: unknown }[] }) => {
    const rowObj: Record<string, unknown> = {};
    if (r && r.c) {
      r.c.forEach((cell, idx) => {
        const colName = cols[idx];
        if (colName) {
          rowObj[colName] = cell ? (cell.f !== undefined ? cell.f : cell.v !== undefined ? cell.v : "") : "";
        }
      });
    }
    rows.push(rowObj);
  });

  return rows;
}

export function OzmapModule() {
  // Pestaña principal: Asistente de Cruce vs Bitácora de Cargas
  const [mainViewTab, setMainViewTab] = useState<"cruce" | "bitacora">("cruce");

  // Proceso activo
  const [activeProcess, setActiveProcess] = useState<ProcessType>("whatsapp_rubpi_cruce");
  const [wizardStep, setWizardStep] = useState<1 | 2>(1);

  // Estados de datasets de entrada
  const [rubpiRows, setRubpiRows] = useState<Record<string, unknown>[]>([]);
  const [wpActivacionRows, setWpActivacionRows] = useState<Record<string, unknown>[]>([]);
  const [wpInstalacionRows, setWpInstalacionRows] = useState<Record<string, unknown>[]>([]);
  const [ozmapBoxes, setOzmapBoxes] = useState<OzmapBoxRecord[]>([]);
  const [cajasInputRows, setCajasInputRows] = useState<Record<string, unknown>[]>([]);
  const [ozmapExportedClients, setOzmapExportedClients] = useState<Record<string, unknown>[]>([]);
  const [ozmapSupportSheet, setOzmapSupportSheet] = useState<Record<string, unknown>[]>([]);

  // Listado oficial ordenado y memoizado de nombres de cajas para autocompletado y validaciones
  const officialBoxNames = useMemo(() => {
    const seen = new Set<string>();
    const list: string[] = [];
    ozmapBoxes.forEach((b) => {
      const name = getBoxName(b);
      if (name && !seen.has(name)) {
        seen.add(name);
        list.push(name);
      }
    });
    return list.sort();
  }, [ozmapBoxes]);

  // Estados de carga/sincronización UI
  const [isSyncingRubpi, setIsSyncingRubpi] = useState(false);
  const [isSyncingWp, setIsSyncingWp] = useState(false);
  const [isSyncingOzBoxes, setIsSyncingOzBoxes] = useState(false);
  const [isSyncingSupport, setIsSyncingSupport] = useState(false);
  const [isUploadingToApi, setIsUploadingToApi] = useState(false);
  const [uploadProgressText, setUploadProgressText] = useState("");
  const [uploadingClientId, setUploadingClientId] = useState<string | null>(null);

  // Estado del proceso de cotejo en segundo plano (No bloqueante)
  const [isMatchingRunning, setIsMatchingRunning] = useState(false);
  const [matchingProgress, setMatchingProgress] = useState<{
    current: number;
    total: number;
    percent: number;
    statusText: string;
  }>({ current: 0, total: 0, percent: 0, statusText: "" });

  // Parámetros opcionales
  const [filterDateActive, setFilterDateActive] = useState(false);
  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [includeIptv, setIncludeIptv] = useState(false);

  // Bitácora de clientes ya subidos a OZmap
  const [liveUploadHistory, setLiveUploadHistory] = useState<BitacoraEntry[]>([]);
  const [bitacoraViewMode, setBitacoraViewMode] = useState<"live" | "historical">("live");
  const [bitacoraSearch, setBitacoraSearch] = useState("");

  // Resultados del Cruce
  const [comparisonResults, setComparisonResults] = useState<ComparisonRow[]>([]);
  const [activeTableFilter, setActiveTableFilter] = useState<string>("all");
  const [tableSearch, setTableSearch] = useState("");
  const [pageSize, setPageSize] = useState<number | "all">(25);
  const [currentPage, setCurrentPage] = useState(1);

  // Modales
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
  const [isLearnedModalOpen, setIsLearnedModalOpen] = useState(false);
  const [selectedDetailClient, setSelectedDetailClient] = useState<ComparisonRow | null>(null);
  const [isStep1WarningModalOpen, setIsStep1WarningModalOpen] = useState(false);
  const [incompleteClients, setIncompleteClients] = useState<ComparisonRow[]>([]);

  // Formulario API
  const [apiServer, setApiServer] = useState(DEFAULT_SERVER_URL);
  const [apiUser, setApiUser] = useState(DEFAULT_USER);
  const [apiPass, setApiPass] = useState(DEFAULT_PASS);

  // Cajas aprendidas
  const [learnedBoxes, setLearnedBoxes] = useState<Record<string, LearnedBoxItem>>({});
  const [newLearnedRaw, setNewLearnedRaw] = useState("");
  const [newLearnedOfficial, setNewLearnedOfficial] = useState("");
  const [learnedSearch, setLearnedSearch] = useState("");

  // Feedback
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);

  // Referencias para file inputs
  const rubpiFileInputRef = useRef<HTMLInputElement>(null);
  const wpFileInputRef = useRef<HTMLInputElement>(null);
  const boxesFileInputRef = useRef<HTMLInputElement>(null);
  const cajasInputFileInputRef = useRef<HTMLInputElement>(null);
  const ozmapExportedClientsRef = useRef<HTMLInputElement>(null);
  const ozmapSupportSheetRef = useRef<HTMLInputElement>(null);

  // Cargar credenciales, cajas aprendidas y caché inicial de OZmap
  useEffect(() => {
    try {
      let storedServer = localStorage.getItem("ozmap_api_server");
      if (!storedServer || storedServer.includes("powerlink.com.ve") || !storedServer.includes(":9994")) {
        storedServer = DEFAULT_SERVER_URL;
        localStorage.setItem("ozmap_api_server", storedServer);
      }
      setApiServer(storedServer);

      let storedUser = localStorage.getItem("ozmap_api_user");
      if (!storedUser) {
        storedUser = DEFAULT_USER;
        localStorage.setItem("ozmap_api_user", storedUser);
      }
      setApiUser(storedUser);

      let storedPass = localStorage.getItem("ozmap_api_pass");
      if (!storedPass) {
        storedPass = DEFAULT_PASS;
        localStorage.setItem("ozmap_api_pass", storedPass);
      }
      setApiPass(storedPass);

      const storedLearned = localStorage.getItem("ozmap_learned_box_corrections");
      if (storedLearned) {
        try {
          setLearnedBoxes(JSON.parse(storedLearned));
        } catch (e) {
          console.error(e);
        }
      }

      const cachedBoxes = localStorage.getItem("cached_ozmap_sheet");
      if (cachedBoxes) {
        try {
          const parsed = JSON.parse(cachedBoxes);
          if (Array.isArray(parsed) && parsed.length > 0) {
            const valid = parsed.filter((b: OzmapBoxRecord) => getBoxName(b).length > 0);
            if (valid.length > 0) {
              setOzmapBoxes(valid);
            }
          }
        } catch (e) {
          console.error(e);
        }
      }

      const storedHistory = localStorage.getItem("ozmap_live_upload_history");
      if (storedHistory) {
        try {
          const parsed = JSON.parse(storedHistory);
          if (Array.isArray(parsed)) {
            setLiveUploadHistory(parsed);
          }
        } catch (e) {
          console.error(e);
        }
      } else {
        const seed: BitacoraEntry[] = [
          {
            id: "hist-seed-6172221",
            fecha: "2026-09-30",
            hora: "17:15",
            id_servicio: "55756",
            id_usuario: "32564",
            cliente: "Yasminia Hernandez",
            cedula: "6172221",
            serial_onu: "ZTEGCA7CF4DD",
            precinto: "60792296",
            caja_nap: "Progreso-MAC-02",
            caja_original: "Progreso-MAC-02",
            tipo_accion: "nuevo",
            codigo_ozmap: "R-6172221-32564-55756",
            georreferenciado: true,
            estado: "Sincronizado",
            timestamp: 1790802900000,
          },
        ];
        setLiveUploadHistory(seed);
        localStorage.setItem("ozmap_live_upload_history", JSON.stringify(seed));
      }
    } catch (err) {
      console.error("Error al iniciar OZmap:", err);
    }
  }, []);

  const showToast = (text: string, type: "success" | "error" | "info" = "info") => {
    setStatusMessage({ text, type });
    setTimeout(() => setStatusMessage(null), 4000);
  };

  // Helper para registrar un cliente subido en la bitácora persistente
  const recordUploadedClient = (client: ComparisonRow, boxName: string, precintoVal: string) => {
    const now = new Date();
    const fecha = now.toISOString().slice(0, 10);
    const hora = now.toTimeString().slice(0, 5);
    const clientCode = formatOzmapClientCode(client);

    const newRecord: BitacoraEntry = {
      id: `upload-${Date.now()}-${client.id_servicio || client.cedula || Math.random().toString(36).slice(2, 6)}`,
      fecha,
      hora,
      id_servicio: client.id_servicio || "",
      id_usuario: client.id_usuario || "",
      cliente: client.nombres || "",
      cedula: client.cedula || "",
      serial_onu: client.serial_onu || "",
      precinto: precintoVal || client.precinto || "",
      caja_nap: boxName || client.caja_oficial || "",
      caja_original: client.caja_original || client.caja_nap || "",
      tipo_accion: "nuevo",
      codigo_ozmap: clientCode,
      georreferenciado: true,
      estado: "Sincronizado",
      timestamp: Date.now(),
    };

    setLiveUploadHistory((prev) => {
      const filtered = prev.filter(
        (h) =>
          !(
            (client.cedula && cleanDigits(h.cedula) === cleanDigits(client.cedula)) ||
            (client.id_servicio && cleanId(h.id_servicio) === cleanId(client.id_servicio))
          )
      );
      const updated = [newRecord, ...filtered];
      try {
        localStorage.setItem("ozmap_live_upload_history", JSON.stringify(updated));
      } catch (e) {
        console.warn("Error guardando bitácora en localStorage:", e);
      }
      return updated;
    });
  };

  const handleRemoveFromLiveBitacora = (id: string, clienteName?: string) => {
    setLiveUploadHistory((prev) => {
      const updated = prev.filter((r) => r.id !== id);
      try {
        localStorage.setItem("ozmap_live_upload_history", JSON.stringify(updated));
      } catch (e) {
        console.warn("Error actualizando bitácora en localStorage:", e);
      }
      return updated;
    });
    showToast(`"${clienteName || id}" retirado de la bitácora. Volverá a aparecer en futuros cotejos.`, "info");
  };

  // Cambio de proceso activo
  const handleSelectProcess = (procId: ProcessType) => {
    setActiveProcess(procId);
    setWizardStep(1);
    setComparisonResults([]);
    setActiveTableFilter("all");
    setCurrentPage(1);
  };

  // Helper para procesar subida manual de cualquier archivo Excel o JSON
  const handleGenericFileUpload = (
    e: React.ChangeEvent<HTMLInputElement>,
    setter: (data: Record<string, unknown>[]) => void,
    labelName: string
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const isJson = file.name.endsWith(".json");
    const reader = new FileReader();

    if (isJson) {
      reader.onload = (ev) => {
        try {
          const parsed = JSON.parse(ev.target?.result as string);
          const arr = Array.isArray(parsed) ? parsed : [parsed];
          setter(arr);
          showToast(`${labelName}: ${arr.length} filas cargadas con éxito.`, "success");
        } catch {
          showToast(`Error al leer archivo JSON de ${labelName}.`, "error");
        }
      };
      reader.readAsText(file);
    } else {
      reader.onload = (ev) => {
        try {
          const data = new Uint8Array(ev.target?.result as ArrayBuffer);
          const wb = XLSX.read(data, { type: "array", cellDates: true });
          const firstSheet = wb.SheetNames[0];
          const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(wb.Sheets[firstSheet], { defval: "" });
          setter(rows);
          showToast(`${labelName}: ${rows.length} filas cargadas desde Excel.`, "success");
        } catch {
          showToast(`Error al leer archivo Excel de ${labelName}.`, "error");
        }
      };
      reader.readAsArrayBuffer(file);
    }
  };

  // Helper para procesar subida manual de archivo Excel de WhatsApp (detecta hojas de activación e instalación)
  const handleWhatsappFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = new Uint8Array(ev.target?.result as ArrayBuffer);
        const wb = XLSX.read(data, { type: "array", cellDates: true });
        let actFound = false;
        let instFound = false;
        wb.SheetNames.forEach((sheetName) => {
          const norm = sheetName.toLowerCase();
          if (norm.includes("activac")) {
            const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(wb.Sheets[sheetName], { defval: "" });
            setWpActivacionRows(rows);
            actFound = true;
          } else if (norm.includes("instalac")) {
            const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(wb.Sheets[sheetName], { defval: "" });
            setWpInstalacionRows(rows);
            instFound = true;
          }
        });
        if (!actFound && !instFound) {
          const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(wb.Sheets[wb.SheetNames[0]], { defval: "" });
          setWpInstalacionRows(rows);
          showToast(`WhatsApp: ${rows.length} filas cargadas desde la hoja ${wb.SheetNames[0]}.`, "success");
        } else {
          showToast(`WhatsApp cargado: activaciones e instalaciones sincronizadas desde el archivo.`, "success");
        }
      } catch {
        showToast("Error al procesar el archivo Excel de WhatsApp.", "error");
      }
    };
    reader.readAsArrayBuffer(file);
  };

  // 1. Sincronizar Rubpi desde IIS
  const handleSyncRubpiFromIis = async () => {
    setIsSyncingRubpi(true);
    try {
      const [resRes, resJur] = await Promise.all([
        fetch("/descargas_powerlink/base_residencial.xlsx"),
        fetch("/descargas_powerlink/base_juridico.xlsx"),
      ]);

      if (!resRes.ok) throw new Error(`No se pudo descargar base_residencial.xlsx (HTTP ${resRes.status})`);
      if (!resJur.ok) throw new Error(`No se pudo descargar base_juridico.xlsx (HTTP ${resJur.status})`);

      const [bufRes, bufJur] = await Promise.all([resRes.arrayBuffer(), resJur.arrayBuffer()]);

      const wbRes = XLSX.read(new Uint8Array(bufRes), { type: "array", cellDates: true });
      const wbJur = XLSX.read(new Uint8Array(bufJur), { type: "array", cellDates: true });

      const dataRes = XLSX.utils.sheet_to_json<Record<string, unknown>>(wbRes.Sheets[wbRes.SheetNames[0]], { defval: "" });
      const dataJur = XLSX.utils.sheet_to_json<Record<string, unknown>>(wbJur.Sheets[wbJur.SheetNames[0]], { defval: "" });

      dataRes.forEach((r) => (r["__tipo_origen__"] = "RESIDENCIAL"));
      dataJur.forEach((r) => (r["__tipo_origen__"] = "JURÍDICO"));

      const combined = [...dataRes, ...dataJur];
      setRubpiRows(combined);
      showToast(`Rubpi sincronizado: ${combined.length} clientes (${dataRes.length} res + ${dataJur.length} jur)`, "success");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.warn("Fallo descarga directa IIS, usando subida manual:", msg);
      showToast(`No se pudo descargar desde IIS automáticamente: ${msg}. Por favor selecciona el archivo .xlsx manual.`, "info");
      rubpiFileInputRef.current?.click();
    } finally {
      setIsSyncingRubpi(false);
    }
  };

  // 2. Sincronizar WhatsApp desde Google Sheets (GViz API)
  const handleSyncWhatsappFromSheets = async () => {
    setIsSyncingWp(true);
    try {
      const [actRows, instRows] = await Promise.all([
        fetchGvizSheet(GOOGLE_SHEETS_WP_ID, "activacion"),
        fetchGvizSheet(GOOGLE_SHEETS_WP_ID, "instalacion"),
      ]);

      setWpActivacionRows(actRows);
      setWpInstalacionRows(instRows);
      showToast(`WhatsApp sincronizado: ${actRows.length} activaciones + ${instRows.length} instalaciones`, "success");
    } catch (err: unknown) {
      showToast(`Error sincronizando WhatsApp: ${err instanceof Error ? err.message : String(err)}`, "error");
    } finally {
      setIsSyncingWp(false);
    }
  };

  // 3. Sincronizar Cajas desde API de OZmap
  const handleSyncOzmapBoxesFromApi = async () => {
    setIsSyncingOzBoxes(true);
    try {
      let serverUrl = (apiServer || DEFAULT_SERVER_URL).trim().replace(/\/+$/, "");
      if (serverUrl.includes("powerlink.com.ve") || !serverUrl.includes(":9994")) {
        serverUrl = DEFAULT_SERVER_URL;
        setApiServer(serverUrl);
        localStorage.setItem("ozmap_api_server", serverUrl);
      }
      const username = (apiUser || DEFAULT_USER).trim();
      const password = (apiPass || DEFAULT_PASS).trim();

      const loginRes = await fetch(`${serverUrl}/api/v2/users/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login: username, password: password }),
      });

      if (!loginRes.ok) throw new Error(`Error de autenticación OZmap (HTTP ${loginRes.status}: ${loginRes.statusText}).`);
      const loginData = await loginRes.json();
      const token = loginData.authorization || loginData.authenticationKey;
      if (!token) throw new Error("No se obtuvo token de autenticación de OZmap.");

      const authHeader = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

      // En OZmap API, limit=0 descarga todas las cajas del sistema con todos sus atributos
      const boxesUrl = `${serverUrl}/api/v2/boxes?limit=0`;
      let boxesRes = await fetch(boxesUrl, {
        method: "GET",
        headers: {
          Accept: "application/json",
          Authorization: authHeader,
          authorization: token,
        },
      });

      if (!boxesRes.ok) {
        boxesRes = await fetch(boxesUrl, {
          method: "GET",
          headers: {
            Accept: "application/json",
            authorization: token,
          },
        });
      }

      if (!boxesRes.ok) throw new Error(`Error consultando cajas de OZmap: HTTP ${boxesRes.status}`);
      const boxesData = await boxesRes.json();
      const rawBoxes = Array.isArray(boxesData) ? boxesData : boxesData.rows || boxesData.data || boxesData.boxes || [];

      if (!Array.isArray(rawBoxes) || rawBoxes.length === 0) {
        throw new Error("La API de OZmap no retornó registros de cajas.");
      }

      const normalized: OzmapBoxRecord[] = [];
      const seen = new Set<string>();

      rawBoxes.forEach((b: { name?: string; code?: string; label?: string; box_name?: string; caja?: string; project?: string; id?: string; coords?: [number, number]; lng?: number; lat?: number; pole?: string }) => {
        if (b && b.project === "6880141ec883ab017e286b68") return; // omitir laboratorio
        const boxName = typeof b === "string" ? b : (b.name || b.code || b.label || b.box_name || b.caja || "");
        const name = String(boxName).trim();
        if (name && !seen.has(name)) {
          seen.add(name);
          normalized.push({
            "Caja NAP": name,
            id: b.id,
            name: name,
            coords: b.coords,
            lng: b.lng,
            lat: b.lat,
            pole: b.pole,
            project: b.project,
          });
        }
      });

      setOzmapBoxes(normalized);
      localStorage.setItem("cached_ozmap_sheet", JSON.stringify(normalized));
      showToast(`API OZmap: ${normalized.length.toLocaleString()} cajas oficiales sincronizadas`, "success");
    } catch (err: unknown) {
      console.warn("Fallo API directa, intentando con Google Sheets de Cajas:", err);
      try {
        const sheetUrl = `https://docs.google.com/spreadsheets/d/${GOOGLE_SHEETS_BOXES_ID}/gviz/tq?gid=${GOOGLE_SHEETS_BOXES_GID}&tqx=out:json`;
        const res = await fetch(sheetUrl);
        const text = await res.text();
        const start = text.indexOf("setResponse(") + 12;
        const end = text.lastIndexOf(")");
        const data = JSON.parse(text.substring(start, end));
        const rows: OzmapBoxRecord[] = [];
        const seen = new Set<string>();

        let cajaColIdx = 5; // default Columna F (Caja NAP)
        if (data?.table?.cols) {
          const found = data.table.cols.findIndex((c: { label?: string }) => c?.label && /caja/i.test(c.label));
          if (found !== -1) cajaColIdx = found;
        }

        data.table.rows.forEach((r: { c?: { f?: string; v?: unknown }[] }) => {
          const val = r?.c?.[cajaColIdx]?.v;
          if (val) {
            const name = String(val).trim();
            if (name && !seen.has(name)) {
              seen.add(name);
              rows.push({ "Caja NAP": name, name: name });
            }
          }
        });

        if (rows.length === 0) throw new Error("No se encontraron cajas en el respaldo Google Sheets");

        setOzmapBoxes(rows);
        localStorage.setItem("cached_ozmap_sheet", JSON.stringify(rows));
        showToast(`Cargadas ${rows.length.toLocaleString()} cajas desde catálogo de respaldo Google Sheets`, "info");
      } catch (_backupErr) {
        void _backupErr;
        showToast(`Error al consultar cajas de OZmap: ${err instanceof Error ? err.message : String(err)}`, "error");
      }
    } finally {
      setIsSyncingOzBoxes(false);
    }
  };

  // 4. Sincronizar Base Soporte desde Google Sheets (para ozmap_rubpi_cruce)
  const handleSyncOzmapSupportFromGoogleSheets = async () => {
    setIsSyncingSupport(true);
    try {
      const spreadsheetId = "14Qiaf8xwYtSc5Xjdcd8zsOGqKPTCKvlXFgcymkX8sDE";
      const gid = "503177434";
      const url = `https://docs.google.com/spreadsheets/d/${spreadsheetId}/gviz/tq?gid=${gid}&tqx=out:json`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("No se pudo conectar con Google Sheets.");
      const rawText = await res.text();
      const startIdx = rawText.indexOf("setResponse(");
      if (startIdx === -1) throw new Error("Formato de respuesta inválido.");
      const jsonStart = startIdx + 12;
      const jsonEnd = rawText.lastIndexOf(")");
      const rawData = JSON.parse(rawText.substring(jsonStart, jsonEnd));
      const table = rawData.table;
      const cols = table.cols.map((c: { label?: string }) => c.label || "");
      const rows: Record<string, unknown>[] = [];
      table.rows.forEach((r: { c?: { f?: string; v?: unknown }[] }) => {
        const rowObj: Record<string, unknown> = {};
        if (r && r.c) {
          r.c.forEach((cell, idx) => {
            const colName = cols[idx];
            if (colName) {
              rowObj[colName] = cell ? (cell.f !== undefined ? cell.f : cell.v !== undefined ? cell.v : "") : "";
            }
          });
        }
        rows.push(rowObj);
      });
      setOzmapSupportSheet(rows);
      showToast(`Base de Soporte sincronizada: ${rows.length} registros`, "success");
    } catch (err: unknown) {
      showToast(`Error al sincronizar Soporte: ${err instanceof Error ? err.message : "Error desconocido"}`, "error");
    } finally {
      setIsSyncingSupport(false);
    }
  };

  // --- MOTOR DE COTEJO DE ALTO RENDIMIENTO (O(1) + ASYNC CHUNKING) ---

  const handleRunComparison = async () => {
    setIsMatchingRunning(true);
    setMatchingProgress({ current: 0, total: 100, percent: 0, statusText: "Iniciando motor de cotejo..." });

    // Pequeño respiro para renderizar el spinner en el DOM
    await new Promise((r) => setTimeout(r, 20));

    try {
      if (activeProcess === "whatsapp_rubpi_cruce") {
        if (rubpiRows.length === 0) {
          showToast("Debes cargar la Base de Datos de Rubpi.", "error");
          return;
        }
        if (wpActivacionRows.length === 0 && wpInstalacionRows.length === 0) {
          showToast("Debes sincronizar o cargar los reportes de WhatsApp.", "error");
          return;
        }

        // Fechas de filtro
        let dStart: Date | null = null;
        let dEnd: Date | null = null;
        if (filterDateActive) {
          if (dateStart) {
            const sParts = dateStart.split("-");
            dStart = new Date(parseInt(sParts[0], 10), parseInt(sParts[1], 10) - 1, parseInt(sParts[2], 10), 0, 0, 0);
          }
          if (dateEnd) {
            const eParts = dateEnd.split("-");
            dEnd = new Date(parseInt(eParts[0], 10), parseInt(eParts[1], 10) - 1, parseInt(eParts[2], 10), 23, 59, 59);
          } else if (dateStart) {
            const sParts = dateStart.split("-");
            dEnd = new Date(parseInt(sParts[0], 10), parseInt(sParts[1], 10) - 1, parseInt(sParts[2], 10), 23, 59, 59);
          }
        }

        // 1. Consolidar WhatsApp (con filtro de fecha si aplica) combinando activaciones e instalaciones
        setMatchingProgress({ current: 0, total: 100, percent: 5, statusText: "Consolidando reportes de WhatsApp..." });
        await new Promise((r) => setTimeout(r, 0));

        const wpClients = consolidateWpReportSheets(wpActivacionRows, wpInstalacionRows, dStart, dEnd, filterDateActive);

        // 2. Filtrar Rubpi por IPTV y Fecha
        setMatchingProgress({ current: 0, total: rubpiRows.length, percent: 15, statusText: "Filtrando abonados de Rubpi..." });
        await new Promise((r) => setTimeout(r, 0));

        let filteredRubpi = rubpiRows;
        if (!includeIptv) {
          filteredRubpi = filteredRubpi.filter((r) => {
            let tipo = "";
            for (const k in r) {
              if (k.toLowerCase().includes("tipo") && k.toLowerCase().includes("servicio")) {
                tipo = String(r[k]).toLowerCase().trim();
                break;
              }
            }
            return !tipo.includes("iptv");
          });
        }

        if (filterDateActive && (dStart || dEnd)) {
          filteredRubpi = filteredRubpi.filter((r) => {
            let fechaVal: unknown = "";
            for (const k in r) {
              const ck = cleanKey(k);
              if (ck.includes("fechadeinstalac") || ck.includes("fechainstalac") || ck.includes("instalac") || ck === "fecha") {
                fechaVal = r[k];
                break;
              }
            }
            if (!fechaVal) return false;
            const pDate = parseInstallDate(fechaVal);
            if (!pDate) return false;
            const checkDate = new Date(pDate.getFullYear(), pDate.getMonth(), pDate.getDate(), 12, 0, 0);
            if (dStart && checkDate < dStart) return false;
            if (dEnd && checkDate > dEnd) return false;
            return true;
          });
        }

        // 3. Cache Levenshtein de Cajas
        const officialBoxNames = ozmapBoxes.map((b) => getBoxName(b)).filter(Boolean);
        const boxCache = new Map<string, ReturnType<typeof fuzzyMatchBox>>();
        const getCachedBox = (caja: string) => {
          const key = caja.trim().toUpperCase();
          if (boxCache.has(key)) return boxCache.get(key)!;
          const match = fuzzyMatchBox(caja, officialBoxNames, learnedBoxes, 70);
          boxCache.set(key, match);
          return match;
        };

        // 4. Procesamiento Asíncrono por Lotes (Chunking) con motor 3-pass (Cédula ±1 dígito, Nombre Token, Serial ONU)
        const total = filteredRubpi.length;
        const CHUNK_SIZE = 500;
        const results: ComparisonRow[] = [];
        const usedWpIndices = new Set<number>();

        for (let i = 0; i < total; i += CHUNK_SIZE) {
          const chunk = filteredRubpi.slice(i, i + CHUNK_SIZE);

          for (const r of chunk) {
            let idServicio = "";
            let idUsuario = "";
            let nombres = "";
            let cedula = "";
            let estado = "";
            let serialOnu = "";

            for (const k in r) {
              if (isIdServicioKey(k)) idServicio = cleanId(r[k]);
              else if (isIdUsuarioKey(k)) idUsuario = cleanId(r[k]);
              else if (isNombresKey(k)) nombres = String(r[k]).trim();
              else if (isCedulaKey(k)) cedula = String(r[k]).trim();
              else if (cleanKey(k) === "estado") estado = String(r[k]).trim();

              const kLow = k.toLowerCase().trim();
              if ((kLow.includes("serial") && kLow.includes("onu")) || kLow === "onu") {
                if (!serialOnu) serialOnu = String(r[k]).trim();
              }
            }

            const cleanCedRubpi = cleanDigits(cedula);
            const cleanServRubpi = cleanId(idServicio);

            // Detección de si ya fue subido a OZmap previamente (Bitácora)
            let isSubidoOzmap = false;
            let bitacoraBox = "";
            let bitacoraPrecinto = "";
            if (liveUploadHistory.length > 0) {
              const histMatch = liveUploadHistory.find((h) => {
                if (cleanCedRubpi && cleanDigits(h.cedula) === cleanCedRubpi) return true;
                if (cleanServRubpi && cleanId(h.id_servicio) === cleanServRubpi) return true;
                return false;
              });
              if (histMatch) {
                isSubidoOzmap = true;
                bitacoraBox = histMatch.caja_nap || "";
                bitacoraPrecinto = histMatch.precinto || "";
              }
            }

            // Búsqueda en 3 pasos con tolerancia
            let wpMatch: ConsolidateWpClient | null = null;
            let wpMatchIdx = -1;
            let matchMethod = "";

            // Paso 1: Cédula (con tolerancia de 1 dígito)
            for (let j = 0; j < wpClients.length; j++) {
              if (usedWpIndices.has(j)) continue;
              if (cedMatch(cleanCedRubpi, wpClients[j].cedula)) {
                wpMatch = wpClients[j];
                wpMatchIdx = j;
                matchMethod = "Cédula";
                break;
              }
            }

            // Paso 2: Nombre (fuzzy token)
            if (!wpMatch && nombres) {
              for (let j = 0; j < wpClients.length; j++) {
                if (usedWpIndices.has(j)) continue;
                if (isNameMatch(nombres, wpClients[j].nombres)) {
                  wpMatch = wpClients[j];
                  wpMatchIdx = j;
                  matchMethod = "Nombre";
                  break;
                }
              }
            }

            // Paso 3: Serial ONU (últimos 6 caracteres)
            if (!wpMatch && serialOnu) {
              const rubpiOnuShort = serialOnu.replace(/[^a-zA-Z0-9]/g, "").toUpperCase().slice(-6);
              if (rubpiOnuShort.length >= 4) {
                for (let j = 0; j < wpClients.length; j++) {
                  if (usedWpIndices.has(j)) continue;
                  const wpOnuShort = wpClients[j].onu.replace(/[^a-zA-Z0-9]/g, "").toUpperCase().slice(-6);
                  if (wpOnuShort.length >= 4 && rubpiOnuShort === wpOnuShort) {
                    wpMatch = wpClients[j];
                    wpMatchIdx = j;
                    matchMethod = "ONU";
                    break;
                  }
                }
              }
            }

            if (wpMatchIdx >= 0) usedWpIndices.add(wpMatchIdx);

            const matched = !!wpMatch;
            let precinto = wpMatch ? wpMatch.precinto : (bitacoraPrecinto || "");
            let caja = wpMatch ? wpMatch.caja_nap : (bitacoraBox || "");
            const wpOnu = wpMatch ? wpMatch.onu : "";

            // Verificación ONU
            const wpOnuClean = wpOnu.replace(/[^a-zA-Z0-9]/g, "").toUpperCase();
            const rubpiOnuClean = serialOnu.replace(/[^a-zA-Z0-9]/g, "").toUpperCase();
            let coincideOnu = "⚠️ Sin datos WP";
            if (matched && wpOnuClean && rubpiOnuClean) {
              const wpShort = wpOnuClean.slice(-6);
              const rubpiShort = rubpiOnuClean.slice(-6);
              if (wpShort === rubpiShort || wpOnuClean.includes(rubpiOnuClean) || rubpiOnuClean.includes(wpOnuClean)) {
                coincideOnu = "✅ Coincide";
              } else {
                coincideOnu = "❌ Diferencia";
              }
            } else if (matched && (!wpOnuClean || !rubpiOnuClean)) {
              coincideOnu = "⚠️ Faltante";
            }

            const rowId = idServicio || `${cleanCedRubpi}-${normalizeText(nombres).substring(0, 5)}`;

            // Recuperar modificaciones manuales locales previas si existen
            const savedPrecinto = localStorage.getItem(`man-mod-${rowId}-precinto`);
            const savedCaja = localStorage.getItem(`man-mod-${rowId}-caja`);
            if (savedPrecinto !== null) precinto = savedPrecinto;
            if (savedCaja !== null) caja = savedCaja;

            const hasPrec = !!precinto.trim();
            const hasCj = !!caja.trim();
            let estadoCampo: ComparisonRow["estado_campo"] = "sin_reporte";
            if (hasPrec && hasCj) estadoCampo = "completo";
            else if (!hasPrec && hasCj) estadoCampo = "falta_precinto";
            else if (hasPrec && !hasCj) estadoCampo = "falta_caja";
            else estadoCampo = "sin_reporte";

            const cajaOriginal = caja;
            let cajaSugerida = "";
            let cajaOficial = "";
            let estadoCajaOzmap = "⚠️ Sin Datos OZmap";
            let cajaEstadoTipo: ComparisonRow["caja_estado_tipo"] = "sin_base";
            let matchScore = 0;

            if (!caja) {
              cajaOficial = "";
              cajaSugerida = "(sin caja)";
              estadoCajaOzmap = "⚠️ Sin Caja";
              cajaEstadoTipo = "sin_caja";
            } else {
              const fuzzy = getCachedBox(caja);
              cajaSugerida = fuzzy.matchedBox || "";
              matchScore = fuzzy.score || 0;
              cajaEstadoTipo = fuzzy.status;
              estadoCajaOzmap = fuzzy.label;

              const savedOficial = localStorage.getItem(`man-mod-${rowId}-caja_oficial`);
              if (savedOficial !== null && savedOficial !== "") {
                cajaOficial = savedOficial;
                cajaEstadoTipo = "valida";
                estadoCajaOzmap = "✅ Confirmada";
              } else if (fuzzy.status === "valida" || fuzzy.status === "aprendida") {
                // SOLO si es 100% exacto o aprendido pasa directo a validada
                cajaOficial = fuzzy.matchedBox;
              } else {
                // Las sugerencias quedan pendientes para revisión del operador
                cajaOficial = "";
              }
            }

            results.push({
              id: rowId,
              codigo_ozmap: formatOzmapClientCode({ cedula, id_usuario: idUsuario, id_servicio: idServicio }),
              id_servicio: idServicio,
              id_usuario: idUsuario,
              nombres,
              cedula,
              serial_onu: serialOnu,
              precinto,
              caja_nap: cajaOriginal,
              caja_original: cajaOriginal,
              caja_sugerida: cajaSugerida,
              caja_candidatas: caja ? (getCachedBox(caja).candidates || []) : [],
              caja_seleccionada: cajaSugerida && cajaSugerida !== "(sin caja)" ? cajaSugerida : "",
              caja_match_score: matchScore,
              caja_oficial: cajaOficial,
              caja_estado_tipo: cajaEstadoTipo,
              estado_campo: estadoCampo,
              estado_caja_ozmap: isSubidoOzmap ? "⚡ Sincronizado" : estadoCajaOzmap,
              subido_ozmap: isSubidoOzmap,
              propiedad_ozmap: isSubidoOzmap,
              estado_rubpi: estado,
              coincide_onu: coincideOnu,
              match_method: matched ? matchMethod : "❌ No encontrado",
              matched,
              deleted: false,
            });
          }

          const processedCount = Math.min(i + CHUNK_SIZE, total);
          setMatchingProgress({
            current: processedCount,
            total,
            percent: Math.round((processedCount / total) * 100),
            statusText: `Cotejando clientes (${processedCount.toLocaleString()} / ${total.toLocaleString()})...`,
          });
          await new Promise((r) => setTimeout(r, 0));
        }

        setComparisonResults(results);
        setWizardStep(1);
        setActiveTableFilter("all");
        setCurrentPage(1);
        const matchCount = results.filter((r) => r.estado_campo === "completo").length;
        const sincCount = results.filter((r) => r.subido_ozmap).length;
        const msg = sincCount > 0
          ? `Paso 1 completado: ${results.length.toLocaleString()} abonados cotejados (${matchCount} completos, ${sincCount} sincronizados con OZmap).`
          : `Paso 1 completado: ${results.length.toLocaleString()} abonados cotejados (${matchCount} con precinto y caja completos).`;
        showToast(msg, "success");

      } else if (activeProcess === "validador_cajas_ozmap") {
        if (cajasInputRows.length === 0) {
          showToast("Debes cargar el archivo Excel con las Cajas NAP.", "error");
          return;
        }

        const officialBoxNames = ozmapBoxes.map((b) => getBoxName(b)).filter(Boolean);
        const boxCache = new Map<string, ReturnType<typeof fuzzyMatchBox>>();
        const getCachedBox = (caja: string) => {
          const key = caja.trim().toUpperCase();
          if (boxCache.has(key)) return boxCache.get(key)!;
          const match = fuzzyMatchBox(caja, officialBoxNames, learnedBoxes, 70);
          boxCache.set(key, match);
          return match;
        };

        const total = cajasInputRows.length;
        const results: ComparisonRow[] = [];

        for (let i = 0; i < total; i++) {
          const row = cajasInputRows[i];
          let rawBoxName = "";
          for (const k in row) {
            const ck = cleanKey(k);
            if (
              ck.includes("cajanap") ||
              ck.includes("caja") ||
              ck.includes("box") ||
              ck.includes("nap") ||
              ck === "nombre" ||
              ck === "name"
            ) {
              rawBoxName = String(row[k] || "").trim();
              if (rawBoxName) break;
            }
          }
          if (!rawBoxName) {
            const firstVal = Object.values(row).find((v) => v !== null && v !== undefined && String(v).trim() !== "");
            if (firstVal) rawBoxName = String(firstVal).trim();
          }
          if (!rawBoxName) continue;

          const fuzzy = getCachedBox(rawBoxName);
          let scoreStr = `${fuzzy.score}%`;
          let statusLabel = fuzzy.label;
          if (fuzzy.status === "valida") {
            statusLabel = "✅ Coincidencia Total";
            scoreStr = "100%";
          } else if (fuzzy.status === "autocorregida") {
            statusLabel = `⚠️ Coincidencia Aproximada (${fuzzy.score}%)`;
          } else if (fuzzy.status === "no_encontrada") {
            statusLabel = "❌ No Existe en OZmap";
            scoreStr = "0%";
          } else if (fuzzy.status === "sin_caja") {
            statusLabel = "⚠️ Sin Caja";
            scoreStr = "0%";
          }

          results.push({
            id: `val-box-${i + 1}`,
            caja_archivo: rawBoxName,
            caja_oficial: fuzzy.matchedBox || "",
            caja_match_score: fuzzy.score,
            caja_match_score_str: scoreStr,
            caja_estado_tipo: fuzzy.status,
            estado_caja_ozmap: statusLabel,
            matched: fuzzy.status === "valida" || fuzzy.status === "autocorregida" || fuzzy.status === "aprendida",
            deleted: false,
          });
        }

        setComparisonResults(results);
        setActiveTableFilter("all");
        setCurrentPage(1);
        showToast(`Validación completada: ${results.length.toLocaleString()} cajas verificadas contra la red.`, "success");

      } else if (activeProcess === "auditoria_rubpi_ozmap") {
        if (rubpiRows.length === 0) {
          showToast("Debes cargar la Base de Datos de Rubpi.", "error");
          return;
        }
        if (ozmapExportedClients.length === 0) {
          showToast("Debes cargar el archivo Clientes.xlsx exportado de OZmap.", "error");
          return;
        }

        // Pre-indexar clientes de OZmap
        interface OzItem {
          codeVal: string;
          cedula: string;
          idServicio: string;
          idUsuario: string;
          caja: string;
          nombre: string;
          serialOnu: string;
          used: boolean;
        }

        const ozList: OzItem[] = [];
        const ozByCedula = new Map<string, OzItem>();
        const ozByIdServ = new Map<string, OzItem>();
        const ozByNameExact = new Map<string, OzItem>();

        ozmapExportedClients.forEach((row) => {
          let codeVal = "";
          let cedFallback = "";
          let caja = "";
          let nombre = "";
          let serialOnu = "";

          for (const k in row) {
            const ck = cleanKey(k);
            if (ck === "codigo" || ck === "cdigo") codeVal = String(row[k]);
            else if (isCedulaKey(k)) cedFallback = cleanDigits(row[k]);
            else if (cleanKey(k).includes("caja")) caja = cleanId(row[k]);
            else if (isNombresKey(k)) nombre = String(row[k]).trim();
            else if (ck.includes("serieonu") || ck.includes("serialonu") || ck.includes("observacion")) {
              if (!serialOnu) serialOnu = String(row[k]).trim();
            }
          }

          let cedFromCode = "";
          let idServFromCode = "";
          let idUserFromCode = "";
          if (codeVal) {
            const parts = codeVal.split("-");
            if (parts.length >= 2) cedFromCode = cleanDigits(parts[1]);
            if (parts.length >= 3) idServFromCode = cleanId(parts[2]);
            if (parts.length >= 4) idUserFromCode = cleanId(parts[3]);
          }

          const finalCed = cedFromCode || cedFallback;
          const item: OzItem = {
            codeVal,
            cedula: finalCed,
            idServicio: idServFromCode,
            idUsuario: idUserFromCode,
            caja,
            nombre,
            serialOnu,
            used: false,
          };
          ozList.push(item);
          if (finalCed && !ozByCedula.has(finalCed)) ozByCedula.set(finalCed, item);
          if (idServFromCode && !ozByIdServ.has(idServFromCode)) ozByIdServ.set(idServFromCode, item);
          const normN = normalizeText(nombre);
          if (normN && !ozByNameExact.has(normN)) ozByNameExact.set(normN, item);
        });

        // Filtrar Rubpi
        let filteredRubpi = rubpiRows;
        if (!includeIptv) {
          filteredRubpi = filteredRubpi.filter((r) => {
            let tipo = "";
            for (const k in r) {
              if (k.toLowerCase().includes("tipo") && k.toLowerCase().includes("servicio")) {
                tipo = String(r[k]).toLowerCase();
                break;
              }
            }
            return !tipo.includes("iptv");
          });
        }

        const total = filteredRubpi.length;
        const CHUNK_SIZE = 2500;
        const results: ComparisonRow[] = [];

        for (let i = 0; i < total; i += CHUNK_SIZE) {
          const chunk = filteredRubpi.slice(i, i + CHUNK_SIZE);
          for (const r of chunk) {
            let idServicio = "";
            let idUsuario = "";
            let nombres = "";
            let cedula = "";
            let serialOnu = "";
            let tipoCliente = "RESIDENCIAL";

            for (const k in r) {
              if (isIdServicioKey(k)) idServicio = cleanId(r[k]);
              else if (isIdUsuarioKey(k)) idUsuario = cleanId(r[k]);
              else if (isNombresKey(k)) nombres = String(r[k]).trim();
              else if (isCedulaKey(k)) cedula = String(r[k]).trim();

              const kLow = k.toLowerCase().trim();
              if ((kLow.includes("serial") && kLow.includes("onu")) || kLow === "onu") {
                if (!serialOnu) serialOnu = String(r[k]).trim();
              }
            }

            if (r["__tipo_origen__"] === "JURÍDICO") tipoCliente = "JURÍDICO";

            const cleanCed = cleanDigits(cedula);
            const normName = normalizeText(nombres);

            let ozMatch: OzItem | null = null;
            let matchMethod = "";

            if (cleanCed && ozByCedula.has(cleanCed) && !ozByCedula.get(cleanCed)!.used) {
              ozMatch = ozByCedula.get(cleanCed)!;
              matchMethod = "Cédula / RIF";
            } else if (idServicio && ozByIdServ.has(idServicio) && !ozByIdServ.get(idServicio)!.used) {
              ozMatch = ozByIdServ.get(idServicio)!;
              matchMethod = "ID Servicio";
            } else if (normName && ozByNameExact.has(normName) && !ozByNameExact.get(normName)!.used) {
              ozMatch = ozByNameExact.get(normName)!;
              matchMethod = "Nombre Exacto";
            }

            const matched = !!ozMatch;
            if (ozMatch) ozMatch.used = true;

            const rowId = idServicio || `${cleanCed}-${normName.substring(0, 5)}`;
            results.push({
              id: rowId,
              id_servicio: idServicio,
              id_usuario: idUsuario,
              tipo_cliente: tipoCliente,
              nombres,
              cedula,
              caja_ozmap: ozMatch ? ozMatch.caja : "(sin caja)",
              serial_onu: serialOnu || (ozMatch ? ozMatch.serialOnu : ""),
              estado_auditoria: matched ? "✅ Ya en OZmap" : "❌ Falta por Subir",
              match_method: matched ? matchMethod : "❌ Sin Coincidencia",
              matched,
            });
          }

          const processedCount = Math.min(i + CHUNK_SIZE, total);
          setMatchingProgress({
            current: processedCount,
            total,
            percent: Math.round((processedCount / total) * 100),
            statusText: `Auditando clientes (${processedCount.toLocaleString()} / ${total.toLocaleString()})...`,
          });
          await new Promise((r) => setTimeout(r, 0));
        }

        // Agregar huérfanos de OZmap
        ozList.forEach((ozItem, idx) => {
          if (!ozItem.used) {
            results.push({
              id: `oz-orphan-${idx}`,
              id_servicio: ozItem.idServicio || "-",
              id_usuario: ozItem.idUsuario || "-",
              tipo_cliente: "N/A",
              nombres: ozItem.nombre || "(sin nombre)",
              cedula: ozItem.cedula || "(sin cédula)",
              caja_ozmap: ozItem.caja || "(sin caja)",
              serial_onu: ozItem.serialOnu || "",
              estado_auditoria: "⚠️ Solo en OZmap",
              match_method: "Huérfano OZmap",
              matched: false,
            });
          }
        });

        setComparisonResults(results);
        setActiveTableFilter("all");
        setCurrentPage(1);
        showToast(`Auditoría completada: ${results.length.toLocaleString()} registros analizados.`, "success");

      } else if (activeProcess === "ozmap_rubpi_cruce") {
        if (rubpiRows.length === 0) {
          showToast("Debes cargar la Base de Datos de Rubpi.", "error");
          return;
        }
        if (ozmapSupportSheet.length === 0) {
          showToast("Debes sincronizar la Base de Datos de Soporte.", "error");
          return;
        }

        // Fechas de filtro
        let dStart: Date | null = null;
        let dEnd: Date | null = null;
        if (filterDateActive) {
          if (dateStart) {
            const sParts = dateStart.split("-");
            dStart = new Date(parseInt(sParts[0], 10), parseInt(sParts[1], 10) - 1, parseInt(sParts[2], 10), 0, 0, 0);
          }
          if (dateEnd) {
            const eParts = dateEnd.split("-");
            dEnd = new Date(parseInt(eParts[0], 10), parseInt(eParts[1], 10) - 1, parseInt(eParts[2], 10), 23, 59, 59);
          }
        }

        let filteredRubpi = rubpiRows;
        if (!includeIptv) {
          filteredRubpi = filteredRubpi.filter((r) => {
            let tipo = "";
            for (const k in r) {
              if (k.toLowerCase().includes("tipo") && k.toLowerCase().includes("servicio")) {
                tipo = String(r[k]).toLowerCase().trim();
                break;
              }
            }
            return !tipo.includes("iptv");
          });
        }

        if (filterDateActive && (dStart || dEnd)) {
          filteredRubpi = filteredRubpi.filter((r) => {
            let fechaVal: unknown = "";
            for (const k in r) {
              const ck = cleanKey(k);
              if (ck.includes("fechadeinstalac") || ck.includes("fechainstalac") || ck.includes("instalac") || ck === "fecha") {
                fechaVal = r[k];
                break;
              }
            }
            if (!fechaVal) return false;
            const pDate = parseInstallDate(fechaVal);
            if (!pDate) return false;
            const checkDate = new Date(pDate.getFullYear(), pDate.getMonth(), pDate.getDate(), 12, 0, 0);
            if (dStart && checkDate < dStart) return false;
            if (dEnd && checkDate > dEnd) return false;
            return true;
          });
        }

        const ozmapMapping = new Map<string, { precinto: string; caja: string }>();
        ozmapSupportSheet.forEach((row) => {
          let ced = "";
          let precinto = "";
          let caja = "";
          for (const k in row) {
            if (isCedulaKey(k)) ced = cleanDigits(row[k]);
            if (cleanKey(k) === "precinto") precinto = cleanId(row[k]);
            if (cleanKey(k).includes("caja")) caja = cleanId(row[k]);
          }
          if (!ced && row["Código"]) {
            const parts = String(row["Código"]).split("-");
            if (parts.length >= 2) ced = cleanDigits(parts[parts.length - 2]);
          }
          if (ced) {
            ozmapMapping.set(ced, {
              precinto: precinto || ozmapMapping.get(ced)?.precinto || "",
              caja: caja || ozmapMapping.get(ced)?.caja || "",
            });
          }
        });

        const total = filteredRubpi.length;
        const CHUNK_SIZE = 2500;
        const results: ComparisonRow[] = [];

        for (let i = 0; i < total; i += CHUNK_SIZE) {
          const chunk = filteredRubpi.slice(i, i + CHUNK_SIZE);
          for (const r of chunk) {
            let idServicio = "";
            let idUsuario = "";
            let nombres = "";
            let cedula = "";
            let estado = "";

            for (const k in r) {
              if (isIdServicioKey(k)) idServicio = cleanId(r[k]);
              else if (isIdUsuarioKey(k)) idUsuario = cleanId(r[k]);
              else if (isNombresKey(k)) nombres = String(r[k]).trim();
              else if (isCedulaKey(k)) cedula = String(r[k]).trim();
              else if (cleanKey(k) === "estado") estado = String(r[k]).trim();
            }

            const cleanCed = cleanDigits(cedula);
            const ozItem = cleanCed ? ozmapMapping.get(cleanCed) : null;
            const matched = !!ozItem;
            const rowId = idServicio || `${cleanCed}-${normalizeText(nombres).substring(0, 5)}`;

            let precinto = ozItem?.precinto || "";
            let caja = ozItem?.caja || "";
            const savedPrecinto = localStorage.getItem(`man-mod-${rowId}-precinto`);
            const savedCaja = localStorage.getItem(`man-mod-${rowId}-caja`);
            if (savedPrecinto !== null) precinto = savedPrecinto;
            if (savedCaja !== null) caja = savedCaja;

            results.push({
              id: rowId,
              id_servicio: idServicio,
              id_usuario: idUsuario,
              nombres,
              cedula,
              precinto,
              caja_nap: caja,
              estado_rubpi: estado,
              matched,
            });
          }

          const processedCount = Math.min(i + CHUNK_SIZE, total);
          setMatchingProgress({
            current: processedCount,
            total,
            percent: Math.round((processedCount / total) * 100),
            statusText: `Cruzando con soporte (${processedCount.toLocaleString()} / ${total.toLocaleString()})...`,
          });
          await new Promise((r) => setTimeout(r, 0));
        }

        setComparisonResults(results);
        setActiveTableFilter("all");
        setCurrentPage(1);
        showToast(`Cruce con soporte completado: ${results.length.toLocaleString()} clientes procesados.`, "success");
      }
    } catch (err: unknown) {
      console.error("Error durante el cotejo:", err);
      showToast(`Error al procesar: ${err instanceof Error ? err.message : String(err)}`, "error");
    } finally {
      setIsMatchingRunning(false);
    }
  };

  // --- MODIFICACIÓN EN LÍNEA DE CELDAS & AUTO-APRENDIZAJE ---

  const handleUpdateCell = (rowId: string, field: "precinto" | "caja_nap" | "caja_oficial", val: string) => {
    const updated = comparisonResults.map((r) => {
      if (r.id === rowId) {
        const copy = { ...r, [field]: val };
        localStorage.setItem(`man-mod-${rowId}-${field}`, val);

        if (field === "precinto" || field === "caja_nap") {
          const prec = field === "precinto" ? val : (r.precinto || "");
          const cj = field === "caja_nap" ? val : (r.caja_nap || "");
          if (field === "caja_nap") copy.caja_original = val;

          const hasPrec = !!prec.trim();
          const hasCj = !!cj.trim();
          let estCampo: ComparisonRow["estado_campo"] = "sin_reporte";
          if (hasPrec && hasCj) estCampo = "completo";
          else if (!hasPrec && hasCj) estCampo = "falta_precinto";
          else if (hasPrec && !hasCj) estCampo = "falta_caja";
          else estCampo = "sin_reporte";
          copy.estado_campo = estCampo;
        }

        if (field === "caja_oficial") {
          if (val) {
            const trimmed = val.trim();
            const exactMatch = officialBoxNames.find(
              (b) => b.trim().toUpperCase() === trimmed.toUpperCase()
            );
            const finalVal = exactMatch || trimmed;
            const isInCatalog = !!exactMatch || officialBoxNames.includes(finalVal);
            copy.caja_oficial = finalVal;
            copy.caja_seleccionada = finalVal;
            copy.caja_manual_input = false;
            copy.caja_estado_tipo = "valida";
            copy.estado_caja_ozmap = isInCatalog ? "✅ Confirmada" : "✅ Manual";

            // Auto-aprender corrección
            const sourceBox = r.caja_nap || r.caja_original || "";
            if (sourceBox.trim() && isInCatalog) {
              const rawKey = sourceBox.trim().toUpperCase();
              const officialVal = finalVal;
              const newLearned = {
                ...learnedBoxes,
                [rawKey]: {
                  rawOriginal: sourceBox.trim(),
                  officialBox: officialVal,
                  date: new Date().toISOString(),
                  isPrimary: true,
                },
              };
              setLearnedBoxes(newLearned);
              localStorage.setItem("ozmap_learned_box_corrections", JSON.stringify(newLearned));
            }
          } else {
            localStorage.removeItem(`man-mod-${rowId}-caja_oficial`);
            copy.caja_oficial = "";
            copy.caja_seleccionada = "";
            copy.caja_manual_input = false;
            copy.caja_estado_tipo = copy.caja_sugerida && copy.caja_sugerida !== "(sin caja)"
              ? "autocorregida"
              : (copy.caja_nap || copy.caja_original ? "no_encontrada" : "sin_caja");
            copy.estado_caja_ozmap = copy.caja_sugerida && copy.caja_sugerida !== "(sin caja)"
              ? `⚠️ Sugerida (${copy.caja_match_score || 0}%)`
              : "❌ Sin Asignar";
          }
        }
        return copy;
      }
      return r;
    });

    setComparisonResults(updated);
  };

  const handleUpdateDraftBox = (rowId: string, val: string) => {
    setComparisonResults((prev) =>
      prev.map((r) => (r.id === rowId ? { ...r, caja_seleccionada: val } : r))
    );
  };

  const handleConfirmManualBox = (rowId: string, rawVal: string) => {
    const boxName = (rawVal || "").trim();
    if (!boxName) {
      showToast("Escribe o selecciona un nombre de caja válido.", "error");
      return;
    }

    const exactMatch = officialBoxNames.find(
      (b) => b.trim().toUpperCase() === boxName.toUpperCase()
    );
    const finalBoxName = exactMatch || boxName;
    const isInCatalog = !!exactMatch || officialBoxNames.includes(finalBoxName);

    setComparisonResults((prev) =>
      prev.map((r) => {
        if (r.id === rowId) {
          localStorage.setItem(`man-mod-${rowId}-caja_oficial`, finalBoxName);

          const sourceBox = r.caja_nap || r.caja_original || "";
          if (sourceBox.trim()) {
            handleLearnBoxCorrection(sourceBox.trim(), finalBoxName);
          }

          return {
            ...r,
            caja_oficial: finalBoxName,
            caja_seleccionada: finalBoxName,
            caja_manual_input: false,
            caja_estado_tipo: "valida" as const,
            estado_caja_ozmap: isInCatalog ? "✅ Confirmada" : "✅ Manual",
            caja_match_score: isInCatalog ? 100 : 85,
          };
        }
        return r;
      })
    );

    showToast(`Caja oficial confirmada: ${finalBoxName}`, "success");
  };

  const handleAcceptAllSuggestions = () => {
    let count = 0;
    const updated = comparisonResults.map((r) => {
      const boxToUse = r.caja_seleccionada || r.caja_sugerida;
      if (boxToUse && boxToUse !== "(sin caja)") {
        if (!r.caja_oficial) {
          count++;
          localStorage.setItem(`man-mod-${r.id}-caja_oficial`, boxToUse);
          return {
            ...r,
            caja_oficial: boxToUse,
            caja_estado_tipo: "valida" as const,
            estado_caja_ozmap: `✅ Confirmada (${r.caja_match_score || 100}%)`,
          };
        }
      }
      return r;
    });
    setComparisonResults(updated);
    showToast(`Se validaron ${count} cajas sugeridas como oficiales definitivas.`, "success");
  };

  const handleLearnBoxCorrection = (rawBox: string, officialBox: string) => {
    if (!rawBox || !officialBox) return;
    const rawKey = rawBox.trim().toUpperCase();
    const updated = {
      ...learnedBoxes,
      [rawKey]: {
        rawOriginal: rawBox.trim(),
        officialBox: officialBox.trim(),
        date: new Date().toISOString(),
        isPrimary: true,
      },
    };
    setLearnedBoxes(updated);
    localStorage.setItem("ozmap_learned_box_corrections", JSON.stringify(updated));
    showToast(`Memoria actualizada: "${rawBox.trim()}" ➔ "${officialBox.trim()}"`, "success");
  };

  // Helper para extraer coordenadas, ID de proyecto y poste de una Caja Oficial
  const getOzmapBoxDetails = async (
    serverUrl: string,
    authHeader: string,
    targetBoxName: string
  ): Promise<{ id: string; name: string; project?: string; coords?: [number, number]; pole?: string } | null> => {
    if (!targetBoxName) return null;
    const boxUpper = targetBoxName.trim().toUpperCase();
    const boxNorm = boxUpper.replace(/[^A-Z0-9]/g, "");

    // 1. Buscar en la memoria local de cajas
    if (Array.isArray(ozmapBoxes) && ozmapBoxes.length > 0) {
      const found = ozmapBoxes.find((b) => {
        const name = getBoxName(b);
        const nameUpper = name.toUpperCase();
        return nameUpper === boxUpper || (boxNorm && nameUpper.replace(/[^A-Z0-9]/g, "") === boxNorm);
      });

      if (found && (found.id || found._id)) {
        const bCoords: [number, number] | undefined =
          found.coords || (found.lng !== undefined && found.lat !== undefined ? [found.lng, found.lat] : undefined);
        return {
          id: (found.id || found._id)!,
          name: getBoxName(found) || targetBoxName,
          project: found.project,
          coords: bCoords,
          pole: found.pole,
        };
      }
    }

    // 2. Si no tiene coordenadas en memoria, consultar directamente a la API de OZmap
    try {
      const filter = JSON.stringify([{ property: "name", operator: "=", value: targetBoxName }]);
      const res = await fetch(`${serverUrl}/api/v2/boxes?filter=${encodeURIComponent(filter)}`, {
        headers: { Authorization: authHeader, "Content-Type": "application/json" },
      });
      if (res.ok) {
        const data = await res.json();
        const rows = Array.isArray(data) ? data : data.rows || data.data || [];
        if (rows.length > 0 && (rows[0].id || rows[0]._id)) {
          const b = rows[0];
          const bCoords: [number, number] | undefined =
            b.coords || (b.lng !== undefined && b.lat !== undefined ? [b.lng, b.lat] : undefined);
          return {
            id: (b.id || b._id)!,
            name: b.name || targetBoxName,
            project: b.project,
            coords: bCoords,
            pole: b.pole,
          };
        }
      }
    } catch (err) {
      console.warn("Fallo buscando coordenadas de caja en API:", err);
    }
    return null;
  };

  const handleValidateBoxesAgainstOzmap = (customBoxes?: OzmapBoxRecord[], customRows?: ComparisonRow[]) => {
    const boxes = customBoxes && customBoxes.length > 0 ? customBoxes : ozmapBoxes;
    const officialNames = boxes.map((b) => getBoxName(b)).filter(Boolean);

    const boxCache = new Map<string, ReturnType<typeof fuzzyMatchBox>>();
    const getCachedBox = (caja: string) => {
      const key = caja.trim().toUpperCase();
      if (boxCache.has(key)) return boxCache.get(key)!;
      const match = fuzzyMatchBox(caja, officialNames, learnedBoxes, 70);
      boxCache.set(key, match);
      return match;
    };

    const sourceRows = customRows || comparisonResults;
    const updated = sourceRows.map((r) => {
      const caja = r.caja_nap || r.caja_original || "";
      if (!caja.trim()) {
        return {
          ...r,
          caja_sugerida: "(sin caja)",
          caja_oficial: "",
          caja_match_score: 0,
          caja_estado_tipo: "sin_caja" as const,
          estado_caja_ozmap: "⚠️ Sin Caja",
        };
      }

      const fuzzy = getCachedBox(caja);
      const savedOficial = localStorage.getItem(`man-mod-${r.id}-caja_oficial`);

      let finalOficial = "";
      let finalEstadoTipo = fuzzy.status;
      let finalLabel = fuzzy.label;

      if (savedOficial !== null && savedOficial !== "") {
        finalOficial = savedOficial;
        finalEstadoTipo = "valida";
        finalLabel = "✅ Confirmada";
      } else if (fuzzy.status === "valida" || fuzzy.status === "aprendida") {
        // Coincidencia 100% exacta o aprendida
        finalOficial = fuzzy.matchedBox;
        finalEstadoTipo = fuzzy.status;
        finalLabel = fuzzy.label;
      } else {
        // Sugerencias (< 100%) quedan pendientes de aceptación por el usuario
        finalOficial = "";
        finalEstadoTipo = fuzzy.status;
        finalLabel = fuzzy.label;
      }

      return {
        ...r,
        caja_original: caja,
        caja_sugerida: fuzzy.matchedBox || "",
        caja_candidatas: fuzzy.candidates || [],
        caja_seleccionada: r.caja_seleccionada || fuzzy.matchedBox || "",
        caja_match_score: fuzzy.score || 0,
        caja_oficial: finalOficial,
        caja_estado_tipo: finalEstadoTipo,
        estado_caja_ozmap: finalLabel,
      };
    });

    setComparisonResults(updated);
    if (officialNames.length > 0) {
      showToast(`Validación completada contra ${officialNames.length.toLocaleString()} cajas del catálogo OZmap.`, "success");
    } else {
      showToast("Catálogo OZmap aún no sincronizado. Presiona 'Sincronizar Cajas desde API' para verificar nombres.", "info");
    }
  };

  const proceedToStep2 = (rowsToUse?: ComparisonRow[]) => {
    setIsStep1WarningModalOpen(false);
    if (rowsToUse) {
      setComparisonResults(rowsToUse);
    }
    setWizardStep(2);
    setActiveTableFilter("all");
    setCurrentPage(1);

    // Sincronizar automáticamente el catálogo de cajas NAP desde la API de OZmap al entrar
    showToast("Paso 2: Sincronizando catálogo oficial de cajas desde la API de OZmap...", "info");
    handleSyncOzmapBoxesFromApi();
  };

  const handleGoToStep2 = (force: boolean | React.MouseEvent = false) => {
    const isForced = typeof force === "boolean" ? force : false;
    if (comparisonResults.length === 0) {
      showToast("Primero debes ejecutar el Paso 1 para cotejar los datos de campo.", "error");
      return;
    }

    if (!isForced) {
      const incompletos = comparisonResults.filter((r) => r.estado_campo !== "completo");
      if (incompletos.length > 0) {
        setIncompleteClients(incompletos);
        setIsStep1WarningModalOpen(true);
        return;
      }
    }

    proceedToStep2(comparisonResults);
  };

  const handleDiscardIncompleteAndAdvance = () => {
    const completos = comparisonResults.filter((r) => r.estado_campo === "completo");
    setComparisonResults(completos);
    incompleteClients.forEach((r) => {
      localStorage.removeItem(`man-mod-${r.id}-precinto`);
      localStorage.removeItem(`man-mod-${r.id}-caja_nap`);
      localStorage.removeItem(`man-mod-${r.id}-caja_oficial`);
    });
    showToast(`Se descartaron ${incompleteClients.length} abonados incompletos. Continuando con ${completos.length} listos.`, "info");
    proceedToStep2(completos);
  };

  const handleDeleteClient = (rowId: string, clientName: string) => {
    if (!window.confirm(`¿Estás seguro de eliminar al abonado "${clientName || rowId}" de la lista de cotejo?`)) {
      return;
    }
    const updated = comparisonResults.filter((r) => r.id !== rowId);
    setComparisonResults(updated);
    localStorage.removeItem(`man-mod-${rowId}-precinto`);
    localStorage.removeItem(`man-mod-${rowId}-caja_nap`);
    localStorage.removeItem(`man-mod-${rowId}-caja_oficial`);
    showToast(`Abonado "${clientName || rowId}" descartado del proceso.`, "info");
  };

  const handleDeleteFromWarningModal = (rowId: string, clientName: string) => {
    const updated = comparisonResults.filter((r) => r.id !== rowId);
    setComparisonResults(updated);
    const updatedIncompletos = incompleteClients.filter((r) => r.id !== rowId);
    setIncompleteClients(updatedIncompletos);
    localStorage.removeItem(`man-mod-${rowId}-precinto`);
    localStorage.removeItem(`man-mod-${rowId}-caja_nap`);
    localStorage.removeItem(`man-mod-${rowId}-caja_oficial`);
    showToast(`Abonado "${clientName || rowId}" eliminado del lote.`, "info");
    if (updatedIncompletos.length === 0) {
      setIsStep1WarningModalOpen(false);
      proceedToStep2(updated);
    }
  };

  const handleGoToStep1 = () => {
    setWizardStep(1);
    setActiveTableFilter("all");
    setCurrentPage(1);
  };

  // --- SINCRONIZACIÓN EN TIEMPO REAL CON API DE OZMAP (100% PARIDAD) ---

  const handleUploadSingleClient = async (client: ComparisonRow) => {
    if (!client.caja_oficial) {
      showToast("El abonado debe tener una Caja Oficial asignada antes de subir.", "error");
      return;
    }

    setUploadingClientId(client.id);
    try {
      showToast(`Conectando con OZmap para subir a ${client.nombres}...`, "info");
      const serverUrl = apiServer.replace(/\/+$/, "");

      const loginRes = await fetch(`${serverUrl}/api/v2/users/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login: apiUser, password: apiPass }),
      });

      if (!loginRes.ok) throw new Error("Error autenticando con la API de OZmap.");
      const loginData = await loginRes.json();
      const token = loginData.authorization || loginData.authenticationKey;
      const authHeader = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

      const clientCode = formatOzmapClientCode(client);
      const precintoVal = client.precinto && String(client.precinto).trim() !== "nan" ? String(client.precinto).trim() : "S/P";
      const obsText = `Caja NAP: ${client.caja_oficial} | Precinto: ${precintoVal}`;

      // 1. Obtener detalles de la caja oficial (id, coords, project, pole)
      const boxDetails = await getOzmapBoxDetails(serverUrl, authHeader, client.caja_oficial);

      let clientId: string | null = null;

      // 2. Comprobar si el cliente ya existe en OZmap
      try {
        // A) Buscar por código exacto de cliente (R-CEDULA-ID_USUARIO-ID_SERVICIO)
        const filterExact = JSON.stringify([{ property: "code", operator: "=", value: clientCode }]);
        const checkRes = await fetch(`${serverUrl}/api/v2/clients?filter=${encodeURIComponent(filterExact)}`, {
          headers: { Authorization: authHeader, "Content-Type": "application/json" },
        });
        if (checkRes.ok) {
          const checkData = await checkRes.json();
          const rows = checkData.rows || [];
          const exactMatch = rows.find((r: { code?: string; id?: string; _id?: string }) => r.code === clientCode);
          if (exactMatch && (exactMatch.id || exactMatch._id)) {
            clientId = exactMatch.id || exactMatch._id;
            console.log(`Cliente existente en OZmap por código exacto: ${clientCode} (ID: ${clientId})`);
            await fetch(`${serverUrl}/api/v2/ftth-clients/${clientId}`, {
              method: "PATCH",
              headers: { Authorization: authHeader, "Content-Type": "application/json" },
              body: JSON.stringify({ observation: obsText }),
            }).catch(() => {});
          }
        }

        // B) Si no se encontró por código exacto y tiene id_servicio, buscar si el código termina exactamente en "-ID_SERVICIO"
        if (!clientId && client.id_servicio) {
          const filterService = JSON.stringify([{ property: "code", operator: "like", value: `-${client.id_servicio}` }]);
          const checkServRes = await fetch(`${serverUrl}/api/v2/clients?filter=${encodeURIComponent(filterService)}`, {
            headers: { Authorization: authHeader, "Content-Type": "application/json" },
          });
          if (checkServRes.ok) {
            const servData = await checkServRes.json();
            const servRows = servData.rows || [];
            const servMatch = servRows.find((r: { code?: string; id?: string; _id?: string }) => r.code && r.code.endsWith(`-${client.id_servicio}`));
            if (servMatch && (servMatch.id || servMatch._id)) {
              clientId = servMatch.id || servMatch._id;
              console.log(`Cliente existente en OZmap por ID Servicio: -${client.id_servicio} (ID: ${clientId})`);
              await fetch(`${serverUrl}/api/v2/ftth-clients/${clientId}`, {
                method: "PATCH",
                headers: { Authorization: authHeader, "Content-Type": "application/json" },
                body: JSON.stringify({ observation: obsText }),
              }).catch(() => {});
            }
          }
        }
      } catch (checkErr) {
        console.warn("Fallo comprobando cliente existente en OZmap:", checkErr);
      }

      // 3. Si no existe, crear cliente FTTH nuevo en OZmap con serial ONU
      if (!clientId) {
        const payload: Record<string, unknown> = {
          code: clientCode,
          name: client.nombres || "",
          observation: obsText,
          implanted: true,
        };
        if (client.serial_onu) {
          payload.onu = { serial_number: String(client.serial_onu).trim() };
        }

        const postClientRes = await fetch(`${serverUrl}/api/v2/ftth-clients`, {
          method: "POST",
          headers: {
            Authorization: authHeader,
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify(payload),
        });

        if (postClientRes.ok || postClientRes.status === 201) {
          const newClientData = await postClientRes.json().catch(() => ({}));
          clientId = newClientData.id || newClientData._id;
        } else {
          const errData = await postClientRes.json().catch(() => ({}));
          const errMsg = errData.message || errData.error || `HTTP ${postClientRes.status}: ${postClientRes.statusText}`;
          throw new Error(`OZmap rechazó la creación de ${clientCode}: ${errMsg}`);
        }
      }

      if (!clientId) {
        throw new Error(`No se pudo obtener el identificador de cliente de OZmap para ${clientCode}`);
      }

      // 4. Georreferenciar propiedad en el mapa vinculada a la Caja NAP
      let propCreated = false;
      if (clientId && boxDetails && boxDetails.coords && boxDetails.project) {
        try {
          const filterProp = JSON.stringify([{ property: "client", operator: "=", value: clientId }]);
          const propCheckRes = await fetch(`${serverUrl}/api/v2/properties?filter=${encodeURIComponent(filterProp)}`, {
            headers: { Authorization: authHeader, "Content-Type": "application/json" },
          });
          const propData = propCheckRes.ok ? await propCheckRes.json() : null;
          const hasProp = propData?.count > 0 || (propData?.rows && propData.rows.length > 0);

          if (!hasProp) {
            const OFFSET_METERS = 28;
            const METER_LAT = 0.000008997;
            const METER_LNG = 0.000009146;
            const angle = 45 * (Math.PI / 180.0);
            const offsetCoords: [number, number] = [
              boxDetails.coords[0] + (OFFSET_METERS * METER_LNG) * Math.cos(angle),
              boxDetails.coords[1] + (OFFSET_METERS * METER_LAT) * Math.sin(angle),
            ];

            const createPropRes = await fetch(`${serverUrl}/api/v2/properties`, {
              method: "POST",
              headers: { Authorization: authHeader, "Content-Type": "application/json" },
              body: JSON.stringify({
                project: "68cd6dbf929ed1a82f7d3a86",
                coords: offsetCoords,
                client: clientId,
                observation: "",
              }),
            });

            if (createPropRes.ok || createPropRes.status === 201) {
              const newPropData = await createPropRes.json().catch(() => ({}));
              const propId = newPropData.id || newPropData._id;
              if (propId && boxDetails.id) {
                await fetch(`${serverUrl}/api/v2/cables`, {
                  method: "POST",
                  headers: { Authorization: authHeader, "Content-Type": "application/json" },
                  body: JSON.stringify({
                    project: "68cd6dbf929ed1a82f7d3a86",
                    kind: "Drop",
                    cableType: "5d83b2fcd846ae365237b3a1",
                    boxA: boxDetails.id,
                    boxB: propId,
                    implanted: true,
                    hierarchyLevel: 3,
                    fiberNumber: 1,
                    looseNumber: 1,
                    poles: boxDetails.pole ? [{ id: boxDetails.pole, reserve: 0 }] : [],
                  }),
                }).catch(() => {});
              }
              propCreated = true;
            }
          } else {
            propCreated = true;
          }
        } catch (errProp) {
          console.warn("Fallo vinculando propiedad georreferenciada:", errProp);
        }
      }

      const updated = comparisonResults.map((r) =>
        r.id === client.id
          ? {
              ...r,
              subido_ozmap: true,
              propiedad_ozmap: propCreated || !!(boxDetails && boxDetails.coords),
              estado_caja_ozmap: "⚡ Sincronizado",
            }
          : r
      );
      setComparisonResults(updated);
      recordUploadedClient(client, boxDetails?.name || client.caja_oficial || "", precintoVal);
      showToast(`Cliente ${client.nombres} subido y vinculado en OZmap con éxito`, "success");
    } catch (err: unknown) {
      showToast(`Error al subir cliente a OZmap: ${err instanceof Error ? err.message : String(err)}`, "error");
    } finally {
      setUploadingClientId(null);
    }
  };

  const handleUploadBatchToOzmap = async () => {
    const pendingRows = comparisonResults.filter((r) => r.caja_oficial && !r.subido_ozmap && !r.deleted);
    if (pendingRows.length === 0) {
      const alreadyUploaded = comparisonResults.filter((r) => r.caja_oficial && r.subido_ozmap && !r.deleted).length;
      if (alreadyUploaded > 0) {
        showToast(`Todos los ${alreadyUploaded} abonados con caja oficial ya están sincronizados en OZmap.`, "info");
      } else {
        showToast("No hay abonados con caja oficial validada para subir.", "error");
      }
      return;
    }

    setIsUploadingToApi(true);
    let successCount = 0;
    let mappedCount = 0;
    try {
      const serverUrl = apiServer.replace(/\/+$/, "");
      const loginRes = await fetch(`${serverUrl}/api/v2/users/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login: apiUser, password: apiPass }),
      });

      if (!loginRes.ok) throw new Error("Error autenticando en OZmap.");
      const loginData = await loginRes.json();
      const token = loginData.authorization || loginData.authenticationKey;
      const authHeader = token.startsWith("Bearer ") ? token : `Bearer ${token}`;

      for (let i = 0; i < pendingRows.length; i++) {
        const item = pendingRows[i];
        setUploadProgressText(`Subiendo ${i + 1}/${pendingRows.length}: ${item.nombres?.slice(0, 16)}...`);

        try {
          const clientCode = formatOzmapClientCode(item);
          const precintoVal = item.precinto && String(item.precinto).trim() !== "nan" ? String(item.precinto).trim() : "S/P";
          const obsText = `Caja NAP: ${item.caja_oficial} | Precinto: ${precintoVal}`;

          const boxDetails = await getOzmapBoxDetails(serverUrl, authHeader, item.caja_oficial!);

          let clientId: string | null = null;

          // 1. Comprobar si existe por código exacto o sufijo de servicio
          try {
            const filterExact = JSON.stringify([{ property: "code", operator: "=", value: clientCode }]);
            const checkRes = await fetch(`${serverUrl}/api/v2/clients?filter=${encodeURIComponent(filterExact)}`, {
              headers: { Authorization: authHeader, "Content-Type": "application/json" },
            });
            if (checkRes.ok) {
              const checkData = await checkRes.json();
              const rows = checkData.rows || [];
              const exactMatch = rows.find((r: { code?: string; id?: string; _id?: string }) => r.code === clientCode);
              if (exactMatch && (exactMatch.id || exactMatch._id)) {
                clientId = exactMatch.id || exactMatch._id;
                await fetch(`${serverUrl}/api/v2/ftth-clients/${clientId}`, {
                  method: "PATCH",
                  headers: { Authorization: authHeader, "Content-Type": "application/json" },
                  body: JSON.stringify({ observation: obsText }),
                }).catch(() => {});
              }
            }

            if (!clientId && item.id_servicio) {
              const filterService = JSON.stringify([{ property: "code", operator: "like", value: `-${item.id_servicio}` }]);
              const checkServRes = await fetch(`${serverUrl}/api/v2/clients?filter=${encodeURIComponent(filterService)}`, {
                headers: { Authorization: authHeader, "Content-Type": "application/json" },
              });
              if (checkServRes.ok) {
                const servData = await checkServRes.json();
                const servRows = servData.rows || [];
                const servMatch = servRows.find((r: { code?: string; id?: string; _id?: string }) => r.code && r.code.endsWith(`-${item.id_servicio}`));
                if (servMatch && (servMatch.id || servMatch._id)) {
                  clientId = servMatch.id || servMatch._id;
                  await fetch(`${serverUrl}/api/v2/ftth-clients/${clientId}`, {
                    method: "PATCH",
                    headers: { Authorization: authHeader, "Content-Type": "application/json" },
                    body: JSON.stringify({ observation: obsText }),
                  }).catch(() => {});
                }
              }
            }
          } catch (checkErr) {
            console.warn("Fallo comprobando cliente en lote:", checkErr);
          }

          // 2. Si no existe, crear cliente FTTH nuevo
          if (!clientId) {
            const payload: Record<string, unknown> = {
              code: clientCode,
              name: item.nombres || "",
              observation: obsText,
              implanted: true,
            };
            if (item.serial_onu) {
              payload.onu = { serial_number: String(item.serial_onu).trim() };
            }

            const postRes = await fetch(`${serverUrl}/api/v2/ftth-clients`, {
              method: "POST",
              headers: { Authorization: authHeader, "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            });
            if (postRes.ok || postRes.status === 201) {
              const resData = await postRes.json().catch(() => ({}));
              clientId = resData.id || resData._id;
            } else {
              const errData = await postRes.json().catch(() => ({}));
              console.warn(`Error al crear cliente ${clientCode} en lote:`, errData);
            }
          }

          // 3. Crear propiedad georreferenciada vinculada a la caja
          if (clientId && boxDetails && boxDetails.coords && boxDetails.project) {
            try {
              const filterProp = JSON.stringify([{ property: "client", operator: "=", value: clientId }]);
              const propRes = await fetch(`${serverUrl}/api/v2/properties?filter=${encodeURIComponent(filterProp)}`, {
                headers: { Authorization: authHeader, "Content-Type": "application/json" },
              });
              const propData = propRes.ok ? await propRes.json() : null;
              const hasProp = propData?.count > 0 || (propData?.rows && propData.rows.length > 0);

              if (!hasProp) {
                const OFFSET_METERS = 28;
                const METER_LAT = 0.000008997;
                const METER_LNG = 0.000009146;
                const angle = ((i % 8) * 45 + 22.5) * (Math.PI / 180.0);
                const offsetCoords: [number, number] = [
                  boxDetails.coords[0] + (OFFSET_METERS * METER_LNG) * Math.cos(angle),
                  boxDetails.coords[1] + (OFFSET_METERS * METER_LAT) * Math.sin(angle),
                ];

                const createPropRes = await fetch(`${serverUrl}/api/v2/properties`, {
                  method: "POST",
                  headers: { Authorization: authHeader, "Content-Type": "application/json" },
                  body: JSON.stringify({
                    project: "68cd6dbf929ed1a82f7d3a86",
                    coords: offsetCoords,
                    client: clientId,
                    observation: "",
                  }),
                });

                if (createPropRes.ok || createPropRes.status === 201) {
                  const newPropData = await createPropRes.json().catch(() => ({}));
                  const propId = newPropData.id || newPropData._id;
                  if (propId && boxDetails.id) {
                    await fetch(`${serverUrl}/api/v2/cables`, {
                      method: "POST",
                      headers: { Authorization: authHeader, "Content-Type": "application/json" },
                      body: JSON.stringify({
                        project: "68cd6dbf929ed1a82f7d3a86",
                        kind: "Drop",
                        cableType: "5d83b2fcd846ae365237b3a1",
                        boxA: boxDetails.id,
                        boxB: propId,
                        implanted: true,
                        hierarchyLevel: 3,
                        fiberNumber: 1,
                        looseNumber: 1,
                        poles: boxDetails.pole ? [{ id: boxDetails.pole, reserve: 0 }] : [],
                      }),
                    }).catch(() => {});
                  }
                  mappedCount++;
                }
              } else {
                mappedCount++;
              }
            } catch (errProp) {
              console.warn("Fallo mapeo propiedad en lote:", errProp);
            }
          }

          if (clientId) {
            item.subido_ozmap = true;
            item.propiedad_ozmap = true;
            item.estado_caja_ozmap = "⚡ Sincronizado";
            successCount++;
            recordUploadedClient(item, boxDetails?.name || item.caja_oficial || "", precintoVal);
          }
        } catch (itemErr) {
          console.warn("Fallo subida de cliente en lote:", item.id, itemErr);
        }
      }

      setComparisonResults([...comparisonResults]);
      showToast(`Lote completado: ${successCount} clientes subidos a OZmap (${mappedCount} georreferenciados en el mapa).`, "success");
    } catch (err: unknown) {
      showToast(`Error durante la subida por lotes: ${err instanceof Error ? err.message : String(err)}`, "error");
    } finally {
      setIsUploadingToApi(false);
      setUploadProgressText("");
    }
  };

  // Exportación y gestión de la Bitácora de Clientes Subidos
  const handleExportLiveBitacoraExcel = () => {
    if (liveUploadHistory.length === 0) {
      showToast("No hay registros en la bitácora para exportar.", "error");
      return;
    }
    try {
      const data = liveUploadHistory.map((h, idx) => ({
        "N°": idx + 1,
        "Fecha": h.fecha,
        "Hora": h.hora,
        "Código OZmap": h.codigo_ozmap,
        "Abonado": h.cliente,
        "Cédula": h.cedula,
        "ID Servicio": h.id_servicio || "",
        "ID Usuario": h.id_usuario || "",
        "Caja NAP Oficial": h.caja_nap,
        "Caja Original": h.caja_original || "",
        "Precinto": h.precinto || "",
        "Serial ONU": h.serial_onu || "",
        "Georreferenciado": h.georreferenciado ? "Sí" : "No",
        "Estado": h.estado,
      }));
      const ws = XLSX.utils.json_to_sheet(data);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Bitacora Subidos");
      XLSX.writeFile(wb, `Bitacora_OZmap_Subidos_${new Date().toISOString().slice(0, 10)}.xlsx`);
      showToast(`Bitácora exportada con éxito (${liveUploadHistory.length} registros).`, "success");
    } catch (err: unknown) {
      showToast(`Error al exportar bitácora: ${err instanceof Error ? err.message : String(err)}`, "error");
    }
  };

  const handleClearLiveBitacora = () => {
    if (window.confirm("¿Seguro que deseas vaciar la bitácora de clientes subidos? Estos clientes volverán a ser cotejados en futuras comparaciones.")) {
      setLiveUploadHistory([]);
      try {
        localStorage.removeItem("ozmap_live_upload_history");
      } catch (e) {
        console.warn(e);
      }
      showToast("Bitácora de clientes subidos vaciada.", "info");
    }
  };

  // --- EXPORTACIONES EN EXCEL (SHEETJS) ---

  const handleExportOzmapMigrationExcel = () => {
    if (comparisonResults.length === 0) {
      showToast("No hay registros en la tabla para exportar.", "error");
      return;
    }

    try {
      const wb = XLSX.utils.book_new();

      // Hoja 1: Clientes Listos con Caja Validada
      const readyClients = comparisonResults
        .filter((r) => r.caja_oficial && !r.deleted)
        .map((r) => ({
          "Código OZmap": formatOzmapClientCode(r),
          "ID Servicio": r.id_servicio || "",
          "ID Usuario": r.id_usuario || "",
          Cliente: r.nombres || "",
          "Cédula / RIF": r.cedula || "",
          Precinto: r.precinto || "",
          "Caja NAP Oficial": r.caja_oficial || "",
          "Serial ONU": r.serial_onu || "",
          Estado: "LISTO_MIGRACION",
        }));
      const wsReady = XLSX.utils.json_to_sheet(readyClients.length > 0 ? readyClients : [{ Mensaje: "Sin registros" }]);
      XLSX.utils.book_append_sheet(wb, wsReady, "Export_Ozmap");

      // Hoja 2: Cajas No Encontradas en OZmap
      const notFoundBoxes = comparisonResults
        .filter((r) => r.caja_estado_tipo === "no_encontrada" && !r.deleted)
        .map((r) => ({
          Cliente: r.nombres || "",
          Cédula: r.cedula || "",
          "Caja Reportada (WhatsApp)": r.caja_nap || "",
          Precinto: r.precinto || "",
          Acción: "VERIFICAR_O_CREAR_NAP",
        }));
      const wsNotFound = XLSX.utils.json_to_sheet(notFoundBoxes.length > 0 ? notFoundBoxes : [{ Mensaje: "Sin registros" }]);
      XLSX.utils.book_append_sheet(wb, wsNotFound, "NAPs_No_Encontradas");

      // Hoja 3: Pendientes Crear NAP
      const pendingCreate = comparisonResults
        .filter((r) => r.caja_estado_tipo === "autocorregida" && !r.caja_oficial && !r.deleted)
        .map((r) => ({
          Cliente: r.nombres || "",
          "Caja Original": r.caja_nap || "",
          "Caja Sugerida": r.caja_sugerida || "",
          Score: `${r.caja_match_score || 0}%`,
        }));
      const wsPending = XLSX.utils.json_to_sheet(pendingCreate.length > 0 ? pendingCreate : [{ Mensaje: "Sin registros" }]);
      XLSX.utils.book_append_sheet(wb, wsPending, "Pendientes_Crear_NAP");

      // Hoja 4: Sin Caja NAP
      const withoutBox = comparisonResults
        .filter((r) => (!r.caja_nap || r.caja_estado_tipo === "sin_caja") && !r.deleted)
        .map((r) => ({
          "ID Servicio": r.id_servicio || "",
          Cliente: r.nombres || "",
          Cédula: r.cedula || "",
          Precinto: r.precinto || "",
          Estado: "REQUIERE_LEVANTAMIENTO",
        }));
      const wsWithoutBox = XLSX.utils.json_to_sheet(withoutBox.length > 0 ? withoutBox : [{ Mensaje: "Sin registros" }]);
      XLSX.utils.book_append_sheet(wb, wsWithoutBox, "Sin_Caja_NAP");

      const todayStr = new Date().toISOString().slice(0, 10);
      XLSX.writeFile(wb, `Migracion_Oficial_OZmap_${todayStr}.xlsx`);
      showToast("Reporte oficial de migración generado con 4 hojas exitosamente.", "success");
    } catch (err: unknown) {
      showToast(`Error exportando Excel: ${err instanceof Error ? err.message : String(err)}`, "error");
    }
  };

  const handleExportTableExcel = () => {
    if (comparisonResults.length === 0) return;
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.json_to_sheet(filteredRows);
    XLSX.utils.book_append_sheet(wb, ws, "Resultados");
    XLSX.writeFile(wb, `Cotejo_${activeProcess}_${new Date().toISOString().slice(0, 10)}.xlsx`);
    showToast("Tabla actual exportada a Excel", "success");
  };

  const filteredRows = useMemo(() => {
    return comparisonResults.filter((r) => {
      if (r.deleted) return false;

      // Filtros de pestaña
      if (activeProcess === "whatsapp_rubpi_cruce") {
        if (wizardStep === 1) {
          if (activeTableFilter === "completos" && r.estado_campo !== "completo") return false;
          if (activeTableFilter === "incompletos" && r.estado_campo !== "falta_precinto" && r.estado_campo !== "falta_caja") return false;
          if (activeTableFilter === "falta_precinto" && r.estado_campo !== "falta_precinto") return false;
          if (activeTableFilter === "falta_caja" && r.estado_campo !== "falta_caja") return false;
          if (activeTableFilter === "sin_reporte" && r.estado_campo !== "sin_reporte") return false;
          if (activeTableFilter === "sincronizados" && (!r.subido_ozmap || (!r.caja_nap?.trim() && !r.caja_oficial?.trim()))) return false;
          if (activeTableFilter === "no_sincronizados" && (r.subido_ozmap && !!(r.caja_nap?.trim() || r.caja_oficial?.trim()))) return false;
        } else {
          if (activeTableFilter === "valid" && !r.caja_oficial && r.caja_estado_tipo !== "valida" && r.caja_estado_tipo !== "aprendida") return false;
          if (activeTableFilter === "todecide" && (!!r.caja_oficial || r.caja_estado_tipo !== "autocorregida" || !r.caja_sugerida || r.caja_sugerida === "(sin caja)")) return false;
          if (activeTableFilter === "unmatched" && (!!r.caja_oficial || (r.caja_estado_tipo !== "no_encontrada" && (!!r.caja_sugerida || (!r.caja_nap && !r.caja_original))))) return false;
          if (activeTableFilter === "nobox" && (!!r.caja_oficial || (r.caja_estado_tipo !== "sin_caja" && (!!r.caja_nap || !!r.caja_original)))) return false;
          if (activeTableFilter === "sincronizados" && !r.subido_ozmap) return false;
          if (activeTableFilter === "no_sincronizados" && r.subido_ozmap) return false;
        }
      } else if (activeProcess === "validador_cajas_ozmap") {
        if (activeTableFilter === "valid" && r.caja_estado_tipo !== "valida" && r.caja_estado_tipo !== "aprendida") return false;
        if (activeTableFilter === "todecide" && r.caja_estado_tipo !== "autocorregida") return false;
        if (activeTableFilter === "unmatched" && r.caja_estado_tipo !== "no_encontrada") return false;
        if (activeTableFilter === "sincronizados" && !r.subido_ozmap) return false;
        if (activeTableFilter === "no_sincronizados" && r.subido_ozmap) return false;
      } else if (activeProcess === "auditoria_rubpi_ozmap") {
        if (activeTableFilter === "valid" && !r.estado_auditoria?.includes("Ya en OZmap")) return false;
        if (activeTableFilter === "unmatched" && !r.estado_auditoria?.includes("Falta por Subir")) return false;
        if (activeTableFilter === "orphans" && !r.estado_auditoria?.includes("Solo en OZmap")) return false;
        if (activeTableFilter === "sincronizados" && !r.subido_ozmap) return false;
        if (activeTableFilter === "no_sincronizados" && r.subido_ozmap) return false;
      } else if (activeProcess === "ozmap_rubpi_cruce") {
        if (activeTableFilter === "valid" && !r.matched) return false;
        if (activeTableFilter === "unmatched" && r.matched) return false;
        if (activeTableFilter === "sincronizados" && !r.subido_ozmap) return false;
        if (activeTableFilter === "no_sincronizados" && r.subido_ozmap) return false;
      }

      // Filtro de búsqueda
      if (tableSearch.trim()) {
        const q = normalizeText(tableSearch);
        const matchName = normalizeText(r.nombres).includes(q);
        const matchCed = cleanDigits(r.cedula).includes(q);
        const matchBox = normalizeText(r.caja_nap || r.caja_archivo || r.caja_oficial || r.caja_sugerida).includes(q);
        const matchPrec = normalizeText(r.precinto).includes(q);
        const matchServ = cleanDigits(r.id_servicio).includes(q);
        if (!matchName && !matchCed && !matchBox && !matchPrec && !matchServ) return false;
      }

      return true;
    });
  }, [comparisonResults, activeTableFilter, tableSearch, activeProcess, wizardStep]);

  const totalPages = pageSize === "all" ? 1 : Math.ceil(filteredRows.length / (pageSize as number)) || 1;
  const paginatedRows = useMemo(() => {
    if (pageSize === "all") return filteredRows;
    const start = (currentPage - 1) * (pageSize as number);
    return filteredRows.slice(start, start + (pageSize as number));
  }, [filteredRows, currentPage, pageSize]);

  // Contadores KPI Paso 1 (whatsapp_rubpi_cruce)
  const step1Total = comparisonResults.filter((r) => !r.deleted).length;
  const step1Completos = comparisonResults.filter((r) => !r.deleted && r.estado_campo === "completo").length;
  const step1Incompletos = comparisonResults.filter(
    (r) => !r.deleted && (r.estado_campo === "falta_precinto" || r.estado_campo === "falta_caja")
  ).length;
  const step1SinReporte = comparisonResults.filter((r) => !r.deleted && r.estado_campo === "sin_reporte").length;
  const step1SincronizadosConCaja = comparisonResults.filter(
    (r) => !r.deleted && r.subido_ozmap && !!(r.caja_nap?.trim() || r.caja_oficial?.trim())
  ).length;
  const step1NoSincronizados = comparisonResults.filter(
    (r) => !r.deleted && (!r.subido_ozmap || (!r.caja_nap?.trim() && !r.caja_oficial?.trim()))
  ).length;

  // Contadores KPI Paso 2 (y otros procesos)
  const totalCount = comparisonResults.filter((r) => !r.deleted).length;
  const validCount = comparisonResults.filter(
    (r) => !r.deleted && (r.caja_estado_tipo === "valida" || r.caja_estado_tipo === "aprendida" || !!r.caja_oficial)
  ).length;
  const pendingUploadCount = comparisonResults.filter(
    (r) => !r.deleted && !!r.caja_oficial && !r.subido_ozmap
  ).length;
  const alreadyUploadedCount = comparisonResults.filter(
    (r) => !r.deleted && !!r.caja_oficial && !!r.subido_ozmap
  ).length;
  const step2NoSincronizados = comparisonResults.filter(
    (r) => !r.deleted && !r.subido_ozmap
  ).length;
  const toDecideCount = comparisonResults.filter(
    (r) => !r.deleted && !r.caja_oficial && r.caja_estado_tipo === "autocorregida" && !!r.caja_sugerida && r.caja_sugerida !== "(sin caja)"
  ).length;
  const unmatchedCount = comparisonResults.filter(
    (r) => !r.deleted && !r.caja_oficial && (r.caja_estado_tipo === "no_encontrada" || (!r.caja_sugerida && (!!r.caja_nap || !!r.caja_original)))
  ).length;
  const noBoxCount = comparisonResults.filter(
    (r) => !r.deleted && !r.caja_oficial && (r.caja_estado_tipo === "sin_caja" || (!r.caja_nap && !r.caja_original))
  ).length;

  // --- GESTIÓN DE CAJAS APRENDIDAS (DICCIONARIO PERSISTENTE) ---

  const handleAddNewLearned = () => {
    if (!newLearnedRaw.trim() || !newLearnedOfficial.trim()) {
      showToast("Ingresa tanto el nombre reportado como el nombre oficial.", "error");
      return;
    }
    const rawKey = newLearnedRaw.trim().toUpperCase();
    const updated = {
      ...learnedBoxes,
      [rawKey]: {
        rawOriginal: newLearnedRaw.trim(),
        officialBox: newLearnedOfficial.trim(),
        date: new Date().toISOString(),
        isPrimary: true,
      },
    };
    setLearnedBoxes(updated);
    localStorage.setItem("ozmap_learned_box_corrections", JSON.stringify(updated));
    setNewLearnedRaw("");
    setNewLearnedOfficial("");
    showToast("Caja agregada a la memoria de aprendizaje.", "success");
  };

  const handleDeleteLearned = (key: string) => {
    const copy = { ...learnedBoxes };
    delete copy[key];
    setLearnedBoxes(copy);
    localStorage.setItem("ozmap_learned_box_corrections", JSON.stringify(copy));
    showToast("Caja eliminada de la memoria.", "info");
  };

  const handleSaveApiConfig = () => {
    localStorage.setItem("ozmap_api_server", apiServer.trim());
    localStorage.setItem("ozmap_api_user", apiUser.trim());
    localStorage.setItem("ozmap_api_pass", apiPass.trim());
    setIsConfigModalOpen(false);
    showToast("Credenciales de API OZmap guardadas exitosamente", "success");
  };

  // Determinar si el botón Ejecutar debe estar habilitado
  const isReadyToRun = useMemo(() => {
    if (activeProcess === "whatsapp_rubpi_cruce") {
      if (wizardStep === 1) {
        return rubpiRows.length > 0 && (wpActivacionRows.length > 0 || wpInstalacionRows.length > 0);
      } else {
        return comparisonResults.length > 0;
      }
    }
    if (activeProcess === "validador_cajas_ozmap") {
      return ozmapBoxes.length > 0 && cajasInputRows.length > 0;
    }
    if (activeProcess === "auditoria_rubpi_ozmap") {
      return rubpiRows.length > 0 && ozmapExportedClients.length > 0;
    }
    if (activeProcess === "ozmap_rubpi_cruce") {
      return rubpiRows.length > 0 && ozmapSupportSheet.length > 0;
    }
    return false;
  }, [
    activeProcess,
    wizardStep,
    rubpiRows.length,
    wpActivacionRows.length,
    wpInstalacionRows.length,
    ozmapBoxes.length,
    cajasInputRows.length,
    ozmapExportedClients.length,
    ozmapSupportSheet.length,
    comparisonResults.length,
  ]);

  return (
    <div className="space-y-6">
      {/* Notificaciones flotantes tipo Toast */}
      {statusMessage && (
        <div
          className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-xl shadow-2xl border text-xs font-bold flex items-center gap-2.5 animate-in fade-in slide-in-from-top-3 ${
            statusMessage.type === "success"
              ? "bg-emerald-950/90 text-emerald-200 border-emerald-500/50"
              : statusMessage.type === "error"
              ? "bg-rose-950/90 text-rose-200 border-rose-500/50"
              : "bg-zinc-900/90 text-zinc-200 border-zinc-700"
          }`}
        >
          {statusMessage.type === "success" && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
          {statusMessage.type === "error" && <XCircle className="h-4 w-4 text-rose-400" />}
          {statusMessage.type === "info" && <Clock className="h-4 w-4 text-primary" />}
          <span>{statusMessage.text}</span>
        </div>
      )}

      {/* Inputs ocultos para subida manual de archivos */}
      <input
        type="file"
        ref={rubpiFileInputRef}
        onChange={(e) => handleGenericFileUpload(e, setRubpiRows, "Rubpi")}
        accept=".xlsx,.json"
        className="hidden"
      />
      <input
        type="file"
        ref={wpFileInputRef}
        onChange={handleWhatsappFileUpload}
        accept=".xlsx,.json,.csv"
        className="hidden"
      />
      <input
        type="file"
        ref={boxesFileInputRef}
        onChange={(e) => handleGenericFileUpload(e, (data) => setOzmapBoxes(data as OzmapBoxRecord[]), "Cajas OZmap")}
        accept=".xlsx,.json"
        className="hidden"
      />
      <input
        type="file"
        ref={cajasInputFileInputRef}
        onChange={(e) => handleGenericFileUpload(e, setCajasInputRows, "Cajas NAP a Validar")}
        accept=".xlsx,.json,.csv"
        className="hidden"
      />
      <input
        type="file"
        ref={ozmapExportedClientsRef}
        onChange={(e) => handleGenericFileUpload(e, setOzmapExportedClients, "Clientes OZmap (Exportación)")}
        accept=".xlsx,.json"
        className="hidden"
      />
      <input
        type="file"
        ref={ozmapSupportSheetRef}
        onChange={(e) => handleGenericFileUpload(e, setOzmapSupportSheet, "Base Soporte OZmap")}
        accept=".xlsx,.json"
        className="hidden"
      />

      {/* HEADER PRINCIPAL */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-3">
            <span className="p-2.5 rounded-xl bg-primary/10 border border-primary/20 text-primary">
              <Globe2 className="h-6 w-6" />
            </span>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-foreground">
              Módulo Oficial OZmap & Cotejo Multi-Fuente
            </h1>
          </div>

          {/* Chips de Conexión en Tiempo Real */}
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            <Badge variant="outline" className="text-xs py-1 px-3 gap-1.5 font-mono border-emerald-500/40 text-emerald-400 bg-emerald-500/10">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              OZmap API v2 Online
            </Badge>
            <Badge variant="outline" className="text-xs py-1 px-3 font-mono border-border text-muted-foreground">
              Host: powerlink.ozmap.com.br:9994
            </Badge>
            <Badge variant="outline" className="text-xs py-1 px-3 font-mono border-border text-muted-foreground">
              IIS Rubpi: 10.0.1.243
            </Badge>
          </div>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Botones de Cabecera: Diccionario & API Config */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsLearnedModalOpen(true)}
            className="h-9 text-xs sm:text-sm font-semibold gap-2 border-border hover:border-primary"
          >
            <Brain className="h-4 w-4 text-primary" />
            <span>Memoria Cajas ({Object.keys(learnedBoxes).length})</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsConfigModalOpen(true)}
            className="h-9 text-xs sm:text-sm font-semibold gap-2 border-border hover:border-primary"
          >
            <Settings className="h-4 w-4 text-muted-foreground" />
            <span>Configurar API</span>
          </Button>

          {/* Selector de Vista Principal (Asistente vs Bitácora) */}
          <div className="flex items-center p-1 rounded-xl bg-muted/60 border border-border">
            <button
              onClick={() => setMainViewTab("cruce")}
              className={`px-3.5 py-1.5 text-xs sm:text-sm font-bold rounded-lg transition-all cursor-pointer ${
                mainViewTab === "cruce"
                  ? "bg-primary text-primary-foreground shadow"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Asistente en Vivo
            </button>
            <button
              onClick={() => setMainViewTab("bitacora")}
              className={`px-3.5 py-1.5 text-xs sm:text-sm font-bold rounded-lg transition-all cursor-pointer ${
                mainViewTab === "bitacora"
                  ? "bg-primary text-primary-foreground shadow"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Bitácora de Cargas ({liveUploadHistory.length})
            </button>
          </div>
        </div>
      </div>

      {/* VISTA 1: ASISTENTE DE CRUCE EN VIVO */}
      {mainViewTab === "cruce" && (
        <div className="space-y-6">
          {/* Selector de Presets / Procesos */}
          <div className="flex flex-wrap items-center gap-2 p-1.5 rounded-2xl bg-muted/40 border border-border">
            {[
              { id: "whatsapp_rubpi_cruce" as ProcessType, label: "Cruce WhatsApp vs Rubpi (Flujo OZmap)", icon: "⚡" },
              { id: "validador_cajas_ozmap" as ProcessType, label: "Validador Cajas NAP vs API", icon: "🔍" },
              { id: "auditoria_rubpi_ozmap" as ProcessType, label: "Auditoría Rubpi vs OZmap", icon: "📋" },
              { id: "ozmap_rubpi_cruce" as ProcessType, label: "Carga de Clientes OZmap", icon: "📥" },
            ].map((p) => (
              <button
                key={p.id}
                onClick={() => handleSelectProcess(p.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                  activeProcess === p.id
                    ? "bg-primary text-primary-foreground shadow-md"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
              >
                <span>{p.icon}</span>
                <span>{p.label}</span>
              </button>
            ))}
          </div>

          {/* TARJETAS DINÁMICAS DE ENTRADA SEGÚN EL PROCESO ACTIVO */}
          <div className={
            activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 1
              ? "flex justify-center w-full"
              : "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
          }>
            {/* PROCESO 1: whatsapp_rubpi_cruce */}
            {activeProcess === "whatsapp_rubpi_cruce" && (
              <>
                {wizardStep === 1 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full max-w-2xl">
                    {/* Tarjeta: Rubpi */}
                    <Card className="p-3.5 border-border bg-card/60 backdrop-blur flex flex-col justify-between space-y-3 shadow-xs">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="text-xs font-bold text-foreground tracking-tight">Base de Datos Rubpi</h3>
                        <Badge
                          variant="outline"
                          className={
                            rubpiRows.length > 0
                              ? "border-emerald-500/40 bg-emerald-500/10 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 font-mono text-[11px] shrink-0"
                              : "text-muted-foreground border-border text-[11px] shrink-0"
                          }
                        >
                          {rubpiRows.length > 0 ? (
                            <span>
                              <strong className="font-black text-emerald-950 dark:text-emerald-100">{rubpiRows.length.toLocaleString()}</strong> clientes
                            </span>
                          ) : (
                            "No cargado"
                          )}
                        </Badge>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <Button
                          size="sm"
                          onClick={handleSyncRubpiFromIis}
                          disabled={isSyncingRubpi}
                          className="w-full h-8 text-xs font-bold gap-1.5 px-2 bg-primary hover:brightness-110 text-primary-foreground shadow-2xs"
                        >
                          <RefreshCw className={`h-3.5 w-3.5 ${isSyncingRubpi ? "animate-spin" : ""}`} />
                          <span>{isSyncingRubpi ? "Sincronizando..." : "Sincronizar"}</span>
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => rubpiFileInputRef.current?.click()}
                          className="w-full h-8 text-xs font-bold gap-1.5 px-2 text-foreground border-border hover:bg-muted/80 shadow-2xs"
                        >
                          <Upload className="h-3.5 w-3.5 text-foreground" />
                          <span>Cargar archivo</span>
                        </Button>
                      </div>
                    </Card>

                    {/* Tarjeta: WhatsApp Google Sheets */}
                    <Card className="p-3.5 border-border bg-card/60 backdrop-blur flex flex-col justify-between space-y-3 shadow-xs">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="text-xs font-bold text-foreground tracking-tight">WhatsApp (Reportes de Campo)</h3>
                        <Badge
                          variant="outline"
                          className={
                            wpActivacionRows.length + wpInstalacionRows.length > 0
                              ? "border-emerald-500/40 bg-emerald-500/10 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 font-mono text-[11px] shrink-0"
                              : "text-muted-foreground border-border text-[11px] shrink-0"
                          }
                        >
                          {wpActivacionRows.length + wpInstalacionRows.length > 0 ? (
                            <span>
                              <strong className="font-black text-emerald-950 dark:text-emerald-100">{(wpActivacionRows.length + wpInstalacionRows.length).toLocaleString()}</strong> reportes
                            </span>
                          ) : (
                            "No sincronizado"
                          )}
                        </Badge>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <Button
                          size="sm"
                          onClick={handleSyncWhatsappFromSheets}
                          disabled={isSyncingWp}
                          className="w-full h-8 text-xs font-bold gap-1.5 px-2 bg-primary hover:brightness-110 text-primary-foreground shadow-2xs"
                        >
                          <RefreshCw className={`h-3.5 w-3.5 ${isSyncingWp ? "animate-spin" : ""}`} />
                          <span>{isSyncingWp ? "Sincronizando..." : "Sincronizar"}</span>
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => wpFileInputRef.current?.click()}
                          className="w-full h-8 text-xs font-bold gap-1.5 px-2 text-foreground border-border hover:bg-muted/80 shadow-2xs"
                        >
                          <Upload className="h-3.5 w-3.5 text-foreground" />
                          <span>Cargar archivo</span>
                        </Button>
                      </div>
                    </Card>
                  </div>
                ) : (
                  /* PASO 2: Catálogo de Cajas OZmap */
                  <div className="md:col-span-3 space-y-4">
                    <Card className="p-5 border-border bg-card/60 backdrop-blur space-y-4">
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-border pb-3">
                        <div>
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="text-xs font-bold uppercase text-primary tracking-wider">Base de Datos de Red</span>
                            <Badge variant="outline" className={`text-xs font-mono font-semibold border-border bg-background ${ozmapBoxes.length > 0 ? "text-emerald-700 dark:text-emerald-300 font-bold" : "text-muted-foreground"}`}>
                              {isSyncingOzBoxes ? "Sincronizando..." : ozmapBoxes.length > 0 ? `${ozmapBoxes.length.toLocaleString()} cajas oficiales activas` : "Sin catálogo"}
                            </Badge>
                            {comparisonResults.length > 0 && (
                              <Badge
                                variant="outline"
                                className={`text-xs font-mono font-semibold border-border ${
                                  validCount === totalCount
                                    ? "bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border-emerald-500/40 font-bold"
                                    : "bg-amber-500/10 text-amber-800 dark:text-amber-300 border-amber-500/40 font-bold"
                                }`}
                              >
                                <strong className="font-black text-foreground">{validCount}</strong>/{totalCount} clientes
                              </Badge>
                            )}
                          </div>
                          <h3 className="text-base font-black text-foreground">Sincronización y Validación de Cajas</h3>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleGoToStep1}
                          className="gap-2 text-xs font-semibold border-border hover:border-primary shrink-0 self-start md:self-center"
                        >
                          <ArrowLeft className="h-3.5 w-3.5" />
                          <span>Volver a Paso 1 (Datos de Campo)</span>
                        </Button>
                      </div>

                      {/* Botones de acción secuencial del Paso 2 */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                        <Button
                          size="sm"
                          onClick={handleSyncOzmapBoxesFromApi}
                          disabled={isSyncingOzBoxes}
                          className="text-xs font-bold gap-2 bg-secondary hover:bg-secondary/80 text-secondary-foreground border border-border h-10 shadow-xs"
                        >
                          <RefreshCw className={`h-4 w-4 ${isSyncingOzBoxes ? "animate-spin" : ""}`} />
                          <span>{isSyncingOzBoxes ? "Sincronizando..." : "1. Sincronizar Cajas desde API"}</span>
                        </Button>

                        <Button
                          size="sm"
                          onClick={() => handleValidateBoxesAgainstOzmap()}
                          disabled={isSyncingOzBoxes}
                          className="text-xs font-black gap-2 bg-primary text-primary-foreground hover:brightness-110 h-10 shadow-sm"
                        >
                          <Sparkles className="h-4 w-4" />
                          <span>2. Aplicar Validación con Base Actual</span>
                        </Button>

                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => boxesFileInputRef.current?.click()}
                          className="text-xs font-semibold gap-1.5 h-10 border-border text-muted-foreground hover:text-foreground"
                        >
                          <Upload className="h-3.5 w-3.5" />
                          <span>Subir Cajas .xlsx</span>
                        </Button>

                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setIsLearnedModalOpen(true)}
                          className="text-xs font-semibold gap-1.5 h-10 border-border text-muted-foreground hover:text-foreground"
                        >
                          <Brain className="h-3.5 w-3.5 text-primary" />
                          <span>Memoria ({Object.keys(learnedBoxes).length})</span>
                        </Button>
                      </div>
                    </Card>
                  </div>
                )}
              </>
            )}

            {/* PROCESO 2: validador_cajas_ozmap */}
            {activeProcess === "validador_cajas_ozmap" && (
              <>
                {/* Tarjeta 1: Catálogo Cajas API */}
                <Card className="p-5 border-border bg-card/60 backdrop-blur flex flex-col justify-between space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold uppercase text-blue-400 tracking-wider">Catálogo Red Oficial</span>
                      <Badge variant="outline" className={ozmapBoxes.length > 0 ? "border-emerald-500/40 text-emerald-800 dark:text-emerald-300 bg-emerald-500/10 dark:bg-emerald-950/40 font-mono text-[11px]" : ""}>
                        {ozmapBoxes.length > 0 ? (
                          <span>
                            <strong className="font-black text-emerald-950 dark:text-emerald-100">{ozmapBoxes.length.toLocaleString()}</strong> cajas
                          </span>
                        ) : (
                          "No cargado"
                        )}
                      </Badge>
                    </div>
                    <h3 className="text-base font-black text-foreground">Catálogo Cajas OZmap (API)</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Cajas oficiales de la red descargadas directamente desde la API REST de OZmap.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Button
                      size="sm"
                      onClick={handleSyncOzmapBoxesFromApi}
                      disabled={isSyncingOzBoxes}
                      className="w-full text-xs font-bold gap-2 bg-blue-600 hover:bg-blue-700 text-white"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${isSyncingOzBoxes ? "animate-spin" : ""}`} />
                      <span>{isSyncingOzBoxes ? "Conectando API..." : "Sincronizar Cajas desde API"}</span>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => boxesFileInputRef.current?.click()}
                      className="w-full text-xs font-semibold gap-1.5 text-muted-foreground hover:text-foreground"
                    >
                      <Upload className="h-3.5 w-3.5" />
                      <span>Subir catálogo Cajas.xlsx</span>
                    </Button>
                  </div>
                </Card>

                {/* Tarjeta 2: Archivo Excel con Cajas a Validar */}
                <Card className="p-5 border-border bg-card/60 backdrop-blur flex flex-col justify-between space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold uppercase text-primary tracking-wider">Archivo Suministrado</span>
                      <Badge variant="outline" className={cajasInputRows.length > 0 ? "border-emerald-500/40 text-emerald-800 dark:text-emerald-300 bg-emerald-500/10 dark:bg-emerald-950/40 font-mono text-[11px]" : ""}>
                        {cajasInputRows.length > 0 ? (
                          <span>
                            <strong className="font-black text-emerald-950 dark:text-emerald-100">{cajasInputRows.length.toLocaleString()}</strong> cajas
                          </span>
                        ) : (
                          "Pendiente"
                        )}
                      </Badge>
                    </div>
                    <h3 className="text-base font-black text-foreground">Archivo Excel con Cajas NAP</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Carga el archivo con las cajas a validar contra el catálogo de OZmap para detectar errores y faltantes.
                    </p>
                  </div>

                  <div
                    onClick={() => cajasInputFileInputRef.current?.click()}
                    className="p-4 border-2 border-dashed border-border hover:border-primary/60 rounded-xl flex flex-col items-center justify-center cursor-pointer transition-colors text-center"
                  >
                    <Upload className="h-6 w-6 text-muted-foreground mb-1.5" />
                    <span className="text-xs font-bold text-foreground">
                      {cajasInputRows.length > 0 ? "Cambiar archivo Excel" : "Seleccionar archivo .xlsx"}
                    </span>
                    <span className="text-[10px] text-muted-foreground mt-0.5">Formatos admitidos: .xlsx, .csv</span>
                  </div>
                </Card>
              </>
            )}

            {/* PROCESO 3: auditoria_rubpi_ozmap */}
            {activeProcess === "auditoria_rubpi_ozmap" && (
              <>
                {/* Tarjeta 1: Rubpi */}
                <Card className="p-5 border-border bg-card/60 backdrop-blur flex flex-col justify-between space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold uppercase text-primary tracking-wider">Maestro Oficial</span>
                      <Badge variant="outline" className={rubpiRows.length > 0 ? "border-emerald-500/40 text-emerald-800 dark:text-emerald-300 bg-emerald-500/10 dark:bg-emerald-950/40 font-mono text-[11px]" : ""}>
                        {rubpiRows.length > 0 ? (
                          <span>
                            <strong className="font-black text-emerald-950 dark:text-emerald-100">{rubpiRows.length.toLocaleString()}</strong> clientes
                          </span>
                        ) : (
                          "No cargado"
                        )}
                      </Badge>
                    </div>
                    <h3 className="text-base font-black text-foreground">Base de Datos Rubpi</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Base administrativa de facturación para verificar clientes faltantes en OZmap.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Button
                      size="sm"
                      onClick={handleSyncRubpiFromIis}
                      disabled={isSyncingRubpi}
                      className="w-full text-xs font-bold gap-2"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${isSyncingRubpi ? "animate-spin" : ""}`} />
                      <span>{isSyncingRubpi ? "Descargando de IIS..." : "Sincronizar Rubpi desde IIS"}</span>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => rubpiFileInputRef.current?.click()}
                      className="w-full text-xs font-semibold gap-1.5 text-muted-foreground hover:text-foreground"
                    >
                      <Upload className="h-3.5 w-3.5" />
                      <span>Cargar archivo .xlsx manual</span>
                    </Button>
                  </div>
                </Card>

                {/* Tarjeta 2: Clientes.xlsx exportado de OZmap */}
                <Card className="p-5 border-border bg-card/60 backdrop-blur flex flex-col justify-between space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold uppercase text-blue-400 tracking-wider">Exportación OZmap</span>
                      <Badge variant="outline" className={ozmapExportedClients.length > 0 ? "border-emerald-500/40 text-emerald-800 dark:text-emerald-300 bg-emerald-500/10 dark:bg-emerald-950/40 font-mono text-[11px]" : ""}>
                        {ozmapExportedClients.length > 0 ? (
                          <span>
                            <strong className="font-black text-emerald-950 dark:text-emerald-100">{ozmapExportedClients.length.toLocaleString()}</strong> abonados
                          </span>
                        ) : (
                          "Pendiente"
                        )}
                      </Badge>
                    </div>
                    <h3 className="text-base font-black text-foreground">Clientes Exportados de OZmap</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Carga el archivo Clientes.xlsx exportado desde la aplicación web de OZmap.
                    </p>
                  </div>

                  <div
                    onClick={() => ozmapExportedClientsRef.current?.click()}
                    className="p-4 border-2 border-dashed border-border hover:border-primary/60 rounded-xl flex flex-col items-center justify-center cursor-pointer transition-colors text-center"
                  >
                    <Upload className="h-6 w-6 text-muted-foreground mb-1.5" />
                    <span className="text-xs font-bold text-foreground">
                      {ozmapExportedClients.length > 0 ? "Cambiar Clientes.xlsx" : "Cargar Clientes.xlsx"}
                    </span>
                    <span className="text-[10px] text-muted-foreground mt-0.5">Exportación directa de OZmap</span>
                  </div>
                </Card>
              </>
            )}

            {/* PROCESO 4: ozmap_rubpi_cruce */}
            {activeProcess === "ozmap_rubpi_cruce" && (
              <>
                {/* Tarjeta 1: Rubpi */}
                <Card className="p-5 border-border bg-card/60 backdrop-blur flex flex-col justify-between space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold uppercase text-primary tracking-wider">Fuente Rubpi</span>
                      <Badge variant="outline" className={rubpiRows.length > 0 ? "border-emerald-500/40 text-emerald-800 dark:text-emerald-300 bg-emerald-500/10 dark:bg-emerald-950/40 font-mono text-[11px]" : ""}>
                        {rubpiRows.length > 0 ? (
                          <span>
                            <strong className="font-black text-emerald-950 dark:text-emerald-100">{rubpiRows.length.toLocaleString()}</strong> clientes
                          </span>
                        ) : (
                          "No cargado"
                        )}
                      </Badge>
                    </div>
                    <h3 className="text-base font-black text-foreground">Base de Datos Rubpi</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Abonados activos a cotejar contra la base de datos de soporte.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Button
                      size="sm"
                      onClick={handleSyncRubpiFromIis}
                      disabled={isSyncingRubpi}
                      className="w-full text-xs font-bold gap-2"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${isSyncingRubpi ? "animate-spin" : ""}`} />
                      <span>{isSyncingRubpi ? "Descargando de IIS..." : "Sincronizar Rubpi desde IIS"}</span>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => rubpiFileInputRef.current?.click()}
                      className="w-full text-xs font-semibold gap-1.5 text-muted-foreground hover:text-foreground"
                    >
                      <Upload className="h-3.5 w-3.5" />
                      <span>Cargar archivo .xlsx manual</span>
                    </Button>
                  </div>
                </Card>

                {/* Tarjeta 2: Base Soporte / OZmap */}
                <Card className="p-5 border-border bg-card/60 backdrop-blur flex flex-col justify-between space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold uppercase text-purple-400 tracking-wider">Base de Soporte</span>
                      <Badge variant="outline" className={ozmapSupportSheet.length > 0 ? "border-emerald-500/40 text-emerald-800 dark:text-emerald-300 bg-emerald-500/10 dark:bg-emerald-950/40 font-mono text-[11px]" : ""}>
                        {ozmapSupportSheet.length > 0 ? (
                          <span>
                            <strong className="font-black text-emerald-950 dark:text-emerald-100">{ozmapSupportSheet.length.toLocaleString()}</strong> filas
                          </span>
                        ) : (
                          "No sincronizado"
                        )}
                      </Badge>
                    </div>
                    <h3 className="text-base font-black text-foreground">Base de Datos de Soporte</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Listado de clientes con precintos y cajas NAP para carga manual en OZmap.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Button
                      size="sm"
                      onClick={handleSyncOzmapSupportFromGoogleSheets}
                      disabled={isSyncingSupport}
                      className="w-full text-xs font-bold gap-2 bg-purple-600 hover:bg-purple-700 text-white"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${isSyncingSupport ? "animate-spin" : ""}`} />
                      <span>{isSyncingSupport ? "Sincronizando..." : "Sincronizar Soporte Google Sheets"}</span>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => ozmapSupportSheetRef.current?.click()}
                      className="w-full text-xs font-semibold gap-1.5 text-muted-foreground hover:text-foreground"
                    >
                      <Upload className="h-3.5 w-3.5" />
                      <span>Cargar archivo .xlsx manual</span>
                    </Button>
                  </div>
                </Card>
              </>
            )}
          </div>

          {/* PARÁMETROS ADICIONALES (FECHA E IPTV) */}
          {(activeProcess === "whatsapp_rubpi_cruce" ||
            activeProcess === "auditoria_rubpi_ozmap" ||
            activeProcess === "ozmap_rubpi_cruce") && (
            <Card className="p-4 border-border bg-card/60 backdrop-blur space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-3">
                  <SlidersHorizontal className="h-4 w-4 text-primary" />
                  <span className="text-xs font-bold text-foreground">Filtros Opcionales de Cotejo</span>
                </div>

                <div className="flex items-center gap-4 flex-wrap">
                  <label className="flex items-center gap-2 text-xs font-semibold text-foreground cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={filterDateActive}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setFilterDateActive(checked);
                        if (checked && !dateStart && !dateEnd) {
                          const today = new Date().toISOString().slice(0, 10);
                          setDateStart(today);
                          setDateEnd(today);
                        }
                      }}
                      className="rounded border-border text-primary focus:ring-primary h-3.5 w-3.5 cursor-pointer"
                    />
                    <span>Filtro por Rango de Fechas</span>
                  </label>

                  {filterDateActive && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground font-mono">Desde:</span>
                      <Input
                        type="date"
                        value={dateStart}
                        onChange={(e) => setDateStart(e.target.value)}
                        className="h-8 text-xs w-36"
                      />
                      <span className="text-xs text-muted-foreground font-mono">Hasta:</span>
                      <Input
                        type="date"
                        value={dateEnd}
                        onChange={(e) => setDateEnd(e.target.value)}
                        className="h-8 text-xs w-36"
                      />
                    </div>
                  )}

                  <label className="flex items-center gap-2 text-xs font-semibold text-foreground cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={includeIptv}
                      onChange={(e) => setIncludeIptv(e.target.checked)}
                      className="rounded border-border text-primary focus:ring-primary h-3.5 w-3.5 cursor-pointer"
                    />
                    <span>Incluir Servicios IPTV</span>
                  </label>
                </div>
              </div>
            </Card>
          )}

          {/* BARRA DE PROGRESO EN VIVO (NO BLOQUEANTE) */}
          {isMatchingRunning && (
            <Card className="p-6 border-primary/50 bg-card/90 backdrop-blur shadow-2xl space-y-4 animate-in fade-in">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <RefreshCw className="h-5 w-5 text-primary animate-spin" />
                  <div>
                    <h4 className="text-sm font-black text-foreground">
                      {matchingProgress.statusText || "Ejecutando cotejo inteligente en segundo plano..."}
                    </h4>
                    <p className="text-xs text-muted-foreground">
                      Procesando con índices invertidos de alta velocidad (sin bloquear la interfaz)
                    </p>
                  </div>
                </div>
                <span className="text-xl font-black font-mono text-primary">{matchingProgress.percent}%</span>
              </div>
              <div className="w-full bg-muted/80 h-3 rounded-full overflow-hidden border border-border">
                <div
                  className="bg-gradient-to-r from-primary via-amber-400 to-emerald-400 h-full transition-all duration-150"
                  style={{ width: `${matchingProgress.percent}%` }}
                />
              </div>
              <div className="flex justify-between text-[11px] font-mono text-muted-foreground">
                <span>
                  Procesados: {matchingProgress.current.toLocaleString()} / {matchingProgress.total.toLocaleString()}
                </span>
                <span>Subprocesos asíncronos activos</span>
              </div>
            </Card>
          )}

          {/* BOTÓN CENTRAL: EJECUTAR COTEJO Y NAVEGACIÓN DE PASOS */}
          <div className="flex justify-center items-center gap-3 flex-wrap">
            {activeProcess === "whatsapp_rubpi_cruce" ? (
              wizardStep === 1 ? (
                <>
                  <Button
                    size="lg"
                    onClick={handleRunComparison}
                    disabled={!isReadyToRun || isMatchingRunning}
                    className="gap-2.5 px-7 font-black shadow-lg bg-primary hover:brightness-110 text-primary-foreground text-sm"
                  >
                    {isMatchingRunning ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        <span>Procesando...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        <span>Ejecutar Paso 1 (Rubpi vs WhatsApp)</span>
                      </>
                    )}
                  </Button>

                  {comparisonResults.length > 0 && (
                    <Button
                      size="lg"
                      onClick={() => handleGoToStep2(false)}
                      disabled={isMatchingRunning}
                      className="gap-2.5 px-6 font-bold shadow-md bg-secondary hover:bg-secondary/80 text-secondary-foreground border border-border text-sm"
                    >
                      <span>Avanzar a Paso 2 (Validar Cajas con OZmap)</span>
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  )}
                </>
              ) : (
                <>
                  <Button
                    size="lg"
                    variant="outline"
                    onClick={handleGoToStep1}
                    className="gap-2.5 px-6 font-bold border-border hover:border-primary text-sm shadow-xs"
                  >
                    <ArrowLeft className="h-4 w-4" />
                    <span>Volver a Paso 1</span>
                  </Button>

                  <Button
                    size="lg"
                    onClick={() => handleValidateBoxesAgainstOzmap()}
                    disabled={isSyncingOzBoxes}
                    className="gap-2.5 px-7 font-black shadow-lg bg-primary hover:brightness-110 text-primary-foreground text-sm"
                  >
                    {isSyncingOzBoxes ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        <span>Validando...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        <span>Validar Cajas con OZmap (Paso 2)</span>
                      </>
                    )}
                  </Button>
                </>
              )
            ) : (
              <Button
                size="lg"
                onClick={handleRunComparison}
                disabled={!isReadyToRun || isMatchingRunning}
                className="gap-2.5 px-8 font-black shadow-lg bg-primary hover:brightness-110 text-primary-foreground text-sm"
              >
                {isMatchingRunning ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Procesando...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    <span>
                      {activeProcess === "validador_cajas_ozmap" && "Validar Cajas NAP vs OZmap"}
                      {activeProcess === "auditoria_rubpi_ozmap" && "Ejecutar Auditoría Rubpi vs OZmap"}
                      {activeProcess === "ozmap_rubpi_cruce" && "Ejecutar Cruce de Clientes"}
                    </span>
                  </>
                )}
              </Button>
            )}
          </div>

          {/* SECCIÓN DE RESULTADOS DE LA COMPARACIÓN */}
          {comparisonResults.length > 0 && (
            <div className="space-y-4 pt-4 border-t border-border">
              {/* TARJETAS KPI DE RESULTADOS Y FILTROS INTERACTIVOS */}
              {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 1 ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
                  <Card
                    onClick={() => {
                      setActiveTableFilter("all");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-primary/60 hover:scale-[1.01] ${
                      activeTableFilter === "all"
                        ? "ring-2 ring-primary border-primary bg-primary/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-muted-foreground uppercase flex items-center justify-between">
                      <span>Total Instalados</span>
                      {activeTableFilter === "all" && <span className="h-1.5 w-1.5 rounded-full bg-primary inline-block" />}
                    </span>
                    <span className="text-xl font-black text-foreground mt-0.5 block">{step1Total.toLocaleString()}</span>
                  </Card>

                  <Card
                    onClick={() => {
                      setActiveTableFilter("completos");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-emerald-500/60 hover:scale-[1.01] ${
                      activeTableFilter === "completos"
                        ? "ring-2 ring-emerald-500 border-emerald-500 bg-emerald-500/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 uppercase flex items-center justify-between">
                      <span>✅ Completos</span>
                      {activeTableFilter === "completos" && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" />}
                    </span>
                    <span className="text-xl font-black text-emerald-800 dark:text-emerald-300 mt-0.5 block">{step1Completos.toLocaleString()}</span>
                  </Card>

                  <Card
                    onClick={() => {
                      setActiveTableFilter("incompletos");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-amber-500/60 hover:scale-[1.01] ${
                      activeTableFilter === "incompletos"
                        ? "ring-2 ring-amber-500 border-amber-500 bg-amber-500/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-amber-700 dark:text-amber-400 uppercase flex items-center justify-between">
                      <span>⚠️ Faltantes</span>
                      {activeTableFilter === "incompletos" && <span className="h-1.5 w-1.5 rounded-full bg-amber-500 inline-block" />}
                    </span>
                    <span className="text-xl font-black text-amber-800 dark:text-amber-300 mt-0.5 block">{step1Incompletos.toLocaleString()}</span>
                  </Card>

                  <Card
                    onClick={() => {
                      setActiveTableFilter("sin_reporte");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-rose-500/60 hover:scale-[1.01] ${
                      activeTableFilter === "sin_reporte"
                        ? "ring-2 ring-rose-500 border-rose-500 bg-rose-500/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-rose-700 dark:text-rose-400 uppercase flex items-center justify-between">
                      <span>❌ Sin Reporte</span>
                      {activeTableFilter === "sin_reporte" && <span className="h-1.5 w-1.5 rounded-full bg-rose-500 inline-block" />}
                    </span>
                    <span className="text-xl font-black text-rose-800 dark:text-rose-300 mt-0.5 block">{step1SinReporte.toLocaleString()}</span>
                  </Card>

                  <Card
                    onClick={() => {
                      setActiveTableFilter("sincronizados");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-emerald-500/60 hover:scale-[1.01] ${
                      activeTableFilter === "sincronizados"
                        ? "ring-2 ring-emerald-500 border-emerald-500 bg-emerald-500/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 uppercase flex items-center justify-between">
                      <span>⚡ Sincronizados</span>
                      {activeTableFilter === "sincronizados" && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" />}
                    </span>
                    <span className="text-xl font-black text-emerald-800 dark:text-emerald-300 mt-0.5 block">{step1SincronizadosConCaja.toLocaleString()}</span>
                  </Card>

                  <Card
                    onClick={() => {
                      setActiveTableFilter("no_sincronizados");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-indigo-500/60 hover:scale-[1.01] ${
                      activeTableFilter === "no_sincronizados"
                        ? "ring-2 ring-indigo-500 border-indigo-500 bg-indigo-500/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-indigo-400 uppercase flex items-center justify-between">
                      <span>⏳ No Sincronizados</span>
                      {activeTableFilter === "no_sincronizados" && <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 inline-block" />}
                    </span>
                    <span className="text-xl font-black text-indigo-400 mt-0.5 block">{step1NoSincronizados.toLocaleString()}</span>
                  </Card>
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
                  <Card
                    onClick={() => {
                      setActiveTableFilter("all");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-primary/60 hover:scale-[1.01] ${
                      activeTableFilter === "all"
                        ? "ring-2 ring-primary border-primary bg-primary/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-muted-foreground uppercase flex items-center justify-between">
                      <span>Total Procesados</span>
                      {activeTableFilter === "all" && <span className="h-1.5 w-1.5 rounded-full bg-primary inline-block" />}
                    </span>
                    <span className="text-xl font-black text-foreground mt-0.5 block">{totalCount.toLocaleString()}</span>
                  </Card>

                  <Card
                    onClick={() => {
                      setActiveTableFilter("valid");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-emerald-500/60 hover:scale-[1.01] ${
                      activeTableFilter === "valid"
                        ? "ring-2 ring-emerald-500 border-emerald-500 bg-emerald-500/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 uppercase flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" />
                        Cajas Validadas
                      </span>
                      {activeTableFilter === "valid" && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" />}
                    </span>
                    <span className="text-xl font-black text-emerald-600 dark:text-emerald-400 mt-0.5 block">{validCount.toLocaleString()}</span>
                  </Card>

                  <Card
                    onClick={() => {
                      setActiveTableFilter("todecide");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-amber-500/60 hover:scale-[1.01] ${
                      activeTableFilter === "todecide"
                        ? "ring-2 ring-amber-500 border-amber-500 bg-amber-500/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-amber-600 dark:text-amber-400 uppercase flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-amber-500 inline-block" />
                        Sugeridas
                      </span>
                      {activeTableFilter === "todecide" && <span className="h-1.5 w-1.5 rounded-full bg-amber-500 inline-block" />}
                    </span>
                    <span className="text-xl font-black text-amber-600 dark:text-amber-400 mt-0.5 block">{toDecideCount.toLocaleString()}</span>
                  </Card>

                  <Card
                    onClick={() => {
                      setActiveTableFilter("unmatched");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-rose-500/60 hover:scale-[1.01] ${
                      activeTableFilter === "unmatched"
                        ? "ring-2 ring-rose-500 border-rose-500 bg-rose-500/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-rose-600 dark:text-rose-400 uppercase flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-rose-500 inline-block" />
                        No Encontradas
                      </span>
                      {activeTableFilter === "unmatched" && <span className="h-1.5 w-1.5 rounded-full bg-rose-500 inline-block" />}
                    </span>
                    <span className="text-xl font-black text-rose-600 dark:text-rose-400 mt-0.5 block">{unmatchedCount.toLocaleString()}</span>
                  </Card>

                  <Card
                    onClick={() => {
                      setActiveTableFilter("nobox");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-slate-500/60 hover:scale-[1.01] ${
                      activeTableFilter === "nobox"
                        ? "ring-2 ring-slate-500 border-slate-500 bg-slate-500/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-slate-600 dark:text-slate-400 uppercase flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-slate-500 inline-block" />
                        Sin Caja
                      </span>
                      {activeTableFilter === "nobox" && <span className="h-1.5 w-1.5 rounded-full bg-slate-500 inline-block" />}
                    </span>
                    <span className="text-xl font-black text-slate-600 dark:text-slate-400 mt-0.5 block">{noBoxCount.toLocaleString()}</span>
                  </Card>

                  <Card
                    onClick={() => {
                      setActiveTableFilter("no_sincronizados");
                      setCurrentPage(1);
                    }}
                    className={`p-3 bg-card/60 backdrop-blur cursor-pointer transition-all duration-200 select-none hover:border-indigo-500/60 hover:scale-[1.01] ${
                      activeTableFilter === "no_sincronizados"
                        ? "ring-2 ring-indigo-500 border-indigo-500 bg-indigo-500/10 shadow-md"
                        : "border-border/80 opacity-80 hover:opacity-100"
                    }`}
                  >
                    <span className="text-[10px] font-bold text-indigo-400 uppercase flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 inline-block" />
                        No Sincronizados
                      </span>
                      {activeTableFilter === "no_sincronizados" && <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 inline-block" />}
                    </span>
                    <span className="text-xl font-black text-indigo-400 mt-0.5 block">{step2NoSincronizados.toLocaleString()}</span>
                  </Card>
                </div>
              )}

              {/* BARRA DE ACCIONES MASIVAS & AVANCE DE PASO */}
              {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 1 ? (
                <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 p-3.5 rounded-xl bg-card border border-primary/30 shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 border border-primary/20">
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-black uppercase text-foreground tracking-wider">
                          Paso 1: Auditoría de Campo
                        </span>
                        <Badge variant="outline" className="text-[10px] font-mono text-primary border-primary/40">
                          {filteredRows.length.toLocaleString()} en vista
                        </Badge>
                      </div>
                      <p className="text-[11px] text-muted-foreground">
                        {step1Completos === step1Total
                          ? `¡Todo listo! Los ${step1Total} abonados tienen Precinto y Caja confirmados.`
                          : `${step1Completos} de ${step1Total} abonados completos. Revisa o completa los faltantes antes de continuar.`}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap w-full md:w-auto justify-end">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleExportTableExcel}
                      className="h-8 text-xs font-semibold gap-1.5 text-muted-foreground hover:text-foreground"
                    >
                      <FileSpreadsheet className="h-3.5 w-3.5" />
                      <span>Tabla Excel</span>
                    </Button>

                    <Button
                      size="sm"
                      onClick={() => handleGoToStep2(false)}
                      className="h-9 px-4 text-xs font-black gap-2 bg-primary text-primary-foreground hover:brightness-110 shadow-md"
                    >
                      <span>Avanzar a Paso 2: Validar Cajas ({step1Completos}/{step1Total})</span>
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-2.5 p-2.5 rounded-xl bg-card border border-border shadow-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-foreground">Acciones del Proceso:</span>
                    <Badge variant="outline" className="text-[10px] font-mono text-primary border-primary/40">
                      {filteredRows.length.toLocaleString()} en vista
                    </Badge>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    {/* Botón Volver a Paso 1 (en Paso 2) */}
                    {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 2 && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleGoToStep1}
                        className="h-8 px-2.5 text-xs font-semibold gap-1.5 border-border hover:border-primary"
                      >
                        <ArrowLeft className="h-3.5 w-3.5" />
                        <span>Volver a Paso 1</span>
                      </Button>
                    )}

                    {/* Sincronizar Catálogo Cajas OZmap */}
                    {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 2 && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleSyncOzmapBoxesFromApi}
                        disabled={isSyncingOzBoxes}
                        className="h-8 px-2.5 text-xs font-semibold gap-1.5 border-border hover:border-primary"
                        title="Actualizar catálogo de cajas oficiales desde la API de OZmap"
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${isSyncingOzBoxes ? "animate-spin text-primary" : ""}`} />
                        <span>{isSyncingOzBoxes ? "Sincronizando..." : `Sincronizar Cajas (${ozmapBoxes.length.toLocaleString()})`}</span>
                      </Button>
                    )}

                    {/* Aplicar / Re-cotejar Cajas */}
                    {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 2 && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleValidateBoxesAgainstOzmap(ozmapBoxes)}
                        disabled={isSyncingOzBoxes || ozmapBoxes.length === 0}
                        className="h-8 px-2.5 text-xs font-semibold gap-1.5 border-border hover:border-primary"
                        title="Aplicar validación de cajas NAP usando el catálogo sincronizado de OZmap"
                      >
                        <Zap className="h-3.5 w-3.5 text-amber-500" />
                        <span>Aplicar Segundo Paso</span>
                      </Button>
                    )}

                    {/* Botón Masivo Sustituir Sugerencias (solo para whatsapp_rubpi_cruce en Paso 2) */}
                    {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 2 && (
                      <Button
                        size="sm"
                        onClick={handleAcceptAllSuggestions}
                        disabled={toDecideCount === 0}
                        className="h-8 px-3 text-xs font-bold gap-1.5 bg-primary text-primary-foreground hover:brightness-110 shadow-xs disabled:opacity-50"
                      >
                        <Zap className="h-3.5 w-3.5" />
                        <span>Aceptar Todas ({toDecideCount})</span>
                      </Button>
                    )}

                    {/* Botón Excel 4 Hojas (solo para whatsapp_rubpi_cruce en Paso 2) */}
                    {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 2 && (
                      <Button
                        size="sm"
                        onClick={handleExportOzmapMigrationExcel}
                        className="h-8 px-3 text-xs font-black gap-1.5 bg-primary text-primary-foreground hover:brightness-110 shadow-xs"
                      >
                        <Download className="h-3.5 w-3.5" />
                        <span>Exportar Excel Oficial OZmap (4 Hojas)</span>
                      </Button>
                    )}

                    {/* Subir a OZmap API (solo en Paso 2 o procesos validados) */}
                    {(activeProcess !== "whatsapp_rubpi_cruce" || wizardStep === 2) && (
                      <Button
                        size="sm"
                        onClick={handleUploadBatchToOzmap}
                        disabled={isUploadingToApi || (pendingUploadCount === 0 && validCount > 0)}
                        className={`h-8 px-3 text-xs font-black gap-1.5 shadow-xs transition-all ${
                          pendingUploadCount === 0 && validCount > 0
                            ? "bg-emerald-700/80 text-white cursor-default"
                            : "bg-gradient-to-r from-emerald-600 to-blue-600 hover:brightness-110 text-white"
                        }`}
                        title={
                          pendingUploadCount === 0 && validCount > 0
                            ? `Todos los ${validCount} abonados ya están sincronizados en OZmap`
                            : `Subir ${pendingUploadCount} abonados pendientes a OZmap (${alreadyUploadedCount} ya sincronizados)`
                        }
                      >
                        <RefreshCw className={`h-3.5 w-3.5 ${isUploadingToApi ? "animate-spin" : ""}`} />
                        <span>
                          {isUploadingToApi
                            ? uploadProgressText
                            : pendingUploadCount === 0 && validCount > 0
                            ? `✅ Todos Sincronizados (${validCount})`
                            : `Subir a OZmap (${pendingUploadCount} pendientes)`}
                        </span>
                      </Button>
                    )}

                    {activeProcess !== "whatsapp_rubpi_cruce" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleExportTableExcel}
                        className="h-8 text-xs font-semibold gap-1 text-muted-foreground hover:text-foreground"
                      >
                        <FileSpreadsheet className="h-3.5 w-3.5" />
                        <span>Tabla Excel</span>
                      </Button>
                    )}
                  </div>
                </div>
              )}

              {/* BARRA DE BÚSQUEDA Y RESUMEN DE VISTA */}
              <div className="flex items-center justify-between gap-3">
                <div className="text-xs text-muted-foreground">
                  Mostrando <span className="font-bold text-foreground">{filteredRows.length.toLocaleString()}</span> de{" "}
                  <span className="font-bold text-foreground">{comparisonResults.length.toLocaleString()}</span> abonados
                  {activeTableFilter !== "all" && (
                    <button
                      type="button"
                      onClick={() => {
                        setActiveTableFilter("all");
                        setCurrentPage(1);
                      }}
                      className="ml-2 text-primary hover:underline font-semibold"
                    >
                      (Ver todos)
                    </button>
                  )}
                </div>

                <div className="relative w-full sm:w-80">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Buscar abonado, cédula o caja..."
                    value={tableSearch}
                    onChange={(e) => {
                      setTableSearch(e.target.value);
                      setCurrentPage(1);
                    }}
                    className="pl-9 h-9 text-xs sm:text-sm"
                  />
                </div>
              </div>





              {/* Datalist nativo para autocompletado rápido de todas las cajas oficiales de OZmap */}
              <datalist id="ozmap-catalog-datalist">
                {officialBoxNames.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>

              {/* TABLA INTERACTIVA DE RESULTADOS */}
              <Card className="p-0 overflow-hidden border-border bg-card/60 backdrop-blur">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs sm:text-sm">
                    <thead className="bg-muted/60 border-b border-border text-xs font-bold text-muted-foreground uppercase tracking-wider">
                      {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 1 && (
                        <tr>
                          <th className="py-3 px-3 pl-4 whitespace-nowrap">ID Servicio / Usuario</th>
                          <th className="py-3 px-3 whitespace-nowrap min-w-[220px]">Abonado (Rubpi)</th>
                          <th className="py-3 px-3 whitespace-nowrap">Cédula</th>
                          <th className="py-3 px-3 whitespace-nowrap">Precinto (WhatsApp)</th>
                          <th className="py-3 px-3 whitespace-nowrap">Caja NAP (WhatsApp)</th>
                          <th className="py-3 px-3 whitespace-nowrap">Estado OZmap</th>
                          <th className="py-3 px-3 whitespace-nowrap">Cruce WhatsApp</th>
                          <th className="py-3 px-3 text-right pr-4 whitespace-nowrap">Ficha</th>
                        </tr>
                      )}
                      {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 2 && (
                        <tr>
                          <th className="py-3 px-3 pl-4 whitespace-nowrap">Código OZmap / ID</th>
                          <th className="py-3 px-3 whitespace-nowrap min-w-[220px]">Abonado</th>
                          <th className="py-3 px-3 whitespace-nowrap">Cédula</th>
                          <th className="py-3 px-3 whitespace-nowrap">Precinto</th>
                          <th className="py-3 px-3 whitespace-nowrap">Caja Reportada (WhatsApp)</th>
                          <th className="py-3 px-3 min-w-[320px]">Caja Oficial OZmap / Sugerencias</th>
                          <th className="py-3 px-3 whitespace-nowrap">Estado OZmap</th>
                          <th className="py-3 px-3 text-right pr-4 whitespace-nowrap">Acción en Vivo</th>
                        </tr>
                      )}
                      {activeProcess === "validador_cajas_ozmap" && (
                        <tr>
                          <th className="py-3 px-3 pl-4"># Fila</th>
                          <th className="py-3 px-3">Caja NAP (Archivo Suministrado)</th>
                          <th className="py-3 px-3">Caja Oficial (Base OZmap)</th>
                          <th className="py-3 px-3">% Coincidencia</th>
                          <th className="py-3 px-3">Estado de Validación</th>
                          <th className="py-3 px-3 text-right pr-4">Acción</th>
                        </tr>
                      )}
                      {activeProcess === "auditoria_rubpi_ozmap" && (
                        <tr>
                          <th className="py-3 px-3 pl-4">ID Servicio</th>
                          <th className="py-3 px-3">ID Usuario</th>
                          <th className="py-3 px-3">Tipo Cliente</th>
                          <th className="py-3 px-3">Abonado</th>
                          <th className="py-3 px-3">Cédula / RIF</th>
                          <th className="py-3 px-3">Caja (OZmap)</th>
                          <th className="py-3 px-3">Serial ONU</th>
                          <th className="py-3 px-3">Estado Auditoría</th>
                          <th className="py-3 px-3 text-right pr-4">Método</th>
                        </tr>
                      )}
                      {activeProcess === "ozmap_rubpi_cruce" && (
                        <tr>
                          <th className="py-3 px-3 pl-4">ID Servicio</th>
                          <th className="py-3 px-3">ID Usuario</th>
                          <th className="py-3 px-3">Abonado</th>
                          <th className="py-3 px-3">Cédula</th>
                          <th className="py-3 px-3">Precinto</th>
                          <th className="py-3 px-3">Caja NAP</th>
                          <th className="py-3 px-3">Estado Servicio</th>
                          <th className="py-3 px-3 text-right pr-4">Cruce</th>
                        </tr>
                      )}
                    </thead>

                    <tbody className="divide-y divide-border/60">
                      {paginatedRows.length === 0 ? (
                        <tr>
                          <td colSpan={10} className="p-8 text-center text-muted-foreground italic text-sm">
                            No se encontraron registros para el filtro seleccionado.
                          </td>
                        </tr>
                      ) : (
                        paginatedRows.map((r, idx) => (
                          <tr key={r.id || idx} className="hover:bg-muted/30 transition-colors">
                            {/* whatsapp_rubpi_cruce - PASO 1 (DATOS DE CAMPO) */}
                            {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 1 && (
                              <>
                                <td className="py-3 px-3 pl-4 font-mono text-xs text-muted-foreground whitespace-nowrap">
                                  <span className="text-foreground font-semibold">{r.id_servicio || "-"}</span>
                                  {r.id_usuario ? <span className="opacity-60 block text-[11px]">u: {r.id_usuario}</span> : null}
                                </td>
                                <td className="py-3 px-3">
                                  <span className="text-sm font-bold text-foreground block whitespace-nowrap">{r.nombres}</span>
                                  {r.serial_onu ? (
                                    <span className="text-xs font-mono text-muted-foreground block whitespace-nowrap mt-0.5">
                                      ONU: {r.serial_onu}
                                    </span>
                                  ) : null}
                                </td>
                                <td className="py-3 px-3 font-mono text-xs text-muted-foreground whitespace-nowrap">{r.cedula}</td>
                                <td className="py-2.5 px-2">
                                  <input
                                    type="text"
                                    value={r.precinto || ""}
                                    onChange={(e) => handleUpdateCell(r.id, "precinto", e.target.value)}
                                    placeholder="Sin precinto..."
                                    className={`h-8 w-32 px-2.5 text-xs font-mono rounded-md border transition-all focus:outline-none focus:ring-1 ${
                                      r.precinto?.trim()
                                        ? "border-border bg-background text-foreground hover:border-muted-foreground/40 focus:border-primary focus:ring-primary/20 shadow-xs font-medium"
                                        : "border-amber-400/70 bg-amber-50/60 dark:bg-amber-950/20 text-amber-800 dark:text-amber-200 placeholder:text-amber-500/50 focus:border-amber-500 focus:ring-amber-500/20"
                                    }`}
                                  />
                                </td>
                                <td className="py-2.5 px-2">
                                  <input
                                    type="text"
                                    value={r.caja_nap || ""}
                                    onChange={(e) => handleUpdateCell(r.id, "caja_nap", e.target.value)}
                                    placeholder="Sin caja NAP..."
                                    className={`h-8 w-44 px-2.5 text-xs font-mono rounded-md border transition-all focus:outline-none focus:ring-1 ${
                                      r.caja_nap?.trim()
                                        ? "border-border bg-background text-foreground hover:border-muted-foreground/40 focus:border-primary focus:ring-primary/20 shadow-xs font-semibold"
                                        : "border-amber-400/70 bg-amber-50/60 dark:bg-amber-950/20 text-amber-800 dark:text-amber-200 placeholder:text-amber-500/50 focus:border-amber-500 focus:ring-amber-500/20"
                                    }`}
                                  />
                                </td>
                                <td className="py-3 px-3 whitespace-nowrap">
                                  {r.subido_ozmap ? (
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60 shadow-xs">
                                      <Zap className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                                      Sincronizado
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-muted/60 text-muted-foreground border border-border/80 shadow-xs">
                                      <Clock className="h-3 w-3 text-muted-foreground" />
                                      No Sincronizado
                                    </span>
                                  )}
                                </td>
                                <td className="py-3 px-3">
                                  {r.match_method === "Cédula" || r.match_method === "ONU" ? (
                                    <span className="inline-flex items-center gap-1.5 font-semibold text-xs text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 px-2.5 py-1 rounded-md whitespace-nowrap shadow-xs">
                                      <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                                      {r.match_method}
                                    </span>
                                  ) : r.match_method === "Nombre" ? (
                                    <span className="inline-flex items-center gap-1.5 font-semibold text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 px-2.5 py-1 rounded-md whitespace-nowrap shadow-xs">
                                      <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                                      Nombre (Aprox)
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1.5 font-semibold text-xs text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 px-2.5 py-1 rounded-md whitespace-nowrap shadow-xs">
                                      <XCircle className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400 shrink-0" />
                                      Sin coincidencia
                                    </span>
                                  )}
                                </td>
                                <td className="py-3 px-3 text-right pr-4">
                                  <div className="flex items-center justify-end gap-1">
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => setSelectedDetailClient(r)}
                                      className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                                      title="Ver detalles del abonado"
                                    >
                                      <Eye className="h-4 w-4" />
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => handleDeleteClient(r.id, r.nombres || "")}
                                      className="h-8 w-8 p-0 text-muted-foreground hover:text-rose-500 hover:bg-rose-500/10"
                                      title="Descartar abonado del cotejo"
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </td>
                              </>
                            )}

                            {/* whatsapp_rubpi_cruce - PASO 2 (VALIDACIÓN OZMAP) */}
                            {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 2 && (
                              <>
                                <td className="py-3 px-3 pl-4 font-mono text-xs text-muted-foreground whitespace-nowrap">
                                  <span className="text-foreground font-bold text-sm block">{formatOzmapClientCode(r)}</span>
                                  {r.id_servicio ? <span className="opacity-70 text-[11px] block">Serv: {r.id_servicio}</span> : null}
                                </td>
                                <td className="py-3 px-3">
                                  <span className="font-bold text-sm text-foreground block whitespace-nowrap">{r.nombres}</span>
                                  {r.serial_onu ? (
                                    <span className="text-xs font-mono text-muted-foreground block whitespace-nowrap mt-0.5">
                                      ONU: {r.serial_onu}
                                    </span>
                                  ) : null}
                                </td>
                                <td className="py-3 px-3 font-mono text-xs text-muted-foreground whitespace-nowrap">{r.cedula || "-"}</td>
                                <td className="py-3 px-3 font-mono text-xs whitespace-nowrap">
                                  {r.precinto && String(r.precinto).trim() !== "nan" ? (
                                    <Badge variant="outline" className="text-xs font-mono bg-background text-foreground border-border font-medium shadow-xs">
                                      {r.precinto}
                                    </Badge>
                                  ) : (
                                    <span className="text-amber-500 text-xs italic font-mono">S/P</span>
                                  )}
                                </td>
                                <td className="py-3 px-3 font-mono text-xs font-semibold text-muted-foreground">
                                  {r.caja_nap || r.caja_original ? (
                                    <span className="bg-muted/60 px-2.5 py-1 rounded border border-border/80 block w-fit">
                                      {r.caja_nap || r.caja_original}
                                    </span>
                                  ) : (
                                    <span className="text-rose-400 italic text-xs">Sin Caja</span>
                                  )}
                                </td>
                                {/* COLUMNA INTEGRADA: CAJA OFICIAL OZMAP / SUGERENCIAS */}
                                <td className="py-2.5 px-3 min-w-[320px]">
                                  {r.caja_oficial ? (
                                    /* Caso 1: Caja Oficial YA Confirmada / Validada */
                                    <div className="flex flex-col gap-1">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <span className="font-bold text-xs sm:text-sm font-mono text-foreground bg-muted/60 px-2.5 py-1 rounded-md border border-border whitespace-nowrap shadow-xs">
                                          {r.caja_oficial}
                                        </span>
                                        <Badge
                                          variant="outline"
                                          className="text-[10px] font-mono font-semibold border-border text-foreground bg-background shadow-xs"
                                        >
                                          <Check className="h-2.5 w-2.5 text-emerald-500 mr-1" />
                                          {r.caja_match_score === 100 ? "100% Exacta" : `${r.caja_match_score || 100}% Aceptada`}
                                        </Badge>
                                        <button
                                          type="button"
                                          onClick={() => {
                                            handleUpdateCell(r.id, "caja_oficial", "");
                                            handleUpdateDraftBox(r.id, "");
                                          }}
                                          className="text-muted-foreground hover:text-foreground text-xs p-1 rounded hover:bg-muted/50 cursor-pointer"
                                          title="Modificar o cambiar caja asignada"
                                        >
                                          ✕
                                        </button>
                                      </div>
                                      <div className="flex items-center justify-between text-[11px]">
                                        <span className="text-muted-foreground font-medium flex items-center gap-1">
                                          {officialBoxNames.some((b) => b.toUpperCase() === r.caja_oficial?.toUpperCase()) ? (
                                            <>
                                              <Check className="h-3 w-3 text-emerald-500" /> En catálogo OZmap
                                            </>
                                          ) : (
                                            <>
                                              <Check className="h-3 w-3 text-amber-500" /> Asignada manual
                                            </>
                                          )}
                                        </span>
                                        {(r.caja_nap || r.caja_original) && (
                                          <button
                                            type="button"
                                            onClick={() => handleLearnBoxCorrection(r.caja_nap || r.caja_original || "", r.caja_oficial!)}
                                            className="text-muted-foreground hover:text-foreground transition-colors text-[10px] underline flex items-center gap-0.5 cursor-pointer"
                                            title="Recordar esta sustitución para futuras importaciones"
                                          >
                                            🧠 Memorizar
                                          </button>
                                        )}
                                      </div>
                                    </div>
                                  ) : (
                                    /* Caso 2 y 3: Caja pendiente de validar (Sugeridas, No Encontradas o Sin Caja) - Unificado */
                                    (() => {
                                      const currentDraft = r.caja_seleccionada !== undefined
                                        ? r.caja_seleccionada
                                        : (r.caja_sugerida && r.caja_sugerida !== "(sin caja)" ? r.caja_sugerida : "");
                                      const hasCandidates = r.caja_candidatas && r.caja_candidatas.length > 0;
                                      const hasSuggestion = r.caja_sugerida && r.caja_sugerida !== "(sin caja)";

                                      return (
                                        <div className="flex flex-col gap-1.5">
                                          <div className="flex items-center gap-1.5">
                                            <div className="relative flex-1 min-w-[200px]">
                                              <input
                                                type="text"
                                                list="ozmap-catalog-datalist"
                                                value={currentDraft}
                                                onChange={(e) => handleUpdateDraftBox(r.id, e.target.value)}
                                                onKeyDown={(e) => {
                                                  // Evita saltar de sección al presionar Enter en el autocompletado; solo valida con el botón Aceptar
                                                  if (e.key === "Enter") {
                                                    e.preventDefault();
                                                  }
                                                }}
                                                placeholder={
                                                  hasSuggestion
                                                    ? `Sugerida: ${r.caja_sugerida}`
                                                    : "Escribir o buscar caja en OZmap..."
                                                }
                                                className="h-8 w-full pl-2.5 pr-7 text-xs font-mono font-medium rounded-lg border border-border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary shadow-xs"
                                              />
                                              {currentDraft ? (
                                                <button
                                                  type="button"
                                                  onClick={() => handleUpdateDraftBox(r.id, "")}
                                                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-xs p-0.5 rounded cursor-pointer"
                                                  title="Limpiar texto"
                                                >
                                                  ✕
                                                </button>
                                              ) : null}
                                            </div>

                                            <Button
                                              size="sm"
                                              onClick={() => handleConfirmManualBox(r.id, currentDraft)}
                                              className="h-8 px-3 text-xs font-bold gap-1 bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs shrink-0"
                                              title="Aceptar y validar esta caja oficial"
                                            >
                                              <Check className="h-3.5 w-3.5 stroke-[2.5]" />
                                              <span>Aceptar</span>
                                            </Button>
                                          </div>

                                          {/* Chips de opciones rápidas o indicador de estado */}
                                          {hasCandidates ? (
                                            <div className="flex items-center gap-1 flex-wrap text-[10px]">
                                              <span className="text-muted-foreground font-semibold">Opciones:</span>
                                              {r.caja_candidatas!.slice(0, 3).map((c, i) => (
                                                <button
                                                  key={i}
                                                  type="button"
                                                  onClick={() => handleUpdateDraftBox(r.id, c.box)}
                                                  className={`px-1.5 py-0.5 rounded border font-mono transition-all cursor-pointer ${
                                                    currentDraft.trim().toUpperCase() === c.box.toUpperCase()
                                                      ? "bg-amber-500/20 text-amber-300 border-amber-500/40 font-bold"
                                                      : "bg-muted/60 text-muted-foreground border-border/80 hover:text-foreground hover:bg-muted"
                                                  }`}
                                                  title={`Seleccionar ${c.box} (${c.score}%)`}
                                                >
                                                  {i === 0 ? "★ " : ""}{c.box} ({c.score}%)
                                                </button>
                                              ))}
                                            </div>
                                          ) : hasSuggestion ? (
                                            <div className="flex items-center gap-1.5 text-[10px]">
                                              <span className="text-muted-foreground font-medium flex items-center gap-1">
                                                <AlertTriangle className="h-3 w-3 text-amber-500" /> Sugerencia:
                                              </span>
                                              <button
                                                type="button"
                                                onClick={() => handleUpdateDraftBox(r.id, r.caja_sugerida!)}
                                                className="px-1.5 py-0.5 rounded border border-amber-500/40 bg-amber-500/10 text-amber-400 font-mono font-bold hover:bg-amber-500/20 cursor-pointer"
                                              >
                                                ★ {r.caja_sugerida} ({r.caja_match_score || 70}%)
                                              </button>
                                            </div>
                                          ) : (
                                            <div className="flex items-center justify-between text-[10px]">
                                              <span className="text-muted-foreground font-medium flex items-center gap-1">
                                                <XCircle className="h-3 w-3 text-rose-500" /> Sin coincidencia en catálogo
                                              </span>
                                              <span className="text-muted-foreground italic">
                                                {officialBoxNames.length.toLocaleString()} cajas en catálogo
                                              </span>
                                            </div>
                                          )}
                                        </div>
                                      );
                                    })()
                                  )}
                                </td>
                                <td className="py-3 px-3">
                                  {r.subido_ozmap ? (
                                    <span className="inline-flex items-center gap-1.5 font-semibold text-xs bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60 px-2.5 py-1 rounded-md whitespace-nowrap shadow-xs">
                                      <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                                      Sincronizado
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1.5 font-semibold text-xs bg-muted/60 text-muted-foreground border border-border/80 px-2.5 py-1 rounded-md whitespace-nowrap shadow-xs">
                                      <Clock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                      No Sincronizado
                                    </span>
                                  )}
                                </td>
                                <td className="py-3 px-3 text-right pr-4">
                                  <div className="flex items-center justify-end gap-2">
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => setSelectedDetailClient(r)}
                                      className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                                      title="Ver ficha completa"
                                    >
                                      <Eye className="h-4 w-4" />
                                    </Button>
                                    {r.subido_ozmap ? (
                                      <Button
                                        size="sm"
                                        disabled
                                        variant="outline"
                                        className="h-8 px-3 text-xs font-semibold border-border bg-muted/40 text-muted-foreground cursor-default shadow-xs"
                                      >
                                        <Check className="h-3.5 w-3.5 text-emerald-500 mr-1" />
                                        Subido
                                      </Button>
                                    ) : (
                                      <Button
                                        size="sm"
                                        disabled={!r.caja_oficial || uploadingClientId === r.id}
                                        onClick={() => handleUploadSingleClient(r)}
                                        className="h-8 px-3 text-xs font-bold bg-primary hover:brightness-110 text-primary-foreground disabled:opacity-40 shadow-xs"
                                        title={!r.caja_oficial ? "Asigna una caja oficial primero" : "Subir y conectar cliente a la caja en el mapa"}
                                      >
                                        {uploadingClientId === r.id ? (
                                          <span className="flex items-center gap-1.5">
                                            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                                            Subiendo...
                                          </span>
                                        ) : (
                                          "Subir API"
                                        )}
                                      </Button>
                                    )}
                                  </div>
                                </td>
                              </>
                            )}

                            {/* validador_cajas_ozmap */}
                            {activeProcess === "validador_cajas_ozmap" && (
                              <>
                                <td className="py-3 px-3 pl-4 font-mono text-xs text-muted-foreground">{idx + 1}</td>
                                <td className="py-3 px-3 font-bold text-foreground font-mono text-sm">{r.caja_archivo}</td>
                                <td className="py-3 px-3 font-mono font-bold text-primary text-sm">{r.caja_oficial || <span className="text-muted-foreground italic">-</span>}</td>
                                <td className="py-3 px-3 font-mono font-bold text-xs">{r.caja_match_score_str}</td>
                                <td className="py-3 px-3">
                                  <Badge
                                    variant="outline"
                                    className={`text-xs ${
                                      r.caja_estado_tipo === "valida"
                                        ? "border-emerald-500/40 text-emerald-400 bg-emerald-500/10"
                                        : r.caja_estado_tipo === "autocorregida"
                                        ? "border-amber-500/40 text-amber-400 bg-amber-500/10"
                                        : "border-rose-500/40 text-rose-400 bg-rose-500/10"
                                    }`}
                                  >
                                    {r.estado_caja_ozmap}
                                  </Badge>
                                </td>
                                <td className="py-3 px-3 text-right pr-4">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                      const newBox = prompt("Modificar Caja Oficial:", r.caja_oficial || "");
                                      if (newBox) handleUpdateCell(r.id, "caja_oficial", newBox);
                                    }}
                                    className="h-8 px-2.5 text-xs font-bold"
                                  >
                                    Editar
                                  </Button>
                                </td>
                              </>
                            )}

                            {/* auditoria_rubpi_ozmap */}
                            {activeProcess === "auditoria_rubpi_ozmap" && (
                              <>
                                <td className="py-3 px-3 pl-4 font-mono text-xs text-muted-foreground">{r.id_servicio || "-"}</td>
                                <td className="py-3 px-3 font-mono text-xs text-muted-foreground">{r.id_usuario || "-"}</td>
                                <td className="py-3 px-3">
                                  <Badge variant="outline" className="text-xs font-mono">
                                    {r.tipo_cliente || "RESIDENCIAL"}
                                  </Badge>
                                </td>
                                <td className="py-3 px-3 font-bold text-foreground text-sm">{r.nombres}</td>
                                <td className="py-3 px-3 font-mono text-xs text-muted-foreground">{r.cedula}</td>
                                <td className="py-3 px-3 font-mono text-xs font-bold">{r.caja_ozmap}</td>
                                <td className="py-3 px-3 font-mono text-xs text-muted-foreground">{r.serial_onu || "-"}</td>
                                <td className="py-3 px-3">
                                  <Badge
                                    variant="outline"
                                    className={`text-xs ${
                                      r.estado_auditoria?.includes("Ya en OZmap")
                                        ? "border-emerald-500/40 text-emerald-400 bg-emerald-500/10"
                                        : r.estado_auditoria?.includes("Falta")
                                        ? "border-rose-500/40 text-rose-400 bg-rose-500/10"
                                        : "border-amber-500/40 text-amber-400 bg-amber-500/10"
                                    }`}
                                  >
                                    {r.estado_auditoria}
                                  </Badge>
                                </td>
                                <td className="py-3 px-3 text-right pr-4 text-xs text-muted-foreground">{r.match_method}</td>
                              </>
                            )}

                            {/* ozmap_rubpi_cruce */}
                            {activeProcess === "ozmap_rubpi_cruce" && (
                              <>
                                <td className="py-3 px-3 pl-4 font-mono text-xs text-muted-foreground">{r.id_servicio || "-"}</td>
                                <td className="py-3 px-3 font-mono text-xs text-muted-foreground">{r.id_usuario || "-"}</td>
                                <td className="py-3 px-3 font-bold text-foreground text-sm">{r.nombres}</td>
                                <td className="py-3 px-3 font-mono text-xs text-muted-foreground">{r.cedula}</td>
                                <td className="py-2.5 px-2">
                                  <input
                                    type="text"
                                    value={r.precinto || ""}
                                    onChange={(e) => handleUpdateCell(r.id, "precinto", e.target.value)}
                                    className="h-9 w-28 px-2 text-xs font-mono rounded-lg border border-border bg-card/60 focus:border-primary focus:outline-none"
                                  />
                                </td>
                                <td className="py-2.5 px-2">
                                  <input
                                    type="text"
                                    value={r.caja_nap || ""}
                                    onChange={(e) => handleUpdateCell(r.id, "caja_nap", e.target.value)}
                                    className="h-9 w-40 px-2 text-xs font-mono rounded-lg border border-border bg-card/60 focus:border-primary focus:outline-none"
                                  />
                                </td>
                                <td className="py-3 px-3 text-muted-foreground text-xs">{r.estado_rubpi || "ACTIVO"}</td>
                                <td className="py-3 px-3 text-right pr-4">
                                  <Badge
                                    variant="outline"
                                    className={`text-xs ${
                                      r.matched
                                        ? "border-emerald-500/40 text-emerald-400 bg-emerald-500/10"
                                        : "border-amber-500/40 text-amber-400 bg-amber-500/10"
                                    }`}
                                  >
                                    {r.matched ? "✅ Encontrado" : "⚠️ Pendiente"}
                                  </Badge>
                                </td>
                              </>
                            )}
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                {/* PAGINACIÓN */}
                <div className="flex items-center justify-between p-3 border-t border-border bg-muted/20 flex-wrap gap-2 text-xs text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <span>Filas por página:</span>
                    {[25, 50, 100, "all"].map((s) => (
                      <button
                        key={String(s)}
                        onClick={() => {
                          setPageSize(s as number | "all");
                          setCurrentPage(1);
                        }}
                        className={`px-2 py-0.5 rounded font-mono font-bold cursor-pointer ${
                          pageSize === s ? "bg-primary text-primary-foreground" : "hover:text-foreground"
                        }`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center gap-2">
                    <span>
                      Página {currentPage} de {totalPages} ({filteredRows.length.toLocaleString()} filas)
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage <= 1}
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      className="h-7 w-7 p-0"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage >= totalPages}
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      className="h-7 w-7 p-0"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </Card>



              {/* BARRA INFERIOR DE NAVEGACIÓN: PASO 2 -> REGRESAR A PASO 1 */}
              {activeProcess === "whatsapp_rubpi_cruce" && wizardStep === 2 && (
                <div className="flex items-center justify-between pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleGoToStep1}
                    className="gap-1.5 text-xs text-muted-foreground hover:text-foreground border-border"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    <span>Volver a Paso 1 (Auditoría de Campo)</span>
                  </Button>
                  <p className="text-[11px] text-muted-foreground">
                    Los cambios y asignaciones de cajas oficiales se guardan automáticamente.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* VISTA 2: BITÁCORA Y REGISTRO DE CARGAS OZMAP */}
      {mainViewTab === "bitacora" && (
        <div className="space-y-4">
          <Card className="p-5 border-border bg-card/60 backdrop-blur space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-4 border-b border-border pb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold uppercase text-primary tracking-wider">Módulo de Auditoría</span>
                  <Badge variant="outline" className="text-xs font-mono border-primary/40 text-primary">
                    {bitacoraViewMode === "live" ? `${liveUploadHistory.length} Registros Activos` : `${ozmapRawHistory.length} Registros Previos`}
                  </Badge>
                </div>
                <h3 className="text-base font-black text-foreground">Bitácora de Sincronización y Cargas a OZmap</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Control de clientes cargados en OZmap. Los abonados registrados en la vista activa quedan protegidos para no duplicarse en cotejos futuros.
                </p>
              </div>

              {/* Botones de acción global de la bitácora */}
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  size="sm"
                  onClick={handleExportLiveBitacoraExcel}
                  disabled={liveUploadHistory.length === 0}
                  className="text-xs font-bold gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  <Download className="h-3.5 w-3.5" />
                  <span>Exportar Bitácora .xlsx</span>
                </Button>

                {liveUploadHistory.length > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleClearLiveBitacora}
                    className="text-xs font-semibold gap-1.5 text-rose-400 border-rose-500/30 hover:bg-rose-500/10"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>Vaciar</span>
                  </Button>
                )}
              </div>
            </div>

            {/* Selector de Sub-vista de Bitácora y Barra de Búsqueda */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center p-1 rounded-xl bg-muted/60 border border-border shrink-0">
                <button
                  onClick={() => setBitacoraViewMode("live")}
                  className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                    bitacoraViewMode === "live"
                      ? "bg-primary text-primary-foreground shadow"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  🚀 Subidos en Plataforma / Exclusión Activa ({liveUploadHistory.length})
                </button>
                <button
                  onClick={() => setBitacoraViewMode("historical")}
                  className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                    bitacoraViewMode === "historical"
                      ? "bg-primary text-primary-foreground shadow"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  📋 Historial Importado Previo ({ozmapRawHistory.length})
                </button>
              </div>

              <div className="relative w-full sm:w-72">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  value={bitacoraSearch}
                  onChange={(e) => setBitacoraSearch(e.target.value)}
                  placeholder="Buscar por cédula, nombre, caja..."
                  className="pl-8 h-8 text-xs bg-background/50 border-border"
                />
              </div>
            </div>
          </Card>

          {/* TABLA: REGISTROS EN VIVO (SUBIDOS DESDE LA PLATAFORMA) */}
          {bitacoraViewMode === "live" ? (
            <Card className="p-0 overflow-hidden border-border bg-card/60 backdrop-blur">
              {liveUploadHistory.length === 0 ? (
                <div className="p-12 text-center text-muted-foreground text-xs space-y-2">
                  <Database className="h-8 w-8 mx-auto text-muted-foreground/50 mb-2" />
                  <p className="font-bold text-foreground">Aún no hay clientes subidos registrados en la bitácora activa.</p>
                  <p>Al subir clientes individualmente o por lotes en el Paso 2, se registrarán aquí con su fecha, caja y estado.</p>
                </div>
              ) : (
                <div className="overflow-x-auto max-h-[600px]">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/80 sticky top-0 border-b border-border text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                      <tr>
                        <th className="p-3 pl-4">Fecha / Hora</th>
                        <th className="p-3">Código OZmap</th>
                        <th className="p-3">Abonado</th>
                        <th className="p-3">Cédula</th>
                        <th className="p-3">ID Servicio</th>
                        <th className="p-3">Caja NAP Oficial</th>
                        <th className="p-3">Precinto</th>
                        <th className="p-3">Serial ONU</th>
                        <th className="p-3 text-center">Georreferenciado</th>
                        <th className="p-3 text-center">Estado</th>
                        <th className="p-3 pr-4 text-right">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {liveUploadHistory
                        .filter((r) => {
                          if (!bitacoraSearch.trim()) return true;
                          const q = bitacoraSearch.toLowerCase();
                          return (
                            r.cliente.toLowerCase().includes(q) ||
                            r.cedula.toLowerCase().includes(q) ||
                            r.codigo_ozmap.toLowerCase().includes(q) ||
                            r.caja_nap.toLowerCase().includes(q) ||
                            (r.id_servicio && r.id_servicio.toLowerCase().includes(q)) ||
                            (r.precinto && r.precinto.toLowerCase().includes(q)) ||
                            (r.serial_onu && r.serial_onu.toLowerCase().includes(q))
                          );
                        })
                        .map((r) => (
                          <tr key={r.id} className="hover:bg-muted/30 transition-colors">
                            <td className="p-3 pl-4 font-mono text-[11px] text-muted-foreground whitespace-nowrap">
                              <div>{r.fecha}</div>
                              <div className="text-[10px] text-muted-foreground/70">{r.hora}</div>
                            </td>
                            <td className="p-3 font-mono text-[11px] font-bold text-primary">{r.codigo_ozmap}</td>
                            <td className="p-3 font-semibold text-foreground">{r.cliente}</td>
                            <td className="p-3 font-mono text-muted-foreground">{r.cedula}</td>
                            <td className="p-3 font-mono text-muted-foreground">{r.id_servicio || "—"}</td>
                            <td className="p-3 font-mono font-bold text-foreground">
                              <span>{r.caja_nap}</span>
                              {r.caja_original && r.caja_original !== r.caja_nap && (
                                <span className="block text-[10px] text-muted-foreground font-normal">
                                  Orig: {r.caja_original}
                                </span>
                              )}
                            </td>
                            <td className="p-3 font-mono text-muted-foreground">{r.precinto || "S/P"}</td>
                            <td className="p-3 font-mono text-muted-foreground">{r.serial_onu || "—"}</td>
                            <td className="p-3 text-center">
                              {r.georreferenciado ? (
                                <span className="text-emerald-400 font-bold text-xs">✅ Sí</span>
                              ) : (
                                <span className="text-muted-foreground text-xs">❌ No</span>
                              )}
                            </td>
                            <td className="p-3 text-center">
                              <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-400 bg-emerald-500/10 whitespace-nowrap">
                                {r.estado}
                              </Badge>
                            </td>
                            <td className="p-3 pr-4 text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleRemoveFromLiveBitacora(r.id, r.cliente)}
                                title="Quitar de exclusión para permitir re-cotejo"
                                className="h-7 px-2 text-[11px] font-semibold text-amber-400 hover:text-amber-300 hover:bg-amber-500/10 cursor-pointer"
                              >
                                ↺ Re-incluir
                              </Button>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          ) : (
            /* TABLA: HISTORIAL IMPORTADO PREVIO (600) */
            <Card className="p-0 overflow-hidden border-border bg-card/60 backdrop-blur">
              <div className="overflow-x-auto max-h-[600px]">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/80 sticky top-0 border-b border-border text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                    <tr>
                      <th className="p-3 pl-4">Código OZmap</th>
                      <th className="p-3">Abonado</th>
                      <th className="p-3">Cédula</th>
                      <th className="p-3">Caja NAP Oficial</th>
                      <th className="p-3">Precinto</th>
                      <th className="p-3">Serial ONU</th>
                      <th className="p-3">Coordenadas</th>
                      <th className="p-3 text-right pr-4">Estado Red</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {ozmapRawHistory
                      .filter((r) => {
                        if (!bitacoraSearch.trim()) return true;
                        const q = bitacoraSearch.toLowerCase();
                        return (
                          r.cliente.toLowerCase().includes(q) ||
                          r.cedula.toLowerCase().includes(q) ||
                          r.codigo_ozmap.toLowerCase().includes(q) ||
                          r.caja_nap.toLowerCase().includes(q) ||
                          (r.precinto && r.precinto.toLowerCase().includes(q)) ||
                          (r.serial_onu && r.serial_onu.toLowerCase().includes(q))
                        );
                      })
                      .slice(0, 100)
                      .map((r, i) => (
                        <tr key={i} className="hover:bg-muted/30 transition-colors">
                          <td className="p-3 pl-4 font-mono text-[11px] font-bold text-primary">{r.codigo_ozmap}</td>
                          <td className="p-3 font-semibold text-foreground">{r.cliente}</td>
                          <td className="p-3 font-mono text-muted-foreground">{r.cedula}</td>
                          <td className="p-3 font-mono font-bold text-foreground">{r.caja_nap}</td>
                          <td className="p-3 font-mono text-muted-foreground">{r.precinto}</td>
                          <td className="p-3 font-mono text-muted-foreground">{r.serial_onu}</td>
                          <td className="p-3 font-mono text-[10px] text-muted-foreground">
                            {r.georreferenciado ? "✅ Sí" : "❌ No"}
                          </td>
                          <td className="p-3 text-right pr-4">
                            <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-400 bg-emerald-500/10">
                              {r.estado}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* MODAL: CONFIGURAR API OZMAP */}
      <Dialog open={isConfigModalOpen} onOpenChange={setIsConfigModalOpen}>
        <DialogContent className="max-w-md bg-card border-border">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-black">
              <Settings className="h-4 w-4 text-primary" />
              <span>Configuración de Servidor API OZmap</span>
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2 text-xs">
            <div>
              <label className="font-bold text-foreground block mb-1">URL del Servidor OZmap:</label>
              <Input
                value={apiServer}
                onChange={(e) => setApiServer(e.target.value)}
                placeholder="https://powerlink.ozmap.com.br:9994"
                className="h-8 text-xs font-mono"
              />
            </div>
            <div>
              <label className="font-bold text-foreground block mb-1">Usuario de API:</label>
              <Input
                value={apiUser}
                onChange={(e) => setApiUser(e.target.value)}
                placeholder="api.powerlink"
                className="h-8 text-xs font-mono"
              />
            </div>
            <div>
              <label className="font-bold text-foreground block mb-1">Contraseña de API:</label>
              <Input
                type="password"
                value={apiPass}
                onChange={(e) => setApiPass(e.target.value)}
                placeholder="••••••••"
                className="h-8 text-xs font-mono"
              />
            </div>
          </div>
          <DialogFooter className="flex items-center justify-between sm:justify-between">
            <Button variant="ghost" size="sm" onClick={() => setIsConfigModalOpen(false)} className="text-xs">
              Cancelar
            </Button>
            <Button size="sm" onClick={handleSaveApiConfig} className="text-xs font-bold bg-primary text-primary-foreground">
              Guardar Credenciales
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL: DICCIONARIO DE APRENDIZAJE DE CAJAS */}
      <Dialog open={isLearnedModalOpen} onOpenChange={setIsLearnedModalOpen}>
        <DialogContent className="max-w-2xl bg-card border-border max-h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-black">
              <Brain className="h-4 w-4 text-primary" />
              <span>Base de Aprendizaje de Cajas ({Object.keys(learnedBoxes).length} Cajas Memorizadas)</span>
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2 flex-1 overflow-y-auto text-xs">
            {/* Formulario para agregar corrección manual */}
            <div className="p-3 rounded-xl border border-border bg-muted/30 space-y-2">
              <span className="font-bold text-foreground block">Aprender Nueva Corrección de Caja:</span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <Input
                  placeholder="Texto Reportado (ej: NP 12 04)"
                  value={newLearnedRaw}
                  onChange={(e) => setNewLearnedRaw(e.target.value)}
                  className="h-8 text-xs"
                />
                <Input
                  placeholder="Caja Oficial (ej: NAP-12-04)"
                  value={newLearnedOfficial}
                  onChange={(e) => setNewLearnedOfficial(e.target.value)}
                  className="h-8 text-xs"
                />
              </div>
              <Button size="sm" onClick={handleAddNewLearned} className="w-full h-8 text-xs font-bold bg-primary text-primary-foreground">
                + Memorizar Corrección
              </Button>
            </div>

            {/* Búsqueda en el diccionario */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Buscar caja aprendida..."
                value={learnedSearch}
                onChange={(e) => setLearnedSearch(e.target.value)}
                className="pl-8 h-8 text-xs"
              />
            </div>

            {/* Lista de cajas aprendidas */}
            <div className="border border-border rounded-xl overflow-hidden max-h-60 overflow-y-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted text-[10px] font-bold text-muted-foreground uppercase sticky top-0">
                  <tr>
                    <th className="p-2.5 pl-3">Texto Original Reportado</th>
                    <th className="p-2.5">Caja Oficial Definitiva</th>
                    <th className="p-2.5 text-right pr-3">Acción</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {Object.entries(learnedBoxes)
                    .filter(([key, val]) => {
                      if (!learnedSearch.trim()) return true;
                      const q = learnedSearch.toUpperCase();
                      return key.includes(q) || val.officialBox.toUpperCase().includes(q);
                    })
                    .map(([key, val]) => (
                      <tr key={key} className="hover:bg-muted/30">
                        <td className="p-2.5 pl-3 font-mono text-muted-foreground">{val.rawOriginal || key}</td>
                        <td className="p-2.5 font-bold font-mono text-primary">{val.officialBox}</td>
                        <td className="p-2.5 text-right pr-3">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteLearned(key)}
                            className="h-6 w-6 p-0 text-rose-400 hover:text-rose-300"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* MODAL: FICHA TÉCNICA DEL ABONADO */}
      <Dialog open={!!selectedDetailClient} onOpenChange={(open) => !open && setSelectedDetailClient(null)}>
        {selectedDetailClient && (
          <DialogContent className="max-w-md bg-card border-border text-xs">
            <DialogHeader>
              <DialogTitle className="text-base font-black">Ficha Técnica de Migración</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div className="p-3 bg-muted/40 rounded-xl border border-border space-y-1.5">
                <span className="text-[10px] font-bold uppercase text-primary tracking-wider">Código Identificador</span>
                <span className="text-sm font-mono font-black text-foreground block">
                  {formatOzmapClientCode(selectedDetailClient)}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase font-bold">Cliente:</span>
                  <span className="font-bold text-foreground">{selectedDetailClient.nombres}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase font-bold">Cédula:</span>
                  <span className="font-mono text-foreground">{selectedDetailClient.cedula}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase font-bold">ID Servicio:</span>
                  <span className="font-mono text-foreground">{selectedDetailClient.id_servicio || "-"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase font-bold">ID Usuario:</span>
                  <span className="font-mono text-foreground">{selectedDetailClient.id_usuario || "-"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase font-bold">Precinto:</span>
                  <span className="font-mono text-foreground font-bold">{selectedDetailClient.precinto || "S/P"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase font-bold">Serial ONU:</span>
                  <span className="font-mono text-foreground">{selectedDetailClient.serial_onu || "S/S"}</span>
                </div>
                <div className="col-span-2 pt-2 border-t border-border">
                  <span className="text-muted-foreground block text-[10px] uppercase font-bold">Caja Oficial Definitiva:</span>
                  <span className="font-mono font-black text-primary text-sm">
                    {selectedDetailClient.caja_oficial || "Pendiente de validación"}
                  </span>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button
                size="sm"
                onClick={() => setSelectedDetailClient(null)}
                className="w-full text-xs font-bold bg-primary text-primary-foreground"
              >
                Cerrar Ficha
              </Button>
            </DialogFooter>
          </DialogContent>
        )}
      </Dialog>

      {/* MODAL: ADVERTENCIA ABONADOS INCOMPLETOS AL PASAR A PASO 2 */}
      <Dialog open={isStep1WarningModalOpen} onOpenChange={setIsStep1WarningModalOpen}>
        <DialogContent className="max-w-2xl bg-card border-border max-h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-black text-amber-500">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              <span>Abonados con Datos de Campo Incompletos ({incompleteClients.length})</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2 flex-1 overflow-y-auto text-xs">
            <div className="p-3.5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200 space-y-1">
              <p className="font-semibold text-xs">
                Se detectaron {incompleteClients.length} abonados que aún no tienen <strong>Precinto</strong> o <strong>Caja NAP</strong> reportados por el técnico.
              </p>
              <p className="text-[11px] opacity-90">
                Para evitar errores o registros huérfanos al subir a OZmap, puedes descartar los incompletos y continuar con los listos, eliminarlos individualmente, o volver a la tabla para completar los datos faltantes.
              </p>
            </div>

            {/* Tarjetas de desglose rápido */}
            <div className="grid grid-cols-3 gap-2.5">
              <div className="p-2.5 rounded-lg border border-border bg-muted/40 text-center">
                <span className="text-[10px] uppercase font-bold text-muted-foreground block">Sin Precinto</span>
                <span className="text-base font-black text-amber-500">
                  {incompleteClients.filter((r) => !r.precinto?.trim() && !!r.caja_nap?.trim()).length}
                </span>
              </div>
              <div className="p-2.5 rounded-lg border border-border bg-muted/40 text-center">
                <span className="text-[10px] uppercase font-bold text-muted-foreground block">Sin Caja NAP</span>
                <span className="text-base font-black text-amber-500">
                  {incompleteClients.filter((r) => !r.caja_nap?.trim() && !!r.precinto?.trim()).length}
                </span>
              </div>
              <div className="p-2.5 rounded-lg border border-border bg-muted/40 text-center">
                <span className="text-[10px] uppercase font-bold text-muted-foreground block">Sin Ambos</span>
                <span className="text-base font-black text-rose-500">
                  {incompleteClients.filter((r) => !r.precinto?.trim() && !r.caja_nap?.trim()).length}
                </span>
              </div>
            </div>

            {/* Lista de clientes incompletos con acción de eliminar individual */}
            <div className="border border-border rounded-xl overflow-hidden">
              <div className="bg-muted px-3 py-2 text-[11px] font-bold text-muted-foreground flex justify-between items-center">
                <span>Listado de abonados pendientes ({incompleteClients.length}):</span>
                <span className="text-[10px] opacity-75">Click en 🗑️ para descartar individualmente</span>
              </div>
              <div className="max-h-56 overflow-y-auto divide-y divide-border">
                {incompleteClients.map((client) => {
                  const faltaPrecinto = !client.precinto?.trim();
                  const faltaCaja = !client.caja_nap?.trim();
                  return (
                    <div
                      key={client.id}
                      className="p-2.5 px-3 flex items-center justify-between gap-3 hover:bg-muted/30 transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-foreground text-xs truncate">{client.nombres}</span>
                          <span className="font-mono text-[10px] text-muted-foreground">CI: {client.cedula || "-"}</span>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          {faltaPrecinto && (
                            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 px-1.5 py-0.5 rounded border border-amber-200 dark:border-amber-800">
                              ⚠️ Falta Precinto
                            </span>
                          )}
                          {faltaCaja && (
                            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40 px-1.5 py-0.5 rounded border border-rose-200 dark:border-rose-800">
                              ⚠️ Falta Caja NAP
                            </span>
                          )}
                          {!faltaPrecinto && (
                            <span className="text-[10px] text-muted-foreground font-mono">
                              Precinto: {client.precinto}
                            </span>
                          )}
                          {!faltaCaja && (
                            <span className="text-[10px] text-muted-foreground font-mono">
                              Caja: {client.caja_nap}
                            </span>
                          )}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDeleteFromWarningModal(client.id, client.nombres || "")}
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-rose-500 hover:bg-rose-500/10 shrink-0"
                        title="Descartar este abonado del lote"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <DialogFooter className="flex flex-col sm:flex-row items-center justify-between gap-2 pt-2 border-t border-border">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsStep1WarningModalOpen(false)}
              className="w-full sm:w-auto text-xs"
            >
              Volver a Revisar / Completar en Tabla
            </Button>
            <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleGoToStep2(true)}
                className="text-xs text-muted-foreground hover:text-foreground"
                title="Avanzar incluyendo estos clientes sin descartar"
              >
                Avanzar de todos modos
              </Button>
              <Button
                size="sm"
                onClick={handleDiscardIncompleteAndAdvance}
                className="w-full sm:w-auto text-xs font-black bg-primary text-primary-foreground hover:brightness-110 shadow-md gap-1.5"
              >
                <span>Descartar Incompletos y Continuar ({comparisonResults.length - incompleteClients.length} listos)</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
