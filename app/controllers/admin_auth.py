# 后台管理认证控制器：登录、登出、会话管理

import tornado.web
from app.models.user import UserRepository
from app.models.db import init_db, seed_admin, get_connection


class AdminLoginHandler(tornado.web.RequestHandler):
    """后台登录页面 & 登录处理"""

    def get(self):
        self.render("admin/login.html", error=None)

    def post(self):
        username = self.get_body_argument("username", "").strip()
        password = self.get_body_argument("password", "").strip()

        if not username or not password:
            self.render("admin/login.html", error="请输入用户名和密码")
            return

        if UserRepository.verify_user(username, password):
            # 检查用户角色，仅管理员可登录后台
            with get_connection() as conn:
                user = conn.execute(
                    "SELECT r.name AS role_name FROM users u "
                    "LEFT JOIN roles r ON u.role_id = r.id "
                    "WHERE u.username = ?",
                    (username,)
                ).fetchone()
            role_name = user["role_name"] if user else ""
            if role_name not in ("超级管理员", "普通管理员"):
                self.render("admin/login.html", error="该账号无后台管理权限，请使用管理员账号登录")
                return

            self.set_secure_cookie("admin_user", username)
            self.redirect("/admin/index")
        else:
            self.render("admin/login.html", error="用户名或密码错误")


import json
from app.models.dashboard_screen import DashboardRepository
from app.models.db import get_engine


class AdminIndexHandler(tornado.web.RequestHandler):
    """后台主页（控制台）"""

    def get(self):
        user = self.get_secure_cookie("admin_user")
        if not user:
            self.redirect("/admin/login")
            return
        username = user.decode("utf-8") if isinstance(user, bytes) else user
        self.render("admin/index.html", username=username, current_page="dashboard")


class AdminStatsHandler(tornado.web.RequestHandler):
    """控制台实时统计数据 API"""

    def get(self):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.set_header("Cache-Control", "no-cache, no-store, must-revalidate")
        try:
            metrics = DashboardRepository.get_core_metrics()
            with get_connection() as conn:
                sentiment_count = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM sentiment_analysis"
                ).fetchone()["cnt"]
            data = {
                "watch_sources": metrics.get("watch_sources", 0),
                "data_entries": metrics.get("messages", 0),
                "chat_sessions": metrics.get("conversations", 0),
                "sentiment_analysis": sentiment_count,
                "users": metrics.get("users", 0),
                "tokens": metrics.get("tokens", 0),
                "skills": metrics.get("skills", 0),
                "engine": get_engine(),
                "timestamp": metrics.get("timestamp", 0),
            }
            self.write({"ok": True, "data": data})
        except Exception as e:
            self.write({"ok": False, "error": str(e)})


class AdminLogoutHandler(tornado.web.RequestHandler):
    """后台登出"""

    def post(self):
        self.clear_cookie("admin_user")
        self.redirect("/admin/login")
