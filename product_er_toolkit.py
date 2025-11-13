
import re, math
import time
import logging
from functools import lru_cache
from typing import List, Tuple, Dict, Any, Callable, Optional
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import GradientBoostingClassifier


logger = logging.getLogger(__name__)

CORP_SUFFIXES = ["INC","INC.","LLC","L.L.C.","LTD","LTD.","LIMITED","CO","CO.","CORP","CORP.","CORPORATION","GMBH","AG","BV","B.V.","S.A.","SAS","PLC","P.L.C.","PTE","PTY","AB","OY","KK","K.K.","SA","S.P.A.","SRL","S.R.L.","TECHNOLOGIES","SYSTEMS","SOLUTIONS","SERVICES","ENTERPRISES","INDUSTRIES","INTERNATIONAL","WORLDWIDE","GLOBAL","GROUP","COMPANY","COMPANIES"]

def canonicalize_name(s: str) -> str:
    if not isinstance(s, str): return ""
    x = s.upper().replace("&"," AND ")
    x = re.sub(r"[^A-Z0-9 ]+"," ", x)
    x = re.sub(r"\s+"," ", x).strip()
    tokens = x.split()
    while tokens and tokens[-1] in CORP_SUFFIXES:
        tokens = tokens[:-1]
    return " ".join(tokens)

def validate_unspsc(unspsc: str) -> bool:
    """Validate UNSPSC code format - should be exactly 8 digits"""
    if not unspsc or not isinstance(unspsc, str):
        return False
    clean_unspsc = str(unspsc).strip()
    return len(clean_unspsc) == 8 and clean_unspsc.isdigit()

def normalize_unspsc(unspsc: str) -> str:
    """Normalize UNSPSC code - just strip whitespace, no other processing needed"""
    if unspsc is None:
        return ""
    return str(unspsc).strip()

def normalize_manufacturer(s: str) -> str:
    import unicodedata
    s = s or ""
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return canonicalize_name(s)

@lru_cache(maxsize=500)
def _generate_manufacturer_prefixes(name: str, min_len: int = 2, max_len: int = 4) -> List[str]:
    """
    Generate intelligent prefixes from a manufacturer name.
    Results are cached for performance.
    
    Args:
        name: Manufacturer name (e.g., "EATON", "MICROSOFT")
        min_len: Minimum prefix length (default: 2)
        max_len: Maximum prefix length (default: 4)
    
    Returns:
        List of prefix strings, sorted by relevance
    """
    if not name or not isinstance(name, str):
        return []
    
    name = name.upper().strip()
    if not name:
        return []
    
    prefixes = set()
    
    # Strategy 1: Simple truncation (first N characters)
    for length in range(min_len, max_len + 1):
        if len(name) >= length:
            prefixes.add(name[:length])
    
    # Strategy 2: Consonant extraction (common for tech companies)
    # e.g., MICROSOFT -> MSFT, APPLE -> APPL
    consonants = ''.join([c for c in name if c not in 'AEIOU'])
    for length in range(min_len, max_len + 1):
        if len(consonants) >= length:
            prefixes.add(consonants[:length])
    
    # Strategy 3: First letter of each word (for multi-word names)
    words = name.replace('-', ' ').replace('_', ' ').split()
    if len(words) > 1:
        acronym = ''.join([w[0] for w in words if w])
        if min_len <= len(acronym) <= max_len:
            prefixes.add(acronym)
        # Also add truncated version if acronym is too long
        if len(acronym) > max_len:
            prefixes.add(acronym[:max_len])
    
    # Strategy 4: First + last characters (for very short target prefixes)
    if len(name) > 2 and min_len <= 2:
        prefixes.add(name[0] + name[-1])
    if len(name) > 3 and min_len <= 3:
        prefixes.add(name[0] + name[-2:])
    
    # Strategy 5: Syllable-aware extraction (take first char + first consonant after vowel)
    # e.g., EATON -> ETN (E + T + N)
    syllable_chars = [name[0]]
    prev_vowel = name[0] in 'AEIOU'
    for c in name[1:]:
        is_vowel = c in 'AEIOU'
        if prev_vowel and not is_vowel:
            syllable_chars.append(c)
        prev_vowel = is_vowel
    
    syllable_prefix = ''.join(syllable_chars)
    for length in range(min_len, max_len + 1):
        if len(syllable_prefix) >= length:
            prefixes.add(syllable_prefix[:length])
    
    # Filter and sort by relevance
    # Prefer: shorter, starts with original first char, has consonants
    valid_prefixes = [p for p in prefixes if min_len <= len(p) <= max_len]
    
    def score_prefix(p):
        score = 0
        score += (max_len - len(p)) * 2  # Prefer shorter
        if p[0] == name[0]:
            score += 5  # Must start with same letter
        else:
            score -= 10  # Penalize heavily if doesn't match
        score += sum(1 for c in p if c not in 'AEIOU')  # Prefer consonants
        return score
    
    valid_prefixes.sort(key=score_prefix, reverse=True)
    
    # Return top results (limit to avoid too many)
    return valid_prefixes[:8]

def _is_suffix_only_difference(pn1: str, pn2: str) -> bool:
    """
    Check if two part numbers differ only by a suffix.
    Returns True if one is a prefix of the other + suffix.
    """
    pn1_clean = pn1.strip().upper()
    pn2_clean = pn2.strip().upper()
    
    # Check if one is a prefix of the other
    if pn1_clean.startswith(pn2_clean) and len(pn1_clean) > len(pn2_clean):
        # pn1 is pn2 + suffix
        suffix = pn1_clean[len(pn2_clean):].strip()
        return _is_valid_suffix(suffix)
    elif pn2_clean.startswith(pn1_clean) and len(pn2_clean) > len(pn1_clean):
        # pn2 is pn1 + suffix  
        suffix = pn2_clean[len(pn1_clean):].strip()
        return _is_valid_suffix(suffix)
    
    return False

