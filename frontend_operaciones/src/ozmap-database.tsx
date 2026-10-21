"use client";

import React, { useState, useEffect, useMemo } from "react";
import * as XLSX from "xlsx";
import {
  Database,
  Globe2,
  Search,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Trash2,
  RefreshCw,
  Eye,
  ShieldCheck,
  FileSpreadsheet,
  Undo2,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  getDiscardedAuditRecords,
  deleteDiscardedRecordPermanently,
  clearDiscardedAuditRecords,
  queueClientForRestoration,
  updateDiscardedRecord,
  verifyClientInOzmapApi,
  checkClientInLocalDatasets,
  type OzmapDiscardedRecord,
} from "@/lib/ozmap-audit";
import { type NavView } from "@/components/layout/sidebar";
import ozmapRawHistory from "@/data/ozmap_history.json";

export interface BitacoraHistoryRecord {
  id?: string;
  fecha: string;
  hora: string;
  id_servicio?: string;
  id_usuario?: string;
  cliente: string;
  cedula: string;
  serial_onu?: string;
  precinto?: string;
  caja_nap: string;
  codigo_ozmap: string;
  georreferenciado?: boolean;
  estado?: string;
}

interface OzmapDatabaseModuleProps {
  onNavigate?: (view: NavView) => void;
}

