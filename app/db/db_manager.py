
from typing import List, Optional

import asyncpg
from app.db.models import AuditLog, Checkout, CheckoutRequest, CreateItemRequest, InventoryStats, Item, UpdateItemRequest, User
from app.error.exceptions import DatabaseNotInitializedError
from app.utils.logger import logger

class DatabaseManager:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool = None

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

    async def get_user(self, user_id: int) -> Optional[User]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * from users where user_id = $1",
                user_id
            )
            return User.from_record(row) if row else None
        
    async def set_admin(self, user_id: int, is_admin: bool):
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_admin = $2 WHERE user_id = $1",
                user_id, is_admin
            )

    # ===== Item =====

    async def add_item(self, request: CreateItemRequest, added_by: int) -> Item:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO items (
                    item_name, quantity_total, quantity_available,
                    location, subteam, point_of_contact, purchase_order, description
                )
                VALUES ($1, $2, $2, $3, $4, $5, $6, $7)
                RETURNING *
            """,
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
                added_by, "add_item", item.id,
                f"Added {request.quantity}x {request.item_name}"
            )

            return item

    async def get_item(self, item_id: int) -> Optional[Item]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * from items WHERE id = $1",
                item_id
            )    
            return Item.from_record(row) if row else None

    async def search_items(
        self,
        search: Optional[str] = None,
        subteam: Optional[str] = None,
        location: Optional[str] = None
    ) -> List[Item]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            query = 'SELECT * FROM items WHERE 1=1'
            params = []
            param_count = 0
            
            if search:
                param_count += 1
                query += f' AND item_name ILIKE ${param_count}'
                params.append(f'%{search}%')
            
            if subteam:
                param_count += 1
                query += f' AND subteam = ${param_count}'
                params.append(subteam)
            
            if location:
                param_count += 1
                query += f' AND location = ${param_count}'
                params.append(location)
            
            query += ' ORDER BY item_name'
            
            rows = await conn.fetch(query, *params)
            return [Item.from_record(row) for row in rows]    

    async def update_item(
        self,
        item_id: int,
        request: UpdateItemRequest,
        updated_by: int
    ) -> Optional[Item]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            updates = request.model_dump(exclude_unset=True, exclude_none=True)

            if not updates:
                return await self.get_item(item_id)
            
            set_clauses = []
            params = [item_id]
            param_count = 1

            for k, v in updates.items():
                param_count += 1
                set_clauses.append(f"{k} = ${param_count}")
                params.append(v)

            query = f"UPDATE items SET {', '.join(set_clauses)} WHERE id = $1 RETURNING *"
            row = await conn.fetchrow(query, *params)

            if row:
                item = Item.from_record(row)

                changes = ', '.join(f"{k}={v}" for k, v in updates.items())
                await self.log_action(
                    updated_by, "edit_item", item.id,
                    f"Updated: {changes}"
                )

                return item
            
        return None
    
    async def delete_item(self, item_id: int, deleted_by: int) -> bool:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            item = await self.get_item(item_id)

            if not item:
                return False
            
            await conn.execute("DELETE from items WHERE id = $1", item_id)

            await self.log_action(
                deleted_by, "delete_item", item_id,
                f"Deleted {item.item_name}"
            )

            return True

    # ===== Checkout =====

    async def checkout_item(
        self,
        request: CheckoutRequest,
        user_id: int
    ):
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                item_row = await conn.fetchrow(
                    "SELECT quantity_available, item_name FROM items WHERE id = $1 FOR UPDATE",
                    request.item_id
                )

                if not item_row or item_row["quantity_available"] < request.quantity:
                    return None
                
                checkout_row = await conn.fetchrow("""
                        INSERT INTO checkouts (
                            item_id, user_id, quantity, expected_return_date, notes
                        )
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING *
                    """,
                    request.item_id,
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
                    user_id, "checkout", request.item_id,
                    f"Checked out {request.quantity}x {item_row["item_name"]}"
                )

                return checkout
            
    async def return_item(self, checkout_id: int, returned_by: int) -> bool:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                checkout_row = await conn.fetchrow("""
                    SELECT c.*, i.item_name
                    FROM checkouts c
                    JOIN items i ON c.items_id = i.id
                    WHERE c.id = $1 AND c.returned_at IS NULL
                    FOR UPDATE
                """, checkout_id)

                if not checkout_row:
                    return False
                
                await conn.execute("""
                    UPDATE checkouts
                    SET returned_at = NOW()
                    WHERE id = $1
                """, checkout_id)

                await conn.execute("""
                    UPDATE items
                    SET quantity_available = quantity_available + $2
                    WHERE id = $1
                """, checkout_row["item_id"], checkout_row["quantity"])

                await self.log_action(
                    returned_by, "return", checkout_row["item_id"],
                    f"Returned {checkout_row["quantity"]}x {checkout_row["item_name"]}"
                )

                return True

    async def get_active_checkouts(self, user_id: Optional[int] = None) -> List[Checkout]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            if user_id:
                rows = await conn.fetch("""
                    SELECT * FROM checkouts
                    WHERE returned_at IS NULL
                    ORDER BY checked_out_at DESC
                """, user_id)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM checkouts
                    WHERE returned_at IS NULL
                    ORDER BY checkout_out_at DESC
                """)

            return [Checkout.from_record(row) for row in rows]
        
    async def get_item_checkouts(self, item_id: int, active_only: bool = False) -> List[Checkout]:
        if not self.pool:
            raise DatabaseNotInitializedError()

        async with self.pool.acquire() as conn:
            if active_only:
                query = """
                    SELECT * FROM checkouts
                    WHERE item_id = $1 AND returned_at IS NULL
                    ORDER BY checked_out_at DESC
                """
            else:
                query = """
                    SELECT * FROM checkouts
                    WHERE item_id = $1
                    ORDER BY checked_out_at DESC
                """

            rows = await conn.fetch(query, item_id)
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
        user_id: int,
        action: str,
        item_id: Optional[int],
        details: str
    ):
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO audit_log (user_id, action, item_id, details)
                VALUES ($1, $2, $3, $4)
            """, user_id, action, item_id, details)

    async def get_audit_log(self, limit: int = 50) -> List[AuditLog]:
        if not self.pool:
            raise DatabaseNotInitializedError()
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM audit_log
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)
            return [AuditLog.from_record(row) for row in rows]

