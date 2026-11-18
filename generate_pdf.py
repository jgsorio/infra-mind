"""Gera docs/base_conhecimento_infra.pdf com casos fictícios de infraestrutura."""
from collections import OrderedDict
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from casos import APENDICE_COMANDOS, CASOS, GLOSSARIO

NAVY = colors.HexColor("#1f3a5f")
GRAY = colors.HexColor("#f2f4f7")
SEV_COR = {"Crítica": "#b00020", "Alta": "#e65100", "Média": "#f9a825", "Baixa": "#2e7d32"}

ss = getSampleStyleSheet()
TITLE = ParagraphStyle("title", parent=ss["Title"], fontSize=30, leading=36, textColor=NAVY, alignment=TA_CENTER)
SUB = ParagraphStyle("sub", parent=ss["Normal"], fontSize=14, leading=20, alignment=TA_CENTER, textColor=colors.HexColor("#555555"))
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=18, textColor=NAVY, spaceBefore=6, spaceAfter=10)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=13, textColor=NAVY, spaceAfter=4)
H3 = ParagraphStyle("h3", parent=ss["Heading3"], fontSize=10.5, textColor=NAVY, spaceBefore=8, spaceAfter=2)
BODY = ParagraphStyle("b", parent=ss["BodyText"], fontSize=10, leading=14)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=8.5, leading=11)
CODE = ParagraphStyle("c", parent=ss["Code"], fontSize=8.5, leading=11, leftIndent=6, backColor=GRAY, borderPadding=4)


def P(t, s=BODY):
    return Paragraph(t, s)


