# app/integrations/sheets_manager.py
from datetime import datetime
from typing import Dict, List, Optional
from oauth2client.service_account import ServiceAccountCredentials
import gspread

from app.config import GOOGLE_SHEETS_FOLDER_ID, GOOGLE_SERVICE_ACCOUNT_FILE
from app.db.models import Item, Checkout, AuditLog, User
from app.sheets.auth import get_credentials
from app.utils.logger import logger


class SheetsManager:
    def __init__(self):
        self.service_account_file = GOOGLE_SERVICE_ACCOUNT_FILE
        self.client = None
        self._sheet_cache: Dict[int, gspread.Spreadsheet] = {}
        self._sheet_to_header_len: Dict[str, int] = {
            "Items": 11,
            "Checkouts": 8,
            "Audit": 5,
            "Stats": 2,
        }
        self._default_format = {
            "textFormat": {"fontFamily": "Calibri", "fontSize": 11}
        }

    def connect(self):
        try:
            creds = get_credentials()
            self.client = gspread.authorize(creds)  # type: ignore
            logger.info("Connected to Google Sheets API")
            return True
        except Exception as e:
            logger.error(f"Google Sheets connection failed: {e}")
            logger.warning("Bot will continue without Sheets sync")
            return False

    def clear_cache(self, guild_id: Optional[int] = None):
        if guild_id:
            self._sheet_cache.pop(guild_id, None)
        else:
            self._sheet_cache.clear()

    async def get_sheet_for_guild(
        self, guild_id: int, sheet_id: str
    ) -> Optional[gspread.Spreadsheet]:
        if not self.client:
            return None

        if guild_id in self._sheet_cache:
            return self._sheet_cache[guild_id]

        try:
            spreadsheet = self.client.open_by_key(sheet_id)
            self._sheet_cache[guild_id] = spreadsheet
            return spreadsheet
        except Exception as e:
            logger.error(f"Failed to load sheet for guild {guild_id}: {e}")
            return None

    async def create_sheet_for_guild(
        self, guild_id: int, guild_name: str
    ) -> tuple[str, str]:
        if not self.client:
            raise Exception("Google Sheets client not connected")

        try:
            sheet_title = f"{guild_name} - Inventory Database"
            spreadsheet = self.client.create(sheet_title, GOOGLE_SHEETS_FOLDER_ID)

            sheet_id = spreadsheet.id
            sheet_url = spreadsheet.url

            self._sheet_cache[guild_id] = spreadsheet

            await self._initialize_sheet_structure(spreadsheet, guild_name)

            logger.info(f"Created Google Sheet for guild '{guild_name}': {sheet_url}")
            return sheet_id, sheet_url

        except Exception as e:
            logger.error(f"Failed to create sheet for guild '{guild_name}': {e}")
            raise

    async def make_sheet_public(self, spreadsheet: gspread.Spreadsheet) -> bool:
        try:
            spreadsheet.share(None, perm_type="anyone", role="reader")  # type: ignore
            return True
        except Exception as e:
            logger.warning(f"Could not make sheet public: {e}")
            return False

    def _apply_default_font(self, sheet: gspread.Worksheet, num_cols: int):
        col_letter = _get_column_letter(num_cols)
        sheet.format(f"A:{col_letter}", self._default_format)

    def _auto_resize_columns(self, spreadsheet: gspread.Spreadsheet, sheet: gspread.Worksheet, num_cols: int):
        try:
            sheet.columns_auto_resize(0, num_cols)
        except Exception as e:
            logger.warning(f"Could not auto-resize columns for '{sheet.title}': {e}")

    async def _initialize_sheet_structure(
        self, spreadsheet: gspread.Spreadsheet, guild_name: str
    ):  
        sheets_to_create = ["Items", "Active Checkouts", "Audit Log", "Stats"]
        for sheet_name in sheets_to_create:
            try:
                spreadsheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)

        await self._setup_items_sheet(spreadsheet)
        await self._setup_checkouts_sheet(spreadsheet)
        await self._setup_audit_sheet(spreadsheet)
        await self._setup_stats_sheet(spreadsheet, guild_name)

        if spreadsheet.sheet1.title == "Sheet1":
            spreadsheet.del_worksheet(spreadsheet.sheet1)

    async def _setup_items_sheet(self, spreadsheet: gspread.Spreadsheet):
        sheet = spreadsheet.worksheet("Items")

        headers = [
            "Item ID", "Item Name", "Total Qty", "Available",
            "Checked Out", "Location", "Subteam", "Point of Contact",
            "Purchase Order", "Description", "Created At",
        ]

        col_end = _get_column_letter(len(headers))

        sheet.update(f"A1:{col_end}1", [headers])  # type: ignore
        sheet.format(f"A1:{col_end}1", {
            "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9},
            "textFormat": {
                "bold": True,
                "fontFamily": "Calibri",
                "fontSize": 11,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            },
            "horizontalAlignment": "CENTER",
        })
        sheet.freeze(rows=1)
        self._apply_default_font(sheet, len(headers))
        self._auto_resize_columns(spreadsheet, sheet, len(headers))

    async def _setup_checkouts_sheet(self, spreadsheet: gspread.Spreadsheet):
        sheet = spreadsheet.worksheet("Active Checkouts")

        headers = [
            "Checkout ID", "Item Name", "User", "Quantity",
            "Checked Out", "Expected Return", "Days Out", "Notes",
        ]

        col_end = _get_column_letter(len(headers))

        sheet.update(f"A1:{col_end}1", [headers])  # type: ignore
        sheet.format(f"A1:{col_end}1", {
            "backgroundColor": {"red": 0.9, "green": 0.6, "blue": 0.2},
            "textFormat": {
                "bold": True,
                "fontFamily": "Calibri",
                "fontSize": 11,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            },
            "horizontalAlignment": "CENTER",
        })
        sheet.freeze(rows=1)
        self._apply_default_font(sheet, len(headers))
        self._auto_resize_columns(spreadsheet, sheet, len(headers))

    async def _setup_audit_sheet(self, spreadsheet: gspread.Spreadsheet):
        sheet = spreadsheet.worksheet("Audit Log")

        headers = ["Timestamp", "User", "Action", "Item ID", "Details"]

        col_end = _get_column_letter(len(headers))

        sheet.update(f"A1:{col_end}1", [headers])  # type: ignore
        sheet.format(f"A1:{col_end}1", {
            "backgroundColor": {"red": 0.5, "green": 0.5, "blue": 0.5},
            "textFormat": {
                "bold": True,
                "fontFamily": "Calibri",
                "fontSize": 11,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            },
            "horizontalAlignment": "CENTER",
        })
        sheet.freeze(rows=1)
        self._apply_default_font(sheet, len(headers))
        self._auto_resize_columns(spreadsheet, sheet, len(headers))

    async def _setup_stats_sheet(self, spreadsheet: gspread.Spreadsheet, guild_name: str):
        sheet = spreadsheet.worksheet("Stats")

        sheet.update("A1:B1", [[f"{guild_name} - Inventory Statistics", ""]])  # type: ignore
        sheet.format("A1:B1", {
            "backgroundColor": {"red": 0.3, "green": 0.7, "blue": 0.3},
            "textFormat": {
                "bold": True,
                "fontFamily": "Calibri",
                "fontSize": 14,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            },
            "horizontalAlignment": "CENTER",
        })
        sheet.merge_cells("A1:B1")

        stats_labels = [
            "Total Items",
            "Total Quantity",
            "Items Checked Out",
            "Active Checkouts",
            "Utilization Rate",
            "",
            "Last Updated",
        ]

        label_rows = [[label] for label in stats_labels]
        sheet.update(f"A2:A{1 + len(stats_labels)}", label_rows)  # type: ignore

        sheet.format("A:A", {
            "textFormat": {"bold": True, "fontFamily": "Calibri", "fontSize": 11}
        })
        self._apply_default_font(sheet, 2)
        self._auto_resize_columns(spreadsheet, sheet, 2)

    async def sync_items(self, guild_id: int, sheet_id: str, items: List[Item], usernames: dict[int, str]):
        spreadsheet = await self.get_sheet_for_guild(guild_id, sheet_id)
        if not spreadsheet:
            logger.warning(f"Could not get spreadsheet for guild {guild_id}")
            return

        try:
            sheet = spreadsheet.worksheet("Items")
            num_cols = self._sheet_to_header_len["Items"]

            rows = []
            for item in items:
                rows.append([
                    item.id,
                    item.item_name,
                    item.quantity_total,
                    item.quantity_available,
                    item.quantity_checked_out,
                    item.location,
                    item.subteam.value if hasattr(item.subteam, "value") else item.subteam,
                    usernames.get(item.point_of_contact, f"Unknown ({item.point_of_contact})"),
                    item.purchase_order,
                    item.description or "",
                    item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
                ])

            if sheet.row_count > 1:
                sheet.batch_clear([f"A2:{_get_column_letter(num_cols)}{sheet.row_count}"])

            if rows:
                sheet.update(
                    f"A2:{_get_column_letter(num_cols)}{len(rows) + 1}",
                    rows,  # type: ignore
                )

            self._auto_resize_columns(spreadsheet, sheet, num_cols)
            logger.info(f"Synced {len(items)} items for guild {guild_id}")

        except Exception as e:
            logger.error(f"Failed to sync items for guild {guild_id}: {e}")

    async def sync_checkouts(
        self, guild_id: int, sheet_id: str, checkouts: List[Checkout], items_map: dict, usernames: dict[int, str]
    ):
        spreadsheet = await self.get_sheet_for_guild(guild_id, sheet_id)
        if not spreadsheet:
            logger.warning(f"Could not get spreadsheet for guild {guild_id}")
            return

        try:
            sheet = spreadsheet.worksheet("Active Checkouts")
            num_cols = self._sheet_to_header_len["Checkouts"]

            rows = []
            overdue_rows = []
            for i, checkout in enumerate(checkouts):
                item_name = items_map.get(checkout.item_id, "Unknown Item")
                days_out = checkout.days_checked_out

                rows.append([
                    checkout.id,
                    item_name,
                    usernames.get(checkout.user_id, f"Unknown ({checkout.user_id})"),
                    checkout.quantity,
                    checkout.checked_out_at.strftime("%Y-%m-%d %H:%M"),
                    checkout.expected_return_date.strftime("%Y-%m-%d")
                    if checkout.expected_return_date
                    else "N/A",
                    days_out,
                    checkout.notes or "",
                ])

                if checkout.is_overdue:
                    overdue_rows.append(i + 2)

            last_col = _get_column_letter(num_cols)

            if sheet.row_count > 1:
                sheet.batch_clear([f"A2:{last_col}{sheet.row_count}"])

            if rows:
                sheet.update(
                    f"A2:{last_col}{len(rows) + 1}",
                    rows,  # type: ignore
                )

                for row_num in overdue_rows:
                    sheet.format(f"A{row_num}:H{row_num}", {
                        "backgroundColor": {"red": 1, "green": 0.8, "blue": 0.8}
                    })

            self._auto_resize_columns(spreadsheet, sheet, num_cols)
            logger.info(f"Synced {len(checkouts)} checkouts for guild {guild_id}")

        except Exception as e:
            logger.error(f"Failed to sync checkouts for guild {guild_id}: {e}")

    async def sync_audit_log(self, guild_id: int, sheet_id: str, logs: List[AuditLog], usernames: dict[int, str]):
        spreadsheet = await self.get_sheet_for_guild(guild_id, sheet_id)
        if not spreadsheet:
            logger.warning(f"Could not get spreadsheet for guild {guild_id}")
            return

        try:
            sheet = spreadsheet.worksheet("Audit Log")
            num_cols = self._sheet_to_header_len["Audit"]

            rows = []
            for log in logs:
                rows.append([
                    log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    usernames.get(log.user_id, f"Unknown ({log.user_id})"),
                    log.action,
                    str(log.item_id) if log.item_id else "N/A",
                    log.details,
                ])

            last_col = _get_column_letter(num_cols)

            if sheet.row_count > 1:
                sheet.batch_clear([f"A2:{last_col}{sheet.row_count}"])

            if rows:
                sheet.update(
                    f"A2:{last_col}{len(rows) + 1}",
                    rows,  # type: ignore
                )

            self._auto_resize_columns(spreadsheet, sheet, num_cols)
            logger.info(f"Synced {len(rows)} audit log entries for guild {guild_id}")

        except Exception as e:
            logger.error(f"Failed to sync audit log for guild {guild_id}: {e}")

    async def append_audit_log(self, guild_id: int, sheet_id: str, log_entry: AuditLog):
        spreadsheet = await self.get_sheet_for_guild(guild_id, sheet_id)
        if not spreadsheet:
            return

        try:
            sheet = spreadsheet.worksheet("Audit Log")

            row = [
                log_entry.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                f"User ID: {log_entry.user_id}",
                log_entry.action,
                str(log_entry.item_id) if log_entry.item_id else "N/A",
                log_entry.details,
            ]

            sheet.append_row(row)

        except Exception as e:
            logger.error(f"Failed to append audit log for guild {guild_id}: {e}")

    async def update_stats(self, guild_id: int, sheet_id: str, stats: dict):
        spreadsheet = await self.get_sheet_for_guild(guild_id, sheet_id)
        if not spreadsheet:
            return

        try:
            sheet = spreadsheet.worksheet("Stats")

            sheet.update("B2:B8", [
                [stats.get("total_items", 0)],
                [stats.get("total_quantity", 0)],
                [stats.get("checked_out_quantity", 0)],
                [stats.get("active_checkouts", 0)],
                [f"{stats.get('utilization_rate', 0):.1f}%"],
                [""],
                [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ])  # type: ignore

            self._auto_resize_columns(spreadsheet, sheet, 2)

        except Exception as e:
            logger.error(f"Failed to update stats for guild {guild_id}: {e}")

    async def full_sync(self, db_manager, guild_id: int):
        settings = await db_manager.get_guild_settings(guild_id)
        if not settings or not settings.google_sheet_id:
            logger.warning(f"No Google Sheet configured for guild {guild_id}")
            return

        logger.info(f"Starting full Google Sheets sync for guild {guild_id}...")

        items = await db_manager.search_items(guild_id)
        checkouts = await db_manager.get_active_checkouts(guild_id)
        audit_logs = await db_manager.get_audit_log(guild_id, limit=100)

        all_user_ids = (
            [item.point_of_contact for item in items]
            + [co.user_id for co in checkouts]
            + [log.user_id for log in audit_logs]
        )
        users = await db_manager.get_users_batch(all_user_ids)
        usernames = {uid: user.username for uid, user in users.items()}

        items_map = {item.id: item.item_name for item in items}

        await self.sync_items(guild_id, settings.google_sheet_id, items, usernames)
        await self.sync_checkouts(guild_id, settings.google_sheet_id, checkouts, items_map, usernames)
        await self.sync_audit_log(guild_id, settings.google_sheet_id, audit_logs, usernames)

        total_qty = sum(item.quantity_total for item in items)
        checked_out_qty = sum(item.quantity_checked_out for item in items)

        stats = {
            "total_items": len(items),
            "total_quantity": total_qty,
            "checked_out_quantity": checked_out_qty,
            "active_checkouts": len(checkouts),
            "utilization_rate": (checked_out_qty / total_qty * 100) if total_qty else 0,
        }
        await self.update_stats(guild_id, settings.google_sheet_id, stats)

        logger.info("Google Sheets full sync complete")


def _get_column_letter(n: int):
    result = ""
    while n > 0:
        n -= 1
        result = chr(65 + (n % 26)) + result
        n //= 26
    return result
