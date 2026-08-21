# OpenCLI 扩展模式接入验证手册

> 目的:验证 **「opencli + Browser Bridge 扩展 + 容器化 Chromium」** 能否跑通,让网站命令(bilibili/小红书等)复用容器内 Chromium 的登录态。
>
> 背景:经源码确认,v1.8.3 的 `OPENCLI_CDP_ENDPOINT` **只对 Electron 桌面应用生效**,网站命令**只能走 daemon+扩展**。所以放弃 CDP,改用官方主推的扩展模式。
> (目录名仍叫 chrome-cdp 是历史遗留,不影响使用。)

## 架构铁律

官方文档明确:通信链 `opencli ↔ daemon(localhost:19825) ↔ 扩展 ↔ 浏览器`,**默认全在 localhost**。

容器化的关键:
- 扩展跑在 **Chromium 容器里**,连的是 **Chromium 容器的** `localhost:19825`
- 所以 opencli/daemon 必须出现在 **同一个 localhost** 上
- 但 `linuxserver/chromium` 镜像没有 Node.js

**解法**:opencli 容器用 `network_mode: service:chromium` 共享 Chromium 的网络命名空间。这样 daemon 绑的 `localhost:19825` 和扩展连的 `localhost:19825` 物理上是同一个。

```
docker 网络
┌─────────────────────────────────────────┐
│ chromium 容器(opencli-chromium)           │
│   linuxserver/chromium(自带网页VNC)        │
│   + Browser Bridge 扩展(在浏览器里)        │
│        ▲ localhost:19825                  │
│ opencli 容器(opencli-runner)              │
│   network_mode: service:chromium ←共享网络 │
│   opencli + daemon(localhost:19825)       │
└─────────────────────────────────────────┘
  网页VNC 3001 仅绑 127.0.0.1 → SSH 隧道访问
```

---

## 操作步骤(在服务器上)

### 1. 下载并解压扩展到 Chromium 可见的目录

扩展要放进挂载给容器的 `chromium-config/`(对应容器内 `/config`),这样网页VNC 里能 load unpacked。

```bash
cd deploy/chrome-cdp
mkdir -p chromium-config

# 下载扩展(v1.8.3 release 里捆绑的扩展是 v1.0.19)
curl -L -o /tmp/opencli-ext.zip \
  https://github.com/jackwener/OpenCLI/releases/download/v1.8.3/opencli-extension-v1.0.19.zip

# 解压到 chromium-config/opencli-extension/(容器内路径 /config/opencli-extension)
mkdir -p chromium-config/opencli-extension
unzip -o /tmp/opencli-ext.zip -d chromium-config/opencli-extension

# 看一眼解压结构,确认有 manifest.json
ls chromium-config/opencli-extension/
# 若 manifest.json 在子目录里,记下那个子目录,load unpacked 时要选到含 manifest.json 的那层
```

### 2. 启动 Chromium + opencli 容器

```bash
docker compose -f docker-compose.verify.yml up -d
docker compose -f docker-compose.verify.yml ps   # 两个容器都 Up
```

### 3. 进网页VNC,装扩展 + 登录网站

本地电脑开 SSH 隧道:

```bash
# 本地电脑执行
ssh -L 3000:127.0.0.1:3000 -L 3001:127.0.0.1:3001 服务器用户@服务器IP
```

本地浏览器访问 `https://localhost:3001`(忽略证书警告;若 WebSocket 仍断开,试 `http://localhost:3000`)→ 进入容器里的 Chromium 桌面,然后:

1. 地址栏输入 `chrome://extensions`
2. 右上角打开 **开发者模式(Developer mode)**
3. 点 **加载已解压的扩展程序(Load unpacked)**
4. 选择 `/config/opencli-extension`(若 manifest.json 在子目录,选到那一层)
5. 确认扩展出现在列表且已启用
6. 在 Chromium 里**打开并登录目标网站**(如 bilibili.com),登录态会存进 `/config`,重启不丢

### 4. 在 opencli 容器里装 opencli 并验证 ⭐

```bash
docker exec -it opencli-runner bash

# 容器内:确认 Node >= 21
node --version

# 装 opencli。pin 到 1.8.3 以匹配扩展 v1.0.19(避免版本不兼容)
npm install -g @jackwener/opencli@1.8.3

# 验证扩展是否连上(关键)
opencli doctor

# 通了再跑真实命令
opencli bilibili hot --limit 5
```

---

## 结果判读

| `opencli doctor` 结果 | 含义 | 下一步 |
|------|------|--------|
| Daemon OK + Extension connected + Connectivity OK | ✅ 全通,方案成立 | 告诉我,做多客户工程化 |
| Extension: not connected | 扩展没连上 daemon | 见下方排查 |
| 版本不兼容警告(CLI/扩展版本不匹配) | opencli 版本和扩展 v1.0.19 对不上 | 确认装的是 `@1.8.3`;或换扩展版本 |

**Extension not connected 排查:**
1. 确认网页VNC 里扩展**已启用**(开发者模式没关、扩展没被禁用)
2. 在 opencli 容器里 `opencli daemon stop` 后重跑 `opencli doctor`(让扩展重新握手)
3. 确认两容器**确实共享网络**:`docker exec opencli-runner sh -c "curl -s localhost:19825/status"` 应有响应
4. Chromium 重启后开发者模式扩展可能被禁用,需回 VNC 重新启用

---

## ⚠️ 安全 & 已知风险

- 网页VNC(3001)只绑 `127.0.0.1`,**不暴露公网**,只走 SSH 隧道。
- **登录态共享**:多客户共用这一个 Chromium,所有客户 Agent 操作同一批账号 Cookie(你已确认接受)。
- **扩展持久化存疑**:Chromium 重启后,`load unpacked` 的开发者模式扩展有可能被禁用或弹警告。这是验证要重点观察的点之一 —— 若每次重启都要重新启用,生产环境需要额外处理(如用 policy 强制安装),验证时先确认这个行为。

---

把第 4 步 `opencli doctor` 和 `opencli bilibili hot` 的输出贴给我。

- **通了** → 我给生产版:把 Chromium+opencli 固化进 `deploy/`(扩展持久化、自动重启),并改 libsclaw 的 `external_cli` 调用层 —— 让每个客户容器通过 `docker exec opencli-runner opencli ...` 调用这个共享的 opencli(因为网站命令的 daemon+扩展必须和 Chromium 同 localhost,opencli 不能跑在客户容器里)。
- **没通** → 按排查表贴结果,我对症处理。
