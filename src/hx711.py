"""Leitura do conversor HX711 em MicroPython."""

from time import sleep_us

from machine import Pin, disable_irq, enable_irq

READING_BITS = 24
SIGN_BIT = 0x800000
FULL_SCALE = 0x1000000
CLOCK_PULSE_US = 1


class HX711:
    """Lê o canal A do HX711 com ganho 128."""

    def __init__(self, data_pin, clock_pin):
        self._data = Pin(data_pin, Pin.IN)
        self._clock = Pin(clock_pin, Pin.OUT)
        self._clock.off()

    def read_raw_if_ready(self):
        """Retorna a leitura ou ``None`` se o conversor ainda estiver ocupado."""
        if self._data.value() != 0:
            return None

        value = 0
        irq_state = disable_irq()

        try:
            for _ in range(READING_BITS):
                self._clock.on()
                sleep_us(CLOCK_PULSE_US)
                value = (value << 1) | self._data.value()
                self._clock.off()
                sleep_us(CLOCK_PULSE_US)

            # O 25º pulso seleciona canal A com ganho 128 na próxima leitura.
            self._clock.on()
            sleep_us(CLOCK_PULSE_US)
            self._clock.off()
            sleep_us(CLOCK_PULSE_US)
        finally:
            # Evita deixar o HX711 em power-down se uma leitura for interrompida.
            self._clock.off()
            enable_irq(irq_state)

        if value & SIGN_BIT:
            value -= FULL_SCALE

        return value
