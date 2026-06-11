import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = BASE_DIR / "data"
_DATA_DIR_ENV = os.environ.get("GESTION_IREKS_DATA_DIR")
DATA_DIR = Path(_DATA_DIR_ENV) if _DATA_DIR_ENV else DEFAULT_DATA_DIR
LEGACY_DB_PATH = DATA_DIR / "gestion_formulas.db"
DB_PATH = DATA_DIR / "gestion_ireks.db"
DB_URL = f"sqlite:///{DB_PATH}"
PEDIDOS_HISTORICO_DIR = DATA_DIR / "exports" / "pedidos_historico"
PEDIDOS_EMAIL_DESTINO = ""

# UI flags
# Activa la pagina de Clientes basada en QML (experimental).
# Recomendado mantener en False y habilitar solo por entorno en pruebas:
#   USE_QML_CUSTOMERS=1
USE_QML_CUSTOMERS = False

