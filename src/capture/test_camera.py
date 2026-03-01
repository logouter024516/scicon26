"""
카메라 캡처 및 배경 차감 테스트 스크립트
실시간으로 카메라에서 프레임을 읽고 배경 차감을 적용하여 화면에 표시합니다.

사용법:
    python -m src.capture.test_camera

종료: 'q' 키를 누르면 종료됩니다.
"""

import cv2
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.capture.camera import CameraCapture
from src.utils.config_loader import get_config
from src.utils.logger import setup_logger


def main():
    """메인 함수"""
    # 설정 로드
    config = get_config()

    # 로거 설정
    logger = setup_logger(
        name="test_camera",
        level=config.get('logging.level', 'INFO'),
        log_file=config.get('logging.file'),
        console=True
    )

    logger.info("카메라 캡처 테스트 시작")

    # 카메라 설정
    camera_config = config.get_section('camera')
    bg_config = config.get_section('background_subtraction')

    # 카메라 캡처 객체 생성
    with CameraCapture(
        device_id=camera_config['device_id'],
        resolution=(camera_config['resolution']['width'], camera_config['resolution']['height']),
        fps=camera_config['fps'],
        buffer_seconds=5.0,
        bg_subtractor_config={
            'method': bg_config['method'],
            'history': bg_config['history'],
            'var_threshold': bg_config['var_threshold'],
            'detect_shadows': bg_config['detect_shadows']
        }
    ) as capture:

        logger.info("카메라 시작됨. 'q'를 눌러 종료하세요.")

        frame_count = 0
        detection_count = 0

        try:
            while True:
                # 프레임 읽기
                result = capture.read_frame()
                if result is None:
                    logger.warning("프레임 읽기 실패")
                    break

                frame, timestamp = result
                frame_count += 1

                # 움직임 감지
                event = capture.detect_motion(frame)

                # 결과 시각화
                display_frame = frame.copy()

                if event is not None:
                    detection_count += 1

                    # 경계 박스 그리기
                    for x, y, w, h in event.bounding_boxes:
                        cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

                    # 정보 표시
                    info_text = f"감지됨! 신뢰도: {event.confidence:.2f}"
                    cv2.putText(
                        display_frame,
                        info_text,
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2
                    )

                    logger.info(f"물체 감지: {len(event.bounding_boxes)}개, 신뢰도: {event.confidence:.2f}")

                # 프레임 카운트 표시
                cv2.putText(
                    display_frame,
                    f"Frame: {frame_count} | Detections: {detection_count}",
                    (10, display_frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )

                # 화면에 표시
                cv2.imshow('Camera Feed', display_frame)

                # 전경 마스크 표시 (event가 있을 때만)
                if event is not None:
                    cv2.imshow('Foreground Mask', event.mask)

                # 'q' 키로 종료
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("사용자가 종료를 요청했습니다.")
                    break

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt: 종료합니다.")

        finally:
            cv2.destroyAllWindows()
            logger.info(f"테스트 종료. 총 프레임: {frame_count}, 총 감지: {detection_count}")


if __name__ == "__main__":
    main()
