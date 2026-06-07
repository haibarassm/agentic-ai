# 第 15 节 实验手册：CRM Assistant 会议商机推进与飞书落表

> 配套课程：AI 业务流架构师 · 第 15 节《CRM Assistant 会议商机推进与飞书落表》
> 预计耗时：45-75 分钟（含飞书多维表格创建与应用配置）
> 操作方式：全程在飞书 DM 里和龙虾对话完成，不需要自己登录服务器
> 前置条件：OpenClaw 已部署 + 龙虾可正常对话 + 飞书应用已具备多维表格权限

---

## 0. 开始前确认

| # | 物料 | 备注 |
|---|---|---|
| 1 | 龙虾可正常对话 | 飞书 DM 发一句话能回复 |
| 2 | 飞书开发者应用 | 有 App ID / App Secret，并已开通多维表格相关权限 |
| 3 | 飞书多维表格 | 可以新建，也可以沿用已有 CRM Demo Base |
| 4 | CRM-Assistant 仓库 | `https://github.com/lemons101/CRM-Assistant.git` |
| 5 | 一份飞书会议原始 JSON | 仓库自带 demo，不用自己准备 |

> 本手册里的“发给龙虾”尽量使用对话式指令。你只需要告诉龙虾目标、资料位置和希望它返回什么；具体命令由龙虾自己选择并执行。只有排障时，才需要让龙虾贴出失败命令和完整报错。

---

## 1. 创建飞书多维表格（发给龙虾）

复制下面文本框里的内容，直接发给龙虾：

```text
请帮我在飞书中创建一个用于 CRM Assistant Demo 的多维表格 Base。

要求：
1. 新建一个 Bitable
2. 创建两张表：Customers 和 OpportunitySnapshots
3. 字段名称必须和下面完全一致，先全部按文本字段创建；Lead Score 可用数字字段，高净值优先可用复选框字段，时间字段可用日期时间字段

Customers 字段：
客户ID、客户名称、客户公司、行业、MBTI、是否单身、沟通风格、成交阻力、价格敏感程度、风险顾虑、客户画像摘要、客户负责人、最后更新时间、数据来源

OpportunitySnapshots 字段：
商机ID、客户ID、客户名称、客户公司、机会名称、商机描述、当前阶段、Lead Score、意向等级、高净值优先、销售区域、业务价值、推荐动作、最新进展、下次跟进时间、最近会议时间、商机负责人、数据来源

创建完成后请给我：
1. Base 链接
2. app_token
3. Customers 的 table_id
4. OpportunitySnapshots 的 table_id
```

龙虾会返回 `app_token` 和两张表的 `table_id`，先记下来，后面配置会用到。

---

## 2. 部署项目（发给龙虾）

复制下面文本框里的内容，直接发给龙虾：

```text
请帮我部署并验证 CRM-Assistant。

仓库地址：
https://github.com/lemons101/CRM-Assistant.git

部署目录：
/root/projects/CRM-Assistant

请你自动完成项目初始化：如果目录已存在就拉取最新代码；如果不存在就克隆仓库。然后在项目目录下新建一个名为 .venv 的 Python 虚拟环境，并在这个 .venv 里安装依赖。不要直接使用系统 Python 环境；如果 .venv 已经存在，请先确认它可用，再继续复用。最后确认 CRM-Assistant 的命令行入口可以正常打开帮助信息。

完成后告诉我：
1. git pull 或 git clone 是否成功
2. .venv 虚拟环境是否已新建或确认可用
3. 依赖是否已经安装在 .venv 里
4. CRM-Assistant 的帮助信息是否能正常输出
```

龙虾完成后你会收到部署确认。

---

## 3. 配置飞书写表参数（发给龙虾）

> **发送前先自己填好真实值，不要把占位符发出去。**
> - `FEISHU_APP_ID` / `FEISHU_APP_SECRET`：飞书开放平台 -> 应用详情页获取
> - `FEISHU_BITABLE_APP_TOKEN`：第 1 步龙虾返回的 `app_token`
> - `FEISHU_CUSTOMER_TABLE_ID`：Customers 的 `table_id`
> - `FEISHU_OPPORTUNITY_TABLE_ID`：OpportunitySnapshots 的 `table_id`

