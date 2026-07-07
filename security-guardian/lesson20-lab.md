# 第 20 节 实验手册：Security Guardian 云端 OpenClaw 安全自审计

> 配套课程：AI 业务流架构师 · 第 20 节《企业级数字员工的安全审计与生产治理》
> 预计耗时：40-60 分钟
> 操作方式：全程发给云端 OpenClaw / 龙虾执行
> 前置条件：OpenClaw 已部署 + Claude Code CLI 可用 + 8511 端口可访问

---

## 0. 开始前确认

| # | 物料 | 备注 |
|---|---|---|
| 1 | 云端 OpenClaw / 龙虾 | 能执行部署和本机 `curl` |
| 2 | Claude Code CLI | `claude -p "请只回复 ok"` 能返回 |
| 3 | OpenClaw 真实目录 | 推荐 `/root/.openclaw` |
| 4 | 课程仓库 | `https://github.com/DjangoPeng/agentic-ai.git`（项目在 `security-guardian/` 子目录） |
| 5 | 访问端口 | 固定 `8511` |

> 本实验只做真实检测和建议输出，不自动修改 OpenClaw 生产配置。

## 实验链路

```text
OpenClaw 真实日志 / 配置 / Skill 记录
  -> Security Guardian 创建本次 audit run 工作区
  -> 复制允许审计的 evidence：先脱敏、再生成 manifest.json
  -> Claude Code CLI 在工作区内自行检索证据并从 stdout 返回 JSON
  -> Claude 输出每条风险的结论、具体处置步骤和复核办法
  -> Security Guardian 负责整理展示；Claude 没给够时再用固定建议兜底
  -> 页面展示风险、告警建议、治理建议、最终复检
```

关键边界：

- Claude Code 必须真实调用成功
- `OPENCLAW_ROOT` 必须指向真实 OpenClaw
- 页面里的勾表示“报告或建议已生成”，不表示生产已经治理

## 1. 部署项目（发给龙虾）

```text
请帮我部署 Security Guardian。

课程仓库地址（项目在 security-guardian/ 子目录）：
https://github.com/DjangoPeng/agentic-ai.git

克隆目录：
/root/projects/agentic-ai

请完成：
1. 如果 /root/projects/agentic-ai 不存在就 clone；已存在就在该目录 git pull
2. 项目目录是 /root/projects/agentic-ai/security-guardian
3. 确认该子目录下 README.md、run_dashboard.sh、openclaw_security_console/app.py 都存在

完成后告诉我：
1. clone / pull 是否成功
2. 当前 commit hash
3. 项目目录 /root/projects/agentic-ai/security-guardian 是否正确
```

---

## 2. 检查 Claude Code（发给龙虾）

```text
请检查 Claude Code CLI 是否可用。

执行：
claude -p "请只回复 ok"

要求：
1. 如果返回 ok，继续
2. 如果命令不存在、未登录或报错，请停止并返回完整错误
3. 不要伪造 Claude 调用成功

完成后告诉我：
1. Claude Code CLI 是否可用
2. 测试命令返回内容
```

如果云端不是 `claude -p`，先设置：

```bash
export CLAUDE_CODE_COMMAND="你的 Claude Code 非交互调用命令，例如 claude -p"
```
---

## 3. 启动服务（发给龙虾）

发送前把 `OPENCLAW_ROOT` 替换为第 4 步真实路径。

```text
请启动 Security Guardian。

执行（后台常驻，别让服务占住当前会话）：
cd /root/projects/agentic-ai/security-guardian
chmod +x run_dashboard.sh
OPENCLAW_ROOT=/root/.openclaw CLAUDE_CODE_TIMEOUT=300 nohup ./run_dashboard.sh > /tmp/sg-8511.log 2>&1 &
sleep 2 && curl -s http://127.0.0.1:8511/api/status >/dev/null && echo "面板已就绪：监听 0.0.0.0:8511"
echo "面板地址：http://$(curl -4 -s --max-time 5 ifconfig.me || curl -4 -s --max-time 5 ipinfo.io/ip):8511/dashboard.html"

要求：
1. 服务监听 0.0.0.0:8511
2. 如果 8511 被占用，请停止并报告
3. 不要停止已有 OpenClaw 生产服务

完成后告诉我：
1. 服务是否启动成功
2. 是否监听 0.0.0.0:8511
3. OPENCLAW_ROOT 实际值
4. CLAUDE_CODE_TIMEOUT 实际值是否为 300
5. 是否自动纳入 /tmp/openclaw 等额外审计目录
6. 上一步输出的「面板地址」（用本机公网 IP 拼好的 http://<公网IP>:8511/dashboard.html）
```

