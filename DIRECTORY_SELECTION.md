# Directory Selection Guide

The web interface now supports filtering which result directories appear on the dashboard. This is useful when you have many output directories but only want to show specific ones.

## Methods to Filter Directories

### 1. Configuration File (Recommended)

Edit `results_config.py` to set default filters:

```python
# Include only specific patterns
INCLUDE_PATTERNS = [
    'per_output',      # Show only directories containing 'per_output'
    'scalable',        # Show only directories containing 'scalable'
]

# Exclude specific patterns
EXCLUDE_PATTERNS = [
    'test',            # Hide directories containing 'test'
    'backup',          # Hide directories containing 'backup'
    'old',             # Hide directories containing 'old'
]

# Set directory priority (order on dashboard)
DIRECTORY_PRIORITY = [
    'per_output',           # Highest priority
    'per_output_fixed',     # Second priority
    'scalable_results',     # Third priority
    'demo_output',          # Fourth priority
]
```

### 2. Environment Variables

Set environment variables when starting the server:

```bash
# Include only specific directories
export PER_INCLUDE_DIRS="per_output,scalable"
python manage.py runserver

# Exclude specific directories
export PER_EXCLUDE_DIRS="test,demo,backup"
python manage.py runserver

# Both include and exclude
export PER_INCLUDE_DIRS="per_output"
export PER_EXCLUDE_DIRS="test"
python manage.py runserver
```

### 3. Management Command

Use the management command to test filters:

```bash
# List all directories
python manage.py list_results --show-all

# Include only specific patterns
python manage.py list_results --include per_output scalable

# Exclude specific patterns
python manage.py list_results --exclude test demo

# Combine include and exclude
python manage.py list_results --include per_output --exclude test
```

## Examples

### Show Only Production Results
```bash
export PER_INCLUDE_DIRS="per_output"
python manage.py runserver
```

### Hide Test and Demo Results
```bash
export PER_EXCLUDE_DIRS="test,demo,example"
python manage.py runserver
```

### Show Only Scalable Results
```bash
export PER_INCLUDE_DIRS="scalable"
python manage.py runserver
```

### Show Only Fixed Results
```bash
export PER_INCLUDE_DIRS="fixed"
python manage.py runserver
```

## Priority Ordering

Directories are ordered by priority (from `DIRECTORY_PRIORITY`) then alphabetically:

1. `per_output` (highest priority)
2. `per_output_fixed`
3. `scalable_results`
4. `demo_output`
5. `example_output`
6. `test_output` (lowest priority)
7. Any other directories (alphabetically)

## Troubleshooting

### No Directories Showing
- Check that directories contain required files (`products.csv`, `links.csv`, `pair_scores.csv` or `golden_records.db`)
- Verify include/exclude patterns are correct
- Use `python manage.py list_results --show-all` to see all available directories

### Wrong Order
- Update `DIRECTORY_PRIORITY` in `results_config.py`
- Restart the server after making changes

### Environment Variables Not Working
- Make sure to export variables before starting the server
- Check that patterns match directory names exactly
- Use the management command to test patterns
