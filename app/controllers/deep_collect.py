# 深度采集控制器 — 对数据仓库数据执行深度采集（爬取+模型分析）

import json
import time
import tornado.web
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from app.models.db import get_connection
from app.utils.auth import require_admin, get_username
from app.models.deep_result import DeepResultRepository
from app.models.model_engine import ModelEngineRepository




def _send_sse(handler, data: dict):
    handler.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")


def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


class DeepCollectListHandler(tornado.web.RequestHandler):
    """深度采集结果列表页 — 展示所有深度采集记录及进度"""

    def get(self):
        if not require_admin(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        page_size = 20
        offset = (page - 1) * page_size

        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) AS cnt FROM deep_results").fetchone()["cnt"]
            rows = conn.execute(
                """SELECT dr.*, wr.title AS source_title, wr.keyword, wr.url AS source_url
                   FROM deep_results dr
                   LEFT JOIN watch_results wr ON dr.watch_result_id = wr.id
                   ORDER BY dr.id DESC LIMIT ? OFFSET ?""",
                (page_size, offset)
            ).fetchall()

        total_pages = (total + page_size - 1) // page_size

        self.render(
            "admin/deep_collect_list.html",
            username=get_username(self),
            current_page="deep",
            list=rows, total=total, page=page, page_size=page_size,
            total_pages=total_pages,
        )


