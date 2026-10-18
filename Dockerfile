FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Runtime JavaScript requis par yt-dlp pour déchiffrer les flux YouTube
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh
ENV PATH="/usr/local/bin:${PATH}"
RUN deno --version
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "import yt_dlp, sys; print('yt-dlp', yt_dlp.version.__version__)"
COPY . .
ENV PORT=8080
EXPOSE 8080
CMD gunicorn -w 1 --threads 4 -t 600 -b 0.0.0.0:${PORT} app:app
