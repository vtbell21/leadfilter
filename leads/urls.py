from django.urls import path
from . import views
from . import views_pipedrive
from leads.views_stripe import create_checkout_session, subscription_success, subscription_cancel
from leads.views_hubspot import hubspot_connect, hubspot_callback, hubspot_connected_success, hubspot_disconnect
from leads.views import integrations_view
from django.contrib.auth import views as auth_views

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
    path('facebook/select-page/', views.select_facebook_page, name='select_facebook_page'),
    path('facebook/save-page/', views.save_facebook_page, name='save_facebook_page'),
    path('connected-pages/', views.connected_pages_view, name='connected_pages'),
    path('connected-pages/disconnect/<str:page_id>/', views.disconnect_page_view, name='disconnect_page'),
    path('connected-pages/conflict/<str:page_id>/', views.handle_page_conflict, name='page_conflict'),
    path('leads/<int:pk>/', views.lead_detail_view, name='lead_detail'),
    path('leads/<int:pk>/toggle-spam/', views.toggle_lead_spam, name='toggle_lead_spam'),
    path('leads/export/', views.export_clean_leads, name='export_clean_leads'),
    path('privacy/', views.privacy_policy, name='privacy_policy'),
    path('terms/', views.terms_of_service, name='terms_of_service'),
    path('about/', views.about_view, name='about'),
    path('create-checkout-session/', create_checkout_session, name='create_checkout_session'),
    path('subscription/success/', subscription_success, name='subscription_success'),
    path('subscription/cancel/', subscription_cancel, name='subscription_cancel'),
    path('pricing/', views.pricing_view, name='pricing'),
    path('hubspot/connect/', hubspot_connect, name='hubspot_connect'),
    path('hubspot/callback/', hubspot_callback, name='hubspot_callback'),
    path('hubspot/connected/', hubspot_connected_success, name='hubspot_connected_success'),
    path('hubspot/disconnect/', hubspot_disconnect, name='hubspot_disconnect'),
    path('integrations/', integrations_view, name='integrations'),
    path('gmail/callback/', views.gmail_callback, name='gmail_callback'),
    path('gmail/oauth/start/', views.gmail_oauth_start, name='gmail_oauth_start'),
    path('gmail/oauth/callback/', views.gmail_oauth_callback, name='gmail_oauth_callback'),
    path('settings/lead-routing/', views.lead_routing_settings_view, name='lead_routing_settings'),
    path('settings/email/', views.update_email_view, name='update_email'),
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='leads/password_reset_form.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='leads/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='leads/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='leads/password_reset_complete.html'), name='password_reset_complete'),
    path('settings/webhook/', views.webhook_settings_view, name='webhook_settings'),
    path('settings/webhook/test/', views.test_webhook, name='test_webhook'),
    path('validate-phone/', views.validate_phone_view, name='validate_phone'),
    path('pipedrive/connect/', views_pipedrive.pipedrive_connect, name='pipedrive_connect'),
    path('pipedrive/callback/', views_pipedrive.pipedrive_callback, name='pipedrive_callback'),
    path('pipedrive/disconnect/', views_pipedrive.pipedrive_disconnect, name='pipedrive_disconnect'),
] 