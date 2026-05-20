"""Servico de envio de email via SMTP para recuperacao de senha."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from settings import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USE_TLS, SMTP_USER


def smtp_configurado() -> bool:
    """Retorna True se as variaveis SMTP estao preenchidas."""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def enviar_email_recuperacao(
    email_destino: str,
    nome_usuario: str,
    token: str,
    base_url: str = "",
) -> tuple[bool, str]:
    """Envia o email de recuperacao de senha.

    Se `base_url` for informado, o email contem um link direto com o token.
    Caso contrario, exibe o token no corpo do email para uso manual.

    Retorna (sucesso, mensagem).
    """
    if not smtp_configurado():
        return False, "Servico de email nao configurado."

    remetente = SMTP_FROM or SMTP_USER

    if base_url:
        link = f"{base_url.rstrip('/')}?reset_token={token}"
        corpo_html = f"""
<html><body>
<p>Ola, <b>{nome_usuario}</b>!</p>
<p>Recebemos uma solicitacao de recuperacao de senha para sua conta no <b>Bolao da Copa</b>.</p>
<p>Clique no link abaixo para redefinir sua senha (valido por 1 hora):</p>
<p><a href="{link}">{link}</a></p>
<p>Se voce nao solicitou a recuperacao, ignore este email.</p>
</body></html>
"""
        corpo_texto = (
            f"Para redefinir sua senha, acesse:\n{link}\n\n"
            "Se nao foi voce, ignore este email."
        )
    else:
        corpo_html = f"""
<html><body>
<p>Ola, <b>{nome_usuario}</b>!</p>
<p>Seu token de recuperacao de senha e:</p>
<p><b>{token}</b></p>
<p>Use este token na tela "Recuperar Senha" do Bolao da Copa. Ele expira em 1 hora.</p>
<p>Se voce nao solicitou a recuperacao, ignore este email.</p>
</body></html>
"""
        corpo_texto = (
            f"Seu token de recuperacao de senha: {token}\n\n"
            "Use este token na tela 'Recuperar Senha' do Bolao da Copa. Ele expira em 1 hora."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Recuperacao de senha - Bolao da Copa"
    msg["From"] = remetente
    msg["To"] = email_destino
    msg.attach(MIMEText(corpo_texto, "plain", "utf-8"))
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))

    try:
        if SMTP_USE_TLS:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(remetente, email_destino, msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(remetente, email_destino, msg.as_string())
        return True, "Email enviado com sucesso."
    except smtplib.SMTPAuthenticationError:
        return False, "Falha na autenticacao SMTP. Verifique as credenciais."
    except smtplib.SMTPException as exc:
        return False, f"Erro ao enviar email: {exc}"
    except OSError as exc:
        return False, f"Nao foi possivel conectar ao servidor SMTP: {exc}"
