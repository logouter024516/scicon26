# MissingFind (React + Vite + TypeScript + Python API)

Figma 레이아웃을 기준으로, 이번 버전은 Streamlit 없이 **프론트/백엔드 분리형**으로 재구성했습니다.

## 구조

- frontend: React + Vite + TypeScript
- backend: FastAPI (Python)

```text
project/
  frontend/
    src/
      components/
        ui/        # shadcn-style primitives (Button/Card/Tabs)
      features/
      hooks/
      api/
      types/
  backend/
    app/
      routers/
      schemas.py
      store.py
      main.py
```

## 모듈형 개발 원칙

기능을 분리해서 만들고, 연결은 마지막 단계에 진행하도록 설계했습니다.

- Home: 대시보드 요약/최근 클립
- Capture: 시작/중지/상태
- Live Search: 프레임 입력/검색/결과
- Quick Search: 검색 결과 리스트
- Register: 등록/조회/삭제

각 기능은 독립 컴포넌트 및 라우터로 분리되어 있어, 추후 실제 AI 파이프라인 연결이 쉽습니다.

## 디자인 컴포넌트

- shadcn MCP로 `tabs-demo`, `card-demo`, `button-demo` 예시를 참고하여 컴포넌트 구조를 적용했습니다.
- `src/components/ui`에 범용 UI 원시 컴포넌트(`Button`, `Card`, `Tabs`)를 분리했습니다.
- 시각 효과는 Figma 유리(Glass) 느낌에 맞춰 Reactbits 스타일의 미세 hover/blur 효과를 CSS로 반영했습니다.

## 실행 방법

### 1) Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --app-dir . --host 127.0.0.1 --port 8080 --reload
```

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

브라우저: http://localhost:5173

## 환경 변수 (선택)

Frontend:

- `VITE_API_BASE_URL` (default: `http://localhost:8000`)
- `VITE_USE_MOCK` (default: `false`)

기본값으로 FastAPI에 연결됩니다.

## 실제 동작(현재 구현)

- Capture: OpenCV MOG2 기반 이벤트 감지 후 로컬 `backend/data/clips`에 MP4 저장
- Live Search: YOLO-World(Open-Vocabulary) 우선 탐지, 실패 시 기존 휴리스틱 fallback
- Quick Search: OpenAI CLIP(ViT-B/32) 기반 이미지-텍스트 유사도 검색, 실패 시 fallback
- Register: 이미지 업로드 기반 등록(히스토그램 임베딩 저장)

추가 설정 파일:

- `backend/config.yaml` (카메라 소스, 감지 임계값, 모델 옵션)

### 2단계 계층형 검색

- API: `POST /api/v1/pipeline/find`
- 동작:
  1) Stage 1 `live_search`
  2) 실패 시 Stage 2 `quick_search`
- 응답에 `stage`(`live`/`quick`)와 `quick` 후보 리스트를 함께 반환합니다.

## 다음 연결 단계 (권장 순서)

현재는 각 페이지 기본 폼과 API 연결이 완료되어 있습니다.

1. Backend `capture` 라우터를 실제 카메라/이벤트 캡처 서비스와 연결
2. Backend `live`/`quick` 라우터를 CLIP/YOLO 검색 서비스와 연결
3. Backend `register` 라우터를 임베딩 저장소(JSON/DB)와 연결
4. Frontend 결과 카드에 실제 프레임/썸네일/비디오 표시 연결
