# 系统设置控制器

import os
import json
import tornado.web

from app.models.system_settings import (
    SystemSettingsRepository,
    OperationLogRepository,
)
from app.models.db import get_db_config, set_db_config, test_mysql_connection, get_engine, DB_CONFIG_FILE
from app.utils.auth import require_admin, get_username




def _int_arg(handler, key, default=0):
    try:
        return int(handler.get_argument(key, str(default)))
    except (ValueError, TypeError):
        return default


# ─── 系统设置主页面 ───

class SystemSettingsHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        settings = SystemSettingsRepository.get_all()
        self.render(
            "admin/system_settings.html",
            username=get_username(self),
            current_page="system",
            settings=settings,
            msg=self.get_query_argument("msg", ""),
        )


class SystemSettingsSaveHandler(tornado.web.RequestHandler):
    def post(self):
        if not require_admin(self):
            return
        data = {}
        for key in self.request.body_arguments:
            val = self.get_body_argument(key, "")
            data[key] = val
        SystemSettingsRepository.save_changes(data)
        op = get_username(self)
        OperationLogRepository.log(
            operator=op,
            action="update_settings",
            detail="更新系统设置",
            ip=self.request.remote_ip,
        )
        self.redirect("/admin/system?msg=saved")


# ─── 备份 ───

class SystemBackupHandler(tornado.web.RequestHandler):
    def post(self):
        if not require_admin(self):
            return
        try:
            path = SystemSettingsRepository.backup_database()
            OperationLogRepository.log(
                operator=get_username(self),
                action="backup",
                detail=f"数据库备份: {path}",
                ip=self.request.remote_ip,
            )
            self.redirect("/admin/system?msg=backup_ok")
        except Exception as e:
            self.redirect(f"/admin/system?msg=backup_fail:{str(e)}")


class SystemRestoreHandler(tornado.web.RequestHandler):
    def post(self):
        if not require_admin(self):
            return
        filename = self.get_body_argument("file", "").strip()
        if not filename:
            self.redirect("/admin/system?msg=restore_no_file")
            return
        ok = SystemSettingsRepository.restore_backup(filename)
        if ok:
            OperationLogRepository.log(
                operator=get_username(self),
                action="restore",
                detail=f"从备份恢复: {filename}",
                ip=self.request.remote_ip,
            )
            self.redirect("/admin/system?msg=restore_ok")
        else:
            self.redirect(f"/admin/system?msg=restore_fail:{filename}")


# ─── 运行状态 ───

class SystemStatusHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        status = SystemSettingsRepository.get_system_status()
        backups = SystemSettingsRepository.list_backups()
        settings = SystemSettingsRepository.get_all()
        self.render(
            "admin/system_status.html",
            username=get_username(self),
            current_page="system",
            status=status,
            backups=backups,
            settings=settings,
        )


class SystemStatusJsonHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        status = SystemSettingsRepository.get_system_status()
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(status, ensure_ascii=False))


# ─── 操作日志 ───

class OperationLogHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        page = max(_int_arg(self, "page", 1), 1)
        operator = self.get_argument("operator", "").strip()
        action = self.get_argument("action", "").strip()
        date_from = self.get_argument("date_from", "").strip()
        date_to = self.get_argument("date_to", "").strip()
        result = OperationLogRepository.paginate(
            page=page, page_size=20,
            operator=operator, action=action,
            date_from=date_from, date_to=date_to,
        )
        total_pages = (result["total"] + 19) // 20
        actions = OperationLogRepository.get_actions()
        self.render(
            "admin/operation_logs.html",
            username=get_username(self),
            current_page="system",
            **result,
            total_pages=total_pages,
            operator=operator, action=action,
            date_from=date_from, date_to=date_to,
            actions=actions,
        )


class OperationLogClearHandler(tornado.web.RequestHandler):
    def post(self):
        if not require_admin(self):
            return
        OperationLogRepository.clear()
        OperationLogRepository.log(
            operator=get_username(self),
            action="clear_logs",
            detail="清空操作日志",
            ip=self.request.remote_ip,
        )
        self.redirect("/admin/operation-logs")


