import subprocess
subprocess.run(['.venv/bin/pip', 'install', 'reportlab'], capture_output=True)

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Group
from reportlab.graphics import renderPDF
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
import os

OUTPUT_PATH = '/home/hakim/Crypto_AML/system_documentation.pdf'

NAVY   = colors.HexColor('#0d1b2e')
BLUE   = colors.HexColor('#1d4ed8')
LGRAY  = colors.HexColor('#f1f5f9')
MGRAY  = colors.HexColor('#e2e8f0')
DGRAY  = colors.HexColor('#64748b')
WHITE  = colors.white
BLACK  = colors.black
GREEN  = colors.HexColor('#166534')
GBG    = colors.HexColor('#dcfce7')

def build_styles():
    base = getSampleStyleSheet()
    styles = {}
    styles['title'] = ParagraphStyle('DocTitle', fontSize=28, textColor=NAVY,
        spaceAfter=10, spaceBefore=0, alignment=TA_CENTER, fontName='Helvetica-Bold', leading=34)
    styles['subtitle'] = ParagraphStyle('DocSubtitle', fontSize=14, textColor=BLUE,
        spaceAfter=6, spaceBefore=4, alignment=TA_CENTER, fontName='Helvetica', leading=18)
    styles['date'] = ParagraphStyle('DocDate', fontSize=11, textColor=DGRAY,
        spaceAfter=0, spaceBefore=4, alignment=TA_CENTER, fontName='Helvetica')
    styles['h1'] = ParagraphStyle('H1', fontSize=18, textColor=NAVY,
        spaceAfter=8, spaceBefore=18, fontName='Helvetica-Bold', leading=22,
        borderPad=4)
    styles['h2'] = ParagraphStyle('H2', fontSize=14, textColor=BLUE,
        spaceAfter=6, spaceBefore=12, fontName='Helvetica-Bold', leading=18)
    styles['h3'] = ParagraphStyle('H3', fontSize=12, textColor=NAVY,
        spaceAfter=4, spaceBefore=8, fontName='Helvetica-Bold', leading=15)
    styles['body'] = ParagraphStyle('Body', fontSize=10, textColor=BLACK,
        spaceAfter=6, spaceBefore=2, fontName='Helvetica', leading=14, alignment=TA_JUSTIFY)
    styles['bullet'] = ParagraphStyle('Bullet', fontSize=10, textColor=BLACK,
        spaceAfter=3, spaceBefore=1, fontName='Helvetica', leading=13,
        leftIndent=16, bulletIndent=4)
    styles['code'] = ParagraphStyle('Code', fontSize=8.5, textColor=NAVY,
        spaceAfter=4, spaceBefore=4, fontName='Courier', leading=12,
        leftIndent=12, backColor=LGRAY, borderPad=6)
    styles['table_header'] = ParagraphStyle('TH', fontSize=9, textColor=WHITE,
        fontName='Helvetica-Bold', alignment=TA_CENTER, leading=12)
    styles['table_cell'] = ParagraphStyle('TC', fontSize=9, textColor=BLACK,
        fontName='Helvetica', leading=12)
    styles['caption'] = ParagraphStyle('Caption', fontSize=9, textColor=DGRAY,
        spaceAfter=4, spaceBefore=2, fontName='Helvetica-Oblique', alignment=TA_CENTER)
    return styles

S = build_styles()

def hr():
    return HRFlowable(width='100%', thickness=1, color=MGRAY, spaceAfter=6, spaceBefore=6)

def h1(text):
    return Paragraph(text, S['h1'])

def h2(text):
    return Paragraph(text, S['h2'])

def h3(text):
    return Paragraph(text, S['h3'])

def body(text):
    return Paragraph(text, S['body'])

def bullet(text):
    return Paragraph(f'• {text}', S['bullet'])

def sp(h=6):
    return Spacer(1, h)

def code_block(text):
    lines = text.strip().split('\n')
    paras = []
    for line in lines:
        paras.append(Paragraph(line.replace(' ', '&nbsp;').replace('<', '&lt;').replace('>', '&gt;'), S['code']))
    return paras

