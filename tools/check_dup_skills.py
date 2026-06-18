import sys; sys.path.insert(0, '.')
from app.models.db import get_connection
c = get_connection()
rows = c.execute("SELECT name, COUNT(*) as cnt FROM ai_skills GROUP BY name HAVING cnt>1 ORDER BY cnt DESC").fetchall()
for r in rows:
    print(f"  {r['name']}: {r['cnt']}条")
total = c.execute("SELECT COUNT(*) FROM ai_skills").fetchone()[0]
print(f"  总技能数: {total}")
