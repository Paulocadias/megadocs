"""
Alert system for critical system events.
Handles notifications for errors, capacity issues, and security threats.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from threading import Thread
import os

logger = logging.getLogger(__name__)

class AlertSystem:
    """System for managing and sending alerts."""
    
    def __init__(self):
        self.enabled = True
        # Load email config from environment or config file
        self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp-relay.brevo.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', 587))
        self.smtp_user = os.environ.get('SMTP_USERNAME')
        self.smtp_pass = os.environ.get('SMTP_PASSWORD')
        self.alert_email = os.environ.get('CONTACT_EMAIL')
        
    def send_alert(self, subject: str, message: str, level: str = 'critical'):
        """
        Send an alert notification.
        
        Args:
            subject: Alert subject
            message: Alert details
            level: Alert severity (info, warning, critical)
        """
        if not self.enabled:
            return
            
        # Log the alert
        logger.warning(f"ALERT [{level.upper()}]: {subject} - {message}")
        
        # Send email asynchronously
        if self.smtp_user and self.smtp_pass and self.alert_email:
            Thread(target=self._send_email, args=(subject, message, level)).start()
            
    def _send_email(self, subject: str, message: str, level: str):
        """Internal method to send email."""
        try:
            msg = MIMEMultipart()
            msg['From'] = f"MegaDoc Alerts <{self.smtp_user}>"
            msg['To'] = self.alert_email
            msg['Subject'] = f"[{level.upper()}] MegaDoc Alert: {subject}"
            
            body = f"""
MegaDoc System Alert
--------------------
Level: {level.upper()}
Time: {datetime.now().isoformat()}
Subject: {subject}

Details:
{message}

--------------------
Automated Alert System
"""
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
                
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")

    def check_thresholds(self, metrics: dict):
        """
        Check system metrics against thresholds.
        
        Args:
            metrics: Dictionary of current system metrics
        """
        # CPU Usage
        if metrics.get('cpu_percent', 0) > 90:
            self.send_alert("High CPU Usage", f"CPU usage is at {metrics['cpu_percent']}%", "warning")
            
        # Memory Usage
        if metrics.get('memory_percent', 0) > 90:
            self.send_alert("High Memory Usage", f"Memory usage is at {metrics['memory_percent']}%", "critical")
            
        # Disk Space
        if metrics.get('disk_percent', 0) > 90:
            self.send_alert("Low Disk Space", f"Disk usage is at {metrics['disk_percent']}%", "critical")
            
        # Error Rate
        if metrics.get('error_rate', 0) > 0.05:  # 5%
            self.send_alert("High Error Rate", f"Error rate is at {metrics['error_rate']*100}%", "critical")

# Global alert system instance
alerts = AlertSystem()
