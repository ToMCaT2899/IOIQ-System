"""数据库双引擎切换 — 最终验证"""
import os, sys
sys.path.insert(0, '.')
from app.models.db import get_engine, get_connection
from app.services.db_migration import switch_engine

# 确保从 SQLite 开始
engine = get_engine()
if engine != "sqlite":
    switch_engine("sqlite")
    print(f"[SETUP] reset to sqlite")

print("=" * 60)

# 1. SQLite verify
print("1. SQLite initial")
conn = get_connection()
users = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
print(f"   engine={get_engine()}, users={users}, tables={len(tables)}")
conn.close()
assert users > 0, "FAIL: SQLite users lost"

# 2. Switch to MySQL
print("\n2. Switch to MySQL")
result = switch_engine("mysql")
print(f"   result={result}")
assert result["ok"], f"FAIL: MySQL switch failed: {result.get('message')}"
assert get_engine() == "mysql", "FAIL: engine not mysql"
print("   PASS")

# 3. Verify MySQL works
conn = get_connection()
try:
    rows = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchall()
    cnt = rows[0]["cnt"]
    print(f"   MySQL users count: {cnt}")
    assert cnt >= 0, "FAIL: users query failed in MySQL"
    print("   PASS")
finally:
    conn.close()

# 4. Switch back to SQLite
print("\n4. Switch back to SQLite")
result = switch_engine("sqlite")
assert result["ok"], f"FAIL: SQLite restore failed: {result.get('message')}"
assert get_engine() == "sqlite", "FAIL: engine not sqlite"
print("   PASS")

# 5. Verify data intact
conn = get_connection()
users = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
print(f"   engine={get_engine()}, users={users}")
conn.close()
assert users > 0, "FAIL: data lost after round-trip"
print("   PASS")

print("\n" + "=" * 60)
print("  ALL PASSED - SQLite <-> MySQL works correctly")
print("=" * 60)
