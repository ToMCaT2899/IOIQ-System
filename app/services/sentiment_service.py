# 舆情分析服务 — 关键词提取 + 情感判定 + AI分析 + 趋势计算

import json
import re
import time
from typing import Optional

from app.models.db import get_connection
from app.models.sentiment import SentimentRepository, SentimentAlertRepository


# ============================================================
# 中文情感词典
# ============================================================

_POSITIVE_WORDS = {
    "好", "棒", "赞", "优秀", "喜欢", "满意", "高兴", "开心", "成功", "进步",
    "安全", "稳定", "提升", "增长", "突破", "领先", "创新", "优秀", "强大",
    "完美", "精彩", "出色", "卓越", "可靠", "信任", "信心", "利好", "庆祝",
    "支持", "感谢", "赞许", "鼓励", "期待", "希望", "乐观", "积极", "美好",
    "幸福", "健康", "繁荣", "发展", "优势", "机遇", "亮点", "荣誉", "称赞",
    "杰出", "非凡", "上乘", "优质", "顶尖", "前沿", "巅峰",
}

_NEGATIVE_WORDS = {
    "差", "烂", "糟", "坏", "失败", "错误", "严重", "问题", "风险", "危机",
    "亏损", "下降", "衰退", "裁员", "事故", "漏洞", "隐患", "威胁", "攻击",
    "欺诈", "造假", "丑闻", "腐败", "违法", "投诉", "质疑", "争议", "困扰",
    "损失", "暴跌", "崩盘", "裁员", "倒闭", "破产", "罚款", "诉讼", "调查",
    "污染", "事故", "爆炸", "火灾", "地震", "洪水", "疫情", "病毒", "死亡",
    "受伤", "伤亡", "失踪", "紧急", "警告", "恐慌", "焦虑", "担忧", "恐惧",
    "愤怒", "不满", "抗议", "抵制", "谴责", "批评", "指责", "攻击", "冲击",
    "压力", "困难", "困境", "危机", "威胁", "挑战", "萧条", "低迷", "恶化",
}

_NEGATION_WORDS = {"不", "没", "无", "非", "别", "未", "否", "勿", "休", "莫"}

# 风险关键词
_RISK_KEYWORDS = {
    "high": {"攻击", "黑客", "泄漏", "入侵", "伪造", "恶意", "钓鱼", "勒索",
             "病毒", "木马", "漏洞", "绕过了", "崩溃", "宕机", "瘫痪"},
    "medium": {"投诉", "举报", "违规", "异常", "波动", "异常波动", "延期",
               "召回", "下架", "约谈", "整改", "警告", "违规操作"},
    "low": {"建议", "反馈", "意见", "询问", "咨询", "了解", "关注"},
}


# ============================================================
# 关键词提取
# ============================================================

def extract_keywords(text: str, top_n: int = 10) -> list:
    """
    从文本中提取关键词（基于 TF-IDF 简化实现）。
    返回: [{"word": str, "weight": float}, ...]
    """
    if not text:
        return []

    # 中文分词简化：按常见分隔符切分
    segments = _simple_segment(text)

    # 词频统计
    word_freq = {}
    for seg in segments:
        if len(seg) < 2:
            continue
        if re.match(r'^[\d.,\-，。！？、：；""''（）()【】《》\s]+$', seg):
            continue
        word_freq[seg] = word_freq.get(seg, 0) + 1

    # 排序
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
    max_freq = sorted_words[0][1] if sorted_words else 1
    return [{"word": w, "weight": round(c / max_freq, 2)} for w, c in sorted_words]


def _simple_segment(text: str) -> list:
    """简易中文分词（2-gram + 停用词过滤）"""
    # 清理
    text = re.sub(r'[a-zA-Z0-9]+', ' ', text)
    text = re.sub(r'[^\u4e00-\u9fff\s]', '', text)

    # 停用词
    stop_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
                  "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
                  "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
                  "它", "们", "那", "些", "什么", "怎么", "如何", "吗", "呢", "吧",
                  "啊", "哦", "嗯", "哈", "呀", "嘛", "呗", "啦", "噢", "哟"}

    # 2-gram & 1-gram
    chars = list(text)
    result = []
    for i in range(len(chars) - 1):
        bigram = chars[i] + chars[i + 1]
        if bigram not in stop_words and len(bigram.strip()) == 2:
            result.append(bigram)

    return result


# ============================================================
# 情感分析
# ============================================================

