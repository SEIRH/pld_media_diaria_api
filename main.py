# ==============================================================================
# API Intermediária CCEE — PLD Média Diária
# ------------------------------------------------------------------------------
# Hospedagem recomendada : Render.com (free tier)
# Consumo no Power BI    : Web.Contents no Power Query (retorna CSV)
# Cache                  : Em memória, expira a cada 24 horas
#
# MANUTENÇÃO ANUAL NECESSÁRIA:
#   Todo início de ano, adicionar o novo resource_id em RESOURCE_IDS_POR_ANO.
#   Os IDs são obtidos em: https://dadosabertos.ccee.org.br
# ==============================================================================

from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse, HTMLResponse
from curl_cffi import requests as curl_requests
import pandas as pd
import time
import random
import io
from datetime import datetime, timedelta

app = FastAPI(
    title="API CCEE - PLD Média Diária",
    description="Consolida dados de PLD médio diário da CCEE para consumo no Power BI.",
    version="1.0.0",
)

# ------------------------------------------------------------------------------
# ⚠️  ATUALIZAR ANUALMENTE — Adicionar o resource_id do novo ano aqui
# ------------------------------------------------------------------------------
RESOURCE_IDS_POR_ANO: dict[int, str] = {
    2021: "9e152b60-f75c-4219-bcee-6033d287e0ab",
    2022: "6ccbf348-66ca-4bb1-a329-f607761fdf11",
    2023: "f28d0cb3-1afa-4b55-bf90-71c68b28272a",
    2024: "ed66d3dd-1987-4460-9164-20e169ad36fc",
    2025: "8b81daa1-8155-4fe1-9ee3-e01beb42fcc8",
    2026: "3ca83769-de89-4dc5-84a7-0128167b594d",
}

LIMITE_REGISTROS = 10000

# ------------------------------------------------------------------------------
# Cache em memória
# ------------------------------------------------------------------------------
_cache: dict = {
    "csv_data": None,
    "expira_em": None,
    "ultima_atualizacao": None,
    "total_registros": 0,
    "anos_coletados": [],
    "erros": [],
}

CACHE_DURACAO_HORAS = 24


def _cache_valido() -> bool:
    return (
        _cache["csv_data"] is not None
        and _cache["expira_em"] is not None
        and datetime.now() < _cache["expira_em"]
    )


def _aquecer_sessao(session) -> None:
    """
    Simula navegação humana antes de chamar a API.
    curl_cffi replica o fingerprint TLS do Chrome, então o WAF não distingue
    esta sessão de um browser real.
    """
    passos = [
        "https://dadosabertos.ccee.org.br/",
        "https://dadosabertos.ccee.org.br/dataset",
        "https://dadosabertos.ccee.org.br/dataset/pld_media_diaria",
    ]
    for url in passos:
        try:
            session.get(url, timeout=15)
            time.sleep(random.uniform(4, 9))
        except Exception:
            pass


def _coletar_dados_ccee() -> None:
    """Faz o scraping de todos os anos e atualiza o cache."""
    todas_as_bases = []
    erros = []
    anos_coletados = []

    # impersonate="chrome124" replica o fingerprint TLS+HTTP2 do Chrome 124
    with curl_requests.Session(impersonate="chrome124") as session:

        _aquecer_sessao(session)

        for ano, resource_id in RESOURCE_IDS_POR_ANO.items():
            url = (
                f"https://dadosabertos.ccee.org.br/api/3/action/datastore_search"
                f"?resource_id={resource_id}&limit={LIMITE_REGISTROS}"
            )
            time.sleep(random.uniform(8, 18))
            try:
                resp = session.get(url, timeout=30)
                resp.raise_for_status()
                registros = resp.json()["result"]["records"]
                df_ano = pd.DataFrame(registros)
                df_ano["ano_referencia_api"] = ano
                todas_as_bases.append(df_ano)
                anos_coletados.append(ano)
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                erros.append({
                    "ano": ano,
                    "erro": f"HTTP {status}" if status else str(e),
                    "url": url,
                })

    if todas_as_bases:
        df_final = pd.concat(todas_as_bases, ignore_index=True)
        df_final.drop(columns=["_id"], errors="ignore", inplace=True)
        buf = io.StringIO()
        df_final.to_csv(buf, index=False, encoding="utf-8", sep=";")
        csv_str = buf.getvalue()
        total = len(df_final)
    else:
        csv_str = ""
        total = 0

    _cache["csv_data"] = csv_str
    _cache["expira_em"] = datetime.now() + timedelta(hours=CACHE_DURACAO_HORAS)
    _cache["ultima_atualizacao"] = datetime.now().isoformat()
    _cache["total_registros"] = total
    _cache["anos_coletados"] = anos_coletados
    _cache["erros"] = erros


