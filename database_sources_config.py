"""
Configuration for database sources (PostgreSQL and SQLite).

This file defines database connections that will appear as cards on the
Results Dashboard, alongside directory-based results.

Database sources are refreshed in real-time on each page load.
"""

import os

# PostgreSQL Database Sources
# These will appear with 'pgsql_' prefix in URLs
POSTGRESQL_SOURCES = [
    #  {
    #     'name': 'pgsql_vpp_data_with_id_80',
    #     'display_name': 'PostgreSQL - VPP Data 80',
    #     'description': 'VPP data with ID threshold 80',
    #     'connection_string': os.environ.get(
    #         'PGSQL_VPP_DATA_WITH_ID_80_CONNECTION',
    #         'postgresql://localhost/per_vpp_with_id_80'
    #     ),
    #     'enabled': True,
    #     'type': 'postgresql'
    # },
    # {
    #     'name': 'pgsql_main',
    #     'display_name': 'PostgreSQL - Main Database',
    #     'description': 'Production distributed entity resolution database',
    #     'connection_string': os.environ.get(
    #         'PGSQL_MAIN_CONNECTION',
    #         'postgresql://localhost/product_entity_resolution'
    #     ),
    #     'enabled': True,
    #     'type': 'postgresql'
    # },
    # {
    #     'name': 'pgsql_test',
    #     'display_name': 'PostgreSQL - Test Database',
    #     'description': 'Test database for development and validation',
    #     'connection_string': os.environ.get(
    #         'PGSQL_TEST_CONNECTION',
    #         'postgresql://localhost/product_entity_resolution_test'
    #     ),
    #     'enabled': True,
    #     'type': 'postgresql'
    # },
    # {
    #     'name': 'per_test_4',
    #     'display_name': 'PostgreSQL - Test Database 4',
    #     'description': 'Test run with new table name, pers_product_staging',
    #     'connection_string': os.environ.get(
    #         'PER_TEST_4',
    #         'postgresql://localhost/per_test_4'
    #     ),
    #     'enabled': True,
    #     'type': 'postgresql'
    # },
    # {
    #     'name': 'pgsql_optimized_v2_50K',
    #     'display_name': 'PostgreSQL - Optimized Database 50K',
    #     'description': 'Test run without partitioned tables',
    #     'connection_string': os.environ.get(
    #         'PGSQL_OPTIMIZED_V2_50K_CONNECTION',
    #         'postgresql://localhost/per_test_optimized_50k'
    #     ),
        
    #     'enabled': True,
    #     'type': 'postgresql'
    # },
    # {
    #     'name': 'pgsql_optimized_v2_100K',
    #     'display_name': 'PostgreSQL - Optimized Database 100K',
    #     'description': 'Test run without partitioned tables',
    #     'connection_string': os.environ.get(
    #         'PGSQL_OPTIMIZED_V2_100K_CONNECTION',
    #         'postgresql://localhost/per_test_optimized_100k'
    #     ),
        
    #     'enabled': True,
    #     'type': 'postgresql'
    # },
    {
        'name': 'adv_data',
        'display_name': 'Advantage Data - Cummulative',
        'description': 'Production distributed entity resolution database',
        'connection_string': os.environ.get(
            'PGSQL_ADV_DATA',
            'postgresql://localhost/adv_data'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
    {
        'name': 'adv_test_0',
        'display_name': 'Advantage Data - Type 0',
        'description': 'Production distributed entity resolution database',
        'connection_string': os.environ.get(
            'PGSQL_ADV_TEST_0',
            'postgresql://localhost/adv_test_0'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
     {
        'name': 'adv_test_1',
        'display_name': 'Advantage Data - Type 1',
        'description': 'Production distributed entity resolution database',
        'connection_string': os.environ.get(
            'PGSQL_ADV_TEST_1',
            'postgresql://localhost/adv_test_1'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
      {
        'name': 'adv_test_2',
        'display_name': 'Advantage Data - Type 2',
        'description': 'Production distributed entity resolution database',
        'connection_string': os.environ.get(
            'PGSQL_ADV_TEST_2',
            'postgresql://localhost/adv_test_2'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
       {
        'name': 'adv_test_3',
        'display_name': 'Advantage Data - Type 3',
        'description': 'Production distributed entity resolution database',
        'connection_string': os.environ.get(
            'PGSQL_ADV_TEST_3',
            'postgresql://localhost/adv_test_3'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
        {
        'name': 'adv_test_4',
        'display_name': 'Advantage Data - Type 4',
        'description': 'Production distributed entity resolution database',
        'connection_string': os.environ.get(
            'PGSQL_ADV_TEST_4',
            'postgresql://localhost/adv_test_4'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
         {
        'name': 'adv_test_5',
        'display_name': 'Advantage Data - Type 5',
        'description': 'Production distributed entity resolution database',
        'connection_string': os.environ.get(
            'PGSQL_ADV_TEST_5',
            'postgresql://localhost/adv_test_5'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
          {
        'name': 'adv_test_6',
        'display_name': 'Advantage Data - Type 6',
        'description': 'Production distributed entity resolution database',
        'connection_string': os.environ.get(
            'PGSQL_ADV_TEST_6',
            'postgresql://localhost/adv_test_6'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
           {
        'name': 'adv_test_7',
        'display_name': 'Advantage Data - Type 7',
        'description': 'Production distributed entity resolution database',
        'connection_string': os.environ.get(
            'PGSQL_ADV_TEST_7',
            'postgresql://localhost/adv_test_7'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
     {
        'name': 'adv_test_8',
        'display_name': 'Advantage Data - Type 8',
        'description': 'Production distributed entity resolution database',
        'connection_string': os.environ.get(
            'PGSQL_ADV_TEST_8',
            'postgresql://localhost/adv_test_8'
        ),
        'enabled': True,
        'type': 'postgresql'
    },

]

# SQLite Database Sources (optional - for custom SQLite databases)
# Note: Scalable entity resolution outputs with golden_records.db are
# automatically detected in output directories and don't need to be listed here
SQLITE_SOURCES = [
    # Example of manually configured SQLite source:
    # {
    #     'name': 'pgsql_custom_sqlite',
    #     'display_name': 'Custom SQLite Database',
    #     'description': 'Manually configured SQLite database',
    #     'connection_string': '/absolute/path/to/database.db',
    #     'enabled': False,
    #     'type': 'sqlite'
    # },
]

# Combined database sources
DATABASE_SOURCES = POSTGRESQL_SOURCES + SQLITE_SOURCES

# Connection pool settings (for PostgreSQL)
CONNECTION_POOL_SETTINGS = {
    'min_connections': 1,
    'max_connections': 10,
    'connection_timeout': 5,  # seconds
}

# Cache settings for database queries
CACHE_SETTINGS = {
    'enabled': True,
    'ttl': 60,  # Time-to-live in seconds (1 minute for real-time updates)
}

# Feature flags
FEATURES = {
    'show_pair_scores': False,  # Hide pair scores for database sources
    'real_time_updates': True,  # Refresh data on each page load
    'show_connection_status': True,  # Show database connection status on cards
}

