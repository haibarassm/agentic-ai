# 第12节 实验手册：云端部署小红书自动发布 Skill

> 配套课程：AI 业务流架构师 · 第12节 云端执行体与跨端登录协作
> 前置条件：已准备好 `DjangoPeng/agentic-ai` 仓库（xhs-auto-publisher/ 目录），并能让龙虾访问目标云服务器
> 操作方式：把本实验中的完整 Prompt 复制给龙虾执行，学员不需要直接登录服务器
> 预计耗时：60-90 分钟

---

## 实验目标

1. 理解小红书自动发布 Skill 的云端最小可运行链路：生成二维码截图 -> 生成 payload -> 由龙虾转发到飞书群。
2. 完成一次标准云端部署：拉取仓库、安装系统依赖、初始化项目、复制 `.env`、设置 `MODE=draft`。
3. 验证 Playwright + Xvfb 能在 Ubuntu 服务器上启动浏览器并跑到扫码登录阶段。
4. 检查二维码截图和 lobster notify payload 是否正确生成。
5. 理解内容 JSON 格式，掌握自定义发布内容的完整链路。
6. 体验核心 Agent 范式：口述意图 → 龙虾生成结构化数据 → 自动执行操作。

---

## 实验说明

这一节不是要把小红书笔记真正发布出去，而是验证云端 Skill 是否具备最基本的运行能力。

当前项目只走一条链路：

```text
生成二维码截图 -> 生成 payload -> 后续由龙虾把图片发到飞书群
```

只要成功生成下面两个文件，就说明本节实验完成：

```text
runtime/runs/<run_id>/screenshots/login_qr.png
runtime/lobster-notify/<run_id>/login_qr.payload.json
```

> 注意：下面的 Prompt 是本实验的核心执行指令。复制给龙虾时请保持完整，不要拆开改写。

---

## 实验一：让龙虾部署并运行 Skill

在飞书中把下面整段发送给龙虾：

```text
帮我在云服务器上部署并运行一个 Skill。

第一步，一键部署（克隆仓库、安装依赖、初始化环境、写好 .env MODE=draft）：
curl -fsSL https://raw.githubusercontent.com/DjangoPeng/agentic-ai/main/xhs-auto-publisher/deploy/setup.sh | bash

第二步，运行：
bash ~/projects/xhs-auto-publisher/deploy/run_with_xvfb.sh

每完成一步回报结果。

跑到需要扫码登录时：
1. 读取 ~/projects/xhs-auto-publisher/runtime/lobster-notify/<run_id>/login_qr.payload.json
2. 取出 delivery.path 字段对应的图片文件
3. 把那张二维码图片直接发到飞书群（图片消息，不是路径文字）
4. 把 delivery.caption_lines 的内容作为说明文字一并发出
5. 等待我确认扫码完成后再继续执行
```

### 确认要点

龙虾回报时，重点检查：

1. 仓库是否在 `~/projects/xhs-auto-publisher`
2. `.venv` 是否创建成功
3. Playwright Chromium 是否安装成功
4. `.env` 中是否是 `MODE=draft`
5. 是否生成 `login_qr.png`
6. 是否生成 `login_qr.payload.json`

---

## 实验二：判断部署是否通过

当龙虾回报执行结果后，用下面标准判断。

### 场景 A：成功跑到二维码阶段

期望看到类似信息：

```text
run_id:
<run_id>

二维码图片路径:
~/projects/xhs-auto-publisher/runtime/runs/<run_id>/screenshots/login_qr.png

payload 文件路径:
~/projects/xhs-auto-publisher/runtime/lobster-notify/<run_id>/login_qr.payload.json
```

如果两个文件都存在，本实验通过。

### 场景 B：系统依赖安装失败

重点看龙虾回报中的：

- `apt` 是否失败
- 是否是 root 用户
- Ubuntu 版本是否符合预期
- `install_system_ubuntu.sh` 的核心报错是什么

### 场景 C：Playwright 或 Chromium 初始化失败

重点看：

- `.venv` 是否存在
- `playwright` 是否能 import
- Chromium 是否安装成功
- 是否缺少 Linux 系统库

### 场景 D：没有生成二维码截图或 payload

重点看：

- `deploy/run_with_xvfb.sh` 是否真的跑起来
- 是否创建了 `runtime/runs/<run_id>/`
- `runtime/runs/<run_id>/screenshots/` 里是否有截图
- `runtime/lobster-notify/` 里是否有对应 run_id

