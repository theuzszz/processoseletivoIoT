# Monitor de Estoque Kanban com ESP32

Projeto da etapa prática do PNAAT, desenvolvido em MicroPython e simulado no
Wokwi. O objetivo é acompanhar o peso de uma caixa de componentes e avisar
quando ela precisa ser reabastecida.

## Candidato

- **Nome:** Matheus Souza da Silva Leite
- **GitHub:** [@theuzszz](https://github.com/theuzszz)

## Como o projeto funciona

Uma célula de carga ligada ao HX711 mede o peso da caixa. O ESP32 lê esse valor,
converte a leitura para gramas e decide qual mensagem deve aparecer no terminal.

O sistema possui quatro comportamentos principais:

- informa o peso enquanto o estoque está em uma faixa segura;
- abre um pedido de reposição quando o peso chega ao nível crítico;
- confirma o abastecimento quando a caixa volta a `5000 g`;
- trata uma leitura de `0 g` como falha do sensor ou caixa removida.

## Componentes e ligações

| Componente | Função |
|---|---|
| ESP32 DevKit C v4 (`esp`) | Executa o firmware MicroPython |
| HX711 com célula de 5 kg (`hx711`) | Envia a leitura da carga para o ESP32 |
| Monitor Serial | Mostra pesos, eventos e alertas |

| HX711 | ESP32 |
|---|---|
| `VCC` | `5V` |
| `GND` | `GND.2` |
| `DT` | GPIO 19 |
| `SCK` | GPIO 18 |

Os pinos usados no circuito são os mesmos definidos em `src/main.py`.

## Organização do código

O firmware foi dividido em três arquivos para deixar cada responsabilidade
clara:

- `src/hx711.py`: faz a leitura de 24 bits do conversor HX711;
- `src/main.py`: configura os pinos, converte a leitura e executa o laço principal;
- `src/kanban.py`: contém os limites e as regras do estoque.

O fluxo dos dados é simples:

```text
Célula de carga -> HX711 -> main.py -> regras do Kanban -> Monitor Serial
```

Separar a leitura do sensor das regras do estoque facilita os testes e evita que
uma mudança no hardware obrigue a reescrever toda a lógica.

## Regras do estoque

| Leitura | Resultado |
|---|---|
| Sensor sem resposta, `0 g` ou valor negativo | Alerta de sensor ou caixa ausente |
| Sem pedido pendente, de `1 g` até `200 g` | Abre um pedido de reposição |
| Sem pedido pendente e peso acima de `200 g` | Estoque regular |
| Pedido pendente e peso abaixo de `5000 g` | Continua aguardando o abastecimento |
| Pedido pendente e peso `>= 5000 g` | Confirma a caixa cheia |

A leitura inválida é verificada antes do nível crítico. Assim, `0 g` não gera um
pedido de reposição comum. Os eventos também são impressos apenas uma vez, mesmo
que o sensor continue enviando o mesmo valor.

## Leitura e tempo de resposta

O ESP32 consulta o HX711 a cada `10 ms`. A leitura não fica presa esperando o
sensor responder. Se o HX711 permanecer sem resposta por `1000 ms`, o firmware
registra uma falha.

Enquanto o peso estiver regular, o status é atualizado a cada `500 ms`. Esse
intervalo mantém a informação visível sem encher o terminal rapidamente.

## Conversão para gramas

Nos testes do desafio, cada unidade do controle `load` gera 420 contagens na
leitura bruta do HX711. A conversão usada é:

```text
peso em gramas = arredondar(leitura bruta / 420)
```

| `load` | Leitura bruta | Peso usado |
|---:|---:|---:|
| 5000 | 2.100.000 | 5000 g |
| 2500 | 1.050.000 | 2500 g |
| 150 | 63.000 | 150 g |
| 0 | 0 | Falha |

Não foi feita tara automática porque os cenários trabalham com valores
absolutos. Uma tara na inicialização mudaria os limites esperados pelos testes.
A relação de 420 contagens também aparece no
[teste de referência do HX711 no Wokwi](https://github.com/wokwi/wokwi-part-tests/blob/main/wokwi-hx711/hx711-uno/hx711.test.yaml).

## Mensagens do sistema

Os testes procuram estas mensagens exatamente como estão escritas:

```text
Sistema Kanban Inicializado
Status: Estoque Regular (2500g)
Evento de reposição disparado! Caixa vazia detectada.
Abastecimento concluído. Caixa cheia.
ALERTA: Caixa ausente ou erro de calibração no sensor HX711!
```

O peso mostrado no status regular é atualizado conforme a leitura do sensor.

## Testes automatizados

| Teste | Valores aplicados | Resultado esperado |
|---|---|---|
| Consumo parcial | `5000 -> 2500` | Continua regular e mostra `2500g` |
| Reposição | `150 -> 5000` | Abre o pedido e depois confirma a caixa cheia |
| Anomalia | `5000 -> 0` | Mostra o alerta de falha |

O GitHub Actions executa o seguinte processo em cada envio:

1. identifica o cenário `WEIGHT`;
2. usa o `Dockerfile` para gerar o sistema de arquivos `fs.bin`;
3. executa os três testes no Wokwi CI.

O token do Wokwi fica no secret `WOKWI_CLI_TOKEN` do GitHub e não é salvo no
código.

## Estrutura do projeto

```text
.
├── .github/workflows/ci.yml
├── binaries/
├── scenarios/
│   ├── WEIGHT.md
│   └── weight/
├── src/
│   ├── hx711.py
│   ├── kanban.py
│   └── main.py
├── diagram.json
├── Dockerfile
├── flasher_args.json
├── README.md
└── wokwi.toml
```

## Resultado e limitações

Os três cenários oficiais foram executados com sucesso no GitHub Actions. A
solução também evita mensagens repetidas, mantém um pedido pendente durante uma
falha momentânea e permite iniciar um novo ciclo depois do abastecimento.

Em uma montagem real seria necessário fazer a tara da caixa, calibrar o sensor
com uma massa conhecida e filtrar pequenas oscilações. Esses tratamentos não
foram adicionados porque a simulação usa valores fixos definidos pelo desafio.
