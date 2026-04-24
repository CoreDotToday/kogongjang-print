from flask import Flask, request, jsonify, render_template, send_file, send_from_directory
from flask_cors import CORS
from fpdf import FPDF
import uuid
import os
import subprocess
import requests
import base64
from PIL import Image, ImageOps
from config import load_config, find_sumatra, find_background, find_font, get_backgrounds_dir, get_output_dir

app = Flask(__name__)
CORS(app)

# GUI에서 키오스크 프로세스를 공유하기 위한 변수
kiosk_process_holder = {"process": None}

# GUI가 graceful shutdown 콜백을 등록하는 곳. /quit 라우트가 호출한다.
shutdown_callback_holder = {"callback": None}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route('/backgrounds/<path:filename>')
def serve_background(filename):
    """외부 backgrounds/ 폴더의 이미지를 서빙"""
    return send_from_directory(get_backgrounds_dir(), filename)


def get_background_path():
    config = load_config()
    path = find_background(config['background'])
    return path if path else os.path.join(BASE_DIR, 'static', 'images', config['background'])


def get_font_path():
    config = load_config()
    path = find_font(config['font'])
    return path if path else os.path.join(BASE_DIR, 'static', 'fonts', config['font'])


@app.route('/static/fonts/<path:filename>')
def custom_static_fonts(filename):
    return send_from_directory('static/fonts', filename, mimetype='font/ttf')


@app.route('/test', methods=['GET'])
def test_page():
    name = request.args.get('name', '홍길동')
    pdf_filename = f'{uuid.uuid4()}.pdf'
    pdf_path = os.path.join(get_output_dir(), pdf_filename)
    generate_pdf(name, pdf_path)
    return send_file(pdf_path, mimetype='application/pdf', as_attachment=False)


@app.route('/preview', methods=['GET'])
def preview_page():
    name = request.args.get('name', '홍길동')
    config = load_config()
    font_path = f"static/fonts/{config['font']}"
    bg_file = config['background']
    # 외부 폴더에 있으면 /backgrounds/ 경로, 아니면 내장 static
    ext_path = os.path.join(get_backgrounds_dir(), bg_file)
    if os.path.exists(ext_path):
        image_path = f"backgrounds/{bg_file}"
    else:
        image_path = f"static/images/{bg_file}"
    return render_template('template.html', name=name, font_path=font_path, image_path=image_path)


@app.route('/print', methods=['POST'])
def print_document():
    data = request.get_json()
    name = data.get('name', '홍길동')
    img_path = data.get('img', None)

    pdf_filename = "certificate.pdf"
    pdf_path = os.path.join(get_output_dir(), pdf_filename)
    generate_pdf(name, pdf_path, img_path)

    try:
        print_pdf(pdf_path)
    except Exception as e:
        print(f"Error printing PDF: {e}")
    finally:
        return jsonify({'status': 'Printed successfully'}), 200


@app.route('/close-kiosk', methods=['POST'])
def close_kiosk():
    proc = kiosk_process_holder.get("process")
    if proc and proc.poll() is None:
        try:
            # Chrome은 GPU/렌더러/네트워크 등 자식 프로세스를 띄우므로
            # taskkill /F /T 로 PID 트리를 통째로 강제 종료해야 창이 닫힌다.
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                shell=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                timeout=5,
            )
        except Exception:
            proc.terminate()  # 폴백
        kiosk_process_holder["process"] = None
        return jsonify({'status': 'Kiosk closed'}), 200
    return jsonify({'status': 'No kiosk running'}), 200


@app.route('/shutdown', methods=['POST'])
def shutdown():
    subprocess.Popen(['shutdown', '/s', '/t', '0'], shell=False)
    return jsonify({'status': 'Shutting down'}), 200


@app.route('/quit', methods=['POST'])
def quit_app():
    """GUI(서버 + 트레이 + 키오스크) 정상 종료. PC 전원에는 영향 없음."""
    cb = shutdown_callback_holder.get("callback")
    if cb:
        cb()
        return jsonify({'status': 'Shutting down'}), 200
    return jsonify({'status': 'No shutdown handler registered'}), 503


def pt_to_mm(pt):
    """포인트(pt) 단위를 mm 단위로 변환"""
    return pt * 25.4 / 72


def generate_pdf(name, pdf_path, img_path=None):
    config = load_config()
    font_path = get_font_path()
    background_image_path = get_background_path()

    pdf = FPDF(unit='mm', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    # 배경 이미지
    if os.path.exists(background_image_path):
        pdf.image(background_image_path, x=0, y=0, w=210, h=297)

    # 이미지 추가 (이미지가 있는 경우에만)
    if img_path:
        # fitz.Rect(69, 186, 208, 337) → mm 변환
        img_x = pt_to_mm(69)
        img_y = pt_to_mm(186)
        img_w = pt_to_mm(208 - 69)
        img_h = pt_to_mm(337 - 186)

        temp_img_path = None
        bordered_img_path = None

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

        if temp_img_path and os.path.exists(temp_img_path):
            with Image.open(temp_img_path) as img:
                img = ImageOps.fit(img, (556, 604))
                bordered_img = ImageOps.expand(img, border=3, fill='black')
                bordered_img_path = 'bordered_temp_image.png'
                bordered_img.save(bordered_img_path)
            pdf.image(bordered_img_path, x=img_x, y=img_y, w=img_w, h=img_h)

        if temp_img_path and temp_img_path != img_path and os.path.exists(temp_img_path):
            os.remove(temp_img_path)
        if bordered_img_path and os.path.exists(bordered_img_path):
            os.remove(bordered_img_path)

    # 텍스트 추가 (이름) — 한글 폰트 등록
    pdf.add_font('CustomFont', '', font_path, uni=True)
    font_size = config['font_size']
    pdf.set_font('CustomFont', '', font_size)

    # config 좌표(pt)를 mm로 변환
    text_x = pt_to_mm(config['name_x'])
    text_y = pt_to_mm(config['name_y'])
    text_w = pt_to_mm(config['name_width'] - config['name_x'])
    text_h = pt_to_mm(config['name_height'] - config['name_y'])

    pdf.set_xy(text_x, text_y)
    pdf.cell(w=text_w, h=text_h, text=name, align='C')

    pdf.output(pdf_path)


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
    get_output_dir()  # data/output/ 보장 생성
    config = load_config()
    app.run(host='0.0.0.0', port=config['port'])
