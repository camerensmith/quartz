"""Advanced search dialog with SQL operators and cross-collection search"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QLineEdit, QComboBox, QGroupBox, QCheckBox, QTextEdit,
    QMessageBox, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from src.core.workspace import Workspace
from src.core.collection_store import CollectionStore


class AdvancedSearchDialog(QDialog):
    """Dialog for advanced search across all collections with SQL operators"""
    
    def __init__(self, parent=None, workspace: Optional[Workspace] = None):
        super().__init__(parent)
        self.workspace = workspace
        self.results: List[Dict] = []  # List of {collection, record} dicts
        
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
        
        # Base search query
        base_group = QGroupBox("Base Search Query")
        base_layout = QVBoxLayout()
        self.base_query_input = QLineEdit()
        self.base_query_input.setPlaceholderText("Enter base search query (e.g., field:value or rating>7)")
        self.base_query_input.setToolTip(
            "Base search query using the standard syntax:\n"
            "- Simple: just type text\n"
            "- Field: field:value or field>value\n"
            "- Boolean: field1:value AND field2:value OR field3:value"
        )
        base_layout.addWidget(self.base_query_input)
        base_group.setLayout(base_layout)
        layout.addWidget(base_group)
        
        # SQL Operators (optional)
        operators_group = QGroupBox("SQL Operators (Optional)")
        operators_layout = QVBoxLayout()
        
        # WHERE clause
        where_layout = QHBoxLayout()
        where_layout.addWidget(QLabel("WHERE:"))
        self.where_input = QLineEdit()
        self.where_input.setPlaceholderText("Additional WHERE conditions (e.g., field IS NOT NULL)")
        where_layout.addWidget(self.where_input)
        operators_layout.addLayout(where_layout)
        
        # OR clause
        or_layout = QHBoxLayout()
        or_layout.addWidget(QLabel("OR:"))
        self.or_input = QLineEdit()
        self.or_input.setPlaceholderText("OR conditions (e.g., field:value OR field2:value2)")
        or_layout.addWidget(self.or_input)
        operators_layout.addLayout(or_layout)
        
        # HAVING clause
        having_layout = QHBoxLayout()
        having_layout.addWidget(QLabel("HAVING:"))
        self.having_input = QLineEdit()
        self.having_input.setPlaceholderText("HAVING conditions (e.g., COUNT(*) > 5)")
        having_layout.addWidget(self.having_input)
        operators_layout.addLayout(having_layout)
        
        operators_group.setLayout(operators_layout)
        layout.addWidget(operators_group)
        
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
        collections_layout.addWidget(QLabel("Or select specific collections:"))
        collections_layout.addWidget(self.collections_list)
        
        collections_group.setLayout(collections_layout)
        layout.addWidget(collections_group)
        
        # Results table
        results_group = QGroupBox("Search Results")
        results_layout = QVBoxLayout()
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Collection", "Record ID", "Preview"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SingleSelection)
        self.results_table.itemDoubleClicked.connect(self._on_result_double_clicked)
        results_layout.addWidget(self.results_table)
        
        # Results count
        self.results_label = QLabel("No results")
        results_layout.addWidget(self.results_label)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
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
    
    def _on_search_all_toggled(self, checked: bool):
        """Handle search all collections checkbox"""
        self.collections_list.setEnabled(not checked)
    
    def _perform_search(self):
        """Perform advanced search across collections"""
        base_query = self.base_query_input.text().strip()
        where_clause = self.where_input.text().strip()
        or_clause = self.or_input.text().strip()
        having_clause = self.having_input.text().strip()
        
        # At least base query or one operator must be provided
        if not base_query and not where_clause and not or_clause and not having_clause:
            QMessageBox.warning(self, "Error", "Please enter a base search query or at least one SQL operator")
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
                    # Build search query
                    search_query = base_query
                    
                    # Combine with OR if provided
                    if or_clause:
                        if search_query:
                            search_query = f"({search_query}) OR ({or_clause})"
                        else:
                            search_query = or_clause
                    
                    # Get fields for query parser
                    fields = [f["key"] for f in store.list_fields()]
                    
                    # Perform search
                    if search_query:
                        from src.core.query_parser import QueryParser
                        parser = QueryParser(fields)
                        try:
                            filter_tree = parser.parse(search_query)
                            if filter_tree:
                                records = store.search_records(search_query, filter_tree=filter_tree)
                            else:
                                records = store.search_records(search_query)
                        except Exception:
                            records = store.search_records(search_query)
                    else:
                        # No base query, get all records for WHERE/HAVING filtering
                        records = store.list_records()
                    
                    # Apply WHERE clause if provided
                    if where_clause:
                        records = self._apply_where_clause(records, where_clause, fields)
                    
                    # Apply HAVING clause if provided (for aggregated results)
                    if having_clause:
                        records = self._apply_having_clause(records, having_clause, fields)
                    
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
        
        # Display results
        self._display_results()
    
    def _apply_where_clause(self, records: List[Dict], where_clause: str, fields: List[str]) -> List[Dict]:
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
                            value_str = f"'{value.replace("'", "''")}'"
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
    
    def _apply_having_clause(self, records: List[Dict], having_clause: str, fields: List[str]) -> List[Dict]:
        """Apply HAVING clause (for aggregated results)"""
        # HAVING is typically used with GROUP BY, but for simplicity,
        # we'll apply it as a filter similar to WHERE
        return self._apply_where_clause(records, having_clause, fields)
    
    def _evaluate_condition(self, condition: str, record: Dict) -> bool:
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
    
    def _display_results(self):
        """Display search results in table"""
        self.results_table.setRowCount(len(self.results))
        
        for row, result in enumerate(self.results):
            collection = result["collection"]
            record = result["record"]
            record_id = record.get("id", "")
            
            # Collection name
            collection_item = QTableWidgetItem(collection)
            collection_item.setFlags(collection_item.flags() & ~Qt.ItemIsEditable)
            self.results_table.setItem(row, 0, collection_item)
            
            # Record ID
            id_item = QTableWidgetItem(str(record_id))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.results_table.setItem(row, 1, id_item)
            
            # Preview (first few field values)
            preview_parts = []
            for key, value in list(record.items())[:3]:  # First 3 fields
                if key != "id" and value:
                    preview_parts.append(f"{key}: {str(value)[:30]}")
            preview = " | ".join(preview_parts) if preview_parts else "(empty record)"
            
            preview_item = QTableWidgetItem(preview)
            preview_item.setFlags(preview_item.flags() & ~Qt.ItemIsEditable)
            self.results_table.setItem(row, 2, preview_item)
        
        self.results_table.resizeColumnsToContents()
        
        # Update results count
        count = len(self.results)
        self.results_label.setText(f"Found {count} result(s) across {len(set(r['collection'] for r in self.results))} collection(s)")
    
    def _on_result_double_clicked(self, item: QTableWidgetItem):
        """Handle double-click on result to open collection and record"""
        row = item.row()
        if row < len(self.results):
            result = self.results[row]
            collection_name = result["collection"]
            record_id = result["record"].get("id")
            
            # Call parent method to open this collection and record
            parent = self.parent()
            if parent and hasattr(parent, '_open_collection_and_record'):
                try:
                    parent._open_collection_and_record(collection_name, record_id)
                    self.accept()
                except Exception as e:
                    QMessageBox.warning(
                        self, "Error",
                        f"Failed to open collection and record:\n{str(e)}"
                    )
            else:
                QMessageBox.information(
                    self, "Result",
                    f"Collection: {collection_name}\nRecord ID: {record_id}\n\n"
                    f"Double-click to open this record in the main window."
                )

