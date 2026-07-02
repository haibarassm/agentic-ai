# Lesson 17 多文件重构 PR 摘要

## 概述

本 PR 将 `financial-automation` 与 `CRM-Assistant` 中各自实现的飞书对接（认证 / 端点 / Bitable / 容错）抽取为共享的 `common/feishu/` 包（约 X 行去重），并为 `xhs-auto-publisher` 新增 `feishu_client` 直发模式（原仅通过 lobster 代理）。

## 变更范围

### 新增

- `common/feishu/` 共享飞书客户端包
  - `errors.py` — 统一异常树（FeishuError 及子类，继承 RuntimeError）
  - `http.py` — 统一传输层（post_json / post_multipart / request_json，60s 超时，HTTP/业务码统一异常）
  - `auth.py` — tenant_access_token 认证
  - `bitable.py` — Bitable API（分页 list / batch_create / batch_update / Drive 媒体上传）
  - `im.py` — IM 能力（上传图片 / 发图片 / 发文本）——为 xhs 新增
  - `client.py` — FeishuClient 门面（token 懒加载缓存，可注入 transport 便于测试）
  - `__init__.py` — 公共导出
- `common/tests/test_feishu_client.py` — 共享包单测（12 个测试，FakeTransport 模拟）
- `xhs-auto-publisher/src/cloud_notify.py` 新增 `feishu_client` 投递模式（默认 `lobster_channel`）
- `claude-code/multi-file-refactor/.github/workflows/ci.yml` — GitHub Actions CI
- `claude-code/multi-file-refactor/.git-hooks/pre-commit` — pre-commit hook

### 修改（仅快照副本，canonical 不动）

- `financial-automation/`：
  - `src/sync_bitable.py`：token / batch_create / upload_attachment 委托给 FeishuClient；删除本地 transport（`_post_json` / `_post_multipart` / `_read_json_response` / `_chunk_records`）；`BitableSyncError` 改为 FeishuClient 别名
  - `src/bitable_attachment_uploader.py`：post_multipart 从 common.feishu.http 导入
- `CRM-Assistant/`：
  - `scripts/crm_assistant.py`：7 个飞书函数（`get_feishu_tenant_access_token` / `list_feishu_bitable_*` / `batch_*`）委托给 common.feishu 模块函数；删除本地 `http_json_request` / `build_url` / `feishu_open_api_request`
- `xhs-auto-publisher/`：
  - `src/cloud_notify.py`：新增 `feishu_client` 模式（上传 IM 图片 + 发图片消息 + 可选文字说明 + 审计落盘），默认仍 `lobster_channel`

### 删除

- `financial-automation/src/sync_bitable.py`：`_post_json`, `_post_multipart`, `_read_json_response`, `_chunk_records`
- `CRM-Assistant/scripts/crm_assistant.py`：`http_json_request`, `build_url`, `feishu_open_api_request`

## 行为等价性验证

### 测试通过

- ✅ financial-automation: `tests.test_smoke` — **29/29 通过**
- ✅ CRM-Assistant: `run-merge-policy-tests` — **全通过**（`run-feishu-pipeline-tests` 与基线一致地 SKIP）
- ✅ common.feishu: `common.tests.test_feishu_client` — **12/12 通过**（token 缓存 / 分页 / chunking / 错误处理 / IM 传输）
- ✅ xhs-auto-publisher: `cloud_notify` smoke — **双模式全绿**（lobster 回归 / feishu_client 上链 / 缺凭证报错 / 文字失败容错 / 审计落盘）

### 护栏验证

- ✅ pre-commit：拒绝硬编码 `open.feishu.cn` / 绕过 FeishuClient 拼 token（仅 multi-file-refactor 目录）
- ✅ GitHub CI：三项目测试 + 密钥扫描（见 `.github/workflows/ci.yml`）

## 技术细节

- **异常兼容**：FeishuError 及子类继承 `RuntimeError`，保证 `except BitableSyncError` / `except RuntimeError` 调用点仍能捕获
- **分块策略**：`batch_create_records` 默认 batch_size=500（飞书上限），FA 原来可配置；CRM 调用返回原始 dict（`return_raw=True`）
- **Token 缓存**：FeishuClient 懒加载 token 并在进程内缓存（适合 CLI 批处理场景）
- **平台兼容**：Windows Git Bash 无 `python3`/`rsync` → 自动回退 `python` / `shutil.copytree`，venv 路径自动 `.venv/Scripts`（Windows） / `.venv/bin`（其他）
- **镜像回退**：清华镜像 403 时自动换阿里云（pip install 时）

## 后续步骤

本 PR 合并后：
1. 可选：将 `common/feishu/` 同步推广到 morning-newspaper（它也有飞书集成）
2. 可选：为 xhs-auto-publisher 补充更多飞书能力（如群机器人 @提及 等）