---

## 实验三：用自己的内容发布一条笔记

这个实验的核心是体验 Agent 范式：**你只描述意图，龙虾负责把内容组织成结构化 JSON 并执行发布**。

### 内容 JSON 格式

发布内容由一个 JSON 文件驱动，结构如下：

```json
{
  "title": "标题，最多 80 字",
  "body": "正文，最多 2000 字",
  "topics": ["话题1", "话题2", "话题3"],
  "images": ["图片路径"],
  "mode": "draft"
}
```

`mode` 建议先用 `draft`，确认内容填写效果后再改 `publish` 真正发出。

### 图片准备

三种方式选一种：

| 方式 | 操作 |
|---|---|
| 用项目自带样例图 | 直接引用 `~/projects/xhs-auto-publisher/examples/assets/Openclaw商业应用场景.jpg` |
| 从公网 URL 下载 | 告诉龙虾图片 URL，让它 `curl -o` 到服务器 |
| 本机上传 | `scp 你的图片 root@服务器IP:~/projects/xhs-auto-publisher/assets/` |

### 发给龙虾的 Prompt

把下面这段发给龙虾，将 `[...]` 部分替换为你自己的内容：

```text
帮我在云服务器上发布一条小红书笔记，内容如下：

标题：[你的标题]
正文：[你的正文]
话题：[话题1, 话题2, 话题3]
图片：~/projects/xhs-auto-publisher/examples/assets/Openclaw商业应用场景.jpg

步骤：
1. 在服务器上创建文件 ~/projects/xhs-auto-publisher/my_content.json，内容按照下面格式写好，mode 先设为 draft：
   {
     "title": "...",
     "body": "...",
     "topics": [...],
     "images": ["..."],
     "mode": "draft"
   }
2. 运行：
   bash ~/projects/xhs-auto-publisher/deploy/run_with_xvfb.sh ~/projects/xhs-auto-publisher/my_content.json
3. 如果需要扫码登录：把二维码图片直接发到飞书群，等我扫码后继续
4. 回报最终 result.json 里的 status 和 url
```

### 验证 draft 效果

`mode: draft` 时，脚本会填好标题、正文、话题、图片，但**不点发布按钮**，停在发布前页面截图。

龙虾回报 `status: draft_ready` 即为正常，截图保存在：

```text
~/projects/xhs-auto-publisher/runtime/runs/<run_id>/screenshots/before_publish.png
```

确认内容填写正确后，把 `my_content.json` 里的 `mode` 改为 `publish`，重新跑一次即可真正发出。

---

## 验收标准

完成本实验时，应满足以下条件：

**实验一、二（部署验证）：**

- 项目目录已正确部署到 `~/projects/xhs-auto-publisher`
- `.venv` 创建成功，Playwright Chromium 安装成功
- 成功生成 `login_qr.png` 和 `login_qr.payload.json`
- 龙虾把二维码图片发到飞书群，扫码登录成功

**实验三（自定义内容发布）：**

- 龙虾根据口述内容生成了正确的 `my_content.json`
- `mode: draft` 时回报 `draft_ready`，截图显示内容填写正确
- `mode: publish` 时回报 `published`，小红书创作后台可见新笔记

---

## 实验记录

请记录你在实验过程中遇到的任何与预期不符的情况：

| # | 发生在哪一步 | 预期行为 | 实际行为 | 你的解决方法 |
|---|------------|----------|---------|------------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

## 常见问题排查

- GitHub 拉取失败：检查服务器网络，确认能访问 GitHub。
- 系统依赖安装失败：确认是 root 用户，检查 apt 源和 Ubuntu 版本。
- `.venv` 创建失败：查看 `deploy/bootstrap_project.sh` 的 Python 相关报错。
- Playwright Chromium 安装失败：重新执行初始化脚本，并确认系统依赖已安装。
- `run_with_xvfb.sh` 无法启动：检查 Xvfb 是否安装，查看 DISPLAY 和 Chromium 报错。
- 没有生成 `login_qr.png`：检查最近一次 `runtime/runs/<run_id>/actions.jsonl` 和 `screenshots/`。
- 没有生成 `login_qr.payload.json`：检查 `runtime/lobster-notify/<run_id>/` 是否生成，以及 payload 生成逻辑是否触发。

> 欢迎把你的实验记录和踩坑发现分享到课程社群。
