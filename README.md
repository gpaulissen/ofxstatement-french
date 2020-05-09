# ofxstatement-french

This project provides custom
[ofxstatement](https://github.com/kedder/ofxstatement) plugin(s) for these french
financial institutions:
- BanquePopulaire, France, PDF (https://www.banquepopulaire.fr/)

`ofxstatement` is a tool to convert a proprietary bank statement to OFX
format, suitable for importing into programs like GnuCash or Beancount. The
plugin for ofxstatement parses the bank statement and produces a common data
structure, that is then formatted into an OFX file.

The PDF is converted using the
[pdftotext](https://pypi.org/project/pdftotext/) utility.

## Installation

### Preconditions

You have to install the poppler library first, see
[pdftotext](https://pypi.org/project/pdftotext/)

### Using pip

```
$ pip install ofxstatement-french
```

### Development version from source

```
$ git clone https://github.com/gpaulissen/ofxstatement-french.git
$ pip install -e .
```

### Troubleshooting

This package depends on ofxstatement with a version at least 0.6.5. This
version may not yet be available in PyPI so install that from source like
this:
```
$ git clone https://github.com/gpaulissen/ofxstatement.git
$ pip install -e .
```

## Test

To run the tests from the development version you can use the py.test command:

```
$ py.test
```

You may need to install the required test packages first:

```
$ pip install -r test_requirements.txt
```

## Usage

### Show installed plugins

This shows the all installed plugins, not only those from this package:

```
$ ofxstatement list-plugins
```

You should see at least:

```
The following plugins are available:

  ...
  fr-banquepopulaire BanquePopulaire, France, PDF (https://www.banquepopulaire.fr/)
  ...

```

### Convert

Use something like this:

```
$ ofxstatement convert -t fr-banquepopulaire <file>.pdf <file>.ofx
```

Or you can convert the PDF yourself and supply the text as input:

```
$ pdftotext -layout <file>.pdf <file>.txt
$ ofxstatement convert -t fr-banquepopulaire <file>.txt <file>.ofx
```

See also the section configuration below.

### Configuration

For BanquePopulaire you may download their OFX files and use them to provide
you with their OFX FITID numbers instead of relying on FITID numbers generated
by the ofxstatement tool. You can specifiy the OFX files to read first using
the ofxstatement configuration. The OFX files configuration is a file wildcard
relative to the PDF to convert.

```
$ ofxstatement edit-config
```

This is a sample configuration (do not forget to specify the plugin for each section):

```
[banquepopulaire]
plugin = fr-banquepopulaire
ofx_files = *.ofx, ../*.ofx
```

Now this statement will convert <file>.pdf downloaded from BanquePopulaire
(Mon Espace -> Mes documents électroniques -> Comptes) to <file>.ofx while
using the FITIDs found in the *.ofx files in the directory of <file>.pdf or in
its parent directory.

```
$ ofxstatement convert -t banquepopulaire <file>.pdf <file>.ofx
```

## Change history

See the Changelog (CHANGELOG.md).
