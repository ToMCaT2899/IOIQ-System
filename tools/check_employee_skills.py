import sys; sys.path.insert(0, '.')
from app.models.db import get_connection
from app.models.ai_skill import AiSkillRepository
import json

def _resolve_skill_ids(skills_raw):
    if not skills_raw: return []
    try: data = json.loads(skills_raw)
    except: return []
    if not data: return []
    if isinstance(data[0], int): return data
    return []

c = get_connection()
rows = c.execute("SELECT id, name, skills, system_prompt FROM digital_employees").fetchall()
for r in rows:
    system_prompt = r["system_prompt"] or ""
    skill_ids = _resolve_skill_ids(r["skills"] or "")
    skill_info = []
    if skill_ids:
        for sid in skill_ids:
            s = AiSkillRepository.get_by_id(sid)
            if s and s["prompt_template"]:
                skill_info.append(f"【{s['name']}】{s['prompt_template']}")
    
    print(f"[{r['id']}] {r['name']}")
    print(f"  skills raw: {r['skills']}")
    print(f"  skill_ids parsed: {skill_ids}")
    print(f"  system_prompt: {(system_prompt or 'NULL')[:80]}")
    print(f"  skills injected: {len(skill_info)}")
    for si in skill_info:
        print(f"    {si[:80]}")
    print()
