from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.warehouse_entry_repair_service import WarehouseEntryRepairService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audita o repara la coherencia entre albaranes y entradas de almacen."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica la reparacion. Sin esta opcion solo se realiza la auditoria.",
    )
    args = parser.parse_args()
    service = WarehouseEntryRepairService()
    if not args.apply:
        print(json.dumps(service.audit().as_dict(), indent=2, ensure_ascii=False))
        return 0

    result = service.repair()
    print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
    remaining = result.after.as_dict()
    return (
        0
        if result.integrity_check.lower() == "ok" and not any(remaining.values())
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
