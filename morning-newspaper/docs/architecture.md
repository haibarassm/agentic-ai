# 系统架构

> Morning Newspaper Assistant 完整架构说明，涵盖数据源、处理流水线、定时调度与交付。

## 外部数据源

| 数据源 | 协议 | 端点 | 配额 |
|---|---|---|---|
| GitHub Trending | REST API | `api.github.com/search/repositories` | 6 条 |
| Hacker News Top | REST API | `hacker-news.firebaseio.com/v0` | 6 条 |
| Tavily Search（4 主题） | REST API | `api.tavily.com/search` | 4×3 = 12 条 |
| SEC 新闻稿 | RSS | `sec.gov/news/pressreleases.rss` | 2 条 |
| 美联储新闻稿 | RSS | `federalreserve.gov/feeds/press_all.xml` | 1 条 |
| 邮箱 | IMAP/POP3 | 用户配置（可选） | — |

所有数据源在采集阶段统一汇入 `collected_raw.json`，后续阶段不再接触外部 API。

## 处理流水线

所有中间产物统一存放在 `runtime/` 目录。流水线分为四个阶段，形成严格的线性链路——每个阶段只消费上一阶段的产出。

### 阶段 1：采集与准备（纯脚本）

| 步骤 | 输入 | 输出 |
|---|---|---|
| collect_mailbox | `.env` + `sources.yaml` | `executive_mailbox.json`、`mail_event_queue.json` |
| collect_raw | `sources.yaml` + `.env` | `collected_raw.json`、`collect_report.json` |
| enrich_content | `collected_raw.json` | `content_enriched.json` |
| prepare_title_shortlist | `content_enriched.json` | `title_candidates.json`、`title_shortlist_prompt.txt` |

采集阶段并行调用 GitHub / HN / Tavily / RSS，全局精确去重。Tavily 按 4 个搜索主题分别调用 REST API。正文抓取阶段多线程获取每条新闻的完整正文，Tavily 条目会从 HTML meta 标签补齐发布时间。

### 阶段 2：LLM 关口 1 — 标题粗筛

| 步骤 | 输入 | 输出 |
|---|---|---|
| **OpenClaw 生成** | `title_shortlist_prompt.txt` | `title_shortlist_result.json` |
| apply_title_shortlist | `content_enriched.json` + `title_shortlist_result.json` | `shortlist.json` |
| prepare_draft_input | `shortlist.json` | `draft_input.json`、`draft_prompt.txt` |

OpenClaw 按 AI 主题相关性从候选中筛选并排序，目标保留约 15 条。apply 阶段还会执行来源多样性补位：若 GitHub 或 HN 被完全挤出，自动补入代表项。

### 阶段 3：LLM 关口 2 — 中文成稿

| 步骤 | 输入 | 输出 |
|---|---|---|
| **OpenClaw 生成** | `draft_prompt.txt` | `draft_result.json` |
| apply_draft_results | `draft_input.json` + `draft_result.json` | `drafted_items.json` |
| prepare_top10_ranking | `drafted_items.json` | `top10_ranking_input.json`、`top10_ranking_prompt.txt` |

OpenClaw 为每条候选生成中文标题和 2-3 句摘要。按 `rank_id` 匹配合并到原始条目。

### 阶段 4：LLM 关口 3 — Top10 精排 + 发布

| 步骤 | 输入 | 输出 |
|---|---|---|
| **OpenClaw 生成** | `top10_ranking_prompt.txt` | `top10_ranking_result.json` |
| apply_top10_ranking | `drafted_items.json` + `top10_ranking_result.json` | `top10_publishable.json`、`final_newspaper.json` |
| build_dashboard | `runtime/*` | `dashboard.html` |
| check_runtime_status | `runtime/*` | 诊断 JSON + `cron_status.json` |

apply 阶段执行来源多样性硬约束：Tavily 最多占 Top10 的 50%，GitHub 和 HN 各至少 2 条。砍掉超额 Tavily 后从候选池补满至 10 条。Dashboard 时间戳统一转为北京时间（CST）。

## 数据漏斗

```
采集 ~27 条 (GitHub 6 + HN 6 + Tavily 12 + RSS 3)
  → 去重 ~24 条
    → 正文抓取 ~24 条
      → LLM 关口1 粗筛 ~15 条
        → LLM 关口2 中文成稿 ~15 条
          → LLM 关口3 精排 10 条
            → 多样性约束 10 条 (Tavily ≤5, GitHub ≥2, HN ≥2)
              → dashboard.html + 飞书推送
```

## 定时调度

三个 Cron Job 按时间线协作，职责严格分离：

| 时间 | 任务 | 执行方式 | 职责 |
|---|---|---|---|
| **07:55** | 生成任务 | 创建隔离 OpenClaw Session | 执行完整流水线（含 3 个 LLM 关口），写 `cron_status.json` + `cron_group_message.txt`，不发送消息 |
| **07:58** | 群回执 | 飞书群消息 | 读 `cron_group_message.txt`，向专属飞书日报群发送执行回执 |
| **08:05** | 正式投递 | 读取结果 | 读 `cron_status.json`，成功则发送正式早报摘要，失败则发送告警 + 失败阶段归因 |

```
07:55 ──生成──→ 07:58 ──群回执──→ 08:05 ──正式投递
  │                │                  │
  ▼                ▼                  ▼
 isolated       飞书日报群         正式通知渠道
 OpenClaw       执行回执           早报摘要 / 失败告警
 Session
```

### 为什么用隔离 Session

- **不污染上下文**：早报生成在独立 Session 中完成，不干扰用户与 OpenClaw 的正常飞书对话
- **每天独立执行**：每次运行是独立执行单元，便于排障和回溯
- **OpenClaw 即 LLM**：不需要额外的 LLM API Key，OpenClaw 自身充当三道关口的 LLM

## 交付出口

| 出口 | 说明 |
|---|---|
| 静态页面 | `http://<IP>:8510/dashboard.html`，由 `serve_dashboard_8510.sh` 启动 |
| 飞书日报群 | 07:58 执行回执 + 08:05 正式早报摘要 |
| Streamlit 看板 | `scripts/dashboard_app.py`（可选，本地调试用） |

## 防护机制

| 机制 | 位置 | 作用 |
|---|---|---|
| mtime 时间戳校验 | 3 个 apply 脚本 | 结果文件必须比输入文件新，拦截上一轮遗留的旧 LLM 输出 |
| rank_id / title 匹配校验 | apply_draft_results、apply_top10_ranking | 结果中的 ID 或标题必须匹配当前输入，拦截内容不匹配的结果 |
| 来源多样性（shortlist 层） | apply_title_shortlist | GitHub / HN 被完全挤出时自动补入代表项 |
| 来源多样性（Top10 层） | apply_top10_ranking | Tavily ≤ 50%，GitHub / HN 各 ≥ 2，不足时从候选池补满 |
| 精确去重 | collect_raw (orchestrator) | 采集阶段按 URL 去重 |
| Session 隔离 | 07:55 Cron | 独立 agentTurn，不污染正常对话上下文 |

## 配置中心

| 文件 | 作用 |
|---|---|
| `config/sources.yaml` | 数据源开关与配额、Tavily 搜索主题与域名白名单、运行时参数 |
| `.env` | API Key（`GITHUB_TOKEN`、`TAVILY_API_KEY`）和邮箱凭据（`IMAP_USER`、`IMAP_PASS`） |
