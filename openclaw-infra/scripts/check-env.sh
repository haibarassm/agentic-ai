#!/bin/bash
# ============================================================
# OpenClaw 环境自检脚本
# ============================================================

set -u

ENV_FILE="/opt/openclaw.env"
OPENCLAW_CONFIG="${OPENCLAW_CONFIG:-/root/.openclaw/openclaw.json}"
REQUIRED_NODE_MAJOR=24
GATEWAY_PORT=18789
SSH_PORT=22
FAILURES=0
WARNINGS=0

print_header() {
    echo "=========================================="
    echo "  OpenClaw 环境自检"
    echo "=========================================="
    echo ""
}

pass() {
    echo "✅ $1"
}

warn() {
    echo "⚠️  $1"
    WARNINGS=$((WARNINGS + 1))
}

fail() {
    echo "❌ $1"
    FAILURES=$((FAILURES + 1))
}

section() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

load_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        fail "环境变量文件不存在：$ENV_FILE"
        return
    fi

    pass "环境变量文件存在：$ENV_FILE"

    if [ -r "$ENV_FILE" ]; then
        set -a
        # shellcheck disable=SC1090
        source "$ENV_FILE"
        set +a
    else
        fail "环境变量文件不可读：$ENV_FILE"
        return
    fi

    local mode
    mode=$(stat -c '%a' "$ENV_FILE" 2>/dev/null || stat -f '%Lp' "$ENV_FILE" 2>/dev/null || true)
    if [ "$mode" = "600" ]; then
        pass "$ENV_FILE 权限为 600"
    elif [ -n "$mode" ]; then
        warn "$ENV_FILE 权限为 $mode，建议执行：chmod 600 $ENV_FILE"
    else
        warn "无法读取 $ENV_FILE 权限"
    fi
}

check_node() {
    section "检查 Node.js"

    if ! command -v node >/dev/null 2>&1; then
        fail "未安装 Node.js，setup-openclaw.sh 需要 Node.js ${REQUIRED_NODE_MAJOR}+"
        return
    fi

    local node_version
    local node_major
    node_version=$(node -v)
    node_major=${node_version#v}
    node_major=${node_major%%.*}

    if [ "$node_major" -ge "$REQUIRED_NODE_MAJOR" ]; then
        pass "Node.js 版本满足要求：$node_version"
    else
        fail "Node.js 版本过低：$node_version，需要 ${REQUIRED_NODE_MAJOR}+"
    fi

    if command -v npm >/dev/null 2>&1; then
        pass "npm 可用：$(npm -v)"
    else
        fail "npm 未安装或不可用"
    fi
}

check_env_vars() {
    section "检查必需环境变量"
    load_env_file

    if [ -n "${OPENAI_API_KEY:-}" ] && [ "${OPENAI_API_KEY:-}" != "sk-xxx" ]; then
        pass "OPENAI_API_KEY 已配置"
    else
        fail "OPENAI_API_KEY 未配置或仍是占位值"
    fi

    if [ -n "${OPENAI_BASE_URL:-}" ]; then
        pass "OPENAI_BASE_URL 已配置：$OPENAI_BASE_URL"
    else
        fail "OPENAI_BASE_URL 未配置"
    fi
}

check_openclaw() {
    section "检查 OpenClaw"

    if command -v openclaw >/dev/null 2>&1; then
        pass "openclaw 命令可用：$(command -v openclaw)"
        if openclaw --version >/dev/null 2>&1; then
            pass "OpenClaw 版本：$(openclaw --version)"
        else
            warn "openclaw --version 执行失败"
        fi
    else
        fail "openclaw 命令不存在，请先执行 npm install -g openclaw@2026.4.22"
    fi

    if [ -f "$OPENCLAW_CONFIG" ]; then
        pass "OpenClaw 配置文件存在：$OPENCLAW_CONFIG"
    else
        fail "OpenClaw 配置文件不存在：$OPENCLAW_CONFIG"
    fi

    if command -v systemctl >/dev/null 2>&1; then
        if systemctl list-unit-files openclaw.service >/dev/null 2>&1; then
            pass "systemd 服务文件已注册：openclaw.service"
        else
            warn "systemd 未注册 openclaw.service"
        fi

        if systemctl is-active --quiet openclaw 2>/dev/null; then
            pass "openclaw 服务正在运行"
        else
            warn "openclaw 服务未运行，可检查：systemctl status openclaw"
        fi
    else
        warn "当前系统没有 systemctl，跳过服务状态检查"
    fi
}

port_pids() {
    local port="$1"

    if command -v ss >/dev/null 2>&1; then
        ss -tlnp 2>/dev/null | grep ":${port}" | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true
    elif command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u || true
    else
        return 1
    fi
}

check_port() {
    local port="$1"
    local label="$2"
    local expected="$3"
    local pids

    pids=$(port_pids "$port")

    if [ -n "$pids" ]; then
        if [ "$expected" = "occupied" ]; then
            pass "$label 端口 $port 已被监听，PID：${pids//$'\n'/, }"
        else
            warn "$label 端口 $port 被占用，PID：${pids//$'\n'/, }"
        fi
    else
        if [ "$expected" = "free" ]; then
            pass "$label 端口 $port 当前空闲"
        else
            warn "$label 端口 $port 未监听"
        fi
    fi
}

check_ports() {
    section "检查关键端口"

    if ! command -v ss >/dev/null 2>&1 && ! command -v lsof >/dev/null 2>&1; then
        warn "未找到 ss 或 lsof，无法检查端口占用"
        return
    fi

    check_port "$GATEWAY_PORT" "OpenClaw Gateway" "occupied"
    check_port "$SSH_PORT" "SSH" "occupied"
}

check_tailscale() {
    section "检查 Tailscale"

    if command -v tailscale >/dev/null 2>&1; then
        pass "tailscale 命令可用：$(command -v tailscale)"
    else
        warn "tailscale 命令不存在，Step 5 前需要安装并认证 Tailscale"
        return
    fi

    if command -v systemctl >/dev/null 2>&1; then
        if systemctl is-active --quiet tailscaled 2>/dev/null; then
            pass "tailscaled 服务正在运行"
        else
            warn "tailscaled 服务未运行"
        fi
    fi

    if tailscale status --self >/dev/null 2>&1; then
        pass "Tailscale 当前已登录并可读取本机状态"
    else
        warn "Tailscale 尚未完成认证，可执行：sudo tailscale up"
    fi
}

print_summary() {
    section "自检结果"

    if [ "$FAILURES" -eq 0 ]; then
        pass "未发现阻断项"
    else
        fail "发现 $FAILURES 个阻断项"
    fi

    if [ "$WARNINGS" -gt 0 ]; then
        warn "发现 $WARNINGS 个提醒项"
    fi

    if [ "$FAILURES" -eq 0 ]; then
        exit 0
    fi

    exit 1
}

print_header
check_node
check_env_vars
check_openclaw
check_ports
check_tailscale
print_summary
