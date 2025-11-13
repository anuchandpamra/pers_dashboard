"""
Django management command to list and filter available results directories.
"""
from django.core.management.base import BaseCommand
from results_viewer.models import results_manager


class Command(BaseCommand):
    help = 'List available results directories with filtering options'

    def add_arguments(self, parser):
        parser.add_argument(
            '--include',
            nargs='+',
            help='Include only directories containing these patterns'
        )
        parser.add_argument(
            '--exclude',
            nargs='+',
            help='Exclude directories containing these patterns'
        )
        parser.add_argument(
            '--show-all',
            action='store_true',
            help='Show all directories (ignore config filters)'
        )

    def handle(self, *args, **options):
        include_patterns = options.get('include')
        exclude_patterns = options.get('exclude')
        
        if options['show_all']:
            include_patterns = None
            exclude_patterns = None
        
        results = results_manager.get_available_results(
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns
        )
        
        if not results:
            self.stdout.write(
                self.style.WARNING('No results directories found matching criteria')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(f'Found {len(results)} results directories:')
        )
        
        for result in results:
            self.stdout.write(f'  • {result["display_name"]} ({result["name"]})')
        
        self.stdout.write('\nTo filter directories, use:')
        self.stdout.write('  python manage.py list_results --include per_output,scalable')
        self.stdout.write('  python manage.py list_results --exclude test,demo')
        self.stdout.write('  python manage.py list_results --show-all')
