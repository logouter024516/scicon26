# 🤖 YOLO-World 테스트 가이드

## 📋 개요

YOLO-World는 **텍스트 프롬프트 기반 오픈 월드 객체 탐지** 모델입니다.  
일반 YOLO와 달리, 미리 정의된 클래스가 아닌 **자연어로 탐지할 객체를 지정**할 수 있습니다!

## 🎯 YOLO-World의 장점

- ✅ **유연한 객체 탐지**: "person", "cup", "wallet" 등 텍스트로 지정
- ✅ **사전 학습 불필요**: 새로운 객체도 텍스트만으로 탐지 가능
- ✅ **Missingfind에 완벽**: "내 지갑"처럼 특정 객체 검색에 이상적

## 🚀 설치

```powershell
# ultralytics 설치 (이미 완료됨)
pip install ultralytics

# PyTorch도 함께 설치됨
```

## 📱 테스트 모드

### 1. 웹캠 모드 (실시간 테스트)

```powershell
# 기본 테스트
python src/analyze/test_yolo_world.py --mode webcam

# 특정 객체만 탐지
python src/analyze/test_yolo_world.py --mode webcam --classes "person,cup,phone,wallet"

# GPU 사용 (CUDA 설치된 경우)
python src/analyze/test_yolo_world.py --mode webcam --device cuda
```

**사용법**:
- 웹캠 창이 열림
- 설정한 객체들이 실시간으로 탐지됨
- `q` 키: 종료
- `c` 키: 클래스 변경 (콘솔 모드에서만)

### 2. 이미지 모드 (사진 테스트)

```powershell
# 이미지 파일로 테스트
python src/analyze/test_yolo_world.py --mode image --image "path/to/image.jpg" --classes "person,laptop,phone"
```

## 🎨 파라미터 설명

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `--mode` | 테스트 모드 (webcam/image) | webcam |
| `--classes` | 탐지할 객체 (쉼표로 구분) | person,cup,phone,... |
| `--device` | 디바이스 (cpu/cuda) | cpu |
| `--image` | 이미지 파일 경로 (image 모드) | None |

## 🔧 탐지할 수 있는 객체 예시

### 일상 물건
```
person, cup, mug, bottle, wallet, phone, laptop, keyboard, mouse, 
remote, book, pen, pencil, backpack, bag, glasses, watch, keys, 
headphones, charger, cable, notebook
```

### 가구/집기
```
chair, desk, table, bed, sofa, lamp, clock, picture, mirror,
door, window, curtain, pillow, blanket
```

### 주방용품
```
plate, bowl, fork, knife, spoon, pot, pan, refrigerator, 
microwave, toaster, kettle, cup
```

### 전자기기
```
tv, monitor, speaker, camera, tablet, router, printer, 
game console, controller
```

## 📊 출력 정보

실시간으로 다음 정보가 표시됩니다:
- **FPS**: 초당 처리 프레임 수
- **Detections**: 현재 프레임에서 감지된 객체 수
- **Total**: 총 감지된 객체 수
- **Classes**: 탐지 중인 클래스 목록

감지된 객체는 다음 정보를 포함합니다:
- **Bounding Box**: 녹색 사각형
- **Class Name**: 객체 이름
- **Confidence**: 신뢰도 점수 (0~1)

## 💡 테스트 시나리오

### 시나리오 1: 일상 물건 찾기 (추천)
```powershell
python src/analyze/test_yolo_world.py --mode webcam --classes "wallet,phone,keys"
```
- 지갑, 핸드폰, 열쇠를 카메라 앞에 놓아보세요
- 가장 자주 찾는 물건들로 구성

### 시나리오 2: 사무용품
```powershell
python src/analyze/test_yolo_world.py --mode webcam --classes "laptop,mouse,pen"
```
- 책상 위 사무용품들이 감지되는지 확인

### 시나리오 3: 음료/컵
```powershell
python src/analyze/test_yolo_world.py --mode webcam --classes "cup,bottle"
```
- 간단한 2개 클래스로 빠른 테스트

## 🎯 Missingfind 통합 계획

### Stage 4에서 사용할 방식:

```python
# 1. 저장된 MP4 클립 로드
frames = sample_frames_from_clip("data/clips/clip_001.mp4", fps=1)

# 2. 각 프레임에서 YOLO-World로 객체 탐지
for frame, timestamp in frames:
    detections = yolo_world.detect(frame, classes=["wallet", "phone"])
    
    # 3. CLIP으로 텍스트 쿼리와 유사도 계산
    for det in detections:
        crop = frame[det.bbox]
        similarity = clip.compute_similarity(query_text, crop)
        
        if similarity > threshold:
            # 매칭 발견!
            return clip_id, timestamp, det
```

## ⚡ 성능 최적화

### CPU 모드 (현재)
- 속도: 약 1-3 FPS
- 메모리: ~2GB
- 권장: 테스트 및 개발용

### GPU 모드 (CUDA)
- 속도: 약 15-30 FPS
- 메모리: ~4GB VRAM
- 권장: 실제 서비스용

GPU 사용 시:
```powershell
python src/analyze/test_yolo_world.py --mode webcam --device cuda
```

## 🐛 문제 해결

### 1. 모델 다운로드 느림
- 최초 실행 시 YOLO-World 모델 (약 100MB) 다운로드
- 인터넷 연결 확인
- 다운로드 후 캐시됨 (~/.cache/ultralytics/)

### 2. 객체가 감지 안 됨
- 조명 확인 (밝은 환경 권장)
- 객체 크기 확인 (너무 작으면 감지 어려움)
- 클래스 이름 확인 (영어로, 간단명료하게)
- confidence 임계값 낮추기 (코드에서 0.25 → 0.15)

### 3. FPS가 너무 낮음
- `--device cuda` 사용 (GPU)
- 해상도 낮추기
- 탐지 클래스 수 줄이기

### 4. CUDA 오류
- CUDA 드라이버 확인
- PyTorch CUDA 버전 확인: `python -c "import torch; print(torch.cuda.is_available())"`
- CPU로 폴백됨

## 📝 로그 예시

```
INFO: ============================================================
INFO: YOLO-World 웹캠 테스트 시작
INFO: ============================================================
INFO: YOLO-World 초기화 중... model=yolov8x-worldv2, device=cpu
INFO: YOLO-World 모델 다운로드 및 로드 중... (최초 실행 시 시간이 걸릴 수 있습니다)
INFO: ✅ YOLO-World 모델 로드 완료!
INFO: ✅ 탐지 클래스 설정: ['person', 'cup', 'phone', 'wallet', 'laptop', 'bottle']
INFO: 카메라 열기 중... (device_id=0)
INFO: ✅ 카메라 열림: 1280x720
INFO: ============================================================
INFO: 🎯 탐지할 객체: ['person', 'cup', 'phone', 'wallet', 'laptop', 'bottle']
INFO: ============================================================
INFO: - 'q' 키를 누르면 종료합니다
INFO: - 'c' 키를 누르면 클래스를 변경할 수 있습니다
INFO: 🎯 2개 객체 감지: ['person', 'cup']
INFO: 🎯 1개 객체 감지: ['phone']
```

## 🎉 다음 단계

YOLO-World 테스트 후:
1. ✅ **Stage 3**: MP4 프레임 샘플링 구현
2. ✅ **Stage 4**: YOLO-World + CLIP 통합
3. ✅ **Stage 5**: 자연어 검색 구현

---

**YOLO-World 테스트를 즐겨보세요!** 🚀

궁금한 점이 있으면 언제든지 물어보세요!
