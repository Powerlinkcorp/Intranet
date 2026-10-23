"use client";

import React, { useState, useEffect } from "react";
import {
  CalendarDays,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  Settings,
  Users,
  Calendar as CalendarIcon,
  Sparkles,
  Edit2,
  Trash2,
  Plus,
  RefreshCw,
  Umbrella,
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

export interface ShiftSchedule {
  lun?: string;
  mar?: string;
  mie?: string;
  jue?: string;
  vie?: string;
  sab?: string;
  dom?: string;
}

export interface ShiftDefinition {
  id: string;
  name: string;
  badge: string;
  schedule: ShiftSchedule;
}

export interface Worker {
  id: string;
  name: string;
  color: string;
  order?: number;
  phone?: string;
}

export interface WeeklyAssignment {
  id: string;
  weekStart: string; // YYYY-MM-DD (Siempre Lunes)
  assignments: Record<string, string>; // shiftId -> workerId
  vacations?: string[];
  isBase?: boolean;
}

export interface Vacation {
  id: string;
  workerId: string;
  startDate: string;
  endDate: string;
  notes?: string;
}

const STORAGE_KEYS = {
  WORKERS: "reportgen_v1_workers",
  SHIFTS: "reportgen_v1_shifts",
  WEEKLY_ASSIGNMENTS: "reportgen_v1_weekly_assignments",
  VACATIONS: "reportgen_v1_vacations",
};

const DEFAULT_WORKERS: Worker[] = [
  { id: "w-1", name: "Ivan Camacho", color: "#3B82F6", order: 0 },
  { id: "w-2", name: "Rayner Revette", color: "#10B981", order: 1 },
  { id: "w-3", name: "Brando Carrero", color: "#8B5CF6", order: 2 },
  { id: "w-4", name: "Dixon Iglesias", color: "#F59E0B", order: 3 },
];

const DEFAULT_SHIFTS: ShiftDefinition[] = [
  {
    id: "turno-1",
    name: "Guardia de Remuneración",
    badge: "T1",
    schedule: { lun: "5pm/10pm", mar: "8am/5pm", mie: "8am/5pm", jue: "8am/5pm", vie: "8am/5pm" },
  },
  {
    id: "turno-2",
    name: "Guardia Fin de Semana",
    badge: "T2",
    schedule: { lun: "7am/4pm", mar: "7am/4pm", mie: "7am/4pm", jue: "7am/4pm", vie: "7am/4pm", sab: "8am/10pm", dom: "8am/10pm" },
  },
  {
    id: "turno-3",
    name: "Turno Normal",
    badge: "T3",
    schedule: { lun: "8am/5pm", mar: "8am/5pm", mie: "8am/5pm", jue: "8am/5pm", vie: "8am/5pm" },
  },
  {
    id: "turno-4",
    name: "Guardia Nocturna",
    badge: "T4",
    schedule: { lun: "8am/5pm", mar: "1pm/10pm", mie: "1pm/10pm", jue: "1pm/10pm", vie: "1pm/10pm" },
  },
];

// Helper de fechas ISO
function formatDateISO(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function getMondayOfDate(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.setDate(diff));
}

function formatScheduleSummary(schedule: ShiftSchedule): string {
  const parts: string[] = [];
  if (schedule.lun) parts.push(`Lun: ${schedule.lun}`);
  if (schedule.mar && schedule.mar === schedule.vie) {
    parts.push(`Mar-Vie: ${schedule.mar}`);
  } else {
    if (schedule.mar) parts.push(`Mar: ${schedule.mar}`);
    if (schedule.mie) parts.push(`Mié: ${schedule.mie}`);
    if (schedule.jue) parts.push(`Jue: ${schedule.jue}`);
    if (schedule.vie) parts.push(`Vie: ${schedule.vie}`);
  }
  if (schedule.sab && schedule.dom && schedule.sab === schedule.dom) {
    parts.push(`Sáb-Dom: ${schedule.sab}`);
  } else {
    if (schedule.sab) parts.push(`Sáb: ${schedule.sab}`);
    if (schedule.dom) parts.push(`Dom: ${schedule.dom}`);
  }
  return parts.join(" | ");
}

export function GuardsScheduleModule() {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [shifts, setShifts] = useState<ShiftDefinition[]>([]);
  const [weeklyAssignments, setWeeklyAssignments] = useState<WeeklyAssignment[]>([]);
  const [vacations, setVacations] = useState<Vacation[]>([]);
  const [weekOffset, setWeekOffset] = useState(0);
  const [activeTab, setActiveTab] = useState<"cards" | "matrix" | "calendar">("cards");
  const [copied, setCopied] = useState(false);

  // Modales
  const [isEditWeekModalOpen, setIsEditWeekModalOpen] = useState(false);
  const [isManageWorkersModalOpen, setIsManageWorkersModalOpen] = useState(false);
  const [isDefineShiftsModalOpen, setIsDefineShiftsModalOpen] = useState(false);
  const [isVacationsModalOpen, setIsVacationsModalOpen] = useState(false);

  // Estado del formulario de edición de semana
  const [editingWeekStart, setEditingWeekStart] = useState("");
  const [tempAssignments, setTempAssignments] = useState<Record<string, string>>({});
  const [tempIsBase, setTempIsBase] = useState(false);

  // Estado para gestión de técnicos
  const [newWorkerName, setNewWorkerName] = useState("");
  const [newWorkerColor, setNewWorkerColor] = useState("#D4AF37");

  // Estado para vacaciones
  const [vacationWorkerId, setVacationWorkerId] = useState("");
  const [vacationStart, setVacationStart] = useState("");
  const [vacationEnd, setVacationEnd] = useState("");

  // Cargar datos de localStorage al montar
  useEffect(() => {
    try {
      // 1. Trabajadores
      const storedWorkers = localStorage.getItem(STORAGE_KEYS.WORKERS);
      let initialWorkers = DEFAULT_WORKERS;
      if (storedWorkers) {
        try {
          const parsed = JSON.parse(storedWorkers);
          if (Array.isArray(parsed) && parsed.length > 0) initialWorkers = parsed;
        } catch (e) {
          console.error("Error parseando workers:", e);
        }
      }
      setWorkers(initialWorkers);

      // 2. Turnos
      const storedShifts = localStorage.getItem(STORAGE_KEYS.SHIFTS);
      let initialShifts = DEFAULT_SHIFTS;
      if (storedShifts) {
        try {
          const parsed = JSON.parse(storedShifts);
          if (Array.isArray(parsed) && parsed.length > 0) {
            // Asegurar que cada turno tenga badge
            initialShifts = parsed.map((s: ShiftDefinition, idx: number) => ({
              ...s,
              badge: s.badge || `T${idx + 1}`,
            }));
          }
        } catch (e) {
          console.error("Error parseando shifts:", e);
        }
      }
      setShifts(initialShifts);

      // 3. Asignaciones semanales
      const storedAssignments = localStorage.getItem(STORAGE_KEYS.WEEKLY_ASSIGNMENTS);
      let initialAssignments: WeeklyAssignment[] = [];
      if (storedAssignments) {
        try {
          const parsed = JSON.parse(storedAssignments);
          if (Array.isArray(parsed)) initialAssignments = parsed;
        } catch (e) {
          console.error("Error parseando weekly assignments:", e);
        }
      }

      // Si no hay asignación base, sembramos una para la semana base de julio 2026
      if (initialAssignments.length === 0 && initialWorkers.length >= 4 && initialShifts.length >= 4) {
        const baseAssignment: WeeklyAssignment = {
          id: "wa-base",
          weekStart: "2026-07-27",
          assignments: {
            [initialShifts[0].id]: initialWorkers[0].id,
            [initialShifts[1].id]: initialWorkers[1].id,
            [initialShifts[2].id]: initialWorkers[2].id,
            [initialShifts[3].id]: initialWorkers[3].id,
          },
          isBase: true,
        };
        initialAssignments = [baseAssignment];
        localStorage.setItem(STORAGE_KEYS.WEEKLY_ASSIGNMENTS, JSON.stringify(initialAssignments));
      }
      setWeeklyAssignments(initialAssignments);

      // 4. Vacaciones
      const storedVacations = localStorage.getItem(STORAGE_KEYS.VACATIONS);
      if (storedVacations) {
        try {
          const parsed = JSON.parse(storedVacations);
          if (Array.isArray(parsed)) setVacations(parsed);
        } catch (e) {
          console.error("Error parseando vacaciones:", e);
        }
      }
    } catch (err) {
      console.error("Error cargando cronograma de guardias:", err);
    }
  }, []);

  // Guardar en localStorage al modificar
  const saveWorkers = (updated: Worker[]) => {
    setWorkers(updated);
    localStorage.setItem(STORAGE_KEYS.WORKERS, JSON.stringify(updated));
  };

  const saveShifts = (updated: ShiftDefinition[]) => {
    setShifts(updated);
    localStorage.setItem(STORAGE_KEYS.SHIFTS, JSON.stringify(updated));
  };

  const saveWeeklyAssignments = (updated: WeeklyAssignment[]) => {
    setWeeklyAssignments(updated);
    localStorage.setItem(STORAGE_KEYS.WEEKLY_ASSIGNMENTS, JSON.stringify(updated));
  };

  const saveVacations = (updated: Vacation[]) => {
    setVacations(updated);
    localStorage.setItem(STORAGE_KEYS.VACATIONS, JSON.stringify(updated));
  };

  // Calcular rango de la semana seleccionada
  const getSelectedMonday = (offset: number) => {
    const today = new Date();
    const monday = getMondayOfDate(today);
    monday.setDate(monday.getDate() + offset * 7);
    return monday;
  };

  const currentMonday = getSelectedMonday(weekOffset);
  const currentSunday = new Date(currentMonday);
  currentSunday.setDate(currentSunday.getDate() + 6);
  const currentMondayStr = formatDateISO(currentMonday);

  // Proyección de Asignación Semanal (Rotación Automática con rotación cíclica)
  const getAssignmentForWeek = (mondayStr: string): { assignment: WeeklyAssignment; isProjected: boolean } => {
    // 1. Revisar si hay una asignación explícita guardada para esta semana
    const explicit = weeklyAssignments.find((a) => a.weekStart === mondayStr);
    if (explicit) {
      return { assignment: explicit, isProjected: false };
    }

    // 2. Buscar la semana base anterior más cercana
    const baseAssignment = weeklyAssignments
      .filter((a) => a.isBase && a.weekStart <= mondayStr)
      .sort((a, b) => b.weekStart.localeCompare(a.weekStart))[0];

    const fallbackBase =
      baseAssignment ||
      weeklyAssignments.filter((a) => a.isBase).sort((a, b) => a.weekStart.localeCompare(b.weekStart))[0];

    if (!fallbackBase || shifts.length === 0 || workers.length === 0) {
      // Fallback simple 1:1
      const defaultAssign: Record<string, string> = {};
      shifts.forEach((s, idx) => {
        if (workers[idx]) defaultAssign[s.id] = workers[idx].id;
      });
      return {
        assignment: { id: `wa-proj-${mondayStr}`, weekStart: mondayStr, assignments: defaultAssign, isBase: false },
        isProjected: true,
      };
    }

    // Cálculo matemático de rotación cíclica: diferencia en semanas
    const baseDate = new Date(fallbackBase.weekStart + "T12:00:00");
    const targetDate = new Date(mondayStr + "T12:00:00");
    const diffWeeks = Math.round((targetDate.getTime() - baseDate.getTime()) / (7 * 24 * 60 * 60 * 1000));

    // Trabajadores en el orden de la asignación base
    const baseWorkers = shifts.map((s) => fallbackBase.assignments[s.id]).filter(Boolean);

    // Filtrar trabajadores en vacaciones durante esta semana
    const targetMondayDate = new Date(mondayStr + "T12:00:00");
    const targetSundayDate = new Date(targetMondayDate);
    targetSundayDate.setDate(targetSundayDate.getDate() + 6);
    const targetSundayStr = formatDateISO(targetSundayDate);

    const activeWorkers = baseWorkers.filter((wId) => {
      return !vacations.some((v) => v.workerId === wId && v.startDate <= targetSundayStr && v.endDate >= mondayStr);
    });

    const activeCount = activeWorkers.length > 0 ? activeWorkers.length : baseWorkers.length;
    const pool = activeWorkers.length > 0 ? activeWorkers : baseWorkers;

    // Desplazamiento rotativo a la izquierda
    const offset = ((diffWeeks % activeCount) + activeCount) % activeCount;
    const rotatedWorkers = [...pool.slice(offset), ...pool.slice(0, offset)];

    const projectedAssignments: Record<string, string> = {};
    shifts.forEach((s, i) => {
      if (i < rotatedWorkers.length) {
        projectedAssignments[s.id] = rotatedWorkers[i];
      }
    });

    return {
      assignment: {
        id: `wa-proj-${mondayStr}`,
        weekStart: mondayStr,
        assignments: projectedAssignments,
        isBase: false,
      },
      isProjected: true,
    };
  };

  const activeWeekData = getAssignmentForWeek(currentMondayStr);
  const activeAssignment = activeWeekData.assignment;
  const isProjected = activeWeekData.isProjected;
  const isBase = !!activeAssignment.isBase;

  // Abrir modal de edición para la semana activa
  const handleOpenEditWeek = (weekStartStr: string = currentMondayStr) => {
    setEditingWeekStart(weekStartStr);
    const existing = weeklyAssignments.find((a) => a.weekStart === weekStartStr);
    if (existing) {
      setTempAssignments({ ...existing.assignments });
      setTempIsBase(!!existing.isBase);
    } else {
      const proj = getAssignmentForWeek(weekStartStr);
      setTempAssignments({ ...proj.assignment.assignments });
      setTempIsBase(false);
    }
    setIsEditWeekModalOpen(true);
  };

  const handleSaveWeekAssignment = () => {
    const updated = weeklyAssignments.filter((a) => a.weekStart !== editingWeekStart);
    const newEntry: WeeklyAssignment = {
      id: `wa-${editingWeekStart}`,
      weekStart: editingWeekStart,
      assignments: tempAssignments,
      isBase: tempIsBase,
    };
    updated.push(newEntry);
    saveWeeklyAssignments(updated);
    setIsEditWeekModalOpen(false);
  };

  const handleResetToAuto = (weekStartStr: string) => {
    const updated = weeklyAssignments.filter((a) => a.weekStart !== weekStartStr);
    saveWeeklyAssignments(updated);
  };

  // Gestión de Trabajadores
  const handleAddWorker = () => {
    if (!newWorkerName.trim()) return;
    const newW: Worker = {
      id: `w-${Date.now()}`,
      name: newWorkerName.trim(),
      color: newWorkerColor,
      order: workers.length,
    };
    saveWorkers([...workers, newW]);
    setNewWorkerName("");
  };

  const handleDeleteWorker = (id: string) => {
    if (workers.length <= 4) {
      alert("Se requiere un mínimo de 4 técnicos para cubrir la rotación completa de los 4 turnos.");
      return;
    }
    if (confirm("¿Estás seguro de eliminar este técnico?")) {
      saveWorkers(workers.filter((w) => w.id !== id));
    }
  };

  // Gestión de Vacaciones
  const handleAddVacation = () => {
    if (!vacationWorkerId || !vacationStart || !vacationEnd) {
      alert("Por favor completa el técnico y las fechas de inicio y fin.");
      return;
    }
    const newVac: Vacation = {
      id: `vac-${Date.now()}`,
      workerId: vacationWorkerId,
      startDate: vacationStart,
      endDate: vacationEnd,
    };
    saveVacations([...vacations, newVac]);
    setVacationWorkerId("");
    setVacationStart("");
    setVacationEnd("");
  };

  const handleDeleteVacation = (id: string) => {
    saveVacations(vacations.filter((v) => v.id !== id));
  };

  // Copia del reporte WhatsApp
  const handleCopyReport = () => {
    const startFmt = currentMonday.toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" });
    const endFmt = currentSunday.toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" });

    let text = `📅 *CRONOGRAMA DE GUARDIAS Y TURNOS — OPERACIONES*\n`;
    text += `🏢 *Departamento:* Operaciones de Red\n`;
    text += `📆 *Semana:* ${startFmt} al ${endFmt}\n\n`;

    shifts.forEach((shift) => {
      const assignedWorkerId = activeAssignment.assignments[shift.id];
      const worker = workers.find((w) => w.id === assignedWorkerId);
      const scheduleSummary = formatScheduleSummary(shift.schedule);

      text += `• *${shift.name} (${shift.badge}):*\n`;
      text += `  👤 Responsable: *${worker ? worker.name : "Sin asignar"}*\n`;
      text += `  🕒 Horario: ${scheduleSummary}\n\n`;
    });

    text += `📡 _Power Link OS — Gestión Operativa_`;

    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
  };

  // Matriz de las próximas 6 semanas
  const matrixWeeks = Array.from({ length: 6 }).map((_, idx) => {
    const monday = getSelectedMonday(weekOffset + idx);
    const sunday = new Date(monday);
    sunday.setDate(sunday.getDate() + 6);
    const monStr = formatDateISO(monday);
    const data = getAssignmentForWeek(monStr);
    return {
      monday,
      sunday,
      monStr,
      assignment: data.assignment,
      isProjected: data.isProjected,
      isBase: !!data.assignment.isBase,
    };
  });

  return (
    <div className="space-y-6 animate-fade">
      {/* Encabezado Principal */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black tracking-tight text-foreground">
              Cronograma de Guardias y Turnos
            </h1>
            <Badge variant="gold">Operaciones de Red</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Matriz de rotación automática cíclica, cobertura de fin de semana y sincronización con WhatsApp.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsManageWorkersModalOpen(true)}
            className="gap-1.5 text-xs font-bold"
          >
            <Users className="h-3.5 w-3.5 text-primary" />
            <span>Técnicos ({workers.length})</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsVacationsModalOpen(true)}
            className="gap-1.5 text-xs font-bold"
          >
            <Umbrella className="h-3.5 w-3.5 text-amber-400" />
            <span>Vacaciones ({vacations.length})</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsDefineShiftsModalOpen(true)}
            className="gap-1.5 text-xs font-bold"
          >
            <Settings className="h-3.5 w-3.5 text-primary" />
            <span>Definir Turnos</span>
          </Button>

          <Button
            onClick={handleCopyReport}
            className="gap-2 border border-emerald-500/40 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 font-bold"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 text-emerald-400" />
                <span>¡Copiado para WhatsApp!</span>
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                <span>Copiar WhatsApp</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Selector de Pestañas de Vista */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="inline-flex rounded-xl bg-muted/60 p-1 border border-border">
          <button
            onClick={() => setActiveTab("cards")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeTab === "cards" ? "bg-primary text-primary-foreground shadow" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Turnos de la Semana
          </button>
          <button
            onClick={() => setActiveTab("matrix")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeTab === "matrix" ? "bg-primary text-primary-foreground shadow" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Matriz de Rotación (Próximas Semanas)
          </button>
        </div>

        {/* Indicador de Estado de la Semana */}
        <div className="flex items-center gap-2 text-xs">
          {isBase ? (
            <Badge variant="gold" className="gap-1">
              <Sparkles className="h-3 w-3" /> Semana Base (Regla de rotación)
            </Badge>
          ) : isProjected ? (
            <Badge variant="outline" className="border-emerald-500/30 text-emerald-400 bg-emerald-500/10 gap-1">
              <RefreshCw className="h-3 w-3" /> Rotación Automática
            </Badge>
          ) : (
            <Badge variant="outline" className="border-blue-500/30 text-blue-400 bg-blue-500/10 gap-1">
              <Edit2 className="h-3 w-3" /> Asignación Manual
            </Badge>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleOpenEditWeek(currentMondayStr)}
            className="text-xs text-primary hover:text-primary underline-offset-4 hover:underline p-1 h-auto font-bold"
          >
            Editar Esta Semana
          </Button>
        </div>
      </div>

      {/* Controles de Semana */}
      <Card className="p-4 bg-card/70 backdrop-blur border-border">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-primary/10 border border-primary/20 text-primary">
              <CalendarDays className="h-5 w-5" />
            </div>
            <div>
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">
                Semana Operativa:
              </span>
              <span className="text-base font-black text-foreground">
                {currentMonday.toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" })} —{" "}
                {currentSunday.toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" })}
              </span>
            </div>
            {weekOffset === 0 && (
              <Badge variant="gold" className="ml-2 font-black text-[11px]">
                Semana Actual
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWeekOffset((prev) => prev - 1)}
              className="gap-1 text-xs"
            >
              <ChevronLeft className="h-4 w-4" />
              <span>Semana Anterior</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWeekOffset(0)}
              className="text-xs font-bold"
            >
              Semana Actual
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWeekOffset((prev) => prev + 1)}
              className="gap-1 text-xs"
            >
              <span>Semana Siguiente</span>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>

      {/* TAB 1: Tarjetas de Turnos de la Semana */}
      {activeTab === "cards" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {shifts.map((shift) => {
            const assignedWorkerId = activeAssignment.assignments[shift.id];
            const worker = workers.find((w) => w.id === assignedWorkerId);
            const scheduleSummary = formatScheduleSummary(shift.schedule);

            return (
              <Card
                key={shift.id}
                className="border-border/80 hover:border-primary/50 transition-all p-5 flex flex-col justify-between group bg-card/60 backdrop-blur"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <Badge variant="gold" className="font-mono font-bold">
                      {shift.badge}
                    </Badge>
                    <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
                      {shift.name}
                    </span>
                  </div>

                  {worker ? (
                    <div className="flex items-center gap-3.5 my-4 p-3.5 rounded-xl bg-muted/40 border border-border group-hover:border-primary/30 transition-colors">
                      <div
                        className="h-11 w-11 rounded-full flex items-center justify-center text-white font-black text-sm shadow-md ring-2 ring-background shrink-0"
                        style={{ backgroundColor: worker.color }}
                      >
                        {worker.name.slice(0, 2).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-sm font-black text-foreground truncate">{worker.name}</h3>
                        <p className="text-[11px] text-muted-foreground">Técnico Asignado</p>
                      </div>
                    </div>
                  ) : (
                    <div className="my-4 p-4 rounded-xl border border-dashed border-destructive/40 bg-destructive/5 text-center">
                      <p className="text-xs font-bold text-destructive">Sin técnico asignado</p>
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t border-border/60">
                  <span className="text-[10px] font-bold text-muted-foreground uppercase block mb-1">
                    Horario de Cobertura:
                  </span>
                  <p className="text-xs font-medium text-foreground/80 leading-relaxed font-mono">
                    {scheduleSummary}
                  </p>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* TAB 2: Matriz de Rotación (Próximas Semanas) */}
      {activeTab === "matrix" && (
        <Card className="p-0 overflow-hidden border-border bg-card/60 backdrop-blur">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-foreground">Proyección de Rotación Continua</h3>
              <p className="text-xs text-muted-foreground">
                Vista panorámica de turnos asignados y automáticos para las próximas 6 semanas.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/50 border-b border-border font-bold text-muted-foreground uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="p-3 pl-4">Semana</th>
                  {shifts.map((s) => (
                    <th key={s.id} className="p-3">
                      {s.badge} — {s.name}
                    </th>
                  ))}
                  <th className="p-3">Modo</th>
                  <th className="p-3 text-right pr-4">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {matrixWeeks.map((mw) => {
                  const isCurrent = mw.monStr === currentMondayStr;
                  return (
                    <tr
                      key={mw.monStr}
                      className={`hover:bg-muted/30 transition-colors ${isCurrent ? "bg-primary/5 font-semibold" : ""}`}
                    >
                      <td className="p-3 pl-4 font-mono font-medium">
                        <div className="flex items-center gap-2">
                          <span>
                            {mw.monday.toLocaleDateString("es-ES", { day: "2-digit", month: "short" })} -{" "}
                            {mw.sunday.toLocaleDateString("es-ES", { day: "2-digit", month: "short" })}
                          </span>
                          {isCurrent && <Badge variant="gold" className="text-[9px] px-1.5 py-0">Actual</Badge>}
                        </div>
                      </td>

                      {shifts.map((s) => {
                        const wId = mw.assignment.assignments[s.id];
                        const w = workers.find((item) => item.id === wId);
                        return (
                          <td key={s.id} className="p-3">
                            {w ? (
                              <div className="flex items-center gap-2">
                                <span
                                  className="h-2.5 w-2.5 rounded-full inline-block shrink-0"
                                  style={{ backgroundColor: w.color }}
                                />
                                <span className="text-foreground font-medium">{w.name}</span>
                              </div>
                            ) : (
                              <span className="text-muted-foreground italic">Libre</span>
                            )}
                          </td>
                        );
                      })}

                      <td className="p-3">
                        {mw.isBase ? (
                          <Badge variant="gold" className="text-[10px]">Semana Base</Badge>
                        ) : mw.isProjected ? (
                          <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-400">
                            Automática
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-[10px] border-blue-500/30 text-blue-400">
                            Manual
                          </Badge>
                        )}
                      </td>

                      <td className="p-3 text-right pr-4">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenEditWeek(mw.monStr)}
                            className="h-7 px-2 text-[11px] gap-1"
                          >
                            <Edit2 className="h-3 w-3" />
                            <span>Editar</span>
                          </Button>
                          {!mw.isProjected && !mw.isBase && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleResetToAuto(mw.monStr)}
                              title="Restaurar a proyección automática"
                              className="h-7 px-2 text-[11px] text-muted-foreground hover:text-destructive"
                            >
                              <RefreshCw className="h-3 w-3" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* MODAL 1: Editar Asignación de Semana */}
      <Dialog open={isEditWeekModalOpen} onOpenChange={setIsEditWeekModalOpen}>
        <DialogContent className="max-w-md bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-lg font-black text-foreground flex items-center gap-2">
              <CalendarIcon className="h-5 w-5 text-primary" />
              <span>Modificar Semana ({editingWeekStart})</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <p className="text-xs text-muted-foreground">
              Asigna qué técnico cumplirá cada turno en esta semana. Si marcas como{" "}
              <strong>Semana Base</strong>, todas las semanas posteriores se proyectarán a partir de este orden.
            </p>

            <div className="space-y-3">
              {shifts.map((shift) => (
                <div key={shift.id} className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <span className="text-xs font-bold text-foreground block">
                      {shift.badge} — {shift.name}
                    </span>
                  </div>
                  <select
                    className="h-9 rounded-xl border border-border bg-card px-3 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    value={tempAssignments[shift.id] || ""}
                    onChange={(e) =>
                      setTempAssignments((prev) => ({ ...prev, [shift.id]: e.target.value }))
                    }
                  >
                    <option value="">-- Sin Asignar --</option>
                    {workers.map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>

            <div className="pt-3 border-t border-border flex items-center gap-2">
              <input
                type="checkbox"
                id="check-is-base"
                checked={tempIsBase}
                onChange={(e) => setTempIsBase(e.target.checked)}
                className="rounded border-border text-primary focus:ring-primary h-4 w-4 cursor-pointer"
              />
              <label htmlFor="check-is-base" className="text-xs font-bold text-foreground cursor-pointer">
                Fijar como Nueva Semana Base (Pivote de rotación)
              </label>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsEditWeekModalOpen(false)}>
              Cancelar
            </Button>
            <Button size="sm" onClick={handleSaveWeekAssignment} className="font-bold">
              Guardar Asignación
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 2: Gestión de Técnicos */}
      <Dialog open={isManageWorkersModalOpen} onOpenChange={setIsManageWorkersModalOpen}>
        <DialogContent className="max-w-lg bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-lg font-black text-foreground flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              <span>Personal de Operaciones</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Lista actual */}
            <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
              {workers.map((w) => (
                <div
                  key={w.id}
                  className="flex items-center justify-between p-2.5 rounded-xl border border-border bg-muted/20"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="h-6 w-6 rounded-full inline-block shadow-sm"
                      style={{ backgroundColor: w.color }}
                    />
                    <span className="text-sm font-bold text-foreground">{w.name}</span>
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteWorker(w.id)}
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>

            {/* Agregar técnico */}
            <div className="pt-3 border-t border-border space-y-2">
              <h4 className="text-xs font-bold text-muted-foreground uppercase">Agregar Técnico</h4>
              <div className="flex items-center gap-2">
                <Input
                  placeholder="Nombre y Apellido..."
                  value={newWorkerName}
                  onChange={(e) => setNewWorkerName(e.target.value)}
                  className="text-xs"
                />
                <input
                  type="color"
                  value={newWorkerColor}
                  onChange={(e) => setNewWorkerColor(e.target.value)}
                  className="h-10 w-12 rounded-xl border border-border p-1 bg-card cursor-pointer"
                />
                <Button size="sm" onClick={handleAddWorker} className="gap-1 font-bold shrink-0">
                  <Plus className="h-4 w-4" />
                  <span>Agregar</span>
                </Button>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button size="sm" onClick={() => setIsManageWorkersModalOpen(false)}>
              Listo
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 3: Definir Horarios de Turnos */}
      <Dialog open={isDefineShiftsModalOpen} onOpenChange={setIsDefineShiftsModalOpen}>
        <DialogContent className="max-w-2xl bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-lg font-black text-foreground flex items-center gap-2">
              <Settings className="h-5 w-5 text-primary" />
              <span>Configuración de Turnos y Horarios</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2 max-h-96 overflow-y-auto pr-2">
            <p className="text-xs text-muted-foreground">
              Define los horarios de cada turno por día de la semana. Los turnos definidos se mostrarán automáticamente en WhatsApp y en las tarjetas.
            </p>

            <div className="space-y-4">
              {shifts.map((shift, idx) => (
                <div key={shift.id} className="p-3 rounded-xl border border-border bg-muted/20 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="gold">{shift.badge}</Badge>
                      <Input
                        value={shift.name}
                        onChange={(e) => {
                          const updated = [...shifts];
                          updated[idx] = { ...shift, name: e.target.value };
                          setShifts(updated);
                        }}
                        className="h-8 text-xs font-bold w-64"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
                    {(["lun", "mar", "mie", "jue", "vie", "sab", "dom"] as (keyof ShiftSchedule)[]).map((day) => (
                      <div key={day} className="space-y-1">
                        <label className="text-[10px] font-bold uppercase text-muted-foreground block">
                          {day}
                        </label>
                        <Input
                          placeholder="Libre"
                          value={shift.schedule[day] || ""}
                          onChange={(e) => {
                            const updated = [...shifts];
                            updated[idx] = {
                              ...shift,
                              schedule: { ...shift.schedule, [day]: e.target.value || undefined },
                            };
                            setShifts(updated);
                          }}
                          className="h-7 text-xs font-mono"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsDefineShiftsModalOpen(false)}>
              Cerrar
            </Button>
            <Button
              size="sm"
              onClick={() => {
                saveShifts(shifts);
                setIsDefineShiftsModalOpen(false);
              }}
              className="font-bold"
            >
              Guardar Horarios
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 4: Vacaciones */}
      <Dialog open={isVacationsModalOpen} onOpenChange={setIsVacationsModalOpen}>
        <DialogContent className="max-w-lg bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-lg font-black text-foreground flex items-center gap-2">
              <Umbrella className="h-5 w-5 text-amber-400" />
              <span>Registro de Vacaciones</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <p className="text-xs text-muted-foreground">
              Los técnicos registrados en vacaciones serán excluidos automáticamente de la rotación semanal y los turnos críticos serán redistribuidos.
            </p>

            {/* Formulario nuevo */}
            <div className="p-3 rounded-xl border border-border bg-muted/20 space-y-3">
              <h4 className="text-xs font-bold text-foreground">Programar Periodo de Vacaciones</h4>
              <div className="space-y-2">
                <select
                  value={vacationWorkerId}
                  onChange={(e) => setVacationWorkerId(e.target.value)}
                  className="h-9 w-full rounded-xl border border-border bg-card px-3 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <option value="">-- Seleccionar Técnico --</option>
                  {workers.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
                </select>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] font-bold uppercase text-muted-foreground block mb-1">
                      Desde
                    </label>
                    <Input
                      type="date"
                      value={vacationStart}
                      onChange={(e) => setVacationStart(e.target.value)}
                      className="text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] font-bold uppercase text-muted-foreground block mb-1">
                      Hasta
                    </label>
                    <Input
                      type="date"
                      value={vacationEnd}
                      onChange={(e) => setVacationEnd(e.target.value)}
                      className="text-xs"
                    />
                  </div>
                </div>

                <Button size="sm" onClick={handleAddVacation} className="w-full font-bold">
                  Registrar Vacaciones
                </Button>
              </div>
            </div>

            {/* Lista actual */}
            <div className="space-y-2 max-h-48 overflow-y-auto">
              <h4 className="text-xs font-bold text-muted-foreground uppercase">Periodos Registrados</h4>
              {vacations.length === 0 ? (
                <p className="text-xs text-muted-foreground italic text-center py-3">
                  No hay vacaciones programadas actualmente.
                </p>
              ) : (
                vacations.map((v) => {
                  const w = workers.find((item) => item.id === v.workerId);
                  return (
                    <div
                      key={v.id}
                      className="flex items-center justify-between p-2.5 rounded-xl border border-border bg-card text-xs"
                    >
                      <div>
                        <span className="font-bold text-foreground block">{w?.name || "Técnico"}</span>
                        <span className="text-[11px] text-muted-foreground font-mono">
                          {v.startDate} al {v.endDate}
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteVacation(v.id)}
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <DialogFooter>
            <Button size="sm" onClick={() => setIsVacationsModalOpen(false)}>
              Cerrar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
