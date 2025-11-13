"""
Views for the results viewer app.
"""
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
import json
import pandas as pd
from .models import results_manager

def index(request):
    """Main dashboard view - includes both directories and databases."""
    # Get directory-based results
    available_results = results_manager.get_available_results()
    
    # Get stats for each results directory
    results_with_stats = []
    for result in available_results:
        stats = results_manager.get_summary_stats(result['path'])
        result['stats'] = stats
        result['source_type'] = 'directory'
        
        # Check if this is a scalable source (has golden_records.db)
        result['is_scalable'] = results_manager.is_scalable_source(result['path'])
        
        results_with_stats.append(result)
    
    # Get database sources
    available_databases = results_manager.get_available_databases()
    
    for db in available_databases:
        # Only fetch stats if database is connected
        if db.get('connection_status') == 'connected':
            stats = results_manager.get_summary_stats_from_db(
                db['database_type'], 
                db['connection_string']
            )
            db['stats'] = stats
        else:
            db['stats'] = {
                'total_golden_records': 0,
                'total_products': 0,
                'matched_products': 0,
                'unique_products': 0,
                'total_links': 0,
                'avg_confidence': 0,
                'top_manufacturers': {},
                'top_unspsc': {},
                'total_pair_scores': 0
            }
        
        results_with_stats.append(db)
    
    context = {
        'available_results': results_with_stats,
        'title': 'Product Entity Resolution - Results Dashboard'
    }
    return render(request, 'results_viewer/index.html', context)

def results_detail(request, results_name):
    """Detailed view for a specific results set - supports directories and databases."""
    
    # Check if this is a database source
    if results_manager.is_database_source(results_name):
        # Database source
        db_config = results_manager.get_database_by_name(results_name)
        
        if not db_config:
            return render(request, 'results_viewer/error.html', {'error': 'Database not found'})
        
        # Get summary stats from database with error handling
        try:
            stats = results_manager.get_summary_stats_from_db(
                db_config['type'],
                db_config['connection_string']
            )
            # Ensure stats is a dict with all required keys
            if not stats:
                stats = {
                    'total_golden_records': 0,
                    'total_products': 0,
                    'matched_products': 0,
                    'unique_products': 0,
                    'total_links': 0,
                    'avg_confidence': 0,
                    'top_manufacturers': {},
                    'top_unspsc': {},
                    'total_pair_scores': 0
                }
        except Exception as e:
            # If stats retrieval fails, use empty stats
            stats = {
                'total_golden_records': 0,
                'total_products': 0,
                'matched_products': 0,
                'unique_products': 0,
                'total_links': 0,
                'avg_confidence': 0,
                'top_manufacturers': {},
                'top_unspsc': {},
                'total_pair_scores': 0
            }
        
        result_info = {
            'name': db_config['name'],
            'display_name': db_config.get('display_name', db_config['name']),
            'description': db_config.get('description', ''),
            'source_type': 'database',
            'database_type': db_config['type'],
            'is_scalable': True,  # Database sources don't have pair_scores
            'connection_status': db_config.get('connection_status', 'unknown')
        }
        
    else:
        # Directory source
        available_results = results_manager.get_available_results()
        result_info = next((r for r in available_results if r['name'] == results_name), None)
        
        if not result_info:
            return render(request, 'results_viewer/error.html', {'error': 'Results not found'})
        
        # Get summary stats from directory
        stats = results_manager.get_summary_stats(result_info['path'])
        
        # Check if this is a scalable source
        result_info['is_scalable'] = results_manager.is_scalable_source(result_info['path'])
        result_info['source_type'] = 'directory'
    
    context = {
        'result_info': result_info,
        'stats': stats,
        'title': f'Results: {result_info["display_name"]}'
    }
    return render(request, 'results_viewer/results_detail.html', context)

