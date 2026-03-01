"""
로깅 설정 모듈
프로젝트 전체에서 사용할 로거를 설정합니다.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "bactriev",
    level: str = "INFO",
    log_file: Optional[str] = None,
    console: bool = True
) -> logging.Logger:
    """
    로거 설정

    Args:
        name: 로거 이름
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 로그 파일 경로 (None이면 파일에 기록하지 않음)
        console: 콘솔 출력 여부

    Returns:
        설정된 로거 객체
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # 기존 핸들러 제거
    logger.handlers.clear()

    # 포맷터 설정
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 콘솔 핸들러
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 파일 핸들러
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "bactriev") -> logging.Logger:
    """
    기존 로거 가져오기 (없으면 기본 설정으로 생성)

    Args:
        name: 로거 이름

    Returns:
        로거 객체
    """
    logger = logging.getLogger(name)

    # 핸들러가 없으면 기본 설정
    if not logger.handlers:
        logger = setup_logger(name)

    return logger
