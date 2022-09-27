import requests
import json
from django.utils import timezone

from django.conf import settings
from email.header import Header
from email.utils import formataddr
from requests.auth import HTTPBasicAuth
from api.services.ncda import get_rebates_redeemed_since
from api.models.go_electric_rebate import GoElectricRebate
from api.models.go_electric_rebate_application import (
    GoElectricRebateApplication,
)
from datetime import timedelta
from django.db.models.signals import post_save
from api.services.ncda import notify
from api.constants import (
    FOUR_THOUSAND_REBATE,
    ONE_THOUSAND_REBATE,
    TWO_THOUSAND_REBATE,
)
from api.utility import get_applicant_full_name
from django_q.tasks import async_task
from func_timeout import func_timeout, FunctionTimedOut
from sequences import get_next_value
from .services import cra
from datetime import date
import boto3
import botocore
from .services.rebate import get_applications, save_rebates, update_application_statuses
from .services.calculate_rebate import get_cra_results
import os
from io import BytesIO
def get_email_service_token() -> str:
    client_id = settings.EMAIL["EMAIL_SERVICE_CLIENT_ID"]
    client_secret = settings.EMAIL["EMAIL_SERVICE_CLIENT_SECRET"]
    url = settings.EMAIL["CHES_AUTH_URL"]
    payload = {"grant_type": "client_credentials"}
    header = {"content-type": "application/x-www-form-urlencoded"}

    token_rs = requests.post(
        url,
        data=payload,
        auth=HTTPBasicAuth(client_id, client_secret),
        headers=header,
        verify=True,
    )
    token_rs.raise_for_status()
    return token_rs.json()["access_token"]


def send_email(
    recipient_email: str,
    application_id: str,
    message: str,
    cc_list: list,
    optional_subject="",
) -> None:
    sender_email = settings.EMAIL["SENDER_EMAIL"]
    sender_name = settings.EMAIL["SENDER_NAME"]
    url = settings.EMAIL["CHES_EMAIL_URL"]

    subject = (
        "CleanBC Go Electric - Application #{}".format(application_id)
        + optional_subject
    )
    bodyType = "html"

    auth_token = get_email_service_token()
    sender_info = formataddr((str(Header(sender_name, "utf-8")), sender_email))

    data = {
        # "bcc": [recipient_email],
        "bodyType": bodyType,
        "body": message,
        "cc": cc_list,
        "delayTS": 0,
        "encoding": "utf-8",
        "from": sender_info,
        "priority": "normal",
        "subject": subject,
        # "to": ["Undisclosed recipients<donotreply@gov.bc.ca>"],
        "to": [recipient_email],
    }

    headers = {
        "Authorization": "Bearer " + auth_token,
        "Content-Type": "application/json",
    }

    response = requests.post(url, data=json.dumps(data), headers=headers)
    response.raise_for_status()


def send_individual_confirm(recipient_email, application_id):
    message = """\
        <html>
        <body>

        <p>
        This email was generated by the CleanBC Go Electric
        Passenger Vehicle Rebate program application.
        </p>

        <p>Thank you.</p>

        <p>
        We have received your application for a rebate under the CleanBC Go
        Electric Passenger Vehicle Rebate program. You can expect to get an email reply with the result of your application within 3 weeks.
        </p>

        <p>Please keep this e-mail for your records.</p>

        <p>Questions?</p>

        <p>Please feel free to contact us at ZEVPrograms@gov.bc.ca</p>
        </body>
        </html>
        """
    send_email(recipient_email, application_id, message, cc_list=[])


def send_spouse_initial_message(recipient_email, application_id, initiator_email):
    origin = settings.CORS_ORIGIN_WHITELIST[0]
    message = """\
        <html>
        <body>

        <p>
        You are receiving this e-mail as you have been identified as a
        spouse under a household rebate application for the CleanBC Go
        Electric Passenger Vehicle Rebate program.
        </p>

        <p>
        To finish the rebate application please click on the
        following link:
        </p>

        <p>{origin}/household?q={application_id}</p>

        <p><i>
        If you are not the intended person to receive this email, please
        contact the CleanBC Go Electric Passenger Vehicle Rebate program at
        ZEVPrograms@gov.bc.ca
        </i></p>

        <p>Additional Questions?</p>

        <p>Please feel free to contact us at ZEVPrograms@gov.bc.ca</p>
        </body>
        </html>
        """.format(
        origin=origin, application_id=application_id
    )
    send_email(recipient_email, application_id, message, [initiator_email])


