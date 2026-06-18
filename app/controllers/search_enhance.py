# 网络搜索管理控制器 — 搜索日志/统计/缓存管理

import json
import tornado.web

from app.models.web_search_log import WebSearchLogRepository
from app.utils.auth import require_admin, get_username




def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


class SearchLogHandler(tornado.web.RequestHandler):
    """搜索日志列表"""

    def get(self):
        if not require_admin(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        user = self.get_argument("user", "").strip()
        date_from = self.get_argument("date_from", "").strip()
        date_to = self.get_argument("date_to", "").strip()

        result = WebSearchLogRepository.paginate(
            page=page, page_size=20,
            keyword=keyword, user=user,
            date_from=date_from, date_to=date_to,
        )
        total_pages = (result["total"] + 19) // 20
        stats = WebSearchLogRepository.get_stats()

        self.render(
            "admin/search_logs.html",
            username=get_username(self),
            current_page="search_enhance",
            **result,
            total_pages=total_pages,
            keyword=keyword, user=user,
            date_from=date_from, date_to=date_to,
            stats=stats,
        )


class SearchLogClearHandler(tornado.web.RequestHandler):
    """清空搜索日志"""

    def post(self):
        if not require_admin(self):
            return
        WebSearchLogRepository.clear()
        self.redirect("/admin/search-logs")


class SearchLogExportHandler(tornado.web.RequestHandler):
    """导出搜索日志 JSON"""

    def get(self):
        if not require_admin(self):
            return
        result = WebSearchLogRepository.paginate(page=1, page_size=50000)
        data = []
        for r in result["list"]:
            data.append({
                "id": r["id"],
                "query": r["query"],
                "result_count": r["result_count"],
                "source": r["source"],
                "source_urls": r["source_urls"],
                "user": r["user"],
                "duration_ms": r["duration_ms"],
                "created_at": r["created_at"],
            })
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.set_header("Content-Disposition", "attachment; filename=search_logs.json")
        self.write(json.dumps(data, ensure_ascii=False, indent=2))


class SearchCacheClearHandler(tornado.web.RequestHandler):
    """清除搜索缓存"""

    def post(self):
        if not require_admin(self):
            return
        from app.services.web_search import clear_cache
        clear_cache()
        self.redirect("/admin/search-logs")


class SearchTestHandler(tornado.web.RequestHandler):
    """搜索测试页 — 直接调用搜索 API 查看结果"""

    def get(self):
        if not require_admin(self):
            return
        query = self.get_argument("q", "").strip()
        result = None
        error = None
        if query:
            try:
                from app.controllers.web_chat import _execute_web_search
                result = _execute_web_search(query)
            except Exception as e:
                error = str(e)
        self.render(
            "admin/search_test.html",
            username=get_username(self),
            current_page="search_enhance",
            query=query,
            result=result,
            error=error,
        )
