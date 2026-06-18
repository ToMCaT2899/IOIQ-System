# 后台管理控制器：角色管理、功能管理、用户管理

import tornado.web
from app.models.user import UserRepository
from app.models.role import RoleRepository
from app.models.function import FunctionRepository
from app.utils.auth import require_admin, get_username


def _int_arg(handler, name: str, default: int = 0) -> int:
    """安全获取整数参数"""
    try:
        val = handler.get_argument(name, str(default))
        return int(val)
    except (ValueError, TypeError):
        return default


# ==================== 功能管理 ====================

class FuncListHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self): return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        result = FunctionRepository.paginate(page=page, page_size=20, keyword=keyword)
        total_pages = (result["total"] + 19) // 20
        self.render(
            "admin/func_list.html",
            username=get_username(self),
            current_page="functions",
            **result,
            total_pages=total_pages,
            keyword=keyword,
        )


class FuncAddHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self): return
        all_funcs = FunctionRepository.get_all(order_by_sort=True)
        self.render(
            "admin/func_edit.html",
            username=get_username(self),
            current_page="functions",
            func=None,
            all_funcs=all_funcs,
            is_add=True,
        )

    def post(self):
        if not require_admin(self): return
        parent_id = _int_arg(self, "parent_id", 0)
        name = self.get_body_argument("name", "").strip()
        code = self.get_body_argument("code", "").strip()
        icon = self.get_body_argument("icon", "").strip()
        path = self.get_body_argument("path", "").strip()
        sort_order = _int_arg(self, "sort_order", 0)
        if name and code:
            FunctionRepository.create(parent_id, name, code, icon, path, sort_order)
        self.redirect("/admin/functions")


class FuncEditHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self): return
        func_id = _int_arg(self, "id")
        func = FunctionRepository.get_by_id(func_id)
        if not func:
            self.redirect("/admin/functions")
            return
        all_funcs = FunctionRepository.get_all(order_by_sort=True)
        self.render(
            "admin/func_edit.html",
            username=get_username(self),
            current_page="functions",
            func=func,
            all_funcs=all_funcs,
            is_add=False,
        )

    def post(self):
        if not require_admin(self): return
        func_id = _int_arg(self, "id")
        parent_id = _int_arg(self, "parent_id", 0)
        name = self.get_body_argument("name", "").strip()
        code = self.get_body_argument("code", "").strip()
        icon = self.get_body_argument("icon", "").strip()
        path = self.get_body_argument("path", "").strip()
        sort_order = _int_arg(self, "sort_order", 0)
        if name and code and func_id:
            FunctionRepository.update(func_id, parent_id, name, code, icon, path, sort_order)
        self.redirect("/admin/functions")


class FuncDeleteHandler(tornado.web.RequestHandler):
    def post(self):
        if not require_admin(self): return
        func_id = _int_arg(self, "id")
        FunctionRepository.delete(func_id)
        self.redirect("/admin/functions")


# ==================== 角色管理 ====================

class RoleListHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self): return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        result = RoleRepository.paginate(page=page, page_size=20, keyword=keyword)
        total_pages = (result["total"] + 19) // 20
        self.render(
            "admin/role_list.html",
            username=get_username(self),
            current_page="roles",
            **result,
            total_pages=total_pages,
            keyword=keyword,
        )


class RoleAddHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self): return
        func_tree = FunctionRepository.get_tree()
        self.render(
            "admin/role_edit.html",
            username=get_username(self),
            current_page="roles",
            role=None,
            func_tree=func_tree,
            is_add=True,
            checked_ids=set(),
        )

    def post(self):
        if not require_admin(self): return
        name = self.get_body_argument("name", "").strip()
        description = self.get_body_argument("description", "").strip()
        function_ids = [int(fid) for fid in self.get_arguments("function_ids")]
        if name:
            role_id = RoleRepository.create(name, description)
            if function_ids:
                RoleRepository.set_functions(role_id, function_ids)
        self.redirect("/admin/roles")


class RoleEditHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self): return
        role_id = _int_arg(self, "id")
        role = RoleRepository.get_by_id(role_id)
        if not role:
            self.redirect("/admin/roles")
            return
        func_tree = FunctionRepository.get_tree()
        checked_ids = set(RoleRepository.get_function_ids(role_id)) if role else set()
        self.render(
            "admin/role_edit.html",
            username=get_username(self),
            current_page="roles",
            role=role,
            func_tree=func_tree,
            is_add=False,
            checked_ids=checked_ids,
        )

    def post(self):
        if not require_admin(self): return
        role_id = _int_arg(self, "id")
        role = RoleRepository.get_by_id(role_id)
        if role and role["is_system"] == 1:
            self.redirect("/admin/roles")
            return
        name = self.get_body_argument("name", "").strip()
        description = self.get_body_argument("description", "").strip()
        function_ids = [int(fid) for fid in self.get_arguments("function_ids")]
        if name and role_id:
            RoleRepository.update(role_id, name, description)
            RoleRepository.set_functions(role_id, function_ids)
        self.redirect("/admin/roles")


class RoleDeleteHandler(tornado.web.RequestHandler):
    def post(self):
        if not require_admin(self): return
        role_id = _int_arg(self, "id")
        role = RoleRepository.get_by_id(role_id)
        if role and role["is_system"] == 1:
            self.redirect("/admin/roles")
            return
        RoleRepository.delete(role_id)
        self.redirect("/admin/roles")


# ==================== 用户管理 ====================

class UserListHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self): return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        offset = (page - 1) * 20
        from app.models.db import get_connection
        with get_connection() as conn:
            if keyword:
                where = "WHERE u.username LIKE ?"
                params = (f"%{keyword}%",)
                total = conn.execute(f"SELECT COUNT(*) AS cnt FROM users u {where}", params).fetchone()["cnt"]
                rows = conn.execute(
                    f"SELECT u.*, r.name AS role_name FROM users u LEFT JOIN roles r ON u.role_id=r.id "
                    f"{where} ORDER BY u.id LIMIT 20 OFFSET ?", (*params, offset)
                ).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
                rows = conn.execute(
                    "SELECT u.*, r.name AS role_name FROM users u LEFT JOIN roles r ON u.role_id=r.id "
                    "ORDER BY u.id LIMIT 20 OFFSET ?", (offset,)
                ).fetchall()
        total_pages = (total + 19) // 20
        self.render(
            "admin/user_list.html",
            username=get_username(self),
            current_page="users",
            list=rows, total=total, page=page, page_size=20,
            total_pages=total_pages,
            keyword=keyword,
        )


class UserAddHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self): return
        roles = RoleRepository.get_all()
        self.render(
            "admin/user_edit.html",
            username=get_username(self),
            current_page="users",
            user=None,
            roles=roles,
            is_add=True,
        )

    def post(self):
        if not require_admin(self): return
        username = self.get_body_argument("username", "").strip()
        password = self.get_body_argument("password", "").strip()
        role_id = _int_arg(self, "role_id") or None
        if username and password:
            UserRepository.create_user(username, password)
            # 绑定角色
            from app.models.db import get_connection
            with get_connection() as conn:
                if role_id:
                    conn.execute("UPDATE users SET role_id=? WHERE username=?", (role_id, username))
                conn.commit()
        self.redirect("/admin/users")


class UserEditHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self): return
        user_id = _int_arg(self, "id")
        from app.models.db import get_connection
        with get_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            self.redirect("/admin/users")
            return
        roles = RoleRepository.get_all()
        self.render(
            "admin/user_edit.html",
            username=get_username(self),
            current_page="users",
            user=user,
            roles=roles,
            is_add=False,
        )

    def post(self):
        if not require_admin(self): return
        user_id = _int_arg(self, "id")
        username = self.get_body_argument("username", "").strip()
        role_id = _int_arg(self, "role_id") or None
        new_password = self.get_body_argument("new_password", "").strip()
        from app.models.db import get_connection
        with get_connection() as conn:
            updates = ["username=?", "role_id=?"]
            values = [username, role_id]
            if new_password:
                import secrets, hashlib
                salt = secrets.token_bytes(16)
                dk = hashlib.pbkdf2_hmac("sha256", new_password.encode("utf-8"), salt, 100_000)
                updates.append("password_hash=?")
                updates.append("salt=?")
                values.append(dk.hex())
                values.append(salt)
            values.append(user_id)
            conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=?", values)
            conn.commit()
        self.redirect("/admin/users")


class UserDeleteHandler(tornado.web.RequestHandler):
    def post(self):
        if not require_admin(self): return
        user_id = _int_arg(self, "id")
        # 不允许删除 admin
        from app.models.db import get_connection
        with get_connection() as conn:
            user = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
            if user and user["username"] != "admin":
                conn.execute("DELETE FROM users WHERE id=?", (user_id,))
                conn.commit()
        self.redirect("/admin/users")
