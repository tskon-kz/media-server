import json
import os
from config import DATA_DIR, DEFAULT_CATS
from lang import ru, en

_LANGS = {"ru": ru.M, "en": en.M}
_lang     = "ru"
_qb_user  = "admin"
_qb_pass  = "adminadmin"

LANG_FILE   = f"{DATA_DIR}/lang.json"
CREDS_FILE  = f"{DATA_DIR}/creds.json"
CATS_FILE   = f"{DATA_DIR}/categories.json"
STATES_FILE = f"{DATA_DIR}/states.json"


def t(key, **kw):
    s = _LANGS[_lang][key]
    return s.format(**kw) if kw else s


def get_lang():
    return _lang


def set_lang(code):
    global _lang
    _lang = code
    _write(LANG_FILE, {"lang": code})


def get_creds():
    return _qb_user, _qb_pass


def set_creds(user, password):
    global _qb_user, _qb_pass
    _qb_user, _qb_pass = user, password
    _write(CREDS_FILE, {"qb_user": user, "qb_pass": password})


def load_cats():
    data = _read(CATS_FILE)
    return data if data is not None else DEFAULT_CATS.copy()


def save_cats(cats):
    _write(CATS_FILE, cats)


def load_states():
    return _read(STATES_FILE) or {}


def save_states(states):
    _write(STATES_FILE, states)


def init():
    global _lang, _qb_user, _qb_pass
    os.makedirs(DATA_DIR, exist_ok=True)
    lang_data  = _read(LANG_FILE)  or {}
    creds_data = _read(CREDS_FILE) or {}
    _lang    = lang_data.get("lang", "ru")
    _qb_user = creds_data.get("qb_user", _qb_user)
    _qb_pass = creds_data.get("qb_pass", _qb_pass)
    if not os.path.exists(CREDS_FILE):
        set_creds(_qb_user, _qb_pass)


def _read(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write(path, data):
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False)
