from dataclasses import dataclass

from app.core.config import settings


DANGEROUS_TERMS = (
    "kill",
    "evil",
    "hack",
    "attack",
    "exploit",
    "malware",
    "木马",
    "病毒",
    "攻击",
    "入侵",
    "绕过",
    "注入攻击",
)

SAFE_REFUSAL_MESSAGE = (
    "抱歉，这个请求可能涉及攻击、入侵、恶意软件或绕过安全机制等风险内容，我不能提供相关操作步骤。"
    "如果你是在做安全学习，我可以帮助你了解防御思路、合规的安全测试流程或基础安全概念。"
)


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str
    matched_terms: list[str]


def check_user_input(message: str) -> GuardrailResult:
    if not settings.guardrail_enabled:
        return GuardrailResult(allowed=True, reason="guardrail_disabled", matched_terms=[])

    normalized = (message or "").casefold()
    matched_terms = [term for term in DANGEROUS_TERMS if term.casefold() in normalized]
    if matched_terms:
        return GuardrailResult(
            allowed=False,
            reason="dangerous_input_detected",
            matched_terms=matched_terms,
        )

    return GuardrailResult(allowed=True, reason="ok", matched_terms=[])
