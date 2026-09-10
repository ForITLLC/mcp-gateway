"""For-Common pre-login presentation for FastMCP 3.2.3's Python UI.

Mirrors UnifiedSignInScreen (navy/dark gradient, centered mark, translucent
card, white provider button, support footer). Only HTML renderers are replaced;
FastMCP retains transaction, CSRF, consent, redirect and token handling.
"""
from html import escape
from pathlib import Path
import base64

_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src https: data:; base-uri 'none'"
_STYLE = """
*{box-sizing:border-box}body{margin:0;min-height:100vh;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:linear-gradient(135deg,#142F43 0%,#0A1A26 100%);color:#fff}
main{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px 16px}.shell{width:100%;max-width:440px;text-align:center}.brand-logo{display:block;height:48px;width:auto;max-width:220px;object-fit:contain;margin:0 auto 24px}.brand-title{font-size:24px;font-weight:600;margin:0}.tagline{font-size:14px;line-height:1.5;color:rgba(255,255,255,.8);margin:6px 0 0}
.card{margin-top:32px;padding:24px;border-radius:16px;background:rgba(0,0,0,.2);text-align:left}.card h1,.card h2{font-size:18px;font-weight:600;margin:0 0 16px;color:#fff}.card p{font-size:14px;line-height:1.6;margin:0 0 16px}.card strong{color:#fff}.callback{border:1px solid rgba(142,220,239,.35);border-radius:8px;background:rgba(142,220,239,.08);padding:12px;margin:20px 0}.label{display:block;font-size:12px;color:rgba(255,255,255,.75);margin-bottom:6px}.value,.detail-value{overflow-wrap:anywhere;font-size:13px;line-height:1.5}.button-group{display:flex;flex-direction:column;gap:10px;margin-top:24px}button{display:inline-flex;align-items:center;justify-content:center;gap:12px;width:100%;border-radius:8px;border:1px solid transparent;padding:12px 20px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;transition:background .15s}.btn-approve{background:#fff;color:#171717}.btn-approve:hover{background:#e8f5f8}.btn-deny{background:transparent;border-color:rgba(255,255,255,.3);color:#fff}.btn-deny:hover{background:rgba(255,255,255,.1)}a{color:inherit}a:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid #8EDCEF;outline-offset:4px}details{font-size:13px;margin-top:16px}summary{cursor:pointer;color:rgba(255,255,255,.85);padding:4px 0}.detail-row{margin-top:12px}.detail-label{font-size:12px;color:rgba(255,255,255,.7);margin-bottom:3px}.error{border:1px solid rgba(252,165,165,.4);border-radius:8px;background:rgba(239,68,68,.15);padding:14px}.error p:last-child{margin-bottom:0}.support{font-size:12px;color:rgba(255,255,255,.7);margin:32px 0 0}.support a:hover{color:#fff}.badge{font-size:12px;color:#a7f3d0;margin:12px 0}.container{padding:0;margin:0;border:0;background:none;text-align:left;max-width:none}.container>.logo{display:none}.info-box,.warning-box{font-size:14px;line-height:1.6}.help-link-container{display:none}code{overflow-wrap:anywhere}@media(max-width:480px){main{padding:32px 16px}.card{padding:20px}}
"""
_MICROSOFT = '<svg aria-hidden="true" width="20" height="20" viewBox="0 0 21 21"><path fill="#f25022" d="M1 1h9v9H1z"/><path fill="#7fba00" d="M11 1h9v9h-9z"/><path fill="#00a4ef" d="M1 11h9v9H1z"/><path fill="#ffb900" d="M11 11h9v9h-9z"/></svg>'


