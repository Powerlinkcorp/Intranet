import sys

with open(r"c:\Users\wgallardo\Documents\Proyectos gravity\intranet\templates\integracion.html", "r", encoding="utf-8") as f:
    content = f.read()

# Buscamos la sección de conciliación financiera
start_tag = '<div id="seccionConciliacionFinanciera" class="bg-white rounded-xl shadow-xs border border-gray-200 p-6 mb-8 hidden">'
end_tag = '<!-- Listado Detallado de Clientes para Validación del Sistema -->'

if start_tag not in content or end_tag not in content:
    print("No se encontraron las etiquetas.")
    sys.exit(1)

parts = content.split(start_tag)
part2 = parts[1].split(end_tag)

original_table = part2[0]

new_html = """<div id="seccionConciliacionFinanciera" class="bg-white rounded-xl shadow-xs border border-gray-200 p-6 mb-8 hidden">
                <div class="flex items-center justify-between border-b border-gray-100 pb-3 mb-4">
                    <h3 class="text-xl font-bold text-gray-800 flex items-center gap-2">
                        <i class="fa-solid fa-file-invoice-dollar text-indigo-600"></i> Variación / Conciliación Financiera
                    </h3>
                    <span class="text-xs font-semibold bg-indigo-50 text-indigo-700 px-3 py-1 rounded-full border border-indigo-100">
                        Base vs Hoy
                    </span>
                </div>
                <p class="text-sm text-gray-500 mb-5">Este desglose explica la diferencia matemática entre el ingreso facturado en la <b>Base Seleccionada (Ayer o Día 1)</b> y el monto total de <b>Hoy</b>.</p>
                
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- CORPORATIVOS -->
                    <div class="bg-white overflow-hidden rounded-xl border border-gray-200 shadow-xs h-fit">
                        <div class="bg-gray-800 text-white p-3 text-center font-bold text-sm tracking-widest uppercase">
                            Corporativos
                        </div>
                        <table class="w-full text-sm">
                            <thead class="bg-gray-50 border-b border-gray-200 text-xs font-bold text-gray-600 uppercase tracking-wider">
                                <tr>
                                    <th class="py-3 px-4 text-left">Concepto</th>
                                    <th class="py-3 px-4 text-right">Monto</th>
                                    <th class="py-3 px-4 text-right">Cantidad</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-100 font-mono">
                                <tr class="bg-gray-50/60 font-bold text-gray-800">
                                    <td class="py-3 px-4 text-left font-sans">1. Ingreso Base</td>
                                    <td class="py-3 px-4 text-right" id="fin-ingreso-ayer-corp">$0.00</td>
                                    <td class="py-3 px-4 text-right text-gray-700" id="fin-cant-ayer-corp">0</td>
                                </tr>
                                <tr class="bg-indigo-50/30 font-bold text-indigo-900 border-t-2 border-indigo-100">
                                    <td class="py-3 px-4 text-left font-sans">2. Ingreso Total Hoy</td>
                                    <td class="py-3 px-4 text-right text-indigo-700" id="fin-ingreso-hoy-corp">$0.00</td>
                                    <td class="py-3 px-4 text-right text-indigo-700" id="fin-cant-hoy-corp">0</td>
                                </tr>
                                <tr class="bg-white font-bold text-gray-800 border-t-2 border-gray-200">
                                    <td class="py-3 px-4 text-left font-sans text-xs uppercase">3. Diferencia Neta (Hoy - Base)</td>
                                    <td class="py-3 px-4 text-right" id="fin-dif-monto-corp">+$0.00</td>
                                    <td class="py-3 px-4 text-right" id="fin-dif-cant-corp">+0</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <!-- RESIDENCIALES -->
                    <div class="bg-white overflow-hidden rounded-xl border border-gray-200 shadow-xs">
                        <div class="bg-indigo-600 text-white p-3 text-center font-bold text-sm tracking-widest uppercase">
                            Residenciales
                        </div>
                        <table class="w-full text-sm">
                            <thead class="bg-gray-50 border-b border-gray-200 text-xs font-bold text-gray-600 uppercase tracking-wider">
                                <tr>
                                    <th class="py-3 px-4 text-left">Concepto</th>
                                    <th class="py-3 px-4 text-right">Monto</th>
                                    <th class="py-3 px-4 text-right">Cantidad</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-100 font-mono">
                                <!-- 1. Ingreso Base -->
                                <tr class="bg-gray-50/60 font-bold text-gray-800">
                                    <td class="py-3 px-4 text-left font-sans">1. Ingreso Base</td>
                                    <td class="py-3 px-4 text-right" id="fin-ingreso-ayer">$0.00</td>
                                    <td class="py-3 px-4 text-right text-gray-700" id="fin-cant-ayer">0</td>
                                </tr>
                                <!-- Nuevas Instalaciones -->
                                <tr class="text-green-600 hover:bg-green-50/30 transition-colors">
                                    <td class="py-2.5 px-4 text-left font-sans">(+) Nuevas Instalaciones</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-instalaciones">+$0.00</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-cant-instalaciones">0</td>
                                </tr>
                                <!-- Reconexiones -->
                                <tr class="text-green-600 hover:bg-green-50/30 transition-colors">
                                    <td class="py-2.5 px-4 text-left font-sans">(+) Reconexiones</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-reconexiones">+$0.00</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-cant-reconexiones">0</td>
                                </tr>
                                <!-- Upgrades de Plan -->
                                <tr class="text-green-600 hover:bg-green-50/30 transition-colors">
                                    <td class="py-2.5 px-4 text-left font-sans">(+) Upgrades de Plan</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-upgrades">+$0.00</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-cant-upgrades">0</td>
                                </tr>
                                <!-- Cambios 3 Meses Beneficio -->
                                <tr class="text-emerald-600 hover:bg-emerald-50/30 transition-colors font-medium">
                                    <td class="py-2.5 px-4 text-left font-sans">(+) Cambios 3 Meses Beneficio a otro Plan</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-upgrades-beneficio">+$0.00</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-cant-upgrades-beneficio">0</td>
                                </tr>
                                <!-- Ajustes / Fuera de Rango -->
                                <tr class="text-purple-600 hover:bg-purple-50/30 transition-colors">
                                    <td class="py-2.5 px-4 text-left font-sans">(±) Ajustes Manuales / Fuera de Rango</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-otros">+$0.00</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-cant-otros">0</td>
                                </tr>
                                <!-- Downgrades de Plan -->
                                <tr class="text-red-500 hover:bg-red-50/30 transition-colors">
                                    <td class="py-2.5 px-4 text-left font-sans">(-) Downgrades de Plan</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-downgrades">-$0.00</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-cant-downgrades">0</td>
                                </tr>
                                <!-- Suspendidos -->
                                <tr class="text-red-500 hover:bg-red-50/30 transition-colors">
                                    <td class="py-2.5 px-4 text-left font-sans">(-) Suspendidos</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-retiros">-$0.00</td>
                                    <td class="py-2.5 px-4 text-right font-semibold" id="fin-cant-retiros">0</td>
                                </tr>
                                <!-- 2. Ingreso Total Hoy -->
                                <tr class="bg-indigo-50/60 font-bold text-gray-900 border-t-2 border-indigo-200">
                                    <td class="py-3 px-4 text-left font-sans text-base">2. Ingreso Total Hoy</td>
                                    <td class="py-3 px-4 text-right text-indigo-700 text-base" id="fin-ingreso-hoy">$0.00</td>
                                    <td class="py-3 px-4 text-right text-indigo-700 text-base" id="fin-cant-hoy">0</td>
                                </tr>
                                <!-- 3. Diferencia Neta -->
                                <tr class="bg-gray-50/70 font-bold border-t border-gray-200">
                                    <td class="py-3 px-4 text-left font-sans text-gray-700">3. Diferencia Neta (Hoy - Base)</td>
                                    <td class="py-3 px-4 text-right" id="fin-diferencia-neta">$0.00</td>
                                    <td class="py-3 px-4 text-right" id="fin-cant-diferencia-neta">0</td>
                                </tr>
                            </tbody>
                        </table>
                        
                        <div class="p-3 border-t border-gray-100 bg-gray-50/40">
                            <div class="p-3 rounded-lg text-center text-xs font-semibold" id="fin-validacion">
                                <!-- Validación matemática -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            """

final_html = parts[0] + new_html + end_tag + part2[1]

with open(r"c:\Users\wgallardo\Documents\Proyectos gravity\intranet\templates\integracion.html", "w", encoding="utf-8") as f:
    f.write(final_html)
print("Modificado con éxito")
