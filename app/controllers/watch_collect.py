# 瞭望采集控制器 — 搜索引擎式采集界面 + SSE 采集执行

import json
import re
import tornado.web
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from app.models.watch_source import WatchSourceRepository
from app.utils.auth import require_admin, get_username
from app.models.watch_result import WatchResultRepository



class WatchCollectPageHandler(tornado.web.RequestHandler):
    """瞭望采集主页面（独立科技风，不继承 base.html）"""

    def get(self):
        if not require_admin(self):
            return
        self.render("admin/watch_collect.html", current_page="watch_collect")


class WatchCollectSourcesHandler(tornado.web.RequestHandler):
    """获取可用数据源列表（JSON）"""

    def get(self):
        if not require_admin(self):
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
        if not require_admin(self):
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
        if not require_admin(self):
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
    """从 HTML 中提取标题、链接、摘要 — 含关键词相关性评分与智能过滤"""
    items = []
    soup = BeautifulSoup(html, "lxml" if _has_parser("lxml") else "html.parser")
    keyword_lower = keyword.lower()

    # 方法1: 搜索常见搜索结果容器（适配百度/Google/Bing/搜狗/360）
    result_containers = soup.select(
        "div.result, div.g, div.results, div.c-container, "
        "li.b_algo, div.vrwrap, div.vr, "
        "div.rb, div.result-item, article.result, "
        "div[class*=result], div[class*=search-item], "
        "li[class*=result], div[class*=item]"
    )
    if result_containers:
        for container in result_containers[:80]:
            item = _extract_from_container(container, keyword_lower, base_url)
            if item:
                items.append(item)

    # 方法2: 查找 a 标签，关键词必须出现在标题或URL中
    if not items:
        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not _is_valid_title(title):
                continue
            if not _keyword_in_text(title, keyword_lower):
                continue
            snippet = _get_parent_text(a)
            if not _keyword_in_text(snippet, keyword_lower):
                snippet = _get_sibling_text(a)
            items.append({
                "title": title[:200],
                "url": _resolve_url(href, base_url),
                "snippet": snippet[:500],
                "raw_html": str(a.parent)[:500] if a.parent else ""
            })

    # 方法3: 补充查找 h3/h4/h2 标题（仅当结果较少时）
    if len(items) < 5:
        for tag in soup.find_all(["h3", "h4", "h2"]):
            a = tag.find("a", href=True)
            if a:
                title = a.get_text(strip=True)
                href = a.get("href", "")
            else:
                title = tag.get_text(strip=True)
                href = ""
            if not _is_valid_title(title):
                continue
            if not _keyword_in_text(title, keyword_lower):
                continue
            snippet = _get_parent_text(tag)
            if not _keyword_in_text(snippet, keyword_lower):
                snippet = tag.get_text(strip=True)
            items.append({
                "title": title[:200],
                "url": _resolve_url(href, base_url) if href else "",
                "snippet": snippet[:500],
                "raw_html": ""
            })

    # 计算相关性评分并过滤
    scored = []
    for item in items:
        score = _keyword_relevance_score(item["title"], item["snippet"], keyword_lower)
        if score >= 0.15:  # 至少有一定相关性
            item["_score"] = score
            scored.append(item)

    # 按相关性评分降序排列
    scored.sort(key=lambda x: x["_score"], reverse=True)

    # 标题相似度去重
    unique = _deduplicate_by_similarity(scored)

    # 移除评分辅助字段
    for item in unique:
        item.pop("_score", None)

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


# ——————————— 关键词相关性 & 智能过滤 ———————————


def _extract_from_container(container, keyword_lower: str, base_url: str) -> dict or None:
    """从搜索结果容器中提取条目 — 适配百度/Google/Bing 等主流搜索引擎 DOM 结构"""
    # 找标题链接
    a_tag = container.find("a", href=True)
    if not a_tag:
        return None
    title = a_tag.get_text(strip=True)
    href = a_tag.get("href", "")
    if not _is_valid_title(title):
        return None
    # 关键词必须出现在标题中（搜索结果容器内）
    if not _keyword_in_text(title, keyword_lower):
        return None

    # 找摘要文本
    snippet = ""
    # 常见摘要选择器
    snippet_selectors = [
        "span.content-right_8Zs40", "div.c-abstract", "span.abstract",
        "div.b_caption p", "div.b_snippet", "p.b_lineclamp",
        "div.str_info", "div.str-text", "div.result-snippet",
        "p", "div.summary", "div.description", "div.snippet",
        "span[class*=abstract]", "div[class*=summary]", "div[class*=snippet]"
    ]
    for sel in snippet_selectors:
        el = container.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if len(text) > len(snippet):
                snippet = text
    if not snippet:
        # 回退：取容器内除标题外的最大文本块
        texts = []
        for el in container.find_all(["p", "div", "span"]):
            if el != a_tag:
                t = el.get_text(strip=True)
                if len(t) > 10:
                    texts.append(t)
        if texts:
            snippet = max(texts, key=len)

    return {
        "title": title[:200],
        "url": _resolve_url(href, base_url),
        "snippet": snippet[:500],
        "raw_html": str(container)[:500]
    }


