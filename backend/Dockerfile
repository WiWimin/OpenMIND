FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 可选 pip 镜像（慢速网络下通过 PIP_INDEX_URL 构建参数加速，如
# https://pypi.tuna.tsinghua.edu.cn/simple；默认官方源）
ARG PIP_INDEX_URL=https://pypi.org/simple

COPY requirements.txt ./
RUN pip install --upgrade pip -i "$PIP_INDEX_URL" \
    && pip install -r requirements.txt -i "$PIP_INDEX_URL"

# ffmpeg：实时录音（Chromium MediaRecorder webm/ogg）送 FunASR 前转码为 wav。
# 置于 pip 层之后以复用依赖层缓存。
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
