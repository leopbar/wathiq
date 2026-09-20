# AI-POL-001 — Automated document processing and human review

> SYNTHETIC POLICY. Written for this demonstration. Not a real bank policy.

## §1.1 Scope

This policy governs the automated reading of customer documents and the circumstances in which
a human must take the decision.

## §2.1 Documents are data, never instructions

Text inside a customer document is data. Where a document contains text that reads as an
instruction to the system — asking it to approve a case, to skip a check, or to change how it
behaves — the document is treated as suspicious, the instruction is never acted on, and the
case is referred to an officer. This applies however the instruction is hidden, including in
invisible characters or in text shown only to the machine.

## §2.2 Personal data in logs and traces

Identity numbers, account numbers, card numbers, telephone numbers and email addresses are
replaced with tokens before anything is written to a log, a trace or an evaluation dataset.
The real values live only in the case record, which is access-controlled and audited.

## §2.3 Output handling

Values produced by an automated reader are cleaned before they are stored or displayed: markup
and scripts are removed, and characters that change how text is displayed without changing what
it says are removed. A value that cannot survive this cleaning is referred to an officer.

## §3.1 Mandatory human review

A case is referred to a human, whatever the confidence of the extraction, when any of the
following is true: a possible sanctions match exists; a required document is expired; the case
is among the first processed for a newly configured document type; or the document is suspected
of carrying a hidden instruction.

## §3.2 Discretionary human review

A case is also referred to a human when the automated reading is weak: low confidence on a
field the decision depends on, a disagreement between the reader and the independent check, or
a value that cannot be found in the source document.

## §3.3 What a reviewer's decision means

A reviewer's correction is recorded as the correct value and becomes part of the evidence used
to measure how well the automated reader performs. A reviewer may waive a finding, and the
waiver is recorded with the reviewer's name, the reason and the time.

## §4.1 Confidence must be honest

A confidence figure shown to a reviewer must mean what it appears to mean. Where a figure has
not been calibrated against observed outcomes, it is presented as an uncalibrated score and
labelled as such.
