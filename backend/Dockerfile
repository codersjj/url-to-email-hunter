# 用 Python 3.12 slim 镜像（轻量，避免 greenlet 问题）
FROM python:3.12-slim

# 安装 Playwright 系统依赖（无 su 问题，因为 Dockerfile 有 root 权限）
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libxss1 libasound2 libpangocairo-1.0-0 \
    libgtk-3-0 libatspi2.0-0 libcups2 libxrandr2 \
    libxss1 libgconf-2-4 xvfb \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制 requirements 并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright + Chromium（现在路径固定，不会丢）
RUN python -m playwright install --with-deps chromium

# 复制所有代码（包括 chrome-extensions 文件夹）
COPY . .

# 暴露端口（Render 会用 $PORT）
EXPOSE $PORT

# 启动命令（用环境变量端口）
CMD ["sh", "-c", "python main.py"]