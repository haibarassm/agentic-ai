# 输入结构说明

当前项目支持两层输入。

## 1. 业务处理层输入

这是 `scripts/crm_assistant.py process-transcript` 直接消费的输入：

- `transcript.txt`
- `context.json`

其中：

- `transcript.txt`：会议转录文本
- `context.json`：从 CRM、日历、会议元信息中补齐的业务上下文

建议字段：

- `customer_id`
- `customer_name`
- `company_name`
- `owner`
- `industry`
- `opportunity_id`
- `meeting_time`
- `next_meeting_time`
- `sales_region`
- `channel`

说明：

- `current_stage` 不建议出现在原始输入层
- 当前阶段应由会议文本分析后生成，而不是在源输入中提前给定

## 2. 飞书原始输入层

这是更接近真实飞书会议入口的数据层，推荐标准化为：

### `feishu_meeting_raw.json`

顶层建议字段：

- `source`
- `meeting`
- `participants`
- `transcript`
- `calendar`
- `crm_binding`

### meeting

- `meeting_id`
- `title`
- `start_time`
- `end_time`
- `host_user_id`
- `meeting_url`
- `calendar_event_id`

### participants

数组，每个元素可包含：

- `user_id`
- `name`
- `role`：`internal` / `external` / `guest` / `host`
- `company`
- `industry`

### transcript

两种方式至少提供一种：

- `full_text`
- `segments`

`segments` 元素建议包含：

- `speaker`
- `text`
- `start_ms`
- `end_ms`

### calendar

- `next_meeting_time`

### crm_binding

这是项目内部的“业务绑定补充层”，用于把飞书会议和 CRM 中的客户/商机关联起来。建议字段：

- `customer_id`
- `customer_name`
- `company_name`
- `owner`
- `industry`
- `opportunity_id`
- `sales_region`

说明：

- `crm_binding` 用于补充客户、公司、负责人、商机 ID 等“绑定信息”
- 不建议在这里直接给 `current_stage`
- 商机当前阶段应在后续处理环节中根据 transcript 推断

## 输入转换关系

项目中通过 `scripts/crm_assistant.py build-context-from-feishu` 完成以下转换：

```text
feishu_meeting_raw.json
  -> transcript.txt
  -> context.json
  -> process-transcript
```

这一步的意义是：

- 飞书提供会议事实和转录文本
- CRM / 多维表格提供客户和商机上下文
- 项目把两者合并成稳定的内部输入格式
