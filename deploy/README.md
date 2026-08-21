# Libs·Claw 多客户部署指南

为多个客户各自部署一个**独立容器**:独立端口、独立数据、独立配置,互不干扰。镜像只构建一份,所有客户共用;**WebUI 前端在镜像内自动构建**,无需手动 `pnpm build` 再复制。

## 原理

隔离靠两层:
- **Docker Compose 项目名**(`-p libsclaw-<客户名>`):让容器、网络归属不同项目,互不冲突。
- **参数化资源**:容器名 `libsclaw-<客户名>`、端口、数据目录 `customers/<客户名>/data/` 都随客户变化。

每个客户的配置存在 `deploy/customers/<客户名>/`(含 `.env` 和 `data/` 数据目录)。

> ⚠️ `deploy/customers/` 含密钥和客户数据,**不应提交到 git**。已在 `.gitignore` 中。

## 文件说明

| 文件 | 作用 |
|------|------|
| `deploy/customer.sh` | 一键管理脚本(新建/启停/更新/查看) |
| `deploy/docker-compose.multi.yml` | 多客户专用 compose(资源已参数化,含 opencli socat 边车) |
| `deploy/customers/<客户名>/` | 每个客户独立的 `.env` + `data/` |
| `deploy/chrome-cdp/` | 共享浏览器服务栈(Chromium + opencli daemon),见 [OPENCLI-BROWSER.md](./OPENCLI-BROWSER.md) |

## 快速开始

```bash
cd deploy

# 1. 构建共用镜像(首次执行一次;以后代码更新后再执行)
#    多阶段构建会自动 pnpm build 前端并放进 astrbot/dashboard/dist
./customer.sh build

# 2. 新建客户(端口可自动分配,也可手动指定)
./customer.sh new clienta            # 不指定 → 自动找本机空闲端口(从 6185 起),如 6185/6186
./customer.sh new clientb            # 自动顺延到下一个空闲端口,如 6187/6188
./customer.sh new clientc 9999       # 指定 WebUI 端口 9999:脚本会先检查是否被占用
#                                       端口空闲 → 直接使用
#                                       端口被占(其他客户已用 / 本机已监听)→ 报错并提示换端口

# 3. 启动客户
./customer.sh up clienta
./customer.sh up clientb

# 4. 访问 WebUI,在界面里完成业务配置(模型/Key/渠道/密码等)
#    clienta → http://<服务器IP>:6185
#    clientb → http://<服务器IP>:6187
```

> 需要浏览器自动化能力(opencli)时,先按 [OPENCLI-BROWSER.md](./OPENCLI-BROWSER.md) §2 部署共享浏览器服务栈。不用 opencli 也不影响客户容器正常运行(边车只是空转)。

## 日常运维

```bash
./customer.sh list              # 列出所有客户(名字/端口/目录)
./customer.sh ps                # 所有客户容器运行状态
./customer.sh status            # 所有客户容器状态 + opencli doctor 状态
./customer.sh logs clienta      # 看某客户日志
./customer.sh restart clienta   # 重启某客户
./customer.sh down clienta      # 停止某客户(保留数据)
```

## 代码更新后,更新所有客户

```bash
# 服务器:先拉最新代码
git pull origin main

cd deploy
./customer.sh build             # 重建共用镜像(前端自动重新构建)
./customer.sh upgrade-all       # 用新镜像滚动更新所有客户,并逐个验证 opencli
./customer.sh cleanup           # 清理旧镜像和构建缓存(可选,小盘服务器建议)
```

> 若某个客户的 `opencli doctor` 失败,`upgrade-all` 会继续检查完其他客户,最后返回非 0。先看 `./customer.sh status`;若是 `bridge missed` 或 `extension not connected`,通常执行 `./customer.sh recover`。
>
> 也可只更新单个:`./customer.sh upgrade clienta`

## 删除客户

```bash
# 停止但保留数据(以后还能 up 回来)
./customer.sh down clienta

# 彻底删除(容器 + 数据目录 + 配置,不可恢复,会二次确认)
./customer.sh rm clienta
```

## 资源隔离对照

| 资源 | clienta | clientb | 是否隔离 |
|------|---------|---------|---------|
| 容器名 | `libsclaw-clienta` | `libsclaw-clientb` | ✅ |
| WebUI 端口 | 6185 | 6187 | ✅ |
| Napcat 端口 | 6186 | 6188 | ✅ |
| 数据目录 | `customers/clienta/data/` | `customers/clientb/data/` | ✅ |
| 镜像 | `libsclaw:local`(共用) | `libsclaw:local`(共用) | 共用(节省资源) |

## 常见问题

**端口怎么分配?** 不指定端口时,脚本从 6185 起自动找空闲端口(跳过已分配给其他客户的 WebUI/Napcat 端口、以及本机已监听的端口),WebUI 和 Napcat 各分配一个。手动指定(如 `new clientc 9999` 或 `new clientc 9999 9998`)时,脚本会先检查该端口:空闲就直接用,被占用则报错并提示你换一个(或不指定让脚本自动分配)。

**业务配置放哪?** 全部在 WebUI 里填,存进该客户的 `data/` 目录(`customers/<客户名>/data/cmd_config.json` 等)。不要写进 `.env`。

**多客户会抢资源吗?** 每个容器独立进程,内存/CPU 各自占用。客户多时建议用 `docker stats` 监控,评估服务器内存。

**反向代理?** 多客户时建议用 Nginx 按域名/路径分发到不同端口,把 `proxy_pass` 指向对应客户的 WebUI 端口即可。
