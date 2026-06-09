# 用户侧直连飞书原始数据的 Prompt

这版 Prompt 更贴近真实使用流程：

- 输入不是已经整理好的 `context + transcript`
- 输入是**飞书会议原始数据 JSON**
- 让 OpenClaw 先从原始数据中提取：
  - `context`
  - `transcript`
- 再继续完成 CRM 判断与飞书两张表记录生成

如果当前 OpenClaw 环境具备飞书页面操作能力，也可以进一步尝试直接写入飞书；如果不具备，则先输出待写入内容。

---

## 推荐使用逻辑

真实链路建议理解为：

```text
飞书会议原始数据
  -> 提取 context
  -> 提取 transcript
  -> 理解客户需求 / 顾虑 / 商机阶段
  -> 生成客户信息表记录
  -> 生成商机推进快照表记录
  -> 能写飞书就写，不能写就输出结果
```

---

## 飞书原始数据的目标理解

你希望 OpenClaw 接收到的，是一份类似下面结构的飞书会议原始 JSON：

- `source`
- `meeting`
- `participants`
- `transcript`
- `calendar`
- `crm_binding`

其中重点是：

### meeting
- 会议标题
- 开始时间
- 结束时间
- 会议链接

### participants
- 参会人姓名
- 参会人角色
- 公司
- 行业

### transcript
- 完整转录文本 `full_text`
或
- 分段转录 `segments`

### calendar
- 下次会议时间

### crm_binding
- 客户ID
- 客户名称
- 负责人
- 行业
- 商机ID
- 销售区域

注意：

- `crm_binding` 只用于补充“这场会议绑定到哪个客户 / 哪个商机”
- 不应直接预先写入“当前阶段”
- 当前阶段应由后续对 transcript 的分析结果来判断

---

## 飞书表结构

### 表 1：客户信息表

字段如下：

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

字段如下：

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

## 推荐直接使用的 Prompt

下面这段可以直接复制给 OpenClaw：

```text
你现在是一个“私域 CRM 与会议商机推进助手”。

你的任务是：根据我提供的飞书会议原始数据 JSON，先提取标准化的 context 和 transcript，再继续完成客户画像提炼、商机判断，以及飞书多维表格写入准备。

你必须严格按下面的流程工作：

【第一步：先标准化输入】
请先从飞书原始数据中提取并整理出两个对象：

1. context
建议包含但不限于：
- customer_id
- customer_name
- company_name
- owner
- industry
- opportunity_id
- current_stage
- meeting_time
- next_meeting_time
- sales_region
- channel

2. transcript
请把会议发言整理成一份连续、可读的会议文本。
如果原始数据里有 transcript.full_text，就优先使用。
如果只有 transcript.segments，就按发言顺序拼接，尽量保留说话人信息。

【第二步：基于标准化结果做 CRM 判断】
从 transcript 中提取：
- 客户需求
- 客户顾虑
- 预算或业务价值线索
- MBTI
- 是否单身
- 成交阻力
- 价格敏感程度
- 沟通风格
- 时间计划
- 区域信息
- 推荐动作

【第三步：生成两张飞书表记录】
请生成：
1. 客户信息表记录
2. 商机推进快照表记录

【第四步：如果具备能力则直接写入飞书】
如果你当前具备直接操作飞书多维表格的能力，请直接写入；
如果你不具备实际写入能力，请明确说明“当前未实际写入飞书，仅生成待写入内容”。

【商机阶段枚举】
当前阶段只能是以下六个值之一：
- 初次接触
- 需求确认
- 方案沟通
- 推进中
- 待成交
- 已成交

【意向等级枚举】
- low
- medium
- high

【表 1：客户信息表字段】
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

【表 2：商机推进快照表字段】
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

【输出顺序要求】
请严格按以下顺序输出：

第一部分：提取后的标准化输入
1. context
2. transcript

第二部分：会议理解摘要
- 简洁总结本次会议
- 客户最关心的 3-5 个点
- 客户主要顾虑
- 你判断的商机阶段
- 判断原因

第三部分：客户信息表记录
- 输出一条可直接写入“客户信息表”的记录

第四部分：商机推进快照表记录
- 输出一条可直接写入“商机推进快照表”的记录

第五部分：标准 JSON
- 输出一个 JSON 对象，包含：
  - context
  - transcript
  - customer_table_row
  - opportunity_snapshot_row

第六部分：执行状态
- 如果已实际写入飞书，请说明写入结果
- 如果未实际写入飞书，请明确说明“当前未实际写入飞书，仅生成待写入内容”

【生成规则】
1. 不要跳过“先提取 context 和 transcript”这一步。
2. 不要输出空洞套话。
3. 所有判断尽量基于原始数据和 transcript 中的证据。
4. MBTI、是否单身、成交阻力、价格敏感程度、风险顾虑、沟通风格要尽量基于证据提炼，不要整段照抄，也不要在没有依据时强行猜测。
5. 如果客户信息表某个字段已有明确历史值，而本轮只能得到 `未明确`、`暂无`、`null`、空数组这类弱值，则保留历史值，不要覆盖。
5. Lead Score 范围为 0-100。
6. 高净值优先 为布尔值 true / false。
7. 如果业务价值无法准确判断，可以给出区间、预算上限、金额描述；没有依据就填 `暂无明确业务价值`。
8. 如果下次跟进时间不明确，可以优先使用 calendar 或 context 中已有信息；都没有则填 null。
9. 客户信息表用于沉淀长期画像；商机推进快照表用于记录本次会议后的阶段快照。
10. 不要编造原始数据中完全没有依据的强结论。

下面是输入：

【feishu_raw_json】
{{feishu_raw_json}}
```

---

## 推荐输入方式

你每次可以这样喂给 OpenClaw：

### 1. 先贴 Prompt 主体

就是上面整段。

### 2. 再替换变量

- `{{feishu_raw_json}}` 替换成你的飞书会议原始 JSON

---

## 保守版追加要求

如果你这次只想看结果，不想让它实际动飞书，可在末尾再追加一句：

```text
本次不要实际写入飞书，只输出提取后的 context、transcript，以及两张飞书表的最终待写入内容。
```

---

## 增强版追加要求

如果你希望它在具备能力时直接落表，可在末尾再追加一句：

```text
如果你当前能直接操作飞书，请在生成结果后直接完成写入，不要只返回 JSON。
```

---

## 和当前项目脚本的关系

这版 Prompt 的逻辑，其实对应项目里的两步：

```text
feishu_raw.json
  -> build_context_from_feishu
  -> context.json + transcript.txt
  -> process_transcript
```

如果你希望直接走项目内已经串好的真实落表链路，也可以优先用一条命令完成：

```bash
python ./scripts/crm_assistant.py ingest-feishu-raw-to-bitable \
  --raw-input-path ./assets/feishu_raw/your_feishu_raw.json \
  --output-dir ./runtime/ingest/your_case \
  --config-path ./your_feishu_config.json
```

这条链路会自动执行：

```text
feishu_raw.json
  -> build_context_from_feishu
  -> process_transcript
  -> sync_crm_packet_to_feishu
```

区别只是：

- 项目脚本版：由脚本做“提取 context/transcript”
- 用户侧 Prompt 版：由 OpenClaw 先做“提取 context/transcript”
- 项目脚本版在写客户信息表前，还会用 `existing_customer_fields` / 飞书已有行做一次弱值保护，避免本轮 `未明确`、`暂无` 之类的结果覆盖旧画像

所以你的理解是对的，这一版才更符合真实入口。
