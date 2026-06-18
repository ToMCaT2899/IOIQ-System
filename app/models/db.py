import os
import sqlite3
import hashlib
import secrets

def _project_root():
	return os.path.abspath(os.path.join(os.path.dirname(__file__),os.pardir,os.pardir))

DB_PATH = os.path.join(_project_root(),"database","app.db")

def get_connection():
	os.makedirs(os.path.dirname(DB_PATH),exist_ok=True)
	conn=sqlite3.connect(DB_PATH)
	conn.row_factory=sqlite3.Row
	return conn

def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex()

def init_db():
	with get_connection() as conn:
		# 用户表
		conn.execute(
			"""
				CREATE TABLE IF NOT EXISTS users(
						id INTEGER PRIMARY KEY AUTOINCREMENT,
						username TEXT NOT NULL UNIQUE,
						password_hash TEXT NOT NULL,
						salt TEXT NOT NULL,
						email TEXT DEFAULT '',
						role_id INTEGER DEFAULT NULL,
						status INTEGER DEFAULT 1,
						created_at TEXT NOT NULL DEFAULT (datetime('now'))
					)
			"""
			)
		# 兼容旧表：添加 email 列（如果不存在）
		try:
			conn.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
		except Exception:
			pass
		# 角色表
		conn.execute(
			"""
				CREATE TABLE IF NOT EXISTS roles(
						id INTEGER PRIMARY KEY AUTOINCREMENT,
						name TEXT NOT NULL UNIQUE,
						description TEXT DEFAULT '',
						is_system INTEGER DEFAULT 0,
						created_at TEXT NOT NULL DEFAULT (datetime('now'))
					)
			"""
			)
		# 功能/菜单表
		conn.execute(
			"""
				CREATE TABLE IF NOT EXISTS functions(
						id INTEGER PRIMARY KEY AUTOINCREMENT,
						parent_id INTEGER DEFAULT 0,
						name TEXT NOT NULL,
						code TEXT NOT NULL UNIQUE,
						icon TEXT DEFAULT '',
						path TEXT DEFAULT '',
						sort_order INTEGER DEFAULT 0,
						status INTEGER DEFAULT 1,
						created_at TEXT NOT NULL DEFAULT (datetime('now'))
					)
			"""
			)
		# 角色-功能关联表（二级联动）
		conn.execute(
			"""
				CREATE TABLE IF NOT EXISTS role_functions(
						id INTEGER PRIMARY KEY AUTOINCREMENT,
						role_id INTEGER NOT NULL,
						function_id INTEGER NOT NULL,
						UNIQUE(role_id, function_id),
						FOREIGN KEY(role_id) REFERENCES roles(id) ON DELETE CASCADE,
						FOREIGN KEY(function_id) REFERENCES functions(id) ON DELETE CASCADE
					)
			"""
			)
		# 模型引擎表
		conn.execute(
			"""
				CREATE TABLE IF NOT EXISTS model_engines(
						id INTEGER PRIMARY KEY AUTOINCREMENT,
						name TEXT NOT NULL,
						provider TEXT NOT NULL DEFAULT 'openai',
						api_base TEXT NOT NULL DEFAULT '',
						api_key TEXT NOT NULL DEFAULT '',
						model_name TEXT NOT NULL,
						model_type TEXT NOT NULL DEFAULT 'text',
						is_default INTEGER DEFAULT 0,
						temperature REAL DEFAULT 0.7,
						max_tokens INTEGER DEFAULT 2048,
						system_prompt TEXT DEFAULT '',
						enable_stream INTEGER DEFAULT 1,
						enable_think INTEGER DEFAULT 0,
						status INTEGER DEFAULT 1,
						total_tokens INTEGER DEFAULT 0,
						created_at TEXT NOT NULL DEFAULT (datetime('now')),
						updated_at TEXT NOT NULL DEFAULT (datetime('now'))
					)
			"""
			)
		# 瞭望数据源表
		conn.execute(
			"""
				CREATE TABLE IF NOT EXISTS watch_sources(
						id INTEGER PRIMARY KEY AUTOINCREMENT,
						name TEXT NOT NULL,
						url_template TEXT NOT NULL DEFAULT '',
						method TEXT NOT NULL DEFAULT 'GET',
						headers TEXT DEFAULT '{}',
						proxy TEXT DEFAULT '',
						status INTEGER DEFAULT 1,
						enable_pagination INTEGER DEFAULT 0,
						created_at TEXT NOT NULL DEFAULT (datetime('now')),
						updated_at TEXT NOT NULL DEFAULT (datetime('now'))
					)
			"""
			)
		# 瞭望采集结果表
		conn.execute(
			"""
				CREATE TABLE IF NOT EXISTS watch_results(
						id INTEGER PRIMARY KEY AUTOINCREMENT,
						source_id INTEGER DEFAULT 0,
						source_name TEXT DEFAULT '',
						keyword TEXT DEFAULT '',
						title TEXT DEFAULT '',
						url TEXT DEFAULT '',
						snippet TEXT DEFAULT '',
						raw_html TEXT DEFAULT '',
						page_num INTEGER DEFAULT 0,
						deep_status INTEGER DEFAULT 0,
						collected_at TEXT NOT NULL DEFAULT (datetime('now'))
					)
			"""
			)
		# 深度采集结果表
		conn.execute(
			"""
				CREATE TABLE IF NOT EXISTS deep_results(
						id INTEGER PRIMARY KEY AUTOINCREMENT,
						watch_result_id INTEGER NOT NULL,
						source_url TEXT DEFAULT '',
						model_engine_id INTEGER DEFAULT 0,
						model_name TEXT DEFAULT '',
						title TEXT DEFAULT '',
						full_content TEXT DEFAULT '',
						content_summary TEXT DEFAULT '',
						status TEXT NOT NULL DEFAULT 'pending',
						error_message TEXT DEFAULT '',
						log_text TEXT DEFAULT '',
						tokens_used INTEGER DEFAULT 0,
						duration_ms INTEGER DEFAULT 0,
						created_at TEXT NOT NULL DEFAULT (datetime('now')),
						FOREIGN KEY(watch_result_id) REFERENCES watch_results(id) ON DELETE CASCADE
					)
			"""
			)
		# 对话会话表
		conn.execute(
			"""
				CREATE TABLE IF NOT EXISTS conversations(
						id INTEGER PRIMARY KEY AUTOINCREMENT,
						user_id INTEGER NOT NULL,
						title TEXT DEFAULT '新对话',
						model_engine_id INTEGER DEFAULT 0,
						model_name TEXT DEFAULT '',
						created_at TEXT NOT NULL DEFAULT (datetime('now')),
						updated_at TEXT NOT NULL DEFAULT (datetime('now')),
						FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
					)
			"""
			)
		# 对话消息表
		conn.execute(
			"""
				CREATE TABLE IF NOT EXISTS chat_messages(
						id INTEGER PRIMARY KEY AUTOINCREMENT,
						conversation_id INTEGER NOT NULL,
						role TEXT NOT NULL DEFAULT 'user',
						content TEXT DEFAULT '',
						tokens_used INTEGER DEFAULT 0,
						created_at TEXT NOT NULL DEFAULT (datetime('now')),
						FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
					)
			"""
			)
		conn.commit()

