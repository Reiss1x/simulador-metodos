"""
Etapa 3 - Simulador de REDES DE FILAS com topologia genérica

Lê o modelo de um arquivo .yml (mesmo estilo do simulador do módulo 3)
e simula qualquer rede: filas com ou sem chegadas externas, capacidade
finita ou infinita, roteamento probabilístico (inclusive realimentação)
e saída do sistema.

Uso:
    python simulador_rede.py modelo.yml
    python simulador_rede.py modelo.yml > resultados.txt

Não precisa de bibliotecas externas (o .yml é lido por um parser próprio).
"""
import heapq
import sys


# =========================================================================
#  LEITOR DE YAML (subconjunto usado pelo simulador do módulo 3)
# =========================================================================
def _escalar(v):
    v = v.strip().strip('"').strip("'")
    for conv in (int, float):
        try:
            return conv(v)
        except ValueError:
            pass
    return v


def ler_yaml(caminho):
    linhas = []
    with open(caminho, encoding="utf-8") as f:
        for bruta in f:
            txt = bruta.split("#", 1)[0].rstrip().replace("\t", "    ")
            if not txt.strip() or txt.strip().startswith("!"):
                continue
            linhas.append([len(txt) - len(txt.lstrip()), txt.strip()])

    def bloco(i, ind):
        if linhas[i][1].startswith("-"):
            return lista(i, ind)
        return mapa(i, ind)

    def lista(i, ind):
        res = []
        while i < len(linhas) and linhas[i][0] == ind and linhas[i][1].startswith("-"):
            resto = linhas[i][1][1:]
            conteudo = resto.lstrip()
            if not conteudo:                         # "-" sozinho na linha
                v, i = bloco(i + 1, linhas[i + 1][0])
            elif ":" in conteudo and not conteudo.endswith("'"):
                linhas[i] = [ind + 1 + len(resto) - len(conteudo), conteudo]
                v, i = mapa(i, linhas[i][0])
            else:
                v, i = _escalar(conteudo), i + 1
            res.append(v)
        return res, i

    def mapa(i, ind):
        res = {}
        while i < len(linhas) and linhas[i][0] == ind and not linhas[i][1].startswith("-"):
            chave, _, valor = linhas[i][1].partition(":")
            chave, valor = chave.strip(), valor.strip()
            i += 1
            if valor:
                res[chave] = _escalar(valor)
            elif i < len(linhas) and (linhas[i][0] > ind or
                                      (linhas[i][0] == ind and linhas[i][1].startswith("-"))):
                res[chave], i = bloco(i, linhas[i][0])
            else:
                res[chave] = None
        return res, i

    return bloco(0, linhas[0][0])[0] if linhas else {}


# =========================================================================
#  GERADOR DE NÚMEROS PSEUDOALEATÓRIOS (Congruente Linear)
# =========================================================================
a = 1664525
c = 1013904223
M = 2 ** 32
previous = 0
count = 0                 # aleatórios restantes (critério de parada)
lista_fixa = None         # usada quando o .yml traz "rndnumbers"


def NextRandom():
    global previous, count
    count -= 1
    if lista_fixa is not None:
        return lista_fixa[len(lista_fixa) - count - 1]
    previous = (a * previous + c) % M
    return previous / M


def Uniforme(minimo, maximo):
    return minimo + (maximo - minimo) * NextRandom()


# =========================================================================
#  CLASSES
# =========================================================================
class Fila:
    def __init__(self, nome, cfg):
        self.nome = nome
        self.server = int(cfg.get("servers", 1))
        cap = cfg.get("capacity")
        self.capacity = int(cap) if cap not in (None, "", -1) else None  # None = infinita
        self.minArrival = cfg.get("minArrival")
        self.maxArrival = cfg.get("maxArrival")
        self.minService = float(cfg["minService"])
        self.maxService = float(cfg["maxService"])
        self.customers = 0
        self.loss = 0
        self.times = [0.0]
        self.rotas = []        # lista de (destino ou None=saída, probabilidade)

    def Status(self):   return self.customers
    def Capacity(self): return self.capacity
    def Servers(self):  return self.server
    def Loss(self):     self.loss += 1
    def In(self):       self.customers += 1
    def Out(self):      self.customers -= 1

    def temEspaco(self):
        return self.capacity is None or self.customers < self.capacity


CHEGADA, SAIDA, PASSAGEM = "CHEGADA", "SAIDA", "PASSAGEM"


