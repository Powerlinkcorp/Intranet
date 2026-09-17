import os
import glob

# Rutas de los archivos HTML
templates_path = os.path.join(os.path.dirname(__file__), '..', 'templates', '*.html')
root_path = os.path.join(os.path.dirname(__file__), '..', '*.html')

files_to_process = glob.glob(templates_path) + glob.glob(root_path)

responsive_css = """
        /* ========================================================= */
        /* RESPONSIVE DESIGN - INJECTED AUTOMATICALLY                */
        /* ========================================================= */
        @media screen and (max-width: 1024px) {
            .main-container, .grid-container, .dashboard-grid, .layout-grid {
                grid-template-columns: 1fr 1fr;
            }
        }

        @media screen and (max-width: 768px) {
            body {
                padding-bottom: 20px;
            }
            .main-container, .grid-container, .dashboard-grid, .layout-grid, 
            .kpi-container, .resource-grid, .metrics-grid, .cards-grid {
                grid-template-columns: 1fr !important;
                display: flex !important;
                flex-direction: column !important;
                padding: 10px;
                gap: 15px;
            }
            
            .hero {
                padding: 30px 20px !important;
                text-align: center;
            }
            
            .hero h1 {
                font-size: 28px !important;
            }
            
            .sidebar {
                position: static !important;
                width: 100% !important;
                height: auto !important;
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: wrap !important;
                justify-content: center !important;
                gap: 10px;
                padding: 15px;
                margin-bottom: 20px;
            }
            
            .content-area, .main-content {
                margin-left: 0 !important;
                width: 100% !important;
                padding: 10px !important;
            }
            
            .card {
                padding: 15px !important;
            }

            table {
                display: block;
                overflow-x: auto;
                white-space: nowrap;
            }
            
            .flex-container, .navbar, .top-bar {
                flex-direction: column !important;
                align-items: center;
                gap: 10px;
            }
            
            .login-container, .login-box {
                width: 95% !important;
                margin: 20px auto !important;
            }
            
            .section-title {
                font-size: 14px;
            }
        }
"""

for filepath in files_to_process:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "/* RESPONSIVE DESIGN - INJECTED AUTOMATICALLY" in content:
        print(f"Skipping {os.path.basename(filepath)} - Already injected.")
        continue
        
    if "</style>" in content:
        # Reemplazar la última ocurrencia de </style>
        parts = content.rsplit("</style>", 1)
        new_content = parts[0] + responsive_css + "\n    </style>" + parts[1]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Injected CSS into {os.path.basename(filepath)}")
    else:
        print(f"Warning: No </style> tag found in {os.path.basename(filepath)}")
