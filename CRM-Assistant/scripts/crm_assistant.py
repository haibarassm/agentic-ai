from __future__ import annotations

import argparse
import json
import os
import re
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import error, parse, request


VALID_INTENT_LEVELS = ["low", "medium", "high"]
VALID_STAGES = ["初次接触", "需求确认", "方案沟通", "推进中", "待成交", "已成交"]
VALID_CHANNELS = ["微信", "邮件", "飞书消息"]


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def write_text(path: str | Path, value: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value, encoding="utf-8-sig")


def read_json(path: str | Path) -> Any:
    return json.loads(read_text(path))


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def get_object_value(obj: Any, property_name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        value = obj.get(property_name, default)
    else:
        value = getattr(obj, property_name, default)
    return default if value is None else value


def resolve_str(path: str | Path | None) -> str | None:
    if not path:
        return None
    return str(Path(path).resolve())


def read_json_if_exists(path: str | Path | None) -> Any:
    if not path:
        return None
    target = Path(path)
    if not target.exists():
        return None
    return read_json(target)


def get_lines(text: str) -> list[str]:
    return [line.strip() for line in re.split(r"\r?\n", text) if line.strip()]


def get_matched_lines(lines: list[str], patterns: list[str]) -> list[str]:
    results: list[str] = []
    for line in lines:
        for pattern in patterns:
            if re.search(pattern, line):
                if line not in results:
                    results.append(line)
                break
    return results


def get_labels(text: str, mapping: dict[str, str]) -> list[str]:
    labels: list[str] = []
    for label, pattern in mapping.items():
        if re.search(pattern, text):
            labels.append(label)
    deduped: list[str] = []
    for item in labels:
        if item not in deduped:
            deduped.append(item)
    return deduped


def join_values(values: list[Any] | None, fallback: str = "暂无") -> str:
    if not values:
        return fallback
    items: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in items:
            items.append(text)
    return "；".join(items) if items else fallback


def parse_budget_max(text: str) -> int:
    max_value = 0
    for match in re.finditer(r"(\d+)\s*到\s*(\d+)\s*万", text):
        max_value = max(max_value, int(match.group(2)))
    for match in re.finditer(r"(预算|金额超过)\D{0,8}(\d+)\s*万", text):
        max_value = max(max_value, int(match.group(2)))
    for match in re.finditer(r"(合同金额|金额|控制在|压在)\D{0,8}(\d+)\s*万", text):
        max_value = max(max_value, int(match.group(2)))
    return max_value


def clamp_score(value: int) -> int:
    return max(0, min(100, value))


def has_pattern(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text))


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return datetime.fromisoformat(text)


def isoformat_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def get_business_value(text: str) -> str | None:
    for pattern in [
        r"预算大概在\s*(\d+)\s*到\s*(\d+)\s*万",
        r"(\d+)\s*到\s*(\d+)\s*万",
    ]:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)}-{match.group(2)}万"
    match = re.search(r"(控制在|控制到|希望先控制在|尽量控制在)\s*(\d+)\s*万以内", text)
    if match:
        return f"{match.group(2)}万以内"
    match = re.search(r"金额在\s*(\d+)\s*万以内", text)
    if match:
        return f"{match.group(1)}万以内"
    match = re.search(r"(\d+)\s*万以内", text)
    if match:
        return f"{match.group(1)}万以内"
    match = re.search(r"合同金额\D{0,8}(\d+)\s*万", text)
    if match:
        return f"约 {match.group(1)} 万"
    match = re.search(r"预算[^。；\n]{0,10}?(\d+)\s*万", text)
    if match:
        return f"约 {match.group(1)} 万"
    return None


def get_business_value_or_default(text: str) -> str:
    value = get_business_value(text)
    return value if value else "暂无明确业务价值"


def clean_opportunity_theme(raw_title: str, company_name: Any = None, customer_name: Any = None) -> str:
    title = str(raw_title).strip()
    if not title:
        return ""
    for value in [company_name, customer_name]:
        text = str(value).strip() if value is not None else ""
        if text:
            title = title.replace(text, "")
    title = re.sub(r"[（(][^)）]*[)）]", "", title)
    title = re.sub(r"(方案)?沟通会$", "", title)
    title = re.sub(r"分享会$", "分享", title)
    title = re.sub(r"培训会$", "培训", title)
    title = re.sub(r"交流会$", "交流", title)
    title = re.sub(r"评审会$", "评审", title)
    title = re.sub(r"启动会$", "启动", title)
    title = re.sub(r"讨论会$", "讨论", title)
    title = re.sub(r"会议$", "", title)
    title = re.sub(r"\s+", "", title)
    title = re.sub(r"^[：:·\-—_]+|[：:·\-—_]+$", "", title)
    return title.strip()


def infer_opportunity_theme(title: Any, text: str, company_name: Any = None, customer_name: Any = None) -> str:
    title_theme = clean_opportunity_theme(str(title or ""), company_name, customer_name)
    if len(title_theme) >= 4:
        return title_theme
    if re.search(r"资产配置|美元", text):
        return "资产配置"
    if re.search(r"安装|部署|上手|教学|带教|培训|操作手册|场景赋能|模板包", text):
        return "现场教学与场景赋能"
    if re.search(r"巡检|售后|工厂|缺陷闭环|班组周复盘", text):
        return "现场运维协同试点"
    if re.search(r"并网|补件|验收|光伏|资料协同", text):
        return "并网资料协同"
    if re.search(r"CRM|客户信息|会议纪要|客户画像|跟进建议", text):
        return "CRM 一期试点"
    return "商机推进"


def infer_mbti(text: str) -> str:
    patterns = [
        ("ESTJ", r"权限边界|审批链|谁能导出|谁能修改|总部|区域|门店|我这个人比较直接|先给我结论|别讲概念|只看三件事"),
        ("ISTJ", r"字段清单|权限矩阵|归档逻辑|流程节点|导出格式|审批节点图"),
        ("INTJ", r"先确认方案框架|先看整体框架|讲清楚差异|讲清楚逻辑|希望看得更细"),
        ("INTP", r"想先了解一下|先研究一下|先看案例|先看思路"),
        ("ENTJ", r"尽快推进|本月底前|立项方向定下来|推进到采购"),
        ("ENTP", r"可以再扩展|后续更复杂的自动化扩展|多试几个场景"),
        ("INFJ", r"希望大家都能接受|照顾团队感受|长期关系|别让一线太难受"),
        ("INFP", r"不喜欢被高频跟进|别太打扰|慢慢看"),
        ("ENFJ", r"一起参与|都拉上|多方一起看"),
        ("ENFP", r"有意思|可以再聊|后面有机会再聊"),
        ("ISFJ", r"本金安全|流动性|稳健|别太复杂"),
        ("ESFJ", r"员工使用感受|内部流转方便|传阅方便"),
        ("ISTP", r"先试点|先覆盖|先把这三个高频场景做扎实"),
        ("ISFP", r"别发一堆材料|结构简单|不要太重"),
        ("ESTP", r"先做一期|马上看效果|快速见效"),
        ("ESFP", r"直接一点|三点结论|不要太长"),
    ]
    for label, pattern in patterns:
        if re.search(pattern, text):
            return label
    return "未明确"


def infer_single_status(text: str) -> str:
    if re.search(r"单身|一个人决定|我自己决定", text):
        return "是"
    if re.search(r"已婚|我先生|我太太|丈夫|妻子|伴侣", text):
        return "否"
    return "未明确"


def infer_resistance_level(stage: str, risk_concerns: list[str], text: str) -> str:
    high_patterns = r"不希望|必须|一定要|卡住|风险大|别太复杂|系统太重|培训复杂"
    low_patterns = r"整体方向认可|没有大的异议|可以推进|基本就可以"
    if re.search(high_patterns, text) or len(risk_concerns) >= 3:
        return "高"
    if re.search(low_patterns, text) and stage in ["推进中", "待成交", "已成交"]:
        return "低"
    if risk_concerns or stage in ["需求确认", "方案沟通", "推进中"]:
        return "中"
    return "未明确"


def infer_price_sensitivity(customer_text: str, risk_concerns: list[str], budget_max: int) -> str:
    if "价格敏感" in risk_concerns or re.search(r"预算|价格|成本|别太重|值不值", customer_text):
        return "高" if budget_max <= 50 and budget_max > 0 else "中"
    if budget_max >= 80:
        return "低"
    return "未明确"


