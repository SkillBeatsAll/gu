import logging
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, models, transaction
from django.db.models import Max
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger("django")

NATURE_CHOICES = [
    ('natural_person', 'Natural Person'),
    ('company', 'Company'),
    ('close_corporation', 'Close Corporation'),
    ('trust', 'Trust'),
    ('partnership', 'Partnership'),
    ('other', 'Other'),
]

ID_TYPE_CHOICES = [
    ('sa_id', 'South African ID'),
    ('passport', 'Passport'),
    ('registration', 'Company Registration Number'),
    ('trust_number', "Master's Reference / Trust Number"),
    ('other', 'Other'),
]

DATE_OF_BIRTH_HELP = ("Required by SARS for a natural person who has no South "
                      "African ID number")


def needs_date_of_birth(nature_of_donor, id_type):
    """SARS will take a natural person's date of birth instead of an ID
    number, so it's mandatory for anyone identified by a passport or
    whatever else.
    """
    return nature_of_donor == 'natural_person' and id_type != 'sa_id'


# Create your models here.
#donor as a class let's us track the number of donations a given donor has made and highlight top donors as needed.
#this also let's us collect multiple donations together so lists won't be filled with a single donor
class Donor(models.Model):
    name=models.CharField(max_length=200)
    display_name=models.CharField(max_length=200, blank=True)
    email=models.CharField(max_length=200)
    donor_url=models.CharField(max_length=50, blank=True, unique=True) #cryptographically random token (secrets.token_urlsafe(32))

    nature_of_donor = models.CharField(
        max_length=20, choices=NATURE_CHOICES, blank=True)
    trading_name = models.CharField(
        max_length=200, blank=True,
        help_text="Trading name of the donor, if different from the registered name")
    id_type = models.CharField(
        max_length=20, choices=ID_TYPE_CHOICES, blank=True,
        verbose_name="identification type")
    id_country = models.CharField(
        max_length=60, blank=True, verbose_name="country of issue",
        help_text="Country that issued the identification (natural persons)")
    id_number = models.CharField(
        max_length=60, blank=True,
        verbose_name="identification / registration number")
    date_of_birth = models.DateField(
        null=True, blank=True, help_text=DATE_OF_BIRTH_HELP)
    income_tax_ref = models.CharField(
        max_length=60, blank=True, verbose_name="income tax reference number")
    contact_number = models.CharField(max_length=60, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name

    @property
    def needs_date_of_birth(self):
        return needs_date_of_birth(self.nature_of_donor, self.id_type)

class Currency(models.Model):
    currency_abr=models.CharField(max_length=5, unique=True)
    def __str__(self):
        return self.currency_abr

#the Donation class has to handle the individual donations and connect them to donor regardless of time and platform
class Donation(models.Model):

    TRANSACTION_STATUS = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending')
    ]

    PAYMENT_TYPE = [
        ('one_time', 'One Time'),
        ('subscription', 'Subscription')
    ]

    PLATFORM_OPTIONS = [
        ('paypal', 'Paypal'),
        ('snapscan', 'Snapscan'),
        ('payfast', 'Payfast')
    ]

    donor = models.ForeignKey(Donor, on_delete=models.CASCADE)
    datetime_of_donation = models.DateTimeField(blank=True, null=True)
    currency_type = models.ForeignKey(Currency, on_delete=models.CASCADE)
    amount = models.FloatField(default=0)
    notified = models.BooleanField(default=False)
    section18a_issued = models.BooleanField(default=False)
    transaction_id = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=TRANSACTION_STATUS,
        null=True, blank=True
    )
    payment_type = models.CharField(
        max_length=20, choices=PAYMENT_TYPE,
        null=True, blank=True
    )
    platform = models.CharField(
        max_length=50, choices=PLATFORM_OPTIONS,
        null=True, blank=True
    )

    def __str__(self):
        return str(self.datetime_of_donation) + "\t" + str(self.donor)

    def get_absolute_url(self):
        return reverse('donation.page', args=[])


