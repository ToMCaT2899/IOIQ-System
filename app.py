# 主入口程序：加载程序、路由注册、静态资源配置、数据库初始化、服务器启动

import os
import tornado.web
import tornado.ioloop
from tornado.httpserver import HTTPServer

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 控制器导入
from app.controllers.admin_auth import AdminLoginHandler, AdminIndexHandler, AdminLogoutHandler
from app.controllers.admin_manage import (
    FuncListHandler, FuncAddHandler, FuncEditHandler, FuncDeleteHandler,
    RoleListHandler, RoleAddHandler, RoleEditHandler, RoleDeleteHandler,
    UserListHandler, UserAddHandler, UserEditHandler, UserDeleteHandler,
)
from app.controllers.model_engine import (
    ModelListHandler, ModelAddHandler, ModelEditHandler, ModelDeleteHandler,
    ModelSetDefaultHandler, ModelChatHandler, ModelChatSSEHandler,
)
from app.controllers.watch_source import (
    WatchSourceListHandler, WatchSourceAddHandler, WatchSourceEditHandler, WatchSourceDeleteHandler,
)
from app.controllers.watch_collect import (
    WatchCollectPageHandler, WatchCollectSourcesHandler,
    WatchCollectFetchHandler, WatchCollectSaveHandler,
)
from app.controllers.data_warehouse import (
    DataWarehouseListHandler, DataWarehouseDeleteHandler, DataWarehouseBatchDeleteHandler,
)
from app.controllers.deep_collect import (
    DeepCollectListHandler, DeepCollectSSEHandler, DeepCollectDetailHandler,
)
from app.controllers.web_auth import WebLoginHandler, WebRegisterHandler, WebLogoutHandler
from app.controllers.web_chat import ChatPageHandler, ChatSSEHandler, ChatHistoryHandler, ChatDeleteHandler
from app.controllers.api_manage import (
    ApiListHandler, ApiAddHandler, ApiEditHandler, ApiDeleteHandler,
    ApiDebugHandler, ApiDebugPageHandler, ApiStatsHandler,
    ApiLogsHandler, ApiClearLogsHandler, ApiDocHandler, ApiDocExportHandler,
)
from app.controllers.digital_employee import (
    EmployeeListHandler, EmployeeAddHandler, EmployeeEditHandler, EmployeeDeleteHandler,
    EmployeeToggleStatusHandler, EmployeeChatHandler, EmployeeChatSSEHandler, EmployeeStatsHandler,
)
from app.controllers.skill_manage import (
    SkillListHandler, SkillAddHandler, SkillEditHandler, SkillDeleteHandler,
    SkillToggleHandler, SkillRefreshHandler, SkillStatsHandler, SkillMarketHandler,
)
from app.controllers.session_manage import (
    SessionListHandler, SessionDetailHandler, SessionEditTitleHandler,
    SessionEditTagsHandler, SessionArchiveHandler, SessionDeleteHandler,
    SessionBatchDeleteHandler, SessionExportHandler, SessionStatsHandler,
)
from app.controllers.chat_manage import (
    ChatListHandler, ChatDeleteHandler, ChatBatchDeleteHandler,
    ChatReviewHandler, ChatScanHandler, ChatContextHandler,
    ChatExportHandler, ChatStatsHandler,
)

# 数据库初始化 & 种子数据
from app.models.db import init_db, seed_admin, seed_roles_and_functions, seed_model_engines, seed_watch_sources


