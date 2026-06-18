* 项目名称：智能瞭望与智能问数系统（IOIQ-System）
* 项目需求：需要实现用户侧+管理侧的所有功能及业务，重点考察需求完整、功能完整、系统风格去AI化、软件能力成熟度、系统安全能力、产品化成熟度等（功能名称与现有演示可能略有出入，自行调整不做强制统一要求，功能实现为主）。
  * 前端侧：面向普通用户，可以通过AI对话实现与数据化员工的交互体验
    * 对话功能
    * 问数功能
    * 导出对话->pdf文档
    * 数据库问数
    * 天气的问数
    * 音乐的问数
    * 电影的问数
    * ......
  * 管理侧：面向管理员，负责系统的日常维护和管理，左侧菜单按以下顺序排列（15项）：
    * 控制台
    * 用户管理
    * 功能管理
    * 权限管理
    * 模型引擎
    * 瞭望管理
    * 数据仓库
    * 深度采集
    * 接口管理
    * 数字员工
    * 技能管理
    * 会话管理
    * 对话管理
    * 数智大屏
    * 系统设置
* 项目目标
  * 1.实现的智能瞭望与智能问数系统的所有功能需求
  * 2.在上述开发方式、技术、环境的基础下，实现用户侧与数字员工的对话功能。实现技能增强，如增加网络搜索功能，拓宽模型数据不足的问题
    * 实现@天气 xxx
    * 实现@音乐
    * 实现@西师妹
    * 实现问数报表功能
    * 实现\xxx 调度技能，如\search xxx指的是调度网络搜索能力获得网络信息
  * 3.实现智慧舆情功能
    * 数智大屏：3D 地球、数据可视化大屏、词云（Echarts-GL, Wordcloud）、数据统计等
    * 智能舆情：在界面中通过AI模型自主分析智能聊天子系统和瞭望子系统中的数据并分析舆情
  * 4.实现多数据库支持和切换功能
    * 系统可同时支持mysql/sqlite，支持后台切换到mysql数据库，默认sqlite
* 开发进度
  * **任务21（技能调度功能模块）**：已完成
    * 文件：`app/services/skill_scheduler.py`（技能调度器）、`test/test_skill_scheduler.py`（测试）
    * 功能：`\xxx` / `@xxx` 命令解析与路由、技能动态注册/注销、调度日志记录
    * 内置技能：search（网络搜索）、weather（天气）、music（音乐）、report（报表）、help（帮助）
    * 测试：6项全部通过
  * **任务22（智能舆情模块）**：已完成
    * 文件：`app/models/sentiment.py`（数据仓储）、`app/services/sentiment_service.py`（分析引擎）、`app/controllers/sentiment.py`（控制器）、3个模板页面、`test/test_sentiment.py`（测试）
    * 功能：AI驱动舆情分析（规则引擎+AI双模式）、情感分析（正面/中性/负面）、风险分级、关键词提取、趋势图表、关键词云、负面舆情自动告警（负面占比>40%触发）、舆情报告生成、数智大屏集成
    * 数据库表：`sentiment_analysis`（分析结果）、`sentiment_alerts`（告警）
    * 测试：6项全部通过
  * **任务23（数智大屏增强）**：已完成
    * 文件：`app/models/dashboard_screen.py`（新增geo/wordcloud/sentiment_trend方法）、`app/controllers/dashboard_screen.py`（新增SSE实时推送）、`app/templates/admin/dashboard_screen.html`（完全重写）
    * 功能：ECharts-GL 3D地球（30个全球城市散点+飞线流+云层+自转）、ECharts-wordcloud关键词云、6项核心指标卡（含舆情分析数）、消息趋势+舆情情感双Y轴组合图、SSE 5s+HTTP 15s双通道实时更新、starfield动画星空背景、3模板切换、全屏沉浸模式
  * **任务24（多数据库支持）**：已完成
    * 文件：`app/models/db.py`（重写双引擎支持）、`app/services/db_migration.py`（迁移服务）、`app/controllers/system_settings.py`（新增5个DB管理Handler）、`app/templates/admin/db_config.html`（配置页面）
    * 功能：SQLite/MySQL双引擎动态切换、`db_config.json`配置文件管理、PyMySQL连接包装（Row/Cursor兼容）、建表DDL自动转换、数据逐表迁移（SSE进度推送）、连接测试、手动切换引擎
    * 路由：5条（/admin/db-config + save/test/migrate/switch）