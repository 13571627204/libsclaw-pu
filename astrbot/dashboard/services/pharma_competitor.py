"""竞品内容扫描：三档真实数据采集（轻量 URL 抓取 / 标准 opencli / 深度 TikHub）。

本模块只负责采集与结构化，不调用生成模型，也不编造数据：
所有条目都来自实际 HTTP 响应或 opencli 输出，并保留来源渠道与原始链接。
"""

from __future__ import annotations

import asyncio
import contextlib
import html
import json
import os
import re
import shutil
import time
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import httpx

COMPETITOR_PLATFORMS = {
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "zhihu": "知乎",
    "ecommerce": "电商",
}
COMPETITOR_MODES = {
    "light": "轻量（公开页面抓取）",
    "standard": "标准（opencli 采集）",
    "deep": "深度（TikHub API）",
}
COMPETITOR_ITEM_LIMIT = 1500
# 搜索翻页上限：单页约 10~20 条，5 页足够覆盖每词最多 50 条
TIKHUB_SEARCH_MAX_PAGES = 5
# api.tikhub.dev 为国内可直连域名，优先使用；api.tikhub.io 在国内常连接超时或响应体卡住
TIKHUB_FALLBACK_BASE_URLS = ("https://api.tikhub.dev", "https://api.tikhub.io")
# 单次请求（含读取响应体）的总时限，超时即切换线路，避免页面长时间转圈
# TikHub 官方说明上游耗时 30~60s（小红书搜索常超过 40s），单次时限需覆盖该区间
TIKHUB_ATTEMPT_TIMEOUT = 58
# 单个接口跨所有线路的总时限，防止逐条线路超时累加导致整体卡住
TIKHUB_REQUEST_BUDGET = 110
_TEXT_LIMIT = 600

_TITLE_KEYS = ("title", "display_title")
_BODY_KEYS = ("desc", "content", "excerpt", "text", "word")
_LIKE_KEYS = ("digg_count", "liked_count", "like_count", "voteup_count", "likes")
_COMMENT_KEYS = ("comment_count", "comments_count", "comment_num", "comments")
_SHARE_KEYS = ("share_count", "shared_count", "shares")
_COLLECT_KEYS = ("collect_count", "collected_count", "collects")
_HEAT_KEYS = ("hot_value", "play_count", "view_count")
_PRICE_KEYS = ("price", "min_price", "sale_price", "final_price")
_ID_KEYS = ("aweme_id", "note_id", "cid", "item_id", "id")
_STAT_CONTAINERS = ("statistics", "interact_info", "stats", "stat")
_PRICE_RE = re.compile(r"[¥￥]\s*(\d{1,5}(?:\.\d{1,2})?)")
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


class CompetitorCollectError(Exception):
    """采集失败（可安全展示给用户的中文信息）。"""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = html.unescape(_TAG_RE.sub("", value))
    return _SPACE_RE.sub(" ", text).strip()


def _parse_count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("+", "")
        multiplier = 1
        if text.endswith("万") or text.lower().endswith("w"):
            multiplier, text = 10000, text[:-1]
        elif text.endswith("亿"):
            multiplier, text = 100000000, text[:-1]
        try:
            return int(float(text) * multiplier)
        except ValueError:
            return None
    return None


def _parse_price(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value) if 0 < value < 100000 else None
    if isinstance(value, str):
        match = re.search(r"\d+(?:\.\d+)?", value)
        if match:
            number = float(match.group(0))
            return number if 0 < number < 100000 else None
    return None


def _first_count(sources: list[dict[str, Any]], keys: tuple[str, ...]) -> int | None:
    for source in sources:
        for key in keys:
            if key in source:
                number = _parse_count(source[key])
                if number is not None:
                    return number
    return None


def _author_of(node: dict[str, Any]) -> str:
    for key in ("author", "user", "user_info"):
        author = node.get(key)
        if isinstance(author, dict):
            name = author.get("nickname") or author.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()[:40]
        elif isinstance(author, str) and author.strip():
            return author.strip()[:40]
    return ""


_ZHIHU_API_RE = re.compile(
    r"^https?://api\.zhihu\.com/(answers|articles|questions|zvideos|pins)/(\d+)"
)
_ZHIHU_WEB_PATHS = {
    "answers": "https://www.zhihu.com/answer/{}",
    "articles": "https://zhuanlan.zhihu.com/p/{}",
    "questions": "https://www.zhihu.com/question/{}",
    "zvideos": "https://www.zhihu.com/zvideo/{}",
    "pins": "https://www.zhihu.com/pin/{}",
}