---

## 4. 执行真实检测（发给龙虾）

```text
请执行 Security Guardian 真实检测，并调用 Claude Code 审计。

执行：
curl -X POST http://127.0.0.1:8511/claude-code/analyze-cloud

完成后检查：
1. Claude 调用是否成功
2. OPENCLAW_ROOT 是否正确
3. 扫描文件数是否大于 0
4. 是否生成 runtime/audit_runs/<run_id>/manifest.json
5. 是否生成 runtime/audit_runs/<run_id>/evidence/
6. 是否生成 runtime/audit_runs/<run_id>/audit_request.md
7. Security Guardian 是否根据 Claude stdout 生成 runtime/audit_runs/<run_id>/report.json 和 report.md
8. manifest.json 的 evidenceFiles 是否标记 redacted: true
9. report.json 的 findings 是否包含 recommendation、remediationSteps、verification
10. 是否出现 CC-CALL-FAILED
11. 是否出现 audit already running；如果出现，说明已有检测在运行，请等待完成后重试

完成后告诉我：
1. Claude Code 是否调用成功
2. 扫描文件数
3. 风险发现总数
4. high / critical 风险数量
5. 本次 run_id
6. manifest、evidence、report.json 路径
```

> 如果出现 `CC-CALL-FAILED`，先修 Claude 调用链路，不要继续解释审计结论。

补充验证：不要用“写 test_report.json”判断 Claude 是否可用，因为某些 Claude Code 权限策略允许读取和回复，但不允许直接写文件。更接近本实验的验证方式是：

```bash
cd /root/projects/agentic-ai/security-guardian/openclaw_security_console/runtime/audit_runs/<run_id>
claude -p '请读取 manifest.json，只输出其中 runId，不要输出其他内容'
```

如果能输出本次 run_id，说明 Claude 可以进入工作区读取 evidence；真实检测只要求 Claude stdout 返回 JSON，报告文件由 Security Guardian 写入。

---

## 5. 生成建议（发给龙虾）

```text
请按顺序生成 Security Guardian 建议。

依次执行：
curl -X POST http://127.0.0.1:8511/claude-code/enable-monitoring
curl -X POST http://127.0.0.1:8511/guardian/seal-control-plane
curl -X POST http://127.0.0.1:8511/guardian/isolate-skill
curl -X POST http://127.0.0.1:8511/guardian/rotate-secrets
curl -X POST http://127.0.0.1:8511/guardian/apply-governance

注意：
这些接口只生成告警规则建议、控制面建议、Skill 建议、密钥建议和治理策略建议。
如果 Claude 已经对某条风险给出 remediationSteps / verification，Security Guardian 会优先整理这些针对性建议；如果 Claude 没给够，再使用固定治理清单兜底。
不要自动修改 OpenClaw 生产配置。

完成后告诉我：
1. 生成了哪些建议
2. 建议分别对应哪些风险
3. 是否有 high / critical 风险需要人工处理
```

---

## 6. 最终复检（发给龙虾）

```text
请执行最终复检。

执行：
curl -X POST http://127.0.0.1:8511/guardian/final-audit

复检规则：
1. Claude 调用失败：不能通过
2. OPENCLAW_ROOT 未定位：审计范围不足
3. 扫描文件数为 0：审计范围不足
4. 存在 critical / high 风险：暂缓上线
5. 只剩 medium 风险：进入人工复核

完成后告诉我：
1. 最终复检结论
2. critical / high / medium 风险数量
3. 是否允许进入上线前人工复核
4. 页面访问链接
```

---

## 7. 查看页面

打开（下面命令用本机公网 IP 直接拼好地址，复制即用）：

```bash
echo "http://$(curl -4 -s --max-time 5 ifconfig.me || curl -4 -s --max-time 5 ipinfo.io/ip):8511/dashboard.html"
```

> 取不到公网 IP 就用云控制台上的公网 IP 手动拼 `http://<公网IP>:8511/dashboard.html`；确认安全组已放行 8511 入站。

重点看：

