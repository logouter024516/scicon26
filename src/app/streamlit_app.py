"""
Missingfind GUI 대시보드 (Streamlit)
카메라 라이브 피드, 이벤트 로그, 저장된 클립을 실시간으로 모니터링합니다.

사용법:
    streamlit run src/app/streamlit_app.py
"""

import sys
from pathlib import Path
import json
from datetime import datetime, timedelta
import time
import cv2
import numpy as np
import streamlit as st
from collections import deque
import threading
from typing import Optional, Dict

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.capture.camera import CameraCapture
from src.capture.event_detector import EventDetector
from src.capture.clip_recorder import ClipRecorder
from src.utils.config_loader import get_config
from src.utils.logger import setup_logger


# 페이지 설정 (이모지 사용)
st.set_page_config(
    page_title="🔍 Missingfind - 물체 위치 추적 시스템",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS로 디자인 개선
st.markdown("""
<style>
    /* 메인 배경 */
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* 카드 스타일 */
    .stMetric {
        background: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* 타이틀 스타일 */
    h1 {
        color: white;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        font-weight: 700;
    }
    
    h2, h3 {
        color: #2d3748;
    }
    
    /* 버튼 스타일 */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: 600;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.2);
    }
    
    /* 로그 컨테이너 */
    .log-container {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 10px;
        padding: 15px;
        max-height: 400px;
        overflow-y: auto;
        font-family: 'Courier New', monospace;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* 클립 카드 */
    .clip-card {
        background: white;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.3s;
    }
    
    .clip-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.2);
    }
    
    /* 사이드바 */
    .css-1d391kg {
        background: rgba(255, 255, 255, 0.95);
    }
    
    /* 비디오 프레임 */
    .video-frame {
        border-radius: 15px;
        box-shadow: 0 8px 16px rgba(0,0,0,0.2);
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)


class CaptureThread(threading.Thread):
    """백그라운드에서 카메라 캡처를 처리하는 스레드"""

    def __init__(self, config: Dict):
        super().__init__(daemon=True)
        self.config = config
        self.camera: Optional[CameraCapture] = None
        self.event_detector: Optional[EventDetector] = None
        self.recorder: Optional[ClipRecorder] = None
        self.running = False
        self.current_frame: Optional[np.ndarray] = None
        self.current_timestamp: Optional[datetime] = None
        self.event_logs = deque(maxlen=100)
        self.stats = {
            'frame_count': 0,
            'event_count': 0,
            'tracking_count': 0,
            'fps': 0.0
        }
        self.logger = setup_logger("streamlit_capture", level="INFO")

    def run(self):
        """스레드 실행"""
        try:
            self._initialize()
            self._capture_loop()
        except Exception as e:
            self.logger.error(f"캡처 스레드 오류: {e}", exc_info=True)
            self.event_logs.append({
                'time': datetime.now(),
                'level': 'ERROR',
                'message': f"캡처 오류: {e}"
            })

    def _initialize(self):
        """컴포넌트 초기화"""
        camera_config = self.config.get_section('camera')
        bg_config = self.config.get_section('background_subtraction')
        obj_config = self.config.get_section('object_detection')
        clip_config = self.config.get_section('clip_recording')
        storage_config = self.config.get_section('storage')

        # 카메라 초기화
        self.camera = CameraCapture(
            device_id=camera_config['device_id'],
            resolution=(
                camera_config['resolution']['width'],
                camera_config['resolution']['height']
            ),
            fps=camera_config['fps'],
            buffer_seconds=clip_config['buffer_seconds'],
            bg_subtractor_config={
                'method': bg_config['method'],
                'history': bg_config['history'],
                'var_threshold': bg_config['var_threshold'],
                'detect_shadows': bg_config['detect_shadows'],
                'min_contour_area': obj_config['min_contour_area']
            }
        )

        # 이벤트 감지기 초기화
        self.event_detector = EventDetector(
            static_duration=obj_config['static_duration'],
            stability_threshold=obj_config['stability_threshold'],
            min_contour_area=obj_config['min_contour_area'],
            max_tracking_distance=obj_config.get('max_tracking_distance', 50),
            cooldown_seconds=5.0
        )

        # 클립 레코더 초기화
        self.recorder = ClipRecorder(
            clips_dir=storage_config['clips_dir'],
            meta_dir=storage_config['meta_dir'],
            thumbs_dir=storage_config['thumbs_dir'],
            codec=clip_config['codec'],
            fps=clip_config['fps']
        )

        # 카메라 열기
        if not self.camera.open():
            raise RuntimeError("카메라를 열 수 없습니다")

        self.event_logs.append({
            'time': datetime.now(),
            'level': 'INFO',
            'message': '✅ 시스템 초기화 완료'
        })

    def _capture_loop(self):
        """메인 캡처 루프"""
        camera_config = self.config.get_section('camera')
        clip_config = self.config.get_section('clip_recording')

        fps_start_time = time.time()
        fps_frame_count = 0

        while self.running:
            try:
                # 프레임 읽기
                result = self.camera.read_frame()
                if result is None:
                    time.sleep(0.01)
                    continue

                frame, timestamp = result
                self.current_frame = frame.copy()
                self.current_timestamp = timestamp
                self.stats['frame_count'] += 1
                fps_frame_count += 1

                # FPS 계산 (1초마다)
                if time.time() - fps_start_time >= 1.0:
                    self.stats['fps'] = fps_frame_count / (time.time() - fps_start_time)
                    fps_start_time = time.time()
                    fps_frame_count = 0

                # 움직임 감지
                detection_event = self.camera.detect_motion(frame)

                if detection_event is not None:
                    triggered_event = self.event_detector.update(
                        detection_event.contours,
                        detection_event.bounding_boxes,
                        timestamp
                    )

                    # 추적 정보 업데이트
                    tracking_info = self.event_detector.get_tracking_info()
                    self.stats['tracking_count'] = tracking_info['tracked_count']

                    # 이벤트 발생
                    if triggered_event is not None:
                        self.stats['event_count'] += 1

                        # 로그 추가
                        self.event_logs.append({
                            'time': timestamp,
                            'level': 'EVENT',
                            'message': f'🎯 물체 감지! 위치: ({triggered_event.bbox[0]}, {triggered_event.bbox[1]}), 안정성: {triggered_event.stability_score:.2f}'
                        })

                        # 클립 저장
                        self._save_clip(timestamp, triggered_event, camera_config, clip_config)

            except Exception as e:
                self.logger.error(f"프레임 처리 오류: {e}")
                self.event_logs.append({
                    'time': datetime.now(),
                    'level': 'ERROR',
                    'message': f'프레임 처리 오류: {e}'
                })

    def _save_clip(self, timestamp, triggered_event, camera_config, clip_config):
        """클립 저장"""
        try:
            # 클립 프레임 추출
            buffer_frames = self.camera.get_buffer_frames()
            start_time = timestamp - timedelta(seconds=clip_config['pre_event_seconds'])
            end_time = timestamp + timedelta(seconds=clip_config['post_event_seconds'])

            clip_frames = [
                (frame, ts) for frame, ts in buffer_frames
                if start_time <= ts <= end_time
            ]

            if clip_frames:
                metadata = self.recorder.save_clip(
                    frames=clip_frames,
                    camera_id=str(camera_config['device_id']),
                    camera_name="기본 웹캠",
                    event_time=timestamp,
                    event_type="object_placed",
                    confidence=triggered_event.stability_score,
                    notes=f"물체 크기: {triggered_event.bbox[2]}x{triggered_event.bbox[3]}"
                )

                if metadata:
                    self.event_logs.append({
                        'time': datetime.now(),
                        'level': 'SUCCESS',
                        'message': f'✅ 클립 저장 완료: {metadata.clip_id[:8]}...'
                    })
        except Exception as e:
            self.logger.error(f"클립 저장 오류: {e}")
            self.event_logs.append({
                'time': datetime.now(),
                'level': 'ERROR',
                'message': f'클립 저장 실패: {e}'
            })

    def start_capture(self):
        """캡처 시작"""
        self.running = True
        self.start()

    def stop_capture(self):
        """캡처 중지"""
        self.running = False
        if self.camera:
            self.camera.close()

        self.event_logs.append({
            'time': datetime.now(),
            'level': 'INFO',
            'message': '⏹️ 캡처 중지됨'
        })


def init_session_state():
    """세션 상태 초기화"""
    if 'capture_thread' not in st.session_state:
        st.session_state.capture_thread = None
    if 'is_running' not in st.session_state:
        st.session_state.is_running = False


def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        st.image("https://via.placeholder.com/200x100/667eea/ffffff?text=Missingfind", use_container_width=True)
        st.title("⚙️ 제어판")

        # 시작/중지 버튼
        col1, col2 = st.columns(2)

        with col1:
            if st.button("▶️ 시작", use_container_width=True, disabled=st.session_state.is_running):
                try:
                    config = get_config()
                    st.session_state.capture_thread = CaptureThread(config)
                    st.session_state.capture_thread.start_capture()
                    st.session_state.is_running = True
                    st.success("✅ 시스템 시작됨")
                except Exception as e:
                    st.error(f"❌ 시작 실패: {e}")

        with col2:
            if st.button("⏹️ 중지", use_container_width=True, disabled=not st.session_state.is_running):
                if st.session_state.capture_thread:
                    st.session_state.capture_thread.stop_capture()
                    st.session_state.is_running = False
                    st.success("✅ 시스템 중지됨")

        st.divider()

        # 설정
        st.subheader("🎛️ 설정")

        with st.expander("카메라 설정", expanded=False):
            config = get_config()
            camera_config = config.get_section('camera')
            st.text(f"카메라 ID: {camera_config['device_id']}")
            st.text(f"해상도: {camera_config['resolution']['width']}x{camera_config['resolution']['height']}")
            st.text(f"FPS: {camera_config['fps']}")

        with st.expander("감지 설정", expanded=False):
            obj_config = config.get_section('object_detection')
            st.text(f"안정 시간: {obj_config['static_duration']}초")
            st.text(f"최소 영역: {obj_config['min_contour_area']} px²")
            st.text(f"안정성 임계값: {obj_config['stability_threshold']}")

        st.divider()

        # 정보
        st.subheader("ℹ️ 정보")
        st.info("""
        **Missingfind**는 AI 기반 물체 위치 추적 시스템입니다.
        
        - 실시간 카메라 모니터링
        - 자동 이벤트 감지
        - 비디오 클립 저장
        """)

        st.divider()

        # 링크
        st.markdown("---")
        st.markdown("Made with ❤️ by Missingfind Team")


def render_main_dashboard():
    """메인 대시보드 렌더링"""
    # 헤더
    st.title("🔍 Missingfind - 물체 위치 추적 시스템")
    st.markdown("실시간으로 카메라를 모니터링하고 물체 배치 이벤트를 감지합니다.")

    # 통계 카드
    if st.session_state.capture_thread and st.session_state.is_running:
        stats = st.session_state.capture_thread.stats

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="📊 처리된 프레임",
                value=f"{stats['frame_count']:,}",
                delta=f"{stats['fps']:.1f} FPS"
            )

        with col2:
            st.metric(
                label="🎯 감지된 이벤트",
                value=f"{stats['event_count']}",
            )

        with col3:
            st.metric(
                label="👁️ 추적 중인 물체",
                value=f"{stats['tracking_count']}",
            )

        with col4:
            config = get_config()
            storage_config = config.get_section('storage')
            recorder = ClipRecorder(
                clips_dir=storage_config.get('clips_dir'),
                meta_dir=storage_config.get('meta_dir'),
                thumbs_dir=storage_config.get('thumbs_dir'),
                codec='mp4v',
                fps=30
            )
            storage_gb = recorder.get_total_storage_size()
            st.metric(
                label="💾 저장 용량",
                value=f"{storage_gb:.2f} GB",
            )
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="📊 처리된 프레임", value="0", delta="0.0 FPS")
        with col2:
            st.metric(label="🎯 감지된 이벤트", value="0")
        with col3:
            st.metric(label="👁️ 추적 중인 물체", value="0")
        with col4:
            st.metric(label="💾 저장 용량", value="0.00 GB")

    st.divider()

    # 메인 컨텐츠: 2열 레이아웃
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("📹 라이브 카메라")
        camera_placeholder = st.empty()

        # 라이브 피드 표시
        if st.session_state.capture_thread and st.session_state.is_running:
            if st.session_state.capture_thread.current_frame is not None:
                frame = st.session_state.capture_thread.current_frame

                # BGR to RGB 변환
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # 프레임에 타임스탬프 추가
                if st.session_state.capture_thread.current_timestamp:
                    timestamp_text = st.session_state.capture_thread.current_timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    cv2.putText(
                        frame_rgb,
                        timestamp_text,
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2
                    )

                camera_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)
            else:
                camera_placeholder.info("⏳ 프레임 로딩 중...")
        else:
            camera_placeholder.info("▶️ 시작 버튼을 눌러 카메라를 활성화하세요")

    with col_right:
        st.subheader("📝 이벤트 로그")
        log_container = st.container()

        with log_container:
            if st.session_state.capture_thread and st.session_state.is_running:
                logs = list(st.session_state.capture_thread.event_logs)

                if logs:
                    # 최근 로그부터 표시 (역순)
                    log_html = '<div class="log-container">'
                    for log in reversed(logs[-20:]):  # 최근 20개만 표시
                        time_str = log['time'].strftime('%H:%M:%S')
                        level = log['level']
                        message = log['message']

                        # 로그 레벨에 따른 색상
                        color = {
                            'INFO': '#3182ce',
                            'SUCCESS': '#38a169',
                            'EVENT': '#d69e2e',
                            'ERROR': '#e53e3e'
                        }.get(level, '#718096')

                        log_html += f'<div style="margin: 5px 0; padding: 8px; background: rgba(0,0,0,0.02); border-left: 3px solid {color}; border-radius: 4px;">'
                        log_html += f'<span style="color: {color}; font-weight: bold;">[{time_str}]</span> '
                        log_html += f'<span style="color: #2d3748;">{message}</span>'
                        log_html += '</div>'

                    log_html += '</div>'
                    st.markdown(log_html, unsafe_allow_html=True)
                else:
                    st.info("이벤트 로그가 없습니다")
            else:
                st.info("시스템이 실행 중이 아닙니다")


def render_clips_page():
    """저장된 클립 페이지"""
    st.title("🎬 저장된 클립")
    st.markdown("감지된 이벤트의 비디오 클립을 확인하세요.")

    # 설정 로드
    config = get_config()
    storage_config = config.get_section('storage')
    meta_dir = Path(storage_config.get('meta_dir', 'data/meta'))
    clips_dir = Path(storage_config.get('clips_dir', 'data/clips'))
    thumbs_dir = Path(storage_config.get('thumbs_dir', 'data/thumbs'))

    # 메타데이터 파일 목록
    meta_files = sorted(list(meta_dir.glob('*.json')), key=lambda x: x.stat().st_mtime, reverse=True)

    if not meta_files:
        st.info("저장된 클립이 없습니다. 시스템을 시작하고 물체를 배치해보세요!")
        return

    st.success(f"총 {len(meta_files)}개의 클립이 저장되어 있습니다")

    # 필터
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_query = st.text_input("🔍 검색", placeholder="클립 ID, 카메라 이름 등...")
    with col2:
        sort_by = st.selectbox("정렬", ["최신순", "오래된순", "신뢰도순"])
    with col3:
        items_per_page = st.selectbox("표시 개수", [10, 20, 50], index=0)

    st.divider()

    # 클립 표시
    for i, meta_file in enumerate(meta_files[:items_per_page]):
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # 검색 필터 적용
            if search_query:
                search_text = f"{metadata.get('clip_id', '')} {metadata.get('camera_name', '')}"
                if search_query.lower() not in search_text.lower():
                    continue

            # 클립 카드
            with st.container():
                col_thumb, col_info = st.columns([1, 3])

                with col_thumb:
                    # 썸네일 표시
                    thumb_filename = metadata.get('thumbnail_path', '')

                    if thumb_filename:
                        # 상대 경로인 경우 프로젝트 루트 기준으로 변환
                        thumb_path = Path(thumb_filename)

                        # 절대 경로가 아니면 프로젝트 루트 기준으로 변환
                        if not thumb_path.is_absolute():
                            thumb_path = project_root / thumb_path

                        if thumb_path.exists():
                            st.image(str(thumb_path), use_container_width=True)
                        else:
                            # 파일이 없으면 파일명만으로 thumbs_dir에서 찾기
                            thumb_filename_only = thumb_path.name
                            thumb_path_alt = thumbs_dir / thumb_filename_only
                            if thumb_path_alt.exists():
                                st.image(str(thumb_path_alt), use_container_width=True)
                            else:
                                st.image("https://via.placeholder.com/300x200/667eea/ffffff?text=No+Thumbnail", use_container_width=True)
                    else:
                        st.image("https://via.placeholder.com/300x200/667eea/ffffff?text=No+Thumbnail", use_container_width=True)

                with col_info:
                    # 클립 정보
                    st.markdown(f"### 📹 {metadata.get('clip_id', 'Unknown')[:12]}...")

                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.markdown(f"**📅 시간:**  \n{metadata.get('event_time', 'N/A')}")
                    with col_b:
                        st.markdown(f"**📷 카메라:**  \n{metadata.get('camera_name', 'N/A')}")
                    with col_c:
                        confidence = metadata.get('confidence', 0) * 100
                        st.markdown(f"**✨ 신뢰도:**  \n{confidence:.1f}%")

                    # 버튼
                    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
                    with col_btn1:
                        if st.button("▶️ 재생", key=f"play_{i}"):
                            st.info("비디오 재생 기능은 곧 추가됩니다!")
                    with col_btn2:
                        # 클립 파일 경로 처리
                        clip_file_path = metadata.get('file_path', '')
                        if clip_file_path:
                            clip_path = Path(clip_file_path)
                            # 절대 경로가 아니면 프로젝트 루트 기준으로 변환
                            if not clip_path.is_absolute():
                                clip_path = project_root / clip_path
                        else:
                            # file_path가 없으면 file_name 사용
                            file_name = metadata.get('file_name', '')
                            clip_path = clips_dir / file_name

                        if clip_path.exists():
                            with open(clip_path, 'rb') as f:
                                st.download_button(
                                    label="💾 다운로드",
                                    data=f,
                                    file_name=clip_path.name,
                                    mime='video/mp4',
                                    key=f"download_{i}"
                                )
                        else:
                            st.warning("파일 없음")

                st.divider()

        except Exception as e:
            st.error(f"클립 로드 오류: {e}")


def main():
    """메인 함수"""
    init_session_state()

    # 사이드바
    render_sidebar()

    # 탭
    tab1, tab2 = st.tabs(["🏠 대시보드", "🎬 저장된 클립"])

    with tab1:
        render_main_dashboard()

        # 자동 새로고침 (1초마다)
        if st.session_state.is_running:
            time.sleep(0.5)
            st.rerun()

    with tab2:
        render_clips_page()


if __name__ == "__main__":
    main()
