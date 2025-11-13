# Implementation Plan: Compare Any Two Products Feature

## Overview
This document outlines the plan to add the capability to compare any two products by their IDs, regardless of whether they belong to the same golden record.

## Current State Analysis

### Current Comparison Flow
1. **User Flow:**
   - User clicks "Show Details" on a Golden Record card
   - Modal opens showing product information and linked products
   - User selects 2 products from the linked products list
   - User clicks "Compare Selected" button
   - Comparison modal displays similarity analysis

2. **API Endpoints:**
   - `/api/results/<results_name>/compare/<product_a_id>/<product_b_id>/` - Traditional comparison (directory-based)
   - `/api/results/<results_name>/compare-scalable/<qbi_id>/<product_a_id>/<product_b_id>/` - Scalable comparison (requires qbi_id)
   - `/api/results/<results_name>/compare/<product_a_id>/<product_b_id>/` (database version) - Uses pers_product_staging table

3. **Data Sources Supported:**
   - **Directory-based:** Uses vendor catalogs via `vendor_catalogs_used.csv` and `links.csv`
   - **Scalable (SQLite):** Uses `golden_records.db` database
   - **Database (PostgreSQL/SQLite):** Uses `pers_product_staging` table directly

### Key Constraints
- Current scalable API requires `qbi_id` parameter (products must be from same golden record)
- Directory-based comparison relies on vendor catalog lookup which may fail if products are from different sources
- Database comparison already supports comparing any two products (no qbi_id required)

## Implementation Plan

### Phase 1: Backend API Enhancement

#### 1.1 Create Universal Product Lookup Function
**File:** `web_interface/results_viewer/compare_api.py`

**New Function:** `get_product_by_id(results_name, product_id)`
- **Purpose:** Retrieve product data by ID from any data source
- **Parameters:**
  - `results_name`: The results source name
  - `product_id`: The product ID to look up
- **Returns:** Dictionary with product data or None if not found
- **Logic:**
  1. Check if database source:
     - Query `pers_product_staging` table for the product_id
     - Return product dictionary with fields: contract_number, product_id, manufacturer, part_number, unspsc, title, description, gtin
  2. Check if scalable source (has golden_records.db):
     - Query SQLite database for product_id in golden_record_products table
     - Get contract_number from golden_record_products
     - Query pers_product_staging or load from vendor catalog based on setup
  3. Check if directory source:
     - Load `links.csv` to find contract_number for product_id
     - Use `get_original_vendor_data()` function to retrieve from vendor catalog
     - Return product dictionary

#### 1.2 Create New Universal Comparison API Endpoint
**File:** `web_interface/results_viewer/compare_api.py`

**New Function:** `product_compare_any_api(request, results_name, product_a_id, product_b_id)`
- **Purpose:** Compare any two products without requiring them to be from the same golden record
- **Parameters:**
  - `request`: Django request object
  - `results_name`: The results source name
  - `product_a_id`: Product ID for first product
  - `product_b_id`: Product ID for second product
- **Returns:** JSON response with comparison data (same format as existing comparison APIs)
- **Logic:**
  1. Use `get_product_by_id()` to retrieve both products
  2. If either product is None, return error response
  3. Use existing comparison logic from `product_compare_database_api()`:
     - Initialize `ManufacturerAliasManager`
     - Call `build_pair_features()` to calculate features
     - Calculate part number variants, manufacturer similarity, etc.
     - Calculate score contributions (PN, Manufacturer, Text, UNSPSC, GTIN, Synergy)
     - Build comparison structure
  4. Return JSON response with same structure as existing comparison APIs

#### 1.3 Add URL Route
**File:** `web_interface/results_viewer/urls.py`

**New Route:**
```python
path('api/results/<str:results_name>/compare-any/<str:product_a_id>/<str:product_b_id>/', 
     product_compare_any_api, 
     name='product_compare_any_api')
```

**Notes:**
- Product IDs may contain special characters (e.g., `GS-35F-309AA_107966467`)
- Consider URL encoding/decoding if needed
- May need to handle product IDs with slashes or other special characters

### Phase 2: Frontend UI Enhancement

#### 2.1 Add "Compare Any Products" Button/Feature
**Location Options:**
- **Option A:** Add button to results detail page header (next to filters)
- **Option B:** Add button to dashboard page (top level)
- **Option C:** Add button to navigation menu
- **Recommendation:** Option A - Add to results detail page for context

**File:** `web_interface/templates/results_viewer/results_detail.html`

**Implementation:**
- Add button in the card header section (around line 120-144)
- Button should open a new modal for product ID input

#### 2.2 Create Product Comparison Input Modal
**File:** `web_interface/templates/results_viewer/results_detail.html`

**New Modal:** `compareAnyModal`
- **Structure:**
  - Modal title: "Compare Any Two Products"
  - Two input fields:
    - Product ID A (text input)
    - Product ID B (text input)
  - Optional: Product ID validation/hints
  - "Compare" button
  - "Cancel" button
