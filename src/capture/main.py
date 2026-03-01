"""
Missingfind 메인 실행 스크립트 (Stage 2)
카메라를 통해 물체 배치 이벤트를 감지하고 MP4 클립으로 저장합니다.

사용법:
    python -m src.capture.main

종료: Ctrl+C로 종료
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.capture.camera import CameraCapture
from src.capture.event_detector import EventDetector
from src.capture.clip_recorder import ClipRecorder
from src.utils.config_loader import get_config
from src.utils.logger import setup_logger


def extract_event_clip(
    camera: CameraCapture,
    event_time: datetime,
    pre_seconds: float,
    post_seconds: float
):
    """
    롤링 버퍼에서 이벤트 전후 프레임 추출

    Args:
        camera: CameraCapture 인스턴스
        event_time: 이벤트 발생 시간
        pre_seconds: 이벤트 전 포함할 시간
        post_seconds: 이벤트 후 포함할 시간

    Returns:
        (프레임, 타임스탬프) 리스트
    """
    buffer_frames = camera.get_buffer_frames()

    if not buffer_frames:
        return []

    # 시간 범위 계산
    start_time = event_time - timedelta(seconds=pre_seconds)
    end_time = event_time + timedelta(seconds=post_seconds)

    # 해당 시간 범위의 프레임만 선택
    clip_frames = [
        (frame, ts) for frame, ts in buffer_frames
        if start_time <= ts <= end_time
    ]

    return clip_frames


def main():
    """메인 함수"""
    # 설정 로드
    config = get_config()

    # 로거 설정
    logger = setup_logger(
        name="missingfind",
        level=config.get('logging.level', 'INFO'),
        log_file=config.get('logging.file'),
        console=True
    )

    logger.info("=" * 60)
    logger.info("Missingfind Stage 2: 이벤트 감지 및 클립 저장 시스템 시작")
    logger.info("=" * 60)

    # 설정 로드
    camera_config = config.get_section('camera')
    bg_config = config.get_section('background_subtraction')
    obj_config = config.get_section('object_detection')
    clip_config = config.get_section('clip_recording')
    storage_config = config.get_section('storage')

    # 카메라 캡처 초기화
    logger.info(f"카메라 초기화 중... (device_id={camera_config['device_id']})")

    camera = CameraCapture(
        device_id=camera_config['device_id'],
        resolution=(
            camera_config['resolution']['width'],
            camera_config['resolution']['height']
        ),
        fps=camera_config['fps'],
        buffer_seconds=clip_config['buffer_seconds'],
        background_learning_frames=bg_config.get('background_learning_frames', 150),
        bg_subtractor_config={
            'method': bg_config['method'],
            'history': bg_config['history'],
            'var_threshold': bg_config['var_threshold'],
            'detect_shadows': bg_config['detect_shadows'],
            'min_contour_area': obj_config['min_contour_area']
        }
    )

    # 이벤트 감지기 초기화
    event_detector = EventDetector(
        static_duration=obj_config['static_duration'],
        stability_threshold=obj_config['stability_threshold'],
        min_contour_area=obj_config['min_contour_area'],
        max_tracking_distance=obj_config.get('max_tracking_distance', 80),
        cooldown_seconds=5.0,
        min_tracking_frames=obj_config.get('min_tracking_frames', 30)
    )

    # 클립 레코더 초기화
    recorder = ClipRecorder(
        clips_dir=storage_config['clips_dir'],
        meta_dir=storage_config['meta_dir'],
        thumbs_dir=storage_config['thumbs_dir'],
        codec=clip_config['codec'],
        fps=clip_config['fps']
    )

    # 카메라 열기
    if not camera.open():
        logger.error("카메라를 열 수 없습니다. 프로그램을 종료합니다.")
        return

    logger.info("시스템 준비 완료. 이벤트 감지 시작...")
    logger.info("종료하려면 Ctrl+C를 누르세요.")
    logger.info("-" * 60)

    frame_count = 0
    event_count = 0

    try:
        while True:
            # 프레임 읽기
            result = camera.read_frame()
            if result is None:
                logger.warning("프레임 읽기 실패")
                break

            frame, timestamp = result
            frame_count += 1

            # 움직임 감지
            detection_event = camera.detect_motion(frame)

            # 이벤트 감지기 업데이트
            if detection_event is not None:
                triggered_event = event_detector.update(
                    detection_event.contours,
                    detection_event.bounding_boxes,
                    timestamp
                )

                # 안정적인 물체 감지됨 → 클립 저장
                if triggered_event is not None:
                    event_count += 1
                    logger.info(
                        f"\n{'=' * 60}\n"
                        f"🎯 이벤트 #{event_count} 감지됨!\n"
                        f"   시간: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"   위치: ({triggered_event.bbox[0]}, {triggered_event.bbox[1]})\n"
                        f"   크기: {triggered_event.bbox[2]}x{triggered_event.bbox[3]}\n"
                        f"   안정성: {triggered_event.stability_score:.2f}\n"
                        f"{'=' * 60}"
                    )

                    # 클립 프레임 추출
                    clip_frames = extract_event_clip(
                        camera,
                        timestamp,
                        clip_config['pre_event_seconds'],
                        clip_config['post_event_seconds']
                    )

                    if clip_frames:
                        logger.info(f"클립 저장 중... ({len(clip_frames)} 프레임)")

                        # 클립 저장
                        metadata = recorder.save_clip(
                            frames=clip_frames,
                            camera_id=str(camera_config['device_id']),
                            camera_name="기본 웹캠",
                            event_time=timestamp,
                            event_type="object_placed",
                            confidence=triggered_event.stability_score,
                            notes=f"물체 크기: {triggered_event.bbox[2]}x{triggered_event.bbox[3]}"
                        )

                        if metadata:
                            logger.info(f"✅ 클립 저장 완료: {metadata.file_path}")
                            logger.info(f"   메타데이터: {metadata.clip_id[:8]}...")

                            # 저장 용량 확인
                            total_size = recorder.get_total_storage_size()
                            logger.info(f"   총 저장 용량: {total_size:.2f} GB")
                        else:
                            logger.error("❌ 클립 저장 실패")
                    else:
                        logger.warning("클립 프레임을 추출할 수 없습니다")

                    logger.info("-" * 60)

            # 주기적으로 상태 표시 (60초마다)
            if frame_count % (camera_config['fps'] * 60) == 0:
                tracking_info = event_detector.get_tracking_info()
                logger.info(
                    f"[상태] 프레임: {frame_count}, 이벤트: {event_count}, "
                    f"추적 중: {tracking_info['tracked_count']}개"
                )

    except KeyboardInterrupt:
        logger.info("\n\nKeyboardInterrupt: 사용자가 종료를 요청했습니다.")

    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}", exc_info=True)

    finally:
        # 정리
        camera.close()
        logger.info("\n" + "=" * 60)
        logger.info(f"시스템 종료")
        logger.info(f"  총 처리 프레임: {frame_count}")
        logger.info(f"  감지된 이벤트: {event_count}")
        logger.info(f"  저장된 클립: {len(recorder.list_clips())}개")
        logger.info(f"  총 저장 용량: {recorder.get_total_storage_size():.2f} GB")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
