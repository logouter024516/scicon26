# Missingfind 설치 및 실행 가이드

## 1. 환경 설정

### Python 버전
- Python 3.10 이상 필요

### 가상환경 생성 (권장)
```powershell
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
.\venv\Scripts\Activate.ps1

# PowerShell 실행 정책 오류가 발생하면:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 2. 의존성 설치

```powershell
# 필수 패키지 설치
pip install -r requirements.txt
```

### 주요 패키지
- opencv-python: 카메라 캡처 및 이미지 처리
- numpy: 수치 연산
- torch, torchvision: 딥러닝 프레임워크
- ultralytics: YOLO-World
- openai-clip: CLIP 모델
- pyyaml, python-dotenv: 설정 관리

## 3. 환경 변수 설정

```powershell
# .env.example을 .env로 복사
Copy-Item .env.example .env

# .env 파일을 편집하여 설정 변경 (필요시)
notepad .env
```

## 4. Stage 2 테스트: 카메라 캡처 및 배경 모델링

### 테스트 실행
```powershell
# 카메라 캡처 테스트
python -m src.capture.test_camera
```

### 테스트 내용
- 웹캠에서 실시간 영상 캡처
- 배경 차감을 통한 전경 객체 감지
- 감지된 객체에 경계 박스 표시
- 프레임 카운트 및 감지 통계 표시

### 종료 방법
- 'q' 키를 누르면 프로그램이 종료됩니다

### 화면 설명
- **Camera Feed**: 실시간 카메라 영상 + 감지된 객체의 경계 박스
- **Foreground Mask**: 배경 차감 결과 (흰색 = 전경 객체)

## 5. 설정 변경

### config/config.yaml
프로젝트의 모든 설정은 `config/config.yaml` 파일에서 관리됩니다.

#### 카메라 설정
```yaml
camera:
  device_id: 0  # 웹캠 인덱스 (0 = 기본 카메라)
  resolution:
    width: 1280
    height: 720
  fps: 30
```

#### 배경 모델링 설정
```yaml
background_subtraction:
  method: "MOG2"  # MOG2 또는 KNN
  history: 500  # 배경 학습 프레임 수
  var_threshold: 16  # 분산 임계값 (높을수록 덜 민감)
  detect_shadows: true  # 그림자 감지 여부
```

#### 객체 감지 설정
```yaml
object_detection:
  static_duration: 3.0  # 물체가 정지해야 하는 시간 (초)
  min_contour_area: 500  # 최소 윤곽선 영역 (픽셀)
  stability_threshold: 0.95  # 안정성 임계값
```

## 6. 문제 해결

### 카메라를 열 수 없음
- 다른 프로그램이 카메라를 사용 중인지 확인
- `config.yaml`에서 `camera.device_id`를 변경해보기 (0, 1, 2 등)
- Windows에서 카메라 접근 권한 확인

### 패키지 설치 오류
```powershell
# pip 업그레이드
python -m pip install --upgrade pip

# 캐시 없이 재설치
pip install --no-cache-dir -r requirements.txt
```

### CUDA 관련 오류 (GPU 사용 시)
- CUDA와 PyTorch 버전 호환성 확인
- CPU만 사용하려면 `.env`에서 `DEVICE=cpu`로 설정

### 배경 차감이 너무 민감함
- `config.yaml`에서 `var_threshold` 값을 증가 (예: 16 → 32)
- `min_contour_area` 값을 증가 (예: 500 → 1000)

### 배경 차감이 너무 둔감함
- `var_threshold` 값을 감소 (예: 16 → 8)
- `min_contour_area` 값을 감소 (예: 500 → 200)

## 7. 다음 단계

현재 Stage 2까지 완료되었습니다. 다음 단계는:

1. **Stage 3**: 정적 물체 감지 및 이벤트 트리거
2. **Stage 4**: MP4 클립 저장 기능
3. **Stage 5**: YOLO-World + CLIP 통합
4. **Stage 6**: 클립 검색 기능
5. **Stage 7**: CLI/웹 UI

각 단계는 독립적으로 테스트 가능하도록 개발됩니다.

## 8. 로그 확인

```powershell
# 로그 파일 확인
Get-Content logs\bactriev.log -Tail 50

# 실시간 로그 모니터링
Get-Content logs\bactriev.log -Wait -Tail 20
```

## 9. 프로젝트 구조

```
00_scicon26_ocr/
├── ai/
│   ├── prompt.md          # 프로젝트 요구사항
│   └── .progress.md       # 진행 상황 로그
├── src/
│   ├── capture/           # ✅ Stage 2 완료
│   │   ├── camera.py
│   │   └── test_camera.py
│   ├── utils/             # ✅ Stage 2 완료
│   │   ├── config_loader.py
│   │   └── logger.py
│   ├── detect/            # 🔜 Stage 5
│   ├── embed/             # 🔜 Stage 5
│   ├── search/            # 🔜 Stage 6
│   └── app/               # 🔜 Stage 7
├── data/
│   ├── clips/             # 🔜 Stage 4
│   ├── meta/              # 🔜 Stage 4
│   └── frames/
├── config/
│   └── config.yaml
└── requirements.txt
```
