from ajax_select.fields import AutoCompleteSelectField
from ajax_select.fields import AutoCompleteSelectMultipleField
from ajax_select import make_ajax_field
from django import forms
from django.utils.html import strip_tags
from filebrowser.settings import ADMIN_VERSIONS, VERSIONS
from . import models, utils
from newsroom.settings import SEARCH_MAXLEN


class DonorForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    name = forms.CharField(max_length=50)
    display_name = forms.CharField(max_length=50)
    #donor_url = forms.CharField(max_length=60)
    
    class Meta:
        model = models.Donor
        fields = ['name', 'display_name', 'email',]

class CurrencyForm(forms.ModelForm):
    currency_abr=forms.CharField(max_length=100)
    
    class Meta:
        model = models.Currency
        fields = ['currency_abr']

class DonationForm(forms.ModelForm):
    donation_date = forms.DateTimeField()
    #donor = forms.ForeignKey(Donor, on_delete=models.CASCADE)
    #donor = AutoCompleteSelectField("donors", required=True, help_text=None, label="donor")
    #platform = forms.ForeignKey(Platform,  on_delete=models.CASCADE)
    recurring = forms.BooleanField()
    donation_amount = forms.IntegerField()
    currency_type = forms.CharField(max_length=4)
    #certificate_issued = models.BooleanField(default=False)

    class Meta:
        model = models.Donation
        fields = ['datetime_of_donation', 'donor', 'currency_type', 'notified', 'amount', 'section18a_issued']


class CertificateRequestForm(forms.ModelForm):
    """Donor-facing form to request an S18A certificate for a tax year.

    The SARS detail fields are bound to the Donor, 
    """
    tax_year = forms.ChoiceField(
        label="Tax year",
        help_text="South African tax year (1 March - end February)")

    class Meta:
        model = models.Donor
        fields = [
            'name', 'trading_name', 'nature_of_donor',
            'id_type', 'id_country', 'id_number', 'date_of_birth',
            'income_tax_ref', 'contact_number', 'email', 'address',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        tax_years = kwargs.pop('tax_years', [])
        super().__init__(*args, **kwargs)
        self.fields['tax_year'].choices = [
            (str(y), "1 March {} - February {}".format(y - 1, y))
            for y in tax_years
        ]
        # helps donors understand which fields SARS actually needs.
        self.fields['name'].label = "Full name / registered name"
        for required in ('name', 'email', 'nature_of_donor', 'id_type',
                         'id_number', 'address'):
            self.fields[required].required = True
        self.fields['id_number'].help_text = (
            "Required by SARS: your ID, passport, company registration or "
            "trust number.")
        self.fields['address'].help_text = "Required by SARS."
        self.fields['id_country'].help_text = (
            "Required for natural persons: the country that issued the "
            "identification above.")
        self.fields['date_of_birth'].help_text = (
            "Only needed if you are an individual without a South African ID "
            "number - SARS identifies you by your date of birth instead.")
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (css + ' form-control').strip()

    def clean(self):
        cleaned = super().clean()
        # country of issue only really matters for a natural person's ID -
        # mirrors S18ACertificate.needs_id_country.
        if (cleaned.get('nature_of_donor') == 'natural_person'
                and not cleaned.get('id_country')):
            self.add_error('id_country',
                           "Please give the country that issued your "
                           "identification.")
        if (models.needs_date_of_birth(cleaned.get('nature_of_donor'),
                                       cleaned.get('id_type'))
                and not cleaned.get('date_of_birth')):
            self.add_error('date_of_birth',
                           "SARS requires your date of birth when you do not "
                           "have a South African ID number.")
        return cleaned


class StaffCertificateForm(forms.ModelForm):
    """Full staff form for creating / editing a certificate, including a
    totally custom donor / organisation (just leave ``donor`` blank and fill
    in the snapshot fields directly)."""

    class Meta:
        model = models.S18ACertificate
        fields = [
            'donor',
            'donor_name', 'first_names', 'surname',
            'trading_name', 'nature_of_donor',
            'id_type', 'id_country', 'id_number', 'date_of_birth',
            'income_tax_ref',
            'contact_number', 'contact_email', 'address',
            'tax_year', 'period_start', 'period_end',
            'amount', 'nature_of_donation', 'date_of_donation_text',
            'signatory_name', 'signatory_title', 'signatory_date',
            'staff_notes',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'staff_notes': forms.Textarea(attrs={'rows': 2}),
            'period_start': forms.DateInput(attrs={'type': 'date'}),
            'period_end': forms.DateInput(attrs={'type': 'date'}),
            'signatory_date': forms.DateInput(attrs={'type': 'date'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['donor'].required = False
        self.fields['donor_name'].required = True

        # A receipt number means this document has been issued and archived.
        # Ideally, this should not change after issue (SARS audits etc)
        if self.instance.pk and self.instance.receipt_number:
            for locked in self.Meta.fields:
                if locked == 'staff_notes':
                    continue
                self.fields[locked].disabled = True
                self.fields[locked].help_text = (
                    "Locked: this certificate has been issued as receipt "
                    "no. {}.".format(self.instance.receipt_number))

        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = (css + ' form-control').strip()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('donor_name'):
            donor = cleaned.get('donor')
            if donor:
                cleaned['donor_name'] = donor.name
            else:
                self.add_error('donor_name', "A donor name is required.")
        # SARS keys a natural person on their ID number, or their date of
        # birth if they have no South African ID
        if (models.needs_date_of_birth(cleaned.get('nature_of_donor'),
                                       cleaned.get('id_type'))
                and not cleaned.get('date_of_birth')):
            self.add_error('date_of_birth',
                           "SARS requires a date of birth for a natural person "
                           "without a South African ID number.")
        return cleaned


class CertificateEmailForm(forms.Form):
    """The customisable version of the donor email."""

    subject = forms.CharField(max_length=200)
    message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 14}),
        help_text="Plain text. Blank lines become paragraphs in the email.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (css + ' form-control').strip()


class PayfastPaymentForm(DonorForm):
    # Add the payment_type field as a radio button
    PAYMENT_CHOICES = [
        ('subscription', 'Subscription'),
        ('one_time', 'One-time Payment'),
    ]

    first_name = forms.CharField(max_length=30, label="First Name")
    last_name = forms.CharField(max_length=30, label="Last Name")
    payment_type = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect,
        required=True,
        label="Payment Type"
    )

    # Add the amount field with a default value of 100, greater than 0
    amount = forms.IntegerField(
        min_value=1,
        initial=100,
        required=True,
        label="Donation Amount (ZAR)",
        help_text="Enter amount in ZAR"
    )
    name = forms.CharField(max_length=100, required=False)
    display_name = forms.CharField(max_length=100, required=False)

    class Meta(DonorForm.Meta):
        # Include the new fields along with inherited ones
        fields = ['first_name', 'last_name', 'email', 'payment_type', 'amount']

    def clean(self):
        cleaned_data = super().clean()

        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        email = cleaned_data.get('email')
        name = ""
        # Set the name as first_name + last_name if either is provided
        if first_name or last_name:
            name = f"{first_name or ''} {last_name or ''}".strip()

        # Set the display_name to the name or fallback to email username
        if not name.strip() and email:
            email_username = email.split('@')[0]
            cleaned_data['display_name'] = email_username
            cleaned_data['name'] = email_username
        else:
            cleaned_data['display_name'] = name
            cleaned_data['name'] = name
        return cleaned_data
