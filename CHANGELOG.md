# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.5.0] - 2023-12-29

## Changed

- [Determination of OFX FITID for a PDF must use final OFX FITIDs from the cache.](https://github.com/gpaulissen/ofxstatement-french/issues/1)

## [1.4.1] - 2022-02-23

### Changed

- The plugin ofx_files which is a list of file specifications is checked for containing files

## [1.4.0] - 2021-01-18

### Added

- Ability to set the bank id in the configuration.

## [1.3.1] - 2020-05-23

### Changed

- In case a transaction is duplicated (in several files), the
  latest transaction and thus FITID read will prevail. A transaction
  key is composed of ACCTID, CHECKNUM, DTPOSTED, TRNAMT and NAME
  (either CHECKNUM or NAME is empty).

## [1.3.0] - 2020-05-23

### Changed

- Replaced the ofxparse library by beautifulsoup4 since the former
  does only read one bank account and a BanquePopulaire OFX file
  may contain several bank accounts (conform the OFX standard).
- The ofx_files configuration may be a list of comma separated
  file name specifications instead of just one file name
  specification.
- The ofx_files cache will provide the OFX FITID for PDF statement
  line ID if there is a match on any of the three dates (DATE
  COMPTA, DATE OPERATION, DATE VALEUR) in the PDF. Usually DATE
  COMPTA is equal to DTPOSTED from the OFX, but not always.
- The ofx_files cache will provide the PAYEE and MEMO fields if
  there is a match since BanquePopulaire does not necessarily show
  the same values for the same transaction in a PDF and OFX file.

## [1.2.0] - 2020-05-02

### Changed

- Added the ability to retrieve the OFX id (FITID) from OFX files
  downloaded from BanquePopulaire instead of using an id generated
  by the ofxstatement tool.

## [1.1.1] - 2020-03-23

### Changed

- The generation af a unique OFX id did only return a counter in
  case of duplicates
- The Readme mentions now my fork of the ofxstatement instead of
  https://github.com/kedder/ofxstatement.git
- The __about__.py file outputs the version number and that is
  used in the Makefile
- The Makefile depends now on GNU make for tagging a release

## [1.1.0] - 2020-03-22

### Added

- This Changelog
- The Readme mentions test_requirements.txt for installing test modules
- More checks concerning the content (dates with start and end
  date exclusive) that may result in a ValidationError exception
- Casden accounts also supported
- Negative balances recognized
- Added Makefile for keeping the important operations together

### Changed

- The date will now be the accounting date (DATE COMPTA) instead of operation date (DATE OPERATION).
- Handling of 29 february improved
- Improved handling of graphics in the PDF which transforms to a
  description starting with F and whitespace.
- The BIC is also recognized if the line does not end with a BIC
  followed by only whitespace (hence BIC<ws><number><ws><.+> is now
  allowed)
- Better determination of the statement header.

## [1.0.0] 2020-03-16

### Added

- Converting the French BanquePopulaire PDFs to an OFX file.
