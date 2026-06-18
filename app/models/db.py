# 数据库核心模块 — SQLite/MySQL 双引擎动态切换

import os
import json
import hashlib
import secrets
import threading

# ============================================================
# 全局状态
# ============================================================
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
_db_dir = os.path.join(_project_root, "database")
DB_CONFIG_FILE = os.path.join(_db_dir, "db_config.json")

# 引擎状态: "sqlite" | "mysql"
_engine = "sqlite"
_mysql_pool = None
_mysql_pool_lock = threading.Lock()
# conn cache for sqlite (thread-local not needed for sqlite, but keep simple)
_config_cache = None


def _default_config():
    return {
        "engine": "sqlite",
        "sqlite": {"path": os.path.join(_db_dir, "app.db")},
        "mysql": {
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "",
            "database": "app",
            "charset": "utf8mb4",
        },
    }


def _load_config():
    os.makedirs(_db_dir, exist_ok=True)
    if os.path.isfile(DB_CONFIG_FILE):
        try:
            with open(DB_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg
        except (json.JSONDecodeError, IOError):
            pass
    cfg = _default_config()
    _save_config(cfg)
    return cfg


def _save_config(cfg):
    os.makedirs(_db_dir, exist_ok=True)
    with open(DB_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_db_config():
    """获取当前数据库配置"""
    global _config_cache
    if _config_cache is None:
        _config_cache = _load_config()
    return _config_cache


def get_engine():
    """获取当前引擎名称: 'sqlite' 或 'mysql'"""
    return get_db_config().get("engine", "sqlite")


def set_db_config(config: dict):
    """更新数据库配置并保存"""
    global _config_cache
    _config_cache = config
    _save_config(config)


# ============================================================
# MySQL Row 包装器（兼容 sqlite3.Row）
# ============================================================
class _MySQLRow:
    """模拟 sqlite3.Row 的 dict + 属性访问"""

    def __init__(self, data: dict):
        self._data = data

    def keys(self):
        return self._data.keys()

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __iter__(self):
        return iter(self._data)

    def __repr__(self):
        return repr(self._data)


class _MySQLCursor:
    """包装 PyMySQL cursor 以兼容 sqlite3.Cursor"""

    def __init__(self, cursor, conn):
        self._cursor = cursor
        self._conn = conn

    def execute(self, sql, params=None):
        # MySQL 不支持 ? 占位符，统一转换为 %s
        if params:
            sql = sql.replace("?", "%s")
        return self._cursor.execute(sql, params)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        # PyMySQL DictCursor 返回 dict
        if isinstance(row, dict):
            return _MySQLRow(row)
        cols = [d[0] for d in self._cursor.description]
        return _MySQLRow(dict(zip(cols, row)))

    def fetchall(self):
        rows = self._cursor.fetchall()
        cols = [d[0] for d in self._cursor.description]
        result = []
        for row in rows:
            if isinstance(row, dict):
                result.append(_MySQLRow(row))
            else:
                result.append(_MySQLRow(dict(zip(cols, row))))
        return result

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        pass  # handled by connection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def __iter__(self):
        return iter(self.fetchall())


class _MySQLConnection:
    """包装 PyMySQL Connection 以兼容 sqlite3.Connection"""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        from pymysql.cursors import DictCursor
        cur = self._conn.cursor(DictCursor)
        return _MySQLCursor(cur, self._conn)

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


# ============================================================
# MySQL 连接池（简化版）
# ============================================================
def _get_mysql_connection():
    """获取 MySQL 连接（如果 PyMySQL 不可用则抛异常）"""
    cfg = get_db_config()["mysql"]
    import pymysql
    conn = pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset=cfg.get("charset", "utf8mb4"),
        autocommit=False,
    )
    return _MySQLConnection(conn)


# ============================================================
# 公共 API
# ============================================================

def get_connection():
    """获取数据库连接（根据当前引擎返回 SQLite 或 MySQL 连接）"""
    engine = get_engine()
    if engine == "mysql":
        return _get_mysql_connection()
    else:
        os.makedirs(_db_dir, exist_ok=True)
        cfg = get_db_config()
        sqlite_path = cfg.get("sqlite", {}).get("path", os.path.join(_db_dir, "app.db"))
        import sqlite3
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn


def get_path():
    """返回当前数据库文件路径（仅 SQLite）"""
    cfg = get_db_config()
    return cfg.get("sqlite", {}).get("path", os.path.join(_db_dir, "app.db"))


def test_mysql_connection(config: dict) -> dict:
    """测试 MySQL 连接是否可用，返回 {ok, message, server_info}"""
    try:
        import pymysql
        conn = pymysql.connect(
            host=config.get("host", "localhost"),
            port=int(config.get("port", 3306)),
            user=config.get("user", "root"),
            password=config.get("password", ""),
            database=config.get("database", "app"),
            charset=config.get("charset", "utf8mb4"),
            connect_timeout=5,
        )
        info = conn.get_server_info()
        conn.close()
        return {"ok": True, "message": "连接成功", "server_info": f"MySQL {info}"}
    except ImportError:
        return {"ok": False, "message": "PyMySQL 未安装，请执行 pip install pymysql"}
    except Exception as e:
        return {"ok": False, "message": f"连接失败: {str(e)}"}


# ============================================================
# 数据库初始化（创建表结构）
# ============================================================

def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex()


def _sqlite_type(col):
    """根据列定义返回 SQLite 兼容的 SQL 片段"""
    return col


def _mysql_type(col):
    """将列定义转换为 MySQL 兼容（仅处理关键差异）"""
    # 替换自增语法
    col = col.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "INTEGER PRIMARY KEY AUTO_INCREMENT")
    # 替换 default datetime
    col = col.replace("TEXT NOT NULL DEFAULT (datetime('now'))", "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
    col = col.replace("TEXT NOT NULL DEFAULT (datetime('now')", "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
    col = col.replace("DEFAULT (datetime('now'))", "DEFAULT CURRENT_TIMESTAMP")
    # 替换 TEXT 为 VARCHAR 用于更小字段（MySQL TEXT 不能有 default）
    # 保持 TEXT 用于 content/snippet 等大字段
    return col


def _init_tables(conn_execute):
    """执行建表语句（引擎无关）"""
    tables_sql = [
        # 用户表
        """CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            email TEXT DEFAULT '',
            role_id INTEGER DEFAULT NULL,
            status INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 角色表
        """CREATE TABLE IF NOT EXISTS roles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            is_system INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 功能/菜单表
        """CREATE TABLE IF NOT EXISTS functions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER DEFAULT 0,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            icon TEXT DEFAULT '',
            path TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            status INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 角色-功能关联表
        """CREATE TABLE IF NOT EXISTS role_functions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            function_id INTEGER NOT NULL,
            UNIQUE(role_id, function_id)
        )""",
        # 模型引擎表
        """CREATE TABLE IF NOT EXISTS model_engines(
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
        )""",
        # 瞭望数据源表
        """CREATE TABLE IF NOT EXISTS watch_sources(
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
        )""",
        # 瞭望采集结果表
        """CREATE TABLE IF NOT EXISTS watch_results(
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
        )""",
        # 深度采集结果表
        """CREATE TABLE IF NOT EXISTS deep_results(
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
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 对话会话表
        """CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT '新对话',
            model_engine_id INTEGER DEFAULT 0,
            model_name TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            tags TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 对话消息表
        """CREATE TABLE IF NOT EXISTS chat_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            content TEXT DEFAULT '',
            tokens_used INTEGER DEFAULT 0,
            review_status TEXT NOT NULL DEFAULT 'normal',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 系统设置表
        """CREATE TABLE IF NOT EXISTS system_settings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT DEFAULT '',
            category TEXT DEFAULT 'general',
            label TEXT DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 操作日志表
        """CREATE TABLE IF NOT EXISTS operation_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operator TEXT DEFAULT '',
            action TEXT NOT NULL,
            detail TEXT DEFAULT '',
            ip TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 网络搜索日志表
        """CREATE TABLE IF NOT EXISTS web_search_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            result_count INTEGER DEFAULT 0,
            source TEXT DEFAULT 'fallback',
            source_urls TEXT DEFAULT '',
            user TEXT DEFAULT '',
            duration_ms INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 接口管理表
        """CREATE TABLE IF NOT EXISTS api_interfaces(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL DEFAULT '',
            method TEXT NOT NULL DEFAULT 'GET',
            description TEXT DEFAULT '',
            params TEXT DEFAULT '{}',
            headers TEXT DEFAULT '{}',
            auth_type TEXT DEFAULT 'none',
            status INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 接口调用日志表
        """CREATE TABLE IF NOT EXISTS api_call_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interface_id INTEGER DEFAULT 0,
            interface_name TEXT DEFAULT '',
            method TEXT DEFAULT 'GET',
            path TEXT DEFAULT '',
            request_params TEXT DEFAULT '',
            request_headers TEXT DEFAULT '',
            response_status INTEGER DEFAULT 0,
            response_body TEXT DEFAULT '',
            response_time_ms INTEGER DEFAULT 0,
            success INTEGER DEFAULT 0,
            error_message TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 数字员工表
        """CREATE TABLE IF NOT EXISTS digital_employees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            avatar TEXT DEFAULT '',
            role_name TEXT DEFAULT '',
            greeting TEXT DEFAULT '',
            skills TEXT DEFAULT '[]',
            model_engine_id INTEGER DEFAULT 0,
            model_name TEXT DEFAULT '',
            system_prompt TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'enabled',
            version TEXT DEFAULT '1.0',
            total_calls INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            total_duration_ms INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 数字员工版本表
        """CREATE TABLE IF NOT EXISTS employee_versions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            version TEXT NOT NULL DEFAULT '1.0',
            system_prompt TEXT DEFAULT '',
            skills TEXT DEFAULT '[]',
            change_log TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # AI 技能表
        """CREATE TABLE IF NOT EXISTS ai_skills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT NOT NULL DEFAULT '通用',
            trigger_keywords TEXT DEFAULT '[]',
            model_engine_id INTEGER DEFAULT 0,
            model_name TEXT DEFAULT '',
            prompt_template TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'enabled',
            icon TEXT DEFAULT 'fa-tools',
            call_count INTEGER DEFAULT 0,
            version TEXT DEFAULT '1.0',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 技能调用日志表
        """CREATE TABLE IF NOT EXISTS skill_call_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_id INTEGER DEFAULT 0,
            skill_name TEXT DEFAULT '',
            caller_type TEXT DEFAULT '',
            caller_id INTEGER DEFAULT 0,
            caller_name TEXT DEFAULT '',
            tokens_used INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            success INTEGER DEFAULT 0,
            error_message TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 舆情分析结果表
        """CREATE TABLE IF NOT EXISTS sentiment_analysis(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'chat',
            source_id INTEGER DEFAULT 0,
            content TEXT DEFAULT '',
            sentiment TEXT NOT NULL DEFAULT 'neutral',
            sentiment_score REAL DEFAULT 0.0,
            emotion_label TEXT DEFAULT '',
            risk_level TEXT NOT NULL DEFAULT 'low',
            keywords TEXT DEFAULT '[]',
            entities TEXT DEFAULT '[]',
            hot_value REAL DEFAULT 0.0,
            source_user TEXT DEFAULT '',
            source_title TEXT DEFAULT '',
            analyzed_by TEXT NOT NULL DEFAULT 'rule',
            model_engine_id INTEGER DEFAULT 0,
            model_name TEXT DEFAULT '',
            tokens_used INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        # 舆情告警表
        """CREATE TABLE IF NOT EXISTS sentiment_alerts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            alert_type TEXT NOT NULL DEFAULT 'negative_surge',
            risk_level TEXT NOT NULL DEFAULT 'medium',
            keywords TEXT DEFAULT '[]',
            affected_count INTEGER DEFAULT 0,
            trend_score REAL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'unread',
            resolved_by TEXT DEFAULT '',
            resolved_at TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
    ]
    engine_type = get_engine()
    for sql in tables_sql:
        if engine_type == "mysql":
            sql = _mysql_type(sql)
        conn_execute(sql)


def init_db():
    """初始化数据库（创建所有表）"""
    with get_connection() as conn:
        if get_engine() == "mysql":
            _init_tables(lambda s: conn.execute(s))
            conn.commit()
        else:
            _init_tables(lambda s: conn.execute(s))
            # SQLite 兼容旧表列
            _add_missing_columns_sqlite(conn)
            conn.commit()


def _add_missing_columns_sqlite(conn):
    """SQLite 模式：为旧表添加缺失列"""
    alterations = [
        ("users", "email TEXT DEFAULT ''"),
        ("conversations", "status TEXT NOT NULL DEFAULT 'active'"),
        ("conversations", "tags TEXT DEFAULT ''"),
        ("chat_messages", "review_status TEXT NOT NULL DEFAULT 'normal'"),
    ]
    for table, col_def in alterations:
        col_name = col_def.split()[0]
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
        except Exception:
            pass


# ============================================================
# 种子数据
# ============================================================

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

        role_row = conn.execute("SELECT id FROM roles WHERE name=?", ("超级管理员",)).fetchone()
        if not role_row:
            role_cursor = conn.execute(
                "INSERT INTO roles (name, description, is_system) VALUES (?, ?, ?)",
                ("超级管理员", "系统内置超级管理员，拥有所有权限，不可删除修改", 1)
            )
            role_id = role_cursor.lastrowid
        else:
            role_id = role_row["id"]

        conn.execute("UPDATE users SET role_id=? WHERE id=?", (role_id, admin_id))
        conn.commit()


def seed_model_engines():
    """初始化默认模型引擎数据"""
    with get_connection() as conn:
        existing = conn.execute("SELECT COUNT(*) AS cnt FROM model_engines").fetchone()
        if existing["cnt"] > 0:
            return
        default_models = [
            ("Qwen 3.5 Flash 默认", "openai", "https://aigc-api.aitoolcore.com/api/v1",
             "YOUR_API_KEY", "qwen3.5-flash", "text", 1, 0.7, 2048, ""),
            ("GPT-4o Mini", "openai", "https://api.openai.com/v1", "sk-YOUR_KEY",
             "gpt-4o-mini", "text", 0, 0.7, 4096, ""),
            ("Claude 3.5 Sonnet", "openai", "https://api.openai.com/v1", "sk-YOUR_KEY",
             "claude-3-5-sonnet", "multimodal", 0, 0.7, 8192, ""),
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
            ("百度新闻搜索",
             "https://www.baidu.com/s?rt=1&bst=1&cl=2&tn=news&rsv_dl=ns_pc&word={关键词}",
             "GET",
             '{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}',
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
        default_functions = [
            (0, "控制台", "dashboard", "fas fa-tachometer-alt", "/admin/index", 1),
            (0, "智能瞭望", "monitor", "fas fa-eye", "/admin/watch-sources", 2),
            (0, "自助问数", "query", "fas fa-database", "#", 3),
            (0, "智能对话", "chat", "fas fa-comments", "#", 4),
            (0, "舆情分析", "sentiment", "fas fa-chart-line", "#", 5),
            (0, "风险监测", "risk", "fas fa-exclamation-triangle", "#", 6),
            (0, "数字员工", "employee", "fas fa-robot", "#", 7),
            (0, "系统设置", "settings", "fas fa-cog", "#", 8),
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
        super_role = conn.execute("SELECT id FROM roles WHERE name=?", ("超级管理员",)).fetchone()
        all_funcs = conn.execute("SELECT id FROM functions").fetchall()
        if super_role and all_funcs:
            for func in all_funcs:
                conn.execute(
                    "INSERT OR IGNORE INTO role_functions (role_id, function_id) VALUES (?, ?)",
                    (super_role["id"], func["id"])
                )
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


def seed_skills():
    """初始化内置 AI 技能数据"""
    with get_connection() as conn:
        conn.execute("SELECT COUNT(*) AS cnt FROM ai_skills")
        skills = [
            ("天气查询", "查询指定城市的实时天气和未来预报", "生活服务",
             '["天气","气温","下雨","晴天"]', 0, "", "你是一个天气查询助手，请根据用户输入的城市名返回天气信息。", "enabled", "fa-cloud-sun", "1.0"),
            ("音乐推荐", "根据心情或场景推荐音乐", "生活服务",
             '["音乐","歌曲","推荐","听歌"]', 0, "", "你是一个音乐推荐助手，请根据用户描述推荐合适的音乐。", "enabled", "fa-music", "1.0"),
            ("SQL问数", "将自然语言转换为 SQL 查询数据库", "数据分析",
             '["查询","统计","SQL","数据"]', 0, "", "你是一个SQL查询助手，将用户的自然语言问题转换为SQL查询语句。", "enabled", "fa-database", "1.0"),
            ("文本翻译", "多语言翻译助手", "办公效率",
             '["翻译","translate","英文","中文"]', 0, "", "你是一个翻译助手，准确地将用户输入的文本翻译为目标语言。", "enabled", "fa-language", "1.0"),
            ("代码生成", "根据需求描述生成代码", "开发工具",
             '["代码","编程","code","写一个"]', 0, "", "你是一个代码生成助手，根据用户需求编写代码。", "enabled", "fa-code", "1.0"),
            ("周报生成", "根据工作内容自动生成周报", "办公效率",
             '["周报","工作总结","汇报"]', 0, "", "你是一个周报生成助手，将用户的工作内容整理为结构化周报。", "enabled", "fa-file-alt", "1.0"),
            ("智能摘要", "对长文本生成摘要", "文本处理",
             '["摘要","总结","概括"]', 0, "", "你是一个文本摘要助手，将长文本压缩为简洁摘要。", "enabled", "fa-file-lines", "1.0"),
            ("数据分析", "对输入的数据进行多维度分析", "数据分析",
             '["分析","数据","报表","图表"]', 0, "", "你是一个数据分析助手，对输入的数据进行专业分析。", "enabled", "fa-chart-pie", "1.0"),
        ]
        for name, desc, cat, keywords, engine_id, model, prompt, status, icon, ver in skills:
            conn.execute(
                "INSERT OR IGNORE INTO ai_skills (name, description, category, trigger_keywords, "
                "model_engine_id, model_name, prompt_template, status, icon, version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, desc, cat, keywords, engine_id, model, prompt, status, icon, ver)
            )
        conn.commit()
