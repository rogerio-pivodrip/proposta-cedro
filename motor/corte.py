"""Cortes -> barras de estoque.

O desenho lista pedacos ("TUBO PVC PBA 160 CL 10 - 1.5M"), mas a compra e por
barra inteira. Sem esta conversao a lista pede um codigo que nao existe no
estoque, ou pede metragem a menos.
"""
import math


def planejar(cortes_mm, barra_mm, perda_corte_mm=0):
    """First-fit decreasing: quantas barras e como cada uma fica dividida.

    Devolve {'barras': n, 'planos': [[corte, corte, ...]], 'sobra_mm': x,
             'aproveitamento': 0-1}
    """
    pecas = sorted((c for c in cortes_mm if c > 0), reverse=True)
    if not pecas:
        return {"barras": 0, "planos": [], "sobra_mm": 0, "aproveitamento": 0.0}
    if max(pecas) > barra_mm:
        raise ValueError(
            f"corte de {max(pecas)}mm nao cabe na barra de {barra_mm}mm"
        )

    planos, livres = [], []
    for peca in pecas:
        for i, livre in enumerate(livres):
            if peca + perda_corte_mm <= livre:
                planos[i].append(peca)
                livres[i] = livre - peca - perda_corte_mm
                break
        else:
            planos.append([peca])
            livres.append(barra_mm - peca - perda_corte_mm)

    usado = sum(pecas)
    total = len(planos) * barra_mm
    return {
        "barras": len(planos),
        "planos": planos,
        "sobra_mm": total - usado,
        "aproveitamento": round(usado / total, 3),
    }


def barras_simples(cortes_mm, barra_mm):
    """Estimativa sem plano de corte - so para comparar com o planejar()."""
    return math.ceil(sum(cortes_mm) / barra_mm) if cortes_mm else 0
