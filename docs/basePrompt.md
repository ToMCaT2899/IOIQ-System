# IOIQ-System 项目基础说明

## 项目概述
**项目名称**：智能瞭望与智能问数系统（IOIQ-System）

**项目背景**：本项目采用 B/S 架构开发基于 AI 的智能瞭望与智能问数综合系统，依托大模型驱动风险监测、自助问数、智能对话、舆情分析全流程，兼容双数据库并支持数字员工多技能拓展，是轻量化一体化数智管理应用。是一款轻量级的智能（体）应用。

**架构说明**：基于 **Python + Tornado** 的 Web 应用，采用经典的 **MVC（Model-View-Controller）** 三层架构模式。项目处于 v0.1 早期开发阶段，当前主要验证 Tornado 框架的路由、程序加载与服务器启动能力。

---

## 技术栈
| 类别 | 技术 |
|------|------|
| 开发语言 | Python 3（虚拟环境：`python -m venv venv`） |
| 后端框架 | Tornado（Python Web 框架，异步非阻塞，含 Tornado Template） |
| 实时通信 | WebSocket、SSE（Server-Sent Events） |
| 数据库 | SQLite3（轻量级关系型数据库） |
| 前端模板 | Tornado Template（存放于 `templates/`） |
| 前端静态资源 | CSS / JS（存放于 `static/`） |
| 前端组件库（第三方） | Bootstrap 5.3.8、Font Awesome 6.4.0、ZUI 3.0.0（压缩包存放于 `dist/`，使用时需解压至 `app/static/`） |

---

## 前端组件库说明

`dist/` 目录下放置了三个第三方 UI 组件库，用于后台管理侧开发时使用，需解压至 `app/static/` 目录下：

| 组件库 | 说明 | 文档链接 |
|--------|------|----------|
| **ZUI 3** | 开源 UI 组件库，提供大量实用组件，支持最大限度定制，不依赖任何其他 JS 框架，可在任何 Web 应用中通过原生方式使用 | https://openzui.com/guide/start/intro.html |
| **Bootstrap 5.3.8** | 基于 Bootstrap 5.3.8 版本的 UI 组件库，提供大量实用组件，支持最大限度定制，不依赖任何其他 JS 框架，可在任何 Web 应用中通过原生方式使用 | https://getbootstrap.com/docs/5.3/getting-started/introduction/ |
| **Font Awesome 6.4.0** | 图标库，提供大量图标，支持自定义图标，可在任何 Web 应用中通过原生方式使用 | https://docs.fontawesome.com/web/setup/get-started |

---

## 目录结构

