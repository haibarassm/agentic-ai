import os
import sys


def _get_required_env(key: str) -> str:
    """从环境变量读取必需配置，缺失时提供友好错误提示。"""
    value = os.getenv(key)
    if not value:
        sys.stderr.write(f"❌ 缺少必需环境变量: {key}\n")
        sys.stderr.write(f"请在 .env 或环境中设置 {key}\n")
        raise SystemExit(1)
    return value


# ✅ 改为环境变量读取，避免硬编码密钥泄露
MYAPP_API_KEY = _get_required_env("MYAPP_API_KEY")
DATABASE_URL = _get_required_env("DATABASE_URL")


def get_client():
    # 使用从环境变量读取的凭据 —— 安全实践
    return {"api_key": MYAPP_API_KEY, "db": DATABASE_URL}
