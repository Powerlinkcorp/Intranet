"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Activity,
  Plus,
  Search,
  Filter,
  BarChart3,
  ExternalLink,
  Zap,
  MapPin,
  FileText,
  User,
  Eye,
  RefreshCw,
  Clock,
  CheckCircle2,
  Check,
  ChevronDown,
  Radio,
  Copy,
  Download,
  Settings,
  AlertTriangle,
  Wifi,
  MessageSquare,
  Sparkles,
  Trash2,
  Sliders,
  Palette,
  X,
  Send,
} from "lucide-react";
import * as XLSX from "xlsx";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

// 96 Eventos históricos reales
import historicalEventsData from "@/data/network_events_history.json";

export type EventEstado = "abierto" | "en_seguimiento" | "solventado";
export type EventCausa = "Falla de proveedor" | "Falla eléctrica" | "Falla interna" | "Actividad" | string;

export interface TicketUpdate {
  id: string;
  timestamp: string;
  hora: string;
  autor: string;
  mensaje: string;
}

export interface NetworkEvent {
  id: string;
  date: string;
  dateRaw?: string;
  anio?: number;
  mes?: number;
  diaSemana?: string;
  causa: EventCausa;
  proveedor?: string;
  lugar: string;
  personal: string;
  motivo: string;
  horaReporte?: string;
  horaSolucion?: string;
  duracion?: string;
  duracionMinutos?: number;
  reporte: string;
  accionTomada?: string;
  causaRaiz?: string;
  estado?: EventEstado;
  updates?: TicketUpdate[];
  // Campos específicos
  fuenteEnergia?: string;
  estadoEnergia?: string;
  autonomiaEstimada?: string;
  ticketProveedor?: string;
  enlaceAfectado?: string;
  equiposAfectados?: string;
  clientesAfectados?: string;
  tipoActividad?: string;
  impactoServicio?: string;
  ventanaFinEstimada?: string;
  cuadrillaEnSitio?: string;
  ticketCorpoelec?: string;
  moduloPuerto?: string;
  accionRequerida?: string;
  customFields?: { id: string; label: string; value: string; icon?: string }[];
  createdAt?: string;
}

export interface ReportFieldDefinition {
  id: string;
  label: string;
  icon?: string;
  type: "text" | "select";
  options?: string[];
  placeholder?: string;
  required?: boolean;
  enabled: boolean;
  isCustom?: boolean;
}

export interface ReportTemplateConfig {
  causa: string;
  title: string;
  icon: string;
  colorTheme: "blue" | "amber" | "rose" | "emerald";
  fields: ReportFieldDefinition[];
}

export interface CatalogsState {
  hubs: string[];
  proveedores: string[];
  personal: string[];
  motivosPorCausa: Record<string, string[]>;
  fuentesEnergia: string[];
  estadosEnergia: string[];
}

const STORAGE_EVENTS_KEY = "reportgen_v1_network_events";
const STORAGE_CATALOGS_KEY = "reportgen_v1_network_catalogs";
const STORAGE_TEMPLATES_KEY = "reportgen_v1_report_templates";
const API_EVENTS_URL = "/operaciones/modulo_de_operaciones_migrado/v2/api/events.ashx";
const POWER_BI_URL = "https://app.powerbi.com/groups/e502575b-4581-45f0-8e85-64de9812c2c8/reports/63f3c560-266a-4cc9-8868-bacbd2120726/4c5eb1dca071d9a505cb?experience=power-bi";

export const DEFAULT_REPORT_TEMPLATES: Record<string, ReportTemplateConfig> = {
  "Falla de proveedor": {
    causa: "Falla de proveedor",
    title: "REPORTE DE FALLA DE PROVEEDOR",
    icon: "🔴",
    colorTheme: "blue",
    fields: [
      {
        id: "proveedor",
        label: "Carrier / Proveedor",
        icon: "🏢",
        type: "select",
        options: [
          "360NET",
          "Goldata",
          "CANTV",
          "Inter",
          "Digitel",
          "Digitel el Valle",
          "CenturyLink",
          "Vtal",
          "CDN",
          "No aplica",
        ],
        enabled: true,
      },
      {
        id: "ticketProveedor",
        label: "Ticket Carrier",
        icon: "🎫",
        type: "text",
        placeholder: "Ej. INC-9941...",
        enabled: true,
      },
      {
        id: "enlaceAfectado",
        label: "Enlace / Servicio Afectado",
        icon: "🌐",
        type: "select",
        options: [
          "Tránsito IP Principal (10G)",
          "Enlace de Respaldo",
          "Salida Internacional",
          "BGP Peering",
          "VLAN Transporte",
          "No especificado",
        ],
        enabled: true,
      },
      {
        id: "impactoServicio",
        label: "Impacto en el Tráfico",
        icon: "⚠️",
        type: "select",
        options: [
          "Pérdida de Paquetes (Packet Loss)",
          "Latencia Elevada / Jitter",
          "Corte Total de Enlace",
          "Flapping / Caídas Intermitentes",
        ],
        enabled: true,
      },
    ],
  },
  "Falla eléctrica": {
    causa: "Falla eléctrica",
    title: "REPORTE DE FALLA ELÉCTRICA",
    icon: "⚡",
    colorTheme: "amber",
    fields: [
      {
        id: "fuenteEnergia",
        label: "Fuente Eléctrica",
        icon: "🔌",
        type: "select",
        options: [
          "Corpoelec / Red Comercial",
          "Generador / Planta Eléctrica",
          "Sistema UPS / Baterías",
        ],
        enabled: true,
      },
      {
        id: "estadoEnergia",
        label: "Estado Energético",
        icon: "🔋",
        type: "select",
        options: [
          "Sin energía comercial (Operando con Planta)",
          "Sin energía comercial (Bajo UPS / Baterías)",
          "Corte Eléctrico General",
          "Energía Restablecida (Normal)",
        ],
        enabled: true,
      },
      {
        id: "autonomiaEstimada",
        label: "Autonomía Estimada",
        icon: "⏳",
        type: "text",
        placeholder: "Ej. 8 horas de combustible / 4h en baterías...",
        enabled: true,
      },
      {
        id: "ticketCorpoelec",
        label: "Reporte / Cuadrilla Corpoelec",
        icon: "⚡",
        type: "text",
        placeholder: "Ej. Reporte #48123 / Cuadrilla en sitio...",
        enabled: true,
      },
    ],
  },
  "Falla interna": {
    causa: "Falla interna",
    title: "REPORTE DE FALLA INTERNA",
    icon: "🔥",
    colorTheme: "rose",
    fields: [
      {
        id: "equiposAfectados",
        label: "Equipos Afectados",
        icon: "🔧",
        type: "select",
        options: [
          "OLT Huawei",
          "OLT ZTE",
          "Switch Core",
          "Mikrotik BGP",
          "Servidores DNS/DHCP",
          "Banco de Baterías",
          "Rectificador",
        ],
        enabled: true,
      },
      {
        id: "moduloPuerto",
        label: "Módulo / Puerto / Tarjeta",
        icon: "🔌",
        type: "text",
        placeholder: "Ej. SFP+ Slot 2 / GE 0/1/4 / PON 8...",
        enabled: true,
      },
      {
        id: "accionRequerida",
        label: "Acción en Curso",
        icon: "🛠️",
        type: "select",
        options: [
          "Revisión física en sitio",
          "Reemplazo de módulo SFP",
          "Reinicio controlado de hardware",
          "Corrección de configuración / VLAN",
          "Revisión de enlaces de fibra óptica",
        ],
        enabled: true,
      },
    ],
  },
  "Actividad": {
    causa: "Actividad",
    title: "REPORTE DE ACTIVIDAD PROGRAMADA",
    icon: "📋",
    colorTheme: "emerald",
    fields: [
      {
        id: "tipoActividad",
        label: "Tipo de Actividad",
        icon: "🛠️",
        type: "select",
        options: [
          "Mantenimiento Preventivo",
          "Migración de Fibra / Servicios",
          "Ampliación de Capacidad / Nodos",
          "Actualización de Firmware / Core",
          "Tendido y Empalme de Troncal",
          "Instalación de Nuevo Equipamiento",
        ],
        enabled: true,
      },
      {
        id: "ventanaFinEstimada",
        label: "Ventana / Hora Fin Estimada",
        icon: "⏱️",
        type: "text",
        placeholder: "Ej. 04:00 AM (Duración aprox: 3 horas)",
        enabled: true,
      },
      {
        id: "impactoServicio",
        label: "Impacto Estimado en Servicio",
        icon: "⚠️",
        type: "select",
        options: [
          "Sin impacto / Tráfico protegido por respaldo",
          "Degradación o intermitencia leve",
          "Corte total de servicio programado (Ventana nocturna)",
        ],
        enabled: true,
      },
      {
        id: "cuadrillaEnSitio",
        label: "Cuadrilla / Técnicos en Sitio",
        icon: "👷",
        type: "text",
        placeholder: "Ej. Cuadrilla Planta Externa / Dixon Iglesias",
        enabled: true,
      },
    ],
  },
};

const DEFAULT_CATALOGS: CatalogsState = {
  hubs: [
    "Hub CMDP",
    "Hub San Jose",
    "Hub Macarena",
    "Hub El Paraiso",
    "Hub Propatria",
    "Hub Retiro",
    "Hub Tibisay",
    "Hub Valle",
    "Hub Cumbre Rojas",
    "Hub tejerias",
    "C.C La Colina",
    "Data center",
    "Servidores",
    "Mikrotik 360net",
    "SW Huawei",
    "Hub Vtal",
    "No aplica",
  ],
  proveedores: [
    "360NET",
    "Goldata",
    "CANTV",
    "Inter",
    "Digitel",
    "Digitel el Valle",
    "CenturyLink",
    "Vtal",
    "CDN",
    "No aplica",
  ],
  personal: [
    "Dixon Iglesias",
    "Ivan Camacho",
    "Brando Carrero",
    "Rayner Revette",
    "Haggyn Subero",
    "Luis Augusto",
    "Operaciones",
    "Todos",
  ],
  motivosPorCausa: {
    "Falla de proveedor": [
      "Packet Loss",
      "Caída de enlace",
      "Corte de fibra carrier",
      "Degradación / Latencia",
      "Problemas de BGP / Enrutamiento",
      "Falla general de proveedor",
    ],
    "Falla eléctrica": [
      "Sin energía comercial (Corpoelec)",
      "Operando con Planta Eléctrica",
      "Bajo UPS / Baterías",
      "Pico de voltaje / Sobretensión",
      "Falla de transfer automático",
      "Falla de planta eléctrica",
      "Baterías descargadas / Baja autonomía",
      "Electrica",
    ],
    "Falla interna": [
      "Corte de fibra",
      "Falla Hardware",
      "Falla Software",
      "Conexion",
      "Inhibición de OLT / Mikrotik",
      "Temperatura",
      "Falla general",
      "Correccion de bugs",
      "Camaras",
      "vpn",
    ],
    Actividad: [
      "Actualizacion fisica",
      "Actualizacion de software",
      "Mantenimiento",
      "Instalacion de equipos",
      "Migracion fisica",
      "Correccion de bugs",
      "Pruebas de enlace",
      "Revision preventiva",
    ],
  },
  fuentesEnergia: [
    "Corpoelec",
    "Generador Propio / Planta",
    "Sistema UPS / Baterías",
    "Solar / Híbrido",
    "No aplica",
  ],
  estadosEnergia: [
    "Sin energía comercial (Operando con Planta)",
    "Sin energía comercial (Bajo UPS / Baterías)",
    "Corte Eléctrico General",
    "Energía Restablecida (Normal)",
  ],
};

// --- Helpers de Tiempo y Formato ---
function getNowTimeStr(): string {
  const now = new Date();
  let hours = now.getHours();
  const minutes = now.getMinutes();
  const ampm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12;
  hours = hours ? hours : 12;
  const minsStr = minutes < 10 ? "0" + minutes : String(minutes);
  return `${hours}:${minsStr} ${ampm}`;
}

function parseTimeStrToMinutes(str?: string): number | null {
  if (!str) return null;
  const cleaned = str.trim().toLowerCase();
  const match = cleaned.match(/(\d{1,2}):(\d{2})\s*(am|pm)?/);
  if (!match) return null;
  let hours = parseInt(match[1], 10);
  const minutes = parseInt(match[2], 10);
  const modifier = match[3];

  if (modifier === "pm" && hours < 12) hours += 12;
  if (modifier === "am" && hours === 12) hours = 0;

  return hours * 60 + minutes;
}

function calculateDuration(startStr?: string, endStr?: string): { minutes: number; text: string } {
  const m1 = parseTimeStrToMinutes(startStr);
  const m2 = parseTimeStrToMinutes(endStr);
  if (m1 === null || m2 === null) return { minutes: 0, text: "" };
  let diff = m2 - m1;
  if (diff < 0) diff += 24 * 60; // Cruce de medianoche
  const hrs = Math.floor(diff / 60);
  const mins = diff % 60;
  let text = "";
  if (hrs > 0 && mins > 0) text = `${hrs}h ${mins}m`;
  else if (hrs > 0) text = `${hrs}h`;
  else text = `${mins}m`;
  return { minutes: diff, text };
}

function computeActiveTime(startStr?: string): string {
  const nowStr = getNowTimeStr();
  const res = calculateDuration(startStr, nowStr);
  return res.text || "Recién iniciado";
}

// Parsea cualquier texto de duración a minutos enteros numéricos (ej. "1h 30m" -> 90, "45m" -> 45)
function parseDurationToMinutes(str?: string): number {
  if (!str) return 0;
  const s = str.trim().toLowerCase();
  if (/^\d+$/.test(s)) return parseInt(s, 10);
  
  let totalMinutes = 0;
  const hMatch = s.match(/(\d+)\s*(?:h|hr|hrs|hora|horas)/);
  const mMatch = s.match(/(\d+)\s*(?:m|min|mins|minuto|minutos)/);
  
  if (hMatch) totalMinutes += parseInt(hMatch[1], 10) * 60;
  if (mMatch) totalMinutes += parseInt(mMatch[1], 10);
  
  if (totalMinutes > 0) return totalMinutes;
  
  const timeMatch = s.match(/^(\d{1,2}):(\d{2})$/);
  if (timeMatch) {
    return parseInt(timeMatch[1], 10) * 60 + parseInt(timeMatch[2], 10);
  }
  
  return 0;
}

// Obtiene la duración exacta en minutos garantizada de cualquier evento
function getEventDurationMinutes(e: { duracionMinutos?: number; horaReporte?: string; horaSolucion?: string; duracion?: string }): number {
  if (typeof e.duracionMinutos === "number" && e.duracionMinutos > 0) {
    return Math.round(e.duracionMinutos);
  }
  if (e.horaReporte && e.horaSolucion) {
    const calc = calculateDuration(e.horaReporte, e.horaSolucion);
    if (calc.minutes > 0) return calc.minutes;
  }
  if (e.duracion) {
    const parsed = parseDurationToMinutes(e.duracion);
    if (parsed > 0) return parsed;
  }
  return 0;
}

// Extrae componentes de fecha plana para alimentar Power BI
function extractDateParts(dateStr?: string): { anio: number; mes: number; diaSemana: string } {
  if (!dateStr) {
    const now = new Date();
    return {
      anio: now.getFullYear(),
      mes: now.getMonth() + 1,
      diaSemana: ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"][now.getDay()],
    };
  }
  const parts = dateStr.split("-");
  if (parts.length === 3) {
    const y = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10);
    const d = parseInt(parts[2], 10);
    const dt = new Date(y, m - 1, d);
    return {
      anio: y,
      mes: m,
      diaSemana: ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"][dt.getDay()],
    };
  }
  return { anio: 2026, mes: 1, diaSemana: "Lunes" };
}

// Semáforo de criticidad y SLA por tiempo transcurrido en el seguidor
function getActiveTimeBadge(horaReporte?: string) {
  const dur = calculateDuration(horaReporte, getNowTimeStr());
  const mins = dur.minutes;
  if (mins < 30) {
    return {
      text: dur.text || "< 30m",
      classes: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
      dot: "bg-emerald-400",
      label: "Reciente",
    };
  } else if (mins <= 120) {
    return {
      text: dur.text,
      classes: "bg-amber-500/15 text-amber-300 border-amber-500/30",
      dot: "bg-amber-400",
      label: "En progreso",
    };
  } else {
    return {
      text: dur.text,
      classes: "bg-rose-500/15 text-rose-400 border-rose-500/30 animate-pulse",
      dot: "bg-rose-500",
      label: "Prolongado (> 2h)",
    };
  }
}

// Abrir directamente en WhatsApp Web con texto pre-cargado
function openWhatsAppWebShare(text: string) {
  if (typeof window === "undefined") return;
  const url = `https://web.whatsapp.com/send?text=${encodeURIComponent(text)}`;
  window.open(url, "_blank");
}

// --- Componente Desplegable con Búsqueda Integrada por Escritura (Combobox) ---
interface SearchableComboboxProps {
  value: string;
  onChange: (value: string) => void;
  options: string[];
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}

