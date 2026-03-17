#!/usr/bin/env python3
"""
Eval script for webhunter outreach prompts.
Runs 22 scenarios through LLM, checks intent classification accuracy.
Returns accuracy as a float (0.0 - 100.0).
"""

import importlib
import json
import os
import sys
import re
import time

# ---------------------------------------------------------------------------
# LLM client (MiniMax via OpenAI-compatible API)
# ---------------------------------------------------------------------------

# Load .env from project root
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "MiniMax-M2.5-highspeed")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.minimax.io/v1")


def call_llm(system, messages):
    """Call LLM and return raw text response."""
    if LLM_PROVIDER == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=LLM_API_KEY)
        resp = client.messages.create(
            model=LLM_MODEL, max_tokens=300,
            system=system, messages=messages, temperature=0.3,
        )
        return resp.content[0].text
    else:
        from openai import OpenAI
        client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
        api_msgs = [{"role": "system", "content": system}] + messages
        resp = client.chat.completions.create(
            model=LLM_MODEL, messages=api_msgs,
            temperature=0.3, max_tokens=300,
        )
        return resp.choices[0].message.content


# ---------------------------------------------------------------------------
# Prompt assembly (mirrors build_llm_messages from tg_outreach_bot.py)
# ---------------------------------------------------------------------------

BASE_PROMPT_FIXED = """\
Ты ведёшь переписку в Telegram от имени веб-разработчика.
КРИТИЧНО: Тебя зовут Алексей. МУЖСКОЙ РОД ВСЕГДА.

КОНТЕКСТ:
- Ты нашёл бизнес "{lead_name}" ({niche_display}) в {city} на 2ГИС
- Написал им как потенциальный клиент, чтобы завязать контакт
- Цель: естественно перейти к предложению сделать/обновить им сайт
- Бренд: ForgeSite — помогаем бизнесу появиться в интернете
- Портфолио: {portfolio_url}
{website_info}
{audit_info}

УСЛУГИ И ЦЕНЫ (НЕ озвучивай пока не спросят):
- От {landing_price} — простой сайт за 3-5 дней
- От {card_price} — сайт побольше за 5-10 дней
- От {corp_price} — полноценный сайт за 10-15 дней
- 5К — Яндекс.Бизнес/2ГИС, 10К — все карты
- 10К — TG-бот, 10К + 2К/мес — AI-чатбот
- Старт 20К, Бизнес 45К + 5К/мес

ТВОЯ РОЛЬ СЕЙЧАС — {current_step}"""

RULES_BLOCK_FIXED = """
ПРАВИЛА:
- Варьируй длину, живая речь, подстройка под тон
- Никаких списков, markdown, эмодзи
- Если вопрос — СНАЧАЛА ответь на него
- При REJECT/HOSTILE — попрощайся коротко
- Не дави, не впаривай, никаких скидок
- Ты — Алексей, мужской род всегда"""

OBJECTION_BLOCK_FIXED = """
ТАКТИКА ПО ВОЗРАЖЕНИЯМ:
"Дорого" → спроси бюджет, предложи дешевле (от {landing_price})
"Надо подумать" → уточни что смущает, одна попытка и отпускай
"Не нужен сайт" → "А как клиенты вас находят?", макс 2 попытки
"Есть сайт" → попроси ссылку, глянешь бесплатно
Одно возражение дважды = отступай."""

NICHE_ACC = {
    "avtoserwis": "хороший автосервис", "stomatologiya": "хорошую стоматологию",
    "medcentr": "хороший медцентр", "restoran": "хороший ресторан",
    "stroitelnaya-kompaniya": "строительную компанию", "mebel": "мебельный магазин",
    "salon-krasoty": "хороший салон красоты", "barbershop": "хороший барбершоп",
    "fitnes-klub": "хороший фитнес-клуб", "klining": "клининг",
    "vetklinka": "хорошую ветклинику", "remont": "бригаду для ремонта",
    "kosmetologiya": "хорошего косметолога", "yurist": "хорошего юриста",
}

