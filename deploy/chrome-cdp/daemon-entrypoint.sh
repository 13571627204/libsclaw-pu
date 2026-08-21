#!/usr/bin/env bash
# 共享 opencli daemon 的容器入口。
# 前台运行 daemon.js(它顶层 httpServer.listen 是阻塞的),作为容器 PID 1 常驻;
# 崩溃则容器退出,由 docker 的 restart: unless-stopped 自动拉起。
#
# 本容器 network_mode: service:chromium,所以 daemon 绑的 127.0.0.1:19825
# 与 Chromium 里扩展连接的 127.0.0.1:19825 是同一个。
set -uo pipefail

DAEMON_SCRIPT="$(npm root -g)/@jackwener/opencli/dist/src/daemon.js"

if [ ! -f "$DAEMON_SCRIPT" ]; then
  echo "[daemon-entrypoint] 错误: 找不到 daemon 脚本 $DAEMON_SCRIPT" >&2
  echo "[daemon-entrypoint] 检查 opencli 是否正确安装到全局" >&2
  exit 1
fi

echo "[daemon-entrypoint] opencli 版本: $(opencli --version 2>/dev/null || echo unknown)"
echo "[daemon-entrypoint] 前台启动 daemon: $DAEMON_SCRIPT"
echo "[daemon-entrypoint] 监听端口: ${OPENCLI_DAEMON_PORT:-19825} (127.0.0.1)"

exec node "$DAEMON_SCRIPT"
