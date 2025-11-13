def get_original_vendor_data(product_id, vendor_catalogs_used, results_path):
    """Get original vendor data for a product ID using vendor catalog tracking file"""
    import os
    import pandas as pd
    
    # Find which vendor catalog contains this product ID
    contract_number = None
    catalog_path = None
    
    # Look up contract number from links.csv
    links_df = pd.read_csv(os.path.join(results_path, 'links.csv'))
    product_link = links_df[links_df['product_id'] == product_id]
    
    if not product_link.empty:
        contract_number = product_link.iloc[0]['contract_number']
        
        # Find catalog path from vendor_catalogs_used.csv
        if contract_number in vendor_catalogs_used:
            catalog_path = vendor_catalogs_used[contract_number]['absolute_path']
    
    if not catalog_path or not os.path.exists(catalog_path):
        return None
    
    try:
        # Load vendor catalog
        vendor_df = pd.read_csv(catalog_path)
        
        # Find the product
        product_row = vendor_df[vendor_df['id'] == product_id]
        
        if not product_row.empty:
            return product_row.iloc[0].to_dict()
        else:
            return None
    except Exception as e:
        print(f"Error loading vendor data for {product_id}: {e}")
        return None


def get_product_by_id(results_name, product_id):
    """
    Universal product lookup function that retrieves product data by ID from any data source.
    
    Args:
        results_name: The results source name
        product_id: The product ID to look up
        
    Returns:
        Dictionary with product data (contract_number, product_id, manufacturer, part_number, 
        unspsc, title, description, gtin) or None if not found
    """
    import os
    import pandas as pd
    from results_viewer.models import results_manager
    
    # Check if this is a database source
    if results_manager.is_database_source(results_name):
        db_config = results_manager.get_database_by_name(results_name)
        
        if not db_config:
            return None
        
        try:
            # Load data from database
            if db_config['type'] == 'postgresql':
                import psycopg2
                conn = psycopg2.connect(db_config['connection_string'])
                query = """
                    SELECT contract_number, product_id, manufacturer, part_number, unspsc, title, description, gtin
                    FROM pers_product_staging
                    WHERE product_id = %s
                """
                cursor = conn.cursor()
                cursor.execute(query, (product_id,))
                row = cursor.fetchone()
                conn.close()
            elif db_config['type'] == 'sqlite':
                import sqlite3
                conn = sqlite3.connect(db_config['connection_string'])
                query = """
                    SELECT contract_number, product_id, manufacturer, part_number, unspsc, title, description, gtin
                    FROM pers_product_staging
                    WHERE product_id = ?
                """
                cursor = conn.cursor()
                cursor.execute(query, (product_id,))
                row = cursor.fetchone()
                conn.close()
            else:
                return None
            
            if not row:
                return None
            
            # Build product dictionary
            columns = ['contract_number', 'product_id', 'manufacturer', 'part_number', 'unspsc', 'title', 'description', 'gtin']
            product = dict(zip(columns, row))
            
            # Clean NaN/None values
            for key in product:
                if product[key] is None or (isinstance(product[key], float) and pd.isna(product[key])):
                    product[key] = None
            
            return product
            
        except Exception as e:
            print(f"Error loading product from database: {e}")
            return None
    
    # Directory or scalable source
    available_results = results_manager.get_available_results()
    result_info = next((r for r in available_results if r['name'] == results_name), None)
    
    if not result_info:
        return None
    
    # Check if this is a scalable source (has golden_records.db)
    db_path = os.path.join(result_info['path'], 'golden_records.db')
    
    if os.path.exists(db_path):
        # Scalable source - try to get from SQLite database
        try:
            from query_database import DatabaseQuery
            db = DatabaseQuery(db_path)
            # Get product from golden_record_products/pers_product_staging if available
            # For scalable sources, we need to look up in the database
            import sqlite3
            conn = sqlite3.connect(db_path)
            
            # Try to get product from golden_record_products first to find contract_number
            links_query = "SELECT contract_number FROM golden_record_products WHERE product_id = ?"
            cursor = conn.cursor()
            cursor.execute(links_query, (product_id,))
            link_row = cursor.fetchone()
            
            if link_row:
                contract_number = link_row[0]
                # Try to get from pers_product_staging
                staging_query = """
                    SELECT contract_number, product_id, manufacturer, part_number, unspsc, title, description, gtin
                    FROM pers_product_staging
                    WHERE product_id = ?
                """
                cursor.execute(staging_query, (product_id,))
                staging_row = cursor.fetchone()
                
                if staging_row:
                    columns = ['contract_number', 'product_id', 'manufacturer', 'part_number', 'unspsc', 'title', 'description', 'gtin']
                    product = dict(zip(columns, staging_row))
                    
                    # Clean NaN/None values
                    for key in product:
                        if product[key] is None or (isinstance(product[key], float) and pd.isna(product[key])):
                            product[key] = None
                    
                    conn.close()
                    return product
            
            conn.close()
        except Exception as e:
            print(f"Error loading product from scalable source: {e}")
            # Fall through to directory-based lookup
    
    # Directory-based source - use vendor catalog lookup
    vendor_catalogs_path = os.path.join(result_info['path'], 'vendor_catalogs_used.csv')
    vendor_catalogs_used = {}
    
    if os.path.exists(vendor_catalogs_path):
        try:
            vendor_catalogs_df = pd.read_csv(vendor_catalogs_path)
            for _, row in vendor_catalogs_df.iterrows():
                vendor_catalogs_used[row['contract_number']] = {
                    'relative_path': row['vendor_catalog_path'],
                    'absolute_path': row['absolute_path']
                }
        except Exception as e:
            print(f"Error loading vendor catalogs tracking file: {e}")
    
    # Get original vendor data
    product_data = get_original_vendor_data(product_id, vendor_catalogs_used, result_info['path'])
    
    if product_data is None:
        return None
    
    # Clean NaN values
    for key, value in product_data.items():
        if pd.isna(value):
            product_data[key] = None
    
    # Ensure we have the standard fields
    standard_product = {
        'contract_number': product_data.get('contract_number') or product_data.get('vendor'),
        'product_id': product_data.get('product_id') or product_data.get('id'),
        'manufacturer': product_data.get('manufacturer', ''),
        'part_number': product_data.get('part_number', ''),
        'unspsc': product_data.get('unspsc', ''),
        'title': product_data.get('title', ''),
        'description': product_data.get('description', ''),
        'gtin': product_data.get('gtin', '')
    }
    
    return standard_product

