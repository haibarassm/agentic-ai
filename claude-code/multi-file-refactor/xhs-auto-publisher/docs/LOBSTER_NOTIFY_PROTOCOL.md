# 龙虾通知协议

这份文档定义的是：

- `xhs-auto-publisher` 如何把登录二维码交给龙虾
- 龙虾应该如何读取 payload 并转发到飞书群

## 1. 文件位置

当任务需要扫码登录时，项目会生成：

```text
runtime/lobster-notify/<run_id>/login_qr.payload.json
```

例如：

```text
runtime/lobster-notify/20260516-153000/login_qr.payload.json
```

## 2. payload 示例

```json
{
  "ts": "2026-05-16T15:30:00+08:00",
  "channel": "lobster_channel",
  "kind": "login_qr",
  "platform": "xiaohongshu",
  "title": "[XHS Cloud Login] 小红书登录二维码",
  "run_id": "20260516-153000",
  "screenshot_path": "runtime/runs/20260516-153000/screenshots/login_qr.png",
  "message_lines": [
    "[XHS Cloud Login] 小红书登录二维码",
    "Run ID: 20260516-153000",
    "图片路径: runtime/runs/20260516-153000/screenshots/login_qr.png",
    "请把这张二维码图片直接发到飞书群，用户扫码后等待任务继续。"
  ],
  "action": "send_image_to_feishu_group",
  "delivery": {
    "type": "image_file",
    "path": "runtime/runs/20260516-153000/screenshots/login_qr.png",
    "caption_lines": [
      "[XHS Cloud Login] 小红书登录二维码",
      "Run ID: 20260516-153000",
      "图片路径: runtime/runs/20260516-153000/screenshots/login_qr.png",
      "请把这张二维码图片直接发到飞书群，用户扫码后等待任务继续。"
    ]
  }
}
```

## 3. 龙虾必须处理的字段

最关键的是这几个：

- `kind`
  当前固定为 `login_qr`
- `run_id`
  当前任务 ID
- `delivery.type`
  当前固定为 `image_file`
- `delivery.path`
  要发出去的二维码图片路径
- `delivery.caption_lines`
  跟随图片一起发送的说明文字

## 4. 龙虾应该怎么做

读取到 payload 后，按这个顺序处理：

1. 解析 JSON
2. 判断 `kind == "login_qr"`
3. 读取 `delivery.path`
4. 找到本地二维码图片
5. 把图片直接发到飞书群
6. 把 `delivery.caption_lines` 拼成多行文本一并发送

## 5. 推荐发送效果

飞书群里建议至少包含：

- 二维码图片
- Run ID
- 简短提示语

例如：

```text
[XHS Cloud Login] 小红书登录二维码
Run ID: 20260516-153000
请扫码完成登录，扫码后等待任务自动继续。
```

## 6. 不需要做的事

龙虾不需要：

- 生成公网访问链接
- 暴露 nginx 静态目录
- 反向代理二维码图片
- 修改图片内容

它只需要把图片发出去。

## 7. 失败处理建议

如果龙虾发送失败，建议至少回报：

- payload 文件路径
- 图片路径
- 失败原因
- 当前 run_id

这样排查会很快。
