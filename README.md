# Missingfind

실내 물체 위치 기억 및 검색 AI 시스템 (MP4 클립 기반)

## 프로젝트 개요

Missingfind는 카메라를 통해 실내에 놓인 물체를 자동으로 감지하고 MP4 클립으로 기록하여, 사용자가 "내 지갑 어디있어?"와 같은 자연어 질문으로 물체의 위치를 찾을 수 있게 해주는 시스템입니다.

**핵심 특징**: Vector Database 없이 MP4 클립과 메타데이터만으로 동작합니다.

## 주요 기능

1. **실시간 카메라 모니터링**: 웹캠 또는 IP 카메라를 통한 영상 캡처
2. **자동 물체 감지**: 배경 모델링을 통해 새로 놓인 물체 자동 감지
3. **이벤트 클립 저장**: 물체가 놓인 순간을 포함한 10~15초 MP4 클립 저장
4. **지능형 검색**: YOLO-World + CLIP을 활용한 자연어 쿼리 검색
5. **메타데이터 관리**: 각 클립의 시간, 카메라, 감지 정보를 JSON으로 저장

## 기술 스택

- **언어**: Python 3.10+
- **컴퓨터 비전**: OpenCV
- **객체 탐지**: YOLO-World (Ultralytics)
- **임베딩**: OpenAI CLIP
- **저장소**: MP4 클립 + JSON 메타데이터 (Vector DB 없음)
- **UI**: CLI / FastAPI / Streamlit

## 프로젝트 구조

```
00_scicon26_ocr/
├── ai/                    # AI 관련 문서 및 진행 로그
│   ├── prompt.md          # 프로젝트 요구사항
│   └── .progress.md       # 진행 상황 로그
├── src/                   # 소스 코드
│   ├── capture/           # Stage 2: 카메라 캡처 및 배경 모델링 ✅
│   ├── analyze/           # Stage 4: YOLO-World + CLIP 분석
│   ├── query/             # Stage 5: 자연어 쿼리 검색
│   ├── app/               # Stage 6: UI (CLI/웹)
│   └── utils/             # 공통 유틸리티 ✅
├── data/                  # 데이터 저장소
│   ├── clips/             # MP4 이벤트 클립
│   ├── meta/              # JSON 메타데이터
│   └── thumbs/            # 썸네일 이미지
├── config/                # 설정 파일
│   └── config.yaml        # 시스템 설정 ✅
├── logs/                  # 로그 파일
├── check_install.py       # 설치 확인 스크립트 ✅
├── requirements.txt       # Python 패키지 의존성
└── README.md             # 이 파일
```

## 빠른 시작

### 1. 환경 설정

```powershell
# Conda 환경 생성 및 활성화
conda create -n missingfind python=3.10 -y
conda activate missingfind

# 프로젝트 디렉터리로 이동
cd D:\01_prj\00_scicon26_ocr
```

### 2. 패키지 설치

```powershell
# Stage 2 테스트에 필요한 기본 패키지 설치
pip install -r requirements_stage2.txt

# 또는 전체 패키지 설치 (PyTorch 포함 - 시간이 오래 걸림)
# pip install -r requirements.txt
```

### 3. 설치 확인

```powershell
# 설치 및 카메라 확인
python check_install.py
```

### 4. 실행 방법

#### 옵션 1: GUI 대시보드 실행 (권장) 🎨

```powershell
# Streamlit 설치
pip install streamlit

# GUI 실행 (자동으로 브라우저가 열림)
streamlit run src/app/streamlit_app.py

# 또는 편리한 실행 스크립트 사용
.\run_gui.bat       # Windows 배치 파일
.\run_gui.ps1       # PowerShell 스크립트
```

**GUI 기능**:
- 📹 실시간 카메라 라이브 피드
- 📊 통계 대시보드 (FPS, 이벤트 수, 저장 용량 등)
- 📝 실시간 이벤트 로그
- 🎬 저장된 클립 관리 및 다운로드
- ⚙️ 시스템 시작/중지 제어

자세한 사용법은 `GUI_GUIDE.md` 참조

#### 옵션 2: 콘솔 모드 실행

```powershell
# 이벤트 감지 및 클립 저장 시스템 실행
python -m src.capture.main
```

**동작**:
- 카메라에서 실시간 영상 캡처
- 배경 차감으로 물체 감지
- 물체가 3초 이상 안정적으로 놓이면 이벤트 발생
- 이벤트 전후 10초 영상을 MP4 클립으로 저장
- JSON 메타데이터 및 썸네일 이미지 자동 생성
- Ctrl+C로 종료

**테스트 방법**:
1. 프로그램 실행 후 5초 대기 (배경 학습)
2. 물체를 카메라 앞에 놓기
3. 3초 이상 가만히 있기
4. "🎯 이벤트 감지됨!" 메시지 확인
5. `data/clips/` 폴더에서 MP4 파일 확인

상세한 가이드는 `STAGE2_GUIDE.md` 참조

## 개발 단계

- [x] **Stage 1**: 프로젝트 스켈레톤 및 구조 설계
- [x] **Stage 2**: 카메라 캡처 + 배경 모델링 + 이벤트 감지 + MP4 클립 저장
- [ ] **Stage 3**: 프레임 샘플링 유틸리티
- [ ] **Stage 4**: YOLO-World + CLIP 통합 (프레임 분석)
- [ ] **Stage 5**: 클립 검색 기능 (자연어 쿼리)
- [x] **Stage 6**: Streamlit 웹 GUI 대시보드

## 설정

모든 설정은 `config/config.yaml` 파일에서 관리됩니다.

### 카메라 설정

```yaml
camera:
  device_id: 0  # 웹캠 인덱스 (다른 카메라 사용 시 1, 2 등으로 변경)
  resolution:
    width: 1280
    height: 720
  fps: 30
```

### 배경 모델링 감도 조절

```yaml
background_subtraction:
  var_threshold: 16  # 높을수록 덜 민감 (8~32 권장)
  min_contour_area: 500  # 최소 감지 영역 (픽셀)
```

## 문제 해결

### 카메라를 열 수 없음
- 다른 프로그램이 카메라를 사용 중인지 확인
- `config.yaml`에서 `camera.device_id`를 변경 (0, 1, 2 등)
- Windows 카메라 접근 권한 확인

### 배경 차감이 너무 민감/둔감
- `config.yaml`에서 `var_threshold` 값 조절
- `min_contour_area` 값 조절

## 진행 상황

상세한 진행 상황은 `ai/.progress.md` 파일을 참조하세요.

## 라이선스

MIT License

## 기여

이슈 및 PR을 환영합니다!
