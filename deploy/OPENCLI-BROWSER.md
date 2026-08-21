# Libs·Claw 多客户 + 共享浏览器(OpenCLI)生产部署

本文整合完整生产架构:**多个客户容器各自内置 opencli,通过 socat 桥接共用一个浏览器服务**(Chromium + 扩展 + 登录态),让各客户的 Agent 都能用 opencli 操作网站。

> 探索过程与踩坑见 [chrome-cdp/README.md](./chrome-cdp/README.md);多客户隔离基础见 [README.md](./README.md)。

---

## 1. 架构总览

```
┌─ 共享浏览器服务栈(全局一份,常驻)─────────────────────┐
│  opencli-chromium    Chromium + 扩展(自动加载) + 登录态    │
│  opencli-daemon      opencli 1.8.3 常驻 daemon            │
│                      (network_mode: service:chromium)     │
│  opencli-daemon-proxy socat,把 daemon 暴露到 :19826       │
│  网络: opencli-shared (external)                          │
└──────────────────────────▲────────────────────────────┘
                          │ opencli-chromium:19826
        ┌─────────────────┼─────────────────┐
┌───────┴────────┐  ┌─────┴──────────┐
│ libsclaw-admin │  │ libsclaw-bob   │   ← customer.sh 生成
│  (端口 6185)    │  │  (端口 6187)    │
│  +socat 边车    │  │  +socat 边车    │   socat: 本地19825 → chromium:19826
│  opencli 1.8.3 │  │  opencli 1.8.3 │   CLI 默认连本机,无感命中边车
└────────────────┘  └────────────────┘
```

**关键设计:**
- **socat 透明桥接**:边车容器占据客户容器的 `127.0.0.1:19825`,opencli CLI 默认连本机即命中,经 socat → 共享 daemon。**调用方代码无需改动**。
- **版本统一 1.8.3**:客户内置 opencli、共享 daemon 都是 1.8.3,扩展 v1.0.19(兼容 >=1.7.0)。避免跨版本触发 CLI 重启 daemon。
- **登录态共享**:所有客户共用同一个 Chromium、同一批账号 Cookie(已确认接受)。

---

## 2. 首次部署

### 2.1 创建共享网络

```bash
docker network create opencli-shared
```

### 2.2 准备并启动共享浏览器服务栈

```bash
cd deploy/chrome-cdp

# 下载扩展(v1.8.3 捆绑 v1.0.19),解压到 chromium-config
mkdir -p chromium-config/opencli-extension
curl -L -o /tmp/ext.zip \
  https://github.com/jackwener/OpenCLI/releases/download/v1.8.3/opencli-extension-v1.0.19.zip
unzip -o /tmp/ext.zip -d chromium-config/opencli-extension
# 确认 manifest.json 在 chromium-config/opencli-extension/ 根层
ls chromium-config/opencli-extension/manifest.json

# 启动共享栈(构建 daemon 镜像)
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps   # chromium / daemon / proxy 三个 Up
```

### 2.3 人工登录目标网站(一次性)

```bash
# 本地电脑开 SSH 隧道
ssh -L 3000:127.0.0.1:3000 -L 3001:127.0.0.1:3001 root@服务器IP
```

本地浏览器访问 `https://localhost:3001`(忽略证书警告;若 WebSocket 仍断开,试 `http://localhost:3000`)→ 进入容器 Chromium 桌面:
1. `chrome://extensions` 确认 OpenCLI 扩展**已启用**(命令行已自动加载)
2. 打开并**登录目标网站**(如 bilibili.com),登录态持久化在 `chromium-config` 卷

### 2.4 验证共享 daemon

```bash
docker exec opencli-daemon bash -c '
node -e "fetch(\"http://127.0.0.1:19825/status\",{headers:{\"X-OpenCLI\":\"1\"}}).then(r=>r.text()).then(console.log)"'
# 期望:{"ok":true,...,"extensionConnected":true,...}
```

### 2.5 构建 libsclaw 镜像并创建客户

```bash
cd deploy
./customer.sh build               # 内置 opencli 1.8.3,WebUI 前端在镜像内自动构建
./customer.sh new admin           # 不指定端口 → 自动找本机空闲端口(从 6185 起)
#                                   指定端口: ./customer.sh new admin 8080
#                                     端口空闲 → 直接用;被占用 → 报错并提示换端口
./customer.sh up admin            # 起 libsclaw + socat 边车

# 验证客户容器内置 opencli 连到共享浏览器
docker exec -it libsclaw-admin opencli doctor
# 期望:Daemon OK + Extension: connected (v1.0.19) + Connectivity: connected
```

---

## 3. 日常运维

