#!/usr/bin/env python3
"""小红书自动发布脚本 - 每天从指定目录读取当日内容发布"""
import json
from pathlib import Path
from datetime import datetime
import subprocess
import sys

PROJECT_ROOT = Path("/root/projects/xhs-auto-publisher")
CONTENT_DIR = PROJECT_ROOT / "daily_content"
LOG_FILE = PROJECT_ROOT / "runtime" / "auto_publish.log"

def get_today_content():
    """获取今日内容文件"""
    today = datetime.now().strftime("%Y-%m-%d")
    content_file = CONTENT_DIR / f"{today}.json"
    return content_file

def publish():
    """执行发布"""
    content_file = get_today_content()
    
    if not content_file.exists():
        log(f"[ERROR] 今日内容文件不存在: {content_file}")
        return 1
    
    log(f"[INFO] 开始发布: {content_file}")
    
    # 执行发布脚本
    result = subprocess.run(
        ["bash", str(PROJECT_ROOT / "deploy" / "run_with_xvfb.sh"), str(content_file)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True
    )
    
    log(f"[INFO] 发布完成，返回码: {result.returncode}")
    if result.stdout:
        log(f"[STDOUT] {result.stdout}")
    if result.stderr:
        log(f"[STDERR] {result.stderr}")
    
    return result.returncode

def log(message):
    """记录日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    print(log_line, end="")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(log_line)

if __name__ == "__main__":
    sys.exit(publish())