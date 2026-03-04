# 감사장 인쇄 서버 — 프론트엔드 API 가이드

> 서버 기본 주소: `http://localhost:5000` (포트는 설정에서 변경 가능)

---

## API 목록

### 1. 인쇄 요청

```
POST /print
Content-Type: application/json
```

**Request Body:**

```json
{
  "name": "김철수",
  "img": "https://example.com/photo.png"   // 선택사항
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `name` | string | O | 감사장에 들어갈 이름 |
| `img` | string | X | 사진 이미지 (URL, base64 data URI, 로컬 파일 경로) |

**Response:**

```json
{ "status": "Printed successfully" }
```

**예시:**

```javascript
// 기본 인쇄
fetch('http://localhost:5000/print', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name: '김철수' })
});

// 사진 포함 인쇄
fetch('http://localhost:5000/print', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: '김철수',
    img: 'https://example.com/photo.png'
  })
});
```

---

### 2. PDF 미리보기 (브라우저)

```
GET /preview?name=김철수
```

HTML 페이지로 감사장 미리보기를 렌더링합니다. 키오스크 URL로 사용 가능합니다.

---

### 3. PDF 테스트 생성

```
GET /test?name=김철수
```

PDF 파일을 생성하여 브라우저에서 직접 표시합니다. 인쇄하지 않고 PDF 결과만 확인할 때 사용합니다.

---

### 4. 키오스크 종료

```
POST /close-kiosk
```

**설명:** 키오스크 모드로 열린 Chrome 브라우저를 종료합니다. 터치 키오스크 환경에서 화면을 빠져나올 때 사용합니다.

**Response:**

```json
{ "status": "Kiosk closed" }
// 또는
{ "status": "No kiosk running" }
```

**프론트엔드 구현 예시:**

```html
<!-- 종료 버튼 (우상단 고정) -->
<button id="close-kiosk-btn" onclick="closeKiosk()">
  전체화면 종료
</button>

<style>
#close-kiosk-btn {
  position: fixed;
  top: 10px;
  right: 10px;
  z-index: 9999;
  background: rgba(244, 67, 54, 0.85);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 18px;
  font-size: 14px;
  cursor: pointer;
}
#close-kiosk-btn:hover {
  background: rgba(244, 67, 54, 1);
}
/* 인쇄 시 버튼 숨기기 */
@media print {
  #close-kiosk-btn { display: none; }
}
</style>

<script>
function closeKiosk() {
  fetch('/close-kiosk', { method: 'POST' })
    .then(() => window.close())
    .catch(() => {});
}
</script>
```

---

## CORS

서버에 CORS가 활성화되어 있으므로 다른 도메인/포트에서도 API 호출이 가능합니다.

다른 포트에서 호출하는 경우 전체 URL을 사용하세요:

```javascript
fetch('http://localhost:5000/print', { ... })
fetch('http://localhost:5000/close-kiosk', { method: 'POST' })
```

---

## 참고: 키오스크 흐름

```
프론트엔드 페이지 (Chrome 풀스크린)
    │
    ├── 이름 입력 → POST /print → 프린터 출력
    │
    └── [종료] 버튼 클릭 → POST /close-kiosk → Chrome 종료
```
