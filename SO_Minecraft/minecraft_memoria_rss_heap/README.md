# Projeto 2 — Minecraft: RSS e JVM Heap Used

## Fundamentação e pergunta

**Pergunta aprovada:** Quanto varia o uso de memória RAM (RSS, em MB) de um servidor Minecraft ao alterar a distância de visão entre 4, 8 e 12 chunks, mantendo o mesmo mundo e número de jogadores?

**Sugestão do professor:** Medir **também o heap em uso**, porque o RSS da JVM pode ficar estável com qualquer `view-distance`. Esta versão coleta **RSS + Java Heap Used + Heap Committed** em cada amostra. O heap é um **indicador complementar**, não substitui o RSS.

## Pré-requisitos no Mac

- Minecraft Java Edition **server** com JAR e mundo já preparados.
- JDK apropriado à versão do servidor (fornece `java`, `jps` e **`jstat`**).
- Python 3 instalado (`python3 --version`).
- Verificar `jstat -help` e `jps -lv`. O processo a monitorar é **o servidor**, não o cliente do jogo.

## Variáveis e controle

| Tipo | Descrição |
|---|---|
| Variável independente | `view-distance=4`, `8`, `12` em `server.properties` |
| Medidas principais | `rss_mib`, `heap_used_mib` |
| Medida auxiliar | `heap_committed_mib` e contadores de GC |
| Controles | Mesmo mundo, versão de Java e Minecraft, seed, coordenadas, 1 jogador imóvel, JVM flags, `simulation-distance`, tempo de aquecimento, duração/intervalo de coleta |

**Sugestão de controle:** usar `simulation-distance=4` em todos os testes para não exceder a menor view-distance. Carregar/preparar previamente a área visível até 12 chunks e manter o jogador parado; sem geração de chunks inéditos durante a medição. Anotar todas as configurações.

**JVM**: se no planejamento anterior foi definida `-Xms2G -Xmx4G`, manter esta mesma configuração em TODOS os testes. Lembre-se de que `-Xms` alto pode ajudar a estabilizar RSS, o que é parte da hipótese do professor.

## Protocolo atualizado: jogador parado, 10 repeticoes por condicao

- Manter **um jogador parado** nas mesmas coordenadas, mesma dimensao e mesma direcao da camera durante toda a coleta; preferencialmente um lugar seguro e sem atividade redstone / farms.
- Precarregar a regiao correspondente a 12 chunks no mesmo mundo antes de iniciar o experimento. Nao se deslocar durante as medicoes.
- Usar `view-distance=4`, `8`, `12`; manter `simulation-distance=4` em todas as condicoes.
- Reiniciar o servidor **a cada repeticao**; manter o mesmo mundo, jogador, versao, `-Xms` e `-Xmx`; nao fazer GC manual.
- Conectar o cliente (ou assegurar presenca do jogador) e aguardar os chunks carregarem + 2 minutos de aquecimento antes de medir. Nao mover o personagem nem mudar a camera.
- Usar 10 repeticoes por condicao (30 runs) e 25 amostras por repeticao (`t=0,5,...,120s`).
- Se desejar realizar um teste piloto rapido: `--amostras 13 --intervalo 5` (60 s). Nao misturar testes piloto com as 30 runs do protocolo final.
- Nao iniciar a medicao antes de o mesmo conjunto de chunks correspondente a cada view distance ter sido carregado. Salvar os arquivos de saida bruta e metadados.

## Passo a passo: coleta

1. Desligar o servidor usando `stop`. No arquivo `server.properties`, definir `view-distance=4` e `simulation-distance=4`.
2. Iniciar o servidor:

   ```bash
   java -Xms2G -Xmx4G -jar server.jar nogui
   ```

3. Conectar 1 jogador, assegurar a posicao fixa e aguardar carga de chunks + 2 minutos.
4. Em outro Terminal, identificar o PID do servidor com `jps -lv` e verificar `ps -o rss= -p PID` e `jstat -gc PID`.
5. Na pasta dos scripts, iniciar a coleta (substituir PID pelo valor real):

   ```bash
   python3 coletar_memoria.py 4 1 PID
   ```

