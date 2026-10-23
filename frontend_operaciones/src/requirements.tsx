"use client";

import React, { useState, useEffect } from "react";
import {
  Zap,
  Plus,
  CheckCircle2,
  Circle,
  Copy,
  Check,
  Trash2,
  FolderPlus,
  AlertTriangle,
  Clock,
  Sparkles,
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

export interface RequirementItem {
  id: string;
  categoryId: string;
  name: string;
  status: "pending" | "completed";
  priority: "alta" | "media" | "baja";
  createdAt: string;
}

export interface RequirementCategory {
  id: string;
  name: string;
  description?: string;
}

const STORAGE_KEYS = {
  CATEGORIES: "reportgen_v1_req_categories",
  REQUIREMENTS: "reportgen_v1_requirements_v2",
};

const DEFAULT_CATEGORIES: RequirementCategory[] = [
  {
    id: "cat-1",
    name: "Actualización Tecnológica de Operaciones",
    description: "Equipamiento de medición, instrumental de campo y herramientas técnicas.",
  },
  {
    id: "cat-2",
    name: "Mejora de Infraestructura en Hubs",
    description: "Patch panels, conectores, ordenadores de fibra y respaldos energéticos.",
  },
  {
    id: "cat-3",
    name: "Plantas Eléctricas y Climatización",
    description: "Mantenimiento motogeneradores, bancos de baterías y aires acondicionados.",
  },
];

const DEFAULT_ITEMS: RequirementItem[] = [
  {
    id: "req-1",
    categoryId: "cat-1",
    name: "Bobina de lanzamiento de fibra óptica monomodo 1000m (FC/UPC)",
    status: "pending",
    priority: "alta",
    createdAt: "2026-08-10T12:00:00.000Z",
  },
  {
    id: "req-2",
    categoryId: "cat-1",
    name: "Power Meter óptico calibrado con rango de -70 a +10 dBm",
    status: "completed",
    priority: "media",
    createdAt: "2026-08-12T10:00:00.000Z",
  },
  {
    id: "req-3",
    categoryId: "cat-1",
    name: "Kit de limpieza de conectores (click cleaner 2.5mm y 1.25mm)",
    status: "completed",
    priority: "media",
    createdAt: "2026-08-15T15:00:00.000Z",
  },
  {
    id: "req-4",
    categoryId: "cat-2",
    name: "Patch cords SC/APC a SC/UPC simplex 3m (Lote 50 uds)",
    status: "pending",
    priority: "alta",
    createdAt: "2026-08-18T09:00:00.000Z",
  },
  {
    id: "req-5",
    categoryId: "cat-2",
    name: "Reemplazo de baterías de respaldo 12V 100Ah en Hub CMDP",
    status: "pending",
    priority: "alta",
    createdAt: "2026-08-20T11:00:00.000Z",
  },
  {
    id: "req-6",
    categoryId: "cat-3",
    name: "Servicio de mantenimiento preventivo y cambio de aceite motogenerador San José",
    status: "completed",
    priority: "alta",
    createdAt: "2026-08-22T08:30:00.000Z",
  },
  {
    id: "req-7",
    categoryId: "cat-3",
    name: "Carga de gas refrigerante R410A para A/A principal de Hub Central",
    status: "pending",
    priority: "media",
    createdAt: "2026-08-25T14:00:00.000Z",
  },
];

export function RequirementsModule() {
  const [categories, setCategories] = useState<RequirementCategory[]>([]);
  const [items, setItems] = useState<RequirementItem[]>([]);
  const [copied, setCopied] = useState(false);

  // Modales
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [isItemModalOpen, setIsItemModalOpen] = useState(false);
  const [targetCategoryId, setTargetCategoryId] = useState<string>("");

  // Formularios
  const [newCatName, setNewCatName] = useState("");
  const [newCatDesc, setNewCatDesc] = useState("");
  const [newItemName, setNewItemName] = useState("");
  const [newItemPriority, setNewItemPriority] = useState<"alta" | "media" | "baja">("media");

  // Cargar de localStorage
  useEffect(() => {
    try {
      const storedCats = localStorage.getItem(STORAGE_KEYS.CATEGORIES);
      if (storedCats) {
        const parsed = JSON.parse(storedCats);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setCategories(parsed);
        } else {
          setCategories(DEFAULT_CATEGORIES);
        }
      } else {
        setCategories(DEFAULT_CATEGORIES);
        localStorage.setItem(STORAGE_KEYS.CATEGORIES, JSON.stringify(DEFAULT_CATEGORIES));
      }

      const storedReqs = localStorage.getItem(STORAGE_KEYS.REQUIREMENTS);
      if (storedReqs) {
        const parsed = JSON.parse(storedReqs);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setItems(parsed);
        } else {
          setItems(DEFAULT_ITEMS);
        }
      } else {
        setItems(DEFAULT_ITEMS);
        localStorage.setItem(STORAGE_KEYS.REQUIREMENTS, JSON.stringify(DEFAULT_ITEMS));
      }
    } catch (e) {
      console.error("Error cargando requerimientos:", e);
      setCategories(DEFAULT_CATEGORIES);
      setItems(DEFAULT_ITEMS);
    }
  }, []);

  const saveCategories = (updated: RequirementCategory[]) => {
    setCategories(updated);
    localStorage.setItem(STORAGE_KEYS.CATEGORIES, JSON.stringify(updated));
  };

  const saveItems = (updated: RequirementItem[]) => {
    setItems(updated);
    localStorage.setItem(STORAGE_KEYS.REQUIREMENTS, JSON.stringify(updated));
  };

  // Toggle estado de requerimiento
  const toggleItemStatus = (id: string) => {
    const updated = items.map((item) => {
      if (item.id === id) {
        return {
          ...item,
          status: item.status === "completed" ? ("pending" as const) : ("completed" as const),
        };
      }
      return item;
    });
    saveItems(updated);
  };

  // Agregar categoría
  const handleCreateCategory = () => {
    if (!newCatName.trim()) return;
    const newCat: RequirementCategory = {
      id: `cat-${Date.now()}`,
      name: newCatName.trim(),
      description: newCatDesc.trim(),
    };
    saveCategories([...categories, newCat]);
    setNewCatName("");
    setNewCatDesc("");
    setIsCategoryModalOpen(false);
  };

  // Agregar requerimiento
  const handleCreateItem = () => {
    if (!newItemName.trim() || !targetCategoryId) return;
    const newItem: RequirementItem = {
      id: `req-${Date.now()}`,
      categoryId: targetCategoryId,
      name: newItemName.trim(),
      status: "pending",
      priority: newItemPriority,
      createdAt: new Date().toISOString(),
    };
    saveItems([...items, newItem]);
    setNewItemName("");
    setNewItemPriority("media");
    setIsItemModalOpen(false);
  };

  // Eliminar ítem
  const handleDeleteItem = (id: string) => {
    saveItems(items.filter((item) => item.id !== id));
  };

  // Eliminar categoría
  const handleDeleteCategory = (catId: string) => {
    if (confirm("¿Estás seguro de eliminar este grupo y todos sus requerimientos?")) {
      saveCategories(categories.filter((c) => c.id !== catId));
      saveItems(items.filter((item) => item.categoryId !== catId));
    }
  };

  // Copiar reporte WhatsApp
  const handleCopyReport = () => {
    const today = new Date().toLocaleDateString("es-ES", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });

    let text = `📦 *REQUERIMIENTOS Y COMPRAS — OPERACIONES DE RED*\n`;
    text += `🏢 *Power Link OS*\n`;
    text += `📅 *Fecha:* ${today}\n\n`;

    categories.forEach((cat) => {
      const catItems = items.filter((i) => i.categoryId === cat.id);
      if (catItems.length === 0) return;

      const completedCount = catItems.filter((i) => i.status === "completed").length;
      text += `📂 *${cat.name} (${completedCount}/${catItems.length})*\n`;

      catItems.forEach((item) => {
        const icon = item.status === "completed" ? "✅" : "⏳";
        const priorityTag = item.priority === "alta" && item.status !== "completed" ? " [URGENTE]" : "";
        text += `  ${icon} ${item.name}${priorityTag}\n`;
      });
      text += `\n`;
    });

    text += `📡 _Power Link OS — Gestión Operativa_`;

    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
  };

  const totalItems = items.length;
  const completedItems = items.filter((i) => i.status === "completed").length;
  const pendingItems = totalItems - completedItems;
  const urgentPending = items.filter((i) => i.status === "pending" && i.priority === "alta").length;

  return (
    <div className="space-y-6 animate-fade">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black tracking-tight text-foreground">
              Requerimientos y Compras de Red
            </h1>
            <Badge variant="gold">Gestión Operativa</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Control de insumos de fibra óptica, instrumental técnico, compras y mejoras de infraestructura.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="outline"
            onClick={() => setIsCategoryModalOpen(true)}
            className="gap-2 font-bold text-xs"
          >
            <FolderPlus className="h-4 w-4 text-primary" />
            <span>Nuevo Grupo</span>
          </Button>

          <Button
            variant="outline"
            onClick={handleCopyReport}
            className="gap-2 border-emerald-500/40 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 font-bold"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 text-emerald-400" />
                <span>¡Requerimientos Copiados!</span>
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

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card className="p-4 bg-card/60 backdrop-blur border-border/80 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
              Total Solicitudes
            </span>
            <span className="text-2xl font-black text-foreground mt-1 block">{totalItems}</span>
          </div>
          <div className="p-3 rounded-xl bg-primary/10 border border-primary/20 text-primary">
            <Zap className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 bg-card/60 backdrop-blur border-border/80 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
              Pendientes
            </span>
            <span className="text-2xl font-black text-amber-400 mt-1 block">{pendingItems}</span>
          </div>
          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <Clock className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 bg-card/60 backdrop-blur border-border/80 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
              Prioridad Urgente
            </span>
            <span className="text-2xl font-black text-destructive mt-1 block">{urgentPending}</span>
          </div>
          <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive">
            <AlertTriangle className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 bg-card/60 backdrop-blur border-border/80 flex items-center justify-between">
          <div>
            <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block">
              Completados / Recibidos
            </span>
            <span className="text-2xl font-black text-emerald-400 mt-1 block">{completedItems}</span>
          </div>
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <CheckCircle2 className="h-5 w-5" />
          </div>
        </Card>
      </div>

      {/* Grupos y Listas de Requerimientos */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {categories.map((cat) => {
          const catItems = items.filter((i) => i.categoryId === cat.id);
          const compCount = catItems.filter((i) => i.status === "completed").length;
          const percent = catItems.length > 0 ? Math.round((compCount / catItems.length) * 100) : 0;

          return (
            <Card
              key={cat.id}
              className="p-5 border-border/80 hover:border-primary/50 transition-all bg-card/60 backdrop-blur flex flex-col justify-between"
            >
              <div>
                {/* Cabecera del Grupo */}
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h3 className="text-base font-black text-foreground">{cat.name}</h3>
                    {cat.description && (
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                        {cat.description}
                      </p>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteCategory(cat.id)}
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive shrink-0"
                    title="Eliminar Grupo"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>

                {/* Barra de Progreso */}
                <div className="space-y-1.5 my-3">
                  <div className="flex items-center justify-between text-[11px] font-bold">
                    <span className="text-muted-foreground">Avance</span>
                    <span className="text-primary font-mono">{percent}% ({compCount}/{catItems.length})</span>
                  </div>
                  <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all duration-300 rounded-full"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                </div>

                {/* Checklist de Requerimientos */}
                <div className="space-y-2 my-4 max-h-72 overflow-y-auto pr-1">
                  {catItems.length === 0 ? (
                    <p className="text-xs text-muted-foreground italic text-center py-4">
                      No hay requerimientos en este grupo aún.
                    </p>
                  ) : (
                    catItems.map((item) => (
                      <div
                        key={item.id}
                        className={`flex items-start justify-between gap-2.5 p-2.5 rounded-xl border transition-colors ${
                          item.status === "completed"
                            ? "bg-muted/20 border-border/60 opacity-60"
                            : "bg-muted/40 border-border hover:border-primary/30"
                        }`}
                      >
                        <div
                          className="flex items-start gap-2.5 flex-1 min-w-0 cursor-pointer"
                          onClick={() => toggleItemStatus(item.id)}
                        >
                          <button
                            type="button"
                            className="mt-0.5 shrink-0 text-muted-foreground hover:text-primary transition-colors cursor-pointer"
                          >
                            {item.status === "completed" ? (
                              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                            ) : (
                              <Circle className="h-4 w-4" />
                            )}
                          </button>
                          <div className="min-w-0">
                            <span
                              className={`text-xs block leading-relaxed ${
                                item.status === "completed"
                                  ? "line-through text-muted-foreground"
                                  : "font-semibold text-foreground"
                              }`}
                            >
                              {item.name}
                            </span>
                            <div className="flex items-center gap-1.5 mt-1">
                              {item.priority === "alta" && (
                                <Badge variant="outline" className="text-[9px] px-1.5 py-0 border-destructive/40 text-destructive bg-destructive/10">
                                  Urgente
                                </Badge>
                              )}
                              {item.priority === "media" && (
                                <Badge variant="outline" className="text-[9px] px-1.5 py-0 border-amber-500/40 text-amber-400 bg-amber-500/10">
                                  Media
                                </Badge>
                              )}
                            </div>
                          </div>
                        </div>

                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteItem(item.id)}
                          className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive shrink-0"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Botón "+ Agregar Requerimiento" */}
              <div className="pt-3 border-t border-border/60">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setTargetCategoryId(cat.id);
                    setIsItemModalOpen(true);
                  }}
                  className="w-full text-xs font-bold gap-1.5 border-dashed border-border hover:border-primary/50"
                >
                  <Plus className="h-3.5 w-3.5 text-primary" />
                  <span>Agregar Requerimiento</span>
                </Button>
              </div>
            </Card>
          );
        })}
      </div>

      {/* MODAL 1: Nuevo Grupo */}
      <Dialog open={isCategoryModalOpen} onOpenChange={setIsCategoryModalOpen}>
        <DialogContent className="max-w-md bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-lg font-black text-foreground flex items-center gap-2">
              <FolderPlus className="h-5 w-5 text-primary" />
              <span>Nuevo Grupo de Requerimientos</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label className="text-xs font-bold text-foreground uppercase block mb-1">
                Nombre del Grupo *
              </label>
              <Input
                placeholder="Ej. Instrumental de Fibra Óptica..."
                value={newCatName}
                onChange={(e) => setNewCatName(e.target.value)}
                className="text-xs"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-foreground uppercase block mb-1">
                Descripción
              </label>
              <Input
                placeholder="Breve detalle del área o propósito..."
                value={newCatDesc}
                onChange={(e) => setNewCatDesc(e.target.value)}
                className="text-xs"
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsCategoryModalOpen(false)}>
              Cancelar
            </Button>
            <Button size="sm" onClick={handleCreateCategory} className="font-bold">
              Crear Grupo
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 2: Nuevo Requerimiento */}
      <Dialog open={isItemModalOpen} onOpenChange={setIsItemModalOpen}>
        <DialogContent className="max-w-md bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-lg font-black text-foreground flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <span>Agregar Requerimiento</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label className="text-xs font-bold text-foreground uppercase block mb-1">
                Descripción del Ítem / Material *
              </label>
              <Input
                placeholder="Ej. Patch cord LC-SC 5 metros..."
                value={newItemName}
                onChange={(e) => setNewItemName(e.target.value)}
                className="text-xs"
              />
            </div>

            <div>
              <label className="text-xs font-bold text-foreground uppercase block mb-1">
                Prioridad
              </label>
              <select
                value={newItemPriority}
                onChange={(e) => setNewItemPriority(e.target.value as "alta" | "media" | "baja")}
                className="h-10 w-full rounded-xl border border-border bg-card px-3 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                <option value="alta">Alta / Urgente</option>
                <option value="media">Media</option>
                <option value="baja">Baja</option>
              </select>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setIsItemModalOpen(false)}>
              Cancelar
            </Button>
            <Button size="sm" onClick={handleCreateItem} className="font-bold">
              Agregar Ítem
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
