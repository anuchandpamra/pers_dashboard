#!/usr/bin/env python3
"""
Manufacturer Alias Manager

This module provides functionality to manage manufacturer aliases and canonical name resolution
for improved product entity resolution. It enables matching of products from different vendors
that use different names for the same manufacturer (e.g., "3M" vs "Minnesota Mining and Manufacturing").

Usage:
    from manufacturer_alias_manager import ManufacturerAliasManager
    
    manager = ManufacturerAliasManager("wikidata_business_results.csv")
    canonical = manager.get_canonical_name("3M")
    aliases = manager.get_aliases("3M")
"""

import pandas as pd
import ast
from typing import Dict, List, Set, Optional, Tuple
import re
from product_er_toolkit import normalize_manufacturer, canonicalize_name

class ManufacturerAliasManager:
    """
    Manages manufacturer aliases and provides canonical name resolution.
    
    This class handles the mapping between manufacturer aliases and their canonical forms,
    enabling better matching of products from different vendors that use different
    names for the same manufacturer (e.g., "3M" vs "Minnesota Mining and Manufacturing").
    """
    
    def __init__(self, alias_data_path: str = None, 
                 include_subsidiaries: bool = True,
                 include_brands: bool = True,
                 verbose: bool = False):
        """
        Initialize the alias manager.
        
        Args:
            alias_data_path: Path to CSV file containing alias data
            include_subsidiaries: Whether to include subsidiary names as aliases
            include_brands: Whether to include brand names as aliases
            verbose: Whether to show detailed loading statistics
        """
        self.alias_to_canonical: Dict[str, str] = {}
        self.canonical_to_aliases: Dict[str, Set[str]] = {}
        self.normalized_to_canonical: Dict[str, str] = {}
        self.canonical_to_normalized: Dict[str, str] = {}
        
        # Configuration options
        self.include_subsidiaries = include_subsidiaries
        self.include_brands = include_brands
        self.verbose = verbose
        
        # Statistics tracking
        self.stats = {
            'manufacturers_with_subsidiaries': 0,
            'manufacturers_with_brands': 0,
            'subsidiaries_added': 0,
            'brands_added': 0,
            'subsidiaries_filtered': 0,
            'brands_filtered': 0
        }
        
        if alias_data_path:
            self.load_aliases(alias_data_path)
    
    def load_aliases(self, path: str) -> None:
        """
        Load manufacturer aliases from CSV file.
        
        Expected CSV format:
        - original_name: The primary/canonical name
        - aliases: List of aliases as string representation of Python list
        - aliases_text: Pipe-separated aliases (fallback)
        - subsidiary_names: Pipe-separated subsidiary names (optional)
        - brands_text: Pipe-separated brand names (optional)
        
        Args:
            path: Path to the CSV file
        """
        try:
            df = pd.read_csv(path)
            print(f"Loading manufacturer aliases from {path}...")
            
            for _, row in df.iterrows():
                if row['status'] != 'found':
                    continue
                    
                original_name = str(row['original_name']).strip()
                if not original_name:
                    continue
                
                # Parse aliases from the aliases column (Python list format)
                aliases = self._parse_aliases_column(row.get('aliases', ''))
                
                # Fallback to aliases_text if aliases column is empty
                if not aliases and 'aliases_text' in row:
                    aliases_text = str(row['aliases_text']).strip()
                    if aliases_text:
                        aliases = [alias.strip() for alias in aliases_text.split('|') if alias.strip()]
                
                # Add the original name to aliases if not already present
                if original_name not in aliases:
                    aliases.append(original_name)
                
                # Extract additional aliases from subsidiaries and brands
                additional_aliases = self._extract_additional_aliases(row)
                
                # Filter out duplicates from additional aliases
                if additional_aliases:
                    additional_aliases = self._filter_duplicate_aliases(additional_aliases, aliases)
                    aliases.extend(additional_aliases)
                    
                    # Update statistics
                    if 'subsidiary_names' in row and pd.notna(row.get('subsidiary_names', '')):
                        self.stats['manufacturers_with_subsidiaries'] += 1
                        self.stats['subsidiaries_added'] += len([a for a in additional_aliases if a in self._parse_pipe_delimited_string(row.get('subsidiary_names', ''))])
                    
                    if 'brands_text' in row and pd.notna(row.get('brands_text', '')):
                        self.stats['manufacturers_with_brands'] += 1
                        self.stats['brands_added'] += len([a for a in additional_aliases if a in self._parse_pipe_delimited_string(row.get('brands_text', ''))])
                
                # Normalize all names for consistent lookup
                normalized_original = normalize_manufacturer(original_name)
                normalized_aliases = [normalize_manufacturer(alias) for alias in aliases if alias.strip()]
                
                # Store mappings
                self._store_alias_mappings(normalized_original, normalized_aliases, original_name)
            
            # Print enhanced statistics
            print(f"Loaded {len(self.canonical_to_aliases)} canonical manufacturers with {len(self.alias_to_canonical)} total aliases")
            
            if self.include_subsidiaries or self.include_brands:
                print(f"Enhanced with subsidiaries and brands:")
                print(f"  Manufacturers with subsidiaries: {self.stats['manufacturers_with_subsidiaries']}")
                print(f"  Manufacturers with brands: {self.stats['manufacturers_with_brands']}")
                print(f"  Subsidiaries added: {self.stats['subsidiaries_added']}")
                print(f"  Brands added: {self.stats['brands_added']}")
                print(f"  Subsidiaries filtered: {self.stats['subsidiaries_filtered']}")
                print(f"  Brands filtered: {self.stats['brands_filtered']}")
            
        except Exception as e:
            print(f"Warning: Could not load aliases from {path}: {e}")
            print("Continuing without manufacturer alias support...")
    
    def _parse_aliases_column(self, aliases_str: str) -> List[str]:
        """
        Parse the aliases column which contains a string representation of a Python list.
        
        Args:
            aliases_str: String like "['alias1', 'alias2', 'alias3']"
            
        Returns:
            List of aliases
        """
        if not aliases_str or aliases_str.strip() == '':
            return []
        
        try:
            # Use ast.literal_eval to safely parse the Python list
            aliases = ast.literal_eval(aliases_str)
            if isinstance(aliases, list):
                return [str(alias).strip() for alias in aliases if str(alias).strip()]
            else:
                return []
        except (ValueError, SyntaxError):
            # Fallback: try to parse as comma-separated values
            try:
                # Remove brackets and quotes, then split
                cleaned = aliases_str.strip("[]'\"")
                aliases = [alias.strip().strip("'\"") for alias in cleaned.split(',')]
                return [alias for alias in aliases if alias]
            except:
                return []
    
    def _parse_pipe_delimited_string(self, text: str) -> List[str]:
        """
        Parse pipe-delimited string into list of names.
        
        Args:
            text: Pipe-delimited string (e.g., "Name1|Name2|Name3")
            
        Returns:
            List of cleaned names
        """
        if not text or pd.isna(text) or str(text).strip() == '':
            return []
        
        # Split by pipe and clean each name
        names = [name.strip() for name in str(text).split('|') if name.strip()]
        return names
    
    def _is_valid_manufacturer_name(self, name: str) -> bool:
        """
        Apply conservative filtering to determine if a name is likely a manufacturer name.
        
        Args:
            name: Name to validate
            
        Returns:
            True if the name passes conservative filtering
        """
        if not name or len(name.strip()) < 3:
            return False
        
        name = name.strip()
        
        # Filter out names that are clearly not manufacturer names
        # (Conservative approach - filter more, include less)
        
        # Skip very short names
        if len(name) < 3:
            return False
        
        # Skip names that are mostly numbers or special characters
        if len(re.sub(r'[^a-zA-Z0-9\s]', '', name)) < len(name) * 0.5:
            return False
        
        # Skip names that look like locations (contain common location words)
        location_words = ['switzerland', 'germany', 'united kingdom', 'canada', 'france', 
                         'italy', 'japan', 'netherlands', 'sweden', 'norway', 'denmark',
                         'australia', 'brazil', 'mexico', 'spain', 'portugal', 'poland',
                         'czech', 'hungary', 'austria', 'belgium', 'finland', 'ireland']
        
        name_lower = name.lower()
        for location in location_words:
            if location in name_lower:
                return False
        
        # Skip names that look like product types or descriptions
        product_words = ['corporation', 'inc', 'llc', 'ltd', 'co', 'company', 'group',
                        'holdings', 'enterprises', 'international', 'global', 'systems',
                        'technologies', 'solutions', 'services', 'products', 'industries']
        
        # If the name is just a common business suffix, skip it
        if name_lower in product_words:
            return False
        
        # Skip names that are mostly business suffixes
        words = name_lower.split()
        if len(words) == 1 and words[0] in product_words:
            return False
        
        return True
    
    def _extract_additional_aliases(self, row: pd.Series) -> List[str]:
        """
        Extract subsidiaries and brands as additional aliases.
        
        Args:
            row: CSV row containing manufacturer data
            
        Returns:
            List of additional aliases (subsidiaries and brands)
        """
        additional_aliases = []
        
        # Extract subsidiaries if enabled
        if self.include_subsidiaries and 'subsidiary_names' in row:
            subsidiaries = self._parse_pipe_delimited_string(row.get('subsidiary_names', ''))
            for subsidiary in subsidiaries:
                if self._is_valid_manufacturer_name(subsidiary):
                    additional_aliases.append(subsidiary)
                else:
                    self.stats['subsidiaries_filtered'] += 1
                    if self.verbose:
                        print(f"  Filtered subsidiary: '{subsidiary}'")
        
        # Extract brands if enabled
        if self.include_brands and 'brands_text' in row:
            brands = self._parse_pipe_delimited_string(row.get('brands_text', ''))
            for brand in brands:
                if self._is_valid_manufacturer_name(brand):
                    additional_aliases.append(brand)
                else:
                    self.stats['brands_filtered'] += 1
                    if self.verbose:
                        print(f"  Filtered brand: '{brand}'")
        
        return additional_aliases
    
    def _filter_duplicate_aliases(self, new_aliases: List[str], existing_aliases: List[str]) -> List[str]:
        """
        Remove duplicates from new aliases by comparing with existing aliases.
        
        Args:
            new_aliases: List of new aliases to check
            existing_aliases: List of existing aliases to compare against
            
        Returns:
            List of new aliases with duplicates removed
        """
        if not new_aliases or not existing_aliases:
            return new_aliases
        
        # Normalize existing aliases for comparison
        existing_normalized = {normalize_manufacturer(alias) for alias in existing_aliases}
        
        # Filter out duplicates
        filtered_aliases = []
        for alias in new_aliases:
            normalized_alias = normalize_manufacturer(alias)
            if normalized_alias not in existing_normalized:
                filtered_aliases.append(alias)
        
        return filtered_aliases
    
    def _store_alias_mappings(self, canonical_normalized: str, aliases_normalized: List[str], canonical_original: str) -> None:
        """
        Store the alias mappings in internal data structures.
        
        Args:
            canonical_normalized: The normalized canonical name
            aliases_normalized: List of normalized aliases
            canonical_original: The original canonical name (for display)
        """
        if not canonical_normalized or not aliases_normalized:
            return
        
        # Store canonical to aliases mapping
        self.canonical_to_aliases[canonical_normalized] = set(aliases_normalized)
        
        # Store alias to canonical mapping
        for alias in aliases_normalized:
            if alias:  # Skip empty aliases
                self.alias_to_canonical[alias] = canonical_normalized
        
        # Store original canonical name for reference
        self.canonical_to_normalized[canonical_normalized] = canonical_original
        self.normalized_to_canonical[canonical_normalized] = canonical_normalized
    
    def get_canonical_name(self, manufacturer_name: str) -> Optional[str]:
        """
        Get the canonical name for a given manufacturer name.
        
        This method normalizes the input and looks up the canonical form.
        If the manufacturer is not found in the alias database, returns None.
        
        Args:
            manufacturer_name: The manufacturer name to look up
            
        Returns:
            The canonical normalized name if found, None otherwise
            
        Examples:
            >>> manager.get_canonical_name("3M")
            "3M"
            >>> manager.get_canonical_name("Minnesota Mining and Manufacturing")
            "3M"
            >>> manager.get_canonical_name("Unknown Corp")
            None
        """
        if not manufacturer_name or not isinstance(manufacturer_name, str):
            return None
        
        # Normalize the input name
        normalized_name = normalize_manufacturer(manufacturer_name)
        
        if not normalized_name:
            return None
        
        # Direct lookup in alias mapping
        canonical = self.alias_to_canonical.get(normalized_name)
        if canonical:
            return canonical
        
        # If not found, the name might already be canonical
        if normalized_name in self.canonical_to_aliases:
            return normalized_name
        
        return None
    
    def get_aliases(self, canonical_name: str) -> Set[str]:
        """
        Get all aliases for a canonical manufacturer name.
        
        Args:
            canonical_name: The canonical name (can be normalized or original)
            
        Returns:
            Set of all aliases including the canonical name itself
            
        Examples:
            >>> manager.get_aliases("3M")
            {"3M", "MINNESOTA MINING AND MANUFACTURING", "3M COMPANY", ...}
            >>> manager.get_aliases("Unknown Corp")
            set()
        """
        if not canonical_name or not isinstance(canonical_name, str):
            return set()
        
        # Normalize the input
        normalized_canonical = normalize_manufacturer(canonical_name)
        
        if not normalized_canonical:
            return set()
        
        # Get aliases from the mapping
        aliases = self.canonical_to_aliases.get(normalized_canonical, set())
        
        # Return a copy to prevent external modification
        return aliases.copy()
    
    def get_all_aliases_for_name(self, manufacturer_name: str) -> Set[str]:
        """
        Get all aliases for any manufacturer name (canonical or alias).
        
        This is a convenience method that first resolves to canonical name,
        then returns all aliases.
        
        Args:
            manufacturer_name: Any manufacturer name (canonical or alias)
            
        Returns:
            Set of all aliases for this manufacturer
        """
        canonical = self.get_canonical_name(manufacturer_name)
        if canonical:
            return self.get_aliases(canonical)
        else:
            # If not found in aliases, return just the normalized name
            normalized = normalize_manufacturer(manufacturer_name)
            return {normalized} if normalized else set()
    
    def is_alias_of(self, name1: str, name2: str) -> bool:
        """
        Check if two manufacturer names are aliases of the same canonical manufacturer.
        
        Args:
            name1: First manufacturer name
            name2: Second manufacturer name
            
        Returns:
            True if both names refer to the same canonical manufacturer
            
        Examples:
            >>> manager.is_alias_of("3M", "Minnesota Mining and Manufacturing")
            True
            >>> manager.is_alias_of("3M", "Apple")
            False
        """
        canonical1 = self.get_canonical_name(name1)
        canonical2 = self.get_canonical_name(name2)
        
        return canonical1 is not None and canonical2 is not None and canonical1 == canonical2
    
    def get_original_canonical_name(self, manufacturer_name: str) -> Optional[str]:
        """
        Get the original (non-normalized) canonical name for display purposes.
        
        Args:
            manufacturer_name: The manufacturer name to look up
            
        Returns:
            The original canonical name if found, None otherwise
        """
        canonical_normalized = self.get_canonical_name(manufacturer_name)
        if canonical_normalized:
            return self.canonical_to_normalized.get(canonical_normalized, canonical_normalized)
        return None
    
    def add_manual_alias(self, canonical_name: str, alias_name: str) -> None:
        """
        Manually add an alias mapping.
        
        This is useful for adding custom aliases not in the CSV data.
        
        Args:
            canonical_name: The canonical manufacturer name
            alias_name: The alias name
        """
        canonical_normalized = normalize_manufacturer(canonical_name)
        alias_normalized = normalize_manufacturer(alias_name)
        
        if canonical_normalized and alias_normalized:
            # Add to canonical to aliases mapping
            if canonical_normalized not in self.canonical_to_aliases:
                self.canonical_to_aliases[canonical_normalized] = set()
            self.canonical_to_aliases[canonical_normalized].add(alias_normalized)
            
            # Add to alias to canonical mapping
            self.alias_to_canonical[alias_normalized] = canonical_normalized
            
            # Store original names
            self.canonical_to_normalized[canonical_normalized] = canonical_name
            self.normalized_to_canonical[canonical_normalized] = canonical_normalized
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about loaded aliases.
        
        Returns:
            Dictionary with statistics
        """
        base_stats = {
            'canonical_manufacturers': len(self.canonical_to_aliases),
            'total_aliases': len(self.alias_to_canonical),
            'avg_aliases_per_manufacturer': len(self.alias_to_canonical) / max(1, len(self.canonical_to_aliases))
        }
        
        # Add enhanced statistics if subsidiaries/brands are enabled
        if self.include_subsidiaries or self.include_brands:
            base_stats.update(self.stats)
        
        return base_stats
    
    def search_manufacturers(self, query: str, limit: int = 10) -> List[Tuple[str, str, Set[str]]]:
        """
        Search for manufacturers by name (useful for debugging/exploration).
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of tuples: (original_name, canonical_normalized, aliases)
        """
        query_normalized = normalize_manufacturer(query)
        results = []
        
        for canonical, aliases in self.canonical_to_aliases.items():
            if query_normalized in canonical or any(query_normalized in alias for alias in aliases):
                original = self.canonical_to_normalized.get(canonical, canonical)
                results.append((original, canonical, aliases))
                
                if len(results) >= limit:
                    break
        
        return results

# Example usage and testing
if __name__ == "__main__":
    # Initialize with the alias data
    manager = ManufacturerAliasManager("wikidata_business_results.csv")
    
    # Test the 3M example
    print("Testing 3M aliases:")
    print(f"Canonical for '3M': {manager.get_canonical_name('3M')}")
    print(f"Canonical for 'Minnesota Mining and Manufacturing': {manager.get_canonical_name('Minnesota Mining and Manufacturing')}")
    print(f"Are they the same? {manager.is_alias_of('3M', 'Minnesota Mining and Manufacturing')}")
    print(f"All aliases for 3M: {manager.get_aliases('3M')}")
    
    # Test HP example
    print("\nTesting HP aliases:")
    print(f"Canonical for 'HP Inc.': {manager.get_canonical_name('HP Inc.')}")
    print(f"Canonical for 'HPQ': {manager.get_canonical_name('HPQ')}")
    print(f"Are they the same? {manager.is_alias_of('HP Inc.', 'HPQ')}")
    
    # Show statistics
    print(f"\nAlias manager stats: {manager.get_stats()}")