```
IOIQ-System/
├─ app.py                  # 主入口：Tornado 应用创建、路由注册、服务器启动
├─ app/                    # MVC 业务代码目录（Python 包）
│  ├─ __init__.py          # 标识 app 为 Python 包
│  ├─ controllers/         # 控制层（C）- 处理请求与路由逻辑
│  │  ├─ __init__.py       # 控制器包标识
│  │  ├─ admin_auth.py     # 后台认证控制器（登录/登出/主页）
│  │  ├─ admin_manage.py   # 后台管理控制器（功能/角色/用户 CRUD）
│  │  ├─ model_engine.py   # 模型引擎控制器（CRUD + SSE 流式对话测试）
│  │  ├─ watch_source.py   # 瞭望数据源控制器（采集规则 CRUD）
│  │  ├─ watch_collect.py  # 瞭望采集控制器（采集执行 / SSE 流式 / 保存）
│  │  ├─ data_warehouse.py # 数据仓库控制器（列表/筛选/删除/批量删除）
│  │  ├─ deep_collect.py   # 深度采集控制器（SSE流式/单条+批量/详情查看）
│  │  ├─ base.py           # 基础控制器（预留）
│  │  ├─ home.py           # 首页控制器（预留）
│  │  └─ auth.py           # 认证控制器（预留）
│  ├─ models/              # 模型层（M）- 数据与业务逻辑
│  │  ├─ __init__.py       # 模型包标识
│  │  ├─ db.py             # 数据库连接管理 & 表初始化 & 种子数据（SQLite3，10张表）
│  │  ├─ user.py           # 用户仓储类（CRUD、密码哈希验证）
│  │  ├─ role.py           # 角色仓储类（CRUD、分页、功能权限分配）
│  │  ├─ function.py       # 功能/菜单仓储类（CRUD、分页、树形结构）
│  │  ├─ model_engine.py   # 模型引擎仓储类（CRUD、Token 统计、默认模型管理）
│  │  ├─ watch_source.py   # 瞭望数据源仓储类（CRUD、分页搜索）
│  │  ├─ watch_result.py   # 瞭望采集结果仓储类（批量保存、分页搜索）
│  │  └─ deep_result.py    # 深度采集结果仓储类（CRUD、批量状态查询）
│  ├─ templates/           # 视图层（V）- HTML 模板
│  │  ├─ admin/            # 后台管理页面
│  │  │  ├─ base.html      # 后台基础布局模板（ZUI 上/左/右布局）
│  │  │  ├─ index.html     # 后台控制台首页
│  │  │  ├─ login.html     # 后台登录页（响应式+沉浸式+居中面板）
│  │  │  ├─ func_list.html # 功能管理列表页
│  │  │  ├─ func_edit.html # 功能新增/编辑页
│  │  │  ├─ role_list.html # 角色管理列表页
│  │  │  ├─ role_edit.html # 角色编辑页（含二级联动功能权限树）
│  │  │  ├─ user_list.html # 用户管理列表页
│  │  │  ├─ user_edit.html # 用户新增/编辑页
│  │  │  ├─ model_list.html # 模型引擎列表页（橱窗卡片/三列/科技风）
│  │  │  ├─ model_edit.html # 模型新增/编辑表单（OPENAI-API配置）
│  │  │  └─ model_chat.html # 模型对话测试页（SSE流式+Think开关）
│  │  │  ├─ watch_source_list.html  # 瞭望数据源列表页
│  │  │  ├─ watch_source_edit.html  # 瞭望数据源新增/编辑页
│  │  │  └─ watch_collect.html      # 瞭望采集页（独立科技风/搜索引擎式交互）
│  │  │  └─ data_warehouse.html     # 数据仓库列表页（筛选栏/批量操作/AI入口/分页+深度采集状态）
│  │  │  └─ deep_detail.html        # 深度采集详情页（源数据信息/AI摘要/正文/日志）
│  │  │  └─ deep_collect_list.html   # 深度采集列表页（所有任务/统计卡片/状态/分页）
│  │  └─ web/              # 前台用户页面（预留）
│  │     ├─ base.html      # 基础模板（预留）
│  │     ├─ index.html     # 首页（预留）
│  │     └─ login.html     # 登录页（预留）
│  └─ static/              # 静态资源
│     ├─ css/
│     │  └─ base.css       # 基础样式（预留）
│     ├─ js/
│     │  └─ base.js        # 基础脚本（预留）
│     ├─ zui/              # ZUI 3 组件库（已解压）
│     ├─ bootstrap-5.3.8-dist/  # Bootstrap 5.3.8（已解压）
│     └─ fontawesome-free-6.4.0-web/  # Font Awesome 6.4.0（已解压）
├─ database/
│  └─ app.db               # SQLite 数据库文件（运行时自动生成）
├─ dist/                   # 第三方前端组件压缩包（源文件）
│  ├─ bootstrap-5.3.8-dist.zip
│  ├─ fontawesome-free-6.4.0-web.zip
│  └─ zui-3.0.0.zip
├─ docs/                   # 开发文档与提示词工程目录
│  ├─ basePrompt.md        # 本项目说明（本文件，AI 维护）
│  ├─ codingPrompt.md      # 编码相关提示词（人类维护）
│  ├─ requirementPrompt.md # 需求相关提示词
│  └─ treePromot.md        # 项目目录结构提示词
├─ test/                   # 单元测试脚本目录
│  └─ testCase1.py         # 用户模块基础测试用例
└─ app.py                  # 主程序入口
```

---

## 架构设计