def send_household_confirm(recipient_email, application_id):
    message = """\
        <html>
        <body>

        <p>
        This email was generated by the CleanBC Go Electric
        Passenger Vehicle Rebate program application.
        </p>

        <p>Thank you.</p>

        <p>
        We have now received all documentation for your application for a
        household rebate under the CleanBC Go Electric Passenger Vehicle
        Rebate program. You can expect to get an email reply with the result of your application within 3 weeks.
        </p>

        <p>Please keep this e-mail for your records.</p>

        <p>Questions?</p>

        <p>Please feel free to contact us at ZEVPrograms@gov.bc.ca</p>

        </body>
        </html>
        """
    send_email(recipient_email, application_id, message, cc_list=[])


def send_reject(recipient_email, application_id):
    message = """\
        <html>
        <body>

        <p>This email was generated by the CleanBC Go Electric Passenger
        Vehicle Rebate program application.</p>

        <p>Dear Applicant,</p>

        <p>Your application cannot be approved due to problems with identity documents.</p>

        <p>Some examples of why this may have happened include:</p>

        <ul>
            <li>
                Driver’s license/secondary piece of ID quality not sufficient or illegible.
            </li>
            <li>
                Secondary piece of ID doesn’t display full name and address or issue date exceeds 90 days.
            </li>
            <li>
                Both pieces of ID don’t match name and/or address.
            </li>
            <li>
                Household application addresses are not the same
                for applicant and spouse.
            </li>
            <li>
                Date of birth provided on the application doesn’t match 
                the date of birth on the driver’s license.
            </li>
        </ul>

        <b>You are encouraged to correct these issues and submit another application.</b>

        <p>Questions?</p>

        <p>Please feel free to contact us at ZEVPrograms@gov.bc.ca</p>
        </body>
        </html>
         """
    send_email(
        recipient_email,
        application_id,
        message,
        cc_list=[],
        optional_subject=" – Identity cannot be verified",
    )


def send_approve(recipient_email, application_id, applicant_full_name, rebate_amounts):
    message = """\
        <html>
        <body>

        <p>This email was generated by the CleanBC Go Electric Passenger
        Vehicle Rebate program application.</p>

        <p>Dear {applicant_full_name},</p>

        <p>Your application has been approved for a maximum rebate amount of up to ${zev_max}. </p>

        <p><b>${zev_max} rebate for long-range ZEV purchase</b> (BEV, FCEV, ER-EV, and PHEV with an electric range of 85 km or more)</p>
        <ul>
          <li>
            ${zev_max} rebate for long-range ZEV 36-month or longer lease term
          </li>
          <li>
            ${zev_mid} rebate for long-range ZEV 24-month lease term
          </li>
          <li>
            ${zev_min} rebate for long-range ZEV 12-month lease term
          </li>
        </ul>

        <p><b>${phev_max} rebate for short-range PHEV purchase</b> (PHEV with an electric range of less than 85 km)</p>
        <ul>
          <li>
            ${phev_max} rebate for short-range PHEV 36-month or longer lease term
          </li>
          <li>
            ${phev_mid} rebate for short-range PHEV 24-month lease term
          </li>
          <li>
            ${phev_min} rebate for short-range PHEV 12-month lease term
          </li>
        </ul>

        <p>This rebate approval will expire one year from today’s date.</p>
        
        <p>Next steps:</p>
        <ol>
          <li>
            Your approval is now linked to your driver’s licence. Bring your driver's licence with you to a new car dealer in B.C.
          </li>
          <li>
            Claim your rebate at the time of vehicle purchase to save money on your new zero-emission vehicle!
          </li>
        </ol>
        <p><i>Please note: This e-mail confirms that you have been approved for a
        rebate under the CleanBC Go Electric Light-Duty Vehicle program only.
        Accessing the rebate is conditional on Program funds being available
        at the time of vehicle purchase.</i></p>

        <p>Questions?</p>

        <p>Please feel free to contact us at ZEVPrograms@gov.bc.ca</p>
        </body>
        </html>
         """.format(
        applicant_full_name=applicant_full_name,
        zev_max=rebate_amounts.ZEV_MAX.value,
        zev_mid=rebate_amounts.ZEV_MID.value,
        zev_min=rebate_amounts.ZEV_MIN.value,
        phev_max=rebate_amounts.PHEV_MAX.value,
        phev_mid=rebate_amounts.PHEV_MID.value,
        phev_min=rebate_amounts.PHEV_MIN.value,
    )
    send_email(
        recipient_email,
        application_id,
        message,
        cc_list=[],
        optional_subject=" – Approved",
    )


