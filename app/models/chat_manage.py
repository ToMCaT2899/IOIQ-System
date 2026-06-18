# 对话消息管理仓储 — 管理端分页/筛选/统计/审核/导出

import json
from app.models.db import get_connection

# 简易敏感词列表
_SENSITIVE_WORDS = {"暴力", "色情", "赌博", "毒品", "枪支", "诈骗"}


class ChatManageRepository:
    """管理端对话消息 CRUD"""

    @staticmethod
    def paginate(page: int = 1, page_size: int = 20,
                 keyword: str = "", user_id: int = 0,
                 role: str = "", conversation_id: int = 0,
                 review_status: str = "",
                 date_from: str = "", date_to: str = ""):
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if keyword:
            conditions.append("cm.content LIKE ?")
            params.append(f"%{keyword}%")
        if user_id:
            conditions.append("c.user_id = ?")
            params.append(user_id)
        if role:
            conditions.append("cm.role = ?")
            params.append(role)
        if conversation_id:
            conditions.append("cm.conversation_id = ?")
            params.append(conversation_id)
        if review_status:
            conditions.append("cm.review_status = ?")
            params.append(review_status)
        if date_from:
            conditions.append("cm.created_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("cm.created_at <= ?")
            params.append(date_to + " 23:59:59")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with get_connection() as conn:
            total = conn.execute(
                f"""SELECT COUNT(*) AS cnt FROM chat_messages cm
                    JOIN conversations c ON cm.conversation_id = c.id
                    LEFT JOIN users u ON c.user_id = u.id
                    {where}""",
                params
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"""SELECT cm.*, c.title AS conv_title, c.user_id,
                    u.username
                    FROM chat_messages cm
                    JOIN conversations c ON cm.conversation_id = c.id
                    LEFT JOIN users u ON c.user_id = u.id
                    {where}
                    ORDER BY cm.id DESC
                    LIMIT ? OFFSET ?""",
                (*params, page_size, offset)
            ).fetchall()
        return {"list": rows, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def get_by_id(msg_id: int):
        with get_connection() as conn:
            return conn.execute(
                """SELECT cm.*, c.title AS conv_title, c.user_id,
                   u.username
                   FROM chat_messages cm
                   JOIN conversations c ON cm.conversation_id = c.id
                   LEFT JOIN users u ON c.user_id = u.id
                   WHERE cm.id=?""",
                (msg_id,)
            ).fetchone()

    @staticmethod
    def delete(msg_id: int):
        with get_connection() as conn:
            conn.execute("DELETE FROM chat_messages WHERE id=?", (msg_id,))
            conn.commit()

    @staticmethod
    def batch_delete(ids: list):
        with get_connection() as conn:
            placeholders = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM chat_messages WHERE id IN ({placeholders})", ids)
            conn.commit()

    @staticmethod
    def set_review_status(msg_id: int, status: str):
        with get_connection() as conn:
            conn.execute(
                "UPDATE chat_messages SET review_status=? WHERE id=?",
                (status, msg_id)
            )
            conn.commit()

    @staticmethod
    def batch_review_status(ids: list, status: str):
        with get_connection() as conn:
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE chat_messages SET review_status=? WHERE id IN ({placeholders})",
                (status, *ids)
            )
            conn.commit()

    @staticmethod
    def get_stats():
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) AS cnt FROM chat_messages").fetchone()["cnt"]
            user_msg = conn.execute(
                "SELECT COUNT(*) AS cnt FROM chat_messages WHERE role='user'"
            ).fetchone()["cnt"]
            ai_msg = conn.execute(
                "SELECT COUNT(*) AS cnt FROM chat_messages WHERE role='assistant'"
            ).fetchone()["cnt"]
            total_tokens = conn.execute(
                "SELECT SUM(tokens_used) AS c FROM chat_messages"
            ).fetchone()["c"] or 0
            flagged = conn.execute(
                "SELECT COUNT(*) AS cnt FROM chat_messages WHERE review_status='flagged'"
            ).fetchone()["cnt"]
            return {
                "total": total,
                "user_messages": user_msg,
                "ai_messages": ai_msg,
                "total_tokens": total_tokens,
                "flagged": flagged,
            }

    @staticmethod
    def get_user_list():
        with get_connection() as conn:
            return conn.execute(
                """SELECT DISTINCT u.id, u.username
                   FROM users u
                   JOIN conversations c ON c.user_id = u.id
                   JOIN chat_messages cm ON cm.conversation_id = c.id
                   ORDER BY u.username"""
            ).fetchall()

    @staticmethod
    def check_sensitive(content: str) -> list:
        """检查敏感词，返回命中的词汇列表"""
        if not content:
            return []
        return [w for w in _SENSITIVE_WORDS if w in content]

    @staticmethod
    def scan_sensitive():
        """扫描最新100条消息的敏感词"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, content, review_status FROM chat_messages ORDER BY id DESC LIMIT 100"
            ).fetchall()
        hits = []
        for r in rows:
            matched = ChatManageRepository.check_sensitive(r["content"] or "")
            if matched and r["review_status"] == "normal":
                hits.append({"id": r["id"], "words": matched})
        return hits

    @staticmethod
    def auto_flag_sensitive():
        """自动标记含敏感词的消息"""
        hits = ChatManageRepository.scan_sensitive()
        ids = [h["id"] for h in hits]
        if ids:
            ChatManageRepository.batch_review_status(ids, "flagged")
        return hits
