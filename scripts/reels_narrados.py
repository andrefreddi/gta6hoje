#!/usr/bin/env python3
# Gera reels 1080x1920 com movimento (Ken Burns) + legenda, em 2 versoes: COM narracao (edge-tts) e SEM.
# Uso: python scripts/reels_narrados.py reels01
import json, os, re, subprocess, sys, textwrap, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VOZ = os.environ.get("TTS_VOZ", "pt-BR-AntonioNeural")

def run(cmd): subprocess.run(cmd, check=True)
def dur_of(path):
    return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","csv=p=0",path], capture_output=True, text=True).stdout.strip())

def build(image, capfile, markfile, dur, audio_in, audio_map, out):
    fps = 30; frames = int(dur*fps)
    vf = (
        "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
        f"zoompan=z='min(zoom+0.0006,1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={fps},"
        "drawbox=x=0:y=150:w=1080:h=230:color=black@0.55:t=fill,"
        f"drawtext=fontfile={FONT}:textfile={capfile}:fontcolor=white:fontsize=62:x=(w-text_w)/2:y=205:line_spacing=12,"
        f"drawtext=fontfile={FONT}:textfile={markfile}:fontcolor=white:fontsize=44:x=(w-text_w)/2:y=h-150:box=1:boxcolor=0xff2e88:boxborderw=22"
    )
    cmd = ["ffmpeg","-y","-loglevel","error","-loop","1","-i",image] + audio_in + [
        "-vf",vf,"-t",str(dur),"-c:v","libx264","-profile:v","high","-g","30","-crf","20",
        "-pix_fmt","yuv420p","-c:a","aac","-ar","48000","-b:a","128k","-movflags","+faststart"]
    cmd += audio_map + [out]
    run(cmd)

def main():
    nome = sys.argv[1] if len(sys.argv) > 1 else "reels01"
    itens = json.loads((ROOT/"conteudo"/f"{nome}.json").read_text(encoding="utf-8"))
    media = ROOT/"media"/f"reels-{nome}"; media.mkdir(parents=True, exist_ok=True)
    work = ROOT/"_work_reels"; work.mkdir(parents=True, exist_ok=True)
    fila_path = ROOT/"fila.json"
    fila = json.loads(fila_path.read_text(encoding="utf-8")) if fila_path.exists() else []

    for it in itens:
        img = str(ROOT/"fontes"/it["img"])
        if not os.path.exists(img): sys.exit("imagem nao existe: "+img)
        cap = "\n".join(textwrap.wrap(it["caption"], width=20))
        capfile = str(work/f"cap{it['id']}.txt"); open(capfile,"w").write(cap)
        markfile = str(work/"mark.txt"); open(markfile,"w").write("@gta6.hoje")

        # versao SEM narracao (8s, trilha silenciosa)
        rel_s = f"media/reels-{nome}/{it['id']}_sem.mp4"
        build(img, capfile, markfile, 8,
              ["-f","lavfi","-i","anullsrc=r=48000:cl=stereo"], ["-map","0:v","-map","1:a","-shortest"],
              str(ROOT/rel_s))
        fila.append({"lote":f"reels-{nome}-sem","id":it["id"],"tipo":"reel",
                     "arquivo":rel_s,"legenda":it["legenda"],"publicado":False})
        print("ok sem narracao", it["id"])

        # versao COM narracao (edge-tts)
        mp3 = str(work/f"nar{it['id']}.mp3")
        run(["edge-tts","--voice",VOZ,"--text",it["narracao"],"--write-media",mp3])
        d = min(max(dur_of(mp3)+0.8, 6), 25)
        rel_n = f"media/reels-{nome}/{it['id']}_nar.mp4"
        build(img, capfile, markfile, d,
              ["-i",mp3], ["-map","0:v","-map","1:a","-shortest"], str(ROOT/rel_n))
        fila.append({"lote":f"reels-{nome}-nar","id":it["id"],"tipo":"reel",
                     "arquivo":rel_n,"legenda":it["legenda"],"publicado":False})
        print("ok com narracao", it["id"], round(d,1),"s")

    fila_path.write_text(json.dumps(fila, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("total na fila:", sum(1 for x in fila if not x["publicado"]), "pendentes")

if __name__ == "__main__":
    main()
