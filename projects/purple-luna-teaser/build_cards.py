"""Render Purple Luna brand cards to 1080x1920 PNGs via headless Chromium.

Brand tokens are lifted verbatim from purple-luna-site/src/app/globals.css so the
cards match the live site rather than approximating it.
"""

import base64
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).parent
CARDS = ROOT / "cards"
CARDS.mkdir(exist_ok=True)
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

INK = "#1a0e2e"
CREAM = "#faf7f2"
PURPLE = "#8b5cf6"
PEACH = "#f4a261"

LOGO_B64 = base64.b64encode((ROOT / "logo.png").read_bytes()).decode()

BASE_CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..700;1,9..144,300..700&family=Geist:wght@300..600&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1080px; height:1920px; }}
body {{
  background: {INK};
  color: {CREAM};
  font-family: 'Geist', system-ui, sans-serif;
  display:flex; align-items:center; justify-content:center;
  overflow:hidden; position:relative;
}}
/* ambient aurora — mirrors the site hero's radial purple glows */
.aurora {{ position:absolute; inset:0; pointer-events:none; }}
.aurora::before {{
  content:''; position:absolute; width:1200px; height:1200px;
  top:-260px; left:-320px; border-radius:50%;
  background: radial-gradient(circle, rgba(139,92,246,0.28) 0%, rgba(139,92,246,0) 62%);
}}
.aurora::after {{
  content:''; position:absolute; width:1000px; height:1000px;
  bottom:-240px; right:-280px; border-radius:50%;
  background: radial-gradient(circle, rgba(244,162,97,0.16) 0%, rgba(244,162,97,0) 66%);
}}
.wrap {{ position:relative; z-index:2; width:100%; padding:0 110px; text-align:left; }}
.eyebrow {{
  font-size:30px; letter-spacing:.20em; text-transform:uppercase;
  color: rgba(250,247,242,0.55); margin-bottom:56px; font-weight:500;
}}
.dot {{
  display:inline-block; width:12px; height:12px; border-radius:50%;
  background:{PURPLE}; margin-right:20px; vertical-align:middle;
}}
h1 {{
  font-family:'Fraunces', Georgia, serif; font-weight:400;
  font-size:104px; line-height:1.08; letter-spacing:-0.02em;
}}
h1 .accent {{ font-style:italic; color:{CREAM}; position:relative; white-space:nowrap; }}
h1 .accent::after {{
  content:''; position:absolute; left:0; right:0; bottom:6px; height:6px;
  background:{PEACH}; border-radius:3px; opacity:.95;
}}
.sub {{ margin-top:52px; font-size:40px; line-height:1.45; color:rgba(250,247,242,0.66); font-weight:300; max-width:820px; }}
/* stats card */
.stats {{ display:flex; flex-direction:column; gap:78px; }}
.stat .big {{ font-family:'Fraunces', Georgia, serif; font-size:132px; line-height:1; letter-spacing:-0.03em; }}
.stat .big.accent {{ color:{PEACH}; }}
.stat .label {{ margin-top:20px; font-size:34px; line-height:1.4; color:rgba(250,247,242,0.62); font-weight:300; max-width:780px; }}
.rule {{ width:132px; height:5px; background:{PURPLE}; border-radius:3px; margin-bottom:56px; }}
/* end card */
.end {{ text-align:center; width:100%; }}
.end img {{ width:660px; height:auto; display:block; margin:0 auto; }}
.end .url {{ margin-top:64px; font-size:44px; letter-spacing:.06em; color:rgba(250,247,242,0.78); font-weight:400; }}
.end .place {{ margin-top:28px; font-size:30px; letter-spacing:.16em; text-transform:uppercase; color:rgba(250,247,242,0.42); }}
"""

def page(body: str) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{BASE_CSS}</style></head><body><div class='aurora'></div>{body}</body></html>"


CARD_BODIES = [
    # 1 — hook
    page("""<div class='wrap'>
      <div class='eyebrow'><span class='dot'></span>Salons · Barbers · Clinics · Studios</div>
      <h1>Your hands are full.<br>The phone rings.</h1>
      <div class='sub'>You can&rsquo;t stop mid&#8209;blow&#8209;dry to answer it.</div>
    </div>"""),
    # 2 — the cost
    page("""<div class='wrap'>
      <div class='rule'></div>
      <h1>So that booking<br><span class='accent'>walks out</span><br>the door.</h1>
    </div>"""),
    # 3 — the answer
    page("""<div class='wrap'>
      <div class='eyebrow'><span class='dot'></span>Meet Luna</div>
      <h1>She answers your<br>WhatsApp in<br><span class='accent'>seconds</span>.</h1>
      <div class='sub'>Your prices. Your hours. Your services. She books them while they&rsquo;re still interested.</div>
    </div>"""),
    # 4 — the honest numbers (verbatim from HonestNumbers.tsx)
    page("""<div class='wrap'>
      <div class='eyebrow'><span class='dot'></span>The honest version</div>
      <div class='stats'>
        <div class='stat'><div class='big'>24/7</div><div class='label'>She never clocks off. 2pm or 2am, weekends and bank holidays included.</div></div>
        <div class='stat'><div class='big'>Seconds</div><div class='label'>Not hours. Not tomorrow. While the enquiry is still warm.</div></div>
        <div class='stat'><div class='big accent'>&pound;0</div><div class='label'>Commission. Every booking stays 100% yours.</div></div>
      </div>
    </div>"""),
    # 5 — end card
    page(f"""<div class='wrap'><div class='end'>
      <img src='data:image/png;base64,{LOGO_B64}' alt='Purple Luna'>
      <div class='url'>purpleluna.co.uk</div>
      <div class='place'>A small studio in Brighton</div>
    </div></div>"""),
]

for i, html in enumerate(CARD_BODIES, start=1):
    src = CARDS / f"card{i}.html"
    out = CARDS / f"card{i}.png"
    src.write_text(html, encoding="utf-8")
    subprocess.run(
        [
            CHROME, "--headless", "--disable-gpu", "--no-sandbox",
            "--hide-scrollbars", "--force-device-scale-factor=1",
            "--default-background-color=1a0e2e",
            "--virtual-time-budget=8000",
            f"--screenshot={out}", "--window-size=1080,1920",
            f"file://{src}",
        ],
        check=True, capture_output=True,
    )
    print(f"rendered {out.name}")
