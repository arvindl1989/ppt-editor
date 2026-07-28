"""
kone_deck_creator.py
=====================
Turns a deck SPEC (see kone_planner.py for how Claude produces it) into a finished,
on-brand, fully editable .pptx.

Architecture (what the user asked for):
  master Cover F  (RETAINED verbatim)         <- brand-approved intro
  -> generated body slides (this module)      <- the pretty part, native + editable
  master Outro "Thank you" (RETAINED verbatim)<- brand-approved outro

Body slides are added on the master's own "Blank" layout, so they inherit the master
theme + the top-right logo + footer automatically. Each body layout function is a
near-direct transcription of a slideLayout block in the kone-design skill's LAYOUTS.md;
geometry converts 1px -> 9525 EMU, font px -> pt*0.75.
"""
import os
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR

# ---------- paths (resolve relative to this skill; kone-design is a sibling skill) ----------
SKILL_DIR   = os.path.dirname(os.path.abspath(__file__))
KONE_DESIGN = os.environ.get("KONE_DESIGN_DIR") or os.path.join(SKILL_DIR, os.pardir, "kone-design")
MASTER      = os.path.join(KONE_DESIGN, "uploads", "master_ppt-1784774200983.pptx")
ASSET_DIR   = os.path.join(SKILL_DIR, "assets")          # bundled logo/tagline PNGs
PHOTO_DIR   = os.path.join(KONE_DESIGN, "assets", "photos")

INTRO_IDX, OUTRO_IDX = 1, 10            # Cover F, Outro "Thank you"

# ---------- unit + token bridge ----------
def X(px):  return Emu(int(round(px * 9525)))
def PT(px): return Pt(px * 0.75)
BLUE=RGBColor(0x14,0x50,0xF5); BLACK=RGBColor(0x14,0x14,0x14); WHITE=RGBColor(0xFF,0xFF,0xFF)
SAND=RGBColor(0xF3,0xEE,0xE6); GREY=RGBColor(0x72,0x72,0x72); HAIR=RGBColor(0xD0,0xD0,0xD0)
INTER="Inter"; INTER_SB="Inter SemiBold"; KINFO="KONE Information"
# type scale (px on the 1280 grid)
FS_DISPLAY,FS_H1,FS_H2,FS_H3=54,40,28,22
FS_BODY_LG,FS_BODY,FS_LABEL,FS_EY,FS_STAT=20,16,14,12,64

# ---------- text helpers ----------
def _tf(slide,x,y,w,h,anchor=MSO_ANCHOR.TOP):
    tb=slide.shapes.add_textbox(X(x),X(y),X(w),X(h)); tf=tb.text_frame
    tf.word_wrap=True; tf.vertical_anchor=anchor
    for m in("margin_left","margin_right","margin_top","margin_bottom"): setattr(tf,m,0)
    return tf
def _run(p,text,font,px,color,caps=False,bold=False):
    r=p.add_run(); r.text=text.upper() if caps else text
    f=r.font; f.name=font; f.size=PT(px); f.color.rgb=color; f.bold=bold; return r
def _bullets(tf,items,color=BLACK):
    for i,it in enumerate(items):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.space_after=Pt(8)
        _run(p,"—  ",INTER,FS_BODY,BLUE)          # blue marker (clean, not a • )
        _run(p,it,INTER,FS_BODY,color)

# ---------- BODY LAYOUT LIBRARY (ported from LAYOUTS.md) ----------
def section_divider(slide,spec):                  # slideLayout11
    tf=_tf(slide,45,110,600,24); _run(tf.paragraphs[0],spec.get("eyebrow",""),KINFO,FS_EY,BLUE,caps=True)
    tf=_tf(slide,45,150,900,430); _run(tf.paragraphs[0],spec["title"],INTER,FS_DISPLAY,BLACK)

def title_content(slide,spec):                    # slideLayout16
    tf=_tf(slide,45,91,917,104); _run(tf.paragraphs[0],spec["title"],INTER,FS_H1,BLACK)
    tf=_tf(slide,45,227,917,402); _bullets(tf,spec["bullets"])

def two_content(slide,spec):                      # slideLayout20
    tf=_tf(slide,45,91,1189,104); _run(tf.paragraphs[0],spec["title"],INTER,FS_H1,BLACK)
    for x,col in zip((45,657),spec["columns"]):
        tf=_tf(slide,x,227,578,402)
        _run(tf.paragraphs[0],col["heading"],INTER_SB,FS_H3,BLACK,bold=True)
        b=tf.add_paragraph(); b.space_before=Pt(10)
        for j,it in enumerate(col["bullets"]):
            p=b if j==0 else tf.add_paragraph(); p.space_after=Pt(8)
            _run(p,"—  ",INTER,FS_BODY,BLUE); _run(p,it,INTER,FS_BODY,BLACK)