class Evento:
    _seq = 0

    def __init__(self, tipo, tempo, origem=None, destino=None):
        self.tipo, self.tempo = tipo, tempo
        self.origem, self.destino = origem, destino
        Evento._seq += 1
        self.seq = Evento._seq             # desempate: ordem de agendamento

    def __lt__(self, outro):               # equivalente ao compareTo do Java
        return (self.tempo, self.seq) < (outro.tempo, outro.seq)


class Escalonador:
    def __init__(self):
        self.eventos = []

    def agenda(self, evento):
        heapq.heappush(self.eventos, evento)

    def NextEvent(self):
        return heapq.heappop(self.eventos)

    def vazio(self):
        return not self.eventos


# =========================================================================
#  ESTADO GLOBAL DA SIMULAÇÃO
# =========================================================================
filas = {}
escalonador = Escalonador()
TempoGlobal = 0.0


def AcumulaTempo(evento):
    """Soma o tempo decorrido ao estado atual de TODAS as filas."""
    global TempoGlobal
    delta = evento.tempo - TempoGlobal
    for f in filas.values():
        while len(f.times) <= f.Status():
            f.times.append(0.0)
        f.times[f.Status()] += delta
    TempoGlobal = evento.tempo


def Roteamento(fila):
    """Sorteia o destino de quem termina o atendimento (None = sai do sistema)."""
    if not fila.rotas:
        return None
    if len(fila.rotas) == 1 and fila.rotas[0][1] >= 1.0:
        return fila.rotas[0][0]            # destino certo: não gasta aleatório
    if count <= 0:
        return None                        # simulação já vai encerrar
    r, acum = NextRandom(), 0.0
    for destino, prob in fila.rotas:
        acum += prob
        if r < acum:
            return destino
    return None                            # probabilidade restante = saída


def AgendaFimAtendimento(fila):
    if count <= 0:
        return
    tempo = TempoGlobal + Uniforme(fila.minService, fila.maxService)
    destino = Roteamento(fila)
    if destino is None:
        escalonador.agenda(Evento(SAIDA, tempo, origem=fila))
    else:
        escalonador.agenda(Evento(PASSAGEM, tempo, origem=fila, destino=destino))


def EntraNaFila(fila):
    if fila.temEspaco():
        fila.In()
        if fila.Status() <= fila.Servers():
            AgendaFimAtendimento(fila)
    else:
        fila.Loss()


def CHEGADA_(evento):
    AcumulaTempo(evento)
    fila = evento.destino
    EntraNaFila(fila)
    if count > 0:
        escalonador.agenda(Evento(CHEGADA,
                                  TempoGlobal + Uniforme(fila.minArrival, fila.maxArrival),
                                  destino=fila))


def SAIDA_(evento):
    AcumulaTempo(evento)
    fila = evento.origem
    fila.Out()
    if fila.Status() >= fila.Servers():
        AgendaFimAtendimento(fila)


def PASSAGEM_(evento):
    AcumulaTempo(evento)
    origem, destino = evento.origem, evento.destino
    origem.Out()
    if origem.Status() >= origem.Servers():
        AgendaFimAtendimento(origem)
    EntraNaFila(destino)


# =========================================================================
#  CARGA DO MODELO E EXECUÇÃO
# =========================================================================
def carrega_modelo(modelo):
    global TempoGlobal
    filas.clear()
    escalonador.eventos.clear()
    TempoGlobal = 0.0
    for nome, cfg in modelo["queues"].items():
        filas[nome] = Fila(nome, cfg or {})
    for ligacao in modelo.get("network") or []:
        origem = filas[ligacao["source"]]
        alvo = ligacao["target"]
        destino = filas.get(alvo)          # alvo desconhecido = saída do sistema
        origem.rotas.append((destino, float(ligacao["probability"])))
    for nome, f in filas.items():
        soma = sum(p for _, p in f.rotas)
        if soma > 1.0 + 1e-9:
            sys.exit(f"Erro: probabilidades de roteamento da fila {nome} somam {soma} (> 1).")
    for nome, tempo in (modelo.get("arrivals") or {}).items():
        f = filas[nome]
        if f.minArrival is None or f.maxArrival is None:
            sys.exit(f"Erro: fila {nome} tem chegada externa mas não tem minArrival/maxArrival.")
        escalonador.agenda(Evento(CHEGADA, float(tempo), destino=f))


