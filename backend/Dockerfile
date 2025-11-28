# 用 Python 3.12-bookworm-slim（Debian 12 稳定版，更可靠）
FROM python:3.12-bookworm-slim

# 安装 Playwright 官方推荐的系统依赖（已适配 Debian 12，去掉弃用包）
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 基础工具
    wget gnupg ca-certificates \
    # Playwright 核心依赖（Chromium）
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libxss1 libasound2 libpangocairo-1.0-0 \
    libgtk-3-0 libatspi2.0-0 libcups2 \
    # 字体和渲染（关键）
    fonts-liberation libappindicator3-1 libu2f-udev \
    # X11 虚拟显示（headless 模式用）
    xvfb \
    # 清理缓存
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 设置工作目录
WORKDIR /app

# 复制 requirements 并安装 Python 包
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright + Chromium（路径固定）
RUN python -m playwright install --with-deps chromium

# 复制所有代码（包括 chrome-extensions）
COPY . .

# 暴露端口（Render 用 $PORT）
EXPOSE $PORT

# 启动命令（用 sh -c 兼容环境变量）
CMD ["sh", "-c", "python main.py"]