def send_not_approve(recipient_email, application_id, tax_year):
    message = """\
        <html>
        <body>

        <p>This email was generated by the CleanBC Go Electric Passenger
        Vehicle Rebate program application.</p>

        <p>Dear Applicant,</p>

        <p>Your application has not been approved.</p>

        <p>Some examples of why this may have happened include:</p>

        <ul>
            <li>
                No record of your {tax_year} Notice of Assessment on file with the Canada Revenue Agency (CRA).
            </li>
            <li>
                The identity records that you have supplied do not match CRA records.
            </li>
            <li>
                Your income does not qualify/exceeds the maximum eligible amount under the program.
            </li>
        </ul>

        <p>Questions?</p>

        <p>Please feel free to contact us at ZEVPrograms@gov.bc.ca</p>
        </body>
        </html>
         """.format(
        tax_year=tax_year
    )
    send_email(
        recipient_email,
        application_id,
        message,
        cc_list=[],
        optional_subject=" – Not Approved",
    )


def send_cancel(recipient_email, application_id):
    message = """\
        <html>
        <body>

        <p>This email was generated by the CleanBC Go Electric Passenger
        Vehicle Rebate program application.</p>

        <p>Your application has been cancelled.</p>

        <p>Some examples of why this may have happened include:</p>

        <ul>
            <li>
                The person you identified as your spouse cancelled the application.
            </li>
            <li>
                The person you identified as your spouse didn’t complete the application within 28 days.
            </li>
        </ul>

        <p>You are encouraged to apply again as an individual if your spouse is unable to complete the household application.</p>

        <p>Questions?</p>

        <p>Please feel free to contact us at ZEVPrograms@gov.bc.ca</p>
        </body>
        </html>
         """
    send_email(
        recipient_email,
        application_id,
        message,
        cc_list=[],
        optional_subject=" – Cancelled",
    )


def send_rebates_to_ncda(max_number_of_rebates=100):
    def inner():
        rebates = GoElectricRebate.objects.filter(ncda_id__isnull=True)[
            :max_number_of_rebates
        ]
        for rebate in rebates:
            try:
                notify(
                    rebate.drivers_licence,
                    rebate.last_name,
                    rebate.expiry_date.strftime("%m/%d/%Y"),
                    str(rebate.rebate_max_amount),
                    rebate.id,
                )
                application = rebate.application
                if application and (
                    application.status == GoElectricRebateApplication.Status.APPROVED
                ):
                    if rebate.rebate_max_amount == 4000:
                        rebate_amounts = FOUR_THOUSAND_REBATE
                    elif rebate.rebate_max_amount == 2000:
                        rebate_amounts = TWO_THOUSAND_REBATE
                    else:
                        rebate_amounts = ONE_THOUSAND_REBATE
                    async_task(
                        "api.tasks.send_approve",
                        application.email,
                        application.id,
                        get_applicant_full_name(application),
                        rebate_amounts,
                    )
            except requests.HTTPError as ncda_error:
                print("error posting rebate to ncda")

    try:
        func_timeout(900, inner)
    except FunctionTimedOut:
        print("send_rebates_to_ncda timed out")
        raise Exception


# check for newly redeemed rebates
def check_rebates_redeemed_since(iso_ts=None):
    ts = iso_ts if iso_ts else timezone.now().strftime("%Y-%m-%dT00:00:00Z")
    print("check_rebate_status " + ts)
    ncda_ids = []
    get_rebates_redeemed_since(ts, ncda_ids, None)
    print(ncda_ids)

    redeemed_rebates = GoElectricRebate.objects.filter(ncda_id__in=ncda_ids)

    # mark redeemed
    redeemed_rebates.update(redeemed=True, modified=timezone.now())
    # update application status
    GoElectricRebateApplication.objects.filter(
        pk__in=list(redeemed_rebates.values_list("application_id", flat=True))
    ).update(
        status=GoElectricRebateApplication.Status.REDEEMED,
        modified=timezone.now(),
    )


# cancels household_initiated applications with a created_time <= (current_time - 28 days)
def cancel_untouched_household_applications():

    applications_qs = GoElectricRebateApplication.objects.filter(
        status=GoElectricRebateApplication.Status.HOUSEHOLD_INITIATED
    ).filter(created__lte=timezone.now() - timedelta(days=28))

    applications = list(applications_qs)

    applications_qs.update(
        status=GoElectricRebateApplication.Status.CANCELLED,
        modified=timezone.now(),
    )

    for application in applications:
        application.status = GoElectricRebateApplication.Status.CANCELLED
        post_save.send(
            sender=GoElectricRebateApplication,
            instance=application,
            created=False,
            update_fields={"status"},
        )


