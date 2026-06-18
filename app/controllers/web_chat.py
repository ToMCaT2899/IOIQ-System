# 前台 AI 问数对话控制器 — SSE 流式 + 意图识别 + 历史管理

import json
import time
import tornado.web
from openai import OpenAI

from app.models.model_engine import ModelEngineRepository
from app.models.conversation import ConversationRepository, ChatMessageRepository
from app.models.db import get_connection


def _require_web_login(handler):
    username = handler.get_secure_cookie("admin_user")
    if not username:
        handler.redirect("/login")
        return False, ""
    if isinstance(username, bytes):
        username = username.decode()
    return True, username


def _get_user_id(username: str) -> int:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        return row["id"] if row else 0


class ChatPageHandler(tornado.web.RequestHandler):
    """AI 问数对话主页面"""

    def get(self):
        ok, username = _require_web_login(self)
        if not ok:
            return
        user_id = _get_user_id(username)
        # 获取可用模型列表
        models = ModelEngineRepository.get_all()
        models_list = [dict(m) for m in models]
        # 获取用户对话历史
        conversations = ConversationRepository.get_by_user(user_id)
        conversations_list = [dict(c) for c in conversations]
        # 获取最后活跃的对话ID
        last_msg_id = ChatMessageRepository.get_last_message_id(user_id)
        self.render(
            "web/chat.html",
            username=username,
            models=models_list,
            conversations=conversations_list,
            conv_id=last_msg_id or 0,
        )


class ChatSSEHandler(tornado.web.RequestHandler):
    """SSE 流式对话接口 — 含意图识别 & SQL 问数"""

    async def post(self):
        ok, username = _require_web_login(self)
        if not ok:
            return
        user_id = _get_user_id(username)

        body = json.loads(self.request.body or "{}")
        user_message = body.get("message", "").strip()
        conversation_id = body.get("conversation_id", 0)
        model_engine_id = body.get("model_engine_id", 0)

        if not user_message:
            self.set_status(400)
            self.finish()
            return

        # 获取模型
        model = None
        if model_engine_id:
            model = ModelEngineRepository.get_by_id(model_engine_id)
        if not model:
            model = ModelEngineRepository.get_default()
        if not model:
            model = ModelEngineRepository.get_all()
            if model:
                model = model[0]
            else:
                self.set_status(500)
                self.finish()
                return

        # 新建或获取会话
        if conversation_id:
            conv = ConversationRepository.get_by_id(conversation_id)
            if not conv or conv["user_id"] != user_id:
                conversation_id = 0
        if not conversation_id:
            conversation_id = ConversationRepository.create(
                user_id, user_message[:30],
                model["id"], model["model_name"]
            )
        else:
            ConversationRepository.update_model(conversation_id, model["id"], model["model_name"])

        # 获取历史消息（最近20条）
        history = ChatMessageRepository.get_last_n(conversation_id, 20)

        # 意图识别：检测是否为 SQL 问数请求
        intent = _detect_intent(user_message)

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.set_header("X-Accel-Buffering", "no")

        try:
            api_key = model["api_key"] or "YOUR_API_KEY"
            api_base = model["api_base"] or "https://api.openai.com/v1"
            model_name = model["model_name"] or "gpt-3.5-turbo"
            system_prompt = model["system_prompt"] or ""

            client = OpenAI(api_key=api_key, base_url=api_base)

            # 保存用户消息
            ChatMessageRepository.add(conversation_id, "user", user_message)
            ConversationRepository.touch(conversation_id)

            # 构建消息列表
            messages = []

            # 系统提示词：意图识别 + SQL 规则
            if intent == "sql":
                sql_schema = _get_db_schema()
                sql_prompt = (
                    "你是一个智能问数助手。用户已经请求查询数据库中的数据。\n"
                    "你的回答必须严格遵循以下规则：\n"
                    "1. 根据用户的问题，生成对应的 SQLite SQL 语句查询数据库\n"
                    "2. 严禁在回复中展示任何 SQL 语句内容，包括 SELECT、FROM、WHERE 等关键字\n"
                    "3. 用自然语言解释查询结果，让用户理解数据含义\n"
                    "4. 如果用户的问数意图不明确，请追问具体想查询什么数据\n"
                    "5. 如果查询无结果，友好地告知用户并建议调整条件\n\n"
                    "数据库表结构如下：\n"
                    f"{sql_schema}\n\n"
                    "你需要在内部生成 SQL 查询（不展示），然后将结果转化为用户友好的自然语言回答。"
                )
                messages.append({"role": "system", "content": sql_prompt})
            elif system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            else:
                messages.append({
                    "role": "system",
                    "content": "你是 IOIQ 智能助手，擅长数据问答、信息检索和知识解答。回答简洁、专业、友好。"
                })

            # 添加历史消息
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})

            # 当前用户消息
            messages.append({"role": "user", "content": user_message})

            # 调用 OpenAI 流式
            stream = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=model["temperature"] if model["temperature"] else 0.7,
                max_tokens=model["max_tokens"] if model["max_tokens"] else 2048,
                stream=True,
            )

            full_content = ""
            total_tokens = 0
            t0 = time.time()

            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    full_content += delta.content
                    data = json.dumps({
                        "type": "content",
                        "content": delta.content,
                        "conversation_id": conversation_id,
                    }, ensure_ascii=False)
                    self.write(f"data: {data}\n\n")
                    await self.flush()

                if chunk.usage and chunk.usage.total_tokens:
                    total_tokens = chunk.usage.total_tokens

                # 如果是 SQL 意图，检查 AI 回复中是否包含 SQL（拦截展示）
                # 实际做法：AI 自己遵守规则不展示 SQL

            elapsed = int((time.time() - t0) * 1000)

            # 保存 AI 回复
            ChatMessageRepository.add(conversation_id, "assistant", full_content, total_tokens)

            # 更新模型 token 统计
            if total_tokens > 0:
                ModelEngineRepository.add_tokens(model["id"], total_tokens)

            # 如果是第一条用户消息，更新对话标题
            if len(history) == 0:
                title = user_message[:30] + ("..." if len(user_message) > 30 else "")
                ConversationRepository.update_title(conversation_id, title)

            # 发送结束事件
            done_data = json.dumps({
                "type": "done",
                "tokens": total_tokens,
                "duration_ms": elapsed,
                "conversation_id": conversation_id,
            }, ensure_ascii=False)
            self.write(f"data: {done_data}\n\n")
            await self.flush()

        except Exception as e:
            error_msg = str(e)
            ChatMessageRepository.add(conversation_id, "assistant", f"[错误] {error_msg}")
            data = json.dumps({
                "type": "error",
                "content": f"请求失败：{error_msg}",
            }, ensure_ascii=False)
            self.write(f"data: {data}\n\n")
            await self.flush()


