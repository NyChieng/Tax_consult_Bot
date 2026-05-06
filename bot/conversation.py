import anthropic
import structlog

from config import settings
from bot.system_prompt import SYSTEM_PROMPT, DISCLAIMER_TEXT, WELCOME_MESSAGE
from bot.language_detector import detect_language, translate_to_english, translate_from_english
from bot.intent_classifier import classify_intent
from bot.retriever import retrieve, format_context
from security.input_guard import input_guard
from security.output_guard import output_guard
from security.rate_limiter import rate_limiter
from security.audit_log import audit_log
from security.encryption import encryptor
from agent.learning.feedback_loop import FeedbackLoop
from agent.learning.self_improver import SelfImprover
from agent.learning.memory_store import MemoryStore

logger = structlog.get_logger()

MAX_HISTORY = 10

# Initialize learning components
feedback_loop = FeedbackLoop()
self_improver = SelfImprover()
memory_store = MemoryStore()

BLOCKED_RESPONSES = {
    "prompt_injection": "I detected an attempt to manipulate my instructions. I can only help with Malaysian tax questions. Please ask a legitimate tax question.",
    "xss_attempt": "Your message contained invalid characters. Please rephrase your tax question.",
    "sql_injection": "Your message was blocked for security reasons. Please ask a normal tax question.",
    "illegal_advice_request": "I cannot provide advice on tax evasion or illegal activities. Tax evasion is a criminal offence under Section 114 of the Income Tax Act 1967. If you need help with LEGAL tax planning, please consult a registered tax agent.",
    "user_banned": "Your access has been temporarily suspended due to suspicious activity. Please try again later.",
    "input_too_long": "Your message is too long. Please keep questions under 2000 characters.",
}


async def handle_query(
    user_message: str,
    conversation_history: list[dict] | None = None,
    user_id: str = "anonymous",
    ip_address: str = "",
) -> dict:
    if conversation_history is None:
        conversation_history = []

    # === SECURITY LAYER 1: Rate Limiting ===
    rate_check = rate_limiter.check(user_id, ip_address)
    if not rate_check["allowed"]:
        audit_log.log("rate_limit", user_id=user_id, details=rate_check, severity="warning")
        return {
            "response": f"⏳ Rate limit reached. You have {rate_check['remaining']} queries remaining. Try again in {rate_check['retry_after_seconds']} seconds.",
            "intent": "rate_limited",
            "language": "en",
            "sources": [],
            "blocked": True,
        }

    # === SECURITY LAYER 2: Input Validation ===
    validation = input_guard.validate(user_message, user_id)
    if not validation["safe"]:
        audit_log.log(
            "injection_blocked",
            user_id=user_id,
            details={"threat_type": validation["threat_type"], "threat_level": validation["threat_level"]},
            severity="critical" if validation["threat_level"] == "critical" else "warning",
            ip_address=ip_address,
        )
        blocked_msg = BLOCKED_RESPONSES.get(validation["threat_type"], "Your message was blocked for security reasons.")
        return {
            "response": blocked_msg,
            "intent": "blocked",
            "language": "en",
            "sources": [],
            "blocked": True,
            "threat_type": validation["threat_type"],
        }

    # Use sanitized input from here on
    safe_message = validation["sanitized"]

    # === CORE LOGIC ===

    # 1. Detect language
    lang = detect_language(safe_message)

    # 2. Translate to English for retrieval
    en_message = translate_to_english(safe_message, lang)

    # 3. Classify intent
    intent = await classify_intent(en_message)
    logger.info("query_processing", intent=intent, lang=lang, user=encryptor.hash_user_id(user_id))

    # 4. Handle greetings
    if intent == "greeting":
        welcome = WELCOME_MESSAGE.get(lang, WELCOME_MESSAGE["en"])
        return {"response": welcome, "intent": intent, "language": lang, "sources": []}

    # === LEARNING LAYER: Detect implicit feedback from previous interaction ===
    if conversation_history:
        prev_query = conversation_history[-1].get("content", "") if conversation_history[-1].get("role") == "user" else None
        feedback_loop.detect_implicit_feedback(user_id, safe_message, prev_query)

    # 5. Retrieve relevant context (RAG)
    context_chunks = retrieve(en_message, intent=intent, top_k=6)
    context = format_context(context_chunks)

    # === LEARNING LAYER: Add few-shot examples from golden memory ===
    few_shot = self_improver.get_few_shot_examples(intent)

    # === LEARNING LAYER: Check memory for similar past successes ===
    memory_context = ""
    similar_episodes = memory_store.recall_similar(en_message, intent, limit=2)
    if similar_episodes:
        memory_context = "\n\nPrevious highly-rated answers for similar questions:\n"
        for ep in similar_episodes:
            memory_context += f"Q: {ep['query']}\nA: {ep['response'][:200]}\n\n"

    # 6. Build messages for Claude
    messages = _build_messages(conversation_history, safe_message, context + few_shot + memory_context)

    # 7. Call Claude
    response_text = await _call_claude(messages, lang)

    # === SECURITY LAYER 3: Output Validation ===
    output_check = output_guard.sanitize_output(response_text)
    response_text = output_check["response"]
    if output_check["issues"]:
        audit_log.log("output_sanitized", user_id=user_id, details={"issues": output_check["issues"]})

    # 8. Extract sources from context
    sources = _extract_sources(context_chunks)

    # 9. Only append disclaimer if Claude didn't already include one
    full_response = response_text
    if "not professional advice" not in response_text and "tax agent" not in response_text.lower()[-200:]:
        disclaimer = DISCLAIMER_TEXT.format(sources=", ".join(sources) if sources else "LHDN official documentation")
        full_response = response_text + disclaimer

    # 10. Translate response if needed
    if lang != "en":
        full_response = translate_from_english(full_response, lang)

    # === LEARNING LAYER: Record interaction for learning ===
    interaction_id = feedback_loop.record_interaction(
        query=encryptor.anonymize_query(safe_message),
        response=response_text[:500],
        intent=intent,
        chunks_used=context_chunks,
        language=lang,
        user_id=encryptor.hash_user_id(user_id),
    )

    # === LEARNING LAYER: Self-critique (async, non-blocking) ===
    # Only critique 10% of queries to save API costs
    import random
    has_llm = settings.anthropic_api_key or (settings.llm_provider == "bedrock" and settings.aws_access_key_id)
    if random.random() < 0.1 and has_llm:
        critique = await self_improver.self_critique(en_message, response_text, context_chunks)
        if critique.get("score", 1.0) < 0.5:
            feedback_loop.record_feedback(interaction_id, critique["score"], "self_critique")
            memory_store.update_meta_knowledge(intent, success=False)
        elif critique.get("score", 0) >= 0.8:
            memory_store.store_episode(en_message, response_text, intent, critique["score"], sources)
            memory_store.update_meta_knowledge(intent, success=True)

    # Log successful query
    audit_log.log("query_success", user_id=encryptor.hash_user_id(user_id), details={"intent": intent, "lang": lang})

    return {
        "response": full_response,
        "intent": intent,
        "language": lang,
        "sources": sources,
        "chunks_used": len(context_chunks),
        "interaction_id": interaction_id,
    }


