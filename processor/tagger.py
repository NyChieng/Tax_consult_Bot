import re

TAX_CATEGORIES = {
    "personal_tax": [
        "personal", "individual", "resident", "employment income",
        "salary", "gaji", "pendapatan individu", "BE form", "B form",
        "PCB", "potongan cukai bulanan", "EA form",
    ],
    "corporate_tax": [
        "corporate", "company", "syarikat", "sdn bhd", "bhd",
        "C form", "pioneer status", "investment tax allowance",
        "capital allowance", "group relief",
    ],
    "sst": [
        "SST", "sales tax", "service tax", "cukai jualan",
        "cukai perkhidmatan", "SST-02", "taxable service",
        "registration threshold",
    ],
    "rpgt": [
        "RPGT", "real property gains", "CKHT", "keuntungan harta tanah",
        "disposal", "property sale", "holding period",
    ],
    "stamp_duty": [
        "stamp duty", "duti setem", "stamp act", "instrument",
        "memorandum of transfer", "MOT",
    ],
    "withholding_tax": [
        "withholding tax", "cukai pegangan", "WHT", "non-resident",
        "CP37", "royalties", "technical fees", "DTA", "treaty",
    ],
    "reliefs": [
        "relief", "pelepasan", "deduction", "rebate", "exemption",
        "lifestyle", "medical", "education", "EPF", "KWSP",
        "life insurance", "childcare",
    ],
    "penalties": [
        "penalty", "penalti", "denda", "late filing", "compound",
        "prosecution", "appeal", "objection",
    ],
    "expatriate": [
        "expatriate", "non-resident", "foreigner", "work permit",
        "knowledge worker", "Iskandar", "returning expert",
    ],
}

TOPIC_TAGS = {
    "efiling": ["e-filing", "efiling", "online filing", "mytax"],
    "budget": ["budget", "belanjawan", "finance act"],
    "deadline": ["deadline", "due date", "tarikh akhir", "filing period"],
    "registration": ["registration", "pendaftaran", "register"],
    "calculation": ["calculate", "computation", "formula", "rate"],
    "exemption": ["exempt", "dikecualikan", "zero-rated", "not subject"],
    "incentive": ["incentive", "insentif", "pioneer", "ITA", "MIDA"],
}


def classify_tax_category(text: str) -> list[str]:
    text_lower = text.lower()
    matched = []
    for category, keywords in TAX_CATEGORIES.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score >= 2:
            matched.append(category)
    return matched or ["general"]


def extract_topic_tags(text: str) -> list[str]:
    text_lower = text.lower()
    tags = []
    for tag, keywords in TOPIC_TAGS.items():
        if any(kw.lower() in text_lower for kw in keywords):
            tags.append(tag)
    return tags


def detect_act_references(text: str) -> list[str]:
    acts = set()
    patterns = [
        (r"Income Tax Act 1967|ITA\s*1967", "ITA1967"),
        (r"Sales Tax Act 2018", "STA2018"),
        (r"Service Tax Act 2018", "SVTA2018"),
        (r"Real Property Gains Tax Act|RPGT Act", "RPGTA1976"),
        (r"Stamp Act 1949", "SA1949"),
        (r"Finance Act \d{4}", None),
        (r"Tax Agents Act 1995", "TAA1995"),
        (r"Labuan Business Activity Tax Act", "LBATA1990"),
    ]

    for pattern, code in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            if code:
                acts.add(code)
            else:
                for m in matches:
                    acts.add(m)

    # Section references
    section_refs = re.findall(r"[Ss]ection\s+\d+[A-Z]?(?:\(\d+\))?", text)
    for ref in section_refs[:5]:
        acts.add(ref)

    return list(acts)


def tag_chunk(chunk_text: str) -> dict:
    return {
        "tax_category": classify_tax_category(chunk_text),
        "topic_tags": extract_topic_tags(chunk_text),
        "act_references": detect_act_references(chunk_text),
    }
