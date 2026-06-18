import sys; sys.path.insert(0, '.')
from app.models.db import get_connection
c = get_connection()
# Show schema
rows = c.execute("PRAGMA table_info(ai_skills)").fetchall()
for r in rows:
    print(f"  {r['name']}  {r['type']}  nullable={not r['notnull']}  default={r['dflt_value']}")
print()
print("Indexes:")
rows = c.execute("PRAGMA index_list(ai_skills)").fetchall()
for r in rows:
    print(f"  {r['name']}  unique={r['unique']}")