把真实值替换进去，复制下面文本框里的内容，直接发给龙虾：

```text
请在 /root/projects/CRM-Assistant/feishu_config.json 写入下面的配置：

app_id：cli_xxxxxxxx
app_secret：xxxxxxxx
app_token：xxxxxxxx
customer_table_id：tblxxxxxxxx
opportunity_snapshot_table_id：tblxxxxxxxx

写入后请确认：
1. 文件路径是 /root/projects/CRM-Assistant/feishu_config.json
2. JSON 格式合法
3. app_id、app_secret、app_token、customer_table_id、opportunity_snapshot_table_id 都不是空值
4. 没有把 cli_xxxxxxxx 或 xxxxxxxx 这样的占位符原样写进去
```

---

## 4. 本地样本验证（发给龙虾）

先跑一遍不接飞书的本地链路，确认 CRM 结构化结果可以生成：

复制下面文本框里的内容，直接发给龙虾：

```text
请用 CRM-Assistant 项目跑一次本地样本验证。

请使用仓库自带的样本 assets/feishu_raw/pingan_longxiahezi_need_confirmation.json，先把飞书原始数据整理成 context 和 transcript，再继续生成 CRM 结构化结果。

这一步只做本地处理，不要写入飞书。输出目录请放在 runtime/lab15_probe/ 下面，方便后续继续使用。

执行完后告诉我：
1. 是否生成 context.json 和 transcript.txt
2. 是否生成 crm_packet.json
3. 是否生成 customer_table_row.json 和 opportunity_snapshot_row.json
4. 当前商机阶段、Lead Score、意向等级、推荐动作分别是什么
```

> 注意：这一步只验证本地结构化处理，不会真实写入飞书。

---

## 5. 检查飞书表结构（发给龙虾）

复制下面文本框里的内容，直接发给龙虾：

```text
请用 CRM-Assistant 检查飞书多维表格结构。

请使用我已经配置好的飞书 App ID、App Secret、app_token，以及 Customers 和 OpportunitySnapshots 的 table_id，检查两张表的字段是否和实验手册一致。

检查结果请保存到 runtime/lab15_feishu/ 下面，分别保存 Customers 和 OpportunitySnapshots 的检查结果。

完成后告诉我：
1. 是否能拿到 tenant_access_token
2. 是否能列出两张表
3. Customers 字段是否完整
4. OpportunitySnapshots 字段是否完整
5. 如果字段缺失，请列出缺失字段
```

如果这里失败，先不要继续写表，优先检查 App ID / App Secret、应用权限、Base 链接和 table_id。

---

## 6. dry-run 写表验证（发给龙虾）

dry-run 会生成写表计划，但不会真实写入飞书。

复制下面文本框里的内容，直接发给龙虾：

```text
请用 CRM-Assistant 做一次飞书写表 dry-run。

请使用第 4 步生成的 crm_packet.json 和第 3 步配置好的 feishu_config.json。这一步只生成写表计划，不要真实写入飞书。输出结果请保存到 runtime/lab15_feishu/dry_run。

执行完后告诉我：
1. feishu_sync_result.json 是否已生成
2. dry_run 是否为 true
3. customer_action 是 create 还是 update
4. opportunity_action 是 create 还是 skipped
5. 待写入的客户名称、当前阶段、Lead Score、推荐动作分别是什么
```

> 注意：看到 `feishu_sync_result.json` 不代表已经写入飞书。只有去掉 `--dry-run` 后才会真实写入。

---

## 7. 真实写入飞书（发给龙虾）

确认第 5 步表结构正确、第 6 步 dry-run 正常后，再执行真实写入：

复制下面文本框里的内容，直接发给龙虾：

```text
请用 CRM-Assistant 把本次 CRM 结果真实写入飞书多维表格。

请使用第 4 步生成的 crm_packet.json 和第 3 步配置好的 feishu_config.json。这一次请真实写入飞书：Customers 表按客户 ID 新增或更新，OpportunitySnapshots 表追加一条商机推进快照。输出结果请保存到 runtime/lab15_feishu/write_once。

执行完成后，用中文返回：
1. 是否写入成功
2. Customers 是新增还是更新
3. OpportunitySnapshots 是否追加成功
4. 本次写入的客户名称、当前阶段、Lead Score、意向等级、推荐动作
5. 如果失败，返回失败命令和完整报错
```

