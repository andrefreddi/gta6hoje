// Gera posts (JPG 1080x1350) e reels (MP4 1080x1920) a partir de conteudo/<lote>.json e adiciona na fila.json.
// Roda no GitHub Actions (Linux: google-chrome + ffmpeg) ou local (CHROME/FFMPEG via env).
// Uso: node scripts/gera.mjs [lote ...]   (sem argumento: todos os lotes de conteudo/ ainda não gerados)
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CHROME = process.env.CHROME || (process.platform === 'win32'
  ? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe' : 'google-chrome');
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
const furl = p => pathToFileURL(p).href;
const esc = s => s.replaceAll('&', '&amp;').replaceAll('<', '&lt;');
const avatar = furl(path.join(ROOT, 'assets', 'avatar.jpg'));
const filaPath = path.join(ROOT, 'fila.json');
const fila = fs.existsSync(filaPath) ? JSON.parse(fs.readFileSync(filaPath, 'utf8')) : [];

function shot(html, out, w, h, transparent) {
  const f = out + '.html';
  fs.writeFileSync(f, html, 'utf8');
  const a = ['--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
    `--window-size=${w},${h}`, '--virtual-time-budget=3000', '--allow-file-access-from-files', `--screenshot=${out}`];
  if (transparent) a.push('--default-background-color=00000000');
  a.push(furl(f));
  try { execFileSync(CHROME, a, { stdio: 'ignore' }); } catch { /* chrome às vezes sai com código != 0 mesmo gerando */ }
  fs.rmSync(f, { force: true });
  if (!fs.existsSync(out)) throw new Error('falha ao renderizar ' + out);
}
const ff = a => execFileSync(FFMPEG, ['-y', '-loglevel', 'error', ...a], { stdio: 'inherit' });

let lotes = process.argv.slice(2);
if (!lotes.length) lotes = fs.readdirSync(path.join(ROOT, 'conteudo')).filter(f => f.endsWith('.json')).map(f => f.slice(0, -5))
  .filter(l => !fila.some(x => x.lote === l));

for (const lote of lotes) {
  const itens = JSON.parse(fs.readFileSync(path.join(ROOT, 'conteudo', lote + '.json'), 'utf8'));
  const out = path.join(ROOT, 'media', lote); fs.mkdirSync(out, { recursive: true });
  const tmp = fs.mkdtempSync(path.join(out, '_tmp'));
  for (const it of itens) {
    const img = path.join(ROOT, 'fontes', it.img);
    if (!fs.existsSync(img)) throw new Error('imagem não existe: ' + img);
    let rel;
    if (it.tipo === 'post') {
      const html = fs.readFileSync(path.join(ROOT, 'templates', 'post.html'), 'utf8')
        .replace('{{TEXTO}}', esc(it.texto)).replace('url(AVATAR)', `url("${avatar}")`).replace('url(IMAGEM)', `url("${furl(img)}")`);
      const png = path.join(tmp, it.id + '.png');
      shot(html, png, 1080, 1350);
      rel = `media/${lote}/${it.id}.jpg`;
      ff(['-i', png, '-q:v', '2', path.join(ROOT, rel)]);
    } else {
      const html = fs.readFileSync(path.join(ROOT, 'templates', 'reel.html'), 'utf8')
        .replace('{{TEXTO}}', esc(it.texto)).replace('url(AVATAR)', `url("${avatar}")`);
      const ov = path.join(tmp, it.id + '_ov.png');
      shot(html, ov, 1080, 1920, true);
      const dur = 8, fps = 30;
      rel = `media/${lote}/${it.id}.mp4`;
      const musica = it.trilha ? path.join(ROOT, 'audio', it.trilha) : null;
      const audioIn = musica && fs.existsSync(musica) ? ['-stream_loop', '-1', '-i', musica] : ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'];
      ff(['-loop', '1', '-i', img, '-i', ov, ...audioIn, '-filter_complex',
        `[0:v]scale=2160:1880:force_original_aspect_ratio=increase,crop=2160:1880,zoompan=z='min(zoom+0.0009,1.2)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${dur * fps}:s=1080x940:fps=${fps}[img];` +
        `color=c=0x0d0a12:s=1080x1920:d=${dur}:r=${fps}[bg];[bg][img]overlay=0:600[b1];[b1][1:v]overlay=0:0,format=yuv420p[v]`,
        '-map', '[v]', '-map', '2:a', '-t', String(dur), '-c:v', 'libx264', '-profile:v', 'high', '-g', '30', '-crf', '20',
        '-c:a', 'aac', '-ar', '48000', '-b:a', '128k', '-movflags', '+faststart', path.join(ROOT, rel)]);
    }
    const prev = fila.find(x => x.lote === lote && x.id === it.id);
    if (prev) Object.assign(prev, { tipo: it.tipo, arquivo: rel, legenda: it.legenda });
    else fila.push({ lote, id: it.id, tipo: it.tipo, arquivo: rel, legenda: it.legenda, publicado: false });
    console.log('ok', lote, it.id, it.tipo);
  }
  fs.rmSync(tmp, { recursive: true, force: true });
}
fs.writeFileSync(filaPath, JSON.stringify(fila, null, 2) + '\n', 'utf8');
console.log('fila:', fila.filter(x => !x.publicado).length, 'pendentes');
