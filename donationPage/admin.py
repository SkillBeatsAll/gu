from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from .models import Donor, Currency, Donation, Subscription, S18ACertificate


class DonorAdmin(admin.ModelAdmin):
    list_display = ("pk", "name", "display_name", "email")
    list_editable = ("name", "display_name", "email")
    search_fields = ("name", "display_name", "email")
    fieldsets = (
        (None, {
            "fields": ("name", "display_name", "email", "donor_url"),
        }),
        ("SARS details (saved for tax certificates)", {
            "fields": ("nature_of_donor", "trading_name", "id_type",
                       "id_country", "id_number", "date_of_birth",
                       "income_tax_ref", "contact_number", "address"),
        }),
    )


# repeat for other models.
class DonationAdmin(admin.ModelAdmin):
    list_display = (
        "donor",
        "datetime_of_donation",
        "currency_type",
        "amount",
        "notified",
        "section18a_issued",
    )
    search_fields = [
        "donor__name",
        "donor__email",
        "donor__pk",
    ]
    # list_editable = ('donor', 'datetime_of_donation',
    #               'currency_type', 'amount','notified','section18a_issued',)


class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("donor", "status", "amount")
    search_fields = [
        "donor__name",
        "donor__email",
        "donor__pk",
    ]


class S18ACertificateAdmin(admin.ModelAdmin):
    """the custom staff pages are the source of truth for managing
    certificates, so the admin just acts as a gateway - the changelist is a
    handy, filterable index, but adding or opening a certificate sends you
    off to the richer custom pages (with approve / reject / email / PDF)."""

    list_display = ("receipt_number", "donor_name", "tax_year", "amount",
                    "status", "requested_by_donor", "requested_at",
                    "open_link")
    list_display_links = None
    list_filter = ("status", "requested_by_donor", "tax_year")
    search_fields = ("donor_name", "contact_email", "receipt_number",
                     "donor__name", "donor__email")
    change_list_template = "admin/donationPage/s18acertificate/change_list.html"

    @admin.display(description="Manage")
    def open_link(self, obj):
        return format_html(
            '<a class="button" href="{}">Open &rarr;</a>',
            reverse('s18a.staff.detail', args=[obj.pk]))

    def has_add_permission(self, request):
        # adding happens on the custom create page.
        return True

    def add_view(self, request, form_url='', extra_context=None):
        return redirect('s18a.staff.create')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        return redirect('s18a.staff.detail', pk=object_id)


admin.site.register(Donor, DonorAdmin)
admin.site.register(Currency)
admin.site.register(Subscription, SubscriptionAdmin)
admin.site.register(Donation, DonationAdmin)
admin.site.register(S18ACertificate, S18ACertificateAdmin)
