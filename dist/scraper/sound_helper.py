import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Sound kinds
SOUND_DING = "ding"
SOUND_SUCCESS = "success"
SOUND_ERROR = "error"

# Env var names to allow easy overrides
_ENV_VARS = {
    SOUND_DING: "BF_SOUND_DING",
    SOUND_SUCCESS: "BF_SOUND_SUCCESS",
    SOUND_ERROR: "BF_SOUND_ERROR",
}

# Try Windows winsound for reliable async playback of system alias or WAV files
try:
    import winsound  # type: ignore
    _HAS_WINSOUND = True
except Exception:
    winsound = None
    _HAS_WINSOUND = False

# Locate project settings (best-effort): look for settings.json in repo root
def _load_settings_json() -> dict:
    try:
        # Assume this module lives under scraper/; project root is parent.parent
        repo_root = Path(__file__).resolve().parents[1]
        settings_path = repo_root / "settings.json"
        if settings_path.is_file():
            with settings_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception as e:
        logger.debug(f"Could not load settings.json: {e}")
    return {}

def _get_custom_sound_path(kind: str) -> Optional[str]:
    # 1) Check environment variable
    env_name = _ENV_VARS.get(kind)
    if env_name:
        env_val = os.environ.get(env_name)
        if env_val:
            p = Path(env_val).expanduser()
            if p.is_file():
                return str(p)
    # 2) Check settings.json keys: sound_ding_file, sound_success_file, sound_error_file
    settings = _load_settings_json()
    key = f"sound_{kind}_file"
    val = settings.get(key)
    if val:
        p = Path(val).expanduser()
        if p.is_file():
            return str(p)
    # 3) Check config.py constants as fallback if set (import lazily)
    try:
        from config import SOUND_DING_FILE, SOUND_SUCCESS_FILE, SOUND_ERROR_FILE, ENABLE_SOUNDS  # type: ignore
        if not ENABLE_SOUNDS:
            return None
        cfg_map = {
            SOUND_DING: SOUND_DING_FILE,
            SOUND_SUCCESS: SOUND_SUCCESS_FILE,
            SOUND_ERROR: SOUND_ERROR_FILE
        }
        cfg_val = cfg_map.get(kind)
        if cfg_val:
            p = Path(cfg_val).expanduser()
            if p.is_file():
                return str(p)
    except Exception:
        pass
    return None

def _play_winsound_file(path: str):
    try:
        if _HAS_WINSOUND:
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)  # type: ignore
            return True
    except Exception as e:
        logger.debug(f"winsound failed to play {path}: {e}")
    return False

def _play_winsound_alias(alias: str):
    try:
        if _HAS_WINSOUND:
            winsound.PlaySound(alias, winsound.SND_ALIAS | winsound.SND_ASYNC)  # type: ignore
            return True
    except Exception as e:
        logger.debug(f"winsound failed to play alias {alias}: {e}")
    return False

def play_sound(kind: str) -> None:
    """Play a non-blocking sound for the given kind.
    Priority:
      1) Env var BF_SOUND_<KIND> -> absolute file path
      2) settings.json sound_<kind>_file
      3) config.py SOUND_*_FILE
      4) On Windows: system alias (Asterisk / Exclamation / Hand)
      5) Fallback: ASCII bell (non-blocking print)
    """
    try:
        if kind not in (SOUND_DING, SOUND_SUCCESS, SOUND_ERROR):
            return
        # custom file path preferred
        custom = _get_custom_sound_path(kind)
        if custom:
            if _play_winsound_file(custom):
                logger.debug(f"Played custom sound file for {kind}: {custom}")
                return
            else:
                logger.debug(f"Custom sound path exists but could not be played: {custom}")
        # If on Windows, use system alias names
        if _HAS_WINSOUND:
            alias_map = {
                SOUND_DING: "SystemAsterisk",
                SOUND_SUCCESS: "SystemExclamation",
                SOUND_ERROR: "SystemHand"
            }
            alias = alias_map.get(kind)
            if alias and _play_winsound_alias(alias):
                logger.debug(f"Played system alias for {kind}: {alias}")
                return
        # Fallback: ASCII bell - best-effort, non-blocking
        try:
            print("\a", end="", flush=True)
            logger.debug(f"Played fallback bell for {kind}")
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"play_sound failed for kind={kind}: {e}")