def pair_scores_api(request, results_name):
    """API endpoint for pair scores data with pagination and filtering."""
    available_results = results_manager.get_available_results()
    result_info = next((r for r in available_results if r['name'] == results_name), None)
    
    if not result_info:
        return JsonResponse({'error': 'Results not found'}, status=404)
    
    pair_scores_df = results_manager.load_pair_scores(result_info['path'])
    
    if pair_scores_df.empty:
        return JsonResponse({'data': [], 'total': 0, 'pages': 0})
    
    # Get filter parameters
    min_score = float(request.GET.get('min_score', 0))
    max_score = float(request.GET.get('max_score', 1))
    search = request.GET.get('search', '')
    
    # Apply filters
    filtered_df = pair_scores_df[
        (pair_scores_df['score'] >= min_score) & 
        (pair_scores_df['score'] <= max_score)
    ]
    
    if search:
        filtered_df = filtered_df[
            filtered_df['L'].str.contains(search, case=False, na=False) |
            filtered_df['R'].str.contains(search, case=False, na=False)
        ]
    
    # Sort by score descending
    filtered_df = filtered_df.sort_values('score', ascending=False)
    
    # Pagination - convert DataFrame to list first
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 50))
    
    data_list = filtered_df.to_dict('records')
    
    # Clean NaN values for JSON serialization
    for item in data_list:
        for key, value in item.items():
            if pd.isna(value):
                item[key] = None
    
    paginator = Paginator(data_list, per_page)
    page_obj = paginator.get_page(page)
    
    return JsonResponse({
        'data': page_obj.object_list,
        'total': paginator.count,
        'pages': paginator.num_pages,
        'current_page': page,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous()
    })

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

def product_detail_api(request, results_name, product_id):
    """API endpoint for detailed product information - supports directories and databases."""
    import os
    import pandas as pd
    
    # Check if this is a database source
    if results_manager.is_database_source(results_name):
        # Database source
        db_config = results_manager.get_database_by_name(results_name)
        
        if not db_config:
            return JsonResponse({'error': 'Database not found'}, status=404)
        
        # Load from database
        if db_config['type'] == 'postgresql':
            products_df = results_manager.load_products_from_postgresql(db_config['connection_string'])
            links_df = results_manager.load_links_from_postgresql(db_config['connection_string'])
        elif db_config['type'] == 'sqlite':
            products_df = results_manager.load_products_from_sqlite(db_config['connection_string'])
            links_df = results_manager.load_links_from_sqlite(db_config['connection_string'])
        else:
            return JsonResponse({'error': 'Unknown database type'}, status=400)
        
        # Find product by GUID (golden record)
        product = products_df[products_df['guid'] == product_id]
        
        if product.empty:
            return JsonResponse({'error': 'Product not found'}, status=404)
        
        product_data = product.iloc[0].to_dict()
        
        # Get linked products
        linked_products = links_df[links_df['guid'] == product_data['guid']].copy()
        if 'created_at' in linked_products.columns:
            linked_products = linked_products.sort_values('created_at', ascending=True, na_position='last')
        linked_products_data = linked_products.to_dict('records')
        
        # Update the size field to reflect the actual number of linked products
        product_data['size'] = len(linked_products_data)
        
    else:
        # Directory source
        available_results = results_manager.get_available_results()
        result_info = next((r for r in available_results if r['name'] == results_name), None)
        
        if not result_info:
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
        
        # Check if this is a vendor product ID (contains underscore) or golden record GUID
        is_contract_number = '_' in product_id and not product_id.startswith('QBI-')
        
        if is_contract_number and vendor_catalogs_used:
            # Get original vendor data for vendor product ID
            product_data = get_original_vendor_data(product_id, vendor_catalogs_used, result_info['path'])
            if product_data is None:
                return JsonResponse({'error': 'Product not found in vendor catalogs'}, status=404)
            
            # Get linked products from the golden record and add GUID to product data
            links_df = results_manager.load_links(result_info['path'])
            linked_product = links_df[links_df['product_id'] == product_id]
            if not linked_product.empty:
                guid = linked_product.iloc[0]['guid']
                # Add GUID to the product data
                product_data['guid'] = guid
                linked_products = links_df[links_df['guid'] == guid].copy()
                if 'created_at' in linked_products.columns:
                    linked_products = linked_products.sort_values('created_at', ascending=True, na_position='last')
                linked_products_data = linked_products.to_dict('records')
            else:
                product_data['guid'] = None
                linked_products_data = []
        else:
            # Find product by GUID (golden record)
            products_df = results_manager.load_products(result_info['path'])
            product = products_df[products_df['guid'] == product_id]
            
            if product.empty:
                return JsonResponse({'error': 'Product not found'}, status=404)
            
            product_data = product.iloc[0].to_dict()
            
            # Get linked products
            links_df = results_manager.load_links(result_info['path'])
            linked_products = links_df[links_df['guid'] == product_data['guid']].copy()
            if 'created_at' in linked_products.columns:
                linked_products = linked_products.sort_values('created_at', ascending=True, na_position='last')
            linked_products_data = linked_products.to_dict('records')
            
            # Update the size field to reflect the actual number of linked products
            product_data['size'] = len(linked_products_data)
    
    # Clean NaN values for JSON serialization
    for key, value in product_data.items():
        if pd.isna(value):
            product_data[key] = None
    
    # Clean NaN values for linked products
    for item in linked_products_data:
        for key, value in item.items():
            if pd.isna(value):
                item[key] = None
    
    return JsonResponse({
        'product': product_data,
        'linked_products': linked_products_data
    })

