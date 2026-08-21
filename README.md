# LibsClaw

LibsClaw 是一个多平台 LLM 聊天机器人及 Agent 开发框架，支持接入多种即时通讯平台与主流模型服务，内置 WebUI、插件系统、知识库、Agent 沙箱等能力。

> 本项目基于 AGPL-3.0 协议的开源软件构建，遵循 AGPL-3.0-or-later 许可发布，详见 [LICENSE](LICENSE)。

## 快速开始

### 源码运行

需要 Python 3.12+、[uv](https://docs.astral.sh/uv/)、Node.js 与 pnpm。

### Docker

```bash
docker build -t libsclaw:latest .
docker compose up -d
```

## 开发

一键启动后端和 Vite 前端开发服务器：

```bash
./scripts/dev.sh
```

首次运行时，脚本会在缺少依赖目录时自动执行 `uv sync` 和 `pnpm install`。如已自行同步依赖，可跳过自动安装：


### Windows

在仓库根目录使用等价的 PowerShell 脚本（macOS / Linux 部署继续使用 `./scripts/dev.sh`，两者行为一致）：

```powershell
.\dev.cmd
# 或
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1
```

Windows 与 macOS/Linux 行为一致：后端日志不会直接刷屏，控制台只显示账号/密码行与错误行，完整后端日志写入 `logs/dev-backend.log`；前端（Vite）输出原样显示。

## 许可

本项目遵循 [AGPL-3.0-or-later](LICENSE) 协议。若基于本项目对外提供网络服务，请依照协议开放对应源代码。