### MVC 分层
- **Model（模型层）** — `app/models/`
  - `db.py`：封装 SQLite3 连接、数据库初始化（`init_db` 创建 users/roles/functions/role_functions 四张表）、种子数据（`seed_admin` 管理员、`seed_roles_and_functions` 默认角色与菜单功能）
  - `user.py`：`UserRepository` 类，提供用户创建、查询、密码验证等数据操作；密码采用 PBKDF2-HMAC-SHA256 + 随机 salt 加密
  - `role.py`：`RoleRepository` 类，角色 CRUD + 分页搜索 + 功能权限分配（二级联动）
  - `function.py`：`FunctionRepository` 类，功能/菜单 CRUD + 分页搜索 + 树形结构获取 + 级联删除
  - `model_engine.py`：`ModelEngineRepository` 类，模型引擎 CRUD + 分页搜索 + 默认模型管理 + Token 统计
  - `watch_source.py`：`WatchSourceRepository` 类，瞭望数据源 CRUD + 分页搜索
  - `watch_result.py`：`WatchResultRepository` 类，采集结果批量保存 + 分页搜索
- **View（视图层）** — `app/templates/`
  - 后台页面（`admin/`）：登录页、基础布局模板（ZUI 上/左/右布局，左侧菜单15项扁平无分组）、控制台首页
  - **功能管理**：`func_list.html`（列表+分页+搜索）、`func_edit.html`（新增/编辑表单）
  - **角色管理**：`role_list.html`（列表+分页+搜索）、`role_edit.html`（编辑含二级联动功能权限树）
  - **用户管理**：`user_list.html`（列表+分页+搜索）、`user_edit.html`（新增/编辑表单）
  - **模型引擎**：`model_list.html`（三列橱窗卡片/科技风/Token 可视化）、`model_edit.html`（OPENAI-API 配置表单/SSE 流式开关/Think 开关）、`model_chat.html`（对话测试/SSE 流式聊天/Think 模式面板）
  - **瞭望数据源管理**：`watch_source_list.html`（表格列表+分页+搜索）、`watch_source_edit.html`（采集规则配置/请求头JSON编辑器/分页开关）
  - **瞭望采集**：`watch_collect.html`（独立深色科技风页面 / 中央搜索框 / 采集源开关面板 / 参数配置联动 / 结果橱窗3列 / 多选全选 / 一键保存）
  - **数据仓库**：`data_warehouse.html`（采集结果列表 + 关键词/时间/来源筛选 + 全选批量删除 + AI深度采集入口(实时进度面板/SSE流式/统计) + 深度采集状态标识 + 分页20条/页）、`deep_detail.html`（源数据信息/AI分析摘要/提取正文/采集日志）
  - **深度采集列表**：`deep_collect_list.html`（所有深度采集任务/统计卡片/状态/分页）
  - 前台页面（`web/`）：
    - `base.html` — 前台基础布局模板
    - `login.html` — 前台用户登录页（深色科技风/品牌展示区/角色区分）
    - `register.html` — 前台用户注册页（用户名/邮箱/密码/确认密码）
    - `chat.html` — AI 智能问数对话页（ChatGPT式布局/左侧模型切换+历史记录/主对话区SSE流式/Enter发送/Shift+Enter换行/@预留调用数字员工/marked.js Markdown渲染）

### 左侧菜单结构（admin/base.html）
菜单项按以下顺序扁平排列，无分组标题：

| 序号 | 菜单名称 | 路由 | current_page 值 | 图标 |
|------|---------|------|-----------------|------|
| 1 | 控制台 | `/admin/index` | `dashboard` | fa-tachometer-alt |
| 2 | 用户管理 | `/admin/users` | `users` | fa-users |
| 3 | 功能管理 | `/admin/functions` | `functions` | fa-list-alt |
| 4 | 权限管理 | `/admin/roles` | `roles` | fa-user-shield |
| 5 | 模型引擎 | `/admin/models` | `models` | fa-microchip |
| 6 | 瞭望管理 | `/admin/watch-sources` | `watch` | fa-eye |
| 7 | 数据仓库 | `/admin/data-warehouse` | `warehouse` | fa-database |
| 8 | 深度采集 | `/admin/deep-collect` | `deep` | fa-microscope |
| 9 | 接口管理 | `#` | `api` | fa-plug |
| 10 | 数字员工 | `#` | `employee` | fa-robot |
| 11 | 技能管理 | `#` | `skills` | fa-tools |
| 12 | 会话管理 | `#` | `sessions` | fa-history |
| 13 | 对话管理 | `#` | `chats` | fa-comments |
| 14 | 数智大屏 | `#` | `dashboard_screen` | fa-chart-bar |
| 15 | 系统设置 | `#` | `system` | fa-cog |