class DeepCollectSSEHandler(tornado.web.RequestHandler):
    """深度采集 SSE 流式接口 — 支持单条/批量"""

    async def post(self):
        if not require_admin(self):
            return

        body = json.loads(self.request.body or "{}")
        ids_raw = body.get("ids", [])
        # 兼容单条: {"id": 5} 或批量: {"ids": [1,2,3]}
        if not ids_raw and body.get("id"):
            ids_raw = [int(body["id"])]

        if not ids_raw:
            self.set_status(400)
            self.finish()
            return

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.set_header("X-Accel-Buffering", "no")

        # 获取默认模型引擎（用于 AI 分析）
        model = ModelEngineRepository.get_default()
        require_ai = bool(body.get("use_ai", True)) and model is not None

        ids = [int(x) for x in ids_raw]
        total = len(ids)
        success_count = 0
        fail_count = 0
        start_time = time.time()

        _send_sse(self, {
            "type": "start", "total": total,
            "mode": "batch" if total > 1 else "single",
            "use_ai": require_ai,
            "model_name": model["model_name"] if model else ""
        })
        await self.flush()

        for idx, watch_id in enumerate(ids):
            item = _get_watch_result(watch_id)
            if not item:
                _send_sse(self, {
                    "type": "log", "watch_id": watch_id,
                    "level": "warn",
                    "message": f"[{idx+1}/{total}] 记录 {watch_id} 不存在，跳过"
                })
                await self.flush()
                fail_count += 1
                continue

            title = item["title"] or "无标题"
            url = item["url"] or ""
            progress = {"type": "progress", "current": idx + 1, "total": total,
                        "watch_id": watch_id, "title": title[:60]}

            if not url or not url.startswith("http"):
                # 无有效 URL — 使用 snippet 做基础分析
                _send_sse(self, {**progress, "message": f"无有效源URL，使用片段内容分析"})
                await self.flush()
                log_lines = [f"[{idx+1}/{total}] {title}", "无有效源URL，使用片段内容分析"]
                result = _analyze_from_snippet(item, model, require_ai)
                log_lines.extend(result.get("logs", []))
                log_text = "\n".join(log_lines)

                deep_id = DeepResultRepository.create(
                    watch_result_id=watch_id,
                    source_url=url,
                    model_engine_id=model["id"] if model else 0,
                    model_name=model["model_name"] if model else "",
                    title=title,
                    full_content=result.get("full_content", ""),
                    content_summary=result.get("summary", ""),
                    status=result.get("status", "success"),
                    error_message=result.get("error", ""),
                    log_text=log_text,
                    tokens_used=result.get("tokens", 0),
                    duration_ms=result.get("duration_ms", 0)
                )
                if result.get("status") == "success":
                    success_count += 1
                else:
                    fail_count += 1
                _send_sse(self, {
                    "type": "item_done", "watch_id": watch_id,
                    "deep_id": deep_id, "status": result.get("status"),
                    "summary": result.get("summary", "")[:100],
                    "duration_ms": result.get("duration_ms", 0)
                })
                await self.flush()
                continue

            # 有 URL — 爬取内容
            _send_sse(self, {**progress, "message": f"正在抓取原文..."})
            await self.flush()
            log_lines = [f"[{idx+1}/{total}] {title}", f"URL: {url}"]

            fetch_result = _fetch_and_extract(url)
            log_lines.extend(fetch_result.get("logs", []))

            if fetch_result.get("error"):
                _send_sse(self, {
                    "type": "log", "watch_id": watch_id,
                    "level": "error", "message": f"抓取失败: {fetch_result['error']}"
                })
                await self.flush()
                log_text = "\n".join(log_lines)
                DeepResultRepository.create(
                    watch_result_id=watch_id,
                    source_url=url,
                    model_engine_id=model["id"] if model else 0,
                    model_name=model["model_name"] if model else "",
                    title=title,
                    full_content="",
                    content_summary=fetch_result.get("error", ""),
                    status="fail",
                    error_message=fetch_result.get("error", ""),
                    log_text=log_text,
                    duration_ms=fetch_result.get("duration_ms", 0)
                )
                fail_count += 1
                _send_sse(self, {
                    "type": "item_done", "watch_id": watch_id,
                    "status": "fail",
                    "error": fetch_result.get("error", "")[:100],
                    "duration_ms": fetch_result.get("duration_ms", 0)
                })
                await self.flush()
                continue

            raw_content = fetch_result.get("content", "")
            log_lines.append(f"抓取成功，内容长度: {len(raw_content)} 字符")

            # AI 分析
            summary = ""
            ai_tokens = 0
            ai_duration_ms = 0
            if require_ai and raw_content:
                _send_sse(self, {**progress, "message": f"正在AI分析..."})
                await self.flush()
                ai_result = _ai_analyze(model, title, raw_content)
                summary = ai_result.get("summary", "")
                ai_tokens = ai_result.get("tokens", 0)
                ai_duration_ms = ai_result.get("duration_ms", 0)
                log_lines.extend(ai_result.get("logs", []))
            else:
                # 无AI或AI不可用 — 使用规则生成摘要
                summary = _rule_summary(raw_content, title)
                log_lines.append("使用规则摘要（未启用AI或模型不可用）")

            total_duration = fetch_result.get("duration_ms", 0) + ai_duration_ms
            log_text = "\n".join(log_lines)

            deep_id = DeepResultRepository.create(
                watch_result_id=watch_id,
                source_url=url,
                model_engine_id=model["id"] if model else 0,
                model_name=model["model_name"] if model else "",
                title=title,
                full_content=raw_content[:50000],
                content_summary=summary,
                status="success",
                log_text=log_text,
                tokens_used=ai_tokens,
                duration_ms=total_duration
            )
            success_count += 1

            _send_sse(self, {
                "type": "item_done", "watch_id": watch_id,
                "deep_id": deep_id, "status": "success",
                "content_len": len(raw_content),
                "summary": summary[:120],
                "tokens": ai_tokens,
                "duration_ms": total_duration
            })
            await self.flush()

        total_duration = int((time.time() - start_time) * 1000)
        _send_sse(self, {
            "type": "all_done",
            "total": total,
            "success": success_count,
            "fail": fail_count,
            "duration_ms": total_duration
        })
        await self.flush()


class DeepCollectDetailHandler(tornado.web.RequestHandler):
    """深度采集结果详情页"""

    def get(self, watch_id):
        if not require_admin(self):
            return
        watch_id = int(watch_id)
        item = _get_watch_result(watch_id)
        if not item:
            self.set_status(404)
            self.write("记录不存在")
            return
        deep = DeepResultRepository.get_by_watch_result_id(watch_id)
        self.render(
            "admin/deep_detail.html",
            username=get_username(self),
            current_page="deep",
            item=item,
            deep=deep,
        )


# ---- 辅助函数 ----

def _get_watch_result(watch_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM watch_results WHERE id=?", (watch_id,)
        ).fetchone()


