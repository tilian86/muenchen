#!/usr/bin/env python3
"""München-Runde: baut STATIONS/AUDIO_DUR in index.html aus texte.md, vertont Stationen (Edge-TTS)
und legt vor jeden Text ein Atmo-Bett (Glocken, Kapelle, Orgel, Wasser ...).
  python3 build.py            -> nur index.html
  python3 build.py 3 7        -> Stationen 3 und 7 neu vertonen + mischen + index.html
  python3 build.py all        -> alles vertonen + mischen
  python3 build.py mix        -> nur Atmo neu mischen (aus audio/raw), keine neue Sprachsynthese
  python3 build.py beds       -> Atmo-Betten neu aus den Quelldateien schneiden (ATMO_SRC)
  python3 build.py --check    -> gesprochene Fassung der Texte anzeigen (Zahlen in Worten)
Zahlen in texte.md als Ziffern; fuer die Sprachausgabe werden sie in Worte gewandelt.
Rohe Sprachdateien liegen in audio/raw/, fertige Mischung in audio/s{n}.mp3."""
import re,json,subprocess,sys,os
from num2words import num2words
TTS=['/Users/florian/Library/Python/3.9/bin/edge-tts','--voice','de-DE-SeraphinaMultilingualNeural','--rate=-5%']
MON='Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Jahrhundert|Todestag'
def w(n): return num2words(n,lang='de')
def year(n): return num2words(n,lang='de',to='year')
def spoken(t):
    t=re.sub(r'\b(\d{1,2})\.\s+(?='+MON+r')',lambda m:num2words(int(m.group(1)),lang='de',to='ordinal')+'n ',t)
    t=re.sub(r'\b(\d{1,3})\.(\d{3})\b',lambda m:m.group(1)+m.group(2),t)
    t=re.sub(r'\b(\d{4})er\b',lambda m:year(int(m.group(1)))+'er',t)
    t=re.sub(r'\b(\d+)([a-z])\b',lambda m:w(int(m.group(1)))+' '+m.group(2),t)
    t=re.sub(r'\d+',lambda m:year(int(m.group(0))) if 1000<=int(m.group(0))<=2099 else w(int(m.group(0))),t)
    return t
# ---------- Atmo ----------
ATMO_SRC=os.environ.get('ATMO_SRC','/private/tmp/claude-501/-Users-florian/20c2f456-7db0-4e8e-9683-25670593eae8/scratchpad/atmo')
SRC={ # key: (Quelldatei, Einstieg in Sekunden)  -- Lizenzen in audio/beds/credits.json
 'bells_big':('bells_big.ogg',60),'bells_mid':('bells_mid.ogg',60),'bells_small':('bells_small.ogg',60),
 'peter':('peter.ogg',3),'meistersinger':('meistersinger.ogg',0),'lohengrin':('lohengrin.ogg',0),
 'zither':('zither.ogg',0),'polka':('polka.ogg',0),'crowd':('crowd.wav',0),'market':('market.ogg',20),
 'mall':('mall.ogg',0),'river':('river.ogg',0),'street':('street.flac',120),'sunday':('sunday.flac',30),
 'organ_bach':('organ_bach.mp3',0),'organ_mend':('organ_mend.mp3',0)}
ATMO={0:('zither','m'),1:('bells_mid','a'),2:('peter','m'),3:('crowd','a'),4:('bells_small','a'),
 5:('polka','m'),6:('meistersinger','m'),7:('lohengrin','m'),8:('sunday','a'),9:('river','a'),
 10:('bells_small','a'),11:('bells_big','a'),12:('organ_bach','m'),13:('street','a'),14:('market','a'),
 15:('organ_mend','m'),16:None,17:('peter','m')}
LEVEL={'a':(0.7,0.28),'m':(0.5,0.2)}   # (Pegel Intro, Pegel unter der Stimme)
def bed(key,force=False):
    out=f'audio/beds/{key}.wav'
    if os.path.exists(out) and not force: return out
    f,off=SRC[key]; src=os.path.join(ATMO_SRC,f)
    if not os.path.exists(src): sys.exit(f'Atmo-Quelle fehlt: {src}')
    cmd=['ffmpeg','-y','-loglevel','error']
    cmd+=['-ss',str(off)] if off else ['-stream_loop','3']
    cmd+=['-i',src,'-t','45','-af','silenceremove=start_periods=1:start_threshold=-45dB,loudnorm=I=-23:TP=-2:LRA=11,aresample=44100,aformat=sample_fmts=s16:channel_layouts=stereo,atrim=0:32',out]
    subprocess.run(cmd,check=True); print('Bett',key,flush=True); return out
def mix(n):
    raw=f'audio/raw/s{n}.mp3'; out=f'audio/s{n}.mp3'
    if not os.path.exists(raw): print('kein raw fuer',n); return
    a=ATMO.get(int(n))
    if not a:
        subprocess.run(['ffmpeg','-y','-loglevel','error','-i',raw,'-af','aresample=44100,aformat=channel_layouts=stereo,adelay=1000|1000,apad=pad_dur=1','-c:a','libmp3lame','-b:a','64k','-ar','44100','-ac','2',out],check=True)
    else:
        key,kind=a; H,L=LEVEL[kind]; b=bed(key)
        vol=f"if(lt(t,4),{H},if(lt(t,5.5),{H}-(t-4)/1.5*({H}-{L}),{L}))"
        fg=(f"[0:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,adelay=4000|4000,apad=pad_dur=1[v];"
            f"[1:a]atrim=0:30,afade=t=in:st=0:d=0.8,volume='{vol}':eval=frame,afade=t=out:st=25:d=5[b];"
            f"[v][b]amix=inputs=2:duration=first:dropout_transition=0:normalize=0")
        subprocess.run(['ffmpeg','-y','-loglevel','error','-i',raw,'-i',b,'-filter_complex',fg,'-c:a','libmp3lame','-b:a','64k','-ar','44100','-ac','2',out],check=True)
    print('gemischt',n,flush=True)
