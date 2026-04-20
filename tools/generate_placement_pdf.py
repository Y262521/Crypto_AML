#!/usr/bin/env python3
"""Generate a concise white-background PDF with ER, clustering flow and placement trace figures.
Output: /home/hakim/Crypto_AML/placement_report.pdf
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
import os
import sys

OUT_PDF = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'placement_report.pdf')
TMP = '/tmp'

# Helper: draw simple ER diagram
def draw_er(path):
    fig, ax = plt.subplots(figsize=(8,4), dpi=150)
    ax.axis('off')
    boxes = [
        (0.05,0.6,'owner_list','id,full_name,...'),
        (0.35,0.6,'owner_list_addresses','address,owner_list_id,is_primary'),
        (0.65,0.6,'wallet_clusters','id,cluster_size,owner_id,label_status'),
        (0.05,0.1,'transactions','tx_hash,from_address,to_address,value_eth'),
        (0.35,0.1,'addresses','address,cluster_id,total_in,total_out'),
        (0.65,0.1,'cluster_evidence','cluster_id,heuristic,confidence'),
    ]
    for x,y,title,cols in boxes:
        ax.add_patch(Rectangle((x,y),0.25,0.25,fill=False,linewidth=1))
        ax.text(x+0.01,y+0.18,title,fontsize=9,weight='bold')
        ax.text(x+0.01,y+0.02,cols,fontsize=7)
    # arrows
    ax.annotate('', xy=(0.28,0.75), xytext=(0.35,0.75), arrowprops=dict(arrowstyle='->'))
    ax.annotate('', xy=(0.58,0.75), xytext=(0.65,0.75), arrowprops=dict(arrowstyle='->'))
    ax.annotate('', xy=(0.28,0.25), xytext=(0.35,0.25), arrowprops=dict(arrowstyle='->'))
    ax.annotate('', xy=(0.58,0.25), xytext=(0.65,0.25), arrowprops=dict(arrowstyle='->'))
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)

# Helper: clustering flow
def draw_clustering(path):
    fig, ax = plt.subplots(figsize=(8,3), dpi=150)
    ax.axis('off')
    steps = ['transactions','build_graph','heuristics (many)','evidence gating','union-find','clusters','persist']
    xs = [0.02 + i*0.14 for i in range(len(steps))]
    for x,step in zip(xs,steps):
        ax.add_patch(FancyBboxPatch((x,0.2),0.12,0.6,boxstyle='round,pad=0.02',ec='black'))
        ax.text(x+0.01,0.5,step,fontsize=7)
    for i in range(len(xs)-1):
        ax.annotate('', xy=(xs[i]+0.13,0.5), xytext=(xs[i+1],0.5), arrowprops=dict(arrowstyle='->'))
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)

# Helper: placement trace example
def draw_trace(path):
    fig, ax = plt.subplots(figsize=(8,3), dpi=150)
    ax.axis('off')
    # draw nodes vertically (origin at left)
    nodes = ['Downstream (suspicious)','...','Intermediate','Placement origin']
    ys = [0.8,0.6,0.4,0.2]
    for y,node in zip(ys,nodes):
        ax.add_patch(Rectangle((0.1,y-0.08),0.35,0.12,fill=False))
        ax.text(0.12,y-0.01,node,fontsize=8)
    # arrows pointing leftwards upstream
    ax.annotate('', xy=(0.1,0.75), xytext=(0.45,0.75), arrowprops=dict(arrowstyle='->'))
    ax.annotate('', xy=(0.1,0.55), xytext=(0.45,0.55), arrowprops=dict(arrowstyle='->'))
    ax.annotate('', xy=(0.1,0.35), xytext=(0.45,0.35), arrowprops=dict(arrowstyle='->'))
    # scoring legend
    ax.text(0.55,0.7,'Scoring (high level):',fontsize=8,weight='bold')
    ax.text(0.55,0.62,'behavior (40%) + graph position (40%) + temporal (20%)',fontsize=7)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def build_pdf(out_pdf):
    er = os.path.join(TMP,'er.png')
    cl = os.path.join(TMP,'clustering.png')
    tr = os.path.join(TMP,'trace.png')
    draw_er(er)
    draw_clustering(cl)
    draw_trace(tr)

    c = canvas.Canvas(out_pdf, pagesize=A4)
    w,h = A4
    margin = 20*mm
    text_x = margin
    y = h - margin

    c.setFont('Helvetica-Bold', 16)
    c.drawString(text_x, y, 'Placement & Clustering Report (concise)')
    y -= 12*mm

    c.setFont('Helvetica', 10)
    lines = [
        'This report summarizes the MariaDB schema, clustering design, labeling and placement detection.',
        'Files scanned: aml_pipeline clustering, analytics/placement, ETL loader, backend placement API.',
    ]
    for line in lines:
        c.drawString(text_x, y, line)
        y -= 6*mm

    # ER diagram
    y -= 4*mm
    c.setFont('Helvetica-Bold',11)
    c.drawString(text_x, y, 'Database ER (key tables & FKs)')
    y -= 6*mm
    img = ImageReader(er)
    iw, ih = img.getSize()
    aspect = ih/iw
    draw_w = w - 2*margin
    draw_h = draw_w * aspect
    c.drawImage(img, text_x, y-draw_h, width=draw_w, height=draw_h)
    y -= draw_h + 6*mm

    # clustering figure
    c.setFont('Helvetica-Bold',11)
    c.drawString(text_x, y, 'Clustering pipeline (flow)')
    y -= 6*mm
    img2 = ImageReader(cl)
    iw, ih = img2.getSize()
    aspect = ih/iw
    draw_h = (w - 2*margin) * aspect
    c.drawImage(img2, text_x, y-draw_h, width=draw_w, height=draw_h)
    y -= draw_h + 6*mm

    # placement trace
    c.setFont('Helvetica-Bold',11)
    c.drawString(text_x, y, 'Placement trace & scoring (example)')
    y -= 6*mm
    img3 = ImageReader(tr)
    iw, ih = img3.getSize()
    aspect = ih/iw
    draw_h = (w - 2*margin) * aspect
    c.drawImage(img3, text_x, y-draw_h, width=draw_w, height=draw_h)
    y -= draw_h + 6*mm

    # short appendix
    c.showPage()
    c.setFont('Helvetica-Bold', 12)
    c.drawString(text_x, h - margin, 'Appendix: Key tables & scoring (short)')
    c.setFont('Helvetica',9)
    y = h - margin - 10*mm
    appendix = [
        '- wallet_clusters: cluster id, cluster_size, owner_id, label_status',
        '- addresses: address, cluster_id, totals; maps addresses → clusters',
        '- owner_list & owner_list_addresses: registry for owner matching and relabeling',
        '- placement: behaviors → trace → placement_score (persisted in placement_* tables)',
    ]
    for line in appendix:
        c.drawString(text_x, y, line)
        y -= 6*mm
    c.save()
    print('WROTE', out_pdf)


if __name__ == '__main__':
    try:
        build_pdf(OUT_PDF)
    except Exception as e:
        print('ERROR', e)
        sys.exit(2)
