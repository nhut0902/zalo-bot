#!/usr/bin/env python3
"""
Zalo AI Bot — NhutBot
=====================
Project độc lập — Zalo Bot chạy trên Vercel (webhook) với dashboard Flask.

Tính năng:
- AI trả lời thông minh (Nhutbot 1.0 Flash qua AI Cloud proxy)
- /image <mô tả> — Tạo ảnh bằng AI (Pollinations.ai)
- /code <câu hỏi> — Trả lời câu hỏi code
- /search <từ khóa> — Tìm kiếm web (Tavily API)
- /xoso <số> — Dò vé số Miền Bắc / Trung / Nam (xoso.com.vn, FREE)
- Dashboard web tại / — hiển thị stats + logs
- Webhook mode (Vercel) + Long Polling fallback (local)
"""

import os
import re
import json
import time
import asyncio
import threading
import datetime
import urllib.parse
import requests
from flask import Flask, request, jsonify, render_template_string
from zalo_bot import Bot, Update
from zalo_bot.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from zalo_bot.constants import ChatAction

# ========== CONFIG ==========
ZALO_BOT_TOKEN = os.environ.get("ZALO_BOT_TOKEN", "1903914807132028399:BsUtmLazGynhSDfuGIwkzjcibFDuaCOsKoPauZopkPSiGmtoVexXKBANOjYHQhxU")
# ⚠️ IMPORTANT: The python-zalo-bot library v0.1.9 hardcodes the LEGACY base URL
# (https://bot-api.zapps.me) which returns 404 for getUpdates/getWebhookInfo.
# We MUST override with the official URL https://bot-api.zaloplatforms.com
ZALO_BASE_URL = os.environ.get("ZALO_BASE_URL", "https://bot-api.zaloplatforms.com")
AI_CLOUD_URL = "https://mcp-hub-ai-cloud.vercel.app/api/chat"
POLLINATIONS_URL = "https://image.pollinations.ai/prompt"
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "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")
PORT = int(os.environ.get("PORT", 10000))

# ========== MULTI-PROVIDER AI CONFIG ==========
# Provider API keys (env vars). Defaults allow fallback to Zernio AI Cloud proxy.
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "sk_bb6c27fe7e26d4c5a24ffed5d1c8969ffed0cdfb1592264c01cc7739a4a6ba05")
GROQ_BASE = "https://api.groq.com/openai/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"

# Provider registry — name → (base_url, env_key_var, display_name, model_listing_url)
PROVIDERS = {
    "aicloud": {
        "name": "AI Cloud (Zernio proxy)",
        "needs_key": False,  # uses JWT
        "default_model": "gemini-1.5-flash",
        "free_models": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
    },
    "openrouter": {
        "name": "OpenRouter (437+ models)",
        "needs_key": True,
        "key_env": "OPENROUTER_API_KEY",
        "base_url": OPENROUTER_BASE,
        "default_model": "openrouter/auto",
        "models_endpoint": f"{OPENROUTER_BASE}/models",
        "note": "Free models end with :free — VD: nvidia/nemotron-3.5-lightning:free",
    },
    "groq": {
        "name": "Groq (Llama, Mixtral — siêu nhanh)",
        "needs_key": True,
        "key_env": "GROQ_API_KEY",
        "base_url": GROQ_BASE,
        "default_model": "llama-3.3-70b-versatile",
        "models_endpoint": f"{GROQ_BASE}/models",
        "note": "Lấy key free tại: https://console.groq.com/keys",
    },
    "nvidia": {
        "name": "Nvidia NIM (80+ models)",
        "needs_key": True,
        "key_env": "NVIDIA_API_KEY",
        "base_url": NVIDIA_BASE,
        "default_model": "deepseek-ai/deepseek-v4-flash-0731",
        "models_endpoint": f"{NVIDIA_BASE}/models",
        "note": "Key mặc định list được models nhưng chat cần key riêng",
    },
}

# Per-chat provider+model selection: {chat_id: (provider_key, model_id)}
# Falls back to ("aicloud", "gemini-1.5-flash") if not set
user_provider_selection = {}

def get_chat_ai_config(chat_id: str) -> tuple:
    """Get (provider_key, model_id) for a chat. Returns default if not set."""
    return user_provider_selection.get(chat_id, ("aicloud", "gemini-1.5-flash"))

def set_chat_ai_config(chat_id: str, provider: str, model: str = None):
    """Set provider+model for a chat."""
    if provider not in PROVIDERS:
        return False
    if model is None:
        model = PROVIDERS[provider]["default_model"]
    user_provider_selection[chat_id] = (provider, model)
    return True

SYSTEM_PROMPT = """Bạn là NhutBot — trợ lý AI thân thiện trên Zalo.
Trả lời ngắn gọn, hữu ích, bằng tiếng Việt.
Nếu người dùng hỏi code, trả lời với code block rõ ràng."""

# ========== STATE ==========
stats = {
    "messages_received": 0,
    "messages_sent": 0,
    "images_generated": 0,
    "ai_calls": 0,
    "search_count": 0,
    "xoso_count": 0,
    "weather_count": 0,
    "wiki_count": 0,
    "currency_count": 0,
    "crypto_count": 0,
    "url_count": 0,
    "ip_count": 0,
    "yt_count": 0,
    "dict_count": 0,
    "joke_count": 0,
    "tiktok_count": 0,
    "ytdl_count": 0,
    "ytmp3_count": 0,
    "news_count": 0,
    "github_count": 0,
    "quote_count": 0,
    "fact_count": 0,
    "uuid_count": 0,
    "hash_count": 0,
    "color_count": 0,
    "gold_count": 0,
    "country_count": 0,
    "tv_count": 0,
    "binance_count": 0,
    "binary_count": 0,
    "horoscope_count": 0,
    "reverse_count": 0,
    "palindrome_count": 0,
    "errors": 0,
    "started_at": time.time(),
}
recent_logs = []
ai_jwt = ""

# Simple in-memory cache: {key: (timestamp, value)}
_cache = {}

def cache_get(key: str, ttl_seconds: int = 300):
    """Get value from cache if not expired. Returns None if missing/expired."""
    if key in _cache:
        ts, val = _cache[key]
        if time.time() - ts < ttl_seconds:
            return val
        else:
            del _cache[key]
    return None

def cache_set(key: str, value):
    _cache[key] = (time.time(), value)
    # Cleanup old entries (keep max 200)
    if len(_cache) > 200:
        oldest = sorted(_cache.items(), key=lambda x: x[1][0])[:50]
        for k, _ in oldest:
            _cache.pop(k, None)

def log(msg):
    entry = f"[{time.strftime('%H:%M:%S')}] {msg}"
    recent_logs.append(entry)
    if len(recent_logs) > 50:
        recent_logs.pop(0)
    print(entry)


# ========== AI ==========

def get_jwt():
    global ai_jwt
    try:
        resp = requests.get("https://nhutcoder-team-v2.vercel.app/api/auth/debug-token", timeout=15)
        token = resp.json().get("mint", {}).get("token", "")
        if token:
            ai_jwt = token
            log(f"AI JWT fetched (len={len(token)})")
            return token
    except Exception as e:
        log(f"AI JWT error: {e}")
    return ""

def _get_provider_api_key(provider: str) -> str:
    """Get API key for a provider."""
    p = PROVIDERS.get(provider, {})
    if not p.get("needs_key"):
        return ""
    env_var = p.get("key_env", "")
    return os.environ.get(env_var, "")

def _fetch_provider_models(provider: str, limit: int = 30) -> list:
    """Fetch real-time model list from a provider's /models endpoint."""
    p = PROVIDERS.get(provider, {})
    endpoint = p.get("models_endpoint")
    if not endpoint:
        return []
    
    # Cache key — refresh every hour
    cache_key = f"models:{provider}"
    cached = cache_get(cache_key, ttl_seconds=3600)
    if cached:
        return cached[:limit]
    
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        api_key = _get_provider_api_key(provider)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        r = requests.get(endpoint, headers=headers, timeout=15)
        if r.status_code != 200:
            return [{"id": f"ERROR: HTTP {r.status_code}", "error": r.text[:100]}]
        data = r.json()
        # OpenAI-compatible: {data: [{id, ...}]}
        models = data.get("data", []) or data.get("models", [])
        # Normalize
        result = []
        for m in models[:200]:  # cap at 200
            mid = m.get("id") if isinstance(m, dict) else str(m)
            if not mid:
                continue
            entry = {"id": mid}
            if isinstance(m, dict):
                if m.get("context_length"):
                    entry["context"] = m.get("context_length")
                pr = m.get("pricing", {})
                if isinstance(pr, dict) and pr.get("prompt"):
                    try:
                        entry["price"] = f"${float(pr['prompt'])*1e6:.2f}/Mtok"
                    except Exception:
                        pass
                if m.get("owned_by"):
                    entry["owner"] = m["owned_by"]
            result.append(entry)
        cache_set(cache_key, result)
        return result[:limit]
    except Exception as e:
        return [{"id": f"ERROR: {e}", "error": str(e)[:100]}]

def _call_provider(provider: str, model: str, messages: list, max_tokens: int = 1024, temperature: float = 0.7) -> dict:
    """Call a specific provider with the given model. Returns {ok, content, error}."""
    p = PROVIDERS.get(provider)
    if not p:
        return {"ok": False, "error": f"Provider '{provider}' không tồn tại"}
    
    # AI Cloud uses Zernio JWT
    if provider == "aicloud":
        global ai_jwt
        if not ai_jwt:
            ai_jwt = get_jwt()
        if not ai_jwt:
            return {"ok": False, "error": "Không lấy được JWT từ AI Cloud"}
        try:
            resp = requests.post(AI_CLOUD_URL, headers={
                "Authorization": f"Bearer {ai_jwt}",
                "Content-Type": "application/json",
            }, json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }, timeout=60)
            if resp.status_code == 200:
                content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                actual_model = resp.json().get("model", model)
                return {"ok": True, "content": content, "model": actual_model}
            elif resp.status_code == 401:
                ai_jwt = get_jwt()
                if ai_jwt:
                    return _call_provider(provider, model, messages, max_tokens, temperature)
            return {"ok": False, "error": f"AI Cloud HTTP {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"ok": False, "error": f"Lỗi: {e}"}
    
    # Other providers — OpenAI-compatible API
    api_key = _get_provider_api_key(provider)
    if not api_key:
        return {"ok": False, "error": f"Chưa set {p.get('key_env','API_KEY')}. /providers để xem hướng dẫn"}
    
    base_url = p.get("base_url")
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # OpenRouter recommends X-Title
        if provider == "openrouter":
            headers["X-Title"] = "NhutBot-Zalo"
            headers["HTTP-Referer"] = "https://zalo-bot-three.vercel.app/"
        
        resp = requests.post(f"{base_url}/chat/completions", headers=headers, json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            actual_model = data.get("model", model)
            return {"ok": True, "content": content, "model": actual_model}
        return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": f"Lỗi: {e}"}

def ai_reply(message: str, chat_id: str = None) -> str:
    """AI reply with per-chat provider+model support."""
    global ai_jwt
    stats["ai_calls"] += 1
    
    # Get chat-specific config (default to AI Cloud)
    provider, model = ("aicloud", "gemini-1.5-flash")
    if chat_id:
        provider, model = get_chat_ai_config(chat_id)
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]
    
    result = _call_provider(provider, model, messages)
    if result.get("ok"):
        return result.get("content", "?")
    # Fallback to AI Cloud if selected provider fails
    if provider != "aicloud":
        log(f"⚠️ {provider}/{model} failed: {result.get('error','?')[:80]}. Falling back to AI Cloud.")
        result = _call_provider("aicloud", "gemini-1.5-flash", messages)
        if result.get("ok"):
            return f"⚠️ Provider {provider}/{model} lỗi, dùng AI Cloud fallback:\n\n" + result.get("content", "?")
    return f"❌ Lỗi AI: {result.get('error', 'unknown')}"

def make_image_url(prompt: str) -> str:
    import urllib.parse
    return f"{POLLINATIONS_URL}/{urllib.parse.quote(prompt[:500])}?width=768&height=768&model=flux&nologo=true"


# ========== WEB SEARCH (Tavily) ==========

def search_web(query: str, max_results: int = 5) -> dict:
    """Search the web using Tavily API. Returns dict with 'answer' and 'results'."""
    try:
        from tavily import TavilyClient
        client = TavilyClient(TAVILY_API_KEY)
        resp = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
        )
        answer = resp.get("answer", "")
        results = resp.get("results", [])
        return {"answer": answer, "results": results}
    except Exception as e:
        return {"answer": "", "results": [], "error": str(e)}


# ========== LOTTERY (Xổ số) — FREE via xoso.com.vn ==========

XOSO_BASE = "https://xoso.com.vn"
XOSO_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Prize labels in Vietnamese for display
PRIZE_LABELS = {
    "DB": "🎯 Đặc biệt",
    "1": "🥇 Giải nhất",
    "2": "🥈 Giải nhì",
    "3": "🥉 Giải ba",
    "4": "4️⃣ Giải tư",
    "5": "5️⃣ Giải năm",
    "6": "6️⃣ Giải sáu",
    "7": "7️⃣ Giải bảy",
    "8": "8️⃣ Giải tám",
}

# Province dictionary — supported provinces with their slugs and codes.
# Key = alias user can type (lowercase, no-diacritics), value = (display_name, slug, code, region)
# region: 'mb' = Miền Bắc, 'mn' = Miền Nam, 'mt' = Miền Trung
PROVINCES = {
    # Miền Bắc (single MB region — every province shares same draw)
    "mb":        ("Miền Bắc",        None,    "mb",  "mb"),
    "mien bac":  ("Miền Bắc",        None,    "mb",  "mb"),
    "hanoi":     ("Hà Nội",          None,    "mb",  "mb"),
    "ha noi":    ("Hà Nội",          None,    "mb",  "mb"),
    "haiphong":  ("Hải Phòng",       None,    "mb",  "mb"),
    "hai phong": ("Hải Phòng",       None,    "mb",  "mb"),
    "quangninh": ("Quảng Ninh",      None,    "mb",  "mb"),
    # Miền Nam
    "hcm":       ("TP. Hồ Chí Minh", "ho-chi-minh", "hcm", "mn"),
    "hcmcity":   ("TP. Hồ Chí Minh", "ho-chi-minh", "hcm", "mn"),
    "tphcm":     ("TP. Hồ Chí Minh", "ho-chi-minh", "hcm", "mn"),
    "saigon":    ("TP. Hồ Chí Minh", "ho-chi-minh", "hcm", "mn"),
    "dn":        ("Đồng Nai",        "dong-nai",   "dn",  "mn"),
    "dongnai":   ("Đồng Nai",        "dong-nai",   "dn",  "mn"),
    "ct":        ("Cần Thơ",         "can-tho",    "ct",  "mn"),
    "cantho":    ("Cần Thơ",         "can-tho",    "ct",  "mn"),
    "st":        ("Sóc Trăng",       "soc-trang",  "st",  "mn"),
    "soctrang":  ("Sóc Trăng",       "soc-trang",  "st",  "mn"),
    "bl":        ("Bạc Liêu",        "bac-lieu",   "bl",  "mn"),
    "baclieu":   ("Bạc Liêu",        "bac-lieu",   "bl",  "mn"),
    "btr":       ("Bến Tre",         "ben-tre",    "btr", "mn"),
    "bentre":    ("Bến Tre",         "ben-tre",    "btr", "mn"),
    "vt":        ("Bà Rịa - Vũng Tàu", "vung-tau", "vt", "mn"),
    "vungtau":   ("Bà Rịa - Vũng Tàu", "vung-tau", "vt", "mn"),
    "dongthap":  ("Đồng Tháp",       "dong-thap",  "dtp", "mn"),
    "dt":        ("Đồng Tháp",       "dong-thap",  "dtp", "mn"),
    "tiengiang": ("Tiền Giang",      "tien-giang", "tg",  "mn"),
    "an giang":  ("An Giang",        "an-giang",   "ag",  "mn"),
    "angiang":   ("An Giang",        "an-giang",   "ag",  "mn"),
    "kien giang":("Kiên Giang",     "kien-giang", "kg",  "mn"),
    "kiengiang": ("Kiên Giang",      "kien-giang", "kg",  "mn"),
    "longan":    ("Long An",         "long-an",    "la",  "mn"),
    "long an":   ("Long An",         "long-an",    "la",  "mn"),
    "tayninh":   ("Tây Ninh",        "tay-ninh",   "tn",  "mn"),
    "vinhlong":  ("Vĩnh Long",       "vinh-long",  "vl",  "mn"),
    "travinh":   ("Trà Vinh",        "tra-vinh",   "tv",  "mn"),
    "hau giang": ("Hậu Giang",       "hau-giang",  "hg",  "mn"),
    "hau giang": ("Hậu Giang",       "hau-giang",  "hg",  "mn"),
    # Miền Trung
    "dna":       ("Đà Nẵng",         "da-nang",    "dna", "mt"),
    "danang":    ("Đà Nẵng",         "da-nang",    "dna", "mt"),
    "da nang":   ("Đà Nẵng",         "da-nang",    "dna", "mt"),
    "kh":        ("Khánh Hòa",       "khanh-hoa",  "kh",  "mt"),
    "khanhhoa":  ("Khánh Hòa",       "khanh-hoa",  "kh",  "mt"),
    "nhatrang":  ("Nha Trang",       "khanh-hoa",  "kh",  "mt"),
    "qna":       ("Quảng Nam",       "quang-nam",  "qna", "mt"),
    "quangnam":  ("Quảng Nam",       "quang-nam",  "qna", "mt"),
    "dlk":       ("Đắk Lắk",         "dak-lak",    "dlk", "mt"),
    "daklak":    ("Đắk Lắk",         "dak-lak",    "dlk", "mt"),
    "hue":       ("Thừa Thiên Huế",  "thua-thien-hue", "tth", "mt"),
    "thuathienhue": ("Thừa Thiên Huế", "thua-thien-hue", "tth", "mt"),
    "quangngai": ("Quảng Ngãi",      "quang-ngai", "qng", "mt"),
    "binhdinh":  ("Bình Định",       "binh-dinh",  "bd",  "mt"),
    "phuyen":    ("Phú Yên",         "phu-yen",    "py",  "mt"),
    "quangbinh": ("Quảng Bình",      "quang-binh", "qb",  "mt"),
    "quangtri":  ("Quảng Trị",       "quang-tri",  "qt",  "mt"),
    "ninhthuan":("Ninh Thuận",       "ninh-thuan", "nt",  "mt"),
    "binhthuan":("Bình Thuận",       "binh-thuan", "bth", "mt"),
    "kontum":    ("Kon Tum",         "kon-tum",    "kt",  "mt"),
    "gialai":    ("Gia Lai",         "gia-lai",    "gl",  "mt"),
    "daknong":   ("Đắk Nông",        "dak-nong",   "dno", "mt"),
    # Region shortcuts
    "mn":        ("Miền Nam",        None,    "mn", "mn"),
    "mien nam":  ("Miền Nam",        None,    "mn", "mn"),
    "mt":        ("Miền Trung",      None,    "mt", "mt"),
    "mien trung":("Miền Trung",      None,    "mt", "mt"),
}

