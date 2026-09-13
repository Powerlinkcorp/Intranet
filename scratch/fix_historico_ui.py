import os

target_file = r"c:\Users\wgallardo\Documents\Proyectos gravity\intranet\templates\historico.html"

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the style block
old_style = """    <style>
        .glass-panel {"""

new_style = """    <style>
        /* ESTILOS CORPORATIVOS GLOBALES (NAVBAR) */
        :root {
            --fondo-principal: #ffffff;
            --blanco: #ffffff;
            --cabeceras: #1A1A1A;
            --acento: #FFC107;
            --acento-hover: #F5C71D;
            --texto-negro: #1A1A1A;
            --texto-gris: #4A4A4A;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: #ffffff;
            color: #1e293b;
        }

        /* NAVBAR (IDÉNTICO A INTRANET.HTML) */
        .navbar {
            background-color: var(--cabeceras);
            padding: 15px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: #fff;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }

        .navbar .logo {
            font-size: 24px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }

        .navbar .logo span {
            color: var(--acento);
        }
        
        .navbar .admin-badge {
            background-color: var(--acento);
            color: var(--texto-negro) !important;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 12px;
            margin-left: 10px;
            font-weight: 700;
            vertical-align: middle;
        }

        .navbar .user-menu {
            display: flex;
            align-items: center;
            gap: 20px;
            font-size: 14px;
        }

        .btn-logout {
            background: transparent;
            color: #ef4444;
            border: 1px solid #ef4444;
            padding: 5px 12px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.2s;
        }

        .btn-logout:hover {
            background: #ef4444;
            color: #fff;
        }

        /* FAST LINKS */
        .fast-links {
            background-color: var(--cabeceras);
            display: flex;
            justify-content: center;
            gap: 40px;
            padding: 16px;
            border-bottom: 3px solid var(--acento);
        }

        .fast-links a {
            color: #e2e8f0;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: color 0.2s;
        }

        .fast-links a:hover, .fast-links a.active {
            color: var(--acento);
        }

        .glass-panel {"""

content = content.replace(old_style, new_style)

# Replace the navbar
old_nav = """    <!-- Navbar Minimalista -->
    <nav class="bg-indigo-600 text-white shadow-lg sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4">
            <div class="flex justify-between h-16">
                <div class="flex items-center space-x-4">
                    <a href="/intranet" class="flex items-center hover:opacity-80 transition-opacity">
                        <i class="fas fa-bolt text-2xl text-yellow-400 mr-2"></i>
                        <span class="font-bold text-xl tracking-tight">Powerlink</span>
                    </a>
                </div>
                <div class="flex items-center space-x-4">
                    <a href="/intranet" class="text-indigo-100 hover:text-white px-3 py-2 rounded-md text-sm font-medium transition-colors">Volver a Inicio</a>
                </div>
            </div>
        </div>
    </nav>"""

new_nav = """    {% if not embed %}
    <!-- NAVBAR CORPORATIVO -->
    <nav class="navbar">
        <a href="/" class="logo" style="text-decoration:none; color:inherit;">
            POWER LINK <span>CORP</span> <span class="admin-badge">Histórico</span>
        </a>
        <div class="user-menu">
            <span style="font-size: 13px;">Hola, {{ user.full_name }}</span>
            <button class="btn-logout" onclick="logout()">Cerrar Sesión</button>
        </div>
    </nav>

    <!-- ENLACES RÁPIDOS GLOBALES -->
    <div class="fast-links">
        <a href="/"><i class="fa-solid fa-house"></i> Inicio</a>
        <a href="#"><i class="fa-solid fa-briefcase"></i> Proyectos</a>
        {% if user.role == 'admin' or 'ver_directorio' in (user.permissions or '') %}
        <a href="/directorio"><i class="fa-solid fa-address-book"></i> Directorio</a>
        {% endif %}
        {% if user.role == 'admin' or 'ver_helpdesk' in (user.permissions or '') %}
        <a href="/helpdesk"><i class="fa-solid fa-headset"></i> Comunicaciones</a>
        {% endif %}
        {% if user.role == 'admin' or 'ver_reportes' in (user.permissions or '') %}
        <a href="/reportes"><i class="fa-solid fa-chart-bar"></i> Reportes</a>
        {% endif %}
        {% if user.role == 'admin' or 'cargar_datos_usuarios' in (user.permissions or '') %}
        <a href="/admin"><i class="fa-solid fa-users"></i> RRHH</a>
        {% endif %}
        {% if user.role == 'admin' %}
        <a href="/admin?tab=permisos"><i class="fa-solid fa-shield-halved"></i> Permisos</a>
        {% endif %}
        {% if user.role == 'admin' or 'ver_integracion' in (user.permissions or '') %}
        <a href="/integracion"><i class="fa-solid fa-network-wired"></i> Integración</a>
        {% endif %}
        <a href="/historico" class="active"><i class="fa-solid fa-history"></i> Histórico</a>
    </div>
    {% endif %}"""

content = content.replace(old_nav, new_nav)

# Add logout script logic
if "async function logout()" not in content:
    logout_script = """        async function logout() {
            try {
                const res = await fetch('/api/auth/logout', { method: 'POST' });
                if(res.ok) window.location.href = '/login';
            } catch (e) { console.error(e); }
        }

        // Permitir buscar al presionar Enter"""
    content = content.replace("        // Permitir buscar al presionar Enter", logout_script)

with open(target_file, "w", encoding="utf-8") as f:
    f.write(content)

print("UI updated successfully.")
