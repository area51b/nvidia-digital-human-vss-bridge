#!/bin/bash

##############################################################################
# Milvus Collection Migration - Bash Wrapper
# 
# Wrapper script to run the migration with pip dependency check
#
# Usage:
#   ./migrate_milvus_collections.sh \
#       --host localhost \
#       --port 19530 \
#       --source-collections "collection1,collection2" \
#       --dest-collection "destination_collection"
#
##############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATION_SCRIPT="$SCRIPT_DIR/migrate_collections.py"

# Check if Python script exists
if [[ ! -f "$MIGRATION_SCRIPT" ]]; then
    echo "Error: migrate_collections.py not found at $MIGRATION_SCRIPT"
    exit 1
fi

# Check if pymilvus is installed, install if needed
echo "Checking for pymilvus library..."
if ! python3 -c "import pymilvus" 2>/dev/null; then
    echo "Installing pymilvus..."
    pip install pymilvus
fi

# Run the migration script with all arguments passed through
python3 "$MIGRATION_SCRIPT" "$@"

exit $?

# Function to print usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

OPTIONS:
    --host HOST                    Milvus server host (default: localhost)
    --port PORT                    Milvus server port (default: 19530)
    --user USER                    Milvus username (default: empty)
    --password PASSWORD            Milvus password (default: empty)
    --source-collections COLS      Comma-separated list of source collection names (required)
    --dest-collection DEST         Destination collection name (required)
    --filter-json FILTER           JSON filter criteria (default: {})
                                   Example: '{"source": "camera1", "date": "2025-01-16"}'
    --output-log FILE              Log file for migration results (optional)
    --verbose                      Enable verbose output
    --help                         Show this help message

EXAMPLES:
    # Copy all documents from source collections
    $0 --source-collections "videos_2025,videos_2024" \\
        --dest-collection "all_videos"

    # Copy documents matching metadata criteria
    $0 --source-collections "collection1" \\
        --dest-collection "filtered_results" \\
        --filter-json '{"source": "camera1", "location": "lobby"}'

    # With custom Milvus connection
    $0 --host 192.168.1.100 --port 19530 \\
        --source-collections "source1" \\
        --dest-collection "destination" \\
        --output-log migration.log --verbose

EOF
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            MILVUS_HOST="$2"
            shift 2
            ;;
        --port)
            MILVUS_PORT="$2"
            shift 2
            ;;
        --user)
            MILVUS_USER="$2"
            shift 2
            ;;
        --password)
            MILVUS_PASSWORD="$2"
            shift 2
            ;;
        --source-collections)
            SOURCE_COLLECTIONS="$2"
            shift 2
            ;;
        --dest-collection)
            DEST_COLLECTION="$2"
            shift 2
            ;;
        --filter-json)
            FILTER_JSON="$2"
            shift 2
            ;;
        --output-log)
            OUTPUT_LOG="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=1
            shift
            ;;
        --help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$SOURCE_COLLECTIONS" ]]; then
    print_error "Missing required argument: --source-collections"
    usage
fi

if [[ -z "$DEST_COLLECTION" ]]; then
    print_error "Missing required argument: --dest-collection"
    usage
fi

# Print configuration
print_info "========== Milvus Collection Migration =========="
print_info "Milvus Host: $MILVUS_HOST"
print_info "Milvus Port: $MILVUS_PORT"
print_info "Source Collections: $SOURCE_COLLECTIONS"
print_info "Destination Collection: $DEST_COLLECTION"
print_info "Filter Criteria: $FILTER_JSON"
print_info "=================================================="

# Create Python migration script
PYTHON_SCRIPT=$(cat << 'PYTHON_EOF'
import sys
import json
import logging
from pymilvus import MilvusClient

def setup_logging(verbose=False, log_file=None):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(levelname)s - %(message)s'
    
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=handlers
    )
    return logging.getLogger(__name__)