- **Controller（控制层）** — `app/controllers/`
  - `admin_auth.py`：后台认证控制器（登录/登出/主页）
  - `admin_manage.py`：后台管理控制器（功能/角色/用户三大模块的完整 CRUD）
  - `model_engine.py`：模型引擎控制器（列表/新增/编辑/删除/设默认 + SSE 流式对话测试）
  - `watch_source.py`：瞭望数据源控制器（列表/新增/编辑/删除 + 占位符URL配置）
  - `watch_collect.py`：瞭望采集控制器（采集主页面 + 数据源JSON接口 + SSE 流式采集执行 + 批量保存）
  - `data_warehouse.py`：数据仓库控制器（列表/筛选/单条删除/批量删除，每页20条）
  - `deep_collect.py`：深度采集控制器（SSE流式采集 / 单条+批量 / 网页抓取+BeautifulSoup提取 / 默认模型AI分析 / 详情查看）
  - `web_auth.py`：前台认证控制器（登录/注册/登出，角色区分：管理员→后台/普通用户→前台）
  - `web_chat.py`：AI 问数对话控制器（ChatGPT式交互 / SSE 流式 / 意图识别SQL天气音乐 / 历史会话管理 / SQLite schema 自动注入 / SQL 不展示规则）

### 数据库设计
| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 用户表 | id, username, password_hash, salt, role_id, status, created_at |
| `roles` | 角色表 | id, name, description, is_system(系统内置标识), created_at |
| `functions` | 功能/菜单表 | id, parent_id(上级ID,0=顶级), name, code(唯一编码), icon, path, sort_order, status |
| `role_functions` | 角色-功能关联表 | role_id, function_id (联合唯一，实现二级联动) |
| `model_engines` | 模型引擎表 | id, name, provider, api_base, api_key, model_name, model_type(text/multimodal/vision/vector), is_default, temperature, max_tokens, system_prompt, enable_stream, enable_think, total_tokens, status |
| `watch_sources` | 瞭望数据源表 | id, name, url_template(含{关键词}/{pn}占位), method, headers(JSON), proxy, enable_pagination, status |
| `watch_results` | 瞭望采集结果表 | id, source_id, source_name, keyword, title, url, snippet, raw_html, page_num, deep_status(0未深度/1已深度), collected_at |
| `deep_results` | 深度采集结果表 | id, watch_result_id(FK), source_url, model_engine_id, model_name, title, full_content(完整正文), content_summary(AI摘要), status(success/fail), error_message, log_text, tokens_used, duration_ms, created_at |
| `conversations` | 对话会话表 | id, user_id(FK), title, model_engine_id, model_name, created_at, updated_at |
| `chat_messages` | 对话消息表 | id, conversation_id(FK), role(user/assistant), content, tokens_used, created_at |

### 主入口（app.py）
- 使用 `tornado.web.Application` 创建 Web 应用实例
- 路由表以列表形式注册 `(路径, Handler类)` 映射
- 配置静态文件路径（`static_path`）、模板路径（`template_path`）、Cookie 密钥（`cookie_secret`）
- 启动时自动执行 `init_db()` + `seed_admin()` + `seed_roles_and_functions()`
- `tornado.httpserver.HTTPServer` 启动服务，监听端口 **10086**
- `debug=True` 开启调试模式

