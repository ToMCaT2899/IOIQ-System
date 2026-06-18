# 前台用户认证控制器：登录、注册、登出

import tornado.web
from app.models.user import UserRepository
from app.models.db import get_connection


class WebLoginHandler(tornado.web.RequestHandler):
    """前台用户登录"""

    def get(self):
        self.render("web/login.html", error=None)

    def post(self):
        username = self.get_body_argument("username", "").strip()
        password = self.get_body_argument("password", "").strip()

        if not username or not password:
            self.render("web/login.html", error="请输入用户名和密码")
            return

        if UserRepository.verify_user(username, password):
            # 检查用户角色
            with get_connection() as conn:
                user = conn.execute(
                    "SELECT u.*, r.name AS role_name FROM users u LEFT JOIN roles r ON u.role_id=r.id WHERE u.username=?",
                    (username,)
                ).fetchone()

            self.set_secure_cookie("admin_user", username)

            role_name = user["role_name"] if user else ""
            # 超级管理员 / 普通管理员 → 后台管理
            if role_name in ("超级管理员", "普通管理员"):
                self.redirect("/admin/index")
            else:
                self.redirect("/chat")
        else:
            self.render("web/login.html", error="用户名或密码错误")


class WebRegisterHandler(tornado.web.RequestHandler):
    """前台用户注册"""

    def get(self):
        self.render("web/register.html", error=None, form={})

    def post(self):
        username = self.get_body_argument("username", "").strip()
        password = self.get_body_argument("password", "").strip()
        password_confirm = self.get_body_argument("password_confirm", "").strip()
        email = self.get_body_argument("email", "").strip()

        form_data = {"username": username, "email": email}

        if not username or not password:
            self.render("web/register.html", error="用户名和密码不能为空", form=form_data)
            return
        if len(username) < 3:
            self.render("web/register.html", error="用户名至少3个字符", form=form_data)
            return
        if len(password) < 4:
            self.render("web/register.html", error="密码至少4个字符", form=form_data)
            return
        if password != password_confirm:
            self.render("web/register.html", error="两次密码输入不一致", form=form_data)
            return

        # 创建用户
        success = UserRepository.create_user(username, password)
        if not success:
            self.render("web/register.html", error="用户名已存在，请更换", form=form_data)
            return

        # 设置邮箱 & 绑定普通用户角色
        with get_connection() as conn:
            if email:
                conn.execute("UPDATE users SET email=? WHERE username=?", (email, username))
            # 绑定普通用户角色
            role = conn.execute("SELECT id FROM roles WHERE name=?", ("普通用户",)).fetchone()
            if role:
                conn.execute("UPDATE users SET role_id=? WHERE username=?", (role["id"], username))
            conn.commit()

        # 注册成功自动登录
        self.set_secure_cookie("admin_user", username)
        self.redirect("/chat")


class WebLogoutHandler(tornado.web.RequestHandler):
    """前台登出"""

    def post(self):
        self.clear_cookie("admin_user")
        self.redirect("/login")