def simula(modelo, semente=None, qtd=None):
    global previous, count, lista_fixa
    carrega_modelo(modelo)
    if "rndnumbers" in modelo:
        lista_fixa = [float(x) for x in modelo["rndnumbers"]]
        count = len(lista_fixa)
    else:
        lista_fixa = None
        previous, count = int(semente), int(qtd)
    total = count

    while count > 0 and not escalonador.vazio():
        evento = escalonador.NextEvent()
        if evento.tipo == CHEGADA:
            CHEGADA_(evento)
        elif evento.tipo == SAIDA:
            SAIDA_(evento)
        elif evento.tipo == PASSAGEM:
            PASSAGEM_(evento)

    return {
        "usados": total - count,
        "tempo": TempoGlobal,
        "filas": {n: {"times": list(f.times), "loss": f.loss,
                      "servers": f.server, "capacity": f.capacity,
                      "minArrival": f.minArrival, "maxArrival": f.maxArrival,
                      "minService": f.minService, "maxService": f.maxService}
                  for n, f in filas.items()},
    }


# =========================================================================
#  RELATÓRIO
# =========================================================================
def fmt(x, casas=4):
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def relatorio(res, titulo):
    T = res["tempo"]
    print("=" * 62)
    print(titulo)
    print("=" * 62)
    for nome, f in res["filas"].items():
        cap = "" if f["capacity"] is None else f"/{f['capacity']}"
        cheg = (f", chegadas {f['minArrival']}..{f['maxArrival']}"
                if f["minArrival"] is not None else "")
        print(f"\n*** {nome}: G/G/{f['servers']}{cap}{cheg}, "
              f"atendimento {f['minService']}..{f['maxService']}")
        print(f"{'Estado':>8}  {'Tempo acumulado':>18}  {'Probabilidade':>14}")
        n_estados = len(f["times"]) if f["capacity"] is None else f["capacity"] + 1
        times = f["times"] + [0.0] * (n_estados - len(f["times"]))
        for i in range(n_estados):
            print(f"{i:>8}  {fmt(times[i]):>18}  {fmt(times[i] / T * 100, 2) + '%':>14}")
        print(f"Clientes perdidos: {f['loss']}")

        # Índices de desempenho
        ms = (f["minService"] + f["maxService"]) / 2
        P = [t / T for t in times]
        N = sum(i * p for i, p in enumerate(P))
        ocup = sum(min(i, f["servers"]) * p for i, p in enumerate(P))
        X = ocup / ms
        U = ocup / f["servers"]
        W = N / X if X > 0 else 0.0
        print(f"População média (N): {fmt(N)} | Vazão (X): {fmt(X)} clientes/min | "
              f"Utilização (U): {fmt(U * 100, 2)}% | Tempo de resposta (W): {fmt(W)} min")
    print(f"\nTempo global de simulação: {fmt(T)}")
    print(f"Números aleatórios usados: {res['usados']}\n")


def media(resultados):
    base = resultados[0]
    k = len(resultados)
    m = {"usados": base["usados"], "tempo": sum(r["tempo"] for r in resultados) / k,
         "filas": {}}
    for nome, f in base["filas"].items():
        n = max(len(r["filas"][nome]["times"]) for r in resultados)
        times = [sum((r["filas"][nome]["times"] + [0.0] * n)[i] for r in resultados) / k
                 for i in range(n)]
        m["filas"][nome] = dict(f, times=times,
                                loss=sum(r["filas"][nome]["loss"] for r in resultados) / k)
    return m


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: python simulador_rede.py modelo.yml")
    modelo = ler_yaml(sys.argv[1])

    if "rndnumbers" in modelo:
        relatorio(simula(modelo), "SIMULAÇÃO (lista fixa de aleatórios do .yml)")
        return

    sementes = modelo.get("seeds") or [12345]
    if not isinstance(sementes, list):
        sementes = [sementes]
    qtd = int(modelo.get("rndnumbersPerSeed", 100000))

    resultados = []
    for s in sementes:
        r = simula(modelo, s, qtd)
        resultados.append(r)
        relatorio(r, f"SIMULAÇÃO - semente {s} ({qtd} aleatórios)")
    if len(resultados) > 1:
        relatorio(media(resultados), f"MÉDIA DAS {len(resultados)} SEMENTES")


if __name__ == "__main__":
    main()