```bash
cd deploy
# 客户管理(详见 deploy/README.md)
./customer.sh new <客户>          # 新建,自动分配空闲端口(带 opencli 桥接)
./customer.sh new <客户> <端口>   # 新建并指定端口;端口被占用会报错提示换端口
./customer.sh up <客户>
./customer.sh list                # 列出所有客户(名字/端口/目录)
./customer.sh ps                  # 所有客户容器状态
./customer.sh status              # 所有客户容器状态 + opencli doctor 状态

# 共享浏览器服务栈
cd deploy/chrome-cdp
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f opencli-daemon
```

---

## 4. 代码更新与重新构建镜像

> **核心原则:所有 Libs·Claw 代码(Python / 前端)都经 `Dockerfile` 烤进镜像(前端在镜像构建时自动 pnpm build),容器跑的是镜像里的 `/LibsClaw`,不是宿主机源码。只要改了代码,就必须先 `./customer.sh build` 重建镜像,再 `upgrade-all`;`upgrade-all` 用的是已存在的 `libsclaw:local` 镜像,永远不会重建镜像。**
>
> 唯一不用 build 的改动:只动了挂载进容器的文件——某客户的 `data/` 目录内容或 `.env`,这类改完 `./customer.sh restart <客户>` 即生效。

### 4.1 改了业务代码(Python / 前端)

代码经 Dockerfile 进镜像,**必须先 build 再 upgrade-all**,最后 cleanup 清理旧镜像和构建缓存(数据/配置保留):

```bash
cd /opt/libsclaw
git pull origin main
cd deploy
./customer.sh build            # 必须:把最新代码 + 自动构建的 WebUI 烤进 libsclaw:local 镜像
./customer.sh upgrade-all       # 再用新镜像滚动更新所有客户,并逐个验证 opencli
./customer.sh cleanup           # 清理旧镜像和构建缓存,不删除容器/数据
```

> 改前端(dashboard/)也一样:镜像的多阶段构建会自动 `pnpm build` 并把产物放进
> `astrbot/dashboard/dist`,**不再需要手动打包前端再复制**。
> ⚠️ `upgrade-all` 只使用现有镜像做滚动更新并运行 `opencli doctor`,**不会**重建镜像;漏了 `build` 就是拿旧镜像滚动,代码不更新。
> `cleanup` 只执行悬空镜像和 BuildKit 构建缓存清理,用于避免小磁盘服务器因多次 build 堆积 `<none>:<none>` 镜像;它不会带 `--volumes`,不会删除客户数据。
> 若某个客户的 `opencli doctor` 失败,`upgrade-all` 会继续检查完其他客户,最后返回非 0。先看 `./customer.sh status`;若是 `bridge missed` 或 `extension not connected`,通常执行 `./customer.sh recover`。

### 4.2 改了 Dockerfile(依赖、Node 版本、内置 opencli 等)

改了 `Dockerfile` 后**必须显式重建共享镜像**,再更新客户:

```bash
cd /opt/libsclaw
git pull origin main
cd deploy

# 1. 重建 libsclaw 共享镜像(所有客户复用同一个 libsclaw:local)
./customer.sh build
#   若改动没生效(命中缓存),强制全量重建:
#   docker build --no-cache -t libsclaw:local /opt/libsclaw

# 2. 用新镜像滚动更新所有客户
./customer.sh upgrade-all

# 3. 清理旧镜像和构建缓存,避免 Docker 占满系统盘
./customer.sh cleanup
```

### 4.3 改了共享浏览器栈(Dockerfile.daemon / prod.yml)

共享栈是独立镜像,改了它要单独重建:

```bash
cd /opt/libsclaw/deploy/chrome-cdp
docker compose -f docker-compose.prod.yml up -d --build   # 重建 daemon 镜像并重启共享栈
# 重启后按需恢复链路(见 §6):
cd /opt/libsclaw/deploy && ./customer.sh recover
```

> ⚠️ 重建共享栈会重启 chromium → 扩展与 daemon 链路会断,重建后务必跑 `./customer.sh recover`。

---

## 5. 删除客户

```bash
cd deploy

# 停止但保留数据(以后还能 ./customer.sh up <客户> 恢复)
./customer.sh down <客户>

# 彻底删除:容器 + socat 边车 + 数据目录 + 配置,不可恢复(会二次确认)
./customer.sh rm <客户>
```

`rm` 做的事:
1. `compose down -v` —— 删除该客户的 libsclaw 容器、socat 边车
2. 删除 `deploy/customers/<客户>/` 配置目录(含 `.env` 和 `data/` 数据)
3. 要求输入客户名二次确认,防误删