def _normalize_province_alias(input_str: str) -> str:
    """Normalize user input to match PROVINCES dict key."""
    s = input_str.lower().strip()
    # Remove Vietnamese diacritics
    import unicodedata
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9 ]', '', s)
    s = s.strip()
    return s


def resolve_province(user_input: str) -> tuple:
    """Resolve user input to (display_name, slug, code, region).
    Returns None if not found.
    """
    key = _normalize_province_alias(user_input)
    if key in PROVINCES:
        return PROVINCES[key]
    # Try short match (first 3 chars)
    for k, v in PROVINCES.items():
        if k.startswith(key[:3]) and len(key) >= 2:
            return v
    return None


def fetch_xoso_results(province_input: str = "mb", date_str: str = None) -> dict:
    """
    Fetch lottery results from xoso.com.vn (FREE, no API key).
    province_input: province alias (hcm/danang/hanoi/mb/mn/mt) or province name
    date_str: 'DD-MM-YYYY' format, default = today
    Returns dict: {date, province, region, prizes: {prize_code: [numbers]}, error: str}
    """
    resolved = resolve_province(province_input)
    if not resolved:
        return {"error": f"Không nhận diện được tỉnh '{province_input}'. Gõ /xoso để xem danh sách tỉnh."}
    
    display_name, slug, code, region = resolved
    if not date_str:
        date_str = datetime.datetime.now().strftime("%d-%m-%Y")
    
    # Cache: results for same province+date don't change after draw (5 min TTL is plenty)
    cache_key = f"xoso:{region}:{slug or 'mb'}:{date_str}"
    cached = cache_get(cache_key, ttl_seconds=300)
    if cached:
        log(f"💾 cache hit {cache_key}")
        return cached
    
    # Build URL based on whether it's MB (dated URL) or province (always-today page)
    if region == "mb":
        # Miền Bắc uses dated URL: /xsmb-DD-MM-YYYY.html
        url = f"{XOSO_BASE}/xsmb-{date_str}.html"
        # Span prefix: mb_prize{CODE}_item0
        prefix = "mb"
    else:
        # Province page: /xo-so-{slug}/xs{code}-p1.html (always today's results)
        url = f"{XOSO_BASE}/xo-so-{slug}/xs{code}-p1.html"
        # Province pages use 'xsdai_' prefix regardless of province
        prefix = "xsdai"
    
    try:
        resp = requests.get(url, headers=XOSO_HEADERS, timeout=15)
        if resp.status_code == 404:
            return {"error": f"Chưa có kết quả xổ số {display_name} ngày {date_str} (có thể chưa quay)."}
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return {"error": f"Lỗi tải KQXS: {e}"}
    
    # Parse prize spans: <span id="{prefix}_prize{CODE}_item{N}">NUMBER</span>
    prizes = {}
    # Match DB (case-insensitive) and digits 1-8
    pattern = re.compile(
        rf'{prefix}_prize(db|[1-8])_item\d+[^>]*>\s*([0-9\s]+?)\s*</span>',
        re.IGNORECASE
    )
    for m in pattern.finditer(html):
        code_raw = m.group(1).upper()
        if code_raw == "DB":
            code_raw = "DB"
        num = re.sub(r'\s+', '', m.group(2))
        if code_raw not in prizes:
            prizes[code_raw] = []
        if num and num not in prizes[code_raw]:
            prizes[code_raw].append(num)
    
    if not prizes:
        return {"error": f"Không tìm thấy kết quả xổ số cho {display_name} ngày {date_str}."}
    
    # Find title to confirm date
    title_match = re.search(r'<title>([^<]+)</title>', html)
    title = title_match.group(1).strip() if title_match else ""
    
    result = {
        "province": display_name,
        "region": region.upper(),
        "date": date_str,
        "title": title,
        "prizes": prizes,
    }
    cache_set(cache_key, result)
    return result


def check_lottery_ticket(user_number: str, province_input: str = "mb", date_str: str = None) -> str:
    """
    Check a user's lottery number against today's results.
    user_number: 2-6 digit number (or comma-separated multiple numbers)
    Returns formatted message with results.
    """
    # Normalize input: extract all numbers
    numbers = re.findall(r'\d+', user_number)
    if not numbers:
        return "❌ Vui lòng nhập số vé. VD: /xoso 94504 hoặc /xoso 04,94504"
    
    # Fetch results
    result = fetch_xoso_results(province_input, date_str)
    if "error" in result:
        return f"❌ {result['error']}"
    
    prizes = result["prizes"]
    region_name = {"MB": "Miền Bắc", "MN": "Miền Nam", "MT": "Miền Trung"}.get(result["region"], result["region"])
    province_name = result["province"]
    
    msg_parts = [
        f"🎰 DÒ VÉ SỐ {province_name} ({region_name})",
        f"📅 Ngày: {result['date']}",
        f"{'─' * 30}",
        f"🎟️ Số của bạn: {', '.join(numbers)}",
        f"{'─' * 30}",
        "",
    ]
    
    # Check each user number
    wins = []
    for num in numbers:
        # Match logic:
        # - DB (5-6 digits): exact match
        # - G1 (5 digits): exact match
        # - 2-digit input: match last 2 digits of any prize
        # - 3-digit input: match last 3 digits of any prize (lô 3 càng)
        for code, win_nums in prizes.items():
            for win_num in win_nums:
                matched = False
                if len(num) >= 5 and num == win_num:
                    matched = True
                elif len(num) == 2 and len(win_num) >= 2 and win_num[-2:] == num:
                    matched = True
                elif len(num) == 3 and len(win_num) >= 3 and win_num[-3:] == num:
                    matched = True
                elif num == win_num:
                    matched = True
                
                if matched:
                    label = PRIZE_LABELS.get(code, f"Giải {code}")
                    wins.append(f"🎉 Số **{num}** trúng {label}! (KQ: {win_num})")
    
    if wins:
        msg_parts.append("🥳 KẾT QUẢ DÒ:")
        msg_parts.extend(f"  {w}" for w in wins)
        msg_parts.append("")
        msg_parts.append("Chúc mừng bạn! 🎊")
    else:
        msg_parts.append("😢 Rất tiếc, không trúng giải.")
        msg_parts.append("")
        # Show today's DB prize for reference
        db_prize = prizes.get("DB", [])
        if db_prize:
            msg_parts.append(f"🎯 KQ Giải Đặc biệt hôm nay: {', '.join(db_prize)}")
    
    msg_parts.append(f"{'─' * 30}")
    msg_parts.append("📋 Tất cả KQXS hôm nay:")
    for code in ["DB", "1", "2", "3", "4", "5", "6", "7", "8"]:
        if code in prizes:
            label = PRIZE_LABELS.get(code, f"Giải {code}")
            nums = ", ".join(prizes[code])
            msg_parts.append(f"  {label}: {nums}")
    
    msg_parts.append("")
    msg_parts.append("📊 Nguồn: xoso.com.vn")
    
    return "\n".join(msg_parts)


# ========== WEATHER — Open-Meteo (FREE, no API key) ==========

OPEN_METEO_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"

# WMO weather code → Vietnamese description (with emoji)
WMO_VI = {
    0:  ("☀️ Trời quang", "Trời quang"),
    1:  ("🌤️ Trời hầu như quang", "Trời hầu như quang"),
    2:  ("⛅ Có mây rải rác", "Có mây rải rác"),
    3:  ("☁️ Trời u ám", "Trời u ám"),
    45: ("🌫️ Có sương mù", "Sương mù"),
    48: ("🌫️ Sương mù đóng băng", "Sương mù đóng băng"),
    51: ("🌦️ Mưa phùn nhẹ", "Mưa phùn nhẹ"),
    53: ("🌦️ Mưa phùn vừa", "Mưa phùn vừa"),
    55: ("🌧️ Mưa phùn dày", "Mưa phùn dày"),
    56: ("🌧️ Mưa phùn lạnh", "Mưa phùn lạnh"),
    57: ("🌧️ Mưa phùn lạnh", "Mưa phùn lạnh"),
    61: ("🌧️ Mưa nhỏ", "Mưa nhỏ"),
    63: ("🌧️ Mưa vừa", "Mưa vừa"),
    65: ("⛈️ Mưa to", "Mưa to"),
    66: ("🌧️ Mưa lạnh", "Mưa lạnh"),
    67: ("🌧️ Mưa lạnh", "Mưa lạnh"),
    71: ("🌨️ Tuyết rơi nhẹ", "Tuyết rơi nhẹ"),
    73: ("🌨️ Tuyết rơi vừa", "Tuyết rơi vừa"),
    75: ("❄️ Tuyết rơi dày", "Tuyết rơi dày"),
    77: ("❄️ Tuyết hạt", "Tuyết hạt"),
    80: ("🌦️ Mưa rào nhẹ", "Mưa rào nhẹ"),
    81: ("🌧️ Mưa rào vừa", "Mưa rào vừa"),
    82: ("⛈️ Mưa rào rất to", "Mưa rào rất to"),
    85: ("🌨️ Mưa tuyết rào", "Mưa tuyết rào"),
    86: ("🌨️ Mưa tuyết rào", "Mưa tuyết rào"),
    95: ("⛈️ Dông", "Dông"),
    96: ("⛈️ Dông có mưa đá", "Dông có mưa đá"),
    99: ("⛈️ Dông có mưa đá", "Dông có mưa đá"),
}

def wmo_to_vi(code: int) -> str:
    """Convert WMO weather code to emoji + Vietnamese description."""
    entry = WMO_VI.get(int(code))
    return entry[0] if entry else f"🌡️ Mã thời tiết {code}"