def _find_alias_csv_path():
    """
    Find the manufacturer aliases CSV file using environment variables or common locations.
    
    Priority order:
    1. MFR_ALIASES_CSV_PATH (fully qualified absolute path) - highest priority
    2. PER_ALIAS_DATA:
       - If absolute path: use directly
       - If relative path/filename: search in common locations
    3. Default filename 'mfr_aliases_with_brands.csv' - search in common locations
    
    Returns:
        str: Path to CSV file if found, None otherwise
    """
    import os
    
    # Priority 1: Fully qualified path from MFR_ALIASES_CSV_PATH
    env_full_path = os.environ.get('MFR_ALIASES_CSV_PATH')
    if env_full_path and os.path.exists(env_full_path):
        return env_full_path
    
    # Priority 2: PER_ALIAS_DATA (can be absolute or relative)
    # Priority 3: Default filename if PER_ALIAS_DATA not set
    alias_path_or_filename = os.environ.get('PER_ALIAS_DATA', 'mfr_aliases_with_brands.csv')
    
    # If PER_ALIAS_DATA is an absolute path, use it directly
    if os.path.isabs(alias_path_or_filename):
        if os.path.exists(alias_path_or_filename):
            return alias_path_or_filename
        # Absolute path doesn't exist, return None (don't search)
        return None
    
    # PER_ALIAS_DATA is relative - search in common locations
    search_locations = []
    
    # Location 1: Same directory as this file (for pers_dashboard structure)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    search_locations.append(current_dir)
    
    # Location 2: Parent directory of web_interface (project root for original structure)
    web_interface_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(web_interface_dir)
    search_locations.append(project_root)
    
    # Location 3: Current working directory
    search_locations.append(os.getcwd())
    
    # Location 4: Parent of current working directory
    search_locations.append(os.path.dirname(os.getcwd()))
    
    # Search for the file in each location
    for location in search_locations:
        candidate_path = os.path.join(location, alias_path_or_filename)
        if os.path.exists(candidate_path):
            return candidate_path
    
    # Not found in any location
    return None

