"""清理 ai_skills 重复数据 + 添加唯一约束"""
import sys; sys.path.insert(0, '.')
from app.models.db import get_connection

c = get_connection()

# 1. 统计当前状态
total_before = c.execute("SELECT COUNT(*) FROM ai_skills").fetchone()[0]
print(f"当前技能总数: {total_before}")

# 2. 保留每个 name 的最小 ID，删除其余重复行
c.execute("""
    DELETE FROM ai_skills 
    WHERE id NOT IN (
        SELECT MIN(id) FROM ai_skills GROUP BY name
    )
""")
c.commit()
deleted = total_before - c.execute("SELECT COUNT(*) FROM ai_skills").fetchone()[0]
print(f"删除了 {deleted} 条重复数据")

# 3. 尝试添加唯一索引（忽略已存在的）
try:
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_name_unique ON ai_skills(name)")
    c.commit()
    print("已添加 name 唯一约束")
except Exception as e:
    print(f"索引创建: {e}")

# 4. 最终状态
total_after = c.execute("SELECT COUNT(*) FROM ai_skills").fetchone()[0]
print(f"当前技能总数: {total_after}")

rows = c.execute("SELECT id, name, category FROM ai_skills ORDER BY id").fetchall()
print("\n现有技能列表:")
for r in rows:
    print(f"  [{r['id']}] {r['name']} ({r['category']})")