def _is_valid_title(title: str) -> bool:
    """判断标题是否有效（非导航、非噪声）"""
    if not title or len(title) < 4:
        return False
    if len(title) > 150:
        return False
    # 常见无关文本
    noise_words = {
        "下一页", "下一页>", "上一页", "首页", "末页", "刷新", "搜索",
        "登录", "注册", "设为首页", "加入收藏", "意见反馈", "举报",
        "广告", "推广", "返回顶部", "回到顶部", "更多", "查看更多",
        "展开", "收起", "查看全部", "加载更多", "正在加载", "loading",
        "上一页", "下一页", "跳转", "确定", "取消", "提交",
        "确认", "菜单", "导航", "首页", "关于我们", "联系方式",
        "版权", "隐私政策", "使用条款", "帮助中心", "帮助",
    }
    if title in noise_words:
        return False
    # 纯数字/符号
    if re.match(r'^[\d\s\-–—,.，。、；;：:（）()\[\]【】/\\|]+$', title):
        return False
    # 常见无意义模式
    if re.match(r'^(第\d+页|\d+条|共\d+条|共\d+页)$', title):
        return False
    return True


def _keyword_in_text(text: str, keyword_lower: str) -> bool:
    """检查关键词是否出现在文本中（支持多词拆分匹配）"""
    if not text or not keyword_lower:
        return False
    text_lower = text.lower()
    # 整词匹配
    if keyword_lower in text_lower:
        return True
    # 拆分关键词逐词匹配（至少匹配一半的词）
    terms = _tokenize_keyword(keyword_lower)
    if not terms:
        return False
    matched = sum(1 for t in terms if t in text_lower)
    return matched >= max(1, len(terms) // 2)


def _tokenize_keyword(keyword: str) -> list:
    """将关键词拆分为独立词元"""
    # 按常见分隔符拆分
    tokens = re.split(r'[\s,，、；;.。！!？?]+', keyword)
    tokens = [t.strip() for t in tokens if len(t.strip()) >= 1]
    # 如果拆分后只有长词，尝试2-gram子词
    if len(tokens) <= 1 and len(keyword) > 2:
        chars = list(keyword)
        ngrams = ["".join(chars[i:i+2]) for i in range(len(chars)-1)]
        tokens = tokens + ngrams
    return tokens


def _keyword_relevance_score(title: str, snippet: str, keyword_lower: str) -> float:
    """计算标题和摘要与关键词的相关性评分 (0.0~1.0)"""
    if not title and not snippet:
        return 0.0

    terms = _tokenize_keyword(keyword_lower)
    if not terms:
        return 0.0

    title_lower = title.lower()
    snippet_lower = snippet.lower() if snippet else ""

    score = 0.0
    term_count = len(terms)

    for term in terms:
        # 标题匹配权重 0.7
        if term in title_lower:
            score += 0.7 / term_count
        # 摘要匹配权重 0.3
        if term in snippet_lower:
            score += 0.3 / term_count

    # 整词完全匹配在标题中额外加分
    if keyword_lower in title_lower:
        score = min(1.0, score + 0.15)

    # 标题开头匹配加分（更相关）
    if title_lower.startswith(keyword_lower):
        score = min(1.0, score + 0.1)

    return round(score, 3)


def _deduplicate_by_similarity(items: list, threshold: float = 0.8) -> list:
    """基于标题相似度去重（字符 trigram Jaccard 相似度）"""
    if len(items) <= 1:
        return items

    def _trigrams(text: str) -> set:
        text = text.lower()
        return {text[i:i+3] for i in range(len(text) - 2)}

    def _similarity(a: str, b: str) -> float:
        tri_a = _trigrams(a)
        tri_b = _trigrams(b)
        if not tri_a or not tri_b:
            return 0.0
        intersection = tri_a & tri_b
        union = tri_a | tri_b
        return len(intersection) / len(union) if union else 0.0

    unique = []
    for item in items:
        title = item.get("title", "")
        is_dup = False
        for kept in unique:
            if _similarity(title, kept.get("title", "")) >= threshold:
                # 保留评分更高的
                if item.get("_score", 0) > kept.get("_score", 0):
                    unique.remove(kept)
                    unique.append(item)
                is_dup = True
                break
        if not is_dup:
            unique.append(item)
    return unique


def _get_sibling_text(element) -> str:
    """获取兄弟节点的文本作为摘要"""
    parent = element.parent
    if not parent:
        return ""
    texts = []
    for child in parent.children:
        if hasattr(child, "get_text") and child != element:
            t = child.get_text(strip=True)
            if len(t) > 5:
                texts.append(t)
    return "; ".join(texts)[:500]
