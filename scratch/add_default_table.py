import os

target_file = r"c:\Users\wgallardo\Documents\Proyectos gravity\intranet\templates\historico.html"

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

new_html = """        <!-- Previsualización / Historial Reciente -->
        <div id="recentEventsContainer" class="glass-panel rounded-2xl p-6 mb-8">
            <h2 class="text-xl font-bold text-gray-800 mb-4 border-b pb-2 flex items-center">
                <i class="fas fa-list text-indigo-500 mr-2"></i> Últimos Movimientos
            </h2>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200 text-sm text-left">
                    <thead class="bg-gray-50 text-gray-500 uppercase font-medium">
                        <tr>
                            <th class="px-4 py-3">ID Servicio</th>
                            <th class="px-4 py-3">Cédula</th>
                            <th class="px-4 py-3">Cliente</th>
                            <th class="px-4 py-3">Plan</th>
                            <th class="px-4 py-3 text-center">Estado Anterior</th>
                            <th class="px-4 py-3 text-center">Estado Nuevo</th>
                            <th class="px-4 py-3 text-center">Evento</th>
                            <th class="px-4 py-3">Fecha</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        {% for ev in recent_events %}
                        <tr class="hover:bg-gray-50">
                            <td class="px-4 py-4 font-semibold text-gray-900">{{ ev.service_id }}</td>
                            <td class="px-4 py-4">{{ ev.cedula }}</td>
                            <td class="px-4 py-4">{{ ev.client_name }}</td>
                            <td class="px-4 py-4 text-gray-600">{{ ev.plan }}</td>
                            <td class="px-4 py-4 text-center">
                                <span class="px-2 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">{{ ev.old_value or '-' }}</span>
                            </td>
                            <td class="px-4 py-4 text-center">
                                <span class="px-2 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">{{ ev.new_value or '-' }}</span>
                            </td>
                            <td class="px-4 py-4 text-center font-bold">
                                {{ ev.event_type }}
                            </td>
                            <td class="px-4 py-4 text-gray-500">{{ ev.date }}</td>
                        </tr>
                        {% endfor %}
                        {% if not recent_events %}
                        <tr><td colspan="8" class="text-center py-4 text-gray-500">Aún no hay movimientos registrados.</td></tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Resultados -->"""

if "id=\"recentEventsContainer\"" not in content:
    content = content.replace("        <!-- Resultados -->", new_html)

# Hide it when searching
js_target = """            loader.classList.remove('hidden');
            results.classList.add('hidden');
            errorBox.classList.add('hidden');"""

js_replacement = """            loader.classList.remove('hidden');
            results.classList.add('hidden');
            errorBox.classList.add('hidden');
            const recentContainer = document.getElementById('recentEventsContainer');
            if (recentContainer) recentContainer.classList.add('hidden');"""

if "recentContainer.classList.add('hidden');" not in content:
    content = content.replace(js_target, js_replacement)

with open(target_file, "w", encoding="utf-8") as f:
    f.write(content)

print("Recent events table added successfully.")
