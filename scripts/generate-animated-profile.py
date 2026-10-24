"""Generate the warm animated profile artwork. Requires fonttools and resvg-py.
The fonts are Cormorant Garamond and DM Sans, sourced from google/fonts (OFL).
All text is outlined; the published SVGs load no fonts, scripts, or external files.
"""
from pathlib import Path
import sys, urllib.request, json, html, io, re
sys.path.insert(0, str(Path('.design-deps').resolve()))
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
from PIL import Image
import resvg_py

ROOT = Path.cwd()
OUT = ROOT / 'motion-assets'
OUT.mkdir(exist_ok=True)
FONT_DIR = ROOT / '.design-fonts'
FONT_DIR.mkdir(exist_ok=True)
FONTS = {}
for name, file, axes in [
    ('serif', 'cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf', {'wght':600}),
    ('sans', 'dmsans/DMSans%5Bopsz,wght%5D.ttf', {'opsz':24, 'wght':400})]:
    p=FONT_DIR/(name+'.ttf')
    if not p.exists(): urllib.request.urlretrieve('https://raw.githubusercontent.com/google/fonts/main/ofl/'+file,p)
    FONTS[name]=instantiateVariableFont(TTFont(p),axes,inplace=True)

CREAM='#f6f0e2'; GREEN='#24483d'; RUST='#bd644c'; SAGE='#a7b39a'; INK='#40594b'; GOLD='#d9bd83'
manifest={}
GLYPHS={}

def width(text, size, face='sans'):
    f=FONTS[face]; glyphs=f.getGlyphSet(); cmap=f.getBestCmap()
    return sum(glyphs[cmap.get(ord(c),'.notdef')].width for c in text)*size/f['head'].unitsPerEm

def txt(text,x,y,size=28,face='sans',color=GREEN,maxw=None):
    if maxw and width(text,size,face)>maxw+1:
        raise ValueError(f'Text exceeds measure: {text} ({width(text,size,face):.1f} > {maxw})')
    f=FONTS[face]; glyphs=f.getGlyphSet(); cmap=f.getBestCmap(); s=size/f['head'].unitsPerEm
    cursor=0; parts=[]
    for c in text:
        glyph=cmap.get(ord(c),'.notdef'); key=f'g-{face}-{ord(c)}'
        if key not in GLYPHS:
            pen=SVGPathPen(glyphs); glyphs[glyph].draw(pen)
            GLYPHS[key]=pen.getCommands()
        parts.append(f'<use href="#{key}" x="{cursor}"/>')
        cursor+=glyphs[glyph].width
    return f'<g fill="{color}" transform="translate({x},{y}) scale({s},-{s})">'+''.join(parts)+'</g>'

def lines(text,x,y,maxw,size=28,gap=39,color=INK):
    result=''; line=''; count=0
    for word in text.split():
        candidate=(line+' '+word).strip()
        if line and width(candidate,size)>maxw:
            result+=txt(line,x,y+count*gap,size,color=color,maxw=maxw); count+=1; line=word
        else: line=candidate
    if line: result+=txt(line,x,y+count*gap,size,color=color,maxw=maxw); count+=1
    return result,count

def move(values,dur='9s',kind='translate',begin='0.01s'):
    return f'<animateTransform attributeName="transform" type="{kind}" values="{values}" dur="{dur}" begin="{begin}" repeatCount="indefinite" calcMode="spline" keyTimes="0;0.5;1" keySplines="0.42 0 0.58 1;0.42 0 0.58 1"/>'

def svg(w,h,title,body,bg=CREAM):
    keys=sorted(set(re.findall(r'href="#(g-[^"]+)"',body)))
    defs='<defs>'+''.join(f'<path id="{k}" d="{GLYPHS[k]}"/>' for k in keys)+'</defs>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="title"><title id="title">{html.escape(title)}</title>
