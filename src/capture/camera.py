"""
카메라 캡처 및 배경 모델링 모듈
실시간으로 카메라 영상을 캡처하고 배경 차감을 통해 새로운 물체를 감지합니다.
"""

import cv2
import numpy as np
from collections import deque
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
from datetime import datetime

from ..utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class DetectionEvent:
    """물체 감지 이벤트 데이터 클래스"""
    timestamp: datetime
    frame: np.ndarray
    mask: np.ndarray
    contours: List[np.ndarray]
    bounding_boxes: List[Tuple[int, int, int, int]]  # (x, y, w, h)
    confidence: float


class BackgroundSubtractor:
    """배경 차감을 통한 새 물체 감지 클래스"""

    def __init__(
        self,
        method: str = "MOG2",
        history: int = 500,
        var_threshold: float = 16,
        detect_shadows: bool = True,
        min_contour_area: int = 500
    ):
        """
        Args:
            method: 배경 차감 방법 ('MOG2' 또는 'KNN')
            history: 배경 학습에 사용할 프레임 수
            var_threshold: 분산 임계값
            detect_shadows: 그림자 감지 여부
            min_contour_area: 최소 윤곽선 영역 (픽셀)
        """
        self.method = method
        self.min_contour_area = min_contour_area

        # 배경 차감기 생성
        if method.upper() == "MOG2":
            self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=history,
                varThreshold=var_threshold,
                detectShadows=detect_shadows
            )
        elif method.upper() == "KNN":
            self.bg_subtractor = cv2.createBackgroundSubtractorKNN(
                history=history,
                dist2Threshold=var_threshold * 10,
                detectShadows=detect_shadows
            )
        else:
            raise ValueError(f"지원하지 않는 배경 차감 방법: {method}")

        logger.info(f"배경 차감기 초기화: {method}, history={history}, var_threshold={var_threshold}")

    def apply(self, frame: np.ndarray, learning_rate: float = -1) -> np.ndarray:
        """
        프레임에 배경 차감 적용

        Args:
            frame: 입력 프레임
            learning_rate: 학습률 (-1이면 자동, 0~1 사이의 값으로 수동 설정)

        Returns:
            전경 마스크 (0 또는 255)
        """
        # 배경 차감 적용
        fg_mask = self.bg_subtractor.apply(frame, learningRate=learning_rate)

        # 노이즈 제거 (모폴로지 연산)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

        return fg_mask

    def find_objects(
        self,
        mask: np.ndarray
    ) -> Tuple[List[np.ndarray], List[Tuple[int, int, int, int]]]:
        """
        마스크에서 객체의 윤곽선과 경계 박스 찾기

        Args:
            mask: 전경 마스크

        Returns:
            (윤곽선 리스트, 경계 박스 리스트)
        """
        # 윤곽선 찾기
        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        # 최소 영역 이상의 윤곽선만 필터링
        valid_contours = []
        bounding_boxes = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= self.min_contour_area:
                valid_contours.append(contour)
                x, y, w, h = cv2.boundingRect(contour)
                bounding_boxes.append((x, y, w, h))

        return valid_contours, bounding_boxes


