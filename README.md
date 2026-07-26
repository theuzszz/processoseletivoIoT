# Monitor de Estoque Kanban Inteligente

Projeto da etapa prática de Sistemas Embarcados do PNAAT, desenvolvido em
MicroPython para ESP32 e preparado para simulação e validação automatizada no
Wokwi CI.

## Identificação do candidato

- **Nome completo:** Matheus Souza da Silva Leite
- **GitHub:** [@theuzszz](https://github.com/theuzszz)

## Visão geral da solução

O projeto automatiza o acompanhamento de uma caixa de componentes em uma linha
de produção. Uma célula de carga simulada pelo HX711 informa o peso atual ao
ESP32. A partir dessa leitura, o firmware:

- publica a telemetria enquanto o estoque está em uma faixa segura;
- abre uma solicitação de reposição quando a caixa chega ao nível crítico;
- confirma o reabastecimento somente depois que uma solicitação está pendente;
- diferencia uma caixa vazia de uma leitura impossível, como `0 g`;
- evita a repetição contínua de alertas para um mesmo evento.

Na simulação, o usuário interage diretamente com o controle de carga do
componente `hx711`. Em produção, esse estímulo corresponderia à retirada ou à
reposição física de peças na caixa.

## Arquitetura do sistema embarcado

O firmware foi separado em três responsabilidades:

```text
HX711 físico/simulado
        │  leitura bruta de 24 bits
        ▼
src/hx711.py ──► src/main.py ──► src/kanban.py ──► Monitor Serial
   protocolo       conversão       regras e          eventos e
   do sensor       para gramas     estados           telemetria
```

- `hx711.py` implementa somente o protocolo do conversor: verifica se existe
  uma amostra pronta, lê os 24 bits e envia o 25º pulso para manter o canal A
  com ganho 128.
- `main.py` configura os pinos, converte a leitura bruta para gramas e mantém o
  laço cooperativo do firmware.
- `kanban.py` concentra limites, mensagens e transições do processo de estoque.

Essa divisão mantém o acesso ao hardware isolado das regras de negócio. Assim,
uma mudança de sensor não exige reescrever a máquina de estados do Kanban.

## Componentes e conexões

| Componente | ID no Wokwi | Função |
|---|---|---|
| ESP32 DevKit C v4 | `esp` | Executa o firmware MicroPython |
| HX711 com célula de 5 kg | `hx711` | Converte a carga simulada em uma leitura digital |
| Monitor Serial | `$serialMonitor` | Exibe telemetria, eventos e alertas |

| HX711 | ESP32 | Finalidade |
|---|---|---|
| `VCC` | `5V` | Alimentação do componente simulado |
| `GND` | `GND.2` | Referência elétrica comum |
| `DT` | GPIO 19 | Dados do conversor |
| `SCK` | GPIO 18 | Relógio gerado pelo firmware |

Os GPIOs 18 e 19 foram escolhidos por não serem pinos de *strapping* do ESP32,
evitando interferência no processo de inicialização da placa.

## Fluxo lógico e estados

A anomalia do sensor é avaliada antes do nível crítico. Essa prioridade impede
que uma leitura de `0 g` abra indevidamente um pedido de reposição.

| Condição | Comportamento |
|---|---|
| Sensor sem resposta ou peso `<= 0 g` | Emite uma vez o alerta de caixa ausente/erro de calibração |
| Peso entre `1 g` e `200 g` | Abre uma única solicitação de reposição |
| Reposição pendente e peso abaixo de `5000 g` | Mantém a solicitação aberta, sem duplicar mensagens |
| Reposição pendente e peso `>= 5000 g` | Confirma o abastecimento e encerra a solicitação |
| Sem reposição pendente e peso acima de `200 g` | Publica o estoque regular a cada 500 ms |

O ciclo só é concluído quando a leitura atinge os `5000 g` definidos pelo
desafio como o patamar de caixa cheia. Enquanto esse valor não é alcançado, uma
solicitação de reposição permanece pendente e não gera mensagens duplicadas.

Duas informações independentes representam o estado do processo:

- `replenishment_pending`: registra que a caixa precisa voltar ao patamar cheio;
- `sensor_fault_active`: impede a repetição do mesmo alerta de falha.

Manter esses estados separados permite, por exemplo, preservar uma solicitação
de reposição mesmo se ocorrer uma falha momentânea do sensor.

## Temporização e responsividade

O laço principal consulta o HX711 a cada `10 ms`, mas nunca espera ocupando o
processador até o conversor responder. Quando o pino de dados indica que o ADC
ainda está ocupado, o método retorna imediatamente e o laço continua. Se não
houver nenhuma amostra por `1000 ms`, o caso é tratado como falha de sensor.

A telemetria regular é periódica, enquanto os eventos são emitidos somente em
transições. Essa escolha atende a dois objetivos:

1. um supervisório pode conhecer o peso atual mesmo que tenha começado a
   escutar depois da última mudança;
2. uma caixa parada no mesmo estado não gera uma sequência de solicitações ou
   alertas duplicados.

## Calibração da simulação

O HX711 de 5 kg do Wokwi utiliza a relação de **420 contagens por unidade do
controle `load`**. Os cenários deste desafio fornecem essa unidade numericamente
em gramas, portanto a conversão aplicada é:

```text
peso_em_gramas = arredondar(leitura_bruta / 420)
```

| Controle `load` | Leitura bruta esperada | Resultado usado pelo firmware |
|---:|---:|---:|
| 5000 | 2.100.000 | 5000 g |
| 2500 | 1.050.000 | 2500 g |
| 150 | 63.000 | 150 g |
| 0 | 0 | falha de sensor/caixa ausente |

Não é feita tara automática na inicialização. Os testes trabalham com cargas
absolutas e uma tara feita antes do primeiro estímulo poderia deslocar todos os
limites ou esconder a anomalia de `0 g`. A relação utilizada pode ser conferida
no [teste oficial do HX711 do Wokwi](https://github.com/wokwi/wokwi-part-tests/blob/main/wokwi-hx711/hx711-uno/hx711.test.yaml)
e na [implementação de referência](https://github.com/wokwi/wokwi-part-tests/blob/main/wokwi-hx711/hx711-uno/src/main.cpp).

## Mensagens da interface serial

As mensagens abaixo são constantes porque os cenários de integração contínua
fazem correspondência exata de caracteres:

```text
Sistema Kanban Inicializado
Status: Estoque Regular (2500g)
Evento de reposição disparado! Caixa vazia detectada.
Abastecimento concluído. Caixa cheia.
ALERTA: Caixa ausente ou erro de calibração no sensor HX711!
```

O número exibido no status regular é dinâmico e acompanha a carga lida.

## Cenários automatizados

| Teste | Estímulo | Resultado validado |
|---|---|---|
| Consumo parcial | `5000 → 2500 g` | Permanece regular e informa `2500g` |
| Ciclo completo | `150 → 5000 g` | Solicita reposição e depois confirma caixa cheia |
| Anomalia | `5000 → 0 g` | Emite alerta de caixa ausente/erro de calibração |

Cada cenário inicia uma nova simulação. O firmware também trata repetições de
amostras, reposição parcial, recuperação após falha e novos ciclos de consumo
sem repetir eventos indevidamente.

## Integração contínua

O workflow original foi preservado. A cada `push` ou `pull_request`, o GitHub
Actions:

1. identifica `scenarios/WEIGHT.md` como o cenário ativo;
2. constrói a imagem definida no `Dockerfile`;
3. empacota todos os arquivos de `src/` no sistema LittleFS (`fs.bin`);
4. executa os três cenários em paralelo no Wokwi CI.

Para que a simulação remota seja autorizada, o repositório deve possuir um
secret chamado exatamente `WOKWI_CLI_TOKEN`, criado em **Settings → Secrets and
variables → Actions**. O token nunca deve ser incluído no código ou nos commits.

## Estrutura do projeto

```text
.
├── .github/workflows/ci.yml   # build e testes Wokwi
├── binaries/                  # firmware MicroPython fornecido
├── scenarios/
│   ├── WEIGHT.md              # especificação escolhida
│   └── weight/                # três cenários automatizados
├── src/
│   ├── hx711.py               # protocolo do conversor
│   ├── kanban.py              # regras e estados do estoque
│   └── main.py                # inicialização e laço principal
├── diagram.json               # ESP32 e HX711 virtual
├── Dockerfile                 # geração do LittleFS
├── flasher_args.json          # mapa de gravação do ESP32
└── wokwi.toml                 # configuração da simulação
```

## Resultados obtidos

A implementação cobre os três fluxos solicitados e mantém o processamento
responsivo às mudanças aplicadas pelo simulador. As verificações locais validam
a sintaxe, a estrutura do circuito, as mensagens exatas e as transições da
máquina de estados. A execução no GitHub Actions é a validação final integrada
do firmware empacotado com o simulador Wokwi.

## Limitações e aplicação em hardware real

O fator `420` e o offset zero são próprios do componente virtual. Em uma balança
física, eu realizaria uma tara com a caixa vazia e obteria o fator de calibração
com uma massa conhecida. Também avaliaria filtragem de ruído, persistência do
contador de ciclos e adaptação de nível lógico do HX711 conforme o módulo usado.

Essas etapas não foram adicionadas à simulação porque alterariam as leituras
absolutas definidas pelo desafio sem trazer benefício aos cenários avaliados.