> 删除某个客户**不影响**共享浏览器栈和其他客户。共享栈是全局的,只有所有客户都不需要浏览器能力时才考虑停它。
> 删除后该客户占用的端口会被释放,`./customer.sh new` 下次可重新分配。

---

## 6. ⚠️ 重启陷阱(最重要的运维知识)

**`network_mode` 共享网络命名空间的容器,在其"宿主容器"重启后必须跟着重启。**

### 6.1 共享栈内部

`opencli-daemon` 和 `opencli-daemon-proxy` 都 `network_mode: service:chromium`。**重启 chromium 会销毁重建其网络命名空间**,导致 daemon/proxy 连到旧命名空间 → 扩展断连。

```bash
# 正确的重启共享栈方式:整栈一起重启
cd deploy/chrome-cdp
docker compose -f docker-compose.prod.yml restart
# 或只重启 chromium 后,必须重启依赖它网络的容器:
docker restart opencli-chromium && sleep 5 \
  && docker restart opencli-daemon opencli-daemon-proxy
```

### 6.2 客户容器

`libsclaw-<客户>-opencli-socat` 边车 `network_mode: service:libsclaw`。**重启客户的 libsclaw 容器后,必须重启其 socat 边车**,否则 opencli 桥接断:

```bash
docker restart libsclaw-admin && sleep 3 \
  && docker restart libsclaw-admin-opencli-socat
```

> `./customer.sh restart` / `up` 走 compose,会正确处理两个容器,优先用脚本而非裸 `docker restart`。

### 6.3 扩展掉线的恢复

若 `opencli doctor` 报 `Extension: not connected`:
1. **优先跑一键恢复**: `cd /opt/libsclaw/deploy && ./customer.sh recover`
2. 恢复后验证客户容器: `docker exec -it libsclaw-<客户> opencli doctor`
3. 仍不行 → 进 VNC `chrome://extensions` 确认扩展启用;必要时重启整个共享栈

> **重要信号**:如果在客户容器里执行 `opencli doctor` 时先出现
> `⏳ Starting daemon...`,通常说明客户容器没有命中 socat 边车占住的
> `127.0.0.1:19825`,而是在客户容器内部启动了一个"错误位置"的本地 daemon。
> 这种情况下,即使 VNC 里的扩展显示 connected,客户容器也会报
> `Extension: not connected`;先跑 `./customer.sh recover` 让客户容器与
> `libsclaw-<客户>-opencli-socat` 按正确顺序重启。

### 6.4 服务器整机重启 / 大面积链路断 —— 一键恢复 ⭐

**问题**:整机 reboot 后,所有容器虽有 `restart: unless-stopped` 会自动拉起,但
`network_mode: service:X` 的依赖容器(daemon、proxy、各客户 socat 边车)**不保证**
在其"宿主容器"网络就绪后才启动(`depends_on` 只在 `up` 时生效,开机恢复时不生效)。
结果:它们可能连到已销毁的旧网络命名空间,opencli 桥接全断,且**不会自愈**。

**解决**:整机重启后跑一键恢复,它按正确顺序重启整条链路:

```bash
cd /opt/libsclaw/deploy
./customer.sh recover
```

`recover` 做的事(顺序很关键):
1. 确保共享网络存在
2. 共享栈:`prod.yml up -d` → 重启 `opencli-chromium` → sleep 5 → 重启 `opencli-daemon` + `opencli-daemon-proxy`
3. 每个客户:重启 `libsclaw-<客户>` → sleep 3 → 重启 `libsclaw-<客户>-opencli-socat`

恢复后验证任一客户:

```bash
docker exec -it libsclaw-admin opencli doctor    # 期望 Extension: connected
```

> **只重启了 opencli daemon**(没动 chromium)的情况:daemon 重启后扩展会自动重连
> (扩展常驻在 chromium 里,daemon 起来后握手)。一般无需额外操作;若 doctor 仍报未连,
> 跑 `./customer.sh recover` 即可。
>
> **建议**:把 `./customer.sh recover` 加入服务器开机自启(systemd / crontab @reboot),
> 实现整机重启后自动恢复 opencli 链路。

---

## 7. 安全

- 网页VNC(3001)**只绑 127.0.0.1**,仅经 SSH 隧道访问,不暴露公网。
- daemon(19825/19826)只在 docker 内网,无 `-p` 公网映射。
- **CDP/daemon 端口 = 完全控制浏览器**,绝不可暴露公网。

---

## 8. 故障排查

### 8.1 `opencli doctor` 报 `Extension: not connected`