<style>.still{{display:none}}@media(prefers-reduced-motion:reduce){{.moving{{display:none}}.still{{display:inline}}}}</style>
{defs}<rect width="{w}" height="{h}" rx="0" fill="{bg}"/>{body}</svg>'''

def rule(x,y,w,delay='0.01s'):
    return f'<path d="M{x} {y}h{w}" stroke="#d5c9af" stroke-width="1.5"/><path class="moving" d="M{x} {y}h40" stroke="{RUST}" stroke-width="2" stroke-dasharray="40" stroke-dashoffset="0"><animate attributeName="stroke-dashoffset" values="40;0" dur="1.3s" begin="{delay}" fill="freeze"/></path>'

def save(name,mobile,w,h,title,body,bg=CREAM):
    filename=name+('-mobile' if mobile else '')+'.svg'
    data=svg(w,h,title,body,bg)
    (OUT/filename).write_text(data,encoding='utf-8')
    manifest['assets/animated/'+filename]=data

def hero(mobile):
    w,h=(600,360) if mobile else (1200,350)
    if mobile:
        b=txt('Vivek Pillai',30,120,100,'serif',maxw=540)
        b+=txt('Backend & machine learning',34,184,28,maxw=532)
        b+=txt('engineer',34,225,28)
        b+=txt('Generative AI / Evaluation',34,287,24,color=INK)
        b+=txt('Computer vision',34,324,24,color=INK)
    else:
        b=txt('Vivek Pillai',46,182,166,'serif',maxw=1100)
        b+=txt('Backend & machine learning engineer',54,250,28,maxw=1092)
        b+=txt('Generative AI / Evaluation / Computer vision',54,299,23,color=INK)
    b+=rule(34 if mobile else 54,h-12,w-(68 if mobile else 108))
    save('hero',mobile,w,h,'Vivek Pillai — Backend and machine learning engineer',b)

def about(mobile):
    w,h=(600,370) if mobile else (1200,250); x=34 if mobile else 50
    b=txt('About',x,65,44,'serif',maxw=w-2*x)
    text='I build backend systems and machine learning applications, with a focus on generative AI, agent evaluation, and computer vision.'
    block,n=lines(text,x,118,w-2*x,28 if mobile else 29,42)
    b+=block
    b+=txt('Open to Backend and AI/ML opportunities.',x,h-44,23 if mobile else 25,maxw=w-2*x)
    b+=rule(x,h-23,w-2*x)
    save('about',mobile,w,h,text+' Open to Backend and AI/ML opportunities.',b)

def heading(mobile):
    w,h=(600,106) if mobile else (1200,106); x=34 if mobile else 50
    b=txt('Selected work',x,70,52,'serif',maxw=w-2*x)
    b+=rule(360 if mobile else 395,57,(w-34)-(360 if mobile else 395),'1s')
    save('work-heading',mobile,w,h,'Selected work — five projects',b)

PROJECTS=[
('qwen','Qwen 2.1 Image Studio','A diffusion image generation pipeline and creative workflow studio.','gwen-2.1-image-generation'),
('ethos','ETHOS AI Evaluator','Automated evaluation and benchmarking for intelligent systems.','ethos-ai-evaluator'),
('campus','CampusHub','Student collaboration and campus resource management.','CampusHub'),
('face','Face2Phase','Computer vision and biometric facial processing.','face2phase'),
('pastebin','Pastebin Lite','Lightweight paste and snippet sharing.','pastebin-lite')]

def project(mobile,idx,data):
    slug,title,desc,repo=data; w,h=(600,240) if mobile else (1200,176); x=34 if mobile else 50
    b=txt(title,x,68,44,'serif',maxw=w-2*x-30)
    block,n=lines(desc,x,118,w-2*x-(0 if mobile else 80),27,37)
    b+=block
    y=h-22
    b+=rule(x,y,w-2*x,str(.1+idx*.3)+'s')
    bx=w-62; by=55
    b+=f'<g transform="translate({bx},{by})"><g class="moving"><path d="M-12 0h24m-9-9 9 9-9 9" fill="none" stroke="{RUST}" stroke-width="2"/></g><path class="still" d="M-12 0h24m-9-9 9 9-9 9" fill="none" stroke="{RUST}" stroke-width="2"/></g>'
    save(slug,mobile,w,h,title+' — '+desc+' Open repository.',b)

STACK=[('Machine learning','Python · PyTorch · Hugging Face · Diffusers · Ollama · OpenCV'),('Backend','FastAPI · Node.js · PostgreSQL · Docker'),('Frontend','TypeScript · JavaScript · React · Next.js · Tailwind CSS · Vite')]
def stack(mobile):
    w,h=(600,520) if mobile else (1200,390); x=34 if mobile else 50
    b=txt('Tools I work with',x,70,52,'serif',maxw=w-2*x); y=128
    for name,tools in STACK:
        b+=txt(name,x,y,26,color=GREEN)
        block,n=lines(tools,x,y+39,w-2*x,25 if mobile else 27,38)
        b+=block; y+=75+(n-1)*38+(30 if mobile else 0)
    if y>h: raise ValueError('Stack content exceeds panel')
    b+=rule(x,h-22,w-2*x,'0.5s')
    save('toolkit',mobile,w,h,'Tools: '+'. '.join(a+': '+b for a,b in STACK),b)

def footer(mobile):
    w,h=(600,240) if mobile else (1200,200); x=34 if mobile else 50
    b=txt('Say hello.',x,80,50 if mobile else 60,'serif',color=CREAM,maxw=w-2*x)
    if mobile:
        b+=txt(' ',x,138,50,'serif',color=CREAM)
    else:
        b=txt('Say hello.',x,93,66,'serif',color=CREAM,maxw=w-2*x)
    b+=txt('pillaivivek200@gmail.com',x,h-45,24,color=CREAM)
    b+=f'<g transform="translate({w-100},{h-53})"><path d="M0 0h32m-10-10 10 10-10 10" stroke="{GOLD}" fill="none" stroke-width="2.5"/><g class="moving"><circle cx="50" cy="0" r="3.5" fill="{GOLD}"/>{move("0 0;10 0;0 0","8s")}</g></g>'
    save('footer',mobile,w,h,'Let’s build something useful. Get in touch by email.',b,GREEN)

for mobile in [False,True]:
    hero(mobile); about(mobile); heading(mobile)
    for i,p in enumerate(PROJECTS): project(mobile,i,p)
    stack(mobile); footer(mobile)

manifest['scripts/generate-animated-profile.py']=Path(__file__).read_text(encoding='utf-8')
manifest['scripts/requirements-profile.txt']='fonttools\nresvg-py\nPillow\n'
manifest['assets/animated/README.md']='''# Animated profile artwork