def _is_valid_suffix(suffix: str) -> bool:
    """Check if the suffix is a valid unit/descriptor suffix"""
    if not suffix:
        return False
    
    # Remove common separators
    suffix_clean = re.sub(r'^[-_/\.\s]+', '', suffix)
    
    # Check against known suffix patterns
    valid_suffixes = [
        'ea', 'each', 'pcs', 'pieces', 'piece', 'pk', 'pack', 'unit', 'units',
        'ct', 'count', 'qty', 'quantity', 'bulk', 'retail', 'consumer', 
        'commercial', 'std', 'standard', 'new', 'old', 'original', 
        'replacement', 'refurb'
    ]
    
    # Check exact matches
    if suffix_clean.lower() in valid_suffixes:
        return True
    
    # Check version patterns (rev1, v2, etc.) - limit to 1-3 digits
    if re.match(r'^(rev|version|v|r)\d{1,3}$', suffix_clean, re.IGNORECASE):
        return True
    
    # Check single letter suffixes
    if len(suffix_clean) == 1 and suffix_clean.isalpha():
        return True
    
    return False

def _extract_manufacturer_prefix(pn: str, manufacturer_name: Optional[str] = None) -> Tuple[str, str]:
    """
    Extract manufacturer prefix from the beginning of part number.
    
    Args:
        pn: Part number string
        manufacturer_name: Optional manufacturer name to generate specific prefixes
    
    Returns:
        Tuple of (prefix, remaining_part_number)
    """
    if not pn:
        return "", pn
    
    pn_upper = pn.upper()
    
    # Generate manufacturer-specific prefixes if name is provided
    known_prefixes = set()
    if manufacturer_name:
        generated = _generate_manufacturer_prefixes(manufacturer_name, min_len=2, max_len=6)
        known_prefixes = set(p.upper() for p in generated)
        # Also add the full manufacturer name (first word if multi-word)
        first_word = manufacturer_name.upper().split()[0]
        known_prefixes.add(first_word)
    
    # Pattern groups: (prefix_capture)(separator?)(remaining)
    patterns = [
        r'^([A-Za-z]{2,6})[-_/.\s](.+)',        # With separator: ABC-123, ABC/XYZ, ABC 123
        r'^([A-Za-z]{2,6})([0-9].+)',           # Direct letters+numbers: ABC123
    ]
    
    best_match = ("", pn)
    best_score = -1
    
    for pattern in patterns:
        match = re.match(pattern, pn, re.IGNORECASE)
        if match:
            prefix = match.group(1).upper()
            remaining = match.group(2)
            
            # Validate the match - just need substantial remaining content
            if not (remaining and len(remaining) >= 2 and len(prefix) >= 2):
                continue
            
            # Score this match
            score = 0
            
            # If we have known prefixes, prioritize exact matches
            if known_prefixes:
                if prefix in known_prefixes:
                    score += 100  # Strong match
                elif any(prefix.startswith(kp) or kp.startswith(prefix) for kp in known_prefixes):
                    score += 50  # Partial match
                else:
                    score = -1  # Generic match, but still possible
            else:
                # No manufacturer context, use generic scoring
                score = -1
                        
            # Prefer longer prefixes (more specific)
            if (score > 0):
                score += len(prefix)
                
                # Strongly prefer matches with clear separators (first pattern)
                if '-' in pn[:len(prefix)+1] or '_' in pn[:len(prefix)+1] or '/' in pn[:len(prefix)+1] or '.' in pn[:len(prefix)+1] or ' ' in pn[:len(prefix)+1]:
                    score += 10
            
            if score > best_score:
                best_score = score
                best_match = (prefix, remaining)
    
    # If no manufacturer-aware match found and no manufacturer provided, fall back to generic extraction
    if best_score < 0 and not manufacturer_name:
        # Fallback to simple pattern matching (original behavior)
        for pattern in patterns:
            match = re.match(pattern, pn, re.IGNORECASE)
            if match:
                prefix = match.group(1).upper()
                remaining = match.group(2)
                # Only treat as prefix if it's clearly separated and substantial
                if (remaining and len(remaining) >= 2 and len(prefix) >= 2):
                    return prefix, remaining
    
    return best_match

def _extract_unit_suffix(pn: str) -> Tuple[str, str]:
    """
    Extract unit suffix from the end of part number.
    Returns (remaining_part_number, suffix)
    """
    # Known unit suffixes - try each pattern
    unit_patterns = [
        r'(.*?)\s*(ea|each|pcs|pieces?|pk|pack|unit|units?|ct|count|qty|quantity)\s*$',
        r'(.*?)\s*(bulk|retail|consumer|commercial|std|standard)\s*$',
        r'(.*?)\s*(rev\d{1,3}|version\d{1,3}|v\d{1,3}|r\d{1,3})\s*$',  # Limit version numbers to 1-3 digits
        r'(.*?)\s*(new|old|original|replacement|refurb)\s*$',
    ]
    
    for pattern in unit_patterns:
        match = re.match(pattern, pn, re.IGNORECASE)
        if match:
            remaining = match.group(1)
            suffix = match.group(2).upper()
            # Only return if the remaining part is substantial (not just a few characters)
            # Also check that the suffix is not part of the core part number
            if len(remaining.strip()) >= 3 and len(suffix) <= 10:
                return remaining, suffix
    
    return pn, ""

