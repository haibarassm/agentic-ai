﻿---
name: crm-assistant
description: 将已经完成转录的会议文本转换成适用于私域销售跟进的 CRM 结构化结果。当 Codex 需要基于会议 transcript 和基础客户上下文，生成会议摘要、客户画像增量、商机判断、跟进任务、会前简报，并最终整理成可写入现有飞书多维表格的结果时使用。
---

# CRM Assistant

在语音转文字已经完成之后使用本 Skill。输入一份 transcript 和一份小型 context JSON，将其转换成结构化 CRM 动作结果，并以“写入现有飞书客户信息表和商机推进快照表”为最终落地目标。

> 当前项目已经统一为 Python CLI：`scripts/crm_assistant.py`  
> 所有核心流程都通过这一个脚本的子命令完成。

## 快速开始

1. 准备：
   - 一份 transcript `.txt` 文件
   - 一份 context `.json` 文件，包含客户、负责人、会议时间、商机等基础信息
2. 运行：

```bash
python ./scripts/crm_assistant.py process-transcript \
  --transcript-path ./runtime/from_feishu/your_case/transcript.txt \
  --context-path ./runtime/from_feishu/your_case/context.json \
  --output-dir ./runtime/your_case
```

3. 查看输出目录中的结果文件：
   - `crm_packet.json`
   - `meeting_record.json`
   - `customer_profile_update.json`
   - `opportunity_update.json`
   - `follow_up_task.json`
   - `pre_meeting_brief.json`
   - `customer_table_row.json`
   - `opportunity_snapshot_row.json`

## 飞书原始输入模式

如果上游是飞书会议，而不是你手工准备好的 `transcript.txt + context.json`，先把飞书原始数据整理成 `feishu_meeting_raw.json`，再运行转换脚本。

```bash
python ./scripts/crm_assistant.py build-context-from-feishu \
  --raw-input-path ./assets/feishu_raw/your_feishu_raw.json \
  --output-dir ./runtime/from_feishu/your_case
```

会生成：
- `context.json`
- `transcript.txt`
- `build_result.json`

然后再送入主处理脚本：

```bash
python ./scripts/crm_assistant.py process-transcript \
  --transcript-path ./runtime/from_feishu/your_case/transcript.txt \
  --context-path ./runtime/from_feishu/your_case/context.json \
  --output-dir ./runtime/from_feishu/your_case/process
```

## LLM 提示词模式

如果你希望把“识别与判断”交给 OpenClaw 背后的大模型，而不是完全依赖当前规则脚本，可以先组装一份标准提示词包。

```bash
python ./scripts/crm_assistant.py build-llm-prompt \
  --transcript-path ./runtime/from_feishu/your_case/transcript.txt \
  --context-path ./runtime/from_feishu/your_case/context.json \
  --output-dir ./runtime/llm_prompt/your_case
```

会生成：
- `system_prompt.txt`
- `user_prompt.txt`
- `prompt_package.json`

这套提示词包包含：
- 角色与任务定义
- 商机阶段判断标准
- 输出 schema
- few-shot 示例
- 当前待处理输入

如果你已经拿到了大模型输出 JSON，可继续运行：

```bash
python ./scripts/crm_assistant.py validate-model-output \
  --model-output-path ./runtime/llm_outputs/your_case/model_output.json

python ./scripts/crm_assistant.py convert-model-output \
  --model-output-path ./runtime/llm_outputs/your_case/model_output.json \
  --context-path ./runtime/from_feishu/your_case/context.json \
  --output-dir ./runtime/from_model/your_case
```

## 用户侧 Prompt 模式

如果你希望直接从用户侧把飞书原始会议 JSON 喂给 OpenClaw，并让它尽量完成“理解会议 -> 生成结果 -> 写入现有飞书表格”的整条链路，优先使用项目内置 Prompt：

- `references/openclaw_user_side_write_prompt.md`

如需更完整的解释版说明，可再参考：

- `references/user_side_feishu_prompt.md`

处理这类“用户侧 raw -> 最终写入飞书表格”的请求时，优先遵循下面顺序：
1. 先读取 `references/openclaw_user_side_write_prompt.md`
2. 按该文件中的固定 Base、客户信息表、商机推进快照表目标执行
3. 先提取 `context + transcript`
4. 再生成两张飞书表记录
5. 如果当前环境具备飞书实际操作能力，则继续完成写入；如果不具备，则明确返回待写入内容和失败原因

