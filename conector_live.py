import asyncio
import logging
import os
from aiohttp import web
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, DisconnectEvent, CommentEvent, GiftEvent

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "10000"))
USERNAME = os.getenv("TIKTOK_USERNAME", "01zeus00").strip().lstrip("@")
logging.basicConfig(level=logging.INFO)
sockets = set()
active_client = None
stopping = False


async def broadcast(payload):
    dead = []
    for ws in list(sockets):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        sockets.discard(ws)


async def home(request):
    return web.FileResponse("index.html")


async def health(request):
    return web.json_response({"ok": True, "service": "urna-do-povo"})


async def events_socket(request):
    ws = web.WebSocketResponse(heartbeat=25)
    await ws.prepare(request)
    sockets.add(ws)
    await ws.send_json({"type": "status", "message": "Painel conectado; aguardando a LIVE"})
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.ERROR:
                break
    finally:
        sockets.discard(ws)
    return ws


def make_client():
    client = TikTokLiveClient(unique_id=USERNAME)

    @client.on(ConnectEvent)
    async def connected(event):
        logging.info("Conectado à LIVE de @%s", USERNAME)
        await broadcast({"type": "status", "message": "CONECTADO À LIVE DE @" + USERNAME})

    @client.on(DisconnectEvent)
    async def disconnected(event):
        logging.warning("Desconectado da LIVE de @%s", USERNAME)
        await broadcast({"type": "status", "message": "LIVE DESCONECTADA — tentando reconectar"})

    @client.on(CommentEvent)
    async def comment(event):
        user_obj = getattr(event, "user", None)
        user = (getattr(user_obj, "nickname", None)
                or getattr(user_obj, "unique_id", None)
                or "Participante")
        body = getattr(event, "comment", "") or ""
        await broadcast({"type": "comment", "username": user, "comment": body})

    @client.on(GiftEvent)
    async def gift(event):
        gift_obj = getattr(event, "gift", None)
        if gift_obj is None:
            return
        # Streakable gifts may emit intermediate events; score only the final count.
        if getattr(gift_obj, "streakable", False) and getattr(event, "streaking", False):
            return
        user_obj = getattr(event, "user", None)
        user = (getattr(user_obj, "nickname", None)
                or getattr(user_obj, "unique_id", None)
                or "Participante")
        name = (getattr(gift_obj, "name", None)
                or getattr(gift_obj, "gift_name", None)
                or "Presente")
        try:
            qty = max(1, int(getattr(event, "repeat_count", 1) or 1))
        except (TypeError, ValueError):
            qty = 1
        await broadcast({"type": "gift", "username": user, "giftName": name, "quantity": qty})

    return client


async def connect_loop():
    global active_client
    delay = 15
    while not stopping:
        client = make_client()
        active_client = client
        try:
            await broadcast({"type": "status", "message": "Conectando à LIVE de @" + USERNAME})
            # start() blocks while the event connection is active. Each retry gets a new client.
            await client.start()
            delay = 15
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Conexão TikTok falhou; nova tentativa em %s segundos.", delay)
            await broadcast({"type": "status", "message": "PAINEL NO AR — reconectando à LIVE em " + str(delay) + "s"})
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
            if active_client is client:
                active_client = None
        if not stopping:
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)


async def on_startup(app):
    app["live_task"] = asyncio.create_task(connect_loop())


async def on_cleanup(app):
    global stopping
    stopping = True
    task = app.get("live_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    if active_client:
        try:
            await active_client.disconnect()
        except Exception:
            pass


def main():
    app = web.Application()
    app.router.add_get("/", home)
    app.router.add_get("/healthz", health)
    app.router.add_get("/live-events", events_socket)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    web.run_app(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