async def _call_claude(messages: list[dict], response_lang: str) -> str:
    lang_instruction = ""
    if response_lang == "bm":
        lang_instruction = "\n\nIMPORTANT: Respond in conversational Bahasa Malaysia (not formal)."
    elif response_lang == "zh":
        lang_instruction = "\n\nIMPORTANT: Respond in conversational Mandarin Chinese (简体中文)."

    system_prompt = SYSTEM_PROMPT + lang_instruction

    try:
        if settings.llm_provider == "bedrock":
            return await _call_bedrock(messages, system_prompt)
        else:
            return await _call_anthropic_direct(messages, system_prompt)
    except Exception as e:
        logger.error("llm_api_error", error=str(e), provider=settings.llm_provider)
        return "Alamak, something went wrong on my end. Give me a sec and try again ya! 🙏"


async def _call_bedrock(messages: list[dict], system_prompt: str) -> str:
    """Call Claude via AWS Bedrock."""
    from anthropic import AsyncAnthropicBedrock

    client = AsyncAnthropicBedrock(aws_region=settings.aws_region)

    response = await client.messages.create(
        model=settings.bedrock_model_id,
        max_tokens=2000,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


async def _call_anthropic_direct(messages: list[dict], system_prompt: str) -> str:
    """Call Claude via direct Anthropic API."""
    if not settings.anthropic_api_key:
        return "API key not configured. Please set ANTHROPIC_API_KEY in your .env file."

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


def _build_messages(history: list[dict], current_message: str, context: str) -> list[dict]:
    messages = []

    # Include recent history (last N messages)
    recent_history = history[-MAX_HISTORY:]
    for msg in recent_history:
        messages.append(msg)

    # Current user message with context
    user_content = f"""Here is the relevant context from Malaysian tax documents:

{context}

---

User Question: {current_message}"""

    messages.append({"role": "user", "content": user_content})
    return messages


def _extract_sources(chunks: list[dict]) -> list[str]:
    sources = []
    seen = set()
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        title = meta.get("title", "")
        url = meta.get("source_url", "")
        source_str = title or url
        if source_str and source_str not in seen:
            sources.append(source_str)
            seen.add(source_str)
    return sources[:5]
