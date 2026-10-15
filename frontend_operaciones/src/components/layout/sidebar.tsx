"use client";

import React from "react";
import {
  Home,
  ClipboardList,
  Activity,
  CalendarDays,
  FolderGit2,
  Zap,
  Globe2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export type NavView =
  | "welcome"
  | "daily-activities"
  | "events-dashboard"
  | "guards"
  | "projects"
  | "activities"
  | "ozmap";

interface SidebarProps {
  activeView: NavView;
  onSelectView: (view: NavView) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

interface NavItem {
  id: NavView;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  live?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

export function Sidebar({
  activeView,
  onSelectView,
  isCollapsed,
  onToggleCollapse,
  isMobileOpen,
  onCloseMobile,
}: SidebarProps) {
  const navSections: NavSection[] = [
    {
      title: "OPERACIONES DE RED",
      items: [
        { id: "welcome" as NavView, label: "Inicio / Resumen", icon: Home },
        { id: "daily-activities" as NavView, label: "Actividades Diarias", icon: ClipboardList },
        { id: "events-dashboard" as NavView, label: "Dashboard de Eventos", icon: Activity, badge: "Power BI" },
        { id: "guards" as NavView, label: "Cronograma de Guardias", icon: CalendarDays },
      ],
    },
    {
      title: "GESTIÓN & SEGUIMIENTO",
      items: [
        { id: "projects" as NavView, label: "Proyectos Principales", icon: FolderGit2 },
        { id: "activities" as NavView, label: "Requerimientos", icon: Zap },
      ],
    },
    {
      title: "RED & MIGRACIÓN",
      items: [
        { id: "ozmap" as NavView, label: "Módulo OZmap", icon: Globe2, live: true },
      ],
    },
  ];

  return (
    <>
      {/* Backdrop Móvil */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      {/* Contenedor del Sidebar */}
      <aside
        className={cn(
          "fixed top-16 bottom-0 left-0 z-40 flex flex-col border-r border-border bg-card/95 transition-all duration-300 lg:static backdrop-blur",
          isCollapsed ? "w-20" : "w-64",
          isMobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Encabezado colapsable Desktop */}
        <div className="hidden lg:flex items-center justify-between p-3 border-b border-border/60">
          {!isCollapsed && (
            <span className="text-[11px] font-black uppercase tracking-wider text-primary/80">
              Navegación
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleCollapse}
            className="h-8 w-8 p-0 text-muted-foreground hover:text-primary mx-auto"
            title={isCollapsed ? "Expandir menú (Ctrl+B)" : "Contraer menú (Ctrl+B)"}
          >
            {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </Button>
        </div>

        {/* Lista de Navegación */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          {navSections.map((sec, idx) => (
            <div key={idx} className="space-y-1">
              {!isCollapsed && (
                <div className="px-3 pb-1 text-[10px] font-black tracking-widest text-muted-foreground/70 uppercase">
                  {sec.title}
                </div>
              )}
              {sec.items.map((item) => {
                const Icon = item.icon;
                const isActive = activeView === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      onSelectView(item.id);
                      onCloseMobile();
                    }}
                    title={isCollapsed ? item.label : undefined}
                    className={cn(
                      "group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-xs font-semibold transition-all text-left",
                      isActive
                        ? "bg-primary text-primary-foreground font-bold shadow-md shadow-primary/20 scale-[1.01]"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-4 w-4 flex-shrink-0 transition-transform group-hover:scale-110",
                        isActive ? "text-primary-foreground" : "text-primary"
                      )}
                    />
                    {!isCollapsed && (
                      <span className="flex-1 truncate">{item.label}</span>
                    )}
                    {!isCollapsed && item.badge && (
                      <span
                        className={cn(
                          "rounded-md px-1.5 py-0.5 text-[9px] font-bold border",
                          isActive
                            ? "bg-black/20 text-black border-black/30"
                            : "bg-primary/10 text-primary border-primary/30"
                        )}
                      >
                        {item.badge}
                      </span>
                    )}
                    {!isCollapsed && item.live && (
                      <span className="flex items-center gap-1 rounded-md bg-emerald-500/10 px-1.5 py-0.5 text-[9px] font-bold text-emerald-400 border border-emerald-500/20">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        ONLINE
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        {/* Footer del Menú: Acceso rápido al Portal Principal */}
        <div className="p-3 border-t border-border/80">
          <a
            href="../../index.html"
            className={cn(
              "flex items-center gap-2 rounded-xl p-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors font-medium",
              isCollapsed && "justify-center"
            )}
            title="Ir al Portal Principal"
          >
            <ExternalLink className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
            {!isCollapsed && <span>Portal General</span>}
          </a>
        </div>
      </aside>
    </>
  );
}