# ---------- Texte ----------
T={}
parts=re.split(r'^## (\d+) .*$',open('texte.md',encoding='utf-8').read(),flags=re.M)
for i in range(1,len(parts),2): T[parts[i]]=parts[i+1].strip()
args=sys.argv[1:]
if args==['--check']:
    for n in T: print(f'--- {n}\n{spoken(T[n])}\n')
    sys.exit()
if args==['beds']:
    for k in SRC: bed(k,force=True)
    sys.exit()
if args==['mix']:
    for n in T: mix(n)
    args=[]
if args==['all']: args=list(T)
for n in args:
    txt=spoken(T[n]); open(f'audio/s{n}.txt','w').write(txt)
    subprocess.run(TTS+['--text',txt,'--write-media',f'audio/raw/s{n}.mp3'],check=True); print('vertont',n,flush=True)
    mix(n)
dur={}
for n in range(len(T)):
    f=f'audio/s{n}.mp3'
    if os.path.exists(f):
        d=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f],capture_output=True,text=True).stdout.strip()
        dur[n]=round(float(d))
    else: dur[n]=0
cred=json.load(open('images/credits.json')) if os.path.exists('images/credits.json') else {}
def c(k): return f"{cred[k]['artist']}, {cred[k]['license']}" if k in cred else ''
def bold(t,words):
    for x in words:
        if x not in t: print('WARN fett nicht gefunden:',x)
        t=t.replace(x,f'<strong>{x}</strong>',1)
    return t
S=[
 (1,'Marienplatz','Das Herz der Stadt · Start',48.13722,11.57550,'s1',['Heinrich der Löwe','Glockenspiel','9. November 1938']),
 (2,'Alter Peter','306 Stufen und eine Heilige',48.13660,11.57500,'s2',['306 Stufen','heilige Munditia','acht Zifferblätter']),
 (3,'Viktualienmarkt','Bier, Brezn und Karl Valentin',48.13510,11.57553,'s3',['1807','Karl Valentin','Weißwurst']),
 (4,'Alter Hof','Der Affe und der Kaiser',48.13790,11.57780,'s4',['Ludwig der Bayer','Affenturm','1347']),
 (5,'Hofbräuhaus','Das berühmteste Wirtshaus der Welt',48.13763,11.57997,'s5',['1589','Krupskaja','24. Februar 1920']),
 (6,'Nationaltheater','Ein Opernhaus, bezahlt mit Bier',48.13930,11.57820,'s6',['Bierpfennig','Richard Wagner','Cuvilliés-Theater']),
 (7,'Residenz','Löwen, Schätze, Märchenkönig',48.14030,11.57760,'s7',['Antiquarium','Ludwig der Zweite','Wintergarten']),
 (8,'Feldherrnhalle','Wo die Geschichte abbog',48.14167,11.57731,'s8',['9. November 1923','Viscardigasse','Drückebergergasserl']),
 (9,'Hofgarten','Tempel, Garten, Welle · Eisbach optional',48.14294,11.58000,'s9',['Dianatempel','Eisbachwelle','Englische Garten']),
 (10,'Theatinerkirche','Ein Gelübde in Gelb',48.14220,11.57705,'s10',['Henriette Adelaide','Max Emanuel','Otto von Griechenland']),
 (11,'Frauenkirche','Der Teufelstritt',48.13858,11.57359,'s11',['Susanna','1525','Teufelstritt']),
 (12,'St. Michael','Turm, Gruft, Märchenkönig',48.13892,11.57041,'s12',['1590','Ludwig der Zweite','Rupert Mayer']),
 (13,'Karlstor & Stachus','Der Platz mit zwei Namen',48.13940,11.56650,'s13',['Eustachius Föderl','Saal 253','Sophie Scholl']),
 (14,'Sendlinger Tor','Die Mordweihnacht',48.13346,11.56686,'s14',['1318','Sendlinger Mordweihnacht','Schmied von Kochel']),
 (15,'Asamkirche','Zwei Brüder bauen den Himmel · innen',48.13521,11.56952,'s15',['1733 bis 1746','Egid Quirin','Nepomuk']),
 (16,'Jakobsplatz','Ein Zelt aus Stein',48.13450,11.57266,'s16',['9. November 2006','Juni 1938','Gang der Erinnerung']),
 (17,'Rindermarkt','Kindl, Schmalznudel, Abschluss',48.13624,11.57343,'s17',['Ruffinihaus','Münchner Kindl','Café Frischhut']),
]
js=[]
for id_,name,sub,lat,lng,img,bw in S:
    t=bold(T[str(id_)],bw).replace('`','\\`').replace('\n\n','\n')
    js.append(f"{{id:{id_},name:'{name}',sub:'{sub}',lat:{lat},lng:{lng},img:'images/{img}.jpg',credit:'{c(img)}',\n text:`{t}`}}")
src=open('index.html',encoding='utf-8').read()
src=re.sub(r'const STATIONS=\[.*?\n\];',lambda m:'const STATIONS=[\n'+',\n'.join(js)+'\n];',src,flags=re.S)
src=re.sub(r'const AUDIO_DUR=\{[^}]*\};','const AUDIO_DUR='+json.dumps(dur,separators=(',',':'))+';',src)
src=re.sub(r'(<span class="audio-time" id="time-s0">)[^<]*',lambda m:m.group(1)+f'{dur[0]//60}:{dur[0]%60:02d}',src)
open('index.html','w',encoding='utf-8').write(src)
print('index.html ok',dur,'gesamt',sum(dur.values())//60,'min')
