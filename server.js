import express from 'express';
import http from 'node:http';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {WebSocketServer} from 'ws';
import {TikTokLiveClient,EventType} from 'piratetok-live-js';
const dir=path.dirname(fileURLToPath(import.meta.url)),app=express(),server=http.createServer(app);
app.use(express.static(path.join(dir,'public')));
const wss=new WebSocketServer({server,path:'/events'}),PORT=process.env.PORT||10000,USERNAME=(process.env.TIKTOK_USERNAME||'01zeus00').replace(/^@/,'');
let status='starting',client=null,retry=null,connecting=false;const sockets=new Set();
function send(event,data={}){const msg=JSON.stringify({event,data});for(const ws of sockets)if(ws.readyState===1)ws.send(msg);}
function setStatus(s,message=''){status=s;send('status',{status:s,username:USERNAME,message});}
function user(d={}){const u=d.user||d.sender||{};return {nickname:u.nickname||u.displayId||u.uniqueId||u.unique_id||'',uniqueId:u.uniqueId||u.unique_id||''};}
function reconnectLater(){if(retry)return;retry=setTimeout(()=>{retry=null;connect();},45000);}
async function connect(){if(connecting)return;connecting=true;setStatus('connecting');try{
 if(client){try{client.disconnect()}catch{}}
 client=new TikTokLiveClient(USERNAME).maxRetries(10).staleTimeout(90000);
 client.on(EventType.gift,d=>{const g=d.gift||{};send('gift',{...user(d),giftName:g.name||d.giftName||d.name||'Presente',giftId:g.id||d.giftId||null,coins:Number(d.coins||d.coinCount||d.diamondCount||d.giftValue||g.diamondCount||g.coins||0),repeatCount:Number(d.repeatCount||1)});});
 client.on(EventType.chat,d=>send('chat',{...user(d),comment:d.content||d.comment||d.text||''}));
 client.on(EventType.like,d=>send('like',{...user(d),count:d.count||d.likeCount||1}));
 client.on(EventType.follow,d=>send('follow',user(d)));
 client.on(EventType.join,d=>send('member',user(d)));
 client.on(EventType.share,d=>send('share',user(d)));
 client.on(EventType.liveEnded,()=>{setStatus('waiting-live','A LIVE terminou; aguardando a próxima.');reconnectLater()});
 client.on('disconnected',()=>{setStatus('disconnected','Conexão interrompida; tentando novamente.');reconnectLater()});
 client.on('reconnecting',()=>setStatus('connecting','Reconectando ao TikTok LIVE...'));
 await client.connect();setStatus('connected','Conectado à LIVE pública.');
 }catch(e){console.error('TikTok:',e?.message||e);setStatus('waiting-live',e?.message||'Não foi possível conectar. Confira se a LIVE está pública.');reconnectLater()}finally{connecting=false}}
wss.on('connection',ws=>{sockets.add(ws);ws.send(JSON.stringify({event:'status',data:{status,username:USERNAME}}));ws.on('close',()=>sockets.delete(ws))});
app.get('/api/health',(q,r)=>r.json({ok:true,status,username:USERNAME}));
app.get('/api/config',(q,r)=>r.json({username:USERNAME}));
app.post('/api/reconnect',(q,r)=>{if(retry){clearTimeout(retry);retry=null}connect();r.json({ok:true})});
server.listen(PORT,'0.0.0.0',()=>{console.log('Sonho Live iniciado',PORT);connect()});