任务 1：进一步学习并理解项目，将以下信息补全到 #basePrompt.md 中：
1、项目名称：智能瞭望与智能问数系统（IOIQ-System）
2、项目背景：通过 B/s 技术实现一款智能数据采集到深度采集再到数据分析与问数的综合业务系统，以大模型驱动整个业务系统的运行，是一款轻量级的智能（体）应用。
3、技术栈：python3 (python -m venv venv)+sqlite3+websocket+sse+tornado+tornadoTemplate

任务 2：进一步学习并理解项目，将以下信息补充到 #basePrompt.md 中：

1、dist 目录下，放置了三个组，用于后台管理侧开发时使用，其：

- zui-3.0.0.zip ：ZUI 3 是一个的开源 UI 组件库，提供了大量实用组件，支持最大限度的定制，不依赖任何其他 JS 框架，可以在任何 Web 应用中通过原生的方式使用。（开发帮助：https://openzui.com/guide/start/intro.html），需要解压 app/static 目录下。
- bootstrap-5.3.8-dist.zip ：Bootstrap 5.3.8 是一个基于 Bootstrap 5.3.8 版本的 UI 组件库，提供了大量实用组件，支持最大限度的定制，不依赖任何其他 JS 框架，可以在任何 Web 应用中通过原生的方式使用。（开发帮助：https://getbootstrap.com/docs/5.3/getting-started/introduction/），需要解压 app/static 目录下。
- fontawesome-free-6.4.0-web.zip ：FontAwesome Awesome 6.4.0 是一个基于 FontAwesome Awesome 6.4.0 版本的图标库，提供了大量图标，支持自定义图标，可以在任何 Web 应用中通过原生的方式使用。（开发帮助：https://fontawesome.com/docs/v6.4.0/getting-started/using-free），需要解压 app/static 目录下。

任务 3：进一步学习并理解项目，将以下信息补充到 #basePrompt.md 中：

1、设计风格：自适应浏览器用户区设计、响应式布局、沉浸式操作。

2、所有开发将基于上下文工程提示完成，所有操作需要同步记录和维护以下几个文件：

- docs/basePrompt.md (项目基础提示，AI 维护)
- docs/codingPrompt.md (项目编码提示，人类维护，你不用干预)
- docs/requirementPrompt.md (项目需求提示，AI 维护)

任务 4：开始编码实现业务功能模块：

1、完成后台 - 管理侧功能模块的开发：

- 后台登录：采用响应式设计、沉浸式操作、自适应设计，界面风格以企业化管理软件风格为主，简约专业（后台主要是 admin 专员使用，默认用户名密码为：admin/admin888），界面参考上传的 UI 效果图风格完开发，登录面板需要居中屏幕中间位置。

- 后台主页：登录后进入后台主页，后期根据需求添加功能模块，本次任务不开发。

- 后台管理：采用 zui 组件实现传统后台管理系统布局：上（LOGO / 系统名称 / 用户信息 /）左（菜单区）右（工作区）布局，菜单需要有图标 + 文字风格设计。

  

  2、开发限制：

- 严格遵循 #basePrompt.md 中的设计风格和组件库使用要求。

- 所有开发操作需要同步记录和维护以下几个文件：

- docs/basePrompt.md (项目基础提示，AI 维护)

- docs/codingPrompt.md (项目编码提示，人类维护，你不用干预)

- docs/requirementPrompt.md (项目需求提示，AI 维护)

任务 5：开始编码实现业务功能模块：

1、完成后台 - 管理侧功能模块的开发：

- 角色管理：系统分为普通用户、管理用户两大类，普通用户可以通过用户侧测试获得访问前台用户侧的功有权限。管理用户可以通过后台添加用户获得管理侧权限，管理用户类默认超级管理员（admin），该角色不允许删除和修改，可以新增角色 / 删除 / 查看 / 修改 / 分页（20 条 / 页）/ 搜索（模糊查询），需要联动功能管理，实现角色动态设置功能（二级联动的方式实现）
- 用户管理：实现用户新增 / 删除（admin 不允许删除）/ 修改 / 查看 / 分页 / 搜索
- 功能管理：将菜单功能管理化，实现功能的新增 / 删除 / 修改 / 查看 / 分页 / 搜索

2、开发限制：

- 严格遵循 #basePrompt.md 中的设计风格和组件库使用要求。
- 确保所有页面的布局、样式、交互等符合设计风格且统一、规范、一致。要求写主维护 Prompt。
- 所有开发操作需要同步记录和维护以下几个文件：
  - docs/basePrompt.md (项目基础提示，AI 维护)
  - docs/codingPrompt.md (项目编码提示，人类维护，你不用干预)
  - docs/requirementPrompt.md (项目需求提示，AI 维护)