# 数字员工控制器 — CRUD + 状态管理 + 对话测试 + 统计 + 版本管理

import json
import time
import tornado.web
from openai import OpenAI

from app.models.digital_employee import DigitalEmployeeRepository, EmployeeVersionRepository
from app.utils.auth import require_admin, get_username
from app.models.model_engine import ModelEngineRepository
from app.models.ai_skill import AiSkillRepository




def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


def _resolve_skill_ids(skills_raw: str):
    """将 skills 字段解析为技能ID列表，兼容旧格式（名称数组→空）"""
    if not skills_raw:
        return []
    try:
        data = json.loads(skills_raw)
    except Exception:
        return []
    if not data:
        return []
    # 新格式：[1, 2, 3] 技能ID
    if isinstance(data[0], int):
        return data
    # 旧格式：["名称1", "名称2"]，返回空（不再支持名称匹配）
    return []


def _get_skill_name_map():
    """获取 {skill_id: skill_name} 映射"""
    skills = AiSkillRepository.get_all()
    return {s["id"]: s["name"] for s in skills}


class EmployeeListHandler(tornado.web.RequestHandler):
    """数字员工列表页"""

    def get(self):
        if not require_admin(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        result = DigitalEmployeeRepository.paginate(page=page, page_size=12, keyword=keyword)
        skill_map = _get_skill_name_map()
        # 预解析技能数据
        parsed_list = []
        for item in result["list"]:
            item_dict = dict(item)
            skill_ids = _resolve_skill_ids(item_dict.get("skills") or "")
            item_dict["_skill_ids"] = skill_ids
            item_dict["_skill_names"] = [skill_map.get(sid, f"技能#{sid}") for sid in skill_ids]
            parsed_list.append(item_dict)
        result["list"] = parsed_list
        total_pages = (result["total"] + 11) // 12
        global_stats = DigitalEmployeeRepository.get_stats()
        self.render(
            "admin/employee_list.html",
            username=get_username(self),
            current_page="employee",
            **result,
            total_pages=total_pages,
            keyword=keyword,
            global_stats=global_stats,
        )


class EmployeeAddHandler(tornado.web.RequestHandler):
    """新增数字员工"""

    def get(self):
        if not require_admin(self):
            return
        models = ModelEngineRepository.get_all()
        all_skills = AiSkillRepository.get_all(enabled_only=False)
        self.render(
            "admin/employee_edit.html",
            username=get_username(self),
            current_page="employee",
            employee=None,
            is_add=True,
            models=models,
            all_skills=all_skills,
            employee_skill_ids=[],
        )

    def post(self):
        if not require_admin(self):
            return
        name = self.get_body_argument("name", "").strip()
        role_name = self.get_body_argument("role_name", "").strip()
        avatar = self.get_body_argument("avatar", "").strip()
        greeting = self.get_body_argument("greeting", "").strip()
        # 从多选复选框收集技能ID
        skill_ids = [int(x) for x in self.get_body_arguments("skill_ids") if x.isdigit()]
        skills = json.dumps(skill_ids)
        model_engine_id = _int_arg(self, "model_engine_id", 0)
        model_name = self.get_body_argument("model_name", "").strip()
        system_prompt = self.get_body_argument("system_prompt", "").strip()
        status = self.get_body_argument("status", "enabled").strip()
        version = self.get_body_argument("version", "1.0").strip()
        if name:
            eid = DigitalEmployeeRepository.create(
                name=name, avatar=avatar, role_name=role_name, greeting=greeting,
                skills=skills, model_engine_id=model_engine_id, model_name=model_name,
                system_prompt=system_prompt, status=status, version=version,
            )
            # 创建初始版本记录
            EmployeeVersionRepository.create(
                employee_id=eid, version=version, system_prompt=system_prompt,
                skills=skills, change_log="初始版本"
            )
        self.redirect("/admin/employees")


class EmployeeEditHandler(tornado.web.RequestHandler):
    """编辑数字员工"""

    def get(self):
        if not require_admin(self):
            return
        employee_id = _int_arg(self, "id")
        employee = DigitalEmployeeRepository.get_by_id(employee_id)
        if not employee:
            self.redirect("/admin/employees")
            return
        models = ModelEngineRepository.get_all()
        all_skills = AiSkillRepository.get_all(enabled_only=False)
        versions = EmployeeVersionRepository.get_by_employee(employee_id)
        employee_skill_ids = _resolve_skill_ids(employee["skills"] or "")
        self.render(
            "admin/employee_edit.html",
            username=get_username(self),
            current_page="employee",
            employee=employee,
            is_add=False,
            models=models,
            versions=versions,
            all_skills=all_skills,
            employee_skill_ids=[str(x) for x in employee_skill_ids],
        )

    def post(self):
        if not require_admin(self):
            return
        employee_id = _int_arg(self, "id")
        employee = DigitalEmployeeRepository.get_by_id(employee_id)
        if not employee:
            self.redirect("/admin/employees")
            return
        name = self.get_body_argument("name", "").strip()
        role_name = self.get_body_argument("role_name", "").strip()
        avatar = self.get_body_argument("avatar", "").strip()
        greeting = self.get_body_argument("greeting", "").strip()
        # 从多选复选框收集技能ID
        skill_ids = [int(x) for x in self.get_body_arguments("skill_ids") if x.isdigit()]
        skills = json.dumps(skill_ids)
        model_engine_id = _int_arg(self, "model_engine_id", 0)
        model_name = self.get_body_argument("model_name", "").strip()
        system_prompt = self.get_body_argument("system_prompt", "").strip()
        status = self.get_body_argument("status", "enabled").strip()
        new_version = self.get_body_argument("new_version", "").strip()
        change_log = self.get_body_argument("change_log", "").strip()

        if name:
            DigitalEmployeeRepository.update(
                employee_id,
                name=name, avatar=avatar, role_name=role_name, greeting=greeting,
                skills=skills, model_engine_id=model_engine_id, model_name=model_name,
                system_prompt=system_prompt, status=status,
            )
            # 如果填写了新版本号，创建版本记录
            if new_version:
                DigitalEmployeeRepository.update(employee_id, version=new_version)
                EmployeeVersionRepository.create(
                    employee_id=employee_id, version=new_version,
                    system_prompt=system_prompt, skills=skills, change_log=change_log,
                )
        self.redirect("/admin/employees")


class EmployeeDeleteHandler(tornado.web.RequestHandler):
    """删除数字员工"""

    def post(self):
        if not require_admin(self):
            return
        employee_id = _int_arg(self, "id")
        DigitalEmployeeRepository.delete(employee_id)
        self.redirect("/admin/employees")


class EmployeeToggleStatusHandler(tornado.web.RequestHandler):
    """切换员工状态（启用/停用）"""

    def post(self):
        if not require_admin(self):
            return
        employee_id = _int_arg(self, "id")
        status = self.get_body_argument("status", "enabled").strip()
        DigitalEmployeeRepository.update(employee_id, status=status)
        self.redirect("/admin/employees")


class EmployeeChatHandler(tornado.web.RequestHandler):
    """数字员工对话测试页"""

    def get(self):
        if not require_admin(self):
            return
        employee_id = _int_arg(self, "id")
        employee = DigitalEmployeeRepository.get_by_id(employee_id)
        if not employee:
            self.redirect("/admin/employees")
            return
        stats = DigitalEmployeeRepository.get_stats(employee_id)
        # 解析技能 ID → 技能名称
        employee_dict = dict(employee)
        skill_ids = _resolve_skill_ids(employee_dict.get("skills") or "")
        skill_map = _get_skill_name_map()
        employee_dict["_skill_names"] = [skill_map.get(sid, f"技能#{sid}") for sid in skill_ids]
        employee_dict["_skill_ids"] = skill_ids
        self.render(
            "admin/employee_chat.html",
            username=get_username(self),
            current_page="employee",
            employee=employee_dict,
            stats=stats,
        )


class EmployeeChatSSEHandler(tornado.web.RequestHandler):
    """数字员工 SSE 流式对话测试"""

    async def post(self):
        if not require_admin(self):
            return

        body = json.loads(self.request.body or "{}")
        employee_id = body.get("id", 0)
        employee = DigitalEmployeeRepository.get_by_id(employee_id)
        if not employee:
            self.set_status(404)
            self.finish()
            return

        user_message = body.get("message", "").strip()
        if not user_message:
            self.set_status(400)
            self.finish()
            return

        model_engine_id = employee["model_engine_id"] or 0
        model = None
        if model_engine_id:
            model = ModelEngineRepository.get_by_id(model_engine_id)
        if not model:
            model = ModelEngineRepository.get_default()

        api_key = (model["api_key"] or "YOUR_API_KEY") if model else "YOUR_API_KEY"
        api_base = (model["api_base"] or "https://api.openai.com/v1") if model else "https://api.openai.com/v1"
        model_name = (model["model_name"] or "gpt-3.5-turbo") if model else "gpt-3.5-turbo"

        system_prompt = employee["system_prompt"] or f"你是 {employee['name']}，{employee['role_name']}。{employee['greeting']}"

        # 注入绑定的技能 prompt
        skill_ids = _resolve_skill_ids(employee["skills"] or "")
        if skill_ids:
            skill_prompts = []
            skill_summary_list = []  # 简洁能力列表，供模型自我描述
            for sid in skill_ids:
                skill = AiSkillRepository.get_by_id(sid)
                if skill and skill["prompt_template"]:
                    skill_prompts.append(f"【{skill['name']}】{skill['prompt_template']}")
                    desc = (skill["description"] or "").strip()
                    skill_summary_list.append(f"- {skill['name']}" + (f"：{desc}" if desc else ""))
            if skill_prompts:
                system_prompt += "\n\n📋 你拥有以下技能能力：\n" + "\n".join(skill_summary_list)
                system_prompt += "\n\n📝 各技能详细行为定义：\n" + "\n".join(skill_prompts)
                system_prompt += "\n\n当用户询问\"你有什么能力\"、\"你会什么\"、\"你的技能\"等问题时，请列出上述技能名称及其简要说明。"
                system_prompt += "\n当用户的问题匹配某个技能时，请使用该技能定义的角色和能力来回答。"

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.set_header("X-Accel-Buffering", "no")

        try:
            client = OpenAI(api_key=api_key, base_url=api_base)
            t0 = time.time()
            total_tokens = 0
            full_content = ""

            stream = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                stream=True,
                temperature=0.7,
                max_tokens=2048,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    sse_data = json.dumps({
                        "type": "content",
                        "content": content,
                    }, ensure_ascii=False)
                    self.write(f"data: {sse_data}\n\n")
                    await self.flush()

            elapsed = int((time.time() - t0) * 1000)
            total_tokens = len(full_content) // 4  # 简单估算

            # 记录调用统计
            DigitalEmployeeRepository.increment_stats(employee_id, tokens=total_tokens, duration_ms=elapsed)

            done_data = json.dumps({
                "type": "done",
                "tokens": total_tokens,
                "duration_ms": elapsed,
            }, ensure_ascii=False)
            self.write(f"data: {done_data}\n\n")
            await self.flush()

        except Exception as e:
            elapsed = int((time.time() - t0) * 1000)
            err_data = json.dumps({
                "type": "error",
                "content": f"对话失败：{str(e)}",
            }, ensure_ascii=False)
            self.write(f"data: {err_data}\n\n")
            await self.flush()


class EmployeeStatsHandler(tornado.web.RequestHandler):
    """数字员工统计页"""

    def get(self):
        if not require_admin(self):
            return
        employee_id = _int_arg(self, "id")
        employee = None
        if employee_id:
            employee = DigitalEmployeeRepository.get_by_id(employee_id)
        stats = DigitalEmployeeRepository.get_stats(employee_id)
        versions = []
        if employee:
            versions = EmployeeVersionRepository.get_by_employee(employee_id)
            employee_dict = dict(employee)
            skill_ids = _resolve_skill_ids(employee_dict.get("skills") or "")
            skill_map = _get_skill_name_map()
            employee_dict["_skill_names"] = [skill_map.get(sid, f"技能#{sid}") for sid in skill_ids]
            employee_dict["_skill_ids"] = skill_ids
        else:
            employee_dict = None
        all_employees = DigitalEmployeeRepository.get_all()
        self.render(
            "admin/employee_stats.html",
            username=get_username(self),
            current_page="employee",
            employee=employee_dict,
            stats=stats,
            versions=versions,
            all_employees=all_employees,
        )
