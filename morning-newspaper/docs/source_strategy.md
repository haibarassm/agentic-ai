# 信息源策略

本文档说明 Morning Newspaper Assistant 的信号源设计：每种来源用哪种采集范式、如何配置、采集产物长什么样、以及它们之间的协作关系。

所有来源在 `config/sources.yaml` 中配置，采集后统一转换为 `RawItem`，写入 `runtime/collected_raw.json`，再进入后续的正文抓取和编辑链路。

## 来源总览

| source_id | 名称 | 采集范式 | source_group | 采集器 |
|---|---|---|---|---|
| `github_high_stars` | GitHub 高星项目 | 结构化 API | primary | `collectors/github.py` |
| `hackernews_top` | Hacker News 热门故事 | 结构化 API | primary | `collectors/hackernews.py` |
| `sec_press_releases` | SEC 新闻稿 | RSS/Atom | background | `collectors/rss.py` |
| `fed_press_all` | 美联储新闻稿 | RSS/Atom | background | `collectors/rss.py` |
| `openclaw_tavily` | Tavily 主题搜索 | 搜索计划回填 | primary | `collectors/tavily.py` |

## 两种采集范式

### 1. 结构化 API

**代表来源**：GitHub Search API、Hacker News Firebase API

**核心逻辑**：先在配置里定义目标画像（stars 门槛、语言、topic、时间窗口），再用官方 API 接口查询，拿到结构化 JSON 响应。

**GitHub 采集器**（`collectors/github.py`）

- 入口函数：`fetch_github_high_stars(source)`
- 通过 `_build_query()` 将配置拼成 GitHub Search query，格式为：

  ```text
  created:>=YYYY-MM-DD stars:>=80 archived:false is:public language:Python
  ```

- `languages` × `extra_queries` 生成多条 query（笛卡尔积），每条独立请求
- 认证：读取 `auth_env` 指定的环境变量（默认 `GITHUB_TOKEN`），通过 `Authorization: Bearer` 头调用
- 采集字段：仓库名、URL、简介、创建时间、stars、forks、语言、topics、最近推送时间
- stars/forks 只进入 `raw_metadata`，不会被写成正文

**配置示例**：

```yaml
- id: github_high_stars
  source_type: github_high_stars
  endpoint: https://api.github.com/search/repositories
  auth_env: GITHUB_TOKEN
  since_days: 3
  min_stars: 80
  per_query_limit: 10
  languages: [Python, TypeScript, Go, Rust]
  extra_queries: [topic:ai, topic:agent]
```

**Hacker News 采集器**（`collectors/hackernews.py`）

- 入口函数：`fetch_hackernews_top(source)`
- 先请求 `topstories.json` 拿 story ID 列表（最多 `max_stories` 条），再逐条请求 story 详情
- 只保留 `type` 为 `story` 或 `job` 的条目
- 没有外部 URL 的条目回退到 HN 讨论页 `news.ycombinator.com/item?id=...`
- 采集字段：标题、原始 URL、发布时间、score、评论数、作者、HN 讨论链接

**配置示例**：

```yaml
- id: hackernews_top
  source_type: hackernews_top
  endpoint: https://hacker-news.firebaseio.com/v0
  stories_type: topstories      # 也支持 newstories / beststories
  max_stories: 20               # 拉取 story ID 的上限
  max_items: 4                  # 最终保留的候选数
  timeout_seconds: 15
```

### 2. RSS/Atom 订阅

**代表来源**：SEC 新闻稿、美联储新闻稿

**核心逻辑**：请求 RSS/Atom XML，用 Python 标准库 `xml.etree.ElementTree` 解析，不依赖第三方 feed 库。

**RSS 采集器**（`collectors/rss.py`）

- 入口函数：`fetch_rss(source)`
- 兼容 RSS 2.0（`<item>`）和 Atom（`<entry>`）两种格式
- 字段映射：
  - 标题：`title`
  - 链接：`link` 或 Atom `link[@href]`
  - 摘要：`description` / `summary`
  - 时间：`pubDate` / `published` / `updated`
- 摘要经过 `strip_html()` 清洗，去除 HTML 标签
- RSS 只作为候选发现层，正文证据由后续 `enrich_content.py` 二次抓取

**配置示例**：

```yaml
- id: sec_press_releases
  source_type: rss
  source_group: background
  url: https://www.sec.gov/news/pressreleases.rss
  max_items: 2
```

