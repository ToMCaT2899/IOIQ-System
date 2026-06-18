# 舆情分析控制器 — 分析执行 + 列表 + 报告 + 告警管理

import json
import tornado.web

from app.models.sentiment import SentimentRepository, SentimentAlertRepository
from app.services.sentiment_service import run_batch_analysis


def _require_login(handler):
    if not handler.get_secure_cookie("admin_user"):
        handler.redirect("/admin/login")
        return False
    return True


def _get_current_user(handler):
    cookie = handler.get_secure_cookie("admin_user")
    return cookie.decode() if cookie else ""


def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


class SentimentPageHandler(tornado.web.RequestHandler):
    """舆情分析主页面"""

    def get(self):
        if not _require_login(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        sentiment_filter = self.get_argument("sentiment", "").strip()
        risk_level = self.get_argument("risk_level", "").strip()
        source_type = self.get_argument("source_type", "").strip()
        keyword = self.get_argument("keyword", "").strip()

        result = SentimentRepository.paginate(
            page=page, page_size=20,
            sentiment=sentiment_filter,
            risk_level=risk_level,
            source_type=source_type,
            keyword=keyword,
        )
        total_pages = (result["total"] + 19) // 20

        # 统计概览
        dist = SentimentRepository.get_sentiment_distribution(7)
        risk_dist = SentimentRepository.get_risk_distribution(7)
        hot_keywords = SentimentRepository.get_hot_keywords(7, 15)
        alerts_unread = SentimentAlertRepository.get_unread_count()

        self.render(
            "admin/sentiment.html",
            username=_get_current_user(self),
            current_page="sentiment",
            **result,
            total_pages=total_pages,
            sentiment_filter=sentiment_filter,
            risk_level=risk_level,
            source_type=source_type,
            keyword=keyword,
            dist=dist,
            risk_dist=risk_dist,
            hot_keywords=hot_keywords,
            alerts_unread=alerts_unread,
        )


class SentimentAnalyzeHandler(tornado.web.RequestHandler):
    """执行舆情分析（SSE 流式）"""

    async def post(self):
        if not _require_login(self):
            return
        source_type = self.get_body_argument("source_type", "all").strip()
        model_engine_id = _int_arg(self, "model_engine_id", 0)
        limit = _int_arg(self, "limit", 50) or 50

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.set_header("X-Accel-Buffering", "no")

        # 进度事件
        start = json.dumps({
            "type": "start",
            "content": f"开始舆情分析，数据源: {source_type}，上限: {limit} 条...",
        }, ensure_ascii=False)
        self.write(f"data: {start}\n\n")
        await self.flush()

        try:
            result = run_batch_analysis(
                source_type=source_type,
                model_engine_id=model_engine_id,
                limit=limit,
            )
            done = json.dumps({
                "type": "done",
                **result,
            }, ensure_ascii=False)
            self.write(f"data: {done}\n\n")
            await self.flush()
        except Exception as e:
            error = json.dumps({
                "type": "error",
                "content": str(e),
            }, ensure_ascii=False)
            self.write(f"data: {error}\n\n")
            await self.flush()


class SentimentDataHandler(tornado.web.RequestHandler):
    """舆情数据 API（JSON）— 供前端图表使用"""

    def get(self):
        if not _require_login(self):
            return
        data = {
            "distribution": SentimentRepository.get_sentiment_distribution(7),
            "risk_distribution": SentimentRepository.get_risk_distribution(7),
            "trend": SentimentRepository.get_sentiment_trend(14),
            "hot_keywords": SentimentRepository.get_hot_keywords(7, 30),
            "source_distribution": SentimentRepository.get_source_distribution(),
            "hot_value_trend": SentimentRepository.get_hot_value_trend(7),
            "emotion_distribution": SentimentRepository.get_emotion_distribution(7),
            "alerts_unread": SentimentAlertRepository.get_unread_count(),
        }
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.write(json.dumps(data, ensure_ascii=False))


class SentimentDeleteHandler(tornado.web.RequestHandler):
    """删除单条分析结果"""

    def post(self):
        if not _require_login(self):
            return
        analysis_id = _int_arg(self, "id", 0)
        if analysis_id:
            SentimentRepository.delete(analysis_id)
        self.redirect("/admin/sentiment")


class SentimentReportHandler(tornado.web.RequestHandler):
    """生成舆情分析报告"""

    def get(self):
        if not _require_login(self):
            return
        dist = SentimentRepository.get_sentiment_distribution(7)
        risk_dist = SentimentRepository.get_risk_distribution(7)
        trend = SentimentRepository.get_sentiment_trend(7)
        hot_words = SentimentRepository.get_hot_keywords(7, 20)
        source_dist = SentimentRepository.get_source_distribution()
        alerts = SentimentAlertRepository.paginate(page=1, page_size=20, status="unread")

        self.render(
            "admin/sentiment_report.html",
            username=_get_current_user(self),
            current_page="sentiment",
            dist=dist,
            risk_dist=risk_dist,
            trend=trend,
            hot_words=hot_words,
            source_dist=source_dist,
            alerts=alerts,
        )


# ---- 告警管理 ----

class SentimentAlertsHandler(tornado.web.RequestHandler):
    """告警列表"""

    def get(self):
        if not _require_login(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        status = self.get_argument("status", "").strip()
        risk_level = self.get_argument("risk_level", "").strip()

        result = SentimentAlertRepository.paginate(
            page=page, page_size=20,
            status=status, risk_level=risk_level,
        )
        total_pages = (result["total"] + 19) // 20
        unread = SentimentAlertRepository.get_unread_count()

        self.render(
            "admin/sentiment_alerts.html",
            username=_get_current_user(self),
            current_page="sentiment",
            **result,
            total_pages=total_pages,
            status=status,
            risk_level=risk_level,
            unread=unread,
        )


class SentimentAlertMarkHandler(tornado.web.RequestHandler):
    """标记告警为已读"""

    def post(self):
        if not _require_login(self):
            return
        alert_id = _int_arg(self, "id", 0)
        username = _get_current_user(self)
        if alert_id:
            SentimentAlertRepository.mark_read(alert_id, username)
        self.redirect("/admin/sentiment/alerts")


class SentimentAlertMarkAllHandler(tornado.web.RequestHandler):
    """全部标记已读"""

    def post(self):
        if not _require_login(self):
            return
        username = _get_current_user(self)
        SentimentAlertRepository.mark_all_read(username)
        self.redirect("/admin/sentiment/alerts")


class SentimentAlertDeleteHandler(tornado.web.RequestHandler):
    """删除告警"""

    def post(self):
        if not _require_login(self):
            return
        alert_id = _int_arg(self, "id", 0)
        if alert_id:
            SentimentAlertRepository.delete(alert_id)
        self.redirect("/admin/sentiment/alerts")
