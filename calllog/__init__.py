"""call-log-maker: 음성/텍스트 기록을 깔끔한 통화록(.md/.docx)으로 바꿔 주는 로컬 도구."""

import os

# faster-whisper 가 모델 파일을 받을 때, Windows 에서는 캐시에 symlink 를 만들 수 없어
# huggingface_hub 가 긴 UserWarning 을 출력한다(동작과는 무관, 첫 다운로드 때 화면을 덮음).
# huggingface_hub 는 import 될 때 이 값을 읽으므로, 패키지가 가장 먼저 불러지는 여기서 정한다.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

__version__ = "1.0.1"
__all__ = ["__version__"]
