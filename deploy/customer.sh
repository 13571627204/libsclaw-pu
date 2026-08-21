#!/usr/bin/env bash
#
# Libs·Claw 多客户部署管理脚本
#
# 每个客户 = 独立容器 + 独立端口 + 独立数据目录,互不干扰。
# 镜像共用一份(只构建一次,WebUI 前端在镜像内自动构建,无需手动打包)。
#
# 用法:
#   ./customer.sh build                        # 构建共用镜像(首次/更新代码后执行一次)
#   ./customer.sh new <客户名> [web端口] [napcat端口]  # 新建一个客户(生成配置,不自动启动)
#   ./customer.sh up <客户名>                   # 启动某客户
#   ./customer.sh down <客户名>                 # 停止并移除某客户容器(保留数据)
#   ./customer.sh restart <客户名>              # 重启某客户
#   ./customer.sh logs <客户名>                 # 查看某客户日志
#   ./customer.sh ps                            # 列出所有客户容器状态
#   ./customer.sh status                        # 列出所有客户状态 + opencli doctor 状态
#   ./customer.sh list                          # 列出所有已配置的客户
#   ./customer.sh upgrade <客户名>              # 用最新镜像更新某客户(保留数据/配置)
#   ./customer.sh upgrade-all                   # 更新所有客户,并逐个验证 opencli
#   ./customer.sh cleanup                       # 清理旧镜像和构建缓存(不删容器/数据)
#   ./customer.sh recover                       # 整机重启/链路断后,按序恢复共享栈+所有客户的 opencli 桥接
#   ./customer.sh rm <客户名>                   # 彻底删除某客户(含数据目录,危险!)
#
# 代码更新后,一键更新所有客户:
#   git pull && cd deploy
#   ./customer.sh build && ./customer.sh upgrade-all && ./customer.sh cleanup
set -euo pipefail

# ===== 路径与常量 =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.multi.yml"
CUSTOMERS_DIR="${SCRIPT_DIR}/customers"
IMAGE_NAME="libsclaw:local"
BASE_PORT=6185          # WebUI 端口从此开始自动分配
SHARED_NETWORK="opencli-shared"   # 共享浏览器服务栈的网络(客户容器经它连 opencli daemon)
PROD_COMPOSE="${SCRIPT_DIR}/chrome-cdp/docker-compose.prod.yml"   # 共享浏览器服务栈

mkdir -p "${CUSTOMERS_DIR}"

# ===== 工具函数 =====
err()  { echo -e "\033[31m[错误]\033[0m $*" >&2; }
info() { echo -e "\033[32m[信息]\033[0m $*"; }
warn() { echo -e "\033[33m[警告]\033[0m $*"; }

