import logging

import requests
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.utils.encoding import smart_bytes
from ledger_api_client.ledger_models import EmailUserRO as EmailUser

from disturbance.components.emails.emails import TemplateEmailBase

logger = logging.getLogger(__name__)

SYSTEM_NAME = settings.SYSTEM_NAME_SHORT + " Automated Message"


def get_sender_user():
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except EmailUser.DoesNotExist:
        EmailUser.objects.create(email=sender, password="")
        sender_user = EmailUser.objects.get(email__icontains=sender)
    return sender_user


class ApplicationFeeInvoiceApiarySendNotificationEmail(TemplateEmailBase):
    subject = "Your application fee invoice."
    html_template = "disturbance/emails/payments/apiary/send_application_fee_notification.html"
    txt_template = "disturbance/emails/payments/apiary/send_application_fee_notification.txt"


def send_application_fee_invoice_apiary_email_notification(request, proposal, invoice, recipients, is_test=False):
    email = ApplicationFeeInvoiceApiarySendNotificationEmail()

    context = {
        "lodgement_number": proposal.lodgement_number,
    }

    filename = f"invoice#{invoice.reference}.pdf"

    api_key = settings.LEDGER_API_KEY
    url = settings.LEDGER_API_URL + "/ledgergw/invoice-pdf/" + api_key + "/" + invoice.reference
    invoice_pdf = requests.get(url=url)
    attachment = (filename, invoice_pdf, "application/pdf")

    msg = email.send(recipients, attachments=[attachment], context=context)
    if is_test:
        return

    sender = get_sender_user()
    _log_proposal_email(msg, proposal, sender=sender)
    if proposal.applicant:
        _log_org_email(msg, proposal.applicant, proposal.submitter, sender=sender)


def _log_proposal_email(email_message, proposal, sender=None):
    from disturbance.components.proposals.models import ProposalLogEntry

    if isinstance(
        email_message,
        (
            EmailMultiAlternatives,
            EmailMessage,
        ),
    ):
        text = email_message.body
        subject = email_message.subject
        fromm = smart_bytes(sender) if sender else smart_bytes(email_message.from_email)
        # the to email is normally a list
        if isinstance(email_message.to, list):
            to = ",".join(email_message.to)
        else:
            to = smart_bytes(email_message.to)
        # we log the cc and bcc in the same cc field of the log entry as a ',' comma separated string
        all_ccs = []
        if email_message.cc:
            all_ccs += list(email_message.cc)
        if email_message.bcc:
            all_ccs += list(email_message.bcc)
        all_ccs = ",".join(all_ccs)

    else:
        text = smart_bytes(email_message)
        subject = ""
        to = proposal.submitter.email
        fromm = smart_bytes(sender) if sender else SYSTEM_NAME
        all_ccs = ""

    customer = proposal.submitter

    staff = sender

    kwargs = {
        "subject": subject,
        "text": text,
        "proposal": proposal,
        "customer": customer,
        "staff": staff,
        "to": to,
        "fromm": fromm,
        "cc": all_ccs,
    }

    email_entry = ProposalLogEntry.objects.create(**kwargs)

    return email_entry


def _log_org_email(email_message, organisation, customer, sender=None):
    from disturbance.components.organisations.models import OrganisationLogEntry

    if isinstance(
        email_message,
        (
            EmailMultiAlternatives,
            EmailMessage,
        ),
    ):
        text = email_message.body
        subject = email_message.subject
        fromm = smart_bytes(sender) if sender else smart_bytes(email_message.from_email)
        # the to email is normally a list
        if isinstance(email_message.to, list):
            to = ",".join(email_message.to)
        else:
            to = smart_bytes(email_message.to)
        # we log the cc and bcc in the same cc field of the log entry as a ',' comma separated string
        all_ccs = []
        if email_message.cc:
            all_ccs += list(email_message.cc)
        if email_message.bcc:
            all_ccs += list(email_message.bcc)
        all_ccs = ",".join(all_ccs)
    else:
        text = smart_bytes(email_message)
        subject = ""
        to = customer
        fromm = smart_bytes(sender) if sender else SYSTEM_NAME
        all_ccs = ""

    customer = customer

    staff = sender

    kwargs = {
        "subject": subject,
        "text": text,
        "organisation": organisation,
        "customer": customer,
        "staff": staff,
        "to": to,
        "fromm": fromm,
        "cc": all_ccs,
    }

    email_entry = OrganisationLogEntry.objects.create(**kwargs)

    return email_entry