def geocode_city(city: str) -> dict:
    """Geocode a city name → {name, latitude, longitude, country}."""
    try:
        r = requests.get(OPEN_METEO_GEOCODE, params={
            "name": city,
            "count": 1,
            "language": "vi",
            "format": "json",
        }, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data.get("results"):
            return {"error": f"Không tìm thấy thành phố '{city}'."}
        place = data["results"][0]
        return {
            "name": place["name"],
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "country": place.get("country", ""),
        }
    except Exception as e:
        return {"error": f"Lỗi tìm thành phố: {e}"}


def fetch_weather(lat: float, lon: float, days: int = 7) -> dict:
    """Fetch current weather + N-day forecast from Open-Meteo (FREE, no API key)."""
    # Cache weather by lat/lon/days for 10 min (current conditions change slowly)
    cache_key = f"weather:{lat:.2f}:{lon:.2f}:{days}"
    cached = cache_get(cache_key, ttl_seconds=600)
    if cached:
        log(f"💾 cache hit {cache_key}")
        return cached
    try:
        r = requests.get(OPEN_METEO_FORECAST, params={
            "latitude": lat,
            "longitude": lon,
            "current": ("temperature_2m,relative_humidity_2m,apparent_temperature,"
                        "precipitation,weather_code,wind_speed_10m,wind_direction_10m"),
            "daily": ("weather_code,temperature_2m_max,temperature_2m_min,"
                      "precipitation_probability_max,precipitation_sum,sunrise,sunset,wind_speed_10m_max"),
            "timezone": "Asia/Ho_Chi_Minh",
            "forecast_days": days,
        }, timeout=10)
        r.raise_for_status()
        data = r.json()
        cache_set(cache_key, data)
        return data
    except Exception as e:
        return {"error": f"Lỗi tải thời tiết: {e}"}


def get_weather_report(city: str, days: int = 7) -> str:
    """One-shot: city name → formatted weather report in Vietnamese."""
    place = geocode_city(city)
    if "error" in place:
        return f"❌ {place['error']}"
    
    w = fetch_weather(place["latitude"], place["longitude"], days)
    if "error" in w:
        return f"❌ {w['error']}"
    
    # Build the message
    parts = []
    parts.append(f"🌤️ THỜI TIẾT: {place['name']}, {place['country']}")
    parts.append(f"📍 Vị trí: {place['latitude']:.2f}, {place['longitude']:.2f}")
    parts.append("─" * 30)
    
    # Current conditions
    c = w.get("current", {})
    if c:
        parts.append("⏱️ HIỆN TẠI")
        temp = c.get("temperature_2m", 0)
        feels = c.get("apparent_temperature", 0)
        humidity = c.get("relative_humidity_2m", 0)
        precip = c.get("precipitation", 0)
        wind = c.get("wind_speed_10m", 0)
        wind_dir = c.get("wind_direction_10m", 0)
        code = c.get("weather_code", 0)
        parts.append(f"{wmo_to_vi(code)}")
        parts.append(f"🌡️ Nhiệt độ: {temp}°C (cảm giác {feels}°C)")
        parts.append(f"💧 Độ ẩm: {humidity}%")
        parts.append(f"💨 Gió: {wind} km/h (hướng {wind_dir}°)")
        parts.append(f"🌧️ Mưa: {precip} mm")
    
    # Daily forecast
    d = w.get("daily", {})
    if d and d.get("time"):
        parts.append("")
        parts.append(f"📅 DỰ BÁO {len(d['time'])} NGÀY")
        for i, date in enumerate(d["time"]):
            code = d.get("weather_code", [0])[i]
            max_t = d.get("temperature_2m_max", [0])[i]
            min_t = d.get("temperature_2m_min", [0])[i]
            rain_prob = d.get("precipitation_probability_max", [0])[i]
            rain_mm = d.get("precipitation_sum", [0])[i]
            wind_max = d.get("wind_speed_10m_max", [0])[i]
            desc = wmo_to_vi(code).split(" ", 1)[-1] if " " in wmo_to_vi(code) else wmo_to_vi(code)
            # Format date DD/MM
            try:
                dd = date.split("-")[2]
                mm = date.split("-")[1]
                date_str = f"{dd}/{mm}"
            except Exception:
                date_str = date
            parts.append(
                f"  {date_str}  {desc:<22} "
                f"{min_t}–{max_t}°C  mưa {rain_prob}% ({rain_mm}mm)  gió {wind_max}km/h"
            )
    
    # Sunrise/sunset for today
    sunrise = d.get("sunrise", [None])[0] if d else None
    sunset = d.get("sunset", [None])[0] if d else None
    if sunrise or sunset:
        parts.append("")
        if sunrise:
            sr = sunrise.split("T")[1] if "T" in sunrise else sunrise
            parts.append(f"🌅 Bình minh: {sr}")
        if sunset:
            ss = sunset.split("T")[1] if "T" in sunset else sunset
            parts.append(f"🌇 Hoàng hôn: {ss}")
    
    parts.append("")
    parts.append("📡 Nguồn: Open-Meteo (FREE, no API key)")
    
    return "\n".join(parts)


# ========== BOT LOGIC ==========

bot_app = None

async def cmd_start(update: Update, context):
    name = update.effective_user.display_name if update.effective_user else "bạn"
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    await update.message.reply_text(
        f"🤖 Chào {name}!\n\nTôi là NhutBot trên Zalo.\n\n"
        "📝 41 LỆNH:\n\n"
        "🤖 AI (multi-provider):\n"
        "• Nhắn tin → AI trả lời\n"
        "• /providers — Xem providers\n"
        "• /models <provider> — List models\n"
        "• /setmodel <provider> [model] — Chọn\n"
        "• /image <mô tả> → Tạo ảnh AI\n"
        "• /code <câu hỏi> → Hỏi code\n"
        "• /translate [lang] <text> → Dịch\n\n"
        "🔍 Tìm kiếm:\n"
        "• /search <từ khóa> → Tìm web\n"
        "• /news [chủ đề] → Tin tức\n"
        "• /wiki [lang] <query> → Wikipedia\n"
        "• /youtube <query> → Tìm video YouTube\n"
        "• /define <word> → Từ điển Anh\n"
        "• /country <tên> → Quốc gia\n"
        "• /tv <tên> → TV show\n"
        "• /github <user> → GitHub profile\n\n"
        "🎬 TẢI MEDIA (NO LOGO):\n"
        "• /tiktok <url> → TikTok không logo\n"
        "• /ytdl <url> → Video YouTube\n"
        "• /ytmp3 <url> → YouTube sang MP3\n\n"
        "💰 Tài chính:\n"
        "• /currency <amt> <f> <to> → Đổi tiền\n"
        "• /crypto <symbol> → Giá crypto\n"
        "• /binance <pair> → Binance ticker\n"
        "• /gold → Giá vàng\n\n"
        "🎰 Xổ số:\n"
        "• /xoso <số> [tỉnh] → Dò vé số\n\n"
        "🌤️ Khác:\n"
        "• /weather <nơi> → Thời tiết\n"
        "• /calc <biểu thức> → Máy tính\n"
        "• /time [múi giờ] → Giờ\n"
        "• /horoscope <sign> → Cung hoàng đạo\n"
        "• /quote → Câu nói hay\n"
        "• /fact → Fact ngẫu nhiên\n"
        "• /joke [cat] → Cười\n\n"
        "🛠️ Tiện ích:\n"
        "• /qr <text> → QR code\n"
        "• /shorten <url> → Rút gọn URL\n"
        "• /base64 enc|dec <text>\n"
        "• /binary <num> [base] → Convert base\n"
        "• /password [length] → Sinh mật khẩu\n"
        "• /hash <algo> <text> → MD5/SHA\n"
        "• /uuid [count] → Sinh UUID\n"
        "• /color <hex> → Thông tin màu\n"
        "• /ip [ip] → Tra IP\n"
        "• /reverse <text> → Đảo text\n"
        "• /palindrome <text> → Check palindrome\n\n"
        "Gõ /help để xem chi tiết!"
    )
    stats["messages_sent"] += 1
    log(f"/start from {name}")

async def cmd_help(update: Update, context):
    await update.message.reply_text(
        "📋 NhutBot v7 — 41 LỆNH\n\n"
        "🤖 AI & MULTI-PROVIDER\n"
        "• Nhắn tin → AI trả lời\n"
        "• /providers — 4 providers: AI Cloud, OpenRouter, Groq, Nvidia NIM\n"
        "• /models <provider> [filter] — List models real-time\n"
        "• /setmodel <provider> [model] — Chọn provider+model cho chat\n"
        "    VD: /setmodel groq llama-3.3-70b-versatile\n"
        "    VD: /setmodel openrouter nvidia/nemotron-3.5-lightning:free\n"
        "• /image <mô tả> → Tạo ảnh AI\n"
        "• /code <câu hỏi> → Hỏi code\n"
        "• /translate [lang] <text> → Dịch\n\n"
        "🎬 TẢI VIDEO/ẢNH (NO LOGO)\n"
        "• /tiktok <url> [music] → TikTok\n"
        "• /ytdl <url> → YouTube video\n"
        "• /ytmp3 <url> → YouTube MP3\n\n"
        "🔍 TÌM KIẾM & TRA CỨU\n"
        "• /search <từ khóa> → Tìm web\n"
        "• /news [chủ đề] → Tin tức\n"
        "• /wiki [vi|en] <query> → Wikipedia\n"
        "• /youtube <query> → Tìm YouTube\n"
        "• /define <word> → Từ điển Anh\n"
        "• /country <tên> → Quốc gia (Wiki)\n"
        "• /tv <tên> → TV show (TVMaze)\n"
        "• /github <user> → GitHub profile\n\n"
        "💰 TÀI CHÍNH\n"
        "• /currency <amt> <from> <to> → Đổi tiền\n"
        "• /crypto <symbol> → Crypto (CoinGecko)\n"
        "• /binance <pair> → Binance ticker\n"
        "• /gold → Giá vàng (USD/VND)\n\n"
        "🎰 XỔ SỐ\n"
        "• /xoso <số> [tỉnh] → Dò vé số\n\n"
        "🌤️ KHÁC\n"
        "• /weather <nơi> [ngày] → Thời tiết\n"
        "• /calc <biểu thức> → Máy tính\n"
        "• /time [múi giờ] → Giờ\n"
        "• /horoscope <sign> → Cung hoàng đạo\n"
        "• /quote → Câu nói hay\n"
        "• /fact → Fact ngẫu nhiên\n"
        "• /joke [cat] → Cười\n\n"
        "🛠️ TIỆN ÍCH\n"
        "• /qr <text> → QR code\n"
        "• /shorten <url> → Rút gọn URL\n"
        "• /base64 enc|dec <text> → Base64\n"
        "• /binary <num> [base] → Convert base\n"
        "• /password [length] → Sinh mật khẩu\n"
        "• /hash <algo> <text> → MD5/SHA1/SHA256\n"
        "• /uuid [count] → Sinh UUID v4\n"
        "• /color <hex> → Info màu + preview\n"
        "• /ip [ip] → Tra IP\n"
        "• /reverse <text> → Đảo text\n"
        "• /palindrome <text> → Check palindrome\n\n"
        "📊 Dashboard: https://zalo-bot-three.vercel.app/\n"
        "📋 Logs: https://zalo-bot-three.vercel.app/logs"
    )
    stats["messages_sent"] += 1

async def cmd_image(update: Update, context):
    if not context.args:
        await update.message.reply_text("🎨 Gõ: /image <mô tả ảnh>\nVD: /image con mèo trên mặt trăng")
        return
    prompt = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    try:
        url = make_image_url(prompt)
        await update.message.reply_photo(photo=url, caption=f'🎨 "{prompt}"\n\nPowered by Pollinations.ai')
        stats["images_generated"] += 1
        log(f"/image: {prompt[:50]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi tạo ảnh: {e}")
        stats["errors"] += 1

async def cmd_code(update: Update, context):
    if not context.args:
        await update.message.reply_text("💻 Gõ: /code <câu hỏi>\nVD: /code hàm fibonacci Python")
        return
    question = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    reply = ai_reply(f"Bạn là chuyên gia lập trình. Trả lời ngắn gọn với code:\n\n{question}", chat_id=update.message.chat.id)
    await update.message.reply_text(reply)
    stats["messages_sent"] += 1
    log(f"/code: {question[:50]}")


async def cmd_search(update: Update, context):
    """Search the web using Tavily API."""
    if not context.args:
        await update.message.reply_text(
            "🔍 Gõ: /search <từ khóa>\n\n"
            "VD:\n"
            "• /search giá vàng hôm nay\n"
            "• /search tỷ giá USD VND\n"
            "• /search tin tức AI mới nhất"
        )
        return
    query = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/search: {query[:60]}")
    
    result = search_web(query, max_results=5)
    stats["search_count"] += 1
    
    if result.get("error"):
        await update.message.reply_text(f"❌ Lỗi tìm kiếm: {result['error']}")
        stats["errors"] += 1
        return
    
    parts = [f"🔍 KẾT QUẢ TÌM KIẾM: \"{query}\"", "─" * 30, ""]
    
    if result.get("answer"):
        parts.append("💡 Câu trả lời AI:")
        parts.append(result["answer"][:1500])
        parts.append("")
        parts.append("─" * 30)
    
    if result.get("results"):
        parts.append("📎 Nguồn tham khảo:")
        for i, item in enumerate(result["results"][:5], 1):
            title = item.get("title", "N/A")[:80]
            url = item.get("url", "")
            snippet = (item.get("content") or "")[:150].replace("\n", " ")
            parts.append(f"\n{i}. {title}")
            if snippet:
                parts.append(f"   {snippet}...")
            if url:
                parts.append(f"   🔗 {url}")
    
    reply = "\n".join(parts)
    # Split long messages
    if len(reply) > 1900:
        for i in range(0, len(reply), 1900):
            await update.message.reply_text(reply[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(reply)
    
    stats["messages_sent"] += 1
    log(f"🤖 Search reply sent ({len(reply)} chars)")


async def cmd_xoso(update: Update, context):
    """Check lottery ticket — /xoso <number> [tỉnh] [date]"""
    if not context.args:
        await update.message.reply_text(
            "🎰 DÒ VÉ SỐ THEO TỈNH\n\n"
            "Cách dùng:\n"
            "• /xoso <số> → Dò KQXS Miền Bắc hôm nay\n"
            "• /xoso <số> <tỉnh> → Dò theo tỉnh\n"
            "• /xoso <số> <tỉnh> DD-MM-YYYY → Dò ngày cụ thể (chỉ MB)\n\n"
            "VD:\n"
            "  /xoso 94504\n"
            "  /xoso 94504,04,15\n"
            "  /xoso 94504 hcm\n"
            "  /xoso 04 danang\n"
            "  /xoso 94504 mb 08-09-2026\n\n"
            "🏙️ TỈNH HỖ TRỢ:\n"
            "Miền Bắc: hanoi, haiphong, quangninh, mb\n"
            "Miền Nam: hcm, dongnai, cantho, soctrang,\n"
            "          bentre, vungtau, dongthap, tiengiang,\n"
            "          angiang, kiengiang, longan, tayninh,\n"
            "          vinhlong, travinh, baclieu, mn\n"
            "Miền Trung: danang, khanhhoa (nhatrang),\n"
            "          quangnam, daklak, hue, quangngai,\n"
            "          binhdinh, phuyen, quangbinh, quangtri,\n"
            "          ninhthuan, binhthuan, kontum, gialai,\n"
            "          daknong, mt\n\n"
            "📊 Nguồn: xoso.com.vn (FREE)"
        )
        return
    
    args = context.args
    user_input = args[0]
    province = "mb"
    date_str = None
    
    # Parse: 2nd arg can be province OR date
    if len(args) >= 2:
        date_match = re.match(r'(\d{1,2})-(\d{1,2})-(\d{4})$', args[1])
        if date_match:
            date_str = args[1]
        else:
            # Treat as province (may contain spaces — join remaining args)
            province = " ".join(args[1:])
            if len(args) >= 3:
                date_match = re.match(r'(\d{1,2})-(\d{1,2})-(\d{4})$', args[2])
                if date_match:
                    date_str = args[2]
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/xoso: {user_input} province={province} date={date_str}")
    
    result_msg = check_lottery_ticket(user_input, province_input=province, date_str=date_str)
    stats["xoso_count"] += 1
    
    # Split long messages
    if len(result_msg) > 1900:
        for i in range(0, len(result_msg), 1900):
            await update.message.reply_text(result_msg[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(result_msg)
    
    stats["messages_sent"] += 1
    log(f"🤖 Xoso reply sent ({len(result_msg)} chars)")


# ========== NEW UTILITY COMMANDS ==========

async def cmd_weather(update: Update, context):
    """Weather — /weather <location> [days]"""
    if not context.args:
        await update.message.reply_text(
            "🌤️ DỰ BÁO THỜI TIẾT\n\n"
            "Cách dùng:\n"
            "• /weather <địa điểm> → Hiện tại + 7 ngày\n"
            "• /weather <địa điểm> 3 → Số ngày tùy chọn (1-16)\n\n"
            "VD:\n"
            "  /weather Hà Nội\n"
            "  /weather Hồ Chí Minh\n"
            "  /weather Đà Nẵng 3\n"
            "  /weather Tokyo\n"
            "  /weather London\n\n"
            "📡 Nguồn: Open-Meteo (FREE, không cần API key)"
        )
        return
    
    args = context.args
    # Last arg may be number of days
    days = 7
    if len(args) >= 2 and args[-1].isdigit():
        days_req = int(args[-1])
        if 1 <= days_req <= 16:
            days = days_req
            args = args[:-1]
    
    location = " ".join(args)
    if not location:
        await update.message.reply_text("❌ Vui lòng nhập tên địa điểm.")
        return
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/weather: {location} ({days} days)")
    
    report = get_weather_report(location, days=days)
    
    # Add weather count to stats
    if "weather_count" not in stats:
        stats["weather_count"] = 0
    stats["weather_count"] += 1
    
    # Split long messages
    if len(report) > 1900:
        for i in range(0, len(report), 1900):
            await update.message.reply_text(report[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(report)
    
    stats["messages_sent"] += 1
    log(f"🤖 Weather reply sent ({len(report)} chars)")


async def cmd_qr(update: Update, context):
    """Generate QR code — /qr <text>"""
    if not context.args:
        await update.message.reply_text("📱 Gõ: /qr <nội dung>\nVD: /qr https://google.com\nVD: /qr 0901234567")
        return
    text = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/qr: {text[:50]}")
    
    # Use Google Chart API (free, no API key) or quickchart.io
    qr_url = f"https://quickchart.io/qr?text={urllib.parse.quote(text)}&size=300"
    
    try:
        await update.message.reply_photo(
            photo=qr_url,
            caption=f"📱 QR Code cho: {text[:100]}\n\nPowered by quickchart.io"
        )
        stats["images_generated"] += 1
    except Exception as e:
        # Fallback to text URL
        await update.message.reply_text(f"📱 QR Code URL:\n{qr_url}\n\n❌ Lỗi: {e}")
        stats["errors"] += 1
    stats["messages_sent"] += 1


async def cmd_translate(update: Update, context):
    """Translate text — /translate <text> (auto-detect → Vietnamese)"""
    if not context.args:
        await update.message.reply_text(
            "🌐 Dịch văn bản\n\n"
            "Cách dùng:\n"
            "• /translate <text> → Tự động dịch sang tiếng Việt\n"
            "• /translate en <text> → Dịch sang tiếng Anh\n\n"
            "VD:\n"
            "  /translate hello world\n"
            "  /translate en Xin chào"
        )
        return
    
    args = context.args
    target_lang = "vi"
    text_to_translate = " ".join(args)
    
    # Check if first arg is a language code
    lang_codes = {"vi", "en", "zh", "ja", "ko", "fr", "de", "es", "ru", "th", "it", "pt"}
    if args[0].lower() in lang_codes:
        target_lang = args[0].lower()
        text_to_translate = " ".join(args[1:])
    
    if not text_to_translate:
        await update.message.reply_text("❌ Vui lòng nhập nội dung cần dịch.")
        return
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/translate -> {target_lang}: {text_to_translate[:60]}")
    
    lang_names = {
        "vi": "tiếng Việt", "en": "English", "zh": "Chinese (Simplified)",
        "ja": "Japanese", "ko": "Korean", "fr": "French", "de": "German",
        "es": "Spanish", "ru": "Russian", "th": "Thai", "it": "Italian", "pt": "Portuguese",
    }
    target_name = lang_names.get(target_lang, target_lang)
    
    prompt = (
        f"You are a professional translator. Translate the following text into {target_name}. "
        f"Only output the translation, no explanation.\n\nText: {text_to_translate}\n\nTranslation:"
    )
    
    # Use the chat's selected provider+model
    result = ai_reply(prompt, chat_id=update.message.chat.id)
    
    if result and not result.startswith("❌"):
        translated = result.strip()
        result_text = (
            f"🌐 DỊCH → {target_name}\n"
            f"{'─' * 30}\n"
            f"📝 Gốc: {text_to_translate[:500]}\n"
            f"✅ Dịch: {translated[:1000]}"
        )
        await update.message.reply_text(result_text)
    else:
        await update.message.reply_text(f"❌ Lỗi dịch: {result}")
        stats["errors"] += 1
    
    stats["messages_sent"] += 1


async def cmd_calc(update: Update, context):
    """Calculator — /calc <expression>"""
    if not context.args:
        await update.message.reply_text(
            "🧮 Máy tính\n\n"
            "Cách dùng: /calc <biểu thức>\n\n"
            "Hỗ trợ: + - * / ^ % ( ) sqrt() sin() cos() tan() log() pi e\n\n"
            "VD:\n"
            "  /calc 2+3*4\n"
            "  /calc sqrt(144)\n"
            "  /calc 10^2\n"
            "  /calc sin(pi/2)"
        )
        return
    
    expr = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/calc: {expr[:80]}")
    
    # Safe eval with math functions
    try:
        import math
        allowed_names = {
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "log": math.log, "log10": math.log10, "exp": math.exp,
            "pi": math.pi, "e": math.e, "abs": abs, "round": round,
            "floor": math.floor, "ceil": math.ceil, "pow": pow,
        }
        # Replace ^ with **
        safe_expr = expr.replace("^", "**")
        # Compile and evaluate in restricted namespace
        code = compile(safe_expr, "<string>", "eval")
        for name in code.co_names:
            if name not in allowed_names:
                raise NameError(f"Function '{name}' not allowed")
        result = eval(code, {"__builtins__": {}}, allowed_names)
        
        if isinstance(result, float):
            if result.is_integer():
                result_str = str(int(result))
            else:
                result_str = f"{result:.6g}"
        else:
            result_str = str(result)
        
        await update.message.reply_text(
            f"🧮 KẾT QUẢ\n"
            f"{'─' * 30}\n"
            f"📝 {expr}\n"
            f"{'─' * 30}\n"
            f"✅ = {result_str}"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Lỗi tính toán: {e}\n\n"
            f"📝 Biểu thức: {expr}\n"
            f"Hỗ trợ: + - * / ^ % sqrt sin cos tan log pi e"
        )
        stats["errors"] += 1
    
    stats["messages_sent"] += 1


async def cmd_time(update: Update, context):
    """Show current time — /time [timezone]"""
    from datetime import timezone as tz_module
    import zoneinfo
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        ZoneInfo = None
    
    # Default timezone from user input or Vietnam
    tz_input = " ".join(context.args) if context.args else "Asia/Ho_Chi_Minh"
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/time: {tz_input}")
    
    # Mapping common short codes to IANA
    TZ_MAP = {
        "vn": "Asia/Ho_Chi_Minh",
        "vietnam": "Asia/Ho_Chi_Minh",
        "us": "America/New_York",
        "usa": "America/New_York",
        "uk": "Europe/London",
        "london": "Europe/London",
        "tokyo": "Asia/Tokyo",
        "japan": "Asia/Tokyo",
        "korea": "Asia/Seoul",
        "sydney": "Australia/Sydney",
        "paris": "Europe/Paris",
        "dubai": "Asia/Dubai",
        "singapore": "Asia/Singapore",
    }
    tz_input_lower = tz_input.lower()
    if tz_input_lower in TZ_MAP:
        tz_name = TZ_MAP[tz_input_lower]
    else:
        tz_name = tz_input
    
    try:
        if ZoneInfo:
            tz = ZoneInfo(tz_name)
        else:
            tz = tz_module.utc
        now = datetime.datetime.now(tz)
        date_str = now.strftime("%A, %d/%m/%Y")
        time_str = now.strftime("%H:%M:%S")
        tz_short = now.strftime("%Z")
        
        await update.message.reply_text(
            f"🕐 GIỜ HIỆN TẠI\n"
            f"{'─' * 30}\n"
            f"🌍 Múi giờ: {tz_name} ({tz_short})\n"
            f"📅 Ngày: {date_str}\n"
            f"⏰ Giờ: {time_str}\n"
            f"{'─' * 30}\n"
            f"VD các múi giờ khác: vn, us, uk, japan, korea, sydney, dubai, paris, singapore"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Không tìm thấy múi giờ '{tz_name}'\n"
            f"Lỗi: {e}\n\n"
            f"VD: /time vn, /time us, /time Asia/Tokyo"
        )
        stats["errors"] += 1
    
    stats["messages_sent"] += 1


# ========== 10 NEW UTILITY COMMANDS ==========

async def cmd_wiki(update: Update, context):
    """Wikipedia summary — /wiki <query> [lang]"""
    if not context.args:
        await update.message.reply_text(
            "📚 Tìm Wikipedia\n\n"
            "Cách dùng:\n"
            "• /wiki <từ khóa> → Wikipedia tiếng Việt\n"
            "• /wiki en <từ khóa> → Wikipedia tiếng Anh\n\n"
            "VD: /wiki Hà Nội, /wiki en Vietnam\n"
            "📡 Nguồn: Wikipedia REST API (FREE)"
        )
        return
    
    args = context.args
    lang = "vi"
    query_args = args
    if args[0].lower() in ("vi", "en", "fr", "ja", "zh", "ko", "es", "de", "ru"):
        lang = args[0].lower()
        query_args = args[1:]
    
    query = " ".join(query_args)
    if not query:
        await update.message.reply_text("❌ Vui lòng nhập từ khóa.")
        return
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/wiki ({lang}): {query}")
    
    # Cache for 1 hour (Wikipedia content rarely changes)
    cache_key = f"wiki:{lang}:{query.lower()}"
    cached = cache_get(cache_key, ttl_seconds=3600)
    if cached:
        await update.message.reply_text(cached)
        stats["messages_sent"] += 1
        stats["wiki_count"] += 1
        return
    
    try:
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query)}"
        # Wikimedia requires a descriptive User-Agent with contact info, otherwise returns 403
        r = requests.get(url, headers={
            "User-Agent": "NhutBot/1.0 (https://zalo-bot-three.vercel.app; contact@nhutbot.com)",
            "Accept": "application/json",
        }, timeout=15)
        if r.status_code == 404:
            await update.message.reply_text(f"❌ Không tìm thấy '{query}' trên Wikipedia {lang}.")
            stats["errors"] += 1
            return
        r.raise_for_status()
        data = r.json()
        
        title = data.get("title", query)
        extract = data.get("extract", "")
        if not extract:
            await update.message.reply_text(f"❌ Bài viết '{title}' không có tóm tắt.")
            stats["errors"] += 1
            return
        
        thumb = data.get("thumbnail", {}).get("source", "")
        url_page = (data.get("content_urls", {}).get("desktop", {}) or {}).get("page", "")
        
        msg = f"📚 WIKIPEDIA ({lang.upper()})\n{'─' * 30}\n📌 {title}\n\n{extract[:1500]}\n"
        if url_page:
            msg += f"\n🔗 {url_page}"
        msg += "\n\n📡 Nguồn: Wikipedia REST API"
        
        cache_set(cache_key, msg)
        await update.message.reply_text(msg)
        stats["wiki_count"] += 1
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")
        stats["errors"] += 1
    
    stats["messages_sent"] += 1


async def cmd_currency(update: Update, context):
    """Currency exchange — /currency <amount> <from> <to>"""
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "💸 QUI ĐỔI TIỀN TỆ\n\n"
            "Cách dùng: /currency <số tiền> <từ> <đến>\n\n"
            "VD:\n"
            "  /currency 100 USD VND\n"
            "  /currency 1000000 VND USD\n"
            "  /currency 50 EUR USD\n\n"
            "📡 Nguồn: open.er-api.com (FREE, no key)"
        )
        return
    
    try:
        amount = float(context.args[0])
        from_curr = context.args[1].upper()
        to_curr = context.args[2].upper()
    except ValueError:
        await update.message.reply_text("❌ Số tiền không hợp lệ.")
        stats["errors"] += 1
        return
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/currency: {amount} {from_curr} → {to_curr}")
    
    # Cache rates 30 min (currency doesn't change fast)
    cache_key = f"rates:{from_curr}"
    rates_data = cache_get(cache_key, ttl_seconds=1800)
    if not rates_data:
        try:
            r = requests.get(f"https://open.er-api.com/v6/latest/{from_curr}", timeout=10)
            r.raise_for_status()
            rates_data = r.json()
            cache_set(cache_key, rates_data)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi tải tỷ giá: {e}")
            stats["errors"] += 1
            return
    
    rates = rates_data.get("rates", {})
    rate = rates.get(to_curr)
    if not rate:
        await update.message.reply_text(f"❌ Không tìm thấy tỷ giá {from_curr} → {to_curr}")
        stats["errors"] += 1
        return
    
    converted = amount * rate
    updated = rates_data.get("time_last_update_utc", "N/A")
    
    msg = (
        f"💸 QUI ĐỔI TIỀN TỆ\n"
        f"{'─' * 30}\n"
        f"💵 {amount:,.2f} {from_curr}\n"
        f"⬇️\n"
        f"💵 {converted:,.2f} {to_curr}\n"
        f"{'─' * 30}\n"
        f"📊 Tỷ giá: 1 {from_curr} = {rate:,.4f} {to_curr}\n"
        f"🕐 Cập nhật: {updated}\n"
        f"📡 Nguồn: open.er-api.com"
    )
    await update.message.reply_text(msg)
    stats["currency_count"] += 1
    stats["messages_sent"] += 1


async def cmd_crypto(update: Update, context):
    """Crypto price — /crypto <symbol>"""
    if not context.args:
        await update.message.reply_text(
            "💰 GIÁ CRYPTO\n\n"
            "Cách dùng: /crypto <symbol>\n\n"
            "VD:\n"
            "  /crypto bitcoin\n"
            "  /crypto ethereum\n"
            "  /crypto solana\n"
            "  /crypto bitcoin ethereum (nhiều)\n\n"
            "📡 Nguồn: CoinGecko (FREE, no key)"
        )
        return
    
    # CoinGecko IDs vs symbols map (common ones)
    COIN_MAP = {
        "btc": "bitcoin", "bitcoin": "bitcoin",
        "eth": "ethereum", "ethereum": "ethereum",
        "sol": "solana", "solana": "solana",
        "bnb": "binancecoin", "binance": "binancecoin",
        "xrp": "ripple", "ripple": "ripple",
        "ada": "cardano", "cardano": "cardano",
        "doge": "dogecoin", "dogecoin": "dogecoin",
        "dot": "polkadot", "polkadot": "polkadot",
        "matic": "matic-network", "polygon": "matic-network",
        "avax": "avalanche-2", "avalanche": "avalanche-2",
        "ltc": "litecoin", "litecoin": "litecoin",
        "usdt": "tether", "tether": "tether",
        "usdc": "usd-coin", "usd-coin": "usd-coin",
        "shib": "shiba-inu", "shiba": "shiba-inu",
        "tron": "tron", "trx": "tron",
    }
    
    coins = []
    for arg in context.args:
        coin = COIN_MAP.get(arg.lower(), arg.lower())
        coins.append(coin)
    
    coins_str = ",".join(coins[:10])  # max 10
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/crypto: {coins_str}")
    
    # Cache 2 min (crypto moves fast)
    cache_key = f"crypto:{coins_str}"
    cached = cache_get(cache_key, ttl_seconds=120)
    if not cached:
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": coins_str, "vs_currencies": "usd,/vnd", "include_24hr_change": "true", "include_market_cap": "true"},
                timeout=10,
            )
            r.raise_for_status()
            cached = r.json()
            cache_set(cache_key, cached)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi tải giá crypto: {e}")
            stats["errors"] += 1
            return
    
    parts = ["💰 GIÁ CRYPTO", "─" * 30]
    for coin in coins:
        info = cached.get(coin)
        if not info:
            parts.append(f"❌ {coin}: không tìm thấy")
            continue
        usd = info.get("usd", 0)
        vnd = info.get("vnd", 0)
        change = info.get("usd_24h_change", 0)
        mcap = info.get("usd_market_cap", 0)
        emoji = "📈" if change >= 0 else "📉"
        parts.append(f"🔹 {coin.upper()}")
        parts.append(f"   💵 ${usd:,.2f} ({vnd:,.0f} VND)")
        parts.append(f"   {emoji} 24h: {change:+.2f}%")
        if mcap:
            parts.append(f"   🏦 Market cap: ${mcap:,.0f}")
        parts.append("")
    
    parts.append("📡 Nguồn: CoinGecko (FREE)")
    await update.message.reply_text("\n".join(parts))
    stats["crypto_count"] += 1
    stats["messages_sent"] += 1


async def cmd_shorten(update: Update, context):
    """URL shortener — /shorten <url>"""
    if not context.args:
        await update.message.reply_text(
            "🔗 RÚT GỌN URL\n\n"
            "Cách dùng: /shorten <url>\n\n"
            "VD: /shorten https://google.com\n\n"
            "📡 Nguồn: is.gd (FREE, no key)"
        )
        return
    
    url = context.args[0]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/shorten: {url}")
    
    try:
        r = requests.get("https://is.gd/create.php", params={
            "format": "json",
            "url": url,
        }, timeout=10)
        data = r.json()
        if "shorturl" in data:
            await update.message.reply_text(
                f"🔗 URL RÚT GỌN\n{'─' * 30}\n"
                f"📝 Gốc: {url}\n"
                f"✅ Ngắn: {data['shorturl']}\n\n"
                f"📡 Nguồn: is.gd"
            )
            stats["url_count"] += 1
        else:
            await update.message.reply_text(f"❌ Lỗi: {data.get('errormessage', 'unknown')}")
            stats["errors"] += 1
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")
        stats["errors"] += 1
    
    stats["messages_sent"] += 1


async def cmd_ip(update: Update, context):
    """IP info — /ip [ip]"""
    if context.args:
        ip = context.args[0]
    else:
        ip = ""  # empty = show server IP for demo
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/ip: {ip or '(own)'}")
    
    # Cache IP lookups for 1h
    cache_key = f"ip:{ip}"
    cached = cache_get(cache_key, ttl_seconds=3600)
    if not cached:
        try:
            url = f"http://ip-api.com/json/{ip}?fields=query,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,as,reverse,mobile,proxy,hosting"
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            cached = r.json()
            cache_set(cache_key, cached)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {e}")
            stats["errors"] += 1
            return
    
    if cached.get("status") == "fail":
        await update.message.reply_text(f"❌ Lỗi: {cached.get('message', 'unknown')}")
        stats["errors"] += 1
        return
    
    parts = [
        f"🌐 THÔNG TIN IP",
        f"{'─' * 30}",
        f"🔢 IP: {cached.get('query', 'N/A')}",
        f"🌍 Quốc gia: {cached.get('country', 'N/A')} ({cached.get('countryCode', '')})",
        f"🏙️ Thành phố: {cached.get('city', 'N/A')}, {cached.get('regionName', 'N/A')}",
    ]
    if cached.get("zip"):
        parts.append(f"📮 ZIP: {cached.get('zip')}")
    if cached.get("lat") and cached.get("lon"):
        parts.append(f"📍 Tọa độ: {cached.get('lat')}, {cached.get('lon')}")
    if cached.get("timezone"):
        parts.append(f"🕐 Múi giờ: {cached.get('timezone')}")
    if cached.get("isp"):
        parts.append(f"📡 ISP: {cached.get('isp')}")
    if cached.get("org"):
        parts.append(f"🏢 Tổ chức: {cached.get('org')}")
    if cached.get("as"):
        parts.append(f"🏷️ AS: {cached.get('as')}")
    if cached.get("proxy"):
        parts.append("🚨 VPN/Proxy: CÓ")
    if cached.get("hosting"):
        parts.append("☁️ Datacenter: CÓ")
    
    parts.append("")
    parts.append("📡 Nguồn: ip-api.com (FREE)")
    
    await update.message.reply_text("\n".join(parts))
    stats["ip_count"] += 1
    stats["messages_sent"] += 1


async def cmd_password(update: Update, context):
    """Generate password — /password [length] [count]"""
    import secrets
    import string
    
    length = 16
    count = 1
    if context.args:
        try:
            length = int(context.args[0])
            if length < 4: length = 4
            if length > 128: length = 128
            if len(context.args) >= 2:
                count = int(context.args[1])
                if count < 1: count = 1
                if count > 10: count = 10
        except ValueError:
            pass
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/password: length={length} count={count}")
    
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}<>?"
    parts = [
        f"🔐 MẬT KHẨU NGẪU NHIÊN",
        f"{'─' * 30}",
        f"📏 Độ dài: {length} ký tự",
        f"🔢 Số lượng: {count}",
        f"{'─' * 30}",
        "",
    ]
    for i in range(count):
        pw = ''.join(secrets.choice(alphabet) for _ in range(length))
        parts.append(f"{i+1}. `{pw}`")
    
    parts.append("")
    parts.append("✨ Sinh bằng secrets module (cryptographically secure)")
    
    await update.message.reply_text("\n".join(parts))
    stats["messages_sent"] += 1


async def cmd_define(update: Update, context):
    """English dictionary — /define <word>"""
    if not context.args:
        await update.message.reply_text(
            "📖 TỪ ĐIỂN TIẾNG ANH\n\n"
            "Cách dùng: /define <word>\n\n"
            "VD: /define hello, /define serendipity\n\n"
            "📡 Nguồn: dictionaryapi.dev (FREE, no key)"
        )
        return
    
    word = " ".join(context.args).lower().strip()
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/define: {word}")
    
    # Cache 1 day (definitions don't change)
    cache_key = f"define:{word}"
    cached = cache_get(cache_key, ttl_seconds=86400)
    if not cached:
        try:
            r = requests.get(
                f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word)}",
                timeout=10,
            )
            if r.status_code == 404:
                await update.message.reply_text(f"❌ Không tìm thấy từ '{word}' trong từ điển.")
                stats["errors"] += 1
                return
            r.raise_for_status()
            cached = r.json()
            cache_set(cache_key, cached)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {e}")
            stats["errors"] += 1
            return
    
    if not cached or not isinstance(cached, list):
        await update.message.reply_text(f"❌ Không tìm thấy từ '{word}'.")
        stats["errors"] += 1
        return
    
    entry = cached[0]
    word_title = entry.get("word", word)
    phonetic = entry.get("phonetic", "")
    
    parts = [f"📖 TỪ ĐIỂN: {word_title}", f"{'─' * 30}"]
    if phonetic:
        parts.append(f"🔤 Phiên âm: {phonetic}")
    parts.append("")
    
    meanings = entry.get("meanings", [])[:3]  # max 3 meanings
    for m in meanings:
        part_of_speech = m.get("partOfSpeech", "")
        parts.append(f"📝 ({part_of_speech})")
        definitions = m.get("definitions", [])[:3]  # max 3 per POS
        for i, d in enumerate(definitions, 1):
            definition = d.get("definition", "")
            example = d.get("example", "")
            parts.append(f"  {i}. {definition[:200]}")
            if example:
                parts.append(f"     VD: \"{example[:150]}\"")
        parts.append("")
    
    parts.append("📡 Nguồn: dictionaryapi.dev")
    
    msg = "\n".join(parts)
    if len(msg) > 1900:
        for i in range(0, len(msg), 1900):
            await update.message.reply_text(msg[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(msg)
    
    stats["dict_count"] += 1
    stats["messages_sent"] += 1


async def cmd_base64(update: Update, context):
    """Base64 encode/decode — /base64 <enc|dec> <text>"""
    import base64
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "🔧 BASE64\n\n"
            "Cách dùng:\n"
            "• /base64 enc <text> → Encode\n"
            "• /base64 dec <text> → Decode\n\n"
            "VD:\n"
            "  /base64 enc Hello World\n"
            "  /base64 dec SGVsbG8gV29ybGQ="
        )
        return
    
    mode = context.args[0].lower()
    text = " ".join(context.args[1:])
    
    if mode in ("enc", "encode"):
        try:
            encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
            await update.message.reply_text(
                f"🔧 BASE64 ENCODE\n{'─' * 30}\n"
                f"📝 Input: {text[:500]}\n"
                f"✅ Output: `{encoded[:1500]}`"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi encode: {e}")
            stats["errors"] += 1
    elif mode in ("dec", "decode"):
        try:
            decoded = base64.b64decode(text).decode("utf-8", errors="replace")
            await update.message.reply_text(
                f"🔧 BASE64 DECODE\n{'─' * 30}\n"
                f"📝 Input: {text[:500]}\n"
                f"✅ Output: {decoded[:1500]}"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi decode: {e}")
            stats["errors"] += 1
    else:
        await update.message.reply_text("❌ Mode phải là `enc` hoặc `dec`.")
        stats["errors"] += 1
    
    stats["messages_sent"] += 1


async def cmd_joke(update: Update, context):
    """Random joke — /joke [category]"""
    if context.args:
        category = context.args[0].lower()
        if category not in ("programming", "misc", "dark", "pun", "spooky", "christmas"):
            await update.message.reply_text(
                "😂 Category: programming, misc, dark, pun, spooky, christmas"
            )
            return
    else:
        category = "Any"
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/joke: {category}")
    
    try:
        r = requests.get(
            "https://v2.jokeapi.dev/joke/" + category,
            params={"format": "json", "type": "single", "lang": "en", "safe-mode": "true"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        
        if data.get("error"):
            await update.message.reply_text(f"❌ Lỗi: {data.get('message')}")
            stats["errors"] += 1
            return
        
        joke = data.get("joke", "Không có joke :(")
        cat = data.get("category", "Any")
        
        await update.message.reply_text(
            f"😂 JOKE ({cat})\n{'─' * 30}\n\n{joke}\n\n📡 Nguồn: JokeAPI"
        )
        stats["joke_count"] += 1
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")
        stats["errors"] += 1
    
    stats["messages_sent"] += 1


async def cmd_youtube(update: Update, context):
    """YouTube search — /youtube <query>"""
    if not context.args:
        await update.message.reply_text(
            "🎬 TÌM VIDEO YOUTUBE\n\n"
            "Cách dùng: /youtube <từ khóa>\n\n"
            "VD:\n"
            "  /youtube nhạc Việt Nam\n"
            "  /youtube python tutorial\n\n"
            "📡 Nguồn: Tavily search (filtered for youtube.com)"
        )
        return
    
    query = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/youtube: {query}")
    
    # Use Tavily with site filter for youtube.com
    try:
        from tavily import TavilyClient
        client = TavilyClient(TAVILY_API_KEY)
        resp = client.search(
            query=f"site:youtube.com {query}",
            search_depth="basic",
            max_results=5,
            include_answer=False,
        )
        results = resp.get("results", [])
        
        if not results:
            await update.message.reply_text(f"❌ Không tìm thấy video cho '{query}'")
            stats["errors"] += 1
            return
        
        parts = [f"🎬 YOUTUBE: \"{query}\"", "─" * 30, ""]
        for i, item in enumerate(results[:5], 1):
            title = item.get("title", "N/A")[:80]
            url = item.get("url", "")
            # Extract video ID for thumbnail
            video_id = ""
            if "watch?v=" in url:
                video_id = url.split("watch?v=")[1][:11]
            elif "youtu.be/" in url:
                video_id = url.split("youtu.be/")[1][:11]
            parts.append(f"{i}. {title}")
            if url:
                parts.append(f"   🔗 {url}")
            if video_id:
                parts.append(f"   🖼️ https://img.youtube.com/vi/{video_id}/hqdefault.jpg")
            parts.append("")
        
        parts.append("📡 Nguồn: Tavily search")
        
        msg = "\n".join(parts)
        if len(msg) > 1900:
            for i in range(0, len(msg), 1900):
                await update.message.reply_text(msg[i:i+1900])
                await asyncio.sleep(0.3)
        else:
            await update.message.reply_text(msg)
        
        stats["yt_count"] += 1
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")
        stats["errors"] += 1

    stats["messages_sent"] += 1


# ========== TIKTOK & YOUTUBE DOWNLOAD ==========

TIKWM_API = "https://www.tikwm.com/api/"
PIPED_API = "https://api.piped.private.coffee"

def _is_tiktok_url(url: str) -> bool:
    return "tiktok.com" in url.lower() or "vm.tiktok.com" in url.lower() or "vt.tiktok.com" in url.lower()

def _is_youtube_url(url: str) -> bool:
    return any(x in url.lower() for x in ("youtube.com", "youtu.be", "youtube-nocookie.com"))

def _extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    import re
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/|youtube-nocookie\.com/embed/)([A-Za-z0-9_-]{11})',
        r'youtube\.com/v/([A-Za-z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return ""


def fetch_tiktok(url: str) -> dict:
    """Fetch TikTok video/photo data via tikwm.com (FREE, no API key)."""
    cache_key = f"tiktok:{url}"
    cached = cache_get(cache_key, ttl_seconds=600)  # 10 min
    if cached:
        return cached
    
    try:
        r = requests.post(
            TIKWM_API,
            data={"url": url, "hd": "1"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            return {"error": f"tikwm: {data.get('msg', 'unknown error')}"}
        result = data.get("data", {})
        cache_set(cache_key, result)
        return result
    except Exception as e:
        return {"error": f"Lỗi tải TikTok: {e}"}


def fetch_youtube_streams(video_id: str) -> dict:
    """Fetch YouTube stream URLs via Piped API (FREE, no API key)."""
    cache_key = f"yt:{video_id}"
    cached = cache_get(cache_key, ttl_seconds=1800)  # 30 min
    if cached:
        return cached
    
    try:
        r = requests.get(
            f"{PIPED_API}/streams/{video_id}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if r.status_code != 200:
            return {"error": f"Piped HTTP {r.status_code}"}
        data = r.json()
        cache_set(cache_key, data)
        return data
    except Exception as e:
        return {"error": f"Lỗi tải YouTube: {e}"}


async def cmd_tiktok(update: Update, context):
    """Download TikTok video/photo/music without watermark — /tiktok <url> [music]"""
    if not context.args:
        await update.message.reply_text(
            "🎬 TẢI TIKTOK KHÔNG LOGO\n\n"
            "Cách dùng:\n"
            "• /tiktok <url> → Tải video không logo\n"
            "• /tiktok <url> music → Tải nhạc\n\n"
            "Hỗ trợ:\n"
            "✅ Video TikTok (gửi ảnh bìa + link tải)\n"
            "✅ Ảnh slide (gửi từng ảnh trực tiếp)\n"
            "✅ Âm thanh (MP3) (gửi ảnh + link nhạc)\n\n"
            "VD:\n"
            "  /tiktok https://www.tiktok.com/@user/video/1234567890\n"
            "  /tiktok https://vm.tiktok.com/ABCDEF/ music\n\n"
            "📡 Nguồn: tikwm.com (FREE)"
        )
        return
    
    url = context.args[0]
    mode = context.args[1].lower() if len(context.args) >= 2 else "video"
    
    if not _is_tiktok_url(url):
        await update.message.reply_text("❌ URL không hợp lệ. Phải là link TikTok (tiktok.com hoặc vm.tiktok.com).")
        stats["errors"] += 1
        return
    
    await context.bot.send_chat_action(
        chat_id=update.message.chat.id,
        action=ChatAction.TYPING,
    )
    log(f"/tiktok: {url[:80]} (mode={mode})")
    
    data = fetch_tiktok(url)
    if "error" in data:
        await update.message.reply_text(f"❌ {data['error']}")
        stats["errors"] += 1
        return
    
    title = data.get("title", "Không có tiêu đề")[:200]
    author = data.get("author", {}).get("nickname", "?")
    cover = data.get("cover", "")
    play_url = data.get("play", "")  # No watermark video
    wm_url = data.get("wmplay", "")  # With watermark
    music_url = data.get("music", "")
    duration = data.get("duration", 0)
    images = data.get("images", []) or []  # Photo slides
    play_count = data.get("play_count", 0)
    digg_count = data.get("digg_count", 0)
    
    # Send cover/thumbnail as photo first (if no photo slides)
    if not images and cover:
        try:
            caption_parts = [
                f"🎬 {title[:100]}",
                f"👤 {author} | ⏱️ {duration}s | 👁️ {play_count:,} | ❤️ {digg_count:,}",
            ]
            await update.message.reply_photo(
                photo=cover,
                caption="\n".join(caption_parts)
            )
            stats["messages_sent"] += 1
            log(f"✅ Cover photo sent")
        except Exception as e:
            log(f"❌ Cover send failed: {e}")
            import traceback
            log(f"❌ Traceback: {traceback.format_exc()[:300]}")
    
    # Photo slides — send each image directly (this is what user wants!)
    if images:
        # Send each image as photo (max 10 to avoid spam)
        sent_count = 0
        for img_url in images[:10]:
            try:
                await update.message.reply_photo(
                    photo=img_url,
                    caption=f"🖼️ Ảnh {sent_count + 1}/{len(images)}" if sent_count == 0 else None
                )
                sent_count += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                log(f"Image send failed {sent_count}: {e}")
                # Fallback to text URL
                await update.message.reply_text(f"🖼️ Ảnh {sent_count + 1}: {img_url}")
                sent_count += 1
        
        # Summary
        summary = f"✅ Đã gửi {sent_count}/{len(images)} ảnh"
        if len(images) > 10:
            summary += f"\n📝 Còn {len(images) - 10} ảnh nữa — dùng /tiktok <url> info để xem tất cả"
        await update.message.reply_text(summary)
    else:
        # Video — Zalo doesn't support sendVideo, so send cover + URL as text
        info_parts = [
            f"🎬 TIKTOK VIDEO (KHÔNG LOGO)",
            f"{'─' * 30}",
            f"👤 Tác giả: {author}",
            f"📝 Tiêu đề: {title[:200]}",
        ]
        if duration > 0:
            info_parts.append(f"⏱️ Thời lượng: {duration}s")
        info_parts.append(f"👁️ Lượt xem: {play_count:,} | ❤️ {digg_count:,}")
        info_parts.append("")
        
        if mode == "music" and music_url:
            info_parts.append("🎵 LINK TẢI NHẠC (MP3):")
            info_parts.append(music_url)
        else:
            info_parts.append("📥 LINK TẢI VIDEO KHÔNG LOGO:")
            info_parts.append(play_url)
            if music_url:
                info_parts.append("")
                info_parts.append(f"🎵 Nhạc MP3: {music_url}")
        
        info_parts.append("")
        info_parts.append("💡 Mở link trên trình duyệt để tải về (chỉnh header Referer nếu lỗi 503)")
        info_parts.append("📡 Nguồn: tikwm.com")
        
        msg = "\n".join(info_parts)
        if len(msg) > 1900:
            for i in range(0, len(msg), 1900):
                await update.message.reply_text(msg[i:i+1900])
                await asyncio.sleep(0.3)
        else:
            await update.message.reply_text(msg)
    
    if "tiktok_count" not in stats:
        stats["tiktok_count"] = 0
    stats["tiktok_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 TikTok reply sent")


async def cmd_ytdl(update: Update, context):
    """Download YouTube video — /ytdl <url>"""
    if not context.args:
        await update.message.reply_text(
            "🎬 TẢI VIDEO YOUTUBE\n\n"
            "Cách dùng: /ytdl <url>\n\n"
            "VD:\n"
            "  /ytdl https://www.youtube.com/watch?v=dQw4w9WgXcQ\n"
            "  /ytdl https://youtu.be/dQw4w9WgXcQ\n"
            "  /ytdl https://www.youtube.com/shorts/VIDEO_ID\n\n"
            "✅ Trả về: ảnh thumbnail + link tải\n"
            "📡 Nguồn: Piped API + YouTube oEmbed"
        )
        return
    
    url = context.args[0]
    video_id = _extract_video_id(url)
    
    if not video_id:
        await update.message.reply_text("❌ URL YouTube không hợp lệ.")
        stats["errors"] += 1
        return
    
    await context.bot.send_chat_action(
        chat_id=update.message.chat.id,
        action=ChatAction.TYPING,
    )
    log(f"/ytdl: {video_id}")
    
    # Get metadata via oEmbed (always works)
    try:
        oembed_resp = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=10,
        )
        oembed = oembed_resp.json() if oembed_resp.status_code == 200 else {}
    except Exception:
        oembed = {}
    
    title = oembed.get("title", video_id)
    author = oembed.get("author_name", "Unknown")
    thumbnail = oembed.get("thumbnail_url", f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg")
    
    # Try Piped first
    streams = fetch_youtube_streams(video_id)
    
    # Get duration & views from Piped
    duration = 0
    views = 0
    if "error" not in streams:
        piped_title = streams.get("title", "")
        if piped_title:
            title = piped_title[:200]
        duration = streams.get("duration", 0)
        views = streams.get("views", 0)
    
    # Send YouTube thumbnail as photo first
    try:
        caption = f"🎬 {title[:100]}\n👤 {author}"
        if duration:
            caption += f" | ⏱️ {duration}s"
        if views:
            caption += f" | 👁️ {views:,}"
        await update.message.reply_photo(photo=thumbnail, caption=caption)
        stats["messages_sent"] += 1
        log(f"✅ YT thumbnail sent")
    except Exception as e:
        log(f"❌ YT thumbnail send failed: {e}")
        import traceback
        log(f"❌ Traceback: {traceback.format_exc()[:300]}")
    
    # Build text message with download links
    parts = [
        f"🎬 LINK TẢI VIDEO YOUTUBE",
        f"{'─' * 30}",
        f"📝 {title[:200]}",
        f"👤 Kênh: {author}",
        f"🔗 https://www.youtube.com/watch?v={video_id}",
        "",
    ]
    
    if "error" not in streams:
        # List available video streams (max 3 to keep message short)
        video_streams = streams.get("videoStreams") or []
        audio_streams = streams.get("audioStreams") or []
        
        if video_streams:
            parts.append("📥 LINK TẢI VIDEO:")
            for vs in video_streams[:3]:
                q = vs.get("quality", "?")
                fmt = vs.get("format", "")
                url_v = vs.get("url", "")
                if url_v:
                    parts.append(f"  • {q} ({fmt}):")
                    parts.append(f"    {url_v}")
            parts.append("")
        
        if audio_streams:
            parts.append("🎵 LINK TẢI AUDIO:")
            audio_streams.sort(key=lambda x: x.get("bitrate", 0), reverse=True)
            for asr in audio_streams[:2]:
                mime = asr.get("mimeType", "")[:30]
                bitrate = asr.get("bitrate", 0) // 1000
                url_a = asr.get("url", "")
                if url_a:
                    parts.append(f"  • {bitrate}kbps ({mime}):")
                    parts.append(f"    {url_a}")
            parts.append("")
        
        if not video_streams and not audio_streams:
            parts.append("⚠️ Piped không trả được stream (YouTube bot detection)")
    else:
        parts.append(f"⚠️ Piped lỗi: {streams['error'][:80]}")
    
    # Fallback: web downloaders
    parts.append("🌐 WEB DOWNLOADERS (backup nếu link trên không được):")
    parts.append(f"  • ssyoutube: https://ssyoutube.com/watch?v={video_id}")
    parts.append(f"  • savefrom: https://en.savefrom.net/#url=https://www.youtube.com/watch?v={video_id}")
    parts.append(f"  • y2mate: https://www.y2mate.com/youtube/{video_id}")
    parts.append("")
    parts.append("📡 Nguồn: Piped + YouTube oEmbed")
    
    msg = "\n".join(parts)
    if len(msg) > 1900:
        for i in range(0, len(msg), 1900):
            await update.message.reply_text(msg[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(msg)
    
    if "ytdl_count" not in stats:
        stats["ytdl_count"] = 0
    stats["ytdl_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Ytdl reply sent")


async def cmd_ytmp3(update: Update, context):
    """YouTube to MP3 (audio only) — /ytmp3 <url>"""
    if not context.args:
        await update.message.reply_text(
            "🎵 YOUTUBE → MP3\n\n"
            "Cách dùng: /ytmp3 <url>\n\n"
            "VD: /ytmp3 https://www.youtube.com/watch?v=dQw4w9WgXcQ\n\n"
            "✅ Lấy link tải audio (MP3/M4A)\n"
            "📡 Nguồn: Piped API"
        )
        return
    
    url = context.args[0]
    video_id = _extract_video_id(url)
    
    if not video_id:
        await update.message.reply_text("❌ URL YouTube không hợp lệ.")
        stats["errors"] += 1
        return
    
    await context.bot.send_chat_action(
        chat_id=update.message.chat.id,
        action=ChatAction.TYPING,
    )
    log(f"/ytmp3: {video_id}")
    
    # Get metadata via oEmbed
    try:
        oembed_resp = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=10,
        )
        oembed = oembed_resp.json() if oembed_resp.status_code == 200 else {}
    except Exception:
        oembed = {}
    
    title = oembed.get("title", video_id)
    author = oembed.get("author_name", "Unknown")
    thumbnail = oembed.get("thumbnail_url", f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg")
    
    # Send YouTube thumbnail as photo first
    try:
        await update.message.reply_photo(
            photo=thumbnail,
            caption=f"🎵 {title[:100]}\n👤 {author}"
        )
        stats["messages_sent"] += 1
        log(f"✅ YT MP3 thumbnail sent")
    except Exception as e:
        log(f"❌ YT MP3 thumbnail send failed: {e}")
        import traceback
        log(f"❌ Traceback: {traceback.format_exc()[:300]}")
    
    parts = [
        f"🎵 YOUTUBE → MP3",
        f"{'─' * 30}",
        f"📝 {title[:200]}",
        f"👤 Kênh: {author}",
        "",
    ]
    
    # Try Piped for audio streams
    streams = fetch_youtube_streams(video_id)
    
    if "error" not in streams:
        audio_streams = streams.get("audioStreams") or []
        if audio_streams:
            # Sort by bitrate (highest first)
            audio_streams.sort(key=lambda x: x.get("bitrate", 0), reverse=True)
            parts.append("📥 LINK TẢI AUDIO:")
            for asr in audio_streams[:3]:
                mime = asr.get("mimeType", "")
                bitrate = asr.get("bitrate", 0) // 1000
                url_a = asr.get("url", "")
                if url_a:
                    parts.append(f"  • {bitrate}kbps | {mime[:40]}")
                    parts.append(f"    {url_a}")
            parts.append("")
            parts.append("💡 Tip: M4A có chất lượng cao hơn MP3.")
        else:
            parts.append("⚠️ Piped không trả được audio streams (YouTube bot detection).")
            parts.append("Dùng link web dưới đây:")
            parts.append(f"  • y2mate: https://www.y2mate.com/youtube/mp3/{video_id}")
            parts.append(f"  • ytmp3: https://ytmp3.cc/youtube-to-mp3/?url=https://www.youtube.com/watch?v={video_id}")
    else:
        parts.append(f"⚠️ Piped: {streams['error']}")
        parts.append("Dùng link web:")
        parts.append(f"  • y2mate: https://www.y2mate.com/youtube/mp3/{video_id}")
    
    parts.append("")
    parts.append("📡 Nguồn: Piped + YouTube oEmbed")
    
    msg = "\n".join(parts)
    if len(msg) > 1900:
        for i in range(0, len(msg), 1900):
            await update.message.reply_text(msg[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(msg)
    
    if "ytmp3_count" not in stats:
        stats["ytmp3_count"] = 0
    stats["ytmp3_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Ytmp3 reply sent")


# ========== 12 NEW UTILITY COMMANDS (v6) ==========

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


async def cmd_news(update: Update, context):
    """Latest news — /news [topic]"""
    if not context.args:
        topic = "Vietnam"
    else:
        topic = " ".join(context.args)
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/news: {topic}")
    
    # Use Tavily with news topic
    result = search_web(f"{topic} latest news today", max_results=5)
    if "news_count" not in stats:
        stats["news_count"] = 0
    stats["news_count"] += 1
    
    parts = [f"📰 TIN TỨC: {topic}", "─" * 30, ""]
    if result.get("answer"):
        parts.append("💡 Tóm tắt:")
        parts.append(result["answer"][:600])
        parts.append("")
    
    if result.get("results"):
        parts.append("📎 Bài viết:")
        for i, item in enumerate(result["results"][:5], 1):
            title = item.get("title", "N/A")[:80]
            url = item.get("url", "")
            snippet = (item.get("content") or "")[:120].replace("\n", " ")
            parts.append(f"\n{i}. {title}")
            if snippet:
                parts.append(f"   {snippet}...")
            if url:
                parts.append(f"   🔗 {url}")
    
    parts.append("")
    parts.append("📡 Nguồn: Tavily search")
    
    msg = "\n".join(parts)
    if len(msg) > 1900:
        for i in range(0, len(msg), 1900):
            await update.message.reply_text(msg[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(msg)
    
    stats["messages_sent"] += 1
    log(f"🤖 News reply sent")


async def cmd_github(update: Update, context):
    """GitHub user info — /github <username>"""
    if not context.args:
        await update.message.reply_text(
            "🐱 GITHUB USER INFO\n\n"
            "Cách dùng: /github <username>\n\n"
            "VD: /github torvalds, /github nhut0902\n"
            "📡 Nguồn: GitHub REST API"
        )
        return
    
    username = context.args[0].strip().lstrip("@")
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/github: {username}")
    
    cache_key = f"github:{username}"
    cached = cache_get(cache_key, ttl_seconds=3600)
    if not cached:
        try:
            r = requests.get(
                f"https://api.github.com/users/{username}",
                headers={
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "Mozilla/5.0",
                },
                timeout=10,
            )
            if r.status_code == 404:
                await update.message.reply_text(f"❌ Không tìm thấy user '{username}' trên GitHub")
                stats["errors"] += 1
                return
            r.raise_for_status()
            cached = r.json()
            cache_set(cache_key, cached)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {e}")
            stats["errors"] += 1
            return
    
    parts = [
        f"🐱 GITHUB USER",
        f"{'─' * 30}",
        f"👤 {cached.get('name') or cached.get('login','?')} (@{cached.get('login','?')})",
    ]
    if cached.get('bio'):
        parts.append(f"📝 Bio: {cached['bio'][:200]}")
    if cached.get('company'):
        parts.append(f"🏢 Company: {cached['company']}")
    if cached.get('location'):
        parts.append(f"📍 Location: {cached['location']}")
    if cached.get('blog'):
        parts.append(f"🔗 Blog: {cached['blog']}")
    parts.append("")
    parts.append(f"📊 Stats:")
    parts.append(f"  • Followers: {cached.get('followers',0):,}")
    parts.append(f"  • Following: {cached.get('following',0):,}")
    parts.append(f"  • Public repos: {cached.get('public_repos',0):,}")
    parts.append(f"  • Public gists: {cached.get('public_gists',0):,}")
    parts.append(f"  • Created: {cached.get('created_at','?')[:10]}")
    parts.append("")
    parts.append(f"🖼️ Avatar: {cached.get('avatar_url','')}")
    parts.append(f"🌐 Profile: https://github.com/{cached.get('login','')}")
    parts.append("")
    parts.append("📡 Nguồn: GitHub REST API")
    
    # Send avatar as photo if available
    avatar = cached.get('avatar_url', '')
    if avatar:
        try:
            await update.message.reply_photo(photo=avatar, caption=f"🖼️ Avatar of @{cached.get('login','?')}")
            stats["messages_sent"] += 1
        except Exception as e:
            log(f"Avatar send failed: {e}")
    
    msg = "\n".join(parts)
    await update.message.reply_text(msg)
    
    if "github_count" not in stats:
        stats["github_count"] = 0
    stats["github_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 GitHub reply sent")


async def cmd_quote(update: Update, context):
    """Random inspirational quote — /quote"""
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/quote")
    
    cache_key = "quote:latest"
    cached = cache_get(cache_key, ttl_seconds=60)  # very short, just to avoid spam
    if not cached:
        try:
            r = requests.get("https://zenquotes.io/api/random", timeout=10)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and data:
                cached = data[0]
                cache_set(cache_key, cached)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {e}")
            stats["errors"] += 1
            return
    
    quote_text = cached.get('q', 'Live and let live.')
    author = cached.get('a', 'Unknown')
    
    msg = (
        f"💬 QUOTE\n"
        f"{'─' * 30}\n\n"
        f"\"{quote_text}\"\n\n"
        f"— {author}\n"
        f"{'─' * 30}\n"
        f"📡 Nguồn: zenquotes.io"
    )
    await update.message.reply_text(msg)
    
    if "quote_count" not in stats:
        stats["quote_count"] = 0
    stats["quote_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Quote reply sent")


async def cmd_fact(update: Update, context):
    """Random useless fact — /fact"""
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/fact")
    
    cache_key = "fact:latest"
    cached = cache_get(cache_key, ttl_seconds=60)
    if not cached:
        try:
            r = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en", timeout=10)
            r.raise_for_status()
            cached = r.json()
            cache_set(cache_key, cached)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {e}")
            stats["errors"] += 1
            return
    
    fact = cached.get('text', 'No fact today.')
    
    msg = (
        f"🧠 RANDOM FACT\n"
        f"{'─' * 30}\n\n"
        f"{fact}\n\n"
        f"📡 Nguồn: uselessfacts.jsph.pl"
    )
    await update.message.reply_text(msg)
    
    if "fact_count" not in stats:
        stats["fact_count"] = 0
    stats["fact_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Fact reply sent")


async def cmd_uuid(update: Update, context):
    """Generate UUID — /uuid [count]"""
    import uuid as uuid_module
    count = 1
    if context.args:
        try:
            count = int(context.args[0])
            if count < 1: count = 1
            if count > 20: count = 20
        except ValueError:
            pass
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/uuid: count={count}")
    
    parts = [
        f"🆔 UUID v4",
        f"{'─' * 30}",
    ]
    for i in range(count):
        parts.append(f"{i+1}. `{uuid_module.uuid4()}`")
    
    parts.append("")
    parts.append("✨ UUID4 cryptographically secure (RFC 4122)")
    
    await update.message.reply_text("\n".join(parts))
    
    if "uuid_count" not in stats:
        stats["uuid_count"] = 0
    stats["uuid_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 UUID reply sent")


async def cmd_hash(update: Update, context):
    """Hash text — /hash <algo> <text>"""
    import hashlib
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "🔐 HASH\n\n"
            "Cách dùng: /hash <algo> <text>\n\n"
            "Algorithms: md5, sha1, sha224, sha256, sha384, sha512\n\n"
            "VD:\n"
            "  /hash md5 hello\n"
            "  /hash sha256 secret\n"
            "  /hash sha512 password"
        )
        return
    
    algo = context.args[0].lower()
    text = " ".join(context.args[1:])
    
    supported = ["md5", "sha1", "sha224", "sha256", "sha384", "sha512"]
    if algo not in supported:
        await update.message.reply_text(f"❌ Algo '{algo}' không hỗ trợ. Dùng: {', '.join(supported)}")
        stats["errors"] += 1
        return
    
    try:
        h = hashlib.new(algo)
        h.update(text.encode('utf-8'))
        result = h.hexdigest()
        
        await update.message.reply_text(
            f"🔐 HASH\n"
            f"{'─' * 30}\n"
            f"📝 Input: {text[:200]}\n"
            f"🔑 Algorithm: {algo.upper()}\n"
            f"{'─' * 30}\n"
            f"✅ Hash: `{result}`"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi hash: {e}")
        stats["errors"] += 1
    
    if "hash_count" not in stats:
        stats["hash_count"] = 0
    stats["hash_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Hash reply sent")


async def cmd_color(update: Update, context):
    """Color info from hex — /color <hex>"""
    if not context.args:
        await update.message.reply_text(
            "🎨 COLOR INFO\n\n"
            "Cách dùng: /color <hex>\n\n"
            "VD: /color ff5733, /color #3498db\n"
            "✅ Trả về: RGB, HSL, preview URL"
        )
        return
    
    hex_color = context.args[0].lstrip("#").strip()
    if not re.match(r'^[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$', hex_color):
        await update.message.reply_text("❌ Hex color không hợp lệ. VD: ff5733, #3498db")
        stats["errors"] += 1
        return
    
    # Expand 3-char to 6-char
    if len(hex_color) == 3:
        hex_color = "".join(c*2 for c in hex_color)
    
    # Parse to RGB
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    # Convert to HSL
    r_n, g_n, b_n = r/255, g/255, b/255
    mx, mn = max(r_n, g_n, b_n), min(r_n, g_n, b_n)
    l = (mx + mn) / 2
    if mx == mn:
        h = s = 0
    else:
        d = mx - mn
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r_n:
            h = ((g_n - b_n) / d + (6 if g_n < b_n else 0)) / 6
        elif mx == g_n:
            h = ((b_n - r_n) / d + 2) / 6
        else:
            h = ((r_n - g_n) / d + 4) / 6
    h, s, l = int(h*360), int(s*100), int(l*100)
    
    # Color name (rough)
    color_names = {
        (0, 0, 0): "Đen", (255, 255, 255): "Trắng",
        (255, 0, 0): "Đỏ", (0, 255, 0): "Xanh lá", (0, 0, 255): "Xanh dương",
        (255, 255, 0): "Vàng", (255, 0, 255): "Hồng tím", (0, 255, 255): "Lam",
    }
    name = "Tùy chỉnh"
    min_dist = 1000
    for (cr, cg, cb), n in color_names.items():
        dist = abs(r-cr) + abs(g-cg) + abs(b-cb)
        if dist < min_dist:
            min_dist = dist
            name = n
    
    preview_url = f"https://via.placeholder.com/200x200/{hex_color}/ffffff?text=#{hex_color.upper()}"
    
    parts = [
        f"🎨 COLOR INFO",
        f"{'─' * 30}",
        f"🏷️ Hex: #{hex_color.upper()}",
        f"📊 RGB: rgb({r}, {g}, {b})",
        f"🌈 HSL: hsl({h}, {s}%, {l}%)",
        f"🎨 Tên: {name}",
        f"🖼️ Preview: {preview_url}",
        "",
        f"💡 CSS: `#{hex_color}`",
    ]
    
    # Send preview as photo
    try:
        await update.message.reply_photo(
            photo=preview_url,
            caption=f"🎨 Preview #{hex_color.upper()}"
        )
        stats["messages_sent"] += 1
    except Exception as e:
        log(f"Color preview failed: {e}")
    
    await update.message.reply_text("\n".join(parts))
    
    if "color_count" not in stats:
        stats["color_count"] = 0
    stats["color_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Color reply sent")


async def cmd_gold(update: Update, context):
    """Gold price — /gold"""
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/gold")
    
    cache_key = "gold:latest"
    cached = cache_get(cache_key, ttl_seconds=300)
    if not cached:
        try:
            r = requests.get("https://api.gold-api.com/price/XAU", timeout=10)
            r.raise_for_status()
            cached = r.json()
            cache_set(cache_key, cached)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi tải giá vàng: {e}")
            stats["errors"] += 1
            return
    
    price_usd = cached.get('price', 0)
    # Convert to VND (approximate)
    try:
        vnd_rate = 25850  # fallback USD/VND
        r_vnd = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        if r_vnd.status_code == 200:
            vnd_rate = r_vnd.json().get('rates', {}).get('VND', vnd_rate)
    except Exception:
        pass
    price_vnd = price_usd * vnd_rate / 31.1035  # per gram
    
    parts = [
        f"💰 GIÁ VÀNG HÔM NAY",
        f"{'─' * 30}",
        f"🥇 1 oz vàng (XAU):",
        f"  💵 ${price_usd:,.2f} USD",
        f"  💱 ~{price_vnd:,.0f} VND/gram",
        f"  💱 Tỷ giá USD/VND: {vnd_rate:,.0f}",
        f"",
        f"🕐 Cập nhật: {cached.get('updatedAt','?')[:19]}",
        f"📡 Nguồn: gold-api.com + open.er-api.com",
    ]
    
    await update.message.reply_text("\n".join(parts))
    
    if "gold_count" not in stats:
        stats["gold_count"] = 0
    stats["gold_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Gold reply sent")


async def cmd_country(update: Update, context):
    """Country info — /country <name>"""
    if not context.args:
        await update.message.reply_text(
            "🌍 COUNTRY INFO\n\n"
            "Cách dùng: /country <name>\n\n"
            "VD: /country Vietnam, /country Japan, /country France\n"
            "📡 Nguồn: Wikipedia REST API"
        )
        return
    
    country = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/country: {country}")
    
    cache_key = f"country:{country.lower()}"
    cached = cache_get(cache_key, ttl_seconds=3600)
    if not cached:
        try:
            r = requests.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(country)}",
                headers={
                    "User-Agent": "NhutBot/1.0 (https://zalo-bot-three.vercel.app)",
                    "Accept": "application/json",
                },
                timeout=15,
            )
            if r.status_code == 404:
                await update.message.reply_text(f"❌ Không tìm thấy quốc gia '{country}'")
                stats["errors"] += 1
                return
            r.raise_for_status()
            cached = r.json()
            cache_set(cache_key, cached)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {e}")
            stats["errors"] += 1
            return
    
    title = cached.get('title', country)
    extract = cached.get('extract', '')[:1200]
    thumbnail = cached.get('thumbnail', {}).get('source', '')
    page_url = (cached.get('content_urls', {}).get('desktop', {}) or {}).get('page', '')
    
    # Send thumbnail as photo first
    if thumbnail:
        try:
            await update.message.reply_photo(
                photo=thumbnail,
                caption=f"🌍 {title}"
            )
            stats["messages_sent"] += 1
        except Exception as e:
            log(f"Country thumbnail failed: {e}")
    
    parts = [
        f"🌍 COUNTRY INFO",
        f"{'─' * 30}",
        f"🏷️ {title}",
        "",
        extract,
    ]
    if page_url:
        parts.append("")
        parts.append(f"🔗 {page_url}")
    parts.append("")
    parts.append("📡 Nguồn: Wikipedia REST API")
    
    msg = "\n".join(parts)
    if len(msg) > 1900:
        for i in range(0, len(msg), 1900):
            await update.message.reply_text(msg[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(msg)
    
    if "country_count" not in stats:
        stats["country_count"] = 0
    stats["country_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Country reply sent")


async def cmd_tv(update: Update, context):
    """TV show info — /tv <name>"""
    if not context.args:
        await update.message.reply_text(
            "📺 TV SHOW INFO\n\n"
            "Cách dùng: /tv <name>\n\n"
            "VD: /tv Breaking Bad, /tv Wednesday, /tv Stranger Things\n"
            "📡 Nguồn: TVMaze API"
        )
        return
    
    query = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/tv: {query}")
    
    cache_key = f"tv:{query.lower()}"
    cached = cache_get(cache_key, ttl_seconds=3600)
    if not cached:
        try:
            r = requests.get(
                "https://api.tvmaze.com/singlesearch/shows",
                params={"q": query},
                timeout=10,
            )
            if r.status_code == 404:
                await update.message.reply_text(f"❌ Không tìm thấy TV show '{query}'")
                stats["errors"] += 1
                return
            r.raise_for_status()
            cached = r.json()
            cache_set(cache_key, cached)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {e}")
            stats["errors"] += 1
            return
    
    name = cached.get('name', '?')
    premiered = cached.get('premiered', '?')
    ended = cached.get('ended', '')
    status = cached.get('status', '?')
    rating = (cached.get('rating') or {}).get('average', 'N/A')
    genres = cached.get('genres', [])
    network = (cached.get('network') or {}).get('name') or (cached.get('webChannel') or {}).get('name', 'N/A')
    summary = re.sub(r'<[^>]+>', '', cached.get('summary', '') or '')[:400]
    image = (cached.get('image') or {}).get('original') or (cached.get('image') or {}).get('medium', '')
    language = cached.get('language', 'N/A')
    runtime = cached.get('runtime', 0)
    
    # Send image as photo first
    if image:
        try:
            await update.message.reply_photo(photo=image, caption=f"📺 {name}")
            stats["messages_sent"] += 1
        except Exception as e:
            log(f"TV image failed: {e}")
    
    parts = [
        f"📺 TV SHOW INFO",
        f"{'─' * 30}",
        f"🎬 {name}",
        f"📅 Premiered: {premiered}" + (f" → Ended: {ended}" if ended else ""),
        f"📊 Status: {status}",
        f"🌐 Language: {language}",
        f"⏱️ Runtime: {runtime} min" if runtime else "",
        f"⭐ Rating: {rating}/10",
        f"🎭 Genres: {', '.join(genres) if genres else 'N/A'}",
        f"📡 Network: {network}",
        "",
        summary,
        "",
        f"🔗 https://www.tvmaze.com/shows/{cached.get('id','')}",
        f"📡 Nguồn: TVMaze API",
    ]
    parts = [p for p in parts if p != ""]
    
    msg = "\n".join(parts)
    if len(msg) > 1900:
        for i in range(0, len(msg), 1900):
            await update.message.reply_text(msg[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(msg)
    
    if "tv_count" not in stats:
        stats["tv_count"] = 0
    stats["tv_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 TV reply sent")


async def cmd_binance(update: Update, context):
    """Binance ticker — /binance <pair>"""
    if not context.args:
        await update.message.reply_text(
            "📈 BINANCE TICKER\n\n"
            "Cách dùng: /binance <pair>\n\n"
            "VD:\n"
            "  /binance BTCUSDT\n"
            "  /binance ETHUSDT\n"
            "  /binance BNBUSDT\n"
            "  /binance SOLUSDT\n\n"
            "📡 Nguồn: Binance API (FREE)"
        )
        return
    
    symbol = context.args[0].upper()
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/binance: {symbol}")
    
    cache_key = f"binance:{symbol}"
    cached = cache_get(cache_key, ttl_seconds=30)  # 30 sec
    if not cached:
        try:
            r = requests.get(
                f"https://api.binance.com/api/v3/ticker/24hr",
                params={"symbol": symbol},
                timeout=10,
            )
            if r.status_code == 400:
                await update.message.reply_text(f"❌ Symbol '{symbol}' không hợp lệ")
                stats["errors"] += 1
                return
            r.raise_for_status()
            cached = r.json()
            cache_set(cache_key, cached)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {e}")
            stats["errors"] += 1
            return
    
    parts = [
        f"📈 BINANCE TICKER",
        f"{'─' * 30}",
        f"🔢 Symbol: {cached.get('symbol','?')}",
        f"💵 Last price: ${float(cached.get('lastPrice',0)):,.4f}",
        f"📊 24h change: {cached.get('priceChangePercent','?')}%",
        f"📈 24h high: ${float(cached.get('highPrice',0)):,.4f}",
        f"📉 24h low: ${float(cached.get('lowPrice',0)):,.4f}",
        f"💰 Volume: {float(cached.get('quoteVolume',0)):,.0f} USDT",
        f"{'─' * 30}",
        f"📡 Nguồn: Binance API",
    ]
    
    await update.message.reply_text("\n".join(parts))
    
    if "binance_count" not in stats:
        stats["binance_count"] = 0
    stats["binance_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Binance reply sent")


async def cmd_binary(update: Update, context):
    """Number base converter — /binary <number> [from_base]"""
    if not context.args:
        await update.message.reply_text(
            "🔢 NUMBER BASE CONVERTER\n\n"
            "Cách dùng: /binary <number> [from_base]\n\n"
            "Bases: 2 (binary), 8 (octal), 10 (decimal), 16 (hex)\n\n"
            "VD:\n"
            "  /binary 255 → convert decimal 255\n"
            "  /binary 1010 2 → convert binary 1010\n"
            "  /binary ff 16 → convert hex ff\n"
            "  /binary 777 8 → convert octal 777"
        )
        return
    
    num_str = context.args[0]
    from_base = int(context.args[1]) if len(context.args) >= 2 else 10
    
    if from_base not in (2, 8, 10, 16):
        await update.message.reply_text("❌ Base phải là 2, 8, 10, hoặc 16")
        stats["errors"] += 1
        return
    
    try:
        # Parse the number
        decimal_value = int(num_str, from_base)
        
        parts = [
            f"🔢 NUMBER BASE CONVERTER",
            f"{'─' * 30}",
            f"📝 Input: {num_str} (base {from_base})",
            f"{'─' * 30}",
            f"🔟 Decimal: {decimal_value}",
            f"2️⃣ Binary: {bin(decimal_value)[2:]}",
            f"8️⃣ Octal: {oct(decimal_value)[2:]}",
            f"🔟 Hex: {hex(decimal_value).upper()[2:]}",
            f"{'─' * 30}",
            f"💡 Cách dùng: /binary <number> [base]",
        ]
        
        await update.message.reply_text("\n".join(parts))
    except ValueError as e:
        await update.message.reply_text(f"❌ Không thể parse '{num_str}' ở base {from_base}: {e}")
        stats["errors"] += 1
        return
    
    if "binary_count" not in stats:
        stats["binary_count"] = 0
    stats["binary_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Binary reply sent")


async def cmd_horoscope(update: Update, context):
    """Daily horoscope — /horoscope <sign>"""
    if not context.args:
        await update.message.reply_text(
            "♈ DAILY HOROSCOPE\n\n"
            "Cách dùng: /horoscope <sign>\n\n"
            "Signs:\n"
            "♈ Aries, ♉ Taurus, ♊ Gemini, ♋ Cancer\n"
            "♌ Leo, ♍ Virgo, ♎ Libra, ♏ Scorpio\n"
            "♐ Sagittarius, ♑ Capricorn, ♒ Aquarius, ♓ Pisces\n\n"
            "VD: /horoscope aries, /horoscope leo"
        )
        return
    
    sign = context.args[0].lower()
    valid_signs = ["aries", "taurus", "gemini", "cancer", "leo", "virgo",
                   "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"]
    if sign not in valid_signs:
        await update.message.reply_text(f"❌ Sign '{sign}' không hợp lệ. Dùng: {', '.join(valid_signs)}")
        stats["errors"] += 1
        return
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/horoscope: {sign}")
    
    cache_key = f"horoscope:{sign}:{datetime.datetime.now().strftime('%Y-%m-%d')}"
    cached = cache_get(cache_key, ttl_seconds=3600)
    if not cached:
        try:
            r = requests.get(
                "https://horoscope-app-api.vercel.app/api/v1/get-horoscope/daily",
                params={"sign": sign, "day": "TODAY"},
                timeout=10,
            )
            r.raise_for_status()
            cached = r.json().get('data', {})
            cache_set(cache_key, cached)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {e}")
            stats["errors"] += 1
            return
    
    sign_emojis = {
        "aries": "♈", "taurus": "♉", "gemini": "♊", "cancer": "♋",
        "leo": "♌", "virgo": "♍", "libra": "♎", "scorpio": "♏",
        "sagittarius": "♐", "capricorn": "♑", "aquarius": "♒", "pisces": "♓",
    }
    emoji = sign_emojis.get(sign, "🔮")
    horoscope_text = cached.get('horoscope', 'No horoscope today.')
    date = cached.get('date', '?')
    
    msg = (
        f"{emoji} HOROSCOPE — {sign.upper()}\n"
        f"{'─' * 30}\n"
        f"📅 {date}\n"
        f"{'─' * 30}\n\n"
        f"{horoscope_text}\n\n"
        f"📡 Nguồn: horoscope-app-api"
    )
    
    if len(msg) > 1900:
        for i in range(0, len(msg), 1900):
            await update.message.reply_text(msg[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(msg)
    
    if "horoscope_count" not in stats:
        stats["horoscope_count"] = 0
    stats["horoscope_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Horoscope reply sent")


async def cmd_reverse(update: Update, context):
    """Reverse text — /reverse <text>"""
    if not context.args:
        await update.message.reply_text(
            "🔄 REVERSE TEXT\n\n"
            "Cách dùng: /reverse <text>\n\n"
            "VD: /reverse Hello World → dlroW olleH"
        )
        return
    
    text = " ".join(context.args)
    reversed_text = text[::-1]
    
    await update.message.reply_text(
        f"🔄 REVERSE TEXT\n"
        f"{'─' * 30}\n"
        f"📝 Input: {text[:500]}\n"
        f"✅ Reversed: {reversed_text[:500]}"
    )
    
    if "reverse_count" not in stats:
        stats["reverse_count"] = 0
    stats["reverse_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Reverse reply sent")


async def cmd_palindrome(update: Update, context):
    """Check palindrome — /palindrome <text>"""
    if not context.args:
        await update.message.reply_text(
            "🪞 PALINDROME CHECKER\n\n"
            "Cách dùng: /palindrome <text>\n\n"
            "VD: /palindrome racecar, /palindrome madam\n"
            "VD: /palindrome Anna — not case-sensitive, ignores spaces"
        )
        return
    
    text = " ".join(context.args)
    # Normalize: lowercase, remove non-alphanumeric
    normalized = re.sub(r'[^a-z0-9]', '', text.lower())
    reversed_norm = normalized[::-1]
    
    is_palindrome = normalized == reversed_norm and len(normalized) > 0
    
    if is_palindrome:
        result_text = "✅ LÀ PALINDROME"
    else:
        result_text = "❌ KHÔNG PHẢI PALINDROME"
    
    await update.message.reply_text(
        f"🪞 PALINDROME CHECK\n"
        f"{'─' * 30}\n"
        f"📝 Input: {text[:500]}\n"
        f"🔧 Normalized: {normalized[:500]}\n"
        f"🔄 Reversed: {reversed_norm[:500]}\n"
        f"{'─' * 30}\n"
        f"{result_text}"
    )
    
    if "palindrome_count" not in stats:
        stats["palindrome_count"] = 0
    stats["palindrome_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Palindrome reply sent")


# ========== MULTI-PROVIDER AI COMMANDS (v7) ==========

async def cmd_providers(update: Update, context):
    """List all available AI providers — /providers"""
    chat_id = update.message.chat.id
    current_provider, current_model = get_chat_ai_config(chat_id)
    
    parts = [
        f"🤖 AI PROVIDERS",
        f"{'─' * 30}",
        f"📌 Đang dùng: **{current_provider}** / `{current_model}`",
        f"{'─' * 30}",
        "",
    ]
    
    for key, p in PROVIDERS.items():
        active = "✅" if key == current_provider else "  "
        api_key = _get_provider_api_key(key)
        status = "🟢 có key" if api_key else ("🆓 không cần key" if not p.get("needs_key") else "🔴 thiếu key")
        parts.append(f"{active} **{key}** — {p.get('name','?')}")
        parts.append(f"   {status} | default: `{p.get('default_model','?')}`")
        if p.get("note"):
            parts.append(f"   💡 {p['note']}")
        parts.append("")
    
    parts.append("📖 Lệnh:")
    parts.append("  • /models <provider> — xem models (real-time)")
    parts.append("  • /setmodel <provider> [model] — chọn provider+model")
    parts.append("  • /setmodel aicloud — reset về mặc định")
    parts.append("")
    parts.append("🔑 Set API key:")
    parts.append("  OpenRouter: https://openrouter.ai/keys")
    parts.append("  Groq: https://console.groq.com/keys")
    parts.append("  Nvidia NIM: https://build.nvidia.com/")
    
    msg = "\n".join(parts)
    if len(msg) > 1900:
        for i in range(0, len(msg), 1900):
            await update.message.reply_text(msg[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(msg)
    
    if "providers_count" not in stats:
        stats["providers_count"] = 0
    stats["providers_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Providers list sent")


async def cmd_models(update: Update, context):
    """List models from a provider (real-time) — /models <provider> [filter]"""
    if not context.args:
        # Show counts per provider
        parts = [
            f"📦 MODELS THEO PROVIDER",
            f"{'─' * 30}",
            "",
        ]
        for key, p in PROVIDERS.items():
            cache_key = f"models:{key}"
            cached = cache_get(cache_key, ttl_seconds=3600)
            count = len(cached) if cached else "?"
            api_key = _get_provider_api_key(key)
            status = "🟢" if api_key else ("🆓" if not p.get("needs_key") else "🔴")
            parts.append(f"{status} {key} — {count} models (cache 1h)")
        parts.append("")
        parts.append("Cách dùng: /models <provider> [filter]")
        parts.append("VD:")
        parts.append("  /models openrouter")
        parts.append("  /models openrouter free  (filter free)")
        parts.append("  /models groq")
        parts.append("  /models nvidia")
        parts.append("  /models aicloud")
        await update.message.reply_text("\n".join(parts))
        stats["messages_sent"] += 1
        return
    
    provider = context.args[0].lower()
    if provider not in PROVIDERS:
        await update.message.reply_text(f"❌ Provider '{provider}' không tồn tại. Dùng /providers để xem danh sách.")
        stats["errors"] += 1
        return
    
    # Optional filter (e.g. "free", "llama", "deepseek")
    filter_str = " ".join(context.args[1:]).lower() if len(context.args) > 1 else ""
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/models {provider} (filter={filter_str})")
    
    # Fetch models
    models = _fetch_provider_models(provider, limit=200)
    
    # Filter
    if filter_str:
        models = [m for m in models if filter_str in (m.get("id","") + " " + str(m.get("owner",""))).lower()]
    
    if not models:
        await update.message.reply_text(f"❌ Không có model nào cho '{provider}' (filter='{filter_str}')")
        stats["errors"] += 1
        return
    
    # Check if it's an error response
    if models and "error" in models[0]:
        await update.message.reply_text(f"❌ Lỗi lấy models: {models[0].get('error','?')}")
        stats["errors"] += 1
        return
    
    # Build message
    p = PROVIDERS[provider]
    parts = [
        f"📦 MODELS — {p.get('name','?')}",
        f"{'─' * 30}",
        f"📊 Tổng: {len(models)} models" + (f" (filter: '{filter_str}')" if filter_str else ""),
        "",
    ]
    
    # Show first 30 models
    for i, m in enumerate(models[:30], 1):
        mid = m.get("id", "?")
        ctx = m.get("context", "")
        price = m.get("price", "")
        owner = m.get("owner", "")
        info_parts = []
        if ctx:
            info_parts.append(f"ctx={ctx//1000}K" if isinstance(ctx, int) else f"ctx={ctx}")
        if price:
            info_parts.append(price)
        if owner:
            info_parts.append(owner)
        info = " | ".join(info_parts) if info_parts else ""
        parts.append(f"{i:2d}. `{mid}`")
        if info:
            parts.append(f"    {info}")
    
    if len(models) > 30:
        parts.append("")
        parts.append(f"📝 Còn {len(models) - 30} models nữa. Dùng filter để xem:")
        parts.append(f"  /models {provider} <từ khóa>")
        parts.append(f"VD: /models {provider} llama")
    
    parts.append("")
    parts.append(f"💡 Chọn: /setmodel {provider} <model_id>")
    
    msg = "\n".join(parts)
    if len(msg) > 1900:
        # Send in chunks
        chunks = []
        current = []
        current_len = 0
        for line in msg.split("\n"):
            if current_len + len(line) > 1800 and current:
                chunks.append("\n".join(current))
                current = [line]
                current_len = len(line)
            else:
                current.append(line)
                current_len += len(line) + 1
        if current:
            chunks.append("\n".join(current))
        for chunk in chunks:
            await update.message.reply_text(chunk)
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(msg)
    
    if "models_count" not in stats:
        stats["models_count"] = 0
    stats["models_count"] += 1
    stats["messages_sent"] += 1
    log(f"🤖 Models reply sent ({len(models)} models)")


async def cmd_setmodel(update: Update, context):
    """Set provider+model for this chat — /setmodel <provider> [model]"""
    if not context.args:
        chat_id = update.message.chat.id
        current_provider, current_model = get_chat_ai_config(chat_id)
        await update.message.reply_text(
            f"⚙️ SET PROVIDER + MODEL\n\n"
            f"📌 Hiện tại: `{current_provider}` / `{current_model}`\n\n"
            f"Cách dùng:\n"
            f"  /setmodel <provider>\n"
            f"  /setmodel <provider> <model_id>\n"
            f"  /setmodel aicloud — reset mặc định\n\n"
            f"Providers:\n"
            f"  • aicloud — AI Cloud (Gemini 1.5 Flash) — mặc định\n"
            f"  • openrouter — 437+ models (free + paid)\n"
            f"  • groq — Llama, Mixtral (siêu nhanh)\n"
            f"  • nvidia — Nvidia NIM (80+ models)\n\n"
            f"VD:\n"
            f"  /setmodel groq\n"
            f"  /setmodel groq llama-3.3-70b-versatile\n"
            f"  /setmodel openrouter nvidia/nemotron-3.5-lightning:free\n"
            f"  /setmodel aicloud\n\n"
            f"Xem models: /models <provider>"
        )
        stats["messages_sent"] += 1
        return
    
    provider = context.args[0].lower()
    if provider not in PROVIDERS:
        await update.message.reply_text(
            f"❌ Provider '{provider}' không tồn tại.\n\n"
            f"Providers khả dụng: {', '.join(PROVIDERS.keys())}\n"
            f"Dùng /providers để xem chi tiết."
        )
        stats["errors"] += 1
        return
    
    # Get model (optional)
    model = " ".join(context.args[1:]) if len(context.args) > 1 else PROVIDERS[provider]["default_model"]
    
    # Check if API key is set (for non-default providers)
    p = PROVIDERS[provider]
    if p.get("needs_key"):
        api_key = _get_provider_api_key(provider)
        if not api_key:
            await update.message.reply_text(
                f"⚠️ Provider **{provider}** cần API key nhưng chưa set!\n\n"
                f"Lấy key tại:\n"
                f"  OpenRouter: https://openrouter.ai/keys\n"
                f"  Groq: https://console.groq.com/keys\n"
                f"  Nvidia NIM: https://build.nvidia.com/\n\n"
                f"Set env var {p.get('key_env','API_KEY')} trên Vercel để dùng được."
            )
            stats["errors"] += 1
            return
    
    # Set
    chat_id = update.message.chat.id
    ok = set_chat_ai_config(chat_id, provider, model)
    if ok:
        p_name = PROVIDERS[provider].get("name", provider)
        await update.message.reply_text(
            f"✅ Đã set provider cho chat này!\n\n"
            f"📡 Provider: `{provider}` ({p_name})\n"
            f"🤖 Model: `{model}`\n\n"
            f"Từ giờ các tin nhắn của bạn sẽ dùng provider+model này.\n"
            f"Reset về mặc định: /setmodel aicloud\n\n"
            f"💡 Test: nhắn 'Xin chào' để xem AI trả lời."
        )
        log(f"✅ Set {chat_id} → {provider}/{model}")
        if "setmodel_count" not in stats:
            stats["setmodel_count"] = 0
        stats["setmodel_count"] += 1
    else:
        await update.message.reply_text(f"❌ Không set được. Provider '{provider}' không hợp lệ.")
        stats["errors"] += 1
    
    stats["messages_sent"] += 1


async def on_message(update: Update, context):
    stats["messages_received"] += 1
    msg = update.message.text
    chat_id = update.message.chat.id
    user = update.effective_user.display_name if update.effective_user else "?"
    log(f"📨 {user}: {msg[:60]}")
    
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(0.3)
    
    # Use chat-specific provider+model
    reply = ai_reply(msg, chat_id=chat_id)
    if len(reply) > 1900:
        for i in range(0, len(reply), 1900):
            await update.message.reply_text(reply[i:i+1900])
            await asyncio.sleep(0.3)
    else:
        await update.message.reply_text(reply)
    stats["messages_sent"] += 1
    log(f"🤖 Reply sent ({len(reply)} chars)")


def init_bot():
    global bot_app
    bot_app = (
        ApplicationBuilder()
        .token(ZALO_BOT_TOKEN)
        .base_url(ZALO_BASE_URL)  # ⚠️ MUST override legacy URL
        .build()
    )
    # NOTE: Do NOT call bot.delete_webhook() here — it uses asyncio.run() which
    # would close the event loop and break the httpx clients for the polling loop.
    # The polling loop in _application.py handles bot.initialize() correctly.
    bot_app.add_handler(CommandHandler("start", cmd_start))
    bot_app.add_handler(CommandHandler("help", cmd_help))
    bot_app.add_handler(CommandHandler("image", cmd_image))
    bot_app.add_handler(CommandHandler("code", cmd_code))
    bot_app.add_handler(CommandHandler("search", cmd_search))
    bot_app.add_handler(CommandHandler("xoso", cmd_xoso))
    bot_app.add_handler(CommandHandler("weather", cmd_weather))
    bot_app.add_handler(CommandHandler("qr", cmd_qr))
    bot_app.add_handler(CommandHandler("translate", cmd_translate))
    bot_app.add_handler(CommandHandler("calc", cmd_calc))
    bot_app.add_handler(CommandHandler("time", cmd_time))
    # 10 new commands
    bot_app.add_handler(CommandHandler("wiki", cmd_wiki))
    bot_app.add_handler(CommandHandler("currency", cmd_currency))
    bot_app.add_handler(CommandHandler("crypto", cmd_crypto))
    bot_app.add_handler(CommandHandler("shorten", cmd_shorten))
    bot_app.add_handler(CommandHandler("ip", cmd_ip))
    bot_app.add_handler(CommandHandler("password", cmd_password))
    bot_app.add_handler(CommandHandler("define", cmd_define))
    bot_app.add_handler(CommandHandler("base64", cmd_base64))
    bot_app.add_handler(CommandHandler("joke", cmd_joke))
    bot_app.add_handler(CommandHandler("youtube", cmd_youtube))
    bot_app.add_handler(CommandHandler("tiktok", cmd_tiktok))
    bot_app.add_handler(CommandHandler("ytdl", cmd_ytdl))
    bot_app.add_handler(CommandHandler("ytmp3", cmd_ytmp3))
    # 14 new commands (v6)
    bot_app.add_handler(CommandHandler("news", cmd_news))
    bot_app.add_handler(CommandHandler("github", cmd_github))
    bot_app.add_handler(CommandHandler("quote", cmd_quote))
    bot_app.add_handler(CommandHandler("fact", cmd_fact))
    bot_app.add_handler(CommandHandler("uuid", cmd_uuid))
    bot_app.add_handler(CommandHandler("hash", cmd_hash))
    bot_app.add_handler(CommandHandler("color", cmd_color))
    bot_app.add_handler(CommandHandler("gold", cmd_gold))
    bot_app.add_handler(CommandHandler("country", cmd_country))
    bot_app.add_handler(CommandHandler("tv", cmd_tv))
    bot_app.add_handler(CommandHandler("binance", cmd_binance))
    bot_app.add_handler(CommandHandler("binary", cmd_binary))
    bot_app.add_handler(CommandHandler("horoscope", cmd_horoscope))
    bot_app.add_handler(CommandHandler("reverse", cmd_reverse))
    bot_app.add_handler(CommandHandler("palindrome", cmd_palindrome))
    # 3 new commands (v7) — multi-provider AI
    bot_app.add_handler(CommandHandler("providers", cmd_providers))
    bot_app.add_handler(CommandHandler("models", cmd_models))
    bot_app.add_handler(CommandHandler("setmodel", cmd_setmodel))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    return bot_app


# ========== FLASK DASHBOARD ==========

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NhutBot — Zalo AI Bot Dashboard</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:system-ui,sans-serif; background:#0F1117; color:#FFFFFF; min-height:100vh; }
.container { max-width:900px; margin:0 auto; padding:20px; }
h1 { color:#0A84FF; font-size:28px; margin-bottom:8px; }
.subtitle { color:#8E8E93; margin-bottom:24px; font-size:14px; }
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:24px; }
.stat-card { background:#1C1C1E; border-radius:14px; padding:18px; border:1px solid #38383A; text-align:center; }
.stat-value { font-size:32px; font-weight:800; color:#0A84FF; }
.stat-label { font-size:12px; color:#8E8E93; margin-top:4px; }
.status { display:inline-flex; align-items:center; gap:6px; background:rgba(48,209,88,0.1); padding:6px 14px; border-radius:999px; border:1px solid #30D158; }
.status-dot { width:8px; height:8px; border-radius:50%; background:#30D158; animation:pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.logs { background:#1C1C1E; border-radius:14px; padding:16px; border:1px solid #38383A; max-height:400px; overflow-y:auto; }
.logs h2 { color:#0A84FF; font-size:16px; margin-bottom:12px; }
.log-entry { font-family:monospace; font-size:13px; color:#8E8E93; padding:4px 0; border-bottom:1px solid #2C2C2E; }
.log-entry:last-child { border:none; }
.commands { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin-bottom:24px; }
.cmd-card { background:#1C1C1E; border-radius:12px; padding:14px; border:1px solid #38383A; }
.cmd-card code { color:#0A84FF; font-weight:700; }
.cmd-card p { color:#8E8E93; font-size:13px; margin-top:4px; }
.uptime { color:#8E8E93; font-size:13px; text-align:center; margin-top:16px; }
</style>
</head>
<body>
<div class="container">
  <h1>🤖 NhutBot — Zalo AI Bot</h1>
  <p class="subtitle">Bot ID: {{ bot_id }} | Token: {{ token_preview }}... | {{ status_html|safe }}</p>
  
  <div class="stats">
    <div class="stat-card"><div class="stat-value">{{ stats.messages_received }}</div><div class="stat-label">Tin nhận</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.messages_sent }}</div><div class="stat-label">Tin gửi</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.ai_calls }}</div><div class="stat-label">AI calls</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.images_generated }}</div><div class="stat-label">Ảnh tạo</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.search_count }}</div><div class="stat-label">Tìm web</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.wiki_count }}</div><div class="stat-label">Wiki</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.yt_count }}</div><div class="stat-label">YouTube</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.xoso_count }}</div><div class="stat-label">Dò vé</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.weather_count }}</div><div class="stat-label">Thời tiết</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.currency_count }}</div><div class="stat-label">Đổi tiền</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.crypto_count }}</div><div class="stat-label">Crypto</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.dict_count }}</div><div class="stat-label">Tra từ</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.url_count }}</div><div class="stat-label">Rút gọn</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.ip_count }}</div><div class="stat-label">Tra IP</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.tiktok_count }}</div><div class="stat-label">TikTok</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.ytdl_count }}</div><div class="stat-label">YT Video</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.ytmp3_count }}</div><div class="stat-label">YT MP3</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.news_count }}</div><div class="stat-label">Tin tức</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.github_count }}</div><div class="stat-label">GitHub</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.country_count }}</div><div class="stat-label">Quốc gia</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.tv_count }}</div><div class="stat-label">TV Show</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.gold_count }}</div><div class="stat-label">Giá vàng</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.binance_count }}</div><div class="stat-label">Binance</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.horoscope_count }}</div><div class="stat-label">Hoàng đạo</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.quote_count }}</div><div class="stat-label">Quote</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.fact_count }}</div><div class="stat-label">Fact</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.joke_count }}</div><div class="stat-label">Joke</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.errors }}</div><div class="stat-label">Lỗi</div></div>
  </div>
  
  <div class="commands">
    <div class="cmd-card"><code>/start</code><p>Chào hỏi + hướng dẫn</p></div>
    <div class="cmd-card"><code>/help</code><p>Hiển thị trợ giúp</p></div>
    <div class="cmd-card"><code>/image &lt;mô tả&gt;</code><p>Tạo ảnh AI</p></div>
    <div class="cmd-card"><code>/code &lt;câu hỏi&gt;</code><p>Hỏi code</p></div>
    <div class="cmd-card"><code>/translate [lang] &lt;txt&gt;</code><p>Dịch văn bản</p></div>
    <div class="cmd-card"><code>/search &lt;từ khóa&gt;</code><p>Tìm web</p></div>
    <div class="cmd-card"><code>/news [chủ đề]</code><p>Tin tức</p></div>
    <div class="cmd-card"><code>/wiki [vi|en] &lt;q&gt;</code><p>Wikipedia</p></div>
    <div class="cmd-card"><code>/youtube &lt;q&gt;</code><p>Tìm YouTube</p></div>
    <div class="cmd-card"><code>/define &lt;word&gt;</code><p>Từ điển Anh</p></div>
    <div class="cmd-card"><code>/country &lt;tên&gt;</code><p>Quốc gia</p></div>
    <div class="cmd-card"><code>/tv &lt;tên&gt;</code><p>TV show</p></div>
    <div class="cmd-card"><code>/github &lt;user&gt;</code><p>GitHub profile</p></div>
    <div class="cmd-card"><code>/tiktok &lt;url&gt;</code><p>Tải TikTok</p></div>
    <div class="cmd-card"><code>/ytdl &lt;url&gt;</code><p>Tải YT video</p></div>
    <div class="cmd-card"><code>/ytmp3 &lt;url&gt;</code><p>YT → MP3</p></div>
    <div class="cmd-card"><code>/xoso &lt;số&gt; [tỉnh]</code><p>Dò vé số</p></div>
    <div class="cmd-card"><code>/weather &lt;nơi&gt;</code><p>Thời tiết</p></div>
    <div class="cmd-card"><code>/currency &lt;amt&gt; &lt;f&gt; &lt;t&gt;</code><p>Đổi tiền</p></div>
    <div class="cmd-card"><code>/crypto &lt;sym&gt;</code><p>Crypto (CoinGecko)</p></div>
    <div class="cmd-card"><code>/binance &lt;pair&gt;</code><p>Binance ticker</p></div>
    <div class="cmd-card"><code>/gold</code><p>Giá vàng</p></div>
    <div class="cmd-card"><code>/qr &lt;text&gt;</code><p>QR code</p></div>
    <div class="cmd-card"><code>/shorten &lt;url&gt;</code><p>Rút gọn URL</p></div>
    <div class="cmd-card"><code>/base64 enc|dec &lt;txt&gt;</code><p>Base64</p></div>
    <div class="cmd-card"><code>/binary &lt;num&gt; [base]</code><p>Convert base</p></div>
    <div class="cmd-card"><code>/password [length]</code><p>Mật khẩu mạnh</p></div>
    <div class="cmd-card"><code>/hash &lt;algo&gt; &lt;text&gt;</code><p>MD5/SHA256</p></div>
    <div class="cmd-card"><code>/uuid [count]</code><p>UUID v4</p></div>
    <div class="cmd-card"><code>/color &lt;hex&gt;</code><p>Info màu</p></div>
    <div class="cmd-card"><code>/ip [ip]</code><p>Tra IP</p></div>
    <div class="cmd-card"><code>/calc &lt;biểu thức&gt;</code><p>Máy tính</p></div>
    <div class="cmd-card"><code>/time [tz]</code><p>Giờ hiện tại</p></div>
    <div class="cmd-card"><code>/horoscope &lt;sign&gt;</code><p>Hoàng đạo</p></div>
    <div class="cmd-card"><code>/quote</code><p>Câu nói hay</p></div>
    <div class="cmd-card"><code>/fact</code><p>Fact ngẫu nhiên</p></div>
    <div class="cmd-card"><code>/joke [cat]</code><p>Câu nói vui</p></div>
    <div class="cmd-card"><code>/reverse &lt;text&gt;</code><p>Đảo text</p></div>
    <div class="cmd-card"><code>/palindrome &lt;text&gt;</code><p>Check palindrome</p></div>
    <div class="cmd-card"><code>Nhắn tin</code><p>AI trả lời</p></div>
  </div>
  
  <div class="logs">
    <h2>📋 Logs gần đây</h2>
    {% for log in logs %}
    <div class="log-entry">{{ log }}</div>
    {% endfor %}
    {% if not logs %}
    <div class="log-entry">Chưa có log. Bot đang chờ tin nhắn...</div>
    {% endif %}
  </div>
  
  <p class="uptime">⏱️ Uptime: {{ uptime }} | Powered by NhutCoder Team</p>
