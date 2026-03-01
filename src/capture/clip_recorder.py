"""
이벤트 클립 녹화 및 저장 모듈
감지된 이벤트를 MP4 파일로 저장하고 메타데이터를 JSON으로 기록합니다.
"""

import cv2
import json
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, asdict
import uuid

from ..utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class ClipMetadata:
    """클립 메타데이터 구조"""
    clip_id: str
    file_path: str
    camera_id: str
    camera_name: str
    start_time: str  # ISO 8601 형식
    end_time: str    # ISO 8601 형식
    duration_seconds: float
    frame_count: int
    fps: float
    resolution: Tuple[int, int]  # (width, height)
    event_time: str  # 이벤트가 발생한 시간
    event_type: str  # 예: "object_placed", "motion_detected"
    confidence: float
    thumbnail_path: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class ClipRecorder:
    """이벤트 클립을 MP4 파일로 저장하는 클래스"""

    def __init__(
        self,
        clips_dir: str = "data/clips",
        meta_dir: str = "data/meta",
        thumbs_dir: str = "data/thumbs",
        codec: str = "mp4v",
        fps: float = 30.0
    ):
        """
        Args:
            clips_dir: MP4 클립 저장 디렉터리
            meta_dir: JSON 메타데이터 저장 디렉터리
            thumbs_dir: 썸네일 이미지 저장 디렉터리
            codec: 비디오 코덱 (mp4v, avc1, xvid 등)
            fps: 저장할 프레임률
        """
        self.clips_dir = Path(clips_dir)
        self.meta_dir = Path(meta_dir)
        self.thumbs_dir = Path(thumbs_dir)
        self.codec = codec
        self.fps = fps

        # 디렉터리 생성
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.thumbs_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"클립 레코더 초기화: clips={clips_dir}, meta={meta_dir}, fps={fps}")

    def save_clip(
        self,
        frames: List[Tuple[Any, datetime]],  # (frame, timestamp) 리스트
        camera_id: str,
        camera_name: str,
        event_time: datetime,
        event_type: str = "object_placed",
        confidence: float = 1.0,
        notes: str = ""
    ) -> Optional[ClipMetadata]:
        """
        프레임 리스트를 MP4 클립으로 저장

        Args:
            frames: (프레임, 타임스탬프) 튜플의 리스트
            camera_id: 카메라 ID
            camera_name: 카메라 이름
            event_time: 이벤트 발생 시간
            event_type: 이벤트 유형
            confidence: 감지 신뢰도
            notes: 추가 메모

        Returns:
            ClipMetadata 또는 None (실패 시)
        """
        if not frames or len(frames) == 0:
            logger.warning("저장할 프레임이 없습니다")
            return None

        try:
            # 클립 ID 생성 (UUID)
            clip_id = str(uuid.uuid4())

            # 파일 이름 생성 (시간 기반)
            timestamp_str = event_time.strftime("%Y%m%d_%H%M%S")
            clip_filename = f"{timestamp_str}_{camera_id}_{clip_id[:8]}.mp4"
            clip_path = self.clips_dir / clip_filename

            # 첫 프레임에서 해상도 가져오기
            first_frame = frames[0][0]
            height, width = first_frame.shape[:2]
            resolution = (width, height)

            # 비디오 라이터 생성
            fourcc = cv2.VideoWriter_fourcc(*self.codec)
            writer = cv2.VideoWriter(
                str(clip_path),
                fourcc,
                self.fps,
                resolution
            )

            if not writer.isOpened():
                logger.error(f"비디오 라이터를 열 수 없습니다: {clip_path}")
                return None

            # 프레임 쓰기
            frame_count = 0
            for frame, timestamp in frames:
                writer.write(frame)
                frame_count += 1

            writer.release()

            # 메타데이터 생성
            start_time = frames[0][1]
            end_time = frames[-1][1]
            duration = (end_time - start_time).total_seconds()

            metadata = ClipMetadata(
                clip_id=clip_id,
                file_path=str(clip_path.relative_to(self.clips_dir.parent)),
                camera_id=camera_id,
                camera_name=camera_name,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                duration_seconds=duration,
                frame_count=frame_count,
                fps=self.fps,
                resolution=resolution,
                event_time=event_time.isoformat(),
                event_type=event_type,
                confidence=confidence,
                notes=notes
            )

            # 썸네일 저장 (이벤트 시간에 가장 가까운 프레임)
            thumb_path = self._save_thumbnail(frames, event_time, clip_id)
            if thumb_path:
                metadata.thumbnail_path = str(thumb_path.relative_to(self.clips_dir.parent))

            # 메타데이터 JSON 저장
            meta_filename = f"{timestamp_str}_{camera_id}_{clip_id[:8]}.json"
            meta_path = self.meta_dir / meta_filename

            with open(meta_path, 'w', encoding='utf-8') as f:
                f.write(metadata.to_json())

            logger.info(
                f"클립 저장 완료: {clip_filename} "
                f"({frame_count} 프레임, {duration:.2f}초)"
            )

            return metadata

        except Exception as e:
            logger.error(f"클립 저장 실패: {e}", exc_info=True)
            return None

    def _save_thumbnail(
        self,
        frames: List[Tuple[Any, datetime]],
        event_time: datetime,
        clip_id: str
    ) -> Optional[Path]:
        """
        이벤트 시간에 가장 가까운 프레임을 썸네일로 저장

        Args:
            frames: 프레임 리스트
            event_time: 이벤트 시간
            clip_id: 클립 ID

        Returns:
            썸네일 경로 또는 None
        """
        try:
            # 이벤트 시간에 가장 가까운 프레임 찾기
            closest_frame = None
            min_diff = float('inf')

            for frame, timestamp in frames:
                diff = abs((timestamp - event_time).total_seconds())
                if diff < min_diff:
                    min_diff = diff
                    closest_frame = frame

            if closest_frame is None:
                return None

            # 썸네일 저장
            thumb_filename = f"{clip_id[:8]}_thumb.jpg"
            thumb_path = self.thumbs_dir / thumb_filename

            cv2.imwrite(str(thumb_path), closest_frame)

            logger.debug(f"썸네일 저장: {thumb_filename}")
            return thumb_path

        except Exception as e:
            logger.warning(f"썸네일 저장 실패: {e}")
            return None

    def load_metadata(self, meta_path: str) -> Optional[ClipMetadata]:
        """
        JSON 파일에서 메타데이터 로드

        Args:
            meta_path: 메타데이터 JSON 파일 경로

        Returns:
            ClipMetadata 또는 None
        """
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return ClipMetadata(**data)

        except Exception as e:
            logger.error(f"메타데이터 로드 실패: {meta_path}, {e}")
            return None

    def list_clips(self) -> List[ClipMetadata]:
        """
        모든 클립의 메타데이터 리스트 반환

        Returns:
            ClipMetadata 리스트 (최신순)
        """
        clips = []

        try:
            # 모든 JSON 파일 찾기
            meta_files = sorted(
                self.meta_dir.glob("*.json"),
                reverse=True  # 최신순
            )

            for meta_file in meta_files:
                metadata = self.load_metadata(str(meta_file))
                if metadata:
                    clips.append(metadata)

            logger.debug(f"클립 목록 로드: {len(clips)}개")

        except Exception as e:
            logger.error(f"클립 목록 로드 실패: {e}")

        return clips

    def get_total_storage_size(self) -> float:
        """
        전체 클립 저장 용량 계산 (GB)

        Returns:
            전체 용량 (GB)
        """
        total_bytes = 0

        try:
            for clip_file in self.clips_dir.glob("*.mp4"):
                total_bytes += clip_file.stat().st_size

            total_gb = total_bytes / (1024 ** 3)
            return total_gb

        except Exception as e:
            logger.error(f"저장 용량 계산 실패: {e}")
            return 0.0