export const SearchableCombobox: React.FC<SearchableComboboxProps> = ({
  value,
  onChange,
  options,
  placeholder = "Seleccionar o buscar...",
  className = "",
  disabled = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredOptions = useMemo(() => {
    const normQuery = query
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();

    if (!normQuery) return options;

    return options.filter((opt) => {
      const normOpt = opt
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase();
      return normOpt.includes(normQuery);
    });
  }, [options, query]);

  const hasExactMatch = useMemo(() => {
    if (!query.trim()) return true;
    const normQuery = query
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
    return options.some(
      (opt) =>
        opt
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .toLowerCase() === normQuery
    );
  }, [options, query]);

  const handleSelect = (option: string) => {
    onChange(option);
    setIsOpen(false);
    setQuery("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (filteredOptions.length > 0) {
        handleSelect(filteredOptions[0]);
      } else if (query.trim()) {
        handleSelect(query.trim());
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
      setQuery("");
      inputRef.current?.blur();
    } else if (e.key === "ArrowDown") {
      if (!isOpen) setIsOpen(true);
    }
  };

  return (
    <div ref={containerRef} className={`relative w-full ${className}`}>
      <div className="relative flex items-center">
        <input
          ref={inputRef}
          type="text"
          disabled={disabled}
          value={isOpen ? query : value || ""}
          placeholder={isOpen ? (value ? `Actual: ${value}` : "Escribe para filtrar (ej. tejeria)...") : placeholder}
          onFocus={() => {
            setIsOpen(true);
            setQuery("");
          }}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen) setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          className={`w-full rounded-xl border border-border bg-background px-3 py-1.5 ${value && !disabled ? "pr-14" : "pr-8"} text-xs font-semibold text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-text truncate transition-colors`}
        />
        {value && !disabled && (
          <button
            type="button"
            tabIndex={-1}
            onClick={(e) => {
              e.stopPropagation();
              onChange("");
              setQuery("");
            }}
            className="absolute right-7 text-muted-foreground hover:text-foreground p-0.5 rounded-full hover:bg-muted"
            title="Limpiar campo"
          >
            <X className="h-3 w-3" />
          </button>
        )}
        <button
          type="button"
          tabIndex={-1}
          onClick={() => {
            if (!isOpen) {
              inputRef.current?.focus();
              setIsOpen(true);
              setQuery("");
            } else {
              setIsOpen(false);
            }
          }}
          className="absolute right-2 text-muted-foreground hover:text-foreground p-0.5"
        >
          <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
        </button>
      </div>

      {isOpen && (
        <div className="absolute left-0 right-0 top-full mt-1 max-h-56 overflow-y-auto rounded-xl border border-border bg-popover/95 backdrop-blur-md shadow-2xl z-50 p-1 divide-y divide-border/20">
          {!hasExactMatch && query.trim().length > 0 && (
            <button
              type="button"
              onClick={() => handleSelect(query.trim())}
              className="w-full text-left px-3 py-2 rounded-lg text-xs font-semibold text-primary bg-primary/10 hover:bg-primary/20 flex items-center justify-between transition-colors mb-1"
            >
              <span>+ Usar valor: &ldquo;{query.trim()}&rdquo;</span>
            </button>
          )}

          {filteredOptions.length === 0 && hasExactMatch ? (
            <div className="p-3 text-center text-xs text-muted-foreground italic">
              No hay opciones disponibles
            </div>
          ) : filteredOptions.length === 0 && !hasExactMatch ? (
            <div className="p-2 text-center text-xs text-muted-foreground italic">
              Presiona Enter o haz clic arriba para usar &ldquo;{query.trim()}&rdquo;
            </div>
          ) : (
            filteredOptions.map((opt) => {
              const isSelected = opt === value;
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => handleSelect(opt)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium flex items-center justify-between transition-colors ${
                    isSelected
                      ? "bg-primary/15 text-primary font-bold"
                      : "hover:bg-muted/70 text-foreground"
                  }`}
                >
                  <span className="truncate">{opt}</span>
                  {isSelected && <Check className="h-3.5 w-3.5 text-primary shrink-0 ml-2" />}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};

export function EventsDashboardModule() {
  // --- Estados Principales ---
  const [events, setEvents] = useState<NetworkEvent[]>([]);
  const [catalogs, setCatalogs] = useState<CatalogsState>(DEFAULT_CATALOGS);
  const [activeTab, setActiveTab] = useState<"seguidor" | "presentacion" | "bitacora" | "catalogos">("seguidor");

  // Filtros
  const [filterCausa, setFilterCausa] = useState("all");
  const [filterEstado, setFilterEstado] = useState<"all" | "abierto" | "solventado">("all");
  const [filterLugar, setFilterLugar] = useState("all");
  const [filterMotivo, setFilterMotivo] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterPeriodo, setFilterPeriodo] = useState<"todos" | "hoy" | "ayer" | "semana" | "mes">("todos");
  const [selectedKpi, setSelectedKpi] = useState<"all" | "en_curso" | "actividad" | "falla_electrica" | "falla_proveedor" | "falla_interna">("all");

  const handleKpiCardClick = (kpi: "all" | "en_curso" | "actividad" | "falla_electrica" | "falla_proveedor" | "falla_interna") => {
    setSelectedKpi(kpi);
    if (kpi === "en_curso") {
      setActiveTab("seguidor");
      return;
    }

    if (activeTab === "seguidor" || activeTab === "catalogos") {
      setActiveTab("presentacion");
    }
    if (kpi === "all") {
      setFilterCausa("all");
      setFilterEstado("all");
      setFilterLugar("all");
      setFilterMotivo("all");
    } else if (kpi === "actividad") {
      setFilterCausa("Actividad");
      setFilterEstado("solventado");
      setFilterLugar("all");
      setFilterMotivo("all");
    } else if (kpi === "falla_electrica") {
      setFilterCausa("Falla eléctrica");
      setFilterEstado("solventado");
      setFilterLugar("all");
      setFilterMotivo("all");
    } else if (kpi === "falla_proveedor") {
      setFilterCausa("Falla de proveedor");
      setFilterEstado("solventado");
      setFilterLugar("all");
      setFilterMotivo("all");
    } else if (kpi === "falla_interna") {
      setFilterCausa("Falla interna");
      setFilterEstado("solventado");
      setFilterLugar("all");
      setFilterMotivo("all");
    }
  };

  // Modales
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [isClosingModalOpen, setIsClosingModalOpen] = useState(false);
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<NetworkEvent | null>(null);
  const [eventToClose, setEventToClose] = useState<NetworkEvent | null>(null);
  const [eventToUpdate, setEventToUpdate] = useState<NetworkEvent | null>(null);

  // Modal para agregar opción rápida a un desplegable
  const [quickOptionModal, setQuickOptionModal] = useState<{
    isOpen: boolean;
    catalogKey: keyof CatalogsState | "motivo";
    title: string;
    causaContext?: string;
  }>({ isOpen: false, catalogKey: "hubs", title: "" });
  const [newOptionValue, setNewOptionValue] = useState("");

  // Form State para Nuevo Evento / Ticket (todos vacíos por defecto para evitar confusión)
  const [formDate, setFormDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [formCausa, setFormCausa] = useState<EventCausa>("Falla eléctrica");
  const [formProveedor, setFormProveedor] = useState("");
  const [formLugar, setFormLugar] = useState("");
  const [formPersonal, setFormPersonal] = useState("");
  const [formMotivo, setFormMotivo] = useState("");
  const [formHoraReporte, setFormHoraReporte] = useState(() => getNowTimeStr());
  const [formHoraSolucion, setFormHoraSolucion] = useState("");
  const [formDuracion, setFormDuracion] = useState("");
  const [formReporte, setFormReporte] = useState("");
  const [formEstadoInicio, setFormEstadoInicio] = useState<EventEstado>("abierto");
  // Campos específicos
  const [formFuenteEnergia, setFormFuenteEnergia] = useState("");
  const [formEstadoEnergia, setFormEstadoEnergia] = useState("");
  const [formAutonomia, setFormAutonomia] = useState("");
  const [formTicketProveedor, setFormTicketProveedor] = useState("");
  const [formEquiposAfectados, setFormEquiposAfectados] = useState("");

  // --- Estados de Plantillas e Identidades Personalizables ---
  const [templates, setTemplates] = useState<Record<string, ReportTemplateConfig>>(DEFAULT_REPORT_TEMPLATES);
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false);
  const [, setEditingTemplateCausa] = useState<string>("Falla de proveedor");
  const [templateDraft, setTemplateDraft] = useState<ReportTemplateConfig | null>(null);

  // Valores dinámicos de los campos de la plantilla activa (vacíos por defecto)
  const [formFieldValues, setFormFieldValues] = useState<Record<string, string>>({});

  // Función para resetear completamente el formulario a blanco al abrir o guardar
  const resetCreateForm = () => {
    setFormDate(new Date().toISOString().slice(0, 10));
    setFormHoraReporte(getNowTimeStr());
    setFormCausa("Falla eléctrica");
    setFormLugar("");
    setFormMotivo("");
    setFormPersonal("");
    setFormReporte("");
    setFormFieldValues({});
    setCustomFieldsList([]);
    setFormProveedor("");
    setFormTicketProveedor("");
    setFormFuenteEnergia("");
    setFormEstadoEnergia("");
    setFormAutonomia("");
    setFormEquiposAfectados("");
    setFormHoraSolucion("");
    setFormDuracion("");
    setFormEstadoInicio("abierto");
    setIsReportManuallyEdited(false);
    setIsAddingCustomField(false);
    setNewCustomFieldLabel("");
    setNewCustomFieldValue("");
  };

  const setFieldValue = (fieldId: string, val: string) => {
    setFormFieldValues((prev) => ({ ...prev, [fieldId]: val }));
    setIsReportManuallyEdited(false);
    if (fieldId === "proveedor") setFormProveedor(val);
    if (fieldId === "ticketProveedor") setFormTicketProveedor(val);
    if (fieldId === "fuenteEnergia") setFormFuenteEnergia(val);
    if (fieldId === "estadoEnergia") setFormEstadoEnergia(val);
    if (fieldId === "autonomiaEstimada") setFormAutonomia(val);
    if (fieldId === "equiposAfectados") setFormEquiposAfectados(val);
  };

  // Campos dinámicos adicionales para este ticket
  const [customFieldsList, setCustomFieldsList] = useState<{ id: string; label: string; value: string; icon: string }[]>([]);
  const [isAddingCustomField, setIsAddingCustomField] = useState(false);
  const [newCustomFieldLabel, setNewCustomFieldLabel] = useState("");
  const [newCustomFieldValue, setNewCustomFieldValue] = useState("");
  const [newCustomFieldIcon] = useState("📌");
  const [saveCustomFieldAsPermanent, setSaveCustomFieldAsPermanent] = useState(false);

  // Para creación de nuevo campo permanente en el modal de plantillas
  const [newPermanentFieldLabel, setNewPermanentFieldLabel] = useState("");
  const [newPermanentFieldIcon, setNewPermanentFieldIcon] = useState("📌");
  const [newPermanentFieldType, setNewPermanentFieldType] = useState<"text" | "select">("text");
  const [newPermanentFieldOptions, setNewPermanentFieldOptions] = useState("");

  const handleRemoveCustomField = (id: string) => {
    setCustomFieldsList((prev) => prev.filter((cf) => cf.id !== id));
    setIsReportManuallyEdited(false);
  };

  const handleAddCustomFieldSubmit = () => {
    if (!newCustomFieldLabel.trim() || !newCustomFieldValue.trim()) {
      showToast("Ingresa el nombre y el valor del campo.", "error");
      return;
    }

    const newFieldObj = {
      id: "cf-" + Date.now(),
      label: newCustomFieldLabel.trim(),
      value: newCustomFieldValue.trim(),
      icon: newCustomFieldIcon || "📌",
    };
    setCustomFieldsList((prev) => [...prev, newFieldObj]);

    if (saveCustomFieldAsPermanent) {
      const currentConf = templates[formCausa] || DEFAULT_REPORT_TEMPLATES[formCausa];
      const permField: ReportFieldDefinition = {
        id: "perm-" + Date.now(),
        label: newCustomFieldLabel.trim(),
        icon: newCustomFieldIcon || "📌",
        type: "text",
        enabled: true,
        isCustom: true,
      };
      const updatedConf = {
        ...currentConf,
        fields: [...currentConf.fields, permField],
      };
      const updatedAll = {
        ...templates,
        [formCausa]: updatedConf,
      };
      setTemplates(updatedAll);
      try {
        localStorage.setItem(STORAGE_TEMPLATES_KEY, JSON.stringify(updatedAll));
      } catch (e) {
        console.error("Error updating templates", e);
      }
      showToast(`Campo añadido al reporte y guardado en la plantilla de ${formCausa}.`, "success");
    } else {
      showToast(`Campo añadido al reporte actual.`, "success");
    }

    setNewCustomFieldLabel("");
    setNewCustomFieldValue("");
    setIsAddingCustomField(false);
    setSaveCustomFieldAsPermanent(false);
    setIsReportManuallyEdited(false);
  };

  const openTemplateCustomizer = (causa: string) => {
    setEditingTemplateCausa(causa);
    const existing = templates[causa] || DEFAULT_REPORT_TEMPLATES[causa] || {
      causa,
      title: `REPORTE DE ${causa.toUpperCase()}`,
      icon: "🔴",
      colorTheme: "blue" as const,
      fields: [],
    };
    setTemplateDraft(JSON.parse(JSON.stringify(existing)));
    setIsTemplateModalOpen(true);
  };

  const handleSwitchTemplateCausa = (c: string) => {
    setEditingTemplateCausa(c);
    const target = templates[c] || DEFAULT_REPORT_TEMPLATES[c];
    setTemplateDraft(JSON.parse(JSON.stringify(target)));
  };

  const handleToggleField = (fieldId: string) => {
    if (!templateDraft) return;
    setTemplateDraft({
      ...templateDraft,
      fields: templateDraft.fields.map((f) =>
        f.id === fieldId ? { ...f, enabled: !f.enabled } : f
      ),
    });
  };

  const handleDeleteField = (fieldId: string) => {
    if (!templateDraft) return;
    setTemplateDraft({
      ...templateDraft,
      fields: templateDraft.fields.filter((f) => f.id !== fieldId),
    });
  };

  const handleAddPermanentField = () => {
    if (!templateDraft || !newPermanentFieldLabel.trim()) {
      showToast("Ingresa el nombre del campo.", "error");
      return;
    }
    const newField: ReportFieldDefinition = {
      id: "field_" + Date.now(),
      label: newPermanentFieldLabel.trim(),
      icon: newPermanentFieldIcon || "📌",
      type: newPermanentFieldType,
      options:
        newPermanentFieldType === "select"
          ? newPermanentFieldOptions.split(",").map((s) => s.trim()).filter(Boolean)
          : undefined,
      enabled: true,
      isCustom: true,
    };
    setTemplateDraft({
      ...templateDraft,
      fields: [...templateDraft.fields, newField],
    });
    setNewPermanentFieldLabel("");
    setNewPermanentFieldOptions("");
    showToast(`Campo "${newField.label}" añadido a la plantilla.`, "success");
  };

  const handleSaveTemplateDraft = () => {
    if (!templateDraft) return;
    const updated = {
      ...templates,
      [templateDraft.causa]: templateDraft,
    };
    setTemplates(updated);
    try {
      localStorage.setItem(STORAGE_TEMPLATES_KEY, JSON.stringify(updated));
    } catch (e) {
      console.error("Error saving templates", e);
    }
    setIsTemplateModalOpen(false);
    showToast(`Plantilla de "${templateDraft.causa}" guardada con éxito.`, "success");
  };

  const handleResetTemplateDefaults = () => {
    if (!templateDraft) return;
    const defaultConf = DEFAULT_REPORT_TEMPLATES[templateDraft.causa];
    if (defaultConf) {
      setTemplateDraft(JSON.parse(JSON.stringify(defaultConf)));
      showToast(`Plantilla restaurada a los valores predeterminados.`, "info");
    }
  };

  // Estado para editor de reporte WhatsApp editable en vivo
  const [customReportText, setCustomReportText] = useState("");
  const [isReportManuallyEdited, setIsReportManuallyEdited] = useState(false);

  // Form State para Cierre / Finalización
  const [closeHoraSolucion, setCloseHoraSolucion] = useState("");
  const [closeAccionTomada, setCloseAccionTomada] = useState("");
  const [closeCausaRaiz, setCloseCausaRaiz] = useState("");
  const [closeCalculatedDuration, setCloseCalculatedDuration] = useState("");
  const [closeReportText, setCloseReportText] = useState("");

  // Form State para Seguimiento / Update
  const [updateNota, setUpdateNota] = useState("");
  const [updateAccionEnCurso, setUpdateAccionEnCurso] = useState("Revisión física en sitio");
  const [updateEta, setUpdateEta] = useState("");
  const [updateAutor, setUpdateAutor] = useState("Dixon Iglesias");
  const [updateReportText, setUpdateReportText] = useState("");

  // Toast / Status Message
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);
  const [isApiModalOpen, setIsApiModalOpen] = useState(false);

  const showToast = (text: string, type: "success" | "error" | "info" = "info") => {
    setStatusMessage({ text, type });
    setTimeout(() => setStatusMessage(null), 3500);
  };

  // --- Cargar Datos Iniciales ---
  useEffect(() => {
    // 1. Cargar Catálogos
    try {
      const rawCat = localStorage.getItem(STORAGE_CATALOGS_KEY);
      if (rawCat) {
        const parsed = JSON.parse(rawCat);
        setCatalogs({
          ...DEFAULT_CATALOGS,
          ...parsed,
          motivosPorCausa: {
            ...DEFAULT_CATALOGS.motivosPorCausa,
            ...(parsed.motivosPorCausa || {}),
          },
        });
      } else {
        localStorage.setItem(STORAGE_CATALOGS_KEY, JSON.stringify(DEFAULT_CATALOGS));
      }
    } catch (e) {
      console.error("Error loading catalogs", e);
    }

    // 1.1 Cargar Plantillas Personalizadas
    try {
      const rawTemplates = localStorage.getItem(STORAGE_TEMPLATES_KEY);
      if (rawTemplates) {
        const parsed = JSON.parse(rawTemplates);
        setTemplates({
          ...DEFAULT_REPORT_TEMPLATES,
          ...parsed,
        });
      } else {
        localStorage.setItem(STORAGE_TEMPLATES_KEY, JSON.stringify(DEFAULT_REPORT_TEMPLATES));
      }
    } catch (e) {
      console.error("Error loading templates", e);
    }

    // 2. Cargar Eventos desde API o LocalStorage / Históricos
    const normalizeEvent = (e: NetworkEvent): NetworkEvent => {
      const durMin = getEventDurationMinutes(e);
      const dateParts = extractDateParts(e.date || e.dateRaw);
      return {
        ...e,
        duracionMinutos: durMin,
        anio: e.anio || dateParts.anio,
        mes: e.mes || dateParts.mes,
        diaSemana: e.diaSemana || dateParts.diaSemana,
        estado: e.id?.startsWith("evt-") ? ("solventado" as EventEstado) : (e.estado || "solventado"),
      };
    };

    const initEvents = async () => {
      let loadedFromApi = false;
      try {
        const res = await fetch(API_EVENTS_URL);
        if (res.ok) {
          const serverEvents = await res.json();
          if (Array.isArray(serverEvents) && serverEvents.length > 0) {
            const normalized = serverEvents.map(normalizeEvent);
            setEvents(normalized);
            localStorage.setItem(STORAGE_EVENTS_KEY, JSON.stringify(normalized));
            loadedFromApi = true;
          }
        }
      } catch {
        // Fallback a localStorage si API no responde
      }

      if (loadedFromApi) return;

      try {
        const rawEvents = localStorage.getItem(STORAGE_EVENTS_KEY);
        if (rawEvents) {
          const parsed = JSON.parse(rawEvents);
          if (Array.isArray(parsed) && parsed.length > 0) {
            const normalized = parsed.map(normalizeEvent);
            setEvents(normalized);
            return;
          }
        }
      } catch (e) {
        console.error("Error loading events from storage", e);
      }

      // Inicializar con los históricos
      if (Array.isArray(historicalEventsData) && historicalEventsData.length > 0) {
        const initialized = (historicalEventsData as NetworkEvent[]).map((e) =>
          normalizeEvent({ ...e, estado: "solventado" as EventEstado })
        );
        setEvents(initialized);
        localStorage.setItem(STORAGE_EVENTS_KEY, JSON.stringify(initialized));
      }
    };

    initEvents();
  }, []);

  const saveEvents = async (updated: NetworkEvent[]) => {
    setEvents(updated);
    try {
      localStorage.setItem(STORAGE_EVENTS_KEY, JSON.stringify(updated));
    } catch (e) {
      console.warn("Error guardando eventos:", e);
    }

    // Sincronizar en tiempo real con la API del servidor IIS para alimentar Power BI
    try {
      await fetch(API_EVENTS_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updated),
      });
    } catch (e) {
      console.warn("Error sincronizando eventos con el servidor API:", e);
    }
  };

  const saveCatalogs = (updated: CatalogsState) => {
    setCatalogs(updated);
    try {
      localStorage.setItem(STORAGE_CATALOGS_KEY, JSON.stringify(updated));
    } catch (e) {
      console.warn("Error guardando catálogos:", e);
    }
  };

  // --- Limpiar Motivo si el seleccionado no pertenece a la nueva Causa (sin forzar preseleccionados) ---
  useEffect(() => {
    const list = catalogs.motivosPorCausa[formCausa] || [];
    if (formMotivo && list.length > 0 && !list.includes(formMotivo)) {
      setFormMotivo("");
    }
  }, [formCausa, catalogs, formMotivo]);

  // --- Generador de Reporte WhatsApp de Apertura en Vivo Basado en Plantillas ---
  const generatedWhatsAppApertura = useMemo(() => {
    const currentTemplate = templates[formCausa] || DEFAULT_REPORT_TEMPLATES[formCausa] || {
      causa: formCausa,
      title: `REPORTE DE ${formCausa.toUpperCase()}`,
      icon: "🔴",
      colorTheme: "blue" as const,
      fields: [],
    };

    let text = `${currentTemplate.icon} *${currentTemplate.title}*\n`;
    text += `📅 *Fecha:* ${formDate}\n`;
    text += `⏱️ *Hora Inicio / Detección:* ${formHoraReporte}\n`;
    if (formLugar && formLugar.trim()) {
      text += `📍 *Ubicación / Hub:* ${formLugar.trim()}\n`;
    }

    // Campos especializados activos que tengan valor
    currentTemplate.fields.forEach((field) => {
      if (!field.enabled) return;
      const val = formFieldValues[field.id];
      if (val && val.trim() && val !== "No aplica") {
        text += `${field.icon || "🔹"} *${field.label}:* ${val.trim()}\n`;
      }
    });

    if (formMotivo && formMotivo.trim()) {
      text += `📝 *Motivo:* ${formMotivo.trim()}\n`;
    }
    if (formPersonal && formPersonal.trim()) {
      text += `👤 *Personal Responsable:* ${formPersonal.trim()}\n`;
    }

    // Campos dinámicos adicionales añadidos al vuelo
    customFieldsList.forEach((cf) => {
      if (cf.value && cf.value.trim()) {
        text += `${cf.icon || "📌"} *${cf.label}:* ${cf.value.trim()}\n`;
      }
    });

    if (formReporte && formReporte.trim()) {
      text += `\n📋 *Diagnóstico / Detalle:*\n${formReporte.trim()}`;
    }

    return text;
  }, [
    templates,
    formCausa,
    formDate,
    formHoraReporte,
    formLugar,
    formMotivo,
    formPersonal,
    formFieldValues,
    customFieldsList,
    formReporte,
  ]);

  // Sincronizar texto de reporte en el modal a menos que se haya editado manualmente
  useEffect(() => {
    if (!isReportManuallyEdited) {
      setCustomReportText(generatedWhatsAppApertura);
    }
  }, [generatedWhatsAppApertura, isReportManuallyEdited]);

  // --- Manejo de Apertura de Ticket / Evento ---
  const handleCreateEvent = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formLugar.trim()) {
      showToast("Por favor selecciona o ingresa el Hub / Lugar.", "error");
      return;
    }
    if (!formMotivo.trim()) {
      showToast("Por favor selecciona o ingresa el Motivo de la eventualidad.", "error");
      return;
    }

    const durationInfo =
      formHoraReporte && formHoraSolucion
        ? calculateDuration(formHoraReporte, formHoraSolucion)
        : { minutes: parseDurationToMinutes(formDuracion), text: formDuracion };
    const dateParts = extractDateParts(formDate);

    const newEvt: NetworkEvent = {
      id: "TKT-" + new Date().toISOString().slice(0, 10).replace(/-/g, "") + "-" + Math.floor(100 + Math.random() * 900),
      date: formDate,
      dateRaw: formDate,
      anio: dateParts.anio,
      mes: dateParts.mes,
      diaSemana: dateParts.diaSemana,
      causa: formCausa,
      proveedor: formCausa === "Falla de proveedor" ? (formFieldValues["proveedor"] || formProveedor) : "No aplica",
      lugar: formLugar,
      personal: formPersonal || "Guardia en turno",
      motivo: formMotivo,
      horaReporte: formHoraReporte,
      horaSolucion: formEstadoInicio === "solventado" ? formHoraSolucion || getNowTimeStr() : "",
      duracion: formEstadoInicio === "solventado" ? durationInfo.text : "",
      duracionMinutos: formEstadoInicio === "solventado" ? durationInfo.minutes : 0,
      reporte: customReportText || generatedWhatsAppApertura,
      estado: formEstadoInicio,
      fuenteEnergia: formFieldValues["fuenteEnergia"] || formFuenteEnergia,
      estadoEnergia: formFieldValues["estadoEnergia"] || formEstadoEnergia,
      autonomiaEstimada: formFieldValues["autonomiaEstimada"] || formAutonomia,
      ticketProveedor: formFieldValues["ticketProveedor"] || formTicketProveedor,
      equiposAfectados: formFieldValues["equiposAfectados"] || formEquiposAfectados,
      enlaceAfectado: formFieldValues["enlaceAfectado"],
      tipoActividad: formFieldValues["tipoActividad"],
      impactoServicio: formFieldValues["impactoServicio"],
      ventanaFinEstimada: formFieldValues["ventanaFinEstimada"],
      cuadrillaEnSitio: formFieldValues["cuadrillaEnSitio"],
      ticketCorpoelec: formFieldValues["ticketCorpoelec"],
      moduloPuerto: formFieldValues["moduloPuerto"],
      accionRequerida: formFieldValues["accionRequerida"],
      customFields: customFieldsList,
      updates: [],
      createdAt: new Date().toISOString(),
    };

    const updated = [newEvt, ...events];
    saveEvents(updated);

    // Si se abrió en curso, cambiar a la pestaña seguidor
    if (formEstadoInicio === "abierto") {
      setActiveTab("seguidor");
    }

    setIsNewModalOpen(false);
    resetCreateForm();
    showToast(`✅ Evento registrado con éxito (${newEvt.id} - ${formEstadoInicio.toUpperCase()}).`, "success");
  };

  // Helper para armar el texto WhatsApp de Cierre
  const buildClosingWhatsApp = (
    evt: NetworkEvent,
    solucionHora: string,
    duracionTexto: string,
    accion: string,
    causaR: string
  ) => {
    let msg = `🟢 *REPORTE DE INCIDENCIA SOLVENTADA*\n`;
    msg += `🆔 *Ticket:* ${evt.id}\n`;
    msg += `📅 *Fecha:* ${evt.date || evt.dateRaw}\n`;
    msg += `📍 *Ubicación / Hub:* ${evt.lugar}\n`;
    msg += `📋 *Tipo / Causa:* ${evt.causa} (${evt.motivo})\n`;
    if (evt.proveedor && evt.proveedor !== "No aplica") msg += `🏢 *Carrier / Proveedor:* ${evt.proveedor}\n`;
    msg += `⏱️ *Horario:* ${evt.horaReporte || "—"} → ${solucionHora}\n`;
    msg += `⏳ *Duración Total:* ${duracionTexto}\n`;
    msg += `👤 *Personal Responsable:* ${evt.personal || "Operaciones"}\n`;
    if (causaR && causaR.trim()) msg += `🔍 *Causa Raíz (RCA):* ${causaR.trim()}\n`;
    msg += `\n✅ *Acción Tomada / Solución:*\n${accion.trim() || "Servicio normalizado y verificado operando al 100%."}`;
    return msg;
  };

  // Helper para armar el texto WhatsApp de Novedad / Seguimiento
  const buildUpdateWhatsApp = (
    evt: NetworkEvent,
    actHora: string,
    autor: string,
    nota: string,
    accionCurso: string,
    etaVal: string
  ) => {
    let msg = `📢 *NOVEDAD / SEGUIMIENTO DE INCIDENCIA*\n`;
    msg += `🆔 *Ticket:* ${evt.id}\n`;
    msg += `📍 *Ubicación / Hub:* ${evt.lugar}\n`;
    msg += `📋 *Incidencia:* ${evt.causa} (${evt.motivo})\n`;
    if (evt.proveedor && evt.proveedor !== "No aplica") msg += `🏢 *Carrier:* ${evt.proveedor}\n`;
    msg += `⏱️ *Tiempo en Curso:* ${computeActiveTime(evt.horaReporte)}\n`;
    msg += `🕒 *Hora Actualización:* ${actHora}\n`;
    msg += `👤 *Informó:* ${autor}\n`;
    if (accionCurso && accionCurso.trim()) msg += `🛠️ *Acción en Curso:* ${accionCurso.trim()}\n`;
    if (etaVal && etaVal.trim()) msg += `⏳ *ETA Estimado de Solución:* ${etaVal.trim()}\n`;
    msg += `\n📝 *Avance Reportado:*\n${nota.trim() || "[Detalle técnico del avance...]"}`;
    return msg;
  };

  // --- Modal de Finalización / Cierre ---
  const openClosingModal = (evt: NetworkEvent) => {
    setEventToClose(evt);
    const nowTime = getNowTimeStr();
    setCloseHoraSolucion(nowTime);
    const accionDef = evt.accionTomada || "Servicio normalizado y verificado operando al 100%.";
    setCloseAccionTomada(accionDef);
    setCloseCausaRaiz(evt.causaRaiz || "");

    const dur = calculateDuration(evt.horaReporte, nowTime);
    setCloseCalculatedDuration(dur.text || "—");

    const msg = buildClosingWhatsApp(evt, nowTime, dur.text || "—", accionDef, evt.causaRaiz || "");
    setCloseReportText(msg);

    setIsClosingModalOpen(true);
  };

  const handleConfirmClose = (e: React.FormEvent) => {
    e.preventDefault();
    if (!eventToClose) return;

    const dur = calculateDuration(eventToClose.horaReporte, closeHoraSolucion);
    const dateParts = extractDateParts(eventToClose.date || eventToClose.dateRaw);

    const updatedEvents = events.map((ev) => {
      if (ev.id === eventToClose.id) {
        return {
          ...ev,
          estado: "solventado" as EventEstado,
          horaSolucion: closeHoraSolucion,
          duracion: dur.text || ev.duracion || "Solventado",
          duracionMinutos: dur.minutes || getEventDurationMinutes(ev),
          accionTomada: closeAccionTomada.trim(),
          causaRaiz: closeCausaRaiz.trim(),
          anio: ev.anio || dateParts.anio,
          mes: ev.mes || dateParts.mes,
          diaSemana: ev.diaSemana || dateParts.diaSemana,
          reporte: closeReportText || ev.reporte,
          closedAt: new Date().toISOString(),
        };
      }
      return ev;
    });

    saveEvents(updatedEvents);
    setIsClosingModalOpen(false);
    setEventToClose(null);
    showToast(`🟢 Incidencia ${eventToClose.id} marcada como FINALIZADA.`, "success");
  };

  const handleDeleteEvent = (eventId: string) => {
    if (!window.confirm("¿Estás seguro de que deseas eliminar este reporte de incidencia? Esta acción no se puede deshacer.")) {
      return;
    }
    const updated = events.filter((ev) => ev.id !== eventId);
    saveEvents(updated);
    showToast("Incidencia eliminada con éxito.", "info");
  };

  // --- Modal de Actualización / Seguimiento ---
  const openUpdateModal = (evt: NetworkEvent) => {
    setEventToUpdate(evt);
    setUpdateNota("");
    setUpdateAccionEnCurso("Revisión física en sitio");
    setUpdateEta("");
    const autor = evt.personal || "Dixon Iglesias";
    setUpdateAutor(autor);

    const nowTime = getNowTimeStr();
    const msg = buildUpdateWhatsApp(evt, nowTime, autor, "", "Revisión física en sitio", "");
    setUpdateReportText(msg);

    setIsUpdateModalOpen(true);
  };

  const handleConfirmUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!eventToUpdate || !updateNota.trim()) return;

    const newUpdate: TicketUpdate = {
      id: "upd-" + Date.now(),
      timestamp: new Date().toISOString(),
      hora: getNowTimeStr(),
      autor: updateAutor,
      mensaje: `${updateAccionEnCurso ? `[${updateAccionEnCurso}] ` : ""}${updateNota.trim()}${updateEta ? ` (ETA: ${updateEta})` : ""}`,
    };

    const updatedEvents = events.map((ev) => {
      if (ev.id === eventToUpdate.id) {
        return {
          ...ev,
          estado: "en_seguimiento" as EventEstado,
          updates: [newUpdate, ...(ev.updates || [])],
        };
      }
      return ev;
    });

    saveEvents(updatedEvents);
    setIsUpdateModalOpen(false);
    setEventToUpdate(null);
    showToast(`📝 Seguimiento añadido al ticket ${eventToUpdate.id}.`, "info");
  };

  // --- Agregar Opción Rápida a un Desplegable ---
  const handleOpenQuickOption = (catalogKey: keyof CatalogsState | "motivo", title: string, causaCtx?: string) => {
    setQuickOptionModal({
      isOpen: true,
      catalogKey,
      title,
      causaContext: causaCtx,
    });
    setNewOptionValue("");
  };

  const handleSaveQuickOption = () => {
    const val = newOptionValue.trim();
    if (!val) return;

    if (quickOptionModal.catalogKey === "motivo") {
      const ctx = quickOptionModal.causaContext || formCausa;
      const current = catalogs.motivosPorCausa[ctx] || [];
      if (!current.includes(val)) {
        const updated = {
          ...catalogs,
          motivosPorCausa: {
            ...catalogs.motivosPorCausa,
            [ctx]: [...current, val],
          },
        };
        saveCatalogs(updated);
        setFormMotivo(val);
      }
    } else {
      const key = quickOptionModal.catalogKey as keyof CatalogsState;
      const list = (catalogs[key] as string[]) || [];
      if (!list.includes(val)) {
        const updated = {
          ...catalogs,
          [key]: [...list, val],
        };
        saveCatalogs(updated);
        if (key === "hubs") setFormLugar(val);
        if (key === "proveedores") setFormProveedor(val);
        if (key === "personal") setFormPersonal(val);
        if (key === "fuentesEnergia") setFormFuenteEnergia(val);
        if (key === "estadosEnergia") setFormEstadoEnergia(val);
      }
    }

    setQuickOptionModal({ isOpen: false, catalogKey: "hubs", title: "" });
    showToast(`Nueva opción agregada: "${val}"`, "success");
  };

  // --- Exportar para Excel (.xlsx) ---
  const handleExportExcel = () => {
    if (events.length === 0) {
      showToast("No hay eventos registrados para exportar.", "info");
      return;
    }

    const exportRows = events.map((e, idx) => {
      const durMin = getEventDurationMinutes(e);
      const dateParts = extractDateParts(e.date || e.dateRaw);
      return {
        ID: idx + 1,
        Ticket: e.id || `TKT-${idx + 1}`,
        Fecha: e.date || e.dateRaw || "",
        Anio: e.anio || dateParts.anio,
        Mes: e.mes || dateParts.mes,
        DiaSemana: e.diaSemana || dateParts.diaSemana,
        Causa: e.causa || "",
        Proveedor: e.proveedor || "No aplica",
        Lugar: e.lugar || "",
        Personal: e.personal || "",
        Motivo: e.motivo || "",
        "Hora de reporte": e.horaReporte || "",
        "Hora de solucion": e.horaSolucion || "",
        Reporte: e.reporte || "",
        Estado: (e.estado || "solventado").toUpperCase(),
        Duracion: e.duracion || (durMin > 0 ? (durMin >= 60 ? `${Math.floor(durMin / 60)}h ${durMin % 60}m` : `${durMin}m`) : ""),
        "Duracion Minutos": durMin,
        "Accion Tomada": e.accionTomada || "",
        "Causa Raiz": e.causaRaiz || "",
      };
    });

    const ws = XLSX.utils.json_to_sheet(exportRows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Eventos_Red");

    const fileName = `Eventos_Red_${new Date().toISOString().slice(0, 10)}.xlsx`;
    XLSX.writeFile(wb, fileName);
    showToast(`Archivo Excel exportado con éxito: ${fileName}`, "success");
  };

  // --- Copiar Reporte WhatsApp al Portapapeles ---
  const handleCopyWhatsApp = (text: string) => {
    navigator.clipboard.writeText(text);
    showToast("✅ Reporte copiado al portapapeles con formato WhatsApp.", "success");
  };

  // --- Métricas KPI Dinámicas ---
  const metrics = useMemo(() => {
    const total = events.length;
    const activos = events.filter((e) => e.estado !== "solventado").length;
    const solventados = events.filter((e) => e.estado === "solventado").length;

    const fallasProveedor = events.filter((e) => e.causa === "Falla de proveedor").length;
    const fallasElectricas = events.filter((e) => e.causa === "Falla eléctrica" || (e.causa === "Falla interna" && e.motivo?.toLowerCase().includes("electr"))).length;
    const fallasInternas = events.filter((e) => e.causa === "Falla interna" && !e.motivo?.toLowerCase().includes("electr")).length;
    const actividades = events.filter((e) => e.causa === "Actividad" || !e.causa).length;

    // Calcular lugar más frecuente
    const lugarCounts: Record<string, number> = {};
    events.forEach((e) => {
      if (e.lugar && e.lugar !== "No aplica") {
        lugarCounts[e.lugar] = (lugarCounts[e.lugar] || 0) + 1;
      }
    });

    let topLugar = "Hub CMDP";
    let topLugarCount = 0;
    Object.entries(lugarCounts).forEach(([lugar, count]) => {
      if (count > topLugarCount) {
        topLugarCount = count;
        topLugar = lugar;
      }
    });

    const proveedorCounts: Record<string, number> = {};
    events.forEach((e) => {
      if (e.proveedor && e.proveedor !== "No aplica") {
        proveedorCounts[e.proveedor] = (proveedorCounts[e.proveedor] || 0) + 1;
      }
    });
    let topProveedor = "Goldata";
    let topProveedorCount = 0;
    Object.entries(proveedorCounts).forEach(([prov, count]) => {
      if (count > topProveedorCount) {
        topProveedorCount = count;
        topProveedor = prov;
      }
    });

    // Calcular duración promedio (MTTR) de eventos solventados con duración en minutos
    const validMinutes = events.map((e) => getEventDurationMinutes(e)).filter((m) => m > 0);
    const avgMinutes = validMinutes.length > 0 ? Math.round(validMinutes.reduce((a, b) => a + b, 0) / validMinutes.length) : 0;
    const avgDurationText = avgMinutes > 0 ? (avgMinutes >= 60 ? `${Math.floor(avgMinutes / 60)}h ${avgMinutes % 60}m` : `${avgMinutes}m`) : "—";

    return {
      total,
      activos,
      solventados,
      fallasProveedor,
      fallasElectricas,
      fallasInternas,
      actividades,
      topLugar,
      topLugarCount,
      topProveedor,
      topProveedorCount,
      avgDurationText,
    };
  }, [events]);

  // Sincronizar selectedKpi si el usuario cambia el filtro manual
  useEffect(() => {
    if (activeTab === "seguidor") {
      setSelectedKpi("en_curso");
    } else if (filterCausa === "Actividad") {
      setSelectedKpi("actividad");
    } else if (filterCausa === "Falla eléctrica") {
      setSelectedKpi("falla_electrica");
    } else if (filterCausa === "Falla de proveedor") {
      setSelectedKpi("falla_proveedor");
    } else if (filterCausa === "Falla interna") {
      setSelectedKpi("falla_interna");
    } else if (filterCausa === "all") {
      setSelectedKpi("all");
    }
  }, [filterCausa, activeTab]);

  // --- Filtrado Reactivo de Bitácora ---
  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      const isElectrical = e.causa === "Falla eléctrica" || (e.causa === "Falla interna" && e.motivo?.toLowerCase().includes("electr"));
      const isInternal = e.causa === "Falla interna" && !e.motivo?.toLowerCase().includes("electr");
      const isActivity = e.causa === "Actividad" || !e.causa;
      const isProvider = e.causa === "Falla de proveedor";

      let matchCausa = true;
      if (filterCausa === "Falla eléctrica") matchCausa = isElectrical;
      else if (filterCausa === "Falla interna") matchCausa = isInternal;
      else if (filterCausa === "Actividad") matchCausa = isActivity;
      else if (filterCausa === "Falla de proveedor") matchCausa = isProvider;
      else if (filterCausa !== "all") matchCausa = e.causa === filterCausa;

      const matchLugar = filterLugar === "all" || e.lugar === filterLugar;
      const matchMotivo = filterMotivo === "all" || e.motivo === filterMotivo;
      const matchEstado =
        filterEstado === "all" ||
        (filterEstado === "abierto" && e.estado !== "solventado") ||
        (filterEstado === "solventado" && e.estado === "solventado");

      const matchQuery =
        !searchQuery.trim() ||
        (e.reporte && e.reporte.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (e.lugar && e.lugar.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (e.personal && e.personal.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (e.motivo && e.motivo.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (e.proveedor && e.proveedor.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (e.id && e.id.toLowerCase().includes(searchQuery.toLowerCase()));

      let matchPeriodo = true;
      if (filterPeriodo !== "todos") {
        const evDate = e.date || e.dateRaw || "";
        const now = new Date();
        const todayStr = now.toISOString().slice(0, 10);
        if (filterPeriodo === "hoy") {
          matchPeriodo = evDate === todayStr;
        } else if (filterPeriodo === "ayer") {
          const yesterday = new Date(now);
          yesterday.setDate(yesterday.getDate() - 1);
          matchPeriodo = evDate === yesterday.toISOString().slice(0, 10);
        } else if (filterPeriodo === "semana") {
          const d = now.getDay();
          const diffToMon = now.getDate() - (d === 0 ? 6 : d - 1);
          const mon = new Date(now);
          mon.setDate(diffToMon);
          const monStr = mon.toISOString().slice(0, 10);
          matchPeriodo = evDate >= monStr;
        } else if (filterPeriodo === "mes") {
          const mStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
          matchPeriodo = evDate >= mStr;
        }
      }

      return matchCausa && matchLugar && matchMotivo && matchEstado && matchQuery && matchPeriodo;
    });
  }, [events, filterCausa, filterLugar, filterMotivo, filterEstado, searchQuery, filterPeriodo]);

  // Resumen dinámico del desglose para la categoría seleccionada
  const categorySummary = useMemo(() => {
    if (selectedKpi === "all") return null;

    const topMotivos: Record<string, number> = {};
    const topLugares: Record<string, number> = {};
    const topProveedores: Record<string, number> = {};

    filteredEvents.forEach((e) => {
      if (e.motivo) topMotivos[e.motivo] = (topMotivos[e.motivo] || 0) + 1;
      if (e.lugar && e.lugar !== "No aplica") topLugares[e.lugar] = (topLugares[e.lugar] || 0) + 1;
      if (e.proveedor && e.proveedor !== "No aplica") {
        topProveedores[e.proveedor] = (topProveedores[e.proveedor] || 0) + 1;
      }
    });

    const sortObject = (obj: Record<string, number>) =>
      Object.entries(obj)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);

    return {
      motivos: sortObject(topMotivos),
      lugares: sortObject(topLugares),
      proveedores: sortObject(topProveedores),
    };
  }, [filteredEvents, selectedKpi]);

  // Análisis global para la pestaña de Presentación de Datos
  const globalAnalysis = useMemo(() => {
    const topMotivos: Record<string, number> = {};
    const topLugares: Record<string, number> = {};
    const topProveedores: Record<string, number> = {};

    events.forEach((e) => {
      if (e.motivo) topMotivos[e.motivo] = (topMotivos[e.motivo] || 0) + 1;
      if (e.lugar && e.lugar !== "No aplica") topLugares[e.lugar] = (topLugares[e.lugar] || 0) + 1;
      if (e.proveedor && e.proveedor !== "No aplica") {
        topProveedores[e.proveedor] = (topProveedores[e.proveedor] || 0) + 1;
      }
    });

    const sortObject = (obj: Record<string, number>, limit = 6) =>
      Object.entries(obj)
        .sort((a, b) => b[1] - a[1])
        .slice(0, limit);

    return {
      topMotivos: sortObject(topMotivos, 6),
      topLugares: sortObject(topLugares, 6),
      topProveedores: sortObject(topProveedores, 6),
    };
  }, [events]);

  // Lista de eventos activos en el seguidor
  const activeEvents = useMemo(() => {
    return events.filter((e) => e.estado !== "solventado");
  }, [events]);

  // Opciones dinámicas de motivos para el modal de nuevo evento
  const motivosDisponiblesParaCausa = useMemo(() => {
    return catalogs.motivosPorCausa[formCausa] || [];
  }, [catalogs, formCausa]);

  return (
    <div className="space-y-6 animate-fade">
      {/* Toast Notificación */}
      {statusMessage && (
        <div
          className={`fixed top-4 right-4 z-50 flex items-center gap-2 rounded-xl px-4 py-3 text-xs font-bold shadow-2xl border transition-all animate-in fade-in slide-in-from-top-2 ${
            statusMessage.type === "success"
              ? "bg-emerald-950/90 text-emerald-200 border-emerald-500/50"
              : statusMessage.type === "error"
              ? "bg-destructive/90 text-destructive-foreground border-destructive"
              : "bg-primary/95 text-primary-foreground border-primary"
          }`}
        >
          {statusMessage.type === "success" && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
          {statusMessage.type === "error" && <AlertTriangle className="h-4 w-4 text-rose-400" />}
          {statusMessage.type === "info" && <Sparkles className="h-4 w-4" />}
          <span>{statusMessage.text}</span>
        </div>
      )}

      {/* Encabezado del Módulo */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-black tracking-tight text-foreground flex items-center gap-2">
              <Activity className="h-6 w-6 text-primary" />
              <span>Dashboard de Eventos & Seguidor en Vivo</span>
            </h1>
            <Badge variant="gold">{events.length} Eventos</Badge>
            {metrics.activos > 0 && (
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
              </span>
            )}
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Gestor de tickets para fallas de proveedores, eléctricas, internas y actividades. Integrado con Power BI.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsApiModalOpen(true)}
            className="text-xs font-bold gap-1.5 border-primary/40 text-primary hover:bg-primary/10"
            title="Ver Endpoint API para alimentar Power BI"
          >
            <Radio className="h-3.5 w-3.5" />
            <span>API Power BI</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleExportExcel}
            className="text-xs font-bold gap-1.5 border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10"
            title="Exportar archivo Excel oficial"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Exportar Excel (.xlsx)</span>
          </Button>

          <a
            href={POWER_BI_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-xl border border-primary/40 bg-primary/10 px-3.5 py-1.5 text-xs font-bold text-primary hover:bg-primary/20 transition-all shadow-sm"
          >
            <BarChart3 className="h-3.5 w-3.5" />
            <span>Power BI Live</span>
            <ExternalLink className="h-3 w-3 opacity-70" />
          </a>

          <Button
            onClick={() => {
              resetCreateForm();
              setIsNewModalOpen(true);
            }}
            className="gap-2 shadow-lg shadow-primary/25 font-bold bg-primary text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            <span>Registrar Evento</span>
          </Button>
        </div>
      </div>

      {/* Selector de Pestañas Principales (ARRIBA DE LOS FILTROS GRANDES) */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as "seguidor" | "presentacion" | "bitacora" | "catalogos")} className="w-full space-y-4">
        <div className="flex items-center justify-between border-b border-border/80 pb-2">
          <TabsList className="bg-muted/40 p-1">
            <TabsTrigger value="seguidor" className="gap-2 font-bold text-xs">
              <Radio className={`h-3.5 w-3.5 ${metrics.activos > 0 ? "text-rose-400 animate-pulse" : ""}`} />
              <span>⚡ Seguidor en Vivo</span>
              {metrics.activos > 0 && (
                <span className="rounded-full bg-rose-500 text-white px-2 py-0.2 text-[10px] font-black">
                  {metrics.activos}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="presentacion" className="gap-2 font-bold text-xs">
              <BarChart3 className="h-3.5 w-3.5" />
              <span>📊 Presentación de Datos</span>
            </TabsTrigger>
            <TabsTrigger value="bitacora" className="gap-2 font-bold text-xs">
              <FileText className="h-3.5 w-3.5" />
              <span>📋 Bitácora de Eventos</span>
            </TabsTrigger>
            <TabsTrigger value="catalogos" className="gap-2 font-bold text-xs">
              <Settings className="h-3.5 w-3.5" />
              <span>⚙️ Catálogos & Opciones</span>
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Tarjetas KPI Interactivas y Filtros Maestros Grandes */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {/* 1. En Curso (Seguidor) */}
          <Card
            onClick={() => handleKpiCardClick("en_curso")}
            className={`p-3 cursor-pointer transition-all duration-200 backdrop-blur select-none ${
              selectedKpi === "en_curso" || activeTab === "seguidor"
                ? "border-rose-500/80 bg-rose-500/15 ring-2 ring-rose-500/50 shadow-lg shadow-rose-500/10 scale-[1.02]"
                : "border-border/80 bg-card/60 hover:bg-card hover:border-rose-500/40 hover:scale-[1.01]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-wider text-rose-400">
                En Curso
              </span>
              <div className="rounded-lg bg-rose-500/15 p-1 text-rose-400 border border-rose-500/30">
                <Radio className={`h-3 w-3 ${metrics.activos > 0 ? "animate-pulse" : ""}`} />
              </div>
            </div>
            <div className="mt-1">
              <div className="text-2xl font-black tracking-tight text-rose-400">
                {metrics.activos}
              </div>
            </div>
          </Card>

          {/* 2. Actividades Resueltas */}
          <Card
            onClick={() => handleKpiCardClick("actividad")}
            className={`p-3 cursor-pointer transition-all duration-200 backdrop-blur select-none ${
              selectedKpi === "actividad" && (activeTab === "presentacion" || activeTab === "bitacora")
                ? "border-emerald-500/80 bg-emerald-500/15 ring-2 ring-emerald-500/50 shadow-lg shadow-emerald-500/10 scale-[1.02]"
                : "border-border/80 bg-card/60 hover:bg-card hover:border-emerald-500/40 hover:scale-[1.01]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-wider text-emerald-400">
                Actividades
              </span>
              <div className="rounded-lg bg-emerald-500/15 p-1 text-emerald-400 border border-emerald-500/30">
                <FileText className="h-3 w-3" />
              </div>
            </div>
            <div className="mt-1">
              <div className="text-2xl font-black tracking-tight text-emerald-400">
                {metrics.actividades}
              </div>
            </div>
          </Card>

          {/* 3. Fallas Eléctricas Resueltas */}
          <Card
            onClick={() => handleKpiCardClick("falla_electrica")}
            className={`p-3 cursor-pointer transition-all duration-200 backdrop-blur select-none ${
              selectedKpi === "falla_electrica" && (activeTab === "presentacion" || activeTab === "bitacora")
                ? "border-amber-500/80 bg-amber-500/15 ring-2 ring-amber-500/50 shadow-lg shadow-amber-500/10 scale-[1.02]"
                : "border-border/80 bg-card/60 hover:bg-card hover:border-amber-500/40 hover:scale-[1.01]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-wider text-amber-400">
                Fallas Eléctricas
              </span>
              <div className="rounded-lg bg-amber-500/15 p-1 text-amber-400 border border-amber-500/30">
                <Zap className="h-3 w-3" />
              </div>
            </div>
            <div className="mt-1">
              <div className="text-2xl font-black tracking-tight text-amber-400">
                {metrics.fallasElectricas}
              </div>
            </div>
          </Card>

          {/* 4. Fallas de Proveedor Resueltas */}
          <Card
            onClick={() => handleKpiCardClick("falla_proveedor")}
            className={`p-3 cursor-pointer transition-all duration-200 backdrop-blur select-none ${
              selectedKpi === "falla_proveedor" && (activeTab === "presentacion" || activeTab === "bitacora")
                ? "border-blue-500/80 bg-blue-500/15 ring-2 ring-blue-500/50 shadow-lg shadow-blue-500/10 scale-[1.02]"
                : "border-border/80 bg-card/60 hover:bg-card hover:border-blue-500/40 hover:scale-[1.01]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-wider text-blue-400">
                Proveedor
              </span>
              <div className="rounded-lg bg-blue-500/15 p-1 text-blue-400 border border-blue-500/30">
                <Wifi className="h-3 w-3" />
              </div>
            </div>
            <div className="mt-1">
              <div className="text-2xl font-black tracking-tight text-blue-400">
                {metrics.fallasProveedor}
              </div>
            </div>
          </Card>

          {/* 5. Fallas Internas Resueltas */}
          <Card
            onClick={() => handleKpiCardClick("falla_interna")}
            className={`p-3 cursor-pointer transition-all duration-200 backdrop-blur select-none ${
              selectedKpi === "falla_interna" && (activeTab === "presentacion" || activeTab === "bitacora")
                ? "border-purple-500/80 bg-purple-500/15 ring-2 ring-purple-500/50 shadow-lg shadow-purple-500/10 scale-[1.02]"
                : "border-border/80 bg-card/60 hover:bg-card hover:border-purple-500/40 hover:scale-[1.01]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-wider text-purple-400">
                Falla Interna
              </span>
              <div className="rounded-lg bg-purple-500/15 p-1 text-purple-400 border border-purple-500/30">
                <AlertTriangle className="h-3 w-3" />
              </div>
            </div>
            <div className="mt-1">
              <div className="text-2xl font-black tracking-tight text-purple-400">
                {metrics.fallasInternas}
              </div>
            </div>
          </Card>

          {/* 6. Total Eventos */}
          <Card
            onClick={() => handleKpiCardClick("all")}
            className={`p-3 cursor-pointer transition-all duration-200 backdrop-blur select-none ${
              selectedKpi === "all" && (activeTab === "presentacion" || activeTab === "bitacora")
                ? "border-primary/80 bg-primary/15 ring-2 ring-primary/50 shadow-lg shadow-primary/10 scale-[1.02]"
                : "border-border/80 bg-card/60 hover:bg-card hover:border-primary/40 hover:scale-[1.01]"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-black uppercase tracking-wider text-foreground">
                Total Eventos
              </span>
              <div className="rounded-lg bg-primary/15 p-1 text-primary border border-primary/30">
                <Activity className="h-3 w-3" />
              </div>
            </div>
            <div className="mt-1">
              <div className="text-2xl font-black tracking-tight text-foreground">
                {metrics.total}
              </div>
            </div>
          </Card>
        </div>

        {/* ==================================================================== */}
        {/* PESTAÑA 1: SEGUIDOR EN VIVO (INCIDENCIAS ACTIVAS)                     */}
        {/* ==================================================================== */}
        <TabsContent value="seguidor" className="space-y-4 pt-2">
          {activeEvents.length === 0 ? (
            <Card className="p-12 text-center border-dashed border-border/80 bg-card/40">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-400 mb-4 border border-emerald-500/30">
                <CheckCircle2 className="h-8 w-8" />
              </div>
              <h3 className="text-lg font-bold text-foreground">Red Operando con Total Normalidad</h3>
              <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto leading-relaxed">
                No hay incidencias ni actividades abiertas en el seguidor en este momento. Todas las fallas anteriores han sido solventadas.
              </p>
              <div className="mt-5">
                <Button
                  onClick={() => {
                    resetCreateForm();
                    setIsNewModalOpen(true);
                  }}
                  className="gap-2 font-bold text-xs"
                >
                  <Plus className="h-4 w-4" />
                  <span>Registrar Evento</span>
                </Button>
              </div>
            </Card>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500"></span>
                  </span>
                  <h2 className="text-sm font-black uppercase tracking-wider text-rose-400">
                    Incidencias Activas en Seguimiento ({activeEvents.length})
                  </h2>
                </div>
                <span className="text-xs text-muted-foreground">
                  Actualiza novedades o finaliza los tickets a medida que se resuelvan.
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {activeEvents.map((evt) => (
                  <Card
                    key={evt.id}
                    className="border border-rose-500/30 bg-card/80 backdrop-blur hover:border-rose-500/50 transition-all p-5 shadow-lg shadow-rose-950/20"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2 mb-1.5">
                          <Badge variant="gold" className="font-mono text-[10px]">
                            {evt.id}
                          </Badge>
                          {evt.causa === "Falla eléctrica" && (
                            <Badge className="bg-amber-500/20 text-amber-300 border-amber-500/40">
                              ⚡ Falla Eléctrica
                            </Badge>
                          )}
                          {evt.causa === "Falla de proveedor" && (
                            <Badge className="bg-blue-500/20 text-blue-300 border-blue-500/40">
                              🌐 Proveedor: {evt.proveedor}
                            </Badge>
                          )}
                          {evt.causa === "Falla interna" && (
                            <Badge className="bg-rose-500/20 text-rose-300 border-rose-500/40">
                              🔥 Falla Interna
                            </Badge>
                          )}
                          {evt.causa === "Actividad" && (
                            <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/40">
                              📋 Actividad
                            </Badge>
                          )}
                          {(() => {
                            const badge = getActiveTimeBadge(evt.horaReporte);
                            return (
                              <span
                                className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${badge.classes}`}
                                title={`Tiempo transcurrido desde ${evt.horaReporte || "inicio"}`}
                              >
                                <span className={`h-1.5 w-1.5 rounded-full ${badge.dot}`}></span>
                                <Clock className="h-3 w-3" />
                                <span>{badge.text}</span>
                                <span className="opacity-80 font-normal">({badge.label})</span>
                              </span>
                            );
                          })()}
                        </div>
                        <h3 className="text-base font-black text-foreground flex items-center gap-2">
                          <MapPin className="h-4 w-4 text-primary shrink-0" />
                          <span>{evt.lugar}</span>
                          <span className="text-xs text-muted-foreground font-normal">• {evt.motivo}</span>
                        </h3>
                      </div>

                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Ver Detalle Completo"
                          className="h-8 w-8 text-primary hover:bg-primary/20"
                          onClick={() => setSelectedEvent(evt)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    {/* Detalle Técnico / Reporte */}
                    <div className="my-3 p-3 rounded-xl bg-background/80 border border-border/80 text-xs text-foreground/90 leading-relaxed whitespace-pre-wrap">
                      {evt.reporte}
                    </div>

                    {/* Metadatos Rápidos */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px] py-1 text-muted-foreground border-t border-border/60">
                      <div>
                        <span className="block font-bold">Inicio / Reporte:</span>
                        <span className="font-mono text-foreground">{evt.horaReporte || "—"}</span>
                      </div>
                      <div>
                        <span className="block font-bold">Responsable:</span>
                        <span className="text-foreground">{evt.personal || "No especificado"}</span>
                      </div>
                      {evt.estadoEnergia && (
                        <div className="col-span-2 sm:col-span-1">
                          <span className="block font-bold">Estado Energía:</span>
                          <span className="text-amber-400 font-bold">{evt.estadoEnergia}</span>
                        </div>
                      )}
                    </div>

                    {/* Última Actualización de Seguimiento si existe */}
                    {evt.updates && evt.updates.length > 0 && (
                      <div className="mt-2.5 p-2 rounded-lg bg-primary/10 border border-primary/20 text-[11px]">
                        <span className="font-bold text-primary block mb-0.5">
                          📢 Última Novedad ({evt.updates[0].hora}):
                        </span>
                        <span className="text-foreground/90">{evt.updates[0].mensaje}</span>
                      </div>
                    )}

                    {/* Botones de Acción del Ticket */}
                    <div className="mt-4 pt-3 border-t border-border/60 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-8 text-xs font-bold gap-1 text-emerald-400 border-emerald-500/40 hover:bg-emerald-500/10"
                          onClick={() => {
                            const aperturaText = [
                              `🚨 *INCIDENCIA ACTIVA*`,
                              `🆔 *Ticket:* ${evt.id}`,
                              `📍 *Lugar:* ${evt.lugar}`,
                              `📝 *Motivo:* ${evt.motivo}`,
                              `⏱️ *Hora Inicio:* ${evt.horaReporte}`,
                              `👤 *Responsable:* ${evt.personal}`,
                              `\n📋 *Detalle:*\n${evt.reporte}`,
                            ].join("\n");
                            handleCopyWhatsApp(aperturaText);
                          }}
                        >
                          <Copy className="h-3.5 w-3.5" />
                          <span>Copiar Reporte</span>
                        </Button>

                        <Button
                          variant="ghost"
                          size="sm"
                          title="Abrir en WhatsApp Web"
                          className="h-8 px-2 text-xs font-bold text-emerald-400 hover:bg-emerald-500/15"
                          onClick={() => {
                            const aperturaText = [
                              `🚨 *INCIDENCIA ACTIVA*`,
                              `🆔 *Ticket:* ${evt.id}`,
                              `📍 *Lugar:* ${evt.lugar}`,
                              `📝 *Motivo:* ${evt.motivo}`,
                              `⏱️ *Hora Inicio:* ${evt.horaReporte}`,
                              `👤 *Responsable:* ${evt.personal}`,
                              `\n📋 *Detalle:*\n${evt.reporte}`,
                            ].join("\n");
                            openWhatsAppWebShare(aperturaText);
                          }}
                        >
                          <Send className="h-3.5 w-3.5" />
                        </Button>

                        <Button
                          variant="outline"
                          size="sm"
                          className="h-8 text-xs font-bold gap-1 text-primary border-primary/40 hover:bg-primary/10"
                          onClick={() => openUpdateModal(evt)}
                        >
                          <MessageSquare className="h-3.5 w-3.5" />
                          <span>Novedad</span>
                        </Button>
                      </div>

                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          className="h-8 text-xs font-bold gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-950/20"
                          onClick={() => openClosingModal(evt)}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          <span>Finalizar</span>
                        </Button>

                        <Button
                          variant="outline"
                          size="sm"
                          title="Eliminar reporte de incidencia"
                          className="h-8 w-8 p-0 text-xs font-bold text-rose-500 hover:text-rose-400 border-rose-500/30 hover:bg-rose-500/10 hover:border-rose-500/50"
                          onClick={() => handleDeleteEvent(evt.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </TabsContent>

        {/* ==================================================================== */}
        {/* PESTAÑA 2: PRESENTACIÓN DE DATOS & ANÁLISIS DE RED                   */}
        {/* ==================================================================== */}
        <TabsContent value="presentacion" className="space-y-4 pt-2">
          {/* Barra superior de estado de la presentación */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl bg-card/60 backdrop-blur border border-border/80 shadow-sm">
            <div>
              <div className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-primary" />
                <h2 className="text-base font-black text-foreground">
                  Presentación de Datos & Análisis de Red
                </h2>
                <Badge variant="gold" className="text-[10px] font-bold">
                  {filteredEvents.length} Eventos Filtrados
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {selectedKpi === "all"
                  ? "Visión ejecutiva consolidada de incidencias históricas, causas recurrentes y tiempos de respuesta."
                  : selectedKpi === "actividad"
                  ? "Análisis detallado de mantenimientos preventivos, mejoras y ampliaciones de infraestructura."
                  : selectedKpi === "falla_electrica"
                  ? "Análisis de afectaciones eléctricas comerciales (Corpoelec), plantas y respaldo por UPS."
                  : selectedKpi === "falla_proveedor"
                  ? "Análisis de cortes y degradación de enlaces troncales con carriers y proveedores IP."
                  : "Análisis de fallas internas de equipamiento: routers Mikrotik, switches Huawei y OLTs."}
              </p>
            </div>

            <div className="flex items-center gap-2 self-start sm:self-center shrink-0">
              {selectedKpi !== "all" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleKpiCardClick("all")}
                  className="text-xs font-bold gap-1 border-border"
                >
                  <span>✕ Ver Todo Consolidado</span>
                </Button>
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setActiveTab("bitacora")}
                className="text-xs font-bold gap-1.5 shadow-sm"
              >
                <FileText className="h-3.5 w-3.5 text-primary" />
                <span>Ver Lista en Bitácora ({filteredEvents.length})</span>
              </Button>
            </div>
          </div>

          {/* VISTA 1: PRESENTACIÓN CONSOLIDADA (selectedKpi === "all") */}
          {selectedKpi === "all" ? (
            <div className="space-y-4">
              {/* Tarjetas de Métricas de Red */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Card className="p-3.5 bg-card/60 border-border/80">
                  <div className="text-[11px] font-bold uppercase text-muted-foreground">MTTR Promedio</div>
                  <div className="text-xl font-black text-foreground mt-1">{metrics.avgDurationText}</div>
                  <div className="text-[10px] text-muted-foreground mt-0.5">Tiempo medio de solución</div>
                </Card>

                <Card className="p-3.5 bg-card/60 border-border/80">
                  <div className="text-[11px] font-bold uppercase text-muted-foreground">Hub con Más Incidencias</div>
                  <div className="text-xl font-black text-primary truncate mt-1">{metrics.topLugar}</div>
                  <div className="text-[10px] text-muted-foreground mt-0.5">{metrics.topLugarCount} intervenciones registradas</div>
                </Card>

                <Card className="p-3.5 bg-card/60 border-border/80">
                  <div className="text-[11px] font-bold uppercase text-muted-foreground">Carrier Principal</div>
                  <div className="text-xl font-black text-blue-400 truncate mt-1">{metrics.topProveedor}</div>
                  <div className="text-[10px] text-muted-foreground mt-0.5">{metrics.topProveedorCount} fallas reportadas</div>
                </Card>

                <Card className="p-3.5 bg-card/60 border-border/80">
                  <div className="text-[11px] font-bold uppercase text-muted-foreground">Estado Operativo</div>
                  <div className="text-xl font-black text-emerald-400 mt-1">100% Solventado</div>
                  <div className="text-[10px] text-emerald-500/80 mt-0.5">0 tickets abiertos actualmente</div>
                </Card>
              </div>

              {/* Distribución Porcentual Interactiva por Causa */}
              <Card className="p-4 border-border/80 bg-card/60 backdrop-blur">
                <div className="flex items-center justify-between mb-3 border-b border-border/60 pb-2">
                  <h3 className="text-sm font-black text-foreground flex items-center gap-2">
                    <Activity className="h-4 w-4 text-primary" />
                    <span>Distribución Consolidada por Causa de Red</span>
                  </h3>
                  <span className="text-xs text-muted-foreground">
                    Haz clic en una causa para desglosar sus detalles
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                  <div
                    onClick={() => handleKpiCardClick("actividad")}
                    className="p-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 cursor-pointer hover:bg-emerald-500/10 hover:border-emerald-500/50 transition-all group"
                  >
                    <div className="flex justify-between font-bold text-emerald-400 mb-1.5">
                      <span className="flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5" />
                        Actividades
                      </span>
                      <span>{metrics.actividades} ({metrics.total > 0 ? Math.round((metrics.actividades / metrics.total) * 100) : 0}%)</span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-emerald-950">
                      <div
                        className="h-full rounded-full bg-emerald-500 transition-all duration-500"
                        style={{ width: `${metrics.total > 0 ? Math.round((metrics.actividades / metrics.total) * 100) : 0}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-2 group-hover:text-emerald-300 transition-colors">
                      Mantenimientos preventivos y mejoras →
                    </p>
                  </div>

                  <div
                    onClick={() => handleKpiCardClick("falla_proveedor")}
                    className="p-3 rounded-xl border border-blue-500/30 bg-blue-500/5 cursor-pointer hover:bg-blue-500/10 hover:border-blue-500/50 transition-all group"
                  >
                    <div className="flex justify-between font-bold text-blue-400 mb-1.5">
                      <span className="flex items-center gap-1.5">
                        <Wifi className="h-3.5 w-3.5" />
                        Proveedor
                      </span>
                      <span>{metrics.fallasProveedor} ({metrics.total > 0 ? Math.round((metrics.fallasProveedor / metrics.total) * 100) : 0}%)</span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-blue-950">
                      <div
                        className="h-full rounded-full bg-blue-500 transition-all duration-500"
                        style={{ width: `${metrics.total > 0 ? Math.round((metrics.fallasProveedor / metrics.total) * 100) : 0}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-2 group-hover:text-blue-300 transition-colors">
                      Troncales, cortes de fibra y latencia →
                    </p>
                  </div>

                  <div
                    onClick={() => handleKpiCardClick("falla_interna")}
                    className="p-3 rounded-xl border border-purple-500/30 bg-purple-500/5 cursor-pointer hover:bg-purple-500/10 hover:border-purple-500/50 transition-all group"
                  >
                    <div className="flex justify-between font-bold text-purple-400 mb-1.5">
                      <span className="flex items-center gap-1.5">
                        <AlertTriangle className="h-3.5 w-3.5" />
                        Falla Interna
                      </span>
                      <span>{metrics.fallasInternas} ({metrics.total > 0 ? Math.round((metrics.fallasInternas / metrics.total) * 100) : 0}%)</span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-purple-950">
                      <div
                        className="h-full rounded-full bg-purple-500 transition-all duration-500"
                        style={{ width: `${metrics.total > 0 ? Math.round((metrics.fallasInternas / metrics.total) * 100) : 0}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-2 group-hover:text-purple-300 transition-colors">
                      Switches, routers Mikrotik y OLTs →
                    </p>
                  </div>

                  <div
                    onClick={() => handleKpiCardClick("falla_electrica")}
                    className="p-3 rounded-xl border border-amber-500/30 bg-amber-500/5 cursor-pointer hover:bg-amber-500/10 hover:border-amber-500/50 transition-all group"
                  >
                    <div className="flex justify-between font-bold text-amber-400 mb-1.5">
                      <span className="flex items-center gap-1.5">
                        <Zap className="h-3.5 w-3.5" />
                        Falla Eléctrica
                      </span>
                      <span>{metrics.fallasElectricas} ({metrics.total > 0 ? Math.round((metrics.fallasElectricas / metrics.total) * 100) : 0}%)</span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-amber-950">
                      <div
                        className="h-full rounded-full bg-amber-500 transition-all duration-500"
                        style={{ width: `${metrics.total > 0 ? Math.round((metrics.fallasElectricas / metrics.total) * 100) : 0}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-2 group-hover:text-amber-300 transition-colors">
                      Corpoelec, plantas y respaldo UPS →
                    </p>
                  </div>
                </div>
              </Card>

              {/* Paneles de Desglose Global: Top Motivos & Top Hubs */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Top Motivos Globales */}
                <Card className="p-4 border-border/80 bg-card/60">
                  <div className="flex items-center justify-between mb-3 border-b border-border/60 pb-2">
                    <h3 className="text-xs font-black uppercase text-foreground flex items-center gap-1.5">
                      <Filter className="h-3.5 w-3.5 text-primary" />
                      <span>Top Motivos Recurrentes (Red Completa)</span>
                    </h3>
                    <span className="text-[11px] text-muted-foreground">Frecuencia histórica</span>
                  </div>
                  <div className="space-y-2.5">
                    {globalAnalysis.topMotivos.map(([motivo, count]) => {
                      const pct = Math.round((count / metrics.total) * 100);
                      return (
                        <div key={motivo} className="space-y-1">
                          <div className="flex items-center justify-between text-xs font-medium">
                            <span className="text-foreground truncate max-w-[240px]">{motivo}</span>
                            <span className="text-muted-foreground font-mono font-bold">
                              {count} <span className="opacity-70 text-[10px]">({pct}%)</span>
                            </span>
                          </div>
                          <div className="w-full h-1.5 rounded-full bg-muted/60 overflow-hidden">
                            <div className="h-full rounded-full bg-primary/70" style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Card>

                {/* Top Hubs Globales */}
                <Card className="p-4 border-border/80 bg-card/60">
                  <div className="flex items-center justify-between mb-3 border-b border-border/60 pb-2">
                    <h3 className="text-xs font-black uppercase text-foreground flex items-center gap-1.5">
                      <MapPin className="h-3.5 w-3.5 text-primary" />
                      <span>Top Hubs con Mayor Incidencia</span>
                    </h3>
                    <span className="text-[11px] text-muted-foreground">Ubicaciones críticas</span>
                  </div>
                  <div className="space-y-2.5">
                    {globalAnalysis.topLugares.map(([lugar, count]) => {
                      const pct = Math.round((count / metrics.total) * 100);
                      return (
                        <div key={lugar} className="space-y-1">
                          <div className="flex items-center justify-between text-xs font-medium">
                            <span className="text-foreground truncate max-w-[240px]">{lugar}</span>
                            <span className="text-muted-foreground font-mono font-bold">
                              {count} <span className="opacity-70 text-[10px]">({pct}%)</span>
                            </span>
                          </div>
                          <div className="w-full h-1.5 rounded-full bg-muted/60 overflow-hidden">
                            <div className="h-full rounded-full bg-amber-500/70" style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              </div>

              {/* Carriers y Proveedores Globales */}
              <Card className="p-4 border-border/80 bg-card/60">
                <div className="flex items-center justify-between mb-3 border-b border-border/60 pb-2">
                  <h3 className="text-xs font-black uppercase text-foreground flex items-center gap-1.5">
                    <Wifi className="h-3.5 w-3.5 text-blue-400" />
                    <span>Carriers y Proveedores de Tránsito Involucrados</span>
                  </h3>
                  <span className="text-[11px] text-muted-foreground">Total: {metrics.fallasProveedor} eventos</span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {globalAnalysis.topProveedores.map(([prov, count]) => (
                    <Badge
                      key={prov}
                      variant="outline"
                      className="px-3 py-1 text-xs font-bold border-blue-500/40 text-blue-300 bg-blue-500/10 cursor-pointer hover:bg-blue-500/20"
                      onClick={() => handleKpiCardClick("falla_proveedor")}
                    >
                      {prov}: <span className="ml-1 text-foreground">{count} incidencias</span>
                    </Badge>
                  ))}
                </div>
              </Card>
            </div>
          ) : (
            /* VISTA 2: DETALLE Y ANÁLISIS ESPECÍFICO DE CATEGORÍA */
            <div className="space-y-4">
              {/* Hero Banner de la Categoría */}
              <Card
                className={`p-5 border transition-all ${
                  selectedKpi === "actividad"
                    ? "border-emerald-500/40 bg-emerald-500/5 shadow-emerald-500/5"
                    : selectedKpi === "falla_electrica"
                    ? "border-amber-500/40 bg-amber-500/5 shadow-amber-500/5"
                    : selectedKpi === "falla_proveedor"
                    ? "border-blue-500/40 bg-blue-500/5 shadow-blue-500/5"
                    : "border-purple-500/40 bg-purple-500/5 shadow-purple-500/5"
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-3.5">
                    <div
                      className={`p-3 rounded-2xl border ${
                        selectedKpi === "actividad"
                          ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                          : selectedKpi === "falla_electrica"
                          ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
                          : selectedKpi === "falla_proveedor"
                          ? "bg-blue-500/20 text-blue-400 border-blue-500/30"
                          : "bg-purple-500/20 text-purple-400 border-purple-500/30"
                      }`}
                    >
                      {selectedKpi === "actividad" && <FileText className="h-6 w-6" />}
                      {selectedKpi === "falla_electrica" && <Zap className="h-6 w-6" />}
                      {selectedKpi === "falla_proveedor" && <Wifi className="h-6 w-6" />}
                      {selectedKpi === "falla_interna" && <AlertTriangle className="h-6 w-6" />}
                    </div>
                    <div>
                      <h3 className="text-lg font-black text-foreground flex items-center gap-2.5">
                        <span>
                          {selectedKpi === "actividad" && "Detalle de Actividades de Red"}
                          {selectedKpi === "falla_electrica" && "Detalle de Fallas Eléctricas"}
                          {selectedKpi === "falla_proveedor" && "Detalle de Fallas de Proveedor / Carriers"}
                          {selectedKpi === "falla_interna" && "Detalle de Fallas Internas de Infraestructura"}
                        </span>
                        <Badge
                          variant="outline"
                          className={`text-xs font-bold ${
                            selectedKpi === "actividad"
                              ? "border-emerald-500/50 text-emerald-400"
                              : selectedKpi === "falla_electrica"
                              ? "border-amber-500/50 text-amber-400"
                              : selectedKpi === "falla_proveedor"
                              ? "border-blue-500/50 text-blue-400"
                              : "border-purple-500/50 text-purple-400"
                          }`}
                        >
                          {filteredEvents.length} Resueltas ({metrics.total > 0 ? Math.round((filteredEvents.length / metrics.total) * 100) : 0}% de la Red)
                        </Badge>
                      </h3>
                      <p className="text-xs text-muted-foreground mt-1 max-w-2xl leading-relaxed">
                        {selectedKpi === "actividad" &&
                          "Mantenimientos preventivos, actualizaciones de software, optimización de enlaces y ampliación de paneles."}
                        {selectedKpi === "falla_electrica" &&
                          "Incidencias por cortes comerciales de Corpoelec, transferencia a plantas de emergencia y respaldo bajo UPS."}
                        {selectedKpi === "falla_proveedor" &&
                          "Caídas de enlaces IP troncales, cortes de fibra óptica y degradación por latencia o pérdida de paquetes (Packet Loss)."}
                        {selectedKpi === "falla_interna" &&
                          "Incidencias en equipamiento interno: switches Huawei, enrutadores Mikrotik y contingencias de red local."}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Desglose dinámico de motivos, carriers y hubs */}
                {categorySummary && (
                  <div className="mt-4 pt-4 border-t border-border/50 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                    {/* Motivos */}
                    <div className="space-y-1.5">
                      <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
                        Top Motivos de esta Causa:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {categorySummary.motivos.map(([motivo, count]) => (
                          <Badge key={motivo} variant="secondary" className="text-xs py-0.5 font-normal">
                            {motivo} <span className="ml-1 font-bold opacity-80">({count})</span>
                          </Badge>
                        ))}
                      </div>
                    </div>

                    {/* Carriers o Equipos */}
                    {categorySummary.proveedores.length > 0 && (
                      <div className="space-y-1.5">
                        <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
                          Carriers Afectados:
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {categorySummary.proveedores.map(([prov, count]) => (
                            <Badge key={prov} variant="outline" className="text-xs py-0.5 font-bold border-blue-500/40 text-blue-400">
                              {prov} ({count})
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Hubs */}
                    <div className="space-y-1.5">
                      <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
                        Hubs Más Impactados:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {categorySummary.lugares.map(([lugar, count]) => (
                          <Badge key={lugar} variant="outline" className="text-xs py-0.5">
                            {lugar} ({count})
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </Card>

              {/* Lista Resumida de Eventos Recientes de esta Categoría */}
              <Card className="overflow-hidden border-border/80">
                <CardHeader className="border-b border-border/60 py-3 bg-muted/20 flex flex-row items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Clock className="h-4 w-4 text-primary" />
                    <span>Últimos Eventos Registrados en esta Categoría ({filteredEvents.slice(0, 6).length} de {filteredEvents.length})</span>
                  </CardTitle>
                  <Button
                    variant="link"
                    size="sm"
                    onClick={() => setActiveTab("bitacora")}
                    className="text-xs text-primary font-bold p-0 h-auto"
                  >
                    Ver todos en la Bitácora →
                  </Button>
                </CardHeader>
                <div className="divide-y divide-border/60">
                  {filteredEvents.slice(0, 6).map((evt) => (
                    <div
                      key={evt.id}
                      onClick={() => setSelectedEvent(evt)}
                      className="p-3.5 hover:bg-muted/40 transition-colors cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                    >
                      <div className="space-y-1 max-w-xl">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-foreground">{evt.date || evt.dateRaw}</span>
                          <Badge variant="outline" className="text-[10px]">{evt.lugar}</Badge>
                          <span className="text-muted-foreground font-medium">• {evt.motivo}</span>
                        </div>
                        <p className="text-foreground/80 line-clamp-1 leading-relaxed">
                          {evt.reporte}
                        </p>
                      </div>

                      <div className="flex items-center gap-3 shrink-0 self-start sm:self-center">
                        <span className="font-mono text-muted-foreground text-[11px] font-bold">
                          {evt.duracion ? `Duración: ${evt.duracion}` : "—"}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-primary hover:bg-primary/20"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedEvent(evt);
                          }}
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Botón grande para ir a la bitácora */}
              <div className="text-center pt-2">
                <Button
                  onClick={() => setActiveTab("bitacora")}
                  className="gap-2 font-bold text-xs shadow-md"
                >
                  <FileText className="h-4 w-4" />
                  <span>Explorar los {filteredEvents.length} Registros en la Bitácora</span>
                </Button>
              </div>
            </div>
          )}
        </TabsContent>

        {/* ==================================================================== */}
        {/* PESTAÑA 3: BITÁCORA DE EVENTOS (TABLA HISTÓRICA)                     */}
        {/* ==================================================================== */}
        <TabsContent value="bitacora" className="space-y-4 pt-2">
          {/* Barra de Filtros y Búsqueda */}
          <Card className="p-4 bg-card/60 backdrop-blur border-border/80">
            <div className="flex flex-col lg:flex-row items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-2.5 w-full lg:w-auto">
                <div className="flex items-center gap-1.5">
                  <Filter className="h-3.5 w-3.5 text-primary" />
                  <span className="text-[11px] font-bold text-muted-foreground uppercase">Filtros:</span>
                </div>

                {/* Selector Rápido de Período (Recomendación 4.B) */}
                <div className="flex items-center gap-1 bg-muted/40 p-1 rounded-xl border border-border/60">
                  {[
                    { id: "todos", label: "Todos" },
                    { id: "hoy", label: "Hoy" },
                    { id: "ayer", label: "Ayer" },
                    { id: "semana", label: "Esta Semana" },
                    { id: "mes", label: "Este Mes" },
                  ].map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setFilterPeriodo(p.id as "todos" | "hoy" | "ayer" | "semana" | "mes")}
                      className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                        filterPeriodo === p.id
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>

                {/* Filtro Causa */}
                <select
                  value={filterCausa}
                  onChange={(e) => setFilterCausa(e.target.value)}
                  className="rounded-xl border border-border bg-background px-2.5 py-1 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-pointer"
                >
                  <option value="all">Todas las Causas</option>
                  <option value="Falla interna">Falla interna</option>
                  <option value="Falla de proveedor">Falla de proveedor</option>
                  <option value="Falla eléctrica">Falla eléctrica</option>
                  <option value="Actividad">Actividad</option>
                </select>

                {/* Filtro Lugar */}
                <select
                  value={filterLugar}
                  onChange={(e) => setFilterLugar(e.target.value)}
                  className="rounded-xl border border-border bg-background px-2.5 py-1 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-pointer max-w-[170px]"
                >
                  <option value="all">Todos los Hubs</option>
                  {catalogs.hubs.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>

                {/* Filtro Estado */}
                <select
                  value={filterEstado}
                  onChange={(e) => setFilterEstado(e.target.value as "all" | "abierto" | "solventado")}
                  className="rounded-xl border border-border bg-background px-2.5 py-1 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-pointer"
                >
                  <option value="all">Todos los Estados</option>
                  <option value="abierto">🔴 En Curso (Activos)</option>
                  <option value="solventado">🟢 Solventados</option>
                </select>

                {/* Limpiar */}
                {(filterCausa !== "all" || filterLugar !== "all" || filterMotivo !== "all" || filterEstado !== "all" || filterPeriodo !== "todos" || searchQuery) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setFilterCausa("all");
                      setFilterLugar("all");
                      setFilterMotivo("all");
                      setFilterEstado("all");
                      setFilterPeriodo("todos");
                      setSearchQuery("");
                    }}
                    className="text-xs text-primary font-bold h-7 px-2"
                  >
                    <RefreshCw className="h-3 w-3 mr-1" />
                    Limpiar
                  </Button>
                )}
              </div>

              <div className="relative w-full lg:w-72">
                <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Buscar en reportes, hubs, personal..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-xl border border-border bg-background pl-8 pr-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>
            </div>
          </Card>

          {/* Tabla de Eventos */}
          <Card className="overflow-hidden">
            <CardHeader className="border-b border-border/60 py-3 bg-muted/20">
              <CardTitle className="text-sm flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" />
                  <span>Bitácora de Eventos de Red ({filteredEvents.length} resultados)</span>
                </div>
                <span className="text-xs text-muted-foreground font-mono">Total histórico: {events.length}</span>
              </CardTitle>
            </CardHeader>

            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="whitespace-nowrap min-w-[110px]">Fecha</TableHead>
                    <TableHead className="whitespace-nowrap w-28">Estado</TableHead>
                    <TableHead className="whitespace-nowrap w-32">Causa</TableHead>
                    <TableHead className="w-40 whitespace-nowrap">Lugar / Hub</TableHead>
                    <TableHead className="w-36">Motivo</TableHead>
                    <TableHead className="w-32">Personal</TableHead>
                    <TableHead>Diagnóstico & Reporte Técnico</TableHead>
                    <TableHead className="w-20 text-center whitespace-nowrap">Duración</TableHead>
                    <TableHead className="w-24 text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredEvents.map((evt) => (
                    <TableRow
                      key={evt.id}
                      className="cursor-pointer hover:bg-muted/60 transition-colors"
                      onClick={() => setSelectedEvent(evt)}
                    >
                      <TableCell className="font-mono text-xs font-bold text-foreground whitespace-nowrap">
                        {evt.date || evt.dateRaw}
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        {evt.estado === "abierto" || evt.estado === "en_seguimiento" ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/25">
                            <span className="h-1.5 w-1.5 rounded-full bg-rose-400 animate-pulse"></span>
                            En curso
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                            Solventado
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        {evt.causa === "Falla eléctrica" && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-[11px] font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/25">
                            <span>⚡</span>
                            <span>Eléctrica</span>
                          </span>
                        )}
                        {evt.causa === "Falla de proveedor" && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-[11px] font-semibold bg-blue-500/10 text-blue-300 border border-blue-500/25">
                            <span>🌐</span>
                            <span>Proveedor</span>
                          </span>
                        )}
                        {evt.causa === "Falla interna" && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-[11px] font-semibold bg-rose-500/10 text-rose-300 border border-rose-500/25">
                            <span>🔥</span>
                            <span>Interna</span>
                          </span>
                        )}
                        {evt.causa === "Actividad" && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-[11px] font-semibold bg-teal-500/10 text-teal-300 border border-teal-500/25">
                            <span>📋</span>
                            <span>Actividad</span>
                          </span>
                        )}
                        {!["Falla eléctrica", "Falla de proveedor", "Falla interna", "Actividad"].includes(evt.causa) && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-[11px] font-semibold bg-muted/40 text-muted-foreground border border-border">
                            {evt.causa}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs font-bold text-primary whitespace-nowrap">{evt.lugar}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{evt.motivo}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{evt.personal || "—"}</TableCell>
                      <TableCell className="text-xs text-foreground/90 max-w-md truncate leading-relaxed">
                        {evt.reporte}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-center text-muted-foreground font-bold whitespace-nowrap">
                        {evt.duracion || (evt.estado === "abierto" ? "En curso" : "—")}
                      </TableCell>
                      <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Ver Detalle Completo"
                            className="h-7 w-7 text-primary hover:bg-primary/20"
                            onClick={() => setSelectedEvent(evt)}
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ==================================================================== */}
        {/* PESTAÑA 3: CATÁLOGOS & OPCIONES (CERO DISCREPANCIAS)                  */}
        {/* ==================================================================== */}
        <TabsContent value="catalogos" className="space-y-4 pt-2">
          <Card className="p-5 bg-card/60 backdrop-blur border-border/80">
            <div className="flex items-center justify-between mb-4 border-b border-border/60 pb-3">
              <div>
                <h3 className="text-base font-black text-foreground flex items-center gap-2">
                  <Settings className="h-5 w-5 text-primary" />
                  <span>Catálogos Maestros de Opciones Desplegables</span>
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Gestiona las opciones oficiales de cada lista desplegable para evitar discrepancias ortográficas y garantizar datos 100% limpios en Power BI.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  saveCatalogs(DEFAULT_CATALOGS);
                  showToast("Catálogos restaurados a valores predeterminados.", "info");
                }}
                className="text-xs font-bold"
              >
                Restaurar Predeterminados
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {/* Hubs / Lugares */}
              <div className="rounded-xl border border-border/80 bg-background/50 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-xs text-primary flex items-center gap-1.5">
                    <MapPin className="h-4 w-4" />
                    <span>Hubs / Lugares ({catalogs.hubs.length})</span>
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-[11px] font-bold text-primary"
                    onClick={() => handleOpenQuickOption("hubs", "Agregar Nuevo Hub")}
                  >
                    + Agregar
                  </Button>
                </div>
                <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto p-1">
                  {catalogs.hubs.map((h) => (
                    <Badge key={h} variant="outline" className="text-[11px] py-0.5">
                      {h}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Proveedores / Carriers */}
              <div className="rounded-xl border border-border/80 bg-background/50 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-xs text-blue-400 flex items-center gap-1.5">
                    <Wifi className="h-4 w-4" />
                    <span>Carriers / Proveedores ({catalogs.proveedores.length})</span>
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-[11px] font-bold text-blue-400"
                    onClick={() => handleOpenQuickOption("proveedores", "Agregar Proveedor")}
                  >
                    + Agregar
                  </Button>
                </div>
                <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto p-1">
                  {catalogs.proveedores.map((p) => (
                    <Badge key={p} variant="outline" className="text-[11px] py-0.5">
                      {p}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Personal Técnico */}
              <div className="rounded-xl border border-border/80 bg-background/50 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-xs text-emerald-400 flex items-center gap-1.5">
                    <User className="h-4 w-4" />
                    <span>Personal Responsable ({catalogs.personal.length})</span>
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-[11px] font-bold text-emerald-400"
                    onClick={() => handleOpenQuickOption("personal", "Agregar Personal Técnico")}
                  >
                    + Agregar
                  </Button>
                </div>
                <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto p-1">
                  {catalogs.personal.map((tech) => (
                    <Badge key={tech} variant="outline" className="text-[11px] py-0.5">
                      {tech}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Motivos por Causa */}
              {Object.entries(catalogs.motivosPorCausa).map(([causa, motivos]) => (
                <div key={causa} className="rounded-xl border border-border/80 bg-background/50 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-xs text-foreground flex items-center gap-1.5 truncate">
                      <span>Motivos: {causa} ({motivos.length})</span>
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 px-2 text-[11px] font-bold text-primary"
                      onClick={() => handleOpenQuickOption("motivo", `Agregar Motivo (${causa})`, causa)}
                    >
                      + Agregar
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto p-1">
                    {motivos.map((m) => (
                      <Badge key={m} variant="secondary" className="text-[11px] py-0.5">
                        {m}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ==================================================================== */}
      {/* MODAL: REGISTRAR / ABRIR NUEVO TICKET CON REPORTE WHATSAPP EN VIVO   */}
      {/* ==================================================================== */}
      <Dialog open={isNewModalOpen} onOpenChange={setIsNewModalOpen}>
        <DialogContent className="w-[96vw] max-w-[1450px] h-[92vh] max-h-[94vh] flex flex-col p-6 overflow-hidden">
          <form onSubmit={handleCreateEvent} className="flex flex-col flex-1 h-full min-h-0">
            <DialogHeader className="pb-3 border-b border-border/60 shrink-0">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <DialogTitle className="flex items-center gap-2 text-base font-black">
                  <Zap className="h-5 w-5 text-primary" />
                  <span>Registrar Evento</span>
                </DialogTitle>

                {/* Selector de Estado Inicial del Ticket */}
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-muted-foreground hidden md:inline">Estado Inicial:</span>
                  <div className="inline-flex items-center gap-1.5 p-1 bg-muted/40 rounded-xl border border-border/60">
                    <button
                      type="button"
                      onClick={() => {
                        setFormEstadoInicio("abierto");
                        setFormHoraSolucion("");
                        setFormDuracion("");
                      }}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                        formEstadoInicio === "abierto"
                          ? "bg-rose-500/20 text-rose-300 border border-rose-500/50 shadow-sm"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/60 border border-transparent"
                      }`}
                    >
                      <Radio className="h-3.5 w-3.5" />
                      <span>🔴 Abrir en el Seguidor (En Curso)</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setFormEstadoInicio("solventado");
                        const now = getNowTimeStr();
                        setFormHoraSolucion(now);
                        if (formHoraReporte) {
                          const dur = calculateDuration(formHoraReporte, now);
                          setFormDuracion(dur.text);
                        }
                      }}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                        formEstadoInicio === "solventado"
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/50 shadow-sm"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted/60 border border-transparent"
                      }`}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      <span>🟢 Guardar como Solventado</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Si está seleccionado Solventado, mostrar los campos de cierre directamente arriba */}
              {formEstadoInicio === "solventado" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 mt-2">
                  <div>
                    <label className="font-bold text-emerald-400 block mb-1 text-[11px]">Hora Solución / Cierre:</label>
                    <input
                      type="text"
                      placeholder="Ej. 10:30 AM o 14:30"
                      value={formHoraSolucion}
                      onChange={(e) => {
                        const val = e.target.value;
                        setFormHoraSolucion(val);
                        if (val && formHoraReporte) {
                          const dur = calculateDuration(formHoraReporte, val);
                          setFormDuracion(dur.text);
                        }
                      }}
                      className="w-full rounded-xl border border-border bg-background px-3 py-1 text-xs text-foreground font-semibold"
                    />
                  </div>
                  <div>
                    <label className="font-bold text-emerald-400 block mb-1 text-[11px]">Duración calculada:</label>
                    <input
                      type="text"
                      placeholder="Ej. 45 min o 2h 15m"
                      value={formDuracion}
                      onChange={(e) => setFormDuracion(e.target.value)}
                      className="w-full rounded-xl border border-border bg-background px-3 py-1 text-xs text-foreground font-semibold"
                    />
                  </div>
                </div>
              )}
            </DialogHeader>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 py-3 flex-1 min-h-0 text-xs">
              {/* Columna Izquierda: Formulario Estructurado (7 cols) */}
              <div className="lg:col-span-7 space-y-4 overflow-y-auto pr-3">
                {/* Selector de Causa con Acceso a Personalizar Identidad */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="font-black text-foreground">Causa de la Eventualidad:</label>
                    <button
                      type="button"
                      onClick={() => openTemplateCustomizer(formCausa)}
                      className="text-xs text-primary hover:text-primary/80 font-bold flex items-center gap-1.5 bg-primary/10 hover:bg-primary/20 px-2.5 py-1 rounded-lg transition-colors border border-primary/20"
                    >
                      <Palette className="h-3.5 w-3.5" />
                      <span>Personalizar Plantillas</span>
                    </button>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {[
                      { id: "Falla de proveedor", label: "🔴 Proveedor", color: "border-blue-500/40 text-blue-400" },
                      { id: "Falla eléctrica", label: "⚡ Eléctrica", color: "border-amber-500/40 text-amber-400" },
                      { id: "Falla interna", label: "🔥 Interna", color: "border-rose-500/40 text-rose-400" },
                      { id: "Actividad", label: "📋 Actividad", color: "border-emerald-500/40 text-emerald-400" },
                    ].map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          setFormCausa(item.id);
                          setFormMotivo("");
                          setIsReportManuallyEdited(false);
                        }}
                        className={`rounded-xl border p-2 text-center text-xs font-black transition-all ${
                          formCausa === item.id
                            ? "bg-primary text-primary-foreground border-primary shadow-sm"
                            : "bg-muted/30 text-muted-foreground border-border hover:bg-muted/60"
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Fecha y Hora de Inicio */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="font-bold text-muted-foreground block mb-1">Fecha:</label>
                    <input
                      type="date"
                      required
                      value={formDate}
                      onChange={(e) => {
                        setFormDate(e.target.value);
                        setIsReportManuallyEdited(false);
                      }}
                      className="w-full rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-pointer"
                    />
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="font-bold text-muted-foreground">Hora Inicio / Reporte:</label>
                      <button
                        type="button"
                        onClick={() => {
                          setFormHoraReporte(getNowTimeStr());
                          setIsReportManuallyEdited(false);
                        }}
                        className="text-[10px] text-primary font-bold hover:underline"
                      >
                        ⏱️ Ahora
                      </button>
                    </div>
                    <input
                      type="text"
                      required
                      value={formHoraReporte}
                      onChange={(e) => {
                        setFormHoraReporte(e.target.value);
                        setIsReportManuallyEdited(false);
                      }}
                      className="w-full rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                    />
                  </div>
                </div>

                {/* Hub / Lugar (Desplegable con búsqueda por escritura) */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="font-bold text-muted-foreground">Lugar / Hub:</label>
                    <button
                      type="button"
                      onClick={() => handleOpenQuickOption("hubs", "Agregar Nuevo Hub")}
                      className="text-[10px] text-primary font-bold hover:underline"
                    >
                      + Nuevo Hub
                    </button>
                  </div>
                  <SearchableCombobox
                    value={formLugar}
                    onChange={(val) => {
                      setFormLugar(val);
                      setIsReportManuallyEdited(false);
                    }}
                    options={catalogs.hubs}
                    placeholder="Buscar o seleccionar Hub (ej. tejeria)..."
                  />
                </div>

                {/* Motivo (Desplegable contextual con búsqueda por escritura) */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="font-bold text-muted-foreground">Motivo ({formCausa}):</label>
                    <button
                      type="button"
                      onClick={() => handleOpenQuickOption("motivo", `Agregar Motivo (${formCausa})`, formCausa)}
                      className="text-[10px] text-primary font-bold hover:underline"
                    >
                      + Nuevo Motivo
                    </button>
                  </div>
                  <SearchableCombobox
                    value={formMotivo}
                    onChange={(val) => {
                      setFormMotivo(val);
                      setIsReportManuallyEdited(false);
                    }}
                    options={motivosDisponiblesParaCausa}
                    placeholder="Buscar o seleccionar Motivo..."
                  />
                </div>

                {/* ========================================================= */}
                {/* CARD DE IDENTIDAD Y CAMPOS ESPECIALIZADOS DE LA CAUSA     */}
                {/* ========================================================= */}
                {(() => {
                  const currentTemplate = templates[formCausa] || DEFAULT_REPORT_TEMPLATES[formCausa] || {
                    causa: formCausa,
                    title: `REPORTE DE ${formCausa.toUpperCase()}`,
                    icon: "🔴",
                    colorTheme: "blue" as const,
                    fields: [],
                  };

                  const themeColors = {
                    blue: {
                      border: "border-blue-500/30",
                      bg: "bg-blue-950/15",
                      title: "text-blue-400",
                      subtext: "text-blue-400/90",
                    },
                    amber: {
                      border: "border-amber-500/30",
                      bg: "bg-amber-950/15",
                      title: "text-amber-400",
                      subtext: "text-amber-400/90",
                    },
                    rose: {
                      border: "border-rose-500/30",
                      bg: "bg-rose-950/15",
                      title: "text-rose-400",
                      subtext: "text-rose-400/90",
                    },
                    emerald: {
                      border: "border-emerald-500/30",
                      bg: "bg-emerald-950/15",
                      title: "text-emerald-400",
                      subtext: "text-emerald-400/90",
                    },
                  };

                  const theme = themeColors[currentTemplate.colorTheme as keyof typeof themeColors] || themeColors.blue;

                  return (
                    <div className={`rounded-2xl border ${theme.border} ${theme.bg} p-4 space-y-3.5 transition-all`}>
                      {/* Cabecera de la Tarjeta de Identidad */}
                      <div className="flex items-center justify-between pb-2 border-b border-border/40">
                        <div className="flex items-center gap-2">
                          <span className="text-base">{currentTemplate.icon}</span>
                          <span className={`font-black text-xs uppercase tracking-wide ${theme.title}`}>
                            {currentTemplate.title}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => openTemplateCustomizer(formCausa)}
                            className="text-[11px] font-bold text-muted-foreground hover:text-foreground flex items-center gap-1 hover:underline"
                          >
                            <Sliders className="h-3 w-3" />
                            <span>Personalizar Campos</span>
                          </button>
                        </div>
                      </div>

                      {/* Campos Especializados de la Plantilla */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {currentTemplate.fields
                          .filter((f) => f.enabled)
                          .map((field) => {
                            const val = formFieldValues[field.id] || "";
                            return (
                              <div key={field.id} className={field.type === "text" && field.id.includes("autonomia") ? "col-span-2" : ""}>
                                <div className="flex items-center justify-between mb-1">
                                  <label className={`font-bold text-xs flex items-center gap-1 ${theme.subtext}`}>
                                    <span>{field.icon || "🔹"}</span>
                                    <span>{field.label}:</span>
                                  </label>
                                  {field.id === "proveedor" && (
                                    <button
                                      type="button"
                                      onClick={() => handleOpenQuickOption("proveedores", "Agregar Proveedor")}
                                      className="text-[10px] text-primary font-bold hover:underline"
                                    >
                                      + Nuevo
                                    </button>
                                  )}
                                </div>

                                {field.type === "select" ? (
                                  <SearchableCombobox
                                    value={val}
                                    onChange={(newVal) => setFieldValue(field.id, newVal)}
                                    options={field.id === "proveedor" ? catalogs.proveedores : (field.options || [])}
                                    placeholder={field.placeholder || `Seleccionar ${field.label}...`}
                                  />
                                ) : (
                                  <input
                                    type="text"
                                    value={val}
                                    onChange={(e) => setFieldValue(field.id, e.target.value)}
                                    placeholder={field.placeholder || `Ingresar ${field.label}...`}
                                    className="w-full rounded-xl border border-border bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                                  />
                                )}
                              </div>
                            );
                          })}
                      </div>

                      {/* Campos Dinámicos Adicionales Agregados al Ticket */}
                      {customFieldsList.length > 0 && (
                        <div className="pt-2 border-t border-border/40 space-y-2">
                          <span className="text-[11px] font-black text-foreground flex items-center gap-1">
                            <span>📌</span>
                            <span>Campos Personalizados Añadidos:</span>
                          </span>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                            {customFieldsList.map((cf) => (
                              <div
                                key={cf.id}
                                className="flex items-center justify-between gap-2 p-2 rounded-xl bg-background/80 border border-border"
                              >
                                <div className="flex-1 min-w-0">
                                  <span className="block text-[10px] font-bold text-muted-foreground truncate">
                                    {cf.icon || "📌"} {cf.label}:
                                  </span>
                                  <span className="block text-xs font-semibold text-foreground truncate">
                                    {cf.value}
                                  </span>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => handleRemoveCustomField(cf.id)}
                                  className="text-rose-400 hover:text-rose-300 p-1 hover:bg-rose-500/10 rounded-lg transition-colors"
                                  title="Eliminar campo de este reporte"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Botón y Panel Expandible para Añadir Campo */}
                      {!isAddingCustomField ? (
                        <div className="pt-1 flex items-center justify-between">
                          <button
                            type="button"
                            onClick={() => setIsAddingCustomField(true)}
                            className="text-xs font-bold text-primary hover:text-primary/80 flex items-center gap-1.5 bg-primary/10 hover:bg-primary/20 px-3 py-1.5 rounded-xl border border-primary/20 transition-all shadow-sm"
                          >
                            <Plus className="h-3.5 w-3.5" />
                            <span>Añadir Campo a este Reporte</span>
                          </button>
                        </div>
                      ) : (
                        <div className="p-3.5 rounded-xl border border-primary/30 bg-background/95 space-y-2.5 shadow-md">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-foreground text-xs flex items-center gap-1.5">
                              <Plus className="h-3.5 w-3.5 text-primary" />
                              <span>Añadir Nuevo Campo Dinámico:</span>
                            </span>
                            <button
                              type="button"
                              onClick={() => {
                                setIsAddingCustomField(false);
                                setNewCustomFieldLabel("");
                                setNewCustomFieldValue("");
                              }}
                              className="text-muted-foreground hover:text-foreground text-xs p-1"
                            >
                              ✕
                            </button>
                          </div>

                          {/* Chips de Sugerencias Rápidas */}
                          <div className="flex flex-wrap gap-1.5 items-center">
                            <span className="text-[10px] text-muted-foreground font-semibold">Sugerencias:</span>
                            {[
                              "VLAN / Servicio",
                              "Enlace de Respaldo",
                              "Subestación",
                              "OT / Ticket Interno",
                              "Clientes Afectados",
                              "Nivel de Combustible",
                              "Ruta de Fibra",
                              "Segmento IP",
                            ].map((sug) => (
                              <button
                                key={sug}
                                type="button"
                                onClick={() => setNewCustomFieldLabel(sug)}
                                className="text-[10px] bg-muted/50 hover:bg-primary/20 hover:text-primary text-foreground px-2 py-0.5 rounded-full border border-border transition-colors font-medium"
                              >
                                + {sug}
                              </button>
                            ))}
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-12 gap-2">
                            <div className="sm:col-span-5">
                              <label className="text-[10px] font-bold text-muted-foreground block mb-0.5">Nombre del Campo:</label>
                              <input
                                type="text"
                                placeholder="Ej. VLAN Afectada"
                                value={newCustomFieldLabel}
                                onChange={(e) => setNewCustomFieldLabel(e.target.value)}
                                className="w-full rounded-xl border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                              />
                            </div>
                            <div className="sm:col-span-7">
                              <label className="text-[10px] font-bold text-muted-foreground block mb-0.5">Valor del Campo:</label>
                              <input
                                type="text"
                                placeholder="Ej. VLAN 204 (Troncal Dixon)"
                                value={newCustomFieldValue}
                                onChange={(e) => setNewCustomFieldValue(e.target.value)}
                                className="w-full rounded-xl border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                              />
                            </div>
                          </div>

                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1 border-t border-border/40">
                            <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={saveCustomFieldAsPermanent}
                                onChange={(e) => setSaveCustomFieldAsPermanent(e.target.checked)}
                                className="rounded border-border text-primary focus:ring-primary"
                              />
                              <span>Guardar también como campo permanente en la plantilla de {formCausa}</span>
                            </label>

                            <div className="flex items-center gap-2 self-end sm:self-auto">
                              <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                className="h-7 text-xs"
                                onClick={() => {
                                  setIsAddingCustomField(false);
                                  setNewCustomFieldLabel("");
                                  setNewCustomFieldValue("");
                                }}
                              >
                                Cancelar
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                className="h-7 text-xs font-bold bg-primary text-primary-foreground hover:bg-primary/90"
                                onClick={handleAddCustomFieldSubmit}
                              >
                                + Agregar Campo
                              </Button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* Personal Responsable (Desplegable con búsqueda por escritura) */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="font-bold text-muted-foreground">Personal Responsable:</label>
                    <button
                      type="button"
                      onClick={() => handleOpenQuickOption("personal", "Agregar Personal Técnico")}
                      className="text-[10px] text-primary font-bold hover:underline"
                    >
                      + Nuevo Técnico
                    </button>
                  </div>
                  <SearchableCombobox
                    value={formPersonal}
                    onChange={(val) => {
                      setFormPersonal(val);
                      setIsReportManuallyEdited(false);
                    }}
                    options={catalogs.personal}
                    placeholder="Buscar o seleccionar Técnico..."
                  />
                </div>

                {/* Diagnóstico / Detalle */}
                <div>
                  <label className="font-bold text-muted-foreground block mb-1">
                    Diagnóstico / Detalle Técnico:
                  </label>
                  <textarea
                    rows={3}
                    placeholder="Describe la eventualidad, comportamiento observado o maniobra realizada..."
                    value={formReporte}
                    onChange={(e) => {
                      setFormReporte(e.target.value);
                      setIsReportManuallyEdited(false);
                    }}
                    className="w-full rounded-xl border border-border bg-background p-2.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none leading-relaxed"
                  />
                </div>
              </div>

              {/* Columna Derecha: Vista Previa y Editor WhatsApp (5 cols) */}
              <div className="lg:col-span-5 flex flex-col h-full rounded-2xl border border-emerald-500/30 bg-emerald-950/10 p-4 min-h-0">
                <div className="flex items-center gap-1.5 mb-2 font-black text-emerald-400 text-xs shrink-0">
                  <MessageSquare className="h-4 w-4" />
                  <span>Vista Previa WhatsApp</span>
                </div>

                <textarea
                  value={customReportText}
                  onChange={(e) => {
                    setCustomReportText(e.target.value);
                    setIsReportManuallyEdited(true);
                  }}
                  className="w-full flex-1 rounded-xl border border-emerald-500/30 bg-background/90 p-3.5 font-mono text-xs text-foreground leading-relaxed focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none whitespace-pre overflow-y-auto"
                />

                {isReportManuallyEdited && (
                  <div className="mt-2 flex items-center justify-end text-[11px] shrink-0">
                    <button
                      type="button"
                      onClick={() => setIsReportManuallyEdited(false)}
                      className="text-primary hover:underline font-bold"
                    >
                      Restablecer formato auto
                    </button>
                  </div>
                )}
              </div>
            </div>

            <DialogFooter className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-border/60 shrink-0">
              <Button
                type="button"
                variant="outline"
                className="border-emerald-500/50 bg-emerald-950/20 hover:bg-emerald-950/40 text-emerald-400 font-bold gap-2 px-4 shadow-sm"
                onClick={() => handleCopyWhatsApp(customReportText)}
              >
                <Copy className="h-4 w-4" />
                <span>Copiar Reporte</span>
              </Button>

              <div className="flex items-center gap-2">
                <Button type="button" variant="outline" onClick={() => setIsNewModalOpen(false)}>
                  Cancelar
                </Button>
                <Button type="submit" className="font-bold">
                  {formEstadoInicio === "abierto" ? "🔴 Guardar y Abrir en Seguidor" : "🟢 Guardar Registro Solventado"}
                </Button>
              </div>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ==================================================================== */}
      {/* MODAL: PERSONALIZAR IDENTIDAD Y CAMPOS DE REPORTES                   */}
      {/* ==================================================================== */}
      <Dialog open={isTemplateModalOpen} onOpenChange={setIsTemplateModalOpen}>
        <DialogContent className="w-[94vw] max-w-[850px] max-h-[90vh] flex flex-col p-6 overflow-hidden">
          <DialogHeader className="pb-3 border-b border-border/60 shrink-0">
            <DialogTitle className="flex items-center gap-2 text-base font-black">
              <Palette className="h-5 w-5 text-primary" />
              <span>Personalizar Identidad y Campos de Reportes</span>
            </DialogTitle>
          </DialogHeader>

          {templateDraft && (
            <div className="space-y-4 py-3 flex-1 overflow-y-auto pr-2 text-xs">
              {/* Selector de Causa a Personalizar */}
              <div>
                <label className="font-bold text-muted-foreground block mb-1.5">
                  Selecciona el Tipo de Reporte a Configurar:
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {Object.keys(DEFAULT_REPORT_TEMPLATES).map((causaKey) => (
                    <button
                      key={causaKey}
                      type="button"
                      onClick={() => handleSwitchTemplateCausa(causaKey)}
                      className={`rounded-xl border p-2 text-center text-xs font-bold transition-all ${
                        templateDraft.causa === causaKey
                          ? "bg-primary text-primary-foreground border-primary shadow-sm"
                          : "bg-muted/30 text-muted-foreground border-border hover:bg-muted/60"
                      }`}
                    >
                      {templates[causaKey]?.icon || DEFAULT_REPORT_TEMPLATES[causaKey]?.icon}{" "}
                      {causaKey.replace("Falla de ", "").replace("Falla ", "")}
                    </button>
                  ))}
                </div>
              </div>

              {/* Identidad del Reporte */}
              <div className="p-3.5 rounded-xl border border-border bg-muted/20 space-y-3">
                <span className="font-black text-foreground text-xs flex items-center gap-1.5">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <span>Identidad Oficial para WhatsApp:</span>
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
                  <div className="sm:col-span-3">
                    <label className="font-bold text-muted-foreground block mb-1">Icono / Emoji:</label>
                    <input
                      type="text"
                      value={templateDraft.icon}
                      onChange={(e) =>
                        setTemplateDraft({ ...templateDraft, icon: e.target.value })
                      }
                      className="w-full text-center text-base rounded-xl border border-border bg-background px-3 py-1.5 font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                    />
                  </div>
                  <div className="sm:col-span-9">
                    <label className="font-bold text-muted-foreground block mb-1">
                      Título Encabezado (WhatsApp):
                    </label>
                    <input
                      type="text"
                      value={templateDraft.title}
                      onChange={(e) =>
                        setTemplateDraft({ ...templateDraft, title: e.target.value })
                      }
                      className="w-full rounded-xl border border-border bg-background px-3 py-1.5 font-mono text-xs font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                    />
                  </div>
                </div>
              </div>

              {/* Lista de Campos de la Plantilla */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="font-black text-foreground text-xs flex items-center gap-1.5">
                    <Sliders className="h-4 w-4 text-primary" />
                    <span>Campos Activos en el Formulario y Reporte:</span>
                  </label>
                  <span className="text-[11px] text-muted-foreground">
                    Activa o desactiva los que desees incluir
                  </span>
                </div>

                <div className="space-y-1.5 border border-border/60 rounded-xl p-2 bg-background/50 divide-y divide-border/20">
                  {templateDraft.fields.map((field) => (
                    <div
                      key={field.id}
                      className="pt-1.5 first:pt-0 flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={field.enabled}
                            onChange={() => handleToggleField(field.id)}
                            className="sr-only peer"
                          />
                          <div className="w-8 h-4 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-primary"></div>
                        </label>
                        <span className="text-base">{field.icon || "🔹"}</span>
                        <span className={`font-semibold truncate ${field.enabled ? "text-foreground" : "text-muted-foreground line-through"}`}>
                          {field.label}
                        </span>
                        <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-normal">
                          {field.type === "select" ? `Desplegable (${field.options?.length || 0})` : "Texto"}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-1">
                        {field.isCustom && (
                          <button
                            type="button"
                            onClick={() => handleDeleteField(field.id)}
                            className="text-rose-400 hover:text-rose-300 p-1 hover:bg-rose-500/10 rounded-lg transition-colors"
                            title="Eliminar campo permanente"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Crear Nuevo Campo Permanente */}
              <div className="p-3.5 rounded-xl border border-primary/30 bg-primary/5 space-y-2.5">
                <span className="font-bold text-primary text-xs flex items-center gap-1.5">
                  <Plus className="h-3.5 w-3.5" />
                  <span>+ Agregar Nuevo Campo Permanente a &ldquo;{templateDraft.causa}&rdquo;:</span>
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-12 gap-2">
                  <div className="sm:col-span-2">
                    <label className="text-[10px] font-bold text-muted-foreground block mb-0.5">Icono:</label>
                    <input
                      type="text"
                      value={newPermanentFieldIcon}
                      onChange={(e) => setNewPermanentFieldIcon(e.target.value)}
                      className="w-full text-center rounded-xl border border-border bg-background px-2 py-1.5 text-xs text-foreground"
                    />
                  </div>
                  <div className="sm:col-span-6">
                    <label className="text-[10px] font-bold text-muted-foreground block mb-0.5">Nombre del Campo:</label>
                    <input
                      type="text"
                      placeholder="Ej. Enlace de Respaldo / VLAN"
                      value={newPermanentFieldLabel}
                      onChange={(e) => setNewPermanentFieldLabel(e.target.value)}
                      className="w-full rounded-xl border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                    />
                  </div>
                  <div className="sm:col-span-4">
                    <label className="text-[10px] font-bold text-muted-foreground block mb-0.5">Tipo:</label>
                    <select
                      value={newPermanentFieldType}
                      onChange={(e) => setNewPermanentFieldType(e.target.value as "text" | "select")}
                      className="w-full rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground"
                    >
                      <option value="text">Texto Libre</option>
                      <option value="select">Desplegable (Opciones)</option>
                    </select>
                  </div>

                  {newPermanentFieldType === "select" && (
                    <div className="sm:col-span-12">
                      <label className="text-[10px] font-bold text-muted-foreground block mb-0.5">
                        Opciones del Desplegable (separadas por coma):
                      </label>
                      <input
                        type="text"
                        placeholder="Ej. Opción 1, Opción 2, Opción 3"
                        value={newPermanentFieldOptions}
                        onChange={(e) => setNewPermanentFieldOptions(e.target.value)}
                        className="w-full rounded-xl border border-border bg-background px-3 py-1.5 text-xs text-foreground"
                      />
                    </div>
                  )}
                </div>

                <div className="flex justify-end pt-1">
                  <Button
                    type="button"
                    size="sm"
                    className="h-7 text-xs font-bold"
                    onClick={handleAddPermanentField}
                  >
                    + Agregar Campo a la Plantilla
                  </Button>
                </div>
              </div>
            </div>
          )}

          <DialogFooter className="flex flex-col sm:flex-row items-center justify-between gap-2 pt-3 border-t border-border/60 shrink-0">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleResetTemplateDefaults}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              🔄 Restablecer Plantilla Original
            </Button>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" onClick={() => setIsTemplateModalOpen(false)}>
                Cancelar
              </Button>
              <Button type="button" onClick={handleSaveTemplateDraft} className="font-bold">
                💾 Guardar Plantilla
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ==================================================================== */}
      {/* MODAL: FINALIZAR / SOLVENTAR INCIDENCIA (CIERRE DE TICKET)          */}
      {/* ==================================================================== */}
      <Dialog open={isClosingModalOpen} onOpenChange={setIsClosingModalOpen}>
        <DialogContent className="max-w-xl">
          <form onSubmit={handleConfirmClose}>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-emerald-400">
                <CheckCircle2 className="h-5 w-5" />
                <span>Finalizar Ticket: {eventToClose?.id}</span>
              </DialogTitle>
              <DialogDescription>
                Registra la hora de solución y la acción correctiva. Se calculará la duración automáticamente y se generará el reporte de cierre.
              </DialogDescription>
            </DialogHeader>

            {eventToClose && (
              <div className="space-y-4 py-3 text-xs">
                {/* Resumen del Evento */}
                <div className="p-3 rounded-xl bg-muted/40 border border-border grid grid-cols-2 gap-2">
                  <div>
                    <span className="font-bold text-muted-foreground block">Lugar / Hub:</span>
                    <span className="font-black text-foreground">{eventToClose.lugar}</span>
                  </div>
                  <div>
                    <span className="font-bold text-muted-foreground block">Causa & Motivo:</span>
                    <span className="font-bold text-foreground">{eventToClose.causa} ({eventToClose.motivo})</span>
                  </div>
                  <div>
                    <span className="font-bold text-muted-foreground block">Hora de Reporte:</span>
                    <span className="font-mono text-primary font-bold">{eventToClose.horaReporte || "—"}</span>
                  </div>
                  <div>
                    <span className="font-bold text-muted-foreground block">Duración Calculada:</span>
                    <span className="font-mono text-emerald-400 font-black text-sm">{closeCalculatedDuration}</span>
                  </div>
                </div>

                {/* Hora de Solución */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="font-bold text-muted-foreground">Hora de Solución:</label>
                    <button
                      type="button"
                      onClick={() => {
                        const now = getNowTimeStr();
                        setCloseHoraSolucion(now);
                        const dur = calculateDuration(eventToClose.horaReporte, now);
                        setCloseCalculatedDuration(dur.text);
                        const msg = buildClosingWhatsApp(eventToClose, now, dur.text || "—", closeAccionTomada, closeCausaRaiz);
                        setCloseReportText(msg);
                      }}
                      className="text-[10px] text-primary font-bold hover:underline"
                    >
                      ⏱️ Usar Hora Actual
                    </button>
                  </div>
                  <input
                    type="text"
                    required
                    value={closeHoraSolucion}
                    onChange={(e) => {
                      setCloseHoraSolucion(e.target.value);
                      const dur = calculateDuration(eventToClose.horaReporte, e.target.value);
                      setCloseCalculatedDuration(dur.text);
                      const msg = buildClosingWhatsApp(eventToClose, e.target.value, dur.text || "—", closeAccionTomada, closeCausaRaiz);
                      setCloseReportText(msg);
                    }}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                </div>

                {/* Acción Tomada / Solución Técnica */}
                <div>
                  <label className="font-bold text-muted-foreground block mb-1">
                    Acción Tomada / Solución Técnica Ejecutada:
                  </label>
                  <textarea
                    required
                    rows={3}
                    placeholder="Describe la maniobra realizada para resolver la eventualidad..."
                    value={closeAccionTomada}
                    onChange={(e) => {
                      setCloseAccionTomada(e.target.value);
                      const dur = calculateDuration(eventToClose.horaReporte, closeHoraSolucion);
                      const msg = buildClosingWhatsApp(eventToClose, closeHoraSolucion, dur.text || "—", e.target.value, closeCausaRaiz);
                      setCloseReportText(msg);
                    }}
                    className="w-full rounded-xl border border-border bg-background p-2.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none leading-relaxed"
                  />
                </div>

                {/* Causa Raíz Confirmada / RCA (Recomendación 3.A & 5) */}
                <div>
                  <label className="font-bold text-muted-foreground block mb-1">
                    Causa Raíz Confirmada (RCA - Para Power BI / Opcional):
                  </label>
                  <input
                    type="text"
                    placeholder="Ej. Corte de fibra óptica por roedor en tramo km 12 / Breaker disparado por sobretensión..."
                    value={closeCausaRaiz}
                    onChange={(e) => {
                      setCloseCausaRaiz(e.target.value);
                      const dur = calculateDuration(eventToClose.horaReporte, closeHoraSolucion);
                      const msg = buildClosingWhatsApp(eventToClose, closeHoraSolucion, dur.text || "—", closeAccionTomada, e.target.value);
                      setCloseReportText(msg);
                    }}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                  />
                </div>

                {/* Vista Previa de Reporte de Cierre */}
                <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/15 p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-emerald-400 font-bold text-[11px] flex items-center gap-1">
                      <Copy className="h-3 w-3" />
                      <span>Reporte de Cierre para WhatsApp:</span>
                    </span>
                    <div className="flex items-center gap-1.5">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-6 text-[11px] font-bold text-emerald-400 hover:bg-emerald-500/20"
                        onClick={() => handleCopyWhatsApp(closeReportText)}
                      >
                        <Copy className="h-3 w-3 mr-1" />
                        Copiar
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-6 text-[11px] font-bold text-emerald-400 hover:bg-emerald-500/20"
                        onClick={() => openWhatsAppWebShare(closeReportText)}
                      >
                        <Send className="h-3 w-3 mr-1" />
                        Enviar WhatsApp
                      </Button>
                    </div>
                  </div>
                  <pre className="text-[11px] font-mono text-foreground/90 whitespace-pre-wrap leading-relaxed max-h-36 overflow-y-auto">
                    {closeReportText}
                  </pre>
                </div>
              </div>
            )}

            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setIsClosingModalOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold">
                Confirmar y Cerrar Ticket
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ==================================================================== */}
      {/* MODAL: AGREGAR SEGUIMIENTO / NOVEDAD A INCIDENCIA ABIERTA           */}
      {/* ==================================================================== */}
      <Dialog open={isUpdateModalOpen} onOpenChange={setIsUpdateModalOpen}>
        <DialogContent className="max-w-lg">
          <form onSubmit={handleConfirmUpdate}>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-primary">
                <MessageSquare className="h-5 w-5" />
                <span>Agregar Novedad de Seguimiento: {eventToUpdate?.id}</span>
              </DialogTitle>
              <DialogDescription>
                Publica un avance técnico para el seguidor y genera el reporte de actualización para WhatsApp.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-3 text-xs">
              <div>
                <label className="font-bold text-muted-foreground block mb-1">Personal que Informa:</label>
                <select
                  value={updateAutor}
                  onChange={(e) => {
                    setUpdateAutor(e.target.value);
                    if (eventToUpdate) {
                      const msg = buildUpdateWhatsApp(eventToUpdate, getNowTimeStr(), e.target.value, updateNota, updateAccionEnCurso, updateEta);
                      setUpdateReportText(msg);
                    }
                  }}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-pointer"
                >
                  {catalogs.personal.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>
                  <label className="font-bold text-muted-foreground block mb-1">Acción en Curso:</label>
                  <select
                    value={updateAccionEnCurso}
                    onChange={(e) => {
                      setUpdateAccionEnCurso(e.target.value);
                      if (eventToUpdate) {
                        const msg = buildUpdateWhatsApp(eventToUpdate, getNowTimeStr(), updateAutor, updateNota, e.target.value, updateEta);
                        setUpdateReportText(msg);
                      }
                    }}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-pointer"
                  >
                    <option value="Revisión física en sitio">🛠️ Revisión física en sitio</option>
                    <option value="Cuadrilla en traslado al nodo">🚗 Cuadrilla en traslado</option>
                    <option value="Escalamiento con Carrier / Proveedor">📞 Escalamiento con Carrier</option>
                    <option value="Pruebas de enlace y potencia óptica">🔬 Pruebas de enlace / potencia</option>
                    <option value="Maniobra eléctrica / Planta activada">⚡ Maniobra eléctrica / Planta</option>
                    <option value="Monitoreo de estabilidad y paquetes">📡 Monitoreo de estabilidad</option>
                  </select>
                </div>
                <div>
                  <label className="font-bold text-muted-foreground block mb-1">ETA Estimado de Solución:</label>
                  <input
                    type="text"
                    placeholder="Ej. 30 min, 1 hora, 10:30 PM..."
                    value={updateEta}
                    onChange={(e) => {
                      setUpdateEta(e.target.value);
                      if (eventToUpdate) {
                        const msg = buildUpdateWhatsApp(eventToUpdate, getNowTimeStr(), updateAutor, updateNota, updateAccionEnCurso, e.target.value);
                        setUpdateReportText(msg);
                      }
                    }}
                    className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-muted-foreground block mb-1">
                  Novedad / Avance Técnico:
                </label>
                <textarea
                  required
                  rows={4}
                  placeholder="Ej: Cuadrilla en sitio revisando empalmes, generador encendido con 8h de autonomía..."
                  value={updateNota}
                  onChange={(e) => {
                    setUpdateNota(e.target.value);
                    if (eventToUpdate) {
                      const msg = buildUpdateWhatsApp(eventToUpdate, getNowTimeStr(), updateAutor, e.target.value, updateAccionEnCurso, updateEta);
                      setUpdateReportText(msg);
                    }
                  }}
                  className="w-full rounded-xl border border-border bg-background p-3 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none leading-relaxed"
                />
              </div>

              {/* Vista Previa Reporte Novedad */}
              <div className="rounded-xl border border-primary/30 bg-primary/10 p-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-primary font-bold text-[11px] flex items-center gap-1">
                    <Copy className="h-3 w-3" />
                    <span>Reporte de Seguimiento WhatsApp:</span>
                  </span>
                  <div className="flex items-center gap-1.5">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-6 text-[11px] font-bold text-primary hover:bg-primary/20"
                      onClick={() => handleCopyWhatsApp(updateReportText)}
                    >
                      <Copy className="h-3 w-3 mr-1" />
                      Copiar
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-6 text-[11px] font-bold text-primary hover:bg-primary/20"
                      onClick={() => openWhatsAppWebShare(updateReportText)}
                    >
                      <Send className="h-3 w-3 mr-1" />
                      Enviar WhatsApp
                    </Button>
                  </div>
                </div>
                <pre className="text-[11px] font-mono text-foreground/90 whitespace-pre-wrap leading-relaxed max-h-32 overflow-y-auto">
                  {updateReportText}
                </pre>
              </div>
            </div>

            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => setIsUpdateModalOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit" className="font-bold">
                Guardar Novedad
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ==================================================================== */}
      {/* MODAL: VER DETALLE COMPLETO DEL EVENTO                              */}
      {/* ==================================================================== */}
      <Dialog open={!!selectedEvent} onOpenChange={(open) => !open && setSelectedEvent(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          {selectedEvent && (
            <div>
              <DialogHeader>
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <Badge variant="gold" className="font-mono">
                    {selectedEvent.id}
                  </Badge>
                  {selectedEvent.estado === "abierto" || selectedEvent.estado === "en_seguimiento" ? (
                    <Badge className="bg-rose-500/20 text-rose-300 border-rose-500/40">
                      🔴 En curso
                    </Badge>
                  ) : (
                    <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/40">
                      🟢 Solventado
                    </Badge>
                  )}
                  <Badge variant="outline">{selectedEvent.causa}</Badge>
                </div>
                <DialogTitle className="text-base font-black">
                  {selectedEvent.motivo} en {selectedEvent.lugar}
                </DialogTitle>
                <DialogDescription>
                  Fecha: {selectedEvent.date || selectedEvent.dateRaw} • Horario: {selectedEvent.horaReporte || "—"}{" "}
                  {selectedEvent.horaSolucion ? `→ ${selectedEvent.horaSolucion}` : ""} • Duración:{" "}
                  {selectedEvent.duracion || "En curso"}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 py-4 text-xs">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-xl bg-muted/30 border border-border">
                  <div>
                    <span className="text-muted-foreground font-bold block mb-1">Lugar / Hub:</span>
                    <span className="font-black text-foreground flex items-center gap-1">
                      <MapPin className="h-3.5 w-3.5 text-primary" />
                      {selectedEvent.lugar}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground font-bold block mb-1">Personal:</span>
                    <span className="font-bold text-foreground flex items-center gap-1">
                      <User className="h-3.5 w-3.5 text-primary" />
                      {selectedEvent.personal || "No especificado"}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground font-bold block mb-1">Carrier / Proveedor:</span>
                    <span className="font-bold text-foreground">
                      {selectedEvent.proveedor || "No aplica"}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground font-bold block mb-1">Duración:</span>
                    <span className="font-mono font-bold text-emerald-400">
                      {selectedEvent.duracion || (selectedEvent.estado === "abierto" ? "En curso" : "—")}
                    </span>
                  </div>
                </div>

                <div>
                  <span className="text-muted-foreground font-bold block mb-1.5">
                    Diagnóstico Inicial & Reporte Técnico:
                  </span>
                  <div className="p-3.5 rounded-xl bg-background border border-border leading-relaxed text-foreground whitespace-pre-wrap">
                    {selectedEvent.reporte}
                  </div>
                </div>

                {selectedEvent.accionTomada && (
                  <div>
                    <span className="text-emerald-400 font-bold block mb-1.5">
                      Acción Tomada / Solución Final:
                    </span>
                    <div className="p-3.5 rounded-xl bg-emerald-950/15 border border-emerald-500/30 leading-relaxed text-foreground whitespace-pre-wrap">
                      {selectedEvent.accionTomada}
                    </div>
                  </div>
                )}

                {/* Historial de Novedades de Seguimiento */}
                {selectedEvent.updates && selectedEvent.updates.length > 0 && (
                  <div>
                    <span className="text-primary font-bold block mb-1.5">
                      Bitácora de Seguimiento ({selectedEvent.updates.length} novedades):
                    </span>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {selectedEvent.updates.map((upd) => (
                        <div key={upd.id} className="p-2.5 rounded-xl bg-muted/40 border border-border/80 text-[11px]">
                          <div className="flex items-center justify-between text-muted-foreground font-bold mb-1">
                            <span>👤 {upd.autor}</span>
                            <span className="font-mono">⏱️ {upd.hora}</span>
                          </div>
                          <p className="text-foreground">{upd.mensaje}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <DialogFooter className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs font-bold gap-1 text-emerald-400 border-emerald-500/40"
                    onClick={() => {
                      const text = [
                        `📋 *REPORTE DE INCIDENCIA*`,
                        `🆔 *Ticket:* ${selectedEvent.id}`,
                        `📍 *Lugar:* ${selectedEvent.lugar}`,
                        `📝 *Causa:* ${selectedEvent.causa} (${selectedEvent.motivo})`,
                        `⏱️ *Horario:* ${selectedEvent.horaReporte || "—"} → ${selectedEvent.horaSolucion || "En curso"}`,
                        `👤 *Personal:* ${selectedEvent.personal}`,
                        `\n📋 *Detalle:*\n${selectedEvent.reporte}`,
                        selectedEvent.accionTomada ? `\n✅ *Solución:*\n${selectedEvent.accionTomada}` : "",
                      ].filter(Boolean).join("\n");
                      handleCopyWhatsApp(text);
                    }}
                  >
                    <Copy className="h-3.5 w-3.5" />
                    <span>Copiar WhatsApp</span>
                  </Button>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 px-2.5 text-xs font-bold text-rose-500 hover:text-rose-400 border-rose-500/30 hover:bg-rose-500/10 gap-1.5"
                    title="Eliminar reporte de incidencia"
                    onClick={() => {
                      const id = selectedEvent.id;
                      setSelectedEvent(null);
                      handleDeleteEvent(id);
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>Eliminar</span>
                  </Button>
                  {selectedEvent.estado !== "solventado" && (
                    <Button
                      size="sm"
                      className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
                      onClick={() => {
                        const target = selectedEvent;
                        setSelectedEvent(null);
                        openClosingModal(target);
                      }}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                      Finalizar
                    </Button>
                  )}
                  <Button variant="outline" size="sm" onClick={() => setSelectedEvent(null)}>
                    Cerrar
                  </Button>
                </div>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ==================================================================== */}
      {/* MODAL RÁPIDO: AGREGAR NUEVA OPCIÓN A UN DESPLEGABLE                 */}
      {/* ==================================================================== */}
      <Dialog
        open={quickOptionModal.isOpen}
        onOpenChange={(open) => setQuickOptionModal((prev) => ({ ...prev, isOpen: open }))}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-4 w-4 text-primary" />
              <span>{quickOptionModal.title}</span>
            </DialogTitle>
            <DialogDescription>
              La nueva opción se guardará en la lista maestra para que aparezca siempre en los menús desplegables sin discrepancias.
            </DialogDescription>
          </DialogHeader>

          <div className="py-3">
            <label className="text-xs font-bold text-muted-foreground block mb-1">Nombre de la nueva opción:</label>
            <input
              type="text"
              autoFocus
              placeholder="Ej. Hub Nuevo, Carrier XYZ, Falla de batería..."
              value={newOptionValue}
              onChange={(e) => setNewOptionValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleSaveQuickOption();
                }
              }}
              className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>

          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setQuickOptionModal((prev) => ({ ...prev, isOpen: false }))}
            >
              Cancelar
            </Button>
            <Button type="button" onClick={handleSaveQuickOption} className="font-bold">
              Guardar Opción
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal de Conexión API Power BI */}
      <Dialog open={isApiModalOpen} onOpenChange={setIsApiModalOpen}>
        <DialogContent className="max-w-2xl border-border bg-card">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg font-black text-foreground">
              <Radio className="h-5 w-5 text-primary animate-pulse" />
              <span>Conexión API en Tiempo Real para Power BI</span>
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Conecta Power BI directamente al servidor local IIS mediante la Web API. Ya no se requiere Google Sheets intermedio: cualquier ticket o cambio se actualiza automáticamente.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            {/* Endpoint JSON */}
            <div className="rounded-xl border border-border bg-muted/40 p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-foreground flex items-center gap-1.5">
                  <Badge variant="gold" className="text-[10px]">Recomendado</Badge>
                  <span>Endpoint JSON (Formato Oficial Power BI)</span>
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs font-bold gap-1 text-primary border-primary/40 hover:bg-primary/10"
                  onClick={() => {
                    const url = `${typeof window !== "undefined" ? window.location.origin : "http://10.0.1.243"}/operaciones/modulo_de_operaciones_migrado/v2/api/events.ashx?format=powerbi`;
                    navigator.clipboard.writeText(url);
                    showToast("URL de API JSON copiada al portapapeles.", "success");
                  }}
                >
                  <Copy className="h-3 w-3" />
                  <span>Copiar URL</span>
                </Button>
              </div>
              <div className="rounded-lg bg-background p-2 font-mono text-[11px] text-primary break-all border border-border/60 select-all">
                {typeof window !== "undefined"
                  ? `${window.location.origin}/operaciones/modulo_de_operaciones_migrado/v2/api/events.ashx?format=powerbi`
                  : "http://10.0.1.243/operaciones/modulo_de_operaciones_migrado/v2/api/events.ashx?format=powerbi"}
              </div>
              <p className="text-[11px] text-muted-foreground">
                Devuelve las 13 columnas normalizadas (ID, Fecha, Causa, Proveedor, Lugar, Personal, Motivo, Horas, Duración, Reporte, Estado, etc.).
              </p>
            </div>

            {/* Endpoint CSV */}
            <div className="rounded-xl border border-border bg-muted/40 p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-foreground">Endpoint CSV (Alternativo)</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs font-bold gap-1 text-muted-foreground hover:bg-muted"
                  onClick={() => {
                    const url = `${typeof window !== "undefined" ? window.location.origin : "http://10.0.1.243"}/operaciones/modulo_de_operaciones_migrado/v2/api/events.ashx?format=csv`;
                    navigator.clipboard.writeText(url);
                    showToast("URL de API CSV copiada al portapapeles.", "success");
                  }}
                >
                  <Copy className="h-3 w-3" />
                  <span>Copiar URL</span>
                </Button>
              </div>
              <div className="rounded-lg bg-background p-2 font-mono text-[11px] text-muted-foreground break-all border border-border/60 select-all">
                {typeof window !== "undefined"
                  ? `${window.location.origin}/operaciones/modulo_de_operaciones_migrado/v2/api/events.ashx?format=csv`
                  : "http://10.0.1.243/operaciones/modulo_de_operaciones_migrado/v2/api/events.ashx?format=csv"}
              </div>
            </div>

            {/* Pasos en Power BI */}
            <div className="rounded-xl border border-border/80 bg-background/50 p-4 space-y-2.5">
              <h4 className="font-bold text-foreground text-xs flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                <span>¿Cómo conectar en Power BI Desktop?</span>
              </h4>
              <ol className="list-decimal list-inside space-y-1.5 text-muted-foreground leading-relaxed text-[11px]">
                <li>Abre Power BI Desktop y haz clic en <strong>Obtener datos</strong> ➔ <strong>Web</strong>.</li>
                <li>Pega la URL del Endpoint JSON copiada arriba y haz clic en <strong>Aceptar</strong>.</li>
                <li>En el editor de Power Query, haz clic en <strong>A la tabla</strong> y expande las columnas.</li>
                <li>¡Listo! Para actualizar en cualquier momento, solo pulsa el botón <strong>Actualizar</strong> en Power BI.</li>
              </ol>
            </div>
          </div>

          <DialogFooter>
            <Button variant="default" onClick={() => setIsApiModalOpen(false)} className="font-bold">
              Entendido
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
