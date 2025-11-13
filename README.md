# Product Entity Resolution Web Interface

A Django web application for exploring and analyzing Product Entity Resolution results.

## Features

- **Dashboard**: Overview of all available results directories with summary statistics
- **Pair Scores Viewer**: Interactive table of product similarity scores with filtering and pagination
- **Golden Records Browser**: Browse consolidated products with search and filter capabilities
- **Product Details**: Detailed view of individual products and their links
- **Product Comparison**: Side-by-side comparison of two products with feature-level similarity breakdown
- **Scalable Output Support**: Works with both traditional (`pair_scores.csv`) and scalable (`golden_records.db`) outputs
- **Real-time Filtering**: Filter by confidence score, manufacturer, UNSPSC code, etc.
- **Intelligent API Selection**: Automatically detects output type and uses appropriate comparison method

## Setup

1. **Install Dependencies**:
   ```bash
   cd web_interface
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run Migrations**:
   ```bash
   python manage.py migrate
   ```

3. **Start the Server**:
   ```bash
   python manage.py runserver
   ```

4. **Open Browser**: Navigate to `http://127.0.0.1:8000`

## Configuration

The web interface automatically detects results directories containing **either**:

### Traditional Output (from `product_entity_resolution.py`)
- `products.csv`
- `links.csv` 
- `pair_scores.csv`
- `vendor_catalogs_used.csv` (optional, for product detail lookup)

### Scalable Output (from `scalable_entity_resolution.py`)
- `golden_records.db` (SQLite database)
- `vendor_catalogs_used.csv` (optional, for product detail lookup)

### Default Results Directory
By default, it looks in the parent directory of the web interface. To specify a different directory:

```bash
export PER_RESULTS_DIR=/path/to/your/results
python manage.py runserver
```

### Filtering Results Directories
You can control which directories appear on the dashboard:

```bash
# Include only specific directories
export PER_INCLUDE_DIRS="per_output,scalable_output"

# Exclude specific directories
export PER_EXCLUDE_DIRS="test_output,demo_output"

python manage.py runserver
```

Or edit `web_interface/results_config.py` for persistent configuration:
```python
INCLUDE_PATTERNS = ["per_output", "production_"]
EXCLUDE_PATTERNS = ["test_", "temp_"]
DIRECTORY_PRIORITY = ["per_output", "scalable_output"]
```

### Supported Results Directories
The interface will automatically detect and display:
- `per_output/` - Traditional entity resolution output
- `scalable_results/` - Scalable entity resolution output
- `demo_output/`
- `example_output/`
- `test_output/`
- Any other directory containing the required files

## Usage

### Command Line Workflow (Unchanged)
Your existing command-line workflow remains exactly the same:

```bash
# Run your entity resolution as usual
python product_entity_resolution.py --vendor_a vendor_catalogs/47QSWA22D006Q.csv --vendor_b vendor_catalogs/GS-02F-0008V.csv --output_dir per_output/

# Results are automatically available in the web interface
```

### Web Interface Features

#### 1. **Dashboard**
- View summary statistics for all results directories
- Display metrics:
  - **Total Products**: Number of vendor products across all catalogs
  - **Golden Records**: Number of consolidated/deduplicated products
  - **Matched Products**: Golden records found in multiple vendor catalogs
  - **Unique Products**: Products found in only one vendor catalog
  - **Average Confidence**: Mean confidence score across all links
- Click "View Details" to explore a specific results set

#### 2. **Pair Scores** (Traditional Output Only)
- Sortable table of all product pairs above similarity threshold
- Features:
  - Filter by minimum similarity score (slider)
  - Search by product ID
  - Pagination with direct page navigation
  - Click eye icons to view product details
  - **Compare button**: Side-by-side feature comparison

#### 3. **Golden Records**
- Browse consolidated products (deduplicated records)
- Available for both traditional and scalable outputs
- Features:
  - Filter by manufacturer, UNSPSC code, size (number of linked products)
  - Search by title, description, part number
  - Pagination with direct page navigation
  - Click "View Details" to see all linked vendor products
  - Visual badges for matched/unique products

#### 4. **Product Details Modal**
- Triggered by clicking eye icons or "View Details" button
- Displays:
  - Product Information (GUID, Manufacturer, Part Number, UNSPSC, GTIN, Size)
  - Product Description
  - All Linked Vendor Products with confidence scores
- **For golden records with 2+ products**:
  - Checkboxes to select products for comparison
  - "Compare Selected" button (always visible at top)
  - Scrollable product list (400px max height)
  - Sticky table header for easy navigation

