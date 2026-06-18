# 对话会话 & 消息仓储类

from app.models.db import get_connection


class ConversationRepository:
    """对话会话 CRUD"""

    @staticmethod
    def create(user_id: int, title: str = "新对话", model_engine_id: int = 0, model_name: str = "") -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO conversations (user_id, title, model_engine_id, model_name) VALUES (?, ?, ?, ?)",
                (user_id, title, model_engine_id, model_name)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_by_user(user_id: int):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM conversations WHERE user_id=? ORDER BY updated_at DESC",
                (user_id,)
            ).fetchall()

    @staticmethod
    def get_by_id(conv_id: int):
        with get_connection() as conn:
            return conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()

    @staticmethod
    def update_title(conv_id: int, title: str):
        with get_connection() as conn:
            conn.execute("UPDATE conversations SET title=?, updated_at=datetime('now') WHERE id=?", (title, conv_id))
            conn.commit()

    @staticmethod
    def update_model(conv_id: int, model_engine_id: int, model_name: str):
        with get_connection() as conn:
            conn.execute(
                "UPDATE conversations SET model_engine_id=?, model_name=?, updated_at=datetime('now') WHERE id=?",
                (model_engine_id, model_name, conv_id)
            )
            conn.commit()

    @staticmethod
    def touch(conv_id: int):
        with get_connection() as conn:
            conn.execute("UPDATE conversations SET updated_at=datetime('now') WHERE id=?", (conv_id,))
            conn.commit()

    @staticmethod
    def delete(conv_id: int):
        with get_connection() as conn:
            conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
            conn.commit()


class ChatMessageRepository:
    """对话消息 CRUD"""

    @staticmethod
    def add(conversation_id: int, role: str, content: str, tokens_used: int = 0) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO chat_messages (conversation_id, role, content, tokens_used) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, tokens_used)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_by_conversation(conversation_id: int):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM chat_messages WHERE conversation_id=? ORDER BY id",
                (conversation_id,)
            ).fetchall()

    @staticmethod
    def get_last_n(conversation_id: int, n: int = 20):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM chat_messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
                (conversation_id, n)
            ).fetchall()[::-1]  # 反转回正序

    @staticmethod
    def get_last_message_id(user_id: int):
        """获取用户最后一条消息所在会话的ID，用于回连"""
        with get_connection() as conn:
            row = conn.execute(
                """SELECT cm.conversation_id FROM chat_messages cm
                   JOIN conversations c ON cm.conversation_id = c.id
                   WHERE c.user_id = ? ORDER BY cm.id DESC LIMIT 1""",
                (user_id,)
            ).fetchone()
            return row["conversation_id"] if row else None
