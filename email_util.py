import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

def _get_smtp_config():
    """Obtiene la configuración SMTP desde variables de entorno."""
    smtp_host = os.getenv("SMTP_HOST", "mail.smtp2go.com")
    try:
        smtp_port = int(os.getenv("SMTP_PORT", 2525))
    except (TypeError, ValueError):
        smtp_port = 2525
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASS", "").strip()
    smtp_sender = os.getenv("SMTP_SENDER", "").strip() or smtp_user or "notificaciones@powerlink.com"
    return smtp_host, smtp_port, smtp_user, smtp_pass, smtp_sender


def send_email_message(to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
    """
    Envía un correo electrónico. Si no hay credenciales SMTP configuradas en .env,
    opera en modo MOCK (simulación segura) para permitir desarrollo local sin exponer claves.
    """
    if not to_email:
        print("[EMAIL] Error: Destinatario no especificado.")
        return False

    smtp_host, smtp_port, smtp_user, smtp_pass, smtp_sender = _get_smtp_config()

    # Modo MOCK seguro para colaboradores / desarrollo local
    if not smtp_user or not smtp_pass:
        print("=" * 60)
        print(f"[EMAIL MOCK - DEV MODE] Para: {to_email}")
        print(f"[EMAIL MOCK - DEV MODE] Asunto: {subject}")
        print(f"[EMAIL MOCK - DEV MODE] Remitente: {smtp_sender}")
        print(f"[EMAIL MOCK - DEV MODE] (Credenciales SMTP no configuradas en .env. Envío simulado con éxito).")
        print("=" * 60)
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_sender
    msg["To"] = to_email

    if text_content:
        msg.attach(MIMEText(text_content, "plain", "utf-8"))
    if html_content:
        msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=12)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_sender, to_email, msg.as_string())
        server.quit()
        print(f"[EMAIL] OK Correo enviado exitosamente a {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Falló el envío de correo a {to_email}: {e}")
        return False


def send_welcome_email(to_email, name, username="", password="", smtp_user=None, smtp_pass=None, is_update=False):
    """
    Envía correo de bienvenida o actualización de datos a un empleado.
    Los parámetros smtp_user y smtp_pass se mantienen como opcionales por compatibilidad
    pero la función prioriza las variables de entorno para máxima seguridad.
    """
    subject = "Bienvenido al Equipo Power Corp." if not is_update else "Actualización de Datos en Power Corp."
    logo_url = "https://ngfihmioixtfnrmlrlam.supabase.co/storage/v1/object/public/power/descarga-removebg-preview.png"

    if not is_update:
        credentials_block = ""
        if username or password:
            credentials_block = f"""
            <div style="background-color:#FAFAFA; border-left:4px solid #FCA311; padding:15px; margin:25px 0;">
                <p style="margin:5px 0;"><strong>Usuario:</strong> {username}</p>
                <p style="margin:5px 0;"><strong>Contraseña:</strong> {password}</p>
            </div>
            """

        html_content = f"""
        <html>
            <body style="margin:0; padding:0; background-color:#F4F7F6; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
                <table align="center" border="0" cellpadding="0" cellspacing="0" width="600" style="background-color:#FFFFFF; margin-top:30px; border-radius:12px; overflow:hidden; box-shadow:0 8px 16px rgba(0,0,0,0.1);">
                    <tr>
                        <td align="center" bgcolor="#14213D" style="padding:40px 0 30px 0;">
                            <img src="{logo_url}" alt="Power Corp Logo" width="150" style="display:block; margin-bottom:15px;" />
                            <h1 style="color:#FCA311; margin:0; font-size:24px; letter-spacing:1px;">¡Bienvenido al Equipo Power!</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:40px 30px; color:#111111; font-size:16px; line-height:1.6;">
                            <p>Hola <strong>{name}</strong>,</p>
                            <p>Nos complace darte la bienvenida oficial a <strong>Power Corp</strong>. Tu perfil ha sido creado exitosamente en nuestra plataforma Intranet.</p>
                            {credentials_block}
                            <p>Estamos emocionados de contar contigo y te deseamos mucho éxito en esta nueva etapa.</p>
                            <p>Atentamente,<br><strong style="color:#14213D;">El equipo de RRHH</strong></p>
                        </td>
                    </tr>
                    <tr>
                        <td bgcolor="#14213D" style="padding:20px; text-align:center; color:#FFFFFF; font-size:12px;">
                            <p style="margin:0;">&copy; 2026 Power Link Corp. Todos los derechos reservados.</p>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """
    else:
        html_content = f"""
        <html>
            <body style="margin:0; padding:0; background-color:#F4F7F6; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
                <table align="center" border="0" cellpadding="0" cellspacing="0" width="600" style="background-color:#FFFFFF; margin-top:30px; border-radius:12px; overflow:hidden; box-shadow:0 8px 16px rgba(0,0,0,0.1);">
                    <tr>
                        <td align="center" bgcolor="#14213D" style="padding:40px 0 30px 0;">
                            <img src="{logo_url}" alt="Power Corp Logo" width="150" style="display:block; margin-bottom:15px;" />
                            <h1 style="color:#FCA311; margin:0; font-size:24px; letter-spacing:1px;">Actualización de Perfil</h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:40px 30px; color:#111111; font-size:16px; line-height:1.6;">
                            <p>Hola <strong>{name}</strong>,</p>
                            <p>Te informamos que tus datos personales y de empleado han sido actualizados exitosamente en nuestra plataforma.</p>
                            <p>Si tienes alguna pregunta sobre estos cambios, por favor contacta al departamento de Recursos Humanos.</p>
                            <p>Atentamente,<br><strong style="color:#14213D;">El equipo de RRHH</strong></p>
                        </td>
                    </tr>
                    <tr>
                        <td bgcolor="#14213D" style="padding:20px; text-align:center; color:#FFFFFF; font-size:12px;">
                            <p style="margin:0;">&copy; 2026 Power Link Corp. Todos los derechos reservados.</p>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
        """

    return send_email_message(to_email=to_email, subject=subject, html_content=html_content)


def send_credentials_update_email(to_email: str, full_name: str, new_email: str, new_password: str = None) -> bool:
    """Envía notificación de actualización de credenciales de usuario del sistema."""
    subject = "Actualización de Credenciales - Intranet Powerlink"
    body_pw = f"\nNueva Contraseña: {new_password}" if new_password else ""
    text_content = f"Hola {full_name},\n\nTus credenciales de acceso han sido actualizadas.\n\nNuevo Correo: {new_email}{body_pw}\n\nSaludos,\nAdministración."
    
    html_content = f"""
    <html>
        <body style="font-family:sans-serif; padding:20px; color:#333;">
            <div style="max-width:500px; margin:auto; border:1px solid #eee; border-radius:8px; padding:20px;">
                <h3 style="color:#14213D;">Actualización de Credenciales</h3>
                <p>Hola <strong>{full_name}</strong>,</p>
                <p>Tus credenciales de acceso a la Intranet han sido actualizadas:</p>
                <ul>
                    <li><strong>Correo:</strong> {new_email}</li>
                    {f'<li><strong>Nueva Contraseña:</strong> {new_password}</li>' if new_password else ''}
                </ul>
                <p style="font-size:12px; color:#777;">Si no reconoces este cambio, por favor contacta al administrador de inmediato.</p>
            </div>
        </body>
    </html>
    """
    return send_email_message(to_email=to_email, subject=subject, html_content=html_content, text_content=text_content)
