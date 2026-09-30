import logging

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from ledger_api_client.ledger_models import EmailUserRO as EmailUser
from ledger_api_client.ledger_models import UsersInGroup
from ledger_api_client.utils import get_organisation
from rest_framework import serializers

from disturbance.components.main.models import MapLayer
from disturbance.components.organisations.models import ApiaryOrganisationAccessGroupMember
from disturbance.components.proposals.models import (
    ApiaryApproverGroupMember,
    ApiaryAssessorGroupMember,
    ApiaryReferralGroupMember,
)

from .request_cache import per_request_cache

logger = logging.getLogger(__name__)


def belongs_to(user, group_name):
    """
    Check if the user belongs to the given group.
    :param user:
    :param group_name:
    :return:
    """
    group = Group.objects.filter(name=group_name)
    if group.exists():
        return user.id in list(
            UsersInGroup.objects.filter(group_id=group.first().id).values_list("emailuser_id", flat=True)
        )
    else:
        return False


# NOTE: this is an env settings based group
def is_apiary_admin(request):
    return request.user.is_authenticated and (belongs_to(request.user, settings.APIARY_ADMIN_GROUP))


def is_in_organisation_contacts(request, organisation):
    return request.user.email in organisation.contacts.all().values_list("email", flat=True)


# NOTE: this is an env settings based group - consider renaming or replacing to avoid confusion
def is_approved_external_user(request):
    if belongs_to(request.user, settings.APPROVED_APIARY_EXTERNAL_USERS_GROUP):
        return True
    return False


def is_apiary_approver(request):
    return (
        request
        and request.user
        and (
            ApiaryApproverGroupMember.objects.filter(emailuser_id=request.user.id).exists() or request.user.is_superuser
        )
    )


def is_apiary_assessor(request):
    return (
        request
        and request.user
        and (
            ApiaryAssessorGroupMember.objects.filter(emailuser_id=request.user.id).exists() or request.user.is_superuser
        )
    )


def is_apiary_referrer(request):
    return (
        request
        and request.user
        and (
            ApiaryReferralGroupMember.objects.filter(emailuser_id=request.user.id).exists() or request.user.is_superuser
        )
    )


def is_apiary_org_request_assessor(request):
    return (
        request
        and request.user
        and (
            ApiaryOrganisationAccessGroupMember.objects.filter(emailuser_id=request.user.id).exists()
            or request.user.is_superuser
        )
    )


def is_internal(request):
    return (
        request
        and request.user
        and (
            request.user.is_superuser
            or is_apiary_admin(request)
            or is_approved_external_user(request)
            or is_apiary_approver(request)
            or is_apiary_assessor(request)
            or is_apiary_referrer(request)
            or is_apiary_org_request_assessor(request)
        )
    )


def get_all_officers():
    return EmailUser.objects.filter(groups__name="Disturbance Admin")


def is_authorised_to_modify(request, instance):
    authorised = True

    # print('1. Application', instance.application_type )
    # print("2. Apiary", str(instance.application_type) == "Apiary")

    # Getting Organisation is different in DAS and Apiary
    if str(instance.application_type) == "Apiary":
        # Get Organisation if in Apiary
        applicant = instance.relevant_applicant
        # print("3. Apiary Applicant", applicant)
    else:
        # Get Organisation if in DAS
        # There can only ever be one Organisation associated with an application so it is
        # ok to just pull the first element from organisation_set.
        applicant = instance.applicant.organisation.organisation_set.all()[0]
        # print("4. DAS Applicant", applicant)
    applicantIsIndividual = isinstance(applicant, EmailUser)
    # print('5. applicantIsIndividual', applicantIsIndividual)
    if is_internal(request):
        # the status must be 'with_assessor'
        authorised &= instance.processing_status == "with_assessor"
        # print("6. Internal with assessor", instance.processing_status == 'with_assessor')
        # the user must be an assessor for this type of application
        authorised &= instance.can_process()
        # print('7. Can process', instance.can_process())
    else:
        # the status of the application must be DRAFT for customer to modify
        authorised &= instance.processing_status == "draft"
        # print('8. Processing status draft', instance.processing_status == 'draft')
        if applicantIsIndividual:
            # it is an individual so the applicant and submitter must be the same
            authorised &= str(request.user.email) == str(instance.relevant_applicant)
            # print('9. Indiv submitter matches applicant', str(request.user.email) == str(instance.relevant_applicant))
        else:
            # the applicant is an organisation so make sure the submitter is in the organisation
            authorised &= is_in_organisation_contacts(request, instance.relevant_applicant)
            # print('10. Applicant is in Org', is_in_organisation_contacts(request, instance.relevant_applicant))

    # print('11. Authorised', authorised)
    if not authorised:
        raise serializers.ValidationError("You are not authorised to modify this application.")