6. A coleta salva 25 amostras em arquivos CSV, raw e meta. Depois, parar o servidor, reiniciar, reconectar, aquecer e medir a repeticao seguinte. O PID pode mudar a cada reinicio.
7. Repetir para as dez rodadas de cada VD (4, 8 e 12). Antes de trocar de VD, ajustar `server.properties` com o servidor desligado.
8. Por fim, executar:

   ```bash
   python3 resumir.py
   ```

   O resumo avisa caso alguma condicao tenha menos de 10 rodadas ou alguma rodada tenha menos de 25 amostras.

## Plano de 30 execucoes

| Condicao | Repeticoes | Amostras/rodada | Duracao de medicao |
|---|---|---|---|
| VD4 | 1 a 10 | 25 | 120 s |
| VD8 | 1 a 10 | 25 | 120 s |
| VD12 | 1 a 10 | 25 | 120 s |

O coletor entende os comandos `python3 coletar_memoria.py 4 10 PID`, `python3 coletar_memoria.py 8 10 PID`, etc. Cada rodada salva em `dados/VD{4,8,12}_run{1..10}.csv`.

## Dados produzidos

Na pasta `dados/` cada repetição gera três arquivos:

- `VD4_run1.csv`: valores numéricos de cada amostra.
- `VD4_run1_raw.txt`: saídas integrais de `ps` e `jstat`, para auditoria.
- `VD4_run1_meta.txt`: data, PID, versão do Java, comandos e parâmetros.

O resumo gera:

- `resumo_por_repeticao.csv`: média, mínimo e máximo **amostrado** por repetição.
- `resumo_por_condicao.csv`: média das médias das repetições, maior máximo amostrado e desvio padrão entre repetições para cada view-distance.

**Unidades:** `ps rss` no macOS retorna KiB (1024 bytes). `jstat -gc` informa áreas de memória em KB (unidades de aproximadamente 1024 bytes). Estes scripts dividem por 1024 e identificam o resultado como **MiB** (mais preciso que MB). O valor de Heap Used é `S0U + S1U + EU + OU`, excluindo Metaspace; Heap Committed é `S0C + S1C + EC + OC` (sem o reservado máximo `-Xmx`).

**Importante:** Heap Used muda naturalmente durante o ciclo do Garbage Collector; por isso não tirar conclusões de uma amostra isolada. Não disparar GC manualmente durante os testes. RSS e heap usado são métricas diferentes: RSS inclui memória nativa e heap residente; não subtrair automaticamente Heap Used de RSS para determinar memória nativa.

**Conservação dos dados:** O coletor nunca substitui CSVs existentes. Se um teste falhar, manter o arquivo parcial e registrar por que foi repetido. Nunca inventar medições.

## Registro manual para o relatório

| Informação | Valor registrado pelo aluno |
|---|---|
| Versão exata do servidor e tipo (Vanilla / Paper) | |
| Versão do Java e flags (`-Xms`, `-Xmx`) | |
| Mundo / seed | |
| Coordenadas / dimensão | |
| Número de jogadores conectados e atividade | |
| `simulation-distance` em todos os testes | |
| Sistema operacional e memória física | |
| Máquina rodando cliente e servidor simultaneamente? | |
| Chunks pré-gerados? Como foi assegurado? | |
| Outros programas abertos / tarefas em segundo plano | |

## Dicas de interpretação

- Se RSS quase não mudar, mas Heap Used aumentar, este é um resultado legítimo e responde ao questionamento do professor.
- Se ambos aumentarem, mostrar as duas tendências.
- Se nenhum mudar, discutir limitações, controle do cenário, GC e as hipóteses, não modificar números.
- Fazer gráficos de linha com as 25 amostras e gráficos comparativos de médias entre 4/8/12 chunks.
