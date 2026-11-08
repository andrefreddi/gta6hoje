#!/usr/bin/env python3
# Baixa um video (trailer oficial) e corta em N clipes verticais 9:16 com legenda + marca.
# Uso: python scripts/cortes.py "<url-ou-busca>" --n 6 --len 15 --prefixo trailer
import argparse, json, os, re, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media" / "cortes"
WORK = ROOT / "_work_cortes"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

GANCHOS = [
    "GTA 6 chega 19/11", "Isso e jogo ou vida real?", "Vice City voltou",
    "Prepara o coracao", "Faltam poucos dias", "Que cena e essa?",
    "A espera ta acabando", "Leonida te espera", "Pronto pra isso?",
]
LEGENDAS = [
    "Dia 19/11 o jogo mais esperado da decada chega. Ta pronto? Comenta 👇\n\n#gta6 #gtavi #gta6brasil #rockstargames #vicecity",
    "Isso rodando no PS5. Absurdo o nivel. Comenta o que achou 👇\n\n#gta6 #gtavi #gta6brasil #rockstargames #leonida",
    "Vice City ta de volta e mais viva que nunca. Qual sua parte favorita? 👇\n\n#gta6 #gtavi #vicecity #gta6brasil",
    "Contagem regressiva pro GTA 6. Salva e volta dia 19 🔖\n\n#gta6 #gtavi #gta6brasil #rockstargames",
]

def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)

def resolve_url(q):
    if re.match(r"https?://", q):
        return q
    # busca e prefere o canal oficial Rockstar Games
    out = subprocess.run(["yt-dlp", "--no-playlist", "--dump-json", f"ytsearch8:{q}"],
                         capture_output=True, text=True).stdout.strip().splitlines()
    cands = [json.loads(l) for l in out if l.strip()]
    for c in cands:
        ch = (c.get("channel") or c.get("uploader") or "").lower()
        if "rockstar" in ch:
            return c["webpage_url"]
    return cands[0]["webpage_url"] if cands else None

def scene_times(src, dur):
    # pega timestamps de troca de cena; fallback = pontos igualmente espacados
    r = subprocess.run(["ffmpeg", "-i", src, "-vf", "select='gt(scene,0.30)',showinfo",
                        "-f", "null", "-"], capture_output=True, text=True)
    ts = sorted(set(float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)))
    ts = [t for t in ts if 1.0 < t < dur - 4]
    return ts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--len", type=int, default=15)
    ap.add_argument("--prefixo", default="trailer")
    a = ap.parse_args()

    MEDIA.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    src = str(WORK / "src.mp4")

    # 1) prefere um arquivo ja no repo (fornecido manualmente): fontes/<query>.mp4 ou fontes/trailer.mp4
    local = None
    for cand in [ROOT / "fontes" / f"{a.query}.mp4", ROOT / "fontes" / "trailer.mp4"]:
        if cand.exists():
            local = cand; break
    if local:
        print("fonte local:", local)
        src = str(local)
    else:
        url = resolve_url(a.query)
        if not url:
            sys.exit("sem arquivo local e download indisponivel. coloque o trailer em fontes/trailer.mp4")
        print("fonte:", url)
        run(["yt-dlp", "--no-playlist", "-f", "mp4/bestvideo*+bestaudio/best",
             "--merge-output-format", "mp4", "-o", src, url])

    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip())
    cuts = scene_times(src, dur)
    if len(cuts) < a.n:
        step = max(1.0, (dur - a.len) / max(1, a.n))
        cuts = sorted(set(cuts + [round(step * i + 1, 2) for i in range(a.n)]))
    # espalha as escolhas ao longo do video
    chosen, last = [], -999
    for t in cuts:
        if t - last >= a.len * 0.8 and t + a.len <= dur:
            chosen.append(t); last = t
        if len(chosen) >= a.n:
            break

    fila_path = ROOT / "fila.json"
    fila = json.loads(fila_path.read_text(encoding="utf-8")) if fila_path.exists() else []
    novos = 0
    for i, t in enumerate(chosen, 1):
        cid = f"{i:02d}"
        gancho = GANCHOS[(i - 1) % len(GANCHOS)].replace(":", "\\:").replace("'", "")
        capfile = str(WORK / f"cap{i}.txt"); open(capfile, "w").write(gancho)
        markfile = str(WORK / "mark.txt"); open(markfile, "w").write("@gta6.hoje")
        rel = f"media/cortes/{a.prefixo}_{cid}.mp4"
        out = str(ROOT / rel)
        vf = (
            "crop=ih*9/16:ih,scale=1080:1920,"
            f"drawbox=x=0:y=180:w=1080:h=200:color=black@0.55:t=fill,"
            f"drawtext=fontfile={FONT}:textfile={capfile}:fontcolor=white:fontsize=58:"
            "x=(w-text_w)/2:y=235:line_spacing=10,"
            f"drawtext=fontfile={FONT}:textfile={markfile}:fontcolor=white:fontsize=44:"
            "x=(w-text_w)/2:y=h-140:box=1:boxcolor=0xff2e88:boxborderw=22"
        )
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", src, "-t", str(a.len),
             "-vf", vf, "-c:v", "libx264", "-profile:v", "high", "-crf", "20", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out])
        fila.append({"lote": f"cortes-{a.prefixo}", "id": cid, "tipo": "reel",
                     "arquivo": rel, "legenda": LEGENDAS[(i - 1) % len(LEGENDAS)], "publicado": False})
        novos += 1
        print("clipe", rel, "de", round(t, 1), "s")
    fila_path.write_text(json.dumps(fila, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("novos clipes:", novos)

if __name__ == "__main__":
    main()
