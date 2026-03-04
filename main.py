import asyncio
import socket
import ssl
import os

LISTEN_PORT  = int(os.environ.get("PORT", 8080))
TARGET_HOST  = "nl1.startvless.site"
TARGET_PORT  = 80

async def pipe(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass

async def handle(client_r, client_w):
    try:
        target_r, target_w = await asyncio.open_connection(
            TARGET_HOST, TARGET_PORT
        )
        await asyncio.gather(
            pipe(client_r, target_w),
            pipe(target_r, client_w),
        )
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            client_w.close()
        except Exception:
            pass

async def main():
    server = await asyncio.start_server(
        handle, "0.0.0.0", LISTEN_PORT
    )
    print(f"✅ TCP Proxy running on port {LISTEN_PORT}")
    print(f"🎯 Forwarding to {TARGET_HOST}:{TARGET_PORT}")
    async with server:
        await server.serve_forever()

asyncio.run(main())
