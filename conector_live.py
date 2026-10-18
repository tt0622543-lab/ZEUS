import asyncio, json, logging, os
from aiohttp import web
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, DisconnectEvent, CommentEvent, GiftEvent

HOST="0.0.0.0"
PORT=int(os.getenv("PORT","10000"))
USERNAME=os.getenv("TIKTOK_USERNAME","01zeus00").strip().lstrip("@")
logging.basicConfig(level=logging.INFO)
sockets=set()
client=TikTokLiveClient(unique_id=USERNAME)

async def broadcast(payload):
    for ws in list(sockets):
        try: await ws.send_json(payload)
        except Exception: sockets.discard(ws)

async def home(request): return web.FileResponse("index.html")
async def health(request): return web.json_response({"ok": True, "service": "urna-do-povo"})
async def events_socket(request):
    ws=web.WebSocketResponse(heartbeat=25); await ws.prepare(request); sockets.add(ws)
    await ws.send_json({"type":"status","message":"Painel conectado; aguardando a LIVE"})
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.ERROR: break
    finally: sockets.discard(ws)
    return ws

@client.on(ConnectEvent)
async def connected(event):
    logging.info("Conectado à LIVE de @%s", USERNAME)
    await broadcast({"type":"status","message":"CONECTADO À LIVE"})
@client.on(DisconnectEvent)
async def disconnected(event):
    await broadcast({"type":"status","message":"LIVE DESCONECTADA"})
@client.on(CommentEvent)
async def comment(event):
    user=getattr(event.user,"nickname",None) or getattr(event.user,"unique_id",None) or "Participante"
    body=getattr(event,"comment","")
    await broadcast({"type":"comment","username":user,"comment":body})
@client.on(GiftEvent)
async def gift(event):
    gift=getattr(event,"gift",None)
    if gift is None: return
    if getattr(gift,"streakable",False) and getattr(event,"streaking",False): return
    user=getattr(event.user,"nickname",None) or getattr(event.user,"unique_id",None) or "Participante"
    name=getattr(gift,"name",None) or getattr(gift,"gift_name",None) or "Presente"
    qty=max(1,int(getattr(event,"repeat_count",1) or 1))
    await broadcast({"type":"gift","username":user,"giftName":name,"quantity":qty})

async def connect_loop():
    while True:
        try:
            await broadcast({"type":"status","message":"Painel no ar; verificando a LIVE de @"+USERNAME})
            await client.start()
        except Exception as e:
            logging.exception("Conector TikTok indisponível; o painel web continuará no ar.")
            await broadcast({"type":"status","message":"PAINEL NO AR — aguardando a LIVE de @"+USERNAME})
            try: await client.disconnect()
            except Exception: pass
        break

async def on_startup(app):
    app["live_task"]=asyncio.create_task(connect_loop())
async def on_cleanup(app):
    app["live_task"].cancel()
    try: await app["live_task"]
    except asyncio.CancelledError: pass
    try: await client.disconnect()
    except Exception: pass

def main():
    app=web.Application()
    app.router.add_get("/",home)
    app.router.add_get("/healthz",health)
    app.router.add_get("/live-events",events_socket)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    web.run_app(app,host=HOST,port=PORT)
if __name__=="__main__": main()
