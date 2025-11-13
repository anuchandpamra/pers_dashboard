"""
Configuration for results directory filtering and display options.
"""

# Directory filtering patterns
INCLUDE_PATTERNS = [
    'per_output',      # Show only directories containing 'per_output'
    'scalable',        # Show only directories containing 'scalable'
    'vpp_data_with_VPP_ID'
    # Add patterns to include specific directories
    # Examples:
    # 'per_output',      # Include only directories containing 'per_output'
    # 'scalable',        # Include only directories containing 'scalable'
    # 'demo',            # Include only directories containing 'demo'
]

EXCLUDE_PATTERNS = [
    'per',
    'scalable',
    'demo',
    'vpp_data_with_vpp_id_80_1',
    'example',
    'test'
    # Add patterns to exclude specific directories
    # Examples:
    # 'test',            # Exclude directories containing 'test'
    # 'backup',          # Exclude directories containing 'backup'
    # 'old',             # Exclude directories containing 'old'
]

# Display options
DISPLAY_OPTIONS = {
    'show_scalable_results': True,      # Show scalable format results
    'show_traditional_results': True,   # Show traditional format results
    'max_results_per_page': 20,         # Maximum results to show per page
    'default_sort': 'name',             # Default sort: 'name', 'date', 'size'
}

# Directory priority (for ordering)
DIRECTORY_PRIORITY = [
    'per_output_all',       # Highest priority
    'per_output_original',  # Second priority
    'per_output_similar',   # Third priority
    'per_output_not_sure',  # Fourth priority
    'per_output_different', # Fifth priority
    'vpp_data',
    'vpp_data_80',
    'scalable_results',     # Sixth priority
    'demo_output',          # Seventh priority
    'example_output',       # Eighth priority
    'test_output',          # Lowest priority
]
