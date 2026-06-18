# 舆情分析功能测试用例
# 运行方式: python test/test_sentiment.py

import os
import sys
import json

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.models.db import init_db
init_db()

from app.models.sentiment import SentimentRepository, SentimentAlertRepository
from app.services.sentiment_service import (
    analyze_sentiment, extract_keywords, _format_keywords
)


def test_sentiment_analysis():
    """测试 1: 情感分析"""
    print("=" * 60)
    print("测试 1: analyze_sentiment 情感分析")
    print("=" * 60)

    # 正面文本
    r = analyze_sentiment("这个系统真好用，非常棒，我很喜欢！")
    assert r["sentiment"] == "positive", f"应为 positive，实际: {r['sentiment']}"
    assert r["score"] > 0, f"得分应>0，实际: {r['score']}"
    print(f"  PASS 正面文本 → {r}")

    # 负面文本
    r = analyze_sentiment("系统有问题，数据风险很大，用户体验很差")
    assert r["sentiment"] == "negative", f"应为 negative，实际: {r['sentiment']}"
    assert r["score"] < 0, f"得分应<0，实际: {r['score']}"
    print(f"  PASS 负面文本 → {r}")

    # 中性文本
    r = analyze_sentiment("今天是星期五")
    assert r["sentiment"] == "neutral", f"应为 neutral，实际: {r['sentiment']}"
    print(f"  PASS 中性文本 → {r}")

    # 高风险文本
    r = analyze_sentiment("系统被黑客攻击了，数据泄漏")
    assert r.get("risk_level") in ("high", "critical"), f"风险等级应高: {r.get('risk_level')}"
    print(f"  PASS 高风险文本 → {r}")


def test_keyword_extraction():
    """测试 2: 关键词提取"""
    print("\n" + "=" * 60)
    print("测试 2: extract_keywords 关键词提取")
    print("=" * 60)

    text = "智能聊天系统需要支持网络搜索功能，模型引擎需要优化性能"
    kws = extract_keywords(text, 5)
    assert len(kws) > 0, "应提取到关键词"
    print(f"  PASS 关键词提取: {kws}")

    # 空文本
    kws = extract_keywords("", 5)
    assert len(kws) == 0, "空文本应返回空列表"
    print("  PASS 空文本提取")


def test_format_keywords():
    """测试 3: 关键词格式化"""
    print("\n" + "=" * 60)
    print("测试 3: _format_keywords 格式化")
    print("=" * 60)

    # dict 格式
    result = _format_keywords([{"word": "测试", "weight": 0.9}, {"word": "关键词", "weight": 0.5}])
    assert len(result) == 2
    assert result[0]["word"] == "测试"
    assert result[0]["weight"] == 0.9
    print(f"  PASS dict格式: {result}")

    # string 格式
    result = _format_keywords(["测试", "关键词"])
    assert result[0]["word"] == "测试"
    assert result[0]["weight"] == 1
    print(f"  PASS str格式: {result}")

    # 空列表
    result = _format_keywords([])
    assert result == []
    print("  PASS 空列表")


def test_repository_crud():
    """测试 4: 数据库 CRUD"""
    print("\n" + "=" * 60)
    print("测试 4: SentimentRepository CRUD")
    print("=" * 60)

    # 创建分析记录
    sid = SentimentRepository.create(
        source_type="chat",
        source_id=1,
        content="测试舆情内容，系统运行良好",
        sentiment="positive",
        sentiment_score=0.8,
        emotion_label="满意",
        risk_level="low",
        keywords=json.dumps([{"word": "系统", "weight": 0.9}, {"word": "良好", "weight": 0.8}], ensure_ascii=False),
        hot_value=7.5,
        source_user="test_user",
    )
    assert sid > 0, "创建应返回有效ID"
    print(f"  PASS 创建记录 ID={sid}")

    # 查询记录
    record = SentimentRepository.get_by_id(sid)
    assert record is not None
    assert record["sentiment"] == "positive"
    print(f"  PASS 查询记录: {dict(record)['sentiment']}")

    # 分页查询
    page = SentimentRepository.paginate(page=1, page_size=10)
    assert page["total"] > 0
    print(f"  PASS 分页: total={page['total']}")

    # 聚合查询
    dist = SentimentRepository.get_sentiment_distribution(7)
    assert "positive" in dist
    print(f"  PASS 情感分布: {dist}")

    risk = SentimentRepository.get_risk_distribution(7)
    print(f"  PASS 风险分布: {risk}")

    hot = SentimentRepository.get_hot_keywords(7, 5)
    print(f"  PASS 热门关键词: {hot}")

    # 删除记录
    SentimentRepository.delete(sid)
    record = SentimentRepository.get_by_id(sid)
    assert record is None
    print("  PASS 删除记录")


def test_alerts():
    """测试 5: 告警管理"""
    print("\n" + "=" * 60)
    print("测试 5: SentimentAlertRepository 告警")
    print("=" * 60)

    # 创建告警
    alert_id = SentimentAlertRepository.create(
        title="测试告警",
        content="检测到负面舆情激增",
        alert_type="negative_surge",
        risk_level="high",
        keywords=json.dumps(["测试"], ensure_ascii=False),
        affected_count=5,
        trend_score=0.6,
    )
    assert alert_id > 0
    print(f"  PASS 创建告警 ID={alert_id}")

    # 未读数量
    unread = SentimentAlertRepository.get_unread_count()
    assert unread > 0
    print(f"  PASS 未读告警: {unread}")

    # 分页
    page = SentimentAlertRepository.paginate(page=1, page_size=10)
    assert page["total"] >= 1
    print(f"  PASS 告警分页: total={page['total']}")

    # 标记已读
    SentimentAlertRepository.mark_read(alert_id, "admin")
    page = SentimentAlertRepository.paginate(page=1, page_size=10, status="read")
    assert page["total"] >= 1
    print("  PASS 标记已读")

    # 删除
    SentimentAlertRepository.delete(alert_id)
    print("  PASS 删除告警")


def test_dashboard_integration():
    """测试 6: 数智大屏集成"""
    print("\n" + "=" * 60)
    print("测试 6: DashboardRepository 舆情集成")
    print("=" * 60)

    from app.models.dashboard_screen import DashboardRepository
    sentiment = DashboardRepository.get_sentiment_overview()
    assert "distribution" in sentiment
    assert "risk_distribution" in sentiment
    assert "hot_keywords" in sentiment
    assert "alerts_unread" in sentiment
    print(f"  PASS 舆情概览: {sentiment}")

    all_data = DashboardRepository.get_all_data()
    assert "sentiment" in all_data
    print(f"  PASS all_data 含 sentiment 字段")


def run_all():
    print("\n" + "#" * 60)
    print("#  舆情分析系统 (Sentiment Analysis) 测试套件")
    print("#" * 60)

    tests = [
        test_sentiment_analysis,
        test_keyword_extraction,
        test_format_keywords,
        test_repository_crud,
        test_alerts,
        test_dashboard_integration,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            import traceback
            print(f"\n  FAIL {test.__name__}: {e}")
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 项")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
