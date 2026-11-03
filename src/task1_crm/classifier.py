"""Rule-based enquiry classifier for CRM Task 1.

Classifies enquiries into categories using keyword matching and pattern
analysis.  This is the CPU-only, zero-dependency classifier — no LLM needed.
It can be hot-swapped for an LLM classifier later via the same interface.

Categories:
- sales_lead:       Genuine interest in purchasing courses/training
- support_issue:    Existing customer with a problem (payment, refund …)
- spam:             Unsolicited promotional content
- job_seeker:       Looking for employment, not a customer
- general_inquiry:  Generic questions not directly about purchasing
"""

import re
from dataclasses import dataclass
from .text_processing import key_text, detect_language


@dataclass
class ClassificationResult:
    """Immutable result of enquiry classification."""
    category: str
    sub_category: str
    priority: str
    confidence: float
    product_interest: str
    sender_role: str
    company_name: str
    is_corporate: bool
    estimated_deal_size: str
    needs_follow_up: bool
    suggested_action: str
    auto_response: str
    reasoning: str


# ---------------------------------------------------------------------------
# Keyword / pattern dictionaries
# ---------------------------------------------------------------------------

SPAM_PATTERNS = [
    r"earn\s+\d+\s+usd", r"crypto\s+signal", r"bit\.ly",
    r"click\s+now", r"free\s+money", r"investment\s+opportunity",
    r"mlm", r"pyramid", r"guaranteed\s+income",
]

JOB_SEEKER_PATTERNS = [
    r"looking\s+for\s+a?\s*job",
    r"where\s+do\s+i\s+apply",
    r"apply\s+for\s+(a\s+)?(position|role|job)",
    r"(vacancy|vacancies)\b",
    r"\b(hiring|recruit)\b",
    r"চাকরি\s*খুঁজ",
    # Bangla "job as intern / AI intern"
    r"job\s+as\s+a?n?\s*(ai\s+)?intern",
]

# Support: patterns that indicate an *existing* customer with a problem.
SUPPORT_PATTERNS = [
    # Bangla: "paid but no confirmation"
    r"(পেমেন্ট|পে মেন্ট).*(কনফার্মেশন|পাইনি|পাই\s*নি)",
    r"(paid|payment).*(no|not|didn).*(confirm|receipt|receiv)",
    # Refund / cancel
    r"(refund|money\s*back|cancel\s*(my|his|her)\s*(enrol|registr))",
    r"(রিফান্ড|টাকা\s*ফেরত|বাতিল)",
    # Angry escalation
    r"(upset|angry|frustrated|post\s+(about|on)\s+facebook)",
]

# Words that strongly indicate support, needing >= 2 hits
SUPPORT_KEYWORDS = {
    # English
    "paid", "refund", "cancel", "confirmation", "receipt",
    "problem", "issue", "complaint", "money back", "bkash",
    # Bangla
    "পেমেন্ট", "কনফার্মেশন", "রিফান্ড", "বাতিল", "বিকাশ", "সমস্যা",
}

# Sales: words that show purchase / enrolment interest
SALES_KEYWORDS = {
    # English
    "price", "cost", "fee", "enroll", "enrol", "register", "join",
    "bootcamp", "fellowship", "training", "programme", "program",
    "discount", "instalment", "installment", "payment plan",
    "quote", "proposal",
    # Bangla
    "দাম", "মূল্য", "ভর্তি", "রেজিস্ট্রেশন", "ফেলোশিপ",
    "বুটক্যাম্প", "ট্রেনিং", "ডিসকাউন্ট", "ছাড়", "কিস্তি",
}

# Explicit enrolment intent (Bangla/Banglish) — treated as a sales signal
ENROL_PATTERNS = [
    r"ভর্তি\s*হতে\s*চাই",         # want to enrol
    r"(enroll|enrol|register)\s*(want|like|please)",
    r"(join|ভর্তি|রেজিস্ট্রেশন).*(করতে|হতে|চাই)",
    r"pay\s+in\s+(two|2|three|3)\s+instal",
    r"instalment.*fellowship",
    r"fellowship.*instalment",
]

# Corporate indicators
CORPORATE_INDICATORS = [
    r"\d+\s*[-–]?\s*(person|people|employee|staff|member|কর্মী|জন)",
    r"(company|team|employees|staff|corporate|enterprise)",
    r"(factory|bank|firm|group)",
    r"(managing\s+director|md\b|ceo|coo|hr\b|gm\b)",
    r"(onsite|on-?site|কোম্পানি|প্রতিষ্ঠান)",
    r"quote\s+(for|to)\s+train",
]

