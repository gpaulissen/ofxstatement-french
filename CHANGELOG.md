# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2020-03-23

### Added

	- Documentation mentions test_requirements.txt
	- More checks concerning the content (dates with start and end
	date exclusive) that may result in a ValidationError exception
	- Casden accounts also supported
	- Negative balances recognized

### Changed

	- The date will now be the accounting date (DATE COMPTA) instead of operation date (DATE OPERATION).
	- Handling of 29 february improved
	- Improved handling of graphics in the PDF which transforms to a
	description starting with F and whitespace.
	- The BIC is also recognized if the line does not end with a BIC
	followed by only whitespace (hence BIC<ws><number><ws><.+> is now
	allowed)
	- Better determination of the statement header.
	
## [1.0.0] - 2020-03-16

### Added

	- Converting the French BanquePopulaire PDFs to an OFX file.
