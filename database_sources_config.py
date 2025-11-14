"""
Configuration for database sources (PostgreSQL and SQLite).

This file defines database connections that will appear as cards on the
Results Dashboard, alongside directory-based results.

Database sources are refreshed in real-time on each page load.
"""

import os


def build_pg_connection_string(db_name, fallback='postgresql://localhost/{db_name}'):
    """
    Build a PostgreSQL connection string from environment variables.
    
    Uses PG_USER and PG_HOST environment variables (required).
    PG_PWD is optional - if not provided, connection string will omit password.
    PG_PORT is optional - if not provided, defaults to 5432 (not included in connection string).
    If any required component is missing, falls back to the provided fallback string.
    
    Args:
        db_name: Name of the database
        fallback: Fallback connection string (supports {db_name} placeholder)
    
    Returns:
        PostgreSQL connection string
    """
    # Try to build from components
    user = os.environ.get('PG_USER')
    pwd = os.environ.get('PG_PWD')
    host = os.environ.get('PG_HOST')
    port = os.environ.get('PG_PORT') or '5432'  # Default to 5432 if not set
    
    # If any required component is missing, use fallback
    if not all([user, host]):
        return fallback.format(db_name=db_name) if '{db_name}' in fallback else fallback
    
    # Include password only if provided
    auth_part = f"{user}:{pwd}@" if pwd else f"{user}@"
    # Include port only if it's not the default 5432
    port_part = f":{port}" if port != '5432' else ""
    return f"postgresql://{auth_part}{host}{port_part}/{db_name}"


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
        'connection_string': build_pg_connection_string(
            'adv_data',
            fallback='postgresql://localhost/adv_data'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
    {
        'name': 'adv_test_0',
        'display_name': 'Advantage Data - Type 0',
        'description': 'Production distributed entity resolution database',
        'connection_string': build_pg_connection_string(
            'adv_test_0',
            fallback='postgresql://localhost/adv_test_0'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
     {
        'name': 'adv_test_1',
        'display_name': 'Advantage Data - Type 1',
        'description': 'Production distributed entity resolution database',
        'connection_string': build_pg_connection_string(
            'adv_test_1',
            fallback='postgresql://localhost/adv_test_1'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
      {
        'name': 'adv_test_2',
        'display_name': 'Advantage Data - Type 2',
        'description': 'Production distributed entity resolution database',
        'connection_string': build_pg_connection_string(
            'adv_test_2',
            fallback='postgresql://localhost/adv_test_2'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
       {
        'name': 'adv_test_3',
        'display_name': 'Advantage Data - Type 3',
        'description': 'Production distributed entity resolution database',
        'connection_string': build_pg_connection_string(
            'adv_test_3',
            fallback='postgresql://localhost/adv_test_3'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
        {
        'name': 'adv_test_4',
        'display_name': 'Advantage Data - Type 4',
        'description': 'Production distributed entity resolution database',
        'connection_string': build_pg_connection_string(
            'adv_test_4',
            fallback='postgresql://localhost/adv_test_4'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
         {
        'name': 'adv_test_5',
        'display_name': 'Advantage Data - Type 5',
        'description': 'Production distributed entity resolution database',
        'connection_string': build_pg_connection_string(
            'adv_test_5',
            fallback='postgresql://localhost/adv_test_5'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
          {
        'name': 'adv_test_6',
        'display_name': 'Advantage Data - Type 6',
        'description': 'Production distributed entity resolution database',
        'connection_string': build_pg_connection_string(
            'adv_test_6',
            fallback='postgresql://localhost/adv_test_6'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
           {
        'name': 'adv_test_7',
        'display_name': 'Advantage Data - Type 7',
        'description': 'Production distributed entity resolution database',
        'connection_string': build_pg_connection_string(
            'adv_test_7',
            fallback='postgresql://localhost/adv_test_7'
        ),
        'enabled': True,
        'type': 'postgresql'
    },
     {
        'name': 'adv_test_8',
        'display_name': 'Advantage Data - Type 8',
        'description': 'Production distributed entity resolution database',
        'connection_string': build_pg_connection_string(
            'adv_test_8',
            fallback='postgresql://localhost/adv_test_8'
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

