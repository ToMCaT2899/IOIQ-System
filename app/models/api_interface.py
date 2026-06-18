# 接口管理仓储类 — 接口 CRUD + 调用日志 + 统计

import json
from app.models.db import get_connection


class ApiInterfaceRepository:
    """API 接口 CRUD"""

    @staticmethod
    def create(name: str, path: str, method: str = "GET", description: str = "",
               params: str = "{}", headers: str = "{}", auth_type: str = "none") -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO api_interfaces (name, path, method, description, params, headers, auth_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, path, method, description, params, headers, auth_type)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_by_id(interface_id: int):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM api_interfaces WHERE id=?", (interface_id,)).fetchone()

    @staticmethod
    def get_all():
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM api_interfaces WHERE status=1 ORDER BY id DESC"
            ).fetchall()

    @staticmethod
    def paginate(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                where = "WHERE (name LIKE ? OR path LIKE ?) AND status=1"
                params = (f"%{keyword}%", f"%{keyword}%")
                total = conn.execute(
                    f"SELECT COUNT(*) AS cnt FROM api_interfaces {where}", params
                ).fetchone()["cnt"]
                rows = conn.execute(
                    f"SELECT * FROM api_interfaces {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                    (*params, page_size, offset)
                ).fetchall()
            else:
                total = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM api_interfaces WHERE status=1"
                ).fetchone()["cnt"]
                rows = conn.execute(
                    "SELECT * FROM api_interfaces WHERE status=1 ORDER BY id DESC LIMIT ? OFFSET ?",
                    (page_size, offset)
                ).fetchall()
        return {"list": rows, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def update(interface_id: int, **kwargs):
        allowed = ["name", "path", "method", "description", "params", "headers", "auth_type"]
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k}=?" for k in updates.keys())
        values = list(updates.values()) + [interface_id]
        with get_connection() as conn:
            conn.execute(
                f"UPDATE api_interfaces SET {set_clause}, updated_at=datetime('now') WHERE id=?",
                values
            )
            conn.commit()

    @staticmethod
    def delete(interface_id: int):
        with get_connection() as conn:
            conn.execute("UPDATE api_interfaces SET status=0 WHERE id=?", (interface_id,))
            conn.commit()

    @staticmethod
    def get_stats(interface_id: int = 0):
        """获取接口调用统计"""
        with get_connection() as conn:
            where = "WHERE interface_id=?" if interface_id else ""
            params = (interface_id,) if interface_id else ()
            total = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM api_call_logs {where}", params
            ).fetchone()["cnt"]
            success = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM api_call_logs {where} AND success=1", params
            ).fetchone()["cnt"]
            avg_time = conn.execute(
                f"SELECT AVG(response_time_ms) AS avg FROM api_call_logs {where}", params
            ).fetchone()["avg"] or 0
            min_time = conn.execute(
                f"SELECT MIN(response_time_ms) AS mn FROM api_call_logs {where}", params
            ).fetchone()["mn"] or 0
            max_time = conn.execute(
                f"SELECT MAX(response_time_ms) AS mx FROM api_call_logs {where}", params
            ).fetchone()["mx"] or 0
        return {
            "total_calls": total,
            "success_calls": success,
            "fail_calls": total - success,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
            "avg_response_ms": int(avg_time),
            "min_response_ms": min_time,
            "max_response_ms": max_time,
        }


class ApiCallLogRepository:
    """接口调用日志 CRUD"""

    @staticmethod
    def create(interface_id: int, interface_name: str, method: str, path: str,
               request_params: str = "", request_headers: str = "",
               response_status: int = 0, response_body: str = "",
               response_time_ms: int = 0, success: int = 0, error_message: str = "") -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO api_call_logs
                   (interface_id, interface_name, method, path, request_params, request_headers,
                    response_status, response_body, response_time_ms, success, error_message)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (interface_id, interface_name, method, path, request_params, request_headers,
                 response_status, response_body, response_time_ms, success, error_message)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def paginate(page: int = 1, page_size: int = 20, interface_id: int = 0):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if interface_id:
                where = "WHERE interface_id=?"
                params = (interface_id,)
            else:
                where = ""
                params = ()
            total = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM api_call_logs {where}", params
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"SELECT * FROM api_call_logs {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset)
            ).fetchall()
        return {"list": rows, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def clear_logs(interface_id: int = 0):
        with get_connection() as conn:
            if interface_id:
                conn.execute("DELETE FROM api_call_logs WHERE interface_id=?", (interface_id,))
            else:
                conn.execute("DELETE FROM api_call_logs")
            conn.commit()
