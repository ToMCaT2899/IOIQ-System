# 舆情分析仓储类 — 分析结果 CRUD + 聚合统计 + 趋势查询 + 告警管理

import json
from app.models.db import get_connection


class SentimentRepository:
    """舆情分析结果 CRUD"""

    @staticmethod
    def create(source_type: str = "chat", source_id: int = 0,
               content: str = "", sentiment: str = "neutral",
               sentiment_score: float = 0.0, emotion_label: str = "",
               risk_level: str = "low", keywords: str = "[]",
               entities: str = "[]", hot_value: float = 0.0,
               source_user: str = "", source_title: str = "",
               analyzed_by: str = "rule", model_engine_id: int = 0,
               model_name: str = "", tokens_used: int = 0,
               duration_ms: int = 0) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO sentiment_analysis
                   (source_type, source_id, content, sentiment, sentiment_score,
                    emotion_label, risk_level, keywords, entities, hot_value,
                    source_user, source_title, analyzed_by, model_engine_id,
                    model_name, tokens_used, duration_ms)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (source_type, source_id, content, sentiment, sentiment_score,
                 emotion_label, risk_level, keywords, entities, hot_value,
                 source_user, source_title, analyzed_by, model_engine_id,
                 model_name, tokens_used, duration_ms)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def paginate(page: int = 1, page_size: int = 20,
                 sentiment: str = "", risk_level: str = "",
                 source_type: str = "", keyword: str = "",
                 date_from: str = "", date_to: str = ""):
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if sentiment:
            conditions.append("sentiment = ?")
            params.append(sentiment)
        if risk_level:
            conditions.append("risk_level = ?")
            params.append(risk_level)
        if source_type:
            conditions.append("source_type = ?")
            params.append(source_type)
        if keyword:
            conditions.append("(content LIKE ? OR keywords LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if date_from:
            conditions.append("created_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("created_at <= ?")
            params.append(date_to + " 23:59:59")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with get_connection() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM sentiment_analysis {where}", params
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"SELECT * FROM sentiment_analysis {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset)
            ).fetchall()
        return {"list": rows, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def delete(analysis_id: int):
        with get_connection() as conn:
            conn.execute("DELETE FROM sentiment_analysis WHERE id=?", (analysis_id,))
            conn.commit()

    @staticmethod
    def get_by_id(analysis_id: int):
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM sentiment_analysis WHERE id=?", (analysis_id,)
            ).fetchone()

    @staticmethod
    def get_recent(days: int = 7, limit: int = 100):
        """获取最近N天分析结果"""
        with get_connection() as conn:
            return conn.execute(
                """SELECT * FROM sentiment_analysis
                   WHERE created_at >= datetime('now', '-' || ? || ' days')
                   ORDER BY id DESC LIMIT ?""",
                (days, limit)
            ).fetchall()

    # ---- 聚合统计 ----

    @staticmethod
    def get_sentiment_distribution(days: int = 7):
        """情感分布统计（正面/中性/负面）"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT sentiment, COUNT(*) AS cnt
                   FROM sentiment_analysis
                   WHERE created_at >= datetime('now', '-' || ? || ' days')
                   GROUP BY sentiment""",
                (days,)
            ).fetchall()
        result = {"positive": 0, "neutral": 0, "negative": 0}
        for r in rows:
            result[r["sentiment"]] = r["cnt"]
        return result

    @staticmethod
    def get_risk_distribution(days: int = 7):
        """风险等级分布"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT risk_level, COUNT(*) AS cnt
                   FROM sentiment_analysis
                   WHERE created_at >= datetime('now', '-' || ? || ' days')
                   GROUP BY risk_level""",
                (days,)
            ).fetchall()
        result = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for r in rows:
            result[r["risk_level"]] = r["cnt"]
        return result

    @staticmethod
    def get_sentiment_trend(days: int = 14):
        """情感趋势（按天聚合）"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT DATE(created_at) AS d, sentiment, COUNT(*) AS cnt
                   FROM sentiment_analysis
                   WHERE created_at >= datetime('now', '-' || ? || ' days')
                   GROUP BY d, sentiment ORDER BY d""",
                (days,)
            ).fetchall()
        trend = {}
        for r in rows:
            d = r["d"]
            if d not in trend:
                trend[d] = {"positive": 0, "neutral": 0, "negative": 0}
            trend[d][r["sentiment"]] = r["cnt"]
        return [{"date": k, **v} for k, v in sorted(trend.items())]

    @staticmethod
    def get_hot_keywords(days: int = 7, limit: int = 30):
        """提取热门关键词（从 keywords JSON 聚合）"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT keywords FROM sentiment_analysis
                   WHERE created_at >= datetime('now', '-' || ? || ' days')
                     AND keywords IS NOT NULL AND keywords != '[]'
                   LIMIT 500""",
                (days,)
            ).fetchall()
        word_count = {}
        for r in rows:
            try:
                kws = json.loads(r["keywords"]) if isinstance(r["keywords"], str) else r["keywords"]
                for kw in kws:
                    w = kw.get("word", kw) if isinstance(kw, dict) else str(kw)
                    w = w.strip()
                    if w and len(w) >= 2:
                        word_count[w] = word_count.get(w, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [{"word": w, "count": c} for w, c in sorted_words]

    @staticmethod
    def get_source_distribution():
        """数据来源分布"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT source_type, COUNT(*) AS cnt FROM sentiment_analysis GROUP BY source_type"
            ).fetchall()
        return [{"name": r["source_type"], "value": r["cnt"]} for r in rows]

    @staticmethod
    def get_hot_value_trend(days: int = 7):
        """热度值趋势（按天平均值）"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT DATE(created_at) AS d, AVG(hot_value) AS avg_hot, MAX(hot_value) AS max_hot
                   FROM sentiment_analysis
                   WHERE created_at >= datetime('now', '-' || ? || ' days')
                   GROUP BY d ORDER BY d""",
                (days,)
            ).fetchall()
        return [{"date": r["d"], "avg": round(r["avg_hot"], 2), "max": round(r["max_hot"], 2)} for r in rows]

    @staticmethod
    def get_emotion_distribution(days: int = 7):
        """情绪标签分布"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT emotion_label, COUNT(*) AS cnt
                   FROM sentiment_analysis
                   WHERE created_at >= datetime('now', '-' || ? || ' days')
                     AND emotion_label IS NOT NULL AND emotion_label != ''
                   GROUP BY emotion_label ORDER BY cnt DESC LIMIT 10""",
                (days,)
            ).fetchall()
        return [{"name": r["emotion_label"], "value": r["cnt"]} for r in rows]


class SentimentAlertRepository:
    """舆情告警 CRUD"""

    @staticmethod
    def create(title: str, content: str = "", alert_type: str = "negative_surge",
               risk_level: str = "medium", keywords: str = "[]",
               affected_count: int = 0, trend_score: float = 0.0) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO sentiment_alerts
                   (title, content, alert_type, risk_level, keywords, affected_count, trend_score)
                   VALUES (?,?,?,?,?,?,?)""",
                (title, content, alert_type, risk_level, keywords, affected_count, trend_score)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_unread_count() -> int:
        with get_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) AS cnt FROM sentiment_alerts WHERE status='unread'"
            ).fetchone()["cnt"]

    @staticmethod
    def paginate(page: int = 1, page_size: int = 20,
                 status: str = "", risk_level: str = "",
                 alert_type: str = ""):
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if risk_level:
            conditions.append("risk_level = ?")
            params.append(risk_level)
        if alert_type:
            conditions.append("alert_type = ?")
            params.append(alert_type)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with get_connection() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM sentiment_alerts {where}", params
            ).fetchone()["cnt"]
            rows = conn.execute(
                f"SELECT * FROM sentiment_alerts {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset)
            ).fetchall()
        return {"list": rows, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def mark_read(alert_id: int, username: str = ""):
        with get_connection() as conn:
            conn.execute(
                """UPDATE sentiment_alerts SET status='read',
                   resolved_by=?, resolved_at=datetime('now')
                   WHERE id=?""",
                (username, alert_id)
            )
            conn.commit()

    @staticmethod
    def mark_all_read(username: str = ""):
        with get_connection() as conn:
            conn.execute(
                """UPDATE sentiment_alerts SET status='read',
                   resolved_by=?, resolved_at=datetime('now')
                   WHERE status='unread'""",
                (username,)
            )
            conn.commit()

    @staticmethod
    def delete(alert_id: int):
        with get_connection() as conn:
            conn.execute("DELETE FROM sentiment_alerts WHERE id=?", (alert_id,))
            conn.commit()

    @staticmethod
    def clear_all():
        with get_connection() as conn:
            conn.execute("DELETE FROM sentiment_alerts")
            conn.commit()
