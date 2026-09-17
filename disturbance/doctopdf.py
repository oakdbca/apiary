import logging
import os
import subprocess
import tempfile

from django.conf import settings
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage, R
from rest_framework.exceptions import ValidationError

from disturbance.components.main.models import ApiaryGlobalSettings

logger = logging.getLogger(__name__)


def create_apiary_licence_pdf_contents(approval, proposal, copied_to_permit, site_transfer_preview=None):
    from disturbance.components.approvals.models import Approval
    from disturbance.components.approvals.serializers import ApprovalSerializerForLicenceDoc

    licence_template = ApiaryGlobalSettings.objects.filter(
        key=ApiaryGlobalSettings.KEY_APIARY_LICENCE_TEMPLATE_FILE
    ).first()

    if licence_template and licence_template._file:
        path_to_template = licence_template._file.path
    else:
        path_to_template = os.path.join(
            settings.BASE_DIR, "disturbance", "static", "disturbance", "apiary_authority_permit_template_v3.docx"
        )

    doc = DocxTemplate(path_to_template)
    path_to_image = os.path.join(settings.BASE_DIR, "disturbance", "static", "disturbance", "img", "dbca-logo.jpg")

    serializer_context = {
        "approver_id": approval.approver_id,
        "site_transfer_preview": site_transfer_preview,
    }

    approval = (
        Approval.objects.select_related(
            "applicant",
            "current_proposal",
            "current_proposal__proposal_apiary",
        )
        .prefetch_related(
            "apiary_sites",
            "proposalrequirement_set",
        )
        .get(id=approval.id)
    )

    context = ApprovalSerializerForLicenceDoc(approval, context=serializer_context).data

    context.update(
        {
            "dbca_logo": InlineImage(doc, image_descriptor=path_to_image, width=Mm(135), height=Mm(20)),
            "page_break": R("\f"),
        }
    )

    doc.render(context)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_docx_path = os.path.join(temp_dir, "licence.docx")
        doc.save(temp_docx_path)

        try:
            cmd = [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                temp_docx_path,
                "--outdir",
                temp_dir,
            ]

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=60,
            )

            temp_pdf_path = os.path.join(temp_dir, "licence.pdf")
            if not os.path.exists(temp_pdf_path):
                raise FileNotFoundError(f"Generated PDF not found at {temp_pdf_path}")

            with open(temp_pdf_path, "rb") as f:
                pdf_bytes = f.read()

        except subprocess.TimeoutExpired as e:
            logger.error(
                "LibreOffice conversion timed out for Approval ID %s: %s",
                approval.id,
                e,
                exc_info=True,
            )
            raise ValidationError("The PDF conversion service timed out. Please try again or contact OIM Service Desk.")
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            stderr_msg = e.stderr.decode("utf-8", errors="ignore") if hasattr(e, "stderr") and e.stderr else ""
            logger.error(
                "LibreOffice conversion failed for Approval ID %s: %s | stderr: %s",
                approval.id,
                e,
                stderr_msg,
                exc_info=True,
            )
            raise ValidationError(
                "An error occurred while generating the licence PDF via LibreOffice. "
                "Please try again or contact OIM Service Desk."
            )
        except Exception as e:
            logger.error(
                "Unexpected error during PDF generation for Approval ID %s: %s",
                approval.id,
                e,
                exc_info=True,
            )
            raise ValidationError(f"An unexpected error occurred while generating the licence PDF: {str(e)}")

    return pdf_bytes
