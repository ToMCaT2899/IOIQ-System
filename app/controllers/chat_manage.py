# 对话管理控制器 — 消息列表/上下文/筛选/审核/导出/统计

import json
import tornado.web

from app.models.chat_manage import ChatManageRepository
from app.models.session_manage import SessionRepository


def _require_login(handler):
    if not handler.get_secure_cookie("admin_user"):
        handler.redirect("/admin/login")
        return False
    return True


def _get_current_user(handler):
    cookie = handler.get_secure_cookie("admin_user")
    return cookie.decode() if cookie else ""


def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


class ChatListHandler(tornado.web.RequestHandler):
    """对话消息列表页"""

    def get(self):
        if not _require_login(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        user_id = _int_arg(self, "user_id", 0)
        role = self.get_argument("role", "").strip()
        conversation_id = _int_arg(self, "conversation_id", 0)
        review_status = self.get_argument("review_status", "").strip()
        date_from = self.get_argument("date_from", "").strip()
        date_to = self.get_argument("date_to", "").strip()
        result = ChatManageRepository.paginate(
            page=page, page_size=20,
            keyword=keyword, user_id=user_id,
            role=role, conversation_id=conversation_id,
            review_status=review_status,
            date_from=date_from, date_to=date_to,
        )
        total_pages = (result["total"] + 19) // 20
        stats = ChatManageRepository.get_stats()
        users = ChatManageRepository.get_user_list()
        self.render(
            "admin/chat_list.html",
            username=_get_current_user(self),
            current_page="chats",
            **result,
            total_pages=total_pages,
            keyword=keyword, user_id=user_id,
            role=role, conversation_id=conversation_id,
            review_status=review_status,
            date_from=date_from, date_to=date_to,
            stats=stats, users=users,
        )


class ChatDeleteHandler(tornado.web.RequestHandler):
    """删除单条消息"""

    def post(self):
        if not _require_login(self):
            return
        msg_id = _int_arg(self, "id")
        ChatManageRepository.delete(msg_id)
        ref = self.request.headers.get("Referer", "/admin/chats")
        self.redirect(ref)


class ChatBatchDeleteHandler(tornado.web.RequestHandler):
    """批量删除消息"""

    def post(self):
        if not _require_login(self):
            return
        ids_str = self.get_body_argument("ids", "").strip()
        if ids_str:
            ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
            if ids:
                ChatManageRepository.batch_delete(ids)
        self.redirect("/admin/chats")


class ChatReviewHandler(tornado.web.RequestHandler):
    """设置审核状态"""

    def post(self):
        if not _require_login(self):
            return
        ids_str = self.get_body_argument("ids", "").strip()
        status = self.get_body_argument("review_status", "normal").strip()
        if ids_str:
            ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
            if ids:
                ChatManageRepository.batch_review_status(ids, status)
        self.redirect("/admin/chats")


class ChatScanHandler(tornado.web.RequestHandler):
    """敏感词扫描"""

    def post(self):
        if not _require_login(self):
            return
        hits = ChatManageRepository.auto_flag_sensitive()
        count = len(hits) if hits else 0
        self.redirect("/admin/chats")


class ChatContextHandler(tornado.web.RequestHandler):
    """查看消息上下文链路"""

    def get(self):
        if not _require_login(self):
            return
        msg_id = _int_arg(self, "id")
        msg = ChatManageRepository.get_by_id(msg_id)
        if not msg:
            self.redirect("/admin/chats")
            return
        # 获取同会话所有消息
        messages = SessionRepository.get_messages(msg["conversation_id"])
        # 获取会话信息
        session = SessionRepository.get_by_id(msg["conversation_id"])
        self.render(
            "admin/chat_context.html",
            username=_get_current_user(self),
            current_page="chats",
            msg=msg,
            messages=messages,
            session=session,
            highlight_id=msg_id,
        )


class ChatExportHandler(tornado.web.RequestHandler):
    """导出对话消息"""

    def get(self):
        if not _require_login(self):
            return
        result = ChatManageRepository.paginate(page=1, page_size=10000)
        export_data = []
        for r in result["list"]:
            export_data.append({
                "id": r["id"],
                "conversation_id": r["conversation_id"],
                "conv_title": r["conv_title"],
                "username": r["username"],
                "role": r["role"],
                "content": r["content"],
                "tokens_used": r["tokens_used"],
                "review_status": r["review_status"],
                "created_at": r["created_at"],
            })
        json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.set_header("Content-Disposition", "attachment; filename=chat_messages.json")
        self.write(json_str)


class ChatStatsHandler(tornado.web.RequestHandler):
    """对话消息统计页"""

    def get(self):
        if not _require_login(self):
            return
        stats = ChatManageRepository.get_stats()
        # 获取审核统计
        auto_hits = ChatManageRepository.scan_sensitive()
        self.render(
            "admin/chat_stats.html",
            username=_get_current_user(self),
            current_page="chats",
            stats=stats,
            sensitive_hits_count=len(auto_hits),
        )
