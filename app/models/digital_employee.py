# 数字员工仓储类 — 员工 CRUD + 版本管理 + 统计

from app.models.db import get_connection


class DigitalEmployeeRepository:
    """数字员工 CRUD"""

    @staticmethod
    def create(name: str, avatar: str = "", role_name: str = "", greeting: str = "",
               skills: str = "[]", model_engine_id: int = 0, model_name: str = "",
               system_prompt: str = "", status: str = "enabled", version: str = "1.0") -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO digital_employees
                   (name, avatar, role_name, greeting, skills, model_engine_id, model_name,
                    system_prompt, status, version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, avatar, role_name, greeting, skills, model_engine_id, model_name,
                 system_prompt, status, version)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_by_id(employee_id: int):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM digital_employees WHERE id=?", (employee_id,)
            ).fetchone()

    @staticmethod
    def get_all(enabled_only: bool = False):
        with get_connection() as conn:
            if enabled_only:
                return conn.execute(
                    "SELECT * FROM digital_employees WHERE status='enabled' ORDER BY id DESC"
                ).fetchall()
            return conn.execute(
                "SELECT * FROM digital_employees ORDER BY id DESC"
            ).fetchall()

    @staticmethod
    def paginate(page: int = 1, page_size: int = 12, keyword: str = ""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                where = "WHERE name LIKE ? OR role_name LIKE ?"
                params = (f"%{keyword}%", f"%{keyword}%")
                total = conn.execute(
                    f"SELECT COUNT(*) AS cnt FROM digital_employees {where}", params
                ).fetchone()["cnt"]
                rows = conn.execute(
                    f"SELECT * FROM digital_employees {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                    (*params, page_size, offset)
                ).fetchall()
            else:
                total = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM digital_employees"
                ).fetchone()["cnt"]
                rows = conn.execute(
                    "SELECT * FROM digital_employees ORDER BY id DESC LIMIT ? OFFSET ?",
                    (page_size, offset)
                ).fetchall()
        return {"list": rows, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def update(employee_id: int, **kwargs):
        allowed = [
            "name", "avatar", "role_name", "greeting", "skills",
            "model_engine_id", "model_name", "system_prompt", "status", "version"
        ]
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [employee_id]
        with get_connection() as conn:
            conn.execute(
                f"UPDATE digital_employees SET {set_clause}, updated_at=datetime('now') WHERE id=?",
                values
            )
            conn.commit()

    @staticmethod
    def delete(employee_id: int):
        with get_connection() as conn:
            conn.execute("DELETE FROM digital_employees WHERE id=?", (employee_id,))
            conn.commit()

    @staticmethod
    def increment_stats(employee_id: int, tokens: int = 0, duration_ms: int = 0):
        with get_connection() as conn:
            conn.execute(
                """UPDATE digital_employees
                   SET total_calls = total_calls + 1,
                       total_tokens = total_tokens + ?,
                       total_duration_ms = total_duration_ms + ?
                   WHERE id=?""",
                (tokens, duration_ms, employee_id)
            )
            conn.commit()

    @staticmethod
    def get_stats(employee_id: int = 0):
        with get_connection() as conn:
            if employee_id:
                row = conn.execute(
                    "SELECT total_calls, total_tokens, total_duration_ms FROM digital_employees WHERE id=?",
                    (employee_id,)
                ).fetchone()
                if not row:
                    return {"total_calls": 0, "total_tokens": 0, "total_duration_ms": 0, "avg_duration_ms": 0}
                avg = int(row["total_duration_ms"] / row["total_calls"]) if row["total_calls"] > 0 else 0
                return {
                    "total_calls": row["total_calls"],
                    "total_tokens": row["total_tokens"],
                    "total_duration_ms": row["total_duration_ms"],
                    "avg_duration_ms": avg,
                }
            else:
                row = conn.execute(
                    "SELECT SUM(total_calls) AS c, SUM(total_tokens) AS t, SUM(total_duration_ms) AS d FROM digital_employees"
                ).fetchone()
                c, t, d = row["c"] or 0, row["t"] or 0, row["d"] or 0
                return {
                    "total_calls": c,
                    "total_tokens": t,
                    "total_duration_ms": d,
                    "avg_duration_ms": int(d / c) if c > 0 else 0,
                }


class EmployeeVersionRepository:
    """数字员工版本 CRUD"""

    @staticmethod
    def create(employee_id: int, version: str, system_prompt: str,
               skills: str = "[]", change_log: str = "") -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO employee_versions (employee_id, version, system_prompt, skills, change_log)
                   VALUES (?, ?, ?, ?, ?)""",
                (employee_id, version, system_prompt, skills, change_log)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_by_employee(employee_id: int):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM employee_versions WHERE employee_id=? ORDER BY id DESC",
                (employee_id,)
            ).fetchall()

    @staticmethod
    def get_latest(employee_id: int):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM employee_versions WHERE employee_id=? ORDER BY id DESC LIMIT 1",
                (employee_id,)
            ).fetchone()
