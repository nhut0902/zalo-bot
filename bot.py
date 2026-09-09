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
    "errors": 0,
    "started_at": time.time(),
}
recent_logs = []
ai_jwt = ""

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

def ai_reply(message: str) -> str:
    global ai_jwt
    stats["ai_calls"] += 1
    if not ai_jwt:
        ai_jwt = get_jwt()
    if not ai_jwt:
        return "Xin lỗi, AI đang bảo trì. Thử lại sau."
    try:
        resp = requests.post(AI_CLOUD_URL, headers={
            "Authorization": f"Bearer {ai_jwt}",
            "Content-Type": "application/json",
        }, json={
            "model": "gemini-1.5-flash",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            "max_tokens": 1024,
            "temperature": 0.7,
        }, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "?")
        elif resp.status_code == 401:
            ai_jwt = get_jwt()
            if ai_jwt: return ai_reply(message)
        return f"AI lỗi (HTTP {resp.status_code})"
    except Exception as e:
        stats["errors"] += 1
        return f"Lỗi: {e}"

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
    
    return {
        "province": display_name,
        "region": region.upper(),
        "date": date_str,
        "title": title,
        "prizes": prizes,
    }


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


# ========== BOT LOGIC ==========

bot_app = None

async def cmd_start(update: Update, context):
    name = update.effective_user.display_name if update.effective_user else "bạn"
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    await update.message.reply_text(
        f"🤖 Chào {name}!\n\nTôi là NhutBot trên Zalo.\n\n"
        "📝 Lệnh:\n"
        "• Nhắn tin → AI trả lời\n"
        "• /image <mô tả> → Tạo ảnh AI\n"
        "• /code <câu hỏi> → Hỏi code\n"
        "• /search <từ khóa> → Tìm web\n"
        "• /xoso <số> [tỉnh] → Dò vé số\n"
        "• /weather <địa điểm> → Thời tiết\n"
        "• /qr <text> → Tạo QR code\n"
        "• /translate <text> → Dịch văn bản\n"
        "• /calc <biểu thức> → Máy tính\n"
        "• /time [múi giờ] → Giờ hiện tại\n"
        "• /help → Trợ giúp"
    )
    stats["messages_sent"] += 1
    log(f"/start from {name}")

