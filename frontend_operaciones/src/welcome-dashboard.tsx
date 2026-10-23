"use client";

import React from "react";
import {
  ClipboardList,
  Activity,
  CalendarDays,
  Globe2,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { type NavView } from "@/components/layout/sidebar";

interface WelcomeDashboardProps {
  onNavigate: (view: NavView) => void;
}

export function WelcomeDashboardModule({ onNavigate }: WelcomeDashboardProps) {
  const quickActions = [
    {
      title: "Bitácora de Actividades Diarias",
      desc: "Llenado ágil de tareas técnicas realizadas por departamento y copia para WhatsApp.",
      icon: ClipboardList,
      view: "daily-activities" as NavView,
      badge: "Uso Diario",
      badgeVariant: "gold" as const,
    },
    {
      title: "Dashboard de Eventos de Red",
      desc: "Monitoreo, registro de fallas, corte de fibras y KPIs de disponibilidad tipo Power BI.",
      icon: Activity,
      view: "events-dashboard" as NavView,
      badge: "Power BI",
      badgeVariant: "warning" as const,
    },
    {
      title: "Cronograma de Guardias",
      desc: "Turnos rotativos semanales (T1 al T4), asignaciones y reportes oficiales.",
      icon: CalendarDays,
      view: "guards" as NavView,
      badge: "Rotativo",
      badgeVariant: "info" as const,
    },
    {
      title: "Módulo OZmap & Cruce de Red",
      desc: "Integración de cajas, clientes de RUBPI y auditorías de conectividad sobre mapa.",
      icon: Globe2,
      view: "ozmap" as NavView,
      badge: "En Línea",
      badgeVariant: "success" as const,
    },
  ];

  return (
    <div className="space-y-8 animate-fade">
      {/* Banner Principal Power Link */}
      <div className="relative overflow-hidden rounded-3xl border border-primary/40 bg-gradient-to-br from-black via-zinc-950 to-zinc-900 p-8 shadow-2xl">
        <div className="absolute right-0 top-0 -mt-10 -mr-10 h-72 w-72 rounded-full bg-primary/10 blur-3xl pointer-events-none" />

        <div className="relative z-10 max-w-2xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-xs font-bold text-primary">
            <ShieldCheck className="h-4 w-4" />
            <span>Sistema Unificado Power Link OS</span>
          </div>

          <h1 className="text-3xl sm:text-4xl font-black tracking-tight text-white uppercase italic">
            Módulo de Operaciones de Red
          </h1>

          <p className="text-sm text-zinc-300 leading-relaxed">
            Plataforma centralizada para la supervisión de infraestructura, registro de actividades técnicas, gestión de turnos rotativos y análisis de eventos de red.
          </p>

          <div className="pt-2 flex flex-wrap gap-3">
            <Button
              onClick={() => onNavigate("daily-activities")}
              className="gap-2 shadow-lg shadow-primary/20 font-bold"
            >
              <ClipboardList className="h-4 w-4" />
              <span>Abrir Bitácora Diaria</span>
            </Button>

            <Button
              variant="outline"
              onClick={() => onNavigate("events-dashboard")}
              className="gap-2 border-border text-white hover:bg-muted font-bold"
            >
              <Activity className="h-4 w-4 text-primary" />
              <span>Ver Dashboard de Red</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Accesos Rápidos Principales */}
      <div>
        <div className="mb-4">
          <h2 className="text-lg font-black tracking-tight text-foreground uppercase">
            Accesos Rápidos del Módulo
          </h2>
          <p className="text-xs text-muted-foreground">
            Selecciona el submódulo de trabajo para el personal operativo.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {quickActions.map((qa, index) => {
            const Icon = qa.icon;
            return (
              <Card
                key={index}
                onClick={() => onNavigate(qa.view)}
                className="group cursor-pointer border-border/80 hover:border-primary/60 hover:shadow-xl hover:shadow-primary/5 transition-all p-6 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="rounded-2xl bg-primary/10 p-3 text-primary border border-primary/20 group-hover:scale-110 transition-transform">
                      <Icon className="h-6 w-6" />
                    </div>
                    <Badge variant={qa.badgeVariant}>{qa.badge}</Badge>
                  </div>

                  <h3 className="text-base font-bold text-foreground group-hover:text-primary transition-colors">
                    {qa.title}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                    {qa.desc}
                  </p>
                </div>

                <div className="mt-5 pt-4 border-t border-border/60 flex items-center justify-between text-xs font-bold text-primary group-hover:translate-x-1 transition-transform">
                  <span>Ingresar al submódulo</span>
                  <ArrowRight className="h-4 w-4" />
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
