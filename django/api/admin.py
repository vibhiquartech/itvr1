from django.contrib import admin
from .models.go_electric_rebate_application import (
    GoElectricRebateApplication,
    GoElectricRebateApplicationWithFailedEmail,
    SearchableGoElectricRebateApplication,
    SubmittedGoElectricRebateApplication,
    CancellableGoElectricRebateApplication,
    DriverLicenceEditableGoElectricRebateApplication,
)
from .models.household_member import HouseholdMember
from .models.go_electric_rebate import GoElectricRebate
from .models.driver_licence_history import DriverLicenceHistory
from django.contrib import messages
from . import messages_custom
from django.db.models import Q
from django.db import transaction
from django.utils import timezone


class HouseholdApplicationInline(admin.StackedInline):
    model = HouseholdMember
    extra = 0
    exclude = ("sin", "doc1", "doc2", "user")
    readonly_fields = (
        "id",
        "last_name",
        "first_name",
        "middle_names",
        "date_of_birth",
        "bcsc_address",
        "bcsc_city",
        "bcsc_postal_code",
        "doc1_tag",
        "doc2_tag",
        "consent_personal",
        "consent_tax",
    )

    def has_delete_permission(self, request, obj=None):
        return False


def get_inlines(obj):
    # TODO update this to use the proper enum later.
    if obj and obj.application_type == "household":
        return [HouseholdApplicationInline]
    else:
        return []


@admin.register(GoElectricRebate)
class GoElectricRebateAdmin(admin.ModelAdmin):
    search_fields = ["application__id", "drivers_licence", "last_name"]
    actions = None
    exclude = ("application",)
    readonly_fields = (
        "application_id",
        "drivers_licence",
        "last_name",
        "expiry_date",
        "rebate_max_amount",
        "redeemed",
        "ncda_id",
        "created",
        "modified",
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DriverLicenceHistory)
class DriverLicenceHistoryAdmin(admin.ModelAdmin):
    search_fields = ["application__id", "drivers_licence"]
    actions = None
    exclude = ("application",)
    readonly_fields = (
        "application_id",
        "drivers_licence",
        "created",
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GoElectricRebateApplication)
class GoElectricRebateApplicationAdmin(admin.ModelAdmin):
    exclude = ("sin",)