def connect_to_milvus(host, port, user="", password=""):
    """Connect to Milvus server"""
    uri = f"http://{host}:{port}"
    
    connect_kwargs = {
        "uri": uri,
    }
    
    if user:
        connect_kwargs["user"] = user
    if password:
        connect_kwargs["password"] = password
    
    logger.info(f"Connecting to Milvus at {uri}")
    client = MilvusClient(**connect_kwargs)
    logger.info("Successfully connected to Milvus")
    return client

def get_collection_schema(client, collection_name):
    """Get schema information for a collection"""
    try:
        collection_info = client.describe_collection(collection_name)
        return collection_info
    except Exception as e:
        logger.error(f"Failed to get schema for collection '{collection_name}': {e}")
        raise

def search_collection(client, collection_name, filter_expr=None, limit=10000):
    """Search and retrieve documents from a collection"""
    try:
        logger.info(f"Searching collection '{collection_name}'...")
        
        # Build search parameters
        search_params = {
            "limit": limit,
            "output_fields": ["*"],
        }
        
        if filter_expr:
            logger.debug(f"Using filter expression: {filter_expr}")
            search_params["filter"] = filter_expr
        
        # Get all documents (no actual vector search, just filter)
        results = client.query(
            collection_name=collection_name,
            filter=filter_expr,
            output_fields=["*"],
            limit=limit
        )
        
        logger.info(f"Found {len(results)} documents in '{collection_name}'")
        return results
    
    except Exception as e:
        logger.error(f"Failed to search collection '{collection_name}': {e}")
        raise

def get_collection_fields(client, collection_name):
    """Get field information from collection"""
    try:
        info = client.describe_collection(collection_name)
        return info.get('fields', [])
    except Exception as e:
        logger.error(f"Failed to get fields for '{collection_name}': {e}")
        raise

def insert_documents(client, collection_name, documents):
    """Insert documents into destination collection"""
    if not documents:
        logger.warning("No documents to insert")
        return 0
    
    try:
        logger.info(f"Inserting {len(documents)} documents into '{collection_name}'...")
        
        # Prepare documents for insertion
        docs_to_insert = []
        for doc in documents:
            docs_to_insert.append(doc)
        
        # Insert documents
        result = client.insert(
            collection_name=collection_name,
            documents=docs_to_insert
        )
        
        inserted_count = result.get('insert_count', len(docs_to_insert))
        logger.info(f"Successfully inserted {inserted_count} documents into '{collection_name}'")
        return inserted_count
    
    except Exception as e:
        logger.error(f"Failed to insert documents into '{collection_name}': {e}")
        raise

def migrate_collections(host, port, source_collections, dest_collection, filter_json, 
                        user="", password="", verbose=False, log_file=None):
    """Main migration function"""
    global logger
    logger = setup_logging(verbose=verbose, log_file=log_file)
    
    try:
        # Connect to Milvus
        client = connect_to_milvus(host, port, user, password)
        
        # Verify destination collection exists
        logger.info(f"Verifying destination collection '{dest_collection}'...")
        try:
            client.describe_collection(dest_collection)
            logger.info(f"Destination collection '{dest_collection}' exists")
        except Exception as e:
            logger.error(f"Destination collection '{dest_collection}' does not exist: {e}")
            raise
        
        # Build filter expression from JSON criteria
        filter_expr = None
        if filter_json and filter_json != "{}":
            try:
                filter_criteria = json.loads(filter_json)
                if filter_criteria:
                    # Build Milvus filter expression
                    conditions = []
                    for key, value in filter_criteria.items():
                        if isinstance(value, str):
                            conditions.append(f"{key} == '{value}'")
                        elif isinstance(value, (int, float)):
                            conditions.append(f"{key} == {value}")
                        else:
                            conditions.append(f"{key} == '{json.dumps(value)}'")
                    
                    filter_expr = " && ".join(conditions) if conditions else None
                    logger.info(f"Filter expression: {filter_expr}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in filter criteria: {e}")
                raise
        
        # Migrate documents from each source collection
        total_migrated = 0
        migration_summary = {}
        
        for source_col in source_collections:
            source_col = source_col.strip()
            logger.info(f"\n--- Processing source collection: '{source_col}' ---")
            
            try:
                # Search source collection
                documents = search_collection(
                    client, 
                    source_col, 
                    filter_expr=filter_expr,
                    limit=100000
                )
                
                if documents:
                    # Insert into destination collection
                    count = insert_documents(client, dest_collection, documents)
                    total_migrated += count
                    migration_summary[source_col] = count
                else:
                    logger.warning(f"No documents found in '{source_col}' matching criteria")
                    migration_summary[source_col] = 0
            
            except Exception as e:
                logger.error(f"Failed to migrate from '{source_col}': {e}")
                migration_summary[source_col] = -1  # Error marker
                raise
        
        # Print summary
        logger.info("\n========== Migration Summary ==========")
        for source_col, count in migration_summary.items():
            if count >= 0:
                logger.info(f"  {source_col}: {count} documents")
            else:
                logger.info(f"  {source_col}: FAILED")
        logger.info(f"Total migrated: {total_migrated} documents")
        logger.info("=======================================")
        
        return total_migrated
    
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