class OperationLogExportHandler(tornado.web.RequestHandler):
    def get(self):
        if not require_admin(self):
            return
        result = OperationLogRepository.paginate(page=1, page_size=50000)
        data = []
        for r in result["list"]:
            data.append({
                "id": r["id"],
                "operator": r["operator"],
                "action": r["action"],
                "detail": r["detail"],
                "ip": r["ip"],
                "created_at": r["created_at"],
            })
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.set_header("Content-Disposition", "attachment; filename=operation_logs.json")
        self.write(json.dumps(data, ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════════════
# 数据库配置管理（SQLite / MySQL 双引擎）
# ═══════════════════════════════════════════════════════════════

class DbConfigHandler(tornado.web.RequestHandler):
    """数据库配置页面"""

    def get(self):
        if not require_admin(self):
            return
        cfg = get_db_config()
        engine = get_engine()
        self.render(
            "admin/db_config.html",
            username=get_username(self),
            current_page="system",
            db_config=cfg,
            engine=engine,
            msg=self.get_query_argument("msg", ""),
        )


class DbConfigSaveHandler(tornado.web.RequestHandler):
    """保存 MySQL 连接参数"""

    def post(self):
        if not require_admin(self):
            return
        cfg = get_db_config()
        mysql_cfg = cfg.get("mysql", {})
        mysql_cfg["host"] = self.get_body_argument("db_host", "localhost").strip()
        mysql_cfg["port"] = int(self.get_body_argument("db_port", "3306"))
        mysql_cfg["user"] = self.get_body_argument("db_user", "root").strip()
        mysql_cfg["password"] = self.get_body_argument("db_password", "").strip()
        mysql_cfg["database"] = self.get_body_argument("db_name", "app").strip()
        cfg["mysql"] = mysql_cfg
        set_db_config(cfg)
        OperationLogRepository.log(
            operator=get_username(self),
            action="db_config",
            detail="更新 MySQL 数据库连接参数",
            ip=self.request.remote_ip,
        )
        self.redirect("/admin/db-config?msg=config_saved")


class DbTestHandler(tornado.web.RequestHandler):
    """测试 MySQL 连接"""

    def post(self):
        if not require_admin(self):
            return
        cfg = {
            "host": self.get_body_argument("db_host", "localhost").strip(),
            "port": int(self.get_body_argument("db_port", "3306")),
            "user": self.get_body_argument("db_user", "root").strip(),
            "password": self.get_body_argument("db_password", "").strip(),
            "database": self.get_body_argument("db_name", "app").strip(),
        }
        result = test_mysql_connection(cfg)
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(result, ensure_ascii=False))


class DbMigrateHandler(tornado.web.RequestHandler):
    """执行数据库迁移（SSE 流式进度）"""

    async def post(self):
        if not require_admin(self):
            return
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.set_header("X-Accel-Buffering", "no")

        from app.services.db_migration import migrate_data

        def progress_callback(stage, message, percent):
            data = json.dumps({"stage": stage, "message": message, "percent": percent}, ensure_ascii=False)
            try:
                self.write(f"data: {data}\n\n")
            except Exception:
                pass

        try:
            # 在同步线程中执行迁移（避免阻塞事件循环）
            import concurrent.futures
            loop = tornado.ioloop.IOLoop.current()
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = executor.submit(migrate_data, progress_callback)
            # 简单等待（Tornado 中不完美但可用）
            result = future.result(timeout=300)

            OperationLogRepository.log(
                operator=get_username(self),
                action="db_migrate",
                detail=f"数据库迁移: {result.get('source_engine')} → {result.get('target_engine')}, "
                        f"{result.get('tables_migrated', 0)} 表, {result.get('rows_migrated', 0)} 行",
                ip=self.request.remote_ip,
            )
            done_msg = json.dumps({
                "stage": "complete",
                "message": result.get("message", ""),
                "ok": result["ok"],
                "tables": result.get("tables_migrated", 0),
                "rows": result.get("rows_migrated", 0),
                "target": result.get("target_engine", ""),
            }, ensure_ascii=False)
            self.write(f"data: {done_msg}\n\n")
            await self.flush()
        except Exception as e:
            error_msg = json.dumps({"stage": "error", "message": f"迁移异常: {str(e)}"}, ensure_ascii=False)
            self.write(f"data: {error_msg}\n\n")
            await self.flush()


class DbSwitchHandler(tornado.web.RequestHandler):
    """切换数据库引擎（仅切换，不迁移）"""

    def post(self):
        if not require_admin(self):
            return
        target = self.get_body_argument("target", "sqlite").strip()
        from app.services.db_migration import switch_engine
        result = switch_engine(target)
        OperationLogRepository.log(
            operator=get_username(self),
            action="db_switch",
            detail=f"数据库引擎切换至: {target}, 结果: {result.get('message', '')}",
            ip=self.request.remote_ip,
        )
        if result["ok"]:
            self.redirect(f"/admin/db-config?msg=switch_ok:{target}")
        else:
            self.redirect(f"/admin/db-config?msg=switch_fail:{result.get('message', '')}")
