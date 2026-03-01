
import asyncio
from typing import List, Optional

import asyncpg
from app.db.models import AuditLog, Checkout, CheckoutRequest, CreateItemRequest, GuildPermission, GuildSettings, InventoryStats, Item, UpdateItemRequest, User
from app.error.exceptions import DatabaseNotInitializedError
from app.sheets.sheets_manager import SheetsManager
from app.utils.logger import logger

class DatabaseManager:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool = None
        self.sheets_manager = None

    def set_sheets_manager(self, sheets_manager: SheetsManager):
        self.sheets_manager = sheets_manager

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        
        logger.info("Connected to database")

    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("Disconnected from database")

    # ===== USER =====

    async def ensure_user_exists(self, user_id: int, username: str):
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username)
                VALUES ($1, $2)
                ON CONFLICT (user_id)
                DO UPDATE SET username = $2
            """, user_id, username)

    async def ensure_guild_member(self, guild_id: int, user_id: int, username: str):
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            await self.ensure_user_exists(user_id, username)

            await conn.execute("""
                INSERT INTO guild_permissions (user_id, guild_id, is_admin)
                VALUES ($1, $2, FALSE)
                ON CONFLICT (guild_id, user_id) DO NOTHING
            """, user_id, guild_id)

    async def get_user(self, user_id: int) -> Optional[User]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * from users where user_id = $1",
                user_id
            )
            return User.from_record(row) if row else None

    async def get_user_permissions(self, guild_id: int, user_id: int) -> Optional[GuildPermission]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * from guild_permissions where user_id = $1 AND guild_id = $2",
                user_id, guild_id
            )
            return GuildPermission.from_record(row) if row else None

    async def is_admin(self, guild_id: int, user_id: int) -> bool:
        perms = await self.get_user_permissions(guild_id, user_id)
        return perms.is_admin if perms else False

    async def set_admin(self, guild_id: int, user_id: int, is_admin: bool):
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                    INSERT INTO guild_permissions (guild_id, user_id, is_admin)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id, user_id)
                    DO UPDATE SET is_admin = $3, updated_at = NOW()
                """, 
                guild_id, user_id, is_admin
            )

    async def get_guild_admins(self, guild_id: int) -> List[GuildPermission]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT gp.*, u.username
                FROM guild_permissions gp
                JOIN users u ON gp.user_id = u.user_id
                WHERE gp.guild_id = $1 AND gp.is_admin = TRUE
                ORDER BY u.username
            ''', guild_id)
            return [GuildPermission.from_record(row) for row in rows]

    # ===== Guild Settings =====
    async def get_guild_settings(self, guild_id: int) -> Optional[GuildSettings]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM guild_settings WHERE guild_id = $1",
                guild_id
            )
            return GuildSettings.from_record(row) if row else None
    
    async def upsert_guild_settings(
        self,
        guild_id: int,
        guild_name: str,
        google_sheet_id: Optional[str] = None,
        google_sheet_url: Optional[str] = None
    ) -> GuildSettings:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO guild_settings (guild_id, guild_name, google_sheet_id, google_sheet_url)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id)
                DO UPDATE SET 
                    guild_name = $2,
                    google_sheet_id = COALESCE($3, guild_settings.google_sheet_id),
                    google_sheet_url = COALESCE($4, guild_settings.google_sheet_url),
                    updated_at = NOW()
                RETURNING *
            """, guild_id, guild_name, google_sheet_id, google_sheet_url)
            
            return GuildSettings.from_record(row)
    
    async def set_guild_sheet(self, guild_id: int, sheet_id: str, sheet_url: str):
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO guild_settings (guild_id, guild_name, google_sheet_id, google_sheet_url)
                VALUES ($1, 'Unknown', $2, $3)
                ON CONFLICT (guild_id)
                DO UPDATE SET google_sheet_id = $2, google_sheet_url = $3, updated_at = NOW()
            """, guild_id, sheet_id, sheet_url)

    # ===== Item =====

    async def add_item(self, request: CreateItemRequest, guild_id, added_by: int) -> Item:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO items (
                    guild_id, item_name, quantity_total, quantity_available,
                    location, subteam, point_of_contact, purchase_order, description
                )
                VALUES ($1, $2, $3, $3, $4, $5, $6, $7, $8)
                RETURNING *
            """,
                guild_id,
                request.item_name,
                request.quantity,
                request.location,
                request.subteam,
                request.point_of_contact,
                request.purchase_order,
                request.description
            )

            item = Item.from_record(row)

            await self.log_action(
                guild_id, added_by, "add_item", item.id,
                f"Added {request.quantity}x {request.item_name}"
            )

            self.trigger_sheets_sync(guild_id)

            return item

    async def get_item(self, guild_id: int, item_id: int) -> Optional[Item]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * from items WHERE id = $1 AND guild_id = $2",
                item_id, guild_id
            )    
            return Item.from_record(row) if row else None

    async def search_items(
        self,
        guild_id: int,
        search: Optional[str] = None,
        subteam: Optional[str] = None,
        location: Optional[str] = None
    ) -> List[Item]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            query = 'SELECT * FROM items WHERE guild_id = $1'
            params = [guild_id]
            param_count = 1
            
            if search:
                param_count += 1
                query += f' AND item_name ILIKE ${param_count}'
                params.append(f'%{search}%') # type: ignore
            
            if subteam:
                param_count += 1
                query += f' AND subteam = ${param_count}'
                params.append(subteam) # type: ignore
            
            if location:
                param_count += 1
                query += f' AND location = ${param_count}'
                params.append(location) # type: ignore
            
            query += ' ORDER BY item_name'
            
            rows = await conn.fetch(query, *params)
            return [Item.from_record(row) for row in rows]    

    async def update_item(
        self,
        guild_id: int,
        item_id: int,
        request: UpdateItemRequest,
        updated_by: int
    ) -> Optional[Item]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            updates = request.model_dump(exclude_unset=True, exclude_none=True)

            if not updates:
                return await self.get_item(guild_id, item_id)
            
            set_clauses = []
            params = [item_id, guild_id]
            param_count = 2

            for k, v in updates.items():
                param_count += 1
                set_clauses.append(f"{k} = ${param_count}")
                params.append(v)

            query = f"UPDATE items SET {', '.join(set_clauses)} WHERE id = $1 AND guild_id = $2 RETURNING *"
            row = await conn.fetchrow(query, *params)

            if row:
                item = Item.from_record(row)

                changes = ', '.join(f"{k}={v}" for k, v in updates.items())
                await self.log_action(
                    guild_id, updated_by, "edit_item", item.id,
                    f"Updated: {changes}"
                )

                self.trigger_sheets_sync(guild_id)

                return item
            
        return None
    
    async def delete_item(self, guild_id: int, item_id: int, deleted_by: int) -> bool:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            item = await self.get_item(guild_id, item_id)

            if not item:
                return False
            
            # Need to log before deleting to avoid violating fkey constraint
            await self.log_action(
                guild_id, deleted_by, "delete_item", item_id,
                f"Deleted {item.item_name}"
            )

            await conn.execute("DELETE from items WHERE id = $1", item_id)

            self.trigger_sheets_sync(guild_id)

            return True

    # ===== Checkout =====

    async def checkout_item(
        self,
        request: CheckoutRequest,
        guild_id: int,
        user_id: int
    ):
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                item_row = await conn.fetchrow(
                    "SELECT quantity_available, item_name FROM items WHERE id = $1 AND guild_id = $2 FOR UPDATE",
                    request.item_id, guild_id
                )

                if not item_row or item_row["quantity_available"] < request.quantity:
                    return None
                
                checkout_row = await conn.fetchrow("""
                        INSERT INTO checkouts (
                            item_id, guild_id, user_id, quantity, expected_return_date, notes
                        )
                        VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING *
                    """,
                    request.item_id,
                    guild_id,
                    user_id,
                    request.quantity,
                    request.expected_return_date,
                    request.notes
                )

                await conn.execute("""
                    UPDATE items
                    SET quantity_available = quantity_available - $2
                    WHERE id = $1
                """, request.item_id, request.quantity)

                checkout = Checkout.from_record(checkout_row)

            await self.log_action(
                guild_id, user_id, "checkout", request.item_id,
                f"Checked out {request.quantity}x {item_row["item_name"]}"
            )

            self.trigger_sheets_sync(guild_id)

            return checkout
            
    async def return_item(self, checkout_id: int, guild_id: int, returned_by: int) -> bool:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                checkout_row = await conn.fetchrow("""
                    SELECT c.*, i.item_name
                    FROM checkouts c
                    JOIN items i ON c.item_id = i.id
                    WHERE c.id = $1 AND c.guild_id = $2 AND c.returned_at IS NULL
                    FOR UPDATE
                """, checkout_id, guild_id)

                if not checkout_row:
                    return False
                
                await conn.execute("""
                    UPDATE checkouts
                    SET returned_at = NOW()
                    WHERE id = $1 AND guild_id = $2
                """, checkout_id, guild_id)

                await conn.execute("""
                    UPDATE items
                    SET quantity_available = quantity_available + $3
                    WHERE id = $1 AND guild_id = $2
                """, checkout_row["item_id"], guild_id, checkout_row["quantity"])

            await self.log_action(
                guild_id, returned_by, "return", checkout_row["item_id"],
                f"Returned {checkout_row["quantity"]}x {checkout_row["item_name"]}"
            )

            self.trigger_sheets_sync(guild_id)

            return True

    async def get_active_checkouts(self, guild_id: int, user_id: Optional[int] = None) -> List[Checkout]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            if user_id:
                rows = await conn.fetch("""
                    SELECT * FROM checkouts
                    WHERE guild_id = $1 AND user_id = $2 AND returned_at IS NULL
                    ORDER BY checked_out_at DESC
                """, guild_id, user_id)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM checkouts
                    WHERE guild_id = $1 AND returned_at IS NULL
                    ORDER BY checked_out_at DESC
                """, guild_id)

            return [Checkout.from_record(row) for row in rows]
        
    async def get_item_checkouts(self, guild_id: int, item_id: int, active_only: bool = False) -> List[Checkout]:
        if not self.pool:
            raise DatabaseNotInitializedError()

        async with self.pool.acquire() as conn:
            if active_only:
                query = """
                    SELECT * FROM checkouts
                    WHERE item_id = $1 AND guild_id = $2 AND returned_at IS NULL
                    ORDER BY checked_out_at DESC
                """
            else:
                query = """
                    SELECT * FROM checkouts
                    WHERE item_id = $1 AND guild_id = $2
                    ORDER BY checked_out_at DESC
                """

            rows = await conn.fetch(query, item_id, guild_id)
            return [Checkout.from_record(row) for row in rows]
        
    # ===== Stats =====

    async def get_stats(self) -> InventoryStats:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(DISTINCT id) as total_items,
                    COALESCE(SUM(quantity_total), 0) as total_quantity,
                    COALESCE(SUM(quantity_total - quantity_available), 0) as checked_out_quantity,
                    (SELECT COUNT(*) FROM checkouts WHERE returned_at IS NULL) as active_checkouts,
                    COUNT(DISTINCT subteam) as unique_subteams
                FROM items
            """)

            return InventoryStats(**dict(row))
        
    # ===== Audit Log =====

    async def log_action(
        self,
        guild_id: int,
        user_id: int,
        action: str,
        item_id: Optional[int],
        details: str
    ):
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            row = await conn.execute("""
                INSERT INTO audit_log (guild_id, user_id, action, item_id, details)
                VALUES ($1, $2, $3, $4, $5)
            """, guild_id, user_id, action, item_id, details)
                

    async def get_audit_log(self, guild_id: int, limit: int = 50) -> List[AuditLog]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM audit_log
                WHERE guild_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, guild_id, limit)
            return [AuditLog.from_record(row) for row in rows]
        
    # ===== Spreadsheets =====
    def trigger_sheets_sync(self, guild_id: int):
        if self.sheets_manager and self.sheets_manager.client:
            asyncio.create_task(self.sheets_manager.full_sync(self, guild_id))