# Main execution
if __name__ == "__main__":
    host = sys.argv[1]
    port = int(sys.argv[2])
    source_collections = sys.argv[3].split(',')
    dest_collection = sys.argv[4]
    filter_json = sys.argv[5]
    user = sys.argv[6]
    password = sys.argv[7]
    verbose = sys.argv[8] == "1"
    log_file = sys.argv[9] if sys.argv[9] != "None" else None
    
    migrate_collections(
        host, 
        port, 
        source_collections, 
        dest_collection, 
        filter_json,
        user=user,
        password=password,
        verbose=verbose,
        log_file=log_file
    )

PYTHON_EOF
)

# Check if pymilvus is installed
print_info "Checking for pymilvus library..."
if ! python3 -c "import pymilvus" 2>/dev/null; then
    print_warning "pymilvus library not found. Installing..."
    pip install pymilvus > /dev/null 2>&1 || {
        print_error "Failed to install pymilvus. Please install manually: pip install pymilvus"
        exit 1
    }
    print_success "pymilvus installed successfully"
fi

# Execute Python migration script
print_info "Starting migration process..."

LOG_FILE_ARG="$OUTPUT_LOG"
if [[ -z "$OUTPUT_LOG" ]]; then
    LOG_FILE_ARG="None"
fi

python3 << PYTHON_EXECUTE
$PYTHON_SCRIPT
import sys
sys.argv = [
    'migrate',
    '$MILVUS_HOST',
    '$MILVUS_PORT',
    '$SOURCE_COLLECTIONS',
    '$DEST_COLLECTION',
    '$FILTER_JSON',
    '$MILVUS_USER',
    '$MILVUS_PASSWORD',
    '$VERBOSE',
    '$LOG_FILE_ARG'
]

exec($PYTHON_SCRIPT.split('# Main execution')[0] + '''
if __name__ == "__main__":
    host = "$MILVUS_HOST"
    port = int("$MILVUS_PORT")
    source_collections = "$SOURCE_COLLECTIONS".split(',')
    dest_collection = "$DEST_COLLECTION"
    filter_json = '$FILTER_JSON'
    user = "$MILVUS_USER"
    password = "$MILVUS_PASSWORD"
    verbose = $VERBOSE == 1
    log_file = "$OUTPUT_LOG" if "$OUTPUT_LOG" else None
    
    migrate_collections(
        host, 
        port, 
        source_collections, 
        dest_collection, 
        filter_json,
        user=user,
        password=password,
        verbose=verbose,
        log_file=log_file
    )
''')
PYTHON_EXECUTE

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    print_success "Migration completed successfully!"
    if [[ -n "$OUTPUT_LOG" ]]; then
        print_info "Details logged to: $OUTPUT_LOG"
    fi
else
    print_error "Migration failed with exit code $EXIT_CODE"
    exit $EXIT_CODE
fi
