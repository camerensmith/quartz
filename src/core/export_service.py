"""Export service for collections"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.collection_store import CollectionStore


class ExportService:
    """Handles exporting collections to various formats"""

    def __init__(self, store: CollectionStore):
        self.store = store

    def export_csv(self, file_path: Path, record_ids: list[int] | None = None,
                   include_headers: bool = True, delimiter: str = ",") -> bool:
        """Export records to CSV"""
        try:
            fields = self.store.list_fields()
            field_keys = [f["key"] for f in fields]

            # Get records
            if record_ids:
                records = [self.store.get_record(rid) for rid in record_ids]
                records = [r for r in records if r]  # Filter None
            else:
                records = self.store.list_records()

            # Write CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=delimiter)

                # Write headers
                if include_headers:
                    headers = [f["label"] for f in fields]
                    writer.writerow(headers)

                # Write records
                for record in records:
                    row = []
                    for field_key in field_keys:
                        value = record.get(field_key, "")
                        # Convert None to empty string
                        if value is None:
                            value = ""
                        # Format based on field type
                        field = next((f for f in fields if f["key"] == field_key), None)
                        if field:
                            value = self._format_value_for_csv(field, value)
                        row.append(str(value))
                    writer.writerow(row)

            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False

    def export_json(self, file_path: Path, record_ids: list[int] | None = None) -> bool:
        """Export records to JSON"""
        try:
            fields = self.store.list_fields()

            # Get records
            if record_ids:
                records = [self.store.get_record(rid) for rid in record_ids]
                records = [r for r in records if r]
            else:
                records = self.store.list_records()

            # Prepare export data
            export_data = {
                "export_date": datetime.now().isoformat(),
                "fields": fields,
                "record_count": len(records),
                "records": records
            }

            # Write JSON
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False

    def export_db(self, file_path: Path) -> bool:
        """Export database file (copy SQLite DB)"""
        try:
            import shutil
            shutil.copy2(self.store.db_path, file_path)
            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False

    def export_pack(self, file_path: Path) -> bool:
        """Export pack (DB + attachments as zip)"""
        try:
            import zipfile

            # Create zip file
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add database (use actual filename)
                db_filename = self.store.db_path.name
                zipf.write(self.store.db_path, db_filename)

                # Add attachments if they exist
                # Attachments are stored in workspace/collection_name/attachments
                # We need to find the collection directory from the workspace
                workspace_path = self.store.db_path.parent.parent  # db folder's parent
                db_name = self.store.db_path.stem  # collection name without .sqlite
                collection_dir = workspace_path / db_name
                attachments_dir = collection_dir / "attachments"

                if attachments_dir.exists():
                    for att_file in attachments_dir.rglob("*"):
                        if att_file.is_file():
                            arc_name = f"attachments/{att_file.relative_to(attachments_dir)}"
                            zipf.write(att_file, arc_name)

            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False

    def export_excel(self, file_path: Path, record_ids: list[int] | None = None,
                     include_headers: bool = True) -> bool:
        """Export records to Excel (.xlsx) using openpyxl directly"""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font

            fields = self.store.list_fields()
            field_keys = [f["key"] for f in fields]
            field_labels = [f["label"] for f in fields]

            # Get records
            if record_ids:
                records = [self.store.get_record(rid) for rid in record_ids]
                records = [r for r in records if r]  # Filter None
            else:
                records = self.store.list_records()

            # Create workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Records"

            # Write headers if requested
            if include_headers:
                header_row = field_labels
                ws.append(header_row)
                # Make header row bold
                for cell in ws[1]:
                    cell.font = Font(bold=True)

            # Write records
            for record in records:
                row = []
                for field_key, field in zip(field_keys, fields, strict=False):
                    value = record.get(field_key, "")
                    # Format value based on field type
                    formatted_value = self._format_value_for_excel(field, value)
                    row.append(formatted_value)
                ws.append(row)

            # Save workbook
            wb.save(file_path)

            return True
        except ImportError:
            print("openpyxl not installed. Install it with: pip install openpyxl")
            return False
        except Exception as e:
            print(f"Export error: {e}")
            return False

    def _format_value_for_excel(self, field: dict, value: Any) -> Any:
        """Format value for Excel export based on field type"""
        if value is None or value == "":
            return None  # Excel handles None as empty cell

        field_type = field.get("type", "text")

        if field_type == "checkbox":
            # Convert to boolean
            if isinstance(value, bool):
                return value
            value_str = str(value).lower()
            return value_str in ("true", "1", "yes", "on")
        elif field_type == "integer":
            try:
                return int(value)
            except (ValueError, TypeError):
                return str(value)
        elif field_type == "decimal":
            try:
                return float(value)
            except (ValueError, TypeError):
                return str(value)
        elif field_type in ("date", "datetime"):
            # Keep as string (ISO format) - Excel will recognize it
            return str(value)

        # Default: return as-is (openpyxl will handle basic types)
        return str(value)

    def _format_value_for_csv(self, field: dict, value: Any) -> str:
        """Format value for CSV export based on field type"""
        if value is None or value == "":
            return ""

        field_type = field.get("type", "text")

        if field_type == "checkbox":
            # Convert to string representation
            if isinstance(value, bool):
                return "true" if value else "false"
            value_str = str(value).lower()
            return "true" if value_str in ("true", "1", "yes", "on") else "false"
        elif field_type in ("date", "datetime"):
            # Keep ISO format
            return str(value)
        elif field_type == "integer":
            # Convert to int if possible
            try:
                return str(int(value)) if value else ""
            except (ValueError, TypeError):
                return str(value)
        elif field_type == "decimal":
            # Convert to float if possible
            try:
                return str(float(value)) if value else ""
            except (ValueError, TypeError):
                return str(value)

        # Default: return as string
        return str(value)