def _extract_all_suffixes(pn: str) -> Tuple[str, List[str]]:
    """
    Extract all suffixes from the end of part number iteratively.
    Returns (core_part_number, list_of_suffixes)
    """
    suffixes = []
    current = pn.strip()
    
    # Keep removing suffixes until no more can be found
    changed = True
    while changed:
        changed = False
        remaining, suffix = _extract_unit_suffix(current)
        if suffix and remaining != current:
            suffixes.insert(0, suffix)  # Insert at beginning to maintain order
            current = remaining.strip()
            changed = True
    
    return current, suffixes

def pn_variants(pn: str, manufacturer_name: Optional[str] = None) -> List[str]:
    """
    Enhanced part number variants with intelligent parsing:
    - Separates manufacturer prefix, core part number, and unit suffix
    - Handles unit suffixes (ea, each, pcs, etc.)
    - Handles OCR errors (O->0, I->1)
    - Handles separator variations (-, _, /, .)
    - Handles space variations
    - Manufacturer-aware prefix extraction (when manufacturer_name provided)
    
    Args:
        pn: Part number string
        manufacturer_name: Optional normalized manufacturer name for intelligent prefix extraction
    """
    if not isinstance(pn, str): return []
    
    original = pn.strip()
    if not original: return []
    
    variants = set()
    
    # Step 1: Add original
    variants.add(original)
    
    # Step 2: Intelligent parsing - extract components
    # Normalize manufacturer name if provided
    norm_mfr = normalize_manufacturer(manufacturer_name) if manufacturer_name else None
    prefix, remaining_after_prefix = _extract_manufacturer_prefix(original, norm_mfr)
    core_part, suffixes = _extract_all_suffixes(remaining_after_prefix)
    
    # Step 3: Generate meaningful variants based on components
    if prefix and core_part and suffixes:
        # Case: "AGM14NV4123414111EA" -> prefix="AGM", core="14NV4123414111", suffixes=["EA"]
        variants.update([
            core_part,                    # "14NV4123414111"
            f"{prefix}{core_part}",       # "AGM14NV4123414111"
        ])
        # Add variants with individual suffixes and combinations
        for suffix in suffixes:
            variants.update([
                f"{core_part}{suffix}",   # "14NV4123414111EA"
                # Don't add suffix alone - too generic (e.g., 'EA', 'PCS' match thousands of products)
            ])
        # Add combinations of multiple suffixes
        if len(suffixes) > 1:
            # Add core + first suffix (for backward compatibility)
            variants.add(f"{core_part}{suffixes[0]}")
            # Add all suffixes combined
            all_suffixes = "".join(suffixes)
            variants.add(f"{core_part}{all_suffixes}")
        # Don't add prefix alone - too generic (e.g., 'HP', 'DELL' match thousands of products)
    elif prefix and core_part:
        # Case: "AGM14NV4123414111" -> prefix="AGM", core="14NV4123414111"
        variants.update([
            core_part,                    # "14NV4123414111"
            f"{prefix}{core_part}",       # "AGM14NV4123414111"
            # Don't add prefix alone - too generic (e.g., 'HP', 'DELL' match thousands of products)
        ])
    elif core_part and suffixes:
        # Case: "14NV4123414111EA" -> core="14NV4123414111", suffixes=["EA"]
        variants.add(core_part)           # "14NV4123414111"
        for suffix in suffixes:
            variants.update([
                f"{core_part}{suffix}",   # "14NV4123414111EA"
                # Don't add suffix alone - too generic (e.g., 'EA', 'PCS' match thousands of products)
            ])
        # Add combinations of multiple suffixes
        if len(suffixes) > 1:
            # Add core + first suffix (for backward compatibility)
            variants.add(f"{core_part}{suffixes[0]}")
            # Add all suffixes combined
            all_suffixes = "".join(suffixes)
            variants.add(f"{core_part}{all_suffixes}")
    elif core_part:
        # Case: "14NV4123414111" -> core="14NV4123414111"
        variants.add(core_part)
    
    # Step 4: Fallback to original suffix removal for edge cases
    # This handles cases where our intelligent parsing might miss something
    suffixes_to_remove = [
        r'\s+(ea|each|pcs|pieces?|pk|pack|unit|units?|ct|count|qty|quantity)\s*$',
        r'\s+(bulk|retail|consumer|commercial|std|standard)\s*$',
        r'\s*[-_/\.]?\s*(rev\d{1,3}|version\d{1,3}|v\d{1,3}|r\d{1,3})\s*$',  # Limit version numbers to 1-3 digits
        r'\s*[-_/\.]?\s*(new|old|original|replacement|refurb)\s*$',
    ]
    
    # Only apply fallback if we didn't find components through intelligent parsing
    if not (prefix or suffixes):
        current = original
        changed = True
        while changed:
            changed = False
            for suffix_pattern in suffixes_to_remove:
                cleaned = re.sub(suffix_pattern, '', current, flags=re.IGNORECASE)
                if cleaned != current and cleaned.strip():
                    variants.add(cleaned)
                    current = cleaned
                    changed = True
                    break
    
    # Step 5: Apply existing transformations to ALL variants
    final_variants = set()
    for variant in variants:
        # EXISTING transformations (unchanged)
        base = re.sub(r"\s+", "", variant)           # Remove spaces
        no_sep = re.sub(r"[-_/\.]", "", base)        # Remove separators  
        o_to_0 = no_sep.replace("O", "0").replace("o", "0")  # OCR: O->0
        i_to_1 = o_to_0.replace("I", "1").replace("l", "1")   # OCR: I/l->1
        
        final_variants.update([variant, base, no_sep, o_to_0, i_to_1])
    
    return list({v.upper() for v in final_variants if v})

