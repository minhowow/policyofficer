"""종료 코드와 도구 오류.

  0  끝까지 돌았다
  2  도구 오류 (폴더가 없음, 인자·설정이 잘못됨, 키가 없음 등)
130  Ctrl+C 로 멈춤
"""

EXIT_OK = 0
EXIT_ERROR = 2


class PolicyofficerError(Exception):
    """사용자에게 보여 줄 도구 오류. 종료 코드 2로 나간다."""

    exit_code = EXIT_ERROR


class ConfigError(PolicyofficerError):
    """명령줄 인자나 입력 파일이 잘못됐다."""
