from __future__ import unicode_literals
import os
import logging
import traceback

import sendgrid
from sendgrid.helpers.mail import Email as EmailAddr, Content, Mail, Personalization
from brow.utils import Soup


logger = logging.getLogger(__name__)


class Email(object):

    subject = ""

    body_html = ""

    @property
    def body_text(self):
        body = getattr(self, "_body_text", None)
        if body is None:
            body = ""
            html = self.body_html
            if html:
                body_texts = [text for text in Soup(html).stripped_strings]
                body = " ".join(body_texts)
        return body

    @body_text.setter
    def body_text(self, body):
        self._body_text = body

    @property
    def to_email(self):
        return os.environ["SENDGRID_EMAIL_TO"]

    @property
    def from_email(self):
        return os.environ["SENDGRID_EMAIL_FROM"]

    @property
    def interface(self):
        if not hasattr(self, '_interface'):
            self._interface = sendgrid.SendGridAPIClient(apikey=os.environ['SENDGRID_KEY'])
        return self._interface

    def send(self):
        response = None
        # https://github.com/sendgrid/sendgrid-python/blob/master/examples/helpers/mail/mail_example.py
        mail = Mail()
        mail.from_email = EmailAddr(self.from_email)
        mail.subject = self.subject

        personalization = Personalization()
        personalization.add_to(EmailAddr(self.to_email))
        mail.add_personalization(personalization)

        mail.add_content(Content("text/plain", self.body_text))
        body_html = self.body_html
        if body_html:
            mail.add_content(Content("text/html", self.body_html))

        # on success it returns 202
        # https://sendgrid.com/docs/API_Reference/api_v3.html
        response = self.interface.client.mail.send.post(request_body=mail.get())
        if response.status_code >= 400:
            raise SendError(response)

        return response

    def __str__(self):
        lines = [
            "FROM: {}".format(self.from_email),
            "TO: {}".format(self.to_email),
            "SUBJECT: {}".format(self.subject)
        ]

        lines.append("BODY HTML: {}".format(self.body_html))
        lines.append("BODY TEXT: {}".format(self.body_text))

        return "\n".join(lines)


class ErrorEmail(Email):
    def __init__(self, errors):
        subject = "{} errors raised".format(len(errors))
        logger.error(subject)

        self.subject = subject
        body = []

        for e, sys_exc_info in errors:
            exc_type, exc_value, exc_traceback = sys_exc_info
            stacktrace = traceback.format_exception(exc_type, exc_value, exc_traceback)
            body.append(str(e))
            body.append("".join(stacktrace))
            body.append("")

        self.body_text = "\n".join(body)



class SendError(Exception):
    def __init__(self, response):
        self.errno = response.status_code

        msg = []
        errors = response.body.get("errors", {})
        for err_d in errors:
            msg.append(err_d.get("message", ""))

        self.response = response
        super(SendError, self).__init__("\n\n".join(msg))

