# Deploy e Configuração

## Estrutura de arquivos necessária

```
meu-projeto/
├── main.py            ← o código da API
├── requirements.txt
└── Procfile           ← instrução de inicialização para o Render
```

---

## requirements.txt

```
fastapi
uvicorn[standard]
httpx[http2]
pandas
```

---

## Procfile

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## Deploy no Render.com (gratuito)

1. Crie uma conta em https://render.com
2. Clique em **New → Web Service**
3. Conecte seu repositório GitHub com os 3 arquivos acima
4. Configure:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Clique em **Deploy**

Sua API estará disponível em algo como:
`https://seu-projeto.onrender.com`

> ⚠️ No plano gratuito do Render, a instância "dorme" após 15 min sem uso.
> O primeiro acesso do dia pode levar ~30s para acordar + tempo de coleta.
> Para ambiente de produção de governo, considere o plano pago ($7/mês) ou Azure.

---

## Código Power Query (Power BI)

No Power BI Desktop, crie uma **nova fonte de dados em branco** e cole este código M no editor avançado:

```powerquery
let
    Fonte = Web.Contents("https://seu-projeto.onrender.com/pld"),
    ConteudoCSV = Text.FromBinary(Fonte),
    CSV = Csv.Document(
        Text.ToBinary(ConteudoCSV, TextEncoding.Utf8),
        [
            Delimiter    = ";",
            Encoding     = TextEncoding.Utf8,
            QuoteStyle   = QuoteStyle.None,
            Columns      = null
        ]
    ),
    ComCabecalho = Table.PromoteHeaders(CSV, [PromoteAllScalars = true])
in
    ComCabecalho
```

Troque `https://seu-projeto.onrender.com` pela URL real da sua API.

---

## Endpoints disponíveis

| Endpoint      | Método | Descrição                                      |
|---------------|--------|------------------------------------------------|
| `/pld`        | GET    | Retorna CSV consolidado (use este no Power BI) |
| `/status`     | GET    | Verifica cache, última atualização e erros     |
| `/atualizar`  | GET    | Força recoleta imediata (ignora cache)         |
| `/docs`       | GET    | Documentação interativa automática (FastAPI)   |
| `/help`       | GET    | Interface de ajuda e apoio                     |

---

## Manutenção anual

No início de cada ano, edite o dicionário `RESOURCE_IDS_POR_ANO` em `main.py`:

```python
RESOURCE_IDS_POR_ANO: dict[int, str] = {
    # ... anos anteriores ...
    2027: "cole-aqui-o-novo-resource-id",
}
```

O novo ID pode ser encontrado acessando o dataset do ano correspondente em
https://dadosabertos.ccee.org.br e capturando o `resource_id` da URL da API.
```
