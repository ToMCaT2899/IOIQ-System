# 接口管理控制器 — CRUD + 在线调试 + 统计 + 文档导出 + 调用日志

import json
import time
import tornado.web
import requests

from app.models.api_interface import ApiInterfaceRepository, ApiCallLogRepository
from app.utils.auth import require_admin, get_username




def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


class ApiListHandler(tornado.web.RequestHandler):
    """接口管理列表页"""

    def get(self):
        if not require_admin(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        result = ApiInterfaceRepository.paginate(page=page, page_size=20, keyword=keyword)
        total_pages = (result["total"] + 19) // 20
        # 每个接口附带调用统计
        for item in result["list"]:
            stats = ApiInterfaceRepository.get_stats(item["id"])
            item_dict = dict(item)
            item_dict["stats"] = stats
            result["list"][result["list"].index(item)] = item_dict
        self.render(
            "admin/api_list.html",
            username=get_username(self),
            current_page="api",
            **result,
            total_pages=total_pages,
            keyword=keyword,
        )


class ApiAddHandler(tornado.web.RequestHandler):
    """新增接口"""

    def get(self):
        if not require_admin(self):
            return
        self.render(
            "admin/api_edit.html",
            username=get_username(self),
            current_page="api",
            interface=None,
            is_add=True,
        )

    def post(self):
        if not require_admin(self):
            return
        name = self.get_body_argument("name", "").strip()
        path = self.get_body_argument("path", "").strip()
        method = self.get_body_argument("method", "GET").strip()
        description = self.get_body_argument("description", "").strip()
        params = self.get_body_argument("params", "{}").strip()
        headers = self.get_body_argument("headers", "{}").strip()
        auth_type = self.get_body_argument("auth_type", "none").strip()
        if name and path:
            ApiInterfaceRepository.create(name, path, method, description, params, headers, auth_type)
        self.redirect("/admin/api-interfaces")


class ApiEditHandler(tornado.web.RequestHandler):
    """编辑接口"""

    def get(self):
        if not require_admin(self):
            return
        interface_id = _int_arg(self, "id")
        interface = ApiInterfaceRepository.get_by_id(interface_id)
        if not interface:
            self.redirect("/admin/api-interfaces")
            return
        self.render(
            "admin/api_edit.html",
            username=get_username(self),
            current_page="api",
            interface=interface,
            is_add=False,
        )

    def post(self):
        if not require_admin(self):
            return
        interface_id = _int_arg(self, "id")
        interface = ApiInterfaceRepository.get_by_id(interface_id)
        if not interface:
            self.redirect("/admin/api-interfaces")
            return
        name = self.get_body_argument("name", "").strip()
        path = self.get_body_argument("path", "").strip()
        method = self.get_body_argument("method", "GET").strip()
        description = self.get_body_argument("description", "").strip()
        params = self.get_body_argument("params", "{}").strip()
        headers = self.get_body_argument("headers", "{}").strip()
        auth_type = self.get_body_argument("auth_type", "none").strip()
        if name and path:
            ApiInterfaceRepository.update(interface_id,
                name=name, path=path, method=method, description=description,
                params=params, headers=headers, auth_type=auth_type)
        self.redirect("/admin/api-interfaces")


class ApiDeleteHandler(tornado.web.RequestHandler):
    """删除接口（软删除）"""

    def post(self):
        if not require_admin(self):
            return
        interface_id = _int_arg(self, "id")
        ApiInterfaceRepository.delete(interface_id)
        self.redirect("/admin/api-interfaces")


class ApiDebugHandler(tornado.web.RequestHandler):
    """在线调试接口 — 模拟请求并 SSE 流式返回"""

    async def post(self):
        if not require_admin(self):
            return
        interface_id = _int_arg(self, "id")
        interface = ApiInterfaceRepository.get_by_id(interface_id)
        if not interface:
            self.set_status(404)
            self.finish()
            return

        # 解析自定义参数
        body = json.loads(self.request.body or "{}")
        custom_params = body.get("params", {})
        custom_headers = body.get("headers", {})

        method = interface["method"].upper()
        url = interface["path"]

        # 合并请求头
        req_headers = {}
        try:
            req_headers = json.loads(interface["headers"] or "{}")
        except Exception:
            pass
        req_headers.update(custom_headers)

        # 合并参数（GET 用 params，POST/PUT 用 json body）
        params = {}
        try:
            params = json.loads(interface["params"] or "{}")
        except Exception:
            pass
        params.update(custom_params)

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")

        t0 = time.time()
        try:
            sse_data = json.dumps({
                "type": "status",
                "content": f"正在请求 {method} {url} ..."
            }, ensure_ascii=False)
            self.write(f"data: {sse_data}\n\n")
            await self.flush()

            if method == "GET":
                resp = requests.get(url, headers=req_headers, params=params, timeout=30)
            elif method == "POST":
                resp = requests.post(url, headers=req_headers, json=params, timeout=30)
            elif method == "PUT":
                resp = requests.put(url, headers=req_headers, json=params, timeout=30)
            elif method == "DELETE":
                resp = requests.delete(url, headers=req_headers, timeout=30)
            elif method == "PATCH":
                resp = requests.patch(url, headers=req_headers, json=params, timeout=30)
            else:
                resp = requests.request(method, url, headers=req_headers, json=params, timeout=30)

            elapsed = int((time.time() - t0) * 1000)
            response_status = resp.status_code
            success = 1 if 200 <= response_status < 400 else 0

            # 截断过长响应
            response_body = resp.text[:5000]

            # 记录日志
            ApiCallLogRepository.create(
                interface_id=interface["id"],
                interface_name=interface["name"],
                method=method,
                path=url,
                request_params=json.dumps(params, ensure_ascii=False),
                request_headers=json.dumps(req_headers, ensure_ascii=False),
                response_status=response_status,
                response_body=response_body,
                response_time_ms=elapsed,
                success=success,
                error_message="" if success else f"HTTP {response_status}"
            )

            done_data = json.dumps({
                "type": "done",
                "status_code": response_status,
                "success": success == 1,
                "elapsed_ms": elapsed,
                "body": response_body,
                "headers": dict(resp.headers),
            }, ensure_ascii=False)
            self.write(f"data: {done_data}\n\n")
            await self.flush()

        except Exception as e:
            elapsed = int((time.time() - t0) * 1000)
            error_msg = str(e)
            ApiCallLogRepository.create(
                interface_id=interface["id"],
                interface_name=interface["name"],
                method=method,
                path=url,
                request_params=json.dumps(params, ensure_ascii=False),
                request_headers=json.dumps(req_headers, ensure_ascii=False),
                response_status=0,
                response_body="",
                response_time_ms=elapsed,
                success=0,
                error_message=error_msg
            )
            err_data = json.dumps({
                "type": "error",
                "content": f"请求失败：{error_msg}",
                "elapsed_ms": elapsed,
            }, ensure_ascii=False)
            self.write(f"data: {err_data}\n\n")
            await self.flush()


class ApiDebugPageHandler(tornado.web.RequestHandler):
    """在线调试页面"""

    def get(self):
        if not require_admin(self):
            return
        interface_id = _int_arg(self, "id")
        interface = ApiInterfaceRepository.get_by_id(interface_id)
        if not interface:
            self.redirect("/admin/api-interfaces")
            return
        stats = ApiInterfaceRepository.get_stats(interface_id)
        self.render(
            "admin/api_debug.html",
            username=get_username(self),
            current_page="api",
            interface=interface,
            stats=stats,
        )


class ApiStatsHandler(tornado.web.RequestHandler):
    """接口统计页"""

    def get(self):
        if not require_admin(self):
            return
        interface_id = _int_arg(self, "id")
        interface = None
        if interface_id:
            interface = ApiInterfaceRepository.get_by_id(interface_id)
        stats = ApiInterfaceRepository.get_stats(interface_id)
        self.render(
            "admin/api_stats.html",
            username=get_username(self),
            current_page="api",
            interface=interface,
            stats=stats,
        )


class ApiLogsHandler(tornado.web.RequestHandler):
    """接口调用日志列表"""

    def get(self):
        if not require_admin(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        interface_id = _int_arg(self, "interface_id", 0)
        result = ApiCallLogRepository.paginate(page=page, page_size=20, interface_id=interface_id)
        total_pages = (result["total"] + 19) // 20
        interfaces = ApiInterfaceRepository.get_all()
        self.render(
            "admin/api_logs.html",
            username=get_username(self),
            current_page="api",
            **result,
            total_pages=total_pages,
            interfaces=interfaces,
            filter_interface_id=interface_id,
        )


class ApiClearLogsHandler(tornado.web.RequestHandler):
    """清空日志"""

    def post(self):
        if not require_admin(self):
            return
        interface_id = _int_arg(self, "interface_id", 0)
        ApiCallLogRepository.clear_logs(interface_id)
        self.redirect("/admin/api-logs")


class ApiDocHandler(tornado.web.RequestHandler):
    """接口文档页面"""

    def get(self):
        if not require_admin(self):
            return
        interfaces = ApiInterfaceRepository.get_all()
        # 预解析 params 和 headers JSON（sqlite3.Row 转 dict）
        parsed = []
        for api in interfaces:
            api_dict = dict(api)
            try:
                api_dict["_params"] = json.loads(api_dict.get("params") or "{}")
            except Exception:
                api_dict["_params"] = {}
            try:
                api_dict["_headers"] = json.loads(api_dict.get("headers") or "{}")
            except Exception:
                api_dict["_headers"] = {}
            parsed.append(api_dict)
        interfaces = parsed
        self.render(
            "admin/api_doc.html",
            username=get_username(self),
            current_page="api",
            interfaces=interfaces,
        )


class ApiDocExportHandler(tornado.web.RequestHandler):
    """导出接口文档（Markdown 格式下载）"""

    def get(self):
        if not require_admin(self):
            return
        interfaces = ApiInterfaceRepository.get_all()
        lines = ["# IOIQ System API 接口文档\n"]
        lines.append(f"自动生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("---\n")

        for api in interfaces:
            lines.append(f"## {api['name']}\n")
            lines.append(f"- **路径**：`{api['method']} {api['path']}`\n")
            lines.append(f"- **描述**：{api['description'] or '无'}\n")
            lines.append(f"- **认证方式**：{api['auth_type']}\n")

            try:
                params = json.loads(api["params"] or "{}")
                if params:
                    lines.append(f"- **请求参数**：\n")
                    for k, v in params.items():
                        lines.append(f"  - `{k}`: {v}\n")
            except Exception:
                pass

            try:
                headers = json.loads(api["headers"] or "{}")
                if headers:
                    lines.append(f"- **请求头**：\n")
                    for k, v in headers.items():
                        lines.append(f"  - `{k}`: {v}\n")
            except Exception:
                pass

            stats = ApiInterfaceRepository.get_stats(api["id"])
            lines.append(f"- **调用统计**：总调用 {stats['total_calls']} 次 | 成功率 {stats['success_rate']}% | 平均响应 {stats['avg_response_ms']}ms\n")
            lines.append("\n---\n\n")

        content = "".join(lines)
        self.set_header("Content-Type", "text/markdown; charset=utf-8")
        self.set_header("Content-Disposition", "attachment; filename=api_doc.md")
        self.write(content)
