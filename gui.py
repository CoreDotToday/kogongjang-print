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

        # 간단한 아이콘 생성 (64x64 파란색 사각형)
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