def analyze_sentiment(text: str) -> dict:
    """
    基于词典的情感分析。
    返回: {"sentiment": "positive/neutral/negative", "score": float,
           "emotion_label": str, "risk_level": str}
    """
    if not text:
        return {"sentiment": "neutral", "score": 0.0, "emotion_label": "无",
                "risk_level": "low"}

    pos_count = 0
    neg_count = 0
    words_found = _simple_segment(text)

    for word in words_found:
        if word in _POSITIVE_WORDS:
            pos_count += 1
        if word in _NEGATIVE_WORDS:
            # 检查否定词
            neg_count += 1

    total = pos_count + neg_count
    if total == 0:
        sentiment = "neutral"
        score = 0.0
        emotion = "平静"
    else:
        score = (pos_count - neg_count) / (pos_count + neg_count)
        if score > 0.1:
            sentiment = "positive"
            emotion = "喜悦" if score > 0.5 else "满意"
        elif score < -0.1:
            sentiment = "negative"
            emotion = "愤怒" if score < -0.5 else "担忧"
        else:
            sentiment = "neutral"
            emotion = "平静"

    # 风险评估
    risk = _assess_risk(text, sentiment)

    return {
        "sentiment": sentiment,
        "score": round(score, 2),
        "emotion_label": emotion,
        "risk_level": risk,
    }


def _assess_risk(text: str, sentiment: str) -> str:
    """评估内容风险等级"""
    if sentiment == "negative":
        for word, level in [("攻击", "critical"), ("黑客", "critical"),
                            ("泄漏", "critical"), ("危机", "high"),
                            ("事故", "high"), ("欺诈", "high")]:
            if word in text:
                return level if word in ("攻击", "黑客", "泄漏") else "high"
        return "medium"
    for kw in _RISK_KEYWORDS["high"]:
        if kw in text:
            return "high"
    for kw in _RISK_KEYWORDS["medium"]:
        if kw in text:
            return "medium"
    return "low"


# ============================================================
# AI 驱动的舆情分析
# ============================================================

