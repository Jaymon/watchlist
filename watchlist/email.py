from __future__ import unicode_literals
import os
from bs4 import BeautifulSoup

import sendgrid
from sendgrid.helpers.mail import Email as EmailAddr, Content, Mail, Personalization


class Email(object):

    subject = ""

    body_html = ""

    #body_text = ""
#     @property
#     def body_html(self):
#         return getattr(self, "_body_html", "")
# 
#     @body_html.setter
#     def body_html(self, body):
#         self._body_html = body_html

    @property
    def body_text(self):
        body = getattr(self, "_body_text", None)
        if body is None:
            body = ""
            html = self.body_html
            if html:
                body_texts = [text for text in BeautifulSoup(html, "html.parser").stripped_strings]
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
        mail.set_from(EmailAddr(self.from_email))
        mail.set_subject(self.subject)

        personalization = Personalization()
        personalization.add_to(EmailAddr(self.to_email))
        mail.add_personalization(personalization)

        mail.add_content(Content("text/plain", self.body_text))
        body_html = self.body_html
        if body_html:
            mail.add_content(Content("text/html", self.body_html))

        response = self.interface.client.mail.send.post(request_body=mail.get())
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


