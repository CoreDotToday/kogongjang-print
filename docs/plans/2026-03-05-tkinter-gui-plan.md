# Tkinter GUI + Flask 통합 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Tkinter GUI를 추가하여 배경 선택, 폰트/위치 설정, 서버 시작/중지를 GUI로 관리하고, config.json으로 설정을 영속화한다.

**Architecture:** gui.py가 메인 진입점. Tkinter GUI에서 설정을 관리하고, Flask 서버를 daemon 스레드로 실행. app.py는 config.json에서 설정을 읽어 PDF 생성/인쇄에 반영. 시스템 트레이 최소화는 pystray 사용.

**Tech Stack:** Python 3, Tkinter, Flask, pystray, Pillow, PyMuPDF

---

### Task 1: config.json 모듈 생성

**Files:**
- Create: `config.py`

**Step 1: config.py 작성**

```python
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
```

**Step 2: Commit**

```bash
git add config.py
git commit -m "feat: add config module for JSON-based settings"
```

---

### Task 2: app.py를 config.json 기반으로 수정

**Files:**
- Modify: `app.py` (전체)

**Step 1: app.py 수정**

아래와 같이 app.py를 수정한다. 핵심 변경사항:
- `generate_pdf()`가 config에서 배경, 폰트, 위치, 크기를 읽음
- `print_pdf()`가 config에서 SumatraPDF 경로를 읽음 (`"auto"`이면 자동 탐지)
- `/preview`, `/test`, `/print` 라우트가 config 사용
- `background.png` 심볼릭링크 불필요

```python
from flask import Flask, request, jsonify, render_template, send_file, send_from_directory
from flask_cors import CORS
import fitz  # PyMuPDF
import uuid
import os
import subprocess
import requests
import base64
from PIL import Image, ImageOps
from config import load_config, find_sumatra

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_background_path():
    config = load_config()
    return os.path.join(BASE_DIR, 'static', 'images', config['background'])


def get_font_path():
    config = load_config()
    return os.path.join(BASE_DIR, 'static', 'fonts', config['font'])


@app.route('/static/fonts/<path:filename>')
def custom_static_fonts(filename):
    return send_from_directory('static/fonts', filename, mimetype='font/ttf')


@app.route('/test', methods=['GET'])
def test_page():
    name = request.args.get('name', '홍길동')
    pdf_filename = f'{uuid.uuid4()}.pdf'
    pdf_path = os.path.join('output', pdf_filename)
    generate_pdf(name, pdf_path)
    return send_file(pdf_path, mimetype='application/pdf', as_attachment=False)


@app.route('/preview', methods=['GET'])
def preview_page():
    name = request.args.get('name', '홍길동')
    config = load_config()
    font_path = f"static/fonts/{config['font']}"
    image_path = f"static/images/{config['background']}"
    return render_template('template.html', name=name, font_path=font_path, image_path=image_path)


@app.route('/print', methods=['POST'])
def print_document():
    data = request.get_json()
    name = data.get('name', '홍길동')
    img_path = data.get('img', None)

    pdf_filename = "certificate.pdf"
    pdf_path = os.path.join('output', pdf_filename)
    generate_pdf(name, pdf_path, img_path)

    try:
        print_pdf(pdf_path)
    except Exception as e:
        print(f"Error printing PDF: {e}")
    finally:
        return jsonify({'status': 'Printed successfully'}), 200


def generate_pdf(name, pdf_path, img_path=None):
    config = load_config()
    font_path = get_font_path()
    background_image_path = get_background_path()

    pdf_document = fitz.open()
    page = pdf_document.new_page(width=595, height=842)

    # 배경 이미지
    background_rect = fitz.Rect(0, 0, 595, 842)
    if os.path.exists(background_image_path):
        page.insert_image(background_rect, filename=background_image_path)

    # 이미지 추가 (이미지가 있는 경우에만)
    if img_path:
        image_rect = fitz.Rect(69, 186, 208, 337)

        if img_path.startswith('http://') or img_path.startswith('https://'):
            response = requests.get(img_path)
            if response.status_code == 200:
                temp_img_path = 'temp_image.png'
                with open(temp_img_path, 'wb') as f:
                    f.write(response.content)
            else:
                raise Exception(f"Failed to download image from {img_path}")
        elif img_path.startswith('data:image/'):
            header, encoded = img_path.split(',', 1)
            img_data = base64.b64decode(encoded)
            temp_img_path = 'temp_image.png'
            with open(temp_img_path, 'wb') as f:
                f.write(img_data)
        else:
            temp_img_path = img_path

        if os.path.exists(temp_img_path):
            with Image.open(temp_img_path) as img:
                img = ImageOps.fit(img, (556, 604))
                bordered_img = ImageOps.expand(img, border=3, fill='black')
                bordered_img_path = 'bordered_temp_image.png'
                bordered_img.save(bordered_img_path)
            page.insert_image(image_rect, filename=bordered_img_path)

        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)
        if os.path.exists(bordered_img_path):
            os.remove(bordered_img_path)

    # 텍스트 추가 (이름)
    font_size = config['font_size']
    text_rect = fitz.Rect(
        config['name_x'], config['name_y'],
        config['name_width'], config['name_height']
    )
    page.insert_textbox(
        text_rect, name, fontsize=font_size, fontfile=font_path,
        fontname="CustomFont", align=fitz.TEXT_ALIGN_CENTER
    )

    pdf_document.save(pdf_path)
    pdf_document.close()


def print_pdf(pdf_path):
    config = load_config()
    sumatra_path = config['sumatra_path']
    if sumatra_path == 'auto':
        sumatra_path = find_sumatra()
        if not sumatra_path:
            raise Exception("SumatraPDF를 찾을 수 없습니다. config.json에서 경로를 직접 설정해주세요.")
    args = [sumatra_path, '-print-to-default', '-silent', pdf_path]
    subprocess.run(args, shell=False)


if __name__ == '__main__':
    if not os.path.exists('output'):
        os.makedirs('output')
    config = load_config()
    app.run(host='0.0.0.0', port=config['port'])
```

