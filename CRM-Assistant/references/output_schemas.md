# 输出结构说明

主处理脚本会输出 8 份核心 JSON 产物。

## 1. `crm_packet.json`

这是总包文件，包含所有下游对象：
- `input`
- `meeting`
- `customer_profile_update`
- `opportunity_update`
- `follow_up_task`
- `pre_meeting_brief`
- `customer_table_row`
- `opportunity_snapshot_row`
- `feishu_bitable_payload`

## 2. `meeting_record.json`

会议维度输出，描述本次会议的结构化结果：
- `meeting_id`
- `customer_id`
- `customer_name`
- `company_name`
- `meeting_time`
- `summary`
- `discussion_points`
- `customer_needs`
- `customer_concerns`
- `next_actions`
- `commitments`

## 3. `customer_profile_update.json`

客户画像增量更新对象：
- `customer_id`
- `company_name`
- `industry`
- `mbti`
- `single_status`
- `resistance_level`
- `price_sensitivity`
- `risk_concerns`
- `communication_style`
- `profile_summary`

## 4. `opportunity_update.json`

商机评估结果：
- `opportunity_id`
- `opportunity_name`
- `opportunity_description`
- `sales_region`
- `business_value`
- `lead_score`
- `intent_level`
- `opportunity_stage`
- `high_value_flag`
- `recommended_action`
- `next_follow_up_at`
- `latest_progress`

## 5. `follow_up_task.json`

给销售负责人执行的跟进任务对象：
- `task_title`
- `owner`
- `due_at`
- `channel`
- `draft_message`
- `checklist`

## 6. `pre_meeting_brief.json`

会前简报对象。即使没有立刻触发提醒，也会先生成这个结构；如果 `next_meeting_at` 为空，则暂不执行提醒。
- `next_meeting_at`
- `trigger_at`
- `headline`
- `opening_script`
- `key_points`
- `watchouts`
- `materials_to_prepare`

## 7. `customer_table_row.json`

写入飞书“客户信息表”的单行数据对象，适合按 `客户ID` 做 upsert。

核心字段：
- `客户ID`
- `客户名称`
- `客户公司`
- `行业`
- `MBTI`
- `是否单身`
- `沟通风格`
- `成交阻力`
- `价格敏感程度`
- `风险顾虑`
- `客户画像摘要`
- `客户负责人`
- `最后更新时间`
- `数据来源`

## 8. `opportunity_snapshot_row.json`

写入飞书“商机推进快照表”的单行数据对象，适合每次会议结束后直接 append。

核心字段：
- `商机ID`
- `客户ID`
- `客户名称`
- `客户公司`
- `机会名称`
- `商机描述`
- `当前阶段`
- `Lead Score`
- `意向等级`
- `高净值优先`
- `销售区域`
- `业务价值`
- `推荐动作`
- `最新进展`
- `下次跟进时间`
- `最近会议时间`
- `商机负责人`
- `数据来源`

## `feishu_bitable_payload` 说明

该对象固定采用两表结构：

### `customer_table`
- `mode`: 固定为 `upsert`
- `key_field`: 固定为 `客户ID`
- `key`: 当前客户 ID
- `update_fields`: 对应 `customer_table_row.json`

### `opportunity_snapshot_table`
- `mode`: 固定为 `append`
- `append_row`: 对应 `opportunity_snapshot_row.json`

## 业务解释规则

- 所有数组字段都应理解为“增量证据集合”，而不是一次性最终结论。
- 客户信息表用于沉淀长期画像，原则上按客户维度更新。
- 商机推进快照表用于保留每次会议后的状态切片，原则上只新增，不覆盖历史。
- `high_value_flag` 主要用于优先级判断，不代表正式客户分层标签。
- `recommended_action` 应保持简短、明确、可执行。
- `opportunity_stage` 当前支持 6 个值：`初次接触`、`需求确认`、`方案沟通`、`推进中`、`待成交`、`已成交`。
- `已成交` 表示合同、金额、付款节点或成交结论已经锁定，后续重点从商务推进切换到启动与交付执行。