ALL_INTENTS = {
    "CONTINUE", "REJECT", "HOSTILE", "INTERESTED", "QUESTION",
    "PRICE_ASK", "OBJECTION_EXPENSIVE", "OBJECTION_THINKING",
    "OBJECTION_NO_NEED", "WANTS_EXAMPLES", "READY_TO_TALK",
    "READY_TO_PITCH", "HAS_SITE",
}

STEP_MAP = {
    "warm_sent": "ПРОГРЕВ (ты притворяешься клиентом, задаёшь вопросы про их услуги)",
    "followup_sent": "КОНТАКТ (продолжаешь общение как клиент, раппорт)",
    "pitch_sent": "ПИТЧ (ты раскрылся как веб-разработчик, предлагаешь услуги)",
    "negotiating": "ПЕРЕГОВОРЫ (обсуждаете детали, цены, возражения)",
    "closing": "ЗАКРЫТИЕ (предлагаешь конкретное действие — макет, звонок)",
}


def load_prompts():
    """Import prompts from target/prompts.py (may be modified by agents)."""
    if "target.prompts" in sys.modules:
        return importlib.reload(sys.modules["target.prompts"])
    return importlib.import_module("target.prompts")


def build_system_prompt(prompts, info, lead, audit=None):
    """Assemble system prompt from prompt blocks + scenario context."""
    niche = lead.get("niche", "avtoserwis")
    city = lead.get("city", "Москва")
    name = lead.get("name", "Тест")
    status = info.get("status", "warm_sent")
    has_website = info.get("has_website", False)

    niche_display = NICHE_ACC.get(niche, niche)
    current_step = STEP_MAP.get(status, status)

    website_info = ""
    audit_info = ""
    if has_website and audit:
        website_info = f"- У них есть сайт (score: {audit.get('score', '?')}/100)"
        problems = []
        if not audit.get("ssl"):
            problems.append("нет SSL")
        if not audit.get("has_viewport"):
            problems.append("не адаптирован под мобильные")
        if problems:
            audit_info = "- Проблемы: " + ", ".join(problems)

    prompt_vars = dict(
        landing_price="15К", card_price="30К", corp_price="50К",
        portfolio_url="https://forgesite.design/demo/",
        landing_price_k=15, card_price_k=30,
        niche_demo_note="",
    )

    parts = [
        BASE_PROMPT_FIXED.format(
            lead_name=name, niche_display=niche_display, city=city,
            website_info=website_info, audit_info=audit_info,
            current_step=current_step, **prompt_vars,
        ),
        prompts.INTENT_BLOCK_TEMPLATE.format(**prompt_vars),
        RULES_BLOCK_FIXED,
    ]

    post_pitch = ("pitch_sent", "demo_sent", "negotiating",
                  "objection_handling", "closing")
    if status in post_pitch:
        parts.append(OBJECTION_BLOCK_FIXED.format(**prompt_vars))

    return "\n".join(parts)


def build_messages(conversations):
    """Convert conversation pairs to LLM messages."""
    messages = []
    for c in conversations:
        role = "assistant" if c.get("dir") == "out" else "user"
        messages.append({"role": role, "content": c["text"]})

    if messages and messages[0]["role"] == "assistant":
        messages.insert(0, {"role": "user", "content": "[Начало диалога]"})

    # Merge consecutive same-role
    merged = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"] += "\n" + m["content"]
        else:
            merged.append(m)

    # Add final instruction
    merged.append({
        "role": "user",
        "content": "Ответь РОВНО 2 строки: первая — INTENT (одно слово), вторая — текст сообщения. Ничего больше."
    })

    return merged


def parse_intent(raw):
    """Parse intent from LLM response."""
    lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]
    if not lines:
        return "UNKNOWN"
    first = lines[0].upper().strip(": ")
    if first.startswith("INTENT"):
        first = first.replace("INTENT", "", 1).strip(": ")
    # Strip <think> tags
    first = re.sub(r"</?think>", "", first).strip()
    # Sometimes model outputs thinking before intent
    for line in lines:
        candidate = line.upper().strip(": ")
        candidate = re.sub(r"</?think>", "", candidate).strip()
        if candidate.startswith("INTENT"):
            candidate = candidate.replace("INTENT", "", 1).strip(": ")
        if candidate in ALL_INTENTS:
            return candidate
    if first in ALL_INTENTS:
        return first
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Scenarios (same as test_llm_scenarios.py)
# ---------------------------------------------------------------------------

