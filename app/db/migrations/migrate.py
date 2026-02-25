import asyncio
import sys
from pathlib import Path
from typing import List, Final

import asyncpg
from app.config import DB_URL
from app.utils.logger import logger

class MigrationManager:
    def __init__(self, database_url: str) -> None:
        self.database_url: str = database_url
        self.migrations_dir: Final[Path] = Path(__file__).parent
    
    async def init_migrations_table(self, conn: asyncpg.Connection) -> None:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')
        logger.info("Migrations table initialized")
    
    async def get_applied_migrations(self, conn: asyncpg.Connection) -> List[str]:
        rows = await conn.fetch(
            'SELECT migration_name FROM schema_migrations ORDER BY id'
        )
        return [dict(row)['migration_name'] for row in rows]
    
    def get_all_migration_files(self) -> List[Path]:
        return sorted(self.migrations_dir.glob('*.sql'))
    
    def get_pending_migrations(self, applied: List[str]) -> List[Path]:
        all_migrations: List[Path] = self.get_all_migration_files()
        return [m for m in all_migrations if m.name not in applied]
    
    async def apply_migration(self, conn: asyncpg.Connection, migration_path: Path) -> None:
        logger.info(f"Applying {migration_path.name}...")
        
        try:
            sql_content: str = migration_path.read_text(encoding='utf-8')
            statements: List[str] = []
            
            for statement in sql_content.split(';'):
                lines: List[str] = []
                for line in statement.split('\n'):
                    if '--' in line:
                        line = line[:line.index('--')]
                    lines.append(line)
                
                clean_statement: str = '\n'.join(lines).strip()
                if clean_statement:
                    statements.append(clean_statement)
            
            for stmt in statements:
                await conn.execute(stmt)
            
            await conn.execute(
                'INSERT INTO schema_migrations (migration_name) VALUES ($1)',
                migration_path.name
            )
            logger.info(f"Applied successfully: {migration_path.name}")
            
        except Exception as e:
            logger.error(f"Failed to apply {migration_path.name}: {e}")
            raise
    
    async def run_migrations(self) -> None:
        conn: asyncpg.Connection = await asyncpg.connect(self.database_url)
        
        try:
            logger.info("Starting migration process")
            await self.init_migrations_table(conn)
            
            applied: List[str] = await self.get_applied_migrations(conn)
            logger.info(f"Applied migrations count: {len(applied)}")
            
            for migration in applied:
                logger.info(f"  [DONE] {migration}")
            
            pending: List[Path] = self.get_pending_migrations(applied)
            
            if not pending:
                logger.info("All migrations are up to date")
                return
            
            logger.info(f"Found {len(pending)} pending migration(s)")
            for m in pending:
                logger.info(f"  - {m.name}")
            
            for m in pending:
                await self.apply_migration(conn, m)
            
            logger.info(f"All {len(pending)} migration(s) completed successfully")
            
        finally:
            await conn.close()
    
    async def status(self) -> None:
        conn: asyncpg.Connection = await asyncpg.connect(self.database_url)
        
        try:
            await self.init_migrations_table(conn)
            
            applied: List[str] = await self.get_applied_migrations(conn)
            pending: List[Path] = self.get_pending_migrations(applied)
            all_files: List[Path] = self.get_all_migration_files()
            
            logger.info("Migration Status Report")
            logger.info(f"Total migrations: {len(all_files)}")
            logger.info(f"Applied: {len(applied)}")
            logger.info(f"Pending: {len(pending)}")
            
            if applied:
                logger.info("Applied Migrations:")
                for m_name in applied:
                    logger.info(f"  [x] {m_name}")
            
            if pending:
                logger.info("Pending Migrations:")
                for m_file in pending:
                    logger.info(f"  [ ] {m_file.name}")
            else:
                logger.info("All migrations up to date")
            
        finally:
            await conn.close()

if __name__ == '__main__':
    if not DB_URL:
        sys.exit(1)

    logger.info(f"Database: {DB_URL[:50]}...")
    
    cmd: str = sys.argv[1] if len(sys.argv) > 1 else 'migrate'
    mgr: MigrationManager = MigrationManager(DB_URL)
    
    if cmd in ('migrate', 'up'):
        asyncio.run(mgr.run_migrations())
    elif cmd == 'status':
        asyncio.run(mgr.status())
    else:
        logger.error(f"Unknown command: {cmd}")
        sys.exit(1)