class CameraCapture:
    """카메라 캡처 및 이벤트 감지 클래스"""

    def __init__(
        self,
        device_id: int = 0,
        resolution: Tuple[int, int] = (1280, 720),
        fps: int = 30,
        buffer_seconds: float = 5.0,
        bg_subtractor_config: Optional[Dict] = None
    ):
        """
        Args:
            device_id: 카메라 디바이스 ID
            resolution: 해상도 (width, height)
            fps: 초당 프레임 수
            buffer_seconds: 롤링 버퍼 유지 시간 (초)
            bg_subtractor_config: 배경 차감기 설정 딕셔너리
        """
        self.device_id = device_id
        self.resolution = resolution
        self.fps = fps
        self.buffer_seconds = buffer_seconds

        # 카메라 초기화
        self.cap = None
        self.is_running = False

        # 프레임 버퍼 (롤링 버퍼)
        buffer_size = int(fps * buffer_seconds)
        self.frame_buffer = deque(maxlen=buffer_size)

        # 배경 차감기 초기화
        if bg_subtractor_config is None:
            bg_subtractor_config = {}
        self.bg_subtractor = BackgroundSubtractor(**bg_subtractor_config)

        # 배경 학습 상태
        self.is_background_learned = False
        self.learning_frame_count = 0
        self.background_learning_frames = 150  # 배경 학습에 필요한 프레임 수

        logger.info(f"카메라 캡처 초기화: device={device_id}, resolution={resolution}, fps={fps}")

    def open(self) -> bool:
        """
        카메라 열기

        Returns:
            성공 여부
        """
        try:
            self.cap = cv2.VideoCapture(self.device_id)

            if not self.cap.isOpened():
                logger.error(f"카메라를 열 수 없습니다: device_id={self.device_id}")
                return False

            # 해상도 설정
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)

            # 실제 설정된 값 확인
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))

            logger.info(f"카메라 열림: {actual_width}x{actual_height} @ {actual_fps}fps")

            self.is_running = True
            return True

        except Exception as e:
            logger.error(f"카메라 열기 실패: {e}")
            return False

    def close(self):
        """카메라 닫기"""
        self.is_running = False
        if self.cap is not None:
            self.cap.release()
            logger.info("카메라 닫힌")

    def read_frame(self) -> Optional[Tuple[np.ndarray, datetime]]:
        """
        프레임 읽기

        Returns:
            (프레임, 타임스탬프) 또는 None
        """
        if not self.is_running or self.cap is None:
            return None

        ret, frame = self.cap.read()
        if not ret:
            logger.warning("프레임 읽기 실패")
            return None

        timestamp = datetime.now()

        # 버퍼에 추가
        self.frame_buffer.append((frame.copy(), timestamp))

        return frame, timestamp

    def detect_motion(self, frame: np.ndarray) -> Optional[DetectionEvent]:
        """
        프레임에서 움직임 감지

        Args:
            frame: 입력 프레임

        Returns:
            DetectionEvent 또는 None (배경 학습 중에는 None 반환)
        """
        # 배경 학습 단계
        if not self.is_background_learned:
            self.learning_frame_count += 1

            # 빠른 학습을 위해 높은 학습률 사용
            self.bg_subtractor.apply(frame, learning_rate=0.1)

            if self.learning_frame_count >= self.background_learning_frames:
                self.is_background_learned = True
                logger.info(f"✅ 배경 학습 완료 ({self.learning_frame_count} 프레임)")
                logger.info("🎯 이제 물체 감지를 시작합니다!")

            # 학습 중에는 None 반환
            return None

        # 배경 차감 적용 (일반 학습률)
        fg_mask = self.bg_subtractor.apply(frame, learning_rate=-1)

        # 객체 찾기
        contours, bboxes = self.bg_subtractor.find_objects(fg_mask)

        if len(contours) == 0:
            return None

        # 감지 이벤트 생성
        event = DetectionEvent(
            timestamp=datetime.now(),
            frame=frame.copy(),
            mask=fg_mask,
            contours=contours,
            bounding_boxes=bboxes,
            confidence=self._calculate_confidence(fg_mask, bboxes)
        )

        return event

    def _calculate_confidence(
        self,
        mask: np.ndarray,
        bboxes: List[Tuple[int, int, int, int]]
    ) -> float:
        """
        감지 신뢰도 계산

        Args:
            mask: 전경 마스크
            bboxes: 경계 박스 리스트

        Returns:
            신뢰도 (0~1)
        """
        if len(bboxes) == 0:
            return 0.0

        # 전경 픽셀 비율 계산
        total_fg_pixels = np.sum(mask > 0)
        total_pixels = mask.shape[0] * mask.shape[1]
        fg_ratio = total_fg_pixels / total_pixels

        # 경계 박스 면적 비율 계산
        total_bbox_area = sum(w * h for x, y, w, h in bboxes)
        bbox_ratio = total_bbox_area / total_pixels

        # 신뢰도는 두 비율의 가중 평균
        confidence = 0.7 * fg_ratio + 0.3 * bbox_ratio

        return min(confidence, 1.0)

    def get_buffer_frames(self) -> List[Tuple[np.ndarray, datetime]]:
        """
        버퍼에 저장된 프레임 가져오기

        Returns:
            (프레임, 타임스탬프) 리스트
        """
        return list(self.frame_buffer)

    def __enter__(self):
        """컨텍스트 매니저 진입"""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.close()
