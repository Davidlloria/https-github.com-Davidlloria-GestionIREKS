from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
LEGACY_DB_PATH = DATA_DIR / "gestion_formulas.db"
DB_PATH = DATA_DIR / "gestion_ireks.db"
DB_URL = f"sqlite:///{DB_PATH}"
PEDIDOS_HISTORICO_DIR = DATA_DIR / "exports" / "pedidos_historico"
PEDIDOS_EMAIL_DESTINO = ""

# UI flags
# Activa la página de Clientes basada en QML.
USE_QML_CUSTOMERS = False

