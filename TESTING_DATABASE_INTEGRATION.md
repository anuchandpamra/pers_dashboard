# Testing Web Interface Database Integration

## Quick Start Guide

### 1. Ensure PostgreSQL is Running

```bash
brew services list | grep postgresql
# Should show "started"
```

### 2. Verify Databases Exist

```bash
psql -l | grep product_entity_resolution
```

You should see:
- `product_entity_resolution` (main database)
- `product_entity_resolution_test` (test database)

### 3. Start the Web Interface

```bash
cd web_interface
source venv/bin/activate
python manage.py runserver
```

### 4. Open Browser

Visit: **http://localhost:8000**

---

## What You Should See

### Dashboard (Homepage)

You should see cards for:

1. **PostgreSQL - Main Database**
   - Server icon (🖥️)
   - **Connected** badge (green) or **Offline** badge (red)
   - Statistics (likely 0 if database is empty)

2. **PostgreSQL - Test Database**
   - Server icon (🖥️)
   - **Connected** badge
   - Statistics

3. **Existing Directory Results** (if any)
   - Folder icon (📁)
   - "CSV" or "Scalable" badge

### Connection Status Badges

| Badge | Meaning |
|-------|---------|
| ✅ Connected | Database is online and accessible |
| ❌ Offline | Database is not running or not accessible |
| ⚠️ Error | Configuration or permission issue |

---

## Testing Scenarios

### Scenario 1: Empty Database (Current State)

**Expected**:
- Card shows "0 Golden Records"
- Card shows "0 Total Products"
- "View Details" button works
- Golden Records tab is active (no Pair Scores tab)
- "No results found" message in Golden Records section

### Scenario 2: Populate Test Database

```bash
# From project root
python test_postgresql_resolver.py \
    --connection_string postgresql://localhost/product_entity_resolution_test \
    --input_dir test_catalogs/ \
    --output_dir test_output/
```

Then **refresh the dashboard** (F5).

**Expected**:
- Card shows actual golden record count
- Card shows actual product count
- Statistics update in real-time
- Top manufacturers appear
- Click "View Details" shows golden records

### Scenario 3: Compare with Scalable Output

If you have a scalable output directory with `golden_records.db`:

**Expected**:
- Scalable directory shows "Scalable" badge
- PostgreSQL database shows "Connected" badge
- **Both hide the Pair Scores tab**
- Both show only Golden Records tab

---

## Troubleshooting

### Database Not Showing

**Fix**:
1. Check `web_interface/database_sources_config.py`
2. Ensure `enabled: True`
3. Verify PostgreSQL is running

### Shows "Offline" But PostgreSQL is Running

**Check connection string**:
```python
# In database_sources_config.py
'connection_string': 'postgresql://localhost/product_entity_resolution_test'
```

**Test manually**:
```bash
psql product_entity_resolution_test
# Should connect without error
```

### No Statistics Showing

**Check if database has data**:
```bash
psql product_entity_resolution_test

SELECT COUNT(*) FROM golden_records;
SELECT COUNT(*) FROM golden_record_products;
```

If counts are 0, database is empty (normal state).

---

## Configuration

### Add Custom Database

Edit `web_interface/database_sources_config.py`:

```python
POSTGRESQL_SOURCES = [
    # ... existing sources ...
    {
        'name': 'pgsql_custom',
        'display_name': 'My Custom Database',
        'description': 'Custom entity resolution database',
        'connection_string': 'postgresql://localhost/my_database',
        'enabled': True,
        'type': 'postgresql'
    },
]
```

### Disable a Database

Set `enabled: False`:

```python
{
    'name': 'pgsql_test',
    'enabled': False,  # Won't appear on dashboard
    ...
}
```

---

## Real-Time Updates

The web interface shows **live data** from databases:
- Statistics are fetched on each page load
- No caching between requests (configurable in `CACHE_SETTINGS`)
- Refresh page to see latest data

---

## Next Steps

1. ✅ Verify web interface shows both databases
2. ✅ Check connection status badges
3. 🔄 Run entity resolution to populate test database
4. ✅ Verify real-time stats update
5. ✅ Test golden records browsing
6. 🔄 Implement multi-threading in PostgreSQL resolver
7. 🔄 Test with large datasets

---

## Success Criteria

- [x] Dashboard shows PostgreSQL databases
- [x] Connection status badges display correctly
- [x] Pair Scores tab hidden for database sources
- [x] Golden Records tab loads data from database
- [x] Filtering and pagination work with database
- [ ] Test with populated database
- [ ] Verify real-time data refresh

---

## Visual Reference

### Dashboard Card Structure

```
╔═══════════════════════════════════════╗
║ 🖥️ PostgreSQL - Test Database   [✅ Connected] ║
╠═══════════════════════════════════════╣
║                                       ║
║   📊 Statistics                       ║
║   • Total Products: 0                 ║
║   • Golden Records: 0                 ║
║   • Matched: 0                        ║
║   • Unique: 0                         ║
║   • Avg Confidence: 0.000             ║
║                                       ║
╠═══════════════════════════════════════╣
║          [👁️ View Details]            ║
╚═══════════════════════════════════════╝
```

Happy testing! 🎉

