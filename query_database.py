#!/usr/bin/env python3
"""
Query utility for Product Entity Resolution database

Usage examples:
    # Look up QBI-ID by vendor product ID
    python query_database.py --db per_output_scalable/golden_records.db --lookup vendor_a prod_123
    
    # Get golden record details by QBI-ID
    python query_database.py --db per_output_scalable/golden_records.db --qbi QBI-ABC123
    
    # List all products from a vendor
    python query_database.py --db per_output_scalable/golden_records.db --vendor vendor_a
    
    # Search products by part number, manufacturer, etc.
    python query_database.py --db per_output_scalable/golden_records.db --search "HP LaserJet"
    
    # Compare two products from the same golden record
    python query_database.py --db per_output_scalable/golden_records.db \
        --compare QBI-8F56A71E6410 47QSHA19D004Z_54557249 47QSHA19D004Z_54886689
    
    # Get database statistics
    python query_database.py --db per_output_scalable/golden_records.db --stats
"""

import sqlite3
import argparse
import pandas as pd
import sys
from pathlib import Path
from typing import Optional, List, Dict
import json

# Import toolkit functions for similarity calculations
from product_er_toolkit import (
    pn_variants, normalize_manufacturer, normalize_unspsc,
    jaro_winkler, char_trigram_set, jaccard,
    build_pair_features
)


