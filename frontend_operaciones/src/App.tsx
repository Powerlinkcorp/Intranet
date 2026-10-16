import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { WelcomeDashboardModule } from "./welcome-dashboard"
import { DailyActivitiesModule } from "./daily-activities"
import { EventsDashboardModule } from "./events-dashboard"
import { GuardsScheduleModule } from "./guards-schedule"
import { ProjectsModule } from "./projects"
import { RequirementsModule } from "./requirements"
import { OzmapModule } from "./ozmap"
import { OzmapDatabaseModule } from "./ozmap-database"
import {
  Home,
  ClipboardList,
  Activity,
  CalendarDays,
  FolderGit2,
  Zap,
  Globe2,
  Database,
  Moon,
  Sun,
} from "lucide-react"

export type NavView =
  | "welcome"
  | "daily-activities"
  | "events-dashboard"
  | "guards"
  | "projects"
  | "activities"
  | "ozmap"
  | "ozmap-database"

interface NavTab {
  id: NavView
  label: string
  shortLabel: string
  icon: React.ComponentType<{ className?: string }>
}

const NAV_TABS: NavTab[] = [
  { id: "welcome", label: "Inicio / Resumen", shortLabel: "Inicio", icon: Home },
  { id: "daily-activities", label: "Actividades Diarias", shortLabel: "Actividades", icon: ClipboardList },
  { id: "events-dashboard", label: "Eventos de Red", shortLabel: "Eventos", icon: Activity },
  { id: "guards", label: "Cronograma de Guardias", shortLabel: "Guardias", icon: CalendarDays },
  { id: "projects", label: "Proyectos", shortLabel: "Proyectos", icon: FolderGit2 },
  { id: "activities", label: "Requerimientos", shortLabel: "Requerimientos", icon: Zap },
  { id: "ozmap", label: "Módulo OZmap", shortLabel: "OZmap", icon: Globe2 },
  { id: "ozmap-database", label: "Base de Datos OZmap", shortLabel: "BD OZmap", icon: Database },
]

function App() {
  const [activeView, setActiveView] = useState<NavView>(() => {
    if (typeof window !== "undefined") {
      const hash = window.location.hash.replace("#", "") as NavView
      if (NAV_TABS.some((t) => t.id === hash)) return hash
      const params = new URLSearchParams(window.location.search)
      const qTab = params.get("tab") as NavView
      if (NAV_TABS.some((t) => t.id === qTab)) return qTab
    }
    return "welcome"
  })

  const [isDark, setIsDark] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("theme")
      if (saved) return saved === "dark"
    }
    return true // Modo oscuro por defecto
  })

  // Escuchar cambios de hash en la URL (por ejemplo desde el menú de la Intranet)
  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace("#", "") as NavView
      if (NAV_TABS.some((t) => t.id === hash)) {
        setActiveView(hash)
      }
    }
    window.addEventListener("hashchange", handleHash)
    return () => window.removeEventListener("hashchange", handleHash)
  }, [])

  // Sincronizar clase 'dark' con documentElement
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark")
      localStorage.setItem("theme", "dark")
    } else {
      document.documentElement.classList.remove("dark")
      localStorage.setItem("theme", "light")
    }
  }, [isDark])

  // Escuchar cambios de tema desde el Sidebar de la Intranet
  useEffect(() => {
    const handleThemeChange = () => {
      const isDocDark = document.documentElement.classList.contains("dark")
      setIsDark(isDocDark)
    }
    window.addEventListener("theme-changed", handleThemeChange)
    return () => window.removeEventListener("theme-changed", handleThemeChange)
  }, [])

  const handleSelectView = (view: NavView) => {
    setActiveView(view)
    if (typeof window !== "undefined") {
      window.location.hash = view
    }
  }

  return (
    <div className={`min-h-screen bg-background text-foreground transition-colors duration-200 ${isDark ? "dark" : ""}`}>
      <div className="w-full max-w-[1920px] mx-auto p-3 sm:p-5 lg:p-7 space-y-6">
        
        {/* Barra Superior del Módulo con Selector de Vista */}
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4 pb-4 border-b border-border/80">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="h-3 w-3 rounded-full bg-primary animate-pulse" />
              <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-foreground uppercase italic">
                IntraPOWER <span className="text-primary not-italic font-bold">OS</span>
              </h1>
              <span className="text-xs px-2 py-0.5 rounded-full border border-primary/40 bg-primary/10 text-primary font-mono font-bold">
                Operaciones v2.1
              </span>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground mt-1">
              Plataforma unificada de ingeniería, monitoreo NOC, bitácora de red y validación de campo.
            </p>
          </div>
        </div>

        {/* Barra de Submódulos Horizontal (Pestañas Rápidas con Iconos) */}
        <div className="overflow-x-auto pb-1 -mx-2 px-2 scrollbar-none">
          <div className="flex items-center gap-1.5 min-w-max p-1.5 rounded-2xl bg-card/80 border border-border/80 shadow-xs backdrop-blur">
            {NAV_TABS.map((tab) => {
              const Icon = tab.icon
              const isActive = activeView === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => handleSelectView(tab.id)}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all cursor-pointer whitespace-nowrap ${
                    isActive
                      ? "bg-primary text-black font-bold shadow-md shadow-primary/20 scale-[1.02]"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                  }`}
                >
                  <Icon className={`h-4 w-4 ${isActive ? "text-black" : "text-primary"}`} />
                  <span className="hidden sm:inline">{tab.label}</span>
                  <span className="sm:hidden">{tab.shortLabel}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Contenedor del Submódulo Activo */}
        <div className="mt-4">
          {activeView === "welcome" && (
            <WelcomeDashboardModule onNavigate={handleSelectView} />
          )}

          {activeView === "daily-activities" && <DailyActivitiesModule />}

          {activeView === "events-dashboard" && <EventsDashboardModule />}

          {activeView === "guards" && <GuardsScheduleModule />}

          {activeView === "projects" && <ProjectsModule />}

          {activeView === "activities" && <RequirementsModule />}

          {activeView === "ozmap" && <OzmapModule />}

          {activeView === "ozmap-database" && (
            <OzmapDatabaseModule onNavigate={handleSelectView} />
          )}
        </div>
      </div>
    </div>
  )
}

export default App
