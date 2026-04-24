import json
import os
import shutil
import sys

# exe 빌드 시 sys.argv[0] 기준, 개발 시도 동일.
APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

# 사용자 데이터(설정/배경/폰트/PDF/로그)는 모두 data/ 한 폴더에 모은다.
DATA_DIR = os.path.join(APP_DIR, 'data')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')
BACKGROUNDS_DIR = os.path.join(DATA_DIR, 'backgrounds')
FONTS_DIR = os.path.join(DATA_DIR, 'fonts')
OUTPUT_DIR = os.path.join(DATA_DIR, 'output')
ERROR_LOG_PATH = os.path.join(DATA_DIR, 'error.log')

# 번들된 정적 자원은 소스/exe에 패키징되어 있다. (config.py가 들어 있는 위치 기준)
_BUNDLED_DIR = os.path.dirname(os.path.abspath(__file__))
BUNDLED_IMAGES_DIR = os.path.join(_BUNDLED_DIR, 'static', 'images')
BUNDLED_FONTS_DIR = os.path.join(_BUNDLED_DIR, 'static', 'fonts')

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


def _migrate_legacy_layout():
    """과거 버전에서 exe 옆에 직접 두던 파일들을 data/로 이동.
    같은 이름이 data/에 이미 있으면 건드리지 않는다."""
    legacy_items = [
        (os.path.join(APP_DIR, 'config.json'), CONFIG_PATH),
        (os.path.join(APP_DIR, 'backgrounds'), BACKGROUNDS_DIR),
        (os.path.join(APP_DIR, 'output'), OUTPUT_DIR),
    ]
    for old, new in legacy_items:
        if os.path.exists(old) and not os.path.exists(new):
            try:
                shutil.move(old, new)
            except OSError:
                pass


def get_data_dir():
    """data/ 폴더 경로를 반환. 없으면 생성하고 레거시 파일을 1회 이동."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        _migrate_legacy_layout()
    return DATA_DIR


def get_backgrounds_dir():
    """사용자 배경 폴더(data/backgrounds). 없으면 생성."""
    get_data_dir()
    if not os.path.exists(BACKGROUNDS_DIR):
        os.makedirs(BACKGROUNDS_DIR)
    return BACKGROUNDS_DIR


def get_fonts_dir():
    """사용자 폰트 폴더(data/fonts). 없으면 생성."""
    get_data_dir()
    if not os.path.exists(FONTS_DIR):
        os.makedirs(FONTS_DIR)
    return FONTS_DIR


def get_output_dir():
    """PDF 출력 폴더(data/output). 없으면 생성."""
    get_data_dir()
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    return OUTPUT_DIR


def load_config():
    get_data_dir()  # 마이그레이션 트리거
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            config = {**DEFAULT_CONFIG, **saved}
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            # 비정상 종료로 config.json이 NUL로 채워지는 등 깨진 경우:
            # 깨진 파일을 .corrupt로 보존하고 기본값으로 복구한다.
            try:
                os.replace(CONFIG_PATH, CONFIG_PATH + '.corrupt')
            except OSError:
                pass
            config = DEFAULT_CONFIG.copy()
            save_config(config)
    else:
        config = DEFAULT_CONFIG.copy()
        save_config(config)
    return config


def save_config(config):
    # tmp에 먼저 쓰고 fsync 후 os.replace로 바꿔야
    # 저장 도중 정전/강제종료 시 NUL로 채워진 파일이 남는 사고를 막을 수 있다.
    get_data_dir()
    tmp_path = CONFIG_PATH + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, CONFIG_PATH)


def find_background(filename):
    """배경 이미지 절대 경로. 사용자 폴더 우선, 없으면 번들."""
    if not filename:
        return None
    user = os.path.join(get_backgrounds_dir(), filename)
    if os.path.exists(user):
        return user
    bundled = os.path.join(BUNDLED_IMAGES_DIR, filename)
    if os.path.exists(bundled):
        return bundled
    return None


def find_font(filename):
    """폰트 파일 절대 경로. 사용자 폴더 우선, 없으면 번들."""
    if not filename:
        return None
    user = os.path.join(get_fonts_dir(), filename)
    if os.path.exists(user):
        return user
    bundled = os.path.join(BUNDLED_FONTS_DIR, filename)
    if os.path.exists(bundled):
        return bundled
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
