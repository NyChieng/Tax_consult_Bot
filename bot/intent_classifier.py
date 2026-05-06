import anthropic
from config import settings

INTENTS = [
    "personal_tax_rate",
    "personal_relief",
    "efiling_procedure",
    "pcb_calculation",
    "corporate_tax",
    "sst_registration",
    "sst_rate",
    "rpgt",
    "stamp_duty",
    "withholding_tax",
    "expatriate_tax",
    "penalty_appeal",
    "deadline",
    "out_of_scope",
    "greeting",
]

CLASSIFICATION_PROMPT = """Classify the following user query into exactly ONE of these intent categories:

{intents}

Query: "{query}"

Respond with ONLY the intent name, nothing else."""


async def classify_intent(query: str) -> str:
    # Use rule-based for speed and cost savings — LLM classification is optional
    has_api = settings.anthropic_api_key or (settings.llm_provider == "bedrock" and settings.aws_access_key_id)
    if not has_api:
        return _rule_based_classify(query)

    try:
        if settings.llm_provider == "bedrock":
            from anthropic import AsyncAnthropicBedrock
            client = AsyncAnthropicBedrock(
                aws_access_key=settings.aws_access_key_id,
                aws_secret_key=settings.aws_secret_access_key,
                aws_region=settings.aws_region,
            )
            model = settings.bedrock_model_id_haiku
        else:
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            model = "claude-haiku-4-5-20251001"

        response = await client.messages.create(
            model=model,
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": CLASSIFICATION_PROMPT.format(
                    intents="\n".join(f"- {i}" for i in INTENTS),
                    query=query,
                ),
            }],
        )
        intent = response.content[0].text.strip().lower()
        if intent in INTENTS:
            return intent
        return _rule_based_classify(query)

    except Exception:
        return _rule_based_classify(query)


def _rule_based_classify(query: str) -> str:
    q = query.lower()

    if any(w in q for w in ["hi", "hello", "hey", "selamat", "你好"]):
        return "greeting"

    if any(w in q for w in ["rate", "kadar", "bracket", "how much tax"]):
        if any(w in q for w in ["company", "corporate", "syarikat"]):
            return "corporate_tax"
        return "personal_tax_rate"

    if any(w in q for w in ["relief", "deduction", "claim", "pelepasan", "减免"]):
        return "personal_relief"

    if any(w in q for w in ["e-filing", "efiling", "file", "submit", "borang"]):
        return "efiling_procedure"

    if any(w in q for w in ["pcb", "monthly deduction", "potongan bulanan"]):
        return "pcb_calculation"

    if any(w in q for w in ["sst", "sales tax", "service tax"]):
        if any(w in q for w in ["register", "threshold", "daftar"]):
            return "sst_registration"
        return "sst_rate"

    if any(w in q for w in ["rpgt", "property", "sell house", "ckht", "rumah"]):
        return "rpgt"

    if any(w in q for w in ["stamp duty", "duti setem"]):
        return "stamp_duty"

    if any(w in q for w in ["withholding", "wht", "non-resident", "cp37"]):
        return "withholding_tax"

    if any(w in q for w in ["expat", "foreigner", "foreign worker"]):
        return "expatriate_tax"

    if any(w in q for w in ["penalty", "late", "appeal", "denda"]):
        return "penalty_appeal"

    if any(w in q for w in ["deadline", "when", "due date", "tarikh akhir"]):
        return "deadline"

    if any(w in q for w in ["company", "corporate", "sdn bhd"]):
        return "corporate_tax"

    return "personal_tax_rate"
