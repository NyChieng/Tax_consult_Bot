"""
AI Content Generator for MyCukai Marketing

Automatically generates:
- TikTok/Reels scripts (60-second tax tips)
- Twitter/X threads
- Facebook posts
- Blog post outlines
- Telegram channel updates
- Instagram carousel ideas
"""
import anthropic
from datetime import datetime
from config import settings

CONTENT_PROMPT = """You are a social media content creator for MyCukai, a Malaysian AI tax assistant bot.
Generate today's marketing content batch. Make it engaging, educational, and shareable.

Target audience: Malaysian taxpayers (individuals + SME owners), age 25-55, mix of English and Bahasa Malaysia speakers.

Today's date: {date}
Current tax season status: {season_status}

Generate ALL of the following in ONE response:

1. TIKTOK SCRIPT (60 seconds)
- Hook in first 3 seconds
- One specific tax tip Malaysian viewers don't know
- Call to action: "Try @MyCukaiBot on Telegram"
- Mix English and BM naturally (how Malaysians actually speak)

2. TWITTER THREAD (5 tweets)
- Educational thread about one Malaysian tax topic
- Include specific numbers/rates
- Last tweet: CTA to try MyCukai

3. FACEBOOK POST
- Longer form, conversational
- Target: SME owners in Facebook business groups
- Include a question to drive engagement

4. TELEGRAM CHANNEL POST
- Brief tax update or tip
- Link to relevant LHDN resource
- Remind followers about the bot

5. BLOG POST OUTLINE
- SEO-optimized title (target a specific keyword)
- 5 section headers
- Target keyword suggestion

6. INSTAGRAM CAROUSEL (5 slides)
- Slide-by-slide text content
- Visual description for each slide
- Educational infographic style

Format as JSON with keys: tiktok, twitter, facebook, telegram, blog, instagram
"""


def _get_season_status() -> str:
    month = datetime.now().month
    if 3 <= month <= 6:
        return "PEAK TAX SEASON - Filing deadlines approaching. High urgency content."
    elif month == 10:
        return "BUDGET SEASON - New budget just announced. Cover changes."
    elif month in [11, 12, 1]:
        return "POST-BUDGET - Finance Act details. Year-end tax planning references."
    else:
        return "OFF-SEASON - Educational content, build audience, long-term SEO plays."


async def generate_daily_content() -> dict:
    if not settings.anthropic_api_key:
        return _fallback_content()

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": CONTENT_PROMPT.format(
                date=datetime.now().strftime("%Y-%m-%d (%A)"),
                season_status=_get_season_status(),
            ),
        }],
    )

    content_text = response.content[0].text

    # Try to parse JSON from response
    try:
        import json
        # Find JSON in response
        start = content_text.find("{")
        end = content_text.rfind("}") + 1
        if start >= 0 and end > start:
            content = json.loads(content_text[start:end])
        else:
            content = {"raw": content_text}
    except Exception:
        content = {"raw": content_text}

    content["generated_at"] = datetime.now().isoformat()
    content["season_status"] = _get_season_status()
    return content


def _fallback_content() -> dict:
    """Generate template content when no API key is available."""
    return {
        "tiktok": {
            "hook": "POV: You just found out you can claim THIS as tax relief...",
            "tip": "Lifestyle relief of RM 2,500 covers books, computers, sports equipment, and internet bills!",
            "cta": "Try @MyCukaiBot on Telegram for more tax tips!",
        },
        "twitter": [
            "Thread: 5 tax reliefs most Malaysians don't claim (and leave money on the table) 🧵",
            "1/ Lifestyle relief (RM 2,500) - Books, computers, sports gear, internet subscription all count!",
            "2/ Medical expenses for parents (RM 8,000) - If you're supporting aging parents, claim this.",
            "3/ Education fees (RM 7,000) - Any course for upskilling, even online courses count.",
            "4/ Childcare (RM 3,000) - Daycare, kindergarten, nursery fees.",
            "5/ Want to know ALL available reliefs? Ask @MyCukaiBot on Telegram - it's free!",
        ],
        "facebook": "Fellow business owners - quick question: Are you claiming ALL the tax reliefs you're entitled to? Most SME owners I talk to miss at least 2-3 reliefs every year. That's thousands of RM left on the table. Drop a 🙋 if you want me to share the full list!",
        "telegram": "💡 Tax Tip: Did you know the lifestyle relief (RM 2,500) now covers internet subscription fees? If you're paying for home WiFi or mobile data for work, you can claim it! Check: https://www.hasil.gov.my",
        "blog": {
            "title": "Complete Guide to Malaysian Tax Reliefs 2025 [Full List]",
            "keyword": "tax relief malaysia 2025",
            "sections": [
                "What Are Tax Reliefs (Pelepasan Cukai)?",
                "Personal & Family Reliefs",
                "Lifestyle & Education Reliefs",
                "Medical & Insurance Reliefs",
                "How to Claim: Step-by-Step e-Filing Guide",
            ],
        },
        "instagram": [
            {"slide": 1, "text": "5 Tax Reliefs You're Probably Missing 💰", "visual": "Bold title with MyCukai branding"},
            {"slide": 2, "text": "Lifestyle Relief: RM 2,500\nBooks • Computer • Sports • Internet", "visual": "Icons for each item"},
            {"slide": 3, "text": "Parents Medical: RM 8,000\nDoctor visits • Medicine • Check-ups", "visual": "Family care illustration"},
            {"slide": 4, "text": "Education: RM 7,000\nOnline courses • Certifications • Degrees", "visual": "Learning/books illustration"},
            {"slide": 5, "text": "Want the FULL list?\nAsk @MyCukaiBot on Telegram 🤖", "visual": "CTA with QR code to bot"},
        ],
        "generated_at": datetime.now().isoformat(),
    }
