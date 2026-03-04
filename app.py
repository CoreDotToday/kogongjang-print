from flask import Flask, request, jsonify, render_template, send_file, send_from_directory
from flask_cors import CORS
import fitz  # PyMuPDF
import uuid
import os
import subprocess
import requests
import base64
from PIL import Image, ImageOps
from config import load_config, find_sumatra, find_background, get_backgrounds_dir

app = Flask(__name__)
CORS(app)

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
