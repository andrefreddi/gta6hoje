#!/usr/bin/env python3
# Transforma qualquer imagem num reel 1080x1920 narrado: imagem inteira visivel sobre fundo desfocado + narracao (edge-tts) + marca.
# Uso: python scripts/reels_imagem.py imgvid01
import json, os, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VOZ = os.environ.get("TTS_VOZ", "pt-BR-AntonioNeural")

def run(c): subprocess.run(c, check=True)
def dur(p): return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p],
                                        capture_output=True, text=True).stdout.strip())

def main():
    nome = sys.argv[1] if len(sys.argv) > 1 else "imgvid01"
    itens = json.loads((ROOT/"conteudo"/f"{nome}.json").read_text(encoding="utf-8"))
    media = ROOT/"media"/f"img-{nome}"; media.mkdir(parents=True, exist_ok=True)
    work = ROOT/"_work_img"; work.mkdir(parents=True, exist_ok=True)
    fp = ROOT/"fila.json"; fila = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else []
    markfile = str(work/"mark.txt"); open(markfile,"w").write("@gta6.hoje")
    for it in itens:
        img = str(ROOT/"fontes"/it["img"])
        if not os.path.exists(img): sys.exit("falta imagem: "+img)
        mp3 = str(work/f"n{it['id']}.mp3")
        run(["edge-tts","--voice",VOZ,"--text",it["narracao"],"--write-media",mp3])
        d = min(max(dur(mp3)+0.8, 6), 45)
        rel = f"media/img-{nome}/{it['id']}.mp4"; out = str(ROOT/rel)
        vf = ("[0:v]split=2[a][b];"
              "[a]scale=1200:2133:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=24[bg];"
              "[b]scale=1030:1840:force_original_aspect_ratio=decrease[fg];"
              "[bg][fg]overlay=(W-w)/2:(H-h)/2,"
              f"drawtext=fontfile={FONT}:textfile={markfile}:fontcolor=white:fontsize=44:x=(w-text_w)/2:y=h-150:box=1:boxcolor=0xff2e88:boxborderw=22[v]")
        run(["ffmpeg","-y","-loglevel","error","-loop","1","-i",img,"-i",mp3,"-filter_complex",vf,
             "-map","[v]","-map","1:a","-t",str(d),"-c:v","libx264","-profile:v","high","-g","30","-crf","20",
             "-pix_fmt","yuv420p","-c:a","aac","-ar","48000","-b:a","128k","-movflags","+faststart",out])
        fila.append({"lote":f"img-{nome}","id":it["id"],"tipo":"reel","arquivo":rel,"legenda":it["legenda"],"publicado":False})
        print("ok", it["id"], round(d,1))
    fp.write_text(json.dumps(fila, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("pendentes:", sum(1 for x in fila if not x["publicado"]))

if __name__ == "__main__":
    main()
