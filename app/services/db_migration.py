# 数据库迁移服务 — SQLite ↔ MySQL 数据迁移

"""
支持两种迁移方向：
1. SQLite → MySQL
2. MySQL → SQLite

迁移流程：
1. 读取源数据库所有表名
2. 在目标数据库创建表结构
3. 逐表逐行复制数据
4. 记录迁移进度和日志
"""

from app.models.db import get_engine, get_db_config, set_db_config, get_connection, _default_config


def _row_to_dict(r):
    """将 sqlite3.Row 或 _MySQLRow 转为普通 dict"""
    if hasattr(r, '_data'):
        return r._data.copy()
    elif hasattr(r, 'keys'):
        return {k: r[k] for k in r.keys()}
    return dict(r)


def _get_all_tables(conn):
    """获取当前数据库所有用户表名"""
    engine = get_engine()
    if engine == "sqlite":
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        tables = [r[0] for r in rows]
    else:
        rows = conn.execute("SHOW TABLES").fetchall()
        tables = [list(_row_to_dict(r).values())[0] for r in rows]
    return [t for t in tables if t not in ("sqlite_sequence",)]


def _get_table_columns(conn, table_name: str):
    """获取表的列定义"""
    engine = get_engine()
    if engine == "sqlite":
        rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    else:
        rows = conn.execute(f"DESCRIBE `{table_name}`").fetchall()
    return [_row_to_dict(r) for r in rows]


def _get_column_names(conn, table_name: str):
    """获取表的所有列名"""
    cols = _get_table_columns(conn, table_name)
    if cols and "name" in cols[0]:
        return [c["name"] for c in cols]
    elif cols and "Field" in cols[0]:
        return [c["Field"] for c in cols]
    # fallback: get keys
    return list(cols[0].keys()) if cols else []


def _get_primary_key(table_name: str, columns: list) -> str:
    """尝试找到主键列名"""
    for c in columns:
        c_dict = dict(c) if not isinstance(c, dict) else c
        name = c_dict.get("name", c_dict.get("Field", ""))
        pk = c_dict.get("pk", c_dict.get("Key", ""))
        if pk in (1, "PRI"):
            return name
    if columns:
        c_dict = dict(columns[0]) if not isinstance(columns[0], dict) else columns[0]
        return c_dict.get("name", c_dict.get("Field", "id"))
    return "id"