def zhihu_web_url(url: str, question_url: str = "") -> str:
    """把知乎 API 链接（api.zhihu.com，需登录）转换为可直接打开的网页链接。"""
    match = _ZHIHU_API_RE.match(url)
    if not match:
        return url
    kind, item_id = match.groups()
    if kind == "answers":
        question = _ZHIHU_API_RE.match(question_url)
        if question and question.group(1) == "questions":
            return (
                f"https://www.zhihu.com/question/{question.group(2)}/answer/{item_id}"
            )
    return _ZHIHU_WEB_PATHS[kind].format(item_id)


def _xsec_token_of(node: dict[str, Any]) -> str:
    value = node.get("xsec_token")
    return value.strip() if isinstance(value, str) else ""


def _xhs_note_url(ref_id: str, xsec_token: str, keyword: str) -> str:
    """小红书网页端必须携带 xsec_token，否则跳转 404「当前笔记暂时无法浏览」。"""
    if xsec_token:
        query = urlencode({"xsec_token": xsec_token, "xsec_source": "pc_search"})
        return f"https://www.xiaohongshu.com/explore/{ref_id}?{query}"
    # 无 token 时退回关键词搜索页，保证链接可打开
    if keyword:
        return f"https://www.xiaohongshu.com/search_result?{urlencode({'keyword': keyword})}"
    return ""


def _canonical_url(
    platform: str,
    ref_id: str,
    node: dict[str, Any],
    *,
    xsec_token: str = "",
    keyword: str = "",
) -> str:
    for key in ("share_url", "url", "link"):
        value = node.get(key)
        if isinstance(value, str) and value.startswith("http"):
            question = node.get("question")
            question_url = question.get("url", "") if isinstance(question, dict) else ""
            return zhihu_web_url(value, str(question_url))[:500]
    if ref_id and platform == "douyin" and "aweme_id" in node:
        return f"https://www.douyin.com/video/{ref_id}"
    if ref_id and platform == "xiaohongshu" and "cid" not in node:
        return _xhs_note_url(ref_id, xsec_token, keyword)[:500]
    return ""


def _node_to_item(
    node: dict[str, Any],
    *,
    platform: str,
    kind: str,
    keyword: str,
    channel: str,
    parent_id: str,
    parent_ref: str,
    xsec_token: str = "",
) -> dict[str, Any] | None:
    title = ""
    for key in _TITLE_KEYS:
        title = _clean_text(node.get(key))
        if title:
            break
    if not title and isinstance(node.get("question"), dict):
        title = _clean_text(
            node["question"].get("name") or node["question"].get("title")
        )
    body = ""
    for key in _BODY_KEYS:
        body = _clean_text(node.get(key))
        if body:
            break
    text = body or title
    if len(text) < 4:
        return None
    stat_sources = [node] + [
        node[key] for key in _STAT_CONTAINERS if isinstance(node.get(key), dict)
    ]
    likes = _first_count(stat_sources, _LIKE_KEYS)
    comments = _first_count(stat_sources, _COMMENT_KEYS)
    heat = _first_count(stat_sources, _HEAT_KEYS)
    price = None
    for key in _PRICE_KEYS:
        if key in node:
            price = _parse_price(node[key])
            if price is not None:
                break
    ref_id = ""
    for key in _ID_KEYS:
        value = node.get(key)
        if isinstance(value, str | int) and not isinstance(value, bool) and str(value):
            ref_id = str(value)[:80]
            break
    ref_id = ref_id or parent_id
    url = _canonical_url(
        platform,
        ref_id,
        node,
        xsec_token=_xsec_token_of(node) or xsec_token,
        keyword=keyword,
    )
    if kind == "hot":
        if heat is None and likes is None:
            return None
    elif likes is None and comments is None and price is None and not url:
        return None
    return {
        "item_id": "",
        "platform": platform,
        "kind": kind,
        "channel": channel,
        "keyword": keyword[:40],
        "title": title[:120],
        "text": text[:_TEXT_LIMIT],
        "author": _author_of(node),
        "likes": likes,
        "comments": comments,
        "shares": _first_count(stat_sources, _SHARE_KEYS),
        "collects": _first_count(stat_sources, _COLLECT_KEYS),
        "heat": heat,
        "price": price,
        "url": url,
        "ref_id": ref_id,
        "parent_ref": parent_ref,
        "collected_at": _now(),
    }


