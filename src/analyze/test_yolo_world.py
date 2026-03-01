"""
YOLO-World 테스트 스크립트
YOLO-World v2 모델을 로드하고 웹캠 영상에서 실시간 객체 탐지를 테스트합니다.

사용법:
    python src/analyze/test_yolo_world.py
    
종료: 'q' 키를 누르거나 Ctrl+C
"""

import sys
from pathlib import Path
import cv2
import time
from typing import List, Tuple, Optional

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config_loader import get_config
from src.utils.logger import setup_logger


logger = setup_logger("test_yolo_world", level="INFO")


class YOLOWorldTester:
    """YOLO-World 테스트 클래스"""

    def __init__(self, model_name: str = "yolov8x-worldv2", device: str = "cpu"):
        """
        Args:
            model_name: YOLO-World 모델 이름
            device: 'cuda' 또는 'cpu'
        """
        self.model_name = model_name
        self.device = device
        self.model = None

        logger.info(f"YOLO-World 초기화 중... model={model_name}, device={device}")

    def load_model(self):
        """YOLO-World 모델 로드"""
        try:
            from ultralytics import YOLO

            logger.info(f"YOLO-World 모델 다운로드 및 로드 중... (최초 실행 시 시간이 걸릴 수 있습니다)")
            self.model = YOLO(self.model_name)

            # 디바이스 설정
            if self.device == 'cuda':
                import torch
                if torch.cuda.is_available():
                    logger.info(f"✅ CUDA 사용 가능: {torch.cuda.get_device_name(0)}")
                else:
                    logger.warning("⚠️ CUDA를 사용할 수 없습니다. CPU로 전환합니다.")
                    self.device = 'cpu'

            logger.info(f"✅ YOLO-World 모델 로드 완료!")
            return True

        except ImportError as e:
            logger.error(f"❌ ultralytics 패키지를 찾을 수 없습니다: {e}")
            logger.error("다음 명령어로 설치하세요: pip install ultralytics")
            return False
        except Exception as e:
            logger.error(f"❌ YOLO-World 모델 로드 실패: {e}")
            return False

    def set_classes(self, classes: List[str]):
        """
        YOLO-World가 탐지할 클래스 설정 (텍스트 프롬프트)

        Args:
            classes: 탐지할 객체 이름 리스트 (예: ["person", "cup", "phone"])
        """
        if self.model is None:
            logger.error("모델이 로드되지 않았습니다.")
            return False

        try:
            self.model.set_classes(classes)
            logger.info(f"✅ 탐지 클래스 설정: {classes}")
            return True
        except Exception as e:
            logger.error(f"❌ 클래스 설정 실패: {e}")
            return False

    def detect(
        self,
        frame,
        confidence: float = 0.25,
        iou_threshold: float = 0.45
    ) -> Tuple[List, Optional[any]]:
        """
        프레임에서 객체 탐지

        Args:
            frame: 입력 프레임
            confidence: 신뢰도 임계값
            iou_threshold: NMS IoU 임계값

        Returns:
            (탐지 결과 리스트, 결과 객체)
        """
        if self.model is None:
            return [], None

        try:
            # YOLO-World 추론
            results = self.model.predict(
                frame,
                conf=confidence,
                iou=iou_threshold,
                device=self.device,
                verbose=False
            )

            if len(results) == 0:
                return [], None

            result = results[0]

            # 탐지 결과 파싱
            detections = []
            if result.boxes is not None and len(result.boxes) > 0:
                boxes = result.boxes

                for i in range(len(boxes)):
                    box = boxes[i]

                    # 좌표 (xyxy 형식)
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                    # 신뢰도
                    conf = float(box.conf[0].cpu().numpy())

                    # 클래스 ID 및 이름
                    cls_id = int(box.cls[0].cpu().numpy())
                    cls_name = result.names[cls_id] if result.names else f"class_{cls_id}"

                    detections.append({
                        'bbox': (int(x1), int(y1), int(x2), int(y2)),
                        'confidence': conf,
                        'class_id': cls_id,
                        'class_name': cls_name
                    })

            return detections, result

        except Exception as e:
            logger.error(f"❌ 객체 탐지 실패: {e}")
            return [], None

    def draw_detections(self, frame, detections: List[dict]):
        """
        프레임에 탐지 결과 그리기

        Args:
            frame: 입력 프레임
            detections: 탐지 결과 리스트

        Returns:
            그려진 프레임
        """
        annotated_frame = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            conf = det['confidence']
            cls_name = det['class_name']

            # 바운딩 박스 그리기
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # 라벨 텍스트
            label = f"{cls_name} {conf:.2f}"

            # 텍스트 배경
            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(annotated_frame, (x1, y1 - label_h - 10), (x1 + label_w, y1), (0, 255, 0), -1)

            # 텍스트
            cv2.putText(annotated_frame, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        return annotated_frame


def test_with_webcam(classes: List[str], device: str = "cpu"):
    """
    웹캠을 사용하여 YOLO-World 실시간 테스트

    Args:
        classes: 탐지할 객체 클래스 리스트
        device: 'cuda' 또는 'cpu'
    """
    logger.info("=" * 60)
    logger.info("YOLO-World 웹캠 테스트 시작")
    logger.info("=" * 60)

    # YOLO-World 초기화
    tester = YOLOWorldTester(model_name="yolov8x-worldv2", device=device)

    if not tester.load_model():
        logger.error("모델 로드 실패. 종료합니다.")
        return

    if not tester.set_classes(classes):
        logger.error("클래스 설정 실패. 종료합니다.")
        return

    # 웹캠 열기
    config = get_config()
    camera_config = config.get_section('camera')
    device_id = camera_config.get('device_id', 0)

    logger.info(f"카메라 열기 중... (device_id={device_id})")
    cap = cv2.VideoCapture(device_id)

    if not cap.isOpened():
        logger.error(f"❌ 카메라를 열 수 없습니다: device_id={device_id}")
        return

    # 해상도 설정
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info(f"✅ 카메라 열림: {actual_width}x{actual_height}")

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"🎯 탐지할 객체: {classes}")
    logger.info("=" * 60)
    logger.info("- 'q' 키를 누르면 종료합니다")
    logger.info("- 'c' 키를 누르면 클래스를 변경할 수 있습니다")
    logger.info("")

    frame_count = 0
    detection_count = 0
    fps = 0
    fps_start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("프레임 읽기 실패")
                break

            frame_count += 1

            # FPS 계산 (1초마다)
            if time.time() - fps_start_time >= 1.0:
                fps = frame_count / (time.time() - fps_start_time)
                frame_count = 0
                fps_start_time = time.time()

            # YOLO-World 추론
            detections, _ = tester.detect(frame, confidence=0.25, iou_threshold=0.45)

            if len(detections) > 0:
                detection_count += len(detections)
                logger.info(f"🎯 {len(detections)}개 객체 감지: {[d['class_name'] for d in detections]}")

            # 결과 그리기
            annotated_frame = tester.draw_detections(frame, detections)

            # FPS 및 통계 표시
            stats_text = f"FPS: {fps:.1f} | Detections: {len(detections)} | Total: {detection_count}"
            cv2.putText(annotated_frame, stats_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            # 탐지할 클래스 표시
            classes_text = f"Classes: {', '.join(classes)}"
            cv2.putText(annotated_frame, classes_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # 화면 표시
            cv2.imshow('YOLO-World Test', annotated_frame)

            # 키 입력 처리
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                logger.info("사용자가 종료를 요청했습니다.")
                break
            elif key == ord('c'):
                logger.info("\n새로운 클래스를 입력하세요 (쉼표로 구분):")
                logger.info("예: person, cup, phone, wallet")
                # 콘솔에서 입력받기는 GUI 모드에서 어려우므로 스킵
                logger.info("(콘솔 모드에서만 가능)")

    except KeyboardInterrupt:
        logger.info("\n사용자가 종료를 요청했습니다.")

    finally:
        cap.release()
        cv2.destroyAllWindows()

        logger.info("")
        logger.info("=" * 60)
        logger.info("테스트 종료")
        logger.info(f"총 감지된 객체 수: {detection_count}")
        logger.info("=" * 60)


def test_with_image(image_path: str, classes: List[str], device: str = "cpu"):
    """
    이미지 파일로 YOLO-World 테스트

    Args:
        image_path: 이미지 파일 경로
        classes: 탐지할 객체 클래스 리스트
        device: 'cuda' 또는 'cpu'
    """
    logger.info("=" * 60)
    logger.info(f"YOLO-World 이미지 테스트: {image_path}")
    logger.info("=" * 60)

    # 이미지 로드
    frame = cv2.imread(image_path)
    if frame is None:
        logger.error(f"❌ 이미지를 열 수 없습니다: {image_path}")
        return

    logger.info(f"✅ 이미지 로드 완료: {frame.shape}")

    # YOLO-World 초기화
    tester = YOLOWorldTester(model_name="yolov8x-worldv2", device=device)

    if not tester.load_model():
        return

    if not tester.set_classes(classes):
        return

    logger.info(f"🎯 탐지할 객체: {classes}")
    logger.info("추론 중...")

    # 추론
    start_time = time.time()
    detections, _ = tester.detect(frame, confidence=0.25, iou_threshold=0.45)
    elapsed = time.time() - start_time

    logger.info(f"✅ 추론 완료 ({elapsed:.2f}초)")
    logger.info(f"감지된 객체 수: {len(detections)}")

    if len(detections) > 0:
        for i, det in enumerate(detections, 1):
            logger.info(f"  {i}. {det['class_name']} (confidence: {det['confidence']:.3f})")

    # 결과 그리기
    annotated_frame = tester.draw_detections(frame, detections)

    # 결과 표시
    cv2.imshow('YOLO-World Result', annotated_frame)
    logger.info("결과 창을 닫으려면 아무 키나 누르세요...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="YOLO-World 테스트 스크립트")
    parser.add_argument(
        "--mode",
        type=str,
        default="webcam",
        choices=["webcam", "image"],
        help="테스트 모드 (webcam 또는 image)"
    )
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="이미지 모드일 때 이미지 파일 경로"
    )
    parser.add_argument(
        "--classes",
        type=str,
        default="wallet,phone,cup,laptop",
        help="탐지할 객체 클래스 (쉼표로 구분)"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        choices=["cpu", "cuda"],
        help="사용할 디바이스 (cpu 또는 cuda)"
    )

    args = parser.parse_args()

    # 클래스 파싱
    classes = [c.strip() for c in args.classes.split(',')]

    # 모드에 따라 실행
    if args.mode == "webcam":
        test_with_webcam(classes, args.device)
    elif args.mode == "image":
        if args.image is None:
            logger.error("❌ 이미지 모드에서는 --image 경로가 필요합니다.")
            return
        test_with_image(args.image, classes, args.device)


if __name__ == "__main__":
    main()