def analyze_with_ai(texts: list, model_engine_id: int = 0) -> dict:
    """
    使用 AI 模型批量分析文本情感。
    返回聚合结果。
    """
    try:
        from app.models.model_engine import ModelEngineRepository
        from openai import OpenAI

        model = None
        if model_engine_id:
            model = ModelEngineRepository.get_by_id(model_engine_id)
        if not model:
            model = ModelEngineRepository.get_default()
        if not model:
            return {"error": "没有可用的模型引擎"}

        batch_texts = texts[:20]  # 限制批次数

        client = OpenAI(
            api_key=model["api_key"] or "YOUR_API_KEY",
            base_url=model["api_base"] or "https://api.openai.com/v1"
        )

        prompt = _build_ai_prompt(batch_texts)
        response = client.chat.completions.create(
            model=model["model_name"] or "gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )

        content = response.choices[0].message.content
        results = _parse_ai_response(content, batch_texts)
        return {
            "results": results,
            "model_name": model["model_name"],
            "tokens_used": response.usage.total_tokens if response.usage else 0,
            "source": "ai",
        }
    except Exception as e:
        # 降级为规则引擎
        return {
            "results": [analyze_sentiment(t) for t in texts],
            "model_name": "rule-engine",
            "tokens_used": 0,
            "source": "rule(fallback)",
            "error": str(e),
        }


def _build_ai_prompt(texts: list) -> str:
    joined = "\n---\n".join([f"[{i}] {t[:200]}" for i, t in enumerate(texts)])
    return (
        "你是一个舆情分析专家。请对以下文本逐一进行情感分析和风险评估。\n\n"
        "对每条文本返回 JSON 格式：\n"
        "{\"index\": 编号, \"sentiment\": \"positive/neutral/negative\", "
        "\"score\": -1到1的分数, \"emotion_label\": \"情感标签\", "
        "\"risk_level\": \"low/medium/high/critical\", "
        "\"keywords\": [\"关键词1\", \"关键词2\"]}\n\n"
        f"{joined}\n\n"
        "请返回完整的 JSON 数组，不要包含任何其他文字。"
    )


def _parse_ai_response(content: str, texts: list) -> list:
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return [analyze_sentiment(t) for t in texts]
    except json.JSONDecodeError:
        # 尝试提取 JSON
        match = re.search(r'\[[\s\S]*\]', content)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return [analyze_sentiment(t) for t in texts]


def _format_keywords(kws: list) -> list:
    """将关键词列表格式化为统一结构"""
    if not kws:
        return []
    result = []
    for k in kws[:8]:
        if isinstance(k, dict):
            result.append({"word": k.get("word", str(k)), "weight": k.get("weight", 1)})
        else:
            result.append({"word": str(k), "weight": 1})
    return result


# ============================================================
# 批量分析调度
# ============================================================

def run_batch_analysis(source_type: str = "all",
                       model_engine_id: int = 0,
                       limit: int = 50) -> dict:
    """
    批量执行舆情分析：从数据源拉取待分析内容，执行情感分析，保存结果。
    """
    texts_info = _fetch_source_data(source_type, limit)
    if not texts_info:
        return {"analyzed": 0, "message": "没有待分析的数据"}

    t0 = time.time()
    texts = [t["content"] for t in texts_info]

    # 尝试 AI 分析，失败则降级规则引擎
    ai_result = analyze_with_ai(texts, model_engine_id)
    results = ai_result.get("results", [])

    saved = 0
    for i, info in enumerate(texts_info):
        if i < len(results):
            r = results[i]
            sentiment = r.get("sentiment", "neutral")
            score = float(r.get("score", 0))
            emotion = r.get("emotion_label", "")
            risk = r.get("risk_level", "low")
            kws = r.get("keywords", [])
        else:
            r = analyze_sentiment(info["content"])
            sentiment = r["sentiment"]
            score = r["score"]
            emotion = r["emotion_label"]
            risk = r["risk_level"]
            kws = [kw["word"] for kw in extract_keywords(info["content"], 5)]

        keywords_json = json.dumps(_format_keywords(kws), ensure_ascii=False)

        # 计算热度值
        hot = SentimentRepository._calc_hot_value(sentiment, risk, score) if hasattr(
            SentimentRepository, '_calc_hot_value') else abs(score) * 10

        SentimentRepository.create(
            source_type=info["source_type"],
            source_id=info["source_id"],
            content=info["content"][:500],
            sentiment=sentiment,
            sentiment_score=score,
            emotion_label=emotion,
            risk_level=risk,
            keywords=keywords_json,
            hot_value=hot,
            source_user=info.get("source_user", ""),
            source_title=info.get("source_title", ""),
            analyzed_by=ai_result.get("source", "rule"),
            model_engine_id=model_engine_id,
            model_name=ai_result.get("model_name", ""),
            tokens_used=ai_result.get("tokens_used", 0) // max(len(results), 1),
            duration_ms=int((time.time() - t0) * 1000) // max(len(results), 1),
        )
        saved += 1

    # 检查是否需要产生告警
    _check_alerts(saved)

    return {
        "analyzed": saved,
        "source": ai_result.get("source", "rule"),
        "duration_ms": int((time.time() - t0) * 1000),
        "message": f"已分析 {saved} 条数据",
    }


def _fetch_source_data(source_type: str, limit: int) -> list:
    """从各数据源拉取待分析内容"""
    results = []

    if source_type in ("all", "chat"):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT cm.id AS source_id, cm.content, u.username,
                          c.title
                   FROM chat_messages cm
                   JOIN conversations c ON cm.conversation_id = c.id
                   LEFT JOIN users u ON c.user_id = u.id
                   WHERE cm.role = 'user' AND cm.content != ''
                     AND cm.id NOT IN (
                         SELECT source_id FROM sentiment_analysis WHERE source_type='chat'
                     )
                   ORDER BY cm.id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        for r in rows:
            results.append({
                "source_type": "chat",
                "source_id": r["source_id"],
                "content": r["content"] or "",
                "source_user": r["username"] or "",
                "source_title": r["title"] or "",
            })

    if source_type in ("all", "watch"):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT id AS source_id, title, snippet, keyword AS source_user
                   FROM watch_results
                   WHERE (title != '' OR snippet != '')
                     AND id NOT IN (
                         SELECT source_id FROM sentiment_analysis WHERE source_type='watch'
                     )
                   ORDER BY id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        for r in rows:
            content = f"{r['title'] or ''} {r['snippet'] or ''}".strip()
            if content:
                results.append({
                    "source_type": "watch",
                    "source_id": r["source_id"],
                    "content": content[:500],
                    "source_user": r["source_user"] or "瞭望采集",
                    "source_title": r["title"] or "",
                })

    if source_type in ("all", "deep"):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT id AS source_id, title, content_summary
                   FROM deep_results
                   WHERE content_summary != ''
                     AND id NOT IN (
                         SELECT source_id FROM sentiment_analysis WHERE source_type='deep'
                     )
                   ORDER BY id DESC LIMIT ?""",
                (limit // 2,)
            ).fetchall()
        for r in rows:
            results.append({
                "source_type": "deep",
                "source_id": r["source_id"],
                "content": r["content_summary"][:500],
                "source_user": "深度采集",
                "source_title": r["title"] or "",
            })

    return results


def _check_alerts(recent_count: int):
    """检查是否需要产生告警"""
    if recent_count == 0:
        return

    dist = SentimentRepository.get_sentiment_distribution(days=1)
    total = dist["positive"] + dist["neutral"] + dist["negative"]
    if total == 0:
        return

    neg_ratio = dist["negative"] / total if total > 0 else 0

    # 负面占比 > 40% → 告警
    if neg_ratio > 0.4:
        exists = SentimentAlertRepository.paginate(
            page=1, page_size=1, alert_type="negative_surge"
        )
        # 避免重复告警（最近1小时内的不再创建）
        if exists["total"] > 0:
            latest = exists["list"][0]
            from datetime import datetime
            try:
                latest_time = datetime.strptime(latest["created_at"], "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - latest_time).seconds < 3600:
                    return
            except Exception:
                pass

        SentimentAlertRepository.create(
            title="负面舆情激增告警",
            content=f"最近1小时内负面情感占比达到 {neg_ratio:.0%}，系统检测到舆情异常波动。"
                     f"共分析 {total} 条内容，其中负面 {dist['negative']} 条。",
            alert_type="negative_surge",
            risk_level="high" if neg_ratio > 0.6 else "medium",
            keywords=json.dumps(["负面激增", "舆情预警"], ensure_ascii=False),
            affected_count=dist["negative"],
            trend_score=neg_ratio,
        )
