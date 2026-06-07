# CRM Assistant

一个面向**私域销售 / 高净值线索跟进**场景的会议理解 Skill。  
它的目标是：把会议转录文本或飞书会议原始数据，转换成可落到 CRM / 飞书多维表格中的结构化结果。

> 当前项目已经收敛为 **纯 Python CLI**，适合没有 `pwsh / powershell` 的 Linux / 云服务器环境。  
> 所有核心流程统一通过 `scripts/crm_assistant.py` 执行。

---

## 1. 项目定位

这个项目解决的是会议结束后的这段工作流：

```text
会议原始数据 / 转录文本
  -> 提取客户上下文与发言内容
  -> 判断客户需求、顾虑、阶段、意向、价值
  -> 生成客户画像增量
  -> 生成商机推进快照
  -> 输出飞书多维表格可写入结果
```

适用场景包括：

- 销售会议纪要整理
- 高净值客户跟进
- 私域 CRM 更新
- 飞书多维表格商机推进记录
- 同一客户多轮会议阶段变化追踪

---

## 2. 当前已实现能力

本项目当前已完成并验证了以下能力：

### 2.1 规则链路

输入：
- `transcript.txt`
- `context.json`

输出：
- `meeting_record.json`
- `customer_profile_update.json`
- `opportunity_update.json`
- `follow_up_task.json`
- `pre_meeting_brief.json`
- `customer_table_row.json`
- `opportunity_snapshot_row.json`
- `crm_packet.json`

### 2.2 飞书原始数据链路

输入：
- `feishu_raw/*.json`

中间过程：
- 提取 `context.json`
- 提取 `transcript.txt`

再进入主处理流程，输出 CRM 结果与飞书两表 payload。

### 2.3 LLM 提示词链路

支持从样本生成标准提示词包：
- `system_prompt.txt`
- `user_prompt.txt`
- `prompt_package.json`

默认会拼入 `zhongguoyidong_ops_rich` 和 `ningdeshidai_service_rich`，用来强化这些字段的稳定抽取：
- `MBTI`
- `是否单身`
- `沟通风格`
- `成交阻力`
- `价格敏感程度`
- `风险顾虑`
- `客户画像摘要`

并支持：
- 校验大模型结构化输出
- 将模型输出转成 CRM / 飞书表结果

### 2.4 多轮客户推进链路

支持同一客户跨多轮会议的推进分析，可输出：
- 各轮独立结果
- `journey_summary.json`

### 2.5 用户侧 Prompt 模式

支持直接把**飞书会议原始 JSON** 喂给 OpenClaw：

```text
飞书原始 JSON
  -> 提取 context + transcript
  -> 生成两张飞书表记录
  -> 能写飞书就写，不能写就输出待写入内容
```

---

## 3. 当前链路状态

当前版本已经实际跑通以下检查：

- 规则样本测试
- 飞书原始数据链路测试
- LLM 输出校验与转换测试
- 多轮客户推进测试
- Prompt 生成测试

也就是说，从“原始输入”到“结构化结果”的核心业务链路是完整的。

> 当前版本优先面向“用户侧 Prompt 发起 -> OpenClaw 生成并写入飞书表格”的使用方式。

---

## 4. 飞书数据设计

本项目当前固定采用**两表方案**：

### 表 1：客户信息表

用途：
- 沉淀长期客户画像
- 按 `客户ID` 做 upsert

核心字段：
- 客户ID
- 客户名称
- 客户公司
- 行业
- MBTI
- 是否单身
- 沟通风格
- 成交阻力
- 价格敏感程度
- 风险顾虑
- 客户画像摘要
- 客户负责人
- 最后更新时间
- 数据来源

### 表 2：商机推进快照表

用途：
- 每次会议结束后追加一条快照
- 不覆盖历史，保留完整推进轨迹

核心字段：
- 商机ID
- 客户ID
- 客户名称
- 客户公司
- 机会名称
- 商机描述
- 当前阶段
- Lead Score
- 意向等级
- 高净值优先
- 销售区域
- 业务价值
- 推荐动作
- 最新进展
- 下次跟进时间
- 最近会议时间
- 商机负责人
- 数据来源

---

## 5. 项目结构

```text
crm-assistant/
├─ agents/
│  └─ openai.yaml
├─ assets/
│  ├─ expected/          # 测试断言
│  ├─ feishu_raw/        # 飞书原始会议样本
│  ├─ few_shot/          # few-shot 示例
│  └─ samples/           # transcript/context 样本
├─ references/
│  ├─ input_schemas.md
│  ├─ output_schemas.md
│  ├─ feishu-bitable-mapping.md
│  ├─ llm_prompt_template.md
│  ├─ llm_output_schema.md
│  ├─ openclaw_system_prompt.md
│  ├─ openclaw_user_side_write_prompt.md
│  └─ user_side_feishu_prompt.md
├─ runtime/              # 运行产物 / 测试输出
├─ scripts/
│  └─ crm_assistant.py
├─ README.md
└─ SKILL.md
```

---

## 6. 快速开始

## 6.0 环境要求

- Python 3.10+
- 无第三方依赖

如果你本地使用 conda，也可以直接用你之前的环境：

```bash
conda run -n env1 python ./scripts/crm_assistant.py --help
```

如果你在云服务器上走统一部署流程，也可以先执行：

```bash
pip install -r requirements.txt
```

## 6.1 方式一：直接处理 transcript + context

```bash
python ./scripts/crm_assistant.py process-transcript \
  --transcript-path ./assets/samples/your_transcript.txt \
  --context-path ./assets/samples/your_context.json \
  --output-dir ./runtime/your_case
```

