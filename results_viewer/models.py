"""
Models for the results viewer app.
"""
from django.db import models
import pandas as pd
import os
from django.conf import settings
import sqlite3

# Try to import configuration, fall back to defaults
try:
    from results_config import INCLUDE_PATTERNS, EXCLUDE_PATTERNS, DIRECTORY_PRIORITY
except ImportError:
    INCLUDE_PATTERNS = []
    EXCLUDE_PATTERNS = []
    DIRECTORY_PRIORITY = []

# Try to import database sources configuration
try:
    from database_sources_config import DATABASE_SOURCES, CACHE_SETTINGS
except ImportError:
    DATABASE_SOURCES = []
    CACHE_SETTINGS = {'enabled': False}

# Try to import psycopg2 for PostgreSQL support
try:
    import psycopg2
    import psycopg2.extras
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    print("Warning: psycopg2 not available. PostgreSQL sources will not work.")

class ResultsManager:
    """Manager class to handle loading and caching of results data."""
    
    def __init__(self, results_dir):
        self.results_dir = results_dir
        self._cache = {}
    
    def get_available_results(self, include_patterns=None, exclude_patterns=None):
        """Get list of available results directories with optional filtering."""
        base_dir = settings.RESULTS_BASE_DIR
        results_dirs = []
        
        # Get include/exclude patterns from environment, config, or parameters
        if include_patterns is None:
            # First try environment variables
            env_include = os.environ.get('PER_INCLUDE_DIRS', '').split(',')
            env_include = [p.strip() for p in env_include if p.strip()]
            # Then try config file
            include_patterns = env_include if env_include else INCLUDE_PATTERNS
        
        if exclude_patterns is None:
            # First try environment variables
            env_exclude = os.environ.get('PER_EXCLUDE_DIRS', '').split(',')
            env_exclude = [p.strip() for p in env_exclude if p.strip()]
            # Then try config file
            exclude_patterns = env_exclude if env_exclude else EXCLUDE_PATTERNS
        
        # Look for directories containing the expected CSV files
        for item in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item)
            if os.path.isdir(item_path):
                # Check for traditional format (with pair_scores.csv)
                traditional_files = ['products.csv', 'links.csv', 'pair_scores.csv']
                # Check for scalable format (with golden_records.db)
                scalable_files = ['products.csv', 'links.csv', 'golden_records.db']
                
                if (all(os.path.exists(os.path.join(item_path, f)) for f in traditional_files) or
                    all(os.path.exists(os.path.join(item_path, f)) for f in scalable_files)):
                    
                    # Apply include patterns (if any)
                    if include_patterns:
                        if not any(pattern.lower() in item.lower() for pattern in include_patterns):
                            continue
                    
                    # Apply exclude patterns (if any)
                    if exclude_patterns:
                        if any(pattern.lower() in item.lower() for pattern in exclude_patterns):
                            continue
                    
                    results_dirs.append({
                        'name': item,
                        'path': item_path,
                        'display_name': item.replace('_', ' ').title()
                    })
        
        # Sort by priority first, then by name
        def sort_key(item):
            name = item['name']
            # Check if directory has a priority
            for i, priority_pattern in enumerate(DIRECTORY_PRIORITY):
                if priority_pattern in name:
                    return (i, name)  # Lower index = higher priority
            return (len(DIRECTORY_PRIORITY), name)  # No priority = lowest
        
        return sorted(results_dirs, key=sort_key)
    
    def load_products(self, results_dir):
        """Load products data from CSV."""
        cache_key = f"products_{results_dir}"
        if cache_key not in self._cache:
            file_path = os.path.join(results_dir, 'products.csv')
            if os.path.exists(file_path):
                self._cache[cache_key] = pd.read_csv(file_path)
            else:
                self._cache[cache_key] = pd.DataFrame()
        return self._cache[cache_key]
    
    def load_links(self, results_dir):
        """Load links data from CSV."""
        cache_key = f"links_{results_dir}"
        if cache_key not in self._cache:
            file_path = os.path.join(results_dir, 'links.csv')
            if os.path.exists(file_path):
                self._cache[cache_key] = pd.read_csv(file_path)
            else:
                self._cache[cache_key] = pd.DataFrame()
        return self._cache[cache_key]
    
    def load_pair_scores(self, results_dir):
        """Load pair scores data from CSV."""
        cache_key = f"pair_scores_{results_dir}"
        if cache_key not in self._cache:
            file_path = os.path.join(results_dir, 'pair_scores.csv')
            if os.path.exists(file_path):
                self._cache[cache_key] = pd.read_csv(file_path)
            else:
                # For scalable format, return empty DataFrame
                self._cache[cache_key] = pd.DataFrame()
        return self._cache[cache_key]
    
    def get_summary_stats(self, results_dir):
        """Get summary statistics for a results directory."""
        products_df = self.load_products(results_dir)
        links_df = self.load_links(results_dir)
        pair_scores_df = self.load_pair_scores(results_dir)
        
        if products_df.empty:
            return {}
        
        # Try to get actual total products from processing stats
        total_products = len(links_df)  # Default to links count
        try:
            import json
            processing_stats_path = os.path.join(results_dir, 'processing_stats.json')
            if os.path.exists(processing_stats_path):
                with open(processing_stats_path, 'r') as f:
                    processing_stats = json.load(f)
                    total_products = processing_stats.get('total_products', len(links_df))
        except Exception:
            pass  # Fall back to links count if processing stats not available
        
        # Calculate statistics
        total_golden_records = len(products_df)
        matched_products = len(products_df[products_df['size'] > 1])
        unique_products = len(products_df[products_df['size'] == 1])
        total_links = len(links_df)
        avg_confidence = links_df['link_confidence'].mean() if not links_df.empty else 0
        
        # Top manufacturers
        top_manufacturers = products_df['manufacturer'].value_counts().head(5).to_dict() if 'manufacturer' in products_df.columns else {}
        
        # Top UNSPSC codes (or brand if unspsc not available)
        if 'unspsc' in products_df.columns:
            top_unspsc = products_df['unspsc'].value_counts().head(5).to_dict()
        elif 'brand' in products_df.columns:
            top_unspsc = products_df['brand'].value_counts().head(5).to_dict()
        else:
            top_unspsc = {}
        
        return {
            'total_golden_records': total_golden_records,
            'total_products': total_products,
            'matched_products': matched_products,
            'unique_products': unique_products,
            'total_links': total_links,
            'avg_confidence': round(avg_confidence, 3),
            'top_manufacturers': top_manufacturers,
            'top_unspsc': top_unspsc,
            'total_pair_scores': len(pair_scores_df)
        }
    
    # ========================================================================
    # DATABASE SOURCE METHODS (PostgreSQL and SQLite)
    # ========================================================================
    
    def get_available_databases(self):
        """Get list of configured database sources."""
        databases = []
        
        for db_config in DATABASE_SOURCES:
            if db_config.get('enabled', True):
                db_info = {
                    'name': db_config['name'],
                    'display_name': db_config.get('display_name', db_config['name']),
                    'description': db_config.get('description', ''),
                    'type': db_config.get('type', 'postgresql'),
                    'connection_string': db_config['connection_string'],
                    'source_type': 'database',
                    'database_type': db_config.get('type', 'postgresql')
                }
                
                # Check connection status
                try:
                    if db_config['type'] == 'postgresql':
                        db_info['connection_status'] = self._test_postgresql_connection(
                            db_config['connection_string']
                        )
                    elif db_config['type'] == 'sqlite':
                        db_info['connection_status'] = self._test_sqlite_connection(
                            db_config['connection_string']
                        )
                    else:
                        db_info['connection_status'] = 'unknown'
                except Exception as e:
                    db_info['connection_status'] = f'error: {str(e)}'
                
                databases.append(db_info)
        
        return databases
    
    def _test_postgresql_connection(self, connection_string):
        """Test PostgreSQL connection."""
        if not POSTGRESQL_AVAILABLE:
            return 'unavailable'
        
        try:
            conn = psycopg2.connect(connection_string, connect_timeout=3)
            conn.close()
            return 'connected'
        except psycopg2.OperationalError:
            return 'offline'
        except Exception as e:
            return f'error'
    
    def _test_sqlite_connection(self, db_path):
        """Test SQLite connection."""
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path, timeout=3)
                conn.close()
                return 'connected'
            except Exception:
                return 'error'
        return 'not_found'
    
    def load_products_from_postgresql(self, connection_string):
        """Load golden records from PostgreSQL database."""
        if not POSTGRESQL_AVAILABLE:
            return pd.DataFrame()
        
        cache_key = f"pg_products_{connection_string}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            conn = psycopg2.connect(connection_string)
            query = """
                SELECT 
                    gr.guid,
                    gr.id_method,
                    gr.unspsc,
                    gr.manufacturer,
                    gr.part_number,
                    gr.gtin_primary as gtin,
                    gr.title,
                    gr.description,
                    COALESCE(vl_count.link_count, 0) AS size,
                    gr.created_at,
                    gr.updated_at
                FROM golden_records gr
                LEFT JOIN (
                    SELECT guid, COUNT(*) AS link_count
                    FROM golden_record_products
                    GROUP BY guid
                ) vl_count ON gr.guid = vl_count.guid
                ORDER BY COALESCE(vl_count.link_count, 0) DESC, gr.created_at DESC
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            self._cache[cache_key] = df
            return df
            
        except Exception as e:
            print(f"Error loading products from PostgreSQL: {e}")
            return pd.DataFrame()
    
    def load_links_from_postgresql(self, connection_string):
        """Load vendor links from PostgreSQL database."""
        if not POSTGRESQL_AVAILABLE:
            return pd.DataFrame()
        
        cache_key = f"pg_links_{connection_string}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            conn = psycopg2.connect(connection_string)
            query = """
                SELECT 
                    contract_number,
                    product_id,
                    guid,
                    link_confidence,
                    created_at
                FROM golden_record_products
                ORDER BY created_at ASC
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            self._cache[cache_key] = df
            return df
            
        except Exception as e:
            print(f"Error loading links from PostgreSQL: {e}")
            return pd.DataFrame()
    
    def get_golden_records_paginated_postgresql(self, connection_string, 
                                                page=1, per_page=50,
                                                manufacturer=None, unspsc=None,
                                                search=None, size_filter=None):
        """
        Get paginated golden records from PostgreSQL with SQL-level filtering and pagination.
        This is optimized for web interface performance - only loads the requested page.
        
        Returns:
            dict with 'data', 'total', 'pages', 'current_page', 'has_next', 'has_previous'
        """
        if not POSTGRESQL_AVAILABLE:
            return {'data': [], 'total': 0, 'pages': 0, 'current_page': page, 'has_next': False, 'has_previous': False}
        
        try:
            conn = psycopg2.connect(connection_string)
            cursor = conn.cursor()
            
            # Build WHERE clause conditions
            where_conditions = []
            params = []
            param_counter = [1]  # Use list to allow modification in nested functions
            
            if manufacturer:
                where_conditions.append(f"LOWER(gr.manufacturer) LIKE LOWER(%s)")
                params.append(f"%{manufacturer}%")
            
            if unspsc:
                where_conditions.append(f"gr.unspsc LIKE %s")
                params.append(f"%{unspsc}%")
            
            if search:
                # Search in golden record fields
                search_conditions = [
                    "LOWER(gr.guid) LIKE LOWER(%s)",
                    "LOWER(gr.title) LIKE LOWER(%s)",
                    "LOWER(gr.description) LIKE LOWER(%s)",
                    "LOWER(gr.part_number) LIKE LOWER(%s)"
                ]
                search_param = f"%{search}%"
                # Also search in golden_record_products
                where_conditions.append(
                    f"(({' OR '.join(search_conditions)})) OR "
                    f"gr.guid IN (SELECT DISTINCT guid FROM golden_record_products WHERE "
                    f"LOWER(contract_number) LIKE LOWER(%s) OR LOWER(product_id) LIKE LOWER(%s))"
                )
                params.extend([search_param] * 4 + [search_param, search_param])
            
            if size_filter == 'matched':
                # Will be handled in HAVING clause after size calculation
                pass
            elif size_filter == 'unique':
                # Will be handled in HAVING clause after size calculation
                pass
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            # Add size filter to WHERE clause if specified
            if size_filter == 'matched':
                where_clause += " AND COALESCE(vl_count.link_count, 0) > 1"
            elif size_filter == 'unique':
                where_clause += " AND COALESCE(vl_count.link_count, 0) = 1"
            
            # Calculate actual size using COUNT in SQL
            # Main query with size calculation and filtering
            # Use COALESCE to ensure size is 0 if no links exist
            base_query = f"""
                SELECT 
                    gr.guid,
                    gr.id_method,
                    gr.unspsc,
                    gr.manufacturer,
                    gr.part_number,
                    gr.gtin_primary as gtin,
                    gr.title,
                    gr.description,
                    COALESCE(vl_count.link_count, 0) as actual_size,
                    gr.created_at,
                    gr.updated_at
                FROM golden_records gr
                LEFT JOIN (
                    SELECT guid, COUNT(*) as link_count
                    FROM golden_record_products
                    GROUP BY guid
                ) vl_count ON gr.guid = vl_count.guid
                WHERE {where_clause}
            """
            
            # Get total count for pagination
            # Build count query by wrapping the base query
            count_query = f"SELECT COUNT(*) FROM ({base_query}) AS filtered_records"
            cursor.execute(count_query, params)
            total_records = cursor.fetchone()[0]
            
            # Add ORDER BY, LIMIT, and OFFSET
            offset = (page - 1) * per_page
            final_query = f"""
                {base_query}
                ORDER BY actual_size DESC, gr.created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([per_page, offset])
            
            cursor.execute(final_query, params)
            
            # Fetch column names
            columns = [desc[0] for desc in cursor.description]
            
            # Fetch results
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries
            data = []
            for row in rows:
                record = dict(zip(columns, row))
                # Build cleaned record (don't modify while iterating)
                cleaned_record = {}
                actual_size = None
                
                for key, value in record.items():
                    # Rename actual_size to size for consistency (don't add it to cleaned_record yet)
                    if key == 'actual_size':
                        actual_size = int(value) if value is not None else 0
                    else:
                        # Clean None/NaN values
                        if value is None or (isinstance(value, float) and pd.isna(value)):
                            cleaned_record[key] = None
                        else:
                            cleaned_record[key] = value
                
                # Add size field (from actual_size if it existed, otherwise use existing size)
                if actual_size is not None:
                    cleaned_record['size'] = actual_size
                elif 'size' not in cleaned_record and 'size' in record:
                    # Keep existing size if actual_size wasn't found
                    cleaned_record['size'] = record['size']
                
                data.append(cleaned_record)
            
            # Calculate pagination metadata
            total_pages = (total_records + per_page - 1) // per_page if total_records > 0 else 0
            has_next = page < total_pages
            has_previous = page > 1
            
            cursor.close()
            conn.close()
            
            return {
                'data': data,
                'total': total_records,
                'pages': total_pages,
                'current_page': page,
                'has_next': has_next,
                'has_previous': has_previous
            }
            
        except psycopg2.ProgrammingError as e:
            print(f"SQL Error loading paginated products from PostgreSQL: {e}")
            import traceback
            traceback.print_exc()
            return {'data': [], 'total': 0, 'pages': 0, 'current_page': page, 'has_next': False, 'has_previous': False}
        except Exception as e:
            print(f"Error loading paginated products from PostgreSQL: {e}")
            import traceback
            traceback.print_exc()
            return {'data': [], 'total': 0, 'pages': 0, 'current_page': page, 'has_next': False, 'has_previous': False}
    
    def load_products_from_sqlite(self, db_path):
        """Load golden records from SQLite database (scalable format)."""
        cache_key = f"sqlite_products_{db_path}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            conn = sqlite3.connect(db_path)
            query = """
                SELECT 
                    gr.guid,
                    gr.id_method,
                    gr.unspsc,
                    gr.manufacturer,
                    gr.part_number,
                    gr.gtin_primary as gtin,
                    gr.title,
                    gr.description,
                    COALESCE(vl_count.link_count, 0) AS size,
                    gr.created_at,
                    gr.updated_at
                FROM golden_records gr
                LEFT JOIN (
                    SELECT guid, COUNT(*) AS link_count
                    FROM golden_record_products
                    GROUP BY guid
                ) vl_count ON gr.guid = vl_count.guid
                ORDER BY COALESCE(vl_count.link_count, 0) DESC, gr.created_at DESC
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            self._cache[cache_key] = df
            return df
            
        except Exception as e:
            print(f"Error loading products from SQLite: {e}")
            return pd.DataFrame()
    
    def load_links_from_sqlite(self, db_path):
        """Load vendor links from SQLite database (scalable format)."""
        cache_key = f"sqlite_links_{db_path}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            conn = sqlite3.connect(db_path)
            query = """
                SELECT 
                    contract_number,
                    product_id,
                    guid,
                    link_confidence,
                    created_at
                FROM golden_record_products
                ORDER BY created_at DESC
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            self._cache[cache_key] = df
            return df
            
        except Exception as e:
            print(f"Error loading links from SQLite: {e}")
            return pd.DataFrame()
    
    def get_summary_stats_from_db(self, db_type, connection_string_or_path):
        """Get summary statistics from database (PostgreSQL or SQLite)."""
        # Load data
        if db_type == 'postgresql':
            products_df = self.load_products_from_postgresql(connection_string_or_path)
            links_df = self.load_links_from_postgresql(connection_string_or_path)
        elif db_type == 'sqlite':
            products_df = self.load_products_from_sqlite(connection_string_or_path)
            links_df = self.load_links_from_sqlite(connection_string_or_path)
        else:
            return {}
        
        if products_df.empty:
            return {}
        
        # Calculate statistics (same logic as directory-based)
        total_products = len(links_df)
        total_golden_records = len(products_df)
        matched_products = len(products_df[products_df['size'] > 1])
        unique_products = len(products_df[products_df['size'] == 1])
        total_links = len(links_df)
        avg_confidence = links_df['link_confidence'].mean() if not links_df.empty else 0
        
        # Top manufacturers
        top_manufacturers = products_df['manufacturer'].value_counts().head(5).to_dict() if 'manufacturer' in products_df.columns else {}
        
        # Top UNSPSC codes
        top_unspsc = products_df['unspsc'].value_counts().head(5).to_dict() if 'unspsc' in products_df.columns else {}
        
        return {
            'total_golden_records': total_golden_records,
            'total_products': total_products,
            'matched_products': matched_products,
            'unique_products': unique_products,
            'total_links': total_links,
            'avg_confidence': round(avg_confidence, 3),
            'top_manufacturers': top_manufacturers,
            'top_unspsc': top_unspsc,
            'total_pair_scores': 0  # No pair scores for database sources
        }
    
    def get_database_by_name(self, name):
        """Get database configuration by name."""
        for db_config in DATABASE_SOURCES:
            if db_config['name'] == name:
                return db_config
        return None
    
    def is_database_source(self, name):
        """Check if a source name is a database source."""
        # Check if name matches any configured database source
        for db_config in DATABASE_SOURCES:
            if db_config.get('enabled', True) and db_config['name'] == name:
                return True
        # Also check for legacy pgsql_ prefix for backward compatibility
        return name.startswith('pgsql_')
    
    def is_scalable_source(self, results_path):
        """Check if a directory contains scalable format (golden_records.db)."""
        return os.path.exists(os.path.join(results_path, 'golden_records.db'))

# Global results manager instance
results_manager = ResultsManager(settings.RESULTS_BASE_DIR)