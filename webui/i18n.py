import os
import json
import streamlit as st

def load_locales(i18n_dir):
    _locales = {}
    for root, dirs, files in os.walk(i18n_dir):
        for file in files:
            if file.endswith(".json"):
                lang = file.split(".")[0]
                with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                    _locales[lang] = json.loads(f.read())
    return _locales

def tr(key, locales):
    loc = locales.get(st.session_state["ui_language"], {})
    return loc.get("Translation", {}).get(key, key)