### 路由表
| 路径 | Handler | 说明 |
|------|---------|------|
| `/` | IndexHandler | 前台首页（重定向到 /login） |
| `/login` | WebLoginHandler | 前台用户登录页 & 登录提交（角色区分） |
| `/register` | WebRegisterHandler(GET/POST) | 前台用户注册 |
| `/logout` | WebLogoutHandler(POST) | 前台登出 |
| `/chat` | ChatPageHandler | AI 问数对话主页面 |
| `/chat/sse` | ChatSSEHandler(POST) | SSE 流式对话接口（含意图识别） |
| `/chat/history` | ChatHistoryHandler(GET) | 获取会话历史消息 |
| `/chat/delete` | ChatDeleteHandler(POST) | 删除对话会话 |
| `/admin/login` | AdminLoginHandler | 后台登录页 & 登录提交 |
| `/admin/index` | AdminIndexHandler | 后台控制台（需登录） |
| `/admin/logout` | AdminLogoutHandler | 后台登出 |
| `/admin/functions` | FuncListHandler | 功能管理列表 |
| `/admin/function/add` | FuncAddHandler(GET/POST) | 新增功能 |
| `/admin/function/edit` | FuncEditHandler(GET/POST) | 编辑功能 |
| `/admin/function/delete` | FuncDeleteHandler(POST) | 删除功能 |
| `/admin/roles` | RoleListHandler | 角色管理列表 |
| `/admin/role/add` | RoleAddHandler(GET/POST) | 新增角色 |
| `/admin/role/edit` | RoleEditHandler(GET/POST) | 编辑角色（含功能联动） |
| `/admin/role/delete` | RoleDeleteHandler(POST) | 删除角色（系统内置不可删） |
| `/admin/users` | UserListHandler | 用户管理列表 |
| `/admin/user/add` | UserAddHandler(GET/POST) | 新增用户 |
| `/admin/user/edit` | UserEditHandler(GET/POST) | 编辑用户 |
| `/admin/user/delete` | UserDeleteHandler(POST) | 删除用户（admin不可删） |
| `/admin/models` | ModelListHandler | 模型引擎列表（三列卡片/6条每页） |
| `/admin/model/add` | ModelAddHandler(GET/POST) | 新增模型引擎 |
| `/admin/model/edit` | ModelEditHandler(GET/POST) | 编辑模型引擎 |
| `/admin/model/delete` | ModelDeleteHandler(POST) | 删除模型引擎 |
| `/admin/model/set-default` | ModelSetDefaultHandler(POST) | 设为默认模型 |
| `/admin/model/chat` | ModelChatHandler(GET) | 模型对话测试页 |
| `/admin/model/chat/sse` | ModelChatSSEHandler(POST) | SSE 流式对话接口 |
| `/admin/watch-sources` | WatchSourceListHandler | 瞭望数据源列表 |
| `/admin/watch-source/add` | WatchSourceAddHandler(GET/POST) | 新增数据源 |
| `/admin/watch-source/edit` | WatchSourceEditHandler(GET/POST) | 编辑数据源 |
| `/admin/watch-source/delete` | WatchSourceDeleteHandler(POST) | 删除数据源 |
| `/admin/watch-collect` | WatchCollectPageHandler | 瞭望采集主页面 |
| `/admin/watch-collect/sources` | WatchCollectSourcesHandler(GET) | 数据源列表JSON |
| `/admin/watch-collect/fetch` | WatchCollectFetchHandler(POST) | SSE 流式采集执行 |
| `/admin/watch-collect/save` | WatchCollectSaveHandler(POST) | 保存选中结果 |
| `/admin/data-warehouse` | DataWarehouseListHandler | 数据仓库列表（筛选/分页20条） |
| `/admin/data-warehouse/delete` | DataWarehouseDeleteHandler(POST) | 单条删除 |
| `/admin/data-warehouse/batch-delete` | DataWarehouseBatchDeleteHandler(POST) | 批量删除 |
| `/admin/deep-collect` | DeepCollectListHandler | 深度采集任务列表 |
| `/admin/deep-collect/sse` | DeepCollectSSEHandler(POST) | 深度采集SSE流式接口（单条/批量） |
| `/admin/deep-collect/detail/(\d+)` | DeepCollectDetailHandler(GET) | 深度采集结果详情页 |

