// ==============================================================================
// POWERLINK CORP. - MÓDULO INTEGRADO DE PARTES DIARIOS Y CORRELATIVOS VGT
// ==============================================================================

(function() {
  const DEFAULT_ROUTES = [{"id": "R-1", "description": "LA MORITA", "vgt": "VGT-P-0223", "postes": "21.0", "distancia_km": "0.68", "observacion": ""}, {"id": "R-2", "description": "C.C LA COLINA- MONTE BELLO", "vgt": "VGT-P-0031", "postes": "50.0", "distancia_km": "5.51", "observacion": ""}, {"id": "R-3", "description": "PARQUE EL RETIRO", "vgt": "VGT-P-0186", "postes": "8.0", "distancia_km": "0.31", "observacion": ""}, {"id": "R-4", "description": "EL PASO", "vgt": "VGT-P-0187", "postes": "19.0", "distancia_km": "0.8", "observacion": ""}, {"id": "R-5", "description": "SOLAR DE LA QTA", "vgt": "VGT-P-0064", "postes": "42.0", "distancia_km": "1.15", "observacion": ""}, {"id": "R-6", "description": "MONTE BELLO- JUNIN-TIBISAY-MACARENA ACTUALIZADA", "vgt": "VGT-P-0218", "postes": "434.0", "distancia_km": "11.7", "observacion": ""}, {"id": "R-7", "description": "LA COLINA-COLISEO-CLUB DE CAMPO", "vgt": "VGT-P-0183", "postes": "88.0", "distancia_km": "5.08", "observacion": ""}, {"id": "R-8", "description": "PUENTE CASTRO-PIE FINO-C. MÉDICO-SOLAR", "vgt": "VGT-2023-P-675", "postes": "247.0", "distancia_km": "7.44", "observacion": ""}, {"id": "R-9", "description": "ESC. TALLER SIMON BOLÍVAR-EL NACIONAL", "vgt": "VGT-2023-P-675", "postes": "75.0", "distancia_km": "3.0", "observacion": ""}, {"id": "R-10", "description": "C. GUAICAIPURO-C. AYACUCHO (23 ENERO)", "vgt": "VGT-2023-P-676", "postes": "19.0", "distancia_km": "0.55", "observacion": ""}, {"id": "R-11", "description": "MACARENA-CABOTAJE -LA MATICA", "vgt": "VGT-P-0218", "postes": "115.0", "distancia_km": "", "observacion": ""}, {"id": "R-12", "description": "CALLEJÓN VARGAS", "vgt": "VGT-2023-P-677", "postes": "15.0", "distancia_km": "4.4", "observacion": ""}, {"id": "R-13", "description": "LAS MINAS", "vgt": "PENDIENTE", "postes": "38.0", "distancia_km": "1.21", "observacion": ""}, {"id": "R-14", "description": "LA ESTRELLA-PANADERO-TRIGO-C. PÁEZ VICTEGUI", "vgt": "VGT-2023-P-678", "postes": "66.0", "distancia_km": "2.21", "observacion": ""}, {"id": "R-15", "description": "PTE. CASTRO-TERMINAL-TIUNA-C. MIQUILEN-BERMUDEZ", "vgt": "VGT-2023-P-679", "postes": "82.0", "distancia_km": "3.2", "observacion": ""}, {"id": "R-16", "description": "CABOTAJE-SANTA EULALIA", "vgt": "VGT-2023-P-680", "postes": "35.0", "distancia_km": "1.3", "observacion": ""}, {"id": "R-17", "description": "BRISAS DE ORIENTE", "vgt": "VGT-2023-P-681", "postes": "36.0", "distancia_km": "1.56", "observacion": ""}, {"id": "R-18", "description": "IUTA - LOS ALPES", "vgt": "VGT-2023-P-682", "postes": "102.0", "distancia_km": "2.2", "observacion": ""}, {"id": "R-19", "description": "LOS ALPES- CAMATAGUA", "vgt": "VGT-2023-P-683", "postes": "39.0", "distancia_km": "1.65", "observacion": ""}, {"id": "R-20", "description": "BARRIO MIRANDA", "vgt": "VGT-2023-P-684", "postes": "28.0", "distancia_km": "1.1", "observacion": ""}, {"id": "R-21", "description": "EL BOSQUE", "vgt": "VGT-2023-P-685", "postes": "11.0", "distancia_km": "0.3", "observacion": ""}, {"id": "R-22", "description": "COLINA DE LA MATICA", "vgt": "VGT-2023-P-686", "postes": "7.0", "distancia_km": "0.27", "observacion": ""}, {"id": "R-23", "description": "EL RINCON", "vgt": "VGT-2023.-P-687", "postes": "30.0", "distancia_km": "1.1", "observacion": ""}, {"id": "R-24", "description": "VALLE ALTO FONTANERA", "vgt": "VGT-2023.-P-688", "postes": "87.0", "distancia_km": "3.3", "observacion": ""}, {"id": "R-25", "description": "CALLE FEDERACION", "vgt": "VGT-2023-P-689", "postes": "14.0", "distancia_km": "45.0", "observacion": ""}, {"id": "R-26", "description": "ELEVADO-PUEBLO", "vgt": "VGT-2023-P-690", "postes": "81.0", "distancia_km": "2.67", "observacion": ""}, {"id": "R-27", "description": "LA ERMITA", "vgt": "VGT-2023-P-691", "postes": "11.0", "distancia_km": "0.39", "observacion": ""}, {"id": "R-28", "description": "TEXAS CITY", "vgt": "VGT-2023.-P-692", "postes": "32.0", "distancia_km": "0.39", "observacion": ""}, {"id": "R-29", "description": "ZONA INDUSTRIAL LAS MINAS", "vgt": "VGT-2023.-P-693", "postes": "49.0", "distancia_km": "1.56", "observacion": ""}, {"id": "R-30", "description": "ZONA INDUSTRIAL EL ORO", "vgt": "VGT-2023.-P-694", "postes": "27.0", "distancia_km": "0.92", "observacion": ""}, {"id": "R-31", "description": "PALO ALTO", "vgt": "VGT-2023.-P-695", "postes": "79.0", "distancia_km": "1.72", "observacion": ""}, {"id": "R-32", "description": "ALBERTO RAVEL", "vgt": "VGT-2023-P-696", "postes": "21.0", "distancia_km": "0.8", "observacion": ""}, {"id": "R-33", "description": "GUAREMAL", "vgt": "VGT-2023-P-767", "postes": "78.0", "distancia_km": "2.51", "observacion": ""}, {"id": "R-34", "description": "QUEBRADA LA VIRGEN", "vgt": "VGT-2023-P-768", "postes": "29.0", "distancia_km": "0.91", "observacion": ""}, {"id": "R-35", "description": "EL BARBECHO", "vgt": "VGT-2023-P-769", "postes": "29.0", "distancia_km": "0.97", "observacion": ""}, {"id": "R 36", "description": "CARRETERA VIEJA LOS TEQUES ACTUALIZADA", "vgt": "VGT-2023-P-770", "postes": "152.0", "distancia_km": "0.5", "observacion": "VERIFICAR DIFERENCIAS ENTRE PLANOS Y MEMORIA DESCRIPTIVA"}, {"id": "R 37", "description": "CENTRO MÉDICO EL PASO-TAMBOR", "vgt": "VGT-2023-P-771", "postes": "58.0", "distancia_km": "2.1", "observacion": ""}, {"id": "R 38", "description": "RAMO VERDE ACTUALIZADA", "vgt": "VGT-2023-P-772", "postes": "52.0", "distancia_km": "2.22", "observacion": "VERIFICAR DIFERENCIAS ENTRE PLANOS Y MEMORIA DESCRIPTIVA"}, {"id": "R 39", "description": "SAN DIEGO DE LOS ALTOS", "vgt": "VGT-2023-P-773", "postes": "313.0", "distancia_km": "15.96", "observacion": ""}, {"id": "R 40", "description": "IGLESIA SAN ANTONIO-AMARILLO", "vgt": "VGT-2023-P-774", "postes": "53.0", "distancia_km": "2.1", "observacion": ""}, {"id": "R 41", "description": "GUADALUPE", "vgt": "VGT-2023-P-775", "postes": "37.0", "distancia_km": "1.35", "observacion": "VERIFICAR DIFERENCIAS ENTRE PLANOS Y MEMORIA DESCRIPTIVA"}, {"id": "R 42", "description": "YERBA BUENA", "vgt": "VGT-2023-P-776", "postes": "33.0", "distancia_km": "1.4", "observacion": ""}, {"id": "R 43", "description": "EL TAMBOR", "vgt": "VGT-2023-P-777", "postes": "49.0", "distancia_km": "1.52", "observacion": ""}, {"id": "R 44", "description": "PACHECO", "vgt": "VGT-2023-P-778", "postes": "29.0", "distancia_km": "1.1", "observacion": ""}, {"id": "R45", "description": "CUMBRE ROJA ACTUALIZADA", "vgt": "VGT-2023-P-1007", "postes": "169.0", "distancia_km": "1.18", "observacion": ""}, {"id": "R46", "description": "SAN PEDRO ACTUALIZADA", "vgt": "VGT-2023-P-1142", "postes": "113.0", "distancia_km": "0.82", "observacion": ""}, {"id": "R47", "description": "COLINAS DEL ANGEL ACTUALIZADA", "vgt": "VGT-2023-P-1143", "postes": "20.0", "distancia_km": "5.14", "observacion": ""}, {"id": "R48", "description": "ALTO VERDE /POR IMPRIMIR", "vgt": "PENDIENTE", "postes": "29.0", "distancia_km": "0.91", "observacion": ""}, {"id": "R49", "description": "MACARENA-LOS CERRITOS /POR IMPRIMIR", "vgt": "VGT-2024-P-326", "postes": "24.0", "distancia_km": "1.1", "observacion": ""}, {"id": "R50", "description": "CUMBRE ROJA TEJERÍAS", "vgt": "VGT-2024-P-429", "postes": "246.0", "distancia_km": "13.4", "observacion": ""}, {"id": "R51", "description": "LOS CASTORES", "vgt": "VGT-2024-P-513", "postes": "161.0", "distancia_km": "5.2", "observacion": ""}, {"id": "R 52", "description": "SAN ANTONIO DE LOS ALTOS- AVENIDA SOUBLETTE", "vgt": "NO FACTIBLE POR S/P", "postes": "-", "distancia_km": "9.01", "observacion": ""}, {"id": "R 53", "description": "ENTRADA DE LA VEGA-CATIA /POR IMPRIMIR", "vgt": "VGT-2024-P-699", "postes": "385.0", "distancia_km": "11.8", "observacion": ""}, {"id": "R 54", "description": "CATIA-AVENIDA SOUBLETTE /POR IMPRIMIR", "vgt": "VGT-2024-P-NH-35", "postes": "-", "distancia_km": "19.2", "observacion": ""}, {"id": "R 55", "description": "SAN ANTONIO DE LOS ALTOS-ENTRADA DE LA VEGA", "vgt": "VGT-2024-P-1088", "postes": "83.0", "distancia_km": "9.01", "observacion": ""}, {"id": "R 56", "description": "CORRALITO KM 18 NO FACTIBLE / NO HAY OFERTA COMERCIAL", "vgt": "VGT-2024-P-1206", "postes": "65.0", "distancia_km": "3.16", "observacion": ""}, {"id": "R 57", "description": "LAGUNETICA /POR IMPRIMIR", "vgt": "VGT-2024-P-1438", "postes": "129.0", "distancia_km": "5.19", "observacion": ""}, {"id": "R 58", "description": "PUENTE CARRIZAL MONTAÑA ALTA (ACT. R56)", "vgt": "VGT-2024-P-1206", "postes": "35.0", "distancia_km": "1.59", "observacion": "REVISAR NUMERO DE RUTA"}, {"id": "R 59", "description": "COLISEO PUENTE CARRIZAL", "vgt": "VGT-2024-P-2411", "postes": "44.0", "distancia_km": "1.8", "observacion": ""}, {"id": "R 60", "description": "SANTO DOMINGO- TRAPICHE", "vgt": "VGT-P-2024-1720", "postes": "209.0", "distancia_km": "5.82", "observacion": ""}, {"id": "R 61", "description": "EL VALLE ETAPA 1", "vgt": "VGT-2024-P-1750", "postes": "251.0", "distancia_km": "6.02", "observacion": ""}, {"id": "R 62", "description": "PUEBLO DE TEJERÍAS-SANTO DOMINGO", "vgt": "VGT-2024-P-1751", "postes": "202.0", "distancia_km": "5.92", "observacion": ""}, {"id": "R 63", "description": "EL PICACHO COCHE /POR IMPRIMIR", "vgt": "-", "postes": "", "distancia_km": "9.2", "observacion": ""}, {"id": "R 64", "description": "CORRALITO -PAN DE AZUCAR", "vgt": "VGT-2024-P-1767", "postes": "31.0", "distancia_km": "1.02", "observacion": ""}, {"id": "R 65", "description": "MONTAÑA ALTA- COLINAS DE CARRIZAL", "vgt": "VGT-2024-P-1851", "postes": "257.0", "distancia_km": "6.95", "observacion": ""}, {"id": "R 66", "description": "POZO DE ROSAS /POR IMPRIMIR", "vgt": "VGT-2024-P-1983", "postes": "133.0", "distancia_km": "3.9", "observacion": ""}, {"id": "R 67", "description": "EL VALLE ETAPA 2", "vgt": "VGT-2024-P-1956", "postes": "304.0", "distancia_km": "9.2", "observacion": ""}, {"id": "R 68", "description": "URB. PIEDRA AZUL/ FALTA AUTORIZACION", "vgt": "VGT-2024-P-2270", "postes": "42.0", "distancia_km": "0.91", "observacion": ""}, {"id": "R 69", "description": "TRAMO SUBTERRÁNEO EL VALLE DESCARTADO/POR IMPRIMIR", "vgt": "VGT-2024-P-680", "postes": "0.0", "distancia_km": "0.92", "observacion": ""}, {"id": "R 70", "description": "LA VEGA KM 0/FALTA AUTORIZCION", "vgt": "VGT-2025-P-131", "postes": "72.0", "distancia_km": "5.2", "observacion": ""}, {"id": "R 71", "description": "LA VEGA FASE 2", "vgt": "VGT-2025-P-2076", "postes": "167.0", "distancia_km": "6.04", "observacion": ""}, {"id": "R 72", "description": "VEREDAS DE COCHE", "vgt": "VGT-2025-P-2136", "postes": "247.0", "distancia_km": "7.4", "observacion": ""}, {"id": "R 73", "description": "23 DE ENERO- DERIVACIONES CATIA", "vgt": "VGT-2025-P-2415", "postes": "1069.0", "distancia_km": "38.42", "observacion": ""}, {"id": "R 74", "description": "DERIVACIONES LAS ADJUNTAS- CARICUAO", "vgt": "VGT-2025-P-2416", "postes": "916.0", "distancia_km": "33.62", "observacion": ""}];
  const DEFAULT_TECHS = [{"id": 1, "block": "AFECTACIONES", "name": "ALEXIS GARCIA OROPEZA", "cedula": "V-12.731.208", "phone": "+58 424-1404877", "cargo": "AFECTACION", "departamento": "AFECTACION"}, {"id": 2, "block": "AFECTACIONES", "name": "ANGEL HIDALGO", "cedula": "V-17.979.012", "phone": "+58 414-9016072", "cargo": "EMPALMADOR", "departamento": "DISTRIBUCIÓN"}, {"id": 3, "block": "AFECTACIONES", "name": "CARLOS JOSÉ BURGOS PINEDA", "cedula": "V-29.850.234", "phone": "+58 424-2894899", "cargo": "AFECTACION", "departamento": "AFECTACION"}, {"id": 4, "block": "AFECTACIONES", "name": "CARLOS SAUL BURGOS", "cedula": "V-18.898.674", "phone": "+58 424-2544061", "cargo": "LINIERO", "departamento": "DISTRIBUCIÓN"}, {"id": 5, "block": "AFECTACIONES", "name": "DANIEL ROJAS", "cedula": "V-21.469.109", "phone": "+58 414-2542030", "cargo": "EMPALMADOR", "departamento": "DISTRIBUCIÓN"}, {"id": 6, "block": "AFECTACIONES", "name": "DAVID RODRIGUEZ", "cedula": "V-26.078.684", "phone": "+58 412-0543227", "cargo": "AYUDANTE", "departamento": "DISTRIBUCIÓN"}, {"id": 7, "block": "AFECTACIONES", "name": "DIEGO ANDRÉS MORONTA VIERA", "cedula": "V-27.371.953", "phone": "+58 424-2920276", "cargo": "AFECTACION", "departamento": "AFECTACION"}, {"id": 8, "block": "AFECTACIONES", "name": "ELIAS MIGUEL JIMENEZ MARMOLET", "cedula": "V-27.908.487", "phone": "+58 412-5913430", "cargo": "AYUDANTE", "departamento": "DISTRIBUCIÓN"}, {"id": 9, "block": "AFECTACIONES", "name": "FRANCISCO RODOLFO REYES URIEPERO", "cedula": "V-27.623.676", "phone": "+58 416-7767278", "cargo": "EMPALMADOR", "departamento": "DISTRIBUCIÓN"}, {"id": 10, "block": "AFECTACIONES", "name": "FRANYELO JOSÉ PEREZ VELASQUEZ", "cedula": "V-30.457.454", "phone": "+58 412-9771281", "cargo": "AYUDANTE", "departamento": "DISTRIBUCIÓN"}, {"id": 11, "block": "AFECTACIONES", "name": "FRANYERSON RAMIREZ", "cedula": "V-29.850.985", "phone": "+58 424-2408734", "cargo": "AYUDANTE", "departamento": "DISTRIBUCIÓN"}, {"id": 12, "block": "AFECTACIONES", "name": "GABRIEL HERNANDEZ", "cedula": "V-28.302.049", "phone": "+58 412-7705454", "cargo": "EMPALMADOR", "departamento": "DISTRIBUCIÓN"}, {"id": 13, "block": "AFECTACIONES", "name": "GADIETH LEXANDRO LOPEZ MARTINEZ", "cedula": "V-32.497.052", "phone": "+58 412-7118551", "cargo": "AYUDANTE", "departamento": "DISTRIBUCIÓN"}, {"id": 14, "block": "AFECTACIONES", "name": "GERAL ANDRES ARIAS", "cedula": "V-27.040.315", "phone": "+58 424-3358423", "cargo": "AYUDANTE", "departamento": "DISTRIBUCIÓN"}, {"id": 15, "block": "AFECTACIONES", "name": "JEAN CARLOS BURGOS", "cedula": "V-32.174.428", "phone": "+58 424-2544061", "cargo": "LINIERO", "departamento": "DISTRIBUCIÓN"}, {"id": 16, "block": "AFECTACIONES", "name": "JOE FRANCO MACHADO", "cedula": "V-14.214.581", "phone": "+58 412-4861337", "cargo": "AFECTACION", "departamento": "AFECTACION"}, {"id": 17, "block": "AFECTACIONES", "name": "JORGE MACHADO", "cedula": "V-11.899.868", "phone": "+58 424-2544061", "cargo": "EMPALMADOR", "departamento": "DISTRIBUCIÓN"}, {"id": 18, "block": "AFECTACIONES", "name": "JOSE ARMANDO LOPEZ", "cedula": "V-8.682.375", "phone": "+58 412-9368853", "cargo": "LINIERO", "departamento": "DISTRIBUCIÓN"}, {"id": 19, "block": "AFECTACIONES", "name": "JOSE MORALES", "cedula": "V-15.255.710", "phone": "+58 414-2356488", "cargo": "LINIERO SUPERVISOR", "departamento": "DISTRIBUCIÓN"}, {"id": 20, "block": "AFECTACIONES", "name": "JOYNERKER DAVID SUÁREZ MEJÍAS", "cedula": "V-32.540.248", "phone": "+58 424-1701521", "cargo": "AYUDANTE", "departamento": "DISTRIBUCIÓN"}, {"id": 21, "block": "AFECTACIONES", "name": "KERVIN MANUEL MARQUEZ CASTRO", "cedula": "V-22.440.512", "phone": "+58 412-3387742", "cargo": "AYUDANTE", "departamento": "DISTRIBUCIÓN"}, {"id": 22, "block": "AFECTACIONES", "name": "LUIS MELENDEZ", "cedula": "V-11.183.645", "phone": "+58 412-9213180", "cargo": "LINIERO", "departamento": "DISTRIBUCIÓN"}, {"id": 23, "block": "AFECTACIONES", "name": "MAIKER GUILLERMO PINEDA RANGEL", "cedula": "V-21.118.622", "phone": "+58 412-9610392", "cargo": "LINIERO", "departamento": "DISTRIBUCIÓN"}, {"id": 24, "block": "AFECTACIONES", "name": "MARIO PIÑERO", "cedula": "V-8.675.093", "phone": "+58 412-9772918", "cargo": "LINIERO", "departamento": "DISTRIBUCIÓN"}, {"id": 25, "block": "AFECTACIONES", "name": "NEOMAR ALBERTO GUAINA GONZÁLEZ", "cedula": "V-27.988.872", "phone": "+58 412-4792793", "cargo": "AYUDANTE", "departamento": "DISTRIBUCIÓN"}, {"id": 26, "block": "AFECTACIONES", "name": "ORLANDO ANTONIO MARRERO CASTILLO", "cedula": "V-25.218.406", "phone": "+58 412-9261975", "cargo": "AYUDANTE", "departamento": "DISTRIBUCIÓN"}, {"id": 27, "block": "AFECTACIONES", "name": "RAYM OROPEZA", "cedula": "V-29.511.706", "phone": "+58 212-3273595", "cargo": "AFECTACION", "departamento": "AFECTACION"}, {"id": 28, "block": "AFECTACIONES", "name": "REINALDO FERNANDEZ", "cedula": "V-17.532.232", "phone": "+58 412-7043735", "cargo": "EMPALMADOR", "departamento": "DISTRIBUCIÓN"}, {"id": 29, "block": "AFECTACIONES", "name": "ROGER MURIA", "cedula": "V-21.469.259", "phone": "+58 414-2367910", "cargo": "AFECTACION", "departamento": "AFECTACION"}, {"id": 30, "block": "AFECTACIONES", "name": "TOMAS SIMON MUJICA MARMOLE", "cedula": "V-14.481.670", "phone": "+58 424-1455746", "cargo": "LINIERO", "departamento": "DISTRIBUCIÓN"}, {"id": 31, "block": "AFECTACIONES", "name": "UDMAR ALEXIS FERNANDEZ PARADA", "cedula": "V-11.603.721", "phone": "+58 412-5858934", "cargo": "LINIERO", "departamento": "DISTRIBUCIÓN"}, {"id": 32, "block": "AFECTACIONES", "name": "VICTOR MANUEL HERNANDEZ ORDAZ", "cedula": "V-19.014.931", "phone": "+58 412-8711136", "cargo": "EMPALMADOR", "departamento": "DISTRIBUCIÓN"}, {"id": 33, "block": "AFECTACIONES", "name": "WENSESLAO MUJICA", "cedula": "V-15.713.395", "phone": "+58 412-3027803", "cargo": "LINIERO SUPERVISOR", "departamento": "DISTRIBUCIÓN"}, {"id": 34, "block": "AFECTACIONES", "name": "WILLIANS ANGARITA", "cedula": "V-20.410.574", "phone": "+58 412-5430647", "cargo": "LINIERO", "departamento": "DISTRIBUCIÓN"}, {"id": 35, "block": "AFECTACIONES", "name": "WOLFAN OLEIDY BARRIOS GARCIA", "cedula": "V-15.913.212", "phone": "+58 424-2684071", "cargo": "LINIERO", "departamento": "DISTRIBUCIÓN"}, {"id": 36, "block": "SOPORTE", "name": "ALEXIS GIL", "cedula": "V-24.886.445", "phone": "+58 424-2558408", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 37, "block": "SOPORTE", "name": "ALFREDO ESCOBAR", "cedula": "V-25.223.904", "phone": "+58 412-1636071", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 38, "block": "SOPORTE", "name": "ARMANDO GONZALEZ", "cedula": "V-28.413.014", "phone": "+58 412-8280467", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 39, "block": "SOPORTE", "name": "CARLOS ARAUJO", "cedula": "V-28.073.816", "phone": "+58 424-1216997", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 40, "block": "SOPORTE", "name": "CARLOS GIL", "cedula": "V-28.329.666", "phone": "+58 412-9960741", "cargo": "SOPORTE DE CAMPO ALTOS MIRANDINOS", "departamento": "SOPORTE DE CAMPO"}, {"id": 41, "block": "SOPORTE", "name": "CESAR AUGUSTO CAMPOS LUQUE", "cedula": "V-30.182.542", "phone": "+58 424-1664020", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 42, "block": "SOPORTE", "name": "CESAR ENRIQUE GÓMEZ CONTRERAS", "cedula": "V-30.457.598", "phone": "+58 424-8940008", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 43, "block": "SOPORTE", "name": "DANIEL ALBERTO COLMENARES LIRA", "cedula": "V-23.652.902", "phone": "+58 412-0192634", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 44, "block": "SOPORTE", "name": "DAVID PEREIRA", "cedula": "V-17.926.043", "phone": "+58 412-9072753", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 45, "block": "SOPORTE", "name": "DOUGLAS MAYOBRE", "cedula": "V-25.840.238", "phone": "+58 426-7318611", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 46, "block": "SOPORTE", "name": "ERNESTO GABRIEL DELGADO", "cedula": "V-27.040.347", "phone": "+58 424-2921840", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 47, "block": "SOPORTE", "name": "GABRIEL VICENTE ESPINOZA DUM", "cedula": "V-30.457.808", "phone": "+58 412-9836858", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 48, "block": "SOPORTE", "name": "HENRY CARTAYA", "cedula": "V-14.480.388", "phone": "+58 424-2563811", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 49, "block": "SOPORTE", "name": "HERNÁN JOSÉ LEAL MARTÍNEZ", "cedula": "V-24.523.064", "phone": "+58 416-1539118", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 50, "block": "SOPORTE", "name": "ISAAC RAFAEL SALGADO ALDAMA", "cedula": "V-16.924.451", "phone": "+58 412-0481272", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 51, "block": "SOPORTE", "name": "JEFFERSON DANIEL MARRERO OCHOA", "cedula": "V-20.114.489", "phone": "+58 424-2197479", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 52, "block": "SOPORTE", "name": "JEFFERSON MIGUEL CASTELLANOS HERNANDEZ", "cedula": "V-25.840.293", "phone": "+58 412-9324959", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 53, "block": "SOPORTE", "name": "JESÚS MANUEL ROMERO MUÑOZ", "cedula": "V-24.898.093", "phone": "+58 424-1430039", "cargo": "SOPORTE DE CAMPO CATIA/LA VEGA", "departamento": "SOPORTE DE CAMPO"}, {"id": 54, "block": "SOPORTE", "name": "JOBER DUGARTE", "cedula": "V-29.511.879", "phone": "+58 412-6345678", "cargo": "SOPORTE DE CAMPO EL VALLE", "departamento": "SOPORTE DE CAMPO"}, {"id": 55, "block": "SOPORTE", "name": "JOHAN RENE RODRIGUEZ MORALES", "cedula": "V-14.216.384", "phone": "+58 424-1247194", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 56, "block": "SOPORTE", "name": "JOLHAN ANTHONY RODRIGUEZ RODRIGUEZ", "cedula": "V-24.998.556", "phone": "+58 424-1514885", "cargo": "SOPORTE DE CAMPO ALTOS MIRANDINOS", "departamento": "SOPORTE DE CAMPO"}, {"id": 57, "block": "SOPORTE", "name": "JONATHAN GUTIERREZ", "cedula": "V-28.307.034", "phone": "+58 424-2114023", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 58, "block": "SOPORTE", "name": "JOSE ENRIQUE LEAL CURIEL", "cedula": "V-14.071.913", "phone": "+58 412-5990012", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 59, "block": "SOPORTE", "name": "JUAN MIJARES", "cedula": "V-14.059.259", "phone": "+58 414-1732347", "cargo": "SUPERVISOR INSTALADOR", "departamento": "INSTALACION"}, {"id": 60, "block": "SOPORTE", "name": "JUNIOR ARNALDO ORTA JIMENEZ", "cedula": "V-20.265.676", "phone": "+58 412-9184912", "cargo": "SOPORTE DE CAMPO TEJERIAS", "departamento": "SOPORTE DE CAMPO"}, {"id": 61, "block": "SOPORTE", "name": "KEHISBER ANTONIO CARABALLO GARCIA", "cedula": "V-30.328.230", "phone": "+58 412-0251325", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 62, "block": "SOPORTE", "name": "KEITHMEL MARCANO", "cedula": "V-30.411.342", "phone": "+58 412-9955190", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 63, "block": "SOPORTE", "name": "KEVIN JOSSUEEP CORTEZ GONZALEZ", "cedula": "V-25.237.424", "phone": "+58 424-2060194", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 64, "block": "SOPORTE", "name": "LUIS ALBERTO ALTUVE MENESES", "cedula": "V-13.717.742", "phone": "+58 424-2897983", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 65, "block": "SOPORTE", "name": "LUIS RODRIGUEZ", "cedula": "V-23.608.565", "phone": "+58 414-7444457", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 66, "block": "SOPORTE", "name": "MOISES ALBERTO PIÑANGO RODRÍGUEZ", "cedula": "V-27.597.252", "phone": "+58 412-6916741", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 67, "block": "SOPORTE", "name": "MOISES ALEJANDRO MUJICA BALZA", "cedula": "V-29.751.880", "phone": "+58 422-3344952", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 68, "block": "SOPORTE", "name": "RANDY EIDAN MORENO CHACOA", "cedula": "V-29.850.452", "phone": "+58 424-2508330", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 69, "block": "SOPORTE", "name": "RONEL JOSE VARGAS VADEL", "cedula": "V-21.118.209", "phone": "+58 412-4215662", "cargo": "SOPORTE DE CAMPO ALTOS MIRANDINOS", "departamento": "SOPORTE DE CAMPO"}, {"id": 70, "block": "SOPORTE", "name": "ROOSEVELT LARA", "cedula": "V-28.073.912", "phone": "+58 424-1257816", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 71, "block": "SOPORTE", "name": "SIMON TORRES", "cedula": "V-30.328.690", "phone": "+58 414-9905942", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 72, "block": "SOPORTE", "name": "STEVEN RAFAEL MARDACH TORRES", "cedula": "V-22.667.018", "phone": "+58 414-2681380", "cargo": "INSTALADOR", "departamento": "INSTALACION"}, {"id": 73, "block": "SOPORTE", "name": "ZADKIEL MENDOZA", "cedula": "V-26.498.545", "phone": "+58 414-1612261", "cargo": "SUPERVISOR INSTALADOR", "departamento": "INSTALACION"}];
  const DEFAULT_DRIVERS = [{"id": 1, "name": "JEFFERSON PLAZA", "cedula": "V-12.879.751", "phone": "+58 414-1339787", "cargo": "CHOFER"}, {"id": 2, "name": "NELSON VEGAS", "cedula": "V-11.817.677", "phone": "+58 424-2842089", "cargo": "CHOFER"}, {"id": 3, "name": "ALEJANDRO CAMACHO", "cedula": "V-10.503.027", "phone": "+58 412-9016479", "cargo": "CHOFER"}, {"id": 4, "name": "IRVIN SANTANA", "cedula": "V-8.677.687", "phone": "+58 412-7846519", "cargo": "CHOFER"}, {"id": 5, "name": "WILLIAM GREGORIO NIEVES", "cedula": "V-15.315.119", "phone": "+58 412-5481476", "cargo": "CHOFER"}, {"id": 6, "name": "JONMEL FERNANDEZ GARCIA", "cedula": "V-16.935.592", "phone": "+58 414-2014293", "cargo": "CHOFER"}, {"id": 7, "name": "RAFAEL ANGEL VELASQUEZ GOUDETH", "cedula": "V-16.249.337", "phone": "+58 412-9709191", "cargo": "CHOFER"}, {"id": 8, "name": "ROBERTO ANTONIO CHACÓN SÁNCHEZ", "cedula": "V-10.161.454", "phone": "+58 414-4729147", "cargo": "CHOFER"}, {"id": 9, "name": "MAICKEL LEANDRO CAPOTE PEÑA", "cedula": "V-15.715.053", "phone": "+58 412-3771725", "cargo": "CHOFER"}, {"id": 10, "name": "YORLAN ALEXANDER ALGUILAR BORGES", "cedula": "V-12.765.034", "phone": "+58 414-0168955", "cargo": "CHOFER"}, {"id": 11, "name": "OLIVER DARIO VEGAS CASTILLO", "cedula": "V-14.674.092", "phone": "+58 424-2844092", "cargo": "CHOFER"}];
  const DEFAULT_VEHS = [{"id": 1, "model": "RICH ZN", "plate": "A00CR8G", "lastSeen": "2026-08-15"}, {"id": 2, "model": "RICH ZN", "plate": "A98DP5K", "lastSeen": "2026-08-15"}, {"id": 3, "model": "EKXPRESS II 150", "plate": "AG2L05E", "lastSeen": "2026-08-15"}, {"id": 4, "model": "EMPIRE HORSE", "plate": "AK7J67M", "lastSeen": "2026-08-15"}, {"id": 5, "model": "EMPIRE HORSE", "plate": "AL3Y16G", "lastSeen": "2026-08-15"}, {"id": 6, "model": "BERA - KAVAK", "plate": "AT2X63D", "lastSeen": "2026-08-15"}, {"id": 7, "model": "DT-200 BR ENDUR", "plate": "AL3Y16G", "lastSeen": "2026-08-15"}, {"id": 8, "model": "HILUX", "plate": "A59EW0A", "lastSeen": "2026-08-15"}, {"id": 9, "model": "MITSUBISHI PANEL L300", "plate": "13HDBA", "lastSeen": "2026-10-04"}];

  const WEEKDAY_TEAMS = [
    { id: "M", letter: "M", type: "AFECTACIONES", active: true, techs: ["JOE FRANCO MACHADO", "GERAL ANDRES ARIAS"], driver: "", vehicle: "RICH ZN", plate: "A00CR8G", rawTickets: "" },
    { id: "E", letter: "E", type: "AFECTACIONES", active: true, techs: ["JORGE MACHADO", "ALEXIS GARCIA OROPEZA", "JEAN CARLOS BURGOS"], driver: "", vehicle: "RICH ZN", plate: "A98DP5K", rawTickets: "" },
    { id: "P", letter: "P", type: "AFECTACIONES", active: true, techs: ["CARLOS JOSÉ BURGOS PINEDA", "DIEGO ANDRÉS MORONTA VIERA"], driver: "", vehicle: "RICH ZN", plate: "A98DP5K", rawTickets: "" },
    { id: "V", letter: "V", type: "SOPORTE TÉCNICO", active: true, techs: ["JESÚS MANUEL ROMERO MUÑOZ"], driver: "", vehicle: "EKXPRESS II 150", plate: "AG2L05E", rawTickets: "" },
    { id: "J", letter: "J", type: "SOPORTE TÉCNICO", active: true, techs: ["JOBER DUGARTE"], driver: "", vehicle: "EMPIRE HORSE", plate: "AK7J67M", rawTickets: "" },
    { id: "G", letter: "G", type: "SOPORTE TÉCNICO", active: true, techs: ["CARLOS GIL"], driver: "", vehicle: "EMPIRE HORSE", plate: "AK7J67M", rawTickets: "" },
    { id: "R", letter: "R", type: "SOPORTE TÉCNICO", active: true, techs: ["RONEL JOSE VARGAS VADEL"], driver: "", vehicle: "EMPIRE HORSE", plate: "AK7J67M", rawTickets: "" },
    { id: "S", letter: "S", type: "SOPORTE TÉCNICO", active: true, techs: ["JOLHAN ANTHONY RODRIGUEZ RODRIGUEZ"], driver: "", vehicle: "EMPIRE HORSE", plate: "AL3Y16G", rawTickets: "" },
    { id: "H", letter: "H", type: "SOPORTE TÉCNICO", active: true, techs: ["HERNÁN JOSÉ LEAL MARTÍNEZ"], driver: "", vehicle: "BERA - KAVAK", plate: "AT2X63D", rawTickets: "" },
    { id: "Y", letter: "Y", type: "SOPORTE TÉCNICO", active: true, techs: ["JUNIOR ARNALDO ORTA JIMENEZ"], driver: "", vehicle: "DT-200 BR ENDUR", plate: "AL3Y16G", rawTickets: "" }
  ];

  const DEFAULT_WEEKEND_TEAMS = [
    { id: "GUARDIA-1", letter: "F", customTitle: '', type: "AFECTACIONES", active: true, techs: [], driver: "", vehicle: "MITSUBISHI PANEL L300", plate: "13HDBA", rawTickets: "" },
    { id: "GUARDIA-2", letter: "xD", customTitle: '', type: "SOPORTE TÉCNICO", active: false, techs: [], driver: "", vehicle: "EMPIRE HORSE", plate: "AK7J67M", rawTickets: "" }
  ];

  // State Variables
  let routesDB = JSON.parse(localStorage.getItem("powerlink_routes")) || DEFAULT_ROUTES;
  let techniciansDB = JSON.parse(localStorage.getItem("powerlink_techs")) || DEFAULT_TECHS;
  let driversDB = JSON.parse(localStorage.getItem("powerlink_drivers")) || DEFAULT_DRIVERS;
  let vehiclesDB = JSON.parse(localStorage.getItem("powerlink_vehicles")) || DEFAULT_VEHS;

  // Sincronizar técnicos
  DEFAULT_TECHS.forEach(dt => {
    const idx = techniciansDB.findIndex(t => t.id === dt.id || normalizeText(t.name) === normalizeText(dt.name));
    if (idx === -1) {
      techniciansDB.push(dt);
    } else {
      if (!techniciansDB[idx].cedula || techniciansDB[idx].cedula !== dt.cedula) techniciansDB[idx].cedula = dt.cedula;
      if (!techniciansDB[idx].phone || techniciansDB[idx].phone !== dt.phone) techniciansDB[idx].phone = dt.phone;
      if (!techniciansDB[idx].block) techniciansDB[idx].block = dt.block;
    }
  });

  let currentPresetMode = "WEEKDAY"; // WEEKDAY or WEEKEND
  let currentInputMode = "TEAM_MANAGER"; // TEAM_MANAGER or MASSIVE_INPUT
  let currentOutputView = "TEXT"; // TEXT or AUDIT
  let currentPersonnelFilter = "ALL";
  let currentSubTab = "TEAMS"; // TEAMS, MASSIVE, ROUTES, PERSONNEL
  let currentPersonnelSubTab = "TECHS"; // TECHS, DRIVERS, VEHS

  let teamsState = JSON.parse(localStorage.getItem("powerlink_vgt_teams")) || JSON.parse(JSON.stringify(WEEKDAY_TEAMS));
  let parsedActivitiesStore = [];

  const TECH_ALIASES = {
    "JOE MACHADO": "JOE FRANCO MACHADO",
    "ANDRES ARIAS": "GERAL ANDRES ARIAS",
    "CARLOS JOSÉ BURGOS": "CARLOS JOSÉ BURGOS PINEDA",
    "CARLOS JOSE BURGOS": "CARLOS JOSÉ BURGOS PINEDA",
    "CARLOS BURGOS": "CARLOS JOSÉ BURGOS PINEDA",
    "DIEGO MORONTA": "DIEGO ANDRÉS MORONTA VIERA",
    "JESUS ROMERO": "JESÚS MANUEL ROMERO MUÑOZ",
    "RONEL VARGAS": "RONEL JOSE VARGAS VADEL",
    "ANTHONY RODRIGUEZ": "JOLHAN ANTHONY RODRIGUEZ RODRIGUEZ",
    "HERNAN LEAL": "HERNÁN JOSÉ LEAL MARTÍNEZ",
    "JUNIOR ORTA": "JUNIOR ARNALDO ORTA JIMENEZ",
    "ALEXIS GARCIA": "ALEXIS GARCIA OROPEZA",
    "ELIAS JIMENEZ": "ELIAS MIGUEL JIMENEZ MARMOLET",
    "FRANCISCO REYES": "FRANCISCO RODOLFO REYES URIEPERO",
    "FRANYELO PEREZ": "FRANYELO JOSÉ PEREZ VELASQUEZ",
    "JOYNERKER SUAREZ": "JOYNERKER DAVID SUÁREZ MEJÍAS",
    "KERVIN MARQUEZ": "KERVIN MANUEL MARQUEZ CASTRO",
    "MAIKER PINEDA": "MAIKER GUILLERMO PINEDA RANGEL",
    "NEOMAR GUAINA": "NEOMAR ALBERTO GUAINA GONZÁLEZ",
    "ORLANDO MARRERO": "ORLANDO ANTONIO MARRERO CASTILLO",
    "TOMAS MUJICA": "TOMAS SIMON MUJICA MARMOLE",
    "UDMAR FERNANDEZ": "UDMAR ALEXIS FERNANDEZ PARADA",
    "VICTOR HERNANDEZ": "VICTOR MANUEL HERNANDEZ ORDAZ",
    "WOLFAN BARRIOS": "WOLFAN OLEIDY BARRIOS GARCIA",
    "CESAR CAMPOS": "CESAR AUGUSTO CAMPOS LUQUE",
    "CESAR GOMEZ": "CESAR ENRIQUE GÓMEZ CONTRERAS",
    "DANIEL COLMENARES": "DANIEL ALBERTO COLMENARES LIRA",
    "ERNESTO DELGADO": "ERNESTO GABRIEL DELGADO",
    "GABRIEL ESPINOZA": "GABRIEL VICENTE ESPINOZA DUM",
    "ISAAC SALGADO": "ISAAC RAFAEL SALGADO ALDAMA",
    "JEFFERSON MARRERO": "JEFFERSON DANIEL MARRERO OCHOA",
    "JEFFERSON CASTELLANOS": "JEFFERSON MIGUEL CASTELLANOS HERNANDEZ",
    "JOHAN RODRIGUEZ": "JOHAN RENE RODRIGUEZ MORALES",
    "JOSE LEAL": "JOSE ENRIQUE LEAL CURIEL",
    "KEHISBER CARABALLO": "KEHISBER ANTONIO CARABALLO GARCIA",
    "KEVIN CORTEZ": "KEVIN JOSSUEEP CORTEZ GONZALEZ",
    "LUIS ALTUVE": "LUIS ALBERTO ALTUVE MENESES",
    "MOISES PIÑANGO": "MOISES ALBERTO PIÑANGO RODRÍGUEZ",
    "MOISES MUJICA": "MOISES ALEJANDRO MUJICA BALZA",
    "RANDY MORENO": "RANDY EIDAN MORENO CHACOA",
    "STEVEN MARDACH": "STEVEN RAFAEL MARDACH TORRES"
  };

  function normalizeText(str) {
    if (!str) return "";
    return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
  }

  function findTechnician(query) {
    if (!query || typeof query !== "string") return null;
    const cleanQ = query.trim();
    if (!cleanQ) return null;
    const normQ = normalizeText(cleanQ);

    let found = techniciansDB.find(t => normalizeText(t.name) === normQ);
    if (found) return found;

    const digitsQ = cleanQ.replace(/\D/g, '');
    if (digitsQ.length >= 6) {
      found = techniciansDB.find(t => {
        const tDigits = (t.cedula || '').replace(/\D/g, '');
        return tDigits && tDigits === digitsQ;
      });
      if (found) return found;
    }

    for (const [alias, realName] of Object.entries(TECH_ALIASES)) {
      if (normalizeText(alias) === normQ) {
        found = techniciansDB.find(t => normalizeText(t.name) === normalizeText(realName));
        if (found) return found;
      }
    }

    const qTokens = normQ.split(/\s+/).filter(w => w.length > 1);
    if (qTokens.length >= 2) {
      const candidates = techniciansDB.filter(t => {
        const tTokens = normalizeText(t.name).split(/\s+/);
        return qTokens.every(qk => tTokens.includes(qk));
      });
      if (candidates.length === 1) return candidates[0];
    }

    found = techniciansDB.find(t => {
      const tn = normalizeText(t.name);
      return normQ.length > 5 && (tn.includes(normQ) || normQ.includes(tn));
    });
    if (found) return found;

    return null;
  }

  function sanitizeTeamTechNames(teams) {
    if (!teams || !Array.isArray(teams)) return;
    teams.forEach(team => {
      if (team.techs && Array.isArray(team.techs)) {
        team.techs = team.techs.map(tName => {
          const found = findTechnician(tName);
          return found ? found.name : tName;
        });
      }
    });
  }

  sanitizeTeamTechNames(teamsState);

  function getVGTForAddress(address, onu = "", zona = "") {
    const normAddr = normalizeText(address);
    const normOnu  = normalizeText(onu);
    const normZona = normalizeText(zona);
    const fullContext = `${normAddr} ${normOnu} ${normZona}`;

    if (fullContext.includes("CENTRO LOS TEQUES") || fullContext.includes("CENTRO TEQUES")) return "VGT-2023-P-679";
    if (fullContext.includes("CUMBRE ROJA") || fullContext.includes("TEJERIA") || fullContext.includes("TEJERIAS")) return "VGT-2024-P-429";
    if (fullContext.includes("SAN ANTONIO")) {
      const exceptions = ["LA MORITA", "CASTORES", "LOS CASTORES", "LAS MINAS", "LA COLINA", "COLISEO", "CLUB DE CAMPO"];
      if (!exceptions.some(exc => fullContext.includes(exc))) return "VGT-2023-P-774";
    }
    if (fullContext.includes("SAN PEDRO")) return "VGT-2023-P-1142";
    if (fullContext.includes("KM 0") || fullContext.includes("KM0") || fullContext.includes("LAS MAYAS") || fullContext.includes("LA MAYA")) return "VGT-2025-P-131";
    if (fullContext.includes("CATIA") || fullContext.includes("PROPATRIA")) return "VGT-2025-P-2415";
    if (fullContext.includes("VALLE")) return "VGT-2024-P-1750";
    if (fullContext.includes("COCHE")) return "VGT-2025-P-2136";
    if (fullContext.includes("LA VEGA") || fullContext.includes("VEGA")) return "VGT-2025-P-2076";
    if (fullContext.includes("LAGUNETICA")) return "VGT-2024-P-1438";
    if (fullContext.includes("CARRETERA VIEJA") || fullContext.includes("ESPERANZA") || normOnu.includes("ESPERANZA")) return "VGT-2023-P-770";
    if (fullContext.includes("AYACUCHO") || normOnu.includes("AYACUCHO") || fullContext.includes("CHORRITO")) return "VGT-2023-P-676";
    if (fullContext.includes("PIEDRA AZUL") || normOnu.includes("P. AZUL") || normOnu.includes("P.AZUL") || normOnu.includes("PIEDRA AZUL")) return "VGT-2024-P-2270";

    let bestMatch = null;
    let bestScore = 0;

    for (const r of routesDB) {
      if (!r.vgt || r.vgt === "-" || r.vgt === "PENDIENTE" || r.vgt.includes("NO FACTIBLE")) continue;
      const normDesc = normalizeText(r.description);
      let score = 0;
      if (fullContext.includes(normDesc)) score += 120;
      const terms = normDesc.split(/[\s\-\/\,]+/).filter(t => 
        t.length > 3 && !['ACTUALIZADA','PROYECTO','COMPLETO','FASE','ETAPA','POR','IMPRIMIR','LOS','LOS TEQUES','TEQUES'].includes(t)
      );
      let matchedCount = 0;
      for (const term of terms) {
        if (normAddr.includes(term)) {
          matchedCount++;
          score += 25 + term.length;
        } else if (normOnu.includes(term) || normZona.includes(term)) {
          matchedCount++;
          score += 20 + term.length;
        }
      }
      if (matchedCount > 0 && score > bestScore) {
        bestScore = score;
        bestMatch = r.vgt.replace('.-P-', '-P-');
      }
    }

    return bestMatch || "SIN NÚMERO";
  }

  function parseTicketsText(rawText) {
    if (!rawText || !rawText.trim()) return [];
    const text = rawText.trim();
    const activities = [];
    const isTicketFormat = /(?:UBICACI[ÓO]N|DIRECCI[ÓO]N)\s*:/i.test(text);

    if (isTicketFormat) {
      let generalZona = "";
      const zonaMatch = text.match(/ZONA\s*:\s*([^\r\n=]+)/i);
      if (zonaMatch) generalZona = zonaMatch[1].trim();

      const blocks = text.split(/(?:\r?\n)?\s*={3,}\s*(?:\r?\n)?/);
      for (const block of blocks) {
        const bTrim = block.trim();
        if (!bTrim) continue;
        const uMatch = bTrim.match(/(?:UBICACI[ÓO]N|DIRECCI[ÓO]N)\s*:\s*([^\r\n]+)/i);
        if (uMatch) {
          let addr = uMatch[1].trim().replace(/^["'*]+|["'*]+$/g, '').trim();
          let onu = "";
          const onuMatch = bTrim.match(/ONU\s*:\s*([^\r\n]+)/i);
          if (onuMatch) onu = onuMatch[1].trim();
          let localZona = generalZona;
          const bZonaMatch = bTrim.match(/ZONA\s*:\s*([^\r\n]+)/i);
          if (bZonaMatch) localZona = bZonaMatch[1].trim();
          if (addr) activities.push({ address: addr, onu: onu, zona: localZona, manualVgt: null });
        }
      }
      if (activities.length === 0) {
        const lines = text.split(/\r?\n/);
        for (const line of lines) {
          const lTrim = line.trim();
          if (/(?:UBICACI[ÓO]N|DIRECCI[ÓO]N)\s*:/i.test(lTrim)) {
            let addr = lTrim.replace(/.*(?:UBICACI[ÓO]N|DIRECCI[ÓO]N)\s*:\s*/i, '').trim();
            if (addr) activities.push({ address: addr, onu: "", zona: generalZona, manualVgt: null });
          }
        }
      }
    } else {
      const lines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
      for (const line of lines) {
        let clean = line.replace(/^[\d\.\-\)\*\>\+\s]+/, '').trim();
        if (!clean || clean.startsWith("===") || clean.startsWith("---")) continue;
        if (clean.toUpperCase().includes("EQUIPO") || clean.toUpperCase().includes("TECNICO") || clean.toUpperCase().includes("VEHICULO")) continue;
        activities.push({ address: clean, onu: "", zona: "", manualVgt: null });
      }
    }
    return activities;
  }

  function saveVgtAll() {
    localStorage.setItem("powerlink_routes", JSON.stringify(routesDB));
    localStorage.setItem("powerlink_techs", JSON.stringify(techniciansDB));
    localStorage.setItem("powerlink_drivers", JSON.stringify(driversDB));
    localStorage.setItem("powerlink_vehicles", JSON.stringify(vehiclesDB));
    localStorage.setItem("powerlink_vgt_teams", JSON.stringify(teamsState));
    if (typeof window.syncServerDB === "function") {
      window.syncServerDB();
    }
  }

  function showToast(msg) {
    const toast = document.getElementById("toast");
    if (toast) {
      toast.innerText = msg;
      toast.classList.remove("translate-y-20", "opacity-0");
      setTimeout(() => toast.classList.add("translate-y-20", "opacity-0"), 3000);
    } else {
      console.log(msg);
    }
  }

  // ==============================================================================
  // RENDERER PRINCIPAL: VGT
  // ==============================================================================
  function renderVgt(app) {
    if (!app) app = document.getElementById("app");
    if (!app) return;

    // Calcular estadísticas en tiempo real
    const totalTeams = teamsState.length;
    const soportesTeams = teamsState.filter(t => t.type.includes("SOPORTE")).length;
    const afectacionesTeams = teamsState.filter(t => t.type.includes("AFECTACION")).length;
    const totalRoutes = routesDB.length;

    let totalActivities = 0;
    let totalConVGT = 0;
    let totalSinVGT = 0;

    teamsState.forEach(tm => {
      const acts = parseTicketsText(tm.rawTickets || "");
      totalActivities += acts.length;
      acts.forEach(a => {
        const v = a.manualVgt || getVGTForAddress(a.address, a.onu, a.zona);
        if (v && v !== "SIN NÚMERO") totalConVGT++;
        else totalSinVGT++;
      });
    });

    app.innerHTML = `
      <div class="space-y-6 fade-in">
        <!-- HEADER PRINCIPAL -->
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div class="flex items-center gap-2.5">
              <h2 class="text-xl sm:text-2xl font-extrabold text-slate-800 dark:text-slate-100">Partes Diarios y Correlativos VGT</h2>
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FFC107]/15 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-700/50">
                ${currentPresetMode === 'WEEKDAY' ? 'Lunes a Viernes' : 'Guardia / Fin de Semana'}
              </span>
            </div>
            <p class="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">Generador inteligente de partes de cuadrillas, asignación automática de códigos VGT y exportación a WhatsApp y Excel.</p>
          </div>
          <div class="flex items-center gap-2 flex-wrap self-start sm:self-auto">
            <button onclick="window.VGT.exportToExcel()" class="btn-modern inline-flex items-center gap-2 px-3.5 py-2 text-xs font-bold text-white bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 rounded-xl shadow-md shadow-emerald-500/20">
              <i class="fa-solid fa-file-excel"></i> Exportar Excel
            </button>
            <button onclick="window.VGT.copyToClipboard()" class="btn-modern inline-flex items-center gap-2 px-3.5 py-2 text-xs font-bold text-white bg-gradient-to-r from-brand-600 to-brand-500 hover:from-brand-500 hover:to-brand-400 rounded-xl shadow-md shadow-brand-500/20">
              <i class="fa-brands fa-whatsapp"></i> Copiar WhatsApp
            </button>
          </div>
        </div>

        <!-- STATS CARDS -->
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-slate-200/90 dark:border-slate-800 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Cuadrillas</span>
              <i class="fa-solid fa-users text-slate-400 text-sm"></i>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-slate-800 dark:text-slate-100 mt-1">${totalTeams}</p>
          </div>
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-brand-200/70 dark:border-brand-900/40 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Soporte</span>
              <span class="text-xs">🎫</span>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-brand-600 dark:text-brand-400 mt-1">${soportesTeams}</p>
          </div>
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-amber-200/70 dark:border-amber-900/40 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Afectaciones</span>
              <span class="text-xs">⚠️</span>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-amber-600 dark:text-amber-400 mt-1">${afectacionesTeams}</p>
          </div>
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-cyan-200/70 dark:border-cyan-900/40 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Rutas VGT</span>
              <i class="fa-solid fa-route text-cyan-500 text-sm"></i>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-cyan-600 dark:text-cyan-400 mt-1">${totalRoutes}</p>
          </div>
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-emerald-200/70 dark:border-emerald-900/40 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Con VGT</span>
              <i class="fa-solid fa-circle-check text-emerald-500 text-sm"></i>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-1">${totalConVGT}</p>
          </div>
          <div class="card-hover bg-white dark:bg-[#0c1427] rounded-2xl p-4 border border-rose-200/70 dark:border-rose-900/40 shadow-sm min-w-0">
            <div class="flex items-center justify-between">
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">Sin VGT</span>
              <i class="fa-solid fa-circle-question text-rose-500 text-sm"></i>
            </div>
            <p class="text-xl sm:text-2xl font-extrabold text-rose-600 dark:text-rose-400 mt-1">${totalSinVGT}</p>
          </div>
        </div>

        <!-- CONTROL BAR: MODALIDADES Y PESTAÑAS -->
        <div class="bg-white dark:bg-[#0c1427] p-3 sm:p-4 rounded-2xl border border-slate-200/90 dark:border-slate-800 shadow-sm flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <!-- Preset Selector -->
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xs font-bold text-slate-500 uppercase tracking-wider">Modalidad:</span>
            <div class="inline-flex p-1 bg-slate-100 dark:bg-slate-800/80 rounded-xl border border-slate-200/80 dark:border-slate-700/80">
              <button onclick="window.VGT.switchPreset('WEEKDAY')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${currentPresetMode === 'WEEKDAY' ? 'bg-[#FFC107] text-[#1A1A1A] shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}">
                🗓️ L-V (10 Equipos Fijos)
              </button>
              <button onclick="window.VGT.switchPreset('WEEKEND')" class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${currentPresetMode === 'WEEKEND' ? 'bg-[#FFC107] text-[#1A1A1A] shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}">
                🛡️ Guardia / Fin de Semana
              </button>
            </div>
            ${currentPresetMode === 'WEEKEND' ? `
            <button onclick="window.VGT.saveGuardPreset()" class="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-semibold transition-all" title="Guardar la configuración de cuadrillas de guardia">
              💾 Guardar Guardia
            </button>
            <button onclick="window.VGT.loadLastGuardPreset()" class="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-semibold transition-all" title="Cargar guardia previa">
              📂 Cargar Guardia Sábado
            </button>
            ` : `
            <button onclick="window.VGT.resetCurrentPreset()" class="px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-semibold transition-all">
              🔄 Restablecer L-V
            </button>
            `}
          </div>

          <!-- View Tabs Switcher -->
          <div class="inline-flex p-1 bg-slate-100 dark:bg-slate-800/80 rounded-xl border border-slate-200/80 dark:border-slate-700/80 overflow-x-auto custom-scrollbar">
            <button onclick="window.VGT.switchSubTab('TEAMS')" class="px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-all ${currentSubTab === 'TEAMS' ? 'bg-[#1A1A1A] text-white shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}">
              👥 Cuadrillas del Día
            </button>
            <button onclick="window.VGT.switchSubTab('MASSIVE')" class="px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-all ${currentSubTab === 'MASSIVE' ? 'bg-[#1A1A1A] text-white shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}">
              📋 Pegado Masivo (WhatsApp)
            </button>
            <button onclick="window.VGT.switchSubTab('ROUTES')" class="px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-all ${currentSubTab === 'ROUTES' ? 'bg-[#1A1A1A] text-white shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}">
              🛣️ Rutas VGT (${totalRoutes})
            </button>
            <button onclick="window.VGT.switchSubTab('PERSONNEL')" class="px-3 py-1.5 rounded-lg text-xs font-bold whitespace-nowrap transition-all ${currentSubTab === 'PERSONNEL' ? 'bg-[#1A1A1A] text-white shadow-sm' : 'text-slate-600 dark:text-slate-300 hover:text-slate-900'}">
              🪪 Personal & Vehículos
            </button>
          </div>
        </div>

        <!-- BANNER DE GUARDIA SI APLICA -->
        ${currentPresetMode === 'WEEKEND' ? `
        <div class="p-3.5 bg-amber-500/10 border border-amber-300 dark:border-amber-700/50 rounded-2xl flex items-center justify-between gap-3 text-xs text-amber-800 dark:text-amber-200">
          <div class="flex items-center gap-2">
            <span class="text-base">🛡️</span>
            <span><strong>Recordatorio de Cuadrilla de Guardia:</strong> Los equipos, técnicos y vehículos de guardia configurados están listos para el fin de semana o feriado. Los cambios se guardan automáticamente.</span>
          </div>
          <button onclick="window.VGT.loadLastGuardPreset()" class="px-3 py-1 bg-amber-500 text-slate-950 font-bold rounded-lg hover:bg-amber-400 shrink-0">
            Recargar Sábado
          </button>
        </div>
        ` : ''}

        <!-- WORKSPACE PRINCIPAL (GRID 2 COLUMNAS) -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <!-- COLUMNA IZQUIERDA: ENTRADA / GESTIÓN -->
          <div class="lg:col-span-7 space-y-4">
            ${renderLeftSubView()}
          </div>

          <!-- COLUMNA DERECHA: SALIDA GERENCIAL & AUDITORÍA -->
          <div class="lg:col-span-5 space-y-4 lg:sticky lg:top-4">
            ${renderRightManagerialView()}
          </div>
        </div>
      </div>
    `;

    setupVgtListeners();
  }

  function renderLeftSubView() {
    if (currentSubTab === "TEAMS") {
      return renderTeamsManagerView();
    } else if (currentSubTab === "MASSIVE") {
      return renderMassiveInputView();
    } else if (currentSubTab === "ROUTES") {
      return renderRoutesCatalogView();
    } else if (currentSubTab === "PERSONNEL") {
      return renderPersonnelCatalogView();
    }
    return "";
  }

  function renderTeamsManagerView() {
    return `
      <div class="bg-white dark:bg-[#0c1427] rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 sm:p-5 shadow-sm space-y-4">
        <!-- HEADER DEL GESTOR -->
        <div class="flex items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div class="flex items-center gap-2">
            <span class="font-extrabold text-sm sm:text-base text-slate-800 dark:text-slate-100">Cuadrillas del Día</span>
            <span class="px-2 py-0.5 rounded-full text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">${teamsState.length}</span>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="window.VGT.addNewTeamCard()" class="px-3 py-1.5 text-xs font-bold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl transition-all">
              + Agregar Cuadrilla
            </button>
            <button onclick="window.VGT.clearAllTeamTickets()" class="px-3 py-1.5 text-xs font-bold text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-xl transition-all">
              Limpiar Tickets
            </button>
          </div>
        </div>

        <!-- BUSCADOR RÁPIDO DE PERSONAL (TÉCNICOS & CHOFERES) -->
        <div class="bg-slate-50 dark:bg-slate-800/40 rounded-xl p-3 border border-slate-200/80 dark:border-slate-700/80 space-y-2.5">
          <div class="relative">
            <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none"></i>
            <input type="text" id="personnelSearchInput" placeholder="Buscar personal por nombre, cédula o teléfono (ej. Alexis, Machado, 12731...)"
              oninput="window.VGT.handleLivePersonnelSearch(this.value)"
              class="input-modern w-full pl-8 pr-3 py-2 text-xs border border-slate-200 dark:border-slate-700 rounded-xl focus:border-brand-500">
          </div>
          <div class="flex items-center gap-1.5 flex-wrap">
            <button onclick="window.VGT.setPersonnelFilter('ALL', this)" class="px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all ${currentPersonnelFilter === 'ALL' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300'}">
              Todos (${techniciansDB.length + driversDB.length})
            </button>
            <button onclick="window.VGT.setPersonnelFilter('AFECTACIONES', this)" class="px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all ${currentPersonnelFilter === 'AFECTACIONES' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300'}">
              ⚠️ Afectaciones (${techniciansDB.filter(t => t.block === 'AFECTACIONES').length})
            </button>
            <button onclick="window.VGT.setPersonnelFilter('SOPORTE', this)" class="px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all ${currentPersonnelFilter === 'SOPORTE' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300'}">
              🎫 Soporte (${techniciansDB.filter(t => t.block !== 'AFECTACIONES').length})
            </button>
            <button onclick="window.VGT.setPersonnelFilter('CHOFER', this)" class="px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all ${currentPersonnelFilter === 'CHOFER' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300'}">
              🚐 Choferes (${driversDB.length})
            </button>
          </div>
          <!-- Live floating results panel -->
          <div id="personnelSearchResults" class="hidden max-h-56 overflow-y-auto space-y-1.5 custom-scrollbar pt-2 border-t border-slate-200 dark:border-slate-700"></div>
        </div>

        <!-- LISTADO DE TARJETAS DE CUADRILLA -->
        <div class="space-y-3.5" id="teamsContainer">
          ${renderTeamCardsHtml()}
        </div>
      </div>
    `;
  }

  function renderTeamCardsHtml() {
    const driverOptions = driversDB.map(d => `<option value="${d.name}">${d.name} (${d.cedula})</option>`).join("");
    const vehOptions = vehiclesDB.map(v => `<option value="${v.model}|${v.plate}">${v.model} · ${v.plate}</option>`).join("");

    return teamsState.map((tm, idx) => {
      const acts = parseTicketsText(tm.rawTickets || "");
      let conVgt = 0;
      acts.forEach(a => {
        const v = a.manualVgt || getVGTForAddress(a.address, a.onu, a.zona);
        if (v && v !== "SIN NÚMERO") conVgt++;
      });

      const isAfectacion = tm.type.includes("AFECTACION");

      return `
        <div class="bg-slate-50/60 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800/80 rounded-2xl p-4 space-y-3.5 hover:border-slate-300 dark:hover:border-slate-700 transition-all" id="teamCard_${idx}">
          <!-- CABECERA DE LA CUADRILLA -->
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <div class="flex items-center gap-2.5">
              <div class="w-8 h-8 rounded-xl bg-[#1A1A1A] text-[#FFC107] font-black text-xs flex items-center justify-center shadow-xs" id="teamAvatar_${idx}">
                ${(tm.letter || tm.id || 'EQ').substring(0, 3)}
              </div>
              <div class="flex items-center gap-1.5">
                <span class="text-xs font-bold text-slate-500 uppercase">Equipo:</span>
                <input type="text" value="${tm.letter || tm.id || ''}" onchange="window.VGT.handleTeamLetterChange(${idx}, this.value)"
                  class="w-16 px-2 py-0.5 text-xs font-black uppercase text-slate-800 dark:text-slate-100 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-center focus:border-brand-500">
              </div>
              <select onchange="window.VGT.handleTeamTypeChange(${idx}, this.value)"
                class="text-xs font-bold px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200">
                <option value="AFECTACIONES" ${isAfectacion ? 'selected' : ''}>⚠️ Afectaciones</option>
                <option value="SOPORTE TÉCNICO" ${!isAfectacion ? 'selected' : ''}>🎫 Soporte Técnico</option>
              </select>
            </div>

            <div class="flex items-center gap-2">
              <span class="text-[11px] font-bold px-2 py-0.5 rounded-full ${acts.length > 0 ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300' : 'bg-slate-200/60 text-slate-500'}">
                ${acts.length} ${acts.length === 1 ? 'actividad' : 'actividades'} (${conVgt} con VGT)
              </span>
              <button onclick="window.VGT.clearSingleTeamTickets(${idx})" title="Limpiar tickets" class="p-1.5 text-slate-400 hover:text-amber-500 rounded-lg">
                <i class="fa-solid fa-eraser text-xs"></i>
              </button>
              <button onclick="window.VGT.removeTeamCard(${idx})" title="Eliminar cuadrilla" class="p-1.5 text-slate-400 hover:text-rose-500 rounded-lg">
                <i class="fa-solid fa-trash-can text-xs"></i>
              </button>
            </div>
          </div>

          <!-- FILA DE TÉCNICOS (CHIPS) -->
          <div class="space-y-1.5">
            <div class="flex items-center justify-between text-xs font-semibold text-slate-600 dark:text-slate-300">
              <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Técnicos Asignados:</span>
              <span class="text-[10px] text-slate-400 font-medium">Escribe y presiona Enter</span>
            </div>
            <div class="flex items-center gap-1.5 flex-wrap">
              ${(tm.techs || []).map(tName => {
                const tObj = findTechnician(tName);
                const label = tObj ? `${tObj.name} (${tObj.cedula})` : tName;
                return `
                  <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 shadow-2xs">
                    <span>${label}</span>
                    <button type="button" onclick="window.VGT.removeTechFromTeam(${idx}, '${tName}')" class="text-slate-400 hover:text-rose-500">×</button>
                  </span>
                `;
              }).join("")}
              <div class="relative inline-flex items-center">
                <input type="text" placeholder="+ Agregar técnico..." onkeydown="if(event.key==='Enter') { window.VGT.handleInlineTechAdd(${idx}, this); }"
                  class="px-2.5 py-1 text-xs border border-dashed border-slate-300 dark:border-slate-700 rounded-lg bg-transparent focus:border-brand-500 focus:bg-white dark:focus:bg-slate-800">
              </div>
            </div>
          </div>

          <!-- FILA DE CHOFER Y VEHÍCULO -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            <div>
              <label class="block text-[11px] font-bold text-slate-400 uppercase mb-1">Chofer:</label>
              <select onchange="window.VGT.handleTeamDriverChange(${idx}, this.value)"
                class="input-modern w-full px-2.5 py-1.5 text-xs border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200">
                <option value="">(Sin chofer asignado)</option>
                ${driversDB.map(d => `<option value="${d.name}" ${tm.driver === d.name ? 'selected' : ''}>${d.name} (${d.cedula})</option>`).join("")}
              </select>
            </div>
            <div>
              <label class="block text-[11px] font-bold text-slate-400 uppercase mb-1">Vehículo y Placa:</label>
              <select onchange="window.VGT.handleTeamVehicleChange(${idx}, this.value)"
                class="input-modern w-full px-2.5 py-1.5 text-xs border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200">
                <option value="|">(Sin vehículo)</option>
                ${vehiclesDB.map(v => `<option value="${v.model}|${v.plate}" ${tm.vehicle === v.model && tm.plate === v.plate ? 'selected' : ''}>${v.model} · ${v.plate}</option>`).join("")}
              </select>
            </div>
          </div>

          <!-- TEXTAREA DE TICKETS / DIRECCIONES -->
          <div>
            <div class="flex items-center justify-between text-xs mb-1">
              <label class="text-[11px] font-bold text-slate-400 uppercase">Tickets / Direcciones del día:</label>
              <span class="text-[10px] text-slate-400 font-medium">Una dirección por línea o formato de ticket</span>
            </div>
            <textarea rows="3" placeholder="Pega aquí los tickets o direcciones del día..."
              oninput="window.VGT.updateTeamTickets(${idx}, this.value)"
              class="input-modern w-full p-2.5 text-xs border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 placeholder:text-slate-400 resize-y">${tm.rawTickets || ''}</textarea>
          </div>
        </div>
      `;
    }).join("");
  }

  function renderMassiveInputView() {
    return `
      <div class="bg-white dark:bg-[#0c1427] rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 sm:p-5 shadow-sm space-y-4">
        <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div>
            <h3 class="font-extrabold text-sm sm:text-base text-slate-800 dark:text-slate-100">Pegado Masivo de Texto (WhatsApp)</h3>
            <p class="text-xs text-slate-500">Pega el reporte completo enviado por WhatsApp. El sistema detectará equipos, integrantes y direcciones automáticamente.</p>
          </div>
          <span class="px-2.5 py-1 rounded-full text-xs font-bold bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
            Auto-Parser VGT
          </span>
        </div>
        <textarea id="massiveRawInput" rows="16" oninput="window.VGT.handleMassiveInput()" placeholder="Pega aquí el reporte completo con todos los equipos...
Ejemplo:
====================================
EQUIPO 'M' DE AFECTACIONES
NÚMERO DE ACTIVIDADES: 3
TÉCNICO(S):
JOE MACHADO
GERAL ANDRES ARIAS
VEHÍCULO: RICH ZN, PLACA: A00CR8G

LOS TEQUES, EL CABOTAJE
LOS TEQUES, EL PANADERO
===================================="
          class="input-modern w-full p-4 font-mono text-xs border border-slate-200 dark:border-slate-700 rounded-xl bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 resize-y"></textarea>
      </div>
    `;
  }

  function renderRoutesCatalogView() {
    return `
      <div class="bg-white dark:bg-[#0c1427] rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 sm:p-5 shadow-sm space-y-4">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div>
            <h3 class="font-extrabold text-sm sm:text-base text-slate-800 dark:text-slate-100">Catálogo de Rutas VGT (${routesDB.length})</h3>
            <p class="text-xs text-slate-500">Inventario oficial de rutas, postes en uso y correlativos VGT.</p>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="window.VGT.showAddRouteModal()" class="px-3 py-1.5 text-xs font-bold text-white bg-gradient-to-r from-brand-600 to-brand-500 rounded-xl shadow-xs">
              + Nueva Ruta VGT
            </button>
            <button onclick="window.VGT.resetDefaultRoutes()" class="px-3 py-1.5 text-xs font-bold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 rounded-xl">
              Restablecer
            </button>
          </div>
        </div>

        <div class="relative">
          <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none"></i>
          <input type="text" id="routeSearchInput" oninput="window.VGT.filterRoutesTable(this.value)" placeholder="Buscar por código VGT o descripción..."
            class="input-modern w-full pl-8 pr-3 py-2 text-xs border border-slate-200 dark:border-slate-700 rounded-xl">
        </div>

        <div class="max-h-[460px] overflow-y-auto custom-scrollbar border border-slate-200 dark:border-slate-800 rounded-xl">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 font-bold border-b border-slate-200 dark:border-slate-700 sticky top-0">
              <tr>
                <th class="p-2.5">Código VGT</th>
                <th class="p-2.5">Descripción / Sector</th>
                <th class="p-2.5">Postes</th>
                <th class="p-2.5">Distancia</th>
                <th class="p-2.5 text-right">Acción</th>
              </tr>
            </thead>
            <tbody id="routesTableBody" class="divide-y divide-slate-100 dark:divide-slate-800">
              ${renderRoutesTableRows(routesDB)}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  function renderRoutesTableRows(list) {
    return list.map((r, i) => `
      <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors">
        <td class="p-2.5 font-mono font-bold text-brand-600 dark:text-brand-400">${r.vgt || '-'}</td>
        <td class="p-2.5 font-semibold text-slate-800 dark:text-slate-200">${r.description || '-'}</td>
        <td class="p-2.5 text-slate-500">${r.postes || '-'}</td>
        <td class="p-2.5 text-slate-500">${r.distancia_km ? r.distancia_km + ' km' : '-'}</td>
        <td class="p-2.5 text-right">
          <button onclick="window.VGT.editRoute(${i})" class="text-slate-400 hover:text-brand-500 p-1"><i class="fa-solid fa-pen-to-square"></i></button>
          <button onclick="window.VGT.deleteRoute(${i})" class="text-slate-400 hover:text-rose-500 p-1 ml-1"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>
    `).join("");
  }

  function renderPersonnelCatalogView() {
    return `
      <div class="bg-white dark:bg-[#0c1427] rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 sm:p-5 shadow-sm space-y-4">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-3">
          <div>
            <h3 class="font-extrabold text-sm sm:text-base text-slate-800 dark:text-slate-100">Directorio de Personal & Vehículos</h3>
            <p class="text-xs text-slate-500">Gestión de técnicos (${techniciansDB.length}), choferes (${driversDB.length}) y vehículos (${vehiclesDB.length}).</p>
          </div>
          <div class="inline-flex p-1 bg-slate-100 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
            <button onclick="window.VGT.switchPersonnelSubTab('TECHS')" class="px-3 py-1 rounded-lg text-xs font-bold ${currentPersonnelSubTab === 'TECHS' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'text-slate-600 dark:text-slate-300'}">Técnicos (${techniciansDB.length})</button>
            <button onclick="window.VGT.switchPersonnelSubTab('DRIVERS')" class="px-3 py-1 rounded-lg text-xs font-bold ${currentPersonnelSubTab === 'DRIVERS' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'text-slate-600 dark:text-slate-300'}">Choferes (${driversDB.length})</button>
            <button onclick="window.VGT.switchPersonnelSubTab('VEHS')" class="px-3 py-1 rounded-lg text-xs font-bold ${currentPersonnelSubTab === 'VEHS' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'text-slate-600 dark:text-slate-300'}">Vehículos (${vehiclesDB.length})</button>
          </div>
        </div>

        <div class="max-h-[460px] overflow-y-auto custom-scrollbar border border-slate-200 dark:border-slate-800 rounded-xl">
          ${renderPersonnelTableContent()}
        </div>
      </div>
    `;
  }

  function renderPersonnelTableContent() {
    if (currentPersonnelSubTab === "TECHS") {
      return `
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 font-bold border-b border-slate-200 dark:border-slate-700 sticky top-0">
            <tr>
              <th class="p-2.5">Nombre</th>
              <th class="p-2.5">Cédula</th>
              <th class="p-2.5">Teléfono</th>
              <th class="p-2.5">Bloque / Cargo</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            ${techniciansDB.map(t => `
              <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                <td class="p-2.5 font-bold text-slate-800 dark:text-slate-200">${t.name}</td>
                <td class="p-2.5 font-mono text-slate-500">${t.cedula || '-'}</td>
                <td class="p-2.5 text-slate-500 font-mono">${t.phone || '-'}</td>
                <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${t.block === 'AFECTACIONES' ? 'bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300' : 'bg-brand-100 text-brand-800 dark:bg-brand-950/60 dark:text-brand-300'}">${t.cargo || t.block || 'TÉCNICO'}</span></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    } else if (currentPersonnelSubTab === "DRIVERS") {
      return `
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 font-bold border-b border-slate-200 dark:border-slate-700 sticky top-0">
            <tr>
              <th class="p-2.5">Nombre</th>
              <th class="p-2.5">Cédula</th>
              <th class="p-2.5">Teléfono</th>
              <th class="p-2.5">Cargo</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            ${driversDB.map(d => `
              <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                <td class="p-2.5 font-bold text-slate-800 dark:text-slate-200">${d.name}</td>
                <td class="p-2.5 font-mono text-slate-500">${d.cedula || '-'}</td>
                <td class="p-2.5 text-slate-500 font-mono">${d.phone || '-'}</td>
                <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">${d.cargo || 'CHOFER'}</span></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    } else {
      return `
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 font-bold border-b border-slate-200 dark:border-slate-700 sticky top-0">
            <tr>
              <th class="p-2.5">Modelo</th>
              <th class="p-2.5">Placa</th>
              <th class="p-2.5">Último Uso</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            ${vehiclesDB.map(v => `
              <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                <td class="p-2.5 font-bold text-slate-800 dark:text-slate-200">${v.model}</td>
                <td class="p-2.5 font-mono font-bold text-brand-600 dark:text-brand-400">${v.plate}</td>
                <td class="p-2.5 text-slate-500">${v.lastSeen || '-'}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }
  }

  function renderRightManagerialView() {
    const outputText = generateManagerialText();

    return `
      <div class="bg-white dark:bg-[#0c1427] rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 sm:p-5 shadow-sm space-y-3.5">
        <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div class="flex items-center gap-2">
            <span class="font-extrabold text-sm sm:text-base text-slate-800 dark:text-slate-100">Formato de Salida Gerencial</span>
          </div>
          <div class="inline-flex p-1 bg-slate-100 dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
            <button onclick="window.VGT.setOutputView('TEXT')" class="px-2.5 py-1 text-xs font-bold rounded-lg ${currentOutputView === 'TEXT' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'text-slate-500'}">
              WhatsApp
            </button>
            <button onclick="window.VGT.setOutputView('AUDIT')" class="px-2.5 py-1 text-xs font-bold rounded-lg ${currentOutputView === 'AUDIT' ? 'bg-[#FFC107] text-[#1A1A1A]' : 'text-slate-500'}">
              Auditoría VGT
            </button>
          </div>
        </div>

        ${currentOutputView === 'TEXT' ? `
        <div class="relative">
          <pre id="formattedOutput" class="p-3.5 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl font-mono text-[11px] text-slate-800 dark:text-slate-200 overflow-x-auto max-h-[580px] custom-scrollbar whitespace-pre-wrap">${outputText || '(Sin actividades para mostrar)'}</pre>
        </div>
        ` : `
        <div class="max-h-[580px] overflow-y-auto custom-scrollbar border border-slate-200 dark:border-slate-800 rounded-xl">
          <table class="w-full text-left text-[11px]">
            <thead class="bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold border-b border-slate-200 dark:border-slate-700 sticky top-0">
              <tr>
                <th class="p-2">Eq.</th>
                <th class="p-2">VGT</th>
                <th class="p-2">Dirección</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
              ${parsedActivitiesStore.map(a => `
                <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                  <td class="p-2 font-bold text-slate-700 dark:text-slate-300">${a.teamName}</td>
                  <td class="p-2 font-mono font-bold ${a.vgt === 'SIN NÚMERO' ? 'text-rose-500' : 'text-emerald-600 dark:text-emerald-400'}">${a.vgt}</td>
                  <td class="p-2 text-slate-600 dark:text-slate-300 line-clamp-1">${a.address}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
        `}

        <div class="flex items-center gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
          <button onclick="window.VGT.copyToClipboard()" class="btn-modern flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-bold text-white bg-gradient-to-r from-emerald-600 to-emerald-500 rounded-xl shadow-md shadow-emerald-500/20">
            <i class="fa-brands fa-whatsapp text-sm"></i> Copiar Formato WhatsApp
          </button>
          <button onclick="window.VGT.exportToExcel()" class="btn-modern inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-bold text-white bg-gradient-to-r from-brand-600 to-brand-500 rounded-xl shadow-md shadow-brand-500/20">
            <i class="fa-solid fa-file-excel text-sm"></i> Excel
          </button>
        </div>
      </div>
    `;
  }

  function generateManagerialText() {
    parsedActivitiesStore = [];
    let blocks = [];

    if (currentInputMode === "TEAM_MANAGER") {
      teamsState.forEach((team, teamIdx) => {
        const activities = parseTicketsText(team.rawTickets || "");
        if (activities.length === 0) return;

        let out = [];
        if (blocks.length === 0) {
          out.push("POWERLINK CORP.");
          out.push("");
        }

        const headerTitle = team.customTitle || `EQUIPO "${team.letter || team.id}"`;
        out.push(`${headerTitle} DE ${team.type}`);
        out.push("");
        out.push(`NÚMERO DE ACTIVIDADES: ${activities.length}`);
        out.push("");

        if (team.techs && team.techs.length > 0) {
          out.push("TÉCNICO(S):");
          team.techs.forEach(tName => {
            const tObj = findTechnician(tName);
            if (tObj) out.push(`${tObj.name}, ${tObj.cedula} (${tObj.phone})`);
            else out.push(tName);
          });
        }

        if (team.driver) {
          out.push(`CHOFER: ${team.driver}`);
        }

        if (team.vehicle && team.plate) {
          out.push(`VEHÍCULO: ${team.vehicle}, PLACA: ${team.plate}`);
        }

        out.push("");
        out.push("====================================");
        out.push("");
        out.push("DATOS DE ACTIVIDAD:");
        out.push("");

        activities.forEach((act, actIdx) => {
          const vgtCode = act.manualVgt || getVGTForAddress(act.address, act.onu, act.zona);
          parsedActivitiesStore.push({
            teamIdx: teamIdx,
            teamName: headerTitle,
            teamType: team.type,
            actIdx: actIdx,
            address: act.address,
            vgt: vgtCode,
            onu: act.onu,
            zona: act.zona
          });

          out.push(`N° DE CORRELATIVO (VGT): ${vgtCode}`);
          out.push(`TIPO DE ACTIVIDAD: ${team.type}`);
          out.push("CANTIDAD DE POSTES A TRABAJAR: 1");
          out.push(`DIRECCIÓN: ${act.address}`);
          out.push("====================================");
          if (actIdx < activities.length - 1) {
            out.push("");
          }
        });

        blocks.push(out.join("\n"));
      });
    } else {
      const rawText = document.getElementById("massiveRawInput") ? document.getElementById("massiveRawInput").value : "";
      const activities = parseTicketsText(rawText);
      if (activities.length > 0) {
        let out = ["POWERLINK CORP.", "", "ACTIVIDADES PROCESADAS: " + activities.length, "===================================="];
        activities.forEach((act, idx) => {
          const vgtCode = getVGTForAddress(act.address, act.onu, act.zona);
          parsedActivitiesStore.push({
            teamIdx: 0,
            teamName: "PROCESADO",
            teamType: "SOPORTE TÉCNICO",
            actIdx: idx,
            address: act.address,
            vgt: vgtCode,
            onu: act.onu,
            zona: act.zona
          });
          out.push(`N° DE CORRELATIVO (VGT): ${vgtCode}`);
          out.push(`DIRECCIÓN: ${act.address}`);
          out.push("====================================");
        });
        blocks.push(out.join("\n"));
      }
    }

    return blocks.join("\n\n");
  }

  function setupVgtListeners() {
    // Listeners setup
  }

  // User Actions
  function switchPreset(mode) {
    currentPresetMode = mode;
    if (mode === "WEEKDAY") {
      teamsState = JSON.parse(JSON.stringify(WEEKDAY_TEAMS));
      sanitizeTeamTechNames(teamsState);
      showToast("Lunes a Viernes activado (10 equipos)");
    } else {
      const saved = localStorage.getItem("powerlink_vgt_guard");
      if (saved) {
        try { teamsState = JSON.parse(saved); } catch(e) { teamsState = JSON.parse(JSON.stringify(DEFAULT_WEEKEND_TEAMS)); }
      } else {
        teamsState = JSON.parse(JSON.stringify(DEFAULT_WEEKEND_TEAMS));
      }
      showToast("Modo Guardia / Fin de Semana activado");
    }
    saveVgtAll();
    renderVgt();
  }

  function switchSubTab(tab) {
    currentSubTab = tab;
    if (tab === "MASSIVE") currentInputMode = "MASSIVE_INPUT";
    else currentInputMode = "TEAM_MANAGER";
    renderVgt();
  }

  function switchPersonnelSubTab(tab) {
    currentPersonnelSubTab = tab;
    renderVgt();
  }

  function setOutputView(view) {
    currentOutputView = view;
    renderVgt();
  }

  function saveGuardPreset() {
    localStorage.setItem("powerlink_vgt_guard", JSON.stringify(teamsState));
    showToast("Plantilla de Guardia guardada exitosamente");
  }

  function loadLastGuardPreset() {
    const saved = localStorage.getItem("powerlink_vgt_guard");
    if (saved) {
      teamsState = JSON.parse(saved);
      showToast("Guardia cargada");
      renderVgt();
    } else {
      showToast("No hay guardia previa guardada");
    }
  }

  function resetCurrentPreset() {
    if (confirm("¿Desea restablecer las cuadrillas a los valores por defecto?")) {
      teamsState = JSON.parse(JSON.stringify(WEEKDAY_TEAMS));
      sanitizeTeamTechNames(teamsState);
      saveVgtAll();
      renderVgt();
      showToast("Cuadrillas restablecidas");
    }
  }

  function handleTeamLetterChange(idx, val) {
    if (!teamsState[idx]) return;
    teamsState[idx].letter = val.trim().toUpperCase();
    saveVgtAll();
    renderVgt();
  }

  function handleTeamTypeChange(idx, val) {
    if (!teamsState[idx]) return;
    teamsState[idx].type = val;
    saveVgtAll();
    renderVgt();
  }

  function handleTeamDriverChange(idx, val) {
    if (!teamsState[idx]) return;
    teamsState[idx].driver = val;
    saveVgtAll();
    renderVgt();
  }

  function handleTeamVehicleChange(idx, val) {
    if (!teamsState[idx]) return;
    const parts = val.split("|");
    teamsState[idx].vehicle = parts[0] || "";
    teamsState[idx].plate = parts[1] || "";
    saveVgtAll();
    renderVgt();
  }

  function updateTeamTickets(idx, val) {
    if (!teamsState[idx]) return;
    teamsState[idx].rawTickets = val;
    saveVgtAll();
    const outPre = document.getElementById("formattedOutput");
    if (outPre) outPre.innerText = generateManagerialText();
  }

  function clearSingleTeamTickets(idx) {
    if (!teamsState[idx]) return;
    teamsState[idx].rawTickets = "";
    saveVgtAll();
    renderVgt();
    showToast("Tickets de cuadrilla limpiados");
  }

  function clearAllTeamTickets() {
    if (confirm("¿Desea limpiar los tickets de todos los equipos?")) {
      teamsState.forEach(t => t.rawTickets = "");
      saveVgtAll();
      renderVgt();
      showToast("Todos los tickets han sido vaciados");
    }
  }

  function addNewTeamCard() {
    const letter = prompt("Ingrese la letra o identificador de la nueva cuadrilla (ej: K, Z, NOCTURNA):", "N");
    if (!letter) return;
    const cleanLetter = letter.trim().toUpperCase();
    teamsState.push({
      id: "EXTRA-" + Date.now(),
      letter: cleanLetter,
      customTitle: `EQUIPO "${cleanLetter}"`,
      type: "SOPORTE TÉCNICO",
      active: true,
      techs: [],
      driver: "",
      vehicle: "EMPIRE HORSE",
      plate: "AK7J67M",
      rawTickets: ""
    });
    saveVgtAll();
    renderVgt();
    showToast(`Cuadrilla EQUIPO "${cleanLetter}" agregada`);
  }

  function removeTeamCard(idx) {
    if (teamsState.length <= 1) return;
    const team = teamsState[idx];
    if (confirm(`¿Desea eliminar la cuadrilla EQUIPO "${team.letter || team.id}"?`)) {
      teamsState.splice(idx, 1);
      saveVgtAll();
      renderVgt();
      showToast("Cuadrilla eliminada");
    }
  }

  function removeTechFromTeam(idx, techName) {
    if (!teamsState[idx]) return;
    teamsState[idx].techs = (teamsState[idx].techs || []).filter(t => t !== techName);
    saveVgtAll();
    renderVgt();
  }

  function handleInlineTechAdd(idx, inputEl) {
    const val = (inputEl.value || "").trim();
    if (!val) return;
    const found = findTechnician(val);
    if (found) {
      if (!teamsState[idx].techs.includes(found.name)) {
        teamsState[idx].techs.push(found.name);
        saveVgtAll();
        renderVgt();
      }
    } else {
      teamsState[idx].techs.push(val.toUpperCase());
      saveVgtAll();
      renderVgt();
    }
    inputEl.value = "";
  }

  function setPersonnelFilter(cat, btn) {
    currentPersonnelFilter = cat;
    const input = document.getElementById("personnelSearchInput");
    handleLivePersonnelSearch(input ? input.value : "");
  }

  function handleLivePersonnelSearch(query) {
    const resultsPanel = document.getElementById("personnelSearchResults");
    if (!resultsPanel) return;

    const q = normalizeText(query);
    if (!q && currentPersonnelFilter === "ALL") {
      resultsPanel.classList.add("hidden");
      return;
    }

    let list = [];
    if (currentPersonnelFilter === "ALL" || currentPersonnelFilter === "AFECTACIONES" || currentPersonnelFilter === "SOPORTE") {
      techniciansDB.forEach(t => {
        if (currentPersonnelFilter === "AFECTACIONES" && t.block !== "AFECTACIONES") return;
        if (currentPersonnelFilter === "SOPORTE" && t.block === "AFECTACIONES") return;
        list.push({
          type: "TECH",
          name: t.name,
          cedula: t.cedula,
          phone: t.phone,
          block: t.block || "SOPORTE",
          cargo: t.cargo || "Técnico"
        });
      });
    }

    if (currentPersonnelFilter === "ALL" || currentPersonnelFilter === "CHOFER") {
      driversDB.forEach(d => {
        list.push({
          type: "DRIVER",
          name: d.name,
          cedula: d.cedula,
          phone: d.phone,
          block: "CHOFER",
          cargo: d.cargo || "Chofer"
        });
      });
    }

    let matches = list;
    if (q) {
      matches = list.filter(p => 
        normalizeText(p.name).includes(q) ||
        normalizeText(p.cedula).includes(q) ||
        normalizeText(p.phone).includes(q) ||
        normalizeText(p.cargo).includes(q)
      );
    }

    if (matches.length === 0) {
      resultsPanel.innerHTML = `<div class="p-3 text-center text-xs text-slate-400">No se encontró personal coincidente</div>`;
      resultsPanel.classList.remove("hidden");
      return;
    }

    const teamOpts = teamsState.map((tm, i) => `<option value="${i}">Equipo "${tm.letter || tm.id}"</option>`).join("");

    resultsPanel.innerHTML = matches.slice(0, 15).map(p => {
      let assignedTeam = null;
      teamsState.forEach(tm => {
        if (tm.techs && tm.techs.some(t => normalizeText(t) === normalizeText(p.name))) assignedTeam = tm.letter || tm.id;
        if (tm.driver && normalizeText(tm.driver) === normalizeText(p.name)) assignedTeam = `${tm.letter || tm.id} (Chofer)`;
      });

      return `
        <div class="flex items-center justify-between gap-2 p-2 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs">
          <div class="min-w-0">
            <div class="font-bold text-slate-800 dark:text-slate-100 truncate">${p.name}</div>
            <div class="text-[10px] text-slate-500 font-mono">${p.cedula || '-'} · ${p.phone || '-'} · ${p.cargo}</div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            ${assignedTeam ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">Eq. ${assignedTeam}</span>` : `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">Disponible</span>`}
            <select onchange="if(this.value!=='') { window.VGT.quickAssignPerson('${p.name}', ${p.type === 'DRIVER'}, this.value); this.value=''; }"
              class="px-2 py-1 text-[11px] font-semibold border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-900">
              <option value="">Asignar a...</option>
              ${teamOpts}
            </select>
          </div>
        </div>
      `;
    }).join("");

    resultsPanel.classList.remove("hidden");
  }

  function quickAssignPerson(name, isDriver, teamIdx) {
    teamIdx = parseInt(teamIdx);
    if (isNaN(teamIdx) || !teamsState[teamIdx]) return;

    if (isDriver) {
      teamsState[teamIdx].driver = name;
      showToast(`${name} asignado como chofer`);
    } else {
      if (!teamsState[teamIdx].techs.includes(name)) {
        teamsState[teamIdx].techs.push(name);
        showToast(`${name} añadido al equipo`);
      }
    }
    saveVgtAll();
    renderVgt();
  }

  function handleMassiveInput() {
    const outPre = document.getElementById("formattedOutput");
    if (outPre) outPre.innerText = generateManagerialText();
  }

  function filterRoutesTable(q) {
    const norm = normalizeText(q);
    const filtered = routesDB.filter(r => normalizeText(r.vgt).includes(norm) || normalizeText(r.description).includes(norm));
    const tbody = document.getElementById("routesTableBody");
    if (tbody) tbody.innerHTML = renderRoutesTableRows(filtered);
  }

  function copyToClipboard() {
    const text = document.getElementById("formattedOutput") ? document.getElementById("formattedOutput").innerText : generateManagerialText();
    if (!text || text.includes("(Sin actividades")) {
      showToast("No hay actividades para copiar");
      return;
    }
    navigator.clipboard.writeText(text).then(() => {
      showToast("¡Formato de parte diario copiado para WhatsApp!");
    });
  }

  function exportToExcel() {
    if (parsedActivitiesStore.length === 0) {
      showToast("No hay actividades para exportar");
      return;
    }

    if (typeof XLSX === "undefined") {
      showToast("Biblioteca Excel no cargada todavía");
      return;
    }

    const rows = [];
    const todayStr = new Date().toISOString().split("T")[0];

    parsedActivitiesStore.forEach((act, idx) => {
      let techNames = "";
      let vehicleStr = "";

      if (currentInputMode === "TEAM_MANAGER" && teamsState[act.teamIdx]) {
        techNames = (teamsState[act.teamIdx].techs || []).map(t => {
          const found = findTechnician(t);
          return found ? `${found.name} (${found.cedula})` : t;
        }).join(" / ");
        vehicleStr = `${teamsState[act.teamIdx].vehicle || ''} [${teamsState[act.teamIdx].plate || ''}]`;
      }

      rows.push({
        "Fecha": todayStr,
        "N°": idx + 1,
        "Equipo": act.teamName,
        "Tipo de Actividad": act.teamType,
        "Técnico(s)": techNames,
        "Vehículo y Placa": vehicleStr,
        "N° Correlativo (VGT)": act.vgt,
        "Postes": 1,
        "Dirección / Detalle": act.address
      });
    });

    const ws = XLSX.utils.json_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Partes Diarios VGT");
    XLSX.writeFile(wb, `Partes_Diarios_VGT_${todayStr}.xlsx`);
    showToast("¡Archivo Excel exportado con éxito!");
  }

  // Window Exports
  window.VGT = {
    getRoutes: () => routesDB,
    getTechs: () => techniciansDB,
    getDrivers: () => driversDB,
    getVehicles: () => vehiclesDB,
    getTeams: () => teamsState,
    getVGTForAddress,
    findTechnician,
    parseTicketsText,
    saveVgtAll,
    renderVgt,
    switchPreset,
    switchSubTab,
    switchPersonnelSubTab,
    setOutputView,
    saveGuardPreset,
    loadLastGuardPreset,
    resetCurrentPreset,
    handleTeamLetterChange,
    handleTeamTypeChange,
    handleTeamDriverChange,
    handleTeamVehicleChange,
    updateTeamTickets,
    clearSingleTeamTickets,
    clearAllTeamTickets,
    addNewTeamCard,
    removeTeamCard,
    removeTechFromTeam,
    handleInlineTechAdd,
    setPersonnelFilter,
    handleLivePersonnelSearch,
    quickAssignPerson,
    handleMassiveInput,
    filterRoutesTable,
    copyToClipboard,
    exportToExcel
  };

  window.renderVgt = renderVgt;

})();