def calculate_lead_score(
    opportunity_stage: str,
    customer_text: str,
    all_text: str,
    budget_max: int,
    next_meeting_time: datetime | None,
    decision_signals: list[str],
    risk_concerns: list[str],
) -> int:
    timeline_signal = has_pattern(customer_text, r"下周|本周|本月|月底|季度内|尽快|明天|周五之前|六月底前")
    scope_signal = has_pattern(customer_text, r"边界|范围|收敛|梳理清楚|需求对齐|需求确认|必须做|后放|优先级")
    proposal_signal = has_pattern(customer_text, r"报价|方案|演示|保守版|标准版|角色权限表|流程节点")
    acceptance_signal = has_pattern(customer_text, r"可以|能接受|认可|方向比上次清楚多了|没问题")
    procurement_signal = has_pattern(customer_text, r"采购|法务|签批|内部评审|内部推进")
    implementation_signal = has_pattern(customer_text, r"上线一期|先上线|试运行|服务站|启动会|联调|推进清单")
    contract_signal = has_pattern(customer_text, r"合同|定稿|付款|付款节点|合同金额|签约|最终版")
    signoff_signal = has_pattern(customer_text, r"这周就进签约流程|周三可以完成签约|不会再拖|没有新增阻塞|基本通过了")
    closed_won_signal = has_pattern(customer_text, r"已成交|正式成交|成交确认|合同(这周)?已经签完|合同今天上午已经完成双方签署|完成双方签署|签署完成|双方法务盖章|项目已经正式敲定|金额.*已经锁定|这笔商机就按正式成交记录")
    kickoff_signal = has_pattern(customer_text, r"启动会|交付负责人|项目经理|阶段验收|交付执行|接口联调计划")
    budget_signal = budget_max > 0
    multi_role_signal = bool(decision_signals) or has_pattern(customer_text, r"运营管理|质控|信息科技|采购|法务|总部")
    risk_signal = bool(risk_concerns)

    lead_score = {
        "初次接触": 20,
        "需求确认": 30,
        "方案沟通": 32,
        "推进中": 30,
        "待成交": 40,
        "已成交": 50,
    }[opportunity_stage]

    if budget_signal:
        lead_score += 14
    if timeline_signal:
        lead_score += 6
    if next_meeting_time is not None:
        lead_score += 4

    if opportunity_stage == "需求确认":
        if multi_role_signal:
            lead_score += 8
        if scope_signal:
            lead_score += 14
        if risk_signal:
            lead_score += 6
    elif opportunity_stage == "方案沟通":
        if multi_role_signal:
            lead_score += 8
        if proposal_signal:
            lead_score += 16
        if acceptance_signal:
            lead_score += 6
        if has_pattern(customer_text, r"保守版|标准版|双版本|报价结构"):
            lead_score += 4
    elif opportunity_stage == "推进中":
        if procurement_signal:
            lead_score += 16
        if implementation_signal:
            lead_score += 12
        if risk_signal:
            lead_score += 10
    elif opportunity_stage == "待成交":
        if contract_signal:
            lead_score += 20
        if procurement_signal:
            lead_score += 10
        if signoff_signal:
            lead_score += 6
        if kickoff_signal:
            lead_score += 6
        if has_pattern(customer_text, r"付款节点|合同版本|最终合同版本|周三可以完成签约|签约收掉|这周就把签约收掉|把合同版本和付款安排锁定"):
            lead_score += 10
    elif opportunity_stage == "已成交":
        if closed_won_signal:
            lead_score += 25
        if kickoff_signal:
            lead_score += 10
        if has_pattern(all_text, r"金额.*锁定|付款按之前确认|正式签署|阶段验收"):
            lead_score += 11
    else:
        if multi_role_signal:
            lead_score += 6
        if proposal_signal:
            lead_score += 6

    if has_pattern(customer_text, r"不着急|先了解|明年再说|明年再定|先看看|观察一下"):
        lead_score -= 15
    if has_pattern(customer_text, r"暂无预算|预算要等明年|预算还没批"):
        lead_score -= 12

    return clamp_score(lead_score)


def get_sales_region(context: dict[str, Any], text: str) -> str | None:
    context_region = get_object_value(context, "sales_region")
    if context_region and str(context_region).strip():
        return str(context_region).strip()
    for keyword, label in [
        ("华北", "华北地区"),
        ("华东", "华东地区"),
        ("华南", "华南地区"),
        ("西南", "西南地区"),
        ("西北", "西北地区"),
        ("全国", "全国"),
    ]:
        if keyword in text:
            return label
    return None


def get_transcript_text(raw: dict[str, Any]) -> str:
    transcript = raw.get("transcript", {}) or {}
    full_text = transcript.get("full_text")
    if full_text and str(full_text).strip():
        return str(full_text).strip()
    segments = transcript.get("segments") or []
    lines: list[str] = []
    for segment in segments:
        speaker = str(segment.get("speaker") or "发言人").strip() or "发言人"
        text = str(segment.get("text") or "").strip()
        if text:
            lines.append(f"{speaker}：{text}")
    if lines:
        return "\n".join(lines)
    raise ValueError("No transcript.full_text or transcript.segments found in raw input.")


def extract_bitable_app_token(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"/base/([A-Za-z0-9]+)", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9]+", text):
        return text
    return None


def resolve_feishu_value(cli_value: str | None, config: dict[str, Any] | None, config_key: str, env_key: str) -> str | None:
    if cli_value and str(cli_value).strip():
        return str(cli_value).strip()
    config_value = get_object_value(config, config_key)
    if config_value and str(config_value).strip():
        return str(config_value).strip()
    env_value = os.getenv(env_key)
    if env_value and env_value.strip():
        return env_value.strip()
    return None


def build_url(base_url: str, query: dict[str, Any] | None = None) -> str:
    if not query:
        return base_url
    normalized: dict[str, Any] = {}
    for key, value in query.items():
        if value is None:
            continue
        normalized[key] = value
    if not normalized:
        return base_url
    return f"{base_url}?{parse.urlencode(normalized)}"


def http_json_request(url: str, method: str = "GET", headers: dict[str, str] | None = None, body: Any = None) -> dict[str, Any]:
    request_headers = dict(headers or {})
    data: bytes | None = None
    if body is not None:
        request_headers["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with request.urlopen(req) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        detail = raw or str(exc)
        raise RuntimeError(f"HTTP {exc.code} request failed for {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network request failed for {url}: {exc}") from exc


def get_feishu_tenant_access_token(app_id: str, app_secret: str) -> str:
    response = http_json_request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        method="POST",
        body={"app_id": app_id, "app_secret": app_secret},
    )
    if int(get_object_value(response, "code", -1)) != 0:
        raise RuntimeError(f"Failed to get tenant access token: {json.dumps(response, ensure_ascii=False)}")
    token = get_object_value(response, "tenant_access_token")
    if token is None or not str(token).strip():
        raise RuntimeError("tenant_access_token missing in Feishu auth response.")
    return str(token).strip()


def feishu_open_api_request(path: str, tenant_access_token: str, method: str = "GET", query: dict[str, Any] | None = None, body: Any = None) -> dict[str, Any]:
    url = build_url(f"https://open.feishu.cn{path}", query)
    response = http_json_request(
        url,
        method=method,
        headers={"Authorization": f"Bearer {tenant_access_token}"},
        body=body,
    )
    if int(get_object_value(response, "code", -1)) != 0:
        raise RuntimeError(f"Feishu API failed for {path}: {json.dumps(response, ensure_ascii=False)}")
    return response


