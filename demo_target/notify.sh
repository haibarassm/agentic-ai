#!/usr/bin/env bash
# ✅ 改为环境变量读取，避免硬编码 webhook URL 泄露
# 如需测试，请在 .env 或环境中设置 FEISHU_WEBHOOK
if [ -z "$FEISHU_WEBHOOK" ]; then
  echo "❌ 缺少必需环境变量: FEISHU_WEBHOOK" >&2
  echo "请在 .env 或环境中设置 FEISHU_WEBHOOK" >&2
  exit 1
fi

curl -s -X POST "$FEISHU_WEBHOOK" -d '{"msg":"demo"}'
