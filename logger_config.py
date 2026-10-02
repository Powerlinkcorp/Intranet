import logging
import os
from logging.handlers import RotatingFileHandler

# Aseguramos que la carpeta logs exista en la raiz del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def get_logger(module_name: str) -> logging.Logger:
    """
    Crea y devuelve un logger configurado para guardar en logs/<module_name>.log
    y al mismo tiempo imprimir en consola.
    """
    logger = logging.getLogger(module_name)
    logger.setLevel(logging.INFO)

    # Evita duplicar logs si se llama multiples veces
    if not logger.handlers:
        # Formato del log
        formatter = logging.Formatter(
            '%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'
        )

        # 1. Handler para archivo (con rotacion automatica cada 5MB, guardando hasta 3 respaldos)
        log_file = os.path.join(LOG_DIR, f"{module_name}.log")
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)

        # 2. Handler para la consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)

        # Agregamos los handlers al logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