def migrate_data(progress_callback=None) -> dict:
    """
    执行数据迁移（从当前引擎迁移到另一个引擎）。

    参数:
        progress_callback: 可选回调函数 callback(stage, message, percent)

    返回:
        {"ok": bool, "message": str, "tables_migrated": int, "rows_migrated": int,
         "source_engine": str, "target_engine": str}
    """
    source_engine = get_engine()
    target_engine = "mysql" if source_engine == "sqlite" else "sqlite"

    if target_engine == "mysql":
        try:
            import pymysql
        except ImportError:
            return {"ok": False, "message": "PyMySQL 未安装，请执行 pip install pymysql"}

    def emit(stage, msg, pct):
        if progress_callback:
            progress_callback(stage, msg, pct)

    emit("start", f"开始迁移: {source_engine} → {target_engine}", 0)

    try:
        # 1. 从源数据库读取所有数据
        emit("read", "读取源数据库表结构...", 10)
        source_conn = get_connection()
        tables = _get_all_tables(source_conn)

        if not tables:
            source_conn.close()
            return {"ok": False, "message": "源数据库无表可迁移"}

        all_data = {}
        for table in tables:
            cols = _get_column_names(source_conn, table)
            # 用 * 读取（避免列名转义问题）
            rows = source_conn.execute(f"SELECT * FROM \"{table}\"" if source_engine == "sqlite" else f"SELECT * FROM `{table}`").fetchall()
            # 读取数据行并转为普通 dict
            row_dicts = [_row_to_dict(r) for r in rows]
            all_data[table] = {"columns": cols, "rows": row_dicts}
        source_conn.close()

        emit("switch", f"切换到目标引擎 {target_engine}...", 30)

        # 2. 切换到目标引擎
        cfg = get_db_config()
        cfg["engine"] = target_engine
        set_db_config(cfg)

        # 3. 在目标数据库创建表
        emit("create", "在目标数据库创建表结构...", 40)
        from app.models.db import init_db
        init_db()

        # 获取目标库中实际存在的表（init_db 可能遗漏动态创建的表）
        with get_connection() as tconn:
            target_tables = set(_get_all_tables(tconn))

        # 4. 写入数据
        total_tables = len(tables)
        total_rows = 0
        migrated_tables = 0
        skipped_tables = 0

        with get_connection() as target_conn:
            for idx, table in enumerate(tables):
                table_data = all_data[table]
                cols = table_data["columns"]
                rows = table_data["rows"]

                if table not in target_tables:
                    skipped_tables += 1
                    pct = 40 + int((idx + 1) / max(total_tables, 1) * 50)
                    emit("copy", f"表 {table}: 跳过（目标库无此表）", pct)
                    continue

                if not rows:
                    migrated_tables += 1
                    pct = 40 + int((idx + 1) / max(total_tables, 1) * 50)
                    emit("copy", f"表 {table}: 0 行（空表）", pct)
                    continue

                # 构建批量插入
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join([f'"{c}"' for c in cols])
                sql = f"INSERT INTO \"{table}\" ({col_names}) VALUES ({placeholders})"

                if target_engine == "mysql":
                    sql = sql.replace("?", "%s").replace('"', '`')

                batch = []
                for row in rows:
                    values = [row.get(c, "") for c in cols]
                    batch.append(values)

                    if len(batch) >= 100:
                        for vals in batch:
                            target_conn.execute(sql, vals)
                        target_conn.commit()
                        batch = []

                # 剩余批次
                for vals in batch:
                    target_conn.execute(sql, vals)
                target_conn.commit()

                total_rows += len(rows)
                migrated_tables += 1
                pct = 40 + int((idx + 1) / max(total_tables, 1) * 50)
                emit("copy", f"表 {table}: {len(rows)} 行已迁移", pct)

        emit("done", f"迁移完成: {migrated_tables} 个表, {total_rows} 行数据", 100)

        return {
            "ok": True,
            "message": "数据迁移成功",
            "tables_migrated": migrated_tables,
            "rows_migrated": total_rows,
            "source_engine": source_engine,
            "target_engine": target_engine,
        }

    except Exception as e:
        # 迁移失败，回滚到源引擎
        cfg = get_db_config()
        cfg["engine"] = source_engine
        set_db_config(cfg)
        emit("error", f"迁移失败: {str(e)}", 0)
        return {
            "ok": False,
            "message": f"数据迁移失败: {str(e)}",
            "source_engine": source_engine,
            "target_engine": target_engine,
        }


def switch_engine(target: str) -> dict:
    """
    仅切换引擎（不迁移数据），用于已手动迁移或重建的场景。

    参数:
        target: "sqlite" 或 "mysql"

    返回:
        {"ok": bool, "message": str}
    """
    if target not in ("sqlite", "mysql"):
        return {"ok": False, "message": f"不支持的引擎: {target}"}

    if target == "mysql":
        try:
            import pymysql
        except ImportError:
            return {"ok": False, "message": "PyMySQL 未安装，请执行 pip install pymysql"}

    cfg = get_db_config()
    cfg["engine"] = target
    set_db_config(cfg)

    # 在新引擎上初始化表结构
    try:
        from app.models.db import init_db
        init_db()
        return {"ok": True, "message": f"已切换到 {target}，表结构已初始化"}
    except Exception as e:
        cfg["engine"] = "sqlite"
        set_db_config(cfg)
        return {"ok": False, "message": f"切换失败: {str(e)}"}
