# Simulador de Redes de Filas — Instruções de Uso

Simulador orientado a eventos para **redes de filas com qualquer topologia**.
O modelo é lido de um arquivo `.yml` no mesmo estilo do simulador do módulo 3.

## Requisitos

- Python 3.8 ou superior. **Nenhuma biblioteca externa** (o `.yml` é lido por
  um leitor próprio, não precisa instalar PyYAML).

## Arquivos

| Arquivo | Descrição |
|---|---|
| `simulador_rede.py` | **Simulador da etapa 3** (rede genérica) |
| `modelo_rede.yml` | Modelo de validação da etapa 3 (3 filas com realimentação) |
| `resultados_rede.txt` | Saída da simulação de validação da etapa 3 |
| `modelo_tandem.yml` | Rede tandem da etapa 2, no formato .yml (para conferência) |
| `simulador_tandem.py`, `resultados_tandem.txt`, `modelo_exemplo.json` | Etapa 2 (filas em tandem) |
| `simulador.py`, `resultados_etapa1.txt` | Etapa 1 (fila simples) |
| `gerador.py`, `dispersao_gerador.png`, `numeros_gerados.csv` | Gerador de aleatórios e seu teste |

## Como executar

```
python simulador_rede.py modelo_rede.yml
```

Para salvar a saída: `python simulador_rede.py modelo_rede.yml > resultados.txt`

(No Windows, se `python` não for reconhecido, use `py` no lugar.)

## Formato do arquivo .yml

```yaml
!PARAMETERS

arrivals:            # filas que recebem clientes de fora e o tempo da 1ª chegada
   Q1: 2.0

queues:
   Q1:
      servers: 1
      minArrival: 2.0     # só para filas com chegada externa
      maxArrival: 4.0
      minService: 1.0
      maxService: 2.0
                          # sem "capacity" = capacidade infinita
   Q2:
      servers: 2
      capacity: 5
      minService: 4.0
      maxService: 6.0

network:             # roteamento: origem -> destino com probabilidade
-  source: Q1
   target: Q2
   probability: 0.2
# O que faltar para somar 1 em cada fila é SAÍDA do sistema.
# Também é possível usar um target que não seja uma fila (ex.: "exit").

rndnumbersPerSeed: 100000   # quantidade de aleatórios (critério de parada)
seeds:                      # uma simulação por semente
- 12345
```

- Com **várias sementes**, o simulador mostra o resultado de cada uma e, ao
  final, a **média** entre elas.
- Para exercícios feitos à mão, pode-se trocar `rndnumbersPerSeed`/`seeds` por
  uma lista fixa de aleatórios:
  ```yaml
  rndnumbers:
  - 0.5
  - 0.2
  - 0.9
  ```

## Saída

Para cada fila:
- tempo acumulado e probabilidade de cada estado (0..K; em fila infinita,
  até o maior estado alcançado);
- número de clientes perdidos;
- índices de desempenho: população média (N), vazão (X), utilização (U)
  e tempo de resposta (W = N / X).

Ao final: tempo global da simulação e quantidade de aleatórios usados.

## Funcionamento (resumo)

- **Gerador:** Congruente Linear `X = (a·X + c) mod M`, com a = 1664525,
  c = 1013904223, M = 2³². `NextRandom()` gera U(0,1), convertido para U(A,B)
  por `A + (B − A)·U`.
- **Parada:** a simulação termina assim que o último aleatório é usado.
- **Eventos** (escalonador = fila de prioridade ordenada pelo tempo):
  - `CHEGADA`: cliente de fora chega numa fila; agenda a próxima chegada.
  - `PASSAGEM`: cliente termina o atendimento numa fila e vai para outra.
  - `SAIDA`: cliente termina o atendimento e deixa o sistema.
- **Roteamento:** ao agendar o fim de um atendimento, **primeiro** sorteia-se
  (com um aleatório) o destino do cliente e **depois** o tempo de atendimento.
  Os destinos são testados em ordem crescente de probabilidade (o que sobrar
  é saída). Se só houver um destino com probabilidade 1, nenhum aleatório é
  gasto. Essa é a mesma regra do `simulator.jar` do professor.
- **Sementes x lista fixa:** se o `.yml` tiver `seeds`, a lista `rndnumbers`
  é ignorada (igual ao `simulator.jar`).
- **Perdas:** cliente que chega (de fora ou de outra fila) numa fila cheia é
  perdido e contado nessa fila.
- **Tempos por estado:** a cada evento, o tempo decorrido é somado ao estado
  atual de **todas** as filas; probabilidade = tempo do estado / tempo global.

## Conferência

Rodar `python simulador_rede.py modelo_tandem.yml` reproduz exatamente o
resultado da etapa 2 (`resultados_tandem.txt`), o que confirma que o simulador
genérico se comporta igual ao anterior nesse caso.

Comparação com o `simulator.jar` do professor
(`java -jar simulator.jar run modelo.yml`):
- com lista fixa (`rndnumbers`), os resultados são **idênticos**;
- trocando temporariamente o gerador pelo do professor (a = 25214903917,
  c = 11, M = 2⁴⁸), os resultados com sementes também são idênticos;
- com o gerador próprio, as probabilidades ficam muito próximas.
- Atenção: o `simulator.jar` mostra o tempo de cada estado **somado** entre
  as sementes e as perdas totais; aqui a seção "MÉDIA" divide ambos pelo
  número de sementes (as probabilidades são as mesmas).

> Os valores dependem da semente e da ordem de uso dos aleatórios; comparados
> com o simulador do módulo 3, as probabilidades devem ficar próximas, mas não
> idênticas.