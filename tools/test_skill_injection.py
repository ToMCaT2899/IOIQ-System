"""
测试：数字员工技能注入功能
验证对话时绑定的技能 prompt 是否正确注入到 system prompt 中
"""
import sys, os, json
sys.path.insert(0, ".")

from app.models.db import get_connection
from app.models.ai_skill import AiSkillRepository
from app.models.digital_employee import DigitalEmployeeRepository

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}  {detail}")
        failed += 1

# 测试使用的辅助函数（从 controller 复制）
def _resolve_skill_ids(skills_raw):
    if not skills_raw:
        return []
    try:
        data = json.loads(skills_raw)
    except Exception:
        return []
    if not data:
        return []
    if isinstance(data[0], int):
        return data
    return []


def build_system_prompt(employee: dict) -> str:
    """模拟 EmployeeChatSSEHandler 中 system_prompt 的构建逻辑"""
    system_prompt = employee.get("system_prompt") or f"你是 {employee['name']}，{employee['role_name']}。{employee.get('greeting', '')}"

    skill_ids = _resolve_skill_ids(employee.get("skills") or "")
    if skill_ids:
        skill_prompts = []
        for sid in skill_ids:
            skill = AiSkillRepository.get_by_id(sid)
            if skill and skill["prompt_template"]:
                skill_prompts.append(f"【{skill['name']}】{skill['prompt_template']}")
        if skill_prompts:
            system_prompt += "\n\n你可以调用以下技能来帮助用户：\n" + "\n".join(skill_prompts)
            system_prompt += "\n当用户的问题匹配某个技能时，请使用该技能的能力来回答。"

    return system_prompt


print("=" * 60)
print("数字员工技能注入测试")
print("=" * 60)

# ---- 准备测试数据 ----
print("\n[准备] 创建测试技能...")
c = get_connection()

# 清理旧测试数据
c.execute("DELETE FROM ai_skills WHERE name LIKE 'TEST_%'")
c.execute("DELETE FROM digital_employees WHERE name LIKE 'TEST_%'")
c.commit()

# 创建 2 个测试技能
skill1_id = AiSkillRepository.create(
    name="TEST_天气查询",
    description="测试天气查询技能",
    category="生活服务",
    prompt_template="你是一个天气查询助手。当用户问天气时，返回城市+温度+天气状况。",
    status="enabled"
)
skill2_id = AiSkillRepository.create(
    name="TEST_翻译助手",
    description="测试翻译技能", 
    category="办公效率",
    prompt_template="你是一个翻译助手。将用户输入翻译为目标语言。",
    status="enabled"
)
print(f"  测试技能已创建: id={skill1_id}, {skill2_id}")

# 创建测试员工（绑定技能）
employee_id = DigitalEmployeeRepository.create(
    name="TEST_测试员工",
    role_name="测试角色",
    greeting="你好，我是测试员工。",
    system_prompt="你是一个测试助理。",
    skills=json.dumps([skill1_id, skill2_id]),
    model_engine_id=0,
    status="enabled"
)
print(f"  测试员工已创建: id={employee_id}")

# ---- 测试用例 ----
print("\n[测试] 技能注入逻辑...")

# TC-1: 员工绑定了技能 → system prompt 应包含技能模板
employee = DigitalEmployeeRepository.get_by_id(employee_id)
prompt = build_system_prompt(dict(employee))
test("TC-1: system prompt 包含员工角色设定",
     "你是一个测试助理" in prompt)
test("TC-2: system prompt 包含技能引导文字",
     "你可以调用以下技能来帮助用户" in prompt)
test("TC-3: system prompt 包含天气查询技能名称",
     "TEST_天气查询" in prompt)
test("TC-4: system prompt 包含天气查询技能模板",
     "城市+温度+天气状况" in prompt)
test("TC-5: system prompt 包含翻译助手技能名称",
     "TEST_翻译助手" in prompt)
test("TC-6: system prompt 包含翻译助手技能模板",
     "将用户输入翻译为目标语言" in prompt)
test("TC-7: system prompt 包含技能使用引导",
     "当用户的问题匹配某个技能时" in prompt)

# TC-8: 员工无技能 → 不包含技能引导
no_skill_id = DigitalEmployeeRepository.create(
    name="TEST_无技能员工",
    role_name="测试角色",
    greeting="你好。",
    skills="[]",
    status="enabled"
)
no_skill_employee = DigitalEmployeeRepository.get_by_id(no_skill_id)
no_skill_prompt = build_system_prompt(dict(no_skill_employee))
test("TC-8: 无技能员工不包含技能引导文字",
     "你可以调用以下技能" not in no_skill_prompt)

# TC-9: 旧格式 skills（字符串数组）→ 不注入
old_fmt_id = DigitalEmployeeRepository.create(
    name="TEST_旧格式员工",
    role_name="测试",
    greeting="你好。",
    skills='["天气查询", "音乐推荐"]',
    status="enabled"
)
old_emp = DigitalEmployeeRepository.get_by_id(old_fmt_id)
old_prompt = build_system_prompt(dict(old_emp))
test("TC-9: 旧格式技能名称不注入（兼容）",
     "你可以调用以下技能" not in old_prompt)

# TC-10: 员工无 system_prompt → 使用默认提示词
default_id = DigitalEmployeeRepository.create(
    name="TEST_默认提示词员工",
    role_name="客服",
    greeting="请问有什么可以帮您？",
    skills=json.dumps([skill1_id]),
    status="enabled"
)
default_emp = DigitalEmployeeRepository.get_by_id(default_id)
default_prompt = build_system_prompt(dict(default_emp))
test("TC-10: 无 system_prompt 时使用默认角色提示词",
     "你是 TEST_默认提示词员工" in default_prompt and "客服" in default_prompt)
test("TC-11: 默认提示词员工也能注入技能",
     "TEST_天气查询" in default_prompt)

# TC-12: 绑定的技能已被禁用 → 仍注入（保持一致性）
AiSkillRepository.update(skill2_id, status="disabled")
disabled_skill_prompt = build_system_prompt(dict(employee))
test("TC-12: 禁用技能仍注入（已绑定的技能保持不变）",
     "TEST_翻译助手" in disabled_skill_prompt)
AiSkillRepository.update(skill2_id, status="enabled")  # 恢复

# TC-13: skills 为空字符串
empty_id = DigitalEmployeeRepository.create(
    name="TEST_空字符串",
    role_name="测试",
    greeting="你好。",
    skills="",
    status="enabled"
)
empty_emp = DigitalEmployeeRepository.get_by_id(empty_id)
empty_prompt = build_system_prompt(dict(empty_emp))
test("TC-13: skills 空字符串不注入",
     "你可以调用以下技能" not in empty_prompt)

# TC-14: skills 为 None → 不注入
none_id = DigitalEmployeeRepository.create(
    name="TEST_None技能",
    role_name="测试",
    greeting="你好。",
    skills=None,
    status="enabled"
)
none_emp = DigitalEmployeeRepository.get_by_id(none_id)
none_prompt = build_system_prompt(dict(none_emp))
test("TC-14: skills=None 不注入",
     "你可以调用以下技能" not in none_prompt)

# ---- 清理测试数据 ----
print("\n[清理] 删除测试数据...")
c.execute("DELETE FROM ai_skills WHERE name LIKE 'TEST_%'")
c.execute("DELETE FROM digital_employees WHERE name LIKE 'TEST_%'")
c.commit()

# ---- 结果 ----
print("\n" + "=" * 60)
print(f"测试完成: {passed+failed} 项, 通过 {passed}, 失败 {failed}")
print("=" * 60)

if failed > 0:
    sys.exit(1)
