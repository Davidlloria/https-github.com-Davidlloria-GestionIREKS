from __future__ import annotations

from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.services.customer_ai_summary_service import CustomerAISummaryResult, CustomerAISummarySections


class CustomerAISummaryDialog(QDialog):
    retry_requested = Signal()

    def __init__(self, *, customer_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("customerAISummaryDialog")
        self.setWindowTitle(f"Resumen IA · {customer_name}")
        self.resize(920, 720)
        self.setMinimumSize(700, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel(f"Resumen comercial · {customer_name}")
        title.setObjectName("customerAISummaryTitle")
        title.setProperty("role", "sectionTitle")
        layout.addWidget(title)

        self.period_label = QLabel("Preparando datos del periodo comparable…")
        self.period_label.setObjectName("customerAISummaryPeriod")
        self.period_label.setStyleSheet("color: #64748B;")
        layout.addWidget(self.period_label)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        self.kg_value = self._metric_card(metrics, 0, "VOLUMEN ACTUAL", "—")
        self.variation_value = self._metric_card(metrics, 1, "VARIACIÓN", "—")
        self.revenue_value = self._metric_card(metrics, 2, "FACTURACIÓN", "—")
        self.activity_value = self._metric_card(metrics, 3, "ÚLTIMA ACTIVIDAD", "—")
        layout.addLayout(metrics)

        self.status_label = QLabel("Generando resumen con IA local…")
        self.status_label.setObjectName("customerAISummaryStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #64748B;")
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setObjectName("customerAISummaryProgress")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self.summary_text = QTextBrowser()
        self.summary_text.setObjectName("customerAISummaryText")
        self.summary_text.setReadOnly(True)
        self.summary_text.setOpenExternalLinks(False)
        self.summary_text.setHtml(self._loading_html())
        layout.addWidget(self.summary_text, 1)

        footer = QHBoxLayout()
        self.source_label = QLabel("Datos de GestionIREKS · redacción local y privada")
        self.source_label.setStyleSheet("color: #64748B;")
        footer.addWidget(self.source_label)
        footer.addStretch(1)
        self.retry_button = QPushButton("Reintentar redacción IA")
        self.retry_button.setObjectName("customerAISummaryRetryButton")
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(self.retry_requested)
        footer.addWidget(self.retry_button)
        close_button = QPushButton("Cerrar")
        close_button.setObjectName("customerAISummaryCloseButton")
        close_button.clicked.connect(self.reject)
        footer.addWidget(close_button)
        layout.addLayout(footer)

    @staticmethod
    def _metric_card(layout: QGridLayout, column: int, caption: str, value: str) -> QLabel:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 9, 12, 9)
        card_layout.setSpacing(3)
        caption_label = QLabel(caption)
        caption_label.setStyleSheet("color: #64748B; font-size: 10px;")
        value_label = QLabel(value)
        value_label.setStyleSheet("font-weight: 600; font-size: 15px;")
        card_layout.addWidget(caption_label)
        card_layout.addWidget(value_label)
        layout.addWidget(card, 0, column)
        return value_label

    def set_loading(self) -> None:
        self.status_label.setText("Generando resumen con IA local…")
        self.progress.setVisible(True)
        self.retry_button.setEnabled(False)
        self.summary_text.setHtml(self._loading_html())

    def set_result(self, result: CustomerAISummaryResult) -> None:
        self.progress.setVisible(False)
        self.retry_button.setEnabled(True)
        self.status_label.setText(result.message)
        if not result.ok or result.snapshot is None:
            self.summary_text.setHtml(
                f"<h3>No se pudo generar el resumen</h3><p>{escape(result.message)}</p>"
            )
            return

        data = result.snapshot
        self.period_label.setText(data.period_label.capitalize())
        self.kg_value.setText(f"{self._number(data.kg_current)} kg")
        variation = "Sin base" if data.delta_kg_pct is None else f"{data.delta_kg_pct:+.1f}%"
        self.variation_value.setText(variation)
        self.revenue_value.setText(f"{self._number(data.euros_current)} €")
        self.activity_value.setText(data.latest_activity or "Sin registrar")
        sections = result.sections or CustomerAISummarySections(
            situation=result.text,
            sales="",
            conclusion="Resumen calculado con datos de GestionIREKS.",
        )
        self.summary_text.setHtml(self._result_html(sections, result.used_ai))

    @staticmethod
    def _loading_html() -> str:
        return (
            "<div style='color:#64748B; padding:18px'>"
            "Analizando ventas, productos y actividad comercial. En CPU, la primera respuesta puede tardar unos minutos."
            "</div>"
        )

    @staticmethod
    def _result_html(sections: CustomerAISummarySections, used_ai: bool) -> str:
        def paragraph(value: str) -> str:
            return escape(value).replace("\n", "<br>")

        def bullets(values: tuple[str, ...], empty: str) -> str:
            clean_values = values or (empty,)
            return "<ul>" + "".join(f"<li>{paragraph(value)}</li>" for value in clean_values) + "</ul>"

        badge = "Redactado por IA local" if used_ai else "Resumen calculado"
        return (
            "<div style='font-family:Segoe UI; color:#334E75; line-height:1.45'>"
            f"<p style='color:#64748B'><b>{badge}</b></p>"
            f"<h3>Situación</h3><p>{paragraph(sections.situation)}</p>"
            f"<h3>Ventas</h3><p>{paragraph(sections.sales)}</p>"
            f"<h3>Productos</h3>{bullets(sections.products, 'Sin observaciones de producto.') }"
            f"<h3>Oportunidades</h3>{bullets(sections.opportunities, 'Sin acciones automáticas sugeridas.') }"
            f"<h3>Conclusión</h3><p>{paragraph(sections.conclusion)}</p>"
            "</div>"
        )

    @staticmethod
    def _number(value: float) -> str:
        return f"{float(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