def create_app():
    """创建 Tornado Web 应用实例"""
    init_db()
    seed_admin()
    seed_roles_and_functions()
    seed_model_engines()
    seed_watch_sources()

    return tornado.web.Application(
        [
            # 前台路由（预留）
            ("/", IndexHandler),
            ("/index.html", IndexHandler),
            # 前台认证路由
            ("/login", WebLoginHandler),
            ("/register", WebRegisterHandler),
            ("/logout", WebLogoutHandler),
            # 前台 AI 问数对话路由
            ("/chat", ChatPageHandler),
            ("/chat/sse", ChatSSEHandler),
            ("/chat/history", ChatHistoryHandler),
            ("/chat/delete", ChatDeleteHandler),
            # 后台认证路由
            ("/admin/login", AdminLoginHandler),
            ("/admin/index", AdminIndexHandler),
            ("/admin/logout", AdminLogoutHandler),
            # 功能管理路由
            ("/admin/functions", FuncListHandler),
            ("/admin/function/add", FuncAddHandler),
            ("/admin/function/edit", FuncEditHandler),
            ("/admin/function/delete", FuncDeleteHandler),
            # 角色管理路由
            ("/admin/roles", RoleListHandler),
            ("/admin/role/add", RoleAddHandler),
            ("/admin/role/edit", RoleEditHandler),
            ("/admin/role/delete", RoleDeleteHandler),
            # 用户管理路由
            ("/admin/users", UserListHandler),
            ("/admin/user/add", UserAddHandler),
            ("/admin/user/edit", UserEditHandler),
            ("/admin/user/delete", UserDeleteHandler),
            # 模型引擎路由
            ("/admin/models", ModelListHandler),
            ("/admin/model/add", ModelAddHandler),
            ("/admin/model/edit", ModelEditHandler),
            ("/admin/model/delete", ModelDeleteHandler),
            ("/admin/model/set-default", ModelSetDefaultHandler),
            ("/admin/model/chat", ModelChatHandler),
            ("/admin/model/chat/sse", ModelChatSSEHandler),
            # 瞭望数据源路由
            ("/admin/watch-sources", WatchSourceListHandler),
            ("/admin/watch-source/add", WatchSourceAddHandler),
            ("/admin/watch-source/edit", WatchSourceEditHandler),
            ("/admin/watch-source/delete", WatchSourceDeleteHandler),
            # 瞭望采集路由
            ("/admin/watch-collect", WatchCollectPageHandler),
            ("/admin/watch-collect/sources", WatchCollectSourcesHandler),
            ("/admin/watch-collect/fetch", WatchCollectFetchHandler),
            ("/admin/watch-collect/save", WatchCollectSaveHandler),
            # 数据仓库路由
            ("/admin/data-warehouse", DataWarehouseListHandler),
            ("/admin/data-warehouse/delete", DataWarehouseDeleteHandler),
            ("/admin/data-warehouse/batch-delete", DataWarehouseBatchDeleteHandler),
            # 深度采集路由
            ("/admin/deep-collect", DeepCollectListHandler),
            ("/admin/deep-collect/sse", DeepCollectSSEHandler),
            (r"/admin/deep-collect/detail/(\d+)", DeepCollectDetailHandler),
            # 接口管理路由
            ("/admin/api-interfaces", ApiListHandler),
            ("/admin/api-interface/add", ApiAddHandler),
            ("/admin/api-interface/edit", ApiEditHandler),
            ("/admin/api-interface/delete", ApiDeleteHandler),
            ("/admin/api-interface/debug", ApiDebugPageHandler),
            ("/admin/api-interface/debug/sse", ApiDebugHandler),
            ("/admin/api-stats", ApiStatsHandler),
            ("/admin/api-logs", ApiLogsHandler),
            ("/admin/api-clear-logs", ApiClearLogsHandler),
            ("/admin/api-doc", ApiDocHandler),
            ("/admin/api-doc/export", ApiDocExportHandler),
            # 数字员工路由
            ("/admin/employees", EmployeeListHandler),
            ("/admin/employee/add", EmployeeAddHandler),
            ("/admin/employee/edit", EmployeeEditHandler),
            ("/admin/employee/delete", EmployeeDeleteHandler),
            ("/admin/employee/toggle-status", EmployeeToggleStatusHandler),
            ("/admin/employee/chat", EmployeeChatHandler),
            ("/admin/employee/chat/sse", EmployeeChatSSEHandler),
            ("/admin/employee-stats", EmployeeStatsHandler),
            # 技能管理路由
            ("/admin/skills", SkillListHandler),
            ("/admin/skill/add", SkillAddHandler),
            ("/admin/skill/edit", SkillEditHandler),
            ("/admin/skill/delete", SkillDeleteHandler),
            ("/admin/skill/toggle", SkillToggleHandler),
            ("/admin/skill-refresh", SkillRefreshHandler),
            ("/admin/skill-stats", SkillStatsHandler),
            ("/admin/skill-market", SkillMarketHandler),
            # 会话管理路由
            ("/admin/sessions", SessionListHandler),
            ("/admin/session/detail", SessionDetailHandler),
            ("/admin/session/edit-title", SessionEditTitleHandler),
            ("/admin/session/edit-tags", SessionEditTagsHandler),
            ("/admin/session/archive", SessionArchiveHandler),
            ("/admin/session/delete", SessionDeleteHandler),
            ("/admin/session/batch-delete", SessionBatchDeleteHandler),
            ("/admin/session/export", SessionExportHandler),
            ("/admin/session-stats", SessionStatsHandler),
            # 对话管理路由
            ("/admin/chats", ChatListHandler),
            ("/admin/chat/context", ChatContextHandler),
            ("/admin/chat/delete", ChatDeleteHandler),
            ("/admin/chat/batch-delete", ChatBatchDeleteHandler),
            ("/admin/chat/review", ChatReviewHandler),
            ("/admin/chat/scan", ChatScanHandler),
            ("/admin/chat/export", ChatExportHandler),
            ("/admin/chat-stats", ChatStatsHandler),
        ],
        # 静态文件配置
        static_path=os.path.join(PROJECT_ROOT, "app", "static"),
        template_path=os.path.join(PROJECT_ROOT, "app", "templates"),
        # Cookie 安全密钥（用于 secure_cookie）
        cookie_secret="ioiq_system_2024_secure_key_change_in_production",
        # 开启调试模式
        debug=True,
    )


class IndexHandler(tornado.web.RequestHandler):
    """前台首页 — 重定向到登录页"""

    def get(self):
        self.redirect("/login")


if __name__ == "__main__":
    application = create_app()
    server = HTTPServer(application)
    server.listen(10086)
    print("Server Started: http://localhost:10086/", flush=True)
    print("Admin Login : http://localhost:10086/admin/login  (admin/123456)", flush=True)
    tornado.ioloop.IOLoop.current().start()