def levenshtein(a: str, b: str) -> int:
    if a == b: return 0
    if len(a) == 0: return len(b)
    if len(b) == 0: return len(a)
    v0 = list(range(len(b) + 1))
    v1 = [0] * (len(b) + 1)
    for i in range(len(a)):
        v1[0] = i + 1
        for j in range(len(b)):
            cost = 0 if a[i] == b[j] else 1
            v1[j+1] = min(v1[j] + 1, v0[j+1] + 1, v0[j] + cost)
        v0, v1 = v1, v0
    return v0[len(b)]

def jaro_winkler(s1: str, s2: str, p=0.1, max_l=4) -> float:
    s1 = (s1 or "").upper(); s2 = (s2 or "").upper()
    if s1 == s2: return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0: return 0.0
    match_distance = (max(len1, len2) // 2) - 1
    s1_matches = [False]*len1; s2_matches = [False]*len2
    matches = transpositions = 0
    for i in range(len1):
        start = max(0, i - match_distance); end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j]: continue
            if s1[i] != s2[j]: continue
            s1_matches[i] = s2_matches[j] = True; matches += 1
            break
    if matches == 0: return 0.0
    k = 0
    for i in range(len1):
        if not s1_matches[i]: continue
        while not s2_matches[k]: k += 1
        if s1[i] != s2[k]: transpositions += 1
        k += 1
    transpositions /= 2
    jaro = (matches/len1 + matches/len2 + (matches - transpositions)/matches) / 3.0
    prefix = 0
    for i in range(min(max_l, len1, len2)):
        if s1[i] == s2[i]: prefix += 1
        else: break
    return jaro + prefix * p * (1 - jaro)

def char_trigram_set(s: str) -> set:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+"," ", s)
    s = re.sub(r"\s+"," ", s).strip()
    if len(s) < 3: return {s} if s else set()
    return {s[i:i+3] for i in range(len(s)-2)}

def jaccard(a: set, b: set) -> float:
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    inter = len(a & b); union = len(a | b)
    return inter/union if union else 0.0

def build_enhanced_manufacturer_features(mfr_a: str, mfr_b: str, alias_manager=None) -> Dict[str, float]:
    """
    Build enhanced manufacturer features using alias information.
    
    Args:
        mfr_a: First manufacturer name
        mfr_b: Second manufacturer name
        alias_manager: Optional ManufacturerAliasManager instance
        
    Returns:
        Dictionary of manufacturer-related features
    """
    # Normalize manufacturer names
    mfr_a_norm = normalize_manufacturer(mfr_a)
    mfr_b_norm = normalize_manufacturer(mfr_b)
    
    # Basic features (existing functionality)
    mfr_exact = 1.0 if mfr_a_norm and mfr_a_norm == mfr_b_norm else 0.0
    
    # OPTIMIZATION: If we have an exact match, skip all fuzzy calculations
    # The similarity score calculation will use mfr_exact and ignore other features
    if mfr_exact == 1.0:
        return {
            'mfr_exact': 1.0,
            'mfr_jw': 1.0,  # Set to 1.0 for consistency (won't be used)
            'mfr_alias_exact': 0.0,
            'mfr_canonical_jw': 0.0,
            'mfr_best_alias_jw': 0.0
        }
    
    # Calculate Jaro-Winkler only if not exact match
    mfr_jw = jaro_winkler(mfr_a_norm, mfr_b_norm)
    
    features = {
        'mfr_exact': 0.0,
        'mfr_jw': float(mfr_jw)
    }
    
    # Enhanced features using alias manager
    if alias_manager:
        # Get canonical names
        canonical_a = alias_manager.get_canonical_name(mfr_a)
        canonical_b = alias_manager.get_canonical_name(mfr_b)
        
        # Alias-based features
        if canonical_a and canonical_b:
            # Same canonical manufacturer
            mfr_alias_exact = 1.0 if canonical_a == canonical_b else 0.0
            features['mfr_alias_exact'] = float(mfr_alias_exact)
            
            # OPTIMIZATION: If we have an alias exact match, skip expensive fuzzy calculations
            # The similarity score calculation will use mfr_alias_exact and ignore fuzzy features
            if mfr_alias_exact == 1.0:
                features['mfr_canonical_jw'] = 1.0  # Set to 1.0 for consistency (won't be used)
                features['mfr_best_alias_jw'] = 1.0  # Set to 1.0 for consistency (won't be used)
                return features
            
            # Jaro-Winkler between canonical names (only if no exact alias match)
            mfr_canonical_jw = jaro_winkler(canonical_a, canonical_b)
            features['mfr_canonical_jw'] = float(mfr_canonical_jw)
            
            # Best Jaro-Winkler between any aliases (only if no exact alias match)
            # OPTIMIZATION: Check for exact alias matches first (O(n) set intersection)
            if canonical_a == canonical_b:
                aliases_a = alias_manager.get_aliases(canonical_a)
                aliases_b = alias_manager.get_aliases(canonical_b)
                
                # Fast path: Check for exact matches first (instant, O(n))
                exact_alias_matches = aliases_a & aliases_b
                if exact_alias_matches:
                    features['mfr_best_alias_jw'] = 1.0  # Perfect match found, skip 14,641 calculations!
                else:
                    # Only do expensive fuzzy matching if no exact match
                    best_alias_jw = 0.0
                    for alias_a in aliases_a:
                        for alias_b in aliases_b:
                            jw = jaro_winkler(alias_a, alias_b)
                            best_alias_jw = max(best_alias_jw, jw)
                    features['mfr_best_alias_jw'] = float(best_alias_jw)
            else:
                features['mfr_best_alias_jw'] = 0.0
        else:
            # No alias information available
            features['mfr_alias_exact'] = 0.0
            features['mfr_canonical_jw'] = 0.0
            features['mfr_best_alias_jw'] = 0.0
    else:
        # No alias manager provided
        features['mfr_alias_exact'] = 0.0
        features['mfr_canonical_jw'] = 0.0
        features['mfr_best_alias_jw'] = 0.0
    
    return features