写入成功后，打开飞书多维表格确认两张表里都有记录。

---

## 8. 一条命令完整链路（可选）

如果你想从飞书原始 JSON 直接跑到落表，可以让龙虾执行：

复制下面文本框里的内容，直接发给龙虾：

```text
请用 CRM-Assistant 跑完整 ingest 链路：从飞书原始 JSON 生成 CRM 结果，并写入飞书多维表格。

请使用样本 assets/feishu_raw/pingan_longxiahezi_need_confirmation.json 和配置文件 feishu_config.json，一次性完成：提取 context、生成 transcript、生成 CRM 结果、写入飞书两张表。输出目录请放到 runtime/lab15_ingest/pingan_need_confirmation。

完成后告诉我：
1. build_result_path 是否生成
2. crm_packet_path 是否生成
3. sync_result_path 是否生成
4. Customers 是新增还是更新
5. OpportunitySnapshots 是否追加成功
```

这一步等价于：

```text
feishu_raw.json
  -> build-context-from-feishu
  -> process-transcript
  -> sync-feishu-bitable
```

---

## 9. 验收检查清单

- [ ] 龙虾部署 CRM-Assistant 成功
- [ ] `python scripts/crm_assistant.py --help` 能正常输出
- [ ] 飞书 Base 已创建，包含 Customers 和 OpportunitySnapshots 两张表
- [ ] `feishu_config.json` 已配置真实 App ID / App Secret / app_token / table_id
- [ ] 本地样本生成 `context.json`、`transcript.txt`、`crm_packet.json`
- [ ] 本地样本生成 `customer_table_row.json` 和 `opportunity_snapshot_row.json`
- [ ] `inspect-feishu-bitable` 能读到两张表字段
- [ ] `sync-feishu-bitable --dry-run` 生成写表计划但不真实写入
- [ ] 去掉 `--dry-run` 后真实写入成功
- [ ] 飞书 Customers 表能看到客户画像记录
- [ ] 飞书 OpportunitySnapshots 表能看到商机推进快照记录

---

## 10. 常见问题速查

| 龙虾报的错 | 原因 | 你发什么 |
|---|---|---|
| `Missing Feishu app token` | 没传 app_token 或配置文件字段名不对 | 「请检查 feishu_config.json 里是否有 app_token」 |
| `Missing customer table id` | Customers 表 ID 缺失 | 「请把 Customers 的 table_id 写入 customer_table_id」 |
| `Missing opportunity table id` | OpportunitySnapshots 表 ID 缺失 | 「请把 OpportunitySnapshots 的 table_id 写入 opportunity_snapshot_table_id」 |
| `tenant_access_token missing` | App ID / App Secret 错误或应用未发布 | 「请重新核对飞书应用的 App ID / App Secret」 |
| `Feishu API failed` | 权限、表 ID 或字段类型不匹配 | 「请返回完整报错，并重新执行 inspect-feishu-bitable」 |
| 字段缺失 | 建表时字段名和脚本字段不一致 | 「请按实验手册第 1 步补齐缺失字段，字段名保持完全一致」 |
| 只生成 JSON 没写表 | 跑的是本地处理命令或带了 `--dry-run` | 「请确认执行的是 sync-feishu-bitable 且没有 --dry-run」 |
| Customers 被覆盖了旧画像 | 当前输入有弱值或历史值保护未生效 | 「请返回 crm_packet.json 和 feishu_sync_result.json 里 customer_table_row 的内容」 |

---

## 11. 一句话讲法

这节课就一条链路：

```text
先让龙虾建 CRM 飞书表
再让龙虾部署 CRM-Assistant
最后由 CRM-Assistant 把会议结果写进 Customers 和 OpportunitySnapshots
```

---

## 实验记录

请记录你在实验过程中遇到的任何与预期不符的情况：

| # | 发生在哪一步 | 预期行为 | 实际行为 | 你的解决方法 |
|---|------------|----------|---------|------------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

> 欢迎把你的实验记录和踩坑发现分享到课程社群。
