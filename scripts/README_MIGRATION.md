# Milvus Collection Migration Scripts

This directory contains scripts to migrate documents between Milvus vector database collections.

## Overview

The migration tool allows you to:
- Copy documents from one or more source collections to a destination collection
- Filter documents based on metadata criteria (JSON format)
- Support for empty credentials (for local development)
- Comprehensive logging and error handling

## Files

- **migrate_collections.py** - Main Python migration script
- **migrate_milvus_collections.sh** - Bash wrapper for convenience

## Prerequisites

- Python 3.7+
- pymilvus library (automatically installed by the wrapper script)
- Access to Milvus database

Install pymilvus manually if needed:
```bash
pip install pymilvus
```

## Usage

### Using the Python script directly

```bash
python3 migrate_collections.py \
    --host localhost \
    --port 19530 \
    --source-collections "collection1,collection2" \
    --dest-collection "destination_collection"
```

### Using the bash wrapper

```bash
./migrate_milvus_collections.sh \
    --host localhost \
    --port 19530 \
    --source-collections "collection1,collection2" \
    --dest-collection "destination_collection"
```

## Command-line Options

| Option | Description | Default | Required |
|--------|-------------|---------|----------|
| `--host` | Milvus server host | localhost | No |
| `--port` | Milvus server port | 19530 | No |
| `--user` | Milvus username | empty | No |
| `--password` | Milvus password | empty | No |
| `--source-collections` | Comma-separated list of source collection names | - | **Yes** |
| `--dest-collection` | Destination collection name | - | **Yes** |
| `--filter-json` | JSON filter criteria | {} | No |
| `--output-log` | Log file for migration results | - | No |
| `--verbose` | Enable verbose output | disabled | No |

## Examples

### 1. Copy all documents from source collections

```bash
python3 migrate_collections.py \
    --source-collections "videos_2025,videos_2024" \
    --dest-collection "all_videos"
```

### 2. Copy documents matching metadata criteria

```bash
python3 migrate_collections.py \
    --source-collections "collection1" \
    --dest-collection "filtered_results" \
    --filter-json '{"source": "camera1", "location": "lobby"}'
```

### 3. With custom Milvus connection and logging

```bash
python3 migrate_collections.py \
    --host 192.168.1.100 \
    --port 19530 \
    --source-collections "source1,source2" \
    --dest-collection "destination" \
    --output-log migration.log \
    --verbose
```

### 4. Using the bash wrapper

```bash
./migrate_milvus_collections.sh \
    --host localhost \
    --port 19530 \
    --source-collections "collection1,collection2" \
    --dest-collection "merged_collection" \
    --output-log migration_$(date +%Y%m%d_%H%M%S).log
```

## Filter JSON Format

The `--filter-json` parameter accepts a JSON object with key-value pairs. These are converted to Milvus filter expressions using `&&` (AND) operators.

Examples:

```bash
# Single condition
--filter-json '{"source": "camera1"}'

# Multiple conditions (all must match)
--filter-json '{"source": "camera1", "location": "lobby", "date": "2025-01-16"}'

# Numeric values
--filter-json '{"confidence": 0.95, "frame_count": 1000}'
```

## Output

The script provides:

1. **Console Output** - Real-time migration progress
2. **Log File** (optional) - Detailed migration results saved to specified file
3. **Migration Summary** - Per-collection and total document counts

Example output:
```
============================================================
Milvus Collection Migration
============================================================
Milvus Host: localhost
Milvus Port: 19530
Source Collections: source1,source2
Destination Collection: destination
Filter Criteria: {"source": "camera1"}
============================================================

2025-01-16 10:30:45 - INFO - Connecting to Milvus at http://localhost:19530
2025-01-16 10:30:45 - INFO - Successfully connected to Milvus
...
==================================================
Migration Summary
==================================================
  source1: 150 documents migrated
  source2: 85 documents migrated
Total migrated: 235 documents
==================================================

✓ Migration completed successfully! Total: 235 documents
```

## Error Handling

The script includes comprehensive error handling for:
- Connection failures to Milvus
- Missing or invalid source collections
- Invalid filter JSON syntax
- Missing destination collection
- Database operation failures

All errors are logged with details to help troubleshooting.

## Troubleshooting

### Connection refused
```bash
# Verify Milvus is running on the correct host and port
python3 migrate_collections.py \
    --host <actual-host> \
    --port <actual-port> \
    --source-collections "test" \
    --dest-collection "test"
```

### pymilvus not found
```bash
# Install the required package
pip install pymilvus
```

### Invalid filter JSON
Ensure the JSON is properly formatted and quoted:
```bash
# Correct
--filter-json '{"source": "camera1"}'

# Incorrect (unquoted keys)
--filter-json '{source: camera1}'
```

### No documents found
Check if:
1. Source collection exists
2. Filter criteria are correct
3. Collection actually contains matching documents

## Local Testing

For local Milvus setup with empty credentials:

```bash
python3 migrate_collections.py \
    --host localhost \
    --port 19530 \
    --user "" \
    --password "" \
    --source-collections "source_collection" \
    --dest-collection "dest_collection" \
    --verbose
```

## Performance Considerations

- Documents are retrieved with a default limit of 100,000 per collection
- For larger migrations, process collections sequentially
- Use filtering to reduce the number of documents migrated
- Check Milvus server resources before large migrations