def is_short_variant(original_pn: str, variant: str) -> bool:
    """
    Determine if a variant is too short to be used for exact matching.
    
    Uses adaptive thresholds based on original part number length:
    - Very short PNs (≤5): Keep all variants (they're all meaningful)
    - Short PNs (6-8): Filter ≤3 chars (< 50% of original)
    - Medium PNs (9-12): Filter ≤4 chars (< 45% of original)
    - Long PNs (13+): Filter <40% of original length
    
    Args:
        original_pn: The original part number
        variant: A generated variant
        
    Returns:
        True if variant should be filtered (too short), False otherwise
    """
    orig_len = len(original_pn)
    var_len = len(variant)
    
    # Very short part numbers: keep all variants
    if orig_len <= 5:
        return False
    
    # Short part numbers (6-8): filter ≤3 chars
    if orig_len <= 8:
        return var_len <= 3
    
    # Medium part numbers (9-12): filter ≤4 chars
    if orig_len <= 12:
        return var_len <= 4
    
    # Long part numbers (13+): filter <40% of original
    return var_len < (orig_len * 0.4)

def calculate_pn_match_weight(pn_a: str, pn_b: str, matching_variants: List[str]) -> float:
    """
    Calculate weight for part number match based on variant quality.
    
    Uses tiered weighting based on the longest matching variant:
    - Near-full match (≥80% of original): 0.4 (full weight)
    - Substantial match (60-80%): 0.3 (75% weight)
    - Medium match (40-60%): 0.2 (50% weight)
    - Short match (<40%): 0.1 (25% weight)
    
    Args:
        pn_a: Original part number A
        pn_b: Original part number B
        matching_variants: List of variant strings that matched
        
    Returns:
        Weight between 0.0 and 0.4 based on best matching variant
    """
    if not matching_variants:
        return 0.0
    
    # Find longest matching variant (most substantial match)
    max_len = max(len(v) for v in matching_variants)
    
    # Calculate percentage of original (use average of both)
    orig_len_a = len(pn_a) if pn_a else 0
    orig_len_b = len(pn_b) if pn_b else 0
    avg_orig_len = (orig_len_a + orig_len_b) / 2
    
    if avg_orig_len == 0:
        return 0.0
    
    percentage = max_len / avg_orig_len
    
    # Tiered weighting
    if percentage >= 0.8:
        return 0.4  # Near-full match (80%+)
    elif percentage >= 0.6:
        return 0.3  # Substantial match (60-80%)
    elif percentage >= 0.4:
        return 0.2  # Medium match (40-60%)
    else:
        return 0.1  # Short match (<40%)

