"""新增一批 API 接口数据"""
from app.models.db import get_connection

apis = [
    ("获取用户列表", "/api/users", "GET", "分页获取系统用户列表",
     '{"page": 1, "page_size": 20}',
     '{"Authorization": "Bearer {token}"}', "token"),
    ("用户登录", "/api/auth/login", "POST", "用户登录获取Token",
     '{"username": "admin", "password": "123456"}',
     '{"Content-Type": "application/json"}', "none"),
    ("获取模型引擎列表", "/api/model-engines", "GET", "获取所有可用的AI模型引擎",
     '{}', '{"Authorization": "Bearer {token}"}', "token"),
    ("创建对话会话", "/api/sessions", "POST", "创建新的对话会话",
     '{"title": "新对话"}', '{"Authorization": "Bearer {token}"}', "token"),
    ("发送消息", "/api/chat/message", "POST", "向指定会话发送消息并获取AI回复",
     '{"session_id": 1, "content": "你好"}',
     '{"Authorization": "Bearer {token}"}', "token"),
    ("获取对话历史", "/api/chat/history", "GET", "获取指定会话的对话历史记录",
     '{"session_id": 1, "page": 1}',
     '{"Authorization": "Bearer {token}"}', "token"),
    ("获取技能列表", "/api/skills", "GET", "获取所有可用的AI技能",
     '{}', '{"Authorization": "Bearer {token}"}', "token"),
    ("执行技能", "/api/skills/execute", "POST", "调用指定技能执行任务",
     '{"skill_id": 1, "input": "查询天气"}',
     '{"Authorization": "Bearer {token}"}', "token"),
    ("瞭望数据采集", "/api/watch/collect", "POST", "根据关键词采集网络数据",
     '{"keyword": "AI", "source_id": 1}',
     '{"Authorization": "Bearer {token}"}', "token"),
    ("获取瞭望结果", "/api/watch/results", "GET", "分页获取瞭望采集结果",
     '{"page": 1, "keyword": ""}',
     '{"Authorization": "Bearer {token}"}', "token"),
    ("舆情分析", "/api/sentiment/analyze", "POST", "对文本进行情感分析和关键词提取",
     '{"text": "产品很好用"}', '{"Authorization": "Bearer {token}"}', "token"),
    ("获取舆情报告", "/api/sentiment/report", "GET", "获取舆情分析统计报告",
     '{"days": 7}', '{"Authorization": "Bearer {token}"}', "token"),
]

c = get_connection()
for name, path, method, desc, params, headers, auth_type in apis:
    c.execute(
        "INSERT INTO api_interfaces (name, path, method, description, params, headers, auth_type) "
        "VALUES (?,?,?,?,?,?,?)",
        (name, path, method, desc, params, headers, auth_type)
    )
c.commit()

print(f"已新增 {len(apis)} 个API接口：")
for i, a in enumerate(apis, 1):
    print(f"  {i}. [{a[2]}] {a[0]}  ->  {a[1]}")