def extract_items(
    payload: Any,
    *,
    platform: str,
    kind: str,
    keyword: str,
    channel: str,
    parent_ref: str = "",
    limit: int = 60,
) -> list[dict[str, Any]]:
    """从任意结构的 JSON 中抽取「最外层」的内容条目，避免把作者/音乐等子对象当成内容。"""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    def walk(node: Any, parent_id: str, depth: int, token: str = "") -> None:
        if len(items) >= limit or depth > 8:
            return
        if isinstance(node, list):
            for child in node:
                walk(child, parent_id, depth + 1, token)
            return
        if not isinstance(node, dict):
            return
        # 小红书搜索结果的 xsec_token 常挂在外层 item 上，需向下传递给笔记节点
        token = _xsec_token_of(node) or token
        item = _node_to_item(
            node,
            platform=platform,
            kind=kind,
            keyword=keyword,
            channel=channel,
            parent_id=parent_id,
            parent_ref=parent_ref,
            xsec_token=token,
        )
        if item is not None:
            key = item["text"][:80]
            if key not in seen:
                seen.add(key)
                items.append(item)
            return
        own_id = next(
            (str(node[k]) for k in _ID_KEYS if isinstance(node.get(k), str | int)),
            parent_id,
        )
        for child in node.values():
            if isinstance(child, dict | list):
                walk(child, own_id, depth + 1, token)

    walk(payload, "", 0)
    return items


# ---------------------------------------------------------------- TikHub（深度）


def _dotenv_value(name: str) -> str:
    from astrbot.core.utils.astrbot_path import (
        get_astrbot_data_path,
        get_astrbot_root,
    )

    for folder in (get_astrbot_root(), get_astrbot_data_path()):
        path = os.path.join(folder, ".env")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8-sig") as file:
            for line in file:
                key, sep, value = line.strip().partition("=")
                if sep and key.strip().removeprefix("export ").strip() == name:
                    return value.strip().strip("\"'").strip()
    return ""


def _tikhub_setting(*names: str) -> str:
    """按环境变量优先、其次项目根目录/data 下 .env 的顺序读取 TikHub 配置。"""
    for name in names:
        if value := os.environ.get(name, "").strip():
            return value
    for name in names:
        if value := _dotenv_value(name):
            return value
    return ""


def tikhub_api_key() -> str:
    return _tikhub_setting("TIKHUB_API_KEY", "TIKHUB_XHS_KEY")


def tikhub_proxy() -> str | None:
    return (
        _tikhub_setting(
            "TIKHUB_PROXY",
            "HTTPS_PROXY",
            "https_proxy",
            "ALL_PROXY",
            "all_proxy",
            "HTTP_PROXY",
            "http_proxy",
        )
        or None
    )


def tikhub_configured() -> bool:
    return bool(tikhub_api_key())


def capabilities() -> dict[str, Any]:
    return {
        "platforms": COMPETITOR_PLATFORMS,
        "modes": COMPETITOR_MODES,
        "tikhub_configured": tikhub_configured(),
        "opencli_available": opencli_command() is not None,
    }


OPENCLI_PACKAGE = "@jackwener/opencli@1.8.3"


def opencli_command() -> list[str] | None:
    """定位 opencli：PATH → npm 全局目录 → npx 按需拉取（与 Dockerfile 同版本）。

    后端进程的 PATH 可能不含 npm 全局目录（Windows 常见），只装了浏览器扩展
    而没有 CLI 时，用 npx 拉起 CLI，由 CLI 自动启动 daemon 与扩展连接。
    """
    executable = os.environ.get("OPENCLI_BIN") or shutil.which("opencli")
    if executable:
        return [executable]
    candidates = []
    if os.environ.get("APPDATA"):
        candidates.append(os.path.join(os.environ["APPDATA"], "npm", "opencli.cmd"))
    candidates += ["/usr/local/bin/opencli", "/usr/bin/opencli"]
    for path in candidates:
        if os.path.isfile(path):
            return [path]
    npx = shutil.which("npx")
    return [npx, "-y", OPENCLI_PACKAGE] if npx else None


_Route = tuple[str, httpx.AsyncClient, str, str | None]


async def _public_dns_resolve(client: httpx.AsyncClient, host: str) -> list[str]:
    """绕过系统 DNS 解析真实 IP。

    Clash/mihomo 的 TUN + fake-ip 模式会把系统 DNS 劫持为 198.18.x.x 假地址，
    代理软件未运行或重启时直连也会失败，此时用公共 DNS 拿到真实地址兜底。
    """
    try:
        response = await client.get(
            "https://223.5.5.5/resolve", params={"name": host, "type": 1}, timeout=6
        )
        ips = [
            a["data"] for a in response.json().get("Answer", []) if a.get("type") == 1
        ]
        if ips:
            return ips
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    try:
        response = await client.get(
            "http://119.29.29.29/d", params={"dn": host}, timeout=6
        )
        return [ip for ip in response.text.strip().split(";") if ip]
    except httpx.HTTPError:
        return []


