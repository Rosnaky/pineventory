# database/migrations/migrate.py
import asyncpg
from pathlib import Path
from typing import List
import sys

class MigrationManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.migrations_dir = Path(__file__).parent
    
    async def init_migrations_table(self, conn):
        """Create migrations tracking table"""
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        ''')
        print("📋 Migrations table initialized")
    
    async def get_applied_migrations(self, conn) -> List[str]:
        """Get list of already applied migrations"""
        rows = await conn.fetch(
            'SELECT migration_name FROM schema_migrations ORDER BY id'
        )
        return [row['migration_name'] for row in rows]
    
    def get_all_migration_files(self) -> List[Path]:
        """Get all SQL migration files sorted by name"""
        migrations = sorted(self.migrations_dir.glob('*.sql'))
        return migrations
    
    def get_pending_migrations(self, applied: List[str]) -> List[Path]:
        """Get SQL files that haven't been applied yet"""
        all_migrations = self.get_all_migration_files()
        return [m for m in all_migrations if m.name not in applied]
    
    async def apply_migration(self, conn, migration_path: Path):
        """Apply a single migration file"""
        print(f"  ⏳ Applying {migration_path.name}...")
        
        try:
            # Read SQL file
            sql_content = migration_path.read_text(encoding='utf-8')
            
            # Split by semicolons to handle multiple statements
            # Remove comments and empty statements
            statements = []
            for statement in sql_content.split(';'):
                # Remove SQL comments (-- style)
                lines = []
                for line in statement.split('\n'):
                    # Remove inline comments
                    if '--' in line:
                        line = line[:line.index('--')]
                    lines.append(line)
                
                statement = '\n'.join(lines).strip()
                if statement:
                    statements.append(statement)
            
            # Execute each statement
            for statement in statements:
                await conn.execute(statement)
            
            # Record migration as applied
            await conn.execute(
                'INSERT INTO schema_migrations (migration_name) VALUES ($1)',
                migration_path.name
            )
            
            print(f"  ✅ {migration_path.name} applied successfully")
            
        except Exception as e:
            print(f"  ❌ Failed to apply {migration_path.name}: {e}")
            raise
    
    async def run_migrations(self):
        """Run all pending migrations"""
        conn = await asyncpg.connect(self.database_url)
        
        try:
            print("🔄 Starting migration process...")
            
            # Initialize migrations table
            await self.init_migrations_table(conn)
            
            # Get applied migrations
            applied = await self.get_applied_migrations(conn)
            print(f"📋 Applied migrations: {len(applied)}")
            
            if applied:
                for migration in applied:
                    print(f"  ✓ {migration}")
            
            # Get pending migrations
            pending = self.get_pending_migrations(applied)
            
            if not pending:
                print("✨ All migrations are up to date!")
                return
            
            print(f"\n🔄 Found {len(pending)} pending migration(s):")
            for migration in pending:
                print(f"  • {migration.name}")
            
            print("\n⏳ Applying migrations...\n")
            
            # Apply each pending migration
            for migration in pending:
                await self.apply_migration(conn, migration)
            
            print(f"\n✅ All {len(pending)} migration(s) completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            raise
            
        finally:
            await conn.close()
    
    async def status(self):
        """Show migration status"""
        conn = await asyncpg.connect(self.database_url)
        
        try:
            # Initialize table if needed
            await self.init_migrations_table(conn)
            
            applied = await self.get_applied_migrations(conn)
            pending = self.get_pending_migrations(applied)
            all_migrations = self.get_all_migration_files()
            
            print("📊 Migration Status")
            print("=" * 50)
            print(f"Total migrations: {len(all_migrations)}")
            print(f"Applied: {len(applied)}")
            print(f"Pending: {len(pending)}")
            print()
            
            if applied:
                print("✅ Applied Migrations:")
                for migration in applied:
                    print(f"  ✓ {migration}")
                print()
            
            if pending:
                print("⏳ Pending Migrations:")
                for migration in pending:
                    print(f"  • {migration.name}")
            else:
                print("✨ All migrations up to date!")
            
        finally:
            await conn.close()

# CLI runner
if __name__ == '__main__':
    import asyncio
    from app.config import *
    
    # Validate config
    
    print(f"🗄️  Database: {DB_URL[:50]}...")
    print()
    
    # Get command
    command = sys.argv[1] if len(sys.argv) > 1 else 'migrate'
    
    manager = MigrationManager(DB_URL)
    
    if command == 'migrate' or command == 'up':
        asyncio.run(manager.run_migrations())
    elif command == 'status':
        asyncio.run(manager.status())
    else:
        print(f"❌ Unknown command: {command}")
        print("\nAvailable commands:")
        print("  migrate/up  - Run pending migrations")
        print("  status      - Show migration status")
        sys.exit(1)