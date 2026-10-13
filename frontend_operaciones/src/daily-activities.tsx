"use client";

import React, { useState, useEffect } from "react";
import {
  ClipboardList,
  Plus,
  Copy,
  Check,
  Calendar,
  Search,
  Trash2,
  Edit2,
  Sparkles,
  Eye,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

interface DailyActivity {
  id: string;
  date: string;
  workerId?: string;
  workerName?: string;
  description: string;
  createdAt?: string;
}

const STORAGE_KEY = "reportgen_v1_daily_activities";

export function DailyActivitiesModule() {
  // Fecha seleccionada
  const [selectedDate, setSelectedDate] = useState<string>(() => {
    return new Date().toISOString().slice(0, 10);
  });
  
  // Mapa de todas las actividades: { "2026-09-25": [...] }
  const [allActivities, setAllActivities] = useState<Record<string, DailyActivity[]>>({});
  const [searchQuery, setSearchQuery] = useState("");
  
  // Modales
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [editingActivity, setEditingActivity] = useState<DailyActivity | null>(null);
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  // Form State
  const [formDescription, setFormDescription] = useState("");
  const [formWorkerName, setFormWorkerName] = useState("Dixon Iglesias");

  // Cargar datos compatibles con localStorage de la intranet
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          setAllActivities(parsed);
          return;
        } else if (Array.isArray(parsed)) {
          // Si era formato lista plana, convertir a diccionario por fecha
          const dict: Record<string, DailyActivity[]> = {};
          parsed.forEach((item: Record<string, unknown>) => {
            const d = (item.date as string) || (item.fecha as string) || new Date().toISOString().slice(0, 10);
            if (!dict[d]) dict[d] = [];
            dict[d].push({
              id: (item.id as string) || "act-" + Math.random(),
              date: d,
              workerName: (item.workerName as string) || (item.personal as string) || "Dixon Iglesias",
              description: (item.description as string) || (item.detalle as string) || "",
            });
          });
          setAllActivities(dict);
          return;
        }
      }
    } catch (e) {
      console.error("Error reading daily activities:", e);
    }

    // Datos iniciales de demostración
    const today = new Date().toISOString().slice(0, 10);
    const initialData: Record<string, DailyActivity[]> = {
      [today]: [
        {
          id: "act-1",
          date: today,
          workerName: "Dixon Iglesias",
          description: "Nombrado y verificación de puerto 11 (tarjeta 13 - CMDP) y puertos 8 y 9 (tarjeta 4 - Tibisay).",
        },
        {
          id: "act-2",
          date: today,
          workerName: "Rayner Revette",
          description: "Creación de VLANs 1045 y 1046 para plan corporativo de 600 Mb en HUB El Valle.",
        },
        {
          id: "act-3",
          date: today,
          workerName: "Brando Carrero",
          description: "Despliegue y pruebas de balanceo de tráfico hacia nuevo router de borde en Data Center.",
        },
        {
          id: "act-4",
          date: today,
          workerName: "Ivan Camacho",
          description: "Acompañamiento a cuadrilla de empalme en corte de fibra troncal tramo San José.",
        },
      ],
    };

    setAllActivities(initialData);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(initialData));
  }, []);

  const saveActivitiesMap = (map: Record<string, DailyActivity[]>) => {
    setAllActivities(map);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  };

  // Actividades del día actual
  const currentDayActivities = allActivities[selectedDate] || [];

  // Filtrado por buscador
  const filteredActivities = currentDayActivities.filter((act) =>
    act.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Abrir modal de creación
  const handleOpenCreateModal = () => {
    setEditingActivity(null);
    setFormDescription("");
    setIsFormModalOpen(true);
  };

  // Abrir modal de edición
  const handleOpenEditModal = (act: DailyActivity) => {
    setEditingActivity(act);
    setFormDescription(act.description);
    setFormWorkerName(act.workerName || "Dixon Iglesias");
    setIsFormModalOpen(true);
  };

  // Guardar actividad (nueva o editada)
  const handleSaveActivity = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formDescription.trim()) return;

    const copy = { ...allActivities };
    if (!copy[selectedDate]) copy[selectedDate] = [];

    if (editingActivity) {
      // Editar
      copy[selectedDate] = copy[selectedDate].map((a) =>
        a.id === editingActivity.id
          ? {
              ...a,
              description: formDescription.trim(),
              workerName: formWorkerName,
            }
          : a
      );
    } else {
      // Crear nueva
      const newAct: DailyActivity = {
        id: "dact-" + Date.now(),
        date: selectedDate,
        workerName: formWorkerName,
        description: formDescription.trim(),
        createdAt: new Date().toISOString(),
      };
      copy[selectedDate].push(newAct);
    }

    saveActivitiesMap(copy);
    setIsFormModalOpen(false);
  };

  // Eliminar
  const handleDeleteActivity = (id: string) => {
    if (confirm("¿Deseas eliminar este registro de actividad?")) {
      const copy = { ...allActivities };
      if (copy[selectedDate]) {
        copy[selectedDate] = copy[selectedDate].filter((a) => a.id !== id);
        if (copy[selectedDate].length === 0) {
          delete copy[selectedDate];
        }
        saveActivitiesMap(copy);
      }
    }
  };

  // Generador de Reporte WhatsApp (Estrictamente SIN nombres de responsables)
  const generateWhatsAppText = () => {
    const acts = allActivities[selectedDate] || [];
    const dateFormatted = new Date(selectedDate + "T12:00:00").toLocaleDateString("es-ES", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });

    let text = `⚡ *REPORTE DE ACTIVIDADES DIARIAS*\n`;
    text += `🏢 *Departamento:* Operaciones de Redes\n`;
    text += `📅 *Fecha:* ${dateFormatted.charAt(0).toUpperCase() + dateFormatted.slice(1)}\n\n`;
    text += `📋 *Actividades Realizadas:*\n`;

    if (acts.length === 0) {
      text += `_No se registraron actividades para este día._\n`;
    } else {
      acts.forEach((act) => {
        text += `• ${act.description}\n`;
      });
    }

    text += `\n✅ *Estado General:* Actividades técnicas ejecutadas y validadas.\n`;
    text += `📡 _Power Link OS — Operaciones de Red_`;

    return text;
  };

  const copyToClipboard = () => {
    const text = generateWhatsAppText();
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
  };

  // Atajos de fecha
  const setToday = () => setSelectedDate(new Date().toISOString().slice(0, 10));
  const setYesterday = () => {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    setSelectedDate(d.toISOString().slice(0, 10));
  };

  return (
    <div className="space-y-6 animate-fade">
      {/* Encabezado del Módulo */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black tracking-tight text-foreground">
              Bitácora de Actividades Diarias
            </h1>
            <Badge variant="gold">Consolidado General</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Registro diario de labores de campo, core y soporte técnico para el reporte departamental.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            onClick={handleOpenCreateModal}
            className="gap-2 shadow-lg shadow-primary/20 font-bold"
          >
            <Plus className="h-4 w-4" />
            <span>Registrar Actividad</span>
          </Button>

          <Button
            variant="outline"
            onClick={() => setIsPreviewModalOpen(true)}
            className="gap-2 border-border text-foreground hover:bg-muted font-bold"
          >
            <Eye className="h-4 w-4 text-primary" />
            <span>Ver Reporte</span>
          </Button>

          <Button
            variant="outline"
            onClick={copyToClipboard}
            className="gap-2 border-emerald-500/40 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 font-bold"
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

      {/* Controles de Fecha y Búsqueda */}
      <Card className="p-4 bg-card/60 backdrop-blur border-border/80">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
            <Calendar className="h-5 w-5 text-primary flex-shrink-0" />
            <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
              Fecha:
            </span>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-pointer"
            />
            <Button variant="outline" size="sm" onClick={setToday} className="text-xs font-bold h-8">
              Hoy
            </Button>
            <Button variant="outline" size="sm" onClick={setYesterday} className="text-xs font-bold h-8">
              Ayer
            </Button>
          </div>

          <div className="relative w-full md:w-80">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Buscar en las actividades de este día..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-xl border border-border bg-background pl-9 pr-4 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>
        </div>
      </Card>

      {/* Tabla de Actividades */}
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border/60 py-4 bg-muted/20">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-primary" />
              <span>
                Actividades Realizadas ({filteredActivities.length})
              </span>
            </CardTitle>
            <span className="text-xs font-bold text-primary">
              {new Date(selectedDate + "T12:00:00").toLocaleDateString("es-ES", {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </span>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {filteredActivities.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12 text-center">
              <div className="rounded-full bg-primary/10 p-4 text-primary mb-3">
                <Sparkles className="h-8 w-8" />
              </div>
              <h3 className="text-base font-bold text-foreground">
                No hay actividades registradas para esta fecha
              </h3>
              <p className="text-xs text-muted-foreground max-w-sm mt-1 mb-4 leading-relaxed">
                Ingresa los detalles de los trabajos técnicos ejecutados durante el día.
              </p>
              <Button size="sm" onClick={handleOpenCreateModal}>
                + Agregar Primera Actividad
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16 text-center">#</TableHead>
                  <TableHead>Detalle de la Actividad Realizada</TableHead>
                  <TableHead className="w-40">Registrado Por</TableHead>
                  <TableHead className="w-24 text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredActivities.map((act, index) => (
                  <TableRow key={act.id}>
                    <TableCell className="font-mono text-xs font-bold text-center text-primary">
                      {index + 1}
                    </TableCell>
                    <TableCell className="text-xs font-medium text-foreground leading-relaxed">
                      {act.description}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1.5 font-semibold">
                        <User className="h-3.5 w-3.5 text-primary/70" />
                        {act.workerName || "Operaciones"}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-primary"
                          onClick={() => handleOpenEditModal(act)}
                          title="Editar"
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                          onClick={() => handleDeleteActivity(act.id)}
                          title="Eliminar"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* MODAL: REGISTRAR / EDITAR ACTIVIDAD */}
      <Dialog open={isFormModalOpen} onOpenChange={setIsFormModalOpen}>
        <DialogContent className="max-w-md">
          <form onSubmit={handleSaveActivity}>
            <DialogHeader>
              <DialogTitle>
                <ClipboardList className="h-5 w-5 text-primary" />
                <span>{editingActivity ? "Editar Actividad" : "Registrar Actividad Diaria"}</span>
              </DialogTitle>
              <DialogDescription>
                Ingresa únicamente lo que se realizó. No es necesario colocar nombres en el texto de la actividad.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4 text-xs">
              <div>
                <label className="font-bold text-muted-foreground block mb-1.5">
                  Responsable Técnico:
                </label>
                <select
                  value={formWorkerName}
                  onChange={(e) => setFormWorkerName(e.target.value)}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 cursor-pointer"
                >
                  <option value="Dixon Iglesias">Dixon Iglesias</option>
                  <option value="Rayner Revette">Rayner Revette</option>
                  <option value="Brando Carrero">Brando Carrero</option>
                  <option value="Ivan Camacho">Ivan Camacho</option>
                </select>
                <p className="text-[10px] text-muted-foreground mt-1">
                  * Este dato es solo para auditoría interna; no saldrá en el reporte de WhatsApp.
                </p>
              </div>

              <div>
                <label className="font-bold text-muted-foreground block mb-1.5">
                  Detalle de la Actividad:
                </label>
                <textarea
                  required
                  rows={4}
                  placeholder="Describe la labor realizada (ej. Fusión de 8 hilos en troncal San José, reemplazo de patchcord...)"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  className="w-full rounded-xl border border-border bg-background p-3 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none leading-relaxed"
                />
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setIsFormModalOpen(false)}>
                Cancelar
              </Button>
              <Button type="submit">
                {editingActivity ? "Guardar Cambios" : "Agregar Actividad"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* MODAL: VISTA PREVIA DEL REPORTE WHATSAPP */}
      <Dialog open={isPreviewModalOpen} onOpenChange={setIsPreviewModalOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              <Eye className="h-5 w-5 text-primary" />
              <span>Vista Previa del Reporte de WhatsApp</span>
            </DialogTitle>
            <DialogDescription>
              Este es el texto exacto que se copiará al portapapeles para el grupo de Operaciones.
            </DialogDescription>
          </DialogHeader>

          <div className="py-3">
            <div className="p-4 rounded-2xl bg-zinc-950 border border-primary/30 text-xs font-mono text-zinc-200 whitespace-pre-wrap leading-relaxed shadow-inner max-h-96 overflow-y-auto">
              {generateWhatsAppText()}
            </div>
          </div>

          <DialogFooter className="flex justify-between items-center">
            <Button variant="outline" onClick={() => setIsPreviewModalOpen(false)}>
              Cerrar
            </Button>
            <Button onClick={copyToClipboard} className="gap-2 font-bold">
              {copied ? (
                <>
                  <Check className="h-4 w-4 text-black" />
                  <span>¡Copiado!</span>
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4" />
                  <span>Copiar al Portapapeles</span>
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
