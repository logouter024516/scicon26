"""
설정 파일 로더
config.yaml 및 환경 변수를 로드하고 관리합니다.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv


class ConfigLoader:
    """YAML 설정 파일과 환경 변수를 로드하는 클래스"""

    def __init__(self, config_path: str = None):
        """
        Args:
            config_path: config.yaml 파일 경로 (기본값: config/config.yaml)
        """
        # .env 파일 로드
        load_dotenv()

        # 프로젝트 루트 디렉터리 찾기
        self.project_root = Path(__file__).parent.parent.parent

        # 설정 파일 경로
        if config_path is None:
            config_path = self.project_root / "config" / "config.yaml"
        else:
            config_path = Path(config_path)

        # YAML 설정 로드
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config: Dict[str, Any] = yaml.safe_load(f)

        # 환경 변수로 오버라이드
        self._override_with_env()

        # 경로 설정
        self._setup_paths()

    def _override_with_env(self):
        """환경 변수로 설정 값을 오버라이드"""
        # 데이터베이스 설정
        if os.getenv('DB_HOST'):
            self.config['database']['host'] = os.getenv('DB_HOST')
        if os.getenv('DB_PORT'):
            self.config['database']['port'] = int(os.getenv('DB_PORT'))
        if os.getenv('DB_NAME'):
            self.config['database']['name'] = os.getenv('DB_NAME')
        if os.getenv('DB_USER'):
            self.config['database']['user'] = os.getenv('DB_USER')
        if os.getenv('DB_PASSWORD'):
            self.config['database']['password'] = os.getenv('DB_PASSWORD')

        # 디바이스 설정
        if os.getenv('DEVICE'):
            self.config['yolo']['device'] = os.getenv('DEVICE')
            self.config['clip']['device'] = os.getenv('DEVICE')

        # 카메라 설정
        if os.getenv('CAMERA_DEVICE_ID'):
            self.config['camera']['device_id'] = int(os.getenv('CAMERA_DEVICE_ID'))

        # 로그 레벨
        if os.getenv('LOG_LEVEL'):
            self.config['logging']['level'] = os.getenv('LOG_LEVEL')

    def _setup_paths(self):
        """저장 경로 설정 및 생성"""
        storage = self.config['storage']

        # 상대 경로를 절대 경로로 변환
        storage['clips_dir'] = str(self.project_root / storage['clips_dir'])
        storage['meta_dir'] = str(self.project_root / storage['meta_dir'])
        storage['thumbs_dir'] = str(self.project_root / storage['thumbs_dir'])

        # 디렉터리 생성
        os.makedirs(storage['clips_dir'], exist_ok=True)
        os.makedirs(storage['meta_dir'], exist_ok=True)
        os.makedirs(storage['thumbs_dir'], exist_ok=True)

        # 로그 디렉터리
        log_file = self.project_root / self.config['logging']['file']
        os.makedirs(log_file.parent, exist_ok=True)

    def get(self, key_path: str, default=None):
        """
        점 표기법으로 설정 값 가져오기

        Args:
            key_path: 예) 'camera.device_id' 또는 'database.host'
            default: 키가 없을 때 반환할 기본값

        Returns:
            설정 값
        """
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        설정 섹션 전체 가져오기

        Args:
            section: 예) 'camera', 'database', 'yolo'

        Returns:
            섹션 딕셔너리
        """
        return self.config.get(section, {})


# 싱글톤 인스턴스
_config_instance = None


def get_config() -> ConfigLoader:
    """전역 설정 인스턴스 가져오기"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader()
    return _config_instance
