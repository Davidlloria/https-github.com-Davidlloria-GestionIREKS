from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR


class ApiSettingsService:
    CONFIG_PATH = DATA_DIR / "api_config.json"
    LEGACY_FDC_PATH = DATA_DIR / "fdc_config.json"
    LEGACY_FATSECRET_PATH = DATA_DIR / "fatsecret_config.json"

    def load_raw(self) -> dict[str, Any]:
        if not self.CONFIG_PATH.exists():
            migrated = self._migrate_legacy_if_present()
            if migrated is not None:
                return migrated
            return {}
        try:
            parsed = json.loads(self.CONFIG_PATH.read_text(encoding="utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _section(self, root: dict[str, Any], name: str) -> dict[str, Any]:
        value = root.get(name)
        return value if isinstance(value, dict) else {}

    def save_raw(self, payload: dict[str, Any]) -> Path:
        self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.CONFIG_PATH

    def get_fdc(self) -> dict[str, Any]:
        root = self.load_raw()
        fdc = self._section(root, "fdc")
        return {
            "api_key": self._decode_secret(fdc.get("api_key")),
            "data_type": str(fdc.get("data_type") or "Foundation").strip() or "Foundation",
        }

    def save_fdc(self, *, api_key: str, data_type: str) -> Path:
        root = self.load_raw()
        root["fdc"] = {
            "api_key": self._encode_secret(api_key),
            "data_type": str(data_type or "Foundation").strip() or "Foundation",
        }
        return self.save_raw(root)

    def get_openai(self) -> dict[str, Any]:
        root = self.load_raw()
        oa = self._section(root, "openai")
        return {
            "api_key": self._decode_secret(oa.get("api_key")),
            "use_ai_translation": bool(oa.get("use_ai_translation", False)),
        }

    def save_openai(self, *, api_key: str, use_ai_translation: bool) -> Path:
        root = self.load_raw()
        root["openai"] = {
            "api_key": self._encode_secret(api_key),
            "use_ai_translation": bool(use_ai_translation),
        }
        return self.save_raw(root)

    def get_fatsecret(self) -> dict[str, Any]:
        root = self.load_raw()
        fat = self._section(root, "fatsecret")
        return {
            "client_id": self._decode_secret(fat.get("client_id")),
            "client_secret": self._decode_secret(fat.get("client_secret")),
            "scope": str(fat.get("scope") or "basic").strip() or "basic",
        }

    def save_fatsecret(self, *, client_id: str, client_secret: str, scope: str) -> Path:
        root = self.load_raw()
        root["fatsecret"] = {
            "client_id": self._encode_secret(client_id),
            "client_secret": self._encode_secret(client_secret),
            "scope": str(scope or "basic").strip() or "basic",
        }
        return self.save_raw(root)

    def get_orders_mail(self) -> dict[str, Any]:
        root = self.load_raw()
        section = self._section(root, "orders_mail")
        return {
            "destino_email": str(section.get("destino_email") or "").strip(),
            "historico_dir": str(section.get("historico_dir") or "").strip(),
        }

    def save_orders_mail(self, *, destino_email: str, historico_dir: str) -> Path:
        root = self.load_raw()
        root["orders_mail"] = {
            "destino_email": str(destino_email or "").strip(),
            "historico_dir": str(historico_dir or "").strip(),
        }
        return self.save_raw(root)

    def get_warehouse(self) -> dict[str, Any]:
        root = self.load_raw()
        section = self._section(root, "warehouse")
        return {
            "low_stock_threshold_units": float(section.get("low_stock_threshold_units") or 1.0),
        }

    def save_warehouse(self, *, low_stock_threshold_units: float) -> Path:
        root = self.load_raw()
        root["warehouse"] = {
            "low_stock_threshold_units": float(low_stock_threshold_units),
        }
        return self.save_raw(root)

    def provider_payload(self, provider: str) -> dict[str, Any]:
        clean_provider = str(provider or "").strip().lower()
        config = self.load_provider(clean_provider)
        return {
            "provider": clean_provider,
            "enabled": any(bool(value) for value in config.values()),
            "config": config,
        }

    def load_provider(self, provider: str) -> dict[str, Any]:
        clean_provider = str(provider or "").strip().lower()
        if clean_provider == "fdc":
            return self.get_fdc()
        if clean_provider == "openai":
            return self.get_openai()
        if clean_provider == "fatsecret":
            return self.get_fatsecret()
        if clean_provider == "orders_mail":
            return self.get_orders_mail()
        if clean_provider == "warehouse":
            return self.get_warehouse()
        raise ValueError("Proveedor de configuracion no soportado.")

    def save_provider(self, provider: str, config: dict[str, Any]) -> dict[str, Any]:
        clean_provider = str(provider or "").strip().lower()
        payload = config if isinstance(config, dict) else {}
        if clean_provider == "fdc":
            self.save_fdc(
                api_key=str(payload.get("api_key") or "").strip(),
                data_type=str(payload.get("data_type") or "Foundation").strip() or "Foundation",
            )
        elif clean_provider == "openai":
            self.save_openai(
                api_key=str(payload.get("api_key") or "").strip(),
                use_ai_translation=bool(payload.get("use_ai_translation", False)),
            )
        elif clean_provider == "fatsecret":
            self.save_fatsecret(
                client_id=str(payload.get("client_id") or "").strip(),
                client_secret=str(payload.get("client_secret") or "").strip(),
                scope=str(payload.get("scope") or "basic").strip() or "basic",
            )
        elif clean_provider == "orders_mail":
            self.save_orders_mail(
                destino_email=str(payload.get("destino_email") or "").strip(),
                historico_dir=str(payload.get("historico_dir") or "").strip(),
            )
        elif clean_provider == "warehouse":
            self.save_warehouse(
                low_stock_threshold_units=float(payload.get("low_stock_threshold_units") or 1.0),
            )
        else:
            raise ValueError("Proveedor de configuracion no soportado.")
        return self.provider_payload(clean_provider)

    def _migrate_legacy_if_present(self) -> dict[str, Any] | None:
        if not self.LEGACY_FDC_PATH.exists() and not self.LEGACY_FATSECRET_PATH.exists():
            return None
        payload: dict[str, Any] = {}
        if self.LEGACY_FDC_PATH.exists():
            try:
                parsed_fdc = json.loads(self.LEGACY_FDC_PATH.read_text(encoding="utf-8"))
                fdc = parsed_fdc if isinstance(parsed_fdc, dict) else {}
            except Exception:
                fdc = {}
            payload["fdc"] = {
                "api_key": self._encode_secret(str(fdc.get("api_key") or "").strip()),
                "data_type": str(fdc.get("data_type") or "Foundation").strip() or "Foundation",
            }
            payload["openai"] = {
                "api_key": self._encode_secret(str(fdc.get("openai_api_key") or "").strip()),
                "use_ai_translation": bool(fdc.get("use_ai_translation", False)),
            }
        if self.LEGACY_FATSECRET_PATH.exists():
            try:
                parsed_fat = json.loads(self.LEGACY_FATSECRET_PATH.read_text(encoding="utf-8"))
                fat = parsed_fat if isinstance(parsed_fat, dict) else {}
            except Exception:
                fat = {}
            payload["fatsecret"] = {
                "client_id": self._encode_secret(str(fat.get("client_id") or "").strip()),
                "client_secret": self._encode_secret(str(fat.get("client_secret") or "").strip()),
                "scope": str(fat.get("scope") or "basic").strip() or "basic",
            }
        self.save_raw(payload)
        return payload

    def _encode_secret(self, value: str) -> Any:
        clear = str(value or "")
        if not clear:
            return ""
        protected = self._dpapi_protect(clear)
        if protected is None:
            return clear
        return {"enc": "dpapi", "v": base64.b64encode(protected).decode("ascii")}

    def _decode_secret(self, stored: Any) -> str:
        if stored is None:
            return ""
        if isinstance(stored, str):
            return stored
        if isinstance(stored, dict) and stored.get("enc") == "dpapi":
            blob64 = str(stored.get("v") or "").strip()
            if not blob64:
                return ""
            try:
                raw = base64.b64decode(blob64)
            except Exception:
                return ""
            clear = self._dpapi_unprotect(raw)
            return clear if clear is not None else ""
        return ""

    def _dpapi_protect(self, text: str) -> bytes | None:
        if os.name != "nt":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

            data = text.encode("utf-8")
            in_buf = (ctypes.c_byte * len(data)).from_buffer_copy(data)
            in_blob = DATA_BLOB(len(data), in_buf)
            out_blob = DATA_BLOB()
            crypt32 = ctypes.windll.crypt32
            kernel32 = ctypes.windll.kernel32
            ok = crypt32.CryptProtectData(
                ctypes.byref(in_blob),
                None,
                None,
                None,
                None,
                0,
                ctypes.byref(out_blob),
            )
            if not ok:
                return None
            try:
                result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            finally:
                kernel32.LocalFree(out_blob.pbData)
            return bytes(result)
        except Exception:
            return None

    def _dpapi_unprotect(self, blob: bytes) -> str | None:
        if os.name != "nt":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

            in_buf = (ctypes.c_byte * len(blob)).from_buffer_copy(blob)
            in_blob = DATA_BLOB(len(blob), in_buf)
            out_blob = DATA_BLOB()
            crypt32 = ctypes.windll.crypt32
            kernel32 = ctypes.windll.kernel32
            ok = crypt32.CryptUnprotectData(
                ctypes.byref(in_blob),
                None,
                None,
                None,
                None,
                0,
                ctypes.byref(out_blob),
            )
            if not ok:
                return None
            try:
                result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            finally:
                kernel32.LocalFree(out_blob.pbData)
            return result.decode("utf-8")
        except Exception:
            return None