# ------------------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------------------

@app.get(
    "/pld",
    response_class=PlainTextResponse,
    summary="Retorna CSV consolidado do PLD Médio Diário",
    description=(
        "Use este endpoint no Power BI via Web.Contents. "
        "Retorna um CSV com separador ';', codificado em UTF-8. "
        "Os dados são atualizados automaticamente a cada 24 horas."
    ),
)
def get_pld():
    if not _cache_valido():
        _coletar_dados_ccee()

    if not _cache["csv_data"]:
        return Response(
            content="Nenhum dado disponível. Verifique os logs.",
            status_code=503,
            media_type="text/plain",
        )

    return PlainTextResponse(
        content=_cache["csv_data"],
        media_type="text/plain; charset=utf-8",
    )


@app.get(
    "/filtrar",
    summary="Filtra os dados por coluna e valor",
    description=(
        "Parâmetros:\n"
        "- `coluna`: nome da coluna a filtrar (obrigatório)\n"
        "- `valor`: valor a buscar na coluna (obrigatório)\n"
        "- `colunas`: colunas a retornar, separadas por vírgula. Omita para retornar todas\n"
        "- `formato`: `csv` (padrão, faz download) ou `json`\n\n"
        "Exemplo: `/filtrar?coluna=SUBMERCADO&valor=NORDESTE&colunas=DIA,PLD_MEDIA_DIA&formato=csv`"
    ),
)
def filtrar(
    coluna: str,
    valor: str,
    colunas: str | None = None,
    formato: str = "csv",
):
    if not _cache_valido():
        _coletar_dados_ccee()

    if not _cache["csv_data"]:
        return Response(content="Nenhum dado disponível.", status_code=503)

    df = pd.read_csv(io.StringIO(_cache["csv_data"]), sep=";", dtype=str)

    if coluna not in df.columns:
        return Response(
            content=f"Coluna '{coluna}' não encontrada. Disponíveis: {', '.join(df.columns)}",
            status_code=400,
            media_type="text/plain",
        )

    df_filtrado = df[df[coluna].astype(str).str.strip() == str(valor).strip()]

    if colunas:
        cols = [c.strip() for c in colunas.split(",")]
        cols_invalidas = [c for c in cols if c not in df.columns]
        if cols_invalidas:
            return Response(
                content=f"Colunas inválidas: {', '.join(cols_invalidas)}. Disponíveis: {', '.join(df.columns)}",
                status_code=400,
                media_type="text/plain",
            )
        df_filtrado = df_filtrado[cols]

    if formato.lower() == "json":
        return df_filtrado.to_dict(orient="records")

    buf = io.StringIO()
    df_filtrado.to_csv(buf, index=False, sep=";")
    nome_arquivo = f"ccee_{coluna}_{valor}.csv".replace(" ", "_")
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )


@app.get("/colunas", summary="Lista as colunas disponíveis no dataset")
def get_colunas():
    if not _cache_valido():
        _coletar_dados_ccee()

    if not _cache["csv_data"]:
        return Response(content="Nenhum dado disponível.", status_code=503)

    df = pd.read_csv(io.StringIO(_cache["csv_data"]), sep=";", dtype=str, nrows=1)
    return {"colunas": list(df.columns)}


@app.get("/status", summary="Status do cache e da última coleta")
def get_status():
    return {
        "cache_valido": _cache_valido(),
        "ultima_atualizacao": _cache["ultima_atualizacao"],
        "expira_em": _cache["expira_em"].isoformat() if _cache["expira_em"] else None,
        "total_registros": _cache["total_registros"],
        "anos_coletados": _cache["anos_coletados"],
        "erros_na_ultima_coleta": _cache["erros"],
    }


@app.get("/atualizar", summary="Força recoleta imediata (ignora cache)")
def forcar_atualizacao():
    _coletar_dados_ccee()
    return {
        "mensagem": "Dados recoletados com sucesso.",
        "total_registros": _cache["total_registros"],
        "anos_coletados": _cache["anos_coletados"],
        "erros": _cache["erros"],
    }


@app.get("/help", response_class=HTMLResponse, include_in_schema=False)
def documentacao():
    with open("help.html", "r", encoding="utf-8") as f:

        return f.read()
