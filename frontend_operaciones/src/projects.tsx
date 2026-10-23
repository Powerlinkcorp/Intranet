"use client";

import React, { useState, useEffect } from "react";
import {
  FolderGit2,
  Plus,
  Search,
  CheckCircle2,
  Clock,
  AlertCircle,
  XCircle,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  History,
  Edit2,
  Trash2,
  RotateCcw,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

export interface ProjectHistoryItem {
  date: string;
  updateText: string;
  observation?: string;
}

export interface TrackingProject {
  id: string;
  departmentId?: string;
  name: string;
  description: string;
  updateText?: string;
  observation?: string;
  completed?: boolean;
  status?: "activo" | "completado" | "suspendido" | "cancelado";
  history?: ProjectHistoryItem[];
  createdAt?: string;
}

const STORAGE_KEY = "reportgen_v1_tracking_projects";

const DEFAULT_PROJECTS: TrackingProject[] = [
  {
    id: "proj-1",
    departmentId: "operaciones-de-redes",
    name: "Cursos de capacitación para el área de operaciones",
    description: "Serie de cursos dictados por Hermes para la capacitación de los trabajadores.",
    updateText: "Los cursos comienzan el 8 de agosto.",
    observation: "Coordinado con el equipo técnico y jefatura.",
    status: "activo",
    completed: false,
    history: [
      {
        date: "2026-08-01T10:00:00.000Z",
        updateText: "Cronograma de fechas recibido por el instructor.",
        observation: "Falta confirmar la sala de reuniones.",
      },
      {
        date: "2026-08-05T14:30:00.000Z",
        updateText: "Los cursos comienzan el 8 de agosto.",
        observation: "Coordinado con el equipo técnico y jefatura.",
      },
    ],
  },
  {
    id: "proj-2",
    departmentId: "operaciones-de-redes",
    name: "Creación de un servidor de CDN",
    description: "Se busca crear el servidor de CDN para un uso independiente de 360.",
    updateText: "Aún estamos a la espera de la respuesta de Netflix y Meta para poder seguir con las pruebas se estima un tiempo de espera de 10 días.",
    observation: "Revisión técnica de ancho de banda y peering completada.",
    status: "activo",
    completed: false,
    history: [
      {
        date: "2026-08-10T09:00:00.000Z",
        updateText: "Aún estamos a la espera de la respuesta de Netflix y Meta para poder seguir con las pruebas se estima un tiempo de espera de 10 días.",
      },
    ],
  },
  {
    id: "proj-3",
    departmentId: "operaciones-de-redes",
    name: "Reunión Líneas Digitel (Central Telefónica)",
    description: "Integración de Digitel para el servicio telefónico en las extensiones de las oficinas.",
    updateText: "Ya la central está operativa.",
    observation: "Se dio con el error y fue solucionado, solo queda un detalle con un mensaje erróneo que envía la central en forma de alerta.",
    status: "activo",
    completed: false,
    history: [
      {
        date: "2026-08-12T16:00:00.000Z",
        updateText: "Ya la central está operativa.",
        observation: "Se dio con el error y fue solucionado.",
      },
    ],
  },
  {
    id: "proj-4",
    departmentId: "operaciones-de-redes",
    name: "Prueba de Ciberseguridad",
    description: "Pruebas internas de la seguridad de la red interna y cortafuegos perimetrales.",
    updateText: "Se están realizando las correcciones indicadas por la empresa, una vez estén listas solicitaremos la re-revisión de nuestros servidores.",
    observation: "Se mitigaron puertos no requeridos en routers de borde.",
    status: "activo",
    completed: false,
    history: [
      {
        date: "2026-08-15T11:00:00.000Z",
        updateText: "Se están realizando las correcciones indicadas por la empresa, una vez estén listas solicitaremos la re-revisión de nuestros servidores.",
      },
    ],
  },
  {
    id: "proj-5",
    departmentId: "operaciones-de-redes",
    name: "Antena StarLink (Oficina C3 / C4)",
    description: "Solicitud de presidencia de una conexión StarLink para respaldo en oficina C3 en el C.C La Colina.",
    updateText: "En espera de decisión de presidencia.",
    observation: "Estamos a la espera de la decisión de presidencia para que soliciten el equipo; se recomienda intentar realizar la instalación de la antena en la oficina de planificación del C4.",
    status: "activo",
    completed: false,
    history: [
      {
        date: "2026-08-18T10:00:00.000Z",
        updateText: "En espera de decisión de presidencia.",
        observation: "Recomendado ubicar en oficina C4.",
      },
    ],
  },
  {
    id: "proj-6",
    departmentId: "operaciones-de-redes",
    name: "Actualización de servidores de tarjetas de arreglos",
    description: "Conexión del servidor para realizar la migración y tolerancia a fallos.",
    updateText: "Ya se instalaron los conectores nuevos; se coordina con Rene para comenzar los trabajos en los servidores y lograr colocarlos en espejo.",
    status: "activo",
    completed: false,
    history: [
      {
        date: "2026-08-20T17:00:00.000Z",
        updateText: "Ya se instalaron los conectores nuevos; se coordina con Rene para comenzar los trabajos en los servidores y lograr colocarlos en espejo.",
      },
    ],
  },
  {
    id: "proj-7",
    departmentId: "operaciones-de-redes",
    name: "Configuración de los servidores DNS",
    description: "Trabajos de DNS para mejorar la seguridad y velocidad de resolución de Power Link.",
    updateText: "Con la reunión realizada se va a generar un nuevo reporte con toda la información y se lograron aclarar más dudas sobre el panel de trabajo.",
    status: "activo",
    completed: false,
    history: [
      {
        date: "2026-08-22T15:00:00.000Z",
        updateText: "Con la reunión realizada se va a generar un nuevo reporte con toda la información y se lograron aclarar más dudas sobre el panel de trabajo.",
      },
    ],
  },
];

export function ProjectsModule() {
  const [projects, setProjects] = useState<TrackingProject[]>([]);
  const [activeTab, setActiveTab] = useState<"active" | "history">("active");
  const [searchQuery, setSearchQuery] = useState("");
  const [historyFilter, setHistoryFilter] = useState<string>("all");
  const [copied, setCopied] = useState(false);
  const [expandedHistories, setExpandedHistories] = useState<Record<string, boolean>>({});

  // Modales
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false);
  const [isFinalizeModalOpen, setIsFinalizeModalOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<TrackingProject | null>(null);

  // Formulario nuevo proyecto
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    updateText: "",
    observation: "",
  });

  // Formulario nueva actualización
  const [updateFormData, setUpdateFormData] = useState({
    updateText: "",
    observation: "",
  });

  // Cargar de localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setProjects(parsed);
          return;
        }
      }
      setProjects(DEFAULT_PROJECTS);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_PROJECTS));
    } catch (e) {
      console.error("Error al cargar tracking_projects:", e);
      setProjects(DEFAULT_PROJECTS);
    }
  }, []);

  const saveProjects = (updated: TrackingProject[]) => {
    setProjects(updated);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  };

  // Toggle historial desplegable
  const toggleHistory = (id: string) => {
    setExpandedHistories((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  // Agregar nuevo proyecto
  const handleCreateProject = () => {
    if (!formData.name.trim()) return;

    const newProject: TrackingProject = {
      id: `proj-${Date.now()}`,
      departmentId: "operaciones-de-redes",
      name: formData.name.trim(),
      description: formData.description.trim(),
      updateText: formData.updateText.trim(),
      observation: formData.observation.trim(),
      status: "activo",
      completed: false,
      createdAt: new Date().toISOString(),
      history: formData.updateText.trim()
        ? [
            {
              date: new Date().toISOString(),
              updateText: formData.updateText.trim(),
              observation: formData.observation.trim(),
            },
          ]
        : [],
    };

    const updated = [newProject, ...projects];
    saveProjects(updated);
    setFormData({ name: "", description: "", updateText: "", observation: "" });
    setIsAddModalOpen(false);
  };

  // Agregar actualización a proyecto existente
  const handleAddUpdate = () => {
    if (!selectedProject || !updateFormData.updateText.trim()) return;

    const now = new Date().toISOString();
    const newHistoryItem: ProjectHistoryItem = {
      date: now,
      updateText: updateFormData.updateText.trim(),
      observation: updateFormData.observation.trim(),
    };

    const updated = projects.map((p) => {
      if (p.id === selectedProject.id) {
        return {
          ...p,
          updateText: updateFormData.updateText.trim(),
          observation: updateFormData.observation.trim() || p.observation,
          history: [newHistoryItem, ...(p.history || [])],
        };
      }
      return p;
    });

    saveProjects(updated);
    setUpdateFormData({ updateText: "", observation: "" });
    setIsUpdateModalOpen(false);
    setSelectedProject(null);
  };

  // Finalizar proyecto (completado, suspendido, cancelado)
  const handleFinalizeProject = (status: "completado" | "suspendido" | "cancelado") => {
    if (!selectedProject) return;

    const updated = projects.map((p) => {
      if (p.id === selectedProject.id) {
        return {
          ...p,
          completed: true,
          status,
        };
      }
      return p;
    });

    saveProjects(updated);
    setIsFinalizeModalOpen(false);
    setSelectedProject(null);
  };

  // Reabrir proyecto
  const handleReopenProject = (id: string) => {
    const updated = projects.map((p) => {
      if (p.id === id) {
        return {
          ...p,
          completed: false,
          status: "activo" as const,
        };
      }
      return p;
    });
    saveProjects(updated);
  };

  // Eliminar proyecto
  const handleDeleteProject = (id: string) => {
    if (confirm("¿Estás seguro de eliminar este proyecto permanentemente?")) {
      saveProjects(projects.filter((p) => p.id !== id));
    }
  };

  // Copiar reporte para WhatsApp
  const handleCopyReport = () => {
    const activeProjects = projects.filter((p) => !p.completed);
    const today = new Date().toLocaleDateString("es-ES", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });

    let text = `📋 *SEGUIMIENTO DE PROYECTOS — OPERACIONES DE RED*\n`;
    text += `🏢 *Power Link OS*\n`;
    text += `📅 *Fecha:* ${today}\n\n`;

    if (activeProjects.length === 0) {
      text += `_No hay proyectos activos en este momento._\n\n`;
    } else {
      activeProjects.forEach((proj, index) => {
        text += `• *${index + 1}. ${proj.name}*\n`;
        if (proj.description) text += `  📝 _${proj.description}_\n`;
        if (proj.updateText) text += `  🔄 *Avance actual:* ${proj.updateText}\n`;
        if (proj.observation) text += `  ⚠️ *Observación:* ${proj.observation}\n`;
        text += `\n`;
      });
    }

    text += `📡 _Power Link OS — Gestión Operativa_`;

    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
  };

  // Filtrado de proyectos
  const filteredProjects = projects.filter((p) => {
    const isCompleted = !!p.completed;
    if (activeTab === "active" && isCompleted) return false;
    if (activeTab === "history" && !isCompleted) return false;

    if (activeTab === "history" && historyFilter !== "all") {
      if (p.status !== historyFilter) return false;
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = p.name.toLowerCase().includes(q);
      const matchDesc = p.description.toLowerCase().includes(q);
      const matchUpdate = (p.updateText || "").toLowerCase().includes(q);
      return matchName || matchDesc || matchUpdate;
    }

    return true;
  });

  const activeCount = projects.filter((p) => !p.completed).length;
  const completedCount = projects.filter((p) => p.status === "completado").length;
  const suspendedCount = projects.filter((p) => p.status === "suspendido").length;

  return (
    <div className="space-y-6 animate-fade">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black tracking-tight text-foreground">
              Proyectos Principales de Operaciones
            </h1>
            <Badge variant="gold">Seguimiento</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Control de iniciativas estratégicas, despliegues y seguimiento de infraestructura de red.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            onClick={() => setIsAddModalOpen(true)}
            className="gap-2 font-bold shadow-md"
          >
            <Plus className="h-4 w-4" />
            <span>Nuevo Proyecto</span>
          </Button>

          <Button
            variant="outline"
            onClick={handleCopyReport}
            className="gap-2 border-emerald-500/40 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 font-bold"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 text-emerald-400" />
                <span>¡Reporte Copiado!</span>
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

      {/* Tarjetas KPI de Resumen */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-4 bg-card/60 backdrop-blur border-border/80 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
              Proyectos en Curso
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-black text-foreground">{activeCount}</span>
              <span className="text-xs text-primary font-bold">Activos</span>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-primary/10 border border-primary/20 text-primary">
            <Clock className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 bg-card/60 backdrop-blur border-border/80 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
              Concluidos con Éxito
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-black text-emerald-400">{completedCount}</span>
              <span className="text-xs text-emerald-400 font-bold">Finalizados</span>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <CheckCircle2 className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 bg-card/60 backdrop-blur border-border/80 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
              Suspendidos / En Pausa
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-black text-amber-400">{suspendedCount}</span>
              <span className="text-xs text-amber-400 font-bold">Stand-by</span>
            </div>
          </div>
          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <AlertCircle className="h-5 w-5" />
          </div>
        </Card>
      </div>

      {/* Barra de Filtros y Búsqueda */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="inline-flex rounded-xl bg-muted/60 p-1 border border-border w-full sm:w-auto">
          <button
            onClick={() => setActiveTab("active")}
            className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-2 ${
              activeTab === "active"
                ? "bg-primary text-primary-foreground shadow"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <span>Proyectos Activos</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-background/30 font-mono">
              {activeCount}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("history")}
            className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-2 ${
              activeTab === "history"
                ? "bg-primary text-primary-foreground shadow"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <span>Historial Concluidos</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-background/30 font-mono">
              {projects.length - activeCount}
            </span>
          </button>
        </div>

        <div className="flex items-center gap-2.5 w-full sm:w-auto">
          {activeTab === "history" && (
            <select
              value={historyFilter}
              onChange={(e) => setHistoryFilter(e.target.value)}
              className="h-10 rounded-xl border border-border bg-card px-3 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <option value="all">Todos los estados</option>
              <option value="completado">Completados</option>
              <option value="suspendido">Suspendidos</option>
              <option value="cancelado">Cancelados</option>
            </select>
          )}

          <div className="relative flex-1 sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar proyecto o palabra clave..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-10 text-xs"
            />
          </div>
        </div>
      </div>

      {/* Lista de Proyectos */}
      {filteredProjects.length === 0 ? (
        <Card className="p-12 text-center border-border bg-card/60 backdrop-blur">
          <FolderGit2 className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-40" />
          <h3 className="text-base font-bold text-foreground">
            {activeTab === "active" ? "No hay proyectos activos" : "No hay proyectos en el historial"}
          </h3>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
            {activeTab === "active"
              ? "Usa el botón '+ Nuevo Proyecto' de arriba para registrar una iniciativa operativa."
              : "Los proyectos marcados como finalizados o cancelados aparecerán en esta sección."}
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredProjects.map((proj) => {
            const isHistoryOpen = !!expandedHistories[proj.id];
            const historyCount = proj.history ? proj.history.length : 0;

            return (
              <Card
                key={proj.id}
                className="p-5 border-border/80 hover:border-primary/50 transition-all bg-card/60 backdrop-blur space-y-4"
              >
                {/* Cabecera del Proyecto */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-black text-foreground">{proj.name}</h3>
                      {proj.status === "completado" ? (
                        <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 bg-emerald-500/10">
                          Completado
                        </Badge>
                      ) : proj.status === "suspendido" ? (
                        <Badge variant="outline" className="border-amber-500/40 text-amber-400 bg-amber-500/10">
                          Suspendido
                        </Badge>
                      ) : proj.status === "cancelado" ? (
                        <Badge variant="outline" className="border-destructive/40 text-destructive bg-destructive/10">
                          Cancelado
                        </Badge>
                      ) : (
                        <Badge variant="gold">En Curso</Badge>
                      )}
                    </div>
                    {proj.description && (
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {proj.description}
                      </p>
                    )}
                  </div>

                  {/* Acciones Rápidas */}
                  <div className="flex items-center gap-1.5 shrink-0 self-start">
                    {!proj.completed ? (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelectedProject(proj);
                            setIsUpdateModalOpen(true);
                          }}
                          className="h-8 text-xs gap-1 font-bold border-primary/30 text-primary bg-primary/5 hover:bg-primary/10"
                        >
                          <Plus className="h-3.5 w-3.5" />
                          <span>Actualizar Avance</span>
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setSelectedProject(proj);
                            setIsFinalizeModalOpen(true);
                          }}
                          className="h-8 text-xs text-muted-foreground hover:text-foreground font-semibold"
                        >
                          Finalizar...
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleReopenProject(proj.id)}
                        className="h-8 text-xs gap-1 font-bold border-emerald-500/30 text-emerald-400"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                        <span>Reabrir</span>
                      </Button>
                    )}

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteProject(proj.id)}
                      className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                      title="Eliminar Proyecto"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                {/* Último Avance y Observaciones */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-border/60">
                  <div className="p-3 rounded-xl bg-muted/30 border border-border/80">
                    <span className="text-[10px] font-bold text-primary uppercase tracking-wider block mb-1">
                      Última Actualización / Avance
                    </span>
                    <p className="text-xs text-foreground/90 font-medium leading-relaxed">
                      {proj.updateText || <span className="text-muted-foreground italic">Sin avances registrados aún.</span>}
                    </p>
                  </div>

                  <div className="p-3 rounded-xl bg-muted/30 border border-border/80">
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block mb-1">
                      Observaciones / Bloqueos
                    </span>
                    <p className="text-xs text-foreground/80 leading-relaxed">
                      {proj.observation || <span className="text-muted-foreground italic">Ninguna observación reportada.</span>}
                    </p>
                  </div>
                </div>

                {/* Historial Desplegable */}
                {historyCount > 0 && (
                  <div>
                    <button
                      onClick={() => toggleHistory(proj.id)}
                      className="flex items-center gap-1.5 text-xs font-bold text-primary hover:underline cursor-pointer"
                    >
                      <History className="h-3.5 w-3.5" />
                      <span>Historial de Actualizaciones ({historyCount})</span>
                      {isHistoryOpen ? (
                        <ChevronUp className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" />
                      )}
                    </button>

                    {isHistoryOpen && (
                      <div className="mt-3 space-y-2 pl-3 border-l-2 border-primary/30">
                        {proj.history?.map((h, hIdx) => {
                          const dateFmt = new Date(h.date).toLocaleDateString("es-ES", {
                            day: "2-digit",
                            month: "short",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          });
                          return (
                            <div key={hIdx} className="text-xs space-y-1 py-1">
                              <span className="text-[10px] font-mono text-muted-foreground font-semibold">
                                {dateFmt}
                              </span>
                              <p className="text-foreground font-medium">{h.updateText}</p>
                              {h.observation && (
                                <p className="text-[11px] text-muted-foreground italic">
                                  Obs: {h.observation}
                                </p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* MODAL 1: Nuevo Proyecto */}
      <Dialog open={isAddModalOpen} onOpenChange={setIsAddModalOpen}>
        <DialogContent className="max-w-md bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-lg font-black text-foreground flex items-center gap-2">
              <FolderGit2 className="h-5 w-5 text-primary" />
              <span>Registrar Nuevo Proyecto</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label className="text-xs font-bold text-foreground uppercase block mb-1">
                Nombre del Proyecto *
              </label>
              <Input
                placeholder="Ej. Servidor CDN Netflix & Meta..."
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="text-xs"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-foreground uppercase block mb-1">
                Descripción General
              </label>
              <Textarea
                placeholder="Objetivo y alcance de la actividad..."
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="text-xs min-h-[70px]"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-foreground uppercase block mb-1">
                Avance / Estatus Inicial
              </label>
              <Textarea
                placeholder="Avance al día de hoy..."
                value={formData.updateText}
                onChange={(e) => setFormData({ ...formData, updateText: e.target.value })}
                className="text-xs min-h-[60px]"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-foreground uppercase block mb-1">
                Observaciones
              </label>
              <Input
                placeholder="Requerimientos pendientes o bloqueos..."
                value={formData.observation}
                onChange={(e) => setFormData({ ...formData, observation: e.target.value })}
                className="text-xs"
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsAddModalOpen(false)}>
              Cancelar
            </Button>
            <Button size="sm" onClick={handleCreateProject} className="font-bold">
              Guardar Proyecto
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 2: Actualizar Avance */}
      <Dialog open={isUpdateModalOpen} onOpenChange={setIsUpdateModalOpen}>
        <DialogContent className="max-w-md bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-lg font-black text-foreground flex items-center gap-2">
              <Edit2 className="h-5 w-5 text-primary" />
              <span>Registrar Avance</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <p className="text-xs text-muted-foreground">
              Proyecto: <strong className="text-foreground">{selectedProject?.name}</strong>
            </p>

            <div>
              <label className="text-xs font-bold text-foreground uppercase block mb-1">
                Nuevo Avance *
              </label>
              <Textarea
                placeholder="Describe el avance logrado..."
                value={updateFormData.updateText}
                onChange={(e) =>
                  setUpdateFormData({ ...updateFormData, updateText: e.target.value })
                }
                className="text-xs min-h-[80px]"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-foreground uppercase block mb-1">
                Observación / Próximo Paso
              </label>
              <Input
                placeholder="Acciones a seguir o bloqueos..."
                value={updateFormData.observation}
                onChange={(e) =>
                  setUpdateFormData({ ...updateFormData, observation: e.target.value })
                }
                className="text-xs"
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsUpdateModalOpen(false)}>
              Cancelar
            </Button>
            <Button size="sm" onClick={handleAddUpdate} className="font-bold">
              Guardar Avance
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 3: Finalizar Proyecto */}
      <Dialog open={isFinalizeModalOpen} onOpenChange={setIsFinalizeModalOpen}>
        <DialogContent className="max-w-sm bg-card border-border text-center">
          <DialogHeader>
            <DialogTitle className="text-lg font-black text-foreground">
              Finalizar Proyecto
            </DialogTitle>
          </DialogHeader>

          <p className="text-xs text-muted-foreground py-2">
            Selecciona el estado final para{" "}
            <strong className="text-foreground">&quot;{selectedProject?.name}&quot;</strong>:
          </p>

          <div className="space-y-2 py-2">
            <Button
              className="w-full bg-emerald-500 hover:bg-emerald-600 text-white font-bold gap-2"
              onClick={() => handleFinalizeProject("completado")}
            >
              <CheckCircle2 className="h-4 w-4" />
              <span>Marcar como Completado</span>
            </Button>

            <Button
              variant="outline"
              className="w-full border-amber-500/40 text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 font-bold gap-2"
              onClick={() => handleFinalizeProject("suspendido")}
            >
              <AlertCircle className="h-4 w-4" />
              <span>Marcar como Suspendido</span>
            </Button>

            <Button
              variant="outline"
              className="w-full border-destructive/40 text-destructive bg-destructive/10 hover:bg-destructive/20 font-bold gap-2"
              onClick={() => handleFinalizeProject("cancelado")}
            >
              <XCircle className="h-4 w-4" />
              <span>Marcar como Cancelado</span>
            </Button>
          </div>

          <DialogFooter>
            <Button variant="ghost" size="sm" onClick={() => setIsFinalizeModalOpen(false)}>
              Cancelar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