def seed_admin():
    """初始化默认管理员用户 admin/123456"""
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM users WHERE username=?", ("admin",)).fetchone()
        if not row:
            salt = secrets.token_bytes(16)
            password_hash = _hash_password("123456", salt)
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                ("admin", password_hash, salt)
            )
            admin_id = cursor.lastrowid
        else:
            admin_id = row["id"]
        # 确保管理员有超级管理员角色
        role_row = conn.execute("SELECT id FROM roles WHERE name=?", ("超级管理员",)).fetchone()
        if not role_row:
            role_cursor = conn.execute(
                "INSERT INTO roles (name, description, is_system) VALUES (?, ?, ?)",
                ("超级管理员", "系统内置超级管理员，拥有所有权限，不可删除修改", 1)
            )
            role_id = role_cursor.lastrowid
        else:
            role_id = role_row["id"]
        # 绑定管理员到超级管理员角色
        existing = conn.execute("SELECT id FROM users WHERE username=? AND role_id=?", (admin_user_id := admin_id, role_id)).fetchone()
        if not existing:
            conn.execute("UPDATE users SET role_id=? WHERE id=?", (role_id, admin_user_id))
        conn.commit()

def seed_model_engines():
    """初始化默认模型引擎数据"""
    with get_connection() as conn:
        existing = conn.execute("SELECT COUNT(*) AS cnt FROM model_engines").fetchone()
        if existing["cnt"] > 0:
            return
        default_models = [
            ("Qwen 3.5 Flash 默认", "openai", "https://aigc-api.aitoolcore.com/api/v1", "YOUR_API_KEY", "qwen3.5-flash", "text", 1, 0.7, 2048, ""),
            ("GPT-4o Mini", "openai", "https://api.openai.com/v1", "sk-YOUR_KEY", "gpt-4o-mini", "text", 0, 0.7, 4096, ""),
            ("Claude 3.5 Sonnet", "openai", "https://api.openai.com/v1", "sk-YOUR_KEY", "claude-3-5-sonnet", "multimodal", 0, 0.7, 8192, ""),
        ]
        for name, provider, api_base, api_key, model_name, model_type, is_default, temp, max_tok, sys_prompt in default_models:
            conn.execute(
                """INSERT INTO model_engines (name, provider, api_base, api_key, model_name,
                   model_type, is_default, temperature, max_tokens, system_prompt)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, provider, api_base, api_key, model_name, model_type, is_default, temp, max_tok, sys_prompt)
            )
        conn.commit()

def seed_watch_sources():
    """初始化默认瞭望数据源"""
    with get_connection() as conn:
        existing = conn.execute("SELECT COUNT(*) AS cnt FROM watch_sources").fetchone()
        if existing["cnt"] > 0:
            return
        default_sources = [
            ("百度新闻搜索", "https://www.baidu.com/s?rt=1&bst=1&cl=2&tn=news&rsv_dl=ns_pc&word={关键词}", "GET",
             '{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}',
             "", 1),
        ]
        for name, url, method, headers, proxy, enable_pn in default_sources:
            conn.execute(
                """INSERT INTO watch_sources (name, url_template, method, headers, proxy, enable_pagination)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, url, method, headers, proxy, enable_pn)
            )
        conn.commit()