# 校验客户名:只允许小写字母、数字、连字符(用于容器名/目录名,必须安全)
validate_name() {
  local name="$1"
  if [[ ! "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    err "客户名 '$name' 非法。只能用小写字母、数字、连字符,且以字母或数字开头。"
    exit 1
  fi
}

customer_dir() { echo "${CUSTOMERS_DIR}/$1"; }
customer_env() { echo "${CUSTOMERS_DIR}/$1/.env"; }

# 确保共享网络存在。客户容器经它连共享 opencli daemon;
# docker-compose.multi.yml 以 external 方式引用,网络缺失会导致启动失败。
ensure_shared_network() {
  if ! docker network inspect "$SHARED_NETWORK" >/dev/null 2>&1; then
    warn "共享网络 $SHARED_NETWORK 不存在,正在创建..."
    docker network create "$SHARED_NETWORK" >/dev/null
    info "已创建共享网络 $SHARED_NETWORK"
  fi
}

# compose 包装:统一带上项目名(-p)和 env-file,确保隔离
dc() {
  local customer="$1"; shift
  local env_file
  env_file="$(customer_env "$customer")"
  if [[ ! -f "$env_file" ]]; then
    err "客户 '$customer' 不存在(找不到 $env_file)。先执行: $0 new $customer"
    exit 1
  fi
  # -p 指定独立项目名,--env-file 注入该客户变量
  docker compose -p "libsclaw-${customer}" --env-file "$env_file" -f "$COMPOSE_FILE" "$@"
}

# 判断端口是否已被占用:① 已分配给其他客户(WEB/NAPCAT 任一) ② 系统已监听。返回 0 表示被占用。
port_in_use() {
  local port="$1"
  # 已分配给其他客户?
  if compgen -G "${CUSTOMERS_DIR}/*/.env" > /dev/null; then
    if grep -hs '^\(WEB_PORT\|NAPCAT_PORT\)=' "${CUSTOMERS_DIR}"/*/.env | cut -d= -f2 | grep -qx "$port"; then
      return 0
    fi
  fi
  # 系统已监听(本机端口被占)?
  if command -v ss >/dev/null && ss -ltn 2>/dev/null | grep -q ":${port} "; then
    return 0
  fi
  return 1
}

# 找一个未被占用的端口(从 $1 起递增)
find_free_port() {
  local port="${1:-$BASE_PORT}"
  while :; do
    port_in_use "$port" || { echo "$port"; return; }
    port=$((port + 1))
  done
}

# 校验并返回一个用户指定的端口;$2 是用途说明(报错用)
check_port_arg() {
  local port="$1" usage="$2"
  if [[ ! "$port" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
    err "${usage}端口 '$port' 非法。请提供 1-65535 之间的数字。"
    exit 1
  fi
  if port_in_use "$port"; then
    err "${usage}端口 $port 已被占用(已分配给其他客户,或本机已有进程监听)。"
    err "请换一个端口,或不指定端口让脚本自动分配。"
    exit 1
  fi
}

container_status() {
  local container="$1"
  docker inspect -f '{{.State.Status}}{{if .State.Health}}/{{.State.Health.Status}}{{end}}' "$container" 2>/dev/null \
    || echo "missing"
}

wait_for_container_running() {
  local container="$1"
  local attempts="${2:-30}"
  local status
  local i
  for ((i = 0; i < attempts; i++)); do
    status="$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || true)"
    [[ "$status" == "true" ]] && return 0
    sleep 1
  done
  return 1
}

opencli_doctor_status() {
  local name="$1"
  local container="libsclaw-${name}"
  local output
  local rc=0

  if ! docker inspect "$container" >/dev/null 2>&1; then
    echo "FAIL: libsclaw container missing"
    return 1
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || true)" != "true" ]]; then
    echo "FAIL: libsclaw container not running"
    return 1
  fi

  output="$(docker exec "$container" opencli doctor 2>&1)" || rc=$?

  if (( rc == 0 )) \
    && grep -q '\[OK\] Extension: connected' <<<"$output" \
    && grep -q '\[OK\] Connectivity: connected' <<<"$output"; then
    echo "OK"
    return 0
  fi

  if grep -q 'Starting daemon' <<<"$output"; then
    echo "FAIL: bridge missed (doctor started local daemon)"
  elif grep -q 'Extension: not connected' <<<"$output"; then
    echo "FAIL: extension not connected"
  elif grep -q 'Connectivity: failed' <<<"$output"; then
    echo "FAIL: connectivity failed"
  elif grep -q 'opencli: command not found' <<<"$output"; then
    echo "FAIL: opencli missing"
  else
    echo "FAIL: doctor rc=${rc}"
  fi
  return 1
}

verify_customer_opencli() {
  local name="$1"
  local result

  info "验证客户 '$name' 的 opencli..."
  if ! wait_for_container_running "libsclaw-${name}" 30; then
    warn "  opencli: FAIL: libsclaw container not running"
    return 1
  fi

  if result="$(opencli_doctor_status "$name")"; then
    info "  opencli: $result"
    return 0
  fi

  warn "  opencli: $result"
  return 1
}

# ===== 命令实现 =====

cmd_build() {
  info "构建共用镜像 ${IMAGE_NAME}(所有客户复用,WebUI 前端在镜像内自动构建)..."
  # 用项目根目录的 Dockerfile 构建,打成共用 tag
  docker build -t "${IMAGE_NAME}" "${PROJECT_ROOT}"
  info "镜像构建完成。"
}

cmd_new() {
  local name="${1:-}"
  local web_port="${2:-}"
  local napcat_port="${3:-}"
  [[ -z "$name" ]] && { err "用法: $0 new <客户名> [web端口] [napcat端口]"; exit 1; }
  validate_name "$name"

  local cdir; cdir="$(customer_dir "$name")"
  if [[ -d "$cdir" ]]; then
    err "客户 '$name' 已存在($cdir)。如需重建请先 $0 rm $name"
    exit 1
  fi

  # 端口处理:
  #   - 指定了端口 → 校验格式与占用,被占用则报错让用户换一个
  #   - 未指定    → 自动从 BASE_PORT 起找空闲端口
  if [[ -n "$web_port" ]]; then
    check_port_arg "$web_port" "WebUI "
    info "客户 '$name' 使用指定 WebUI 端口: $web_port"
  else
    web_port="$(find_free_port "$BASE_PORT")"
    info "未指定端口,为客户 '$name' 自动分配 WebUI 端口: $web_port"
  fi
  if [[ -n "$napcat_port" ]]; then
    [[ "$napcat_port" == "$web_port" ]] && { err "napcat 端口不能与 WebUI 端口相同。"; exit 1; }
    check_port_arg "$napcat_port" "Napcat "
    info "客户 '$name' 使用指定 Napcat 端口: $napcat_port"
  else
    # 从 web_port+1 起找,天然避开刚分配的 web_port
    napcat_port="$(find_free_port "$((web_port + 1))")"
    info "为客户 '$name' 自动分配 Napcat 端口: $napcat_port"
  fi

  mkdir -p "${cdir}/data"

  # 生成该客户的 .env(只含部署隔离项)。
  # 业务配置(模型/各 API Key/渠道/密码…)一律在 Web 界面填,存入同目录的 data/。
  # 切勿把业务配置写进 .env——避免环境变量覆盖 Web 界面保存的配置。
  cat > "${cdir}/.env" <<EOF
# 客户 '${name}' 的部署隔离配置。这几项是容器隔离关键,勿手改。
# 业务配置(模型 / 各 API Key / 渠道 / 密码…)请在 Web 界面填,存入同目录的 data/。
CUSTOMER=${name}
WEB_PORT=${web_port}
NAPCAT_PORT=${napcat_port}
CUSTOMER_DIR=${cdir}
LIBSCLAW_IMAGE=${IMAGE_NAME}
EOF

  info "客户 '$name' 创建完成:"
  echo "  配置目录:    $cdir"
  echo "  WebUI 端口:  $web_port"
  echo "  Napcat 端口: $napcat_port"
  echo "  下一步:      $0 up $name   然后访问 http://<服务器IP>:${web_port}"
}

cmd_up() {
  local name="${1:?用法: $0 up <客户名>}"
  validate_name "$name"
  ensure_shared_network
  info "启动客户 '$name'..."
  dc "$name" up -d
  local port; port="$(grep '^WEB_PORT=' "$(customer_env "$name")" | cut -d= -f2)"
  info "已启动。访问 http://<服务器IP>:${port}"
}

cmd_down() {
  local name="${1:?用法: $0 down <客户名>}"
  validate_name "$name"
  dc "$name" down
  info "客户 '$name' 已停止(数据保留)。"
}

cmd_restart() {
  local name="${1:?用法: $0 restart <客户名>}"
  validate_name "$name"
  dc "$name" restart
  info "客户 '$name' 已重启。"
}

cmd_logs() {
  local name="${1:?用法: $0 logs <客户名>}"
  validate_name "$name"
  dc "$name" logs -f
}

cmd_upgrade() {
  local name="${1:?用法: $0 upgrade <客户名>}"
  validate_name "$name"
  ensure_shared_network
  info "用最新镜像更新客户 '$name'(数据/配置保留)..."
  dc "$name" up -d
  info "客户 '$name' 已更新。"
}

cmd_upgrade_all() {
  local found=0
  local failed=0
  for env in "${CUSTOMERS_DIR}"/*/.env; do
    [[ -e "$env" ]] || continue
    found=1
    local name; name="$(basename "$(dirname "$env")")"
    cmd_upgrade "$name"
    verify_customer_opencli "$name" || failed=1
  done
  [[ "$found" -eq 0 ]] && warn "没有任何客户。"
  if [[ "$found" -eq 1 && "$failed" -eq 1 ]]; then
    warn "有客户 opencli 检查失败。可先运行: $0 status"
    warn "若看到 bridge missed / extension not connected,通常执行: $0 recover"
    return 1
  fi
}

cmd_cleanup() {
  info "清理 Docker 旧镜像和构建缓存(不删除容器/数据)..."

  info "清理前 Docker 空间概览:"
  docker system df

  info "删除悬空镜像(<none>:<none>)..."
  docker image prune -f

  info "删除 BuildKit 构建缓存..."
  docker builder prune -af

  info "清理后 Docker 空间概览:"
  docker system df
  info "清理完成。若仍需细查,可运行: docker system df -v"
}

cmd_ps() {
  info "所有 Libs·Claw 客户容器:"
  docker ps -a --filter "name=libsclaw-" \
    --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

cmd_status() {
  local found=0
  local failed=0

  info "所有客户状态:"
  printf "%-20s %-8s %-24s %-24s %s\n" "客户名" "端口" "libsclaw" "opencli-socat" "opencli"
  for env in "${CUSTOMERS_DIR}"/*/.env; do
    [[ -e "$env" ]] || continue
    found=1
    local name port libsclaw_status socat_status opencli_status
    name="$(basename "$(dirname "$env")")"
    port="$(grep '^WEB_PORT=' "$env" | cut -d= -f2)"
    libsclaw_status="$(container_status "libsclaw-${name}")"
    socat_status="$(container_status "libsclaw-${name}-opencli-socat")"

    if opencli_status="$(opencli_doctor_status "$name")"; then
      :
    else
      failed=1
    fi

    printf "%-20s %-8s %-24s %-24s %s\n" "$name" "$port" "$libsclaw_status" "$socat_status" "$opencli_status"
  done

  if [[ "$found" -eq 0 ]]; then
    warn "没有任何客户。"
    return 0
  fi
  if [[ "$failed" -eq 1 ]]; then
    warn "存在客户 opencli 不可用。若是 bridge missed / extension not connected,通常执行: $0 recover"
    return 1
  fi
}

cmd_list() {
  info "已配置的客户:"
  printf "%-20s %-8s %-8s %s\n" "客户名" "WebUI" "Napcat" "配置目录"
  for env in "${CUSTOMERS_DIR}"/*/.env; do
    [[ -e "$env" ]] || { echo "  (无)"; break; }
    local name web_port napcat_port
    name="$(basename "$(dirname "$env")")"
    web_port="$(grep '^WEB_PORT=' "$env" | cut -d= -f2)"
    napcat_port="$(grep '^NAPCAT_PORT=' "$env" | cut -d= -f2)"
    printf "%-20s %-8s %-8s %s\n" "$name" "$web_port" "$napcat_port" "$(dirname "$env")"
  done
}

cmd_rm() {
  local name="${1:?用法: $0 rm <客户名>}"
  validate_name "$name"
  warn "即将彻底删除客户 '$name':容器 + 数据目录 + 配置,不可恢复!"
  read -r -p "确认删除请输入客户名 '$name': " confirm
  [[ "$confirm" == "$name" ]] || { err "未确认,已取消。"; exit 1; }
  dc "$name" down -v 2>/dev/null || true
  rm -rf "$(customer_dir "$name")"
  info "客户 '$name' 已彻底删除。"
}

# 整机重启 / 链路断后的一键恢复。
# 按正确顺序重启:network_mode 共享网络的容器,必须在其"宿主容器"网络就绪后才重启,
# 否则会连到已销毁的旧网络命名空间,导致 opencli 桥接断。
cmd_recover() {
  ensure_shared_network

  info "[1/2] 恢复共享浏览器服务栈..."
  if [[ -f "$PROD_COMPOSE" ]]; then
    docker compose -f "$PROD_COMPOSE" up -d          # 确保三个容器都在
    # 关键顺序:先重启 chromium(网络命名空间宿主),再重启共享它网络的 daemon/proxy
    docker restart opencli-chromium >/dev/null
    sleep 5
    docker restart opencli-daemon opencli-daemon-proxy >/dev/null 2>&1 || true
    info "  共享栈已恢复(chromium → daemon/proxy)"
  else
    warn "  找不到共享栈 compose: $PROD_COMPOSE,跳过"
  fi

  info "[2/2] 恢复所有客户容器..."
  local found=0
  for env in "${CUSTOMERS_DIR}"/*/.env; do
    [[ -e "$env" ]] || continue
    found=1
    local name; name="$(basename "$(dirname "$env")")"
    # 关键顺序:先重启 libsclaw(网络宿主),再重启共享它网络的 socat 边车
    docker restart "libsclaw-${name}" >/dev/null 2>&1 || true
    sleep 3
    docker restart "libsclaw-${name}-opencli-socat" >/dev/null 2>&1 || true
    info "  客户 '$name' 已恢复(libsclaw → socat 边车)"
  done
  [[ "$found" -eq 0 ]] && warn "  没有任何客户。"

  info "恢复完成。验证某客户: docker exec -it libsclaw-<客户> opencli doctor"
}

# ===== 入口 =====
case "${1:-}" in
  build)        cmd_build ;;
  new)          shift; cmd_new "$@" ;;
  up)           shift; cmd_up "$@" ;;
  down)         shift; cmd_down "$@" ;;
  restart)      shift; cmd_restart "$@" ;;
  logs)         shift; cmd_logs "$@" ;;
  upgrade)      shift; cmd_upgrade "$@" ;;
  upgrade-all)  cmd_upgrade_all ;;
  cleanup)      cmd_cleanup ;;
  recover)      cmd_recover ;;
  ps)           cmd_ps ;;
  status)       cmd_status ;;
  list)         cmd_list ;;
  rm)           shift; cmd_rm "$@" ;;
  *)
    sed -n '2,/^set -euo pipefail/p' "$0" \
      | sed '/^set -euo pipefail/d; s/^# \{0,1\}//'
    exit 1
    ;;
esac