def page_deco(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(2 * cm, A4[1] - 1.2 * cm, "InfraMind - Base de Conhecimento de Troubleshooting")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        canvas.drawString(2 * cm, 1.2 * cm, "Documento fictício - uso interno")
        canvas.setStrokeColor(colors.lightgrey)
        canvas.line(2 * cm, A4[1] - 1.4 * cm, A4[0] - 2 * cm, A4[1] - 1.4 * cm)
    canvas.restoreState()


def table(data, widths, header=True, extra=None):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    t.setStyle(TableStyle(style + (extra or [])))
    return t


def cover():
    return [Spacer(1, 6 * cm), P("InfraMind", TITLE), Spacer(1, 0.4 * cm),
            P("Base de Conhecimento de Troubleshooting<br/>de Infraestrutura e Sistemas Operacionais", SUB),
            Spacer(1, 1.5 * cm),
            P(f"Versão 2.0 · {date.today():%d/%m/%Y}<br/>%d incidentes documentados" % len(CASOS), SUB),
            Spacer(1, 5 * cm),
            P("Documento fictício, criado para demonstração e testes do assistente InfraMind. "
              "Os casos, hosts e valores são ilustrativos. Valide qualquer comando antes de executar em produção.", SMALL),
            PageBreak()]


def intro():
    s = [P("1. Como usar este documento", H1),
         P("Este guia reúne incidentes recorrentes de infraestrutura. Cada caso segue a mesma estrutura para facilitar a consulta "
           "durante um plantão:", BODY), Spacer(1, 4)]
    campos = [("Impacto", "O que o problema afeta no negócio."), ("Sintomas", "Como o problema se manifesta."),
              ("Causa provável", "Origem mais comum do incidente."), ("Diagnóstico", "Comandos para confirmar a causa."),
              ("Solução", "Passos recomendados, em ordem."), ("Validação", "Como confirmar que o problema foi resolvido."),
              ("Prevenção", "Ações para evitar recorrência."), ("Escalonamento", "Quando e para quem escalar, com o tempo alvo.")]
    s.append(table([["Campo", "Descrição"]] + [[a, P(b, SMALL)] for a, b in campos], [3.5 * cm, 13.5 * cm]))
    s += [Spacer(1, 14), P("2. Política de severidade e escalonamento", H1)]
    sev = [["Severidade", "Definição", "Tempo de resposta", "Escalonamento"],
           ["Crítica", "Serviço essencial totalmente indisponível, risco de perda de dados ou incidente de segurança.", "15 min", "Gestor de plantão + Diretoria"],
           ["Alta", "Degradação grave ou indisponibilidade parcial de serviço importante.", "30 min", "Líder técnico da área"],
           ["Média", "Impacto limitado a um grupo de usuários ou com contorno disponível.", "2 horas", "Analista sênior"],
           ["Baixa", "Falha pontual sem impacto relevante no negócio.", "1 dia útil", "Fila normal de atendimento"]]
    sev = [sev[0]] + [[r[0], P(r[1], SMALL), r[2], P(r[3], SMALL)] for r in sev[1:]]
    extra = [("TEXTCOLOR", (0, i), (0, i), colors.HexColor(SEV_COR[sev[i][0]])) for i in range(1, 5)]
    extra += [("FONTNAME", (0, i), (0, i), "Helvetica-Bold") for i in range(1, 5)]
    s.append(table(sev, [2.3 * cm, 7.2 * cm, 2.8 * cm, 4.7 * cm], extra=extra))
    s += [Spacer(1, 14), P("3. Metodologia geral de troubleshooting", H1)]
    for i, t in enumerate(["<b>Definir o problema:</b> o que falha, desde quando e quem é afetado.",
                           "<b>Verificar mudanças recentes:</b> deploys, patches, alterações de rede ou configuração.",
                           "<b>Coletar evidências:</b> logs, métricas e mensagens de erro exatas.",
                           "<b>Formular hipóteses</b> e testar a mais provável com o menor risco.",
                           "<b>Aplicar a correção</b> e documentar o que foi feito.",
                           "<b>Validar</b> com o usuário e monitorar por um período.",
                           "<b>Registrar a causa raiz</b> e as ações preventivas."], 1):
        s.append(P(f"{i}. {t}"))
    s.append(PageBreak())
    return s


def index():
    s = [P("4. Índice de incidentes", H1)]
    rows = [["ID", "Título", "Categoria", "Severidade"]]
    extra = []
    for i, c in enumerate(CASOS, 1):
        rows.append([c["id"], P(escape(c["titulo"]), SMALL), P(c["cat"], SMALL), c["sev"]])
        extra += [("TEXTCOLOR", (3, i), (3, i), colors.HexColor(SEV_COR[c["sev"]])), ("FONTNAME", (3, i), (3, i), "Helvetica-Bold")]
    s.append(table(rows, [2.0 * cm, 9.0 * cm, 3.6 * cm, 2.4 * cm], extra=extra))
    s.append(PageBreak())
    return s


def caso(c):
    cor = SEV_COR[c["sev"]]
    head = Table([[P(f"<b>{c['id']} - {escape(c['titulo'])}</b>", ParagraphStyle("hh", parent=H2, textColor=colors.white, spaceAfter=0))]],
                 colWidths=[17 * cm])
    head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    meta = P(f"<b>Categoria:</b> {c['cat']} &nbsp;|&nbsp; <b>Severidade:</b> <font color='{cor}'><b>{c['sev']}</b></font> "
             f"&nbsp;|&nbsp; <b>Ambiente:</b> {escape(c['so'])}", SMALL)
    s = [KeepTogether([head, Spacer(1, 4), meta])]
    for rot, key in (("Impacto", "impacto"), ("Sintomas", "sintomas"), ("Causa provável", "causa")):
        s += [P(rot, H3), P(escape(c[key]))]
    s += [P("Diagnóstico (comandos)", H3), Preformatted("\n".join(c["diag"]), CODE), P("Solução recomendada", H3)]
    s += [P(f"{i}. {escape(x)}") for i, x in enumerate(c["solucao"], 1)]
    for rot, key in (("Validação", "validacao"), ("Prevenção", "prevencao"), ("Escalonamento", "escal")):
        s += [P(rot, H3), P(escape(c[key]))]
    s += [Spacer(1, 10)]
    return s


def casos_por_categoria():
    grupos = OrderedDict()
    for c in CASOS:
        grupos.setdefault(c["cat"], []).append(c)
    s = []
    for n, (cat, lista) in enumerate(grupos.items(), 1):
        s.append(P(f"5.{n} {cat}", H1))
        for c in lista:
            s += caso(c)
        s.append(PageBreak())
    return s


def apendices():
    s = [P("6. Apêndice A - Cheat sheet de comandos", H1)]
    for tit, cmds in APENDICE_COMANDOS:
        s += [P(tit, H3), Preformatted("\n".join(cmds), CODE)]
    s += [Spacer(1, 10), P("7. Apêndice B - Checklist pós-incidente", H1)]
    for item in ["Serviço restabelecido e validado com o usuário/solicitante.", "Causa raiz identificada e registrada.",
                 "Linha do tempo do incidente documentada (detecção, ação, resolução).",
                 "Ações preventivas abertas com responsável e prazo.", "Monitoramento e alertas revisados.",
                 "Base de conhecimento atualizada com o novo aprendizado.", "Comunicação final enviada às partes interessadas."]:
        s.append(P(f"[  ] {item}"))
    s += [Spacer(1, 10), P("8. Apêndice C - Glossário", H1)]
    s.append(table([["Termo", "Definição"]] + [[t, P(d, SMALL)] for t, d in GLOSSARIO], [3.5 * cm, 13.5 * cm]))
    return s


def build(path: Path) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm, title="Base de Conhecimento InfraMind", author="InfraMind")
    doc.build(cover() + intro() + index() + casos_por_categoria() + apendices(), onFirstPage=page_deco, onLaterPages=page_deco)


if __name__ == "__main__":
    out = Path(__file__).parent / "docs"
    out.mkdir(exist_ok=True)
    build(out / "base_conhecimento_infra.pdf")
    print("PDF gerado em", out / "base_conhecimento_infra.pdf")
