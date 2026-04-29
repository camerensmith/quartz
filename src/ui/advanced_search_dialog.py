"""Advanced search dialog with SQL operators and cross-collection search"""


from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.collection_store import CollectionStore
from src.core.workspace import Workspace


class AdvancedSearchDialog(QDialog):
    """Dialog for advanced search across all collections with SQL operators"""

    def __init__(self, parent=None, workspace: Workspace | None = None):
        super().__init__(parent)
        self.workspace = workspace
        self.results: list[dict] = []  # List of {collection, record} dicts

        self.setWindowTitle("Advanced Search")
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)

        # Apply theme from parent if available
        if parent:
            self.setStyleSheet(parent.styleSheet())

        self._init_ui()

    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)

        # Search criteria builder (with guardrails)
        criteria_group = QGroupBox("Search Criteria")
        criteria_layout = QVBoxLayout()

        # Simple text search option
        self.use_text_search = QCheckBox("Simple text search (searches all fields)")
        self.use_text_search.setChecked(False)
        self.text_search_input = QLineEdit()
        self.text_search_input.setPlaceholderText("Enter text to search for...")
        self.text_search_input.setEnabled(False)
        self.use_text_search.toggled.connect(lambda checked: self.text_search_input.setEnabled(checked))
        criteria_layout.addWidget(self.use_text_search)
        criteria_layout.addWidget(self.text_search_input)

        # Field-based search criteria (builder)
        self.criteria_list = []  # List of {field, operator, value, logic} dicts
        self.criteria_widgets = []  # List of widget containers

        criteria_scroll = QWidget()
        criteria_scroll_layout = QVBoxLayout(criteria_scroll)
        criteria_scroll_layout.setContentsMargins(0, 0, 0, 0)

        # Add first criterion row
        self._add_criterion_row(criteria_scroll_layout)

        criteria_layout.addWidget(QLabel("Or build field-based search:"))
        criteria_layout.addWidget(criteria_scroll)

        # Add criterion button
        add_criterion_btn = QPushButton("+ Add Another Condition")
        add_criterion_btn.clicked.connect(lambda: self._add_criterion_row(criteria_scroll_layout))
        criteria_layout.addWidget(add_criterion_btn)

        criteria_group.setLayout(criteria_layout)
        layout.addWidget(criteria_group)

        # Collection selection
        collections_group = QGroupBox("Search Collections")
        collections_layout = QVBoxLayout()

        self.search_all_check = QCheckBox("Search all collections")
        self.search_all_check.setChecked(True)
        self.search_all_check.toggled.connect(self._on_search_all_toggled)
        collections_layout.addWidget(self.search_all_check)

        # Collection list (disabled when "search all" is checked)
        self.collections_list = QComboBox()
        self.collections_list.setEnabled(False)
        if self.workspace:
            collections = self.workspace.list_collections()
            self.collections_list.addItems(collections)
            self.collections_list.currentTextChanged.connect(self._on_collection_changed)
            # Populate fields initially (all collections by default)
            self._populate_field_dropdowns(collections)
        collections_layout.addWidget(QLabel("Or select specific collections:"))
        collections_layout.addWidget(self.collections_list)

        collections_group.setLayout(collections_layout)
        layout.addWidget(collections_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        search_btn = QPushButton("Search")
        search_btn.setDefault(True)
        search_btn.clicked.connect(self._perform_search)
        button_layout.addWidget(search_btn)

        cancel_btn = QPushButton("Close")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _add_criterion_row(self, parent_layout):
        """Add a new criterion row with dropdowns"""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 4, 0, 4)

        # Logic operator (AND/OR) - only show if not first row
        logic_combo = QComboBox()
        logic_combo.addItems(["AND", "OR"])
        if len(self.criteria_widgets) == 0:
            logic_combo.setVisible(False)  # Hide for first row
        row_layout.addWidget(logic_combo)

        # Field dropdown
        field_combo = QComboBox()
        field_combo.addItem("Select field...", None)
        # Populate with fields from all collections (we'll get them dynamically)
        row_layout.addWidget(QLabel("Field:"))
        row_layout.addWidget(field_combo)

        # Operator dropdown
        operator_combo = QComboBox()
        operator_combo.addItems(["=", "!=", ">", "<", ">=", "<=", "LIKE", "IS NULL", "IS NOT NULL"])
        row_layout.addWidget(QLabel("Operator:"))
        row_layout.addWidget(operator_combo)

        # Value input (hidden for IS NULL / IS NOT NULL)
        value_input = QLineEdit()
        value_input.setPlaceholderText("Value...")
        row_layout.addWidget(QLabel("Value:"))
        row_layout.addWidget(value_input)

        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(24, 24)
        remove_btn.clicked.connect(lambda: self._remove_criterion_row(row_widget))
        row_layout.addWidget(remove_btn)

        # Show/hide value input based on operator
        def on_operator_changed():
            op = operator_combo.currentText()
            value_input.setVisible(op not in ("IS NULL", "IS NOT NULL"))

        operator_combo.currentTextChanged.connect(on_operator_changed)

        parent_layout.addWidget(row_widget)
        self.criteria_widgets.append({
            "widget": row_widget,
            "logic": logic_combo,
            "field": field_combo,
            "operator": operator_combo,
            "value": value_input
        })

    def _remove_criterion_row(self, widget):
        """Remove a criterion row"""
        for i, criteria in enumerate(self.criteria_widgets):
            if criteria["widget"] == widget:
                # Hide the widget
                widget.setParent(None)
                widget.deleteLater()
                self.criteria_widgets.pop(i)
                # Show logic combo for first remaining row if any
                if self.criteria_widgets:
                    self.criteria_widgets[0]["logic"].setVisible(False)
                break

    def _populate_field_dropdowns(self, collections):
        """Populate field dropdowns with fields from collections"""
        all_fields = set()
        for collection_name in collections:
            try:
                info = self.workspace.get_collection_info(collection_name)
                if not info:
                    continue
                db_path = self.workspace.workspace_path / info.db_path
                store = CollectionStore(db_path)
                store.connect()
                try:
                    fields = store.list_fields()
                    for field in fields:
                        if field["key"] != "id":
                            field_label = field.get("alias", field.get("label", field["key"]))
                            all_fields.add((field["key"], field_label))
                finally:
                    store.close()
            except Exception:
                continue

        # Update all field dropdowns
        for criteria in self.criteria_widgets:
            field_combo = criteria["field"]
            current_data = field_combo.currentData()
            field_combo.clear()
            field_combo.addItem("Select field...", None)
            for field_key, field_label in sorted(all_fields, key=lambda x: x[1].lower()):
                field_combo.addItem(field_label, field_key)
            # Restore selection if possible
            if current_data:
                index = field_combo.findData(current_data)
                if index >= 0:
                    field_combo.setCurrentIndex(index)

    def _on_search_all_toggled(self, checked: bool):
        """Handle search all collections checkbox"""
        self.collections_list.setEnabled(not checked)
        # Update field dropdowns when collection selection changes
        if checked:
            collections = self.workspace.list_collections() if self.workspace else []
        else:
            selected = self.collections_list.currentText()
            collections = [selected] if selected else []
        self._populate_field_dropdowns(collections)

    def _on_collection_changed(self, text: str):
        """Handle collection selection change"""
        if not self.search_all_check.isChecked():
            self._populate_field_dropdowns([text] if text else [])

    def _perform_search(self):
        """Perform advanced search across collections"""
        # Check if using simple text search
        use_text_search = self.use_text_search.isChecked()
        text_query = self.text_search_input.text().strip() if use_text_search else ""

        # Build query from criteria
        criteria_query_parts = []
        for criteria in self.criteria_widgets:
            field_key = criteria["field"].currentData()
            operator = criteria["operator"].currentText()
            value = criteria["value"].text().strip()

            if not field_key:
                continue  # Skip if no field selected

            # Build condition
            if operator in ("IS NULL", "IS NOT NULL"):
                condition = f"{field_key} {operator}"
            elif operator == "LIKE":
                condition = f"{field_key} LIKE '%{value}%'"
            else:
                # Escape value for safety
                value_escaped = value.replace("'", "''")
                condition = f"{field_key} {operator} '{value_escaped}'"

            # Add logic operator if not first condition
            if criteria_query_parts:
                logic = criteria["logic"].currentText()
                criteria_query_parts.append(logic)

            criteria_query_parts.append(condition)

        base_query = " ".join(criteria_query_parts) if criteria_query_parts else ""

        # At least one search method must be provided
        if not text_query and not base_query:
            QMessageBox.warning(self, "Error", "Please enter a text search or add at least one field condition")
            return

        if not self.workspace:
            QMessageBox.warning(self, "Error", "Workspace not available")
            return

        # Get collections to search
        if self.search_all_check.isChecked():
            collections = self.workspace.list_collections()
        else:
            selected = self.collections_list.currentText()
            if not selected:
                QMessageBox.warning(self, "Error", "Please select a collection or enable 'Search all collections'")
                return
            collections = [selected]

        if not collections:
            QMessageBox.warning(self, "Error", "No collections found")
            return

        # Perform search
        self.results = []

        for collection_name in collections:
            try:
                # Get collection info
                info = self.workspace.get_collection_info(collection_name)
                if not info:
                    continue

                # Open collection
                db_path = self.workspace.workspace_path / info.db_path
                store = CollectionStore(db_path)
                store.connect()

                try:
                    # Get fields for query parser
                    fields = [f["key"] for f in store.list_fields()]

                    # Perform search
                    records = []
                    if use_text_search and text_query:
                        # Simple text search
                        records = store.simple_search(text_query)
                    elif base_query:
                        # Field-based search using query parser
                        from src.core.query_parser import QueryParser
                        parser = QueryParser(fields)
                        try:
                            filter_tree = parser.parse(base_query)
                            if filter_tree:
                                records = store.search_records(base_query, filter_tree=filter_tree)
                            else:
                                records = store.search_records(base_query)
                        except Exception:
                            # Fallback to simple search if parsing fails
                            records = store.simple_search(base_query)
                    else:
                        # No search criteria, get all records
                        records = store.list_records()

                    # Add collection info to each record
                    for record in records:
                        self.results.append({
                            "collection": collection_name,
                            "record": record
                        })

                finally:
                    store.close()

            except Exception as e:
                QMessageBox.warning(
                    self, "Search Error",
                    f"Error searching collection '{collection_name}':\n{str(e)}"
                )

        # Display results in separate modal
        if self.results:
            from src.ui.search_results_dialog import SearchResultsDialog
            results_dialog = SearchResultsDialog(self, self.results)
            results_dialog.exec()
        else:
            QMessageBox.information(self, "No Results", "No results found matching your search criteria.")

    def _apply_where_clause(self, records: list[dict], where_clause: str, fields: list[str]) -> list[dict]:
        """Apply WHERE clause filtering to records"""
        # Simple WHERE clause parsing - for complex SQL, this would need a proper parser
        # For now, support basic conditions like "field IS NOT NULL", "field = value", etc.
        filtered = []

        for record in records:
            # Simple evaluation - in production, use a proper SQL parser
            # This is a simplified version that handles basic cases
            try:
                # Replace field names with record values
                condition = where_clause
                for field in fields:
                    if field in record:
                        value = record[field]
                        # Escape value for string comparison
                        if isinstance(value, str):
                            escaped = value.replace("'", "''")
                            value_str = f"'{escaped}'"
                        else:
                            value_str = str(value)
                        condition = condition.replace(field, value_str)

                # Evaluate condition (very basic - not production ready)
                # In production, use a proper expression evaluator
                if self._evaluate_condition(condition, record):
                    filtered.append(record)
            except Exception:
                # If evaluation fails, skip this record
                continue

        return filtered

    def _apply_having_clause(self, records: list[dict], having_clause: str, fields: list[str]) -> list[dict]:
        """Apply HAVING clause (for aggregated results)"""
        # HAVING is typically used with GROUP BY, but for simplicity,
        # we'll apply it as a filter similar to WHERE
        return self._apply_where_clause(records, having_clause, fields)

    def _evaluate_condition(self, condition: str, record: dict) -> bool:
        """Evaluate a simple condition string"""
        # Very basic evaluation - handles IS NOT NULL, =, !=, >, <, etc.
        # This is a simplified version - in production, use a proper SQL parser

        condition = condition.strip()

        # IS NOT NULL
        if "IS NOT NULL" in condition.upper():
            field = condition.split()[0].strip()
            return field != "NULL" and field != "''"

        # IS NULL
        if "IS NULL" in condition.upper():
            field = condition.split()[0].strip()
            return field == "NULL" or field == "''"

        # Basic operators: =, !=, >, <, >=, <=
        for op in ["!=", ">=", "<=", "=", ">", "<"]:
            if op in condition:
                parts = condition.split(op, 1)
                if len(parts) == 2:
                    left = parts[0].strip().strip("'\"")
                    right = parts[1].strip().strip("'\"")

                    try:
                        # Try numeric comparison
                        left_num = float(left)
                        right_num = float(right)
                        if op == "=":
                            return left_num == right_num
                        elif op == "!=":
                            return left_num != right_num
                        elif op == ">":
                            return left_num > right_num
                        elif op == "<":
                            return left_num < right_num
                        elif op == ">=":
                            return left_num >= right_num
                        elif op == "<=":
                            return left_num <= right_num
                    except ValueError:
                        # String comparison
                        if op == "=":
                            return left == right
                        elif op == "!=":
                            return left != right

        # Default: if condition is not empty and not "0" or "false", return True
        return condition and condition.lower() not in ("0", "false", "null", "''")


