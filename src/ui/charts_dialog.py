"""Charts dialog - visualize collection data as bar or pie charts"""

import json

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QPieSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.core.collection_store import CollectionStore

# Field types that are meaningful to chart (exclude binary/rich-text blobs)
_CHARTABLE_TYPES = {
    "text",
    "number",
    "select",
    "multi_select",
    "boolean",
    "date",
    "email",
    "url",
    "phone",
}

# Palette of distinct colours for chart series
_PALETTE = [
    "#7C3AED",  # violet
    "#2563EB",  # blue
    "#16A34A",  # green
    "#D97706",  # amber
    "#DC2626",  # red
    "#0891B2",  # cyan
    "#9333EA",  # purple
    "#EA580C",  # orange
    "#65A30D",  # lime
    "#DB2777",  # pink
    "#0D9488",  # teal
    "#B45309",  # yellow-brown
]


class ChartsDialog(QDialog):
    """Dialog for visualizing collection field value distributions."""

    def __init__(
        self,
        parent=None,
        store: CollectionStore | None = None,
        fields: list[dict] | None = None,
        collection_name: str = "",
    ):
        super().__init__(parent)
        self.store = store
        self.fields = [f for f in (fields or []) if f.get("type") in _CHARTABLE_TYPES]
        self.collection_name = collection_name

        self.setWindowTitle("Charts")
        self.setMinimumWidth(760)
        self.setMinimumHeight(600)

        if parent:
            self.setStyleSheet(parent.styleSheet())

        self._init_ui()

        # Auto-render if there are usable fields
        if self.fields:
            self._run_chart()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        # Title
        title = QLabel("Charts")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        root.addWidget(title)

        subtitle_text = (
            "Select a field to see how its values are distributed across all records."
        )
        if self.collection_name:
            subtitle_text = (
                f"Collection: <b>{self.collection_name}</b> — " + subtitle_text
            )
        subtitle = QLabel(subtitle_text)
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(QLabel("Field:"))
        self.field_combo = QComboBox()
        self.field_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for field in self.fields:
            label = field.get("label") or field["key"]
            self.field_combo.addItem(label, field["key"])
        self.field_combo.currentIndexChanged.connect(self._run_chart)
        controls.addWidget(self.field_combo)

        controls.addWidget(QLabel("Chart type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Bar Chart", "Pie Chart"])
        self.type_combo.currentIndexChanged.connect(self._run_chart)
        controls.addWidget(self.type_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._run_chart)
        controls.addWidget(refresh_btn)

        root.addLayout(controls)

        # Chart view
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.chart_view.setMinimumHeight(320)
        root.addWidget(self.chart_view)

        # Summary table
        table_label = QLabel("Breakdown")
        table_label.setFont(QFont())
        root.addWidget(table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Value", "Count", "Percentage"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setMaximumHeight(180)
        root.addWidget(self.table)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        # Empty-state label (shown when no data / no fields)
        self._empty_label = QLabel("No data available for this field.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.hide()
        root.addWidget(self._empty_label)

    # ------------------------------------------------------------------
    # Data + chart rendering
    # ------------------------------------------------------------------

    def _run_chart(self):
        """Query the store and render the selected chart type."""
        if not self.store or not self.fields:
            self._show_empty("No collection or chartable fields available.")
            return

        field_key = self.field_combo.currentData()
        if not field_key:
            return

        counts = self._query_counts(field_key)
        if not counts:
            self._show_empty("No records found.")
            return

        total = sum(c for _, c in counts)
        if total == 0:
            self._show_empty("No records found.")
            return

        self._empty_label.hide()
        self._populate_table(counts, total)

        chart_type = self.type_combo.currentText()
        if chart_type == "Pie Chart":
            self._render_pie(counts, total, field_key)
        else:
            self._render_bar(counts, total, field_key)

    def _query_counts(self, field_key: str) -> list[tuple[str, int]]:
        """Return sorted list of (value_label, count) for a field."""
        self.store.connect()
        cursor = self.store.conn.cursor()

        # Retrieve the field definition to handle multi-select expansion
        field_def = self.store.get_field(field_key)
        field_type = field_def.get("type") if field_def else None

        if field_type == "multi_select":
            # Each record may hold a JSON array; expand individually
            cursor.execute(f"SELECT {field_key} FROM records")  # noqa: S608
            rows = cursor.fetchall()
            tally: dict[str, int] = {}
            for (raw,) in rows:
                if raw:
                    try:
                        values = json.loads(raw)
                        if isinstance(values, list):
                            for v in values:
                                label = str(v).strip() if v is not None else ""
                                key = label or "(Empty)"
                                tally[key] = tally.get(key, 0) + 1
                        else:
                            label = str(raw).strip() or "(Empty)"
                            tally[label] = tally.get(label, 0) + 1
                    except (json.JSONDecodeError, TypeError):
                        label = str(raw).strip() or "(Empty)"
                        tally[label] = tally.get(label, 0) + 1
                else:
                    tally["(Empty)"] = tally.get("(Empty)", 0) + 1
            counts = sorted(tally.items(), key=lambda x: -x[1])
        else:
            cursor.execute(
                f"SELECT COALESCE({field_key}, '') as val, COUNT(*) as cnt"  # noqa: S608
                f" FROM records GROUP BY val ORDER BY cnt DESC"
            )
            counts = []
            for row in cursor.fetchall():
                label = str(row[0]).strip() if row[0] else "(Empty)"
                if not label:
                    label = "(Empty)"
                counts.append((label, row[1]))

        return counts

    def _populate_table(self, counts: list[tuple[str, int]], total: int):
        """Fill the summary table."""
        self.table.setRowCount(len(counts))
        for row, (label, count) in enumerate(counts):
            pct = (count / total * 100) if total else 0.0
            self.table.setItem(row, 0, QTableWidgetItem(label))

            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, count_item)

            pct_item = QTableWidgetItem(f"{pct:.1f}%")
            pct_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, pct_item)

    def _render_bar(self, counts: list[tuple[str, int]], total: int, field_key: str):
        """Render a vertical bar chart."""
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setTitle(f'Distribution of "{self._field_label(field_key)}"')
        chart.legend().setVisible(False)

        bar_set = QBarSet("Count")
        bar_set.setColor(QColor(_PALETTE[0]))

        categories = []
        for label, count in counts:
            # Truncate long labels for display
            display = label if len(label) <= 20 else label[:18] + "…"
            categories.append(display)
            bar_set.append(count)

        series = QBarSeries()
        series.append(bar_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        max_count = max(c for _, c in counts) if counts else 1
        axis_y = QValueAxis()
        axis_y.setRange(0, max_count * 1.1)
        axis_y.setLabelFormat("%d")
        axis_y.setTitleText("Count")
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)

        self.chart_view.setChart(chart)

    def _render_pie(self, counts: list[tuple[str, int]], total: int, field_key: str):
        """Render a pie chart with percentage labels."""
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        chart.setTitle(f'Distribution of "{self._field_label(field_key)}"')

        series = QPieSeries()
        for i, (label, count) in enumerate(counts):
            pct = count / total * 100
            display = label if len(label) <= 20 else label[:18] + "…"
            slice_ = series.append(f"{display}  {pct:.1f}%", count)
            slice_.setColor(QColor(_PALETTE[i % len(_PALETTE)]))
            # Label the largest slice explicitly
            if i == 0:
                slice_.setLabelVisible(True)
                slice_.setExploded(True)
                slice_.setExplodeDistanceFactor(0.05)

        chart.addSeries(series)
        chart.legend().setAlignment(Qt.AlignRight)

        self.chart_view.setChart(chart)

    def _show_empty(self, message: str):
        """Display an empty-state message and clear chart/table."""
        self.chart_view.setChart(QChart())
        self.table.setRowCount(0)
        self._empty_label.setText(message)
        self._empty_label.show()

    def _field_label(self, field_key: str) -> str:
        """Return the display label for a field key."""
        for f in self.fields:
            if f["key"] == field_key:
                return f.get("label") or field_key
        return field_key