def build_pair_features(a: Dict[str, Any], b: Dict[str, Any], alias_manager=None, filter_short_variants: bool = True) -> Dict[str, float]:
    # Get enhanced manufacturer features
    mfr_features = build_enhanced_manufacturer_features(
        a.get("manufacturer", ""), 
        b.get("manufacturer", ""), 
        alias_manager
    )
    
    
    # UNSPSC features (replacing brand features)
    unspsc_a = normalize_unspsc(a.get("unspsc", ""))
    unspsc_b = normalize_unspsc(b.get("unspsc", ""))
    unspsc_exact = 1.0 if unspsc_a and unspsc_b and unspsc_a == unspsc_b else 0.0
    
    # UNSPSC hierarchical matching (segment, family, class, commodity)
    unspsc_segment_match = 1.0 if (unspsc_a and unspsc_b and len(unspsc_a) >= 2 and len(unspsc_b) >= 2 
                                   and unspsc_a[:2] == unspsc_b[:2]) else 0.0
    unspsc_family_match = 1.0 if (unspsc_a and unspsc_b and len(unspsc_a) >= 4 and len(unspsc_b) >= 4 
                                  and unspsc_a[:4] == unspsc_b[:4]) else 0.0
    unspsc_class_match = 1.0 if (unspsc_a and unspsc_b and len(unspsc_a) >= 6 and len(unspsc_b) >= 6 
                                 and unspsc_a[:6] == unspsc_b[:6]) else 0.0
    
    # GTIN features
    gtin_a = str(a.get("gtin", "")).strip().upper()
    gtin_b = str(b.get("gtin", "")).strip().upper()
    
    # Check if GTINs are valid (non-empty and not placeholder values)
    gtin_a_valid = gtin_a and gtin_a not in ['NAN', 'NONE', '', '0']
    gtin_b_valid = gtin_b and gtin_b not in ['NAN', 'NONE', '', '0']
    
    # GTIN exact match (both must have valid GTINs)
    gtin_exact = 1.0 if (gtin_a_valid and gtin_b_valid and gtin_a == gtin_b) else 0.0
    
    # GTIN available flag (at least one has a GTIN)
    gtin_available = 1.0 if (gtin_a_valid or gtin_b_valid) else 0.0
    
    # GTIN mismatch flag (both have GTINs but they don't match - strong negative signal)
    gtin_mismatch = 1.0 if (gtin_a_valid and gtin_b_valid and gtin_a != gtin_b) else 0.0
    
    
    # Generate part number variants with manufacturer context
    # Extract and normalize manufacturer names
    mfr_a = normalize_manufacturer(a.get("manufacturer", ""))
    mfr_b = normalize_manufacturer(b.get("manufacturer", ""))
    pna = [v for v in pn_variants(a.get("part_number",""), mfr_a) if v]
    pnb = [v for v in pn_variants(b.get("part_number",""), mfr_b) if v]
    
    # Filter short variants if enabled (adaptive threshold based on original PN length)
    pn_a_orig = str(a.get("part_number", ""))
    pn_b_orig = str(b.get("part_number", ""))
    
    if filter_short_variants:
        pna = [v for v in pna if not is_short_variant(pn_a_orig, v)]
        pnb = [v for v in pnb if not is_short_variant(pn_b_orig, v)]
    
    # Find matching variants and calculate weighted score
    matching_variants = list(set(pna) & set(pnb))
    pn_exact_any = 1.0 if matching_variants else 0.0
    pn_match_weight = calculate_pn_match_weight(pn_a_orig, pn_b_orig, matching_variants)
    best_edit, best_jw, pn_common_prefix, pn_common_suffix = 1.0, 0.0, 0, 0
    suffix_only_match = 0.0  # NEW: Track suffix-only differences
    if pna and pnb:
        best_edit = 1e9
        for x in pna:
            for y in pnb:
                # Standard metrics (existing logic)
                d = levenshtein(x,y); best_edit = min(best_edit, d)
                jw = jaro_winkler(x,y); best_jw = max(best_jw, jw)
                
                # NEW: Check for suffix-only differences
                if _is_suffix_only_difference(x, y):
                    suffix_only_match = 0.9  # High confidence for suffix-only differences
                    # Boost other scores since it's just a suffix difference
                    if d <= 5:  # Allow for suffix length
                        best_edit = min(best_edit, 0)
                        jw = max(jw, 0.95)
                
                cp = 0
                for i in range(min(len(x), len(y))):
                    if x[i] == y[i]: cp += 1
                    else: break
                cs = 0
                for i in range(1, min(len(x), len(y))+1):
                    if x[-i] == y[-i]: cs += 1
                    else: break
                pn_common_prefix = max(pn_common_prefix, cp)
                pn_common_suffix = max(pn_common_suffix, cs)
    text_a = (a.get("title","")+" "+a.get("description","")).lower()
    text_b = (b.get("title","")+" "+b.get("description","")).lower()
    tri_a = char_trigram_set(text_a); tri_b = char_trigram_set(text_b)
    text_jacc = jaccard(tri_a, tri_b)
    
    # Handle empty text or text with only stop words
    text_tfidf_cos = 0.0
    if text_a.strip() and text_b.strip():
        try:
            vect = TfidfVectorizer(ngram_range=(1,2), min_df=1)
            m = vect.fit_transform([text_a, text_b])
            text_tfidf_cos = float(cosine_similarity(m[0], m[1])[0][0])
        except ValueError:
            # Empty vocabulary (only stop words or empty text)
            # Fall back to 0.0 similarity
            text_tfidf_cos = 0.0
            
    import re
    nums_a = set(re.findall(r"\b\d+(?:\.\d+)?\b", text_a))
    nums_b = set(re.findall(r"\b\d+(?:\.\d+)?\b", text_b))
    units = ["mm","cm","m","inch","in","gb","tb","mb","ghz","mhz","w","kw","v","ma"]
    units_a = {u for u in units if re.search(rf"\b{re.escape(u)}\b", text_a)}
    units_b = {u for u in units if re.search(rf"\b{re.escape(u)}\b", text_b)}
    number_overlap = len(nums_a & nums_b); unit_overlap = len(units_a & units_b)
    # Combine all features
    features = {
        # Enhanced manufacturer features
        **mfr_features,
        # UNSPSC features (replacing brand features)
        "unspsc_exact": float(unspsc_exact),
        "unspsc_segment_match": float(unspsc_segment_match),
        "unspsc_family_match": float(unspsc_family_match),
        "unspsc_class_match": float(unspsc_class_match),
        # GTIN features
        "gtin_exact": float(gtin_exact),
        "gtin_available": float(gtin_available),
        "gtin_mismatch": float(gtin_mismatch),
        # Part number features
        "pn_exact_any": float(pn_exact_any), "pn_edit": float(best_edit), "pn_jw": float(best_jw),
        "pn_common_prefix": float(pn_common_prefix), "pn_common_suffix": float(pn_common_suffix),
        "pn_suffix_only_match": float(suffix_only_match),
        "pn_match_weight": float(pn_match_weight),  # NEW: Weighted score based on variant quality
        # Text features
        "text_jacc": float(text_jacc), "text_tfidf_cos": float(text_tfidf_cos),
        "number_overlap": float(number_overlap), "unit_overlap": float(unit_overlap),
    }

    return features

