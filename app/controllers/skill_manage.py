# 技能管理控制器 — CRUD + 状态切换 + 热更新 + 调用统计 + 市场预留

import json
import tornado.web

from app.models.ai_skill import (
    AiSkillRepository, SkillCallLogRepository,
    refresh_skill_cache, get_all_skills_from_cache,
)
from app.models.model_engine import ModelEngineRepository


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


class SkillListHandler(tornado.web.RequestHandler):
    """技能管理列表页"""

    def get(self):
        if not _require_login(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        keyword = self.get_argument("keyword", "").strip()
        category = self.get_argument("category", "").strip()
        result = AiSkillRepository.paginate(page=page, page_size=12, keyword=keyword, category=category)
        total_pages = (result["total"] + 11) // 12
        categories = AiSkillRepository.get_categories()
        stats = AiSkillRepository.get_stats()
        # 预解析 trigger_keywords
        parsed = []
        for item in result["list"]:
            d = dict(item)
            try:
                d["_keywords"] = json.loads(d.get("trigger_keywords") or "[]")
            except Exception:
                d["_keywords"] = []
            parsed.append(d)
        result["list"] = parsed
        self.render(
            "admin/skill_list.html",
            username=_get_current_user(self),
            current_page="skills",
            **result,
            total_pages=total_pages,
            keyword=keyword,
            category=category,
            categories=categories,
            stats=stats,
        )


class SkillAddHandler(tornado.web.RequestHandler):
    """新增技能"""

    def get(self):
        if not _require_login(self):
            return
        models = ModelEngineRepository.get_all()
        categories = AiSkillRepository.get_categories()
        self.render(
            "admin/skill_edit.html",
            username=_get_current_user(self),
            current_page="skills",
            skill=None,
            is_add=True,
            models=models,
            categories=categories,
        )

    def post(self):
        if not _require_login(self):
            return
        name = self.get_body_argument("name", "").strip()
        description = self.get_body_argument("description", "").strip()
        category = self.get_body_argument("category", "通用").strip()
        trigger_keywords = self.get_body_argument("trigger_keywords", "[]").strip()
        model_engine_id = _int_arg(self, "model_engine_id", 0)
        model_name = self.get_body_argument("model_name", "").strip()
        prompt_template = self.get_body_argument("prompt_template", "").strip()
        status = self.get_body_argument("status", "enabled").strip()
        icon = self.get_body_argument("icon", "fa-tools").strip()
        version = self.get_body_argument("version", "1.0").strip()
        if name:
            AiSkillRepository.create(
                name=name, description=description, category=category,
                trigger_keywords=trigger_keywords, model_engine_id=model_engine_id,
                model_name=model_name, prompt_template=prompt_template,
                status=status, icon=icon, version=version,
            )
        self.redirect("/admin/skills")


class SkillEditHandler(tornado.web.RequestHandler):
    """编辑技能"""

    def get(self):
        if not _require_login(self):
            return
        skill_id = _int_arg(self, "id")
        skill = AiSkillRepository.get_by_id(skill_id)
        if not skill:
            self.redirect("/admin/skills")
            return
        models = ModelEngineRepository.get_all()
        categories = AiSkillRepository.get_categories()
        self.render(
            "admin/skill_edit.html",
            username=_get_current_user(self),
            current_page="skills",
            skill=skill,
            is_add=False,
            models=models,
            categories=categories,
        )

    def post(self):
        if not _require_login(self):
            return
        skill_id = _int_arg(self, "id")
        skill = AiSkillRepository.get_by_id(skill_id)
        if not skill:
            self.redirect("/admin/skills")
            return
        name = self.get_body_argument("name", "").strip()
        description = self.get_body_argument("description", "").strip()
        category = self.get_body_argument("category", "通用").strip()
        trigger_keywords = self.get_body_argument("trigger_keywords", "[]").strip()
        model_engine_id = _int_arg(self, "model_engine_id", 0)
        model_name = self.get_body_argument("model_name", "").strip()
        prompt_template = self.get_body_argument("prompt_template", "").strip()
        status = self.get_body_argument("status", "enabled").strip()
        icon = self.get_body_argument("icon", "fa-tools").strip()
        version = self.get_body_argument("version", "1.0").strip()
        if name:
            AiSkillRepository.update(
                skill_id,
                name=name, description=description, category=category,
                trigger_keywords=trigger_keywords, model_engine_id=model_engine_id,
                model_name=model_name, prompt_template=prompt_template,
                status=status, icon=icon, version=version,
            )
        self.redirect("/admin/skills")


class SkillDeleteHandler(tornado.web.RequestHandler):
    """删除技能"""

    def post(self):
        if not _require_login(self):
            return
        skill_id = _int_arg(self, "id")
        AiSkillRepository.delete(skill_id)
        self.redirect("/admin/skills")


class SkillToggleHandler(tornado.web.RequestHandler):
    """切换技能启用/停用"""

    def post(self):
        if not _require_login(self):
            return
        skill_id = _int_arg(self, "id")
        status = self.get_body_argument("status", "enabled").strip()
        AiSkillRepository.update(skill_id, status=status)
        self.redirect("/admin/skills")


class SkillRefreshHandler(tornado.web.RequestHandler):
    """手动热更新技能缓存"""

    def post(self):
        if not _require_login(self):
            return
        refresh_skill_cache()
        count = len(get_all_skills_from_cache())
        self.redirect("/admin/skills")


class SkillStatsHandler(tornado.web.RequestHandler):
    """技能调用统计页"""

    def get(self):
        if not _require_login(self):
            return
        skill_id = _int_arg(self, "id")
        skill = None
        if skill_id:
            skill = dict(AiSkillRepository.get_by_id(skill_id) or {})
        stats = AiSkillRepository.get_stats()
        log_result = SkillCallLogRepository.paginate(page=1, page_size=20, skill_id=skill_id)
        all_skills = AiSkillRepository.get_all()
        self.render(
            "admin/skill_stats.html",
            username=_get_current_user(self),
            current_page="skills",
            skill=skill,
            stats=stats,
            logs=log_result["list"],
            all_skills=all_skills,
        )


class SkillMarketHandler(tornado.web.RequestHandler):
    """技能市场 — 预留接口"""

    def get(self):
        if not _require_login(self):
            return
        all_skills = AiSkillRepository.get_all(enabled_only=True)
        stats = AiSkillRepository.get_stats()
        self.render(
            "admin/skill_market.html",
            username=_get_current_user(self),
            current_page="skills",
            skills=all_skills,
            stats=stats,
        )