</div>
<script>setTimeout(()=>location.reload(),10000)</script>
</body>
</html>
"""

@app.route("/")
def dashboard():
    uptime_sec = int(time.time() - stats["started_at"])
    h, m, s = uptime_sec // 3600, (uptime_sec % 3600) // 60, uptime_sec % 60
    return render_template_string(DASHBOARD_HTML,
        bot_id=ZALO_BOT_TOKEN.split(":")[0],
        token_preview=ZALO_BOT_TOKEN.split(":")[1][:10],
        stats=stats,
        logs=list(reversed(recent_logs)),
        uptime=f"{h}h {m}m {s}s",
        status_html='<span class="status"><span class="status-dot"></span>Online</span>',
    )

@app.route("/health")
def health():
    return jsonify({"status": "ok", "bot_id": ZALO_BOT_TOKEN.split(":")[0], "stats": stats})

@app.route("/logs")
def logs():
    """View recent logs for debugging."""
    return jsonify({
        "logs": list(reversed(recent_logs)),
        "stats": stats,
        "cache_size": len(_cache),
        "bot_initialized": bot_app.bot._initialized if bot_app else False,
    })

@app.route("/webhook", methods=["POST"])
def webhook():
    """Zalo webhook endpoint."""
    data = request.json or {}
    log(f"Webhook received: {json.dumps(data)[:300]}")
    # Zalo wraps the update in `{"ok": true, "result": {...}}`
    payload = data.get("result", data) if isinstance(data, dict) else data
    
    # Skip Zalo webhook test events (event_name="webhook.test")
    event_name = payload.get("event_name") if isinstance(payload, dict) else None
    if event_name == "webhook.test":
        log("✅ Webhook test event received (ignoring)")
        return jsonify({"ok": True})
    
    if not bot_app:
        log("❌ bot_app not initialized")
        return jsonify({"ok": False, "error": "bot not initialized"})
    
    if not payload:
        log("❌ empty payload")
        return jsonify({"ok": False, "error": "empty payload"})
    
    try:
        loop = asyncio.new_event_loop()
        # Ensure bot is initialized (needed for httpx client)
        if not bot_app.bot._initialized:
            log("🔧 Initializing bot...")
            loop.run_until_complete(bot_app.bot.initialize())
        
        update = Update.de_json(payload, bot_app.bot)
        if update is None or update.message is None or update.message.chat is None:
            log(f"❌ Invalid update (no message/chat): {json.dumps(payload)[:200]}")
            return jsonify({"ok": False, "error": "invalid update"})
        
        log(f"✅ Processing update from chat_id={update.message.chat.id}")
        loop.run_until_complete(bot_app.process_update(update))
        loop.close()
        log("✅ Update processed")
    except Exception as e:
        import traceback
        log(f"❌ Webhook error: {e}")
        log(f"❌ Traceback: {traceback.format_exc()[:500]}")
        stats["errors"] += 1
    return jsonify({"ok": True})


@app.route("/setup-webhook")
def setup_webhook():
    """Call this once after deploy to register the webhook URL with Zalo."""
    host = request.host_url.rstrip("/")
    webhook_url = f"{host}/webhook"
    secret = "nhutbot-secret-2024"
    log(f"Setting webhook URL: {webhook_url}")
    try:
        # Use sync wrapper of Bot.set_webhook
        from zalo_bot import Bot as _Bot
        b = _Bot(token=ZALO_BOT_TOKEN, base_url=ZALO_BASE_URL)
        ok = b.set_webhook(url=webhook_url, secret_token=secret)
        return jsonify({
            "ok": ok,
            "webhook_url": webhook_url,
            "secret": secret,
            "message": "Webhook registered. Bot will now reply to messages on Zalo." if ok else "Failed to set webhook."
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/remove-webhook")
def remove_webhook():
    """Remove webhook so we can use long polling again."""
    try:
        from zalo_bot import Bot as _Bot
        b = _Bot(token=ZALO_BOT_TOKEN, base_url=ZALO_BASE_URL)
        ok = b.delete_webhook()
        return jsonify({"ok": ok, "message": "Webhook removed — bot will use long polling."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ========== BOT THREAD ==========

def run_bot_polling():
    """Run bot in background thread (long polling)."""
    log("Bot polling thread started")
    try:
        init_bot()
        bot_app.run_polling()
    except Exception as e:
        log(f"Bot polling error: {e}")
        stats["errors"] += 1


# ========== INIT FOR SERVERLESS ==========

# Always initialize bot handlers at module load so webhook endpoint works
# (On Vercel/serverless, __main__ doesn't run — only the Flask `app` is exposed)
try:
    init_bot()
    log("Bot handlers initialized (webhook mode ready)")
except Exception as e:
    log(f"init_bot error (will retry on demand): {e}")


# ========== MAIN ==========

if __name__ == "__main__":
    log("=" * 50)
    log("🤖 NhutBot — Zalo AI Bot starting...")
    log(f"Bot Token: {ZALO_BOT_TOKEN[:20]}...")
    log(f"Base URL: {ZALO_BASE_URL}")

    # Get AI JWT
    log("Connecting to AI Cloud...")
    get_jwt()
    if ai_jwt:
        log("✅ AI Cloud ready (Nhutbot 1.0 Flash)")
    else:
        log("⚠️ AI Cloud unavailable")

    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot_polling, daemon=True)
    bot_thread.start()
    log("Bot polling thread started")

    # Start Flask dashboard
    log(f"Dashboard: http://0.0.0.0:{PORT}")
    log("=" * 50)

    app.run(host="0.0.0.0", port=PORT)
