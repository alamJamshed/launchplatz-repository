from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .smtp_config import SMTPConfigManager
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending various types of emails"""
    
    @staticmethod
    def send_email(subject, message, recipient_list, html_message=None, from_email=None):
        """Send basic email"""
        try:
            connection, default_from = SMTPConfigManager.get_smtp_connection()
            from_email = from_email or default_from
            
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
                html_message=html_message,
                connection=connection,
                fail_silently=False
            )
            logger.info(f"Email sent successfully to {recipient_list}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False

    @staticmethod
    def send_template_email(template_name, context, subject, recipient_list, from_email=None):
        """Send email using HTML template"""
        try:
            connection, default_from = SMTPConfigManager.get_smtp_connection()
            from_email = from_email or default_from
            html_content = render_to_string(f'emails/{template_name}.html', context)
            text_content = strip_tags(html_content)
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=recipient_list,
                connection=connection
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            logger.info(f"Template email sent successfully to {recipient_list}")
            return True
        except Exception as e:
            logger.error(f"Failed to send template email: {str(e)}")
            return False

    @staticmethod
    def send_welcome_email(user_email, user_name, login_url=None):
        """Send welcome email to new user"""
        logger.info(f"Attempting to send welcome email to {user_email}")
        
        from utility.models import SiteSettings
        site_settings = SiteSettings.objects.first()
        
        context = {
            'user_name': user_name,
            'login_url': login_url or f"{settings.FRONTEND_URL}/login",
            'site_name': site_settings.site_name if site_settings else 'Our Platform'
        }
        
        subject = f"Welcome to {context['site_name']}!"
        
        # For testing without template, send simple email
        try:
            result = EmailService.send_email(
                subject=subject,
                message=f"Welcome {user_name}! Thanks for joining {context['site_name']}.",
                recipient_list=[user_email]
            )
            logger.info(f"Welcome email result for {user_email}: {result}")
            return result
        except Exception as e:
            logger.error(f"Welcome email failed for {user_email}: {str(e)}")
            return False

    @staticmethod
    def send_password_reset_email(user_email, user_name, reset_token, reset_url=None):
        """Send password reset email"""
        if not reset_url:
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{reset_token}"
        
        from utility.models import SiteSettings
        site_settings = SiteSettings.objects.first()
        
        context = {
            'user_name': user_name,
            'reset_url': reset_url,
            'site_name': site_settings.site_name if site_settings else 'Our Platform',
            'expiry_hours': getattr(settings, 'PASSWORD_RESET_TIMEOUT_HOURS', 24)
        }
        
        subject = "Password Reset Request"
        
        return EmailService.send_template_email(
            template_name='password_reset',
            context=context,
            subject=subject,
            recipient_list=[user_email]
        )

    @staticmethod
    def send_email_verification(user_email, user_name, verification_token, verification_url=None):
        """Send email verification"""
        if not verification_url:
            verification_url = f"{settings.FRONTEND_URL}/verify-email/{verification_token}"
        
        from utility.models import SiteSettings
        site_settings = SiteSettings.objects.first()
        
        context = {
            'user_name': user_name,
            'verification_url': verification_url,
            'site_name': site_settings.site_name if site_settings else 'Our Platform'
        }
        
        subject = "Please verify your email address"
        
        return EmailService.send_template_email(
            template_name='email_verification',
            context=context,
            subject=subject,
            recipient_list=[user_email]
        )

    @staticmethod
    def send_password_changed_notification(user_email, user_name):
        """Send notification when password is changed"""
        from utility.models import SiteSettings
        site_settings = SiteSettings.objects.first()
        
        context = {
            'user_name': user_name,
            'site_name': site_settings.site_name if site_settings else 'Our Platform',
            'support_email': site_settings.contact_email if site_settings else 'support@example.com'
        }
        
        subject = "Password Changed Successfully"
        
        return EmailService.send_template_email(
            template_name='password_changed',
            context=context,
            subject=subject,
            recipient_list=[user_email]
        )

    @staticmethod
    def send_account_activation_email(user_email, user_name, activation_token, activation_url=None):
        """Send account activation email"""
        if not activation_url:
            activation_url = f"{settings.FRONTEND_URL}/activate/{activation_token}"
        
        from utility.models import SiteSettings
        site_settings = SiteSettings.objects.first()
        
        context = {
            'user_name': user_name,
            'activation_url': activation_url,
            'site_name': site_settings.site_name if site_settings else 'Our Platform'
        }
        
        subject = "Activate Your Account"
        
        return EmailService.send_template_email(
            template_name='account_activation',
            context=context,
            subject=subject,
            recipient_list=[user_email]
        )


# Convenience functions
def send_welcome_email(user_email, user_name, login_url=None):
    return EmailService.send_welcome_email(user_email, user_name, login_url)

def send_password_reset_email(user_email, user_name, reset_token, reset_url=None):
    return EmailService.send_password_reset_email(user_email, user_name, reset_token, reset_url)

def send_email_verification(user_email, user_name, verification_token, verification_url=None):
    return EmailService.send_email_verification(user_email, user_name, verification_token, verification_url)

def send_password_changed_notification(user_email, user_name):
    return EmailService.send_password_changed_notification(user_email, user_name)

def send_account_activation_email(user_email, user_name, activation_token, activation_url=None):
    return EmailService.send_account_activation_email(user_email, user_name, activation_token, activation_url)