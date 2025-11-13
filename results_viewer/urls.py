"""
URL configuration for results_viewer app.
"""
from django.urls import path
from . import views
from .compare_api import product_compare_api, product_compare_scalable_api, product_compare_any_api

urlpatterns = [
    path('', views.index, name='index'),
    path('results/<str:results_name>/', views.results_detail, name='results_detail'),
    path('api/results/<str:results_name>/pair-scores/', views.pair_scores_api, name='pair_scores_api'),
    path('api/results/<str:results_name>/products/<str:product_id>/', views.product_detail_api, name='product_detail_api'),
    path('api/results/<str:results_name>/golden-records/', views.golden_records_api, name='golden_records_api'),
    path('api/results/<str:results_name>/compare/<str:product_a_id>/<str:product_b_id>/', product_compare_api, name='product_compare_api'),
    path('api/results/<str:results_name>/compare-scalable/<str:qbi_id>/<str:product_a_id>/<str:product_b_id>/', product_compare_scalable_api, name='product_compare_scalable_api'),
    path('api/results/<str:results_name>/compare-any/<str:product_a_id>/<str:product_b_id>/', product_compare_any_api, name='product_compare_any_api'),
]
