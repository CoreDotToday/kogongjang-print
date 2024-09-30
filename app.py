from flask import Flask, request, jsonify, render_template, send_file, send_from_directory
from flask_cors import CORS  # CORS 추가
import fitz  # PyMuPDF
import uuid
import os
import subprocess
import requests
import base64

app = Flask(__name__)

CORS(app)

@app.route('/static/fonts/<path:filename>')
def custom_static_fonts(filename):
    return send_from_directory('static/fonts', filename, mimetype='font/ttf')

@app.route('/test', methods=['GET'])
def test_page():
    name = request.args.get('name', '홍길동')  # 기본값 설정

    # PDF 생성 테스트 (파일 경로는 출력하지 않고 브라우저에서 바로 확인)
    pdf_filename = f'{uuid.uuid4()}.pdf'
    pdf_path = os.path.join('output', pdf_filename)
    
    # 절대 경로 폰트 설정
    font_path = os.path.abspath('static/fonts/nanum.ttf')  # TTF 폰트 파일 경로 지정
    generate_pdf(name, pdf_path, font_path)

    # PDF 파일을 브라우저에서 다운로드하거나 표시할 수 있도록 응답
    return send_file(pdf_path, mimetype='application/pdf', as_attachment=False)

@app.route('/preview', methods=['GET'])
def preview_page():
    name = request.args.get('name', '홍길동')  # 기본값 설정

    # HTML 미리보기 렌더링
    font_path = 'static/fonts/nanum.ttf'
    image_path = 'static/images/background.png'
    html_out = render_template('template.html', name=name, font_path=font_path, image_path=image_path)

    return html_out

@app.route('/print', methods=['POST'])
def print_document():
    data = request.get_json()
    name = data.get('name', '홍길동')  # 기본값 설정
    img_path = data.get('img', '')  # 이미지 데이터

    # PDF 생성
    pdf_filename = f'certificate.pdf'
    pdf_path = os.path.join('output', pdf_filename)
    
    # 폰트 경로 설정
    font_path = 'static/fonts/nanum.ttf'
    generate_pdf(name, pdf_path, font_path, img_path)

    # PDF 출력
    try:
        print_pdf(pdf_path)
    except Exception as e:
        print(f"Error printing PDF: {e}")
        return jsonify({'status': f'Error printing PDF: {e}'}), 500

    # 출력 후 PDF 파일 삭제 (선택 사항)
    os.remove(pdf_path)

    return jsonify({'status': 'Printed successfully'}), 200

def generate_pdf(name, pdf_path, font_path, img_path):
    # PDF 문서 생성
    pdf_document = fitz.open()  # 새 문서 생성
    page = pdf_document.new_page(width=595, height=842)  # A4 사이즈 페이지 추가

    # 배경 이미지 추가
    background_image_path = 'static/images/background.png'
    background_rect = fitz.Rect(0, 0, 595, 842)  # 페이지 전체 크기에 맞게
    if os.path.exists(background_image_path):
        page.insert_image(background_rect, filename=background_image_path)

    # 새로운 이미지 추가
    image_rect = fitz.Rect(100, 200, 300, 400)  # 고정된 특정 위치에 맞게

    # 이미지 파일 경로 설정
    if img_path.startswith('http://') or img_path.startswith('https://'):
        # 웹 상의 이미지 다운로드
        response = requests.get(img_path)
        if response.status_code == 200:
            temp_img_path = 'temp_image.png'
            with open(temp_img_path, 'wb') as f:
                f.write(response.content)
        else:
            raise Exception(f"Failed to download image from {img_path}")
    elif img_path.startswith('data:image/'):
        # Base64 이미지 디코딩
        header, encoded = img_path.split(',', 1)
        img_data = base64.b64decode(encoded)
        temp_img_path = 'temp_image.png'
        with open(temp_img_path, 'wb') as f:
            f.write(img_data)
    else:
        # 로컬 파일 경로
        temp_img_path = img_path

    print("Image Path: ", temp_img_path)
    if os.path.exists(temp_img_path):
        print(f"Adding image: {temp_img_path}")
        page.insert_image(image_rect, filename=temp_img_path)

    # 폰트 설정 (custom font embedding)
    custom_font = None

    # 텍스트 추가 (이름)
    font_size = 24
    text_rect = fitz.Rect(20, 300, 500, 350)  # 이름 텍스트를 표시할 영역
    page.insert_textbox(
        text_rect, name, fontsize=font_size, fontfile=font_path, fontname="CustomFont", align=fitz.TEXT_ALIGN_CENTER
    )

    # PDF 저장
    pdf_document.save(pdf_path)
    pdf_document.close()

    # 임시 이미지 파일 삭제
    if img_path.startswith('http://') or img_path.startswith('https://') or img_path.startswith('data:image/'):
        os.remove(temp_img_path)


def print_pdf(pdf_path):
    # SumatraPDF 경로 설정
    # sumatra_exe = r'C:\Program Files\SumatraPDF\SumatraPDF.exe'
    sumatra_exe = r'C:\Users\CORE\AppData\Local\SumatraPDF\SumatraPDF.exe'
    args = [sumatra_exe, '-print-to-default', '-silent', pdf_path]
    subprocess.run(args, shell=False)


if __name__ == '__main__':
    # 출력 폴더 생성
    if not os.path.exists('output'):
        os.makedirs('output')
    app.run(host='0.0.0.0', port=5000)
