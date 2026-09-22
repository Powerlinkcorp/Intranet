// content.js - Pantalla Flotante Permanente con Cierre Exclusivo por Botón
(function () {
    const PANEL_ID = 'soporte_tecnico_permanent_window';
    const DIM_KEY = 'st_panel_dimensions_v2';
    const MIN_W = 380;
    const MIN_H = 500;

    function openPermanentPanel() {
        let container = document.getElementById(PANEL_ID);

        // Si ya existe y estaba oculta, la mostramos
        if (container) {
            container.style.display = 'flex';
            return;
        }

        // Recuperar última posición y tamaño
        let dims = { width: 450, height: 650, top: 20, right: 20 };
        try {
            const saved = localStorage.getItem(DIM_KEY);
            if (saved) dims = Object.assign(dims, JSON.parse(saved));
        } catch (e) { }

        // 1. Contenedor Flotante Principal
        container = document.createElement('div');
        container.id = PANEL_ID;
        container.style.cssText = `
            position: fixed !important;
            top: ${dims.top}px !important;
            left: ${dims.left !== undefined ? dims.left + 'px' : 'auto'} !important;
            right: ${dims.left === undefined ? (dims.right || 20) + 'px' : 'auto'} !important;
            width: ${Math.max(dims.width, MIN_W)}px !important;
            height: ${Math.max(dims.height, MIN_H)}px !important;
            min-width: ${MIN_W}px !important;
            min-height: ${MIN_H}px !important;
            max-width: 96vw !important;
            max-height: 96vh !important;
            z-index: 2147483647 !important;
            background: #0f172a !important;
            border-radius: 16px !important;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.1) !important;
            display: flex !important;
            flex-direction: column !important;
            overflow: hidden !important;
            box-sizing: border-box !important;
            user-select: none !important;
            pointer-events: auto !important;
        `;

        // 2. Barra Superior (Cabecera Arrastrable + Botón Cerrar)
        const header = document.createElement('div');
        header.style.cssText = `
            height: 38px !important;
            background: #0f172a !important;
            color: #ffffff !important;
            display: flex !important;
            align-items: center !important;
            justify-content: space-between !important;
            padding: 0 14px !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
            font-size: 12px !important;
            font-weight: 800 !important;
            cursor: grab !important;
            flex-shrink: 0 !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
        `;
        header.innerHTML = `
            <div style="display:flex; align-items:center; gap:8px; pointer-events:none;">
                <span style="font-size:14px;">🛡️</span>
                <span>Soporte Técnico</span>
                <span style="font-size:10px; background:#1e293b; color:#38bdf8; padding:2px 6px; border-radius:6px; font-weight:600;">Pantalla Fija</span>
            </div>
            <div style="display:flex; align-items:center; gap:6px;">
                <button id="btn_minimize_panel" title="Minimizar temporalmente" style="
                    background: rgba(255,255,255,0.1) !important;
                    border: none !important;
                    color: #94a3b8 !important;
                    border-radius: 8px !important;
                    width: 26px !important;
                    height: 26px !important;
                    cursor: pointer !important;
                    font-size: 14px !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                ">−</button>
                <button id="btn_close_panel" title="Cerrar pantalla" style="
                    background: #ef4444 !important;
                    border: none !important;
                    color: #ffffff !important;
                    border-radius: 8px !important;
                    width: 26px !important;
                    height: 26px !important;
                    cursor: pointer !important;
                    font-size: 16px !important;
                    font-weight: bold !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: center !important;
                ">&times;</button>
            </div>
        `;

        // 3. IFrame con la Aplicación de Soporte (popup.html)
        const iframe = document.createElement('iframe');
        iframe.src = chrome.runtime.getURL('popup.html');
        iframe.style.cssText = `
            flex: 1 !important;
            width: 100% !important;
            height: calc(100% - 38px) !important;
            border: none !important;
            display: block !important;
            background: #ffffff !important;
        `;

        container.appendChild(header);
        container.appendChild(iframe);

        // 4. Controladores de Redimensionamiento (8 Handles en bordes y esquinas)
        const handles = [
            { dir: 'n', cursor: 'ns-resize', css: 'top: 0; left: 10px; right: 10px; height: 8px;' },
            { dir: 's', cursor: 'ns-resize', css: 'bottom: 0; left: 10px; right: 10px; height: 8px;' },
            { dir: 'w', cursor: 'ew-resize', css: 'left: 0; top: 10px; bottom: 10px; width: 8px;' },
            { dir: 'e', cursor: 'ew-resize', css: 'right: 0; top: 10px; bottom: 10px; width: 8px;' },
            { dir: 'nw', cursor: 'nwse-resize', css: 'top: 0; left: 0; width: 14px; height: 14px; z-index: 10;' },
            { dir: 'ne', cursor: 'nesw-resize', css: 'top: 0; right: 0; width: 14px; height: 14px; z-index: 10;' },
            { dir: 'sw', cursor: 'nesw-resize', css: 'bottom: 0; left: 0; width: 14px; height: 14px; z-index: 10;' },
            { dir: 'se', cursor: 'nwse-resize', css: 'bottom: 0; right: 0; width: 14px; height: 14px; z-index: 10;' }
        ];

        handles.forEach(h => {
            const el = document.createElement('div');
            el.className = 'st-handle';
            el.setAttribute('data-dir', h.dir);
            el.style.cssText = `position: absolute !important; ${h.css} cursor: ${h.cursor} !important; background: transparent !important;`;
            container.appendChild(el);
        });

        document.documentElement.appendChild(container);

        // Guardar dimensiones
        function saveDims() {
            const r = container.getBoundingClientRect();
            localStorage.setItem(DIM_KEY, JSON.stringify({
                width: r.width,
                height: r.height,
                top: r.top,
                left: r.left
            }));
        }

        // ===============================================
        // BOTÓN CERRAR (Única vía para cerrar la pantalla)
        // ===============================================
        container.querySelector('#btn_close_panel').addEventListener('click', (e) => {
            e.stopPropagation();
            container.style.display = 'none';
        });

        container.querySelector('#btn_minimize_panel').addEventListener('click', (e) => {
            e.stopPropagation();
            container.style.display = 'none';
        });

        // ===============================================
        // ARRASTRE DE LA VENTANA (DRAG)
        // ===============================================
        let isDragging = false;
        let startX, startY, origLeft, origTop;

        header.addEventListener('mousedown', (e) => {
            if (e.target.tagName === 'BUTTON') return;
            isDragging = true;
            header.style.cursor = 'grabbing';
            startX = e.clientX;
            startY = e.clientY;
            const r = container.getBoundingClientRect();
            origLeft = r.left;
            origTop = r.top;

            iframe.style.pointerEvents = 'none'; // Evita que el iframe capture el ratón

            const onMove = (ev) => {
                if (!isDragging) return;
                let nl = origLeft + (ev.clientX - startX);
                let nt = origTop + (ev.clientY - startY);

                // Límites de la ventana
                nl = Math.max(10, Math.min(window.innerWidth - container.offsetWidth - 10, nl));
                nt = Math.max(10, Math.min(window.innerHeight - container.offsetHeight - 10, nt));

                container.style.left = `${nl}px`;
                container.style.top = `${nt}px`;
                container.style.right = 'auto';
            };

            const onUp = () => {
                isDragging = false;
                header.style.cursor = 'grab';
                iframe.style.pointerEvents = 'auto';
                window.removeEventListener('mousemove', onMove);
                window.removeEventListener('mouseup', onUp);
                saveDims();
            };

            window.addEventListener('mousemove', onMove);
            window.addEventListener('mouseup', onUp);
        });

        // ===============================================
        // REDIMENSIONAMIENTO (RESIZE 8 DIRECCIONES)
        // ===============================================
        container.querySelectorAll('.st-handle').forEach(h => {
            h.addEventListener('mousedown', (e) => {
                e.preventDefault();
                e.stopPropagation();

                const dir = h.getAttribute('data-dir');
                const startX = e.clientX;
                const startY = e.clientY;
                const r = container.getBoundingClientRect();
                const initW = r.width;
                const initH = r.height;
                const initTop = r.top;
                const initLeft = r.left;

                container.style.left = `${initLeft}px`;
                container.style.top = `${initTop}px`;
                container.style.right = 'auto';

                iframe.style.pointerEvents = 'none';

                const onResize = (ev) => {
                    const dx = ev.clientX - startX;
                    const dy = ev.clientY - startY;

                    let nw = initW;
                    let nh = initH;
                    let nt = initTop;
                    let nl = initLeft;

                    if (dir.includes('e')) nw = Math.max(MIN_W, initW + dx);
                    if (dir.includes('w')) {
                        if (initW - dx >= MIN_W) {
                            nw = initW - dx;
                            nl = initLeft + dx;
                        }
                    }
                    if (dir.includes('s')) nh = Math.max(MIN_H, initH + dy);
                    if (dir.includes('n')) {
                        if (initH - dy >= MIN_H) {
                            nh = initH - dy;
                            nt = initTop + dy;
                        }
                    }

                    container.style.width = `${Math.min(nw, window.innerWidth - 20)}px`;
                    container.style.height = `${Math.min(nh, window.innerHeight - 20)}px`;
                    container.style.left = `${Math.max(10, nl)}px`;
                    container.style.top = `${Math.max(10, nt)}px`;
                };

                const onResizeEnd = () => {
                    iframe.style.pointerEvents = 'auto';
                    window.removeEventListener('mousemove', onResize);
                    window.removeEventListener('mouseup', onResizeEnd);
                    saveDims();
                };

                window.addEventListener('mousemove', onResize);
                window.addEventListener('mouseup', onResizeEnd);
            });
        });
    }

    // Escuchar el clic en el icono de la extensión
    chrome.runtime.onMessage.addListener((msg) => {
        if (msg.action === "open_locked_panel") {
            openPermanentPanel();
        }
    });
})();