import express from 'express';
import http from 'node:http';
import { WebSocketServer } from 'ws';
import { TikTokLiveConnection, WebcastEvent } from 'tiktok-live-connector';

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server, path: '/events' });
const PORT = process.env.PORT || 10000;
const USERNAME = (process.env.TIKTOK_USERNAME || '01zeus00').replace(/^@/, '');
const clients = new Set();
let liveConnection = null;
let retryTimer = null;
let connecting = false;
let state = 'starting';

function broadcast(payload) {
  const data = JSON.stringify(payload);
  for (const ws of clients) {
    if (ws.readyState === 1) ws.send(data);
  }
}
function status(text) {
  state = text;
  broadcast({ event: 'zeusStatus', data: { status: text, username: USERNAME } });
}
function getUser(data) {
  const user = data?.user || data?.sender || {};
  return {
    nickname: user.nickname || user.displayId || user.uniqueId || user.unique_id || '',
    uniqueId: user.uniqueId || user.unique_id || user.displayId || '',
    username: user.uniqueId || user.unique_id || ''
  };
}
function attachEvent(eventName, normalizedName, mapData = d => d) {
  const eventKey = WebcastEvent?.[eventName];
  if (!eventKey) return;
  liveConnection.on(eventKey, data => {
    try {
      broadcast({ event: normalizedName, data: { ...getUser(data), ...mapData(data) } });
    } catch (error) {
      console.error('Event mapping error:', normalizedName, error?.message || error);
    }
  });
}
async function connectToLive() {
  if (connecting) return;
  connecting = true;
  if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
  status('connecting');
  try {
    if (liveConnection) {
      try { liveConnection.disconnect(); } catch {}
    }
    liveConnection = new TikTokLiveConnection(USERNAME, {
      processInitialData: false,
      fetchRoomInfoOnConnect: true,
      enableExtendedGiftInfo: true
    });
    attachEvent('CHAT', 'chat', d => ({ comment: d.comment || d.text || '' }));
    attachEvent('GIFT', 'gift', d => ({ giftName: d.giftName || d.gift?.name || '', repeatCount: d.repeatCount || 1 }));
    attachEvent('LIKE', 'like', d => ({ likeCount: d.likeCount || d.count || 1, totalLikes: d.totalLikes || 0 }));
    attachEvent('MEMBER', 'member', d => ({ nickname: getUser(d).nickname }));
    attachEvent('ROOM_USER', 'roomUser', d => ({ viewerCount: d.viewerCount || d.userCount || 0 }));
    attachEvent('FOLLOW', 'follow');
    attachEvent('SHARE', 'share');
    attachEvent('SOCIAL', 'share');
    attachEvent('SUBSCRIBE', 'subscribe');
    await liveConnection.connect();
    status('connected');
    console.log('Connected to TikTok LIVE:', USERNAME);
    liveConnection.on(WebcastEvent.DISCONNECTED, () => {
      status('disconnected');
      scheduleReconnect();
    });
  } catch (error) {
    console.error('TikTok LIVE connection failed:', error?.message || error);
    status('waiting-live');
    scheduleReconnect();
  } finally {
    connecting = false;
  }
}
function scheduleReconnect() {
  if (retryTimer) return;
  retryTimer = setTimeout(() => {
    retryTimer = null;
    connectToLive();
  }, 60000);
}

app.get('/health', (_req, res) => res.json({ ok: true, service: 'zeus-ia-live', status: state, username: USERNAME }));
app.use(express.static('public'));
wss.on('connection', ws => {
  clients.add(ws);
  ws.send(JSON.stringify({ event: 'zeusStatus', data: { status: state, username: USERNAME } }));
  ws.on('close', () => clients.delete(ws));
});
server.listen(PORT, '0.0.0.0', () => {
  console.log('Zeus server listening on', PORT, 'for @' + USERNAME);
  connectToLive();
});
