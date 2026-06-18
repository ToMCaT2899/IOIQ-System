import sys; sys.path.insert(0, '.')
from app.models.db import get_connection
c = get_connection()
rows = c.execute("SELECT id, name, category, prompt_template FROM ai_skills").fetchall()
for r in rows:
    tmpl = (r["prompt_template"] or "")[:80]
    print(f"  [{r['id']}] {r['name']} ({r['category']}): {tmpl}")