# Patterns that look like a job question ("will I get a job?") — NOT job seeking
JOB_QUESTION_PATTERNS = [
    r"(korle|করলে)\s*(job|চাকরি)\s*(pabo|পাব|hobe|হবে)",
    r"course\s+korle\s+job",
    r"job\s+(pabo|পাব|hobe|হবে)",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _match_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _keyword_score(text: str, keywords: set[str]) -> int:
    text_lower = key_text(text)
    return sum(1 for kw in keywords if kw in text_lower)


def _extract_company(sender_name: str) -> str:
    m = re.search(r"\(([^)]+)\)", sender_name)
    if m:
        return m.group(1).strip()
    return ""


def _extract_role(sender_name: str) -> str:
    m = re.search(r"\(([^,)]+)", sender_name)
    if m:
        candidate = m.group(1).strip()
        roles = ["director", "manager", "head", "owner", "hr", "ceo",
                 "md", "lead", "officer", "founder", "coo"]
        if any(r in candidate.lower() for r in roles):
            return candidate
    return ""


def _deal_size(message: str, is_corp: bool) -> str:
    if not is_corp:
        return "individual"
    m = re.search(r"(\d+)\s*(?:person|people|employee|staff|member|কর্মী|জন)",
                  message, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        return "large" if n >= 100 else ("medium" if n >= 20 else "small")
    return "medium"


def _product_interest(message: str) -> str:
    checks = [
        (r"bootcamp|বুটক্যাম্প", "3-day bootcamp"),
        (r"fellowship|ফেলোশিপ", "fellowship program"),
        (r"masterclass|মাস্টারক্লাস", "free masterclass"),
        (r"course|কোর্স", "AI course"),
        (r"training|ট্রেনিং", "AI training"),
    ]
    for pattern, label in checks:
        if re.search(pattern, message, re.IGNORECASE):
            return label
    return ""


def _auto_response(language: str, category: str) -> str:
    if category == "spam":
        return ""
    if category == "job_seeker":
        return "Thank you for your interest! Please visit our careers page or email hr@biai.com for job opportunities."
    if category == "support_issue":
        if language == "bangla":
            return "আপনার বার্তা পেয়েছি। আমাদের সাপোর্ট টিম শীঘ্রই যোগাযোগ করবে।"
        return "We have received your message and our support team will get back to you shortly."
    # sales_lead / general_inquiry
    if language == "bangla":
        return "আপনার বার্তার জন্য ধন্যবাদ! আমাদের টিম শীঘ্রই আপনার সাথে যোগাযোগ করবে।"
    if language == "banglish":
        return "Apnar message er jonno dhonnobad! Amader team shighroi apnar sathe jogajog korbe."
    return "Thank you for your interest! Our team will reach out to you shortly with all the details."


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------

def classify_enquiry(
    enquiry_id: int,
    channel: str,
    sender_name: str,
    phone: str,
    message: str,
) -> ClassificationResult:
    """Classify a single CRM enquiry using a deterministic decision tree.

    Priority chain:  SPAM → JOB_SEEKER → SUPPORT → SALES_LEAD → GENERAL.
    """
    language = detect_language(message)
    product = _product_interest(message)
    company = _extract_company(sender_name)
    role = _extract_role(sender_name)
    is_corp = _match_any(message, CORPORATE_INDICATORS) or _match_any(sender_name, CORPORATE_INDICATORS)
    deal = _deal_size(message, is_corp)

    # ---- 1. SPAM ----
    if _match_any(message, SPAM_PATTERNS):
        return ClassificationResult(
            category="spam", sub_category="promotional_spam",
            priority="none", confidence=0.95,
            product_interest="", sender_role="", company_name="",
            is_corporate=False, estimated_deal_size="",
            needs_follow_up=False,
            suggested_action="Mark as spam and block sender.",
            auto_response="",
            reasoning="Spam patterns detected (crypto, earn USD, bit.ly).",
        )

    # ---- 2. JOB SEEKER ----
    # Guard: "course korle job pabo?" is a *student* question, NOT a job seeker
    is_job_question = _match_any(message, JOB_QUESTION_PATTERNS)
    if _match_any(message, JOB_SEEKER_PATTERNS) and not is_job_question:
        return ClassificationResult(
            category="job_seeker", sub_category="job_application",
            priority="low", confidence=0.90,
            product_interest="", sender_role="", company_name="",
            is_corporate=False, estimated_deal_size="",
            needs_follow_up=False,
            suggested_action="Redirect to careers page or HR team.",
            auto_response=_auto_response(language, "job_seeker"),
            reasoning="Job-seeking intent detected. Not a sales enquiry.",
        )

    # ---- 3. SUPPORT ISSUE ----
    support_pattern_hit = _match_any(message, SUPPORT_PATTERNS)
    support_kw_score = _keyword_score(message, SUPPORT_KEYWORDS)

    if support_pattern_hit or support_kw_score >= 2:
        is_refund = bool(re.search(
            r"(refund|cancel|money\s*back|ফেরত|বাতিল|রিফান্ড)", message, re.I))
        is_angry = bool(re.search(
            r"(upset|angry|post\s+(about|on)\s+facebook)", message, re.I))
        is_payment = bool(re.search(
            r"(paid|পেমেন্ট).*(confirm|কনফার্ম|পাইনি)", message, re.I))

        if is_angry or is_refund:
            sub, pri = ("escalation" if is_angry else "refund_request"), "high"
        elif is_payment:
            sub, pri = "payment_issue", "medium"
        else:
            sub, pri = "general_support", "medium"

        return ClassificationResult(
            category="support_issue", sub_category=sub,
            priority=pri, confidence=0.88,
            product_interest="", sender_role="", company_name="",
            is_corporate=False, estimated_deal_size="",
            needs_follow_up=True,
            suggested_action=(
                f"URGENT: Handle {sub.replace('_', ' ')}. Respond within 2 hours."
                if pri == "high" else
                f"Handle {sub.replace('_', ' ')}. Respond within 24 hours."
            ),
            auto_response=_auto_response(language, "support_issue"),
            reasoning=f"Support issue ({sub}). Urgency: {pri}.",
        )

    # ---- 4. SALES LEAD ----
    sales_kw = _keyword_score(message, SALES_KEYWORDS)
    enrol_hit = _match_any(message, ENROL_PATTERNS)

    if is_corp or sales_kw >= 2 or enrol_hit:
        if is_corp:
            sub, pri = "corporate_training", "high"
        elif enrol_hit or sales_kw >= 3:
            sub, pri = "direct_purchase_intent", "high"
        elif sales_kw >= 2:
            sub, pri = "pricing_inquiry", "medium"
        else:
            sub, pri = "pricing_inquiry", "medium"

        time = "4 hours" if is_corp else "24 hours"
        prefix = "HIGH PRIORITY CORPORATE: " if is_corp else ""

        return ClassificationResult(
            category="sales_lead", sub_category=sub,
            priority=pri, confidence=0.85 if sales_kw >= 2 else 0.75,
            product_interest=product, sender_role=role,
            company_name=company, is_corporate=is_corp,
            estimated_deal_size=deal,
            needs_follow_up=True,
            suggested_action=f"{prefix}Contact within {time}. Product: {product or 'to be determined'}.",
            auto_response=_auto_response(language, "sales_lead"),
            reasoning=f"Sales lead ({sub}). Corporate: {is_corp}. Product: {product}. Deal: {deal}.",
        )

    # Single sales keyword — still a weak sales signal, classify as sales
    if sales_kw == 1 and product:
        return ClassificationResult(
            category="sales_lead", sub_category="pricing_inquiry",
            priority="medium", confidence=0.65,
            product_interest=product, sender_role=role,
            company_name=company, is_corporate=is_corp,
            estimated_deal_size=deal,
            needs_follow_up=True,
            suggested_action=f"Contact within 24 hours. Product: {product}.",
            auto_response=_auto_response(language, "sales_lead"),
            reasoning=f"Weak sales signal with product interest ({product}).",
        )

    # ---- 5. GENERAL INQUIRY (fallback) ----
    sub_cats = {
        "class_format":     r"(live|recorded|recording|offline|online|ক্লাস|লাইভ|রেকর্ডেড|লাইভ)",
        "eligibility":      r"(suitable|eligible|qualify|পারব|পড়ি|non.?technical)",
        "certification":    r"(certificate|সার্টিফিকেট|govt\s+approved|সরকারি|approved)",
        "location":         r"(kothay|location|mirpur|venue|কোথায়|ঠিকানা)",
        "student_discount": r"(student\s+discount|ছাত্র|ছাড়)",
        "addon":            r"(add.?on|lifetime\s+access|লাইফটাইম|lifetime)",
        "career_query":     r"(job\s+pabo|course\s+korle\s+job|চাকরি\s+পাব)",
    }
    sub = "unclassified"
    for cat_name, pat in sub_cats.items():
        if re.search(pat, message, re.IGNORECASE):
            sub = cat_name
            break

    return ClassificationResult(
        category="general_inquiry", sub_category=sub,
        priority="low", confidence=0.60,
        product_interest=product, sender_role="",
        company_name="", is_corporate=False,
        estimated_deal_size="individual",
        needs_follow_up=True,
        suggested_action=f"Respond to {sub.replace('_', ' ')} question. May convert to sales lead.",
        auto_response=_auto_response(language, "general_inquiry"),
        reasoning=f"General inquiry ({sub}). Could convert to a sale with proper follow-up.",
    )
