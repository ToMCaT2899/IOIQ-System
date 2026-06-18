# 会话管理仓储 — 管理端 CRUD + 筛选 + 统计 + 归档 + 导出

import json
import time
from app.models.db import get_connection


class SessionRepository:
    """管理端会话 CRUD（基于 conversations 表）"""

    @staticmethod
    def paginate(page: int = 1, page_size: int = 15,
                 keyword: str = "", user_id: int = 0,
                 status: str = "", date_from: str = "", date_to: str = ""):
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if keyword:
            conditions.append("(c.title LIKE ? OR u.username LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if user_id:
            conditions.append("c.user_id=?")
            params.append(user_id)
        if status:
            conditions.append("c.status=?")
            params.append(status)
        if date_from:
            conditions.append("c.created_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("c.created_at <= ?")
            params.append(date_to + " 23:59:59")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with get_connection() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM conversations c LEFT JOIN users u ON c.user_id = u.id {where}",
                params
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"""SELECT c.*, u.username,
                    (SELECT COUNT(*) FROM chat_messages WHERE conversation_id=c.id) AS message_count
                    FROM conversations c
                    LEFT JOIN users u ON c.user_id = u.id
                    {where}
                    ORDER BY c.updated_at DESC
                    LIMIT ? OFFSET ?""",
                (*params, page_size, offset)
            ).fetchall()
        return {"list": rows, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def get_by_id(conv_id: int):
        with get_connection() as conn:
            return conn.execute(
                """SELECT c.*, u.username,
                   (SELECT COUNT(*) FROM chat_messages WHERE conversation_id=c.id) AS message_count
                   FROM conversations c
                   LEFT JOIN users u ON c.user_id = u.id
                   WHERE c.id=?""",
                (conv_id,)
            ).fetchone()

    @staticmethod
    def get_messages(conv_id: int):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM chat_messages WHERE conversation_id=? ORDER BY id",
                (conv_id,)
            ).fetchall()

    @staticmethod
    def update_title(conv_id: int, title: str):
        with get_connection() as conn:
            conn.execute(
                "UPDATE conversations SET title=?, updated_at=datetime('now') WHERE id=?",
                (title, conv_id)
            )
            conn.commit()

    @staticmethod
    def update_tags(conv_id: int, tags: str):
        with get_connection() as conn:
            conn.execute(
                "UPDATE conversations SET tags=?, updated_at=datetime('now') WHERE id=?",
                (tags, conv_id)
            )
            conn.commit()

    @staticmethod
    def archive(conv_id: int):
        with get_connection() as conn:
            conn.execute(
                "UPDATE conversations SET status='archived', updated_at=datetime('now') WHERE id=?",
                (conv_id,)
            )
            conn.commit()

    @staticmethod
    def unarchive(conv_id: int):
        with get_connection() as conn:
            conn.execute(
                "UPDATE conversations SET status='active', updated_at=datetime('now') WHERE id=?",
                (conv_id,)
            )
            conn.commit()

    @staticmethod
    def delete(conv_id: int):
        with get_connection() as conn:
            conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
            conn.commit()

    @staticmethod
    def batch_delete(ids: list):
        with get_connection() as conn:
            placeholders = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM conversations WHERE id IN ({placeholders})", ids)
            conn.commit()

    @staticmethod
    def get_stats():
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) AS cnt FROM conversations").fetchone()["cnt"]
            active = conn.execute(
                "SELECT COUNT(*) AS cnt FROM conversations WHERE status='active'"
            ).fetchone()["cnt"]
            archived = conn.execute(
                "SELECT COUNT(*) AS cnt FROM conversations WHERE status='archived'"
            ).fetchone()["cnt"]
            total_msgs = conn.execute(
                "SELECT COUNT(*) AS cnt FROM chat_messages"
            ).fetchone()["cnt"]
            # 平均每会话消息数
            avg_rounds = 0
            if total > 0:
                avg_rounds = round(total_msgs / total, 1)
            return {
                "total": total,
                "active": active,
                "archived": archived,
                "total_messages": total_msgs,
                "avg_rounds": avg_rounds,
            }

    @staticmethod
    def get_user_list():
        """获取有会话的用户列表，用于筛选"""
        with get_connection() as conn:
            return conn.execute(
                """SELECT DISTINCT u.id, u.username
                   FROM users u JOIN conversations c ON c.user_id = u.id
                   ORDER BY u.username"""
            ).fetchall()

    @staticmethod
    def to_json_export(conv_id: int):
        """导出单个会话为 JSON 结构"""
        conv = SessionRepository.get_by_id(conv_id)
        if not conv:
            return None
        msgs = SessionRepository.get_messages(conv_id)
        return {
            "id": conv["id"],
            "title": conv["title"],
            "username": conv["username"],
            "user_id": conv["user_id"],
            "model_name": conv["model_name"],
            "status": conv["status"],
            "tags": conv["tags"],
            "message_count": conv["message_count"],
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
            "messages": [
                {
                    "id": m["id"],
                    "role": m["role"],
                    "content": m["content"],
                    "tokens_used": m["tokens_used"],
                    "created_at": m["created_at"],
                }
                for m in msgs
            ],
        }
