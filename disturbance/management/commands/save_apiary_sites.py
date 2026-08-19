import datetime
import json
import logging
import os

import pytz
from django.core.management.base import BaseCommand

from disturbance.components.approvals.serializers_apiary import ApiarySiteOnApprovalGeometryExportSerializer
from disturbance.components.main.utils import (
    get_qs_approval_for_export,
    get_qs_proposal_for_export,
    get_qs_vacant_site_for_export,
)
from disturbance.components.proposals.serializers_apiary import (
    ApiarySiteOnProposalDraftGeometryExportSerializer,
    ApiarySiteOnProposalProcessedGeometryExportSerializer,
)
from disturbance.settings import BASE_DIR, SPATIAL_DATA_DIR, TIME_ZONE

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Save the apiary sites as a json file"

    def handle(self, *args, **options):
        try:
            errors = []

            # 1. Retrieve 'vacant' sites
            qs_vacant_site_proposal, qs_vacant_site_approval = get_qs_vacant_site_for_export()
            # qs_vacant_site_proposal may not have the wkb_geometry_processed if the apiary site is the selected 'vacant' site

            serializer_vacant_proposal_d = ApiarySiteOnProposalDraftGeometryExportSerializer(
                qs_vacant_site_proposal.filter(wkb_geometry_processed__isnull=True), many=True
            )
            serializer_vacant_proposal = ApiarySiteOnProposalProcessedGeometryExportSerializer(
                qs_vacant_site_proposal.filter(wkb_geometry_processed__isnull=False), many=True
            )
            serializer_vacant_approval = ApiarySiteOnApprovalGeometryExportSerializer(
                qs_vacant_site_approval, many=True
            )

            # 2. ApiarySiteOnProposal
            qs_on_proposal_draft, qs_on_proposal_processed = get_qs_proposal_for_export()

            # 3. ApiarySiteOnApproval
            qs_on_approval = get_qs_approval_for_export()

            # 4. Exclude the duplicated sites from the qs_on_proposal_processed
            qs_on_proposal_processed = qs_on_proposal_processed.exclude(
                apiary_site__in=qs_on_approval.values("apiary_site")
            )

            # 5. Serialize them
            serializer_proposal_processed = ApiarySiteOnProposalProcessedGeometryExportSerializer(
                qs_on_proposal_processed, many=True
            )
            serializer_approval = ApiarySiteOnApprovalGeometryExportSerializer(qs_on_approval, many=True)

            # Merge all the data above
            serializer_approval.data["features"].extend(serializer_proposal_processed.data["features"])
            serializer_approval.data["features"].extend(serializer_vacant_proposal_d.data["features"])
            serializer_approval.data["features"].extend(serializer_vacant_proposal.data["features"])
            serializer_approval.data["features"].extend(serializer_vacant_approval.data["features"])

            save_dir = os.path.join(BASE_DIR, SPATIAL_DATA_DIR)
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)

            datetime_local = datetime.datetime.now(pytz.timezone(TIME_ZONE)).strftime("%Y%m%d-%H%M%S")
            file_path = os.path.join(save_dir, f"{datetime_local}-apiary-sites.json")
            with open(file_path, "w") as fp:
                json.dump(serializer_approval.data, fp)

            files = os.listdir(save_dir)
            files = sorted(files, reverse=True)  # sort by descending order
            for file in files[3:]:
                os.remove(os.path.join(save_dir, file))

        except Exception as e:
            err_msg = f"Error command {__name__}"
            logger.exception(f"{err_msg}\n{str(e)}")
            errors.append(err_msg)

        cmd_name = __name__.split(".")[-1].replace("_", " ").upper()
        err_str = (
            f'<strong style="color: red;">Errors: {len(errors)}</strong>'
            if len(errors) > 0
            else '<strong style="color: green;">Errors: 0</strong>'
        )
        msg = f"<p>{cmd_name} completed. {err_str}.</p>"
        logger.info(msg)
        print(msg)  # will redirect to cron_tasks.log file, by the parent script
