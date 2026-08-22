"""Export issued S18A certificates for SARS."""

import csv

from django.utils.formats import date_format

COLUMNS = [
    '',
    'S18A Receipt Number',
    'Date of Issue',
    'FirstNames',
    'Surname',
    'Nature of Donor',
    'IDNumber',
    'Date of Birth',
    'IncomeTaxRefNumber',
    'ContactNumber',
    'Email',
    'AddressLine1',
    'AddressLine2',
    'AddressLine3',
    'AddressLine4',
    'AddressLine5',
    'Nature of Donation',
    'RTotalDonated',
    'Date(s) of Donation',
]

ADDRESS_LINES = 5


def format_date(value):
    """Write dates out in full"""
    return date_format(value, "j F Y") if value else ""


def format_amount(value):
    formatted = "{:,.2f}".format(value or 0)
    return "R" + formatted.replace(",", " ").replace(".", ",")


def address_lines(address, count=ADDRESS_LINES):
    """A donor's address squeezed into exactly ``count`` cells - anything
    past the last cell gets folded into it instead of silently dropped."""
    lines = [line.strip() for line in (address or "").splitlines()]
    lines = [line for line in lines if line]
    if len(lines) > count:
        lines = lines[:count - 1] + [", ".join(lines[count - 1:])]
    return lines + [""] * (count - len(lines))


def row(certificate):
    return [
        '',
        certificate.receipt_number or "",
        format_date(certificate.date_of_issue),
        certificate.first_names_display,
        certificate.surname_display,
        (certificate.get_nature_of_donor_display()
         if certificate.nature_of_donor else ""),
        certificate.id_number,
        format_date(certificate.date_of_birth),
        certificate.income_tax_ref,
        certificate.contact_number,
        certificate.contact_email,
        *address_lines(certificate.address),
        certificate.nature_of_donation,
        format_amount(certificate.amount),
        certificate.date_of_donation_text,
    ]


def write(certificates, fh):
    """Write the header and one row per certificate to a file-like object."""
    writer = csv.writer(fh)
    writer.writerow(COLUMNS)
    for certificate in certificates:
        writer.writerow(row(certificate))
