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

def fetch_xoso_results(region: str = "mb", date_str: str = None) -> dict:
    """
    Fetch lottery results from xoso.com.vn (FREE, no API key).
    region: 'mb' (Miền Bắc), 'mn' (Miền Nam), 'mt' (Miền Trung)
    date_str: 'DD-MM-YYYY' format, default = today
    Returns dict: {date, region, prizes: {prize_code: [numbers]}, error: str}
    """
    if not date_str:
        date_str = datetime.datetime.now().strftime("%d-%m-%Y")
    
    url = f"{XOSO_BASE}/xs{region}-{date_str}.html"
    try:
        resp = requests.get(url, headers=XOSO_HEADERS, timeout=15)
        if resp.status_code == 404:
            return {"error": f"Chưa có kết quả xổ số ngày {date_str} (có thể chưa quay)."}
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return {"error": f"Lỗi tải KQXS: {e}"}
    
    # Parse prize spans: <span id="{region}_prize{CODE}_item{N}">NUMBER</span>
    # Examples: mb_prizeDB_item0, mb_prize1_item0, mb_prize2_item0, ...
    prizes = {}
    pattern = re.compile(
        rf'{region}_prize(DB|[1-8])_item\d+[^>]*>\s*([0-9\s]+)\s*</span>',
        re.IGNORECASE
    )
    for m in pattern.finditer(html):
        code = m.group(1).upper().replace("DB", "DB")
        num = re.sub(r'\s+', '', m.group(2))
        if code not in prizes:
            prizes[code] = []
        if num and num not in prizes[code]:
            prizes[code].append(num)
    
    if not prizes:
        return {"error": f"Không tìm thấy kết quả xổ số cho {region.upper()} ngày {date_str}."}
    
    # Find title to confirm date
    title_match = re.search(r'<title>([^<]+)</title>', html)
    title = title_match.group(1).strip() if title_match else ""
    
    return {
        "region": region.upper(),
        "date": date_str,
        "title": title,
        "prizes": prizes,
    }


def check_lottery_ticket(user_number: str, region: str = "mb", date_str: str = None) -> str:
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
    result = fetch_xoso_results(region, date_str)
    if "error" in result:
        return f"❌ {result['error']}"
    
    prizes = result["prizes"]
    region_name = {"MB": "Miền Bắc", "MN": "Miền Nam", "MT": "Miền Trung"}.get(result["region"], result["region"])
    
    msg_parts = [
        f"🎰 DÒ VÉ SỐ {region_name}",
        f"📅 Ngày: {result['date']}",
        f"{'─' * 30}",
        f"🎟️ Số của bạn: {', '.join(numbers)}",
        f"{'─' * 30}",
        "",
    ]
    
    # Check each user number
    wins = []
    for num in numbers:
        num_clean = num.lstrip('0') or '0'
        # Check against each prize — match by full number or last 2 digits for lower prizes
        for code, win_nums in prizes.items():
            for win_num in win_nums:
                win_clean = win_num.lstrip('0') or '0'
                # Match logic:
                # - DB, G1 (5-digit): exact match
                # - G2-7: for 2-digit user input, match last 2 digits
                # - For full user input length, match exact
                matched = False
                if len(num) >= 5 and num == win_num:
                    matched = True
                elif len(num) == 2 and len(win_num) >= 2 and win_num[-2:] == num:
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
        "• /search <từ khóa> → Tìm kiếm web\n"
        "• /xoso <số> → Dò vé số\n"
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
        "🎰 /xoso <số> [miền] → Dò vé số\n"
        "    VD: /xoso 94504\n"
        "    VD: /xoso 94504 mn (Miền Nam)\n"
        "    VD: /xoso 04 mb 08-09-2026\n\n"
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
    """Check lottery ticket — /xoso <number> [region] [date]"""
    if not context.args:
        await update.message.reply_text(
            "🎰 DÒ VÉ SỐ\n\n"
            "Cách dùng:\n"
            "• /xoso <số> → Dò KQXS Miền Bắc hôm nay\n"
            "• /xoso <số> mb|mn|mt → Chọn miền (Bắc/Nam/Trung)\n"
            "• /xoso <số> mb 08-09-2026 → Dò ngày cụ thể\n\n"
            "VD:\n"
            "  /xoso 94504\n"
            "  /xoso 94504,04,15\n"
            "  /xoso 94504 mn\n"
            "  /xoso 04 mb 08-09-2026\n\n"
            "📊 Nguồn: xoso.com.vn (FREE)"
        )
        return
    
    args = context.args
    user_input = args[0]
    region = "mb"
    date_str = None
    
    # Parse optional region (mb/mn/mt)
    if len(args) >= 2 and args[1].lower() in ("mb", "mn", "mt"):
        region = args[1].lower()
        if len(args) >= 3:
            date_str = args[2]
    elif len(args) >= 2:
        # Maybe 2nd arg is a date
        date_match = re.match(r'(\d{1,2})-(\d{1,2})-(\d{4})$', args[1])
        if date_match:
            date_str = args[1]
    
    await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    log(f"/xoso: {user_input} ({region}) date={date_str}")
    
    result_msg = check_lottery_ticket(user_input, region=region, date_str=date_str)
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
    <div class="cmd-card"><code>/xoso &lt;số&gt;</code><p>Dò vé số Miền Bắc/Trung/Nam</p></div>
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
