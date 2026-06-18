# AI 技能仓储类 — 技能 CRUD + 调用日志 + 统计 + 热更新缓存

import json
from app.models.db import get_connection

# 技能内存缓存（热更新：编辑保存后立即刷新）
_skill_cache = {}
_cache_loaded = False


def refresh_skill_cache():
    """热更新：重新加载全量技能到内存缓存"""
    global _skill_cache, _cache_loaded
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_skills WHERE status='enabled'"
        ).fetchall()
    _skill_cache = {row["id"]: dict(row) for row in rows}
    _cache_loaded = True


def get_skill_from_cache(skill_id: int):
    """从内存缓存读取技能（找不到则回表查）"""
    if not _cache_loaded:
        refresh_skill_cache()
    if skill_id in _skill_cache:
        return _skill_cache[skill_id]
    return AiSkillRepository.get_by_id(skill_id)


def get_all_skills_from_cache():
    """获取所有启用中的技能"""
    if not _cache_loaded:
        refresh_skill_cache()
    return list(_skill_cache.values())


class AiSkillRepository:
    """AI 技能 CRUD"""

    @staticmethod
    def create(name: str, description: str = "", category: str = "通用",
               trigger_keywords: str = "[]", model_engine_id: int = 0,
               model_name: str = "", prompt_template: str = "",
               status: str = "enabled", icon: str = "fa-tools",
               version: str = "1.0") -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO ai_skills
                   (name, description, category, trigger_keywords, model_engine_id,
                    model_name, prompt_template, status, icon, version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, description, category, trigger_keywords, model_engine_id,
                 model_name, prompt_template, status, icon, version)
            )
            conn.commit()
            skill_id = cursor.lastrowid
        refresh_skill_cache()
        return skill_id

    @staticmethod
    def get_by_id(skill_id: int):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM ai_skills WHERE id=?", (skill_id,)
            ).fetchone()

    @staticmethod
    def get_all(enabled_only: bool = False):
        with get_connection() as conn:
            if enabled_only:
                return conn.execute(
                    "SELECT * FROM ai_skills WHERE status='enabled' ORDER BY category, id DESC"
                ).fetchall()
            return conn.execute(
                "SELECT * FROM ai_skills ORDER BY category, id DESC"
            ).fetchall()

    @staticmethod
    def paginate(page: int = 1, page_size: int = 12, keyword: str = "", category: str = ""):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            conditions = []
            params = []
            if keyword:
                conditions.append("(name LIKE ? OR description LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])
            if category:
                conditions.append("category=?")
                params.append(category)
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            total = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM ai_skills {where}", params
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"SELECT * FROM ai_skills {where} ORDER BY category, id DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset)
            ).fetchall()
        return {"list": rows, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def get_categories():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM ai_skills ORDER BY category"
            ).fetchall()
        return [r["category"] for r in rows]

    @staticmethod
    def update(skill_id: int, **kwargs):
        allowed = [
            "name", "description", "category", "trigger_keywords",
            "model_engine_id", "model_name", "prompt_template", "status",
            "icon", "version"
        ]
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [skill_id]
        with get_connection() as conn:
            conn.execute(
                f"UPDATE ai_skills SET {set_clause}, updated_at=datetime('now') WHERE id=?",
                values
            )
            conn.commit()
        refresh_skill_cache()

    @staticmethod
    def delete(skill_id: int):
        with get_connection() as conn:
            conn.execute("DELETE FROM ai_skills WHERE id=?", (skill_id,))
            conn.commit()
        refresh_skill_cache()

    @staticmethod
    def increment_call(skill_id: int):
        with get_connection() as conn:
            conn.execute(
                "UPDATE ai_skills SET call_count = call_count + 1 WHERE id=?",
                (skill_id,)
            )
            conn.commit()

    @staticmethod
    def get_stats():
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) AS cnt FROM ai_skills").fetchone()["cnt"]
            enabled = conn.execute(
                "SELECT COUNT(*) AS cnt FROM ai_skills WHERE status='enabled'"
            ).fetchone()["cnt"]
            total_calls = conn.execute(
                "SELECT SUM(call_count) AS c FROM ai_skills"
            ).fetchone()["c"] or 0
            return {
                "total": total,
                "enabled": enabled,
                "disabled": total - enabled,
                "total_calls": total_calls,
            }


class SkillCallLogRepository:
    """技能调用日志"""

    @staticmethod
    def create(skill_id: int, skill_name: str, caller_type: str = "",
               caller_id: int = 0, caller_name: str = "",
               tokens_used: int = 0, duration_ms: int = 0,
               success: int = 1, error_message: str = "") -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO skill_call_logs
                   (skill_id, skill_name, caller_type, caller_id, caller_name,
                    tokens_used, duration_ms, success, error_message)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (skill_id, skill_name, caller_type, caller_id, caller_name,
                 tokens_used, duration_ms, success, error_message)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def paginate(page: int = 1, page_size: int = 20, skill_id: int = 0):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if skill_id:
                where, params = "WHERE skill_id=?", (skill_id,)
            else:
                where, params = "", ()
            total = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM skill_call_logs {where}", params
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"SELECT * FROM skill_call_logs {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset)
            ).fetchall()
        return {"list": rows, "total": total, "page": page, "page_size": page_size}