def conv(*pairs):
    return [{"dir": d, "text": t, "at": "2026-03-13T12:00:00"} for d, t in pairs]

def make_info(niche="avtoserwis", city="Москва", name="Тест",
              status="warm_sent", has_website=False, auto_reply_count=0):
    return {"lead_name": name, "lead_niche": niche, "lead_city": city,
            "status": status, "has_website": has_website,
            "auto_reply_count": auto_reply_count, "intent_history": []}

def make_lead(niche="avtoserwis", city="Москва", name="Тест", website=""):
    return {"name": name, "city": city, "niche": niche,
            "contacts": {"website": website} if website else {}}

SCENARIOS = [
    {"name": "Warm: positive", "info": make_info("stomatologiya", "Москва", "Стомклиника", "warm_sent"),
     "lead": make_lead("stomatologiya", "Москва", "Стомклиника"),
     "conv": conv(("out", "Здравствуйте! Подскажите, вы сейчас принимаете? Ищу хорошую стоматологию в Москве."), ("in", "Да, работаем! Что вас беспокоит?")),
     "expected": ["CONTINUE"]},

    {"name": "Warm: closed", "info": make_info("stomatologiya", "Москва", "Стомклиника", "warm_sent"),
     "lead": make_lead("stomatologiya", "Москва", "Стомклиника"),
     "conv": conv(("out", "Здравствуйте! Подскажите, вы сейчас принимаете?"), ("in", "Мы закрылись")),
     "expected": ["REJECT"]},

    {"name": "Warm: hostile", "info": make_info("medcentr", "Москва", "Медцентр", "warm_sent"),
     "lead": make_lead("medcentr", "Москва", "Медцентр"),
     "conv": conv(("out", "Здравствуйте! Подскажите, медцентр работает?"), ("in", "Иди нахуй спамер ёбаный")),
     "expected": ["HOSTILE"]},

    {"name": "Warm: question", "info": make_info("restoran", "Казань", "Ресторан", "warm_sent"),
     "lead": make_lead("restoran", "Казань", "Ресторан"),
     "conv": conv(("out", "Здравствуйте! Ресторан работает?"), ("in", "А откуда у вас мой номер?")),
     "expected": ["QUESTION"]},

    {"name": "Warm: not our thing", "info": make_info("mebel", "Казань", "Мебель", "warm_sent"),
     "lead": make_lead("mebel", "Казань", "Мебель"),
     "conv": conv(("out", "Здравствуйте! Подскажите, вы делаете мебель на заказ?"), ("in", "Нет, мы этим не занимаемся")),
     "expected": ["REJECT"]},

    {"name": "Followup: normal", "info": make_info("stroitelnaya-kompaniya", "Новосибирск", "СтройКомп", "followup_sent"),
     "lead": make_lead("stroitelnaya-kompaniya", "Новосибирск", "СтройКомп"),
     "conv": conv(("out", "Здравствуйте! Ищу строительную компанию. Вы работаете?"), ("in", "Да, работаем. Что нужно?"), ("out", "Хочу пристройку к дому. Вы такое делаете?"), ("in", "Делаем, от 500 тысяч. Приезжайте на замер.")),
     "expected": ["CONTINUE"]},

    {"name": "Followup: question", "info": make_info("restoran", "Казань", "Ресторан", "followup_sent"),
     "lead": make_lead("restoran", "Казань", "Ресторан"),
     "conv": conv(("out", "Здравствуйте! Ресторан работает?"), ("in", "Да. На сколько человек?"), ("out", "На 6 человек. А банкетное меню есть?"), ("in", "А вы откуда про нас узнали?")),
     "expected": ["QUESTION"]},

    {"name": "Pitch: price ask", "info": make_info("salon-krasoty", "Краснодар", "Салон", "pitch_sent", has_website=False),
     "lead": make_lead("salon-krasoty", "Краснодар", "Салон"),
     "conv": conv(("out", "Привет! Ищу салон красоты. Работаете?"), ("in", "Да!"), ("out", "А стрижка сколько? Кстати, я веб-разработчик, заметил у вас нет сайта."), ("in", "А сколько стоит сайт? И что входит?")),
     "expected": ["PRICE_ASK", "INTERESTED"]},

    {"name": "Pitch: reject", "info": make_info("fitnes-klub", "Ростов-на-Дону", "Фитнес", "pitch_sent"),
     "lead": make_lead("fitnes-klub", "Ростов-на-Дону", "Фитнес"),
     "conv": conv(("out", "Привет! Ищу фитнес-клуб. Работаете?"), ("in", "Работаем"), ("out", "Кстати, заметил что у вас нет сайта. Я веб-разработчик, могу помочь."), ("in", "Нет спасибо не нужно нам ничего")),
     "expected": ["REJECT", "OBJECTION_NO_NEED"]},

    {"name": "Pitch: examples", "info": make_info("avtoserwis", "Самара", "Автосервис", "pitch_sent"),
     "lead": make_lead("avtoserwis", "Самара", "Автосервис"),
     "conv": conv(("out", "Привет! Автосервис работает?"), ("in", "Да"), ("out", "Кстати, я веб-разработчик, делаю сайты. У вас нет сайта."), ("in", "Ну покажите примеры что вы делали")),
     "expected": ["WANTS_EXAMPLES"]},

    {"name": "Negotiating: expensive", "info": make_info("klining", "Москва", "Клининг", "negotiating", auto_reply_count=2),
     "lead": make_lead("klining", "Москва", "Клининг"),
     "conv": conv(("out", "Лендинг от 15К, полный сайт от 30К. Всё включено."), ("in", "80 тысяч это дорого, у нас нет такого бюджета")),
     "expected": ["OBJECTION_EXPENSIVE"]},

    {"name": "Negotiating: thinking", "info": make_info("vetklinka", "Казань", "Ветклиника", "negotiating", auto_reply_count=3),
     "lead": make_lead("vetklinka", "Казань", "Ветклиника"),
     "conv": conv(("out", "Вот примеры: forgesite.design/demo/. Лендинг от 15К."), ("in", "Надо подумать. Не сейчас наверное")),
     "expected": ["OBJECTION_THINKING"]},

    {"name": "Negotiating: no need", "info": make_info("barbershop", "Пермь", "Барбер", "negotiating", auto_reply_count=2),
     "lead": make_lead("barbershop", "Пермь", "Барбер"),
     "conv": conv(("out", "Сайт поможет привлечь новых клиентов из поиска."), ("in", "Нам и так нормально, клиенты есть, сайт не нужен")),
     "expected": ["OBJECTION_NO_NEED"]},

    {"name": "Negotiating: ready to talk", "info": make_info("remont", "Москва", "Ремонт", "negotiating", auto_reply_count=4),
     "lead": make_lead("remont", "Москва", "Ремонт"),
     "conv": conv(("out", "Могу набросать макет бесплатно, посмотрите как будет выглядеть."), ("in", "Ок давайте созвонимся, расскажете подробнее")),
     "expected": ["READY_TO_TALK"]},

    {"name": "Negotiating: question", "info": make_info("kosmetologiya", "Москва", "Косметолог", "negotiating", auto_reply_count=2),
     "lead": make_lead("kosmetologiya", "Москва", "Косметолог"),
     "conv": conv(("out", "Делаю сайты за 2-3 недели, включая дизайн и мобильную версию."), ("in", "А кто будет тексты писать для сайта? И фотографии нужны?")),
     "expected": ["QUESTION"]},

    {"name": "Closing: accept", "info": make_info("mebel", "Краснодар", "Мебель", "closing", auto_reply_count=6),
     "lead": make_lead("mebel", "Краснодар", "Мебель"),
     "conv": conv(("out", "Могу набросать бесплатный макет за день. Посмотрите — без обязательств."), ("in", "Ну давайте, попробуйте. Скиньте на почту info@mebel.ru")),
     "expected": ["READY_TO_TALK"]},

    {"name": "Closing: reject", "info": make_info("fitnes-klub", "Москва", "Фитнес", "closing", auto_reply_count=7),
     "lead": make_lead("fitnes-klub", "Москва", "Фитнес"),
     "conv": conv(("out", "Могу показать за 5 минут по телефону как будет выглядеть."), ("in", "Нет, мы не хотим. Спасибо")),
     "expected": ["REJECT"]},

    {"name": "Bad site: interest", "info": make_info("avtoserwis", "Тольятти", "АвтоМастер", "pitch_sent", has_website=True),
     "lead": make_lead("avtoserwis", "Тольятти", "АвтоМастер", "http://avtomaster-tlt.ru"),
     "audit": {"score": 25, "ssl": False, "has_viewport": False, "cms": None},
     "conv": conv(("out", "Кстати, посмотрел ваш сайт — без SSL и не адаптирован под мобильные. Могу помочь."), ("in", "А что конкретно не так и сколько стоит исправить?")),
     "expected": ["INTERESTED", "PRICE_ASK"]},

    {"name": "Good site: polite reject", "info": make_info("restoran", "Москва", "Ресторан", "pitch_sent", has_website=True),
     "lead": make_lead("restoran", "Москва", "Ресторан", "http://resto-msk.ru"),
     "audit": {"score": 82, "ssl": True, "has_viewport": True, "cms": "WordPress"},
     "conv": conv(("out", "Ваш сайт неплохой! Если нужна будет помощь с SEO или контентом — обращайтесь."), ("in", "Спасибо, у нас всё хорошо с сайтом")),
     "expected": ["REJECT", "CONTINUE", "OBJECTION_NO_NEED"]},

    {"name": "Edge: emoji only", "info": make_info("salon-krasoty", "Казань", "Салон", "warm_sent"),
     "lead": make_lead("salon-krasoty", "Казань", "Салон"),
     "conv": conv(("out", "Здравствуйте! Салон красоты работает?"), ("in", "👍")),
     "expected": ["CONTINUE"]},

    {"name": "Edge: long message", "info": make_info("remont", "Москва", "Ремонт", "negotiating", auto_reply_count=3),
     "lead": make_lead("remont", "Москва", "Ремонт"),
     "conv": conv(("out", "Делаю сайты от 15К, включено всё — дизайн, мобильная, хостинг на год."), ("in", "А у вас есть примеры для строительной тематики? И сколько по времени делается? И можно рассрочку?")),
     "expected": ["WANTS_EXAMPLES", "QUESTION", "INTERESTED"]},

    {"name": "Edge: send to email", "info": make_info("yurist", "Москва", "Юрист", "negotiating", auto_reply_count=4),
     "lead": make_lead("yurist", "Москва", "Юрист"),
     "conv": conv(("out", "Могу скинуть примеры и цены на почту."), ("in", "Да, скиньте на mail@law.ru пожалуйста")),
     "expected": ["READY_TO_TALK"]},
]