class Subscription(models.Model):

    SUBSCRIPTION_STATUS = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('cancelled', 'Cancelled')
    ]

    donor = models.ForeignKey(Donor, on_delete=models.CASCADE)
    subscription_id = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=SUBSCRIPTION_STATUS)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    failed_payments = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.donor.email

# used when aggregating for a tax year
SUCCESSFUL_DONATION_STATUSES = {'success', 'complete', 'completed'}

SA_TAX_YEAR_START_MONTH = 3


class S18ACertificate(models.Model):
    """A Section 18A donation tax-deduction receipt.

    Can be linked to a Donor (self-service or staff-generated) or fully
    custom (staff typing in a donor/org that isn't in the system at all).
    We snapshot the donor's details at creation so the issued receipt can't
    change under you even if the donor edits their profile later. The
    receipt number only gets handed out once staff approve it.
    """

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_EMAILED = 'emailed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_EMAILED, 'Emailed to donor'),
    ]

    donor = models.ForeignKey(
        Donor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='certificates',
        help_text="Leave blank for a fully custom donor / organisation")

    # snapshot of the donor's details at the time we made the certificate.
    donor_name = models.CharField(max_length=200)
    first_names = models.CharField(
        max_length=200, blank=True,
        help_text="CSV export only. Leave blank to split the donor name.")
    surname = models.CharField(
        max_length=200, blank=True,
        help_text="CSV export only. Leave blank to split the donor name.")
    trading_name = models.CharField(
        max_length=200, blank=True,
        help_text="Trading name of the donor, if different from the registered name")
    nature_of_donor = models.CharField(
        max_length=20, choices=NATURE_CHOICES, blank=True)
    id_type = models.CharField(
        max_length=20, choices=ID_TYPE_CHOICES, blank=True,
        verbose_name="identification type")
    id_country = models.CharField(
        max_length=60, blank=True, verbose_name="country of issue")
    id_number = models.CharField(
        max_length=60, blank=True,
        verbose_name="identification / registration number")
    date_of_birth = models.DateField(
        null=True, blank=True, help_text=DATE_OF_BIRTH_HELP)
    income_tax_ref = models.CharField(
        max_length=60, blank=True, verbose_name="income tax reference number")
    contact_number = models.CharField(max_length=60, blank=True)
    contact_email = models.EmailField(max_length=200, blank=True)
    address = models.TextField(blank=True)

    # donation details
    tax_year = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Year of assessment ending end-February, e.g. 2026")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nature_of_donation = models.CharField(
        max_length=200, default="Cash (via EFT)",
        help_text="Nature of the donation, e.g. 'Cash (via EFT)'")
    date_of_donation_text = models.CharField(
        max_length=200, blank=True,
        help_text="Free text, e.g. 'R100 Monthly, March 2025 through February 2026'")
    donations = models.ManyToManyField(
        Donation, blank=True, related_name='certificates')

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    receipt_number = models.PositiveIntegerField(
        null=True, blank=True, unique=True,
        help_text="Allocated automatically on approval")
    requested_by_donor = models.BooleanField(default=False)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    rejection_reason = models.TextField(blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True, editable=False)
    staff_notes = models.TextField(blank=True)

    # TODO: change when Nathan resigns in 10 years
    signatory_name = models.CharField(max_length=100, default="Nathan Geffen")
    signatory_title = models.CharField(max_length=100, default="Director")
    signatory_date = models.DateField(null=True, blank=True)

    pdf_file = models.FileField(
        upload_to='s18a/', blank=True, null=True, editable=False,
        verbose_name="issued PDF")

    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['-requested_at']
        verbose_name = "S18A certificate"

    def __str__(self):
        ref = self.receipt_number or "draft"
        return "{} - {} - {}".format(ref, self.donor_name, self.get_status_display())

    def get_absolute_url(self):
        return reverse('s18a.staff.detail', args=[self.pk])

    @property
    def is_approved(self):
        return self.status in (self.STATUS_APPROVED, self.STATUS_EMAILED)

    @property
    def amount_display(self):
        """Display as rand (formated)"""
        formatted = "{:,.2f}".format(self.amount or Decimal('0'))
        formatted = formatted.replace(",", " ").replace(".", ",")
        return "R " + formatted

    @property
    def needs_id_country(self):
        return self.nature_of_donor == 'natural_person'

    @property
    def needs_date_of_birth(self):
        return needs_date_of_birth(self.nature_of_donor, self.id_type)

    @property
    def show_trading_name(self):
        return bool(self.trading_name) and self.trading_name != self.donor_name

    @property
    def date_of_issue(self):
        """the date the receipt was issued - what's printed on it, falling
        back to the approval date if that's not set."""
        if self.signatory_date:
            return self.signatory_date
        if self.approved_at:
            return timezone.localtime(self.approved_at).date()
        return None

    def _split_name(self):
        """(first names, surname) for a natural person 
        It just grabs the last whitespace-separated word as the surname. 
        entities keep their whole registered name in the first-names column"""
        if self.nature_of_donor != 'natural_person':
            return self.donor_name, ""
        parts = self.donor_name.split()
        if len(parts) < 2:
            return self.donor_name, ""
        return " ".join(parts[:-1]), parts[-1]

    @property
    def first_names_display(self):
        if self.first_names or self.surname:
            return self.first_names
        return self._split_name()[0]

    @property
    def surname_display(self):
        if self.first_names or self.surname:
            return self.surname
        return self._split_name()[1]


    def snapshot_from_donor(self, donor):
        """Copy the donor's saved SARS details onto this certificate."""
        self.donor = donor
        self.donor_name = donor.name
        self.trading_name = donor.trading_name
        self.nature_of_donor = donor.nature_of_donor
        self.id_type = donor.id_type
        self.id_country = donor.id_country
        self.id_number = donor.id_number
        self.date_of_birth = donor.date_of_birth
        self.income_tax_ref = donor.income_tax_ref
        self.contact_number = donor.contact_number
        self.contact_email = donor.email
        self.address = donor.address


    @staticmethod
    def tax_year_period(year):
        """(start, end) dates for a SA year of assessment.

        ``year`` is the calendar year the tax year ends in, e.g. 2026 covers
        1 March 2025 to 28/29 February 2026.
        """
        import calendar
        from datetime import date
        start = date(year - 1, SA_TAX_YEAR_START_MONTH, 1)
        last_day = calendar.monthrange(year, 2)[1]
        end = date(year, 2, last_day)
        return start, end

    @staticmethod
    def tax_year_for_date(dt):
        """The tax year (ending year) a datetime falls into.

        Stored datetimes are UTC, so we have to convert to local (SAST) time
        first - a donation at 00:30 on 1 March SAST is 22:30 on 28 February
        UTC, and belongs to the tax year that's only just starting.
        """
        local = timezone.localtime(dt) if timezone.is_aware(dt) else dt
        if local.month >= SA_TAX_YEAR_START_MONTH:
            return local.year + 1
        return local.year

    @staticmethod
    def successful_donations(donor):
        return Donation.objects.filter(
            donor=donor,
            status__in=SUCCESSFUL_DONATION_STATUSES,
            datetime_of_donation__isnull=False,
        )

    @staticmethod
    def available_tax_years(donor):
        """Tax years for which the donor has at least one successful donation."""
        years = set()
        for don in S18ACertificate.successful_donations(donor):
            years.add(S18ACertificate.tax_year_for_date(don.datetime_of_donation))
        return sorted(years, reverse=True)

    def build_from_tax_year(self, donor, year):
        start, end = self.tax_year_period(year)
        donations = self.successful_donations(donor).filter(
            datetime_of_donation__date__gte=start,
            datetime_of_donation__date__lte=end,
        ).order_by('datetime_of_donation')

        # Donation.amount is a float field, so add these up as Decimals
        # ourselves instead of letting the database sum floats first.
        total = sum((Decimal(str(a)) for a in
                     donations.values_list('amount', flat=True)), Decimal('0'))
        self.tax_year = year
        self.period_start = start
        self.period_end = end
        self.amount = total.quantize(Decimal('0.01'))
        self.date_of_donation_text = self._describe_dates(donations, start, end)
        return donations

    def link_period_donations(self):
        """Attach the donor's successful donations that fall inside this
        certificate's period. Needed for staff-created certificates, since
        the form only gives us the donor and the dates."""
        if not (self.donor_id and self.period_start and self.period_end):
            return
        self.donations.set(self.successful_donations(self.donor).filter(
            datetime_of_donation__date__gte=self.period_start,
            datetime_of_donation__date__lte=self.period_end))

    @staticmethod
    def _describe_dates(donations, start, end):
        """A human-readable blurb about when the donations came in."""
        dates = [timezone.localtime(d.datetime_of_donation)
                 if timezone.is_aware(d.datetime_of_donation)
                 else d.datetime_of_donation
                 for d in donations]
        if not dates:
            return ""
        if len(dates) == 1:
            return dates[0].strftime("%d %B %Y")
        return "{} through {}".format(
            dates[0].strftime("%B %Y"), dates[-1].strftime("%B %Y"))

    @staticmethod
    def allocate_receipt_number():
        """The next unique receipt number, carrying on the existing
        sequence and never reusing one.

        """
        start = getattr(settings, "S18A_RECEIPT_START", 332)
        current_max = S18ACertificate.objects.aggregate(
            m=Max('receipt_number'))['m']
        return max(current_max or 0, start - 1) + 1

    def approve(self, user, attempts=3):
        """Approve the certificate -> hand out the receipt number, stamp the
        signatory date, archive the issued PDF, and mark the covered
        donations as issued."""
        for attempt in range(attempts):
            try:
                with transaction.atomic():
                    if self.receipt_number is None:
                        self.receipt_number = self.allocate_receipt_number()
                    self.status = self.STATUS_APPROVED
                    self.approved_by = user
                    self.approved_at = timezone.now()
                    if self.signatory_date is None:
                        self.signatory_date = timezone.localdate()
                    self.save()
                break
            except IntegrityError:
                # someone else grabbed this receipt number first; we try next
                if attempt == attempts - 1:
                    raise
                self.receipt_number = None

        self.donations.update(section18a_issued=True)
        try:
            self.archive_pdf()
        except Exception as e:
            logger.error("Could not archive S18A certificate %s PDF: %s",
                         self.pk, e)

    def archive_pdf(self):
        """Render the certificate once and stash it, so every later
        download or emailed copy is byte-identical to the receipt as issued."""
        from .pdf import certificate_filename, render_certificate_pdf
        if self.pdf_file:
            return
        pdf = render_certificate_pdf(self)
        self.pdf_file.save(certificate_filename(self), ContentFile(pdf),
                           save=False)
        self.save(update_fields=['pdf_file', 'modified'])

    def mark_emailed(self):
        self.status = self.STATUS_EMAILED
        self.emailed_at = timezone.now()
        self.save(update_fields=['status', 'emailed_at', 'modified'])

    def reject(self, reason=""):
        """Reject a draft before it is issued.

        Issued receipts have a receipt number, linked donations, and an
        archived document. They must be voided through a dedicated audit
        workflow rather than silently disappearing from the donor portal
        while remaining in the SARS export.
        """
        if self.status != self.STATUS_PENDING or self.receipt_number is not None:
            raise ValueError("Only pending certificates can be rejected.")
        self.status = self.STATUS_REJECTED
        self.rejection_reason = reason
        self.save(update_fields=['status', 'rejection_reason', 'modified'])