### 3. 搜索计划回填（Tavily）

**代表来源**：AI 前沿技术、AI Agent 与开源工具、AI 商业化与企业采用、AI 创业融资与产品发布

**核心逻辑**：采集器不直接搜索。先由 `write_tavily_plan()` 根据配置生成搜索计划文件（`runtime/tavily_search_plan.json`），再由外部 OpenClaw Skill 执行搜索并回填结果到 `runtime/tavily_search_results.json`，最后由 `read_tavily_results()` 读取结果转换为 `RawItem`。

**Tavily 采集器**（`collectors/tavily.py`）

- `write_tavily_plan(config, path)`：遍历 `topics`，为每个主题生成一条搜索任务项，包含 query、域名白名单、时间窗口
- `read_tavily_results(path)`：读取回填结果 JSON，逐条转换为 `RawItem`
- 搜索计划的核心字段：

  ```json
  {
    "topic_id": "ai_agent_open_source",
    "topic_name": "AI Agent 与开源工具",
    "query": "AI agent MCP coding agent open source",
    "domains": ["github.com", "news.ycombinator.com"],
    "max_items": 5,
    "recency_days": 3,
    "since_date": "2026-06-04"
  }
  ```

- 这种"写计划 + 读结果"的两阶段解耦意味着搜索能力可以替换成任何 Skill

**配置示例**：

```yaml
openclaw_tavily:
  enabled: true
  skill_name: tavily-search
  max_items_per_topic: 5
  recency_days: 3
  topics:
    - id: ai_frontier_technology
      name: AI 前沿技术
      query: latest AI model release multimodal reasoning inference benchmark
      domains: [openai.com, anthropic.com, deepmind.google, ai.meta.com]
    - id: ai_agent_open_source
      name: AI Agent 与开源工具
      query: AI agent MCP coding agent open source GitHub Hacker News
      domains: [github.com, news.ycombinator.com, huggingface.co]
```

**主题切换**：要把早报从 AI 换成其他领域，只需修改 `topics` 里的 `name`、`query`、`domains` 三个字段，流程代码不用动。

## 采集调度与去重

**调度器**（`collectors/orchestrator.py`）

`collect_all(config, root=...)` 是统一入口，按以下顺序执行：

1. 遍历 `fixed_sources`（GitHub、HN、RSS），逐个调用对应采集器
2. 处理 Tavily：先写搜索计划，再读取已有结果文件
3. 对所有候选做精确去重（`dedup_exact()`，按 URL 去重）
4. 按 `lookback_days`（默认 3 天）过滤过旧候选

返回值：`(items: List[RawItem], reports: List[Dict])`，其中 reports 记录每个来源的采集状态和数量。

**去重规则**（`collectors/items.py`）

- `dedup_exact()`：按 `item.url`（URL 相同视为重复）做精确去重
- 语义去重（同一事件不同标题）留给后续 LLM 标题粗筛阶段处理

## 统一数据模型

所有来源输出统一的 `RawItem` 结构（定义在 `models.py`）：

```python
@dataclass
class RawItem:
    item_id: str           # sha1(source_id|url|title)
    source_id: str         # 来源标识，如 github_high_stars
    source_name: str       # 来源显示名，如 GitHub 高星项目
    source_group: str      # primary / background
    source_type: str       # 采集器类型
    title: str             # 候选标题
    url: str               # 原始链接
    published_at: str      # 发布时间（ISO 格式）
    raw_snippet: str       # 原始摘要片段
    raw_metadata: dict     # 来源特有的结构化元数据
    fetched_at: str        # 采集时间（UTC ISO 格式）
```

关键约束：
- `raw_metadata` 只存储来源特有数据（stars、score、query、rank 等），不会进入正式摘要
- `raw_snippet` 只作为候选线索，正文证据由 `enrich_content.py` 二次抓取补充
- `item_id` 由 `source_id + url + title` 的 SHA-1 生成，保证同一条目幂等

## 暂停来源

以下来源已配置但当前暂停：

| source_id | 名称 | 暂停原因 |
|---|---|---|
| `github_security_advisories` | GitHub Advisory | 安全公告容易把 AI 早报带成漏洞简报 |
| `executive_mailbox` | 邮箱告警 | 私有提醒不进入公开早报，独立走邮箱侧链 |
