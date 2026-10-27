FROM python:3.13-slim

ARG FUNASR_VERSION=1.4.16
ARG TORCH_VERSION=2.8.0
ARG TORCHAUDIO_VERSION=2.8.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FUNASR_MODEL=sensevoice \
    FUNASR_DEVICE=cpu \
    FUNASR_PORT=8000 \
    MODELSCOPE_CACHE=/models

WORKDIR /app

RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g; s|http://security.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    else \
        sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g; s|http://security.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu \
        "torch==${TORCH_VERSION}" \
        "torchaudio==${TORCHAUDIO_VERSION}" \
    && pip install --index-url https://mirrors.aliyun.com/pypi/simple/ \
        "funasr==${FUNASR_VERSION}" \
        fastapi \
        "uvicorn[standard]" \
        python-multipart

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=900s --retries=10 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.getenv('FUNASR_PORT', '8000'), timeout=5).read()" || exit 1

CMD ["sh", "-c", "funasr-server --host 0.0.0.0 --port ${FUNASR_PORT:-8000} --device ${FUNASR_DEVICE:-cpu} --model ${FUNASR_MODEL:-sensevoice}"]