def seed_roles_and_functions():
    """初始化默认角色和菜单功能数据"""
    with get_connection() as conn:
        # 默认角色
        default_roles = [
            ("超级管理员", "系统内置超级管理员，拥有所有权限，不可删除修改", 1),
            ("普通管理员", "后台管理用户，可管理用户和基础功能", 0),
            ("普通用户", "前台访问用户，仅限前台功能使用", 0),
        ]
        for name, desc, is_sys in default_roles:
            conn.execute(
                "INSERT OR IGNORE INTO roles (name, description, is_system) VALUES (?, ?, ?)",
                (name, desc, is_sys)
            )
        # 默认菜单功能（对应 base.html 左侧菜单）
        default_functions = [
            # 主要功能（顶级）
            (0, "控制台", "dashboard", "fas fa-tachometer-alt", "/admin/index", 1),
            (0, "智能瞭望", "monitor", "fas fa-eye", "/admin/watch-sources", 2),
            (0, "自助问数", "query", "fas fa-database", "#", 3),
            (0, "智能对话", "chat", "fas fa-comments", "#", 4),
            # 数据分析（顶级）
            (0, "舆情分析", "sentiment", "fas fa-chart-line", "#", 5),
            (0, "风险监测", "risk", "fas fa-exclamation-triangle", "#", 6),
            # 系统管理（顶级）
            (0, "数字员工", "employee", "fas fa-robot", "#", 7),
            (0, "系统设置", "settings", "fas fa-cog", "#", 8),
            # 系统管理子功能
            (8, "用户管理", "user_manage", "fas fa-users", "#", 1),
            (8, "角色管理", "role_manage", "fas fa-user-shield", "#", 2),
            (8, "功能管理", "func_manage", "fas fa-list-alt", "#", 3),
            (8, "模型引擎", "model_engine", "fas fa-microchip", "#", 4),
        ]
        for parent_id, name, code, icon, path, sort_order in default_functions:
            conn.execute(
                "INSERT OR IGNORE INTO functions (parent_id, name, code, icon, path, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
                (parent_id, name, code, icon, path, sort_order)
            )
        # 超级管理员拥有所有功能
        super_role = conn.execute("SELECT id FROM roles WHERE name=?", ("超级管理员",)).fetchone()
        all_funcs = conn.execute("SELECT id FROM functions").fetchall()
        if super_role and all_funcs:
            for func in all_funcs:
                conn.execute(
                    "INSERT OR IGNORE INTO role_functions (role_id, function_id) VALUES (?, ?)",
                    (super_role["id"], func["id"])
                )
        # 普通管理员拥有基础管理功能
        admin_role = conn.execute("SELECT id FROM roles WHERE name=?", ("普通管理员",)).fetchone()
        if admin_role:
            basic_codes = ["dashboard", "user_manage", "role_manage", "func_manage"]
            for code in basic_codes:
                func = conn.execute("SELECT id FROM functions WHERE code=?", (code,)).fetchone()
                if func:
                    conn.execute(
                        "INSERT OR IGNORE INTO role_functions (role_id, function_id) VALUES (?, ?)",
                        (admin_role["id"], func["id"])
                    )
        conn.commit()