# ---------------------------------------------------------------------------
# Main eval
# ---------------------------------------------------------------------------

def main():
    try:
        prompts = load_prompts()
    except Exception as e:
        print(f"Import error: {e}", file=sys.stderr)
        print("0.0")
        return

    ok = 0
    total = len(SCENARIOS)
    errors = []

    for i, sc in enumerate(SCENARIOS):
        try:
            system = build_system_prompt(
                prompts, sc["info"], sc["lead"], sc.get("audit")
            )
            messages = build_messages(sc["conv"])
            raw = call_llm(system, messages)
            intent = parse_intent(raw)
            match = intent in sc["expected"]
            if match:
                ok += 1
            else:
                errors.append(f"  {sc['name']}: expected {sc['expected']}, got {intent}")
            status = "OK" if match else "FAIL"
            print(f"[{i+1}/{total}] {sc['name']}: {intent} [{status}]", file=sys.stderr)
        except Exception as e:
            errors.append(f"  {sc['name']}: ERROR {e}")
            print(f"[{i+1}/{total}] {sc['name']}: ERROR {e}", file=sys.stderr)

        # Small delay to avoid rate limits
        time.sleep(0.3)

    accuracy = (ok / total) * 100 if total > 0 else 0.0

    if errors:
        print(f"\nFailed:", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)

    print(f"\nAccuracy: {ok}/{total} ({accuracy:.1f}%)", file=sys.stderr)
    # Score on stdout (this is what SwarmResearch reads)
    print(f"{accuracy:.2f}")


if __name__ == "__main__":
    main()
