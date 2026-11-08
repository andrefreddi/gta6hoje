// Publica o próximo item da fila no Instagram via API oficial (Instagram API with Instagram Login).
// Env: IG_TOKEN (obrigatório), IG_USER_ID (opcional, descobre via /me), MEDIA_BASE_URL (ex: https://usuario.github.io/gta6hoje)
// Uso: node scripts/publica.mjs [--id lote02/03] [--dry-run]
import { readFileSync, writeFileSync } from 'node:fs';

const TOKEN = process.env.IG_TOKEN;
// token EAA... (usuário do sistema, login unificado) usa graph.facebook.com; token IG... usa graph.instagram.com
const API = (TOKEN || '').startsWith('IG') ? 'https://graph.instagram.com/v27.0' : 'https://graph.facebook.com/v27.0';
const BASE = (process.env.MEDIA_BASE_URL || '').replace(/\/$/, '');
const FILA = new URL('../fila.json', import.meta.url);
const args = process.argv.slice(2);
const dry = args.includes('--dry-run');
const idArg = args.includes('--id') ? args[args.indexOf('--id') + 1] : null;

if (!TOKEN) throw new Error('IG_TOKEN ausente');
if (!BASE) throw new Error('MEDIA_BASE_URL ausente');

const sleep = ms => new Promise(r => setTimeout(r, ms));
async function api(method, path, params = {}) {
  const url = new URL(API + path);
  const body = new URLSearchParams({ ...params, access_token: TOKEN });
  const res = method === 'GET'
    ? await fetch(url + '?' + body)
    : await fetch(url, { method, body });
  const json = await res.json().catch(() => ({}));
  if (!res.ok || json.error) throw new Error(`${method} ${path}: ${res.status} ${JSON.stringify(json.error || json)}`);
  return json;
}

const fila = JSON.parse(readFileSync(FILA, 'utf8'));
const item = idArg ? fila.find(x => `${x.lote}/${x.id}` === idArg) : fila.find(x => !x.publicado);
if (!item) { console.log('fila vazia, nada a publicar'); process.exit(0); }

const mediaUrl = `${BASE}/${item.arquivo}`;
const head = await fetch(mediaUrl, { method: 'HEAD' });
if (!head.ok) throw new Error(`mídia não acessível publicamente: ${mediaUrl} (${head.status})`);
console.log(`item ${item.lote}/${item.id} (${item.tipo}) -> ${mediaUrl} [${head.headers.get('content-type')}]`);
if (dry) process.exit(0);

const me = process.env.IG_USER_ID || (await api('GET', '/me', { fields: 'user_id,username' })).user_id;

const params = { caption: item.legenda };
if (item.tipo === 'reel') Object.assign(params, { media_type: 'REELS', video_url: mediaUrl, share_to_feed: 'true' });
else params.image_url = mediaUrl;

const { id: container } = await api('POST', `/${me}/media`, params);
console.log('container', container);

// vídeo precisa processar; imagem normalmente já vem FINISHED
for (let i = 0; i < 20; i++) {
  const { status_code, status } = await api('GET', `/${container}`, { fields: 'status_code,status' });
  console.log('status', status_code, status || '');
  if (status_code === 'FINISHED') break;
  if (status_code === 'ERROR' || status_code === 'EXPIRED') throw new Error(`container ${status_code}: ${status}`);
  await sleep(15000);
}

const { id: mediaId } = await api('POST', `/${me}/media_publish`, { creation_id: container });
const { permalink } = await api('GET', `/${mediaId}`, { fields: 'permalink' }).catch(() => ({}));
console.log('PUBLICADO', mediaId, permalink || '');

Object.assign(item, { publicado: true, publicadoEm: new Date().toISOString(), mediaId, permalink: permalink || null });
writeFileSync(FILA, JSON.stringify(fila, null, 2) + '\n', 'utf8');
