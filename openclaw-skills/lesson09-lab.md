# 第 9 节 · 实操手册：从零开发加密货币行情巡检 Skill

> **目标**：完成 crypto-monitor Skill 的全流程开发——从 API 注册到 Cron 定时巡检  
> **预计耗时**：30-45 分钟  
> **前置条件**：已完成第 2 节的服务器部署 + Tailscale SSH，第 4 节的飞书集成

---

## 实操流程概览

```
Step 1  注册 CoinGecko API Key
  ↓
Step 2  配置环境变量 + 验证 API 连通性
  ↓
Step 3  创建 crypto-monitor Skill
  ↓
Step 4  手动触发测试
  ↓
Step 5  接入 Cron 定时巡检
  ↓
Step 6  验证 + 恢复生产配置
```

---

## Step 1 · 注册 CoinGecko API Key

### 操作

1. 打开 [CoinGecko Developer Dashboard](https://www.coingecko.com/en/developers/dashboard)
2. 注册账号（邮箱即可，无需信用卡）
3. 登录后在 Developer Dashboard 中创建 API Key（格式：`CG-xxxxxxxxxxxxxxxxxxxx`）
4. 参考：[CoinGecko API Key 申请指南](https://support.coingecko.com/hc/en-us/articles/21880397454233)

### 验证清单

- [ ] 拿到 `CG-` 开头的 API Key
- [ ] Demo 计划显示 30 calls/min, 10,000 calls/month

> **提示**：Demo Key 注册后立即可用，无需等待审批。

---

## Step 2 · 配置环境变量 + 验证 API

### 2.1 写入环境变量

在飞书 DM 中发送：

```
请把以下环境变量写入 OpenClaw 全局配置文件 ~/.openclaw/.env，并设置文件权限为 600：
COINGECKO_API_KEY=CG-你的实际Key
MONITOR_THRESHOLD_PERCENT=3
```

> 如果 Agent 询问用途，回复"后续自定义 Skill 会用到"。

### 2.2 验证 API 可用性

在飞书 DM 中发送：

```
帮我用刚配置的 CoinGecko API Key 测试一下，获取 BTC、ETH、LTC 的实时价格
```

### 预期返回

Agent 应返回三个币种的 USD/CNY 价格和 24h 涨跌幅，例如：

- BTC：$103,200（+0.8%）
- ETH：$2,650（-4.1%）
- LTC：$87（+1.2%）

### 验证清单

- [ ] Agent 返回包含 bitcoin、ethereum、litecoin 三个币种
- [ ] 每个币种有 USD、CNY 价格和 24h 涨跌幅
- [ ] 数据合理（BTC 当前价格量级、涨跌幅在正常范围内）

### 常见问题

| 问题 | 排查 |
|------|------|
| Agent 报 "API Key 为空" | 让 Agent 重新配置环境变量，确认 Key 完整 |
| Agent 报 "限流" | 等 60 秒重试，或确认 Key 是否为 Demo 计划 |
| Agent 报 "无法连接" | 检查服务器网络是否能访问 api.coingecko.com |

---

## Step 3 · 创建 crypto-monitor Skill

### 操作

在飞书 DM 中发送：

```
请帮我创建一个名为 crypto-monitor 的自定义 Skill，功能是定期巡检加密货币行情。

具体需求：
1. 通过 CoinGecko API 获取 BTC、ETH、LTC 的 USD 和 CNY 价格及 24h 涨跌幅
2. 涨跌幅绝对值超过阈值（环境变量 MONITOR_THRESHOLD_PERCENT，默认 3%）时输出行情摘要
3. 全部在阈值内时回复 HEARTBEAT_OK
4. API 调用失败时等待 10 秒重试一次，仍失败则报告错误
5. 返回 429 限流时等待 60 秒后重试

需要的环境变量：
- COINGECKO_API_KEY（必须）
- MONITOR_THRESHOLD_PERCENT（可选，默认 3）

需要的 CLI 工具：curl、jq
```

等 Agent 创建完成后，发送：

```
请展示 crypto-monitor 的 SKILL.md 完整内容
```

### 逐项检查

- [ ] **Frontmatter** 包含 `name: crypto-monitor`
- [ ] **description** 包含功能描述（定期巡检、行情摘要、HEARTBEAT_OK 等关键词）
- [ ] **metadata.openclaw.requires.env** 包含 `COINGECKO_API_KEY`
- [ ] **metadata.openclaw.requires.bins** 包含 `curl` 和 `jq`
- [ ] **Markdown Body** 中的 curl 命令使用了 `x_cg_demo_api_key` 参数
- [ ] **异常处理** 包含 429 限流等待逻辑
- [ ] **停止条件** 包含 `HEARTBEAT_OK`

### 如果生成不完整

在飞书中要求修改：

```
请修改 crypto-monitor Skill：
1. 补充 429 限流的等待逻辑（等待 60 秒后重试）
2. 补充停止条件：全部在阈值内时回复 HEARTBEAT_OK
3. 确保 curl 命令使用 x_cg_demo_api_key 参数认证
```

---

## Step 4 · 手动触发测试

### 操作

先确认 Skill 已注册：

```
/skills list
```

确认 `crypto-monitor` 出现在列表中后，用斜杠命令触发：

```
/crypto-monitor
```

等待返回结果后，再用自然语言触发：

```
帮我看一下现在 BTC 和 ETH 的行情
```

### 验证清单

- [ ] `/skills list` 包含 crypto-monitor
- [ ] `/crypto-monitor` 返回三个币种的实时价格（USD + CNY）和 24h 涨跌幅
- [ ] 自然语言触发也能正确调用 Skill
- [ ] 输出格式与 SKILL.md 定义一致
- [ ] 如果有币种涨跌幅超过 3%，显示行情摘要
- [ ] 如果全部在阈值内，显示 HEARTBEAT_OK 或正常状态

### 常见问题

| 问题 | 排查 |
|------|------|
| Agent 不识别 `/crypto-monitor` | `/skills list` 确认注册；检查 SKILL.md 的 name 字段 |
| 返回 "API Key 为空" | SSH 检查 `~/.openclaw/.env` 内容和权限；重启 Agent |
| 返回 401 | Key 无效，重新检查 CoinGecko Dashboard |
| 自然语言不触发 | description 覆盖不够，用斜杠命令兜底 |

---

## Step 5 · 接入 Cron 定时巡检

### 操作

在飞书 DM 中发送：

```
请帮我创建一个 cron 定时任务：
- 任务名称：crypto-check
- 执行频率：每 2 分钟（测试用）
- 执行内容：调用 crypto-monitor Skill，巡检加密货币行情，超阈值推送飞书摘要，全部正常回复 HEARTBEAT_OK
```

> **提示**：先用每 2 分钟间隔测试，验证通过后再改为正式频率。

### 验证

让 Agent 展示 cron 配置：

```
请展示当前的 crontab 内容
```

- [ ] crontab 中包含 `crypto-check` 相关任务
- [ ] 执行频率为每 2 分钟（`*/2 * * * *`）
- [ ] 执行命令正确调用 crypto-monitor Skill

### 等待定时触发

等待 2-3 分钟，观察飞书是否收到：

- **有超阈值币种**：格式化的行情摘要（币种 + 价格 + 涨跌幅 + 阈值）
- **全部正常**：HEARTBEAT_OK 或静默无消息

> **技巧**：如果当前市场波动不大（全部在 3% 以内），临时调低阈值触发摘要输出：
> ```
> 请把 crypto-monitor 的 MONITOR_THRESHOLD_PERCENT 改为 0.5
> ```
> 截图后记得改回 3。

---

## Step 6 · 恢复生产配置

测试验证完成后，把临时配置改回正式值。

在飞书 DM 中发送：

```
请把 crypto-check 的 cron 定时任务频率改为每 4 小时执行一次
```

如果之前改过阈值：

```
请把 crypto-monitor 的 MONITOR_THRESHOLD_PERCENT 改回 3
```

### 验证清单

- [ ] Cron 频率已改为每 4 小时（`0 */4 * * *`）
- [ ] 阈值恢复为 3%

---

## 常见问题速查

| 问题 | 原因 | 解决 |
|------|------|------|
| CoinGecko 注册页面打不开 | 网络问题 | 使用 VPN 或直接访问 api 页面注册 |
| API 返回空或超时 | 服务器无法访问外网 | 检查防火墙规则，确认 443 端口开放 |
| Agent 创建的 SKILL.md 质量差 | 指令不够具体 | 用 Step 3 中的完整指令重新创建 |
| Cron 不触发 | Agent 进程可能需要重启 | `systemctl restart openclaw` 或重启进程 |
| 环境变量改了不生效 | Agent 缓存了旧环境 | 重启 Agent 进程后生效 |
| crontab 语法错误 | Agent 生成的 cron 表达式不对 | 让 Agent 展示 crontab 内容，手动确认格式 |

---

## 课后作业

### 作业一（必做）：完成 crypto-monitor Skill 全流程

按本手册 Step 1-6 完成端到端实战：注册 CoinGecko → 配置环境变量 → 创建 Skill → 手动触发 → 接入 Cron 定时。在飞书群分享巡检消息截图。

### 作业二（必做）：按 SKILL.md 规范优化你的 Skill

对照课程中讲解的规范逐项检查并优化：description 覆盖度、requires 依赖声明、异常处理四要素、自诊断规则。提交优化前后的 SKILL.md 对比。

### 作业三（选做）：创建一个全新的自定义 Skill

选择你的真实需求（汇率监控 / 竞品检测 / GitHub Star 追踪），必须包含完整 Frontmatter + 异常处理 + Cron 定时。