async def cmd_help(update: Update, context):
    await update.message.reply_text(
        "📋 HƯỚNG DẪN NhutBot\n\n"
        "🤖 Nhắn tin → AI trả lời thông minh\n\n"
        "🎨 /image <mô tả> → Tạo ảnh AI\n"
        "    VD: /image con mèo trên mặt trăng\n\n"
        "💻 /code <câu hỏi> → Hỏi về lập trình\n"
        "    VD: /code hàm fibonacci Python\n\n"
        "🔍 /search <từ khóa> → Tìm kiếm web\n"
        "    VD: /search giá vàng hôm nay\n\n"
        "🎰 /xoso <số> [tỉnh] → Dò vé số theo tỉnh\n"
        "    VD: /xoso 94504\n"
        "    VD: /xoso 94504 hcm (TP.HCM)\n"
        "    VD: /xoso 04 danang (Đà Nẵng)\n"
        "    VD: /xoso 94504 mb 08-09-2026 (ngày cụ thể)\n"
        "    Gõ /xoso để xem tất cả tỉnh hỗ trợ\n\n"
        "🌤️ /weather <địa điểm> → Thời tiết\n"
        "    VD: /weather Hà Nội\n\n"
        "📱 /qr <text> → Tạo QR code\n"
        "    VD: /qr https://google.com\n\n"
        "🌐 /translate [lang] <text> → Dịch văn bản\n"
        "    VD: /translate hello\n"
        "    VD: /translate en Xin chào\n\n"
        "🧮 /calc <biểu thức> → Máy tính\n"
        "    VD: /calc 2+3*4\n"
        "    VD: /calc sqrt(144)\n\n"
        "🕐 /time [múi giờ] → Giờ hiện tại\n"
        "    VD: /time\n"
        "    VD: /time us, /time japan, /time london\n\n"
        "💡 Nhắn tự nhiên, AI hiểu tiếng Việt!"
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
    reply = ai_reply(f"Bạn là chuyên gia lập trình. Trả lời ngắn gọn với code:\n\n{question}")
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
    """Weather — /weather <location>"""
    if not context.args:
        await update.message.reply_text("🌤️ Gõ: /weather <địa điểm>\nVD: /weather Hà Nội")
        return
    location = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/weather: {location}")
    
    # Use Tavily to search weather (free, no separate API needed)
    result = search_web(f"thời tiết {location} hôm nay", max_results=3)
    stats["search_count"] += 1
    
    parts = [f"🌤️ THỜI TIẾT: {location}", "─" * 30, ""]
    if result.get("answer"):
        parts.append(result["answer"][:1200])
    else:
        parts.append("❌ Không tìm thấy thông tin thời tiết.")
    
    if result.get("results"):
        parts.append("")
        parts.append("📎 Nguồn:")
        for i, item in enumerate(result["results"][:2], 1):
            parts.append(f"{i}. {item.get('title', '')[:60]}")
            if item.get("url"):
                parts.append(f"   🔗 {item['url']}")
    
    await update.message.reply_text("\n".join(parts))
    stats["messages_sent"] += 1


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
    
    # Use AI Cloud proxy for translation (more reliable than Google Translate API which blocks bots)
    try:
        if not ai_jwt:
            get_jwt()
        if not ai_jwt:
            await update.message.reply_text("❌ Dịch vụ AI đang bảo trì, thử lại sau.")
            stats["errors"] += 1
            return
        
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
        
        resp = requests.post(AI_CLOUD_URL, headers={
            "Authorization": f"Bearer {ai_jwt}",
            "Content-Type": "application/json",
        }, json={
            "model": "gemini-1.5-flash",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.3,
        }, timeout=30)
        
        if resp.status_code == 200:
            translated = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            stats["ai_calls"] += 1
            result_text = (
                f"🌐 DỊCH → {target_name}\n"
                f"{'─' * 30}\n"
                f"📝 Gốc: {text_to_translate[:500]}\n"
                f"✅ Dịch: {translated[:1000]}"
            )
            await update.message.reply_text(result_text)
        else:
            await update.message.reply_text(f"❌ Lỗi dịch (HTTP {resp.status_code})")
            stats["errors"] += 1
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi dịch: {e}")
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


async def on_message(update: Update, context):
    stats["messages_received"] += 1
    msg = update.message.text
    user = update.effective_user.display_name if update.effective_user else "?"
    log(f"📨 {user}: {msg[:60]}")
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(0.3)
    
    reply = ai_reply(msg)
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
    <div class="stat-card"><div class="stat-value">{{ stats.search_count }}</div><div class="stat-label">Tìm kiếm</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.xoso_count }}</div><div class="stat-label">Dò vé số</div></div>
    <div class="stat-card"><div class="stat-value">{{ stats.errors }}</div><div class="stat-label">Lỗi</div></div>
  </div>
  
  <div class="commands">
    <div class="cmd-card"><code>/start</code><p>Chào hỏi + hướng dẫn</p></div>
    <div class="cmd-card"><code>/help</code><p>Hiển thị trợ giúp</p></div>
    <div class="cmd-card"><code>/image &lt;mô tả&gt;</code><p>Tạo ảnh bằng AI</p></div>
    <div class="cmd-card"><code>/code &lt;câu hỏi&gt;</code><p>Hỏi về lập trình</p></div>
    <div class="cmd-card"><code>/search &lt;từ khóa&gt;</code><p>Tìm kiếm web (Tavily)</p></div>
    <div class="cmd-card"><code>/xoso &lt;số&gt; [tỉnh]</code><p>Dò vé số theo tỉnh</p></div>
    <div class="cmd-card"><code>/weather &lt;nơi&gt;</code><p>Thời tiết</p></div>
    <div class="cmd-card"><code>/qr &lt;text&gt;</code><p>Tạo QR code</p></div>
    <div class="cmd-card"><code>/translate [lang] &lt;text&gt;</code><p>Dịch văn bản</p></div>
    <div class="cmd-card"><code>/calc &lt;biểu thức&gt;</code><p>Máy tính khoa học</p></div>
    <div class="cmd-card"><code>/time [múi giờ]</code><p>Giờ hiện tại</p></div>
    <div class="cmd-card"><code>Nhắn tin</code><p>AI trả lời thông minh</p></div>
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

@app.route("/webhook", methods=["POST"])
def webhook():
    """Zalo webhook endpoint (if configured)."""
    data = request.json or {}
    log(f"Webhook received: {json.dumps(data)[:200]}")
    # Zalo wraps the update in `{"ok": true, "result": {...}}`
    payload = data.get("result", data) if isinstance(data, dict) else data
    if bot_app and payload:
        try:
            loop = asyncio.new_event_loop()
            update = Update.de_json(payload, bot_app.bot)
            loop.run_until_complete(bot_app.process_update(update))
            loop.close()
        except Exception as e:
            log(f"Webhook error: {e}")
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
