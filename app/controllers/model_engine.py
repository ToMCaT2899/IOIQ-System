# 模型引擎控制器

import json
import tornado.web
import tornado.ioloop
from openai import OpenAI

from app.models.model_engine import ModelEngineRepository
from app.utils.auth import require_admin, get_username




def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


class ModelListHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        result = ModelEngineRepository.paginate(page=page, page_size=6, keyword=keyword)
        total_pages = (result["total"] + 5) // 6
        self.render(
            "admin/model_list.html",
            username=get_username(self),
            current_page="models",
            **result,
            total_pages=total_pages,
            keyword=keyword,
        )


class ModelAddHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        self.render(
            "admin/model_edit.html",
            username=get_username(self),
            current_page="models",
            model=None,
            is_add=True,
        )

    def post(self):
        if not require_admin(self):
            return
        name = self.get_body_argument("name", "").strip()
        provider = self.get_body_argument("provider", "openai").strip()
        api_base = self.get_body_argument("api_base", "").strip()
        api_key = self.get_body_argument("api_key", "").strip()
        model_name = self.get_body_argument("model_name", "").strip()
        model_type = self.get_body_argument("model_type", "text").strip()
        temperature = float(self.get_body_argument("temperature", "0.7"))
        max_tokens = int(self.get_body_argument("max_tokens", "2048"))
        system_prompt = self.get_body_argument("system_prompt", "").strip()
        enable_stream = 1 if self.get_body_argument("enable_stream", None) == "1" else 0
        enable_think = 1 if self.get_body_argument("enable_think", None) == "1" else 0
        if name and model_name:
            ModelEngineRepository.create(
                name, provider, api_base, api_key, model_name,
                model_type, temperature, max_tokens, system_prompt,
                enable_stream, enable_think
            )
        self.redirect("/admin/models")


class ModelEditHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        model_id = _int_arg(self, "id")
        model = ModelEngineRepository.get_by_id(model_id)
        if not model:
            self.redirect("/admin/models")
            return
        self.render(
            "admin/model_edit.html",
            username=get_username(self),
            current_page="models",
            model=model,
            is_add=False,
        )

    def post(self):
        if not require_admin(self):
            return
        model_id = _int_arg(self, "id")
        model = ModelEngineRepository.get_by_id(model_id)
        if not model:
            self.redirect("/admin/models")
            return
        name = self.get_body_argument("name", "").strip()
        provider = self.get_body_argument("provider", "openai").strip()
        api_base = self.get_body_argument("api_base", "").strip()
        api_key = self.get_body_argument("api_key", "").strip()
        model_name = self.get_body_argument("model_name", "").strip()
        model_type = self.get_body_argument("model_type", "text").strip()
        temperature = float(self.get_body_argument("temperature", "0.7"))
        max_tokens = int(self.get_body_argument("max_tokens", "2048"))
        system_prompt = self.get_body_argument("system_prompt", "").strip()
        enable_stream = 1 if self.get_body_argument("enable_stream", None) == "1" else 0
        enable_think = 1 if self.get_body_argument("enable_think", None) == "1" else 0
        if name and model_name:
            ModelEngineRepository.update(
                model_id,
                name=name, provider=provider, api_base=api_base, api_key=api_key,
                model_name=model_name, model_type=model_type, temperature=temperature,
                max_tokens=max_tokens, system_prompt=system_prompt,
                enable_stream=enable_stream, enable_think=enable_think
            )
        self.redirect("/admin/models")


class ModelDeleteHandler(tornado.web.RequestHandler):
    def post(self):
        if not require_admin(self):
            return
        model_id = _int_arg(self, "id")
        ModelEngineRepository.delete(model_id)
        self.redirect("/admin/models")


class ModelSetDefaultHandler(tornado.web.RequestHandler):
    def post(self):
        if not require_admin(self):
            return
        model_id = _int_arg(self, "id")
        ModelEngineRepository.set_default(model_id)
        self.redirect("/admin/models")


class ModelChatHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        model_id = _int_arg(self, "id")
        model = ModelEngineRepository.get_by_id(model_id)
        if not model:
            self.redirect("/admin/models")
            return
        all_models = ModelEngineRepository.get_all()
        self.render(
            "admin/model_chat.html",
            username=get_username(self),
            current_page="models",
            model=model,
            all_models=all_models,
        )


class ModelChatSSEHandler(tornado.web.RequestHandler):
    """SSE 流式对话测试接口"""

    async def post(self):
        if not require_admin(self):
            return
        model_id = _int_arg(self, "id")
        model = ModelEngineRepository.get_by_id(model_id)
        if not model:
            self.set_status(404)
            self.finish()
            return

        body = json.loads(self.request.body or "{}")
        user_message = body.get("message", "").strip()
        if not user_message:
            self.set_status(400)
            self.finish()
            return

        api_key = model["api_key"]
        api_base = model["api_base"]
        model_name = model["model_name"]
        enable_stream = model["enable_stream"]
        enable_think = self.get_argument("think", "0") == "1" or model["enable_think"] == 1
        system_prompt = model["system_prompt"]

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.set_header("X-Accel-Buffering", "no")

        try:
            client = OpenAI(api_key=api_key, base_url=api_base)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_message})

            total_token = 0

            if enable_stream:
                stream = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=model["temperature"],
                    max_tokens=model["max_tokens"],
                    stream=True,
                    stream_options={"include_usage": True}
                )
                for chunk in stream:
                    if chunk.usage:
                        total_token = chunk.usage.total_tokens
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        data = json.dumps({"type": "content", "text": delta.content})
                        self.write(f"data: {data}\n\n")
                        await self.flush()
                if total_token > 0:
                    ModelEngineRepository.add_tokens(model_id, total_token)
                self.write(f"data: {json.dumps({'type': 'done'})}\n\n")
                await self.flush()
            else:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=model["temperature"],
                    max_tokens=model["max_tokens"],
                    stream=False,
                )
                text = response.choices[0].message.content
                token_count = response.usage.total_tokens if response.usage else 0
                if token_count > 0:
                    ModelEngineRepository.add_tokens(model_id, token_count)
                data = json.dumps({"type": "content", "text": text})
                self.write(f"data: {data}\n\n")
                await self.flush()
                self.write(f"data: {json.dumps({'type': 'done'})}\n\n")
                await self.flush()
        except Exception as e:
            error_data = json.dumps({"type": "error", "text": str(e)})
            self.write(f"data: {error_data}\n\n")
            await self.flush()
