from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('dashboard/', views.lead_dashboard, name='dashboard'),
    path('facebook/webhook/', views.facebook_webhook, name='webhook'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('facebook/connect/', views.facebook_connect, name='facebook_connect'),
    path('facebook/callback/', views.facebook_callback, name='facebook_callback'),
    path('facebook/save-page/', views.save_facebook_page, name='save_facebook_page'),
    path('connected-pages/', views.connected_pages_view, name='connected_pages'),
    path('connected-pages/disconnect/<str:page_id>/', views.disconnect_page_view, name='disconnect_page'),
    path('connected-pages/conflict/<str:page_id>/', views.page_conflict_view, name='page_conflict'),
    path('leads/<int:pk>/', views.lead_detail_view, name='lead_detail'),
    path('leads/<int:pk>/toggle-spam/', views.toggle_lead_spam, name='toggle_lead_spam'),
    path('leads/export/', views.export_clean_leads, name='export_clean_leads'),
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_service, name='terms_of_service'),
] 