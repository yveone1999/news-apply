# AGENTS.md — 项目协作约定（AI 与人工共同遵守）

## 红线
1. 不伪造新闻、来源、阅读量、收益或测试结果；数据缺失就写"缺失"
2. 不自动发布、不自动声明原创/首发；发布由人工在今日头条完成并回填链接
3. 不修改 `~/.hermes/` 下任何文件；Hermes 配置变更必须先备份、只追加、diff 验证
4. 密钥只进 `.env`（gitignored）；代码与日志中不得出现明文密钥（日志经 scrub 脱敏）
5. 服务只监听 127.0.0.1

## 代码约定
- Python 3.14，venv 在 `.venv/`，用 `.venv/bin/` 下的工具；测试用 `.venv/bin/pytest`
- 业务规则写 Python 服务，不散落在 Skills 或前端
- 数据模型变更必须走 Alembic 迁移（`migrations/`），不允许只靠 `create_all`
- API 路径 `/api/v1/`；JSON 响应；错误用 HTTP 状态码 + 中文 message
- 时间一律 UTC 存储，展示层转换
- 新增资讯源改 `configs/news_sources.yaml`（enabled 控制启停）

## 验证要求
- 每次改后端：`.venv/bin/pytest -q` 必须全绿
- 涉及采集/LLM 的改动：用真实数据跑一次 `POST /api/v1/collect/run` 或 `/llm/test` 验证（需要网络权限时向用户请求）
- 阶段汇报必须包含：已完成、真实运行结果、未完成、已知风险、下一步

## 目录速查
- `apps/api/main.py` FastAPI 入口（路由集中在此，阶段 C/D 按需拆 router）
- `src/domain/models.py` 12 实体；`src/domain/db.py` 引擎/会话
- `src/llm/client.py` 模型适配层；`src/collectors/feeds.py` 采集；`src/workflows/runs.py` 任务编排
- `tests/` pytest（含 LLM MockTransport、采集去重、任务幂等用例）