这个模式更适合：
- 演示
- 轻量人工协同
- 直接输入飞书原始会议 JSON，让 OpenClaw 先提取 `context + transcript`
- 让 OpenClaw 生成客户信息表记录和商机推进快照表记录
- 当前 OpenClaw 已具备飞书操作能力时，最终直接写入现有飞书表格
- 如果当前环境不具备实际写入能力，则返回待写入内容和失败原因

## 同一客户多轮推进

当同一客户跨多轮会议持续推进、你想查看其阶段变化和得分变化时，可先准备一份自己的 journey manifest。

```bash
python ./scripts/crm_assistant.py run-customer-journey \
  --manifest-path ./assets/feishu_raw/your_journey_manifest.json \
  --output-dir ./runtime/your_case_journey
```

会生成：
- 每一轮一个独立子目录
- `journey_summary.json`

可用于查看：
- 同一客户如何从一个阶段推进到下一个阶段
- Lead Score 如何随轮次变化
- 每一轮推荐的下一步动作是什么
- 每一轮会新增哪一条飞书快照记录

## 项目逻辑

### 输入
1. 主输入：`transcript.txt`
2. 辅助输入：`context.json`
3. 可选输入：`feishu_raw/*.json`
4. 可选输入：LLM 的结构化 `model_output.json`

### 中间处理
1. 从 transcript 中抽取需求、顾虑、沟通风格、MBTI 线索、是否单身线索、成交阻力、价格敏感程度，以及预算/区域/时间信息
2. 结合 context 补齐客户、负责人、商机、会议时间等基础字段
3. 生成五类核心业务对象：
   - 会议记录
   - 客户画像增量
   - 商机更新
   - 跟进任务
   - 会前简报
4. 映射成飞书两张表可写入的结构：
   - 客户信息表：按客户 ID 做 upsert
   - 商机推进快照表：每次会议 append 一行
   - 如果客户信息表中已有旧值，而本轮某字段只得到 `未明确`、`暂无`、`null` 这类弱值，则保留旧值，不要用弱值覆盖
5. 如果当前运行环境具备飞书实际操作能力，则继续把这两张表记录写入现有飞书多维表格；如果不具备，则返回待写入内容与失败原因

### 输出
- 标准 CRM JSON 文件
- 飞书客户信息表单行对象
- 飞书商机推进快照单行对象
- `feishu_bitable_payload` 两表写入载荷
- 在具备能力时，最终完成对现有飞书表格的写入

## 脚本

- `scripts/crm_assistant.py`
  - Python 主入口
  - 通过子命令覆盖完整链路：
    - `process-transcript`
    - `build-context-from-feishu`
    - `build-llm-prompt`
    - `validate-model-output`
    - `convert-model-output`
    - `run-sample-tests`
    - `run-feishu-pipeline-tests`
    - `run-model-output-tests`
    - `run-customer-journey`
    - `inspect-feishu-bitable`
    - `sync-feishu-bitable`
    - `ingest-feishu-raw-to-bitable`

## 参考资料

按需读取：
- `references/input_schemas.md`
- `references/output_schemas.md`
- `references/feishu-bitable-mapping.md`
- `references/llm_prompt_template.md`
- `references/llm_output_schema.md`
- `references/openclaw_user_side_write_prompt.md`

## 样本资源

使用 `assets/feishu_raw/` 中的飞书原始会议样本可快速测试或演示本 Skill。先用 `build-context-from-feishu` 提取 `context.json` 和 `transcript.txt`，再送入主处理流程。

运行全部规则样本：

```bash
python ./scripts/crm_assistant.py run-sample-tests
```

运行全部飞书链路样本：

```bash
python ./scripts/crm_assistant.py run-feishu-pipeline-tests
```

运行全部模型输出样本：

```bash
python ./scripts/crm_assistant.py run-model-output-tests
```

LLM few-shot 示例位于：
- `assets/few_shot/zhongguoyidong_ops_rich.json`
- `assets/few_shot/ningdeshidai_service_rich.json`

## 输出规范

优先保证：
- 中文业务摘要简洁清晰
- 下一步动作明确
- 跟进草稿可直接给负责人使用
- 字段名适合飞书多维表格
- JSON 结构稳定可复用

避免：
- 原始 prompt 痕迹
- 隐式推理过程外露
- 过长且无结构的大段文本
- 在没有明确证据时覆盖长期客户字段