def expire_expired_applications():
    print('hello')
    expired_rebates = GoElectricRebate.objects.filter(redeemed=False).filter(
        expiry_date__lte=timezone.now().date()
    )

    expired_application_ids = []
    for rebate in expired_rebates:
        if rebate.application:
            expired_application_ids.append(rebate.application.id)

    GoElectricRebateApplication.objects.filter(id__in=expired_application_ids).update(
        status=GoElectricRebateApplication.Status.EXPIRED,
        modified=timezone.now(),
    )

def get_verified_applications_last_24hours():
    rebates =  GoElectricRebateApplication.objects.filter(
        status=GoElectricRebateApplication.Status.VERIFIED,
        created__gte=timezone.now() - timedelta(days=1),
    )
    data = []
    cra_env = settings.CRA_ENVIRONMENT
    cra_sequence = get_next_value("cra_sequence")
    program_code = "BCVR"

    for rebate in rebates:
        data.append(
            {
                "sin": rebate.sin,
                "years": [rebate.tax_year],
                "given_name": rebate.first_name,
                "family_name": rebate.last_name,
                "birth_date": rebate.date_of_birth.strftime("%Y%m%d"),
                "application_id": rebate.id,
            }
        )

        # TODO this should be some kind of enum like the status is.
        if rebate.application_type == "household":
            household_member = rebate.householdmember
            data.append(
                {
                    "sin": household_member.sin,
                    "years": [rebate.tax_year],
                    "given_name": household_member.first_name,
                    "family_name": household_member.last_name,
                    "birth_date": household_member.date_of_birth.strftime("%Y%m%d"),
                    "application_id": rebate.id,
                }
            )

    filename = get_cra_filename(program_code, cra_env, cra_sequence)
    today = date.today().strftime("%Y%m%d")
    with open(filename, "w") as file:
        res = cra.write(
                data,
                today=today,
                program_code=program_code,
                cra_env=cra_env,
                cra_sequence=f"{cra_sequence:05}",
            )
        file.write(res)
    upload_to_s3(filename)
  

def get_cra_filename(program_code="BCVR", cra_env="A", cra_sequence="00001"):
    filename = "TO.{cra_env}TO#@@00.R7005.IN.{program_code}.{cra_env}{cra_sequence:05}".format(
        cra_env=cra_env, cra_sequence=cra_sequence, program_code=program_code
    )
    print(filename)
    return filename


def upload_to_s3(file):
    AWS_ACCESS_KEY_ID = 'nr-itvr-tst'
    AWS_S3_ENDPOINT_URL = 'https://nrs.objectstore.gov.bc.ca:443'
    AWS_SECRET_ACCESS_KEY = 'xVNKLDynorU12GYSTNfWvo2plBVxp6Wl2xsTwHSj'

    client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        endpoint_url=AWS_S3_ENDPOINT_URL
    )

    BUCKET_NAME = 'itvrts'
    UPLOAD_FOLDER_NAME = 'cra/encrypt'

    client.upload_file(file, BUCKET_NAME, '%s/%s' % (UPLOAD_FOLDER_NAME, file))

def download_from_s3():
    # Download file from s3
    AWS_ACCESS_KEY_ID = 'nr-itvr-tst'
    AWS_S3_ENDPOINT_URL = 'https://nrs.objectstore.gov.bc.ca:443'
    AWS_SECRET_ACCESS_KEY = 'xVNKLDynorU12GYSTNfWvo2plBVxp6Wl2xsTwHSj'

    client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        endpoint_url = AWS_S3_ENDPOINT_URL
    )
    resource = boto3.resource(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        endpoint_url = AWS_S3_ENDPOINT_URL
    )

    BUCKET_NAME = 'itvrts'
    DOWNLOAD_FOLDER_NAME = 'cra/decrypt'

    my_bucket = resource.Bucket(BUCKET_NAME)
    files = my_bucket.objects.filter(Prefix=DOWNLOAD_FOLDER_NAME)
    object = [obj.key for obj in sorted(files, key=lambda x: x.last_modified,
        reverse=True)][0]
    file = object.split('/')[-1]

    try:
        client.download_file(BUCKET_NAME, object, file)
        obj = resource.Object(BUCKET_NAME, object)
        dataa = obj.get()['Body'].read().decode("utf-8")
        data = cra.read(dataa)
        rebates = get_cra_results(data)
        associated_applications = get_applications(rebates)
        save_rebates(rebates, associated_applications)
        update_application_statuses(rebates, associated_applications)
        print(data)
        return data
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            print("The object does not exist.")
        else:
            raise