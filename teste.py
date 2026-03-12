from curl_cffi import requests as curl_requests
from curl_cffi import __version__ as cffi_version
import time
import random

URL_TESTE = (
    "https://dadosabertos.ccee.org.br/api/3/action/datastore_search"
    "?resource_id=9e152b60-f75c-4219-bcee-6033d287e0ab&limit=1"
)

# Tenta do mais recente para o mais antigo até achar um suportado
TARGETS = ["chrome124", "chrome123", "chrome122", "chrome110", "chrome107", "chrome101", "chrome100"]

def encontrar_target():
    for t in TARGETS:
        try:
            with curl_requests.Session(impersonate=t) as s:
                s.get("https://httpbin.org/get", timeout=10)
            print(f"✅ Target suportado: {t}")
            return t
        except Exception as e:
            print(f"  ✗ {t} — {e}")
    return None

def aquecer_sessao(session):
    passos = [
        ("Home",     "https://dadosabertos.ccee.org.br/"),
        ("Datasets", "https://dadosabertos.ccee.org.br/dataset"),
        ("PLD",      "https://dadosabertos.ccee.org.br/dataset/pld_media_diaria"),
    ]
    for nome, url in passos:
        print(f"  → Visitando {nome}...", end=" ")
        try:
            r = session.get(url, timeout=15)
            print(f"HTTP {r.status_code}")
        except Exception as e:
            print(f"Erro: {e}")
        delay = random.uniform(4, 9)
        print(f"    Aguardando {delay:.1f}s...")
        time.sleep(delay)

print(f"curl_cffi versão: {cffi_version}")
print("\n=== Detectando target suportado ===")
target = encontrar_target()

if not target:
    print("\n❌ Nenhum target suportado encontrado.")
    print("Tente: pip install --upgrade curl_cffi")
else:
    print(f"\n=== Aquecendo sessão com {target} ===")
    with curl_requests.Session(impersonate=target) as session:
        aquecer_sessao(session)

        print("\n=== Testando endpoint da API ===")
        try:
            resp = session.get(URL_TESTE, timeout=30)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                registros = resp.json()["result"]["records"]
                print(f"✅ Sucesso! Registros retornados: {len(registros)}")
                print(f"   Primeiro registro: {registros[0]}")
            else:
                print(f"❌ Falhou. Resposta:")
                print(resp.text[:300])
        except Exception as e:
            print(f"❌ Exceção: {e}")