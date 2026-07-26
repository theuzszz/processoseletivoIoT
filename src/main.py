"""Ponto de entrada do monitor de estoque Kanban no ESP32."""

from micropython import const
from time import sleep_ms, ticks_diff, ticks_ms

from hx711 import HX711
from kanban import INITIALIZATION_MESSAGE, KanbanMonitor


HX711_DATA_PIN = const(19)
HX711_CLOCK_PIN = const(18)

# O modelo do Wokwi gera 420 contagens para cada unidade do controle
# ``load``. No desafio, essa unidade numérica representa um grama.
CALIBRATION_COUNTS_PER_GRAM = const(420)

POLL_INTERVAL_MS = const(10)
SENSOR_RESPONSE_TIMEOUT_MS = const(1000)


def raw_to_grams(raw_value):
    """Converte a leitura bruta do HX711 para gramas inteiras."""
    return int(round(raw_value / CALIBRATION_COUNTS_PER_GRAM))


def run():
    """Lê o sensor continuamente e encaminha os dados ao monitor Kanban."""
    scale = HX711(HX711_DATA_PIN, HX711_CLOCK_PIN)
    monitor = KanbanMonitor()
    last_sensor_response_ms = ticks_ms()

    # O cenário de CI aguarda esta mensagem antes de injetar os estímulos.
    print(INITIALIZATION_MESSAGE)

    while True:
        now_ms = ticks_ms()
        raw_value = scale.read_raw_if_ready()

        if raw_value is not None:
            last_sensor_response_ms = now_ms
            monitor.process(raw_to_grams(raw_value), now_ms)
        elif ticks_diff(now_ms, last_sensor_response_ms) >= SENSOR_RESPONSE_TIMEOUT_MS:
            monitor.process(None, now_ms)

        # Pausa curta e cooperativa: mantém o firmware responsivo sem busy-wait.
        sleep_ms(POLL_INTERVAL_MS)


if __name__ == "__main__":
    run()