class _TikHubClient:
    def __init__(
        self, clients: list[tuple[str, httpx.AsyncClient]], proxy: str | None
    ) -> None:
        self.proxy = proxy
        configured = (_tikhub_setting("TIKHUB_BASE_URL") or "").rstrip("/")
        self.base_urls = list(
            dict.fromkeys(
                [url for url in (configured, *TIKHUB_FALLBACK_BASE_URLS) if url]
            )
        )
        self.direct = clients[-1][1]
        # 线路 = (连接方式, 地址, SNI 主机名)；配置的代理不可用时自动回退直连，
        # 直连也失败时再用公共 DNS 解析的真实 IP 兜底；成功线路会被记住优先使用
        self.routes: list[_Route] = [
            (name, client, url, None)
            for name, client in clients
            for url in self.base_urls
        ]
        self.route = self.routes[0]
        self.dead: set[_Route] = set()
        self.slow: set[_Route] = set()
        self.semaphore = asyncio.Semaphore(4)
        self.dns_lock = asyncio.Lock()
        self.dns_resolved = False
        self.reachable = False

    async def _add_dns_routes(self) -> list[_Route]:
        async with self.dns_lock:
            if self.dns_resolved:
                return [r for r in self.routes if r[0] == "dns"]
            self.dns_resolved = True
            added: list[_Route] = []
            for url in self.base_urls:
                host = urlparse(url).hostname
                if not host:
                    continue
                for ip in (await _public_dns_resolve(self.direct, host))[:2]:
                    added.append(("dns", self.direct, f"https://{ip}", host))
            self.routes += added
            return added

    async def get(self, path: str, params: dict[str, Any]) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, body: dict[str, Any]) -> Any:
        return await self._request("POST", path, json=body)

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        ordered = [self.route] + [r for r in self.routes if r != self.route]
        alive = [r for r in ordered if r not in self.dead] or ordered
        # 曾超时的线路排到最后，优先尝试响应正常的线路
        candidates = [r for r in alive if r not in self.slow] + [
            r for r in alive if r in self.slow
        ]
        deadline = time.monotonic() + TIKHUB_REQUEST_BUDGET
        timed_out = False
        proxy_down = False
        tried = 0
        index = 0
        while True:
            if index >= len(candidates):
                # 所有常规线路都失败：用公共 DNS 解析的真实 IP 再试一轮
                extra_routes = [
                    r
                    for r in await self._add_dns_routes()
                    if r not in candidates and r not in self.dead
                ]
                if not extra_routes:
                    break
                candidates += extra_routes
            route = candidates[index]
            index += 1
            remaining = deadline - time.monotonic()
            if remaining <= 3:
                break
            tried += 1
            name, client, base_url, host = route
            extra: dict[str, Any] = {}
            if host:
                extra = {
                    "headers": {"Host": host},
                    "extensions": {"sni_hostname": host},
                }
            try:
                response = await asyncio.wait_for(
                    client.request(method, f"{base_url}{path}", **kwargs, **extra),
                    timeout=min(TIKHUB_ATTEMPT_TIMEOUT, remaining),
                )
            except (TimeoutError, httpx.TimeoutException):
                timed_out = True
                self.slow.add(route)
                continue
            except httpx.ProxyError:
                proxy_down = True
                self.dead.add(route)
                continue
            except httpx.ConnectError:
                proxy_down = proxy_down or name == "proxy"
                self.dead.add(route)
                continue
            except httpx.RequestError:
                continue
            self.route = route
            self.slow.discard(route)
            self.reachable = True
            return response
        proxy_down = proxy_down or any(r[0] == "proxy" for r in self.dead)
        if timed_out and self.reachable:
            # 同批其他请求已成功，说明网络可用，是该接口上游抓取过慢
            raise CompetitorCollectError(
                "TikHub 上游接口响应超时（网络正常，同批其他请求已成功），"
                "可稍后点击「补采」重试"
            )
        if proxy_down and self.proxy:
            hint = (
                f"配置的代理 {self.proxy} 无法连接，直连及公共 DNS 兜底线路也失败"
                "（请启动代理软件或检查本机网络）"
            )
        else:
            hint = "请检查网络，或在 .env 中配置可用代理 TIKHUB_PROXY 后重试"
        reason = "响应超时" if timed_out else "无法连接"
        raise CompetitorCollectError(
            f"TikHub {reason}（已尝试 {tried} 条线路），{hint}"
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        async with self.semaphore:
            response = await self._send(method, path, **kwargs)
            # TikHub 上游抓取偶发失败时返回 400/5xx（不计费），重试一次
            if response.status_code == 400 or response.status_code >= 500:
                await asyncio.sleep(1.5)
                response = await self._send(method, path, **kwargs)
        if response.status_code in {401, 403}:
            raise CompetitorCollectError(
                "TikHub 鉴权失败，请检查 TIKHUB_API_KEY 是否正确或已开通接口权限"
            )
        if response.status_code == 402:
            raise CompetitorCollectError("TikHub 账户余额不足，请充值后重试")
        if response.status_code == 429:
            raise CompetitorCollectError("TikHub 请求被限流，请稍后重试")
        if response.status_code >= 400:
            raise CompetitorCollectError(
                f"TikHub 接口返回错误（HTTP {response.status_code}）：{path}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise CompetitorCollectError(f"TikHub 返回非 JSON 数据：{path}") from exc
        if isinstance(payload, dict) and payload.get("code") not in (None, 200):
            message = str(payload.get("message_zh") or payload.get("message") or "")[
                :120
            ]
            raise CompetitorCollectError(f"TikHub 接口失败：{path} {message}")
        return payload.get("data") if isinstance(payload, dict) else payload


def _find_meta(payload: Any, keys: tuple[str, ...], depth: int = 0) -> Any:
    """在响应外层几级查找分页字段（has_more / cursor 等），不深入内容列表。"""
    if not isinstance(payload, dict) or depth > 3:
        return None
    for key in keys:
        if key in payload and not isinstance(payload[key], dict | list):
            return payload[key]
    for value in payload.values():
        if isinstance(value, dict):
            found = _find_meta(value, keys, depth + 1)
            if found is not None:
                return found
    return None


def _has_more(payload: Any) -> bool:
    is_end = _find_meta(payload, ("is_end", "isEnd"))
    if is_end is not None:
        return not bool(is_end)
    more = _find_meta(payload, ("has_more", "hasMore"))
    return True if more is None else bool(more) and more not in ("0", "false")


def _next_cursor(payload: Any, fallback: int) -> int:
    value = _parse_count(_find_meta(payload, ("cursor", "next_cursor", "offset")))
    return value if value and value > 0 else fallback


async def collect_tikhub(
    platforms: list[str], keywords: list[str], *, per_keyword: int = 20
) -> tuple[list[dict[str, Any]], list[str]]:
    api_key = tikhub_api_key()
    if not api_key:
        raise CompetitorCollectError(
            "未配置 TIKHUB_API_KEY（环境变量或项目根目录 .env），无法使用深度采集",
            status_code=422,
        )
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    timeout = httpx.Timeout(TIKHUB_ATTEMPT_TIMEOUT, connect=8)
    proxy = tikhub_proxy()
    async with contextlib.AsyncExitStack() as stack:
        clients: list[tuple[str, httpx.AsyncClient]] = []
        if proxy:
            clients.append(
                (
                    "proxy",
                    await stack.enter_async_context(
                        httpx.AsyncClient(timeout=timeout, headers=headers, proxy=proxy)
                    ),
                )
            )
        # 直连客户端不读取系统代理环境变量，作为代理失效时的兜底
        clients.append(
            (
                "direct",
                await stack.enter_async_context(
                    httpx.AsyncClient(timeout=timeout, headers=headers, trust_env=False)
                ),
            )
        )
        api = _TikHubClient(clients, proxy)

        async def safe(label: str, coro: Any) -> Any:
            try:
                return await coro
            except CompetitorCollectError as exc:
                warnings.append(f"{label}：{exc}")
                return None

        def fetch_page(
            platform: str, keyword: str, page: int, cursor: int, token: dict[str, str]
        ) -> Any:
            if platform == "douyin":
                # 翻页必须带上一页返回的 search_id / backtrace，否则接口返回 400
                return api.post(
                    "/api/v1/douyin/search/fetch_video_search_v2",
                    {
                        "keyword": keyword,
                        "cursor": cursor,
                        "search_id": token.get("search_id", ""),
                        "backtrace": token.get("backtrace", ""),
                    },
                )
            if platform == "xiaohongshu":
                return api.get(
                    "/api/v1/xiaohongshu/app_v2/search_notes",
                    {"keyword": keyword, "page": page + 1},
                )
            return api.get(
                "/api/v1/zhihu/web/fetch_article_search_v3",
                {"keyword": keyword, "limit": min(per_keyword, 20), "offset": cursor},
            )

        async def search_keyword(
            platform: str, keyword: str, label: str
        ) -> list[dict[str, Any]]:
            """逐页搜索直到凑满每词条数，或平台没有更多结果。"""
            found: list[dict[str, Any]] = []
            seen: set[str] = set()
            cursor = 0
            token: dict[str, str] = {}
            failed = False
            for page in range(TIKHUB_SEARCH_MAX_PAGES):
                try:
                    data = await fetch_page(platform, keyword, page, cursor, token)
                except CompetitorCollectError as exc:
                    if found:
                        # 首页已有结果，翻页失败只影响补足条数，不作为采集错误
                        warnings.append(
                            f"{label}「{keyword}」第 {page + 1} 页翻页失败，已保留前 {len(found)} 条"
                        )
                    else:
                        warnings.append(f"{label}「{keyword}」第 {page + 1} 页：{exc}")
                    failed = True
                    break
                batch = extract_items(
                    data,
                    platform=platform,
                    kind="post",
                    keyword=keyword,
                    channel=label,
                )
                fresh = [i for i in batch if i["text"][:80] not in seen]
                for item in fresh[: per_keyword - len(found)]:
                    seen.add(item["text"][:80])
                    found.append(item)
                if len(found) >= per_keyword or not fresh or not _has_more(data):
                    break
                cursor = _next_cursor(data, cursor + len(batch))
                for key, names in (
                    ("search_id", ("search_id", "searchId", "impr_id", "logid")),
                    ("backtrace", ("backtrace",)),
                ):
                    value = _find_meta(data, names)
                    if value:
                        token[key] = str(value)
            if len(found) < per_keyword and not failed:
                warnings.append(
                    f"{label}「{keyword}」仅搜到 {len(found)} 条（每词设定 {per_keyword} 条，平台无更多结果）"
                )
            return found

        searches = [
            (platform, keyword, label)
            for keyword in keywords
            for platform, label in (
                ("douyin", "TikHub 抖音视频搜索"),
                ("xiaohongshu", "TikHub 小红书笔记搜索"),
                ("zhihu", "TikHub 知乎搜索"),
            )
            if platform in platforms
        ]
        for batch in await asyncio.gather(
            *(search_keyword(*search) for search in searches)
        ):
            items.extend(batch)

        if "douyin" in platforms:
            videos = sorted(
                (i for i in items if i["platform"] == "douyin" and i["ref_id"]),
                key=lambda i: i.get("likes") or 0,
                reverse=True,
            )[:5]
            comment_results = await asyncio.gather(
                *(
                    safe(
                        "TikHub 抖音评论",
                        api.get(
                            "/api/v1/douyin/app/v3/fetch_video_comments",
                            {"aweme_id": video["ref_id"], "cursor": 0, "count": 20},
                        ),
                    )
                    for video in videos
                )
            )
            for video, data in zip(videos, comment_results, strict=True):
                if data is not None:
                    items.extend(
                        extract_items(
                            data,
                            platform="douyin",
                            kind="comment",
                            keyword=video["keyword"],
                            channel="TikHub 抖音评论",
                            parent_ref=video["ref_id"],
                            limit=20,
                        )
                    )
            hot = await safe(
                "TikHub 抖音热榜",
                api.get("/api/v1/douyin/web/fetch_hot_search_result", {}),
            )
            if hot is not None:
                items.extend(
                    extract_items(
                        hot,
                        platform="douyin",
                        kind="hot",
                        keyword="",
                        channel="TikHub 抖音热榜",
                        limit=30,
                    )
                )
        if "xiaohongshu" in platforms:
            notes = sorted(
                (i for i in items if i["platform"] == "xiaohongshu" and i["ref_id"]),
                key=lambda i: i.get("likes") or 0,
                reverse=True,
            )[:3]
            comment_results = await asyncio.gather(
                *(
                    safe(
                        "TikHub 小红书评论",
                        api.get(
                            "/api/v1/xiaohongshu/app_v2/get_note_comments",
                            {"note_id": note["ref_id"]},
                        ),
                    )
                    for note in notes
                )
            )
            for note, data in zip(notes, comment_results, strict=True):
                if data is not None:
                    items.extend(
                        extract_items(
                            data,
                            platform="xiaohongshu",
                            kind="comment",
                            keyword=note["keyword"],
                            channel="TikHub 小红书评论",
                            parent_ref=note["ref_id"],
                            limit=20,
                        )
                    )
    if "ecommerce" in platforms:
        warnings.append("电商价格需用轻量档提供商品页链接采集，深度档不含电商接口")
    if not items and warnings:
        raise CompetitorCollectError("TikHub 采集全部失败：" + "；".join(warnings[:3]))
    return items, warnings


# ---------------------------------------------------------------- opencli（标准）

_OPENCLI_SITES = {"douyin": "douyin", "xiaohongshu": "xiaohongshu", "zhihu": "zhihu"}
_OPENCLI_LIMITS = {"douyin": 30}
OPENCLI_TIMEOUT = 90
_OPENCLI_HOMES = {
    "douyin": "https://www.douyin.com",
    "xiaohongshu": "https://www.xiaohongshu.com",
    "zhihu": "https://www.zhihu.com",
}


def _opencli_error_text(site: str, raw: str) -> str:
    """把 opencli 的 YAML 错误输出转成可执行的中文提示。"""
    text = (raw or "").strip()
    if "AUTH_REQUIRED" in text or "login wall" in text:
        return f"需要登录：请在装有 OpenCLI 扩展的 Chrome 中登录 {_OPENCLI_HOMES.get(site, site)} 后重试"
    if "out of memory" in text:
        return "opencli（Node）内存不足崩溃，请关闭部分程序后重试"
    if text == "timeout":
        return "执行超时，请确认 Chrome 已打开且 OpenCLI 扩展已连接"
    message = re.search(r"message:\s*(.+)", text)
    return (message.group(1) if message else text or "无输出")[:160]


def _opencli_fatal(raw: str) -> bool:
    """登录失效、扩展未连接、超时属于平台级故障，换关键词重试也无济于事。"""
    text = (raw or "").strip()
    lowered = text.lower()
    return (
        text == "timeout"
        or "AUTH_REQUIRED" in text
        or "login wall" in lowered
        or "not connected" in lowered
        or "无法启动 opencli" in text
    )


async def _run_opencli(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        return -1, "", f"无法启动 opencli：{exc}"
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        return -1, "", "timeout"
    return (
        process.returncode or 0,
        stdout.decode("utf-8", "replace"),
        stderr.decode("utf-8", "replace"),
    )


async def collect_opencli(
    platforms: list[str], keywords: list[str], *, per_keyword: int = 20
) -> tuple[list[dict[str, Any]], list[str]]:
    command = opencli_command()
    if not command:
        raise CompetitorCollectError(
            "未检测到 opencli 命令行（Chrome 扩展之外还需 CLI）：请执行 "
            f"npm install -g {OPENCLI_PACKAGE}，或设置 OPENCLI_BIN 指向 opencli 可执行文件",
            status_code=422,
        )
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    # 平台级失败原因：登录失效 / 扩展未连接时同平台其余关键词必然同样失败，直接跳过
    failed: dict[str, str] = {}
    for platform in platforms:
        site = _OPENCLI_SITES.get(platform)
        name = COMPETITOR_PLATFORMS.get(platform, platform)
        if not site:
            warnings.append(f"opencli 不支持平台：{name}")
            continue
        limit = min(per_keyword, _OPENCLI_LIMITS.get(site, per_keyword))
        label = f"opencli {name}搜索"
        got = 0
        for keyword in keywords:
            code, output, error = await _run_opencli(
                [
                    *command,
                    site,
                    "search",
                    keyword,
                    "--limit",
                    str(limit),
                    "-f",
                    "json",
                ],
                timeout=OPENCLI_TIMEOUT,
            )
            if code != 0 or not output.strip():
                raw = error or output
                reason = _opencli_error_text(site, raw)
                if _opencli_fatal(raw):
                    failed[platform] = reason
                    break
                warnings.append(f"{label}「{keyword}」失败：{reason}")
                continue
            try:
                data = json.loads(output)
            except ValueError:
                warnings.append(f"{label}「{keyword}」输出不是 JSON")
                continue
            batch = extract_items(
                data, platform=platform, kind="post", keyword=keyword, channel=label
            )
            got += len(batch)
            items.extend(batch)
        if not got and platform not in failed and keywords:
            failed[platform] = "未采到任何内容"

    if failed and tikhub_api_key():
        # opencli 不可用的平台自动改用 TikHub 补采，避免整次采集失败
        fallback = [p for p in failed if p in _OPENCLI_SITES]
        try:
            extra, extra_warnings = await collect_tikhub(
                fallback, keywords, per_keyword=per_keyword
            )
        except CompetitorCollectError as exc:
            extra, extra_warnings = [], [str(exc)]
        items.extend(extra)
        warnings.extend(extra_warnings)
        recovered = {item.get("platform") for item in extra}
        for platform in fallback:
            name = COMPETITOR_PLATFORMS.get(platform, platform)
            if platform in recovered:
                warnings.append(
                    f"opencli {name}不可用（{failed.pop(platform)}），已自动改用 TikHub 深度采集"
                )
    for platform, reason in failed.items():
        warnings.append(
            f"opencli {COMPETITOR_PLATFORMS.get(platform, platform)}：{reason}"
        )

    if not items and warnings:
        hint = (
            ""
            if tikhub_api_key()
            else "；也可在 .env 配置 TIKHUB_API_KEY，opencli 不可用时将自动改用 TikHub"
        )
        raise CompetitorCollectError(
            "opencli 采集全部失败：" + "；".join(warnings[:4]) + hint
        )
    return items, warnings


# ---------------------------------------------------------------- 公开页面（轻量）

_ECOMMERCE_HOSTS = (
    "jd.com",
    "taobao.com",
    "tmall.com",
    "yangkeduo.com",
    "pinduoduo.com",
    "jd.hk",
)
_META_RE = re.compile(
    r'<meta[^>]+(?:name|property)=["\'](?:description|og:description|og:title)["\'][^>]*content=["\']([^"\']+)',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_SCRIPT_RE = re.compile(
    r"<(script|style|noscript)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)


def _platform_of_url(url: str) -> str:
    host = urlparse(url).hostname or ""
    if any(host.endswith(item) for item in _ECOMMERCE_HOSTS):
        return "ecommerce"
    for key, domain in (
        ("douyin", "douyin.com"),
        ("xiaohongshu", "xiaohongshu.com"),
        ("zhihu", "zhihu.com"),
    ):
        if host.endswith(domain):
            return key
    return "web"


def search_link_keyword(url: str) -> tuple[str, str] | None:
    """识别小红书/抖音/知乎搜索页链接，返回 (平台, 关键词)。

    这类页面由脚本渲染、需要登录，直接抓取拿不到内容，改走 opencli 搜索。
    """
    parsed = urlparse(url)
    platform = _platform_of_url(url)
    query = parse_qs(parsed.query)
    keyword = ""
    if platform == "xiaohongshu" and parsed.path.startswith("/search_result"):
        keyword = (query.get("keyword") or [""])[0]
    elif platform == "douyin" and parsed.path.startswith("/search/"):
        keyword = unquote(parsed.path[len("/search/") :].split("/")[0])
    elif platform == "zhihu" and parsed.path.startswith("/search"):
        keyword = (query.get("q") or [""])[0]
    keyword = keyword.strip()
    return (platform, keyword) if keyword else None


async def collect_light(
    urls: list[str], *, per_keyword: int = 20
) -> tuple[list[dict[str, Any]], list[str]]:
    if not urls:
        raise CompetitorCollectError(
            "请粘贴至少一个链接（商品页/笔记/文章，或按产品名生成的搜索链接）",
            status_code=422,
        )
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    searches: dict[str, list[str]] = {}
    page_urls: list[str] = []
    for url in urls:
        found = search_link_keyword(url)
        if found:
            searches.setdefault(found[0], []).append(found[1])
        else:
            page_urls.append(url)
    for platform, keywords in searches.items():
        try:
            found_items, found_warnings = await collect_opencli(
                [platform], list(dict.fromkeys(keywords)), per_keyword=per_keyword
            )
        except CompetitorCollectError as exc:
            warnings.append(f"{COMPETITOR_PLATFORMS[platform]}搜索链接：{exc}")
            continue
        items.extend(found_items)
        warnings.extend(found_warnings)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    async with httpx.AsyncClient(
        timeout=20, headers=headers, follow_redirects=True
    ) as client:
        for url in urls:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                warnings.append(f"抓取失败 {url[:80]}：{type(exc).__name__}")
                continue
            page = response.text[:800000]
            title_match = _TITLE_RE.search(page)
            title = _clean_text(title_match.group(1)) if title_match else ""
            metas = [_clean_text(item) for item in _META_RE.findall(page)]
            body = _clean_text(_SCRIPT_RE.sub(" ", page))
            text = "；".join(dict.fromkeys(filter(None, [*metas, body[:400]])))
            if len(text) < 4 and not title:
                warnings.append(
                    f"页面无可读文本（可能需要登录或由脚本渲染）：{url[:80]}"
                )
                continue
            prices = [float(p) for p in _PRICE_RE.findall(page)][:20]
            platform = _platform_of_url(url)
            items.append(
                {
                    "item_id": "",
                    "platform": platform,
                    "kind": "product" if platform == "ecommerce" else "page",
                    "channel": "公开页面抓取",
                    "keyword": "",
                    "title": title[:120],
                    "text": (text or title)[:_TEXT_LIMIT],
                    "author": "",
                    "likes": None,
                    "comments": None,
                    "shares": None,
                    "collects": None,
                    "heat": None,
                    "price": min(prices) if prices else None,
                    "url": str(response.url)[:500],
                    "ref_id": "",
                    "parent_ref": "",
                    "collected_at": _now(),
                }
            )
    if not items:
        raise CompetitorCollectError("公开页面全部抓取失败：" + "；".join(warnings[:3]))
    return items, warnings


# ---------------------------------------------------------------- 汇总


def merge_items(
    existing: list[dict[str, Any]], new_items: list[dict[str, Any]], *, mode: str
) -> tuple[list[dict[str, Any]], int]:
    """合并去重并分配稳定编号 c001…；返回 (合并结果, 新增条数)。"""
    result = list(existing)
    seen = {(item["platform"], item["text"][:80]) for item in result}
    next_no = 1 + max(
        (
            int(item["item_id"][1:])
            for item in result
            if re.fullmatch(r"c\d+", item.get("item_id", ""))
        ),
        default=0,
    )
    added = 0
    for item in new_items:
        key = (item["platform"], item["text"][:80])
        if key in seen or len(result) >= COMPETITOR_ITEM_LIMIT:
            continue
        seen.add(key)
        item = dict(item)
        item["item_id"] = f"c{next_no:03d}"
        item["source_mode"] = mode
        item["uid"] = uuid.uuid4().hex[:12]
        next_no += 1
        result.append(item)
        added += 1
    return result, added