见 [§6 重启陷阱](#6-️-重启陷阱最重要的运维知识)。最常见原因是 chromium 或客户 libsclaw 容器重启后,共享网络的依赖容器没跟着重启。先试 `./customer.sh recover`。

如果 VNC `https://localhost:3001` 里看到 OpenCLI 扩展是 connected,但客户容器内仍报未连接,不要只看扩展状态。VNC 只能证明"Chromium 内扩展 ↔ 共享 daemon"可能是通的,不能证明"客户容器本机 `127.0.0.1:19825` ↔ socat ↔ 共享 daemon"也通。

按三段链路排查(`<客户>` 换成实际客户名):

```bash
# 1. 共享 daemon 自己是否看到扩展
docker exec opencli-daemon sh -lc 'curl -sS -H "X-OpenCLI: 1" http://127.0.0.1:19825/status'

# 2. 客户容器是否能访问共享 proxy
docker exec libsclaw-<客户> sh -lc 'curl -sS -H "X-OpenCLI: 1" http://opencli-chromium:19826/status'

# 3. 客户本机 19825 是否被 socat 正确桥接
docker exec libsclaw-<客户> sh -lc 'curl -sS -H "X-OpenCLI: 1" http://127.0.0.1:19825/status'
```

结果判读:
- 第 1 步失败:共享 daemon/扩展链路有问题,按 §6.1 恢复共享栈。
- 第 1 步成功、第 2 步失败:客户容器没连上 `opencli-shared` 网络,或 `opencli-daemon-proxy` 异常。
- 第 2 步成功、第 3 步失败:客户 socat 边车没在当前 libsclaw 网络命名空间里监听,跑 `./customer.sh recover`。
- `opencli doctor` 输出 `⏳ Starting daemon...`:客户 CLI 没命中 socat,优先按上一条处理。

### 8.2 `https://localhost:3001` 打开后黑屏或 WebSocket 断开

共享栈的 Chromium 镜像必须使用 `lscr.io/linuxserver/chromium:kasm`。不要用 `latest`:该标签可能切到 Selkies/Wayland 图形栈,在部分服务器/VNC 环境里会出现只剩黑屏、看不到 Chrome,或页面提示 `WebSocket disconnected. Attempting to reconnect...`。

本地 SSH 隧道也要同时转发 `3000` 和 `3001`:

```bash
ssh -L 3000:127.0.0.1:3000 -L 3001:127.0.0.1:3001 root@服务器IP
```

修复后在服务器执行:

```bash
cd /opt/libsclaw/deploy/chrome-cdp
docker compose -f docker-compose.prod.yml pull chromium
docker compose -f docker-compose.prod.yml up -d --force-recreate chromium
sleep 5
docker restart opencli-daemon opencli-daemon-proxy
docker inspect opencli-chromium --format '{{.Config.Image}}'
```

最后一行应输出 `lscr.io/linuxserver/chromium:kasm`。如果 `https://localhost:3001` 仍断开,试 `http://localhost:3000`;若 3000 可用,说明 HTTPS/WebSocket 层仍受证书或代理影响,先用 3000 完成人工登录。

### 8.3 客户容器内 `opencli: command not found`

libsclaw 镜像没装上 opencli。opencli 在 `Dockerfile` 里无条件全局安装(`npm install -g @jackwener/opencli@1.8.3`);确认镜像重建成功后 `./customer.sh upgrade <客户>`。

### 8.4 服务器磁盘被 Docker 占满

多次执行 `./customer.sh build` 后,旧的 `libsclaw:local` 镜像会变成 `<none>:<none>` 悬空镜像,BuildKit 也会保留构建缓存。小盘服务器(如 40G 左右)应在更新成功后清理:

```bash
cd /opt/libsclaw/deploy
./customer.sh cleanup
df -hT
docker system df -v
```

若需要先确认占用来源:

```bash
docker system df -v
sudo du -xh -d1 /var/lib/docker 2>/dev/null | sort -h
docker images -f dangling=true --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}\t{{.Size}}'
docker builder du 2>/dev/null || true
```

不要用 `docker system prune -a --volumes` 做日常清理;`--volumes` 有删除数据卷的风险。`./customer.sh cleanup` 不会删除容器和数据。

---

## 9. 已知约束

| 约束 | 说明 |
|------|------|
| 浏览器命令只能走扩展模式 | CDP 模式仅对 Electron 桌面应用生效,网站命令(bilibili 等)只认 daemon+扩展。详见 chrome-cdp/README.md |
| 登录态全客户共享 | 共用一个 Chromium,所有客户 Agent 操作同一批账号 |
| 共享栈是单点 | 所有客户依赖这一个浏览器服务;它挂了所有客户的浏览器能力都受影响 |
| 扩展命令行加载 | 靠 `--load-extension`;Chromium 重启后由命令行参数自动重载,但 daemon 需按 §6 重启重连 |
