# 数据仓库控制器 — 瞭望采集结果管理

import tornado.web

from app.models.watch_result import WatchResultRepository
from app.utils.auth import require_admin, get_username
from app.models.deep_result import DeepResultRepository
from app.models.db import get_connection




def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


class DataWarehouseListHandler(tornado.web.RequestHandler):
    """数据仓库列表页 — 支持关键词/数据来源/时间范围筛选"""

    def get(self):
        if not require_admin(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        source = self.get_argument("source", "").strip()
        date_from = self.get_argument("date_from", "").strip()
        date_to = self.get_argument("date_to", "").strip()

        page_size = 20
        offset = (page - 1) * page_size

        with get_connection() as conn:
            # 动态构建 WHERE 条件
            conditions = []
            params = []

            if keyword:
                conditions.append("(keyword LIKE ? OR title LIKE ? OR snippet LIKE ?)")
                params.extend([f"%{keyword}%"] * 3)
            if source:
                conditions.append("source_name LIKE ?")
                params.append(f"%{source}%")
            if date_from:
                conditions.append("collected_at >= ?")
                params.append(date_from)
            if date_to:
                conditions.append("collected_at <= ?")
                params.append(date_to + " 23:59:59")

            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

            total = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM watch_results {where}", params
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"SELECT * FROM watch_results {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset)
            ).fetchall()

        # 获取所有来源列表（用于筛选下拉）
        with get_connection() as conn:
            source_rows = conn.execute(
                "SELECT DISTINCT source_name FROM watch_results WHERE source_name != '' ORDER BY source_name"
            ).fetchall()
            sources = [r["source_name"] for r in source_rows]

        total_pages = (total + page_size - 1) // page_size

        # 批量查询深度采集状态
        watch_ids = [r["id"] for r in rows] if rows else []
        deep_status_map = DeepResultRepository.get_batch_deep_status(watch_ids) if watch_ids else {}

        self.render(
            "admin/data_warehouse.html",
            username=get_username(self),
            current_page="warehouse",
            list=rows, total=total, page=page, page_size=page_size,
            total_pages=total_pages,
            keyword=keyword, source=source,
            date_from=date_from, date_to=date_to,
            sources=sources,
            deep_status_map=deep_status_map,
        )


class DataWarehouseDeleteHandler(tornado.web.RequestHandler):
    """单条删除"""

    def post(self):
        if not require_admin(self):
            return
        item_id = _int_arg(self, "id")
        with get_connection() as conn:
            conn.execute("DELETE FROM watch_results WHERE id=?", (item_id,))
            conn.commit()
        self.redirect(self.get_argument("next", "/admin/data-warehouse"))


class DataWarehouseBatchDeleteHandler(tornado.web.RequestHandler):
    """批量删除"""

    def post(self):
        if not require_admin(self):
            return
        ids_str = self.get_body_argument("ids", "").strip()
        if ids_str:
            ids = [int(x.strip()) for x in ids_str.split(",") if x.strip().isdigit()]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                with get_connection() as conn:
                    conn.execute(
                        f"DELETE FROM watch_results WHERE id IN ({placeholders})",
                        ids
                    )
                    conn.commit()
        self.redirect("/admin/data-warehouse")
