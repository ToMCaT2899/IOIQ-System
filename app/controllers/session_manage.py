# 会话管理控制器 — 列表/详情/筛选/标记/归档/导出

import json
import tornado.web
import tornado.escape

from app.models.session_manage import SessionRepository
from app.utils.auth import require_admin, get_username




def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


class SessionListHandler(tornado.web.RequestHandler):
    """会话管理列表页"""

    def get(self):
        if not require_admin(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        user_id = _int_arg(self, "user_id", 0)
        status = self.get_argument("status", "").strip()
        date_from = self.get_argument("date_from", "").strip()
        date_to = self.get_argument("date_to", "").strip()
        result = SessionRepository.paginate(
            page=page, page_size=15,
            keyword=keyword, user_id=user_id,
            status=status, date_from=date_from, date_to=date_to,
        )
        total_pages = (result["total"] + 14) // 15
        stats = SessionRepository.get_stats()
        users = SessionRepository.get_user_list()
        self.render(
            "admin/session_list.html",
            username=get_username(self),
            current_page="sessions",
            **result,
            total_pages=total_pages,
            keyword=keyword, user_id=user_id,
            status=status, date_from=date_from, date_to=date_to,
            stats=stats, users=users,
        )


class SessionDetailHandler(tornado.web.RequestHandler):
    """会话详情页 — 展示完整对话历史"""

    def get(self):
        if not require_admin(self):
            return
        conv_id = _int_arg(self, "id")
        session = SessionRepository.get_by_id(conv_id)
        if not session:
            self.redirect("/admin/sessions")
            return
        messages = SessionRepository.get_messages(conv_id)
        self.render(
            "admin/session_detail.html",
            username=get_username(self),
            current_page="sessions",
            session=session,
            messages=messages,
        )


class SessionEditTitleHandler(tornado.web.RequestHandler):
    """修改会话标题"""

    def post(self):
        if not require_admin(self):
            return
        conv_id = _int_arg(self, "id")
        title = self.get_body_argument("title", "").strip()
        if title:
            SessionRepository.update_title(conv_id, title)
        self.redirect(f"/admin/session/detail?id={conv_id}")


class SessionEditTagsHandler(tornado.web.RequestHandler):
    """修改会话标记"""

    def post(self):
        if not require_admin(self):
            return
        conv_id = _int_arg(self, "id")
        tags = self.get_body_argument("tags", "").strip()
        SessionRepository.update_tags(conv_id, tags)
        self.redirect(f"/admin/session/detail?id={conv_id}")


class SessionArchiveHandler(tornado.web.RequestHandler):
    """归档/取消归档"""

    def post(self):
        if not require_admin(self):
            return
        conv_id = _int_arg(self, "id")
        action = self.get_body_argument("action", "archive").strip()
        if action == "unarchive":
            SessionRepository.unarchive(conv_id)
        else:
            SessionRepository.archive(conv_id)
        self.redirect(f"/admin/session/detail?id={conv_id}")


class SessionDeleteHandler(tornado.web.RequestHandler):
    """删除会话"""

    def post(self):
        if not require_admin(self):
            return
        conv_id = _int_arg(self, "id")
        SessionRepository.delete(conv_id)
        self.redirect("/admin/sessions")


class SessionBatchDeleteHandler(tornado.web.RequestHandler):
    """批量删除会话"""

    def post(self):
        if not require_admin(self):
            return
        ids_str = self.get_body_argument("ids", "").strip()
        if ids_str:
            ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
            if ids:
                SessionRepository.batch_delete(ids)
        self.redirect("/admin/sessions")


class SessionExportHandler(tornado.web.RequestHandler):
    """导出会话 — JSON"""

    def get(self):
        if not require_admin(self):
            return
        conv_id = _int_arg(self, "id")
        fmt = self.get_argument("format", "json").strip()
        data = SessionRepository.to_json_export(conv_id)
        if not data:
            self.set_status(404)
            self.write("Session not found")
            return
        if fmt == "pdf":
            # 简易 PDF 导出：以文本形式返回对话（后续可集成正式 PDF 库）
            lines = [f"会话: {data['title']}", f"用户: {data['username']}",
                     f"时间: {data['created_at']}", "-" * 50]
            for m in data["messages"]:
                role_label = "用户" if m["role"] == "user" else "AI"
                lines.append(f"\n[{role_label}] {m['created_at']}:")
                lines.append(m["content"])
                lines.append("-" * 40)
            self.set_header("Content-Type", "text/plain; charset=utf-8")
            self.set_header("Content-Disposition",
                            f"attachment; filename=session_{conv_id}.txt")
            self.write("\n".join(lines))
            return
        # JSON 导出
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.set_header("Content-Disposition",
                        f"attachment; filename=session_{conv_id}.json")
        self.write(json_str)


class SessionStatsHandler(tornado.web.RequestHandler):
    """会话统计页"""

    def get(self):
        if not require_admin(self):
            return
        stats = SessionRepository.get_stats()
        self.render(
            "admin/session_stats.html",
            username=get_username(self),
            current_page="sessions",
            stats=stats,
        )
