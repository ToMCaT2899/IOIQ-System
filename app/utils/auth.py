# 统一权限守卫 — 后台接口必须同时满足：已登录 + 管理员角色

from app.models.db import get_connection


# 角色名缓存（避免每次请求都查数据库）
_admin_role_names = ("超级管理员", "普通管理员")


def get_username(handler) -> str:
    """从 cookie 中获取当前用户名"""
    cookie = handler.get_secure_cookie("admin_user")
    if not cookie:
        return ""
    return cookie.decode() if isinstance(cookie, bytes) else cookie


def is_admin(username: str) -> bool:
    """检查用户是否拥有管理员角色"""
    if not username:
        return False
    with get_connection() as conn:
        row = conn.execute(
            "SELECT r.name AS role_name FROM users u "
            "LEFT JOIN roles r ON u.role_id = r.id "
            "WHERE u.username = ?",
            (username,)
        ).fetchone()
    return (row["role_name"] in _admin_role_names) if row else False


def require_admin(handler) -> bool:
    """管理后台权限守卫：未登录→跳转登录页，非管理员→跳转用户端

    用法：
        if not require_admin(self):
            return
    """
    username = get_username(handler)
    if not username:
        handler.redirect("/admin/login")
        return False
    if not is_admin(username):
        handler.render("admin/login.html", error="该账号无后台管理权限，请使用管理员账号登录")
        return False
    return True