### 数据流
```
HTTP请求 → Tornado Router → Controller Handler → Model 数据操作 → 渲染 Template → HTTP响应
```

---

## 设计风格
- **自适应浏览器用户区设计**：页面自动适配浏览器窗口大小
- **响应式布局**：支持多种设备屏幕尺寸，灵活调整页面结构
- **沉浸式操作**：减少干扰元素，提供专注的用户体验

---

## 开发模式

### 上下文工程提示
所有开发将基于上下文工程提示完成，需要同步记录和维护以下文件：
- `docs/basePrompt.md`（项目基础提示，AI 维护）
- `docs/codingPrompt.md`（项目编码提示，人类维护，AI 不干预）
- `docs/requirementPrompt.md`（项目需求提示，AI 维护）

### 启动方式
```bash
python app.py
```
服务启动后访问 `http://localhost:10086/`

### 数据库初始化
```python
from app.models.db import init_db
init_db()
```

### 测试方式
```bash
python test/testCase1.py
```

### 编码规范参考
- Python 3.13+（基于 `.cpython-313.pyc` 缓存文件）
- 使用 `sqlite3.Row` 作为行工厂，支持列名访问查询结果
- 密码安全：`hashlib.pbkdf2_hmac` + `secrets.token_bytes(16)` 生成 salt
- 控制器文件采用静态方法或类方法组织 Handler 逻辑
- 模板与静态资源按 admin/web 双端分离

### 当前开发状态
- v0.1 阶段，已完成框架搭建、数据库设计、用户模型实现
- **后台认证模块**：登录页（响应式+沉浸式+居中面板）、控制台首页（ZUI 上/左/右布局）、认证控制器
- **功能管理模块**：CRUD + 分页(20条/页) + 模糊搜索 + 级联删除 + 树形菜单展示
- **角色管理模块**：CRUD + 分页(20条/页) + 模糊搜索 + 二级联动功能权限分配（系统内置角色不可删除修改）
- **用户管理模块**：CRUD + 分页(20条/页) + 模糊搜索 + 角色分配（admin 不可删除）
- **模型引擎模块**：CRUD + 分页(6条/页) + 模糊搜索 + 三列橱窗卡片布局(科技风格) + OPENAI-API范式配置 + Token可视化统计 + SSE流式对话测试 + Think模式 + 默认模型管理
- **瞭望数据源模块**：CRUD + 分页(20条/页) + 模糊搜索 + URL占位符配置({关键词}{pn}) + Request Headers JSON编辑器 + 分页采集开关 + 代理配置
- **瞭望采集模块**：独立深色科技风页面（非ZUI布局）+ 中央搜索框 + 采集源动态开关面板 + 参数配置联动(pages/pn_step/URL预览) + SSE流式采集 + 结果3列橱窗 + 多选/全选 + 一键保存到数据库
- **数据仓库模块**：采集结果列表 + 关键词/数据来源/时间范围筛选 + 全选批量删除 + 单条删除 + 分页(20条/页) + 深度采集状态标注（已深度/未深度）
- **深度采集模块**：单条/批量深度采集 + SSE流式进度面板 + 实时日志 + 网页抓取(requests+BeautifulSoup) + 默认模型AI分析(OpenAI兼容API) + 统计（成功/失败/耗时/Tokens） + 详情查看页（源数据信息/AI摘要/完整正文/采集日志）
- **前台认证模块**：用户登录（深色科技风/角色区分：管理员→后台/普通用户→前台）、用户注册（用户名/密码/邮箱/自动绑定普通用户角色）、登出
- **AI 问数模块**：ChatGPT式对话布局（左侧：模型服务切换 + 历史对话管理，主区：SSE流式对话 + Markdown渲染 + Enter发送/Shift+Enter换行）、意图识别（SQL问数/天气/音乐/通用）、@预留调用数字员工、数据库表结构自动注入、SQL不展示规则、对话历史CRUD
- 默认管理员账号：**admin / 123456**
- 默认角色：超级管理员、普通管理员、普通用户（含预置功能权限）
- 前台页面（`web/`）已实现登录、注册、AI问数对话