def _fetch_and_extract(url: str) -> dict:
    """抓取网页并提取正文内容"""
    logs = []
    t0 = time.time()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text
        logs.append(f"HTTP {resp.status_code}, 内容长度: {len(html)}")
    except Exception as e:
        duration = int((time.time() - t0) * 1000)
        return {"error": str(e), "logs": logs, "duration_ms": duration}

    # 提取正文
    try:
        soup = BeautifulSoup(html, "lxml" if _has_parser("lxml") else "html.parser")
        # 移除无用标签
        for tag in soup(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
            tag.decompose()

        # 提取正文 — 优先 article/main 标签，否则取 body 文本
        body = soup.find("article") or soup.find("main") or soup.find("body")
        if body:
            text = body.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # 清理：合并连续空行
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 截断过长内容
        if len(text) > 50000:
            text = text[:50000] + "\n\n[内容过长，已截断至50000字符]"
            logs.append("内容过长，已截断至50000字符")
    except Exception as e:
        duration = int((time.time() - t0) * 1000)
        return {"error": f"解析失败: {e}", "logs": logs, "duration_ms": duration}

    duration = int((time.time() - t0) * 1000)
    return {"content": text, "logs": logs, "duration_ms": duration}


def _analyze_from_snippet(item, model, require_ai: bool) -> dict:
    """对无URL的记录做基于摘要的简单分析"""
    snippet = item.get("snippet", "") or ""
    title = item.get("title", "") or ""
    logs = []
    t0 = time.time()

    if require_ai and model and snippet:
        try:
            result = _call_model(model, title, snippet)
            duration = int((time.time() - t0) * 1000)
            logs.append(f"AI分析完成，Tokens: {result.get('tokens', 0)}")
            return {
                "status": "success",
                "full_content": snippet,
                "summary": result.get("summary", snippet[:200]),
                "logs": logs,
                "tokens": result.get("tokens", 0),
                "duration_ms": duration
            }
        except Exception as e:
            logs.append(f"AI分析失败: {e}")

    duration = int((time.time() - t0) * 1000)
    combined = f"【{title}】\n{snippet}" if title else snippet
    summary = combined[:200] + ("..." if len(combined) > 200 else "")
    return {
        "status": "success",
        "full_content": combined,
        "summary": summary,
        "logs": logs,
        "tokens": 0,
        "duration_ms": duration
    }


def _ai_analyze(model, title: str, content: str) -> dict:
    """使用模型引擎进行 AI 分析"""
    logs = []
    t0 = time.time()
    try:
        # 截取内容，避免超出模型限制
        truncated = content[:8000] if len(content) > 8000 else content
        result = _call_model(model, title, truncated)
        duration = int((time.time() - t0) * 1000)
        logs.append(f"AI分析完成，Tokens: {result.get('tokens', 0)}")
        return {
            "summary": result.get("summary", ""),
            "tokens": result.get("tokens", 0),
            "duration_ms": duration,
            "logs": logs
        }
    except Exception as e:
        duration = int((time.time() - t0) * 1000)
        logs.append(f"AI分析失败：{e}")
        return {
            "summary": _rule_summary(content, title),
            "tokens": 0,
            "duration_ms": duration,
            "logs": logs
        }


def _call_model(model, title: str, content: str) -> dict:
    """调用 OpenAI 兼容 API 进行内容分析"""
    from openai import OpenAI

    client = OpenAI(
        base_url=model["api_base"],
        api_key=model["api_key"]
    )
    prompt = (
        f"请对以下文章进行深度分析，返回JSON格式（不要markdown包裹）：\n"
        f'{{"summary": "200字以内的内容摘要", "keywords": ["关键词1","关键词2"], '
        f'"category": "文章分类", "sentiment": "正面/负面/中性"}}\n\n'
        f"标题：{title}\n\n内容：\n{content[:6000]}"
    )
    resp = client.chat.completions.create(
        model=model["model_name"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=800,
        timeout=60,
    )
    usage = resp.usage
    tokens = usage.total_tokens if usage else 0
    raw = resp.choices[0].message.content

    # 尝试解析 JSON
    try:
        parsed = json.loads(raw)
        summary = parsed.get("summary", raw[:200])
    except json.JSONDecodeError:
        # 去掉可能的 markdown 包裹
        import re
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            try:
                parsed = json.loads(m.group())
                summary = parsed.get("summary", raw[:200])
            except json.JSONDecodeError:
                summary = raw[:200]
        else:
            summary = raw[:200]

    return {"summary": summary, "tokens": tokens}


def _rule_summary(content: str, title: str = "") -> str:
    """规则生成摘要 — 提取前200字符"""
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    summary = " ".join(lines)[:200]
    if len(summary) == 200:
        summary += "..."
    return summary


def _has_parser(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False
