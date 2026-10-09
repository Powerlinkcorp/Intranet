import React from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { EventsDashboardModule } from './events-dashboard'
import { OzmapModule } from './ozmap'

function App() {
  return (
    <div className="min-h-screen bg-background p-4 sm:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Módulo de Operaciones</h1>
          <p className="text-slate-500 mt-1">Gestión de eventos de red y validación de cajas Ozmap.</p>
        </div>
        
        <Tabs defaultValue="eventos" className="w-full">
          <TabsList className="grid w-full grid-cols-2 max-w-[400px]">
            <TabsTrigger value="eventos">Eventos de Red</TabsTrigger>
            <TabsTrigger value="ozmap">Validador Ozmap</TabsTrigger>
          </TabsList>
          
          <TabsContent value="eventos" className="mt-6 border-none p-0 outline-none">
            <EventsDashboardModule />
          </TabsContent>
          
          <TabsContent value="ozmap" className="mt-6 border-none p-0 outline-none">
            <OzmapModule />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

export default App