class DatabaseQuery:
    """Helper class to query the entity resolution database"""
    
    def __init__(self, db_path: str):
        """Initialize with database path"""
        self.db_path = db_path
        if not Path(db_path).exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    
    def __del__(self):
        """Close connection on cleanup"""
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def lookup_qbi_id(self, contract_number: str, product_id: str) -> Optional[Dict]:
        """
        Look up QBI-ID for a specific vendor product
        
        Args:
            contract_number: Vendor identifier
            product_id: Product identifier within vendor catalog
            
        Returns:
            Dictionary with QBI-ID and link information, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT contract_number, product_id, guid, link_confidence, created_at
            FROM golden_record_products
            WHERE contract_number = ? AND product_id = ?
        ''', (contract_number, product_id))
        
        result = cursor.fetchone()
        if result:
            return dict(result)
        return None
    
    def get_golden_record(self, qbi_id: str) -> Optional[Dict]:
        """
        Get full golden record details by QBI-ID
        
        Args:
            qbi_id: QBI-ID (guid)
            
        Returns:
            Dictionary with golden record details, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT gr.guid, gr.id_method, gr.unspsc, gr.manufacturer, gr.part_number, 
                   gr.gtin_primary, gr.title, gr.description,
                   COALESCE(stats.link_count, 0) AS size,
                   gr.created_at, gr.updated_at
            FROM golden_records gr
            LEFT JOIN (
                SELECT guid, COUNT(*) AS link_count
                FROM golden_record_products
                GROUP BY guid
            ) stats ON stats.guid = gr.guid
            WHERE gr.guid = ?
        ''', (qbi_id,))
        
        result = cursor.fetchone()
        if result:
            return dict(result)
        return None
    
    def get_vendor_products_for_golden_record(self, qbi_id: str) -> List[Dict]:
        """
        Get all vendor products linked to a golden record
        
        Args:
            qbi_id: QBI-ID (guid)
            
        Returns:
            List of dictionaries with vendor product links
        """
        df = pd.read_sql_query('''
            SELECT contract_number, product_id, link_confidence, created_at
            FROM golden_record_products
            WHERE guid = ?
            ORDER BY link_confidence DESC, contract_number
        ''', self.conn, params=[qbi_id])
        
        return df.to_dict('records')
    
    def list_vendor_products(self, contract_number: str, limit: int = 100) -> List[Dict]:
        """
        List all products from a specific vendor
        
        Args:
            contract_number: Vendor identifier
            limit: Maximum number of results
            
        Returns:
            List of dictionaries with product information
        """
        df = pd.read_sql_query('''
            SELECT vl.contract_number,
                   vl.product_id,
                   vl.guid,
                   vl.link_confidence,
                   gr.manufacturer,
                   gr.part_number,
                   gr.title,
                   COALESCE(stats.link_count, 0) AS size
            FROM golden_record_products vl
            JOIN golden_records gr ON vl.guid = gr.guid
            LEFT JOIN (
                SELECT guid, COUNT(*) AS link_count
                FROM golden_record_products
                GROUP BY guid
            ) stats ON stats.guid = gr.guid
            WHERE vl.contract_number = ?
            ORDER BY vl.product_id
            LIMIT ?
        ''', self.conn, params=[contract_number, limit])
        
        return df.to_dict('records')
    
    def search_products(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search for products across all fields
        
        Args:
            query: Search term
            limit: Maximum number of results
            
        Returns:
            List of dictionaries with matching products
        """
        search_term = f'%{query}%'
        df = pd.read_sql_query('''
            SELECT gr.guid, gr.unspsc, gr.manufacturer, gr.part_number, gr.gtin_primary,
                   gr.title, gr.description, COALESCE(stats.link_count, 0) AS size
            FROM golden_records gr
            LEFT JOIN (
                SELECT guid, COUNT(*) AS link_count
                FROM golden_record_products
                GROUP BY guid
            ) stats ON stats.guid = gr.guid
            WHERE gr.unspsc LIKE ? OR gr.manufacturer LIKE ? OR gr.part_number LIKE ? 
                  OR gr.title LIKE ? OR gr.description LIKE ? OR gr.gtin_primary LIKE ?
            ORDER BY COALESCE(stats.link_count, 0) DESC, gr.manufacturer, gr.part_number
            LIMIT ?
        ''', self.conn, params=[search_term] * 6 + [limit])
        
        return df.to_dict('records')
    
    def get_statistics(self) -> Dict:
        """
        Get database statistics
        
        Returns:
            Dictionary with various statistics
        """
        cursor = self.conn.cursor()
        
        # Total counts
        cursor.execute("SELECT COUNT(*) FROM golden_records")
        total_golden_records = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM golden_record_products")
        total_vendor_products = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT contract_number) FROM golden_record_products")
        total_vendors = cursor.fetchone()[0]
        
        # Size distribution
        cursor.execute('''
            SELECT link_count, COUNT(*) as count
            FROM (
                SELECT guid, COUNT(*) AS link_count
                FROM golden_record_products
                GROUP BY guid
            ) counts
            GROUP BY link_count
            ORDER BY link_count
        ''')
        size_distribution = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Top manufacturers
        cursor.execute('''
            SELECT manufacturer, COUNT(*) as count 
            FROM golden_records 
            WHERE manufacturer != ''
            GROUP BY manufacturer 
            ORDER BY count DESC 
            LIMIT 10
        ''')
        top_manufacturers = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Top UNSPSC codes
        cursor.execute('''
            SELECT unspsc, COUNT(*) as count 
            FROM golden_records 
            WHERE unspsc != '' AND unspsc != '00000000'
            GROUP BY unspsc 
            ORDER BY count DESC 
            LIMIT 10
        ''')
        top_unspsc = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {
            'total_golden_records': total_golden_records,
            'total_vendor_products': total_vendor_products,
            'total_vendors': total_vendors,
            'unique_products': size_distribution.get(1, 0),
            'multi_vendor_products': sum(count for size, count in size_distribution.items() if size > 1),
            'size_distribution': size_distribution,
            'top_manufacturers': top_manufacturers,
            'top_unspsc': top_unspsc
        }
    
    def get_all_vendors(self) -> List[str]:
        """Get list of all contract numbers in the database"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT contract_number FROM golden_record_products ORDER BY contract_number")
        return [row[0] for row in cursor.fetchall()]
    
    def get_multi_vendor_products(self, min_vendors: int = 2, limit: int = 100) -> List[Dict]:
        """
        Get products that appear in multiple vendor catalogs
        
        Args:
            min_vendors: Minimum number of vendors required
            limit: Maximum number of results
            
        Returns:
            List of dictionaries with multi-vendor products
        """
        df = pd.read_sql_query('''
            SELECT gr.guid, gr.unspsc, gr.manufacturer, gr.part_number, gr.title,
                   COALESCE(stats.link_count, 0) AS size
            FROM golden_records gr
            LEFT JOIN (
                SELECT guid, COUNT(*) AS link_count
                FROM golden_record_products
                GROUP BY guid
            ) stats ON stats.guid = gr.guid
            WHERE COALESCE(stats.link_count, 0) >= ?
            ORDER BY COALESCE(stats.link_count, 0) DESC, gr.manufacturer, gr.part_number
            LIMIT ?
        ''', self.conn, params=[min_vendors, limit])
        
        return df.to_dict('records')
    
    def compare_products(self, qbi_id: str, product_id_a: str, product_id_b: str) -> Optional[Dict]:
        """
        Compare two products from the same golden record (QBI-ID)
        
        Args:
            qbi_id: QBI-ID that both products belong to
            product_id_a: First product ID to compare
            product_id_b: Second product ID to compare
            
        Returns:
            Dictionary with detailed comparison analysis
        """
        # Get the products from the staging table or reconstruct from vendor links
        cursor = self.conn.cursor()
        
        # Get contract numbers for both products
        cursor.execute('''
            SELECT contract_number FROM golden_record_products 
            WHERE product_id = ? AND guid = ?
        ''', (product_id_a, qbi_id))
        vendor_a_result = cursor.fetchone()
        if not vendor_a_result:
            return None
        vendor_a = vendor_a_result[0]
        
        cursor.execute('''
            SELECT contract_number FROM golden_record_products 
            WHERE product_id = ? AND guid = ?
        ''', (product_id_b, qbi_id))
        vendor_b_result = cursor.fetchone()
        if not vendor_b_result:
            return None
        vendor_b = vendor_b_result[0]
        
        # Get product details from staging table
        cursor.execute('''
            SELECT contract_number, product_id, manufacturer, unspsc, part_number, title, description, gtin
            FROM pers_product_staging 
            WHERE product_id = ? AND contract_number = ?
        ''', (product_id_a, vendor_a))
        product_a_result = cursor.fetchone()
        
        cursor.execute('''
            SELECT contract_number, product_id, manufacturer, unspsc, part_number, title, description, gtin
            FROM pers_product_staging 
            WHERE product_id = ? AND contract_number = ?
        ''', (product_id_b, vendor_b))
        product_b_result = cursor.fetchone()
        
        # If not found in staging, try to get from golden record as fallback
        if not product_a_result or not product_b_result:
            cursor.execute('''
                SELECT manufacturer, unspsc, part_number, title, description, gtin_primary
                FROM golden_records WHERE guid = ?
            ''', (qbi_id,))
            golden_record = cursor.fetchone()
            
            if golden_record:
                # Create product records from golden record
                if not product_a_result:
                    product_a_result = (vendor_a, product_id_a, golden_record[0], golden_record[1], 
                                      golden_record[2], golden_record[3], golden_record[4], golden_record[5])
                if not product_b_result:
                    product_b_result = (vendor_b, product_id_b, golden_record[0], golden_record[1], 
                                      golden_record[2], golden_record[3], golden_record[4], golden_record[5])
            else:
                return None
        
        # Convert to dictionaries
        product_a = {
            'contract_number': product_a_result[0],
            'product_id': product_a_result[1],
            'manufacturer': product_a_result[2] or '',
            'unspsc': product_a_result[3] or '',
            'part_number': product_a_result[4] or '',
            'title': product_a_result[5] or '',
            'description': product_a_result[6] or '',
            'gtin': product_a_result[7] or ''
        }
        
        product_b = {
            'contract_number': product_b_result[0],
            'product_id': product_b_result[1],
            'manufacturer': product_b_result[2] or '',
            'unspsc': product_b_result[3] or '',
            'part_number': product_b_result[4] or '',
            'title': product_b_result[5] or '',
            'description': product_b_result[6] or '',
            'gtin': product_b_result[7] or ''
        }
        
        # Generate part number variants
        pn_variants_a = pn_variants(product_a['part_number'])
        pn_variants_b = pn_variants(product_b['part_number'])
        
        # Find matching variants
        matching_variants = list(set(pn_variants_a) & set(pn_variants_b))
        pn_exact_match = len(matching_variants) > 0
        
        # Calculate Jaro-Winkler for part numbers (best match)
        best_pn_jw = 0.0
        if pn_variants_a and pn_variants_b:
            for var_a in pn_variants_a:
                for var_b in pn_variants_b:
                    jw = jaro_winkler(var_a, var_b)
                    best_pn_jw = max(best_pn_jw, jw)
        
        # Normalize manufacturers
        mfr_a_norm = normalize_manufacturer(product_a['manufacturer'])
        mfr_b_norm = normalize_manufacturer(product_b['manufacturer'])
        
        # Calculate manufacturer Jaro-Winkler
        mfr_jw = jaro_winkler(mfr_a_norm, mfr_b_norm) if mfr_a_norm and mfr_b_norm else 0.0
        
        # Calculate text similarity
        text_a = f"{product_a['title']} {product_a['description']}".lower()
        text_b = f"{product_b['title']} {product_b['description']}".lower()
        
        tri_a = char_trigram_set(text_a)
        tri_b = char_trigram_set(text_b)
        text_jaccard = jaccard(tri_a, tri_b)
        
        # TF-IDF cosine similarity (simplified)
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        if text_a.strip() and text_b.strip():
            vect = TfidfVectorizer(ngram_range=(1,2), min_df=1)
            try:
                m = vect.fit_transform([text_a, text_b])
                text_tfidf_cos = float(cosine_similarity(m[0], m[1])[0][0])
            except:
                text_tfidf_cos = 0.0
        else:
            text_tfidf_cos = 0.0
        
        # Calculate overall similarity score (using the same weights as in build_pair_features)
        overall_score = 0.0
        
        # Part number contribution
        if pn_exact_match:
            overall_score += 0.4
        else:
            overall_score += best_pn_jw * 0.3
        
        # Manufacturer contribution
        mfr_exact_match = mfr_a_norm == mfr_b_norm
        if mfr_exact_match:
            overall_score += 0.25
        else:
            overall_score += mfr_jw * 0.2
        
        # Text contribution (increased weights)
        overall_score += text_tfidf_cos * 0.15
        overall_score += text_jaccard * 0.10
        
        # UNSPSC contribution with hierarchical matching (reduced weights)
        unspsc_score_contribution = 0.0
        if product_a['unspsc'] and product_b['unspsc']:
            unspsc_a_str = str(product_a['unspsc']).replace('.0', '').strip()
            unspsc_b_str = str(product_b['unspsc']).replace('.0', '').strip()
            
            if len(unspsc_a_str) >= 8 and len(unspsc_b_str) >= 8:
                # Exact match (all 8 digits)
                if unspsc_a_str == unspsc_b_str:
                    unspsc_score_contribution = 0.10  # Reduced weight for UNSPSC exact match
                # Class match (first 6 digits)
                elif unspsc_a_str[:6] == unspsc_b_str[:6]:
                    unspsc_score_contribution = 0.08
                # Family match (first 4 digits)
                elif unspsc_a_str[:4] == unspsc_b_str[:4]:
                    unspsc_score_contribution = 0.06
                # Segment match (first 2 digits)
                elif unspsc_a_str[:2] == unspsc_b_str[:2]:
                    unspsc_score_contribution = 0.04
        
        overall_score += unspsc_score_contribution
        
        # Combined PN + Manufacturer exact match synergy boost
        synergy_boost = 0.30 if (pn_exact_match and mfr_exact_match) else 0.0
        overall_score += synergy_boost
        
        # GTIN contribution (highest priority)
        gtin_score_contribution = 0.0
        gtin_exact_match = False
        gtin_mismatch = False
        
        if product_a['gtin'] and product_b['gtin']:
            gtin_a_str = str(product_a['gtin']).strip().upper()
            gtin_b_str = str(product_b['gtin']).strip().upper()
            
            # Check if GTINs are valid (not placeholder values)
            if (gtin_a_str and gtin_a_str not in ['NAN', 'NONE', '', '0'] and 
                gtin_b_str and gtin_b_str not in ['NAN', 'NONE', '', '0']):
                
                if gtin_a_str == gtin_b_str:
                    gtin_exact_match = True
                    gtin_score_contribution = 0.6  # Very high weight for GTIN match
                else:
                    gtin_mismatch = True
                    gtin_score_contribution = 0.0  # GTIN mismatch = 0 score
        
        overall_score += gtin_score_contribution
        overall_score = min(overall_score, 1.0)
        
        # Determine UNSPSC match levels for display
        unspsc_segment_match = False
        unspsc_family_match = False
        unspsc_class_match = False
        unspsc_match_level = 'none'
        
        if product_a['unspsc'] and product_b['unspsc']:
            unspsc_a_str = str(product_a['unspsc']).replace('.0', '').strip()
            unspsc_b_str = str(product_b['unspsc']).replace('.0', '').strip()
            
            if len(unspsc_a_str) >= 8 and len(unspsc_b_str) >= 8:
                if unspsc_a_str == unspsc_b_str:
                    unspsc_segment_match = unspsc_family_match = unspsc_class_match = True
                    unspsc_match_level = 'exact'
                elif unspsc_a_str[:6] == unspsc_b_str[:6]:
                    unspsc_segment_match = unspsc_family_match = unspsc_class_match = True
                    unspsc_match_level = 'class'
                elif unspsc_a_str[:4] == unspsc_b_str[:4]:
                    unspsc_segment_match = unspsc_family_match = True
                    unspsc_match_level = 'family'
                elif unspsc_a_str[:2] == unspsc_b_str[:2]:
                    unspsc_segment_match = True
                    unspsc_match_level = 'segment'
        
        return {
            'qbi_id': qbi_id,
            'product_a': product_a,
            'product_b': product_b,
            'overall_score': overall_score,
            'part_number': {
                'product_a_variants': pn_variants_a,
                'product_b_variants': pn_variants_b,
                'matching_variants': matching_variants,
                'exact_match': pn_exact_match,
                'jaro_winkler': best_pn_jw,
                'score_contribution': 0.4 if pn_exact_match else best_pn_jw * 0.3
            },
            'manufacturer': {
                'product_a_normalized': mfr_a_norm,
                'product_b_normalized': mfr_b_norm,
                'jaro_winkler': mfr_jw,
                'exact_match': mfr_a_norm == mfr_b_norm,
                'score_contribution': 0.25 if mfr_a_norm == mfr_b_norm else mfr_jw * 0.2
            },
            'text_similarity': {
                'title_similarity': 0.0,  # Not calculated separately in this version
                'description_similarity': 0.0,  # Not calculated separately in this version
                'jaccard': text_jaccard,
                'tfidf_cosine': text_tfidf_cos,
                'score_contribution': text_tfidf_cos * 0.15 + text_jaccard * 0.10  # Updated weights
            },
            'unspsc': {
                'product_a': product_a['unspsc'],
                'product_b': product_b['unspsc'],
                'exact_match': unspsc_match_level == 'exact',
                'segment_match': unspsc_segment_match,
                'family_match': unspsc_family_match,
                'class_match': unspsc_class_match,
                'match_level': unspsc_match_level,
                'score_contribution': unspsc_score_contribution
            },
            'gtin': {
                'product_a': product_a['gtin'],
                'product_b': product_b['gtin'],
                'exact_match': gtin_exact_match,
                'mismatch': gtin_mismatch,
                'available': bool(product_a['gtin'] and product_b['gtin'] and 
                                str(product_a['gtin']).strip().upper() not in ['NAN', 'NONE', '', '0'] and
                                str(product_b['gtin']).strip().upper() not in ['NAN', 'NONE', '', '0']),
                'score_contribution': gtin_score_contribution
            } if (product_a['gtin'] and product_b['gtin'] and 
                  str(product_a['gtin']).strip().upper() not in ['NAN', 'NONE', '', '0'] and
                  str(product_b['gtin']).strip().upper() not in ['NAN', 'NONE', '', '0']) else None,
            'synergy_boost': {
                'applied': synergy_boost > 0,
                'score_contribution': synergy_boost,
                'description': 'Combined PN + Manufacturer exact match boost'
            } if synergy_boost > 0 else None
        }


def print_dict(data: Dict, indent: int = 0):
    """Pretty print a dictionary"""
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            print(f"{prefix}{key}:")
            print_dict(value, indent + 1)
        else:
            print(f"{prefix}{key}: {value}")


def main():
    parser = argparse.ArgumentParser(
        description='Query Product Entity Resolution Database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--db', required=True, help='Path to golden_records.db')
    
    # Query options
    parser.add_argument('--lookup', nargs=2, metavar=('VENDOR_ID', 'PRODUCT_ID'),
                       help='Look up QBI-ID for a vendor product')
    parser.add_argument('--qbi', metavar='QBI_ID',
                       help='Get golden record details by QBI-ID')
    parser.add_argument('--vendor', metavar='VENDOR_ID',
                       help='List all products from a vendor')
    parser.add_argument('--search', metavar='QUERY',
                       help='Search products by any field')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--vendors', action='store_true',
                       help='List all contract numbers')
    parser.add_argument('--multi-vendor', action='store_true',
                       help='Show products appearing in multiple vendor catalogs')
    parser.add_argument('--compare', nargs=3, metavar=('QBI_ID', 'PRODUCT_ID_A', 'PRODUCT_ID_B'),
                       help='Compare two products from the same golden record')
    parser.add_argument('--limit', type=int, default=100,
                       help='Limit number of results (default: 100)')
    
    args = parser.parse_args()
    
    try:
        db = DatabaseQuery(args.db)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Execute query based on arguments
    if args.lookup:
        contract_number, product_id = args.lookup
        print(f"\n=== Looking up: Vendor '{contract_number}', Product '{product_id}' ===\n")
        
        result = db.lookup_qbi_id(contract_number, product_id)
        if result:
            print(f"QBI-ID: {result['guid']}")
            print(f"Confidence: {result['link_confidence']:.4f}")
            print(f"Created: {result['created_at']}")
            
            # Also show golden record details
            golden = db.get_golden_record(result['guid'])
            if golden:
                print(f"\n=== Golden Record Details ===\n")
                print(f"Manufacturer: {golden['manufacturer']}")
                print(f"Part Number: {golden['part_number']}")
                print(f"UNSPSC: {golden['unspsc']}")
                print(f"Title: {golden['title']}")
                print(f"Vendors: {golden['size']}")
        else:
            print("Not found in database")
    
    elif args.qbi:
        print(f"\n=== Golden Record: {args.qbi} ===\n")
        
        golden = db.get_golden_record(args.qbi)
        if golden:
            print_dict(golden)
            
            # Show linked vendor products
            vendors = db.get_vendor_products_for_golden_record(args.qbi)
            print(f"\n=== Linked Vendor Products ({len(vendors)}) ===\n")
            for v in vendors:
                print(f"  {v['contract_number']}: {v['product_id']} (confidence: {v['link_confidence']:.4f})")
        else:
            print("Not found in database")
    
    elif args.vendor:
        print(f"\n=== Products from Vendor: {args.vendor} ===\n")
        
        products = db.list_vendor_products(args.vendor, args.limit)
        if products:
            print(f"Found {len(products)} products:\n")
            for i, prod in enumerate(products, 1):
                print(f"{i}. Product ID: {prod['product_id']}")
                print(f"   QBI-ID: {prod['guid']}")
                print(f"   Manufacturer: {prod['manufacturer']}")
                print(f"   Part Number: {prod['part_number']}")
                print(f"   Title: {prod['title'][:80]}...")
                print(f"   Vendors with same product: {prod['size']}")
                print()
        else:
            print("No products found")
    
    elif args.search:
        print(f"\n=== Search Results for: '{args.search}' ===\n")
        
        results = db.search_products(args.search, args.limit)
        if results:
            print(f"Found {len(results)} matches:\n")
            for i, result in enumerate(results, 1):
                print(f"{i}. QBI-ID: {result['guid']}")
                print(f"   Manufacturer: {result['manufacturer']}")
                print(f"   Part Number: {result['part_number']}")
                print(f"   UNSPSC: {result['unspsc']}")
                print(f"   Title: {result['title'][:80]}...")
                print(f"   Vendors: {result['size']}")
                print()
        else:
            print("No matches found")
    
    elif args.stats:
        print("\n=== Database Statistics ===\n")
        
        stats = db.get_statistics()
        print(f"Total Golden Records: {stats['total_golden_records']:,}")
        print(f"Total Vendor Products: {stats['total_vendor_products']:,}")
        print(f"Total Vendors: {stats['total_vendors']}")
        print(f"Unique Products (1 vendor): {stats['unique_products']:,}")
        print(f"Multi-Vendor Products: {stats['multi_vendor_products']:,}")
        
        print(f"\n=== Size Distribution ===\n")
        for size, count in sorted(stats['size_distribution'].items()):
            print(f"  {size} vendor(s): {count:,} products")
        
        print(f"\n=== Top 10 Manufacturers ===\n")
        for i, (mfr, count) in enumerate(stats['top_manufacturers'].items(), 1):
            print(f"  {i}. {mfr}: {count:,} products")
        
        print(f"\n=== Top 10 UNSPSC Codes ===\n")
        for i, (unspsc, count) in enumerate(stats['top_unspsc'].items(), 1):
            print(f"  {i}. {unspsc}: {count:,} products")
    
    elif args.vendors:
        print("\n=== All Vendors ===\n")
        
        vendors = db.get_all_vendors()
        for i, vendor in enumerate(vendors, 1):
            print(f"{i}. {vendor}")
        print(f"\nTotal: {len(vendors)} vendors")
    
    elif args.multi_vendor:
        print("\n=== Multi-Vendor Products ===\n")
        
        products = db.get_multi_vendor_products(min_vendors=2, limit=args.limit)
        if products:
            print(f"Found {len(products)} multi-vendor products:\n")
            for i, prod in enumerate(products, 1):
                print(f"{i}. QBI-ID: {prod['guid']}")
                print(f"   Manufacturer: {prod['manufacturer']}")
                print(f"   Part Number: {prod['part_number']}")
                print(f"   Title: {prod['title'][:80]}...")
                print(f"   Found in {prod['size']} vendor catalogs")
                print()
        else:
            print("No multi-vendor products found")
    
    elif args.compare:
        qbi_id, product_id_a, product_id_b = args.compare
        print(f"\n=== Product Comparison ===\n")
        print(f"QBI-ID: {qbi_id}")
        print(f"Product A: {product_id_a}")
        print(f"Product B: {product_id_b}\n")
        
        comparison = db.compare_products(qbi_id, product_id_a, product_id_b)
        if comparison:
            # Product details
            print("=== Product Details ===\n")
            print(f"Product A:")
            print(f"  Vendor: {comparison['product_a']['contract_number']}")
            print(f"  Manufacturer: {comparison['product_a']['manufacturer']}")
            print(f"  Part Number: {comparison['product_a']['part_number']}")
            print(f"  UNSPSC: {comparison['product_a']['unspsc']}")
            print(f"  Title: {comparison['product_a']['title']}")
            print(f"  Description: {comparison['product_a']['description']}")
            print()
            print(f"Product B:")
            print(f"  Vendor: {comparison['product_b']['contract_number']}")
            print(f"  Manufacturer: {comparison['product_b']['manufacturer']}")
            print(f"  Part Number: {comparison['product_b']['part_number']}")
            print(f"  UNSPSC: {comparison['product_b']['unspsc']}")
            print(f"  Title: {comparison['product_b']['title']}")
            print(f"  Description: {comparison['product_b']['description']}")
            print()
            
            # Overall score
            print("=== Similarity Analysis ===\n")
            print(f"Overall Score: {comparison['overall_score']:.1%}")
            print()
            
            # Part number analysis
            print("=== Part Number Analysis ===")
            print(f"Product A Variants: {', '.join(comparison['part_number']['product_a_variants'])}")
            print(f"Product B Variants: {', '.join(comparison['part_number']['product_b_variants'])}")
            print(f"Exact Match: {'Yes' if comparison['part_number']['exact_match'] else 'No'}")
            print(f"Jaro-Winkler: {comparison['part_number']['jaro_winkler']:.3f}")
            print(f"Score Contribution: {comparison['part_number']['score_contribution']:.3f}")
            print()
            
            # Manufacturer analysis
            print("=== Manufacturer Analysis ===")
            print(f"Product A Normalized: {comparison['manufacturer']['product_a_normalized']}")
            print(f"Product B Normalized: {comparison['manufacturer']['product_b_normalized']}")
            print(f"Exact Match: {'Yes' if comparison['manufacturer']['exact_match'] else 'No'}")
            print(f"Jaro-Winkler: {comparison['manufacturer']['jaro_winkler']:.3f}")
            print(f"Score Contribution: {comparison['manufacturer']['score_contribution']:.3f}")
            print()
            
            # UNSPSC analysis
            print("=== UNSPSC Analysis ===")
            print(f"Product A: {comparison['unspsc']['product_a']}")
            print(f"Product B: {comparison['unspsc']['product_b']}")
            print(f"Match Level: {comparison['unspsc']['match_level']}")
            print(f"  Segment Match (2 digits): {'Yes' if comparison['unspsc']['segment_match'] else 'No'}")
            print(f"  Family Match (4 digits): {'Yes' if comparison['unspsc']['family_match'] else 'No'}")
            print(f"  Class Match (6 digits): {'Yes' if comparison['unspsc']['class_match'] else 'No'}")
            print(f"  Exact Match (8 digits): {'Yes' if comparison['unspsc']['exact_match'] else 'No'}")
            print(f"Score Contribution: {comparison['unspsc']['score_contribution']:.3f}")
            print()
            
            # Text similarity
            print("=== Text Similarity ===")
            print(f"Jaccard: {comparison['text_similarity']['jaccard']:.3f}")
            print(f"TF-IDF Cosine: {comparison['text_similarity']['tfidf_cosine']:.3f}")
            print(f"Score Contribution: {comparison['text_similarity']['score_contribution']:.3f}")
            print()
            
            # Score breakdown
            print("=== Score Breakdown ===")
            total_contribution = (comparison['part_number']['score_contribution'] + 
                                comparison['manufacturer']['score_contribution'] + 
                                comparison['text_similarity']['score_contribution'] + 
                                comparison['unspsc']['score_contribution'])
            print(f"Part Number: {comparison['part_number']['score_contribution']:.3f}")
            print(f"Manufacturer: {comparison['manufacturer']['score_contribution']:.3f}")
            print(f"Text Similarity: {comparison['text_similarity']['score_contribution']:.3f}")
            print(f"UNSPSC: {comparison['unspsc']['score_contribution']:.3f}")
            print(f"Total: {total_contribution:.3f}")
            
        else:
            print("Products not found or not linked to the same QBI-ID")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