| 区域 | 看什么 |
|---|---|
| 云端 OpenClaw 状态 | 审计运行状态、Claude 调用、OPENCLAW_ROOT、扫描文件数 |
| Claude Code 风险发现 | 风险等级、位置、证据、建议、具体处置、复核办法 |
| 告警规则 | high / critical 是否转成告警建议 |
| 建议治理动作 | 控制面、Skill、密钥、治理策略 |
| 最终复检 | 是否还有上线阻断项 |

生成文件：

```text
openclaw_security_console/runtime/audit_runs/<run_id>/manifest.json
openclaw_security_console/runtime/audit_runs/<run_id>/evidence/
openclaw_security_console/runtime/audit_runs/<run_id>/audit_request.md
openclaw_security_console/runtime/audit_runs/<run_id>/report.md
openclaw_security_console/runtime/audit_runs/<run_id>/report.json
```

说明：`audit_request.md` 只是短任务说明，证据在 `evidence/` 和 `manifest.json` 中；写入 `evidence/` 前会先做文本脱敏，Claude Code 会在该 run 目录内自行检索这些已脱敏证据，并在 stdout 返回 JSON。`report.json` 和 `report.md` 由 Security Guardian 写入，其中会保留 Claude 给出的 `recommendation`、`remediationSteps` 和 `verification`。
---

## 8. 验收检查清单

- [ ] Security Guardian 已部署到 `/root/projects/agentic-ai/security-guardian`
- [ ] Claude Code CLI 可用
- [ ] `OPENCLAW_ROOT` 指向真实 OpenClaw
- [ ] 服务监听 `0.0.0.0:8511`
- [ ] 页面可以访问
- [ ] Claude 调用成功
- [ ] 扫描文件数大于 0
- [ ] manifest、已脱敏 evidence、audit_request、Markdown 报告、JSON 报告均已生成
- [ ] 页面显示风险发现
- [ ] 页面显示 Claude 针对性处置 / 复核建议，或显示 Security Guardian 兜底建议
- [ ] 页面显示最终复检结论
- [ ] 没有把“建议已生成”说成“生产已治理”

---

## 9. 常见问题速查

| 现象 | 原因 | 你发什么 |
|---|---|---|
| `CC-CALL-FAILED` | Claude CLI 不可用、超时或 stdout 没有返回 JSON | 「请执行 `claude -p "请只回复 ok"`，再在 audit_runs/<run_id> 中执行 `claude -p "请读取 manifest.json，只输出其中 runId"`」 |
| Claude 调用失败 | 命令不匹配 | 「请设置正确的 `CLAUDE_CODE_COMMAND`」 |
| `OPENCLAW_ROOT` 待检测 | 路径没设置或设置错 | 「请重新定位真实 OpenClaw 目录」 |
| 扫描文件数为 0 | 指到了空目录或日志不在范围内 | 「请列出 OPENCLAW_ROOT 下的日志和配置文件」 |
| 扫描文件太多或 evidence 过宽 | 审计目录过宽、历史 session 太多 | 「请调低 OPENCLAW_MAX_AUDIT_FILES 和 OPENCLAW_MAX_FILES_PER_ROOT，并缩窄 OPENCLAW_AUDIT_PATHS」 |
| 担心 evidence 含敏感值 | 当前 evidence 写入前会脱敏，manifest 会记录 redacted: true | 「请抽查 evidence 文件和 manifest.json 的 evidenceFiles」 |
| `audit already running` | 已有 Claude Code 审计任务在运行，系统已阻止并发启动 | 「请等待当前检测完成后再重新执行 /claude-code/analyze-cloud」 |
| 页面打不开 | 8511 未监听或安全组未放行 | 「请检查 8511 监听和云安全组」 |
| 页面有建议但没修复 | 正常，本项目只生成建议 | 「请不要声称已治理，除非真实修改并复核」 |
| 建议看起来像模板 | Claude 本次没有返回足够具体的 remediationSteps / verification，Security Guardian 使用兜底清单 | 「请查看 report.json 中该 finding 是否包含 remediationSteps 和 verification」 |

---

## 10. 本节课带走什么

- 会让 OpenClaw 收集真实审计材料，并生成已脱敏的受控 evidence 工作区
- 会让 Claude Code 自行检索 evidence、stdout 返回 JSON，再由 Security Guardian 生成结构化安全报告
- 会让 Claude 输出针对证据的处置步骤和复核办法，Security Guardian 只负责整理和兜底
- 会区分“建议已生成”和“生产已治理”
- 会用证据决定是否暂缓上线
