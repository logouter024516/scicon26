"""
이벤트 감지 모듈
배경 차감 결과를 분석하여 "새로운 물체가 놓인" 이벤트를 감지합니다.
"""

import cv2
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

from ..utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class TrackedObject:
    """추적 중인 물체 정보"""
    object_id: int
    bbox: Tuple[int, int, int, int]  # (x, y, w, h)
    first_seen: datetime
    last_seen: datetime
    stability_score: float  # 0~1, 1에 가까울수록 안정적
    frame_count: int
    area: int
    
    def is_stable(self, threshold: float = 0.95, min_duration: float = 3.0) -> bool:
        """
        물체가 안정적(정적)으로 놓였는지 판단
        
        Args:
            threshold: 안정성 임계값
            min_duration: 최소 지속 시간 (초)
        
        Returns:
            안정적이면 True
        """
        duration = (self.last_seen - self.first_seen).total_seconds()
        return self.stability_score >= threshold and duration >= min_duration


class EventDetector:
    """이벤트 감지 클래스"""
    
    def __init__(
        self,
        static_duration: float = 3.0,
        stability_threshold: float = 0.95,
        min_contour_area: int = 500,
        max_tracking_distance: int = 50,
        cooldown_seconds: float = 5.0
    ):
        """
        Args:
            static_duration: 물체가 정지해야 하는 최소 시간 (초)
            stability_threshold: 안정성 임계값 (0~1)
            min_contour_area: 최소 윤곽선 영역
            max_tracking_distance: 같은 물체로 판단할 최대 거리 (픽셀)
            cooldown_seconds: 이벤트 발생 후 대기 시간 (초)
        """
        self.static_duration = static_duration
        self.stability_threshold = stability_threshold
        self.min_contour_area = min_contour_area
        self.max_tracking_distance = max_tracking_distance
        self.cooldown_seconds = cooldown_seconds
        
        # 추적 중인 물체들
        self.tracked_objects: Dict[int, TrackedObject] = {}
        self.next_object_id = 0
        
        # 마지막 이벤트 시간
        self.last_event_time: Optional[datetime] = None
        
        logger.info(
            f"이벤트 감지기 초기화: static_duration={static_duration}s, "
            f"stability_threshold={stability_threshold}"
        )
    
    def update(
        self,
        contours: List[np.ndarray],
        bboxes: List[Tuple[int, int, int, int]],
        timestamp: datetime
    ) -> Optional[TrackedObject]:
        """
        감지된 윤곽선으로 추적 업데이트 및 이벤트 체크
        
        Args:
            contours: 윤곽선 리스트
            bboxes: 경계 박스 리스트 (x, y, w, h)
            timestamp: 현재 타임스탬프
        
        Returns:
            새로운 이벤트가 발생했으면 해당 TrackedObject, 없으면 None
        """
        # Cooldown 체크
        if self.last_event_time is not None:
            cooldown_elapsed = (timestamp - self.last_event_time).total_seconds()
            if cooldown_elapsed < self.cooldown_seconds:
                return None
        
        # 현재 프레임의 물체들
        current_objects = []
        for contour, bbox in zip(contours, bboxes):
            area = cv2.contourArea(contour)
            if area >= self.min_contour_area:
                current_objects.append((bbox, area))
        
        # 기존 추적 물체와 매칭
        matched_ids = set()
        new_objects = []
        
        for bbox, area in current_objects:
            matched_id = self._find_matching_object(bbox)
            
            if matched_id is not None:
                # 기존 물체 업데이트
                self._update_tracked_object(matched_id, bbox, area, timestamp)
                matched_ids.add(matched_id)
            else:
                # 새로운 물체
                new_objects.append((bbox, area))
        
        # 매칭되지 않은 추적 물체 제거
        unmatched_ids = set(self.tracked_objects.keys()) - matched_ids
        for obj_id in unmatched_ids:
            del self.tracked_objects[obj_id]
        
        # 새로운 물체 추가
        for bbox, area in new_objects:
            self._add_tracked_object(bbox, area, timestamp)
        
        # 안정적인 물체가 있는지 체크
        for obj_id, obj in self.tracked_objects.items():
            if obj.is_stable(self.stability_threshold, self.static_duration):
                # 이벤트 발생!
                logger.info(
                    f"이벤트 감지: 물체 ID={obj_id}, "
                    f"위치=({obj.bbox[0]}, {obj.bbox[1]}), "
                    f"크기={obj.bbox[2]}x{obj.bbox[3]}, "
                    f"지속시간={(obj.last_seen - obj.first_seen).total_seconds():.2f}s"
                )
                
                self.last_event_time = timestamp
                
                # 이 물체는 이벤트 처리되었으므로 제거
                del self.tracked_objects[obj_id]
                
                return obj
        
        return None
    
    def _find_matching_object(
        self,
        bbox: Tuple[int, int, int, int]
    ) -> Optional[int]:
        """
        경계 박스와 매칭되는 기존 추적 물체 찾기
        
        Args:
            bbox: 새로운 경계 박스 (x, y, w, h)
        
        Returns:
            매칭된 물체 ID 또는 None
        """
        x, y, w, h = bbox
        center = (x + w // 2, y + h // 2)
        
        min_distance = float('inf')
        best_match_id = None
        
        for obj_id, obj in self.tracked_objects.items():
            ox, oy, ow, oh = obj.bbox
            obj_center = (ox + ow // 2, oy + oh // 2)
            
            # 중심점 거리 계산
            distance = np.sqrt(
                (center[0] - obj_center[0]) ** 2 +
                (center[1] - obj_center[1]) ** 2
            )
            
            if distance < self.max_tracking_distance and distance < min_distance:
                min_distance = distance
                best_match_id = obj_id
        
        return best_match_id
    
    def _update_tracked_object(
        self,
        obj_id: int,
        bbox: Tuple[int, int, int, int],
        area: int,
        timestamp: datetime
    ):
        """추적 물체 정보 업데이트"""
        obj = self.tracked_objects[obj_id]
        
        # 위치 변화량 계산
        old_x, old_y, old_w, old_h = obj.bbox
        new_x, new_y, new_w, new_h = bbox
        
        # 중심점 이동 거리
        old_center_x = old_x + old_w // 2
        old_center_y = old_y + old_h // 2
        new_center_x = new_x + new_w // 2
        new_center_y = new_y + new_h // 2

        position_change = np.sqrt(
            (new_center_x - old_center_x) ** 2 +
            (new_center_y - old_center_y) ** 2
        )

        # 크기 변화율
        old_area = old_w * old_h
        new_area = new_w * new_h
        size_change_ratio = abs(new_area - old_area) / max(old_area, 1)

        # 안정성 점수 계산 (0~1, 1이 가장 안정적)
        # 위치 안정성: 30픽셀 이하 이동 시 높은 점수
        position_stability = max(0, 1 - position_change / 30)

        # 크기 안정성: 20% 이하 변화 시 높은 점수
        size_stability = max(0, 1 - size_change_ratio / 0.2)

        # 가중 평균 (위치 변화가 더 중요)
        current_stability = position_stability * 0.7 + size_stability * 0.3

        # 지수 이동 평균으로 안정성 점수 업데이트 (최근 값에 더 큰 가중치)
        alpha = 0.3  # 최근 값의 가중치
        obj.stability_score = alpha * current_stability + (1 - alpha) * obj.stability_score

        # 정보 업데이트
        obj.bbox = bbox
        obj.area = area
        obj.last_seen = timestamp
        obj.frame_count += 1

        # 디버그 로그 (가끔씩만)
        if obj.frame_count % 30 == 0:
            logger.debug(
                f"물체 ID={obj_id} 추적 중: 프레임={obj.frame_count}, "
                f"안정성={obj.stability_score:.3f}, 이동={position_change:.1f}px"
            )

    def _add_tracked_object(
        self,
        bbox: Tuple[int, int, int, int],
        area: int,
        timestamp: datetime
    ):
        """새로운 추적 물체 추가"""
        obj_id = self.next_object_id
        self.next_object_id += 1
        
        self.tracked_objects[obj_id] = TrackedObject(
            object_id=obj_id,
            bbox=bbox,
            first_seen=timestamp,
            last_seen=timestamp,
            stability_score=0.5,  # 초기 점수
            frame_count=1,
            area=area
        )
        
        logger.debug(f"새 물체 추적 시작: ID={obj_id}, bbox={bbox}")
    
    def reset(self):
        """추적 상태 리셋"""
        self.tracked_objects.clear()
        self.next_object_id = 0
        self.last_event_time = None
        logger.info("이벤트 감지기 리셋")
    
    def get_tracking_info(self) -> Dict:
        """현재 추적 상태 정보 반환"""
        return {
            'tracked_count': len(self.tracked_objects),
            'objects': [
                {
                    'id': obj.object_id,
                    'bbox': obj.bbox,
                    'duration': (obj.last_seen - obj.first_seen).total_seconds(),
                    'stability': obj.stability_score,
                    'frames': obj.frame_count
                }
                for obj in self.tracked_objects.values()
            ]
        }