def  train_baseline(X, y):
    model = Pipeline([("scaler", StandardScaler(with_mean=False)),
                      ("clf", GradientBoostingClassifier(random_state=42))])
    model.fit(X, y)
    return model

# Blocking utilities (simplified, using exact/near PN and name fuzzy)
class BKTree:
    def __init__(self, distance_fn=None):
        self.distance_fn = distance_fn or levenshtein
        self.tree = None
    class Node:
        def __init__(self, term):
            self.term = term; self.children = {}
    def add(self, term):
        if self.tree is None:
            self.tree = self.Node(term); return
        node = self.tree
        d = self.distance_fn(term, node.term)
        while d in node.children:
            node = node.children[d]
            d = self.distance_fn(term, node.term)
        node.children[d] = self.Node(term)
    def search(self, term, max_dist):
        res = []
        if self.tree is None: return res
        nodes = [self.tree]
        while nodes:
            n = nodes.pop()
            d = self.distance_fn(term, n.term)
            if d <= max_dist: res.append((n.term, d))
            lo, hi = d - max_dist, d + max_dist
            for cd, child in n.children.items():
                if lo <= cd <= hi: nodes.append(child)
        return res

def extract_tokens(s: str) -> set:
    import re
    return set(re.findall(r"[A-Za-z0-9\+\-_/\.]{2,}", s or ""))

def rare_tokens(texts, min_df=1, max_df_ratio=0.15):
    df = {}; n = len(texts)
    import re, math
    for t in texts:
        toks = set(re.findall(r"[A-Za-z0-9\+\-_/\.]{2,}", t or ""))
        for tok in toks:
            df[tok] = df.get(tok, 0) + 1
    rarity = {}
    for tok, c in df.items():
        if c >= min_df and c <= max(1, int(max_df_ratio * n)):
            rarity[tok] = math.log((n+1)/(c+1)) + 1.0
    return rarity

