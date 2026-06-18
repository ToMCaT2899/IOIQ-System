# 瞭望采集控制器 — 搜索引擎式采集界面 + SSE 采集执行

import json
import re
import tornado.web
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from app.models.watch_source import WatchSourceRepository
from app.models.watch_result import WatchResultRepository


def _require_login(handler):
    if not handler.get_secure_cookie("admin_user"):
        handler.redirect("/admin/login")
        return False
    return True


class WatchCollectPageHandler(tornado.web.RequestHandler):
    """瞭望采集主页面（独立科技风，不继承 base.html）"""

    def get(self):
        if not _require_login(self):
            return
        self.render("admin/watch_collect.html", current_page="watch_collect")


class WatchCollectSourcesHandler(tornado.web.RequestHandler):
    """获取可用数据源列表（JSON）"""

    def get(self):
        if not _require_login(self):
            return
        sources = WatchSourceRepository.get_all()
        data = [{
            "id": s["id"], "name": s["name"],
            "url_template": s["url_template"],
            "method": s["method"], "headers": s["headers"],
            "proxy": s["proxy"], "enable_pagination": s["enable_pagination"]
        } for s in sources]
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))


class WatchCollectFetchHandler(tornado.web.RequestHandler):
    """执行采集 — SSE 流式返回进度与结果"""

    async def post(self):
        if not _require_login(self):
            return

        body = json.loads(self.request.body or "{}")
        keyword = body.get("keyword", "").strip()
        source_ids = body.get("source_ids", [])   # 选中的采集源ID列表
        pages = int(body.get("pages", 1))          # 采集页数
        pn_step = int(body.get("pn_step", 10))     # 分页步进

        if not keyword:
            self.set_status(400)
            self.finish()
            return

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.set_header("X-Accel-Buffering", "no")

        all_sources = WatchSourceRepository.get_all()
        active_sources = [s for s in all_sources if s["id"] in source_ids]

        if not active_sources:
            active_sources = all_sources  # 未选则全部使用

        total_collected = 0

        for src in active_sources:
            src_name = src["name"]
            url_tpl = src["url_template"]
            enable_pn = src["enable_pagination"]
            method = src["method"]
            proxy = src["proxy"] or None

            # 解析 headers
            try:
                headers = json.loads(src["headers"] or "{}")
            except json.JSONDecodeError:
                headers = {}

            max_pages = pages if enable_pn else 1

            for pg in range(max_pages):
                pn_value = pg * pn_step
                url = url_tpl.replace("{关键词}", keyword)
                if "{pn}" in url:
                    url = url.replace("{pn}", str(pn_value))

                # 通知前端当前采集进度
                progress = {
                    "source": src_name,
                    "source_id": src["id"],
                    "page": pg + 1,
                    "total_pages": max_pages,
                    "url": url[:120]
                }
                self.write(f"data: {json.dumps({'type': 'progress', **progress}, ensure_ascii=False)}\n\n")
                await self.flush()

                try:
                    if method == "POST":
                        resp = requests.post(url, headers=headers, proxies={"http": proxy, "https": proxy} if proxy else None, timeout=15)
                    else:
                        resp = requests.get(url, headers=headers, proxies={"http": proxy, "https": proxy} if proxy else None, timeout=15)
                    resp.encoding = resp.apparent_encoding or "utf-8"
                    html = resp.text
                except Exception as e:
                    err = {"type": "error", "source": src_name, "message": str(e)}
                    self.write(f"data: {json.dumps(err, ensure_ascii=False)}\n\n")
                    await self.flush()
                    continue

                # 从 URL 模板提取 base_url（用于补全相对路径）
                base_url = _extract_base_url(url_tpl)

                # 从 HTML 提取标题和摘要
                items = _extract_items(html, keyword, base_url)
                for item in items:
                    item["source_id"] = src["id"]
                    item["source_name"] = src_name
                    item["keyword"] = keyword
                    item["page_num"] = pg + 1
                    item["raw_html"] = item.get("raw_html", "")[:500]

                total_collected += len(items)

                # 逐条推送结果
                for item in items:
                    result = {
                        "type": "result",
                        "source_id": item["source_id"],
                        "source_name": item["source_name"],
                        "keyword": item["keyword"],
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", ""),
                        "page_num": item.get("page_num", 1)
                    }
                    self.write(f"data: {json.dumps(result, ensure_ascii=False)}\n\n")
                    await self.flush()

            # 每个源采集完成后通知
            done_msg = {
                "type": "source_done",
                "source_id": src["id"],
                "source_name": src_name
            }
            self.write(f"data: {json.dumps(done_msg, ensure_ascii=False)}\n\n")
            await self.flush()

        # 全部完成
        final = {"type": "all_done", "total": total_collected}
        self.write(f"data: {json.dumps(final, ensure_ascii=False)}\n\n")
        await self.flush()


class WatchCollectSaveHandler(tornado.web.RequestHandler):
    """保存选中的采集结果到数据库"""

    def post(self):
        if not _require_login(self):
            return
        body = json.loads(self.request.body or "{}")
        results = body.get("results", [])
        if results:
            saved = WatchResultRepository.save_batch(results)
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"saved": saved}, ensure_ascii=False))
        else:
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"saved": 0}))


def _extract_items(html: str, keyword: str, base_url: str = "") -> list:
    """从 HTML 中提取标题、链接、摘要"""
    items = []
    soup = BeautifulSoup(html, "lxml" if _has_parser("lxml") else "html.parser")

    # 方法1: 查找 a 标签内包含关键词的
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if title and len(title) >= 4:
            # 过滤掉纯导航链接
            if len(title) > 100 or title in {"下一页", "下一页>", "上一页", "首页", "末页", "刷新", "搜索"}:
                continue
            snippet = _get_parent_text(a)
            items.append({
                "title": title[:200],
                "url": _resolve_url(href, base_url),
                "snippet": snippet[:500],
                "raw_html": str(a.parent)[:500] if a.parent else ""
            })

    # 方法2: 查找 h3 标题
    for tag in soup.find_all(["h3", "h4"]):
        a = tag.find("a", href=True) if tag.name != "a" else tag
        if a and a.name == "a":
            title = a.get_text(strip=True)
            href = a.get("href", "")
        else:
            title = tag.get_text(strip=True)
            href = ""
        if title and len(title) >= 4 and not any(
            item["title"] == title for item in items
        ):
            snippet = _get_parent_text(tag)
            items.append({
                "title": title[:200],
                "url": _resolve_url(href, base_url) if href else "",
                "snippet": snippet[:500],
                "raw_html": ""
            })

    # 去重（按title）
    seen = set()
    unique = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    return unique[:50]


def _get_parent_text(element) -> str:
    """获取父级/兄弟节点的文本作为摘要"""
    parent = element.parent
    if parent:
        return parent.get_text(strip=True)[:500]
    return ""


def _resolve_url(href: str, base_url: str = "") -> str:
    """补全相对 URL — 使用 urljoin 将相对路径转为绝对 URL"""
    if not href:
        return ""
    if href.startswith("javascript:") or href.startswith("#"):
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if base_url:
        return urljoin(base_url, href)
    return href


def _has_parser(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _extract_base_url(url_template: str) -> str:
    """从 URL 模板中提取 base URL（scheme + netloc），用于补全相对路径。
    例如: 'https://www.baidu.com/s?wd={关键词}&pn={pn}' -> 'https://www.baidu.com'
    """
    if not url_template:
        return ""
    parsed = urlparse(url_template)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""