export function OzmapDatabaseModule({ onNavigate }: OzmapDatabaseModuleProps) {
  // Estado de registros descartados
  const [discardedRecords, setDiscardedRecords] = useState<OzmapDiscardedRecord[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "no_subido" | "verificado" | "reincorporado">("all");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 12;

  // Estado de bitácora en vivo
  const [liveHistory, setLiveHistory] = useState<BitacoraHistoryRecord[]>([]);
  const [historySearch, setHistorySearch] = useState("");
  const [historyPage, setHistoryPage] = useState(1);

  // Estados de verificación
  const [isVerifyingAll, setIsVerifyingAll] = useState(false);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<OzmapDiscardedRecord | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);

  // Estado de mensaje / feedback
  const [toastMessage, setToastMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);

  // Verificador rápido individual
  const [quickQuery, setQuickQuery] = useState("");
  const [isQuickChecking, setIsQuickChecking] = useState(false);
  const [quickResult, setQuickResult] = useState<{
    found: boolean;
    cedula: string;
    id_servicio?: string;
    nombres?: string;
    caja?: string;
    source?: string;
    codigo_ozmap?: string;
    details?: Record<string, unknown>;
  } | null>(null);

  const showToast = (text: string, type: "success" | "error" | "info" = "info") => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Cargar datos al montar y suscribirse a eventos
  const reloadData = async () => {
    const records = getDiscardedAuditRecords();
    setDiscardedRecords(records);

    if (typeof window !== "undefined") {
      try {
        const rawLive = localStorage.getItem("ozmap_live_upload_history");
        if (rawLive) {
          const parsed = JSON.parse(rawLive);
          if (Array.isArray(parsed) && parsed.length > 0) {
            setLiveHistory(parsed);
            return;
          }
        }

        // Sincronización con API de la Intranet
        try {
          const res = await fetch("/api/operaciones/ozmap/bitacora");
          if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
              setLiveHistory(data);
              localStorage.setItem("ozmap_live_upload_history", JSON.stringify(data));
              return;
            }
          }
        } catch {
          // Fallback silencioso si no hay red
        }

        // Respaldo inmediato con el dataset histórico importado
        if (Array.isArray(ozmapRawHistory) && ozmapRawHistory.length > 0) {
          setLiveHistory(ozmapRawHistory as BitacoraHistoryRecord[]);
          localStorage.setItem("ozmap_live_upload_history", JSON.stringify(ozmapRawHistory));
        }
      } catch (e) {
        console.warn("Error leyendo bitácora local o remota:", e);
      }
    }
  };

  useEffect(() => {
    reloadData();

    const handleUpdate = () => {
      reloadData();
    };

    window.addEventListener("ozmap-discarded-updated", handleUpdate);
    return () => {
      window.removeEventListener("ozmap-discarded-updated", handleUpdate);
    };
  }, []);

  // Métricas
  const totalDiscarded = discardedRecords.length;
  const verifiedCount = discardedRecords.filter((r) => r.estado_ozmap === "verificado").length;
  const pendingCount = discardedRecords.filter((r) => r.estado_ozmap === "no_subido").length;
  const restoredCount = discardedRecords.filter((r) => r.estado_ozmap === "reincorporado" || r.restaurado).length;

  // Filtrado de descartes
  const filteredDiscarded = useMemo(() => {
    return discardedRecords.filter((item) => {
      // Filtro por estado
      if (statusFilter !== "all" && item.estado_ozmap !== statusFilter) {
        return false;
      }

      // Filtro por texto
      if (!searchTerm.trim()) return true;
      const q = searchTerm.toLowerCase().trim();
      return (
        item.nombres?.toLowerCase().includes(q) ||
        item.cedula?.toLowerCase().includes(q) ||
        item.id_servicio?.toLowerCase().includes(q) ||
        item.id_usuario?.toLowerCase().includes(q) ||
        item.serial_onu?.toLowerCase().includes(q) ||
        item.precinto?.toLowerCase().includes(q) ||
        item.caja_nap?.toLowerCase().includes(q) ||
        item.caja_oficial?.toLowerCase().includes(q) ||
        item.motivo_descarte?.toLowerCase().includes(q)
      );
    });
  }, [discardedRecords, statusFilter, searchTerm]);

  // Paginación descartes
  const totalPages = Math.ceil(filteredDiscarded.length / itemsPerPage) || 1;
  const paginatedDiscarded = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredDiscarded.slice(start, start + itemsPerPage);
  }, [filteredDiscarded, currentPage]);

  // Filtrado de bitácora
  const filteredHistory = useMemo(() => {
    if (!historySearch.trim()) return liveHistory;
    const q = historySearch.toLowerCase().trim();
    return liveHistory.filter((item) => {
      return (
        item.cliente?.toLowerCase().includes(q) ||
        item.cedula?.toLowerCase().includes(q) ||
        item.id_servicio?.toLowerCase().includes(q) ||
        item.codigo_ozmap?.toLowerCase().includes(q) ||
        item.caja_nap?.toLowerCase().includes(q) ||
        item.precinto?.toLowerCase().includes(q)
      );
    });
  }, [liveHistory, historySearch]);

  const totalHistoryPages = Math.ceil(filteredHistory.length / itemsPerPage) || 1;
  const paginatedHistory = useMemo(() => {
    const start = (historyPage - 1) * itemsPerPage;
    return filteredHistory.slice(start, start + itemsPerPage);
  }, [filteredHistory, historyPage]);

  // Acciones sobre registros individuales
  const handleVerifySingle = async (record: OzmapDiscardedRecord) => {
    setVerifyingId(record.id);
    try {
      const serverUrl = localStorage.getItem("ozmap_api_server") || "https://powerlink.ozmap.com.br:9994";
      const apiUser = localStorage.getItem("ozmap_api_user") || "api.powerlink";
      const apiPass = localStorage.getItem("ozmap_api_pass") || "gxgq459n";

      let authHeader = "";
      try {
        const loginRes = await fetch(`${serverUrl.replace(/\/+$/, "")}/api/v2/users/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ login: apiUser, password: apiPass }),
        });
        if (loginRes.ok) {
          const loginData = await loginRes.json();
          const token = loginData.authorization || loginData.authenticationKey;
          authHeader = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
        }
      } catch (errAuth) {
        console.warn("No se pudo conectar directamente con API OZmap, verificando histórico:", errAuth);
      }

      const res = await verifyClientInOzmapApi(record, serverUrl, authHeader);
      const now = new Date();
      const fechaVerif = `${now.toISOString().slice(0, 10)} ${now.toTimeString().slice(0, 5)}`;

      if (res.found) {
        updateDiscardedRecord(record.id, {
          estado_ozmap: "verificado",
          detalles_verificacion: {
            metodo: res.source.includes("API") ? "api_en_vivo" : "bitacora_local",
            fecha_verificacion: fechaVerif,
            ozmap_client_id: res.ozmapId,
            observacion: res.observation || `Encontrado vía ${res.source}`,
          },
        });
        showToast(`✅ Abonado ${record.nombres} verificado: YA está en OZmap (${res.source}).`, "success");
      } else {
        updateDiscardedRecord(record.id, {
          estado_ozmap: "no_subido",
          detalles_verificacion: {
            metodo: "manual",
            fecha_verificacion: fechaVerif,
            observacion: "No encontrado en OZmap ni en bitácora local.",
          },
        });
        showToast(`⚠️ Abonado ${record.nombres} NO se encuentra en OZmap. Requiere reincorporación o subida.`, "info");
      }
      reloadData();
    } catch (err: unknown) {
      showToast(`Error al verificar: ${err instanceof Error ? err.message : String(err)}`, "error");
    } finally {
      setVerifyingId(null);
    }
  };

  // Verificación masiva contra OZmap
  const handleVerifyAll = async () => {
    if (discardedRecords.length === 0) {
      showToast("No hay registros descartados para verificar.", "info");
      return;
    }

    setIsVerifyingAll(true);
    showToast("Iniciando verificación masiva en base de datos OZmap...", "info");

    try {
      const serverUrl = localStorage.getItem("ozmap_api_server") || "https://powerlink.ozmap.com.br:9994";
      const apiUser = localStorage.getItem("ozmap_api_user") || "api.powerlink";
      const apiPass = localStorage.getItem("ozmap_api_pass") || "gxgq459n";

      let authHeader = "";
      try {
        const loginRes = await fetch(`${serverUrl.replace(/\/+$/, "")}/api/v2/users/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ login: apiUser, password: apiPass }),
        });
        if (loginRes.ok) {
          const loginData = await loginRes.json();
          const token = loginData.authorization || loginData.authenticationKey;
          authHeader = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
        }
      } catch (e) {
        console.warn("Fallo login masivo:", e);
      }

      let verifiedFound = 0;
      let missingCount = 0;

      for (const rec of discardedRecords) {
        const res = await verifyClientInOzmapApi(rec, serverUrl, authHeader);
        const now = new Date();
        const fechaVerif = `${now.toISOString().slice(0, 10)} ${now.toTimeString().slice(0, 5)}`;

        if (res.found) {
          verifiedFound++;
          updateDiscardedRecord(rec.id, {
            estado_ozmap: "verificado",
            detalles_verificacion: {
              metodo: res.source.includes("API") ? "api_en_vivo" : "bitacora_local",
              fecha_verificacion: fechaVerif,
              ozmap_client_id: res.ozmapId,
              observacion: res.observation || `Encontrado vía ${res.source}`,
            },
          });
        } else {
          missingCount++;
          updateDiscardedRecord(rec.id, {
            estado_ozmap: "no_subido",
            detalles_verificacion: {
              metodo: "manual",
              fecha_verificacion: fechaVerif,
              observacion: "No encontrado en OZmap ni en bitácora local.",
            },
          });
        }
      }

      reloadData();
      showToast(
        `Verificación completada: ${verifiedFound} encontrados en OZmap, ${missingCount} pendientes/no subidos.`,
        "success"
      );
    } catch (err: unknown) {
      showToast(`Error durante la verificación: ${err instanceof Error ? err.message : String(err)}`, "error");
    } finally {
      setIsVerifyingAll(false);
    }
  };

  // Reincorporación de abonado
  const handleRestoreClient = (record: OzmapDiscardedRecord) => {
    queueClientForRestoration(record);
    showToast(`Abonado "${record.nombres}" reincorporado. Disponible para el Módulo OZmap.`, "success");
    reloadData();
  };

  // Eliminación definitiva
  const handleDeletePermanent = (record: OzmapDiscardedRecord) => {
    if (window.confirm(`¿Estás seguro de eliminar PERMANENTEMENTE a "${record.nombres}" de la papelera de auditoría?`)) {
      deleteDiscardedRecordPermanently(record.id);
      showToast(`Registro de "${record.nombres}" eliminado definitivamente.`, "info");
      reloadData();
    }
  };

  // Vaciar papelera
  const handleClearTrash = () => {
    if (
      window.confirm(
        "¿Deseas vaciar todos los registros de abonados descartados? Esta acción eliminará el historial de descartes actual."
      )
    ) {
      clearDiscardedAuditRecords();
      showToast("Papelera de auditoría vaciada.", "info");
      reloadData();
    }
  };

  // Exportar Excel Completo
  const handleExportFullAuditExcel = () => {
    try {
      const wb = XLSX.utils.book_new();

      // Hoja 1: Clientes Descartados
      const discardData = discardedRecords.map((r, idx) => ({
        "N°": idx + 1,
        "Fecha Descarte": r.fecha_descarte,
        "Hora Descarte": r.hora_descarte,
        "Motivo de Descarte": r.motivo_descarte,
        "Origen en Módulo": r.origen_paso,
        "ID Servicio": r.id_servicio,
        "ID Usuario": r.id_usuario,
        "Abonado": r.nombres,
        "Cédula": r.cedula,
        "Serial ONU": r.serial_onu,
        "Precinto": r.precinto,
        "Caja NAP Reportada": r.caja_nap,
        "Caja NAP Oficial": r.caja_oficial || "",
        "Código OZmap": r.codigo_ozmap,
        "Estado en OZmap":
          r.estado_ozmap === "verificado"
            ? "Verificado en OZmap"
            : r.estado_ozmap === "reincorporado"
            ? "Reincorporado"
            : "No Subido / Pendiente",
        "Detalle Verificación": r.detalles_verificacion?.observacion || "",
      }));
      const wsDiscard = XLSX.utils.json_to_sheet(discardData);
      XLSX.utils.book_append_sheet(wb, wsDiscard, "Abonados Descartados");

      // Hoja 2: Bitácora de Sincronizados
      if (liveHistory.length > 0) {
        const historyData = liveHistory.map((h, idx) => ({
          "N°": idx + 1,
          "Fecha": h.fecha,
          "Hora": h.hora,
          "Código OZmap": h.codigo_ozmap,
          "Abonado": h.cliente,
          "Cédula": h.cedula,
          "ID Servicio": h.id_servicio,
          "ID Usuario": h.id_usuario,
          "Caja NAP Oficial": h.caja_nap,
          "Precinto": h.precinto,
          "Serial ONU": h.serial_onu,
          "Georreferenciado": h.georreferenciado ? "Sí" : "No",
          "Estado": h.estado,
        }));
        const wsHistory = XLSX.utils.json_to_sheet(historyData);
        XLSX.utils.book_append_sheet(wb, wsHistory, "Bitacora OZmap Subidos");
      }

      const fileName = `Auditoria_OZmap_Descartes_${new Date().toISOString().slice(0, 10)}.xlsx`;
      XLSX.writeFile(wb, fileName);
      showToast(`Libro de auditoría exportado con éxito: ${fileName}`, "success");
    } catch (err: unknown) {
      showToast(`Error al exportar Excel: ${err instanceof Error ? err.message : String(err)}`, "error");
    }
  };

  // Buscador rápido
  const handleQuickCheck = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickQuery.trim()) return;

    setIsQuickChecking(true);
    setQuickResult(null);

    try {
      const q = quickQuery.trim();
      const local = checkClientInLocalDatasets(q, q);

      if (local.found) {
        setQuickResult({
          found: true,
          cedula: local.details?.cedula ? String(local.details.cedula) : q,
          id_servicio: local.details?.id_servicio ? String(local.details.id_servicio) : undefined,
          nombres: (local.details?.cliente as string) || (local.details?.nombres as string) || undefined,
          caja: local.caja,
          source: local.source === "bitacora" ? "Bitácora Local de Subidas" : "Histórico Consolidado OZmap",
          codigo_ozmap: local.details?.codigo_ozmap ? String(local.details.codigo_ozmap) : undefined,
          details: local.details,
        });
        showToast("Abonado encontrado en registros locales.", "success");
      } else {
        // Consultar API en vivo
        const serverUrl = localStorage.getItem("ozmap_api_server") || "https://powerlink.ozmap.com.br:9994";
        const apiUser = localStorage.getItem("ozmap_api_user") || "api.powerlink";
        const apiPass = localStorage.getItem("ozmap_api_pass") || "gxgq459n";

        let authHeader = "";
        try {
          const loginRes = await fetch(`${serverUrl.replace(/\/+$/, "")}/api/v2/users/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ login: apiUser, password: apiPass }),
          });
          if (loginRes.ok) {
            const loginData = await loginRes.json();
            const token = loginData.authorization || loginData.authenticationKey;
            authHeader = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
          }
        } catch (e) {
          console.warn("Fallo login:", e);
        }

        const dummyRecord: OzmapDiscardedRecord = {
          id: "temp",
          fecha_descarte: "",
          hora_descarte: "",
          timestamp: 0,
          motivo_descarte: "",
          origen_paso: "",
          id_servicio: q,
          id_usuario: "",
          nombres: "",
          cedula: q,
          serial_onu: "",
          precinto: "",
          caja_nap: "",
          codigo_ozmap: `R-${q}`,
          estado_ozmap: "no_subido",
        };

        const apiRes = await verifyClientInOzmapApi(dummyRecord, serverUrl, authHeader);
        if (apiRes.found) {
          setQuickResult({
            found: true,
            cedula: q,
            id_servicio: q,
            nombres: "Abonado en Servidor OZmap",
            caja: apiRes.observation,
            source: apiRes.source,
            codigo_ozmap: apiRes.code,
          });
          showToast("Abonado localizado en la API de OZmap.", "success");
        } else {
          setQuickResult({
            found: false,
            cedula: q,
            source: "No registrado en OZmap",
          });
          showToast("El abonado no se encuentra en OZmap.", "info");
        }
      }
    } catch (err: unknown) {
      showToast(`Error al consultar: ${err instanceof Error ? err.message : String(err)}`, "error");
    } finally {
      setIsQuickChecking(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade">
      {/* Toast Alert */}
      {toastMessage && (
        <div
          className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-2xl border text-sm font-bold transition-all ${
            toastMessage.type === "success"
              ? "bg-zinc-950/95 border-emerald-500/50 text-emerald-400"
              : toastMessage.type === "error"
              ? "bg-zinc-950/95 border-rose-500/50 text-rose-400"
              : "bg-zinc-950/95 border-primary/50 text-primary"
          }`}
        >
          {toastMessage.type === "success" && <CheckCircle2 className="h-5 w-5" />}
          {toastMessage.type === "error" && <XCircle className="h-5 w-5" />}
          {toastMessage.type === "info" && <ShieldCheck className="h-5 w-5" />}
          <span>{toastMessage.text}</span>
        </div>
      )}

      {/* Encabezado Principal */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/80 pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="gold" className="text-[10px] tracking-wider uppercase">
              RED & MIGRACIÓN
            </Badge>
            <Badge variant="outline" className="text-[10px] border-primary/30 text-primary">
              AUDITORÍA DE DATOS
            </Badge>
          </div>
          <h1 className="text-2xl md:text-3xl font-black text-foreground uppercase tracking-tight flex items-center gap-3">
            <Database className="h-7 w-7 text-primary" />
            Base de Datos & Auditoría OZmap
          </h1>
          <p className="text-xs md:text-sm text-muted-foreground mt-1">
            Resguardo de abonados descartados, trazabilidad de modificaciones y verificación de sincronización en OZmap para garantizar cero pérdida de datos.
          </p>
        </div>

        {/* Acciones Rápidas del Encabezado */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={reloadData}
            className="gap-2 text-xs border-border/70 hover:border-primary/50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Refrescar</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleVerifyAll}
            disabled={isVerifyingAll || totalDiscarded === 0}
            className="gap-2 text-xs border-primary/40 text-primary hover:bg-primary/10"
          >
            <Sparkles className={`h-3.5 w-3.5 ${isVerifyingAll ? "animate-spin text-primary" : ""}`} />
            <span>{isVerifyingAll ? "Verificando en OZmap..." : "Verificar Todos en OZmap"}</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleExportFullAuditExcel}
            className="gap-2 text-xs bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" />
            <span>Exportar Excel</span>
          </Button>

          {onNavigate && (
            <Button
              size="sm"
              onClick={() => onNavigate("ozmap")}
              className="gap-2 text-xs font-bold shadow-md shadow-primary/20"
            >
              <Globe2 className="h-3.5 w-3.5" />
              <span>Ir a Módulo OZmap</span>
            </Button>
          )}
        </div>
      </div>

      {/* Tarjetas de Métricas KPI */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 border-border/70 bg-card/70 hover:border-primary/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground">Total Descartes</span>
            <Trash2 className="h-4 w-4 text-rose-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-foreground">{totalDiscarded}</span>
            <span className="text-[10px] text-muted-foreground">abonados protegidos</span>
          </div>
          <div className="mt-2 text-[11px] text-zinc-400">
            Resguardados en papelera de auditoría
          </div>
        </Card>

        <Card className="p-4 border-emerald-500/20 bg-emerald-500/5 hover:border-emerald-500/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-400">Verificados en OZmap</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-emerald-400">{verifiedCount}</span>
            <span className="text-[10px] text-emerald-500/80">sincronizados</span>
          </div>
          <div className="mt-2 text-[11px] text-zinc-400">
            Ya existen registrados en el mapa
          </div>
        </Card>

        <Card className="p-4 border-amber-500/20 bg-amber-500/5 hover:border-amber-500/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-400">Pendientes / No Subidos</span>
            <AlertTriangle className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-amber-400">{pendingCount}</span>
            <span className="text-[10px] text-amber-500/80">requieren atención</span>
          </div>
          <div className="mt-2 text-[11px] text-zinc-400">
            Descartados y ausentes en OZmap
          </div>
        </Card>

        <Card className="p-4 border-primary/20 bg-primary/5 hover:border-primary/40 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-primary">Sincronizados en Bitácora</span>
            <Globe2 className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-primary">{liveHistory.length}</span>
            <span className="text-[10px] text-primary/80">subidos en vivo</span>
          </div>
          <div className="mt-2 text-[11px] text-zinc-400">
            {restoredCount > 0 ? `${restoredCount} reincorporados` : "Historial operativo"}
          </div>
        </Card>
      </div>

      {/* Pestañas Principales */}
      <Tabs defaultValue="discarded" className="space-y-4">
        <TabsList className="bg-card border border-border/80 p-1 rounded-xl">
          <TabsTrigger value="discarded" className="gap-2 text-xs">
            <Trash2 className="h-3.5 w-3.5 text-rose-400" />
            <span>Abonados Descartados & Papelera ({totalDiscarded})</span>
          </TabsTrigger>
          <TabsTrigger value="bitacora" className="gap-2 text-xs">
            <Globe2 className="h-3.5 w-3.5 text-primary" />
            <span>Bitácora de Sincronizados ({liveHistory.length})</span>
          </TabsTrigger>
          <TabsTrigger value="quick-verify" className="gap-2 text-xs">
            <Search className="h-3.5 w-3.5 text-blue-400" />
            <span>Consultar Abonado en OZmap</span>
          </TabsTrigger>
        </TabsList>

        {/* --- PESTAÑA 1: ABONADOS DESCARTADOS --- */}
        <TabsContent value="discarded" className="space-y-4">
          <Card className="p-4 border-border/70 bg-card/60 space-y-4">
            {/* Barra de Filtros y Búsqueda */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Buscar por Abonado, Cédula, ID Servicio, Serial ONU, Caja o Motivo..."
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="pl-9 h-9 text-xs bg-background/80 border-border/80 focus-visible:ring-primary"
                />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant={statusFilter === "all" ? "default" : "outline"}
                  onClick={() => {
                    setStatusFilter("all");
                    setCurrentPage(1);
                  }}
                  className="h-8 text-xs font-semibold"
                >
                  Todos ({totalDiscarded})
                </Button>

                <Button
                  size="sm"
                  variant={statusFilter === "no_subido" ? "destructive" : "outline"}
                  onClick={() => {
                    setStatusFilter("no_subido");
                    setCurrentPage(1);
                  }}
                  className="h-8 text-xs font-semibold gap-1 text-amber-400 border-amber-500/30"
                >
                  <AlertTriangle className="h-3 w-3" />
                  <span>Pendientes ({pendingCount})</span>
                </Button>

                <Button
                  size="sm"
                  variant={statusFilter === "verificado" ? "secondary" : "outline"}
                  onClick={() => {
                    setStatusFilter("verificado");
                    setCurrentPage(1);
                  }}
                  className="h-8 text-xs font-semibold gap-1 text-emerald-400 border-emerald-500/30"
                >
                  <CheckCircle2 className="h-3 w-3" />
                  <span>En OZmap ({verifiedCount})</span>
                </Button>

                {restoredCount > 0 && (
                  <Button
                    size="sm"
                    variant={statusFilter === "reincorporado" ? "secondary" : "outline"}
                    onClick={() => {
                      setStatusFilter("reincorporado");
                      setCurrentPage(1);
                    }}
                    className="h-8 text-xs font-semibold gap-1 text-blue-400 border-blue-500/30"
                  >
                    <Undo2 className="h-3 w-3" />
                    <span>Reincorporados ({restoredCount})</span>
                  </Button>
                )}

                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleClearTrash}
                  title="Vaciar Papelera de Auditoría"
                  className="h-8 text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-500/10"
                >
                  <Trash2 className="h-3.5 w-3.5 mr-1" />
                  <span>Vaciar</span>
                </Button>
              </div>
            </div>

            {/* Tabla de Abonados Descartados */}
            <div className="overflow-x-auto rounded-xl border border-border/80">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/80 uppercase font-black tracking-wider text-[11px] text-muted-foreground border-b border-border">
                  <tr>
                    <th className="p-3">Fecha / Hora</th>
                    <th className="p-3">ID Serv / Usu</th>
                    <th className="p-3">Abonado / Cédula</th>
                    <th className="p-3">Serial ONU / Precinto</th>
                    <th className="p-3">Caja NAP (Original & Oficial)</th>
                    <th className="p-3">Motivo de Descarte</th>
                    <th className="p-3 text-center">Estado OZmap</th>
                    <th className="p-3 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60 font-medium">
                  {paginatedDiscarded.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="p-8 text-center text-muted-foreground">
                        <div className="flex flex-col items-center justify-center gap-2">
                          <CheckCircle2 className="h-8 w-8 text-emerald-400/50" />
                          <p className="text-sm font-semibold">No hay abonados en la papelera de auditoría.</p>
                          <p className="text-xs text-zinc-500">
                            Cualquier cliente eliminado en el proceso de cotejo de OZmap aparecerá aquí automáticamente.
                          </p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    paginatedDiscarded.map((row) => (
                      <tr
                        key={row.id}
                        className="hover:bg-muted/40 transition-colors group cursor-pointer"
                        onClick={() => {
                          setSelectedRecord(row);
                          setIsDetailModalOpen(true);
                        }}
                      >
                        <td className="p-3 whitespace-nowrap">
                          <div className="font-bold text-foreground">{row.fecha_descarte}</div>
                          <div className="text-[10px] text-muted-foreground">{row.hora_descarte} hrs</div>
                        </td>

                        <td className="p-3 whitespace-nowrap">
                          <div className="font-bold text-primary">{row.id_servicio || "S/S"}</div>
                          <div className="text-[10px] text-muted-foreground">Usu: {row.id_usuario || "S/U"}</div>
                        </td>

                        <td className="p-3">
                          <div className="font-bold text-foreground line-clamp-1">{row.nombres || "Sin Nombre"}</div>
                          <div className="text-[10px] font-mono text-zinc-400">CI: {row.cedula || "S/C"}</div>
                        </td>

                        <td className="p-3 whitespace-nowrap">
                          <div className="font-mono text-zinc-300">{row.serial_onu || "S/N"}</div>
                          <div className="text-[10px] font-mono text-amber-400">
                            Prec: {row.precinto || "Sin Precinto"}
                          </div>
                        </td>

                        <td className="p-3">
                          <div className="font-semibold text-zinc-300 line-clamp-1">
                            {row.caja_oficial || row.caja_nap || "Sin Caja"}
                          </div>
                          {row.caja_nap && row.caja_oficial && row.caja_nap !== row.caja_oficial && (
                            <div className="text-[10px] text-zinc-500 line-clamp-1">Orig: {row.caja_nap}</div>
                          )}
                        </td>

                        <td className="p-3">
                          <Badge
                            variant={
                              row.motivo_descarte.includes("precinto")
                                ? "warning"
                                : row.motivo_descarte.includes("Caja")
                                ? "info"
                                : "destructive"
                            }
                            className="text-[10px] line-clamp-1 max-w-[200px]"
                            title={row.motivo_descarte}
                          >
                            {row.motivo_descarte}
                          </Badge>
                          <div className="text-[9px] text-zinc-500 mt-0.5">{row.origen_paso}</div>
                        </td>

                        <td className="p-3 text-center whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                          {row.estado_ozmap === "verificado" ? (
                            <Badge variant="success" className="gap-1 text-[10px]">
                              <CheckCircle2 className="h-3 w-3" />
                              <span>En OZmap</span>
                            </Badge>
                          ) : row.estado_ozmap === "reincorporado" ? (
                            <Badge variant="info" className="gap-1 text-[10px]">
                              <Undo2 className="h-3 w-3" />
                              <span>Reincorporado</span>
                            </Badge>
                          ) : (
                            <Badge variant="warning" className="gap-1 text-[10px]">
                              <AlertTriangle className="h-3 w-3" />
                              <span>No Subido</span>
                            </Badge>
                          )}
                        </td>

                        <td className="p-3 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-end gap-1">
                            {/* Botón Verificar en OZmap */}
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleVerifySingle(row)}
                              disabled={verifyingId === row.id}
                              title="Verificar si existe en OZmap"
                              className="h-7 w-7 p-0 text-primary hover:bg-primary/20"
                            >
                              <Sparkles className={`h-3.5 w-3.5 ${verifyingId === row.id ? "animate-spin" : ""}`} />
                            </Button>

                            {/* Botón Reincorporar */}
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleRestoreClient(row)}
                              title="Reincorporar al lote de OZmap"
                              className="h-7 w-7 p-0 text-emerald-400 hover:bg-emerald-500/20"
                            >
                              <Undo2 className="h-3.5 w-3.5" />
                            </Button>

                            {/* Botón Ver Detalle */}
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => {
                                setSelectedRecord(row);
                                setIsDetailModalOpen(true);
                              }}
                              title="Ver Ficha Completa"
                              className="h-7 w-7 p-0 text-zinc-400 hover:text-white hover:bg-zinc-800"
                            >
                              <Eye className="h-3.5 w-3.5" />
                            </Button>

                            {/* Botón Eliminar Permanente */}
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleDeletePermanent(row)}
                              title="Eliminar permanentemente"
                              className="h-7 w-7 p-0 text-rose-400 hover:bg-rose-500/20"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Paginación */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between text-xs text-muted-foreground pt-2">
                <span>
                  Mostrando {paginatedDiscarded.length} de {filteredDiscarded.length} registros
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    className="h-7 px-2"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="font-bold text-foreground">
                    {currentPage} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                    className="h-7 px-2"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </TabsContent>

        {/* --- PESTAÑA 2: BITÁCORA DE SINCRONIZADOS --- */}
        <TabsContent value="bitacora" className="space-y-4">
          <Card className="p-4 border-border/70 bg-card/60 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Buscar en bitácora por Abonado, Cédula, Código OZmap, Caja..."
                  value={historySearch}
                  onChange={(e) => {
                    setHistorySearch(e.target.value);
                    setHistoryPage(1);
                  }}
                  className="pl-9 h-9 text-xs bg-background/80 border-border/80"
                />
              </div>

              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-xs">
                  {liveHistory.length} Registros Sincronizados
                </Badge>
              </div>
            </div>

            <div className="overflow-x-auto rounded-xl border border-border/80">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/80 uppercase font-black tracking-wider text-[11px] text-muted-foreground border-b border-border">
                  <tr>
                    <th className="p-3">Fecha / Hora</th>
                    <th className="p-3">Código OZmap</th>
                    <th className="p-3">Abonado</th>
                    <th className="p-3">Cédula</th>
                    <th className="p-3">ID Servicio</th>
                    <th className="p-3">Caja Oficial</th>
                    <th className="p-3">Precinto</th>
                    <th className="p-3">Serial ONU</th>
                    <th className="p-3 text-center">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60 font-medium">
                  {paginatedHistory.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="p-8 text-center text-muted-foreground">
                        <div className="flex flex-col items-center justify-center gap-2">
                          <Globe2 className="h-8 w-8 text-primary/40" />
                          <p className="text-sm font-semibold">No hay clientes sincronizados en la bitácora activa.</p>
                          <p className="text-xs text-zinc-500">
                            Los clientes que subas desde el Módulo OZmap se listarán aquí en tiempo real.
                          </p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    paginatedHistory.map((row, idx) => (
                      <tr key={row.id || idx} className="hover:bg-muted/40 transition-colors">
                        <td className="p-3 whitespace-nowrap">
                          <div className="font-bold text-foreground">{row.fecha}</div>
                          <div className="text-[10px] text-muted-foreground">{row.hora} hrs</div>
                        </td>
                        <td className="p-3 font-mono text-primary font-bold">{row.codigo_ozmap}</td>
                        <td className="p-3 font-semibold text-foreground">{row.cliente}</td>
                        <td className="p-3 font-mono text-zinc-400">{row.cedula}</td>
                        <td className="p-3 font-bold text-zinc-300">{row.id_servicio}</td>
                        <td className="p-3 font-semibold text-emerald-400">{row.caja_nap}</td>
                        <td className="p-3 font-mono text-amber-400">{row.precinto || "S/P"}</td>
                        <td className="p-3 font-mono text-zinc-400">{row.serial_onu || "S/N"}</td>
                        <td className="p-3 text-center">
                          <Badge variant="success" className="text-[10px]">
                            {row.estado || "Sincronizado"}
                          </Badge>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {totalHistoryPages > 1 && (
              <div className="flex items-center justify-between text-xs text-muted-foreground pt-2">
                <span>
                  Mostrando {paginatedHistory.length} de {filteredHistory.length} registros
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                    disabled={historyPage === 1}
                    className="h-7 px-2"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="font-bold text-foreground">
                    {historyPage} / {totalHistoryPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setHistoryPage((p) => Math.min(totalHistoryPages, p + 1))}
                    disabled={historyPage === totalHistoryPages}
                    className="h-7 px-2"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </TabsContent>

        {/* --- PESTAÑA 3: CONSULTAR ABONADO EN OZMAP --- */}
        <TabsContent value="quick-verify" className="space-y-4">
          <Card className="p-6 border-border/70 bg-card/60 space-y-6 max-w-3xl mx-auto">
            <div>
              <h3 className="text-lg font-black uppercase text-foreground flex items-center gap-2">
                <Search className="h-5 w-5 text-primary" />
                Consulta Inmediata de Abonado en OZmap
              </h3>
              <p className="text-xs text-muted-foreground mt-1">
                Escribe la Cédula, ID de Servicio o Código para consultar en tiempo real si el abonado está subido en el servidor de OZmap o en la bitácora histórica.
              </p>
            </div>

            <form onSubmit={handleQuickCheck} className="flex gap-2">
              <Input
                placeholder="Ej. 18740297 ó 54670 ó R-18740297-31685-54670"
                value={quickQuery}
                onChange={(e) => setQuickQuery(e.target.value)}
                className="text-xs bg-background/80 border-border/80 focus-visible:ring-primary"
              />
              <Button type="submit" disabled={isQuickChecking || !quickQuery.trim()} className="gap-2 font-bold">
                <Sparkles className={`h-4 w-4 ${isQuickChecking ? "animate-spin" : ""}`} />
                <span>{isQuickChecking ? "Consultando..." : "Consultar"}</span>
              </Button>
            </form>

            {quickResult && (
              <div
                className={`p-5 rounded-2xl border ${
                  quickResult.found
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                    : "bg-rose-500/10 border-rose-500/30 text-rose-300"
                }`}
              >
                <div className="flex items-center gap-3 mb-3">
                  {quickResult.found ? (
                    <CheckCircle2 className="h-6 w-6 text-emerald-400" />
                  ) : (
                    <XCircle className="h-6 w-6 text-rose-400" />
                  )}
                  <div>
                    <h4 className="font-black text-sm uppercase">
                      {quickResult.found
                        ? "Abonado Sincronizado en OZmap"
                        : "Abonado No Encontrado en OZmap"}
                    </h4>
                    <span className="text-xs opacity-80">Fuente: {quickResult.source}</span>
                  </div>
                </div>

                {quickResult.found ? (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs bg-black/40 p-4 rounded-xl border border-emerald-500/20">
                    <div>
                      <span className="text-zinc-400 text-[10px] block">Nombre / Abonado</span>
                      <strong className="text-white">{quickResult.nombres || "Abonado Registrado"}</strong>
                    </div>
                    <div>
                      <span className="text-zinc-400 text-[10px] block">Cédula</span>
                      <strong className="text-white font-mono">{quickResult.cedula}</strong>
                    </div>
                    <div>
                      <span className="text-zinc-400 text-[10px] block">ID Servicio</span>
                      <strong className="text-primary font-mono">{quickResult.id_servicio || "N/A"}</strong>
                    </div>
                    <div>
                      <span className="text-zinc-400 text-[10px] block">Caja NAP Asociada</span>
                      <strong className="text-emerald-400">{quickResult.caja || "Asignada"}</strong>
                    </div>
                    <div className="col-span-2">
                      <span className="text-zinc-400 text-[10px] block">Código OZmap Oficial</span>
                      <strong className="text-amber-400 font-mono">{quickResult.codigo_ozmap || "R-..."}</strong>
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-zinc-300 space-y-2">
                    <p>
                      El identificador <strong className="text-white font-mono">{quickResult.cedula}</strong> no figura
                      como abonado sincronizado en el servidor ni en las bitácoras recientes.
                    </p>
                    <p className="text-amber-400">
                      💡 Puedes cargarlo o reincorporarlo en el Módulo OZmap para cotejar su caja NAP y subirlo al servidor.
                    </p>
                  </div>
                )}
              </div>
            )}
          </Card>
        </TabsContent>
      </Tabs>

      {/* Modal de Detalle Completo de Abonado Descartado */}
      <Dialog open={isDetailModalOpen} onOpenChange={setIsDetailModalOpen}>
        <DialogContent className="max-w-2xl bg-zinc-950 border-border text-foreground">
          <DialogHeader>
            <DialogTitle className="text-lg font-black uppercase flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-primary" />
              Expediente de Abonado Descartado
            </DialogTitle>
          </DialogHeader>

          {selectedRecord && (
            <div className="space-y-4 py-2 text-xs">
              {/* Alerta de Estado */}
              <div
                className={`p-3 rounded-xl border flex items-center justify-between ${
                  selectedRecord.estado_ozmap === "verificado"
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                    : selectedRecord.estado_ozmap === "reincorporado"
                    ? "bg-blue-500/10 border-blue-500/30 text-blue-300"
                    : "bg-amber-500/10 border-amber-500/30 text-amber-300"
                }`}
              >
                <div className="flex items-center gap-2">
                  {selectedRecord.estado_ozmap === "verificado" ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                  ) : selectedRecord.estado_ozmap === "reincorporado" ? (
                    <Undo2 className="h-5 w-5 text-blue-400" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 text-amber-400" />
                  )}
                  <div>
                    <strong className="block text-sm">
                      {selectedRecord.estado_ozmap === "verificado"
                        ? "Verificado en Servidor OZmap"
                        : selectedRecord.estado_ozmap === "reincorporado"
                        ? "Reincorporado al Proceso Activo"
                        : "Pendiente / No Sincronizado en OZmap"}
                    </strong>
                    <span className="text-[11px] opacity-80">
                      {selectedRecord.detalles_verificacion?.observacion || "Sin auditoría previa"}
                    </span>
                  </div>
                </div>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleVerifySingle(selectedRecord)}
                  disabled={verifyingId === selectedRecord.id}
                  className="gap-1 text-xs border-current"
                >
                  <Sparkles className={`h-3.5 w-3.5 ${verifyingId === selectedRecord.id ? "animate-spin" : ""}`} />
                  <span>Verificar Ahora</span>
                </Button>
              </div>

              {/* Ficha Técnica */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 bg-muted/30 p-4 rounded-xl border border-border">
                <div>
                  <span className="text-muted-foreground text-[10px] block">Nombre Completo</span>
                  <strong className="text-foreground text-sm">{selectedRecord.nombres || "Sin Nombre"}</strong>
                </div>
                <div>
                  <span className="text-muted-foreground text-[10px] block">Cédula / RIF</span>
                  <strong className="font-mono text-foreground text-sm">{selectedRecord.cedula || "S/C"}</strong>
                </div>
                <div>
                  <span className="text-muted-foreground text-[10px] block">Código OZmap Oficial</span>
                  <strong className="font-mono text-primary text-sm">{selectedRecord.codigo_ozmap}</strong>
                </div>
                <div>
                  <span className="text-muted-foreground text-[10px] block">ID de Servicio</span>
                  <strong className="font-mono text-foreground">{selectedRecord.id_servicio || "S/S"}</strong>
                </div>
                <div>
                  <span className="text-muted-foreground text-[10px] block">ID de Usuario</span>
                  <strong className="font-mono text-foreground">{selectedRecord.id_usuario || "S/U"}</strong>
                </div>
                <div>
                  <span className="text-muted-foreground text-[10px] block">Serial ONU</span>
                  <strong className="font-mono text-foreground">{selectedRecord.serial_onu || "S/N"}</strong>
                </div>
                <div>
                  <span className="text-muted-foreground text-[10px] block">Precinto</span>
                  <strong className="font-mono text-amber-400">{selectedRecord.precinto || "Sin Precinto"}</strong>
                </div>
                <div>
                  <span className="text-muted-foreground text-[10px] block">Caja NAP Original (WhatsApp)</span>
                  <strong className="text-foreground">{selectedRecord.caja_nap || "S/C"}</strong>
                </div>
                <div>
                  <span className="text-muted-foreground text-[10px] block">Caja NAP Oficial Asignada</span>
                  <strong className="text-emerald-400">{selectedRecord.caja_oficial || "Pendiente"}</strong>
                </div>
              </div>

              {/* Auditoría del Descarte */}
              <div className="bg-muted/30 p-4 rounded-xl border border-border space-y-2">
                <span className="font-bold text-foreground text-xs uppercase block text-muted-foreground">
                  Información del Descarte
                </span>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-muted-foreground text-[10px] block">Fecha y Hora</span>
                    <strong className="text-foreground">
                      {selectedRecord.fecha_descarte} a las {selectedRecord.hora_descarte} hrs
                    </strong>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[10px] block">Módulo de Origen</span>
                    <strong className="text-foreground">{selectedRecord.origen_paso}</strong>
                  </div>
                  <div className="col-span-2">
                    <span className="text-muted-foreground text-[10px] block">Motivo Registrado</span>
                    <strong className="text-rose-400">{selectedRecord.motivo_descarte}</strong>
                  </div>
                </div>
              </div>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            {selectedRecord && (
              <>
                <Button
                  variant="outline"
                  onClick={() => {
                    handleRestoreClient(selectedRecord);
                    setIsDetailModalOpen(false);
                  }}
                  className="gap-2 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20"
                >
                  <Undo2 className="h-4 w-4" />
                  <span>Reincorporar al Proceso</span>
                </Button>

                <Button
                  variant="ghost"
                  onClick={() => {
                    handleDeletePermanent(selectedRecord);
                    setIsDetailModalOpen(false);
                  }}
                  className="text-rose-400 hover:bg-rose-500/20"
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  <span>Eliminar Definitivo</span>
                </Button>
              </>
            )}
            <Button variant="secondary" onClick={() => setIsDetailModalOpen(false)}>
              Cerrar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