class ChatHistoryHandler(tornado.web.RequestHandler):
    """获取会话的历史消息"""

    def get(self):
        ok, username = _require_web_login(self)
        if not ok:
            return
        conv_id = int(self.get_argument("conversation_id", "0"))
        user_id = _get_user_id(username)
        conv = ConversationRepository.get_by_id(conv_id)
        if not conv or conv["user_id"] != user_id:
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"error": "无权访问"}, ensure_ascii=False))
            return
        messages = ChatMessageRepository.get_by_conversation(conv_id)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({
            "conversation": dict(conv),
            "messages": [dict(m) for m in messages],
        }, ensure_ascii=False))


class ChatDeleteHandler(tornado.web.RequestHandler):
    """删除对话"""

    def post(self):
        ok, username = _require_web_login(self)
        if not ok:
            return
        conv_id = int(self.get_body_argument("conversation_id", "0"))
        user_id = _get_user_id(username)
        conv = ConversationRepository.get_by_id(conv_id)
        if not conv or conv["user_id"] != user_id:
            self.set_header("Content-Type", "application/json")
            self.write(json.dumps({"error": "无权操作"}, ensure_ascii=False))
            return
        ConversationRepository.delete(conv_id)
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({"ok": True}, ensure_ascii=False))


def _detect_intent(message: str) -> str:
    """简单意图识别"""
    sql_keywords = ["查询", "统计", "有多少", "列表", "数据", "记录", "汇总",
                    "查一下", "帮我查", "问数", "数据库", "表", "字段",
                    "哪个", "哪些", "多少条", "一共有"]
    weather_keywords = ["天气", "气温", "下雨", "多云", "晴天", "阴天"]
    music_keywords = ["音乐", "歌曲", "歌", "听", "播放", "专辑"]

    msg_lower = message.lower()
    for kw in weather_keywords:
        if kw in message:
            return "weather"
    for kw in music_keywords:
        if kw in message:
            return "music"
    for kw in sql_keywords:
        if kw in message:
            return "sql"
    return "chat"


def _get_db_schema() -> str:
    """获取数据库表结构描述"""
    with get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        schema_parts = []
        for t in tables:
            table_name = t["name"]
            cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            col_descs = [f"  {c['name']} ({c['type']})" for c in cols]
            schema_parts.append(f"表名: {table_name}\n" + "\n".join(col_descs))
        return "\n\n".join(schema_parts)
