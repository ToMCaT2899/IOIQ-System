# 功能/菜单仓储类

from app.models.db import get_connection


class FunctionRepository:
    """功能（菜单）CRUD 操作"""

    @staticmethod
    def create(parent_id: int, name: str, code: str, icon: str = "", path: str = "", sort_order: int = 0) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO functions (parent_id, name, code, icon, path, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
                (parent_id, name, code, icon, path, sort_order)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_by_id(func_id: int):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM functions WHERE id=?", (func_id,)).fetchone()

    @staticmethod
    def get_all(order_by_sort: bool = True):
        with get_connection() as conn:
            if order_by_sort:
                return conn.execute("SELECT * FROM functions ORDER BY parent_id, sort_order, id").fetchall()
            return conn.execute("SELECT * FROM functions ORDER BY id").fetchall()

    @staticmethod
    def get_tree():
        """获取树形结构菜单（顶级+子级）"""
        all_funcs = FunctionRepository.get_all(order_by_sort=True)
        tree = []
        for f in all_funcs:
            if f["parent_id"] == 0:
                item = dict(f)
                item["children"] = [dict(c) for c in all_funcs if c["parent_id"] == f["id"]]
                tree.append(item)
        return tree

    @staticmethod
    def update(func_id: int, parent_id: int, name: str, code: str, icon: str, path: str, sort_order: int):
        with get_connection() as conn:
            conn.execute(
                "UPDATE functions SET parent_id=?, name=?, code=?, icon=?, path=?, sort_order=? WHERE id=?",
                (parent_id, name, code, icon, path, sort_order, func_id)
            )
            conn.commit()

    @staticmethod
    def delete(func_id: int) -> bool:
        """删除功能（级联删除子功能和角色关联）"""
        func = FunctionRepository.get_by_id(func_id)
        if not func:
            return False
        with get_connection() as conn:
            # 删除子功能
            children = conn.execute("SELECT id FROM functions WHERE parent_id=?", (func_id,)).fetchall()
            for child in children:
                conn.execute("DELETE FROM role_functions WHERE function_id=?", (child["id"],))
                conn.execute("DELETE FROM functions WHERE id=?", (child["id"],))
            # 删除自身关联和记录
            conn.execute("DELETE FROM role_functions WHERE function_id=?", (func_id,))
            conn.execute("DELETE FROM functions WHERE id=?", (func_id,))
            conn.commit()
        return True

    @staticmethod
    def paginate(page: int = 1, page_size: int = 20, keyword: str = ""):
        """分页查询 + 模糊搜索"""
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                where = "WHERE f.name LIKE ? OR f.code LIKE ?"
                params = (f"%{keyword}%", f"%{keyword}%")
                total = conn.execute(f"SELECT COUNT(*) AS cnt FROM functions f {where}", params).fetchone()["cnt"]
                rows = conn.execute(
                    f"SELECT f.*, p.name AS parent_name FROM functions f LEFT JOIN functions p ON f.parent_id=p.id "
                    f"{where} ORDER BY f.parent_id, f.sort_order, f.id LIMIT ? OFFSET ?",
                    (*params, page_size, offset)
                ).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) AS cnt FROM functions").fetchone()["cnt"]
                rows = conn.execute(
                    "SELECT f.*, p.name AS parent_name FROM functions f LEFT JOIN functions p ON f.parent_id=p.id "
                    "ORDER BY f.parent_id, f.sort_order, f.id LIMIT ? OFFSET ?",
                    (page_size, offset)
                ).fetchall()
        return {"list": rows, "total": total, "page": page, "page_size": page_size}
