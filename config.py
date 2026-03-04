import json
import os
import sys

# exe 빌드 시 sys.argv[0] 기준, 개발 시 __file__ 기준
APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CONFIG_PATH = os.path.join(APP_DIR, 'config.json')
BACKGROUNDS_DIR = os.path.join(APP_DIR, 'backgrounds')

DEFAULT_CONFIG = {
    "background": "background_kogongjang.png",
    "font": "nanum.ttf",
    "font_size": 24,
    "name_x": 20,
    "name_y": 300,
    "name_width": 500,
    "name_height": 350,
    "sumatra_path": "auto",
    "port": 5000,
    "kiosk_url": "",
    "kiosk_auto_open": False,
    "kiosk_zoom": 100
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


def get_backgrounds_dir():
    """외부 배경 폴더 경로 반환. 없으면 생성."""
    if not os.path.exists(BACKGROUNDS_DIR):
        os.makedirs(BACKGROUNDS_DIR)
    return BACKGROUNDS_DIR


def find_background(filename):
    """배경 이미지 파일의 절대 경로를 반환. 외부 폴더 우선, 없으면 내장 static."""
    # 외부 backgrounds/ 폴더 우선
    external = os.path.join(get_backgrounds_dir(), filename)
    if os.path.exists(external):
        return external
    # 내장 static/images/
    internal = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'images', filename)
    if os.path.exists(internal):
        return internal
    return None


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
