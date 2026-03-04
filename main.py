#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════╗
║  VLESS WebSocket Proxy — Fly.io                  ║
║  SNI: youtube.com                                ║
║  Target: nl1.startvless.site:80                  ║
╚══════════════════════════════════════════════════╝
"""

import asyncio
import websockets
import websockets.server
import ssl
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ═══════════════════════════════════════════
#  إعدادات السيرفر
# ═══════════════════════════════════════════
LISTEN_HOST  = "0.0.0.0"
LISTEN_PORT  = int(os.environ.get("PORT", 8080))

# هدف VLESS
TARGET_HOST  = "nl1.startvless.site"
TARGET_PORT  = 80
TARGET_PATH  = "/vless"
TARGET_WS    = f"ws://{TARGET_HOST}:{TARGET_PORT}{TARGET_PATH}"

# SNI للتمويه
SNI_HOST     = "youtube.com"


async def pipe(src, dst, label=""):
    """ينقل البيانات من src إلى dst"""
    try:
        while True:
            data = await src.read(65536)
            if not data:
                break
            await dst.write(data)
    except Exception as e:
        logging.debug(f"pipe [{label}] ended: {e}")


async def handle_ws(client_ws, path):
    """يستقبل اتصال WebSocket من العميل ويوجهه للـ VLESS"""
    client_ip = client_ws.remote_address[0] if client_ws.remote_address else "unknown"
    logging.info(f"🔌 اتصال جديد من {client_ip} — path: {path}")

    try:
        # الاتصال بسيرفر VLESS
        headers = {
            "Host": TARGET_HOST,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
        }
        async with websockets.connect(
            TARGET_WS,
            extra_headers=headers,
            open_timeout=15,
            close_timeout=10,
            ping_interval=20,
            ping_timeout=20,
        ) as target_ws:
            logging.info(f"✅ متصل بـ VLESS — {TARGET_HOST}")

            # نقل البيانات في الاتجاهين
            async def forward(src, dst, label):
                try:
                    async for msg in src:
                        if isinstance(msg, bytes):
                            await dst.send(msg)
                        else:
                            await dst.send(msg.encode() if isinstance(msg, str) else msg)
                except websockets.exceptions.ConnectionClosed:
                    pass
                except Exception as e:
                    logging.debug(f"forward [{label}]: {e}")
                finally:
                    try:
                        await dst.close()
                    except Exception:
                        pass

            await asyncio.gather(
                forward(client_ws, target_ws, "client→vless"),
                forward(target_ws, client_ws, "vless→client"),
            )

    except websockets.exceptions.ConnectionClosed as e:
        logging.info(f"🔌 اتصال مغلق: {e}")
    except Exception as e:
        logging.error(f"❌ خطأ: {e}")
    finally:
        logging.info(f"👋 انتهى الاتصال من {client_ip}")


async def health_check(reader, writer):
    """نقطة /health للتحقق من أن السيرفر يعمل"""
    try:
        data = await asyncio.wait_for(reader.read(1024), timeout=5)
        request = data.decode(errors="ignore")
        if "GET /health" in request or "GET /" in request:
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 2\r\n"
                "\r\n"
                "OK"
            )
            writer.write(response.encode())
            await writer.drain()
    except Exception:
        pass
    finally:
        writer.close()


async def smart_handler(reader, writer):
    """يحدد إذا الاتصال WebSocket أو HTTP عادي"""
    try:
        data = await asyncio.wait_for(reader.read(4096), timeout=10)
        if not data:
            writer.close()
            return

        request = data.decode(errors="ignore")

        # إذا WebSocket Upgrade — وجّه للـ VLESS
        if "Upgrade: websocket" in request or "upgrade: websocket" in request:
            # أعد البيانات للـ WebSocket handler
            # نستخدم websockets server مباشرة
            writer.close()
            return

        # HTTP عادي — ارجع OK
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html\r\n"
            "Content-Length: 50\r\n"
            "\r\n"
            "<html><body><h1>Server Running ✅</h1></body></html>"
        )
        writer.write(response.encode())
        await writer.drain()
    except Exception as e:
        logging.debug(f"smart_handler: {e}")
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def main():
    logging.info("═" * 50)
    logging.info("🚀 VLESS WebSocket Proxy يعمل!")
    logging.info(f"📡 يستمع على: {LISTEN_HOST}:{LISTEN_PORT}")
    logging.info(f"🎯 الهدف: {TARGET_WS}")
    logging.info(f"🔒 SNI: {SNI_HOST}")
    logging.info("═" * 50)

    # تشغيل WebSocket server
    ws_server = await websockets.serve(
        handle_ws,
        LISTEN_HOST,
        LISTEN_PORT,
        ping_interval=30,
        ping_timeout=20,
        max_size=10 * 1024 * 1024,  # 10MB
        compression=None,
    )

    logging.info(f"✅ WebSocket Server جاهز على البورت {LISTEN_PORT}")

    await ws_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
