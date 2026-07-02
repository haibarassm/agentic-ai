# Multi-File Refactor

> 配套课程：AI 业务流架构师 · 第 17 节《多文件协同与终端代码级重构实战》

本节的**实验工作区**：让 Claude Code 读懂一整个项目群，并安全地完成一次跨文件、跨项目的重构——把 `financial-automation`（第 13 节）、`CRM-Assistant`（第 15 节）和 `xhs-auto-publisher`（第 12 节）各写了一遍的飞书对接，抽成一个共享 `FeishuClient`。

```
读懂代码库（按需检索 Glob/Grep/Read + 依赖图）
  → 安全重构（抽出共享 FeishuClient：认证 / 端点 / Bitable / 容错）
  → 工程化护栏（pre-commit + GitHub CI + PR 自动摘要）
```

## 与课程的关系

本目录是第 17 节的实战工作区，服务于课程的三个核心留存物：

| 留存物 | 在本工作区中的体现 |
|--------|------------------|
| **给目标，不给步骤** | 让 Claude Code 自己 Glob/Grep/Read 读懂 4 个 app、画依赖图、定位重复——你不挑文件喂它 |
| **安全重构四件套** | 先方案 → 分批 + diff 审查 → 测试兜底 → dry-run / git 回滚，全程骑在 app 自带的测试网上 |
| **规则只是期望，机制才是保障** | pre-commit + CI + PR 摘要，把"都走共享客户端"从口头约定焊成自动机制 |

## 这是个"沙箱"，不是新 app

- 本目录**不产出新的可复用应用**，它是 L17 的练习工作区。
- `setup.sh` 会把 `financial-automation` + `CRM-Assistant` 的**快照**拷进来再动手，**原始 app 目录绝不改动**——这既是真实工程对待遗留代码的姿势（在隔离副本上改，原件永远安全），也保证课程录播与仓库一致。
- 两个原 app 本是各自独立的 Python 项目（各有 venv），把它们并进同一个工作区，才谈得上抽一个共享层。

## 快速开始

```bash
# 在仓库根，让 Claude Code 跑这个脚本（或自己 bash）
bash claude-code/multi-file-refactor/setup.sh
```

脚本完成"快照两个 app + 建 venv + 跑重构前绿色基线"。然后跟着 lesson17-lab.md 一步步做。

> 想从零重练：先 `rm -rf claude-code/multi-file-refactor/{financial-automation,CRM-Assistant,xhs-auto-publisher,common}` 再跑脚本。

## 重构靶子（真实存在的重复）

三个 app 各写了一遍飞书对接——同一件事、却没法直接互换：

| 关注点 | `financial-automation` | `CRM-Assistant` | `xhs-auto-publisher` |
|--------|----------------------|-----------------|---------------------|
| 取 tenant_access_token | `get_tenant_access_token(settings)` | `get_feishu_tenant_access_token(app_id, app_secret)` | 无（走龙虾代理） |
| 认证端点 | `/open-apis/auth/v3/tenant_access_token/internal` | 同上 | — |
| 入参 / 异常 | `settings` 对象 / `BitableSyncError` | 裸参数 / `RuntimeError` | — |
| Bitable 调用 | `sync_bitable.py` / `bitable_session_writer.py` / `bitable_attachment_uploader.py` | `list/batch_create/batch_update_feishu_bitable_records` | — |
| IM 消息 | 无 | 无 | `cloud_notify.py`（仅写 lobster payload，龙虾代发飞书群） |

> 函数名、签名、异常类型都不同，所以不能"查找替换"一把梭——必须语义级理解后改写，这正是 Claude Code 的主场。

## 共享层 `common/feishu/` 收敛什么

重构后三个 app 都从一个 `common/feishu/` **包**导入（按职责拆成 7 个模块）：

| 模块 | 职责 |
|------|------|
| **`errors.py`** | 统一异常树 `FeishuError`（下挂 `FeishuAuthError` / `FeishuHTTPError` / `FeishuAPIError`）；继承 `RuntimeError` 保兼容 |
| **`http.py`** | 统一传输层 `post_json()` / `post_multipart()` / `request_json()`，60s 超时，HTTP/业务码统一异常 |
| **`auth.py`** | `fetch_tenant_access_token()`，端点作参数传入，不再硬编码 `open.feishu.cn` |
| **`bitable.py`** | Bitable API：分页 list / batch_create / batch_update / Drive 媒体上传 |
| **`im.py`** | IM 能力：上传 IM 图片（拿 image_key）/ 发图片消息 / 发文本消息 —— 为 xhs 新增 |
| **`client.py`** | `FeishuClient` 门面：token 懒加载缓存 + 可注入 transport 便于测试 |
| **`__init__.py`** | 对外导出公共 API |

> 实测：去重约 **450+ 行**，财务 29 + CRM 2 + common 12 = **43 个测试一遍全绿**、行为零变化。

## 目录结构

```
multi-file-refactor/
├── README.md
├── lesson17-lab.md          # 第 17 节实验手册（学生跟做）
├── setup.sh                 # 搭工作区：快照 + venv + 重构前绿色基线
├── common/feishu/           # 共享飞书客户端包（errors/auth/http/bitable/im/client）
├── common/tests/            # 共享包单测
│   ├── __init__.py
│   └── test_feishu_client.py
├── financial-automation/    # 快照（跑 setup.sh 后生成；原件在仓库顶层，不动）
├── CRM-Assistant/           # 快照（同上）
├── xhs-auto-publisher/      # 快照（同上）
├── .github/                 # 工程化护栏
│   ├── workflows/ci.yml     # GitHub Actions CI（三项目测试 + 密钥扫描）
│   └── PULL_REQUEST_TEMPLATE.md  # PR 自动摘要模板
└── .git-hooks/              # 本地护栏
    └── pre-commit           # 拒绝硬编码 open.feishu.cn / 绕过 FeishuClient
```

## 工程化护栏

### 三道关

| 关 | 范围 | 功能 |
|---|---|---|
| **1. pre-commit** | 本地 | 拒绝提交硬编码 `open.feishu.cn` / 绕过 FeishuClient 自拼 token 的代码 |
| **2. GitHub CI** | 云端 | push / PR 时自动跑三项目测试 + common 包单测 + 密钥扫描 |
| **3. PR 摘要** | PR | 基于模板自动生成重构摘要，讲清抽了什么、两个 app 怎么受影响、测试是否通过 |

### 安装 pre-commit

```bash
# 方法 1：复制到仓库根 .git/hooks（推荐）
cp claude-code/multi-file-refactor/.git-hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# 方法 2：全局配置 core.hooksPath（需仓库根 .git/hooks 存在）
git config core.hooksPath claude-code/multi-file-refactor/.git-hooks
```

## 验证命令（重构前后都用它确认行为没变）

```bash
# financial：单元冒烟测试
cd financial-automation && python -m unittest tests.test_smoke

# CRM：merge policy tests
cd CRM-Assistant && python scripts/crm_assistant.py run-merge-policy-tests

# common 包单测
python -m unittest common.tests.test_feishu_client

# xhs cloud_notify smoke（双模式：lobster 回归 + feishu_client）
cd xhs-auto-publisher && python -c "from src.cloud_notify import CloudNotifier; ..."
```

> 这些命令本就记录在项目根 `CLAUDE.md` 里，课上由 Claude Code 自己调用——你给目标即可。