def is_authorised_to_modify_draft(request, instance):
    authorised = True
    applicant = instance.relevant_applicant

    applicantIsIndividual = isinstance(applicant, EmailUser)
    if instance.processing_status == "draft":
        if request.user and request.user.is_authenticated:
            # the status of the application must be DRAFT for customer to modify
            # NOTE: internal users that are apiary assessors can also edit if in draft
            if is_internal(request):
                authorised &= is_apiary_assessor(request) or request.user.is_superuser
            elif applicantIsIndividual:
                # it is an individual so the applicant and submitter must be the same
                authorised &= str(request.user.email) == str(instance.relevant_applicant)
            else:
                # the applicant is an organisation so make sure the submitter is in the organisation
                authorised &= is_in_organisation_contacts(request, instance.relevant_applicant)
        else:
            authorised = False
    else:
        if is_internal(request):
            # the status must be 'with_assessor'
            # the user must be an assessor for this type of application
            authorised &= instance.can_assess()
        else:
            authorised = False

    if not authorised:
        raise serializers.ValidationError("You are not authorised to modify this application.")


def get_proxy_cache():
    proxy_cache_dumped_data = cache.get("utils_cache.get_proxy_cache()")
    proxy_cache_array = []
    if proxy_cache_dumped_data is None:
        proxy_cache_query = MapLayer.objects.all()

        for pr in proxy_cache_query:
            proxy_cache_array.append({"layer_name": pr.layer_name, "cache_expiry": pr.cache_expiry})

        cache.set("utils_cache.get_proxy_cache()", proxy_cache_array, 86400)
    else:
        proxy_cache_array = proxy_cache_dumped_data
    return proxy_cache_array


@per_request_cache
def is_internal_user(user):
    return (
        user
        and hasattr(user, "id")
        and (
            user.is_superuser
            or belongs_to(user, settings.APIARY_ADMIN_GROUP)
            or belongs_to(user, settings.APPROVED_APIARY_EXTERNAL_USERS_GROUP)
            or ApiaryApproverGroupMember.objects.filter(emailuser_id=user.id).exists()
            or ApiaryAssessorGroupMember.objects.filter(emailuser_id=user.id).exists()
            or ApiaryReferralGroupMember.objects.filter(emailuser_id=user.id).exists()
            or ApiaryOrganisationAccessGroupMember.objects.filter(emailuser_id=user.id).exists()
        )
    )


@per_request_cache
def get_cached_ledger_organisation(organisation_id):
    """
    This is safe because it's keyed by an integer.
    Multiple model instances calling this with ID 50
    will only trigger one network call.
    """
    return get_organisation(organisation_id).get("data")


def convert_external_url_to_internal_url(url):
    if not settings.SITE_SUBDOMAIN_INTERNAL_SUFFIX:
        return url

    if settings.SITE_SUBDOMAIN_INTERNAL_SUFFIX not in url:
        # Add the internal subdomain suffix to the url
        url = f"{settings.SITE_SUBDOMAIN_INTERNAL_SUFFIX}.{settings.SITE_DOMAIN}".join(
            url.split("." + settings.SITE_DOMAIN)
        )
    return url


def convert_internal_url_to_external_url(url):
    if not settings.SITE_SUBDOMAIN_INTERNAL_SUFFIX:
        return url

    if settings.SITE_SUBDOMAIN_INTERNAL_SUFFIX in url:
        # remove '-internal'. This email is for external submitters
        url = "".join(url.split(settings.SITE_SUBDOMAIN_INTERNAL_SUFFIX))
    return url