def install_login_branding(*, name: str, logo_url: str, support_email: str = "help@forit.io") -> None:
    """Install once per gateway process before serving requests.

    Each tenant process supplies its own name/logo. The default ForIT navy
    mark uses the same white asset as for-Common to remain legible on navy.
    No remote CSS, fonts, JavaScript or additional authentication calls.
    """
    from fastmcp.utilities import ui
    from fastmcp.server.auth.oauth_proxy import ui as oauth_ui, consent, proxy
    from fastmcp.server.auth.handlers import authorize

    if logo_url == "https://www.forit.io/images/forit-hex-only.png":
        mark = Path(__file__).with_name("assets") / "forit-mark-white.png"
        logo_url = "data:image/png;base64," + base64.b64encode(mark.read_bytes()).decode()
    if not (logo_url.startswith("https://") or logo_url.startswith("data:image/png;base64,")):
        raise ValueError("Login logo must be HTTPS or an embedded PNG")
    if any(c in support_email for c in '\r\n?&#'):
        raise ValueError("Invalid support email")
    brand = escape(name)
    logo = escape(logo_url, quote=True)
    support = escape(support_email, quote=True)

    def page(content: str, title: str = "Sign in", additional_styles: str = "", csp_policy: str = _CSP) -> str:
        # Our stylesheet owns the full presentation. Upstream callers' style
        # strings are intentionally not appended over these shared tokens.
        csp = f'<meta http-equiv="Content-Security-Policy" content="{escape(csp_policy, quote=True)}">' if csp_policy else ''
        footer = f'<p class="support">Need help? <a href="mailto:{support}">{support}</a></p>' if support else ''
        return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">{csp}<title>{escape(title)} · {brand}</title><style>{_STYLE}</style></head><body><main><div class="shell"><img class="brand-logo" src="{logo}" alt="{brand}"><h1 class="brand-title">{brand}</h1><p class="tagline">Secure access to your connected tools.</p><section class="card" aria-label="{escape(title, quote=True)}">{content}</section>{footer}</div></main></body></html>'''

    def details(rows: list[tuple[str, str]], title: str = "Connection details") -> str:
        items = ''.join(f'<div class="detail-row"><div class="detail-label">{escape(k)}</div><div class="detail-value">{escape(v)}</div></div>' for k, v in rows)
        return f'<details><summary>{escape(title)}</summary>{items}</details>'

    def consent_html(client_id: str, redirect_uri: str, scopes: list[str], txn_id: str, csrf_token: str,
                     client_name: str | None = None, title: str = "Application Access Request",
                     server_name: str | None = None, server_icon_url: str | None = None,
                     server_website_url: str | None = None, client_website_url: str | None = None,
                     csp_policy: str | None = None, is_cimd_client: bool = False,
                     cimd_domain: str | None = None) -> str:
        client = escape(client_name or client_id)
        badge = f'<p class="badge">Verified domain: {escape(cimd_domain)}</p>' if is_cimd_client and cimd_domain else ''
        fields = ''.join(f'<input type="hidden" name="{k}" value="{escape(v, quote=True)}">' for k, v in [('txn_id', txn_id), ('csrf_token', csrf_token), ('submit', 'true')])
        info = details([('Application', client_name or client_id), ('Application ID', client_id), ('Application website', client_website_url or 'Not provided'), ('Requested permissions', ', '.join(scopes) if scopes else 'None')])
        content = f'''<h2>Connect {client}</h2><p>This application is requesting access to {brand}. Continue only if you recognize it and the return address below.</p>{badge}<div class="callback"><span class="label">After sign-in, authorization returns to</span><div class="value">{escape(redirect_uri)}</div></div>{info}<form id="consentForm" method="POST" action="">{fields}<div class="button-group"><button type="submit" name="action" value="approve" class="btn-approve">{_MICROSOFT}Continue with Microsoft</button><button type="submit" name="action" value="deny" class="btn-deny">Cancel</button></div></form>'''
        return page(content, "Sign in", csp_policy=_CSP if csp_policy is None else csp_policy)

    def error_html(error_title: str, error_message: str, error_details: dict[str, str] | None = None,
                   server_name: str | None = None, server_icon_url: str | None = None) -> str:
        extra = details(list(error_details.items()), 'Error details') if error_details else ''
        return page(f'<h2>{escape(error_title)}</h2><div class="error" role="alert"><p>{escape(error_message)}</p></div>{extra}', error_title)

    def unregistered_html(client_id: str, registration_endpoint: str, discovery_endpoint: str,
                          server_name: str | None = None, server_icon_url: str | None = None,
                          title: str = "Client Not Registered") -> str:
        return error_html('Reconnect your application', 'This connection is no longer registered. Close this window and reconnect the application to start a new sign-in.', {'Application ID': client_id})

    # FastMCP imports renderer functions into these modules at import time.
    # Patch those exact bindings, never handlers or identity validation.
    ui.FASTMCP_LOGO_URL = logo_url
    ui.create_page = oauth_ui.create_page = authorize.create_page = page
    oauth_ui.create_consent_html = consent.create_consent_html = consent_html
    oauth_ui.create_error_html = proxy.create_error_html = error_html
    authorize.create_unregistered_client_html = unregistered_html
    # Missing/expired transactions and CSRF failures use fragment responses.
    # Retain the original status and clickjacking header when branding them.
    from starlette.responses import HTMLResponse
    def secure_response(html: str, status_code: int = 200):
        if '<html' not in html.lower():
            html = page(f'<div class="error" role="alert">{html}</div>', 'Unable to sign in')
        return HTMLResponse(html, status_code=status_code, headers={"X-Frame-Options": "DENY"})
    ui.create_secure_html_response = consent.create_secure_html_response = authorize.create_secure_html_response = secure_response
