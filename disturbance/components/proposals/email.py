import logging

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.urls import reverse
from django.utils.encoding import smart_bytes
from ledger_api_client.ledger_models import EmailUserRO as EmailUser

from disturbance.components.emails.emails import TemplateEmailBase
from disturbance.helpers import convert_external_url_to_internal_url, convert_internal_url_to_external_url

logger = logging.getLogger(__name__)

SYSTEM_NAME = settings.SYSTEM_NAME_SHORT + " Automated Message"


def get_sender_user():
    sender = settings.DEFAULT_FROM_EMAIL
    try:
        sender_user = EmailUser.objects.get(email__icontains=sender)
    except:
        EmailUser.objects.create(email=sender, password="")
        sender_user = EmailUser.objects.get(email__icontains=sender)
    return sender_user


class ReferralSendNotificationEmail(TemplateEmailBase):
    subject = "A referral for a proposal has been sent to you."
    html_template = "disturbance/emails/proposals/send_referral_notification.html"
    txt_template = "disturbance/emails/proposals/send_referral_notification.txt"


class ReferralCompleteNotificationEmail(TemplateEmailBase):
    subject = "A referral for a proposal has been completed."
    html_template = "disturbance/emails/proposals/send_referral_complete_notification.html"
    txt_template = "disturbance/emails/proposals/send_referral_complete_notification.txt"


class ReferralRecallNotificationEmail(TemplateEmailBase):
    subject = "A referral for a proposal has been recalled."
    html_template = "disturbance/emails/proposals/send_referral_recall_notification.html"
    txt_template = "disturbance/emails/proposals/send_referral_recall_notification.txt"


class ProposalDeclineSendNotificationEmail(TemplateEmailBase):
    subject = "Your Proposal has been declined."
    html_template = "disturbance/emails/proposals/send_decline_notification.html"
    txt_template = "disturbance/emails/proposals/send_decline_notification.txt"


class ProposalApprovalSendNotificationEmail(TemplateEmailBase):
    subject = "Your Proposal has been approved."
    html_template = "disturbance/emails/proposals/send_approval_notification.html"
    txt_template = "disturbance/emails/proposals/send_approval_notification.txt"


class AmendmentRequestSendNotificationEmail(TemplateEmailBase):
    subject = "An amendment to your Proposal is required."
    html_template = "disturbance/emails/proposals/send_amendment_notification.html"
    txt_template = "disturbance/emails/proposals/send_amendment_notification.txt"


class SubmitSendNotificationEmail(TemplateEmailBase):
    subject = "A new Proposal has been submitted."
    html_template = "disturbance/emails/proposals/send_submit_notification.html"
    txt_template = "disturbance/emails/proposals/send_submit_notification.txt"


class AssessmentReminderSendNotificationEmail(TemplateEmailBase):
    subject = "A Proposal is waiting for assessment."
    html_template = "disturbance/emails/proposals/send_assessment_reminder_notification.html"
    txt_template = "disturbance/emails/proposals/send_assessment_reminder_notification.txt"


class ExternalSubmitSendNotificationEmail(TemplateEmailBase):
    subject = "A new Proposal has been submitted."
    html_template = "disturbance/emails/proposals/send_external_submit_notification.html"
    txt_template = "disturbance/emails/proposals/send_external_submit_notification.txt"


class ApproverDeclineSendNotificationEmail(TemplateEmailBase):
    subject = "A Proposal has been recommended for decline."
    html_template = "disturbance/emails/proposals/send_approver_decline_notification.html"
    txt_template = "disturbance/emails/proposals/send_approver_decline_notification.txt"


class ApproverApproveSendNotificationEmail(TemplateEmailBase):
    subject = "A Proposal has been recommended for approval."
    html_template = "disturbance/emails/proposals/send_approver_approve_notification.html"
    txt_template = "disturbance/emails/proposals/send_approver_approve_notification.txt"


class ApproverSendBackNotificationEmail(TemplateEmailBase):
    subject = "A Proposal has been sent back by approver."
    html_template = "disturbance/emails/proposals/send_approver_sendback_notification.html"
    txt_template = "disturbance/emails/proposals/send_approver_sendback_notification.txt"


## Apiary Templates
class ApiaryReferralSendNotificationEmail(TemplateEmailBase):
    subject = "A referral for an application has been sent to you."
    html_template = "disturbance/emails/proposals/apiary_send_referral_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_referral_notification.txt"


