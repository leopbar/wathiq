# KYC-POL-003 — Identity documents: passports

> SYNTHETIC POLICY. Written for this demonstration. Not a real bank policy.

## §1.1 Required fields

A passport presented for a file refresh must show the passport number, the full name, the
nationality, the date of birth, the issue date and the expiry date. A missing passport number
makes the document unusable: it is the key that ties the passport to the rest of the file.

## §2.1 Validity

An expired passport cannot support a file refresh. The file remains open and the customer is
asked for a current document.

## §2.2 Internal date consistency

The issue date must precede the expiry date. Where it does not, the extraction is treated as
unreliable and an officer re-reads the document.

## §2.3 Remaining validity

A passport with less than six months of remaining validity is accepted for the refresh, but the
file is flagged so that a renewed copy is requested before the next periodic review. The file
should still be valid at the next review date, and six months is the margin that makes that
likely.

## §2.5 Machine-readable zone

Where a machine-readable zone is legible, the values read from it take precedence over the
printed values, because the printed values are more often damaged. Any disagreement between
the two is recorded on the case.