#### 5. **Product Comparison** ⭐ NEW
Compare two products with detailed feature-level analysis:

**Accessing Comparison**:
- **From Pair Scores**: Click "Compare" button on any row
- **From Golden Records**: Select 2 products and click "Compare Selected"
- Works with both traditional and scalable outputs (intelligent API selection)

**Comparison Details**:
- **Part Number Analysis**:
  - Original part numbers
  - Generated variants
  - Matching variants highlighted
  - Similarity scores (Exact, Jaro-Winkler, Levenshtein)
  - Score contribution to overall similarity
  
- **Manufacturer Analysis**:
  - Original manufacturer names
  - Normalized/canonical names
  - Similarity score
  - Score contribution
  
- **Text Similarity**:
  - Title similarity (Jaccard)
  - Description similarity (Jaccard)
  - TF-IDF Cosine similarity
  - Overall text score contribution
  
- **UNSPSC Matching** (if available):
  - UNSPSC codes for both products
  - Hierarchical match level (exact, family, class, segment)
  - Score contribution
  
- **Score Breakdown Table**:
  - Part Number contribution
  - Manufacturer contribution
  - Text Similarity contribution
  - UNSPSC contribution (if applicable)
  - **Total Overall Score**

**Intelligent Behavior**:
- Automatically detects output type (traditional vs. scalable)
- Uses appropriate API endpoint
- Graceful fallback if database not available
- Consistent UX across both output types

## API Endpoints

The interface provides comprehensive REST API endpoints:

### Data Retrieval
- `GET /api/results/{results_name}/pair-scores/` - Pair scores with pagination
  - Query params: `page`, `per_page`, `min_score`, `search`
- `GET /api/results/{results_name}/golden-records/` - Golden records with filtering
  - Query params: `page`, `per_page`, `manufacturer`, `unspsc`, `min_size`, `max_size`, `search`
- `GET /api/results/{results_name}/products/{product_id}/` - Product details
  - Returns: Product info, description, linked products with confidence scores

### Product Comparison ⭐ NEW
- `GET /api/results/{results_name}/compare/{product_a_id}/{product_b_id}/`
  - Traditional output comparison (uses `pair_scores.csv` and vendor catalogs)
  - Returns: Detailed feature-level similarity analysis
  
- `GET /api/results/{results_name}/compare-scalable/{qbi_id}/{product_a_id}/{product_b_id}/`
  - Scalable output comparison (queries `golden_records.db`)
  - Returns: Same detailed analysis as traditional comparison

**Response Format** (both comparison endpoints):
```json
{
  "product_a": {
    "id": "A::47QSWA22D006Q_106361522",
    "manufacturer": "3M",
    "part_number": "14NV4123414111",
    "description": "..."
  },
  "product_b": {
    "id": "B::GS-02F-0008V_531589749",
    "manufacturer": "3M",
    "part_number": "AGM14NV-412341 4111 ea",
    "description": "..."
  },
  "comparison": {
    "part_number": {
      "a_variants": ["14NV4123414111", "14NV412341", ...],
      "b_variants": ["AGM14NV412341", "4111", ...],
      "matched_variants": ["14NV412341"],
      "pn_exact": 0.0,
      "pn_jw": 0.85,
      "pn_lev": 0.82,
      "score_contribution": 0.283
    },
    "manufacturer": {
      "a_original": "3M Company",
      "b_original": "3M",
      "a_normalized": "3M",
      "b_normalized": "3M",
      "similarity": 1.0,
      "score_contribution": 0.25
    },
    "text": {
      "title_similarity": 0.92,
      "description_similarity": 0.88,
      "tfidf_cosine": 0.91,
      "jaccard": 0.87,
      "score_contribution": 0.138
    },
    "unspsc": {
      "a_value": "31191506",
      "b_value": "31191506",
      "exact_match": true,
      "score_contribution": 0.25
    },
    "overall_score": 0.921
  }
}
```

## Customization

### Adding New Features
- Modify `results_viewer/views.py` for new API endpoints
- Update `results_viewer/templates/` for UI changes
- Add new models in `results_viewer/models.py`

### Styling
- Bootstrap 5 is included for responsive design
- Custom CSS in `templates/results_viewer/base.html`
- Easy to customize colors, layouts, and components

## Troubleshooting

### No Results Found
- **Traditional output**: Ensure directory contains `products.csv`, `links.csv`, and `pair_scores.csv`
- **Scalable output**: Ensure directory contains `golden_records.db`
- Check that `PER_RESULTS_DIR` environment variable points to the correct directory
- Verify file permissions
- Check console for any error messages

