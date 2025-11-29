# 2025 年 Render 上最稳的 Playwright 部署方案
FROM python:3.12-slim-bookworm

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 libcairo2 libcups2 \
    libdbus-1-3 libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 libnss3 libx11-6 libxcomposite1 \
    libxdamage1 libxrandr2 wget xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 只装 chromium（自带，支持 headless=False 模拟）
RUN python -m playwright install --with-deps chromium

COPY . .

ENV PORT=10000

CMD ["python", "main.py"]