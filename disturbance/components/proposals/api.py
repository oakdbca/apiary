import json
import logging
import re
from datetime import datetime

import pytz
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q, Value
from django.db.models.functions import Concat
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from ledger_api_client.ledger_models import EmailUserRO as EmailUser
from rest_framework import mixins, serializers, status, views, viewsets
from rest_framework.decorators import action, renderer_classes
from rest_framework.exceptions import NotFound
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework_datatables.filters import DatatablesFilterBackend
from rest_framework_datatables.pagination import DatatablesPageNumberPagination

from disturbance.components.approvals.email import (
    send_contact_licence_holder_email,
    send_on_site_notification_email,
)
from disturbance.components.approvals.models import ApiarySiteOnApproval, Approval
from disturbance.components.approvals.permissions import (
    InternalApprovalPermission,
)
from disturbance.components.approvals.serializers import ApprovalLogEntrySerializer
from disturbance.components.approvals.utils import (
    annotate_apiary_site_on_approval_geometry,
    annotate_apiary_site_on_approval_min_geometry,
)
from disturbance.components.compliances.models import Compliance
from disturbance.components.main.decorators import basic_exception_handler, timeit
from disturbance.components.main.models import ApplicationType
from disturbance.components.main.process_document import process_generic_document
from disturbance.components.main.utils import (
    get_qs_all_apiary_sites,
    get_qs_approval,
    get_qs_current_site,
    get_qs_denied_site,
    get_qs_not_to_be_reissued_site,
    get_qs_pending_site,
    get_qs_proposal,
    get_qs_suspended_site,
    get_qs_vacant_site,
    get_template_group,
    remove_html_tags,
)
from disturbance.components.organisations.models import Organisation
from disturbance.components.proposals.models import (
    AmendmentReason,
    AmendmentRequest,
    AmendmentRequestDocument,
    ApiaryChecklistAnswer,
    ApiaryChecklistQuestion,
    ApiaryReferral,
    ApiaryReferralGroup,
    ApiarySite,
    ApiarySiteFee,
    ApiarySiteOnProposal,
    DeedPollDocument,
    OnSiteInformation,
    Proposal,
    ProposalApiary,
    ProposalApiaryTemporaryUse,
    ProposalRequirement,
    ProposalStandardRequirement,
    ProposalType,
    ProposalUserAction,
    PublicLiabilityInsuranceDocument,
    Referral,
    SiteTransferApiarySite,
    SupportingApplicationDocument,
    TemporaryUseApiarySite,
    search_reference,
    searchKeyWords,
)
from disturbance.components.proposals.permissions import (
    InternalProposalPermission,
    ProposalApproverPermission,
    ProposalAssessorPermission,
    ProposalReferrerPermission,
)
from disturbance.components.proposals.serializers import (
    AmendmentRequestDisplaySerializer,
    AmendmentRequestSerializer,
    DTReferralSerializer,
    ListProposalSerializer,
    PropedDeclineSerializer,
    ProposalLogEntrySerializer,
    ProposalRequirementSerializer,
    ProposalSerializer,
    ProposalStandardRequirementSerializer,
    ProposalUserActionSerializer,
    ProposalWrapperSerializer,
    ProposedApprovalSerializer,
    ReferralSerializer,
    ReferralWrapperSerializer,
    SaveProposalRegionSerializer,
    SaveProposalSerializer,
    SearchKeywordSerializer,
    SearchReferenceSerializer,
    SendReferralSerializer,
)
from disturbance.components.proposals.serializers_apiary import (
    ApiaryInternalProposalSerializer,
    ApiaryReferralGroupSerializer,
    ApiaryReferralSerializer,
    ApiarySiteFeeSerializer,
    ApiarySiteSerializer,
    CreateProposalApiarySiteTransferSerializer,
    DTApiaryReferralSerializer,
    FullApiaryReferralSerializer,
    OnSiteInformationSerializer,
    ProposalApiarySerializer,
    ProposalApiaryTemporaryUseSerializer,
    ProposalApiaryTypeSerializer,
    ProposalHistorySerializer,
    SaveProposalApiarySerializer,
    SendApiaryReferralSerializer,
    TemporaryUseApiarySiteSerializer,
    UserApiaryApprovalSerializer,
)
from disturbance.components.proposals.utils import (
    annotate_apiary_site_on_proposal_draft_geometry,
    annotate_apiary_site_on_proposal_minimal_geometry,
    annotate_apiary_site_on_proposal_processed_geometry,
    annotate_apiary_site_on_proposal_processed_minimal_geometry,
    annotate_apiary_site_on_proposal_vacant_draft_minimal_geometry,
    annotate_site_transfer_apiary_site,
    annotate_temporary_use_apiary_site,
    save_apiary_assessor_data,
    save_assessor_data,
    save_proponent_data,
)
from disturbance.helpers import is_authorised_to_modify_draft, is_internal
from disturbance.settings import (
    SITE_STATUS_CURRENT,
    SITE_STATUS_DENIED,
    SITE_STATUS_DRAFT,
    SITE_STATUS_NOT_TO_BE_REISSUED,
    TIME_ZONE,
)

logger = logging.getLogger(__name__)


class ProposalFilterBackend(DatatablesFilterBackend):
    """
    Custom filters
    """

    def filter_queryset(self, request, queryset, view):
        search_text = request.GET.get("search[value]", "")
        total_count = queryset.count()

        try:
            super_queryset = super().filter_queryset(request, queryset, view)
        except Exception as e:
            print(e)

        if search_text:
            search_text = search_text.lower()

            email_user_ids = list(
                EmailUser.objects.annotate(
                    full_name=Concat("first_name", Value(" "), "last_name"),
                    legal_full_name=Concat("legal_first_name", Value(" "), "legal_last_name"),
                )
                .filter(
                    Q(email__icontains=search_text)
                    | Q(first_name__icontains=search_text)
                    | Q(last_name__icontains=search_text)
                    | Q(full_name__icontains=search_text)
                    | Q(legal_first_name__icontains=search_text)
                    | Q(legal_last_name__icontains=search_text)
                    | Q(legal_full_name__icontains=search_text)
                )
                .values_list("id", flat=True)
            )

            organisation_ids = list(Organisation.objects.filter(property_cache__name__icontains=search_text))

            search_text_app_ids = Proposal.objects.values("id").filter(
                Q(proxy_applicant_id__in=email_user_ids)
                | Q(submitter_id__in=email_user_ids)
                | Q(assigned_officer_id__in=email_user_ids)
                | Q(applicant_id__in=organisation_ids)
            )

            queryset = queryset.filter(id__in=search_text_app_ids).distinct() | super_queryset

        application_type = request.GET.get("application_type")
        if application_type and not application_type.lower() == "all":
            if queryset.model is Referral or queryset.model is Compliance:
                queryset = queryset.filter(proposal__application_type__name=application_type)
            else:
                queryset = queryset.filter(application_type__name=application_type)
        proposal_activity = request.GET.get("proposal_activity")
        if proposal_activity and not proposal_activity.lower() == "all":
            if queryset.model is Referral or queryset.model is Compliance:
                queryset = queryset.filter(proposal__activity=proposal_activity)
            else:
                queryset = queryset.filter(activity=proposal_activity)
        proposal_status = request.GET.get("proposal_status")
        if proposal_status and not proposal_status.lower() == "all":
            if queryset.model is Referral or queryset.model is Compliance:
                queryset = queryset.filter(proposal__processing_status=proposal_status)
            else:
                queryset = queryset.filter(processing_status=proposal_status)

        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        if queryset.model is Proposal:
            if date_from:
                queryset = queryset.filter(lodgement_date__gte=date_from)

            if date_to:
                queryset = queryset.filter(lodgement_date__lte=date_to)

        elif queryset.model is Compliance:
            if date_from:
                queryset = queryset.filter(due_date__gte=date_from)

            if date_to:
                queryset = queryset.filter(due_date__lte=date_to)

            if request.GET.get("processing_status"):
                queryset = queryset.filter(processing_status__icontains=request.GET.get("processing_status"))

            if request.GET.get("customer_status"):
                queryset = queryset.filter(customer_status__icontains=request.GET.get("customer_status"))

        elif queryset.model is Referral:
            if date_from:
                queryset = queryset.filter(proposal__lodgement_date__gte=date_from)

            if date_to:
                queryset = queryset.filter(proposal__lodgement_date__lte=date_to)

        fields = self.get_fields(request)
        ordering = self.get_ordering(request, view, fields)
        if len(ordering):
            queryset = queryset.order_by(*ordering)

        setattr(view, "_datatables_total_count", total_count)
        return queryset


class ProposalPaginatedViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = (ProposalFilterBackend,)
    pagination_class = DatatablesPageNumberPagination
    queryset = Proposal.objects.none()
    serializer_class = ListProposalSerializer
    search_fields = [
        "lodgement_number",
    ]
    page_size = 10

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            return Proposal.objects.exclude(processing_status="hidden").select_related(
                "application_type", "applicant", "approval", "previous_application"
            )
        elif user.is_authenticated:
            user_orgs = [org.id for org in user.disturbance_organisations.all()]
            qs = Proposal.objects.exclude(processing_status="hidden").filter(
                Q(applicant_id__in=user_orgs) | Q(submitter=user) | Q(proxy_applicant=user)
            )
            return qs
        return Proposal.objects.none()

    @action(
        detail=False,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def proposals_internal(self, request, *args, **kwargs):
        """
        Used by the internal dashboard

        http://localhost:8499/api/proposal_paginated/proposal_paginated_internal/?format=datatables&draw=1&length=2
        """
        template_group = get_template_group(request)
        qs = self.get_queryset().filter(
            application_type__name__in=[
                ApplicationType.APIARY,
                ApplicationType.SITE_TRANSFER,
                ApplicationType.TEMPORARY_USE,
            ]
        )
        qs = self.filter_queryset(qs)
        # on the internal organisations dashboard, filter the Proposal/Approval/Compliance datatables by applicant/organisation
        applicant_id = request.GET.get("org_id")
        if applicant_id:
            qs = qs.filter(applicant_id=applicant_id)

        result_page = self.paginator.paginate_queryset(qs, request)
        serializer = ListProposalSerializer(
            result_page,
            context={"request": request, "template_group": template_group},
            many=True,
        )
        return self.paginator.get_paginated_response(serializer.data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def referrals_internal(self, request, *args, **kwargs):
        """
        Used by the internal dashboard

        http://localhost:8499/api/proposal_paginated/referrals_internal/?format=datatables&draw=1&length=2
        """
        template_group = get_template_group(request)

        qs = (
            Referral.objects.filter(apiary_referral__referral_group__members=request.user)
            if is_internal(self.request)
            else Referral.objects.none()
        )

        qs = self.filter_queryset(qs)

        result_page = self.paginator.paginate_queryset(qs, request)
        serializer = DTReferralSerializer(
            result_page,
            context={"request": request, "template_group": template_group},
            many=True,
        )
        return self.paginator.get_paginated_response(serializer.data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    def proposals_external(self, request, *args, **kwargs):
        """
        Used by the external dashboard

        http://localhost:8499/api/proposal_paginated/proposal_paginated_external/?format=datatables&draw=1&length=2
        """
        template_group = get_template_group(request)
        qs = (
            self.get_queryset()
            .filter(
                application_type__name__in=[
                    ApplicationType.APIARY,
                    ApplicationType.SITE_TRANSFER,
                    ApplicationType.TEMPORARY_USE,
                ]
            )
            .exclude(processing_status=Proposal.PROCESSING_STATUS_DISCARDED)
        )
        qs = self.filter_queryset(qs)

        # on the internal organisations dashboard, filter the Proposal/Approval/Compliance datatables by applicant/organisation
        applicant_id = request.GET.get("org_id")
        if applicant_id:
            qs = qs.filter(applicant_id=applicant_id)

        result_page = self.paginator.paginate_queryset(qs, request)
        serializer = ListProposalSerializer(
            result_page,
            context={"request": request, "template_group": template_group},
            many=True,
        )
        return self.paginator.get_paginated_response(serializer.data)


class OnSiteInformationViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = OnSiteInformation.objects.filter(datetime_deleted=None)
    serializer_class = OnSiteInformationSerializer

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            return OnSiteInformation.objects.filter(datetime_deleted=None)
        elif user.is_authenticated:
            user_orgs = [org.id for org in self.request.user.disturbance_organisations.all()]
            qs = OnSiteInformation.objects.filter(datetime_deleted=None).filter(
                Q(apiary_site_on_approval__approval__applicant_id__in=user_orgs)
                | Q(apiary_site_on_approval__approval__current_proposal__submitter_id=user.id)
                | Q(apiary_site_on_approval__approval__current_proposal__proxy_applicant_id=user.id)
            )
            return qs
        return OnSiteInformation.objects.none()

    @staticmethod
    def sanitize_date(data_dict, property_name):
        if (
            property_name not in data_dict
            or not data_dict[property_name]
            or "invalid" in data_dict[property_name].lower()
        ):
            # There isn't 'property_name' in the data received, or
            # the value in it is False, or
            # the value has a substring 'invalid' in it
            # Add the property if needed and set the value to None
            data_dict[property_name] = None
        else:
            # There is a 'property_name' in the data received
            m = re.match(r"^(\d{2}).(\d{2}).(\d{4})$", data_dict[property_name])
            if m:
                year = m.group(3)
                if int(m.group(2)) > 12:
                    # Date format is 'MM/DD/YYYY' probably
                    month = m.group(1)
                    day = m.group(2)
                else:
                    # Date format is 'DD/MM/YYYY' probably
                    month = m.group(2)
                    day = m.group(1)

                data_dict[property_name] = year + "-" + month + "-" + day

        return data_dict

    @basic_exception_handler
    def destroy(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()

            now = datetime.now(pytz.timezone(TIME_ZONE))
            serializer = OnSiteInformationSerializer(instance, {"datetime_deleted": now}, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response({})

    def _construct_data(self, request):
        request_data = request.data

        apiary_site_id = request.data.get("apiary_site_id")
        approval_id = request.data.get("approval_id")

        if not apiary_site_id:
            raise serializers.ValidationError("Please provide Apiary Site.")

        if is_internal(self.request):
            approval_queryset = Approval.objects.filter(id=approval_id)
            apiary_site = (
                ApiarySite.objects.filter(id=apiary_site_id).filter(approval_set__in=approval_queryset).first()
            )
            approval = approval_queryset.first()
        else:
            user_orgs = [org.id for org in self.request.user.disturbance_organisations.all()]
            approval_queryset = Approval.objects.filter(id=approval_id).filter(
                Q(applicant_id__in=user_orgs) | Q(proxy_applicant_id=self.request.user.id)
            )
            apiary_site = (
                ApiarySite.objects.filter(id=apiary_site_id).filter(approval_set__in=approval_queryset).first()
            )
            approval = approval_queryset.first()

        if not apiary_site:
            if is_internal(self.request):
                raise serializers.ValidationError("Apiary Site does not exist on Approval.")
            else:
                raise serializers.ValidationError(
                    "User not authorised to add site information to specified Apiary Site."
                )

        if not approval:
            if is_internal(self.request):
                raise serializers.ValidationError("Approval does not exist.")
            else:
                raise serializers.ValidationError("User not authorised to add site information to specified Approval.")

        apiary_site_on_approval = ApiarySiteOnApproval.objects.get(apiary_site=apiary_site, approval=approval)
        request_data["apiary_site_on_approval_id"] = apiary_site_on_approval.id

        self.sanitize_date(request_data, "period_from")
        self.sanitize_date(request_data, "period_to")

        return request_data

    @basic_exception_handler
    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            logger.info(f"Updating OnSiteInformation: [{instance}]")

            request_data = self._construct_data(request)

            serializer = OnSiteInformationSerializer(instance, data=request_data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            logger.info(f"OnSiteInformation updated: [{serializer.data}]")

        sender = request.user
        try:
            send_on_site_notification_email(request_data, sender, update=True)
        except Exception as e:
            logger.error(f"Failed to send an email: {e}")

        return Response(serializer.data)

    @basic_exception_handler
    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            logger.info("Creating a new OnSiteInformation...")
            request_data = self._construct_data(request)

            serializer = OnSiteInformationSerializer(data=request_data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            logger.info(f"OnSiteInformation created: [{serializer.data}]")

        sender = request.user
        try:
            send_on_site_notification_email(request_data, sender)
        except Exception as e:
            logger.error(f"Failed to send an email: {e}")

        return Response(serializer.data)


class ApiarySiteViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = ApiarySite.objects.none()
    serializer_class = ApiarySiteSerializer

    def get_queryset(self):
        if is_internal(self.request):
            return ApiarySite.objects.all()
        elif self.request.user.is_authenticated:
            user_orgs = [org.id for org in self.request.user.disturbance_organisations.all()]
            approval_queryset = Approval.objects.filter(
                Q(applicant_id__in=user_orgs) | Q(proxy_applicant_id=self.request.user.id)
            ).exclude(status="hidden")
            apiary_sites = ApiarySite.objects.filter(approval_set__in=approval_queryset).distinct()
            return apiary_sites
        else:
            return ApiarySite.objects.none()

    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def relevant_applicant_name(self, request, pk=None):
        try:
            apiary_site = ApiarySite.objects.get(pk=pk)
            logger.info(f"apiary_site: [{apiary_site}]")
        except ApiarySite.DoesNotExist:
            raise NotFound(detail="No ApiarySite matches the given query.", code=404)

        relevant_applicant = apiary_site.get_relevant_applicant_name()
        return Response({"relevant_applicant": relevant_applicant})

    # TODO on-cleanup consider putting better controls around this
    # - right now a user can just keep emailing another user through our system without any limits
    @action(
        detail=True,
        methods=[
            "POST",
        ],
    )
    @basic_exception_handler
    def contact_licence_holder(self, request, pk=None):
        try:
            apiary_site = ApiarySite.objects.get(pk=pk)
            logger.info(f"Contacting licence holder for apiary site:[{apiary_site}] for the user: [{request.user}]...")
        except ApiarySite.DoesNotExist:
            raise NotFound(detail="No ApiarySite matches the given query.", code=404)

        comments = remove_html_tags(request.data.get("comments", ""))

        if comments:
            sender = request.user
            email_data = send_contact_licence_holder_email(apiary_site.latest_approval_link, comments, sender)

            email_data["approval"] = f"{apiary_site.latest_approval_link.approval.id}"
            email_data["fromm"] = sender.email if sender else None
            email_data["to"] = (
                apiary_site.latest_approval_link.approval.relevant_applicant_email
                if apiary_site.latest_approval_link and apiary_site.latest_approval_link.approval
                else None
            )

            serializer = ApprovalLogEntrySerializer(data=email_data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return Response({})

    @action(
        detail=True,
        methods=[
            "PATCH",
        ],
    )
    @basic_exception_handler
    def toggle_availability(self, request, pk=None):
        set_available = request.data.get("available", "")
        instance = self.get_object()
        try:
            apiary_site_on_approval = instance.latest_approval_link
            if apiary_site_on_approval.site_status == "current":
                apiary_site_on_approval.available = set_available
                apiary_site_on_approval.save()
        except Exception as e:
            raise serializers.ValidationError("Invalid Request" + str(e))
        data = annotate_apiary_site_on_approval_geometry(
            ApiarySiteOnApproval.objects.filter(id=apiary_site_on_approval.id)
        )
        return Response(data[0] if len(data) > 0 else {})

    @action(
        detail=True,
        methods=[
            "PATCH",
        ],
        permission_classes=[InternalApprovalPermission],
    )
    @basic_exception_handler
    def make_vacant(self, request, pk=None):
        instance = self.get_object()

        if not hasattr(instance, "latest_approval_link") or instance.latest_approval_link is None:
            raise serializers.ValidationError("This site can not be made vacant as it has no latest approval")

        apiary_site_on_approval = instance.latest_approval_link
        apiary_site_on_approval.site_status = "vacant"
        apiary_site_on_approval.save()

        instance.save()
        data = annotate_apiary_site_on_approval_geometry(ApiarySiteOnApproval.objects.filter(id=instance.id))
        return Response(data[0] if len(data) > 0 else {})

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def list_apiary_sites_vacant(self, request):
        search_text = request.query_params.get("search_text", "")
        qs_vacant_site_proposal, qs_vacant_site_approval = get_qs_vacant_site(search_text)
        vacant_site_proposal = annotate_apiary_site_on_proposal_vacant_draft_minimal_geometry(qs_vacant_site_proposal)
        vacant_site_approval = annotate_apiary_site_on_approval_min_geometry(qs_vacant_site_approval)
        data = {
            "type": "FeatureCollection",
            "features": list(vacant_site_proposal) + list(vacant_site_approval),
        }
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def list_apiary_sites_pending(self, request):
        search_text = request.query_params.get("search_text", "")
        qs_sites = get_qs_pending_site(search_text)
        sites = annotate_apiary_site_on_proposal_minimal_geometry(qs_sites)
        data = {"type": "FeatureCollection", "features": list(sites)}
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def list_apiary_sites_denied(self, request):
        search_text = request.query_params.get("search_text", "")
        qs_sites = get_qs_denied_site(search_text)
        sites = annotate_apiary_site_on_proposal_minimal_geometry(qs_sites)
        data = {"type": "FeatureCollection", "features": list(sites)}
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def list_apiary_sites_current_available(self, request):
        search_text = request.query_params.get("search_text", "")
        qs_sites = get_qs_current_site(search_text, available=True)
        sites = annotate_apiary_site_on_approval_min_geometry(qs_sites)
        data = {"type": "FeatureCollection", "features": list(sites)}
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def list_apiary_sites_current_unavailable(self, request):
        search_text = request.query_params.get("search_text", "")
        qs_sites = get_qs_current_site(search_text, available=False)
        sites = annotate_apiary_site_on_approval_min_geometry(qs_sites)
        data = {"type": "FeatureCollection", "features": list(sites)}
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def list_apiary_sites_current(self, request):
        search_text = request.query_params.get("search_text", "")
        qs_sites = get_qs_current_site(search_text)
        sites = annotate_apiary_site_on_approval_min_geometry(qs_sites)
        data = {"type": "FeatureCollection", "features": list(sites)}
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def list_apiary_sites_suspended(self, request):
        search_text = request.query_params.get("search_text", "")
        qs_sites = get_qs_suspended_site(search_text)
        sites = annotate_apiary_site_on_approval_min_geometry(qs_sites)
        data = {"type": "FeatureCollection", "features": list(sites)}
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def list_apiary_sites_not_to_be_reissued(self, request):
        search_text = request.query_params.get("search_text", "")
        qs_sites = get_qs_not_to_be_reissued_site(search_text)
        sites = annotate_apiary_site_on_approval_min_geometry(qs_sites)
        data = {"type": "FeatureCollection", "features": list(sites)}
        return Response(data)

    @action(
        detail=False,
        methods=["GET"],
    )
    @basic_exception_handler
    def list_apiary_sites(self, request):
        statuses_param = request.query_params.get("statuses", "")
        availabilities_param = request.query_params.get("availabilities", "")
        search_text = request.query_params.get("search_text", "")

        status_filter = [s for s in statuses_param.split(",") if s]
        availability_filter = [a for a in availabilities_param.split(",") if a]
        search_int = int(search_text) if search_text and search_text.isdigit() else ""

        show_all = not status_filter
        features = []

        if show_all or "vacant" in status_filter:
            qs_p, qs_a = get_qs_vacant_site(search_int or search_text)
            features += list(annotate_apiary_site_on_proposal_vacant_draft_minimal_geometry(qs_p))
            features += list(annotate_apiary_site_on_approval_min_geometry(qs_a))

        if show_all or "pending" in status_filter:
            features += list(
                annotate_apiary_site_on_proposal_minimal_geometry(get_qs_pending_site(search_int or search_text))
            )

        if show_all or "denied" in status_filter:
            features += list(
                annotate_apiary_site_on_proposal_minimal_geometry(get_qs_denied_site(search_int or search_text))
            )

        # All approval-based statuses in one optimised DB query
        if show_all or any(s in status_filter for s in ("current", "suspended", "not_to_be_reissued")):
            qs = get_qs_all_apiary_sites(search_int or search_text)

            # Status filter — push to DB
            if not show_all:
                relevant = [s for s in ("current", "suspended", "not_to_be_reissued") if s in status_filter]
                qs = qs.filter(site_status__in=relevant)

            # Availability filter — only meaningful for current, push to DB
            if availability_filter and (show_all or "current" in status_filter):
                if "available" in availability_filter and "unavailable" not in availability_filter:
                    qs = qs.filter(Q(available=True) | ~Q(site_status=SITE_STATUS_CURRENT))
                elif "unavailable" in availability_filter and "available" not in availability_filter:
                    qs = qs.filter(Q(available=False) | ~Q(site_status=SITE_STATUS_CURRENT))

            features += list(annotate_apiary_site_on_approval_min_geometry(qs))

        return Response({"type": "FeatureCollection", "features": features})

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    @timeit
    def list_existing_proposal_vacant_draft(self, request):
        qs_vacant_site_proposal, _ = get_qs_vacant_site()
        vacant_site_proposal = annotate_apiary_site_on_proposal_vacant_draft_minimal_geometry(qs_vacant_site_proposal)
        data = {"type": "FeatureCollection", "features": list(vacant_site_proposal)}
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    @timeit
    def list_existing_proposal_vacant_processed(self, request):
        qs_vacant_site_proposal, _ = get_qs_vacant_site()
        qs_vacant_site_proposal = qs_vacant_site_proposal.filter(wkb_geometry_processed__isnull=False)
        vacant_site_proposal = annotate_apiary_site_on_proposal_processed_minimal_geometry(qs_vacant_site_proposal)
        data = {"type": "FeatureCollection", "features": list(vacant_site_proposal)}
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    @timeit
    def list_existing_approval_vacant(self, request):
        _, qs_vacant_site_approval = get_qs_vacant_site()
        vacant_site_approval = annotate_apiary_site_on_approval_min_geometry(qs_vacant_site_approval)
        data = {"type": "FeatureCollection", "features": list(vacant_site_approval)}
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    @timeit
    def list_existing_proposal_draft(self, request):
        proposal_id = request.query_params.get("proposal_id", None)
        search_text = request.query_params.get("search_text", "")
        proposal = Proposal.objects.get(id=proposal_id) if proposal_id else None
        qs_on_proposal_draft = get_qs_proposal("draft", proposal, search_text)
        on_proposal_draft = annotate_apiary_site_on_proposal_minimal_geometry(qs_on_proposal_draft)
        data = {"type": "FeatureCollection", "features": list(on_proposal_draft)}
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    @timeit
    def list_existing_proposal_processed(self, request):
        proposal_id = request.query_params.get("proposal_id", None)
        proposal = Proposal.objects.get(id=proposal_id) if proposal_id else None
        qs_on_proposal_processed = get_qs_proposal("processed", proposal)
        on_proposal_processed = annotate_apiary_site_on_proposal_processed_minimal_geometry(qs_on_proposal_processed)
        data = {"type": "FeatureCollection", "features": list(on_proposal_processed)}
        return Response(data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    @timeit
    def list_existing_approval(self, request):
        # ApiarySiteOnApproval
        qs_on_approval = get_qs_approval()
        sites = annotate_apiary_site_on_approval_min_geometry(qs_on_approval)
        data = {"type": "FeatureCollection", "features": list(sites)}
        return Response(data)

    def _available_sites_qs(self):
        q_include = Q(id__in=(ApiarySite.objects.all().values("latest_approval_link__id")))
        q_include &= Q(site_status=SITE_STATUS_CURRENT)
        q_include &= Q(available=True)
        qs_on_approval = ApiarySiteOnApproval.objects.filter(q_include).distinct("apiary_site")
        return qs_on_approval

    def _not_to_be_reissued_sites_qs(self):
        q_include_approval = Q(
            id__in=(ApiarySite.objects.all().exclude(is_vacant=True).values("latest_approval_link__id"))
        )
        q_include_approval &= Q(site_status=SITE_STATUS_NOT_TO_BE_REISSUED)
        qs_on_approval = ApiarySiteOnApproval.objects.filter(q_include_approval).distinct("apiary_site")
        return qs_on_approval

    def _denied_sites_qs(self):
        q_include_proposal = Q(
            id__in=(ApiarySite.objects.all().exclude(is_vacant=True).values("latest_proposal_link__id"))
        )
        q_include_proposal &= Q(site_status=SITE_STATUS_DENIED)
        qs_on_proposal = ApiarySiteOnProposal.objects.filter(q_include_proposal).distinct("apiary_site")
        return qs_on_proposal

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def available_sites(self, request):
        qs_on_approval = self._available_sites_qs()
        sites = annotate_apiary_site_on_approval_geometry(qs_on_approval)
        data = {"type": "FeatureCollection", "features": list(sites)}
        return Response(data)

    # TODO on-cleanup: this may not be needed any more
    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def transitable_sites(self, request):
        qs_on_proposal = self._denied_sites_qs()
        qs_on_approval = self._not_to_be_reissued_sites_qs()

        proposal_data = annotate_apiary_site_on_proposal_processed_geometry(qs_on_proposal)
        approval_data = annotate_apiary_site_on_approval_geometry(qs_on_approval)

        data = {"features": list(proposal_data) + list(approval_data)}

        return Response(data)


class ProposalApiaryViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = ProposalApiary.objects.none()
    serializer_class = ProposalApiarySerializer

    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def apiary_sites(self, request, *args, **kwargs):
        proposal_apiary = self.get_object()

        apiary_site_on_proposals = ApiarySiteOnProposal.objects.filter(
            apiary_site__in=proposal_apiary.apiary_sites.all()
        ).distinct("apiary_site")

        draft_apiary_sites = apiary_site_on_proposals.filter(site_status=SITE_STATUS_DRAFT)
        non_draft_apiary_sites = apiary_site_on_proposals.exclude(site_status=SITE_STATUS_DRAFT)

        draft_apiary_sites = list(annotate_apiary_site_on_proposal_draft_geometry(draft_apiary_sites))
        non_draft_apiary_sites = list(annotate_apiary_site_on_proposal_processed_geometry(non_draft_apiary_sites))

        data = {"features": draft_apiary_sites + non_draft_apiary_sites}

        return Response(data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    @basic_exception_handler
    def transfer_apiary_sites(self, request, *args, **kwargs):
        proposal_apiary = self.get_object()

        if proposal_apiary.proposal and proposal_apiary.proposal.customer_status == "draft":
            sites = proposal_apiary.site_transfer_apiary_sites.all()
        else:
            sites = proposal_apiary.site_transfer_apiary_sites.filter(customer_selected=True)

        data = list(annotate_site_transfer_apiary_site(sites))

        return Response(data)

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            return ProposalApiary.objects.all()
        elif user.is_authenticated:
            user_orgs = [org.id for org in self.request.user.disturbance_organisations.all()]
            qs = ProposalApiary.objects.filter(
                Q(proposal_id__applicant_id__in=user_orgs)
                | Q(proposal_id__submitter_id=user.id)
                | Q(proposal_id__proxy_applicant_id=user.id)
            )
            return qs
        return ProposalApiary.objects.none()

    @basic_exception_handler
    def internal_apiary_serializer_class(self):
        instance = self.get_object()
        application_type = instance.proposal.application_type.name
        if application_type in (ApplicationType.APIARY, ApplicationType.SITE_TRANSFER):
            return ApiaryInternalProposalSerializer

    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def internal_apiary_proposal(self, request, *args, **kwargs):
        instance = self.get_object()
        proposal_instance = instance.proposal
        proposal_instance.internal_view_log(request)
        serializer_class = self.internal_apiary_serializer_class()
        serializer = serializer_class(proposal_instance, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def process_deed_poll_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = None
        action = request.data.get("action")
        if (
            action == "list"
            or instance.proposal
            and instance.proposal.customer_status == Proposal.CUSTOMER_STATUS_DRAFT
        ):
            returned_data = process_generic_document(request, instance, document_type=DeedPollDocument.DOC_TYPE_NAME)
        if returned_data:
            return Response(returned_data)
        else:
            return Response()

    @action(detail=True, methods=["POST"])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def process_public_liability_insurance_document(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except ProposalApiary.DoesNotExist:
            instance = ProposalApiaryTemporaryUse.objects.get(proposal__id=kwargs.get("pk"))

        returned_data = None
        action = request.data.get("action")
        if (
            action == "list"
            or instance.proposal
            and instance.proposal.customer_status == Proposal.CUSTOMER_STATUS_DRAFT
        ):
            returned_data = process_generic_document(
                request,
                instance,
                document_type=PublicLiabilityInsuranceDocument.DOC_TYPE_NAME,
            )
        if returned_data:
            return Response(returned_data)
        else:
            return Response()

    @action(detail=True, methods=["POST"])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def process_supporting_application_document(self, request, *args, **kwargs):
        instance = self.get_object()

        returned_data = None
        action = request.data.get("action")
        if (
            action == "list"
            or instance.proposal
            and instance.proposal.customer_status == Proposal.CUSTOMER_STATUS_DRAFT
        ):
            returned_data = process_generic_document(
                request,
                instance,
                document_type=SupportingApplicationDocument.DOC_TYPE_NAME,
            )
        if returned_data:
            return Response(returned_data)
        else:
            return Response()

    @action(detail=True, methods=["post"], permission_classes=[ProposalAssessorPermission])
    @basic_exception_handler
    def apiary_assessor_send_referral(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.proposal and instance.proposal.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR:
            serializer = SendApiaryReferralSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.send_referral(
                request,
                serializer.validated_data["group_id"],
                serializer.validated_data["text"],
            )
            serializer_class = self.internal_apiary_serializer_class()
            serializer = serializer_class(instance.proposal, context={"request": request})
            return Response(serializer.data)
        else:
            raise serializer.ValidationError("Can only send reference when proposal is With Assessor.")

    @action(detail=True, methods=["post"], permission_classes=[ProposalAssessorPermission])
    @renderer_classes((JSONRenderer,))
    @basic_exception_handler
    def assessor_save(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.proposal and instance.proposal.has_assessor_mode(request.user):
            save_apiary_assessor_data(
                instance.proposal,
                request,
            )
            instance.refresh_from_db()
        proposal_instance = instance.proposal
        serializer_class = self.internal_apiary_serializer_class()
        serializer = serializer_class(proposal_instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    @renderer_classes((JSONRenderer,))
    def proposal_history(self, request, *args, **kwargs):
        instance = self.get_object()
        proposal_instance = instance.proposal
        serializer = ProposalHistorySerializer(proposal_instance)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[ProposalApproverPermission],
    )
    @basic_exception_handler
    def final_approval(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()

            if instance.proposal.application_type.name == ApplicationType.SITE_TRANSFER:
                serializer = ProposedApprovalSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
            else:
                serializer = ProposedApprovalSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)

            preview = None
            if instance.proposal and instance.proposal.processing_status == Proposal.PROCESSING_STATUS_WITH_APPROVER:
                preview = request.data.get("preview")
                instance = instance.final_approval(request, serializer.validated_data, preview=preview)

            serializer_class = self.internal_apiary_serializer_class()
            serializer = serializer_class(instance.proposal, context={"request": request})

            if preview:
                site_transfer_preview = False
                if instance.proposal.application_type.name == ApplicationType.SITE_TRANSFER:
                    site_transfer_preview = True
                    originating_target = request.data.get("originating_target")
                    if originating_target == "originating":
                        preview_approval_id = serializer.data.get("proposal_apiary", {}).get("originating_approval_id")
                    else:
                        preview_approval_id = instance.target_approval_id
                else:
                    preview_approval_id = serializer.data.get("approval", {}).get("id")
                licence_response = HttpResponse(content_type="application/pdf")
                preview_approval = Approval.objects.get(id=preview_approval_id)
                preview_approval.approver_id = request.user.id

                licence_response.content = preview_approval.generate_doc(
                    preview=True, site_transfer_preview=site_transfer_preview
                )
                transaction.set_rollback(True)
                return licence_response

            return Response(serializer.data)

    # TODO on-cleanup - why it is a POST?
    # Good question
    @action(
        detail=True,
        methods=[
            "POST",
        ],
    )
    def get_licence_holders(self, request, *args, **kwargs):
        instance = self.get_object()
        user = None
        user_qs = []
        if request.data.get("user_email"):
            user_qs = EmailUser.objects.filter(email=request.data.get("user_email"))
            if user_qs:
                user = user_qs[0]
                serializer = UserApiaryApprovalSerializer(
                    user,
                    context={
                        "request": request,
                        "originating_approval_id": instance.originating_approval.id,
                    },
                )
                return Response(serializer.data)
        # Fallback if no email address found
        return Response("Email address not known")


class ApiaryReferralViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = ApiaryReferral.objects.none()
    serializer_class = ApiaryReferralSerializer
    permission_classes = [InternalProposalPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and is_internal(self.request):
            queryset = ApiaryReferral.objects.all()
            return queryset
        return ApiaryReferral.objects.none()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data)

    # TODO on-cleanup - ideally this should be paginated (so should comms and actions logs)
    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    def datatable_list(self, request, *args, **kwargs):
        proposal_field = request.GET.get("proposal", None)
        if not proposal_field:
            raise serializers.ValidationError("Valid proposal id not provided")
        try:
            proposal = Proposal.objects.get(id=int(proposal_field))
        except Proposal.DoesNotExist:
            raise serializers.ValidationError("Valid proposal id not provided")
        qs = Referral.objects.filter(proposal=proposal)
        serializer = DTApiaryReferralSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"], permission_classes=[ProposalReferrerPermission])
    def complete(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.complete(request)
        data = {}
        data["type"] = "email"
        data["fromm"] = f"{request.user.get_full_name()}"
        data["to"] = f"{instance.referral_group.name}"
        data["proposal"] = f"{instance.referral.proposal.id}"
        data["staff"] = f"{request.user.id}"
        data["text"] = f"{instance.referral.referral_text}"
        data["subject"] = f"{instance.referral.referral_text}"
        serializer = ProposalLogEntrySerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data)

    # TODO on-cleanup - why GET?
    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[ProposalAssessorPermission],
    )
    def remind(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.remind(request)
        serializer = ApiaryInternalProposalSerializer(instance.referral.proposal, context={"request": request})
        return Response(serializer.data)

    # TODO on-cleanup - why GET?
    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[ProposalAssessorPermission],
    )
    def recall(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.recall(request)
        serializer = ApiaryInternalProposalSerializer(instance.referral.proposal, context={"request": request})
        return Response(serializer.data)

    # TODO on-cleanup - why GET?
    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[ProposalAssessorPermission],
    )
    def resend(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.resend(request)
        serializer = ApiaryInternalProposalSerializer(instance.referral.proposal, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[ProposalReferrerPermission],
    )
    def assign_request_user(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.assign_officer(request, request.user)
        serializer = FullApiaryReferralSerializer(instance.referral, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[ProposalReferrerPermission],
    )
    def assign_to(self, request, *args, **kwargs):
        instance = self.get_object()
        user_id = request.data.get("assigned_officer_id", None)
        user = None
        if user_id is not None:
            try:
                user = EmailUser.objects.get(id=user_id)
            except EmailUser.DoesNotExist:
                raise serializers.ValidationError("A user with the id passed in does not exist")
        instance.assign_officer(request, user)
        serializer = FullApiaryReferralSerializer(instance.referral, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[ProposalReferrerPermission],
    )
    def unassign(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.unassign(request)
        serializer = FullApiaryReferralSerializer(instance.referral, context={"request": request})
        return Response(serializer.data)


class ProposalViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = Proposal.objects.none()
    serializer_class = ProposalSerializer

    def get_queryset(self):
        user = self.request.user
        if is_internal(self.request):
            return (
                Proposal.objects.filter(
                    application_type__name__in=[
                        ApplicationType.APIARY,
                        ApplicationType.SITE_TRANSFER,
                        ApplicationType.TEMPORARY_USE,
                    ]
                )
                .select_related("apiary_temporary_use", "application_type")
                .prefetch_related(
                    Prefetch(
                        "apiary_temporary_use__temporary_use_apiary_sites",
                        queryset=TemporaryUseApiarySite.objects.select_related(
                            "apiary_site_on_approval",
                            "apiary_site_on_approval__apiary_site",
                            "apiary_site_on_approval__site_category",
                            "apiary_site_on_approval__approval",
                            "apiary_site_on_approval__approval__applicant",
                        ),
                    )
                )
            )
        elif user.is_authenticated:
            user_orgs = [org.id for org in user.disturbance_organisations.all()]
            queryset = Proposal.objects.filter(
                application_type__name__in=[
                    ApplicationType.APIARY,
                    ApplicationType.SITE_TRANSFER,
                    ApplicationType.TEMPORARY_USE,
                ]
            ).filter(Q(applicant_id__in=user_orgs) | Q(proxy_applicant=user) | Q(submitter=user))
            return queryset

        return Proposal.objects.none()

    def get_serializer_class(self):
        return ProposalApiaryTypeSerializer

    def internal_serializer_class(self):
        return ApiaryInternalProposalSerializer

    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    def temporary_use_apiary_sites(self, request, *args, **kwargs):
        instance = self.get_object()
        qs = TemporaryUseApiarySite.objects.filter(proposal_apiary_temporary_use=instance.apiary_temporary_use)
        data = list(annotate_temporary_use_apiary_site(qs))
        return Response(data)

    @action(detail=True, methods=["POST"])
    @renderer_classes((JSONRenderer,))
    def process_deed_poll_document(self, request, *args, **kwargs):
        instance = self.get_object()
        returned_data = None
        action = request.data.get("action")
        if action == "list" or instance.customer_status == Proposal.CUSTOMER_STATUS_DRAFT:
            returned_data = process_generic_document(request, instance, document_type=DeedPollDocument.DOC_TYPE_NAME)
        if returned_data:
            return Response(returned_data)
        else:
            return Response()

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    def filter_list(self, request, *args, **kwargs):
        """Used by the internal/external dashboard filters"""
        qs = self.get_queryset().filter(
            application_type__name__in=[
                ApplicationType.APIARY,
                ApplicationType.SITE_TRANSFER,
                ApplicationType.TEMPORARY_USE,
            ]
        )
        activity_qs = qs.filter(activity__isnull=False).values_list("activity", flat=True).distinct()

        data = dict(
            activities=activity_qs,
            approval_status_choices=[i[1] for i in Approval.STATUS_CHOICES],
        )
        return Response(data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def action_log(self, request, *args, **kwargs):
        instance = self.get_object()
        qs = instance.action_logs.all()
        serializer = ProposalUserActionSerializer(qs, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def comms_log(self, request, *args, **kwargs):
        instance = self.get_object()
        qs = instance.comms_logs.all()
        serializer = ProposalLogEntrySerializer(qs, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[InternalProposalPermission],
    )
    @renderer_classes((JSONRenderer,))
    def add_comms_log(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = self.get_object()
            request_data = request.data.copy()
            request_data["proposal"] = f"{instance.id}"
            request_data["staff"] = f"{request.user.id}"
            serializer = ProposalLogEntrySerializer(data=request_data)
            serializer.is_valid(raise_exception=True)

            comms = serializer.save()

            # Save the files
            for f in request.FILES.getlist("files"):
                document = comms.documents.create()
                document.check_file(f)
                document.name = str(f)
                document._file = f
                document.save()

            return Response(serializer.data)

    # TODO:on-cleanup requirements endpoints should ideally be paginated but not necessary for now
    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def requirements(self, request, *args, **kwargs):
        instance = self.get_object()
        qs = instance.requirements.all().exclude(is_deleted=True)
        serializer = ProposalRequirementSerializer(qs, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def apiary_site_transfer_originating_approval_requirements(self, request, *args, **kwargs):
        instance = self.get_object()
        approval = Approval.objects.get(id=instance.proposal_apiary.originating_approval_id)
        qs = instance.apiary_requirements(approval).exclude(is_deleted=True)
        serializer = ProposalRequirementSerializer(qs, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def apiary_site_transfer_target_approval_requirements(self, request, *args, **kwargs):
        # for new licences, sitetransfer_approval is None
        instance = self.get_object()
        if instance.proposal_apiary.target_approval_id:
            approval = Approval.objects.get(id=instance.proposal_apiary.target_approval_id)
            qs = instance.apiary_requirements(approval).exclude(is_deleted=True)
        else:
            qs = instance.apiary_requirements().exclude(is_deleted=True)

        serializer = ProposalRequirementSerializer(qs, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    def amendment_request(self, request, *args, **kwargs):
        instance = self.get_object()
        qs = instance.amendment_requests
        qs = qs.filter(status="requested")
        serializer = AmendmentRequestDisplaySerializer(qs, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def internal_proposal(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.internal_view_log(request)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    def internal_proposal_wrapper(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer_class = ProposalWrapperSerializer
        serializer = serializer_class(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    @renderer_classes((JSONRenderer,))
    def submit(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.customer_status == Proposal.CUSTOMER_STATUS_DRAFT:
            save_proponent_data(instance, request, self)
            # Submitter and lodgement log set here - if payment fails we should still log this and submitter can be overridden later if necessary
            instance.submitter = request.user
            instance.log_user_action(
                ProposalUserAction.ACTION_LODGE_APPLICATION.format(instance.lodgement_number),
                request,
            )
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def assign_request_user(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.assign_officer(request, request.user)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def assign_to(self, request, *args, **kwargs):
        instance = self.get_object()
        user_id = request.data.get("assessor_id", None)
        user = None
        if not user_id:
            raise serializers.ValidationError("An assessor id is required")
        try:
            user = EmailUser.objects.get(id=user_id)
        except EmailUser.DoesNotExist:
            raise serializers.ValidationError("A user with the id passed in does not exist")
        instance.assign_officer(request, user)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def unassign(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.unassign(request)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def switch_status(self, request, *args, **kwargs):
        instance = self.get_object()
        status = request.data.get("status")
        approver_comment = request.data.get("approver_comment")
        if not status:
            raise serializers.ValidationError("Status is required")
        else:
            if status not in [
                "with_assessor",
                "with_assessor_requirements",
                "with_approver",
            ]:
                raise serializers.ValidationError("The status provided is not allowed")
        instance.move_to_status(request, status, approver_comment)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def reissue_approval(self, request, *args, **kwargs):
        instance = self.get_object()
        status = request.data.get("status")
        if not status:
            raise serializers.ValidationError("Status is required")
        else:
            if status not in ["with_approver"]:
                raise serializers.ValidationError("The status provided is not allowed")
        instance.reissue_approval(request, status)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    def renew_approval(self, request, pk=None, *args, **kwargs):
        # For this function we must authenticate based on the approval id provided, as site transfer applications are not accessible by transferees from which their approvals are created from
        approval_id = request.GET.get("approval_id", None)

        user_orgs = [org.id for org in self.request.user.disturbance_organisations.all()]
        queryset = Approval.objects.filter(id=approval_id).filter(
            Q(applicant_id__in=user_orgs) | Q(proxy_applicant_id=self.request.user.id)
        )
        if not queryset.exists() and not is_internal(request):
            raise serializers.ValidationError("User not authorised to renew this Approval.")

        instance = Proposal.objects.get(id=pk)
        new_instance = instance.renew_approval(request)
        serializer = SaveProposalSerializer(new_instance, context={"request": request})

        # verify that the proposal is the new proposal that the user is allowed to access
        if not (
            new_instance.applicant_id in user_orgs
            or new_instance.proxy_applicant_id == self.request.user.id
            or is_internal(request)
        ):
            raise serializers.ValidationError("User not authorised to access this Proposal.")

        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    def amend_approval(self, request, *args, **kwargs):
        instance = self.get_object()
        instance = instance.amend_approval(request)
        serializer = SaveProposalSerializer(instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[ProposalAssessorPermission],
    )
    def proposed_approval(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = ProposedApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance.proposed_approval(request, serializer.validated_data)

        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})

        return Response(serializer.data)

    # TODO on-cleanup - determine if this is required for apiary or not (applying internal permissions for now)
    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def approval_level_document(self, request, *args, **kwargs):
        instance = self.get_object()
        instance = instance.assing_approval_level_document(request)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    # TODO on-cleanup - determine if this is required for apiary or not (applying internal permissions for now)
    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[InternalProposalPermission],
    )
    def approval_level_comment(self, request, *args, **kwargs):
        instance = self.get_object()
        instance = instance.save_approval_level_comment(request)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[ProposalAssessorPermission, ProposalApproverPermission],
    )
    @basic_exception_handler
    def final_approval_temp_use(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.final_approval_temp_use(
            request,
        )
        return Response({})

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[ProposalAssessorPermission, ProposalApproverPermission],
    )
    @basic_exception_handler
    def final_decline_temp_use(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.final_decline_temp_use(
            request,
        )
        return Response({})

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[ProposalApproverPermission],
    )
    def final_approval(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ProposedApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance.final_approval(request, serializer.validated_data)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[ProposalAssessorPermission],
    )
    def proposed_decline(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = PropedDeclineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance.proposed_decline(request, serializer.validated_data)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
        permission_classes=[ProposalApproverPermission],
    )
    def final_decline(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = PropedDeclineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance.final_decline(request, serializer.validated_data)
        serializer_class = self.internal_serializer_class()
        serializer = serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[ProposalAssessorPermission])
    def assesor_send_referral(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR:
            instance = self.get_object()
            serializer = SendReferralSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance.send_referral(
                request,
                serializer.validated_data["email"],
                serializer.validated_data["text"],
            )
            serializer_class = self.internal_serializer_class()
            serializer = serializer_class(instance, context={"request": request})
            return Response(serializer.data)
        else:
            raise serializer.ValidationError("Can only send reference when proposal is With Assessor.")

    @action(detail=True, methods=["post"])
    @basic_exception_handler
    def remove_apiary_site(self, request, *args, **kwargs):
        proposal_obj = self.get_object()

        is_authorised_to_modify_draft(request, proposal_obj)

        apiary_site_id = request.data.get("apiary_site_id")

        apiary_site = ApiarySite.objects.get(id=apiary_site_id)
        apiary_site_on_proposal = ApiarySiteOnProposal.objects.get(
            apiary_site=apiary_site, proposal_apiary=proposal_obj.proposal_apiary
        )
        apiary_site_on_proposal.delete()

        return Response({"removed": "success"})

    @action(detail=True, methods=["post"])
    @renderer_classes((JSONRenderer,))
    def draft(self, request, *args, **kwargs):
        instance = self.get_object()
        # Ensure the current user is a member of the organisation that created the draft application.
        is_authorised_to_modify_draft(request, instance)
        save_proponent_data(instance, request, self)
        serializer = self.serializer_class(instance, context={"request": request})
        return Response(serializer.data)

    # TODO on-cleanup - determine if this is required for apiary or not
    @action(detail=True, methods=["post"])
    @renderer_classes((JSONRenderer,))
    def update_region_section(self, request, *args, **kwargs):
        instance = self.get_object()
        region = request.data.get("region")
        district = request.data.get("district")
        activity = request.data.get("activity")
        sub_activity1 = request.data.get("sub_activity1")
        sub_activity2 = request.data.get("sub_activity2")
        management_area = request.data.get("category")
        approval_level = request.data.get("approval_level")
        data = {
            "region": region,
            "district": district,
            "activity": activity,
            "sub_activity_level1": sub_activity1,
            "sub_activity_level2": sub_activity2,
            "management_area": management_area,
            "approval_level": approval_level,
        }
        serializer = SaveProposalRegionSerializer(instance, data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[ProposalAssessorPermission])
    @renderer_classes((JSONRenderer,))
    def assessor_save(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.has_assessor_mode(request.user):
            save_assessor_data(instance, request, self)
        return redirect(reverse("external"))

    def create(self, request, *args, **kwargs):
        with transaction.atomic():
            if request.data.get("application"):
                application_type = ApplicationType.objects.get(id=request.data.get("application"))

            # When there is a parameter named 'application_type_str', we may need to update application_type
            application_type_str = request.data.get("application_type_str", None)
            if application_type_str == "apiary":
                application_type = ApplicationType.objects.get(name=ApplicationType.APIARY)
            elif application_type_str == "temporary_use":
                application_type = ApplicationType.objects.get(name=ApplicationType.TEMPORARY_USE)
            elif application_type_str == "site_transfer":
                application_type = ApplicationType.objects.get(name=ApplicationType.SITE_TRANSFER)

            region = request.data.get("region")
            district = request.data.get("district")
            activity = request.data.get("activity")
            sub_activity1 = request.data.get("sub_activity1")
            sub_activity2 = request.data.get("sub_activity2")
            category = request.data.get("category")
            approval_level = request.data.get("approval_level")

            # Get most recent versions of the Proposal Types
            qs_proposal_type = ProposalType.objects.all().order_by("name", "-version").distinct("name")
            proposal_type = qs_proposal_type.get(name=application_type.name)
            applicant = None
            proxy_applicant = None
            if request.data.get("behalf_of") == "individual":
                # Validate User for Individual applications
                request_user = EmailUser.objects.get(id=request.user.id)
                if not request_user.residential_address:
                    raise ValidationError("null_applicant_address")
                # Assign request.user as applicant
                proxy_applicant = request.user.id
            else:
                applicant = request.data.get("behalf_of")

            data = {
                "schema": proposal_type.schema,
                "submitter": request.user.id,
                "applicant": applicant,
                "proxy_applicant": proxy_applicant,
                "application_type": application_type.id,
                "region": region,
                "district": district,
                "activity": activity,
                "approval_level": approval_level,
                "sub_activity_level1": sub_activity1,
                "sub_activity_level2": sub_activity2,
                "management_area": category,
                "data": [],
            }
            serializer = SaveProposalSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            proposal_obj = serializer.save()

            if proposal_obj.apiary_group_application_type:
                proposal_obj.activity = proposal_obj.application_type.name
                proposal_obj.save()
            details_data = {"proposal_id": proposal_obj.id}
            if application_type.name == ApplicationType.APIARY:
                serializer = SaveProposalApiarySerializer(data=details_data)
                serializer.is_valid(raise_exception=True)
                proposal_apiary = serializer.save()
                for question in ApiaryChecklistQuestion.objects.filter(
                    checklist_type="apiary", checklist_role="applicant"
                ):
                    ApiaryChecklistAnswer.objects.create(proposal=proposal_apiary, question=question)
                # Find relevant approval
                approval = proposal_apiary.retrieve_approval
                if approval:
                    # Copy requirements from approval.current_proposal
                    req = approval.proposalrequirement_set.exclude(is_deleted=True)
                    from copy import deepcopy

                    if req:
                        for r in req:
                            old_r = deepcopy(r)
                            r.proposal = proposal_apiary.proposal
                            r.apiary_approval = None
                            r.copied_from = old_r
                            r.id = None
                            r.save()
                    # Set previous_application to maintain proposal history
                    proposal_apiary.proposal.previous_application = approval.current_proposal
                    proposal_apiary.proposal.save()

            elif application_type.name == ApplicationType.SITE_TRANSFER:
                approval_id = request.data.get("originating_approval_id")
                approval = Approval.objects.get(id=approval_id)
                details_data["originating_approval_id"] = approval_id
                serializer = CreateProposalApiarySiteTransferSerializer(data=details_data)
                serializer.is_valid(raise_exception=True)
                proposal_apiary = serializer.save()
                # Set proposal applicant
                if approval.applicant:
                    proposal_obj.applicant = approval.applicant
                else:
                    proposal_obj.proxy_applicant = approval.proxy_applicant
                proposal_obj.save()
                # Set up checklist questions
                for question in ApiaryChecklistQuestion.objects.filter(
                    checklist_type="site_transfer", checklist_role="applicant"
                ):
                    ApiaryChecklistAnswer.objects.create(proposal=proposal_apiary, question=question)
                # Save approval apiary sites to site transfer proposal
                # for apiary_site in approval.apiary_sites.all():
                for relation in approval.get_relations():
                    SiteTransferApiarySite.objects.create(
                        proposal_apiary=proposal_apiary,
                        apiary_site_on_approval=relation,
                    )

            elif application_type.name == ApplicationType.TEMPORARY_USE:
                approval_id = request.data.get("approval_id")
                approval = Approval.objects.get(id=approval_id)
                details_data["loaning_approval_id"] = approval_id
                serializer = ProposalApiaryTemporaryUseSerializer(data=details_data)
                serializer.is_valid(raise_exception=True)
                new_temp_use = serializer.save()

                # Save TemporaryUseApiarySite
                for relation in approval.get_relations():
                    data_to_save = {
                        "proposal_apiary_temporary_use_id": new_temp_use.id,
                        "apiary_site_on_approval_id": relation.id,
                    }
                    serializer = TemporaryUseApiarySiteSerializer(data=data_to_save)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()

            serializer = SaveProposalSerializer(proposal_obj)
            return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "delete",
        ],
    )
    def discard(self, request, *args, **kwargs):
        instance = self.get_object()
        is_authorised_to_modify_draft(request, instance)
        instance.discard(request)
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ReferralViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = Referral.objects.none()
    serializer_class = ReferralSerializer
    permission_classes = [InternalProposalPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and is_internal(self.request):
            queryset = Referral.objects.all()
            return queryset
        return Referral.objects.none()

    def get_serializer_class(self):
        referral = self.get_object()
        apiary_referral_attribute_exists = getattr(referral, "apiary_referral", None)
        if apiary_referral_attribute_exists:
            return FullApiaryReferralSerializer
        else:
            return ReferralSerializer

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    def filter_list(self, request, *args, **kwargs):
        qs = (
            Referral.objects.filter(apiary_referral__referral_group__members=request.user)
            if is_internal(self.request)
            else Referral.objects.none()
        )
        application_type_qs = (
            ApplicationType.objects.filter(name__in=[ApplicationType.APIARY, ApplicationType.SITE_TRANSFER])
            .values_list("name", flat=True)
            .distinct()
        )
        processing_status_qs = (
            qs.filter(proposal__processing_status__isnull=False)
            .order_by("proposal__processing_status")
            .distinct("proposal__processing_status")
            .values_list("proposal__processing_status", flat=True)
        )
        processing_status = [
            dict(value=i, name="{}".format(" ".join(i.split("_")).capitalize())) for i in processing_status_qs
        ]
        data = dict(
            application_types=application_type_qs,
            processing_status_choices=processing_status,
        )
        return Response(data)

    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    def referral_wrapper(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer_class = ReferralWrapperSerializer
        serializer = serializer_class(instance)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data)


class ProposalRequirementViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = ProposalRequirement.objects.none()
    serializer_class = ProposalRequirementSerializer
    permission_classes = [ProposalAssessorPermission]

    def get_queryset(self):
        if is_internal(self.request):
            return ProposalRequirement.objects.exclude(is_deleted=True)
        return ProposalRequirement.objects.none()

    # TODO on-cleanup - why GET?
    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    def move_up(self, request, *args, **kwargs):
        instance = self.get_object()
        if not (
            instance.proposal
            and instance.proposal.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS
        ):
            raise serializers.ValidationError(
                "Proposal must be With Assessor (Requirements) for requirement to updated."
            )
        instance.up()
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # TODO on-cleanup - why GET?
    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    def move_down(self, request, *args, **kwargs):
        instance = self.get_object()
        if not (
            instance.proposal
            and instance.proposal.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS
        ):
            raise serializers.ValidationError(
                "Proposal must be With Assessor (Requirements) for requirement to updated."
            )
        instance.down()
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # TODO on-cleanup - why GET?
    @action(
        detail=True,
        methods=[
            "GET",
        ],
    )
    def discard(self, request, *args, **kwargs):
        instance = self.get_object()
        if not (
            instance.proposal
            and instance.proposal.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS
        ):
            raise serializers.ValidationError(
                "Proposal must be With Assessor (Requirements) for requirement to removed."
            )
        instance.is_deleted = True
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # add status check and perm
    def create(self, request, *args, **kwargs):
        data = request.data.get("data")
        proposal = Proposal.objects.get(id=data["proposal"])
        if proposal.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS:
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        else:
            raise serializers.ValidationError(
                "No valid proposal With Assessor (Requirements) for requirement provided."
            )

    # add status check and perm
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if (
            instance.proposal
            and instance.proposal.processing_status == Proposal.PROCESSING_STATUS_WITH_ASSESSOR_REQUIREMENTS
        ):
            serializer = self.get_serializer(instance, data=request.data.get("data"))
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        else:
            raise serializers.ValidationError(
                "No valid proposal With Assessor (Requirements) for requirement provided."
            )


class ProposalStandardRequirementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProposalStandardRequirement.objects.none()
    serializer_class = ProposalStandardRequirementSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return ProposalStandardRequirement.objects.all()
        return ProposalStandardRequirement.objects.none()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        search = request.GET.get("search")
        if search:
            queryset = queryset.filter(text__icontains=search)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # TODO on-cleanup remove
    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    def disturbance_standard_requirements(self, request, *args, **kwargs):
        # Only Disturbance standard requirements
        queryset = self.get_queryset().filter(system="disturbance")
        search = request.GET.get("search")
        if search:
            queryset = queryset.filter(text__icontains=search)
        # Only Disturbance standard requirements
        queryset = queryset.filter(system="disturbance")
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    def apiary_standard_requirements(self, request, *args, **kwargs):
        # Only Apiary standard requirements
        queryset = self.get_queryset().filter(system="apiary")
        search = request.GET.get("search")
        if search:
            queryset = queryset.filter(text__icontains=search)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class AmendmentRequestViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    queryset = AmendmentRequest.objects.none()
    serializer_class = AmendmentRequestSerializer
    permission_classes = [ProposalAssessorPermission]

    def get_queryset(self):
        if is_internal(self.request):
            return AmendmentRequest.objects.all()
        return AmendmentRequest.objects.none()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=json.loads(request.data.get("data")))
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        instance.add_documents(request)
        instance.generate_amendment(request)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=[
            "POST",
        ],
    )
    @renderer_classes((JSONRenderer,))
    def delete_document(self, request, *args, **kwargs):
        instance = self.get_object()
        AmendmentRequestDocument.objects.get(id=request.data.get("id")).delete()
        return Response([dict(id=i.id, name=i.name, _file=i._file.url) for i in instance.requirement_documents.all()])


class AmendmentRequestReasonChoicesView(views.APIView):
    renderer_classes = [
        JSONRenderer,
    ]

    def get(self, request, format=None):
        choices_list = []
        choices = AmendmentReason.objects.all()
        if choices:
            for c in choices:
                choices_list.append({"key": c.id, "value": c.reason})
        return Response(choices_list)


class SearchKeywordsView(views.APIView):
    renderer_classes = [
        JSONRenderer,
    ]
    permission_classes = [InternalProposalPermission]

    def post(self, request, format=None):
        qs = []
        searchWords = request.data.get("searchKeywords")
        searchProposal = request.data.get("searchProposal")
        searchApproval = request.data.get("searchApproval")
        searchCompliance = request.data.get("searchCompliance")
        if searchWords:
            qs = searchKeyWords(searchWords, searchProposal, searchApproval, searchCompliance)
        serializer = SearchKeywordSerializer(qs, many=True)
        return Response(serializer.data)


class SearchReferenceView(views.APIView):
    renderer_classes = [
        JSONRenderer,
    ]
    permission_classes = [InternalProposalPermission]

    def post(self, request, format=None):
        qs = []
        reference_number = request.data.get("reference_number")
        if reference_number:
            qs = search_reference(reference_number)
        serializer = SearchReferenceSerializer(qs)
        return Response(serializer.data)


class ApiaryReferralGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ApiaryReferralGroup.objects.none()
    serializer_class = ApiaryReferralGroupSerializer
    permission_classes = [InternalProposalPermission]

    def get_queryset(self):
        if is_internal(self.request):
            return ApiaryReferralGroup.objects.all()
        else:
            return ApiaryReferralGroup.objects.none()

    @action(
        detail=False,
        methods=[
            "GET",
        ],
    )
    def get_referral_group_list(self, request, *args, **kwargs):
        data = self.get_queryset().values("id", "name")
        return Response(data)


class GetSiteTransferFees(views.APIView):
    renderer_classes = [
        JSONRenderer,
    ]

    def get(self, request, format=None):
        south_west = (
            ApiarySiteFee.objects.filter(apiary_site_fee_type__name="transfer", site_category__name="south_west")
            .order_by("-date_of_enforcement")
            .first()
        )
        remote = (
            ApiarySiteFee.objects.filter(apiary_site_fee_type__name="transfer", site_category__name="remote")
            .order_by("-date_of_enforcement")
            .first()
        )
        return_list = [south_west, remote]
        serializer = ApiarySiteFeeSerializer(return_list, many=True)
        return Response(serializer.data)
