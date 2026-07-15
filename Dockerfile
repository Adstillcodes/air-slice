# Air Slice (pygame) — LINUX HOSTS ONLY.
#
# A container can only reach a webcam and a display on a Linux host
# (--device /dev/video0 + X11 socket passthrough). On Windows/macOS stall
# laptops, run natively instead — see README "Stall laptop setup".

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    libx11-6 libxext6 libxrandr2 libxcursor1 libxi6 libxfixes3 \
    libxrender1 libxss1 libxxf86vm1 libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV DATA_DIR=/data \
    SDL_AUDIODRIVER=dummy
RUN mkdir -p /data

CMD ["python", "-m", "app.desktop"]
