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
│  │  ├─ base.py           # 基础控制器（预留）
│  │  ├─ home.py           # 首页控制器（预留）
│  │  └─ auth.py           # 认证控制器（预留）
│  ├─ models/              # 模型层（M）- 数据与业务逻辑
│  │  ├─ __init__.py       # 模型包标识
│  │  ├─ db.py             # 数据库连接管理 & 表初始化（SQLite3）
│  │  └─ user.py           # 用户仓储类（CRUD、密码哈希验证）
│  ├─ templates/           # 视图层（V）- HTML 模板
│  │  ├─ admin/            # 后台管理页面（预留）
│  │  └─ web/              # 前台用户页面
│  │     ├─ base.html      # 基础模板（预留）
│  │     ├─ index.html     # 首页（预留）
│  │     └─ login.html     # 登录页（预留）
│  ├─ static/              # 静态资源
│  │  ├─ css/
│  │  │  └─ base.css       # 基础样式（预留）
│  │  └─ js/
│  │     └─ base.js        # 基础脚本（预留）
├─ database/
│  └─ app.db               # SQLite 数据库文件（运行时生成）
├─ dist/                   # 第三方前端组件压缩包
│  ├─ bootstrap-5.3.8-dist.zip
│  ├─ fontawesome-free-6.4.0-web.zip
│  └─ zui-3.0.0.zip
├─ docs/                   # 开发文档与提示词工程目录
│  ├─ basePrompt.md        # 本项目说明（本文件）
│  ├─ codingPrompt.md      # 编码相关提示词
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
  - `db.py`：封装 SQLite3 连接池、数据库初始化（`init_db` 创建 users 表）
  - `user.py`：`UserRepository` 类，提供用户创建、查询、密码验证等数据操作；密码采用 PBKDF2-HMAC-SHA256 + 随机 salt 加密
- **View（视图层）** — `app/templates/`
  - 前台页面（`web/`）与后台页面（`admin/`）分离
  - 当前使用 Tornado 内置模板系统，HTML 文件预留，待填充内容
- **Controller（控制层）** — `app/controllers/`
  - 负责接收 HTTP 请求、调用 Model、渲染 View 返回响应
  - 当前控制器文件已创建但内容为空，路由暂时定义在 `app.py` 中

### 主入口（app.py）
- 使用 `tornado.web.Application` 创建 Web 应用实例
- 路由表以列表形式注册 `(路径, Handler类)` 映射
- `tornado.httpserver.HTTPServer` 启动服务，监听端口 **10086**
- `debug="True"` 开启调试模式

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
- 控制器和视图层文件已创建但内容为空，待后续填充
- 路由当前硬编码在 `app.py` 中，后续应迁移至 `controllers/` 统一管理
