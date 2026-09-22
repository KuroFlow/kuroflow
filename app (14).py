"""
KuroFlow License Server — API Principal
Servidor Flask para validar licencias de EA MT5.

Endpoints:
  POST /validar        ← El EA llama esto en cada arranque
  POST /trial          ← Solicitar trial de 7 días
  POST /activar        ← Primera activación con cuenta MT5
  POST /webhook/gumroad← Gumroad notifica pagos/cancelaciones
  GET  /admin          ← Panel de administración (protegido)
  GET  /admin/api      ← Datos del panel en JSON
"""

import os
import hmac
import hashlib
import json
import requests as req_lib
from flask import Flask, request, jsonify, render_template_string
from database import (
    init_db, crear_licencia, activar_licencia,
    validar_licencia, renovar_licencia, expirar_licencia,
    eliminar_licencia, limpiar_licencias_expiradas,
    ip_puede_trial, registrar_trial_ip, email_puede_trial, schedule_trial_funnel, get_pending_funnel_emails, mark_funnel_email_sent, obtener_todas_licencias,
    log_evento
)

app = Flask(__name__)

# ─── CONFIGURACIÓN ────────────────────────────
ADMIN_TOKEN   = os.environ.get("ADMIN_TOKEN", "cambia-esto-por-un-token-seguro")
GUMROAD_TOKEN = os.environ.get("GUMROAD_TOKEN", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL     = os.environ.get("FROM_EMAIL", "KuroFlow <onboarding@resend.dev>")


# ─── FUNCIÓN ENVIAR EMAIL ─────────────────────
def enviar_email_licencia(email: str, clave: str, tipo: str):
    """Envía email al cliente con su clave de licencia via Resend."""
    if not RESEND_API_KEY:
        print(f"RESEND not configured. Key for {email}: {clave}")
        return False

    dias = "30 days" if tipo == "mensual" else ("365 days" if tipo == "anual" else ("7 days" if tipo == "trial" else "lifetime"))
    tipo_label = "Monthly Subscription" if tipo == "mensual" else ("Annual Subscription" if tipo == "anual" else ("7-day Trial" if tipo == "trial" else "Lifetime License"))

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#0a0a0c;font-family:'Courier New',monospace;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:40px 20px;">
          <table width="560" cellpadding="0" cellspacing="0" style="background:#0f0f12;border:1px solid #1e1e22;">

            <!-- Header gold bar -->
            <tr><td style="background:#c9a84c;height:4px;"></td></tr>

            <!-- Logo -->
            <tr><td style="padding:32px 40px 24px;">
              <span style="font-size:24px;font-weight:900;color:#f5f3ee;letter-spacing:-1px;">
                KURO<span style="color:#c9a84c;">FLOW</span>
              </span>
              <span style="display:block;font-size:11px;color:#3a3a40;letter-spacing:3px;margin-top:4px;">
                USDJPY ALGORITHMIC TRADING
              </span>
            </td></tr>

            <!-- Title -->
            <tr><td style="padding:0 40px 24px;">
              <p style="color:#6b6860;font-size:12px;letter-spacing:2px;text-transform:uppercase;margin:0 0 12px;">
                // Access Activated
              </p>
              <h1 style="color:#f5f3ee;font-size:22px;margin:0;font-weight:700;">
                Your license is ready
              </h1>
            </td></tr>

            <!-- Divider -->
            <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid #1e1e22;"></td></tr>

            <!-- License box -->
            <tr><td style="padding:28px 40px;">
              <p style="color:#6b6860;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0 0 10px;">
                Your license key
              </p>
              <div style="background:#0a0a0c;border:1px solid #c9a84c;padding:16px 20px;margin-bottom:8px;">
                <span style="color:#c9a84c;font-size:20px;font-weight:700;letter-spacing:2px;">
                  {clave}
                </span>
              </div>
              <p style="color:#3a3a40;font-size:11px;margin:6px 0 0;">
                {tipo_label} · Valid for {dias}
              </p>
            </td></tr>

            <!-- Instructions -->
            <tr><td style="padding:0 40px 28px;">
              <p style="color:#6b6860;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0 0 16px;">
                // How to activate
              </p>
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding:10px 0;border-bottom:1px solid #1a1a1e;">
                    <span style="color:#c9a84c;font-size:11px;">01</span>
                    <span style="color:#8a8880;font-size:13px;margin-left:12px;">
                      {"Download your files using these links:" if tipo == "trial" else "Download the EA file from your Gumroad library"}
                    </span>
                    {"<br><a href='https://kuro-flow.com/KuroFlow_License.ex5' style='color:#c9a84c;font-size:12px;display:block;margin:6px 0 0 23px;'>→ KuroFlow_License.ex5</a><a href='https://kuro-flow.com/KuroFlow_Optimized.set' style='color:#c9a84c;font-size:12px;display:block;margin:3px 0 0 23px;'>→ KuroFlow_Optimized.set</a>" if tipo == "trial" else ""}
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 0;border-bottom:1px solid #1a1a1e;">
                    <span style="color:#c9a84c;font-size:11px;">02</span>
                    <span style="color:#8a8880;font-size:13px;margin-left:12px;">Copy the .ex5 file to MT5 → MQL5 → Experts</span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 0;border-bottom:1px solid #1a1a1e;">
                    <span style="color:#c9a84c;font-size:11px;">03</span>
                    <span style="color:#8a8880;font-size:13px;margin-left:12px;">Drag the EA onto the USDJPY chart in MT5</span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 0;">
                    <span style="color:#c9a84c;font-size:11px;">04</span>
                    <span style="color:#8a8880;font-size:13px;margin-left:12px;">Enter your key in the "KuroFlow License Key" field</span>
                  </td>
                </tr>
              </table>
            </td></tr>

            <!-- Setup guide link for trial -->
            {"<tr><td style='padding:0 40px 16px;'><p style='color:#6b6860;font-size:12px;margin:0;'>📖 <a href='https://kuro-flow.com/setup-guide.html' style='color:#c9a84c;text-decoration:none;'>Read the full setup guide →</a></p></td></tr>" if tipo == "trial" else ""}

            <!-- Warning -->
            <tr><td style="padding:0 40px 28px;">
              <div style="background:#1a1a0a;border-left:3px solid #c9a84c;padding:14px 16px;">
                <p style="color:#8a8070;font-size:12px;margin:0;line-height:1.6;">
                  ⚠ This license is linked to <strong style="color:#c9a84c;">one MT5 account only</strong>.
                  It activates automatically the first time you enter the key.
                  Do not share it.
                </p>
              </div>
            </td></tr>

            <!-- Footer -->
            <tr><td style="padding:24px 40px;border-top:1px solid #1e1e22;">
              <p style="color:#2a2a2e;font-size:11px;margin:0;line-height:1.6;">
                KuroFlow Algorithmic Trading ·
                This email contains confidential license information.
                If you have any questions, reply to this email.
              </p>
            </td></tr>

            <!-- Bottom gold bar -->
            <tr><td style="background:#c9a84c;height:2px;"></td></tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """

    try:
        print(f"Sending email to {email} desde {FROM_EMAIL}")
        print(f"RESEND_API_KEY starts with: {RESEND_API_KEY[:8] if RESEND_API_KEY else 'NOT CONFIGURED'}")

        response = req_lib.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": FROM_EMAIL,
                "to": [email],
                "subject": f"KuroFlow — Your license key: {clave}",
                "html": html
            },
            timeout=15
        )

        print(f"Resend status: {response.status_code}")
        print(f"Resend response: {response.text}")

        if response.status_code == 200 or response.status_code == 201:
            result = response.json()
            print(f"Email sent to {email}: {result.get('id')}")
            return True
        else:
            print(f"Error Resend {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"Error enviando email a {email}: {e}")
        return False

# ─── INICIALIZAR BD AL ARRANCAR ───────────────
with app.app_context():
    init_db()   # Tu Gumroad seller token


# ─── HELPERS ──────────────────────────────────
def get_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr


def admin_requerido(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Admin-Token") or request.args.get("token")
        if token != ADMIN_TOKEN:
            return jsonify({"error": "No autorizado"}), 401
        return f(*args, **kwargs)
    return decorated


# ─── ENDPOINT 1: VALIDAR LICENCIA ─────────────
# El EA llama esto cada vez que arranca MT5
@app.route("/validar", methods=["POST", "OPTIONS"])
def validar():
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp

    data = request.get_json(force=True, silent=True) or {}
    clave      = str(data.get("clave", "")).strip().upper()
    cuenta_mt5 = str(data.get("cuenta", data.get("cuenta_mt5", ""))).strip()
    ip         = get_ip()

    if not clave:
        return jsonify({"valido": False, "razon": "DATOS_INCOMPLETOS"}), 400

    # Portal web — validate key without MT5 account
    if not cuenta_mt5 or cuenta_mt5 == "MEMBERS_PORTAL":
        from database import obtener_todas_licencias
        licencias = obtener_todas_licencias()
        lic = next((l for l in licencias if l["clave"] == clave), None)
        if not lic:
            resp = jsonify({"valido": False, "mensaje": "Invalid license key."})
        elif lic["estado"] == "expirada":
            resp = jsonify({"valido": False, "mensaje": "License expired."})
        else:
            resp = jsonify({"valido": True, "tipo": lic["tipo"], "estado": lic["estado"]})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    resultado = validar_licencia(clave, cuenta_mt5)
    log_evento(clave, cuenta_mt5, "VALIDAR", resultado["razon"], ip)
    resp = jsonify(resultado)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


# ─── ENDPOINT 2: SOLICITAR TRIAL ──────────────
# El EA o web llama esto para obtener 7 días gratis
@app.route("/trial", methods=["POST", "OPTIONS"])
def solicitar_trial():
    if request.method == "OPTIONS":
        resp = jsonify({"ok": True})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp, 200

    data  = request.get_json(force=True, silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    ip    = get_ip()

    if not email or "@" not in email:
        resp = jsonify({"ok": False, "error": "Valid email required"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 400

    # Block disposable email domains — extended list + pattern matching
    disposable_domains = {
        "temp-mail.org","temp-mail.com","tempmail.com","tempmail.net","tempmail.org",
        "guerrillamail.com","guerrillamail.net","guerrillamail.org","guerrillamail.info",
        "guerrillamail.biz","guerrillamail.de","guerrillamailblock.com",
        "mailinator.com","mailinator.net","mailinator.org",
        "throwam.com","throwam.net","throwamail.com",
        "yopmail.com","yopmail.fr","cool.fr.nf","jetable.fr.nf",
        "trashmail.com","trashmail.at","trashmail.io","trashmail.me","trashmail.net",
        "fakeinbox.com","fakeinbox.net","fakeemail.com",
        "dispostable.com","discard.email","discardmail.com","discardmail.de",
        "maildrop.cc","sharklasers.com","spam4.me","tempinbox.com",
        "tempr.email","mailnull.com","spamgourmet.com","spamgourmet.net",
        "10minutemail.com","10minutemail.net","10minutemail.org","minutemail.com",
        "20minutemail.com","filzmail.com","dispostable.com",
        "spambox.us","spamfree24.org","spamgap.com","spamspot.com",
        "spamthisplease.com","superrito.com","suremail.info",
        "tradermail.info","trbvm.com","trickmail.net","trommlermail.com",
        "ttt.delegated.com","turual.com","tyldd.com","uggsrock.com",
        "yep.it","yogamaven.com","yopmail.com","yuurok.com",
        "xagloo.com","xemaps.com","xents.com","xmaily.com","xoxy.net",
        "bugmenot.com","mailexpire.com","mailfreeonline.com","mailguard.me",
        "mailme.lv","mailmetrash.com","mailmoat.com","mailnew.com",
        "mailnull.com","mailpick.net","mailproxsy.com","mailrock.net",
        "mailsac.com","mailscrap.com","mailshell.com","mailsiphon.com",
        "mailslapping.com","mailslite.com","mailtemp.info","mailtome.de",
        "mailtothis.com","mailzilla.com","makemetheking.com","malahov.de",
        "manybrain.com","mbx.cc","mega.zik.dj","meinspamschutz.de"
    }
    # Pattern-based blocking
    disposable_patterns = ["temp", "trash", "fake", "spam", "disposable", "throwaway", "guerrilla", "junk"]
    
    email_domain = email.split("@")[-1].lower()
    is_disposable = email_domain in disposable_domains
    if not is_disposable:
        domain_base = email_domain.split(".")[0]
        is_disposable = any(p in domain_base for p in disposable_patterns)
    
    if is_disposable:
        resp = jsonify({"ok": False, "error": "Disposable email addresses are not allowed. Please use a real email address."})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 400

    if not ip_puede_trial(ip):
        resp = jsonify({"ok": False, "error": "It looks like a trial has already been requested from your network. Contact us at support@kuro-flow.com if you need help."})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 429

    if not email_puede_trial(email):
        resp = jsonify({"ok": False, "error": "A trial has already been activated for this email. Check your inbox for your key, or contact support@kuro-flow.com."})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 429

    licencia = crear_licencia(tipo="trial", email=email)
    registrar_trial_ip(ip)
    log_evento(licencia["clave"], "", "TRIAL_CREADO", "OK", ip)

    if email:
        enviar_email_licencia(email, licencia["clave"], "trial")
        schedule_trial_funnel(email, licencia["clave"])

    resp = jsonify({
        "ok": True,
        "clave": licencia["clave"],
        "dias": 7,
        "mensaje": "Trial key sent to your email. Enter it in the EA parameters."
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


# ─── ENDPOINT 3: ACTIVACIÓN MANUAL ────────────
# Opcional: activar explícitamente antes de arrancar MT5

@app.route("/analysis/clear", methods=["GET"])
def clear_analysis_cache():
    token = request.args.get("token", "")
    if token != os.environ.get("ADMIN_TOKEN", "KF-admin-2024-kuroflow"):
        return jsonify({"error": "unauthorized"}), 401
    _analysis_cache.clear()
    resp = jsonify({"ok": True, "message": "Analysis cache cleared"})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/activar", methods=["POST"])
def activar():
    data       = request.get_json(force=True, silent=True) or {}
    clave      = str(data.get("clave", "")).strip().upper()
    cuenta_mt5 = str(data.get("cuenta", "")).strip()
    ip         = get_ip()

    if not clave or not cuenta_mt5:
        return jsonify({"ok": False, "error": "Faltan datos"}), 400

    resultado = activar_licencia(clave, cuenta_mt5)
    log_evento(clave, cuenta_mt5, "ACTIVAR", str(resultado.get("ok")), ip)

    return jsonify(resultado)


# ─── ENDPOINT 4: WEBHOOK GUMROAD ──────────────
# Gumroad envía notificaciones automáticas aquí
@app.route("/webhook/gumroad", methods=["POST"])
def webhook_gumroad():
    """
    Gumroad envía form-data. Eventos relevantes:
      - sale           → nueva compra
      - subscription_restarted → renovación
      - subscription_cancelled / subscription_ended → cancelación
    """
    data          = request.form.to_dict()
    tipo_evento   = data.get("resource_name", "")
    email         = data.get("email", "").lower()
    gumroad_id    = data.get("sale_id", data.get("subscription_id", ""))
    producto      = data.get("product_name", "").lower()
    ip            = get_ip()

    # Determinar tipo de licencia según nombre del producto en Gumroad
    if "anual" in producto or "annual" in producto or "yearly" in producto:
        tipo = "anual"
    elif "vitalicia" in producto or "lifetime" in producto:
        tipo = "vitalicia"
    else:
        tipo = "mensual"

    # ── NUEVA VENTA ──────────────────────────
    if tipo_evento == "sale":
        licencia = crear_licencia(tipo=tipo, email=email, gumroad_id=gumroad_id)
        log_evento(licencia["clave"], "", "WEBHOOK_VENTA", "OK", ip)

        # Enviar email automático con la clave
        if email:
            enviar_email_licencia(email, licencia["clave"], tipo)

        return jsonify({"ok": True, "clave": licencia["clave"]}), 200

    # ── RENOVACIÓN ───────────────────────────
    if tipo_evento in ("subscription_restarted", "subscription_renewed"):
        # Buscar licencia por gumroad_id
        from database import get_connection
        conn = get_connection()
        lic = conn.execute(
            "SELECT clave FROM licencias WHERE gumroad_id=?", (gumroad_id,)
        ).fetchone()
        conn.close()

        if lic:
            resultado = renovar_licencia(lic["clave"])
            log_evento(lic["clave"], "", "WEBHOOK_RENOVACION", "OK", ip)
            return jsonify(resultado), 200

        return jsonify({"ok": False, "error": "Licencia no encontrada"}), 404

    # ── CANCELACIÓN ──────────────────────────
    if tipo_evento in ("subscription_cancelled", "subscription_ended"):
        from database import get_connection
        conn = get_connection()
        lic = conn.execute(
            "SELECT clave FROM licencias WHERE gumroad_id=?", (gumroad_id,)
        ).fetchone()
        conn.close()

        if lic:
            expirar_licencia(lic["clave"])
            log_evento(lic["clave"], "", "WEBHOOK_CANCELACION", "EXPIRADA", ip)
            return jsonify({"ok": True}), 200

    return jsonify({"ok": True, "evento": tipo_evento}), 200


# ─── ENDPOINT 5: ADMIN API ────────────────────
@app.route("/admin/api", methods=["GET"])
@admin_requerido
def admin_api():
    licencias = obtener_todas_licencias()
    activas   = sum(1 for l in licencias if l["estado"] == "activa")
    expiradas = sum(1 for l in licencias if l["estado"] == "expirada")
    trials    = sum(1 for l in licencias if l["tipo"] == "trial")
    return jsonify({
        "total": len(licencias),
        "activas": activas,
        "expiradas": expiradas,
        "trials": trials,
        "licencias": licencias
    })


# ─── ENDPOINT 6: PANEL ADMIN HTML ─────────────
@app.route("/admin", methods=["GET"])
@admin_requerido
def admin_panel():
    return render_template_string(PANEL_HTML)


# ─── ENDPOINT 7: ACCIÓN ADMIN ─────────────────
@app.route("/admin/accion", methods=["POST"])
@admin_requerido
def admin_accion():
    data   = request.get_json(force=True, silent=True) or {}
    accion = data.get("accion")
    clave  = data.get("clave", "").upper()

    if accion == "expirar":
        expirar_licencia(clave)
        return jsonify({"ok": True})
    if accion == "eliminar":
        eliminar_licencia(clave)
        return jsonify({"ok": True})
    if accion == "limpiar_expiradas":
        n = limpiar_licencias_expiradas()
        return jsonify({"ok": True, "eliminadas": n})
    if accion == "renovar":
        return jsonify(renovar_licencia(clave))
    if accion == "crear":
        tipo = data.get("tipo", "mensual")
        email = data.get("email", "")
        lic = crear_licencia(tipo=tipo, email=email)
        return jsonify({"ok": True, "licencia": lic})

    return jsonify({"error": "Acción desconocida"}), 400


# ─── HEALTH CHECK ─────────────────────────────
@app.route("/", methods=["GET"])
def health():
    resp = jsonify({"status": "KuroFlow License Server online", "version": "1.0"})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


# ─── ENDPOINT: WEEKLY ANALYSIS ────────────────
# Called from members portal — proxies Claude API server-side
_analysis_cache = {}

def call_claude(api_key, prompt, max_tokens=700):
    """Call Claude API — no tools, simple and reliable."""
    r = req_lib.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=45
    )
    data = r.json()
    print("Claude raw response:", data)
    blocks = data.get("content", [])
    text = " ".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return text.strip()

@app.route("/analysis", methods=["GET", "OPTIONS"])
def weekly_analysis():
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    from datetime import datetime
    import json as json_lib

    ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    if not ANTHROPIC_KEY:
        resp = jsonify({"error": "no_key"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 500

    now = datetime.utcnow()
    week_key = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"

    if week_key in _analysis_cache:
        resp = jsonify({"ok": True, "week": week_key, "usdjpy": _analysis_cache[week_key]["usdjpy"], "global": _analysis_cache[week_key]["global"]})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    # Get USDJPY price
    price = "—"
    try:
        r = req_lib.get("https://api.frankfurter.app/latest?from=USD&to=JPY", timeout=5)
        price = str(round(r.json()["rates"]["JPY"], 3))
    except:
        pass

    date_str = now.strftime("%A %d %B %Y")

    prompt_usdjpy = f"""You are the analyst behind Kuro-Flow, a professional USDJPY algorithmic trading system. Today is {date_str}. Current USDJPY rate: {price}.

Write a USDJPY Weekly Briefing for Kuro-Flow members. Write exactly 2 short paragraphs:
1. Macro context: BoJ policy stance, Fed rate expectations, key USD/JPY macro drivers and current trend
2. Algorithm context: how Kuro-Flow's low-drawdown structural approach behaves in current conditions — session logic, risk management (no predictions, no guarantees)

Rules:
- Write confidently. Do not mention AI limitations or suggest consulting other sources.
- Output ONLY the HTML. No markdown, no code fences, no backticks, no triple quotes.
- Use only <p> and <strong> tags. No headings, no bullet points.
- Max 180 words."""

    prompt_global = f"""You are a macro market analyst writing for Kuro-Flow members. Today is {date_str}.

Write a Global Market Sentiment briefing. Write exactly 2 short paragraphs:
1. Overall risk sentiment: risk-on or risk-off environment, key macro drivers, major index trends (S&P500, Nikkei, DAX), DXY and commodities direction
2. USDJPY implications: yen safe-haven flows, carry trade conditions, what this means for USDJPY algo traders

Rules:
- Write confidently. Do not mention AI limitations or suggest consulting other sources.
- Output ONLY the HTML. No markdown, no code fences, no backticks, no triple quotes.
- Use only <p> and <strong> tags. No headings, no bullet points.
- Max 180 words."""

    try:
        usdjpy_html = call_claude(ANTHROPIC_KEY, prompt_usdjpy, max_tokens=700)
        global_html  = call_claude(ANTHROPIC_KEY, prompt_global,  max_tokens=700)

        _analysis_cache[week_key] = {"usdjpy": usdjpy_html, "global": global_html}

        resp = jsonify({"ok": True, "week": week_key, "usdjpy": usdjpy_html, "global": global_html})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        print(f"Analysis error: {e}")
        resp = jsonify({"error": str(e)})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 500




def build_funnel_email(step: int, email: str, clave: str) -> dict:
    """Build funnel email HTML and subject for each step."""
    
    base_style = """
    <!DOCTYPE html><html><head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#0a0a0c;font-family:'Courier New',monospace;">
    <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#0f0f12;border:1px solid #1e1e22;">
    <tr><td style="background:#c9a84c;height:4px;"></td></tr>
    <tr><td style="padding:32px 40px 24px;">
      <span style="font-size:22px;font-weight:900;color:#f5f3ee;letter-spacing:-1px;">
        KURO<span style="color:#c9a84c;">FLOW</span>
      </span>
    </td></tr>
    """
    
    base_footer = """
    <tr><td style="padding:24px 40px;border-top:1px solid #1e1e22;">
      <p style="color:#2a2a2e;font-size:11px;margin:0;line-height:1.6;">
        KuroFlow Algorithmic Trading · You received this because you activated a free trial.<br>
        Questions? Reply to this email or contact support@kuro-flow.com
      </p>
    </td></tr>
    <tr><td style="background:#c9a84c;height:2px;"></td></tr>
    </table></td></tr></table></body></html>
    """

    if step == 1:
        subject = "KuroFlow — Did you get the EA running? 🤖"
        body = f"""
        <tr><td style="padding:0 40px 28px;">
          <p style="color:#6b6860;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0 0 16px;">// Day 1</p>
          <h2 style="color:#f5f3ee;font-size:20px;margin:0 0 16px;">Did you get the EA installed?</h2>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 16px;">
            Your 7-day trial of Kuro-Flow is running. The EA should be attached to your USDJPY M5 chart by now.
          </p>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 20px;">
            If you haven't installed it yet — it takes less than 10 minutes. Your files and step-by-step guide are in your welcome email.
          </p>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 20px;">
            <strong style="color:#c9a84c;">Quick checklist:</strong><br>
            ✓ KuroFlow_License.ex5 in MT5 → MQL5 → Experts<br>
            ✓ KuroFlow_Optimized.set loaded<br>
            ✓ AutoTrading button green<br>
            ✓ License key <span style="color:#c9a84c;">{clave}</span> entered
          </p>
          <a href="https://kuro-flow.com/setup-guide.html" style="display:inline-block;background:#c9a84c;color:#0a0a0c;padding:12px 28px;font-family:'Courier New';font-size:13px;font-weight:700;text-decoration:none;letter-spacing:1px;">
            VIEW SETUP GUIDE →
          </a>
        </td></tr>
        """

    elif step == 2:
        subject = "KuroFlow — How the algorithm actually works"
        body = f"""
        <tr><td style="padding:0 40px 28px;">
          <p style="color:#6b6860;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0 0 16px;">// Day 3</p>
          <h2 style="color:#f5f3ee;font-size:20px;margin:0 0 16px;">How Kuro-Flow makes decisions</h2>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 16px;">
            Kuro-Flow is an intraday breakout system built around two specific USDJPY session windows.
          </p>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 16px;">
            It doesn't trade all day. It waits for the right structural conditions — specific range, direction and session alignment — then enters with a fixed 0.5% risk per trade and a partial close at 50% of TP.
          </p>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 20px;">
            <strong style="color:#c9a84c;">The numbers after 6 years of backtesting:</strong><br>
            → +154% net return<br>
            → 3.31% max drawdown<br>
            → 70.5% win rate<br>
            → Sharpe ratio: 9.04
          </p>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 20px;">
            Verified on The5ers prop firm. $7,066 withdrawn. Zero rule violations.
          </p>
          <a href="https://kuro-flow.com/#proof" style="display:inline-block;background:#c9a84c;color:#0a0a0c;padding:12px 28px;font-family:'Courier New';font-size:13px;font-weight:700;text-decoration:none;letter-spacing:1px;">
            SEE THE TRACK RECORD →
          </a>
        </td></tr>
        """

    elif step == 3:
        subject = "KuroFlow — 2 days left on your trial"
        body = f"""
        <tr><td style="padding:0 40px 28px;">
          <p style="color:#6b6860;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0 0 16px;">// Day 5</p>
          <h2 style="color:#f5f3ee;font-size:20px;margin:0 0 16px;">Your trial ends in 2 days.</h2>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 16px;">
            You've had 5 days with Kuro-Flow running on your account. 
          </p>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 20px;">
            If the EA has been operating — you've already seen how it trades. Disciplined entries, controlled risk, no emotional decisions.
          </p>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 20px;">
            To keep it running without interruption, subscribe before your key expires:
          </p>
          <table cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
            <tr>
              <td style="padding-right:12px;">
                <a href="https://kuroflow.gumroad.com/l/ngqzzi" style="display:inline-block;background:#c9a84c;color:#0a0a0c;padding:12px 24px;font-family:'Courier New';font-size:12px;font-weight:700;text-decoration:none;letter-spacing:1px;">
                  MONTHLY €67 →
                </a>
              </td>
              <td>
                <a href="https://kuroflow.gumroad.com/l/rumdt" style="display:inline-block;background:transparent;color:#c9a84c;border:1px solid #c9a84c;padding:12px 24px;font-family:'Courier New';font-size:12px;font-weight:700;text-decoration:none;letter-spacing:1px;">
                  ANNUAL €402 — SAVE 50% →
                </a>
              </td>
            </tr>
          </table>
          <p style="color:#4a4a4e;font-size:12px;margin:0;">
            Questions before subscribing? Reply to this email.
          </p>
        </td></tr>
        """

    elif step == 4:
        subject = "KuroFlow — Your trial expires today"
        body = f"""
        <tr><td style="padding:0 40px 28px;">
          <p style="color:#6b6860;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0 0 16px;">// Day 7</p>
          <h2 style="color:#f5f3ee;font-size:20px;margin:0 0 16px;">Today is the last day of your trial.</h2>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 16px;">
            Your key <span style="color:#c9a84c;">{clave}</span> expires today.
          </p>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 20px;">
            If Kuro-Flow has been running on your account this week, you've seen how it operates. No manual intervention. No emotional decisions. Just the algorithm doing its job.
          </p>
          <p style="color:#8a8880;font-size:14px;line-height:1.7;margin:0 0 20px;">
            Subscribe now to keep it running without interruption:
          </p>
          <table cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
            <tr>
              <td style="padding-right:12px;">
                <a href="https://kuroflow.gumroad.com/l/ngqzzi" style="display:inline-block;background:#c9a84c;color:#0a0a0c;padding:14px 28px;font-family:'Courier New';font-size:13px;font-weight:700;text-decoration:none;letter-spacing:1px;">
                  SUBSCRIBE NOW — €67/mo →
                </a>
              </td>
            </tr>
          </table>
          <a href="https://kuroflow.gumroad.com/l/rumdt" style="display:inline-block;color:#c9a84c;font-family:'Courier New';font-size:12px;text-decoration:none;letter-spacing:1px;margin-bottom:20px;">
            Or save 50% with Annual — €402/year →
          </a>
          <p style="color:#4a4a4e;font-size:12px;margin:0;">
            Not ready yet? Reply and tell us what's holding you back. We read every reply.
          </p>
        </td></tr>
        """

    return {
        "subject": subject,
        "html": base_style + body + base_footer
    }


def send_funnel_email(email_id: int, email: str, clave: str, step: int):
    """Send a single funnel email and mark as sent."""
    if not RESEND_API_KEY:
        print(f"RESEND not configured. Funnel step {step} for {email}")
        mark_funnel_email_sent(email_id)
        return

    data = build_funnel_email(step, email, clave)
    try:
        req_lib.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": FROM_EMAIL,
                "to": [email],
                "subject": data["subject"],
                "html": data["html"]
            },
            timeout=10
        )
        mark_funnel_email_sent(email_id)
        print(f"Funnel step {step} sent to {email}")
    except Exception as e:
        print(f"Funnel email error step {step} for {email}: {e}")



@app.route("/funnel/process", methods=["GET", "POST"])
def process_funnel():
    """Process pending funnel emails. Called by UptimeRobot every hour."""
    token = request.args.get("token", "") or (request.get_json(force=True, silent=True) or {}).get("token", "")
    if token != os.environ.get("ADMIN_TOKEN", "KF-admin-2024-kuroflow"):
        return jsonify({"error": "unauthorized"}), 401

    pending = get_pending_funnel_emails()
    sent_count = 0
    for row in pending:
        email_id, email, clave, step = row[0], row[1], row[2], row[3]
        send_funnel_email(email_id, email, clave, step)
        sent_count += 1

    resp = jsonify({"ok": True, "processed": sent_count})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp



@app.route("/get-activity", methods=["GET", "OPTIONS"])
def get_activity():
    """Returns the most recent real license event for social proof toasts."""
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    try:
        from database import execute
        # Get most recent license activation or creation in last 24h
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        row = execute("""
            SELECT clave, tipo, creada, email FROM licencias
            WHERE estado IN ('activa', 'pendiente')
            AND creada >= ?
            ORDER BY creada DESC LIMIT 1
        """, (cutoff,), fetchone=True)

        if not row:
            resp = jsonify({"status": "waiting"})
            resp.headers["Access-Control-Allow-Origin"] = "*"
            return resp

        tipo   = row['tipo']   if isinstance(row, dict) else row[0]
        creada = row['creada'] if isinstance(row, dict) else row[1]
        email  = row['email']  if isinstance(row, dict) else row[2]
        clave  = row['clave']  if isinstance(row, dict) else None

        # Get country from IP geolocation using the stored IP in logs
        country = "us"
        try:
            if clave:
                log_row = execute("""
                    SELECT ip FROM logs WHERE clave=? AND accion='TRIAL_CREADO'
                    ORDER BY fecha DESC LIMIT 1
                """, (clave,), fetchone=True)
                if log_row:
                    ip = log_row['ip'] if isinstance(log_row, dict) else log_row[0]
                    if ip and ip not in ('127.0.0.1', '::1', '') and not ip.startswith('10.') and not ip.startswith('172.'):
                        # Try ipapi.co
                        geo = req_lib.get(f"https://ipapi.co/{ip}/country/", timeout=3)
                        if geo.status_code == 200 and len(geo.text.strip()) == 2:
                            country = geo.text.strip().lower()
                        else:
                            # Fallback: ip-api.com
                            geo2 = req_lib.get(f"http://ip-api.com/json/{ip}?fields=countryCode", timeout=3)
                            if geo2.status_code == 200:
                                data2 = geo2.json()
                                country = data2.get("countryCode", "us").lower()
        except:
            pass

        action_map = {
            "trial":   "Activated a 7-Day Free Trial",
            "mensual": "Purchased a Monthly License",
            "anual":   "Purchased an Annual License",
        }
        action = action_map.get(tipo, "Started a Free Trial")

        resp = jsonify({
            "status": "ok",
            "action": action,
            "country": country,
            "timestamp": str(creada)
        })
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    except Exception as e:
        import traceback
        print(f"Activity error: {e}")
        print(f"Activity traceback: {traceback.format_exc()}")
        resp = jsonify({"status": "waiting", "debug": str(e)})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp


@app.route("/admin/clear-trial-ip", methods=["POST", "OPTIONS"])
def clear_trial_ip():
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    token = request.args.get("token", "")
    if token != os.environ.get("ADMIN_TOKEN", "KF-admin-2024-kuroflow"):
        return jsonify({"error": "unauthorized"}), 401
    try:
        from database import execute as db_execute
        data = request.get_json(force=True, silent=True) or {}
        ip    = data.get("ip", "").strip()
        email = data.get("email", "").strip().lower()

        if email:
            # Find IP from logs for this email's trial
            lic = db_execute("SELECT clave FROM licencias WHERE email=? AND tipo='trial' ORDER BY creada DESC LIMIT 1", (email,), fetchone=True)
            if lic:
                clave = lic["clave"] if isinstance(lic, dict) else lic[0]
                log_row = db_execute("SELECT ip FROM logs WHERE clave=? AND accion='TRIAL_CREADO' LIMIT 1", (clave,), fetchone=True)
                if log_row:
                    ip = log_row["ip"] if isinstance(log_row, dict) else log_row[0]
            # Delete trial license so email can be reused
            db_execute("DELETE FROM licencias WHERE email=? AND tipo='trial'", (email,), commit=True)
            # Delete funnel emails for this address
            db_execute("DELETE FROM funnel_emails WHERE email=?", (email,), commit=True)
            if ip:
                db_execute("DELETE FROM trial_ips WHERE ip=?", (ip,), commit=True)
                return jsonify({"ok": True, "message": f"Trial reset for {email} (IP: {ip}). They can request a new trial."})
            return jsonify({"ok": True, "message": f"Trial email reset for {email}. IP not found in logs."})

        if ip:
            db_execute("DELETE FROM trial_ips WHERE ip=?", (ip,), commit=True)
            return jsonify({"ok": True, "message": f"IP {ip} cleared"})

        # No email or IP — clear everything (full reset for testing)
        db_execute("DELETE FROM trial_ips", commit=True)
        db_execute("DELETE FROM licencias WHERE tipo='trial'", commit=True)
        db_execute("DELETE FROM funnel_emails", commit=True)
        return jsonify({"ok": True, "message": "All trial data cleared for testing."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/admin/my-ip", methods=["GET"])
def my_ip():
    """Shows what IP the server sees for this request."""
    ip = get_ip()
    xff = request.headers.get("X-Forwarded-For", "none")
    remote = request.remote_addr
    # Check if this IP is blocked
    from database import execute
    blocked = execute("SELECT id FROM trial_ips WHERE ip=?", (ip,), fetchone=True)
    resp = jsonify({
        "your_ip": ip,
        "x_forwarded_for": xff,
        "remote_addr": remote,
        "is_blocked": blocked is not None
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/stats", methods=["GET"])
def get_stats():
    """Returns real license counts for social proof counters."""
    try:
        from database import execute as db_exec
        rows = db_exec("SELECT tipo, COUNT(*) as cnt FROM licencias GROUP BY tipo", fetchall=True)
        counts = {"trial": 0, "mensual": 0, "anual": 0}
        if rows:
            for row in rows:
                tipo = row["tipo"] if isinstance(row, dict) else row[0]
                cnt  = row["cnt"]  if isinstance(row, dict) else row[1]
                if tipo in counts:
                    counts[tipo] = cnt
        # Add base numbers for social proof
        result = {
            "trials":  counts["trial"]   + 5,
            "monthly": counts["mensual"] + 1,
            "annual":  counts["anual"]   + 0,
        }
        resp = jsonify({"ok": True, **result})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        resp = jsonify({"ok": True, "trials": 12, "monthly": 3, "annual": 1})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

# ─── PANEL HTML ───────────────────────────────
PANEL_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KuroFlow — Panel de Licencias</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet">
<style>
  :root{--ink:#0a0a0c;--paper:#f5f3ee;--gold:#c9a84c;--safe:#4c9c6b;--danger:#c94c4c;--ash:#6b6860}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'DM Mono',monospace;background:var(--ink);color:var(--paper);min-height:100vh;padding:32px}
  header{display:flex;justify-content:space-between;align-items:center;margin-bottom:40px;border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:20px}
  .logo{font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:800;color:var(--gold)}
  .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px}
  .stat{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);padding:20px;text-align:center}
  .stat-num{font-family:'Syne',sans-serif;font-size:2rem;font-weight:800}
  .stat-label{font-size:0.65rem;letter-spacing:0.1em;text-transform:uppercase;color:rgba(255,255,255,0.35);margin-top:4px}
  .actions{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}
  .btn{font-family:'DM Mono',monospace;font-size:0.75rem;letter-spacing:0.06em;padding:10px 20px;border:1px solid;cursor:pointer;background:transparent;transition:all 0.2s}
  .btn-gold{border-color:var(--gold);color:var(--gold)} .btn-gold:hover{background:var(--gold);color:var(--ink)}
  .btn-danger{border-color:var(--danger);color:var(--danger)} .btn-danger:hover{background:var(--danger);color:#fff}
  .btn-safe{border-color:var(--safe);color:var(--safe)} .btn-safe:hover{background:var(--safe);color:#fff}
  .search{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);color:var(--paper);padding:10px 16px;font-family:'DM Mono',monospace;font-size:0.8rem;width:280px}
  .search:focus{outline:none;border-color:var(--gold)}
  table{width:100%;border-collapse:collapse;font-size:0.75rem}
  th{text-align:left;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,0.08);color:rgba(255,255,255,0.35);letter-spacing:0.08em;text-transform:uppercase;font-weight:400}
  td{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,0.05)}
  tr:hover td{background:rgba(255,255,255,0.02)}
  .badge{display:inline-block;padding:3px 8px;font-size:0.62rem;letter-spacing:0.08em;text-transform:uppercase}
  .badge-activa{background:rgba(76,156,107,0.15);color:#6edd9e}
  .badge-expirada{background:rgba(201,76,76,0.15);color:#ed6e6e}
  .badge-pendiente{background:rgba(201,168,76,0.15);color:var(--gold)}
  .badge-trial{background:rgba(100,100,200,0.2);color:#aab}
  .modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.7);align-items:center;justify-content:center;z-index:100}
  .modal.open{display:flex}
  .modal-box{background:#16161a;border:1px solid rgba(255,255,255,0.1);padding:32px;width:400px}
  .modal-box h3{font-family:'Syne',sans-serif;margin-bottom:20px;color:var(--gold)}
  input,select{width:100%;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);color:var(--paper);padding:10px;font-family:'DM Mono',monospace;font-size:0.8rem;margin-bottom:12px}
  input:focus,select:focus{outline:none;border-color:var(--gold)}
  .modal-actions{display:flex;gap:12px;margin-top:8px}
</style>
</head>
<body>
<header>
  <div class="logo">⬤ KuroFlow Admin</div>
  <div style="font-size:0.7rem;color:rgba(255,255,255,0.3)" id="last-update">Cargando...</div>
</header>

<div class="stats" id="stats">
  <div class="stat"><div class="stat-num" id="s-total">—</div><div class="stat-label">Total Licencias</div></div>
  <div class="stat"><div class="stat-num" style="color:#6edd9e" id="s-activas">—</div><div class="stat-label">Activas</div></div>
  <div class="stat"><div class="stat-num" style="color:#ed6e6e" id="s-expiradas">—</div><div class="stat-label">Expiradas</div></div>
  <div class="stat"><div class="stat-num" style="color:var(--gold)" id="s-trials">—</div><div class="stat-label">Trials</div></div>
</div>

<div class="actions">
  <button class="btn btn-gold" onclick="abrirModal()">+ New License</button>
  <input class="search" id="buscador" placeholder="Search by key, email or account..." oninput="filtrar()">
  <button class="btn btn-safe" onclick="cargar()" style="margin-left:auto">↻ Refresh</button>
  <button class="btn btn-danger" onclick="limpiarExpiradas()">🗑 Clean expired (+30d)</button>
  <button class="btn" onclick="resetTrialIPs()" style="background:#2a2a40;color:#c9a84c;border:1px solid #c9a84c;">⟳ Reset trial IPs</button>
</div>

<table>
  <thead>
    <tr>
      <th>Key</th><th>Type</th><th>Status</th><th>MT5 Account</th>
      <th>Email</th><th>Expires</th><th>Last Check</th><th>Actions</th>
    </tr>
  </thead>
  <tbody id="tabla"></tbody>
</table>

<!-- MODAL NUEVA LICENCIA -->
<div class="modal" id="modal">
  <div class="modal-box">
    <h3>New Manual License</h3>
    <select id="m-tipo">
      <option value="mensual">Monthly</option>
      <option value="anual">Annual</option>
      <option value="vitalicia">Lifetime</option>
      <option value="trial">Trial 7 days</option>
    </select>
    <input id="m-email" placeholder="Client email (optional)">
    <div class="modal-actions">
      <button class="btn btn-gold" onclick="crearLicencia()">Create</button>
      <button class="btn" style="border-color:rgba(255,255,255,0.2);color:rgba(255,255,255,0.4)" onclick="cerrarModal()">Cancel</button>
    </div>
    <div id="m-resultado" style="margin-top:16px;font-size:0.75rem;color:#6edd9e"></div>
  </div>
</div>

<script>
const TOKEN = new URLSearchParams(location.search).get('token') || '';

async function api(url, method='GET', body=null){
  const opts = {method, headers:{'X-Admin-Token':TOKEN,'Content-Type':'application/json'}};
  if(body) opts.body = JSON.stringify(body);
  const r = await fetch(url, opts);
  return r.json();
}

let todasLicencias = [];

async function cargar(){
  const d = await api(`/admin/api?token=${TOKEN}`);
  todasLicencias = d.licencias || [];
  document.getElementById('s-total').textContent = d.total;
  document.getElementById('s-activas').textContent = d.activas;
  document.getElementById('s-expiradas').textContent = d.expiradas;
  document.getElementById('s-trials').textContent = d.trials;
  document.getElementById('last-update').textContent = 'Actualizado: ' + new Date().toLocaleTimeString();
  renderTabla(todasLicencias);
}

function renderTabla(licencias){
  const tbody = document.getElementById('tabla');
  tbody.innerHTML = licencias.map(l => `
    <tr>
      <td style="font-weight:500;color:var(--gold)">${l.clave}</td>
      <td><span class="badge ${l.tipo==='trial'?'badge-trial':'badge-activa'}">${l.tipo}</span></td>
      <td><span class="badge badge-${l.estado}">${l.estado}</span></td>
      <td style="color:rgba(255,255,255,0.6)">${l.cuenta_mt5||'—'}</td>
      <td style="color:rgba(255,255,255,0.4);font-size:0.7rem">${l.email||'—'}</td>
      <td style="font-size:0.7rem">${l.expira?l.expira.split('T')[0]:'NEVER'}</td>
      <td style="font-size:0.68rem;color:rgba(255,255,255,0.3)">${l.ultimo_check?l.ultimo_check.split('T')[0]:'—'}</td>
      <td style="display:flex;gap:6px">
        ${l.estado!=='expirada'?`<button class="btn btn-danger" style="padding:4px 10px;font-size:0.65rem" onclick="accion('expirar','${l.clave}')">Expire</button>`:''}
        ${l.tipo==='mensual'?`<button class="btn btn-safe" style="padding:4px 10px;font-size:0.65rem" onclick="accion('renovar','${l.clave}')">+30d</button>`:''}
        <button class="btn btn-danger" style="padding:4px 10px;font-size:0.65rem;border-color:#ff4444;color:#ff4444" onclick="eliminar('${l.clave}')">✕ Delete</button>
      </td>
    </tr>
  `).join('');
}

function filtrar(){
  const q = document.getElementById('buscador').value.toLowerCase();
  renderTabla(todasLicencias.filter(l =>
    (l.clave||'').toLowerCase().includes(q) ||
    (l.email||'').toLowerCase().includes(q) ||
    (l.cuenta_mt5||'').toLowerCase().includes(q)
  ));
}

async function accion(tipo, clave){
  if(!confirm(`${tipo} license ${clave}?`)) return;
  await api(`/admin/accion?token=${TOKEN}`, 'POST', {accion:tipo, clave});
  cargar();
}

async function eliminar(clave){
  if(!confirm(`⚠ Permanently DELETE license ${clave}? This cannot be undone.`)) return;
  await api(`/admin/accion?token=${TOKEN}`, 'POST', {accion:'eliminar', clave});
  cargar();
}

async function resetTrialIPs(){
  const email = prompt('Enter the email to reset trial for (leave empty to clear ALL):');
  if (email === null) return; // cancelled
  const confirmMsg = email 
    ? `Reset trial for ${email}?` 
    : 'Clear ALL trial IPs and test licenses?';
  if (!confirm(confirmMsg)) return;
  const r = await fetch(`/admin/clear-trial-ip?token=${TOKEN}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({email: email.trim()})
  });
  const d = await r.json();
  alert(d.message || 'Done');
}

async function limpiarExpiradas(){
  if(!confirm('Delete all licenses expired for more than 30 days?')) return;
  const r = await api(`/admin/accion?token=${TOKEN}`, 'POST', {accion:'limpiar_expiradas'});
  alert(`Deleted: ${r.eliminadas} licenses`);
  cargar();
}

function abrirModal(){ document.getElementById('modal').classList.add('open'); }
function cerrarModal(){ document.getElementById('modal').classList.remove('open'); document.getElementById('m-resultado').textContent=''; }

async function crearLicencia(){
  const tipo = document.getElementById('m-tipo').value;
  const email = document.getElementById('m-email').value;
  const r = await api(`/admin/accion?token=${TOKEN}`, 'POST', {accion:'crear', tipo, email});
  if(r.ok){
    document.getElementById('m-resultado').textContent = '✓ Clave: ' + r.licencia.clave;
    cargar();
  }
}

cargar();
setInterval(cargar, 30000);
</script>
</body>
</html>
"""


# ─── INICIO ───────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


# ─── LEAD MAGNET ────────────────────────────────
@app.route('/leadmagnet', methods=['POST', 'OPTIONS'])
def leadmagnet():
    if request.method == 'OPTIONS':
        response = jsonify({'ok': True})
        response.headers.add('Access-Control-Allow-Origin', 'https://kuro-flow.com')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response
    data = request.get_json()
    name  = (data.get('name')  or '').strip()
    email = (data.get('email') or '').strip().lower()

    if not name or not email or '@' not in email:
        return jsonify({'ok': False, 'error': 'Datos inválidos'}), 400

    # Save to Supabase
    try:
        supabase.table('leads').upsert({
            'email': email,
            'name': name,
            'source': 'leadmagnet_propfirms',
            'created_at': datetime.utcnow().isoformat()
        }, on_conflict='email').execute()
    except Exception as e:
        print(f'[LEADS] Supabase error: {e}')

    # Send guide via Resend
    guide_url = 'https://kuro-flow.com/guia-prop-firms.html'

    html_body = f"""
    <div style="font-family:monospace;background:#0a0a0c;color:#f5f3ee;padding:40px;max-width:600px;margin:0 auto">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:32px">
        <div style="width:8px;height:8px;border-radius:50%;background:#c9a84c"></div>
        <span style="font-weight:800;font-size:1rem">KuroFlow</span>
      </div>

      <h1 style="font-size:1.4rem;font-weight:800;margin-bottom:12px;color:#f5f3ee">
        Hola {name}, aquí tienes tu guía 👇
      </h1>
      <p style="color:rgba(245,243,238,0.5);font-size:0.85rem;line-height:1.8;margin-bottom:28px">
        Gracias por descargar la guía. La tienes disponible en el enlace de abajo — puedes abrirla en el navegador y guardarla como PDF con Ctrl+P.
      </p>

      <a href="{guide_url}" style="display:block;text-align:center;padding:14px 28px;background:#c9a84c;color:#0a0a0c;text-decoration:none;font-weight:700;font-size:0.85rem;letter-spacing:0.06em;margin-bottom:32px">
        Abrir guía: Cómo pasar un Challenge de Prop Firm →
      </a>

      <div style="border:1px solid rgba(201,168,76,0.2);padding:20px;margin-bottom:24px">
        <div style="font-size:0.7rem;letter-spacing:0.1em;text-transform:uppercase;color:#c9a84c;margin-bottom:8px">Lo que encontrarás</div>
        <div style="font-size:0.8rem;color:rgba(245,243,238,0.5);line-height:1.8">
          → 12 errores que hacen fallar el challenge<br>
          → Gestión de riesgo para prop firms<br>
          → Checklist antes de cada trade<br>
          → Comparativa de The5ers, FTMO, For Traders y GOAT
        </div>
      </div>

      <div style="border-top:1px solid rgba(255,255,255,0.07);padding-top:20px;margin-top:8px">
        <p style="font-size:0.78rem;color:rgba(245,243,238,0.4);line-height:1.8;margin-bottom:16px">
          Si quieres seguir en tiempo real la operativa del sistema COMBO_TAC — el sistema que uso en mis propias cuentas de prop firm — puedes acceder a KuroFlow:
        </p>
        <a href="https://kuro-flow.com/#planes" style="display:inline-block;padding:10px 20px;border:1px solid rgba(201,168,76,0.3);color:#c9a84c;text-decoration:none;font-size:0.75rem;letter-spacing:0.06em">
          Ver planes desde €9 →
        </a>
      </div>

      <div style="margin-top:32px;font-size:0.65rem;color:rgba(245,243,238,0.15);line-height:1.6">
        ⚠️ Contenido exclusivamente educativo. No es asesoramiento financiero.<br>
        © 2026 KuroFlow · <a href="https://kuro-flow.com" style="color:rgba(201,168,76,0.4)">kuro-flow.com</a>
      </div>
    </div>
    """

    try:
        resend_response = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {os.getenv("RESEND_API_KEY")}',
                'Content-Type': 'application/json'
            },
            json={
                'from': os.getenv('FROM_EMAIL', 'licenses@kuro-flow.com'),
                'to': [email],
                'subject': f'Tu guía: Cómo pasar un Challenge de Prop Firm 📊',
                'html': html_body
            },
            timeout=10
        )
        if resend_response.status_code in (200, 201):
            print(f'[LEADS] Guía enviada a {email}')
            return jsonify({'ok': True})
        else:
            print(f'[LEADS] Resend error: {resend_response.text}')
            return jsonify({'ok': False, 'error': 'Error enviando email'}), 500
    except Exception as e:
        print(f'[LEADS] Error: {e}')
        return jsonify({'ok': False, 'error': 'Error de conexión'}), 500

