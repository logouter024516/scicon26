"""
설치 확인 및 간단한 카메라 테스트
모든 필수 패키지가 제대로 설치되었는지 확인합니다.
"""

import sys

print("=" * 60)
print("Missingfind 설치 확인")
print("=" * 60)

# Python 버전 확인
print(f"\n✓ Python 버전: {sys.version}")

# 필수 패키지 확인
packages = {
    'cv2': 'OpenCV',
    'numpy': 'NumPy',
    'yaml': 'PyYAML',
    'dotenv': 'python-dotenv'
}

print("\n패키지 확인:")
failed = []
for module_name, package_name in packages.items():
    try:
        __import__(module_name)
        print(f"  ✓ {package_name}")
    except ImportError as e:
        print(f"  ✗ {package_name} - 설치되지 않음")
        failed.append(package_name)

if failed:
    print(f"\n⚠ 설치 필요: {', '.join(failed)}")
    print("다음 명령으로 설치하세요:")
    print("  pip install -r requirements_stage2.txt")
    sys.exit(1)

# 카메라 확인
print("\n카메라 확인:")
try:
    import cv2
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            h, w = frame.shape[:2]
            print(f"  ✓ 카메라 사용 가능 (해상도: {w}x{h})")
        else:
            print("  ⚠ 카메라가 열렸지만 프레임을 읽을 수 없습니다")
        cap.release()
    else:
        print("  ✗ 카메라를 열 수 없습니다")
        print("  - 다른 프로그램이 카메라를 사용 중인지 확인하세요")
        print("  - 카메라 접근 권한을 확인하세요")
except Exception as e:
    print(f"  ✗ 카메라 테스트 실패: {e}")

# 설정 파일 확인
print("\n설정 파일 확인:")
from pathlib import Path

project_root = Path(__file__).parent
config_file = project_root / "config" / "config.yaml"

if config_file.exists():
    print(f"  ✓ config.yaml 존재")
else:
    print(f"  ✗ config.yaml 없음")

print("\n" + "=" * 60)
print("설치 확인 완료!")
print("=" * 60)
print("\n다음 단계:")
print("  1. 카메라 테스트: python -m src.capture.test_camera")
print("  2. 테스트 종료: 'q' 키를 누르세요")
print("=" * 60)
