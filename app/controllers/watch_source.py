# 瞭望数据源控制器

import tornado.web

from app.models.watch_source import WatchSourceRepository
from app.utils.auth import require_admin, get_username




def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


class WatchSourceListHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        result = WatchSourceRepository.paginate(page=page, page_size=20, keyword=keyword)
        total_pages = (result["total"] + 19) // 20
        self.render(
            "admin/watch_source_list.html",
            username=get_username(self),
            current_page="watch",
            **result,
            total_pages=total_pages,
            keyword=keyword,
        )


class WatchSourceAddHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        self.render(
            "admin/watch_source_edit.html",
            username=get_username(self),
            current_page="watch",
            source=None,
            is_add=True,
        )

    def post(self):
        if not require_admin(self):
            return
        name = self.get_body_argument("name", "").strip()
        url_template = self.get_body_argument("url_template", "").strip()
        method = self.get_body_argument("method", "GET").strip()
        headers = self.get_body_argument("headers", "{}").strip()
        proxy = self.get_body_argument("proxy", "").strip()
        enable_pagination = 1 if self.get_body_argument("enable_pagination", None) == "1" else 0
        if name and url_template:
            WatchSourceRepository.create(name, url_template, method, headers, proxy, enable_pagination)
        self.redirect("/admin/watch-sources")


class WatchSourceEditHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        source_id = _int_arg(self, "id")
        source = WatchSourceRepository.get_by_id(source_id)
        if not source:
            self.redirect("/admin/watch-sources")
            return
        self.render(
            "admin/watch_source_edit.html",
            username=get_username(self),
            current_page="watch",
            source=source,
            is_add=False,
        )

    def post(self):
        if not require_admin(self):
            return
        source_id = _int_arg(self, "id")
        source = WatchSourceRepository.get_by_id(source_id)
        if not source:
            self.redirect("/admin/watch-sources")
            return
        name = self.get_body_argument("name", "").strip()
        url_template = self.get_body_argument("url_template", "").strip()
        method = self.get_body_argument("method", "GET").strip()
        headers = self.get_body_argument("headers", "{}").strip()
        proxy = self.get_body_argument("proxy", "").strip()
        enable_pagination = 1 if self.get_body_argument("enable_pagination", None) == "1" else 0
        if name and url_template:
            WatchSourceRepository.update(
                source_id,
                name=name, url_template=url_template, method=method,
                headers=headers, proxy=proxy, enable_pagination=enable_pagination
            )
        self.redirect("/admin/watch-sources")


class WatchSourceDeleteHandler(tornado.web.RequestHandler):
    def post(self):
        if not require_admin(self):
            return
        source_id = _int_arg(self, "id")
        WatchSourceRepository.delete(source_id)
        self.redirect("/admin/watch-sources")