### Product Details Not Loading
- Ensure `vendor_catalogs_used.csv` exists in the output directory
- This file is automatically created by both `product_entity_resolution.py` and `scalable_entity_resolution.py`
- Contains paths to original vendor catalogs for accurate product detail lookup
- If missing, re-run the entity resolution with the latest version

### Comparison Not Working
- **Error "golden_records.db not found"**: System will automatically fall back to traditional comparison
- Check browser console for error messages
- Verify that both products exist in the results
- For scalable comparison, ensure products belong to the same golden record

### Performance Issues
- Large datasets are paginated automatically (50 items per page)
- Use direct page navigation box for quick access to specific pages
- Results are cached in memory for better performance
- For golden records with 500+ linked products, scrollable list limits height to 400px
- Consider filtering by manufacturer or UNSPSC to reduce result set

### Styling Issues
- Hard refresh browser (Cmd+Shift+R or Ctrl+Shift+R) to clear cached CSS/JS
- Check that Bootstrap 5 and Font Awesome are loading correctly
- View browser console for any 404 errors on static resources

## Architecture

### Backend (Python/Django)
- **`results_viewer/models.py`**: `ResultsManager` class for loading and caching CSV/DB data
- **`results_viewer/views.py`**: Django views for rendering HTML pages and serving data APIs
- **`results_viewer/compare_api.py`**: Product comparison endpoints (traditional and scalable)
- **`results_viewer/urls.py`**: URL routing configuration
- **Integration**: Uses `product_er_toolkit.py` and `query_database.py` from main project

### Frontend (HTML/CSS/JavaScript)
- **`templates/results_viewer/base.html`**: Base template with Bootstrap 5 and Font Awesome
- **`templates/results_viewer/index.html`**: Dashboard landing page
- **`templates/results_viewer/results_detail.html`**: Detail page with tabs, modals, and comparison
- **Styling**: Bootstrap 5 with custom purple gradient theme
- **JavaScript**: Vanilla JS with fetch API for dynamic content loading

### Data Flow
```
Command Line Tool → CSV/DB Output → Web Interface
                                           ↓
                               ResultsManager (cache)
                                           ↓
                                  Django Views/APIs
                                           ↓
                              Frontend (HTML/JS/CSS)
```

## Recent Improvements

### Product Comparison Feature (Latest)
- **Scalable Product Comparison**: Compare products from `golden_records.db` output
- **Intelligent API Selection**: Auto-detects traditional vs. scalable output
- **Complete Score Breakdown**: Shows contribution from each feature component
- **Text Similarity Details**: Includes title, description, TF-IDF, and Jaccard metrics

### UX Enhancements
- **Fixed Header Layout**: Product info and Compare button always visible
- **Scrollable Product List**: 400px max height with sticky table header
- **Direct Page Navigation**: Text box to jump to specific page number
- **Improved Statistics**: Correctly displays Total Products vs. Golden Records
- **Better Contrast**: White text on gradient background for readability

### Technical Improvements
- **Vendor Catalog Tracking**: `vendor_catalogs_used.csv` for accurate product lookup
- **Dual Output Support**: Works with both traditional and scalable entity resolution
- **Graceful Fallback**: Automatic retry with alternative API if primary fails
- **Error Handling**: Comprehensive error messages for debugging

## Development

To extend the interface:

1. **Add new views** in `results_viewer/views.py`
2. **Create templates** in `templates/results_viewer/`
3. **Update URLs** in `results_viewer/urls.py`
4. **Add JavaScript** for interactive features
5. **Add API endpoints** in `results_viewer/compare_api.py` or `views.py`

### Development Workflow
```bash
# Activate virtual environment
cd web_interface
source venv/bin/activate

# Make changes to code

# Run development server
export PER_RESULTS_DIR=/path/to/results
export PYTHONPATH=/path/to/project/root:$PYTHONPATH
python manage.py runserver

# Or use the convenience script
./run_server.sh
```

The interface is designed to be easily extensible while maintaining compatibility with your existing command-line workflow.

## Quick Start Script

The `run_server.sh` script automates setup and server start:

```bash
cd web_interface
./run_server.sh
```

This script will:
1. Create virtual environment (if needed)
2. Install all dependencies
3. Set environment variables (`PER_RESULTS_DIR`, `PYTHONPATH`)
4. Run database migrations
5. Start development server on port 8000

Access at: `http://localhost:8000`
