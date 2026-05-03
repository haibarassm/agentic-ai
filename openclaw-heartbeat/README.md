# ⏱ openclaw-heartbeat — 心跳与定时任务

> Cron vs Heartbeat 选型 + HEARTBEAT.md 设计方法论

## 这是什么

OpenClaw 提供两种自动化机制让 Agent 在你不说话时也能主动工作：

- **Cron Task**：在精确时间点执行预设任务——定时闹钟，到点就响
- **Heartbeat**：按固定间隔唤醒 Agent，读取检查清单后自主决策——巡逻保安，没事就静默

两者的核心区别：Cron 每次都有输出，Heartbeat 无事发生时自动静默（HEARTBEAT_OK 被 Gateway 拦截，用户零打扰）。

## 什么时候用哪个

| 场景 | 选择 | 理由 |
|------|------|------|
| 每天 7:00 生成晨间简报 | Cron | 需要精确时间 |
| 每 30 分钟检查邮件+日历+服务器 | Heartbeat | 多项检查合并，正常时静默 |
| 20 分钟后提醒我开会 | Cron (`--at`) | 一次性提醒 |
| 检查日报文件是否生成 | Heartbeat | 条件判断，正常时不打扰 |
| Cron 抓数据 + Heartbeat 查质量 | 组合使用 | 最常用的生产模式 |

**选型口诀**：心跳看状态，Cron 干活。

**成本提示**：5 个同频率监控任务，用 5 个 Cron = 5 次 Agent turn，用 1 个 Heartbeat = 1 次 turn，Token 成本差 5 倍。

## HEARTBEAT.md 四条黄金法则

| 法则 | 说明 |
|------|------|
| 精简至上 | 控制在 200 tokens 以内，每条检查项一两行 |
| 阈值明确 | 用可量化条件（">85%""文件不存在"），不用模糊描述 |
| 必须有停止条件 | 最后写"以上均无异常时，回复 HEARTBEAT_OK" |
| 设定时段窗口 | 每个检查项标注适用时段，避免凌晨 3 点推送告警 |

## openclaw.json 日常三件套

```json
{
  "heartbeat": {
    "every": "30m",
    "target": "last",
    "activeHours": { "start": "07:00", "end": "23:00" }
  }
}
```

| 配置项 | 说明 |
|--------|------|
| `every` | 心跳间隔，`"0m"` = 禁用 |
| `target` | 消息投递目标，`"last"` = 最近联系的渠道 |
| `activeHours` | 活跃时段窗口（本地时区） |

## 文件说明

```
openclaw-heartbeat/
├── README.md                              # 本文件
├── lesson06-lab.md                        # 实验手册（可直接跟着操作）
├── templates/
│   └── HEARTBEAT.md.example               # 通用模板（带注释）
└── examples/
    ├── morning-briefing-heartbeat.md       # 多轮资讯日报巡检配置
    └── memory-guardian-heartbeat.md        # 记忆守护巡检配置（含资讯巡检）
```

## 快速使用

在微信/飞书中告诉 Agent：
```
请把你的 HEARTBEAT.md 文件替换为以下内容……
```

或者复制模板后手动编辑：
```bash
cp templates/HEARTBEAT.md.example ~/.openclaw/workspace/HEARTBEAT.md
```

## 配套课程

本目录对应课程第6节《Heartbeat 心跳机制：打破被动响应的主动唤醒引擎》。