class ApiaryReferralCompleteNotificationEmail(TemplateEmailBase):
    subject = "A referral for an application has been completed."
    html_template = "disturbance/emails/proposals/apiary_send_referral_complete_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_referral_complete_notification.txt"


class ApiaryReferralRecallNotificationEmail(TemplateEmailBase):
    subject = "A referral for an application has been recalled."
    html_template = "disturbance/emails/proposals/apiary_send_referral_recall_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_referral_recall_notification.txt"


class ApiaryProposalDeclineSendNotificationEmail(TemplateEmailBase):
    subject = "Your Application has been declined."
    html_template = "disturbance/emails/proposals/apiary_send_decline_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_decline_notification.txt"


class ApiaryProposalApprovalSiteTransferSendNotificationEmail(TemplateEmailBase):
    subject = "Your Licence has been issued."
    html_template = "disturbance/emails/proposals/apiary_send_approval_site_transfer_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_approval_site_transfer_notification.txt"


class ApiaryProposalApprovalSendNotificationEmail(TemplateEmailBase):
    subject = "Your Application has been approved."
    html_template = "disturbance/emails/proposals/apiary_send_approval_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_approval_notification.txt"


class ApiaryAmendmentRequestSendNotificationEmail(TemplateEmailBase):
    subject = "An amendment to your Application is required."
    html_template = "disturbance/emails/proposals/apiary_send_amendment_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_amendment_notification.txt"


class ApiarySubmitSendNotificationEmail(TemplateEmailBase):
    subject = "A new Application has been submitted."
    html_template = "disturbance/emails/proposals/apiary_send_submit_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_submit_notification.txt"


class ApiaryAssessmentReminderSendNotificationEmail(TemplateEmailBase):
    subject = "An Application is waiting for assessment."
    html_template = "disturbance/emails/proposals/apiary_send_assessment_reminder_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_assessment_reminder_notification.txt"


class ApiaryExternalSubmitSendNotificationEmail(TemplateEmailBase):
    subject = "A new Application has been submitted."
    html_template = "disturbance/emails/proposals/apiary_send_external_submit_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_external_submit_notification.txt"


class ApiaryApproverDeclineSendNotificationEmail(TemplateEmailBase):
    subject = "An Application has been recommended for decline."
    html_template = "disturbance/emails/proposals/apiary_send_approver_decline_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_approver_decline_notification.txt"


class ApiaryApproverApproveSendNotificationEmail(TemplateEmailBase):
    subject = "An Application has been recommended for approval."
    html_template = "disturbance/emails/proposals/apiary_send_approver_approve_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_approver_approve_notification.txt"


class ApiaryApproverSendBackNotificationEmail(TemplateEmailBase):
    subject = "An Application has been sent back by approver."
    html_template = "disturbance/emails/proposals/apiary_send_approver_sendback_notification.html"
    txt_template = "disturbance/emails/proposals/apiary_send_approver_sendback_notification.txt"


def send_referral_email_notification(referral, request, reminder=False):
    """Recipient: Always internal users"""
    email = ReferralSendNotificationEmail()

    url = request.build_absolute_uri(
        reverse("internal-referral-detail", kwargs={"proposal_pk": referral.proposal.id, "referral_pk": referral.id})
    )

    url = convert_external_url_to_internal_url(url)

    context = {"proposal": referral.proposal, "url": url, "reminder": reminder, "comments": referral.text}

    msg = email.send(referral.referral.email, context=context)
    sender = get_sender_user()
    _log_proposal_referral_email(msg, referral, sender=sender)
    if referral.proposal.applicant:
        _log_org_email(msg, referral.proposal.applicant, referral.referral, sender=sender)


def send_referral_recall_email_notification(referral, request):
    """Recipient: Always internal users"""
    email = ReferralRecallNotificationEmail()
    url = request.build_absolute_uri(
        reverse("internal-referral-detail", kwargs={"proposal_pk": referral.proposal.id, "referral_pk": referral.id})
    )

    url = convert_external_url_to_internal_url(url)

    context = {
        "proposal": referral.proposal,
        "url": url,
    }

    msg = email.send(referral.referral.email, context=context)
    sender = get_sender_user()
    _log_proposal_referral_email(msg, referral, sender=sender)
    if referral.proposal.applicant:
        _log_org_email(msg, referral.proposal.applicant, referral.referral, sender=sender)


