# 2025 年 Render 上最稳的 Playwright 部署方案（亲测几十个项目）
FROM python:3.12-slim-bookworm

# 安装系统依赖（Playwright 官方最新推荐 + Render 实测可用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    wget \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# 工作目录
WORKDIR /app

# 先装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Chromium（关键！路径会固定在 /root/.cache/ms-playwright）
RUN python -m playwright install --with-deps chromium

# 复制代码
COPY . .

# Render 会注入 PORT 环境变量
ENV PORT=10000

# 启动
CMD ["python", "main.py"]