# The proxy model is used to avoid a Django limitation where a model can only
# be registered once on the admin panel. This locked down version will be used
# by government staff to verify or decline submitted applications
# by BCeID users.
@admin.register(SubmittedGoElectricRebateApplication)
class SubmittedGoElectricRebateApplicationAdmin(admin.ModelAdmin):
    search_fields = ["drivers_licence", "id", "status", "last_name"]
    # disable bulk actions
    actions = None
    exclude = (
        "sin",
        "doc1",
        "doc2",
        "user",
        "spouse_email",
        "status",
        "application_type",
    )
    readonly_fields = (
        "id",
        "last_name",
        "first_name",
        "middle_names",
        "email",
        "user_is_bcsc",
        "address",
        "city",
        "postal_code",
        "drivers_licence",
        "date_of_birth",
        "tax_year",
        "doc1_tag",
        "doc2_tag",
        "consent_personal",
        "consent_tax",
        "is_legacy",
        "confirmation_email_success",
        "spouse_email_success",
        "created",
        "approved_on",
        "not_approved_on",
    )

    def get_queryset(self, request):
        return GoElectricRebateApplication.objects.filter(
            status=GoElectricRebateApplication.Status.SUBMITTED
        )

    def get_inlines(self, request, obj=None):
        return get_inlines(obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def response_change(self, request, obj):
        ret = super().response_change(request, obj)
        if "approve_application" in request.POST:
            obj.status = GoElectricRebateApplication.Status.VERIFIED
            obj.save(update_fields=["status"])
        if "reject_application" in request.POST:
            obj.status = GoElectricRebateApplication.Status.DECLINED
            obj.save(update_fields=["status"])
        return ret

    def message_user(
        self,
        request,
        message,
        level=messages.INFO,
        extra_tags="",
        fail_silently=False,
    ):
        revised_level = level
        if "reject_application" in request.POST:
            revised_level = messages_custom.NEGATIVE_SUCCESS
        super().message_user(request, message, revised_level, extra_tags, fail_silently)


@admin.register(CancellableGoElectricRebateApplication)
class CancellableGoElectricRebateApplicationAdmin(admin.ModelAdmin):
    search_fields = ["drivers_licence", "id", "status", "last_name"]
    # disable bulk actions
    actions = None
    exclude = (
        "sin",
        "doc1",
        "doc2",
        "user",
        "spouse_email",
        "status",
        "address",
        "city",
        "postal_code",
        "application_type",
        "doc1_tag",
        "doc2_tag",
        "consent_personal",
        "consent_tax",
        "reason_for_decline",
    )
    readonly_fields = (
        "id",
        "last_name",
        "first_name",
        "middle_names",
        "status",
        "email",
        "user_is_bcsc",
        "drivers_licence",
        "date_of_birth",
        "tax_year",
        "is_legacy",
        "confirmation_email_success",
        "spouse_email_success",
        "created",
        "approved_on",
        "not_approved_on",
    )

    def get_queryset(self, request):
        return GoElectricRebateApplication.objects.filter(
            Q(status=GoElectricRebateApplication.Status.HOUSEHOLD_INITIATED)
            | Q(status=GoElectricRebateApplication.Status.SUBMITTED)
            | Q(status=GoElectricRebateApplication.Status.APPROVED)
            | Q(status=GoElectricRebateApplication.Status.VERIFIED)
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def response_change(self, request, obj):
        ret = super().response_change(request, obj)
        if "cancel_application" in request.POST:
            dl = obj.drivers_licence
            GoElectricRebate.objects.filter(drivers_licence=dl).delete()
            obj.status = GoElectricRebateApplication.Status.CANCELLED
            obj.save(update_fields=["status"])
        return ret

    def message_user(
        self,
        request,
        message,
        level=messages.INFO,
        extra_tags="",
        fail_silently=False,
    ):
        revised_level = level
        if "cancel_application" in request.POST:
            revised_level = messages_custom.NEGATIVE_SUCCESS
        super().message_user(request, message, revised_level, extra_tags, fail_silently)


@admin.register(SearchableGoElectricRebateApplication)
class SearchableGoElectricRebateApplicationAdmin(admin.ModelAdmin):
    actions = None
    search_fields = ["drivers_licence", "id", "status", "last_name"]
    exclude = (
        "sin",
        "doc1",
        "doc2",
        "user",
    )
    readonly_fields = (
        "id",
        "last_name",
        "first_name",
        "middle_names",
        "status",
        "email",
        "user_is_bcsc",
        "address",
        "city",
        "postal_code",
        "drivers_licence",
        "date_of_birth",
        "tax_year",
        "application_type",
        "doc1_tag",
        "doc2_tag",
        "consent_personal",
        "consent_tax",
        "is_legacy",
        "confirmation_email_success",
        "spouse_email_success",
        "reason_for_decline",
        "rebate_max_amount",
        "created",
        "approved_on",
        "not_approved_on",
    )

    def rebate_max_amount(self, obj):
        return (
            GoElectricRebate.objects.get(application_id=obj.id).rebate_max_amount
            if obj.status == "approved"
            else "-"
        )

    rebate_max_amount.short_description = "Rebate Max Amount"

    def get_queryset(self, request):
        return GoElectricRebateApplication.objects.all()

    def has_delete_permission(self, request, obj=None):
        return False

    def get_inlines(self, request, obj=None):
        return get_inlines(obj)


@admin.register(GoElectricRebateApplicationWithFailedEmail)
class GoElectricRebateApplicationWithFailedEmailAdmin(admin.ModelAdmin):
    actions = None
    search_fields = ["drivers_licence", "id", "status", "last_name"]
    exclude = (
        "sin",
        "doc1",
        "doc2",
        "user",
        "tax_year",
        "consent_personal",
        "consent_tax",
        "is_legacy",
    )
    readonly_fields = (
        "id",
        "last_name",
        "first_name",
        "middle_names",
        "status",
        "email",
        "user_is_bcsc",
        "address",
        "city",
        "postal_code",
        "drivers_licence",
        "date_of_birth",
        "application_type",
        "doc1_tag",
        "doc2_tag",
        "confirmation_email_success",
        "spouse_email_success",
        "reason_for_decline",
        "created",
        "approved_on",
        "not_approved_on",
    )

    def get_queryset(self, request):
        return GoElectricRebateApplication.objects.filter(
            Q(confirmation_email_success=False) | Q(spouse_email_success=False)
        )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DriverLicenceEditableGoElectricRebateApplication)
class DriverLicenceEditableGoElectricRebateApplicationAdmin(admin.ModelAdmin):
    search_fields = ["drivers_licence", "id", "status", "last_name"]
    # disable bulk actions
    actions = None
    exclude = (
        "sin",
        "doc1",
        "doc2",
        "user",
        "spouse_email",
        "status",
        "address",
        "city",
        "postal_code",
        "application_type",
        "doc1_tag",
        "doc2_tag",
        "consent_personal",
        "consent_tax",
        "reason_for_decline",
    )
    # drivers_licence will be included in the form as an editable field
    readonly_fields = (
        "id",
        "last_name",
        "first_name",
        "middle_names",
        "status",
        "email",
        "user_is_bcsc",
        "date_of_birth",
        "tax_year",
        "is_legacy",
        "confirmation_email_success",
        "spouse_email_success",
        "created",
        "approved_on",
        "not_approved_on",
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if "edit_drivers_licence" in request.POST:
            return self.edit_drivers_licence(
                request, object_id, form_url, extra_context
            )
        return super().change_view(request, object_id, form_url, extra_context)

    def response_change(self, request, obj):
        ret = super().response_change(request, obj)
        if "edit_drivers_licence" in request.POST:
            GoElectricRebate.objects.filter(application__id=obj.id).update(
                drivers_licence=obj.drivers_licence, modified=timezone.now()
            )
        return ret

    @transaction.atomic
    def edit_drivers_licence(self, request, object_id, form_url, extra_context):
        application = GoElectricRebateApplication.objects.get(id=object_id)
        dl_history_entry = DriverLicenceHistory(
            drivers_licence=application.drivers_licence, application=application
        )
        dl_history_entry.save()
        return super().change_view(request, object_id, form_url, extra_context)
