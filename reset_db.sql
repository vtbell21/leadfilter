DROP TABLE IF EXISTS leads_facebooklead CASCADE;
DROP TABLE IF EXISTS leads_facebookpageconnection CASCADE;
DROP TABLE IF EXISTS leads_gmailcredentials CASCADE;
DROP TABLE IF EXISTS leads_leadroutingsettings CASCADE;
DROP TABLE IF EXISTS leads_userprofile CASCADE;
DROP TABLE IF EXISTS leads_webhooksettings CASCADE;
DELETE FROM django_migrations WHERE app = 'leads'; 