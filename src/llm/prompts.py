"""LLM 提示词模板（严格 JSON 输出约定）。"""

SYSTEM_JSON = "你是玄知见解内容运营系统的内容引擎。只输出合法 JSON，不要 markdown 代码块，不要解释文字。"

SCORE_TOPICS = """你是科技自媒体「玄知见解」的选题编辑。账号定位：全球 AI 与前沿科技的独立解读（模型/芯片/机器人/智能硬件）。

以下是过去 24 小时的候选资讯（编号 | 来源 | 标题 | 摘要）：
{items}

请从中挑选 {max_topics} 个最值得做的选题，同一事件的多条资讯合并为一个选题。对每个选题按 100 分制打分：
- audience 受众关注度与话题热度（0-25）
- reliability 信息可靠性与证据完整度（0-25，来源越权威、多方印证越高分）
- differentiation 独立分析与差异化空间（0-20）
- timeliness 时效性（0-15）
- fit 账号定位与读者价值（0-15）

输出 JSON 数组，每个元素：
{{"title": "选题标题（中文，20字内）", "reason": "一句话理由", "scores": {{"audience": 0, "reliability": 0, "differentiation": 0, "timeliness": 0, "fit": 0}}, "item_ids": [资讯编号], "suggested_column": "全球 AI 前沿速递|玄知深度拆解|科技背后的生意"}}
"""

RESEARCH = """你是科技研究员。围绕选题「{topic_title}」，基于以下已采集的原始资讯做事实研究：

{items}

要求：
1. 只使用上面提供的资讯内容，不得虚构；资讯中没有的信息写进 open_questions。
2. 每条事实必须标注来源（source_url 用资讯里的真实链接）。
3. 区分"已证实"（verified=true，有明确来源）与"据报道/未证实"（verified=false）。

输出 JSON：
{{"content": "研究档案正文（中文，含事件经过、背景、各方信息）", "evidence": [{{"fact": "关键事实", "source_title": "来源媒体", "source_url": "链接", "verified": true}}], "open_questions": ["待核验问题1"], "conclusion": "研究结论（2-3句，含不确定性说明）"}}
"""

WRITE_ARTICLE = """你是科技自媒体「玄知见解」的主笔。栏目：{column}
- 全球 AI 前沿速递：发生了什么、为什么重要、后续关注什么，400-800字，信息密度高
- 玄知深度拆解：技术原理、产品差异、能力边界、实际应用与行业竞争，800-1500字
- 科技背后的生意：商业模式、算力成本、供应链、变现路径与产业格局，800-1500字

选题：{topic_title}
研究档案：
{research}

要求：
1. 标题清晰有信息量，15-25字，禁止绝对化用语（最/第一/100%）
2. 导语 2 句内交代核心事件与读者价值
3. 关键数字、时间、人物必须与研究档案一致；未证实内容必须用"据报道""尚未证实"等表述
4. 有独立观点和推理，不拼接翻译
5. 结尾留一个开放式互动问题
6. 长度按栏目要求，不机械凑字数

输出 JSON：
{{"title": "标题", "summary": "摘要（50字内）", "body": "正文（markdown，可用小标题）"}}
"""

QUALITY_CHECK = """你是内容审核员。对下面的文章做事实与质量核查。

文章：
标题：{title}
正文：
{body}

研究档案（事实依据）：
{research}

检查项：
1. facts：正文中的关键数字/时间/人物/能力表述，是否与 research evidence 一致；列出每处（fact | in_evidence: true/false）
2. unsupported：正文中出现但研究档案里没有依据的具体陈述
3. unmarked_uncertainty：未证实内容但正文没有用"据报道/尚未证实"等标注的
4. logic：明显的逻辑问题

输出 JSON：
{{"facts": [{{"fact": "...", "in_evidence": true}}], "unsupported": ["..."], "unmarked_uncertainty": ["..."], "logic": ["..."], "comment": "总体评价（1-2句）"}}
"""
