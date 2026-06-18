"""数据库双引擎切换完整测试"""
import os
import sys; sys.path.insert(0, '.')
from app.models.db import (
    get_engine, get_db_config, set_db_config,
    test_mysql_connection, get_connection, _load_config,
)
from app.services.db_migration import switch_engine

passed = 0; failed = 0
def test(name, result, expected=True):
    global passed, failed
    ok = result if isinstance(expected, bool) else result == expected
    if ok: passed += 1; print(f"  [PASS] {name}")
    else:   failed += 1; print(f"  [FAIL] {name}: got={result}")

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ──────────────────────────────
section("1. 当前状态")
# ──────────────────────────────
engine = get_engine()
print(f"  当前引擎: {engine}")
test("1.1 当前引擎是 sqlite", engine, "sqlite")

cfg = get_db_config()
test("1.2 配置中 sqlite.path 存在", os.path.isfile(cfg["sqlite"]["path"]) if "sqlite" in cfg else False)

test("1.3 db_config.json 存在", os.path.isfile("database/db_config.json"))

# ──────────────────────────────
section("2. SQLite 读写验证")
# ──────────────────────────────
conn = get_connection()
try:
    rows = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchall()
    cnt = rows[0]["cnt"]
    test(f"2.1 users 表可读 (行数={cnt})", cnt > 0)

    rows = conn.execute("SELECT username FROM users LIMIT 1").fetchall()
    test("2.2 能查到用户名", len(rows) > 0)
except Exception as e:
    test(f"2.1 users 表可读", False)
    print(f"       错误: {e}")
conn.close()

# ──────────────────────────────
section("3. MySQL 连接测试")
# ──────────────────────────────
mysql_cfg = cfg.get("mysql", {})
print(f"  MySQL 配置: {mysql_cfg.get('host','?')}:{mysql_cfg.get('port','?')}/{mysql_cfg.get('database','?')}")
result = test_mysql_connection(mysql_cfg)
print(f"  测试结果: {result}")
# MySQL 连接可能成功也可能失败, 都是正常的
print(f"  状态: {'ok' if result['ok'] else '预期失败(无MySQL服务)，正常行为'}")

# ──────────────────────────────
section("4. 切换到 MySQL (预期失败/回滚)")
# ──────────────────────────────
result = switch_engine("mysql")
print(f"  切换结果: {result}")
test("4.1 切换后引擎仍为 sqlite", get_engine(), "sqlite")
# 如果 PyMySQL 没装或 MySQL 不可用，切换应该返回 ok=False

# ──────────────────────────────
section("5. 切换到不合法引擎")
# ──────────────────────────────
result = switch_engine("oracle")
test("5.1 拒绝不合法引擎", result["ok"], False)
test("5.2 引擎仍为 sqlite", get_engine(), "sqlite")

# ──────────────────────────────
section("6. 切换回 SQLite (幂等)")
# ──────────────────────────────
result = switch_engine("sqlite")
test("6.1 切换成功", result["ok"], True)
test("6.2 引擎是 sqlite", get_engine(), "sqlite")

# ──────────────────────────────
section("7. 切换后数据完整性")
# ──────────────────────────────
conn = get_connection()
try:
    rows = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchall()
    cnt = rows[0]["cnt"]
    test(f"7.1 切换后 users 可读 (行数={cnt})", cnt > 0)

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    print(f"  表数量: {len(tables)}")
    test("7.2 表结构存在", len(tables) > 0)
except Exception as e:
    test("7.1 数据完整性", False)
    print(f"       错误: {e}")
conn.close()

# ──────────────────────────────
section("8. 配置读写循环")
# ──────────────────────────────
cfg2 = _load_config()
test("8.1 重新加载配置引擎为 sqlite", cfg2.get("engine"), "sqlite")
cfg2["engine"] = "sqlite"
set_db_config(cfg2)
cfg3 = get_db_config()
test("8.2 写入后读取一致", cfg3.get("engine"), "sqlite")

# ──────────────────────────────
section("9. 边界条件")
# ──────────────────────────────
# 空字符串
result = switch_engine("")
test("9.1 空字符串拒绝", result["ok"], False)

# 大小写
result = switch_engine("SQLITE")
test("9.2 大写 SQLITE 拒绝", result["ok"], False)

print(f"\n{'='*60}")
print(f"  总计: {passed+failed} 项, 通过 {passed}, 失败 {failed}")
print(f"{'='*60}")