Original SVG artwork for Vivek Pillai. Text stays visible while decorative motion runs through SMIL. Each panel has a separate mobile composition and a reduced-motion treatment.

Typography: Cormorant Garamond and DM Sans from https://github.com/google/fonts, licensed under the SIL Open Font License. Text is outlined; the SVGs make no external requests.

Inspiration: https://github.com/ryanpolasky/ryme.md and https://github.com/saroo98/profile-signal-kit. No artwork or code copied from these projects.

The cat is a separate actual GIF linked from GIPHY. GitHub controls the native repository cards and contribution graph outside the README.
'''
(ROOT/'motion-manifest.json').write_text(json.dumps(manifest),encoding='utf-8')

order=['hero','about','work-heading']+[p[0] for p in PROJECTS]+['toolkit','footer']
for mobile,screen in [(False,850),(True,360)]:
    imgs=[]
    for name in order:
        s=manifest['assets/animated/'+name+('-mobile' if mobile else '')+'.svg']
        im=Image.open(io.BytesIO(resvg_py.svg_to_bytes(svg_string=s))).convert('RGB')
        im=im.resize((screen,round(im.height*screen/im.width)),Image.Resampling.LANCZOS)
        imgs.append(im)
    canvas=Image.new('RGB',(screen,sum(i.height for i in imgs)+12*(len(imgs)-1)),CREAM)
    y=0
    for im in imgs: canvas.paste(im,(0,y)); y+=im.height+12
    canvas.save(ROOT/('motion-preview-mobile.png' if mobile else 'motion-preview-desktop.png'))
print(json.dumps({'assets':len(manifest),'svg_bytes':sum(len(s.encode()) for p,s in manifest.items() if p.endswith('.svg'))}))
