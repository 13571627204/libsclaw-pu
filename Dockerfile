# ===== 阶段 1:构建 WebUI(dashboard)=====
# 前端在镜像内自动构建,无需手动 pnpm build 再复制。
FROM node:22-bookworm-slim AS dashboard-builder

# pnpm 10 匹配 dashboard/pnpm-lock.yaml(lockfileVersion 9.0)与 pnpm-workspace.yaml 的 allowBuilds
RUN npm install -g pnpm@10

WORKDIR /build/dashboard

# 先只拷贝依赖清单,充分利用 Docker 层缓存(依赖不变则不重装)
COPY dashboard/package.json dashboard/pnpm-lock.yaml dashboard/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# write-dist-version.mjs 会读 ../pyproject.toml 生成 dist/assets/version,
# 后端启动时靠它校验 WebUI 与核心版本是否匹配,缺了会触发在线下载兜底。
COPY pyproject.toml /build/pyproject.toml
COPY dashboard/ ./

# 跳过 vue-tsc 类型检查(类型检查在本地/CI 做),只做产物构建
RUN node scripts/subset-mdi-font.mjs \
    && pnpm exec vite build \
    && node scripts/write-dist-version.mjs

# ===== 阶段 2:运行时镜像 =====
FROM python:3.12-slim

# 与共享 daemon、扩展统一的 opencli 版本(扩展 v1.0.19 兼容 >=1.7.0)
ARG OPENCLI_VERSION=1.8.3

WORKDIR /LibsClaw

# 弱网健壮性:apt 下载失败自动重试,避免个别包 502 导致整层失败
RUN printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\nAcquire::https::Timeout "30";\n' > /etc/apt/apt.conf.d/80-retries

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    ca-certificates \
    bash \
    ffmpeg \
    libavcodec-extra \
    curl \
    gnupg \
    git \
    ripgrep \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 内置 opencli CLI:客户容器经 socat 边车桥接到共享浏览器 daemon(见 deploy/OPENCLI-BROWSER.md)
RUN npm install -g "@jackwener/opencli@${OPENCLI_VERSION}"

COPY . /LibsClaw/

RUN python -m pip install uv \
    && echo "3.12" > .python-version \
    && uv lock \
    && uv export --format requirements.txt --output-file requirements.txt --frozen \
    && uv pip install -r requirements.txt --no-cache-dir --system \
    && uv pip install socksio uv pilk --no-cache-dir --system

# WebUI 产物放进后端的内置 dist 路径(get_bundled_dashboard_dist_path)
COPY --from=dashboard-builder /build/dashboard/dist /LibsClaw/astrbot/dashboard/dist

EXPOSE 6185

CMD ["python", "main.py"]
