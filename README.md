# 玄知见解 · 海外 AI 科技内容运营系统

本地内容运营闭环：海外 AI 资讯发现 → 去重筛选 → 选题评分 → 研究核验 → 文章生成 → 图片管理 → 质量审核 → 人工审批 → 人工发布 → 数据回收 → 日报复盘。

服务于今日头条账号「玄知见解」（全球 AI 前沿速递 40% / 玄知深度拆解 35% / 科技背后的生意 25%，比例按真实数据迭代）。

## 架构
- 后端：FastAPI + SQLAlchemy 2 + Alembic + SQLite（`apps/api`、`src/`）
- 前端：React + TypeScript（`apps/web`，阶段 D 交付）
- 模型：OpenAI 兼容接口适配层（`src/llm`，超时/有限重试/密钥脱敏），主接口 `http://172.20.100.212:40000/v1`（DeepSeek-V4-Flash，免认证）
- 编排：Hermes Skills（`hermes/skills/`，阶段 E 接入）+ 业务内工作流（`src/workflows`，幂等/重试/恢复）
- 数据：`data/app.db`（12 实体），素材 `storage/`，日志 `logs/`（JSON 结构化、脱敏）

## 快速开始
```bash
make venv          # 创建 .venv（miniconda 3.14）
make install       # 安装依赖
cp .env.example .env   # 按需修改
make migrate       # 数据库迁移（alembic）
make test          # pytest
make run           # 启动 API：http://127.0.0.1:8700
```

## 主要 API（阶段 B 已交付）
- `GET /health` 健康检查
- `GET|POST /api/v1/news-sources`、`PATCH /api/v1/news-sources/{id}` 资讯源管理
- `POST /api/v1/collect/run` 采集（当日幂等，重复触发返回历史记录）
- `GET /api/v1/news-items?source_id=&limit=` 资讯条目
- `GET /api/v1/workflow-runs` 任务记录
- `POST /api/v1/llm/test` 模型连接测试（真实推理）

## 业务规则（不可破坏）
- 审批与发布分离：`approved ≠ published`；只有人工批准才进入待发布
- 审核未通过必须退回修改（`in_review → rejected → draft`）
- 发布与收益只记录真实数据；不伪造新闻、来源、阅读量、收益
- 不自动声明原创/首发，不自动发布，不绕过平台规则
- 任务幂等：同一任务重复触发不重复产稿、不覆盖已批准版本
- 密钥只存 `.env`（已 gitignore），日志脱敏

## 状态机
文章：`draft → in_review → approved → pending_publish → published`；`in_review → rejected → draft`
选题：`candidate → selected → researching → done | discarded`
任务：`running → success | failed`
