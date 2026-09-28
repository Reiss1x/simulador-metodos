"""
Etapa 2 - Simulador de filas em TANDEM (Fila 1 -> Fila 2)

Reaproveita a estrutura do simulador de fila simples, agora com:
  - classe Fila       (propriedades e procedimentos de manipulação)
  - classe Evento     (tipo + tempo; comparável pelo tempo)
  - classe Escalonador (fila de prioridade de eventos, via heapq)
  - eventos CHEGADA (externa -> Fila 1), PASSAGEM (Fila 1 -> Fila 2)
    e SAIDA (Fila 2 -> fora do sistema)

Uso:
  python simulador_tandem.py              (configuração padrão da validação)
  python simulador_tandem.py modelo.json  (configuração própria)
"""
import heapq

# ======================= GERADOR (Congruente Linear) =======================
a = 1664525
c = 1013904223
M = 2 ** 32
previous = 12345                 # semente
QTD_ALEATORIOS = 100000
count = QTD_ALEATORIOS           # números pseudoaleatórios restantes


def NextRandom():
    global previous, count
    previous = (a * previous + c) % M
    count -= 1
    return previous / M


def Uniforme(minimo, maximo):
    return minimo + (maximo - minimo) * NextRandom()


# ================================ CLASSES =================================
class Fila:
    def __init__(self, nome, servers, capacity, minService, maxService,
                 minArrival=None, maxArrival=None):
        self.nome = nome
        self.server = servers
        self.capacity = capacity
        self.minArrival = minArrival
        self.maxArrival = maxArrival
        self.minService = minService
        self.maxService = maxService
        self.customers = 0
        self.loss = 0
        self.times = [0.0] * (capacity + 1)

    # ---- procedimentos de manipulação das propriedades ----
    def Status(self):
        return self.customers

    def Capacity(self):
        return self.capacity

    def Servers(self):
        return self.server

    def Loss(self):
        self.loss += 1

    def In(self):
        self.customers += 1

    def Out(self):
        self.customers -= 1


CHEGADA, SAIDA, PASSAGEM = "CHEGADA", "SAIDA", "PASSAGEM"


class Evento:
    def __init__(self, tipo, tempo):
        self.tipo = tipo
        self.tempo = tempo

    def __lt__(self, outro):          # equivalente ao compareTo do Java
        return self.tempo < outro.tempo


class Escalonador:
    def __init__(self):
        self.eventos = []

    def agenda(self, tipo, tempo):
        heapq.heappush(self.eventos, Evento(tipo, tempo))

    def NextEvent(self):
        return heapq.heappop(self.eventos)

    def vazio(self):
        return len(self.eventos) == 0


# ============================ CONFIGURAÇÃO ================================
# Configuração padrão (validação da etapa):
#   Fila 1: G/G/2/3, chegadas 1..5, atendimento 4..5
#   Fila 2: G/G/1/5, atendimento 1..3
#   primeira chegada em 2,5 | 100.000 aleatórios | semente 12345
# Pode ser substituída por um arquivo JSON:  python simulador_tandem.py modelo.json
import sys, json

CONFIG = {
    "semente": 12345,
    "aleatorios": 100000,
    "primeira_chegada": 2.5,
    "fila1": {"servidores": 2, "capacidade": 3,
              "chegada_min": 1.0, "chegada_max": 5.0,
              "atendimento_min": 4.0, "atendimento_max": 5.0},
    "fila2": {"servidores": 1, "capacidade": 5,
              "atendimento_min": 1.0, "atendimento_max": 3.0},
}
if len(sys.argv) > 1:
    with open(sys.argv[1], encoding="utf-8") as f:
        CONFIG.update(json.load(f))

previous = CONFIG["semente"]
QTD_ALEATORIOS = CONFIG["aleatorios"]
count = QTD_ALEATORIOS
PRIMEIRA_CHEGADA = CONFIG["primeira_chegada"]

f1, f2 = CONFIG["fila1"], CONFIG["fila2"]
fila1 = Fila("Fila 1", f1["servidores"], f1["capacidade"],
             f1["atendimento_min"], f1["atendimento_max"],
             f1["chegada_min"], f1["chegada_max"])
fila2 = Fila("Fila 2", f2["servidores"], f2["capacidade"],
             f2["atendimento_min"], f2["atendimento_max"])

escalonador = Escalonador()
TempoGlobal = 0.0


# ======================= PROCEDIMENTOS DE SIMULAÇÃO =======================
def AcumulaTempo(evento):
    """Contabiliza o tempo decorrido no estado atual de AMBAS as filas."""
    global TempoGlobal
    delta = evento.tempo - TempoGlobal
    fila1.times[fila1.Status()] += delta
    fila2.times[fila2.Status()] += delta
    TempoGlobal = evento.tempo


def agenda_aleatorio(tipo, minimo, maximo):
    """Agenda um evento só se ainda houver números aleatórios disponíveis."""
    if count > 0:
        escalonador.agenda(tipo, TempoGlobal + Uniforme(minimo, maximo))


def CHEGADA_(evento):
    AcumulaTempo(evento)
    if fila1.Status() < fila1.Capacity():
        fila1.In()
        if fila1.Status() <= fila1.Servers():
            agenda_aleatorio(PASSAGEM, fila1.minService, fila1.maxService)
    else:
        fila1.Loss()
    agenda_aleatorio(CHEGADA, fila1.minArrival, fila1.maxArrival)


def PASSAGEM_(evento):
    AcumulaTempo(evento)
    fila1.Out()
    if fila1.Status() >= fila1.Servers():
        agenda_aleatorio(PASSAGEM, fila1.minService, fila1.maxService)
    if fila2.Status() < fila2.Capacity():
        fila2.In()
        if fila2.Status() <= fila2.Servers():
            agenda_aleatorio(SAIDA, fila2.minService, fila2.maxService)
    else:
        fila2.Loss()


def SAIDA_(evento):
    AcumulaTempo(evento)
    fila2.Out()
    if fila2.Status() >= fila2.Servers():
        agenda_aleatorio(SAIDA, fila2.minService, fila2.maxService)


def relatorio(fila):
    chegada = (f", chegadas {fila.minArrival}..{fila.maxArrival}"
               if fila.minArrival is not None else "")
    print(f"*** {fila.nome}: G/G/{fila.Servers()}/{fila.Capacity()}{chegada}, "
          f"atendimento {fila.minService}..{fila.maxService}")
    print("Estado   Tempo acumulado    Probabilidade")
    for i in range(fila.Capacity() + 1):
        print(f"{i:>6}   {fila.times[i]:>15.4f}   "
              f"{fila.times[i] / TempoGlobal * 100:>10.2f}%")
    print(f"Clientes perdidos: {fila.loss}\n")


# ================================== MAIN ==================================
def main():
    escalonador.agenda(CHEGADA, PRIMEIRA_CHEGADA)

    while count > 0 and not escalonador.vazio():
        evento = escalonador.NextEvent()
        if evento.tipo == CHEGADA:
            CHEGADA_(evento)
        elif evento.tipo == SAIDA:
            SAIDA_(evento)
        elif evento.tipo == PASSAGEM:
            PASSAGEM_(evento)

    print("=========== SIMULAÇÃO DE FILAS EM TANDEM ===========")
    print(f"Números aleatórios usados: {QTD_ALEATORIOS - count}")
    print(f"Semente: {CONFIG['semente']} | Primeira chegada: {PRIMEIRA_CHEGADA}\n")
    relatorio(fila1)
    relatorio(fila2)
    print(f"Tempo global de simulação: {TempoGlobal:.4f}")


if __name__ == "__main__":
    main()