def product_compare_api(request, results_name, product_a_id, product_b_id):
    """API endpoint for detailed product comparison - supports directories and databases."""
    from django.http import JsonResponse
    import pandas as pd
    import sys
    import os
    from results_viewer.models import results_manager
    
    # Add parent directory to Python path to import product_er_toolkit
    # Get the web_interface directory (current file is in results_viewer/)
    web_interface_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Get the project root directory (parent of web_interface)
    project_root = os.path.dirname(web_interface_dir)
    
    # Add project root to Python path if not already there
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Also try adding the current working directory's parent
    cwd_parent = os.path.dirname(os.getcwd())
    if cwd_parent not in sys.path:
        sys.path.insert(0, cwd_parent)
    
    # Check if this is a database source or scalable source
    if results_manager.is_database_source(results_name):
        # Database source - delegate to scalable comparison
        # Extract the GUID from one of the product IDs (they should be from the same golden record)
        db_config = results_manager.get_database_by_name(results_name)
        
        if not db_config:
            return JsonResponse({'error': 'Database not found'}, status=404)
        
        # Load links to find the GUID
        if db_config['type'] == 'postgresql':
            links_df = results_manager.load_links_from_postgresql(db_config['connection_string'])
        elif db_config['type'] == 'sqlite':
            links_df = results_manager.load_links_from_sqlite(db_config['connection_string'])
        else:
            return JsonResponse({'error': 'Unknown database type'}, status=400)
        
        # Find the GUID for product A
        product_a_link = links_df[links_df['product_id'] == product_a_id]
        if product_a_link.empty:
            return JsonResponse({'error': 'Product A not found in database'}, status=404)
        
        qbi_id = product_a_link.iloc[0]['guid']
        
        # Use the database comparison logic (similar to scalable)
        return product_compare_database_api(request, results_name, qbi_id, product_a_id, product_b_id)
    
    available_results = results_manager.get_available_results()
    result_info = next((r for r in available_results if r['name'] == results_name), None)
    
    if not result_info:
        # Check if this is a scalable source
        if result_info and results_manager.is_scalable_source(result_info.get('path', '')):
            # Scalable source - get QBI ID and delegate
            links_df = results_manager.load_links(result_info['path'])
            product_a_link = links_df[links_df['product_id'] == product_a_id]
            if not product_a_link.empty:
                qbi_id = product_a_link.iloc[0]['guid']
                return product_compare_scalable_api(request, results_name, qbi_id, product_a_id, product_b_id)
        return JsonResponse({'error': 'Results not found'}, status=404)
    
    # Load vendor catalog tracking file
    vendor_catalogs_path = os.path.join(result_info['path'], 'vendor_catalogs_used.csv')
    vendor_catalogs_used = {}
    
    if os.path.exists(vendor_catalogs_path):
        try:
            vendor_catalogs_df = pd.read_csv(vendor_catalogs_path)
            for _, row in vendor_catalogs_df.iterrows():
                vendor_catalogs_used[row['contract_number']] = {
                    'relative_path': row['vendor_catalog_path'],
                    'absolute_path': row['absolute_path']
                }
        except Exception as e:
            print(f"Error loading vendor catalogs tracking file: {e}")
    
    # Get original vendor data for both products
    product_a_data = get_original_vendor_data(product_a_id, vendor_catalogs_used, result_info['path'])
    product_b_data = get_original_vendor_data(product_b_id, vendor_catalogs_used, result_info['path'])
    
    if product_a_data is None or product_b_data is None:
        return JsonResponse({'error': 'One or both products not found in vendor catalogs'}, status=404)
    
    # Clean NaN values
    for key, value in product_a_data.items():
        if pd.isna(value):
            product_a_data[key] = None
    
    for key, value in product_b_data.items():
        if pd.isna(value):
            product_b_data[key] = None
    
    # Calculate detailed comparison features
    try:
        from product_er_toolkit import build_pair_features, pn_variants, normalize_manufacturer, jaro_winkler
        from manufacturer_alias_manager import ManufacturerAliasManager
        
        # Initialize alias manager with CSV file if available
        csv_path = _find_alias_csv_path()
        if csv_path:
            alias_manager = ManufacturerAliasManager(csv_path)
            print(f"Loaded manufacturer aliases from {csv_path}")
        else:
            alias_manager = ManufacturerAliasManager()
            print("Warning: Manufacturer alias CSV not found - using basic matching only")
        
        # Build features for comparison
        features = build_pair_features(product_a_data, product_b_data, alias_manager)
        
        # Calculate part number variants and similarities
        pn_a_variants = pn_variants(product_a_data.get('part_number', ''))
        pn_b_variants = pn_variants(product_b_data.get('part_number', ''))
        
        # Check for exact match or alias exact match FIRST
        mfr_exact_match = features.get('mfr_exact', 0) == 1.0
        mfr_alias_exact_match = features.get('mfr_alias_exact', 0) == 1.0
        
        # Calculate manufacturer similarity
        mfr_a = normalize_manufacturer(product_a_data.get('manufacturer', ''))
        mfr_b = normalize_manufacturer(product_b_data.get('manufacturer', ''))
        
        # Use 1.0 if exact match (normalized or alias), otherwise Jaro-Winkler
        if mfr_exact_match or mfr_alias_exact_match:
            mfr_similarity = 1.0
        else:
            mfr_similarity = jaro_winkler(mfr_a, mfr_b) if mfr_a and mfr_b else 0.0
        
        # Calculate text similarity score contribution (updated weights)
        text_jacc = features.get('text_jacc', 0)
        text_tfidf_cos = features.get('text_tfidf_cos', 0)
        text_score_contribution = text_tfidf_cos * 0.15 + text_jacc * 0.10
        
        # Calculate UNSPSC score contribution
        unspsc_score_contribution = 0.0
        if features.get('unspsc_exact', 0) == 1.0:
            unspsc_score_contribution = 0.10  # Reduced weight for UNSPSC exact match
        elif features.get('unspsc_class_match', 0) == 1.0:
            unspsc_score_contribution = 0.08
        elif features.get('unspsc_family_match', 0) == 1.0:
            unspsc_score_contribution = 0.06
        elif features.get('unspsc_segment_match', 0) == 1.0:
            unspsc_score_contribution = 0.04
        
        # Calculate GTIN score contribution
        gtin_score_contribution = 0.0
        gtin_exact = features.get('gtin_exact', 0)
        gtin_mismatch = features.get('gtin_mismatch', 0)
        
        if gtin_exact == 1.0:
            gtin_score_contribution = 0.6  # Very high weight for GTIN match
        elif gtin_mismatch == 1.0:
            gtin_score_contribution = 0.0  # GTIN mismatch = 0 score
        
        # Calculate overall similarity score (updated weights to match current system)
        pn_contrib = features.get('pn_exact_any', 0) * 0.4 if features.get('pn_exact_any', 0) > 0 else features.get('pn_jw', 0) * 0.3
        mfr_contrib = mfr_similarity * 0.25  # Updated from 0.2 to 0.25
        
        # Calculate combined PN + Manufacturer exact match synergy boost
        pn_is_exact = (features.get('pn_exact_any', 0) == 1.0 or 
                       features.get('pn_match_weight', 0) >= 0.4)
        mfr_is_exact = (features.get('mfr_exact', 0) == 1.0 or 
                        features.get('mfr_alias_exact', 0) == 1.0)
        
        synergy_boost = 0.30 if (pn_is_exact and mfr_is_exact) else 0.0
        
        overall_score = gtin_score_contribution + pn_contrib + mfr_contrib + text_score_contribution + unspsc_score_contribution + synergy_boost
        overall_score = min(overall_score, 1.0)  # Cap at 1.0
        
        # Build detailed comparison
        comparison = {
            'part_number': {
                'a_value': product_a_data.get('part_number', ''),
                'b_value': product_b_data.get('part_number', ''),
                'a_variants': pn_a_variants,
                'b_variants': pn_b_variants,
                'exact_match': features.get('pn_exact_any', 0),
                'jaro_winkler': features.get('pn_jw', 0),
                'score_contribution': pn_contrib
            },
            'manufacturer': {
                'a_value': product_a_data.get('manufacturer', ''),
                'b_value': product_b_data.get('manufacturer', ''),
                'a_normalized': mfr_a,
                'b_normalized': mfr_b,
                'exact_match': mfr_exact_match or mfr_alias_exact_match,
                'jaro_winkler': mfr_similarity,
                'score_contribution': mfr_contrib
            },
            'text': {
                'a_title': product_a_data.get('title', ''),
                'b_title': product_b_data.get('title', ''),
                'a_description': product_a_data.get('description', ''),
                'b_description': product_b_data.get('description', ''),
                'title_similarity': features.get('title_jw', 0),
                'description_similarity': features.get('desc_jw', 0),
                'jaccard': text_jacc,
                'tfidf_cosine': text_tfidf_cos,
                'score_contribution': text_score_contribution
            },
            'unspsc': {
                'a_value': product_a_data.get('unspsc', ''),
                'b_value': product_b_data.get('unspsc', ''),
                'exact_match': features.get('unspsc_exact', 0) == 1.0,
                'score_contribution': unspsc_score_contribution
            },
            'gtin': {
                'a_value': product_a_data.get('gtin', ''),
                'b_value': product_b_data.get('gtin', ''),
                'exact_match': gtin_exact == 1.0,
                'mismatch': gtin_mismatch == 1.0,
                'available': features.get('gtin_available', 0) == 1.0,
                'score_contribution': gtin_score_contribution
            } if (product_a_data.get('gtin') and product_b_data.get('gtin') and 
                  str(product_a_data.get('gtin')).strip().upper() not in ['NAN', 'NONE', '', '0'] and
                  str(product_b_data.get('gtin')).strip().upper() not in ['NAN', 'NONE', '', '0']) else None,
            'synergy_boost': {
                'applied': synergy_boost > 0,
                'score_contribution': synergy_boost,
                'description': 'Combined PN + Manufacturer exact match boost'
            } if synergy_boost > 0 else None,
            'overall_score': overall_score,
            'features': features
        }
        
        return JsonResponse({
            'product_a': product_a_data,
            'product_b': product_b_data,
            'comparison': comparison
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error calculating comparison: {str(e)}'}, status=500)


def product_compare_scalable_api(request, results_name, qbi_id, product_a_id, product_b_id):
    """API endpoint for detailed product comparison from scalable entity resolution output or databases."""
    from django.http import JsonResponse
    import sys
    import os
    from results_viewer.models import results_manager
    
    # Add parent directory to Python path to import query_database
    web_interface_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(web_interface_dir)
    
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    cwd_parent = os.path.dirname(os.getcwd())
    if cwd_parent not in sys.path:
        sys.path.insert(0, cwd_parent)
    
    # Check if this is a database source
    if results_manager.is_database_source(results_name):
        # Database source - use database comparison API
        return product_compare_database_api(request, results_name, qbi_id, product_a_id, product_b_id)
    
    # Get results directory for scalable (SQLite) sources
    available_results = results_manager.get_available_results()
    result_info = next((r for r in available_results if r['name'] == results_name), None)
    
    if not result_info:
        return JsonResponse({'error': 'Results not found'}, status=404)
    
    # Check if this is scalable output (has golden_records.db)
    db_path = os.path.join(result_info['path'], 'golden_records.db')
    
    if not os.path.exists(db_path):
        return JsonResponse({'error': 'This is not a scalable entity resolution output (golden_records.db not found)'}, status=400)
    
    try:
        # Import DatabaseQuery class from query_database.py
        from query_database import DatabaseQuery
        
        # Create database connection
        db = DatabaseQuery(db_path)
        
        # Call compare_products method
        comparison_result = db.compare_products(qbi_id, product_a_id, product_b_id)
        
        if comparison_result is None:
            return JsonResponse({'error': 'One or both products not found in database'}, status=404)
        
        # Transform the result to match the format expected by frontend
        # The query_database.py returns a slightly different structure, so we'll adapt it
        
        product_a = comparison_result['product_a']
        product_b = comparison_result['product_b']
        
        # Build comparison structure matching the traditional API format
        comparison = {
            'part_number': {
                'a_value': product_a.get('part_number', ''),
                'b_value': product_b.get('part_number', ''),
                'a_variants': comparison_result['part_number']['product_a_variants'],
                'b_variants': comparison_result['part_number']['product_b_variants'],
                'exact_match': 1.0 if comparison_result['part_number']['exact_match'] else 0.0,
                'jaro_winkler': comparison_result['part_number']['jaro_winkler'],
                'score_contribution': comparison_result['part_number']['score_contribution']
            },
            'manufacturer': {
                'a_value': product_a.get('manufacturer', ''),
                'b_value': product_b.get('manufacturer', ''),
                'a_normalized': comparison_result['manufacturer']['product_a_normalized'],
                'b_normalized': comparison_result['manufacturer']['product_b_normalized'],
                'jaro_winkler': comparison_result['manufacturer']['jaro_winkler'],
                'score_contribution': comparison_result['manufacturer']['score_contribution']
            },
            'text': {
                'a_title': product_a.get('title', ''),
                'b_title': product_b.get('title', ''),
                'a_description': product_a.get('description', ''),
                'b_description': product_b.get('description', ''),
                'title_similarity': comparison_result['text_similarity']['title_similarity'],
                'description_similarity': comparison_result['text_similarity']['description_similarity'],
                'score_contribution': comparison_result['text_similarity'].get('score_contribution', 0.0)
            },
            'unspsc': {
                'a_value': product_a.get('unspsc', ''),
                'b_value': product_b.get('unspsc', ''),
                'exact_match': comparison_result.get('unspsc', {}).get('exact_match', False),
                'score_contribution': comparison_result.get('unspsc', {}).get('score_contribution', 0.0)
            } if 'unspsc' in comparison_result else None,
            'gtin': {
                'a_value': product_a.get('gtin', ''),
                'b_value': product_b.get('gtin', ''),
                'exact_match': comparison_result.get('gtin', {}).get('exact_match', False),
                'mismatch': comparison_result.get('gtin', {}).get('mismatch', False),
                'available': comparison_result.get('gtin', {}).get('available', False),
                'score_contribution': comparison_result.get('gtin', {}).get('score_contribution', 0.0)
            } if 'gtin' in comparison_result and comparison_result.get('gtin') is not None else None,
            'synergy_boost': comparison_result.get('synergy_boost'),
            'overall_score': comparison_result['overall_score'],
            'features': {
                'pn_exact_any': 1.0 if comparison_result['part_number']['exact_match'] else 0.0,
                'pn_jw': comparison_result['part_number']['jaro_winkler'],
                'mfr_jw': comparison_result['manufacturer']['jaro_winkler'],
                'text_jacc': comparison_result['text_similarity']['jaccard'],
                'text_tfidf_cos': comparison_result['text_similarity']['tfidf_cosine']
            }
        }
        
        return JsonResponse({
            'product_a': product_a,
            'product_b': product_b,
            'comparison': comparison
        })
        
    except ImportError as e:
        return JsonResponse({'error': f'Could not import query_database module: {str(e)}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Error calculating comparison: {str(e)}'}, status=500)


def product_compare_database_api(request, results_name, qbi_id, product_a_id, product_b_id):
    """API endpoint for detailed product comparison from database sources (PostgreSQL/SQLite)."""
    from django.http import JsonResponse
    import sys
    import os
    import pandas as pd
    from results_viewer.models import results_manager
    
    # Add parent directory to Python path to import product_er_toolkit
    web_interface_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(web_interface_dir)
    
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    cwd_parent = os.path.dirname(os.getcwd())
    if cwd_parent not in sys.path:
        sys.path.insert(0, cwd_parent)
    
    # Get database configuration
    db_config = results_manager.get_database_by_name(results_name)
    
    if not db_config:
        return JsonResponse({'error': 'Database not found'}, status=404)
    
    try:
        # Import comparison utilities
        from product_er_toolkit import build_pair_features, pn_variants, normalize_manufacturer, jaro_winkler
        from manufacturer_alias_manager import ManufacturerAliasManager
        
        # Initialize alias manager with CSV file if available
        csv_path = _find_alias_csv_path()
        if csv_path:
            alias_manager = ManufacturerAliasManager(csv_path)
            print(f"Loaded manufacturer aliases from {csv_path}")
        else:
            alias_manager = ManufacturerAliasManager()
            print("Warning: Manufacturer alias CSV not found - using basic matching only")
        
        # Load data from database
        if db_config['type'] == 'postgresql':
            import psycopg2
            conn = psycopg2.connect(db_config['connection_string'])
        elif db_config['type'] == 'sqlite':
            import sqlite3
            conn = sqlite3.connect(db_config['connection_string'])
        else:
            return JsonResponse({'error': 'Unknown database type'}, status=400)
        
        # Get product data from pers_product_staging (original vendor data, not merged golden record)
        if db_config['type'] == 'postgresql':
            query = """
                SELECT contract_number, product_id, manufacturer, part_number, unspsc, title, description, gtin
                FROM pers_product_staging
                WHERE product_id = %s
            """
        else:
            query = """
                SELECT contract_number, product_id, manufacturer, part_number, unspsc, title, description, gtin
                FROM pers_product_staging
                WHERE product_id = ?
            """
        
        cursor = conn.cursor()
        
        # Get product A
        cursor.execute(query, (product_a_id,))
        product_a_row = cursor.fetchone()
        if not product_a_row:
            conn.close()
            return JsonResponse({'error': 'Product A not found in database'}, status=404)
        
        # Get product B
        cursor.execute(query, (product_b_id,))
        
        product_b_row = cursor.fetchone()
        if not product_b_row:
            conn.close()
            return JsonResponse({'error': 'Product B not found in database'}, status=404)
        
        conn.close()
        
        # Build product dictionaries
        columns = ['contract_number', 'product_id', 'manufacturer', 'part_number', 'unspsc', 'title', 'description', 'gtin']
        product_a = dict(zip(columns, product_a_row))
        product_b = dict(zip(columns, product_b_row))
        
        # Clean NaN/None values
        for prod in [product_a, product_b]:
            for key in prod:
                if prod[key] is None or (isinstance(prod[key], float) and pd.isna(prod[key])):
                    prod[key] = None
        
        # Build features for comparison
        features = build_pair_features(product_a, product_b, alias_manager)
        
        # Calculate part number variants and similarities
        pn_a_variants = pn_variants(product_a.get('part_number', ''))
        pn_b_variants = pn_variants(product_b.get('part_number', ''))
        
        # Check for exact match or alias exact match FIRST
        mfr_exact_match = features.get('mfr_exact', 0) == 1.0
        mfr_alias_exact_match = features.get('mfr_alias_exact', 0) == 1.0
        
        # Calculate manufacturer similarity
        mfr_a = normalize_manufacturer(product_a.get('manufacturer', ''))
        mfr_b = normalize_manufacturer(product_b.get('manufacturer', ''))
        
        # Use 1.0 if exact match (normalized or alias), otherwise Jaro-Winkler
        if mfr_exact_match or mfr_alias_exact_match:
            mfr_similarity = 1.0
        else:
            mfr_similarity = jaro_winkler(mfr_a, mfr_b) if mfr_a and mfr_b else 0.0
        
        # Calculate score contributions
        text_jacc = features.get('text_jacc', 0)
        text_tfidf_cos = features.get('text_tfidf_cos', 0)
        text_score_contribution = text_tfidf_cos * 0.15 + text_jacc * 0.10
        
        # UNSPSC score
        unspsc_score_contribution = 0.0
        if features.get('unspsc_exact', 0) == 1.0:
            unspsc_score_contribution = 0.10  # Reduced weight for UNSPSC exact match
        elif features.get('unspsc_class_match', 0) == 1.0:
            unspsc_score_contribution = 0.08
        elif features.get('unspsc_family_match', 0) == 1.0:
            unspsc_score_contribution = 0.06
        elif features.get('unspsc_segment_match', 0) == 1.0:
            unspsc_score_contribution = 0.04
        
        # GTIN score
        gtin_score_contribution = 0.0
        gtin_exact = features.get('gtin_exact', 0)
        gtin_mismatch = features.get('gtin_mismatch', 0)
        
        if gtin_exact == 1.0:
            gtin_score_contribution = 0.6
        elif gtin_mismatch == 1.0:
            gtin_score_contribution = 0.0
        
        # Part number and manufacturer contributions
        pn_contrib = features.get('pn_exact_any', 0) * 0.4 if features.get('pn_exact_any', 0) > 0 else features.get('pn_jw', 0) * 0.3
        mfr_contrib = mfr_similarity * 0.25
        
        # Synergy boost
        pn_is_exact = (features.get('pn_exact_any', 0) == 1.0 or features.get('pn_match_weight', 0) >= 0.4)
        mfr_is_exact = (features.get('mfr_exact', 0) == 1.0 or features.get('mfr_alias_exact', 0) == 1.0)
        synergy_boost = 0.30 if (pn_is_exact and mfr_is_exact) else 0.0
        
        overall_score = gtin_score_contribution + pn_contrib + mfr_contrib + text_score_contribution + unspsc_score_contribution + synergy_boost
        overall_score = min(overall_score, 1.0)  # Cap at 1.0
        
        # Build comparison structure
        comparison = {
            'part_number': {
                'a_value': product_a.get('part_number', ''),
                'b_value': product_b.get('part_number', ''),
                'a_variants': pn_a_variants,
                'b_variants': pn_b_variants,
                'exact_match': features.get('pn_exact_any', 0),
                'jaro_winkler': features.get('pn_jw', 0),
                'score_contribution': pn_contrib
            },
            'manufacturer': {
                'a_value': product_a.get('manufacturer', ''),
                'b_value': product_b.get('manufacturer', ''),
                'a_normalized': mfr_a,
                'b_normalized': mfr_b,
                'exact_match': mfr_exact_match or mfr_alias_exact_match,
                'jaro_winkler': mfr_similarity,
                'score_contribution': mfr_contrib
            },
            'text': {
                'a_title': product_a.get('title', ''),
                'b_title': product_b.get('title', ''),
                'a_description': product_a.get('description', ''),
                'b_description': product_b.get('description', ''),
                'title_similarity': features.get('title_jw', 0),
                'description_similarity': features.get('desc_jw', 0),
                'jaccard': text_jacc,
                'tfidf_cosine': text_tfidf_cos,
                'score_contribution': text_score_contribution
            },
            'unspsc': {
                'a_value': product_a.get('unspsc', ''),
                'b_value': product_b.get('unspsc', ''),
                'exact_match': features.get('unspsc_exact', 0) == 1.0,
                'score_contribution': unspsc_score_contribution
            },
            'gtin': {
                'a_value': product_a.get('gtin', ''),
                'b_value': product_b.get('gtin', ''),
                'exact_match': gtin_exact == 1.0,
                'mismatch': gtin_mismatch == 1.0,
                'available': features.get('gtin_available', 0) == 1.0,
                'score_contribution': gtin_score_contribution
            } if (product_a.get('gtin') and product_b.get('gtin') and 
                  str(product_a.get('gtin')).strip().upper() not in ['NAN', 'NONE', '', '0'] and
                  str(product_b.get('gtin')).strip().upper() not in ['NAN', 'NONE', '', '0']) else None,
            'synergy_boost': {
                'applied': synergy_boost > 0,
                'score_contribution': synergy_boost,
                'description': 'Combined PN + Manufacturer exact match boost'
            } if synergy_boost > 0 else None,
            'overall_score': overall_score,
            'features': features
        }
        
        return JsonResponse({
            'product_a': product_a,
            'product_b': product_b,
            'comparison': comparison
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Error calculating comparison: {str(e)}'}, status=500)


def product_compare_any_api(request, results_name, product_a_id, product_b_id):
    """
    API endpoint for comparing any two products by their IDs, regardless of whether they belong 
    to the same golden record. Works across all data source types.
    
    Args:
        request: Django request object
        results_name: The results source name
        product_a_id: Product ID for first product
        product_b_id: Product ID for second product
        
    Returns:
        JSON response with comparison data (same format as existing comparison APIs)
    """
    from django.http import JsonResponse
    import sys
    import os
    import pandas as pd
    
    # Add parent directory to Python path to import product_er_toolkit
    web_interface_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(web_interface_dir)
    
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    cwd_parent = os.path.dirname(os.getcwd())
    if cwd_parent not in sys.path:
        sys.path.insert(0, cwd_parent)
    
    # Get both products using universal lookup
    product_a = get_product_by_id(results_name, product_a_id)
    product_b = get_product_by_id(results_name, product_b_id)
    
    if product_a is None:
        return JsonResponse({'error': f'Product A (ID: {product_a_id}) not found in source'}, status=404)
    
    if product_b is None:
        return JsonResponse({'error': f'Product B (ID: {product_b_id}) not found in source'}, status=404)
    
    try:
        # Import comparison utilities
        from product_er_toolkit import build_pair_features, pn_variants, normalize_manufacturer, jaro_winkler
        from manufacturer_alias_manager import ManufacturerAliasManager
        
        # Initialize alias manager with CSV file if available
        csv_path = _find_alias_csv_path()
        if csv_path:
            alias_manager = ManufacturerAliasManager(csv_path)
            print(f"Loaded manufacturer aliases from {csv_path}")
        else:
            alias_manager = ManufacturerAliasManager()
            print("Warning: Manufacturer alias CSV not found - using basic matching only")
        
        # Build features for comparison
        features = build_pair_features(product_a, product_b, alias_manager)
        
        # Calculate part number variants and similarities
        pn_a_variants = pn_variants(product_a.get('part_number', ''))
        pn_b_variants = pn_variants(product_b.get('part_number', ''))
        
        # Check for exact match or alias exact match FIRST
        mfr_exact_match = features.get('mfr_exact', 0) == 1.0
        mfr_alias_exact_match = features.get('mfr_alias_exact', 0) == 1.0
        
        # Calculate manufacturer similarity
        mfr_a = normalize_manufacturer(product_a.get('manufacturer', ''))
        mfr_b = normalize_manufacturer(product_b.get('manufacturer', ''))
        
        # Use 1.0 if exact match (normalized or alias), otherwise Jaro-Winkler
        if mfr_exact_match or mfr_alias_exact_match:
            mfr_similarity = 1.0
        else:
            mfr_similarity = jaro_winkler(mfr_a, mfr_b) if mfr_a and mfr_b else 0.0
        
        # Calculate score contributions
        text_jacc = features.get('text_jacc', 0)
        text_tfidf_cos = features.get('text_tfidf_cos', 0)
        text_score_contribution = text_tfidf_cos * 0.15 + text_jacc * 0.10
        
        # UNSPSC score
        unspsc_score_contribution = 0.0
        if features.get('unspsc_exact', 0) == 1.0:
            unspsc_score_contribution = 0.10  # Reduced weight for UNSPSC exact match
        elif features.get('unspsc_class_match', 0) == 1.0:
            unspsc_score_contribution = 0.08
        elif features.get('unspsc_family_match', 0) == 1.0:
            unspsc_score_contribution = 0.06
        elif features.get('unspsc_segment_match', 0) == 1.0:
            unspsc_score_contribution = 0.04
        
        # GTIN score
        gtin_score_contribution = 0.0
        gtin_exact = features.get('gtin_exact', 0)
        gtin_mismatch = features.get('gtin_mismatch', 0)
        
        if gtin_exact == 1.0:
            gtin_score_contribution = 0.6
        elif gtin_mismatch == 1.0:
            gtin_score_contribution = 0.0
        
        # Part number and manufacturer contributions
        pn_contrib = features.get('pn_exact_any', 0) * 0.4 if features.get('pn_exact_any', 0) > 0 else features.get('pn_jw', 0) * 0.3
        mfr_contrib = mfr_similarity * 0.25
        
        # Synergy boost
        pn_is_exact = (features.get('pn_exact_any', 0) == 1.0 or features.get('pn_match_weight', 0) >= 0.4)
        mfr_is_exact = (features.get('mfr_exact', 0) == 1.0 or features.get('mfr_alias_exact', 0) == 1.0)
        synergy_boost = 0.30 if (pn_is_exact and mfr_is_exact) else 0.0
        
        overall_score = gtin_score_contribution + pn_contrib + mfr_contrib + text_score_contribution + unspsc_score_contribution + synergy_boost
        overall_score = min(overall_score, 1.0)  # Cap at 1.0
        
        # Build comparison structure (same format as product_compare_database_api)
        comparison = {
            'part_number': {
                'a_value': product_a.get('part_number', ''),
                'b_value': product_b.get('part_number', ''),
                'a_variants': pn_a_variants,
                'b_variants': pn_b_variants,
                'exact_match': features.get('pn_exact_any', 0),
                'jaro_winkler': features.get('pn_jw', 0),
                'score_contribution': pn_contrib
            },
            'manufacturer': {
                'a_value': product_a.get('manufacturer', ''),
                'b_value': product_b.get('manufacturer', ''),
                'a_normalized': mfr_a,
                'b_normalized': mfr_b,
                'exact_match': mfr_exact_match or mfr_alias_exact_match,
                'jaro_winkler': mfr_similarity,
                'score_contribution': mfr_contrib
            },
            'text': {
                'a_title': product_a.get('title', ''),
                'b_title': product_b.get('title', ''),
                'a_description': product_a.get('description', ''),
                'b_description': product_b.get('description', ''),
                'title_similarity': features.get('title_jw', 0),
                'description_similarity': features.get('desc_jw', 0),
                'jaccard': text_jacc,
                'tfidf_cosine': text_tfidf_cos,
                'score_contribution': text_score_contribution
            },
            'unspsc': {
                'a_value': product_a.get('unspsc', ''),
                'b_value': product_b.get('unspsc', ''),
                'exact_match': features.get('unspsc_exact', 0) == 1.0,
                'score_contribution': unspsc_score_contribution
            },
            'gtin': {
                'a_value': product_a.get('gtin', ''),
                'b_value': product_b.get('gtin', ''),
                'exact_match': gtin_exact == 1.0,
                'mismatch': gtin_mismatch == 1.0,
                'available': features.get('gtin_available', 0) == 1.0,
                'score_contribution': gtin_score_contribution
            } if (product_a.get('gtin') and product_b.get('gtin') and 
                  str(product_a.get('gtin')).strip().upper() not in ['NAN', 'NONE', '', '0'] and
                  str(product_b.get('gtin')).strip().upper() not in ['NAN', 'NONE', '', '0']) else None,
            'synergy_boost': {
                'applied': synergy_boost > 0,
                'score_contribution': synergy_boost,
                'description': 'Combined PN + Manufacturer exact match boost'
            } if synergy_boost > 0 else None,
            'overall_score': overall_score,
            'features': features
        }
        
        return JsonResponse({
            'product_a': product_a,
            'product_b': product_b,
            'comparison': comparison
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Error calculating comparison: {str(e)}'}, status=500)