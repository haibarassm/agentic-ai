# OpenClaw 自定义 Skill 开发指南

> **配套课程**：第 9 节 · SDL 语法精通与定制化业务 Skill 编写实战

## 什么是自定义 Skill？

OpenClaw 通过 **SKILL.md** 文件定义 Agent 的能力模块。每个 Skill 是一个独立的 Markdown 文件，包含结构化的 YAML Frontmatter（元数据）和自由格式的 Markdown Body（执行指令）。

Agent 读取 SKILL.md 后，就"学会"了一项新能力——无需写代码，无需部署服务。

## SKILL.md 文件结构

```
┌─────────────────────────────────┐
│  YAML Frontmatter (---)         │  ← 元数据：名称、描述、依赖声明
│  - name                         │
│  - description                  │
│  - metadata.openclaw.requires   │
├─────────────────────────────────┤
│  Markdown Body                  │  ← 执行指令：Agent 的操作手册
│  - 执行步骤                      │
│  - 异常处理规则                   │
│  - 输出格式定义                   │
│  - 停止条件                      │
└─────────────────────────────────┘
```

## Frontmatter 关键字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `name` | Skill 名称，用于 `/skills list` 和斜杠命令触发 | `crypto-monitor` |
| `description` | 功能描述，Agent 据此判断何时调用 | `定期巡检加密货币行情...` |
| `metadata.openclaw.requires.env` | 必需的环境变量 | `COINGECKO_API_KEY` |
| `metadata.openclaw.requires.bins` | 必需的 CLI 工具 | `curl`, `jq` |

## 关键开发规范

### 1. description 覆盖度

`description` 决定了自然语言能否触发 Skill。应覆盖：

- 核心功能关键词（如"行情"、"巡检"、"价格"）
- 用户可能的提问方式（如"帮我看一下 BTC"）
- 相关概念（如"加密货币"、"cryptocurrency"）

### 2. 环境变量隔离

敏感信息（API Key、Token）通过环境变量注入，不硬编码在 SKILL.md 中：

```yaml
metadata:
  openclaw:
    requires:
      env:
        - COINGECKO_API_KEY
```

配置路径：`~/.openclaw/.env`，权限设为 `600`。

### 3. 异常处理四要素

生产级 Skill 必须包含：

- **超时处理**：设置合理的请求超时时间
- **重试机制**：失败后等待后重试（如 10 秒后重试 1 次）
- **限流应对**：收到 429 时等待指定时间后重试（如 60 秒）
- **降级策略**：多次失败后的兜底处理（报告错误而非静默失败）

### 4. 停止条件与输出约定

- **HEARTBEAT_OK**：通用的"一切正常"信号——执行成功且无需告警时返回
- **行情摘要**：超过阈值时输出结构化的告警信息

## 定时调度：Cron 集成

通过 Cron 实现定时执行，一行配置即可：

```bash
# 每 4 小时巡检一次
0 */4 * * *  openclaw run crypto-monitor

# 常用频率参考
*/30 * * * *   # 每 30 分钟
0 */1 * * *    # 每小时
0 */4 * * *    # 每 4 小时（推荐）
0 9 * * *      # 每天早上 9 点
```

## 目录结构

```
openclaw-skills/
├── README.md                          # 本文件：SKILL.md 规范指南
├── lesson09-lab.md                    # 实操手册：端到端开发流程
├── templates/
│   └── SKILL.md.example               # 带注释的 SKILL.md 模板
└── examples/
    └── crypto-monitor/
        └── SKILL.md                   # 完整示例：加密货币行情巡检 Skill
```

## 快速开始

1. 复制 `templates/SKILL.md.example` 作为起点
2. 参考 `examples/crypto-monitor/SKILL.md` 了解完整写法
3. 按照 `lesson09-lab.md` 的步骤完成端到端实战

## 参考资源

- [课程主页](https://github.com/DjangoPeng/agentic-ai)
- [OpenClaw 官方文档](https://docs.openclaw.ai)
- [CoinGecko API 文档](https://docs.coingecko.com/reference/introduction)