def send_referral_complete_email_notification(referral, request):
    """Recipient: Always internal users"""
    email = ReferralCompleteNotificationEmail()

    url = request.build_absolute_uri(reverse("internal-proposal-detail", kwargs={"proposal_pk": referral.proposal.id}))

    url = convert_external_url_to_internal_url(url)

    context = {"proposal": referral.proposal, "url": url, "referral_comments": referral.referral_text}

    msg = email.send(referral.sent_by.email, context=context)
    sender = get_sender_user()
    _log_proposal_referral_email(msg, referral, sender=sender)
    if referral.proposal.applicant:
        _log_org_email(msg, referral.proposal.applicant, referral.referral, sender=sender)


def send_apiary_referral_email_notification(referral, recipients, request, reminder=False):
    """Recipient: Always internal users"""
    email = ApiaryReferralSendNotificationEmail()

    url = request.build_absolute_uri(
        reverse("internal-referral-detail", kwargs={"proposal_pk": referral.proposal.id, "referral_pk": referral.id})
    )

    url = convert_external_url_to_internal_url(url)

    context = {"proposal": referral.proposal, "url": url, "reminder": reminder, "comments": referral.text}

    msg = email.send(recipients, context=context)
    sender = get_sender_user()
    _log_proposal_referral_email(msg, referral, sender=sender)
    if referral.proposal.applicant:
        _log_org_email(email_message=msg, organisation=referral.proposal.applicant, customer=None, sender=sender)


def send_apiary_referral_complete_email_notification(referral, request, completed_by):
    """Recipient: Always internal users"""
    email = ApiaryReferralCompleteNotificationEmail()
    email.subject = referral.sent_by.email + ": " + email.subject

    url = request.build_absolute_uri(reverse("internal-proposal-detail", kwargs={"proposal_pk": referral.proposal.id}))

    url = convert_external_url_to_internal_url(url)

    context = {
        "completed_by": completed_by,
        "proposal": referral.proposal,
        "url": url,
        "referral_comments": referral.referral_text,
    }

    msg = email.send(referral.sent_by.email, context=context)
    sender = get_sender_user()
    _log_proposal_referral_email(msg, referral, sender=sender)

    if referral.proposal.applicant:
        _log_org_email(email_message=msg, organisation=referral.proposal.applicant, customer=None, sender=sender)


def send_amendment_email_notification(amendment_request, request, proposal):
    """Recipient: Always external users"""
    if proposal.apiary_group_application_type:
        email = ApiaryAmendmentRequestSendNotificationEmail()
    else:
        email = AmendmentRequestSendNotificationEmail()

    reason = amendment_request.reason.reason

    url = request.build_absolute_uri(reverse("external-proposal-detail", kwargs={"proposal_pk": proposal.id}))

    url = convert_internal_url_to_external_url(url)

    attachments = []
    if amendment_request.amendment_request_documents:
        for doc in amendment_request.amendment_request_documents.all():
            file_name = doc.name
            attachment = (file_name, doc._file.file.read())
            attachments.append(attachment)

    context = {"proposal": proposal, "reason": reason, "amendment_request_text": amendment_request.text, "url": url}

    all_ccs = []
    if (
        proposal.applicant
        and proposal.relevant_applicant.email != proposal.submitter.email
        and proposal.relevant_applicant.email
    ):
        cc_list = proposal.relevant_applicant.email
        if cc_list:
            all_ccs = [cc_list]

    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context, attachments=attachments)
    sender = get_sender_user()
    _log_proposal_email(msg, proposal, sender=sender)
    if proposal.applicant:
        _log_org_email(msg, proposal.applicant, proposal.submitter, sender=sender)


def send_submit_email_notification(request, proposal):
    """Recipient: Always internal users"""
    if proposal.apiary_group_application_type:
        email = ApiarySubmitSendNotificationEmail()
    else:
        email = SubmitSendNotificationEmail()

    url = request.build_absolute_uri(reverse("internal-proposal-detail", kwargs={"proposal_pk": proposal.id}))

    url = convert_external_url_to_internal_url(url)

    context = {"proposal": proposal, "url": url}

    msg = email.send(proposal.assessor_recipients, context=context)
    sender = get_sender_user()
    _log_proposal_email(msg, proposal, sender=sender)
    if proposal.applicant:
        _log_org_email(msg, proposal.applicant, proposal.submitter, sender=sender)
    return msg


