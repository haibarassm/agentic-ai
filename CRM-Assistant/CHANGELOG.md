# Changelog

### 飞书表名中文化与写表权限说明

- 飞书两张表名从英文改为中文：Customers → 客户信息，OpportunitySnapshots → 商机快照
- 第 6/7/8 步 prompt 明确要求使用用户权限（user identity）写表，避免应用权限 403
- 第 8 步标题改为"一键全链路"，去掉 ingest 术语，新增重复记录警告
- 常见问题速查新增 403 Forbidden 条目

### 环境变量配置统一

- 新增 `.env.example` 环境变量模板，与第 13/14 节格式统一（`cp .env.example .env.local`）
- 实验手册第 3 步从 `feishu_config.json` 改为 `.env.local`，部署步骤新增 `.env.local` 创建
- README 飞书配置章节新增 `.env.local` 作为推荐方式，保留 `feishu_config.json` 作为备选
- 验收清单和常见问题速查表统一引用 `.env.local` 变量名

### README.md — 全面重写

- 对齐第 15 节 PPT 文稿，以"四段式架构（接入→理解→判断→沉淀）"为主线重组全文
- 新增"与课程的关系"表格，突出三个核心留存物：四段式架构、Prompt+Schema+few-shot 三件套、历史强值保护
- 新增"8 类结构化产出""历史强值保护""多轮客户推进""飞书表字段"等独立章节
- 新增"完成标准"清单和"相关课程章节"前置/后续表
- 修复 CLI 参数错误：`--packet-path` → `--crm-packet-path`，`inspect-feishu-bitable --config-path` → `--app-id`/`--app-secret`/`--app-token-or-url`
- 修复 `run-customer-journey` 示例路径指向不存在的 `assets/samples/`

### lesson15-lab.md — 术语统一与结构补齐

- 标题对齐 PPT："让每一场高价值会议，自动沉淀为可经营的 CRM 资产"
- 引导语、部署步骤、项目路径、警告格式、前置条件统一为课程系列惯例
- 项目路径统一为 `~/projects/agentic-ai/CRM-Assistant`
- 第 5 步明确 `inspect-feishu-bitable` 需分别传参（不支持 `--config-path`）
- 第 6 步检查项修正：dry-run 输出为 `preview_only`，不区分 create/update
- 新增第 9 章"注册 Skill"（拉代码→复制目录→配置环境变量→验证生效）
- 验收清单补上 Skill 注册相关两项，常见问题速查表补上 Skill 相关两条
- 步骤名优化：配置飞书写表参数→配置环境，dry-run 写表验证→模拟写表验证，真实写入飞书→真实落表验证，一条命令完整链路→完整链路

### SKILL.md — 路径修复与迁移

- 从根目录迁移至 `skills/crm-assistant/SKILL.md`
- 修复不存在的路径引用：`assets/samples/`、`assets/expected/`、`references/openclaw_system_prompt.md`
- 子命令列表补齐 `inspect-feishu-bitable`、`sync-feishu-bitable`、`ingest-feishu-raw-to-bitable`

### scripts/crm_assistant.py — 代码修复

- 删除无效赋值：`opportunity_stage = "初次接触"` 在已等于该值时的 no-op 赋值
- 修正 `get_business_value` 正则匹配顺序：最精确 pattern 前置，避免宽泛 pattern 吞掉精确匹配

### references/user_side_feishu_prompt.md — 术语统一

- `业务价值`兜底值从 `null` 统一为 `"暂无明确业务价值"`，与其他 reference 文档对齐

### .gitignore — 安全加固

- 新增 `.venv/`、`venv/`：防止误提交虚拟环境
- 新增 `feishu_config.json`：防止泄露 `app_secret` 等飞书敏感信息