def golden_records_api(request, results_name):
    """API endpoint for golden records with pagination and filtering - supports directories and databases."""
    
    # Get pagination parameters
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 50))
    
    # Get filter parameters
    manufacturer = request.GET.get('manufacturer', '')
    unspsc = request.GET.get('unspsc', '')
    search = request.GET.get('search', '')
    size_filter = request.GET.get('size', '')
    
    # Check if this is a database source
    if results_manager.is_database_source(results_name):
        # Database source - use optimized SQL queries
        db_config = results_manager.get_database_by_name(results_name)
        
        if not db_config:
            return JsonResponse({'error': 'Database not found'}, status=404)
        
        # For PostgreSQL, use optimized paginated query with SQL-level filtering
        if db_config['type'] == 'postgresql':
            result = results_manager.get_golden_records_paginated_postgresql(
                connection_string=db_config['connection_string'],
                page=page,
                per_page=per_page,
                manufacturer=manufacturer if manufacturer else None,
                unspsc=unspsc if unspsc else None,
                search=search if search else None,
                size_filter=size_filter if size_filter else None
            )
            return JsonResponse(result)
        
        elif db_config['type'] == 'sqlite':
            # For SQLite, still use the old method (can be optimized later)
            products_df = results_manager.load_products_from_sqlite(db_config['connection_string'])
            links_df = results_manager.load_links_from_sqlite(db_config['connection_string'])
            
            if products_df.empty:
                return JsonResponse({'data': [], 'total': 0, 'pages': 0, 'current_page': page, 'has_next': False, 'has_previous': False})
            
            # Apply filters (fallback to in-memory for SQLite - can be optimized later)
            filtered_df = products_df.copy()
            
            if manufacturer and 'manufacturer' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['manufacturer'].str.contains(manufacturer, case=False, na=False)]
            
            if unspsc:
                if 'unspsc' in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df['unspsc'].str.contains(unspsc, case=False, na=False)]
            
            if search:
                search_conditions = []
                if 'guid' in filtered_df.columns:
                    search_conditions.append(filtered_df['guid'].str.contains(search, case=False, na=False))
                if 'title' in filtered_df.columns:
                    search_conditions.append(filtered_df['title'].str.contains(search, case=False, na=False))
                if 'description' in filtered_df.columns:
                    search_conditions.append(filtered_df['description'].str.contains(search, case=False, na=False))
                if 'part_number' in filtered_df.columns:
                    search_conditions.append(filtered_df['part_number'].str.contains(search, case=False, na=False))
                
                if search_conditions:
                    combined_condition = search_conditions[0]
                    for condition in search_conditions[1:]:
                        combined_condition = combined_condition | condition
                    filtered_df = filtered_df[combined_condition]
            
            if size_filter:
                if size_filter == 'matched':
                    filtered_df = filtered_df[filtered_df['size'] > 1]
                elif size_filter == 'unique':
                    filtered_df = filtered_df[filtered_df['size'] == 1]
            
            # Pagination
            data_list = filtered_df.to_dict('records')
            for item in data_list:
                for key, value in item.items():
                    if pd.isna(value):
                        item[key] = None
            
            paginator = Paginator(data_list, per_page)
            page_obj = paginator.get_page(page)
            
            return JsonResponse({
                'data': page_obj.object_list,
                'total': paginator.count,
                'pages': paginator.num_pages,
                'current_page': page,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            })
        
        else:
            return JsonResponse({'error': 'Unknown database type'}, status=400)
    
    else:
        # Directory source - use existing method (file-based)
        available_results = results_manager.get_available_results()
        result_info = next((r for r in available_results if r['name'] == results_name), None)
        
        if not result_info:
            return JsonResponse({'error': 'Results not found'}, status=404)
        
        products_df = results_manager.load_products(result_info['path'])
        links_df = results_manager.load_links(result_info['path'])
        
        if products_df.empty:
            return JsonResponse({'data': [], 'total': 0, 'pages': 0, 'current_page': page, 'has_next': False, 'has_previous': False})
        
        # Apply filters
        filtered_df = products_df.copy()
        
        if manufacturer and 'manufacturer' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['manufacturer'].str.contains(manufacturer, case=False, na=False)]
        
        if unspsc:
            if 'unspsc' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['unspsc'].str.contains(unspsc, case=False, na=False)]
            elif 'brand' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['brand'].str.contains(unspsc, case=False, na=False)]
        
        if search:
            # First, check if search matches contract_number or product_id in golden_record_products
            matching_links = links_df[
                links_df['contract_number'].str.contains(search, case=False, na=False) |
                links_df['product_id'].str.contains(search, case=False, na=False)
            ]
            
            if not matching_links.empty:
                matching_guids = matching_links['guid'].unique()
                vendor_product_matches = filtered_df[filtered_df['guid'].isin(matching_guids)]
            else:
                vendor_product_matches = pd.DataFrame()
            
            # Also search in product fields
            search_conditions = []
            if 'guid' in filtered_df.columns:
                search_conditions.append(filtered_df['guid'].str.contains(search, case=False, na=False))
            if 'title' in filtered_df.columns:
                search_conditions.append(filtered_df['title'].str.contains(search, case=False, na=False))
            if 'description' in filtered_df.columns:
                search_conditions.append(filtered_df['description'].str.contains(search, case=False, na=False))
            if 'part_number' in filtered_df.columns:
                search_conditions.append(filtered_df['part_number'].str.contains(search, case=False, na=False))
            
            if search_conditions:
                combined_condition = search_conditions[0]
                for condition in search_conditions[1:]:
                    combined_condition = combined_condition | condition
                product_field_matches = filtered_df[combined_condition]
            else:
                product_field_matches = pd.DataFrame()
            
            if not vendor_product_matches.empty and not product_field_matches.empty:
                filtered_df = pd.concat([vendor_product_matches, product_field_matches]).drop_duplicates()
            elif not vendor_product_matches.empty:
                filtered_df = vendor_product_matches
            elif not product_field_matches.empty:
                filtered_df = product_field_matches
            else:
                filtered_df = filtered_df.iloc[0:0]
        
        if size_filter:
            if size_filter == 'matched':
                filtered_df = filtered_df[filtered_df['size'] > 1]
            elif size_filter == 'unique':
                filtered_df = filtered_df[filtered_df['size'] == 1]
        
        # Calculate actual size for each golden record
        def calculate_actual_size(guid):
            return len(links_df[links_df['guid'] == guid])
        
        filtered_df['size'] = filtered_df['guid'].apply(calculate_actual_size)
        
        if size_filter:
            if size_filter == 'matched':
                filtered_df = filtered_df[filtered_df['size'] > 1]
            elif size_filter == 'unique':
                filtered_df = filtered_df[filtered_df['size'] == 1]
        
        filtered_df = filtered_df.sort_values('size', ascending=False)
        
        # Pagination
        data_list = filtered_df.to_dict('records')
        for item in data_list:
            for key, value in item.items():
                if pd.isna(value):
                    item[key] = None
        
        paginator = Paginator(data_list, per_page)
        page_obj = paginator.get_page(page)
        
        return JsonResponse({
            'data': page_obj.object_list,
            'total': paginator.count,
            'pages': paginator.num_pages,
            'current_page': page,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous()
        })