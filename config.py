import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

DEFAULT_CONFIG = {
    "background": "background_kogongjang.png",
    "font": "nanum.ttf",
    "font_size": 24,
    "name_x": 20,
    "name_y": 300,
    "name_width": 500,
    "name_height": 350,
    "sumatra_path": "auto",
    "port": 5000
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            saved = json.load(f)
        config = {**DEFAULT_CONFIG, **saved}
    else:
        config = DEFAULT_CONFIG.copy()
        save_config(config)
    return config


def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def find_sumatra():
    """SumatraPDF 자동 탐지. 찾으면 경로 반환, 못 찾으면 None."""
    candidates = [
        os.path.expandvars(r'%LOCALAPPDATA%\SumatraPDF\SumatraPDF.exe'),
        r'C:\Program Files\SumatraPDF\SumatraPDF.exe',
        r'C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None
