"""Regras do monitor de estoque Kanban."""

try:
    from time import ticks_diff
except ImportError:  # Também permite testar este arquivo no Python comum.

    def ticks_diff(current, previous):
        return current - previous


INITIALIZATION_MESSAGE = "Sistema Kanban Inicializado"
REPLENISHMENT_MESSAGE = "Evento de reposição disparado! Caixa vazia detectada."
REFILL_COMPLETE_MESSAGE = "Abastecimento concluído. Caixa cheia."
SENSOR_FAULT_MESSAGE = "ALERTA: Caixa ausente ou erro de calibração no sensor HX711!"
REGULAR_STATUS_TEMPLATE = "Status: Estoque Regular ({}g)"

CRITICAL_WEIGHT_MAX_G = 200
FULL_WEIGHT_MIN_G = 5000
REGULAR_STATUS_INTERVAL_MS = 500


class KanbanMonitor:
    """Controla o estoque, a reposição e as falhas do sensor."""

    def __init__(self, emit=print):
        self._emit = emit
        self._replenishment_pending = False
        self._sensor_fault_active = False
        self._last_regular_status_ms = None

    def process(self, weight_grams, now_ms):
        """Processa uma leitura já convertida para gramas."""
        if weight_grams is None or weight_grams <= 0:
            self._handle_sensor_fault()
            return

        self._sensor_fault_active = False

        if self._replenishment_pending:
            self._handle_pending_replenishment(weight_grams)
            return

        if weight_grams <= CRITICAL_WEIGHT_MAX_G:
            self._emit(REPLENISHMENT_MESSAGE)
            self._replenishment_pending = True
            self._last_regular_status_ms = None
            return

        self._report_regular_status(weight_grams, now_ms)

    def _handle_sensor_fault(self):
        """Mostra a falha uma vez sem cancelar um pedido existente."""
        if not self._sensor_fault_active:
            self._emit(SENSOR_FAULT_MESSAGE)
            self._sensor_fault_active = True
            self._last_regular_status_ms = None

    def _handle_pending_replenishment(self, weight_grams):
        """Fecha o pedido quando a caixa volta ao peso cheio."""
        if weight_grams >= FULL_WEIGHT_MIN_G:
            self._emit(REFILL_COMPLETE_MESSAGE)
            self._replenishment_pending = False
            self._last_regular_status_ms = None

    def _report_regular_status(self, weight_grams, now_ms):
        """Mostra o peso periodicamente enquanto o estoque está regular."""
        first_report = self._last_regular_status_ms is None
        report_due = (
            not first_report
            and ticks_diff(now_ms, self._last_regular_status_ms)
            >= REGULAR_STATUS_INTERVAL_MS
        )

        if first_report or report_due:
            self._emit(REGULAR_STATUS_TEMPLATE.format(weight_grams))
            self._last_regular_status_ms = now_ms