def send_external_submit_email_notification(request, proposal):
    """Recipient: Always external users"""
    if proposal.apiary_group_application_type:
        email = ApiaryExternalSubmitSendNotificationEmail()
    else:
        email = ExternalSubmitSendNotificationEmail()
    url = request.build_absolute_uri(reverse("external-proposal-detail", kwargs={"proposal_pk": proposal.id}))

    url = convert_internal_url_to_external_url(url)

    context = {"proposal": proposal, "submitter": proposal.submitter.get_full_name(), "url": url}

    all_ccs = []
    if (
        proposal.applicant
        and proposal.relevant_applicant.email != proposal.submitter.email
        and proposal.relevant_applicant.email
    ):
        cc_list = proposal.relevant_applicant.email
        if cc_list:
            all_ccs = [cc_list]

    msg = email.send(proposal.submitter.email, cc=all_ccs, context=context)
    sender = get_sender_user()
    _log_proposal_email(msg, proposal, sender=sender)
    # Don't log organisation if application submitted on behalf of an individual
    if proposal.applicant:
        _log_org_email(msg, proposal.applicant, proposal.submitter, sender=sender)
    return msg


# send email when Proposal is 'proposed to decline' by assessor.
def send_approver_decline_email_notification(reason, request, proposal):
    """Recipient: Always internal users"""
    if proposal.apiary_group_application_type:
        email = ApiaryApproverDeclineSendNotificationEmail()
    else:
        email = ApproverDeclineSendNotificationEmail()
    url = request.build_absolute_uri(reverse("internal-proposal-detail", kwargs={"proposal_pk": proposal.id}))

    url = convert_external_url_to_internal_url(url)

    context = {"proposal": proposal, "reason": reason, "url": url}

    msg = email.send(proposal.approver_recipients, context=context)
    sender = get_sender_user()
    _log_proposal_email(msg, proposal, sender=sender)
    if proposal.applicant:
        _log_org_email(msg, proposal.applicant, proposal.submitter, sender=sender)


def send_approver_approve_email_notification(request, proposal):
    """Recipient: Always internal users"""
    if proposal.apiary_group_application_type:
        email = ApiaryApproverApproveSendNotificationEmail()
    else:
        email = ApproverApproveSendNotificationEmail()

    url = request.build_absolute_uri(reverse("internal-proposal-detail", kwargs={"proposal_pk": proposal.id}))

    url = convert_external_url_to_internal_url(url)

    context = {
        "start_date": proposal.proposed_issuance_approval.get("start_date"),
        "expiry_date": proposal.proposed_issuance_approval.get("expiry_date"),
        "details": proposal.proposed_issuance_approval.get("details"),
        "proposal": proposal,
        "url": url,
    }

    msg = email.send(proposal.approver_recipients, context=context)
    sender = get_sender_user()
    _log_proposal_email(msg, proposal, sender=sender)
    if proposal.applicant:
        _log_org_email(msg, proposal.applicant, proposal.submitter, sender=sender)


def send_proposal_decline_email_notification(proposal, request, proposal_decline):
    """Recipient: Always external users"""
    if proposal.apiary_group_application_type:
        email = ApiaryProposalDeclineSendNotificationEmail()
    else:
        email = ProposalDeclineSendNotificationEmail()

    context = {
        "proposal": proposal,
    }
    cc_list = proposal_decline.cc_email
    all_ccs = []
    if cc_list:
        all_ccs = cc_list.split(",")

    if (
        proposal.applicant
        and proposal.relevant_applicant.email != proposal.submitter.email
        and proposal.relevant_applicant.email
    ):
        all_ccs.append(proposal.relevant_applicant.email)

    msg = email.send(proposal.submitter.email, bcc=all_ccs, context=context)
    sender = get_sender_user()
    _log_proposal_email(msg, proposal, sender=sender)
    if proposal.applicant:
        _log_org_email(msg, proposal.applicant, proposal.submitter, sender=sender)


def send_proposal_approver_sendback_email_notification(request, proposal):
    """Recipient: Always internal users"""
    if proposal.apiary_group_application_type:
        email = ApiaryApproverSendBackNotificationEmail()
    else:
        email = ApproverSendBackNotificationEmail()

    url = request.build_absolute_uri(reverse("internal-proposal-detail", kwargs={"proposal_pk": proposal.id}))

    url = convert_external_url_to_internal_url(url)

    context = {"proposal": proposal, "url": url, "approver_comment": proposal.approver_comment}

    msg = email.send(proposal.assessor_recipients, context=context)
    sender = get_sender_user()
    _log_proposal_email(msg, proposal, sender=sender)
    if proposal.applicant:
        _log_org_email(msg, proposal.applicant, proposal.submitter, sender=sender)