- **Placement:** Add after existing modals (around line 194)

#### 2.3 Add JavaScript Function for Universal Comparison
**File:** `web_interface/templates/results_viewer/results_detail.html`

**New Function:** `compareAnyProducts(productAId, productBId)`
- **Purpose:** Call the new API endpoint and display comparison results
- **Parameters:**
  - `productAId`: Product ID for first product
  - `productBId`: Product ID for second product
- **Logic:**
  1. Validate inputs (non-empty)
  2. Show loading spinner in comparison modal
  3. Call `/api/results/${resultsName}/compare-any/${productAId}/${productBId}/`
  4. On success: Call existing `displayComparison(data)` function
  5. On error: Display error message in modal
- **Error Handling:**
  - Handle 404 (product not found)
  - Handle 500 (server error)
  - Handle network errors
  - Display user-friendly error messages

#### 2.4 Wire Up Modal Events
- Add event listener for "Compare" button click
- Add event listener for Enter key in input fields
- Add input validation before making API call
- Handle modal close/reset

### Phase 3: Testing & Validation

#### 3.1 Test Cases
1. **Same Golden Record Products:**
   - Compare two products from the same golden record
   - Verify results match existing comparison functionality

2. **Different Golden Records:**
   - Compare products from different golden records
   - Verify comparison works correctly

3. **Cross-Source Comparison:**
   - Test with database sources
   - Test with directory sources
   - Test with scalable sources

4. **Error Cases:**
   - Invalid product ID (non-existent)
   - Empty product IDs
   - Network errors
   - Database connection errors

5. **Edge Cases:**
   - Product IDs with special characters
   - Very long product IDs
   - Products with missing data fields

#### 3.2 Validation Checklist
- [ ] Backend API handles all data source types
- [ ] Frontend modal displays correctly
- [ ] Comparison results match existing format
- [ ] Error messages are user-friendly
- [ ] URL encoding handles special characters
- [ ] Performance is acceptable for large datasets
- [ ] Works with all supported data sources (directory, scalable, database)

## Implementation Details

### Product ID Format
Based on the code analysis, product IDs can be:
- Vendor product IDs: `GS-35F-309AA_107966467` (format: `contract_number_product_id`)
- Golden record GUIDs: `QBI-A5FE537DED4C` (format: `QBI-<hex>`)

The new API should handle both formats:
- For vendor product IDs: Look up in golden_record_products/pers_product_staging
- For GUIDs: Could either:
  - Look up the primary product in the golden record
  - Return error (since comparing GUIDs doesn't make sense - they're golden records, not individual products)

**Recommendation:** Focus on vendor product IDs for comparison, as that's what users see in the linked products table.

### Data Source Priority
When looking up products:
1. **Database sources:** Query `pers_product_staging` table directly (fastest, most reliable)
2. **Scalable sources:** Query SQLite database or vendor catalogs
3. **Directory sources:** Use vendor catalog lookup via `get_original_vendor_data()`

### Reusing Existing Code
The comparison logic in `product_compare_database_api()` (lines 405-581) can be reused almost entirely. The main difference is:
- Current: Gets products from database based on product IDs
- New: Gets products from any source using `get_product_by_id()` helper

## Potential Challenges & Solutions

### Challenge 1: Product ID Format Ambiguity
**Problem:** Product IDs might be contract numbers or GUIDs
**Solution:** 
- Try vendor product ID lookup first (most common)
- If fails, check if it's a GUID and provide helpful error message
- Add validation in frontend to guide users

### Challenge 2: Different Data Sources
**Problem:** Products might be from different data sources
**Solution:** 
- Ensure `results_name` specifies which source to use
- All products must come from the same results source
- Add clear error message if product not found in source

### Challenge 3: Performance
**Problem:** Looking up products from vendor catalogs might be slow
**Solution:**
- Cache vendor catalog data if possible
- Use database queries for database sources (already fast)
- Consider async loading for better UX

### Challenge 4: URL Encoding
**Problem:** Product IDs with special characters might break URLs
**Solution:**
- Use Django's URL encoding/decoding
- Consider POST request instead of GET if needed
- Test with various product ID formats

## File Modification Summary

### Files to Modify:
1. `web_interface/results_viewer/compare_api.py`
   - Add `get_product_by_id()` function
   - Add `product_compare_any_api()` function

2. `web_interface/results_viewer/urls.py`
   - Add new URL route for compare-any endpoint

3. `web_interface/templates/results_viewer/results_detail.html`
   - Add "Compare Any Products" button
   - Add modal for product ID input
   - Add JavaScript function `compareAnyProducts()`
   - Wire up event handlers

### Estimated Effort:
- Backend API: 2-3 hours
- Frontend UI: 1-2 hours
- Testing & Debugging: 1-2 hours
- **Total: 4-7 hours**

## Next Steps
1. Review and approve this plan
2. Implement backend API endpoint
3. Implement frontend UI components
4. Test with various scenarios
5. Deploy and document