**Step 2: Commit**

```bash
git add app.py
git commit -m "refactor: use config.json instead of hardcoded values in app.py"
```

---

### Task 3: pystray 의존성 추가

**Files:**
- Modify: `requirements.txt`

**Step 1: requirements.txt에 pystray 추가**

```
Flask==3.0.3
PyMuPDF==1.24.10
flask_cors==5.0.0
pillow==10.4.0
requests==2.32.3
pystray==0.19.5
```

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pystray dependency for system tray support"
```

---

### Task 4: gui.py 생성 - Tkinter GUI + Flask 통합

**Files:**
- Create: `gui.py`

**Step 1: gui.py 작성**

gui.py는 다음 기능을 포함한다:

1. **설정 UI**: 배경 선택(드롭다운), 폰트 선택(드롭다운), 글자 크기, 이름 위치(X, Y, W, H), SumatraPDF 경로(자동탐지+찾아보기), 서버 포트
2. **서버 제어**: 시작/중지 버튼, 상태 표시
3. **시스템 트레이**: 최소화 시 트레이로, 트레이 메뉴에서 복원/종료
4. **설정 자동 저장**: 설정 변경 시 config.json에 저장

```python
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import glob

from config import load_config, save_config, find_sumatra

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class CertificateApp:
    def __init__(self, root):
        self.root = root
        self.root.title("감사장 인쇄 시스템")
        self.root.geometry("480x520")
        self.root.resizable(False, False)

        self.config = load_config()
        self.server_thread = None
        self.flask_app = None
        self.server_running = False

        self._build_ui()
        self._load_config_to_ui()

        # 종료 시 서버 정리
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 시스템 트레이 지원
        self.tray_icon = None
        self.root.bind("<Unmap>", self._on_minimize)

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        row = 0

        # 배경 템플릿
        ttk.Label(frame, text="배경 템플릿:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.bg_var = tk.StringVar()
        self.bg_combo = ttk.Combobox(frame, textvariable=self.bg_var, state='readonly', width=30)
        self.bg_combo['values'] = self._get_backgrounds()
        self.bg_combo.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=5)
        self.bg_combo.bind('<<ComboboxSelected>>', lambda e: self._save_ui_to_config())
        row += 1

        # 폰트
        ttk.Label(frame, text="폰트:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.font_var = tk.StringVar()
        self.font_combo = ttk.Combobox(frame, textvariable=self.font_var, state='readonly', width=30)
        self.font_combo['values'] = self._get_fonts()
        self.font_combo.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=5)
        self.font_combo.bind('<<ComboboxSelected>>', lambda e: self._save_ui_to_config())
        row += 1

        # 글자 크기
        ttk.Label(frame, text="글자 크기:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.fontsize_var = tk.IntVar()
        ttk.Spinbox(frame, from_=8, to=72, textvariable=self.fontsize_var, width=10,
                     command=self._save_ui_to_config).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        # 이름 위치
        ttk.Label(frame, text="이름 위치:").grid(row=row, column=0, sticky=tk.W, pady=5)
        pos_frame = ttk.Frame(frame)
        pos_frame.grid(row=row, column=1, columnspan=2, sticky=tk.W, pady=5)

        ttk.Label(pos_frame, text="X").pack(side=tk.LEFT)
        self.name_x_var = tk.IntVar()
        ttk.Entry(pos_frame, textvariable=self.name_x_var, width=5).pack(side=tk.LEFT, padx=(2, 8))

        ttk.Label(pos_frame, text="Y").pack(side=tk.LEFT)
        self.name_y_var = tk.IntVar()
        ttk.Entry(pos_frame, textvariable=self.name_y_var, width=5).pack(side=tk.LEFT, padx=(2, 8))

        ttk.Label(pos_frame, text="W").pack(side=tk.LEFT)
        self.name_w_var = tk.IntVar()
        ttk.Entry(pos_frame, textvariable=self.name_w_var, width=5).pack(side=tk.LEFT, padx=(2, 8))

        ttk.Label(pos_frame, text="H").pack(side=tk.LEFT)
        self.name_h_var = tk.IntVar()
        ttk.Entry(pos_frame, textvariable=self.name_h_var, width=5).pack(side=tk.LEFT, padx=(2, 0))
        row += 1

        # 위치 저장 버튼
        ttk.Button(frame, text="위치 저장", command=self._save_ui_to_config).grid(
            row=row, column=1, sticky=tk.W, pady=2)
        row += 1

        # 구분선
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=3, sticky=tk.EW, pady=10)
        row += 1

        # SumatraPDF 경로
        ttk.Label(frame, text="SumatraPDF:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.sumatra_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.sumatra_var, width=30).grid(row=row, column=1, sticky=tk.W, pady=5)
        ttk.Button(frame, text="찾아보기", command=self._browse_sumatra).grid(row=row, column=2, sticky=tk.W, padx=5)
        row += 1

        # 서버 포트
        ttk.Label(frame, text="서버 포트:").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.port_var = tk.IntVar()
        ttk.Entry(frame, textvariable=self.port_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1

        # 구분선
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=3, sticky=tk.EW, pady=10)
        row += 1

        # 서버 제어 버튼
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=5)

        self.start_btn = ttk.Button(btn_frame, text="서버 시작", command=self._start_server)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="서버 중지", command=self._stop_server, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        row += 1

        # 상태 표시
        self.status_var = tk.StringVar(value="서버 중지됨")
        self.status_label = ttk.Label(frame, textvariable=self.status_var, foreground='gray')
        self.status_label.grid(row=row, column=0, columnspan=3, pady=10)

    def _get_backgrounds(self):
        pattern = os.path.join(BASE_DIR, 'static', 'images', 'background_*.png')
        files = glob.glob(pattern)
        return [os.path.basename(f) for f in sorted(files)]

    def _get_fonts(self):
        pattern = os.path.join(BASE_DIR, 'static', 'fonts', '*.ttf')
        files = glob.glob(pattern)
        return [os.path.basename(f) for f in sorted(files)]

    def _load_config_to_ui(self):
        self.bg_var.set(self.config.get('background', ''))
        self.font_var.set(self.config.get('font', ''))
        self.fontsize_var.set(self.config.get('font_size', 24))
        self.name_x_var.set(self.config.get('name_x', 20))
        self.name_y_var.set(self.config.get('name_y', 300))
        self.name_w_var.set(self.config.get('name_width', 500))
        self.name_h_var.set(self.config.get('name_height', 350))
        sumatra = self.config.get('sumatra_path', 'auto')
        if sumatra == 'auto':
            found = find_sumatra()
            self.sumatra_var.set(found if found else 'auto')
        else:
            self.sumatra_var.set(sumatra)
        self.port_var.set(self.config.get('port', 5000))

    def _save_ui_to_config(self):
        self.config['background'] = self.bg_var.get()
        self.config['font'] = self.font_var.get()
        self.config['font_size'] = self.fontsize_var.get()
        self.config['name_x'] = self.name_x_var.get()
        self.config['name_y'] = self.name_y_var.get()
        self.config['name_width'] = self.name_w_var.get()
        self.config['name_height'] = self.name_h_var.get()
        self.config['sumatra_path'] = self.sumatra_var.get()
        self.config['port'] = self.port_var.get()
        save_config(self.config)

    def _browse_sumatra(self):
        path = filedialog.askopenfilename(
            title="SumatraPDF 선택",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
        )
        if path:
            self.sumatra_var.set(path)
            self._save_ui_to_config()

    def _start_server(self):
        if self.server_running:
            return
        self._save_ui_to_config()

        from app import app as flask_app
        from werkzeug.serving import make_server

        port = self.port_var.get()
        try:
            self.http_server = make_server('0.0.0.0', port, flask_app)
        except OSError as e:
            messagebox.showerror("오류", f"서버 시작 실패: {e}")
            return

        self.server_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.server_thread.start()
        self.server_running = True

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_var.set(f"● 서버 실행 중 (포트 {port})")
        self.status_label.config(foreground='green')

    def _stop_server(self):
        if not self.server_running:
            return
        self.http_server.shutdown()
        self.server_running = False

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("서버 중지됨")
        self.status_label.config(foreground='gray')

    def _on_minimize(self, event):
        if self.root.state() == 'iconic':
            self._hide_to_tray()

    def _hide_to_tray(self):
        try:
            import pystray
            from PIL import Image as PILImage
        except ImportError:
            return  # pystray 없으면 그냥 최소화만

        self.root.withdraw()

        # 간단한 아이콘 생성 (16x16 파란색 사각형)
        icon_image = PILImage.new('RGB', (64, 64), color=(0, 102, 204))

        menu = pystray.Menu(
            pystray.MenuItem("열기", self._show_from_tray),
            pystray.MenuItem("종료", self._quit_from_tray)
        )
        self.tray_icon = pystray.Icon("certificate", icon_image, "감사장 인쇄", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_from_tray(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.after(0, self.root.deiconify)

    def _quit_from_tray(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self._on_close)

    def _on_close(self):
        if self.server_running:
            self._stop_server()
        self.root.destroy()


if __name__ == '__main__':
    # 출력 폴더 생성
    if not os.path.exists('output'):
        os.makedirs('output')

    root = tk.Tk()
    app = CertificateApp(root)

    # 서버 자동 시작
    root.after(500, app._start_server)

    root.mainloop()
```

**Step 2: Commit**

```bash
git add gui.py
git commit -m "feat: add Tkinter GUI with Flask integration, tray support, config management"
```

---

### Task 5: .gitignore 업데이트

**Files:**
- Modify: `.gitignore`

**Step 1: config.json과 output을 .gitignore에 추가**

```
/venv
config.json
/output
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add config.json and output to gitignore"
```

---

### Task 6: 수동 테스트

**Step 1: 의존성 설치 확인**

```bash
pip install pystray
```

**Step 2: gui.py 실행 테스트**

```bash
python gui.py
```

Expected: Tkinter 창이 열리고, 배경 드롭다운에 4개 배경 표시, 0.5초 후 서버 자동 시작.

**Step 3: API 테스트**

```bash
curl http://localhost:5000/test?name=테스트
```

Expected: PDF가 생성되어 반환됨.

**Step 4: 설정 변경 테스트**

GUI에서 배경/폰트를 변경 후 다시 `/test` 호출. 변경된 설정이 반영되는지 확인.

---

### Task 7: CLAUDE.md 업데이트

**Files:**
- Modify: `CLAUDE.md`

**Step 1: CLAUDE.md에 gui.py 관련 내용 추가**

Commands 섹션에 추가:
```bash
# GUI 실행 (권장)
python gui.py
```

Architecture 섹션에 추가:
- **`gui.py`** — Tkinter GUI 메인 진입점. 설정 관리 + Flask 서버 스레드 실행
- **`config.py`** — config.json 로드/저장, SumatraPDF 자동 탐지
- **`config.json`** — 런타임 설정 (배경, 폰트, 위치, SumatraPDF 경로, 포트)

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with GUI and config documentation"
```
