# 角色仓储类

import sqlite3

from app.models.db import get_connection


class RoleRepository:
    """角色 CRUD 操作"""

    @staticmethod
    def create(name: str, description: str = "", is_system: int = 0) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO roles (name, description, is_system) VALUES (?, ?, ?)",
                (name, description, is_system)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_by_id(role_id: int):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()

    @staticmethod
    def get_all():
        with get_connection() as conn:
            return conn.execute("SELECT * FROM roles ORDER BY id").fetchall()

    @staticmethod
    def update(role_id: int, name: str, description: str):
        with get_connection() as conn:
            conn.execute(
                "UPDATE roles SET name=?, description=? WHERE id=?",
                (name, description, role_id)
            )
            conn.commit()

    @staticmethod
    def delete(role_id: int) -> bool:
        """删除角色，系统内置角色不可删除"""
        role = RoleRepository.get_by_id(role_id)
        if not role or role["is_system"] == 1:
            return False
        with get_connection() as conn:
            # 删除关联的功能权限
            conn.execute("DELETE FROM role_functions WHERE role_id=?", (role_id,))
            # 解除用户绑定
            conn.execute("UPDATE users SET role_id=NULL WHERE role_id=?", (role_id,))
            conn.execute("DELETE FROM roles WHERE id=?", (role_id,))
            conn.commit()
        return True

    @staticmethod
    def paginate(page: int = 1, page_size: int = 20, keyword: str = ""):
        """分页查询 + 模糊搜索"""
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                where = "WHERE name LIKE ? OR description LIKE ?"
                params = (f"%{keyword}%", f"%{keyword}%")
                total = conn.execute(f"SELECT COUNT(*) AS cnt FROM roles {where}", params).fetchone()["cnt"]
                rows = conn.execute(f"SELECT * FROM roles {where} ORDER BY id LIMIT ? OFFSET ?", (*params, page_size, offset)).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) AS cnt FROM roles").fetchone()["cnt"]
                rows = conn.execute("SELECT * FROM roles ORDER BY id LIMIT ? OFFSET ?", (page_size, offset)).fetchall()
        return {"list": rows, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def set_functions(role_id: int, function_ids: list):
        """设置角色的功能权限（先删后插）"""
        with get_connection() as conn:
            conn.execute("DELETE FROM role_functions WHERE role_id=?", (role_id,))
            for fid in function_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO role_functions (role_id, function_id) VALUES (?, ?)",
                    (role_id, fid)
                )
            conn.commit()

    @staticmethod
    def get_function_ids(role_id: int) -> list:
        """获取角色已分配的功能 ID 列表"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT function_id FROM role_functions WHERE role_id=?", (role_id,)
            ).fetchall()
        return [r["function_id"] for r in rows]