def list_feishu_bitable_tables(app_token: str, tenant_access_token: str) -> list[dict[str, Any]]:
    page_token: str | None = None
    items: list[dict[str, Any]] = []
    while True:
        response = feishu_open_api_request(
            f"/open-apis/bitable/v1/apps/{app_token}/tables",
            tenant_access_token,
            query={"page_size": 100, "page_token": page_token},
        )
        data = response.get("data") or {}
        items.extend(list(data.get("items") or []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
        if not page_token:
            break
    return items


def list_feishu_bitable_fields(app_token: str, table_id: str, tenant_access_token: str) -> list[dict[str, Any]]:
    page_token: str | None = None
    items: list[dict[str, Any]] = []
    while True:
        response = feishu_open_api_request(
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            tenant_access_token,
            query={"page_size": 500, "page_token": page_token},
        )
        data = response.get("data") or {}
        items.extend(list(data.get("items") or []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
        if not page_token:
            break
    return items


def list_feishu_bitable_records(app_token: str, table_id: str, tenant_access_token: str) -> list[dict[str, Any]]:
    page_token: str | None = None
    items: list[dict[str, Any]] = []
    while True:
        response = feishu_open_api_request(
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            tenant_access_token,
            query={"page_size": 500, "page_token": page_token},
        )
        data = response.get("data") or {}
        items.extend(list(data.get("items") or []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
        if not page_token:
            break
    return items


def batch_create_feishu_bitable_records(app_token: str, table_id: str, records: list[dict[str, Any]], tenant_access_token: str) -> dict[str, Any]:
    return feishu_open_api_request(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
        tenant_access_token,
        method="POST",
        body={"records": records},
    )


def batch_update_feishu_bitable_records(app_token: str, table_id: str, records: list[dict[str, Any]], tenant_access_token: str) -> dict[str, Any]:
    return feishu_open_api_request(
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
        tenant_access_token,
        method="POST",
        body={"records": records},
    )


def map_row_fields(row: dict[str, Any], field_mapping: dict[str, Any] | None = None) -> OrderedDict[str, Any]:
    mapped = OrderedDict()
    mapping = field_mapping or {}
    for source_field, value in row.items():
        target_field = mapping.get(source_field, source_field)
        if target_field is None:
            continue
        target_text = str(target_field).strip()
        if not target_text:
            continue
        mapped[target_text] = value
    return mapped


def is_weak_field_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        normalized = text.lower()
        if normalized in {"null", "none", "n/a", "na"}:
            return True
        if text in {"未明确", "暂无", "未知", "待确认", "待补充"}:
            return True
        if text.startswith("暂无明确"):
            return True
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def merge_row_preserving_existing_values(current_row: OrderedDict[str, Any], existing_fields: dict[str, Any] | None) -> tuple[OrderedDict[str, Any], list[str]]:
    merged = OrderedDict()
    preserved_fields: list[str] = []
    existing = existing_fields or {}
    for field_name, current_value in current_row.items():
        existing_value = existing.get(field_name)
        if is_weak_field_value(current_value) and not is_weak_field_value(existing_value):
            merged[field_name] = existing_value
            preserved_fields.append(field_name)
        else:
            merged[field_name] = current_value
    return merged, preserved_fields


def get_summary_value(value: Any, fallback: str) -> str:
    return fallback if is_weak_field_value(value) else str(value).strip()


def build_customer_profile_summary(
    customer_name: Any,
    opportunity_stage: Any,
    mbti: Any,
    single_status: Any,
    communication_style: Any,
    resistance_level: Any,
    price_sensitivity: Any,
    risk_concerns: Any,
) -> str:
    single_status_text = str(single_status).strip() if single_status is not None else ""
    single_status_summary = {
        "是": "单身状态有明确信号",
        "否": "会话中出现伴侣或婚姻相关信号",
        "未明确": "是否单身未明确",
    }.get(single_status_text, "是否单身未明确")
    customer_name_text = get_summary_value(customer_name, "该客户")
    stage_text = get_summary_value(opportunity_stage, "当前")
    mbti_text = get_summary_value(mbti, "未明确")
    communication_text = get_summary_value(communication_style, "常规沟通")
    resistance_text = get_summary_value(resistance_level, "未明确")
    price_text = get_summary_value(price_sensitivity, "未明确")
    risk_text = get_summary_value(risk_concerns, "暂无明显风险顾虑")
    return (
        f"{customer_name_text}当前处于{stage_text}阶段，"
        f"MBTI 倾向{mbti_text}，{single_status_summary}，"
        f"沟通风格偏{communication_text}，"
        f"成交阻力{resistance_text}，价格敏感程度{price_text}，"
        f"主要风险顾虑为{risk_text}。"
    )


def find_feishu_record_by_field(records: list[dict[str, Any]], field_name: str, expected_value: Any) -> dict[str, Any] | None:
    if expected_value is None:
        return None
    expected_text = str(expected_value).strip()
    if not expected_text:
        return None
    for record in records:
        fields = record.get("fields") or {}
        actual_value = fields.get(field_name)
        if actual_value is None:
            continue
        if isinstance(actual_value, list):
            values = [str(item).strip() for item in actual_value if str(item).strip()]
            if expected_text in values:
                return record
        elif str(actual_value).strip() == expected_text:
            return record
    return None


def inspect_feishu_bitable(app_id: str, app_secret: str, app_token_or_url: str, output_dir: str | Path, table_id: str | None = None) -> dict[str, Any]:
    app_token = extract_bitable_app_token(app_token_or_url)
    if app_token is None:
        raise ValueError("Unable to parse Feishu bitable app token from --app-token-or-url.")
    access_token = get_feishu_tenant_access_token(app_id, app_secret)
    tables = list_feishu_bitable_tables(app_token, access_token)
    result: OrderedDict[str, Any] = OrderedDict([
        ("app_token", app_token),
        ("tables", tables),
    ])
    if table_id:
        result["fields"] = list_feishu_bitable_fields(app_token, table_id, access_token)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "feishu_bitable_inspect.json", result)
    return result


def sync_crm_packet_to_feishu(
    crm_packet_path: str | Path,
    output_dir: str | Path,
    config_path: str | Path | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
    app_token_or_url: str | None = None,
    customer_table_id: str | None = None,
    opportunity_table_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    crm_packet = read_json(crm_packet_path)
    config = read_json_if_exists(config_path) or {}

    resolved_app_id = resolve_feishu_value(app_id, config, "app_id", "FEISHU_APP_ID")
    resolved_app_secret = resolve_feishu_value(app_secret, config, "app_secret", "FEISHU_APP_SECRET")
    resolved_app_token_source = (
        app_token_or_url
        or get_object_value(config, "app_token")
        or get_object_value(config, "bitable_url")
        or os.getenv("FEISHU_BITABLE_APP_TOKEN")
        or os.getenv("FEISHU_BITABLE_URL")
    )
    resolved_app_token = extract_bitable_app_token(str(resolved_app_token_source) if resolved_app_token_source else None)
    if resolved_app_token is None:
        raise ValueError("Missing Feishu app token. Provide --app-token-or-url, config.app_token, config.bitable_url, FEISHU_BITABLE_APP_TOKEN, or FEISHU_BITABLE_URL.")

    resolved_customer_table_id = (
        customer_table_id
        or get_object_value(config, "customer_table_id")
        or os.getenv("FEISHU_CUSTOMER_TABLE_ID")
    )
    resolved_opportunity_table_id = (
        opportunity_table_id
        or get_object_value(config, "opportunity_snapshot_table_id")
        or get_object_value(config, "opportunity_table_id")
        or os.getenv("FEISHU_OPPORTUNITY_TABLE_ID")
    )
    if not resolved_customer_table_id or not str(resolved_customer_table_id).strip():
        raise ValueError("Missing customer table id.")
    if not resolved_opportunity_table_id or not str(resolved_opportunity_table_id).strip():
        raise ValueError("Missing opportunity snapshot table id.")

    customer_field_mapping = get_object_value(config, "customer_field_mapping", {}) or {}
    opportunity_field_mapping = get_object_value(config, "opportunity_field_mapping", {}) or {}
    customer_key_field = str(get_object_value(config, "customer_key_field", "客户ID")).strip() or "客户ID"

    customer_row = map_row_fields(crm_packet["customer_table_row"], customer_field_mapping)
    opportunity_row = map_row_fields(crm_packet["opportunity_snapshot_row"], opportunity_field_mapping)
    customer_key_source_field = next((field for field, target in customer_field_mapping.items() if str(target).strip() == customer_key_field), customer_key_field)
    customer_key_value = crm_packet["customer_table_row"].get(customer_key_source_field)

    report: OrderedDict[str, Any] = OrderedDict([
        ("crm_packet_path", resolve_str(crm_packet_path)),
        ("config_path", resolve_str(config_path)),
        ("app_token", resolved_app_token),
        ("customer_table_id", resolved_customer_table_id),
        ("opportunity_snapshot_table_id", resolved_opportunity_table_id),
        ("customer_key_field", customer_key_field),
        ("customer_key_value", customer_key_value),
        ("dry_run", dry_run),
        ("customer_candidate_row_fields", customer_row),
        ("customer_row_fields", customer_row),
        ("opportunity_row_fields", opportunity_row),
    ])

    if dry_run:
        report["customer_action"] = "preview_only"
        report["opportunity_action"] = "preview_only"
    else:
        if not resolved_app_id or not resolved_app_secret:
            raise ValueError("Missing Feishu app credentials. Provide --app-id/--app-secret, config, or environment variables.")
        access_token = get_feishu_tenant_access_token(resolved_app_id, resolved_app_secret)
        existing_records = list_feishu_bitable_records(resolved_app_token, str(resolved_customer_table_id), access_token)
        existing_record = find_feishu_record_by_field(existing_records, customer_key_field, customer_key_value)
        if existing_record is None:
            customer_response = batch_create_feishu_bitable_records(
                resolved_app_token,
                str(resolved_customer_table_id),
                [{"fields": customer_row}],
                access_token,
            )
            report["customer_action"] = "created"
            report["customer_response"] = customer_response
        else:
            effective_customer_row, preserved_fields = merge_row_preserving_existing_values(customer_row, existing_record.get("fields") or {})
            effective_customer_row["客户画像摘要"] = build_customer_profile_summary(
                effective_customer_row.get("客户名称"),
                opportunity_row.get("当前阶段"),
                effective_customer_row.get("MBTI"),
                effective_customer_row.get("是否单身"),
                effective_customer_row.get("沟通风格"),
                effective_customer_row.get("成交阻力"),
                effective_customer_row.get("价格敏感程度"),
                effective_customer_row.get("风险顾虑"),
            )
            customer_response = batch_update_feishu_bitable_records(
                resolved_app_token,
                str(resolved_customer_table_id),
                [{"record_id": existing_record["record_id"], "fields": effective_customer_row}],
                access_token,
            )
            report["customer_action"] = "updated"
            report["customer_record_id"] = existing_record.get("record_id")
            report["customer_row_fields"] = effective_customer_row
            report["customer_preserved_fields"] = preserved_fields
            report["customer_response"] = customer_response

        opportunity_response = batch_create_feishu_bitable_records(
            resolved_app_token,
            str(resolved_opportunity_table_id),
            [{"fields": opportunity_row}],
            access_token,
        )
        report["opportunity_action"] = "appended"
        report["opportunity_response"] = opportunity_response

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "feishu_sync_result.json", report)
    return report


def get_first_participant_by_role(participants: list[dict[str, Any]], roles: list[str]) -> dict[str, Any] | None:
    for participant in participants:
        if participant.get("role") in roles:
            return participant
    return None


def build_context_from_feishu(raw_input_path: str | Path, output_dir: str | Path, context_file_name: str = "context.json", transcript_file_name: str = "transcript.txt") -> dict[str, Any]:
    raw = read_json(raw_input_path)
    participants = list(raw.get("participants") or [])
    crm_binding = raw.get("crm_binding") or {}
    existing_customer_fields = get_object_value(crm_binding, "existing_customer_fields", {}) or {}
    external_participant = get_first_participant_by_role(participants, ["external", "guest", "customer"])
    internal_participant = get_first_participant_by_role(participants, ["internal", "host", "owner"])
    transcript_text = get_transcript_text(raw)

    customer_name = get_object_value(crm_binding, "customer_name")
    if customer_name is None and external_participant is not None:
        customer_name = external_participant.get("name")
    company_name = get_object_value(crm_binding, "company_name")
    if company_name is None and external_participant is not None:
        company_name = external_participant.get("company")
    owner = get_object_value(crm_binding, "owner")
    if owner is None and internal_participant is not None:
        owner = internal_participant.get("name")
    industry = get_object_value(crm_binding, "industry")
    if industry is None and external_participant is not None:
        industry = external_participant.get("industry")

    meeting = raw.get("meeting") or {}
    calendar = raw.get("calendar") or {}
    context = OrderedDict([
        ("customer_id", get_object_value(crm_binding, "customer_id")),
        ("customer_name", customer_name),
        ("company_name", company_name),
        ("owner", owner),
        ("industry", industry),
        ("opportunity_id", get_object_value(crm_binding, "opportunity_id")),
        ("current_stage", get_object_value(crm_binding, "current_stage", "未知")),
        ("sales_region", get_object_value(crm_binding, "sales_region")),
        ("meeting_time", meeting.get("start_time")),
        ("next_meeting_time", calendar.get("next_meeting_time")),
        ("channel", "飞书会议纪要导入"),
        ("source_meeting_id", meeting.get("meeting_id")),
        ("source_event_id", meeting.get("calendar_event_id")),
        ("source_title", meeting.get("title")),
        ("existing_customer_fields", existing_customer_fields),
    ])

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    context_path = output / context_file_name
    transcript_path = output / transcript_file_name
    write_json(context_path, context)
    write_text(transcript_path, transcript_text)

    result = OrderedDict([
        ("raw_input_path", resolve_str(raw_input_path)),
        ("generated_context", resolve_str(context_path)),
        ("generated_transcript", resolve_str(transcript_path)),
    ])
    write_json(output / "build_result.json", result)
    return result


def process_transcript(transcript_path: str | Path, context_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    context = read_json(context_path)
    transcript = read_text(transcript_path)
    lines = get_lines(transcript)
    company_name = get_object_value(context, "company_name")
    industry_name = get_object_value(context, "industry")
    source_channel = get_object_value(context, "channel", "手动导入")
    existing_customer_fields = get_object_value(context, "existing_customer_fields", {}) or {}

    customer_lines = [line for line in lines if re.search(r"^(客户|张总|陈女士|刘总|孙总|客户A|客户B|客户C|客户D)[:：]", line)]
    if not customer_lines:
        customer_lines = lines[:]
    all_text = " ".join(lines)
    customer_text = " ".join(customer_lines)

    need_lines = get_matched_lines(customer_lines, ["希望", "想", "需要", "重点", "最好", "计划", "目标", "关注", "更在意", "最大的痛点", "先了解", "有意思"])
    concern_lines = get_matched_lines(customer_lines, ["担心", "顾虑", "怕", "不太喜欢", "不喜欢", "不希望", "合规", "隐私", "安全", "风险", "别太复杂", "不要太长", "别搞太重", "培训周期不要太长"])
    next_action_lines = get_matched_lines(lines, ["下周", "下次", "再约", "安排", "发我", "发邮件", "邮箱", "邮件", "报价", "方案", "演示", "见面", "周一", "周二", "周三", "周四", "周五", "今晚", "明天", "试点"])

    risk_concern_map = OrderedDict([
        ("价格敏感", "预算|价格|成本|报价"),
        ("交付风险", "实施|交付|上线|周期拖长|培训周期"),
        ("合规与数据安全", "合规|数据安全|权限|隐私|资金进出"),
        ("效果不确定", "效果|ROI|值不值|产出"),
        ("时间窗口紧张", "本周|下周|本月|月底|季度内|尽快|周五之前|明天"),
    ])
    communication_style_map = OrderedDict([
        ("偏好微信触达", "微信"),
        ("偏好简洁表达", "简洁|不要太长|别太长|三点结论|直接"),
        ("偏好先看材料", "先发|先看|发我|材料|方案发我|清单"),
        ("偏好多方共同沟通", "一起看|一起聊|都参与|拉上"),
        ("偏好邮件接收", "发邮件|发我邮箱|邮箱给我|邮件给我|今晚发我邮箱"),
    ])
    decision_signal_map = OrderedDict([
        ("本人为关键决策人", "我本人会盯|我来拍板|我定|我决定|先跟我沟通"),
        ("家庭共同决策", "我先生|我太太|先生会一起看|太太也会看"),
        ("企业多角色决策", "CFO|CTO|采购|法务|财务总监|运营负责人|董事会|合伙人"),
        ("明确预算", "预算|金额超过"),
        ("明确时间表", "下周|本周|本月|月底|季度内|明天|周五之前|六月底前|下周一|下周三|下周四"),
    ])
    risk_concerns = get_labels(customer_text, risk_concern_map)
    communication_style = get_labels(customer_text, communication_style_map)
    decision_signals = get_labels(customer_text, decision_signal_map)

    budget_max = parse_budget_max(customer_text)

    meeting_time = parse_datetime(get_object_value(context, "meeting_time"))
    next_meeting_time = parse_datetime(get_object_value(context, "next_meeting_time"))
    sales_region = get_sales_region(context, all_text)
    business_value = get_business_value_or_default(all_text)

    opportunity_stage = "初次接触"
    if re.search("已成交|正式成交|成交确认|合同(这周)?已经签完|合同今天上午已经完成双方签署|完成双方签署|签署完成|双方法务盖章|项目已经正式敲定|金额.*已经锁定|这笔商机就按正式成交记录", customer_text):
        opportunity_stage = "已成交"
    elif re.search("合同|签约|付款|定稿", customer_text):
        opportunity_stage = "待成交"
    elif re.search("采购|法务|上线一期", customer_text):
        opportunity_stage = "推进中"
    elif re.search("先把需求对齐|先确认需求|先把边界梳理清楚|先确认范围|先把流程梳理清楚|先做需求确认|先把需求确认完整", customer_text):
        opportunity_stage = "需求确认"
    elif re.search("报价|演示|实施清单|字段清单|保守版|平衡版", customer_text):
        opportunity_stage = "方案沟通"
    elif need_lines:
        opportunity_stage = "需求确认"

    lead_score = calculate_lead_score(
        opportunity_stage,
        customer_text,
        all_text,
        budget_max,
        next_meeting_time,
        decision_signals,
        risk_concerns,
    )
    intent_level = "high" if lead_score >= 75 else ("medium" if lead_score >= 60 else "low")

    high_value_flag = (
        lead_score >= 75
        or budget_max >= 80
        or bool(re.search("家族办公室|资产配置|两家工厂|集团|高净值", all_text))
        or bool(re.search("家族办公室", str(get_object_value(context, "industry", ""))))
    )

    follow_up_time = next_meeting_time if next_meeting_time is not None else (meeting_time + timedelta(days=2) if meeting_time else None)
    recommended_action = {
        "已成交": "切换到交付执行节奏，确认启动会、责任分工与阶段验收安排",
        "待成交": "推动最终确认并准备签约/付款材料",
        "推进中": "整理推进清单，锁定关键角色并跟进采购/法务节点",
        "方案沟通": "24小时内发送定制方案/报价并确认下一次沟通",
        "需求确认": "补齐关键需求信息并推动进入方案讨论",
        "初次接触": "发送简洁会后摘要并继续培育客户意向",
    }[opportunity_stage]
    channel = "邮件" if "偏好邮件接收" in communication_style else ("微信" if "偏好微信触达" in communication_style else "飞书消息")

    summary = f"{get_object_value(context, 'customer_name')}本次重点关注{join_values(need_lines, '当前需求待补充')}；主要顾虑为{join_values(concern_lines, '当前未明确提出强顾虑')}；建议下一步{join_values(next_action_lines, recommended_action)}。"
    mbti = infer_mbti(all_text)
    single_status = infer_single_status(customer_text)
    resistance_level = infer_resistance_level(opportunity_stage, risk_concerns, customer_text)
    price_sensitivity = infer_price_sensitivity(customer_text, risk_concerns, budget_max)
    profile_summary = build_customer_profile_summary(
        get_object_value(context, "customer_name"),
        opportunity_stage,
        mbti,
        single_status,
        join_values(communication_style, "常规沟通"),
        resistance_level,
        price_sensitivity,
        join_values(risk_concerns, "暂无明显风险顾虑"),
    )
    latest_progress = f"本次会议后，客户处于{opportunity_stage}阶段，Lead Score {lead_score}，推荐动作：{recommended_action}"

    opportunity_theme = infer_opportunity_theme(
        get_object_value(context, "source_title"),
        all_text,
        company_name,
        get_object_value(context, "customer_name"),
    )
    opportunity_name = f"{get_object_value(context, 'customer_name')} - {opportunity_theme}"
    opportunity_description = {
        "已成交": "客户已完成合同签署或成交确认，当前重点已转向项目启动、交付排期与阶段验收。",
        "待成交": "客户已进入合同/定稿推进阶段，重点是锁定签约前材料与排期。",
        "推进中": "客户已进入多角色内部推进阶段，需同步采购、法务或实施边界。",
        "方案沟通": "客户已进入方案、报价或演示讨论阶段，正在细化可落地方案。",
        "需求确认": "客户已明确核心需求与约束条件，下一步应推动进入方案沟通。",
        "初次接触": "客户当前仍处于接触或观察阶段，适合继续培育与补充需求理解。",
    }[opportunity_stage]

    draft_message = (
        f"{get_object_value(context, 'customer_name')} 您好，今天沟通的重点我帮您收了一版：\n"
        f"1. 您当前最关注的是：{join_values(need_lines, '核心需求已记录')}。\n"
        f"2. 我们会重点处理：{join_values(concern_lines, '本次暂无突出顾虑')}。\n"
        f"3. 下一步我会：{recommended_action}。\n"
        f"如果方便，我先通过{channel}发您精简版材料，您看完后我们再按约定时间推进。"
    )
    brief_trigger = next_meeting_time - timedelta(hours=1) if next_meeting_time is not None else None
    opening_script = f"先从客户最在意的{join_values(need_lines, '当前需求')}切入，再回应{join_values(risk_concerns, '执行细节')}，最后确认{join_values(next_action_lines, recommended_action)}。"

    discussion_points: list[str] = []
    for item in need_lines + concern_lines:
        if item not in discussion_points:
            discussion_points.append(item)
    key_points: list[str] = []
    for item in need_lines + next_action_lines:
        if item not in key_points:
            key_points.append(item)
    commitments = next_action_lines[:3]
    meeting_id_suffix = meeting_time.strftime("%Y%m%d%H%M") if meeting_time else "unknown"

    meeting_record = OrderedDict([
        ("meeting_id", f"MTG-{get_object_value(context, 'customer_id')}-{meeting_id_suffix}"),
        ("customer_id", get_object_value(context, "customer_id")),
        ("customer_name", get_object_value(context, "customer_name")),
        ("company_name", company_name),
        ("meeting_time", isoformat_or_none(meeting_time)),
        ("summary", summary),
        ("discussion_points", discussion_points),
        ("customer_needs", need_lines),
        ("customer_concerns", concern_lines),
        ("next_actions", next_action_lines),
        ("commitments", commitments),
    ])
    customer_profile_update = OrderedDict([
        ("customer_id", get_object_value(context, "customer_id")),
        ("company_name", company_name),
        ("industry", industry_name),
        ("mbti", mbti),
        ("single_status", single_status),
        ("resistance_level", resistance_level),
        ("price_sensitivity", price_sensitivity),
        ("risk_concerns", risk_concerns),
        ("communication_style", communication_style),
        ("profile_summary", profile_summary),
    ])
    opportunity_update = OrderedDict([
        ("opportunity_id", get_object_value(context, "opportunity_id")),
        ("opportunity_name", opportunity_name),
        ("opportunity_description", opportunity_description),
        ("sales_region", sales_region),
        ("business_value", business_value),
        ("lead_score", lead_score),
        ("intent_level", intent_level),
        ("opportunity_stage", opportunity_stage),
        ("high_value_flag", bool(high_value_flag)),
        ("recommended_action", recommended_action),
        ("next_follow_up_at", isoformat_or_none(follow_up_time)),
        ("latest_progress", latest_progress),
    ])
    follow_up_task = OrderedDict([
        ("task_title", f"跟进 {get_object_value(context, 'customer_name')} - {opportunity_stage}"),
        ("owner", get_object_value(context, "owner")),
        ("due_at", isoformat_or_none(follow_up_time)),
        ("channel", channel),
        ("draft_message", draft_message),
        ("checklist", ["确认客户核心需求是否完整记录", "按推荐动作发送材料或推进下一次沟通", "更新飞书多维表格中的商机状态"]),
    ])
    pre_meeting_brief = OrderedDict([
        ("next_meeting_at", isoformat_or_none(next_meeting_time)),
        ("trigger_at", isoformat_or_none(brief_trigger)),
        ("headline", f"{get_object_value(context, 'customer_name')} 会前行动简报"),
        ("opening_script", opening_script),
        ("key_points", key_points),
        ("watchouts", list(OrderedDict.fromkeys(concern_lines))),
        ("materials_to_prepare", ["客户画像摘要", "上次会议结论", "与本次需求对应的方案/案例/报价材料"]),
    ])
    customer_table_row = OrderedDict([
        ("客户ID", get_object_value(context, "customer_id")),
        ("客户名称", get_object_value(context, "customer_name")),
        ("客户公司", company_name),
        ("行业", industry_name),
        ("MBTI", customer_profile_update["mbti"]),
        ("是否单身", customer_profile_update["single_status"]),
        ("沟通风格", join_values(customer_profile_update["communication_style"])),
        ("成交阻力", customer_profile_update["resistance_level"]),
        ("价格敏感程度", customer_profile_update["price_sensitivity"]),
        ("风险顾虑", join_values(customer_profile_update["risk_concerns"])),
        ("客户画像摘要", customer_profile_update["profile_summary"]),
        ("客户负责人", get_object_value(context, "owner")),
        ("最后更新时间", isoformat_or_none(meeting_time)),
        ("数据来源", source_channel),
    ])
    customer_table_row, preserved_customer_fields = merge_row_preserving_existing_values(customer_table_row, existing_customer_fields)
    customer_table_row["客户画像摘要"] = build_customer_profile_summary(
        customer_table_row.get("客户名称"),
        opportunity_stage,
        customer_table_row.get("MBTI"),
        customer_table_row.get("是否单身"),
        customer_table_row.get("沟通风格"),
        customer_table_row.get("成交阻力"),
        customer_table_row.get("价格敏感程度"),
        customer_table_row.get("风险顾虑"),
    )
    opportunity_snapshot_row = OrderedDict([
        ("商机ID", get_object_value(context, "opportunity_id")),
        ("客户ID", get_object_value(context, "customer_id")),
        ("客户名称", get_object_value(context, "customer_name")),
        ("客户公司", company_name),
        ("机会名称", opportunity_update["opportunity_name"]),
        ("商机描述", opportunity_update["opportunity_description"]),
        ("当前阶段", opportunity_update["opportunity_stage"]),
        ("Lead Score", opportunity_update["lead_score"]),
        ("意向等级", opportunity_update["intent_level"]),
        ("高净值优先", opportunity_update["high_value_flag"]),
        ("销售区域", opportunity_update["sales_region"]),
        ("业务价值", opportunity_update["business_value"]),
        ("推荐动作", opportunity_update["recommended_action"]),
        ("最新进展", opportunity_update["latest_progress"]),
        ("下次跟进时间", opportunity_update["next_follow_up_at"]),
        ("最近会议时间", meeting_record["meeting_time"]),
        ("商机负责人", get_object_value(context, "owner")),
        ("数据来源", source_channel),
    ])
    feishu_payload = OrderedDict([
        ("customer_table", OrderedDict([("mode", "upsert"), ("key_field", "客户ID"), ("key", get_object_value(context, "customer_id")), ("update_fields", customer_table_row)])),
        ("opportunity_snapshot_table", OrderedDict([("mode", "append"), ("append_row", opportunity_snapshot_row)])),
    ])
    crm_packet = OrderedDict([
        ("input", OrderedDict([("transcript_path", resolve_str(transcript_path)), ("context_path", resolve_str(context_path)), ("customer_id", get_object_value(context, "customer_id")), ("opportunity_id", get_object_value(context, "opportunity_id"))])),
        ("meeting", meeting_record),
        ("customer_profile_update", customer_profile_update),
        ("opportunity_update", opportunity_update),
        ("follow_up_task", follow_up_task),
        ("pre_meeting_brief", pre_meeting_brief),
        ("customer_table_row", customer_table_row),
        ("customer_preserved_fields", preserved_customer_fields),
        ("opportunity_snapshot_row", opportunity_snapshot_row),
        ("feishu_bitable_payload", feishu_payload),
    ])

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "meeting_record.json", meeting_record)
    write_json(output / "customer_profile_update.json", customer_profile_update)
    write_json(output / "opportunity_update.json", opportunity_update)
    write_json(output / "follow_up_task.json", follow_up_task)
    write_json(output / "pre_meeting_brief.json", pre_meeting_brief)
    write_json(output / "customer_table_row.json", customer_table_row)
    write_json(output / "opportunity_snapshot_row.json", opportunity_snapshot_row)
    write_json(output / "crm_packet.json", crm_packet)
    return crm_packet


def build_example_block(example: dict[str, Any]) -> str:
    return "\r\n".join([
        f"### 示例：{example['name']}",
        f"任务提示：{example['task_hint']}",
        "",
        "输入 context:",
        "```json",
        json.dumps(example["input"]["context"], ensure_ascii=False, indent=2),
        "```",
        "",
        "输入 transcript:",
        "```text",
        example["input"]["transcript"],
        "```",
        "",
        "参考输出:",
        "```json",
        json.dumps(example["output"], ensure_ascii=False, indent=2),
        "```",
    ])


def build_llm_prompt(transcript_path: str | Path, context_path: str | Path, output_dir: str | Path, example_names: list[str] | None = None) -> dict[str, Any]:
    names = example_names or ["zhongguoyidong_ops_rich", "ningdeshidai_service_rich"]
    template = read_text(skill_root() / "references" / "llm_prompt_template.md")
    schema = read_text(skill_root() / "references" / "llm_output_schema.md")
    context_json = read_text(context_path)
    transcript_text = read_text(transcript_path)
    example_blocks = [build_example_block(read_json(skill_root() / "assets" / "few_shot" / f"{name}.json")) for name in names]
    system_prompt = "\r\n".join([template, "", "以下是输出 schema，请严格遵守：", "", schema]).strip()
    user_prompt = "\r\n".join([
        "以下是 few-shot 示例，请学习其抽取方式、阶段判断标准和输出风格：",
        "",
        "\r\n\r\n".join(example_blocks),
        "",
        "现在请处理新的输入。",
        "",
        "输入 context:",
        "```json",
        context_json,
        "```",
        "",
        "输入 transcript:",
        "```text",
        transcript_text,
        "```",
        "",
        "请只输出 JSON，不要输出解释。",
    ]).strip()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prompt_package = OrderedDict([
        ("system_prompt", system_prompt),
        ("user_prompt", user_prompt),
        ("examples", names),
        ("transcript_path", resolve_str(transcript_path)),
        ("context_path", resolve_str(context_path)),
    ])
    write_json(output / "prompt_package.json", prompt_package)
    write_text(output / "system_prompt.txt", system_prompt)
    write_text(output / "user_prompt.txt", user_prompt)
    return prompt_package


def assert_has_property(obj: dict[str, Any], property_name: str, scope: str) -> None:
    if obj is None:
        raise ValueError(f"Missing object [{scope}] in model output.")
    if property_name not in obj:
        raise ValueError(f"Missing property [{scope}.{property_name}] in model output.")


def validate_datetime(value: Any, field_name: str) -> None:
    if value is None or not str(value).strip():
        return
    try:
        datetime.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Invalid datetime in [{field_name}]: {value}") from exc


def validate_model_output(model_output_path: str | Path) -> dict[str, Any]:
    model = read_json(model_output_path)
    for top in ["meeting", "customer_profile_update", "opportunity_update", "follow_up_task", "pre_meeting_brief"]:
        assert_has_property(model, top, "root")
    for field in ["customer_id", "customer_name", "company_name", "meeting_time", "summary"]:
        assert_has_property(model["meeting"], field, "meeting")
    for field in ["customer_id", "company_name", "industry", "mbti", "single_status", "resistance_level", "price_sensitivity", "profile_summary"]:
        assert_has_property(model["customer_profile_update"], field, "customer_profile_update")
    for field in ["opportunity_id", "opportunity_name", "opportunity_description", "sales_region", "business_value", "lead_score", "intent_level", "opportunity_stage", "high_value_flag", "recommended_action", "latest_progress"]:
        assert_has_property(model["opportunity_update"], field, "opportunity_update")
    for field in ["task_title", "owner", "channel", "draft_message", "checklist"]:
        assert_has_property(model["follow_up_task"], field, "follow_up_task")
    for field in ["headline", "opening_script", "key_points", "watchouts", "materials_to_prepare"]:
        assert_has_property(model["pre_meeting_brief"], field, "pre_meeting_brief")
    if model["opportunity_update"]["intent_level"] not in VALID_INTENT_LEVELS:
        raise ValueError(f"Invalid opportunity_update.intent_level: {model['opportunity_update']['intent_level']}")
    if model["opportunity_update"]["opportunity_stage"] not in VALID_STAGES:
        raise ValueError(f"Invalid opportunity_update.opportunity_stage: {model['opportunity_update']['opportunity_stage']}")
    channel = model["follow_up_task"].get("channel")
    if channel and channel not in VALID_CHANNELS:
        raise ValueError(f"Invalid follow_up_task.channel: {channel}")
    lead_score = int(model["opportunity_update"]["lead_score"])
    if lead_score < 0 or lead_score > 100:
        raise ValueError("lead_score must be between 0 and 100.")
    validate_datetime(model["meeting"].get("meeting_time"), "meeting.meeting_time")
    validate_datetime(model["opportunity_update"].get("next_follow_up_at"), "opportunity_update.next_follow_up_at")
    validate_datetime(model["follow_up_task"].get("due_at"), "follow_up_task.due_at")
    validate_datetime(model["pre_meeting_brief"].get("next_meeting_at"), "pre_meeting_brief.next_meeting_at")
    validate_datetime(model["pre_meeting_brief"].get("trigger_at"), "pre_meeting_brief.trigger_at")
    return model


def convert_model_output_to_crm(model_output_path: str | Path, output_dir: str | Path, context_path: str | Path | None = None) -> dict[str, Any]:
    model = validate_model_output(model_output_path)
    context = read_json(context_path) if context_path and Path(context_path).exists() else None
    source_channel = get_object_value(context, "channel", "LLM 结构化输出")
    owner = get_object_value(context, "owner", model["follow_up_task"]["owner"])
    existing_customer_fields = get_object_value(context, "existing_customer_fields", {}) or {}
    customer_table_row = OrderedDict([
        ("客户ID", model["customer_profile_update"]["customer_id"]),
        ("客户名称", model["meeting"]["customer_name"]),
        ("客户公司", model["customer_profile_update"]["company_name"]),
        ("行业", model["customer_profile_update"]["industry"]),
        ("MBTI", get_object_value(model["customer_profile_update"], "mbti", "未明确")),
        ("是否单身", get_object_value(model["customer_profile_update"], "single_status", "未明确")),
        ("沟通风格", join_values(model["customer_profile_update"].get("communication_style"))),
        ("成交阻力", get_object_value(model["customer_profile_update"], "resistance_level", "未明确")),
        ("价格敏感程度", get_object_value(model["customer_profile_update"], "price_sensitivity", "未明确")),
        ("风险顾虑", join_values(model["customer_profile_update"].get("risk_concerns"))),
        ("客户画像摘要", model["customer_profile_update"]["profile_summary"]),
        ("客户负责人", owner),
        ("最后更新时间", model["meeting"]["meeting_time"]),
        ("数据来源", source_channel),
    ])
    customer_table_row, preserved_customer_fields = merge_row_preserving_existing_values(customer_table_row, existing_customer_fields)
    customer_table_row["客户画像摘要"] = build_customer_profile_summary(
        customer_table_row.get("客户名称"),
        get_object_value(model["opportunity_update"], "opportunity_stage", "当前"),
        customer_table_row.get("MBTI"),
        customer_table_row.get("是否单身"),
        customer_table_row.get("沟通风格"),
        customer_table_row.get("成交阻力"),
        customer_table_row.get("价格敏感程度"),
        customer_table_row.get("风险顾虑"),
    )
    opportunity_snapshot_row = OrderedDict([
        ("商机ID", model["opportunity_update"]["opportunity_id"]),
        ("客户ID", model["meeting"]["customer_id"]),
        ("客户名称", model["meeting"]["customer_name"]),
        ("客户公司", model["meeting"]["company_name"]),
        ("机会名称", model["opportunity_update"]["opportunity_name"]),
        ("商机描述", model["opportunity_update"]["opportunity_description"]),
        ("当前阶段", model["opportunity_update"]["opportunity_stage"]),
        ("Lead Score", model["opportunity_update"]["lead_score"]),
        ("意向等级", model["opportunity_update"]["intent_level"]),
        ("高净值优先", model["opportunity_update"]["high_value_flag"]),
        ("销售区域", model["opportunity_update"]["sales_region"]),
        ("业务价值", model["opportunity_update"]["business_value"]),
        ("推荐动作", model["opportunity_update"]["recommended_action"]),
        ("最新进展", model["opportunity_update"]["latest_progress"]),
        ("下次跟进时间", model["opportunity_update"].get("next_follow_up_at")),
        ("最近会议时间", model["meeting"]["meeting_time"]),
        ("商机负责人", owner),
        ("数据来源", source_channel),
    ])
    crm_packet = OrderedDict([
        ("input", OrderedDict([("model_output_path", resolve_str(model_output_path)), ("context_path", resolve_str(context_path) if context_path and Path(context_path).exists() else None)])),
        ("meeting", model["meeting"]),
        ("customer_profile_update", model["customer_profile_update"]),
        ("opportunity_update", model["opportunity_update"]),
        ("follow_up_task", model["follow_up_task"]),
        ("pre_meeting_brief", model["pre_meeting_brief"]),
        ("customer_table_row", customer_table_row),
        ("customer_preserved_fields", preserved_customer_fields),
        ("opportunity_snapshot_row", opportunity_snapshot_row),
        (
            "feishu_bitable_payload",
            OrderedDict([
                (
                    "customer_table",
                    OrderedDict([
                        ("mode", "upsert"),
                        ("key_field", "客户ID"),
                        ("key", model["customer_profile_update"]["customer_id"]),
                        ("update_fields", customer_table_row),
                    ]),
                ),
                (
                    "opportunity_snapshot_table",
                    OrderedDict([
                        ("mode", "append"),
                        ("append_row", opportunity_snapshot_row),
                    ]),
                ),
            ]),
        ),
    ])
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "meeting_record.json", model["meeting"])
    write_json(output / "customer_profile_update.json", model["customer_profile_update"])
    write_json(output / "opportunity_update.json", model["opportunity_update"])
    write_json(output / "follow_up_task.json", model["follow_up_task"])
    write_json(output / "pre_meeting_brief.json", model["pre_meeting_brief"])
    write_json(output / "customer_table_row.json", customer_table_row)
    write_json(output / "opportunity_snapshot_row.json", opportunity_snapshot_row)
    write_json(output / "crm_packet.json", crm_packet)
    return crm_packet


def run_sample_tests(output_root: str | Path) -> None:
    sample_dir = skill_root() / "assets" / "samples"
    expected_dir = skill_root() / "assets" / "expected"
    context_files = sorted(sample_dir.glob("*_context.json"))
    if not context_files:
        raise ValueError(f"No sample contexts found in {sample_dir}")
    failures = 0
    checked = 0
    for context_file in context_files:
        sample_name = context_file.stem.replace("_context", "")
        transcript_path = sample_dir / f"{sample_name}_transcript.txt"
        expected_path = expected_dir / f"{sample_name}.json"
        out_dir = Path(output_root) / sample_name
        if not transcript_path.exists():
            raise FileNotFoundError(f"Missing transcript for sample {sample_name}")
        if not expected_path.exists():
            print(f"[SKIP] {sample_name} (missing expected assertion file)")
            continue
        checked += 1
        packet = process_transcript(transcript_path, context_file, out_dir)
        expected = read_json(expected_path)
        errors: list[str] = []
        if packet["opportunity_update"]["intent_level"] != expected["intent_level"]:
            errors.append(f"intent_level expected [{expected['intent_level']}] actual [{packet['opportunity_update']['intent_level']}]")
        if int(packet["opportunity_update"]["lead_score"]) < int(expected["min_lead_score"]):
            errors.append(f"lead_score expected >= {expected['min_lead_score']} actual [{packet['opportunity_update']['lead_score']}]")
        if packet["opportunity_update"]["opportunity_stage"] != expected["opportunity_stage"]:
            errors.append(f"opportunity_stage expected [{expected['opportunity_stage']}] actual [{packet['opportunity_update']['opportunity_stage']}]")
        if bool(packet["opportunity_update"]["high_value_flag"]) != bool(expected["high_value_flag"]):
            errors.append(f"high_value_flag expected [{expected['high_value_flag']}] actual [{packet['opportunity_update']['high_value_flag']}]")
        all_tags: list[str] = []
        customer_profile = packet["customer_profile_update"]
        scalar_tags = [
            customer_profile.get("mbti"),
            customer_profile.get("single_status"),
            customer_profile.get("resistance_level"),
            customer_profile.get("price_sensitivity"),
        ]
        for tag in scalar_tags:
            text = str(tag).strip() if tag is not None else ""
            if text and text not in all_tags:
                all_tags.append(text)
        for group in ["risk_concerns", "communication_style"]:
            for tag in customer_profile.get(group, []):
                if tag not in all_tags:
                    all_tags.append(tag)
        for tag in expected["required_tags"]:
            if tag not in all_tags:
                errors.append(f"missing required tag [{tag}]")
        required_channel = expected.get("required_channel")
        if required_channel and packet["follow_up_task"]["channel"] != required_channel:
            errors.append(f"required_channel expected [{required_channel}] actual [{packet['follow_up_task']['channel']}]")
        for snippet in expected["summary_must_include"]:
            if snippet not in packet["meeting"]["summary"]:
                errors.append(f"summary missing snippet [{snippet}]")
        if bool(expected["pre_meeting_should_exist"]) != bool(packet["pre_meeting_brief"].get("next_meeting_at")):
            errors.append(f"pre_meeting existence expected [{expected['pre_meeting_should_exist']}] actual [{bool(packet['pre_meeting_brief'].get('next_meeting_at'))}]")
        if errors:
            failures += 1
            print(f"[FAIL] {sample_name}")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"[PASS] {sample_name}")
    if checked == 0:
        print("[SKIP] No sample tests were executed because no expected assertion files were found.")
        return
    if failures:
        raise RuntimeError(f"{failures} sample test(s) failed.")


def run_feishu_pipeline_tests(output_root: str | Path) -> None:
    raw_dir = skill_root() / "assets" / "feishu_raw"
    expected_dir = skill_root() / "assets" / "expected"
    raw_files = sorted(raw_dir.glob("*.json"))
    if not raw_files:
        raise ValueError(f"No Feishu raw sample files found in {raw_dir}")
    failures = 0
    checked = 0
    for raw_file in raw_files:
        sample_name = raw_file.stem
        expected_path = expected_dir / f"{sample_name}.json"
        if not expected_path.exists():
            print(f"[SKIP] {sample_name} (missing expected assertion file)")
            continue
        checked += 1
        sample_output = Path(output_root) / sample_name
        build_output = sample_output / "build"
        process_output = sample_output / "process"
        build_context_from_feishu(raw_file, build_output)
        packet = process_transcript(build_output / "transcript.txt", build_output / "context.json", process_output)
        expected = read_json(expected_path)
        errors: list[str] = []
        if packet["opportunity_update"]["intent_level"] != expected["intent_level"]:
            errors.append(f"intent_level expected [{expected['intent_level']}] actual [{packet['opportunity_update']['intent_level']}]")
        if int(packet["opportunity_update"]["lead_score"]) < int(expected["min_lead_score"]):
            errors.append(f"lead_score expected >= {expected['min_lead_score']} actual [{packet['opportunity_update']['lead_score']}]")
        if packet["opportunity_update"]["opportunity_stage"] != expected["opportunity_stage"]:
            errors.append(f"opportunity_stage expected [{expected['opportunity_stage']}] actual [{packet['opportunity_update']['opportunity_stage']}]")
        if errors:
            failures += 1
            print(f"[FAIL] {sample_name}")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"[PASS] {sample_name}")
    if checked == 0:
        print("[SKIP] No Feishu pipeline tests were executed because no expected assertion files were found.")
        return
    if failures:
        raise RuntimeError(f"{failures} Feishu pipeline test(s) failed.")


def run_model_output_tests(output_root: str | Path) -> None:
    model_dir = skill_root() / "runtime" / "llm_outputs"
    sample_dir = skill_root() / "assets" / "samples"
    model_files = sorted(model_dir.rglob("model_output.json"))
    if not model_files:
        raise ValueError(f"No model_output.json files found under {model_dir}")
    for model_file in model_files:
        sample_name = model_file.parent.name
        context_path = sample_dir / f"{sample_name}_context.json"
        out_dir = Path(output_root) / sample_name
        validate_model_output(model_file)
        packet = convert_model_output_to_crm(model_file, out_dir, context_path if context_path.exists() else None)
        if packet["feishu_bitable_payload"].get("customer_table") is None:
            raise RuntimeError(f"customer_table missing in {sample_name}")
        if packet["feishu_bitable_payload"].get("opportunity_snapshot_table") is None:
            raise RuntimeError(f"opportunity_snapshot_table missing in {sample_name}")
        print(f"[PASS] {sample_name}")


def run_customer_journey(manifest_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rounds: list[dict[str, Any]] = []
    for item in manifest["rounds"]:
        round_name = item["round_id"]
        context_path = skill_root() / item["context_path"]
        transcript_path = skill_root() / item["transcript_path"]
        round_output = output / round_name
        packet = process_transcript(transcript_path, context_path, round_output)
        rounds.append(OrderedDict([
            ("round_id", round_name),
            ("label", item["label"]),
            ("meeting_time", packet["meeting"]["meeting_time"]),
            ("lead_score", packet["opportunity_update"]["lead_score"]),
            ("intent_level", packet["opportunity_update"]["intent_level"]),
            ("opportunity_stage", packet["opportunity_update"]["opportunity_stage"]),
            ("high_value_flag", packet["opportunity_update"]["high_value_flag"]),
            ("recommended_action", packet["opportunity_update"]["recommended_action"]),
            ("summary", packet["meeting"]["summary"]),
            ("next_follow_up_at", packet["opportunity_update"]["next_follow_up_at"]),
        ]))
    sorted_rounds = sorted(rounds, key=lambda item: datetime.fromisoformat(item["meeting_time"]))
    progression_notes: list[str] = []
    for i, current in enumerate(sorted_rounds):
        if i == 0:
            progression_notes.append(f"第1轮为{current['label']}，阶段：{current['opportunity_stage']}，Lead Score {current['lead_score']}")
            continue
        previous = sorted_rounds[i - 1]
        delta = int(current["lead_score"]) - int(previous["lead_score"])
        direction = "提升" if delta > 0 else ("下降" if delta < 0 else "持平")
        delta_text = f" {delta}" if delta != 0 else ""
        progression_notes.append(f"{current['label']} 从 {previous['opportunity_stage']} -> {current['opportunity_stage']}，Lead Score {current['lead_score']}（{direction}{delta_text}）")
    journey = OrderedDict([
        ("customer_id", manifest["customer_id"]),
        ("customer_name", manifest["customer_name"]),
        ("opportunity_id", manifest["opportunity_id"]),
        ("total_rounds", len(sorted_rounds)),
        ("journey_theme", manifest["journey_theme"]),
        ("stage_path", [item["opportunity_stage"] for item in sorted_rounds]),
        ("latest_stage", sorted_rounds[-1]["opportunity_stage"]),
        ("latest_lead_score", sorted_rounds[-1]["lead_score"]),
        ("latest_intent", sorted_rounds[-1]["intent_level"]),
        ("progression_notes", progression_notes),
        ("rounds", sorted_rounds),
    ])
    write_json(output / "journey_summary.json", journey)
    return journey


def ingest_feishu_raw_to_bitable(
    raw_input_path: str | Path,
    output_dir: str | Path,
    config_path: str | Path | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
    app_token_or_url: str | None = None,
    customer_table_id: str | None = None,
    opportunity_table_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir)
    build_output = output / "build"
    process_output = output / "process"
    sync_output = output / "sync"

    build_result = build_context_from_feishu(raw_input_path, build_output)
    crm_packet = process_transcript(build_output / "transcript.txt", build_output / "context.json", process_output)
    sync_result = sync_crm_packet_to_feishu(
        process_output / "crm_packet.json",
        sync_output,
        config_path,
        app_id,
        app_secret,
        app_token_or_url,
        customer_table_id,
        opportunity_table_id,
        dry_run,
    )
    result = OrderedDict([
        ("raw_input_path", resolve_str(raw_input_path)),
        ("build_result_path", resolve_str(build_output / "build_result.json")),
        ("crm_packet_path", resolve_str(process_output / "crm_packet.json")),
        ("sync_result_path", resolve_str(sync_output / "feishu_sync_result.json")),
        ("customer_id", crm_packet["customer_table_row"].get("客户ID")),
        ("opportunity_id", crm_packet["opportunity_snapshot_row"].get("商机ID")),
        ("customer_action", sync_result.get("customer_action")),
        ("opportunity_action", sync_result.get("opportunity_action")),
    ])
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "ingest_result.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CRM Assistant Python CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("process-transcript")
    p.add_argument("--transcript-path", required=True)
    p.add_argument("--context-path", required=True)
    p.add_argument("--output-dir", required=True)

    p = sub.add_parser("build-context-from-feishu")
    p.add_argument("--raw-input-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--context-file-name", default="context.json")
    p.add_argument("--transcript-file-name", default="transcript.txt")

    p = sub.add_parser("build-llm-prompt")
    p.add_argument("--transcript-path", required=True)
    p.add_argument("--context-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--example-names", nargs="*", default=["zhongguoyidong_ops_rich", "ningdeshidai_service_rich"])

    p = sub.add_parser("validate-model-output")
    p.add_argument("--model-output-path", required=True)

    p = sub.add_parser("convert-model-output")
    p.add_argument("--model-output-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--context-path")

    p = sub.add_parser("run-sample-tests")
    p.add_argument("--output-root", default=str(skill_root() / "runtime"))

    p = sub.add_parser("run-feishu-pipeline-tests")
    p.add_argument("--output-root", default=str(skill_root() / "runtime" / "feishu_pipeline_py"))

    p = sub.add_parser("run-model-output-tests")
    p.add_argument("--output-root", default=str(skill_root() / "runtime" / "from_model_py"))

    p = sub.add_parser("run-customer-journey")
    p.add_argument("--manifest-path", required=True)
    p.add_argument("--output-dir", required=True)

    p = sub.add_parser("inspect-feishu-bitable")
    p.add_argument("--app-id")
    p.add_argument("--app-secret")
    p.add_argument("--app-token-or-url", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--table-id")

    p = sub.add_parser("sync-feishu-bitable")
    p.add_argument("--crm-packet-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--config-path")
    p.add_argument("--app-id")
    p.add_argument("--app-secret")
    p.add_argument("--app-token-or-url")
    p.add_argument("--customer-table-id")
    p.add_argument("--opportunity-table-id")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("ingest-feishu-raw-to-bitable")
    p.add_argument("--raw-input-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--config-path")
    p.add_argument("--app-id")
    p.add_argument("--app-secret")
    p.add_argument("--app-token-or-url")
    p.add_argument("--customer-table-id")
    p.add_argument("--opportunity-table-id")
    p.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "process-transcript":
        process_transcript(args.transcript_path, args.context_path, args.output_dir)
        print(f"CRM packet generated at: {args.output_dir}")
    elif args.command == "build-context-from-feishu":
        build_context_from_feishu(args.raw_input_path, args.output_dir, args.context_file_name, args.transcript_file_name)
        print(f"Feishu raw input converted at: {args.output_dir}")
    elif args.command == "build-llm-prompt":
        build_llm_prompt(args.transcript_path, args.context_path, args.output_dir, args.example_names)
        print(f"LLM prompt package generated at: {args.output_dir}")
    elif args.command == "validate-model-output":
        validate_model_output(args.model_output_path)
        print(f"Model output is valid: {args.model_output_path}")
    elif args.command == "convert-model-output":
        convert_model_output_to_crm(args.model_output_path, args.output_dir, args.context_path)
        print(f"Converted model output to CRM artifacts at: {args.output_dir}")
    elif args.command == "run-sample-tests":
        run_sample_tests(args.output_root)
        print(f"All sample tests passed. Output root: {args.output_root}")
    elif args.command == "run-feishu-pipeline-tests":
        run_feishu_pipeline_tests(args.output_root)
        print(f"All Feishu pipeline tests passed. Output root: {args.output_root}")
    elif args.command == "run-model-output-tests":
        run_model_output_tests(args.output_root)
        print(f"All model output tests passed. Output root: {args.output_root}")
    elif args.command == "run-customer-journey":
        run_customer_journey(args.manifest_path, args.output_dir)
        print(f"Customer journey generated at: {args.output_dir}")
    elif args.command == "inspect-feishu-bitable":
        inspect_feishu_bitable(args.app_id, args.app_secret, args.app_token_or_url, args.output_dir, args.table_id)
        print(f"Feishu bitable inspection generated at: {args.output_dir}")
    elif args.command == "sync-feishu-bitable":
        sync_crm_packet_to_feishu(
            args.crm_packet_path,
            args.output_dir,
            args.config_path,
            args.app_id,
            args.app_secret,
            args.app_token_or_url,
            args.customer_table_id,
            args.opportunity_table_id,
            args.dry_run,
        )
        print(f"Feishu bitable sync result generated at: {args.output_dir}")
    elif args.command == "ingest-feishu-raw-to-bitable":
        ingest_feishu_raw_to_bitable(
            args.raw_input_path,
            args.output_dir,
            args.config_path,
            args.app_id,
            args.app_secret,
            args.app_token_or_url,
            args.customer_table_id,
            args.opportunity_table_id,
            args.dry_run,
        )
        print(f"Feishu raw input fully ingested to bitable at: {args.output_dir}")


if __name__ == "__main__":
    main()