def three_stats(slide,spec):                      # slideLayout49 (body variant)
    tf=_tf(slide,46,92,985,180); _run(tf.paragraphs[0],spec["title"],INTER,FS_H1,BLACK)
    for x,st in zip((46,453,861),spec["stats"]):
        tf=_tf(slide,x,364,374,265)
        _run(tf.paragraphs[0],st["label"],KINFO,FS_LABEL,BLUE,caps=True)
        p=tf.add_paragraph(); p.space_before=Pt(6); _run(p,st["value"],INTER,FS_STAT,BLACK)
        p=tf.add_paragraph(); p.space_before=Pt(10); _run(p,st["desc"],INTER,FS_BODY,GREY)

def roadmap(slide,spec):                          # 3-content grid + timeline axis
    tf=_tf(slide,45,60,700,20); _run(tf.paragraphs[0],spec.get("eyebrow",""),KINFO,FS_EY,BLUE,caps=True)
    tf=_tf(slide,45,86,1000,60); _run(tf.paragraphs[0],spec["title"],INTER,FS_H1,BLACK)
    phases=spec["phases"]; n=len(phases); MARGIN,GUT,RIGHT=45,34,1235
    colw=(RIGHT-MARGIN-(n-1)*GUT)/n; cols=[MARGIN+i*(colw+GUT) for i in range(n)]; ay=300
    ln=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,X(cols[0]+7),X(ay),X(cols[-1]+7),X(ay))
    ln.line.color.rgb=HAIR; ln.line.width=Pt(1)
    for cx,ph in zip(cols,phases):
        d=slide.shapes.add_shape(MSO_SHAPE.OVAL,X(cx),X(ay-7),X(14),X(14))
        d.fill.solid(); d.fill.fore_color.rgb=BLUE; d.line.fill.background(); d.shadow.inherit=False
        tf=_tf(slide,cx,324,colw,34); _run(tf.paragraphs[0],ph["year"],KINFO,24,BLUE,caps=True)
        tf=_tf(slide,cx,366,colw,70); _run(tf.paragraphs[0],ph["title"],INTER_SB,FS_H3,BLACK,bold=True)
        tf=_tf(slide,cx,440,colw,160); _run(tf.paragraphs[0],ph["desc"],INTER,FS_BODY,GREY)

def quote(slide,spec):                            # slideLayout40
    panel=slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,X(453),X(136),X(782),X(493))
    panel.fill.solid(); panel.fill.fore_color.rgb=BLUE; panel.line.fill.background(); panel.shadow.inherit=False
    tf=_tf(slide,45,136,272,104); _run(tf.paragraphs[0],spec.get("label","QUOTE"),KINFO,FS_LABEL,BLACK,caps=True)
    tf=_tf(slide,510,212,657,349,anchor=MSO_ANCHOR.MIDDLE)
    _run(tf.paragraphs[0],"\u201c"+spec["quote"]+"\u201d",INTER,FS_H2,WHITE)
    tf=_tf(slide,510,561,657,40); _run(tf.paragraphs[0],spec["attribution"],KINFO,FS_LABEL,WHITE,caps=True)

REGISTRY={"section_divider":section_divider,"title_content":title_content,
          "two_content":two_content,"three_stats":three_stats,
          "roadmap":roadmap,"quote":quote}

# ---------- intro/outro text fill (retain design, update copy) ----------
def _set_title(slide,text):
    # target the title placeholder (idx 0), whatever it's named; add a run if empty
    tgt=next((sh for sh in slide.shapes if sh.is_placeholder and sh.placeholder_format.idx==0), None)
    if tgt is None or not tgt.has_text_frame: return False
    p=tgt.text_frame.paragraphs[0]
    if p.runs:
        p.runs[0].text=text
        for r in p.runs[1:]: r.text=""
    else:
        p.add_run().text=text        # inherits Inter + cover styling from the master layout
    return True

# ---------- assembler ----------
from pptx.oxml.ns import qn
def build_deck(spec, out_path):
    prs=Presentation(MASTER)
    lst=prs.slides._sldIdLst
    originals=list(lst)
    intro, outro = originals[INTRO_IDX], originals[OUTRO_IDX]
    # retain intro design, set its title from the spec
    if spec.get("title"): _set_title(list(prs.slides)[INTRO_IDX], spec["title"])
    # generate body on the master's Blank layout (inherits logo + footer)
    blank=next(l for l in prs.slide_layouts if l.name.strip().lower()=="blank")
    for s in spec["slides"]:
        slide=prs.slides.add_slide(blank)
        REGISTRY[s["layout"]](slide, s)
    body=[el for el in list(lst) if el not in originals]
    # drop the master's other example slides (unreference them), keep intro+body+outro
    keep={id(intro),id(outro),*(id(b) for b in body)}
    for el in originals:
        if id(el) not in keep:
            prs.part.drop_rel(el.get(qn('r:id'))); lst.remove(el)
    # reorder: intro, body..., outro
    for el in list(lst): lst.remove(el)
    lst.append(intro); [lst.append(b) for b in body]; lst.append(outro)
    prs.save(out_path)
    return out_path

if __name__=="__main__":
    import json,sys
    spec=json.load(open(sys.argv[1]))
    print("built:", build_deck(spec, sys.argv[2]))
