#!/usr/bin/env python3
"""
Milvus Collection Document Migration Script

Copies documents matching search criteria from source collections to a destination collection.

Usage:
    python3 migrate_collections.py \\
        --host localhost \\
        --port 19530 \\
        --source-collections "collection1,collection2" \\
        --dest-collection "destination_collection" \\
        [--filter-json '{"metadata_field": "value"}'] \\
        [--output-log migration.log] \\
        [--verbose]
"""

import argparse
import json
import logging
import sys
from typing import List, Dict, Any, Optional

try:
    from pymilvus import MilvusClient, exceptions
except ImportError:
    print("Error: pymilvus library not found.")
    print("Install it using: pip install pymilvus")
    sys.exit(1)


class MilvusLogger:
    """Custom logger for Milvus migration operations"""
    
    def __init__(self, verbose: bool = False, log_file: Optional[str] = None):
        self.logger = logging.getLogger("MilvusMigration")
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def info(self, msg: str):
        self.logger.info(msg)
    
    def warning(self, msg: str):
        self.logger.warning(msg)
    
    def error(self, msg: str):
        self.logger.error(msg)
    
    def debug(self, msg: str):
        self.logger.debug(msg)


class MilvusMigrator:
    """Handles migration of documents between Milvus collections"""
    
    def __init__(self, host: str, port: int, logger: MilvusLogger, 
                 user: str = "", password: str = ""):
        self.host = host
        self.port = port
        self.logger = logger
        self.user = user
        self.password = password
        self.client: Optional[MilvusClient] = None
    
    def connect(self) -> bool:
        """Connect to Milvus server"""
        try:
            uri = f"http://{self.host}:{self.port}"
            self.logger.info(f"Connecting to Milvus at {uri}")
            
            connect_kwargs = {"uri": uri}
            if self.user:
                connect_kwargs["user"] = self.user
            if self.password:
                connect_kwargs["password"] = self.password
            
            self.client = MilvusClient(**connect_kwargs)
            self.logger.info("Successfully connected to Milvus")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Milvus: {e}")
            return False
    
    def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists"""
        try:
            self.client.describe_collection(collection_name)
            return True
        except Exception:
            return False
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """Get information about a collection"""
        try:
            info = self.client.describe_collection(collection_name)
            self.logger.debug(f"Collection '{collection_name}' info: {info}")
            return info
        except Exception as e:
            self.logger.error(f"Failed to get info for collection '{collection_name}': {e}")
            raise
    
    def search_collection(self, collection_name: str, filter_expr: Optional[str] = None,
                         limit: int = 100000) -> List[Dict[str, Any]]:
        """Search and retrieve documents from a collection"""
        try:
            self.logger.info(f"Searching collection '{collection_name}'...")
            
            query_params = {
                "collection_name": collection_name,
                "output_fields": ["*"],
                "limit": limit,
            }
            
            if filter_expr:
                self.logger.debug(f"Using filter expression: {filter_expr}")
                query_params["filter"] = filter_expr
            
            results = self.client.query(**query_params)
            self.logger.info(f"Found {len(results)} documents in '{collection_name}'")
            return results
        except Exception as e:
            self.logger.error(f"Failed to search collection '{collection_name}': {e}")
            raise
    
    def insert_documents(self, collection_name: str, documents: List[Dict[str, Any]]) -> int:
        """Insert documents into destination collection"""
        if not documents:
            self.logger.warning("No documents to insert")
            return 0
        
        try:
            self.logger.info(f"Inserting {len(documents)} documents into '{collection_name}'...")
            
            result = self.client.insert(
                collection_name=collection_name,
                documents=documents
            )
            
            inserted_count = result.get('insert_count', len(documents))
            self.logger.info(f"Successfully inserted {inserted_count} documents")
            return inserted_count
        except Exception as e:
            self.logger.error(f"Failed to insert documents: {e}")
            raise
    
    def build_filter_expression(self, filter_json: str) -> Optional[str]:
        """Build Milvus filter expression from JSON criteria"""
        if not filter_json or filter_json == "{}":
            return None
        
        try:
            filter_criteria = json.loads(filter_json)
            if not filter_criteria:
                return None
            
            conditions = []
            for key, value in filter_criteria.items():
                if isinstance(value, str):
                    conditions.append(f"{key} == '{value}'")
                elif isinstance(value, bool):
                    conditions.append(f"{key} == {str(value).lower()}")
                elif isinstance(value, (int, float)):
                    conditions.append(f"{key} == {value}")
                else:
                    conditions.append(f"{key} == '{json.dumps(value)}'")
            
            filter_expr = " && ".join(conditions) if conditions else None
            self.logger.debug(f"Built filter expression: {filter_expr}")
            return filter_expr
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in filter criteria: {e}")
            raise
    
    def migrate(self, source_collections: List[str], dest_collection: str,
               filter_json: str = "{}") -> int:
        """Migrate documents from source collections to destination"""
        try:
            # Verify destination collection exists
            self.logger.info(f"Verifying destination collection '{dest_collection}'...")
            if not self.collection_exists(dest_collection):
                self.logger.error(f"Destination collection '{dest_collection}' does not exist")
                raise ValueError(f"Destination collection '{dest_collection}' not found")
            
            self.logger.info(f"Destination collection '{dest_collection}' verified")
            
            # Build filter expression
            filter_expr = self.build_filter_expression(filter_json)
            
            # Migrate documents from each source collection
            total_migrated = 0
            migration_summary = {}
            
            for source_col in source_collections:
                source_col = source_col.strip()
                if not source_col:
                    continue
                
                self.logger.info(f"\n--- Processing source collection: '{source_col}' ---")
                
                try:
                    # Verify source collection exists
                    if not self.collection_exists(source_col):
                        self.logger.warning(f"Source collection '{source_col}' does not exist")
                        migration_summary[source_col] = -1
                        continue
                    
                    # Search source collection
                    documents = self.search_collection(
                        source_col,
                        filter_expr=filter_expr,
                        limit=100000
                    )
                    
                    if documents:
                        # Insert into destination collection
                        count = self.insert_documents(dest_collection, documents)
                        total_migrated += count
                        migration_summary[source_col] = count
                        self.logger.info(f"Migration from '{source_col}' completed: {count} documents")
                    else:
                        self.logger.warning(f"No documents found in '{source_col}' matching criteria")
                        migration_summary[source_col] = 0
                
                except Exception as e:
                    self.logger.error(f"Failed to migrate from '{source_col}': {e}")
                    migration_summary[source_col] = -1
                    raise
            
            # Print summary
            self.logger.info("\n" + "=" * 50)
            self.logger.info("Migration Summary")
            self.logger.info("=" * 50)
            for source_col, count in migration_summary.items():
                if count >= 0:
                    self.logger.info(f"  {source_col}: {count} documents migrated")
                else:
                    self.logger.info(f"  {source_col}: FAILED or NOT FOUND")
            self.logger.info(f"Total migrated: {total_migrated} documents")
            self.logger.info("=" * 50)
            
            return total_migrated
        
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Migrate documents between Milvus collections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Copy all documents from source collections
  python3 migrate_collections.py \\
      --source-collections "videos_2025,videos_2024" \\
      --dest-collection "all_videos"

  # Copy documents matching metadata criteria
  python3 migrate_collections.py \\
      --source-collections "collection1" \\
      --dest-collection "filtered_results" \\
      --filter-json '{{"source": "camera1", "location": "lobby"}}'

  # With custom Milvus connection and logging
  python3 migrate_collections.py \\
      --host 192.168.1.100 --port 19530 \\
      --source-collections "source1,source2" \\
      --dest-collection "destination" \\
      --output-log migration.log --verbose
        """
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Milvus server host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=19530,
        help="Milvus server port (default: 19530)"
    )
    parser.add_argument(
        "--user",
        type=str,
        default="",
        help="Milvus username (default: empty)"
    )
    parser.add_argument(
        "--password",
        type=str,
        default="",
        help="Milvus password (default: empty)"
    )
    parser.add_argument(
        "--source-collections",
        type=str,
        required=True,
        help="Comma-separated list of source collection names"
    )
    parser.add_argument(
        "--dest-collection",
        type=str,
        required=True,
        help="Destination collection name"
    )
    parser.add_argument(
        "--filter-json",
        type=str,
        default="{}",
        help='JSON filter criteria (default: {}) Example: \'{"source": "camera1", "date": "2025-01-16"}\''
    )
    parser.add_argument(
        "--output-log",
        type=str,
        help="Log file for migration results (optional)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Setup logger
    logger = MilvusLogger(verbose=args.verbose, log_file=args.output_log)
    
    # Print configuration
    logger.info("=" * 60)
    logger.info("Milvus Collection Migration")
    logger.info("=" * 60)
    logger.info(f"Milvus Host: {args.host}")
    logger.info(f"Milvus Port: {args.port}")
    logger.info(f"Source Collections: {args.source_collections}")
    logger.info(f"Destination Collection: {args.dest_collection}")
    logger.info(f"Filter Criteria: {args.filter_json}")
    logger.info("=" * 60 + "\n")
    
    try:
        # Create migrator and run migration
        migrator = MilvusMigrator(
            host=args.host,
            port=args.port,
            logger=logger,
            user=args.user,
            password=args.password
        )
        
        # Connect to Milvus
        if not migrator.connect():
            sys.exit(1)
        
        # Parse source collections
        source_collections = [c.strip() for c in args.source_collections.split(',')]
        
        # Run migration
        total_migrated = migrator.migrate(
            source_collections=source_collections,
            dest_collection=args.dest_collection,
            filter_json=args.filter_json
        )
        
        logger.info(f"\n✓ Migration completed successfully! Total: {total_migrated} documents")
        if args.output_log:
            logger.info(f"Details logged to: {args.output_log}")
        
        return 0
    
    except Exception as e:
        logger.error(f"\n✗ Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
