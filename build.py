"""Nuitka 빌드 스크립트 — 단일 exe 생성"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from version import __version__, __app_name__, __copyright__

DIST_DIR = "dist"
APP_NAME = "감사장인쇄"

# Windows 파일 버전은 M.m.p.b 4-tuple 형식 요구.
file_version_4 = __version__ if __version__.count('.') >= 3 else f"{__version__}.0"

cmd = [
    sys.executable, "-m", "nuitka",
    "--mode=onefile",
    "--zig",
    "--windows-console-mode=disable",
    "--output-filename=감사장인쇄.exe",
    "--output-dir=dist",

    # Windows exe 파일 속성 메타데이터 (탐색기 → 속성 → 세부 정보)
    f"--product-name={__app_name__}",
    f"--product-version={__version__}",
    f"--file-version={file_version_4}",
    f"--file-description={__app_name__}",
    f"--copyright={__copyright__}",

    # 패키지 포함
    "--include-package=flask",
    "--include-package=werkzeug",
    "--include-package=jinja2",
    "--include-package=markupsafe",
    "--include-package=flask_cors",
    "--include-package=fpdf",
    "--include-package=PIL",
    "--include-package=requests",
    "--include-package=pystray",
    "--include-package=customtkinter",
    "--include-package-data=customtkinter",

    # 불필요한 패키지 제외 (Anaconda 환경에서 딸려오는 것 방지)
    "--nofollow-import-to=fitz",
    "--nofollow-import-to=pymupdf",
    "--nofollow-import-to=scipy",
    "--nofollow-import-to=numpy",
    "--nofollow-import-to=pandas",
    "--nofollow-import-to=matplotlib",
    "--nofollow-import-to=pytest",
    "--nofollow-import-to=IPython",
    "--nofollow-import-to=notebook",
    "--nofollow-import-to=setuptools",
    "--nofollow-import-to=pip",
    "--nofollow-import-to=conda",
    "--nofollow-import-to=sklearn",
    "--nofollow-import-to=torch",
    "--nofollow-import-to=tensorflow",
    "--nofollow-import-to=mkl",

    # tkinter 플러그인
    "--enable-plugin=tk-inter",

    # 정적 파일 포함
    "--include-data-dir=static=static",
    "--include-data-dir=templates=templates",
    # About 다이얼로그에서 표시할 릴리즈 노트
    "--include-data-file=CHANGELOG.md=CHANGELOG.md",

    # 멀티코어 빌드
    f"--jobs={os.cpu_count()}",

    # 메인 스크립트
    "gui.py",
]

print(f"빌드 시작... (버전 {__version__})")
print(" ".join(cmd))
result = subprocess.run(cmd)
if result.returncode == 0:
    exe_path = os.path.join(DIST_DIR, f"{APP_NAME}.exe")
    exe_size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"\n빌드 완료! {exe_path} ({exe_size_mb:.1f} MB)")
else:
    print(f"\n빌드 실패 (exit code: {result.returncode})")
    sys.exit(1)
