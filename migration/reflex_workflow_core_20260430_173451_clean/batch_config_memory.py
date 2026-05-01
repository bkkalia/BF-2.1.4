import json
import logging
import os

logger = logging.getLogger(__name__)


class BatchConfigMemory:
    """Persists batch scrape groups and last-used batch settings."""

    def __init__(self, config_file="batch_scrape_profiles.json"):
        self.config_file = config_file
        self.config_data = self._load_config()

    def _default_config(self):
        return {
            "groups": {},
            "last_selection": [],
            "mode": "sequential",
            "max_parallel": 2,
            "only_new": True,
            "delta_mode": "quick",
            "ip_safety": {
                "per_domain_max": 1,
                "min_delay_sec": 1.0,
                "max_delay_sec": 3.0,
                "cooldown_sec": 10,
                "max_retries": 2
            }
        }

    def _load_config(self):
        if not os.path.exists(self.config_file):
            return self._default_config()

        try:
            with open(self.config_file, "r", encoding="utf-8") as config_handle:
                loaded = json.load(config_handle)
            if not isinstance(loaded, dict):
                return self._default_config()

            default = self._default_config()
            default.update(loaded)
            if not isinstance(default.get("groups"), dict):
                default["groups"] = {}
            if not isinstance(default.get("last_selection"), list):
                default["last_selection"] = []
            if not isinstance(default.get("ip_safety"), dict):
                default["ip_safety"] = self._default_config()["ip_safety"].copy()
            return default
        except Exception as error:
            logger.error(f"Error loading batch config memory: {error}")
            return self._default_config()

    def _save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as config_handle:
                json.dump(self.config_data, config_handle, indent=2, ensure_ascii=False)
            return True
        except Exception as error:
            logger.error(f"Error saving batch config memory: {error}")
            return False

    def get_groups(self):
        return dict(self.config_data.get("groups", {}))

    def save_group(self, group_name, portal_names):
        clean_name = (group_name or "").strip()
        if not clean_name:
            return False

        unique_portals = sorted(set([name for name in portal_names if name]))
        self.config_data.setdefault("groups", {})[clean_name] = unique_portals
        return self._save_config()

    def delete_group(self, group_name):
        groups = self.config_data.setdefault("groups", {})
        if group_name in groups:
            del groups[group_name]
            return self._save_config()
        return False

    def save_last_settings(self, selection, mode, max_parallel, ip_safety=None, only_new=True, delta_mode="quick"):
        self.config_data["last_selection"] = sorted(set(selection or []))
        self.config_data["mode"] = mode if mode in ("sequential", "parallel") else "sequential"
        self.config_data["only_new"] = bool(only_new)
        clean_delta_mode = str(delta_mode or "quick").strip().lower()
        self.config_data["delta_mode"] = clean_delta_mode if clean_delta_mode in ("quick", "full") else "quick"
        try:
            self.config_data["max_parallel"] = max(1, int(max_parallel))
        except Exception:
            self.config_data["max_parallel"] = 2

        safe = ip_safety or {}
        defaults = self._default_config()["ip_safety"]
        merged = defaults.copy()
        merged.update({k: safe.get(k, defaults[k]) for k in defaults.keys()})

        try:
            merged["per_domain_max"] = max(1, int(merged["per_domain_max"]))
        except Exception:
            merged["per_domain_max"] = defaults["per_domain_max"]

        try:
            merged["min_delay_sec"] = max(0.0, float(merged["min_delay_sec"]))
        except Exception:
            merged["min_delay_sec"] = defaults["min_delay_sec"]

        try:
            merged["max_delay_sec"] = max(merged["min_delay_sec"], float(merged["max_delay_sec"]))
        except Exception:
            merged["max_delay_sec"] = max(merged["min_delay_sec"], defaults["max_delay_sec"])

        try:
            merged["cooldown_sec"] = max(0, int(merged["cooldown_sec"]))
        except Exception:
            merged["cooldown_sec"] = defaults["cooldown_sec"]

        try:
            merged["max_retries"] = max(0, int(merged["max_retries"]))
        except Exception:
            merged["max_retries"] = defaults["max_retries"]

        self.config_data["ip_safety"] = merged
        return self._save_config()

    def get_last_settings(self):
        return {
            "last_selection": list(self.config_data.get("last_selection", [])),
            "mode": self.config_data.get("mode", "sequential"),
            "max_parallel": self.config_data.get("max_parallel", 2),
            "only_new": bool(self.config_data.get("only_new", True)),
            "delta_mode": str(self.config_data.get("delta_mode", "quick") or "quick").strip().lower(),
            "ip_safety": self.config_data.get("ip_safety", self._default_config()["ip_safety"].copy())
        }


_batch_memory = None


def get_batch_memory():
    global _batch_memory
    if _batch_memory is None:
        _batch_memory = BatchConfigMemory()
    return _batch_memory