def send_proposal_approval_email_notification(proposal, request):
    """Recipient: Always external users"""
    if proposal.apiary_group_application_type:
        email = ApiaryProposalApprovalSendNotificationEmail()
    else:
        email = ProposalApprovalSendNotificationEmail()
    if proposal.approval.reissued:
        email.subject = "Your Approval has been reissued."

    context = {
        "proposal": proposal,
    }
    cc_list = proposal.proposed_issuance_approval["cc_email"]
    all_ccs = []
    if cc_list:
        all_ccs = cc_list.split(",")
    if (
        proposal.applicant
        and proposal.relevant_applicant.email != proposal.submitter.email
        and proposal.relevant_applicant.email
    ):
        all_ccs.append(proposal.relevant_applicant.email)

    licence_document = proposal.approval.licence_document._file
    if licence_document is not None:
        file_name = proposal.approval.licence_document.name
        attachment = (file_name, licence_document.file.read(), "application/pdf")
        attachment = [attachment]
    else:
        attachment = []

    msg = email.send(proposal.submitter.email, bcc=all_ccs, attachments=attachment, context=context)
    sender = get_sender_user()
    _log_proposal_email(msg, proposal, sender=sender)
    if proposal.applicant:
        _log_org_email(msg, proposal.applicant, proposal.submitter, sender=sender)


def send_site_transfer_approval_email_notification(proposal, request, approval):
    """Recipient: Always external users"""
    email = ApiaryProposalApprovalSiteTransferSendNotificationEmail()
    if approval.reissued:
        email.subject = "Your Licence has been reissued."

    context = {
        "approval": approval,
        "proposal": proposal,
    }
    cc_list = proposal.proposed_issuance_approval["cc_email"]
    all_ccs = []
    if cc_list:
        all_ccs = cc_list.split(",")

    relevant_applicant_email = approval.relevant_applicant_email

    licence_document = approval.licence_document._file
    if licence_document is not None:
        file_name = approval.licence_document.name
        attachment = (file_name, licence_document.file.read(), "application/pdf")
        attachment = [attachment]
    else:
        attachment = []

    if relevant_applicant_email:
        msg = email.send(approval.relevant_applicant_email, bcc=all_ccs, attachments=attachment, context=context)
        sender = get_sender_user()
        _log_proposal_email(msg, proposal, sender=sender)
        if (
            approval.applicant
            and approval.applicant.organisation
            and hasattr(approval.applicant.organisation, "email")
            and approval.applicant.organisation.email
        ):
            _log_org_email(msg, approval.applicant, proposal.submitter, sender=sender)


def send_assessment_reminder_email_notification(proposal):
    """Recipient: Always internal users"""
    if proposal.apiary_group_application_type:
        email = ApiaryAssessmentReminderSendNotificationEmail()
    else:
        email = AssessmentReminderSendNotificationEmail()

    url = settings.SITE_URL if settings.SITE_URL else ""
    url += reverse("internal-proposal-detail", kwargs={"proposal_pk": proposal.id})

    url = convert_external_url_to_internal_url(url)

    context = {"proposal": proposal, "url": url}

    msg = email.send(proposal.assessor_recipients, context=context)
    sender = get_sender_user()
    _log_proposal_email(msg, proposal, sender=sender)
    if proposal.applicant:
        _log_org_email(msg, proposal.applicant, proposal.submitter, sender=sender)
    return msg


def _log_proposal_referral_email(email_message, referral, sender=None):
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
        to = referral.proposal.relevant_applicant.email if referral.proposal.relevant_applicant.email else ""
        fromm = smart_bytes(sender) if sender else SYSTEM_NAME
        all_ccs = ""

    customer = referral.referral

    staff = sender

    kwargs = {
        "subject": subject,
        "text": text,
        "proposal": referral.proposal,
        "customer": customer,
        "staff": staff,
        "to": to,
        "fromm": fromm,
        "cc": all_ccs,
    }

    email_entry = ProposalLogEntry.objects.create(**kwargs)

    return email_entry


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
