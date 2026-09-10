"""Presentation and security-contract checks against pinned FastMCP renderers."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from html.parser import HTMLParser
from forit_mcp_gateway.login_branding import install_login_branding


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class LoginBrandingTests(unittest.TestCase):
    def setUp(self):
        install_login_branding(name='ForIT MCP Gateway', logo_url='https://www.forit.io/images/forit-hex-only.png')

    def test_consent_preserves_form_contract_and_escapes_untrusted_values(self):
        from fastmcp.server.auth.oauth_proxy.consent import create_consent_html
        html = create_consent_html('client', 'https://client.example/cb?x=1&y=2', ['tools.read'], 'tx"<', 'csrf"<', client_name='<script>alert(1)</script>')
        tags = Elements(html).tags
        self.assertEqual([a for t, a in tags if t == 'form'], [{'id':'consentForm', 'method':'POST', 'action':''}])
        self.assertEqual({a['name']:a['value'] for t,a in tags if t=='input'}, {'txn_id':'tx"<', 'csrf_token':'csrf"<', 'submit':'true'})
        self.assertEqual({a['value'] for t,a in tags if t=='button'}, {'approve','deny'})
        self.assertNotIn('script', [t for t,a in tags])
        self.assertIn('https://client.example/cb?x=1&amp;y=2', html)
        self.assertIn('tools.read', html)
        self.assertIn('Continue with Microsoft', html)
        self.assertIn('#142F43', html)
        self.assertIn('#0A1A26', html)
        self.assertNotIn('FastMCP', html)
        self.assertNotIn('gofastmcp.com', html)
        self.assertIn('help@forit.io', html)

    def test_error_and_expired_transaction_share_brand_and_keep_security_headers(self):
        from fastmcp.server.auth.oauth_proxy.proxy import create_error_html
        from fastmcp.server.auth.oauth_proxy.consent import create_secure_html_response
        html = create_error_html('Sign-in failed', '<bad>', {'Reason':'<unsafe>'})
        self.assertIn('&lt;bad&gt;', html)
        self.assertIn('&lt;unsafe&gt;', html)
        self.assertIn('data:image/png;base64,', html)
        self.assertNotIn('FastMCP', html)
        response = create_secure_html_response('<h1>Error</h1><p>Invalid or expired transaction</p>', 400)
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.headers['x-frame-options'],'DENY')
        self.assertIn(b'Invalid or expired transaction',response.body)
        self.assertIn(b'ForIT MCP Gateway',response.body)

    def test_csp_custom_and_default_contract(self):
        from fastmcp.server.auth.oauth_proxy.consent import create_consent_html
        for policy in (None, '', "default-src 'none'"):
            html = create_consent_html('c','https://client.example/cb',[],'t','s',csp_policy=policy)
            csp = [a for t,a in Elements(html).tags if t=='meta' and a.get('http-equiv')=='Content-Security-Policy']
            if policy == '': self.assertEqual(csp,[])
            elif policy is None: self.assertIn("base-uri 'none'", csp[0]['content'])
            else: self.assertEqual(csp[0]['content'],policy)

    def test_configured_tenant_and_unregistered_error_do_not_fall_back(self):
        install_login_branding(name='Example Gateway',logo_url='https://example.org/logo.png',support_email='help@example.org')
        from fastmcp.server.auth.handlers.authorize import create_unregistered_client_html
        html=create_unregistered_client_html('<bad>','https://example.org/register','https://example.org/discovery')
        self.assertIn('Example Gateway',html)
        self.assertIn('help@example.org',html)
        self.assertNotIn('help@forit.io',html)
        self.assertNotIn('FastMCP',html)
        self.assertIn('&lt;bad&gt;',html)

    def test_real_oauth_flow_keeps_csrf_and_consent_enforcement(self):
        from fastmcp import FastMCP
        from fastmcp.server.auth import OAuthProxy
        from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
        from starlette.testclient import TestClient
        provider=OAuthProxy(
            upstream_authorization_endpoint='https://login.microsoftonline.com/example/oauth2/v2.0/authorize',
            upstream_token_endpoint='https://login.microsoftonline.com/example/oauth2/v2.0/token',
            upstream_client_id='example-upstream', token_verifier=StaticTokenVerifier(tokens={}),
            base_url='https://gateway.example.org', allowed_client_redirect_uris=['https://client.example/callback'],
            jwt_signing_key='test-only-signing-key-not-a-live-credential',
        )
        app=FastMCP('ForIT MCP Gateway',auth=provider).http_app()
        with TestClient(app,base_url='https://gateway.example.org',follow_redirects=False) as client:
            registration=client.post('/register',json={'redirect_uris':['https://client.example/callback'],'client_name':'Test Desktop','grant_types':['authorization_code','refresh_token'],'response_types':['code'],'token_endpoint_auth_method':'none'})
            self.assertEqual(registration.status_code,201,registration.text)
            auth=client.get('/authorize',params={'client_id':registration.json()['client_id'],'redirect_uri':'https://client.example/callback','response_type':'code','state':'caller-state','code_challenge':'a'*43,'code_challenge_method':'S256'})
            self.assertIn(auth.status_code,(302,303,307),auth.text)
            screen=client.get(auth.headers['location'])
            self.assertEqual(screen.status_code,200,screen.text)
            fields={a['name']:a['value'] for t,a in Elements(screen.text).tags if t=='input'}
            rejected=client.post('/consent',data={**fields,'csrf_token':'wrong','action':'approve'})
            self.assertEqual(rejected.status_code,400,rejected.text)
            self.assertIn('ForIT MCP Gateway',rejected.text)
            approved=client.post('/consent',data={**fields,'action':'approve'})
            self.assertIn(approved.status_code,(302,303,307),approved.text)
            self.assertTrue(approved.headers['location'].startswith('https://login.microsoftonline.com/'))


if __name__ == '__main__': unittest.main()
