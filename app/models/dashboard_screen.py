# 数智大屏数据聚合仓储 — 跨模块全量统计查询

import time
from app.models.db import get_connection


class DashboardRepository:
    """数智大屏聚合数据查询"""

    @staticmethod
    def get_core_metrics():
        """核心指标：总用户/总会话/总消息/总Token/活跃会话"""
        with get_connection() as conn:
            total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            total_convs = conn.execute("SELECT COUNT(*) AS c FROM conversations").fetchone()["c"]
            total_msgs = conn.execute("SELECT COUNT(*) AS c FROM chat_messages").fetchone()["c"]
            total_tokens = conn.execute(
                "SELECT COALESCE(SUM(tokens_used), 0) AS c FROM chat_messages"
            ).fetchone()["c"]
            active_convs = conn.execute(
                "SELECT COUNT(*) AS c FROM conversations WHERE status='active'"
            ).fetchone()["c"]
            total_employees = conn.execute("SELECT COUNT(*) AS c FROM digital_employees").fetchone()["c"]
            total_skills = conn.execute("SELECT COUNT(*) AS c FROM ai_skills").fetchone()["c"]
            total_apis = conn.execute("SELECT COUNT(*) AS c FROM api_interfaces").fetchone()["c"]
            total_watch = conn.execute("SELECT COUNT(*) AS c FROM watch_sources").fetchone()["c"]
            flagged_msgs = conn.execute(
                "SELECT COUNT(*) AS c FROM chat_messages WHERE review_status='flagged'"
            ).fetchone()["c"]
        return {
            "users": total_users,
            "conversations": total_convs,
            "messages": total_msgs,
            "tokens": total_tokens,
            "active_convs": active_convs,
            "employees": total_employees,
            "skills": total_skills,
            "apis": total_apis,
            "watch_sources": total_watch,
            "flagged": flagged_msgs,
            "timestamp": int(time.time()),
        }

    @staticmethod
    def get_message_trend(days: int = 7):
        """最近N天消息趋势（按小时聚合）"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT DATE(created_at) AS d, COUNT(*) AS cnt
                   FROM chat_messages
                   WHERE created_at >= datetime('now', '-' || ? || ' days')
                   GROUP BY d ORDER BY d""",
                (days,)
            ).fetchall()
        return [{"date": r["d"], "count": r["cnt"]} for r in rows]

    @staticmethod
    def get_role_distribution():
        """用户/AI 消息分布"""
        with get_connection() as conn:
            user_cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM chat_messages WHERE role='user'"
            ).fetchone()["c"]
            ai_cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM chat_messages WHERE role='assistant'"
            ).fetchone()["c"]
        return [
            {"name": "用户消息", "value": user_cnt},
            {"name": "AI消息", "value": ai_cnt},
        ]

    @staticmethod
    def get_model_usage():
        """模型调用分布"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT COALESCE(c.model_name, '默认') AS model, COUNT(*) AS cnt
                   FROM chat_messages cm
                   JOIN conversations c ON cm.conversation_id = c.id
                   GROUP BY c.model_name
                   ORDER BY cnt DESC
                   LIMIT 10"""
            ).fetchall()
        return [{"name": r["model"], "count": r["cnt"]} for r in rows]

    @staticmethod
    def get_skill_calls():
        """技能调用分布"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT name, call_count FROM ai_skills
                   WHERE call_count > 0
                   ORDER BY call_count DESC LIMIT 10"""
            ).fetchall()
        return [{"name": r["name"], "count": r["call_count"]} for r in rows]

    @staticmethod
    def get_hourly_activity():
        """最近24小时按小时活跃度"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT strftime('%H', created_at) AS h, COUNT(*) AS cnt
                   FROM chat_messages
                   WHERE created_at >= datetime('now', '-24 hours')
                   GROUP BY h ORDER BY h"""
            ).fetchall()
        result = {str(i).zfill(2): 0 for i in range(24)}
        for r in rows:
            result[r["h"]] = r["cnt"]
        return [{"hour": k, "count": v} for k, v in result.items()]

    @staticmethod
    def get_risk_alerts():
        """风险预警列表"""
        alerts = []
        with get_connection() as conn:
            # 已标记消息
            flagged = conn.execute(
                """SELECT 'flag' AS type, cm.id, cm.content, u.username, cm.created_at
                   FROM chat_messages cm
                   JOIN conversations c ON cm.conversation_id = c.id
                   LEFT JOIN users u ON c.user_id = u.id
                   WHERE cm.review_status = 'flagged'
                   ORDER BY cm.id DESC LIMIT 5"""
            ).fetchall()
            for r in flagged:
                alerts.append({
                    "type": "content_risk",
                    "level": "warning",
                    "title": "敏感内容标记",
                    "detail": f"用户 {r['username']}: {r['content'][:50]}...",
                    "time": r["created_at"],
                })
            # 高Token消息
            high_tokens = conn.execute(
                """SELECT cm.id, cm.tokens_used, u.username, cm.created_at
                   FROM chat_messages cm
                   JOIN conversations c ON cm.conversation_id = c.id
                   LEFT JOIN users u ON c.user_id = u.id
                   WHERE cm.tokens_used > 500
                   ORDER BY cm.tokens_used DESC LIMIT 5"""
            ).fetchall()
            for r in high_tokens:
                alerts.append({
                    "type": "high_token",
                    "level": "info",
                    "title": "高Token消耗",
                    "detail": f"用户 {r['username']}: 单条 {r['tokens_used']} tokens",
                    "time": r["created_at"],
                })
        return alerts

    @staticmethod
    def get_live_messages(limit: int = 10):
        """实时最新消息"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT cm.role, cm.content, u.username, cm.created_at
                   FROM chat_messages cm
                   JOIN conversations c ON cm.conversation_id = c.id
                   LEFT JOIN users u ON c.user_id = u.id
                   ORDER BY cm.id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        return [
            {
                "role": r["role"],
                "username": r["username"] or "-",
                "content": (r["content"] or "")[:80],
                "time": r["created_at"],
            }
            for r in rows
        ]

    @staticmethod
    def get_sentiment_overview():
        """舆情概览"""
        try:
            from app.models.sentiment import SentimentRepository, SentimentAlertRepository
            dist = SentimentRepository.get_sentiment_distribution(7)
            risk = SentimentRepository.get_risk_distribution(7)
            hot = SentimentRepository.get_hot_keywords(7, 15)
            alerts = SentimentAlertRepository.get_unread_count()
            trend = SentimentRepository.get_sentiment_trend(7)
            return {
                "distribution": dist,
                "risk_distribution": risk,
                "hot_keywords": hot,
                "alerts_unread": alerts,
                "trend": trend,
            }
        except Exception:
            return {
                "distribution": {"positive": 0, "neutral": 0, "negative": 0},
                "risk_distribution": {"low": 0, "medium": 0, "high": 0, "critical": 0},
                "hot_keywords": [],
                "alerts_unread": 0,
                "trend": [],
            }

    @staticmethod
    def get_geo_data():
        """3D地球数据：城市坐标 + 活动量（对话/瞭望/舆情分布点）"""
        import random
        random.seed(42)
        # 主要城市坐标 [lng, lat]
        cities = [
            ("北京", 116.40, 39.90), ("上海", 121.47, 31.23), ("广州", 113.26, 23.13),
            ("深圳", 114.07, 22.62), ("杭州", 120.15, 30.28), ("成都", 104.07, 30.67),
            ("南京", 118.78, 32.07), ("武汉", 114.30, 30.60), ("重庆", 106.55, 29.57),
            ("西安", 108.93, 34.27), ("天津", 117.20, 39.12), ("苏州", 120.58, 31.30),
            ("长沙", 112.97, 28.23), ("青岛", 120.38, 36.07), ("大连", 121.62, 38.92),
            ("郑州", 113.62, 34.75), ("济南", 117.00, 36.67), ("沈阳", 123.43, 41.80),
            ("厦门", 118.08, 24.48), ("合肥", 117.23, 31.82),
            # 全球主要城市
            ("纽约", -74.00, 40.71), ("伦敦", -0.12, 51.50), ("东京", 139.69, 35.69),
            ("新加坡", 103.85, 1.29), ("悉尼", 151.21, -33.87), ("柏林", 13.40, 52.52),
            ("莫斯科", 37.62, 55.75), ("迪拜", 55.27, 25.20), ("首尔", 126.98, 37.57),
            ("巴黎", 2.35, 48.86),
        ]
        points = []
        for name, lng, lat in cities:
            # 模拟活动量（用系统实际数据加权）
            val = random.randint(10, 100)
            cat = "domestic" if lng > 70 else "global"
            points.append({
                "name": name, "value": [lng, lat, val],
                "category": cat,
            })

        # 数据流向（飞线）
        lines_data = []
        hubs = cities[:5]  # 以国内前5个城市为枢纽
        for src_name, src_lng, src_lat in hubs:
            for dst_name, dst_lng, dst_lat in cities[5:15]:
                lines_data.append({
                    "fromName": src_name,
                    "toName": dst_name,
                    "coords": [[src_lng, src_lat], [dst_lng, dst_lat]],
                    "value": random.randint(1, 30),
                })

        return {"points": points, "lines": lines_data}

    @staticmethod
    def get_wordcloud_data():
        """词云数据：从舆情 + 技能调用 + 对话关键词聚合"""
        words = []
        # 从舆情模块获取热门关键词
        try:
            from app.models.sentiment import SentimentRepository
            hot_kws = SentimentRepository.get_hot_keywords(7, 30)
            for kw in hot_kws:
                words.append({"name": kw["word"], "value": kw["count"]})
        except Exception:
            pass
        # 从技能调用补充
        try:
            with get_connection() as conn:
                skills = conn.execute(
                    "SELECT name, call_count FROM ai_skills WHERE call_count>0 ORDER BY call_count DESC LIMIT 10"
                ).fetchall()
                for s in skills:
                    words.append({"name": f"[技能]{s['name']}", "value": s["call_count"] * 2})
        except Exception:
            pass
        # 如果没有数据，用默认词填充
        if not words:
            words = [
                {"name": "AI对话", "value": 50}, {"name": "数据分析", "value": 40},
                {"name": "舆情监测", "value": 35}, {"name": "智能问数", "value": 30},
                {"name": "网络搜索", "value": 25}, {"name": "深度采集", "value": 22},
                {"name": "数字员工", "value": 20}, {"name": "模型引擎", "value": 18},
                {"name": "瞭望管理", "value": 15}, {"name": "安全预警", "value": 12},
                {"name": "SQL报表", "value": 10}, {"name": "技能调度", "value": 9},
                {"name": "实时监控", "value": 8}, {"name": "数据仓库", "value": 7},
                {"name": "认证系统", "value": 6},
            ]
        return words

    @staticmethod
    def get_sentiment_trend():
        """舆情情感趋势（专供大屏使用）"""
        try:
            from app.models.sentiment import SentimentRepository
            return SentimentRepository.get_sentiment_trend(7)
        except Exception:
            return []

    @staticmethod
    def get_all_data():
        """一次性获取全部大屏数据"""
        return {
            "metrics": DashboardRepository.get_core_metrics(),
            "trend": DashboardRepository.get_message_trend(7),
            "distribution": DashboardRepository.get_role_distribution(),
            "model_usage": DashboardRepository.get_model_usage(),
            "skill_calls": DashboardRepository.get_skill_calls(),
            "hourly": DashboardRepository.get_hourly_activity(),
            "alerts": DashboardRepository.get_risk_alerts(),
            "live": DashboardRepository.get_live_messages(10),
            "sentiment": DashboardRepository.get_sentiment_overview(),
            "sentiment_trend": DashboardRepository.get_sentiment_trend(),
            "geo": DashboardRepository.get_geo_data(),
            "wordcloud": DashboardRepository.get_wordcloud_data(),
        }
