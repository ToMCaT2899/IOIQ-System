# 数智大屏控制器 — 主页 + 实时数据 API + SSE 推送

import json
import asyncio
import tornado.web

from app.models.dashboard_screen import DashboardRepository
from app.utils.auth import require_admin, get_username




def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


class DashboardScreenHandler(tornado.web.RequestHandler):
    """数智大屏主页"""

    def get(self):
        if not require_admin(self):
            return
        template = self.get_argument("template", "1").strip()
        self.render(
            "admin/dashboard_screen.html",
            username=get_username(self),
            current_page="dashboard_screen",
            template=template,
        )


class DashboardDataHandler(tornado.web.RequestHandler):
    """大屏数据 API（JSON）"""

    def get(self):
        if not require_admin(self):
            return
        data = DashboardRepository.get_all_data()
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.write(json.dumps(data, ensure_ascii=False))


class DashboardLiveHandler(tornado.web.RequestHandler):
    """大屏实时数据 SSE 推送 — 每秒推送最新指标"""

    async def get(self):
        if not require_admin(self):
            return
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.set_header("X-Accel-Buffering", "no")

        try:
            while True:
                data = DashboardRepository.get_all_data()
                payload = json.dumps(data, ensure_ascii=False)
                self.write(f"data: {payload}\n\n")
                await self.flush()
                await asyncio.sleep(5)  # 每5秒推送
        except tornado.iostream.StreamClosedError:
            pass
