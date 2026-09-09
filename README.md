# Zalo AI Bot — NhutBot

Trợ lý AI thông minh trên Zalo, sử dụng Nhutbot 1.0 Flash (AI Cloud) + Pollinations.ai

## Cài đặt

```bash
cd zalo-bot
python3 -m venv venv
source venv/bin/activate
pip install python-zalo-bot requests
```

## Chạy bot

```bash
python3 bot.py
```

## Tính năng

| Lệnh | Mô tả |
|------|-------|
| Nhắn tin bất kỳ | AI trả lời thông minh (Nhutbot 1.0 Flash) |
| `/start` | Chào hỏi + hướng dẫn |
| `/help` | Hiển thị trợ giúp |
| `/image <mô tả>` | Tạo ảnh bằng AI (Pollinations.ai — free) |
| `/code <câu hỏi>` | Hỏi về code |

## Ví dụ

```
Bạn: Giá vàng hôm nay thế nào?
Bot: [AI trả lời thông minh]

Bạn: /image con mèo ngồi trên mặt trăng
Bot: [Ảnh AI tạo]

Bạn: /code viết hàm fibonacci Python
Bot: ```python
def fib(n):
    ...
```

Bạn: Chào bot!
Bot: 🤖 Chào bạn! Tôi là NhutBot...
```

## Cấu hình

- **Zalo Bot Token**: `1903914807132028399:BsUtmLazGynhSDfuGIwkzjcibFDuaCOsKoPauZopkPSiGmtoVexXKBANOjYHQhxU`
- **AI Model**: Nhutbot 1.0 Flash (Gemini 1.5 Flash qua AI Cloud proxy)
- **Image Gen**: Pollinations.ai (free, no API key)
- **JWT**: Auto-fetch từ nhutcoder-team-v2.vercel.app (valid 7 days)

## Tạo Zalo Bot mới

1. Vào https://bot.zalo.me → Create Bot
2. Lấy Bot Token
3. Thay thế `ZALO_BOT_TOKEN` trong `bot.py`
4. Chạy `python3 bot.py`