---

## 6.2 方式二：从飞书原始数据开始

先提取标准化输入：

```bash
python ./scripts/crm_assistant.py build-context-from-feishu \
  --raw-input-path ./assets/feishu_raw/your_feishu_raw.json \
  --output-dir ./runtime/from_feishu/your_case
```

再进入主处理：

```bash
python ./scripts/crm_assistant.py process-transcript \
  --transcript-path ./runtime/from_feishu/your_case/transcript.txt \
  --context-path ./runtime/from_feishu/your_case/context.json \
  --output-dir ./runtime/from_feishu/your_case/process
```

如果你已经配置好飞书写表信息，推荐直接走一条命令串完整链路：

```bash
python ./scripts/crm_assistant.py ingest-feishu-raw-to-bitable \
  --raw-input-path ./assets/feishu_raw/your_feishu_raw.json \
  --output-dir ./runtime/ingest/your_case \
  --config-path ./your_feishu_config.json
```

这会自动完成：
- 提取 `context.json`
- 提取 `transcript.txt`
- 生成 `crm_packet.json`
- 将客户信息表 upsert 到飞书
- 将商机推进快照表 append 到飞书

客户信息表写入前会优先保护历史明确值：
- 如果本轮某字段只得到 `未明确`、`暂无`、`null`、空数组这类弱值，而历史已有清晰值，则保留历史值
- 真正写入飞书的应是合并后的最终 `customer_table_row`

---

## 6.3 方式三：生成标准 LLM Prompt 包

```bash
python ./scripts/crm_assistant.py build-llm-prompt \
  --transcript-path ./assets/samples/your_transcript.txt \
  --context-path ./assets/samples/your_context.json \
  --output-dir ./runtime/llm_prompt/your_case
```

---

## 6.4 方式四：校验并转换 LLM 输出

```bash
python ./scripts/crm_assistant.py validate-model-output \
  --model-output-path ./runtime/llm_outputs/your_case/model_output.json

python ./scripts/crm_assistant.py convert-model-output \
  --model-output-path ./runtime/llm_outputs/your_case/model_output.json \
  --context-path ./assets/samples/your_context.json \
  --output-dir ./runtime/from_model/your_case
```

---

## 6.5 方式五：用户侧 Prompt 直接使用

如果你希望直接喂给 OpenClaw / 龙虾，可优先使用：

- `references/openclaw_user_side_write_prompt.md`

如果你还需要更完整的解释版说明，可再参考：

- `references/user_side_feishu_prompt.md`

这版 Prompt 的输入是：
- 飞书会议原始 JSON

这版 Prompt 的目标是：
- 先提取 `context + transcript`
- 再生成两张飞书表记录
- 如果具备能力，再直接写飞书

---

## 7. 输出说明

推荐重点关注：

### `crm_packet.json`
总包结果，包含：
- 会议结果
- 客户画像增量
- 商机判断
- 跟进任务
- 会前简报
- 飞书两张表记录
- 两表写入 payload

### `customer_table_row.json`
客户信息表单行结果。

如果 `context.json` 或飞书已有记录里带了历史画像，当前版本会先做一次“弱值不覆盖旧值”的合并，再输出最终行。

### `opportunity_snapshot_row.json`
商机推进快照表单行结果。

---

## 8. 测试命令

### 全部规则样本

```bash
python ./scripts/crm_assistant.py run-sample-tests
```

### 全部飞书原始链路样本

```bash
python ./scripts/crm_assistant.py run-feishu-pipeline-tests
```

### 全部 LLM 输出链路样本

```bash
python ./scripts/crm_assistant.py run-model-output-tests
```

### 多轮客户推进样本

```bash
python ./scripts/crm_assistant.py run-customer-journey \
  --manifest-path ./assets/samples/your_journey_manifest.json \
  --output-dir ./runtime/your_case_journey
```

---

## 9. 给龙虾 / OpenClaw 部署建议

如果你准备让龙虾部署这个 Skill，建议优先走这两条方式之一：

### 方式 A：项目化调用
- 先用脚本处理 `feishu_raw`
- 再输出标准结果
- 适合结构化演示

### 方式 B：用户侧 Prompt 调用
- 优先使用 `references/openclaw_user_side_write_prompt.md`
- 如需更完整说明，再参考 `references/user_side_feishu_prompt.md`
- 输入飞书会议原始 JSON
- 让模型先提取 `context + transcript`
- 再生成两张飞书表结果

如果是教学 / 演示 / 快速落地，优先建议 **方式 B**。

---

## 10. 当前边界

当前版本未包含：

- 真正的线上 ASR / 会议录音接入
- 持久化数据库
- 正式权限管理与审计机制

当前版本已经足够支持：

- Skill 演示
- Prompt 实战
- 会议纪要理解
- CRM 字段结构化
- 飞书多维表格写入前的数据准备

---

## 11. 参考资料

- `SKILL.md`
- `references/input_schemas.md`
- `references/output_schemas.md`
- `references/feishu-bitable-mapping.md`
- `references/llm_prompt_template.md`
- `references/llm_output_schema.md`
- `references/openclaw_system_prompt.md`
- `references/openclaw_user_side_write_prompt.md`
- `references/user_side_feishu_prompt.md`

---

## 12. 一句话总结

这是一个已经跑通核心链路的 CRM 会议理解 Skill：  
**它能把飞书会议原始数据或转录文本，转换成客户画像、商机推进判断，以及两张飞书表可直接落地的结构化结果。**