def generate_candidates(df_a, df_b, jw_mfr=0.90, pn_max_edit=1, max_cands_per_item=200, alias_manager=None):
    df_a = df_a.copy(); df_b = df_b.copy()
    for df in (df_a, df_b):
        df["mfr_norm"] = df["manufacturer"].apply(normalize_manufacturer)
        df["unspsc_clean"] = df["unspsc"].apply(normalize_unspsc)
        # Use df.apply to pass both part_number and manufacturer to pn_variants
        df["pn_variants"] = df.apply(
            lambda row: pn_variants(row["part_number"], row.get("mfr_norm", None)),
            axis=1
        )
        df["text_all"] = (df["title"].fillna("").astype(str) + " " + df["description"].fillna("").astype(str)).str.lower()
    # exact indexes
    mfr_to_b, unspsc_to_b, unspsc_segment_to_b, unspsc_family_to_b, unspsc_class_to_b = {}, {}, {}, {}, {}
    for idx, row in df_b.iterrows():
        if row["mfr_norm"]: 
            mfr_to_b.setdefault(row["mfr_norm"], []).append(idx)
            # Add alias-based indexing if alias manager is available
            if alias_manager:
                canonical = alias_manager.get_canonical_name(row["manufacturer"])
                if canonical and canonical != row["mfr_norm"]:
                    mfr_to_b.setdefault(canonical, []).append(idx)
                # Also index all aliases
                aliases = alias_manager.get_all_aliases_for_name(row["manufacturer"])
                for alias in aliases:
                    if alias != row["mfr_norm"]:
                        mfr_to_b.setdefault(alias, []).append(idx)
        
        # UNSPSC indexing with hierarchical levels
        if row["unspsc_clean"] and len(row["unspsc_clean"]) == 8:
            unspsc_to_b.setdefault(row["unspsc_clean"], []).append(idx)
            unspsc_segment_to_b.setdefault(row["unspsc_clean"][:2], []).append(idx)
            unspsc_family_to_b.setdefault(row["unspsc_clean"][:4], []).append(idx)
            unspsc_class_to_b.setdefault(row["unspsc_clean"][:6], []).append(idx)
    
    # GTIN index
    gtin_to_b = {}
    for idx, row in df_b.iterrows():
        gtin = str(row.get('gtin', '')).strip().upper()
        if gtin and gtin not in ['NAN', 'NONE', '', '0']:
            gtin_to_b.setdefault(gtin, []).append(idx)
    
    # PN index + BK-tree
    pn_to_bidx, bk = {}, BKTree()
    for idx, row in df_b.iterrows():
        for v in row["pn_variants"]:
            if v not in pn_to_bidx:
                pn_to_bidx[v] = []; bk.add(v)
            pn_to_bidx[v].append(idx)
    # rare tokens
    rarity = rare_tokens(df_b["text_all"].tolist(), min_df=1, max_df_ratio=0.15)
    b_token_sets = {}
    for idx, row in df_b.iterrows():
        toks = extract_tokens(row["text_all"])
        b_token_sets[idx] = {t for t in toks if t in rarity}
    a_to_candidates = {}
    for idx_a, row_a in df_a.iterrows():
        cand_scores = {}
        
        # Track which candidates matched on manufacturer and part number for synergy boost
        mfr_matched = set()
        pn_matched = set()
        
        # GTIN exact matching (highest priority)
        gtin_a = str(row_a.get('gtin', '')).strip().upper()
        if gtin_a and gtin_a not in ['NAN', 'NONE', '', '0']:
            for j in gtin_to_b.get(gtin_a, []):
                cand_scores[j] = cand_scores.get(j, 0) + 10.0  # Very high weight for GTIN match
        
        # Manufacturer matching with alias support
        if row_a["mfr_norm"]:
            # Direct manufacturer match
            for j in mfr_to_b.get(row_a["mfr_norm"], []):
                cand_scores[j] = cand_scores.get(j, 0) + 1.0
                mfr_matched.add(j)
            
            # Alias-based manufacturer matching
            if alias_manager:
                canonical_a = alias_manager.get_canonical_name(row_a["manufacturer"])
                if canonical_a and canonical_a != row_a["mfr_norm"]:
                    for j in mfr_to_b.get(canonical_a, []):
                        cand_scores[j] = cand_scores.get(j, 0) + 1.0
                        mfr_matched.add(j)
                
                # Match against all aliases
                aliases_a = alias_manager.get_all_aliases_for_name(row_a["manufacturer"])
                for alias in aliases_a:
                    if alias != row_a["mfr_norm"]:
                        for j in mfr_to_b.get(alias, []):
                            cand_scores[j] = cand_scores.get(j, 0) + 0.8  # Slightly lower weight for alias matches
                            mfr_matched.add(j)
        
        # UNSPSC matching with hierarchical levels
        if row_a["unspsc_clean"] and len(row_a["unspsc_clean"]) == 8:
            # Exact UNSPSC match (highest weight)
            for j in unspsc_to_b.get(row_a["unspsc_clean"], []):
                cand_scores[j] = cand_scores.get(j, 0) + 3.0
            
            # Class-level match (very strong)
            for j in unspsc_class_to_b.get(row_a["unspsc_clean"][:6], []):
                cand_scores[j] = cand_scores.get(j, 0) + 2.0
            
            # Family-level match (strong)
            for j in unspsc_family_to_b.get(row_a["unspsc_clean"][:4], []):
                cand_scores[j] = cand_scores.get(j, 0) + 1.5
            
            # Segment-level match (moderate)
            for j in unspsc_segment_to_b.get(row_a["unspsc_clean"][:2], []):
                cand_scores[j] = cand_scores.get(j, 0) + 1.0
        for idx_b, row_b in df_b.iterrows():
            # Manufacturer Jaro-Winkler matching with alias support
            if row_a["mfr_norm"] and row_b["mfr_norm"]:
                # Direct Jaro-Winkler
                jw = jaro_winkler(row_a["mfr_norm"], row_b["mfr_norm"])
                if jw >= jw_mfr:
                    cand_scores[idx_b] = cand_scores.get(idx_b, 0) + jw
                    mfr_matched.add(idx_b)
                
                # Alias-based Jaro-Winkler matching
                if alias_manager:
                    aliases_a = alias_manager.get_all_aliases_for_name(row_a["manufacturer"])
                    aliases_b = alias_manager.get_all_aliases_for_name(row_b["manufacturer"])
                    
                    # Find best Jaro-Winkler score between any aliases
                    best_jw = 0.0
                    for alias_a in aliases_a:
                        for alias_b in aliases_b:
                            jw_alias = jaro_winkler(alias_a, alias_b)
                            best_jw = max(best_jw, jw_alias)
                    
                    if best_jw >= jw_mfr:
                        cand_scores[idx_b] = cand_scores.get(idx_b, 0) + best_jw * 0.9  # Slightly lower weight for alias matches
                        mfr_matched.add(idx_b)
            
        for v in row_a["pn_variants"]:
            if v in pn_to_bidx:
                for j in pn_to_bidx[v]:
                    cand_scores[j] = cand_scores.get(j, 0) + 3.0
                    pn_matched.add(j)
            for v2, d in bk.search(v, max_dist=pn_max_edit):
                for j in pn_to_bidx.get(v2, []):
                    cand_scores[j] = cand_scores.get(j, 0) + max(0.0, 2.0 - 0.5*d)
                    pn_matched.add(j)
        a_rare = {t for t in extract_tokens(row_a["text_all"]) if t in rarity}
        if a_rare:
            for idx_b, b_rare in b_token_sets.items():
                if a_rare & b_rare:
                    cand_scores[idx_b] = cand_scores.get(idx_b, 0) + 0.5*len(a_rare & b_rare)
        
        # Combined PN + Manufacturer match synergy boost
        # Apply additional boost to candidates that matched on BOTH dimensions
        for idx_b in (mfr_matched & pn_matched):  # Set intersection
            cand_scores[idx_b] = cand_scores.get(idx_b, 0) + 5.0  # Synergy boost for combined match
        
        if cand_scores:
            top = sorted(cand_scores.items(), key=lambda x: -x[1])[:max_cands_per_item]
            a_to_candidates[idx_a] = [j for j,_ in top]
        else:
            a_to_candidates[idx_a] = []
    return a_to_candidates

def make_training_pairs(df_a, df_b, cand_map):
    X = []; y = []
    for ia, cands in cand_map.items():
        arow = df_a.loc[ia].to_dict()
        for ib in cands:
            brow = df_b.loc[ib].to_dict()
            feats = build_pair_features(arow, brow)
            pos = (feats["pn_exact_any"] == 1.0 and (feats["unspsc_exact"] == 1.0 or feats["mfr_jw"] > 0.95)) or \
                  (feats["text_tfidf_cos"] > 0.8 and feats["unspsc_class_match"] == 1.0) or \
                  (feats["unspsc_exact"] == 1.0 and feats["mfr_jw"] > 0.8)
            X.append(feats); y.append(1 if pos else 0)
    return pd.DataFrame(X).fillna(0), pd.Series(y)
