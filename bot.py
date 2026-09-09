#!/usr/bin/env python3
"""
Zalo AI Bot — NhutBot
=====================
Project độc lập — Zalo Bot chạy trên Render với dashboard Flask.

Tính năng:
- AI trả lời thông minh (Nhutbot 1.0 Flash qua AI Cloud proxy)
- /image <mô tả> — Tạo ảnh bằng AI (Pollinations.ai)
- /code <câu hỏi> — Trả lời câu hỏi code
- Dashboard web tại / — hiển thị stats + logs
- Webhook mode (Render) + Long Polling fallback

Deploy: Render.com (web service)
"""

import os
import json
import time
import asyncio
import threading
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
        "• /help → Trợ giúp"
    )
    stats["messages_sent"] += 1
    log(f"/start from {name}")

async def cmd_help(update: Update, context):
    await update.message.reply_text(
        "📋 HƯỚNG DẪN\n\n"
        "🤖 Nhắn tin → AI trả lời\n"
        "🎨 /image <mô tả> → Tạo ảnh\n"
        "💻 /code <câu hỏi> → Code help\n"
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
    <div class="stat-card"><div class="stat-value">{{ stats.errors }}</div><div class="stat-label">Lỗi</div></div>
  </div>
  
  <div class="commands">
    <div class="cmd-card"><code>/start</code><p>Chào hỏi + hướng dẫn</p></div>
    <div class="cmd-card"><code>/help</code><p>Hiển thị trợ giúp</p></div>
    <div class="cmd-card"><code>/image &lt;mô tả&gt;</code><p>Tạo ảnh bằng AI</p></div>
    <div class="cmd-card"><code>/code &lt;câu hỏi&gt;</code><p>Hỏi về lập trình</p></div>
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
    data = request.json
    log(f"Webhook received: {json.dumps(data)[:200]}")
    # Process update
    if bot_app and data:
        try:
            loop = asyncio.new_event_loop()
            update = Update.de_json(data)
            loop.run_until_complete(bot_app.process_update(update))
            loop.close()
        except Exception as e:
            log(f"Webhook error: {e}")
    return jsonify({"ok": True})


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


# ========== MAIN ==========

if __name__ == "__main__":
    log("=" * 50)
    log("🤖 NhutBot — Zalo AI Bot starting...")
    log(f"Bot Token: {ZALO_BOT_TOKEN[:20]}...")
    
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
