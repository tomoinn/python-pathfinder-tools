# Python-pathfinder-tools

A set of utilities to do things related to the 
Pathfinder tabletop role playing game. These tools are really intended 
for those already comfortable with Python, they may also have external
dependencies. Tested on linux and MacOS.

There are some command-line tools, and some utility libraries you could use
to write your own tools if you were so minded.

At the moment this isn't uploaded anywhere, so to install you'll want to do:

```
> git checkout https://github.com/tomoinn/python-pathfinder-tools.git
> cd python-pathfinder-tools/src/python
> python3 setup.py install
```

Requires Python3.7 upwards, use a virtual environment by preference, although it'll probably
work without one.

# Tools

## Chronicle sheets

A command-line tool to pull information out of a reporting sheet created as a
Google Docs spreadsheet, extract the chronicle sheet from a scenario PDF, and
merge the two, creating single-page PDF chronicle sheets for each player and
for the GM with everything filled in.

### Usage

```
> pfs_sheets -h

usage: pfs_sheets [-h] [-s SEASON] scenario_pdf [output_dir]

positional arguments:
  scenario_pdf          fetch chronicle sheet from INPUT_PDF
  output_dir            write sheets to OUTPUT_DIR, will be created if not
                        found, if not specified, will use chronicle-sheets
                        alongside the input scenario PDF.

optional arguments:
  -h, --help            show this help message and exit
  -s SEASON, --season SEASON
                        Explicitly set the season, normally we can auto-detect
                        this
```
To get your player information into the system you will need to copy this Google sheet:

https://docs.google.com/spreadsheets/d/1QozrfVAk0Z8lLiBil6VTblWlpqRf3XS-wVb7c5uBAVo/edit?usp=sharing

Once you've done that, you'll need to make your copy publicly accessible (it doesn't have to be
editable although it's harmless enough to do so, and lets your players fill in their own info). You
then need to work out the URL to download a CSV of the **'Export - DO NOT EDIT'** sheet within this
doc. You can construct this by opening the sheet, selecting the export sheet, and copying the URL
shown in the browser address bar. You will then need to change this URL:

*  Your URL will currently end with something like `edit#gid=461828162`
*  Change this to be `export?format=csv&gid=461828162` - this sets export mode, tells it to
use a CSV file, and the `gid` bit means it'll export the right sheet rather than the first one

When you've got your URL you can test it by putting that into a browser, it should cause a
CSV file to download.

Run the `pfs_sheets` tool once, it'll fail, but this will create a default configuration file
into which you can put your new URL. Edit that file, it'll be found in `~/.pathfinder/config.yaml` 
and change the `sheets: url:` to point to your new doc.

Once this is done you can enter data into the `Players` and `GM` parts of the sheets and it'll
pick them up when you run the tool.

To add your signature and initials to the generated sheets you need to put two images inside the `~/.pathfinder/`
directory:

1. `signature.png` is used for the main signature
2. `initials.png` is used for the 'GM initials' boxes

The code will scale these to fit, I've used a 100x60 PNG for my initials and a 1251x233 one for my signature
because I was too lazy to shrink it.

Once you've got all these done you can run the tool with `pfs_sheets SCENARIO_PDF [OUTPUT_DIR] [-s SEASON]` - if you don't specify the output
directory it'll create a new `chronicle-sheets` alongside the input PDF, and if you don't specify
the season it'll try to infer it from the scenario PDF, this normally works okay.

## Maps

Tools to pull out map images from scenario PDFs, apply a neural net based scaler to increase their
resolution, and then to emit one of three kinds of output:

1. Tiled PDFs ready to print out and stick together, these include configuration for print margins and overlap
to make it easier to cut and stick.
2. Single page PDF scaled exactly to the size of the map, this is what you'll need if you're having the map
printed by a professional print shop.
3. Single upscaled PNG image, this is what we're using for games on Roll20

### Installation

* Requires the pdfimages tool from poppler-utils to extract images
  from scenario PDFs (install with apt or brew)
* Requires waifu2x to do smart upscaling, although if it's not present
  the tools will still run at lower quality. On linux you'll need
  to install torch, have a CUDA compatible GPU, and build waifu2x. On
  MacOS there's a port to use the metal API, it can be downloaded from
  https://github.com/imxieyi/waifu2x-mac/releases
  
### Usage

This is a three-stage process. Firstly you run `pfs_extract` to pull images that look like they might be maps,
as well as any other large images (it's nice to have these for characters and scenes especially if you're using
a virtual tabletop). Secondly you go through the output, removing any duplicates, files that aren't maps, and 
renaming anything you want to use as a map. Map images must be named e.g. `canyon_25x30.png` - this lets the
final part of the process know how big (in one inch squares) the map needs to be. Finally you run the `pfs_build_maps`
tool which scans a directory for images with the right name pattern, scales and de-noises, does some basic
image processing operations, and packages them into your choice of output format.

```
> pfs_extract -h

usage: pfs_extract [-h] [-p PAGE] [-t TOPAGE] input_pdf output_dir

positional arguments:
  input_pdf             search INPUT_PDF for map images
  output_dir            write images to OUTPUT_DIR, will be created if not
                        found

optional arguments:
  -h, --help            show this help message and exit
  -p PAGE, --page PAGE  optionally only extract from the given page
  -t TOPAGE, --topage TOPAGE
                        optionally extract up to the given page (inclusive)
```

```
> pfs_build_maps -h

usage: pfs_build_maps [-h] [-c COLOUR] [-s SHARPEN] [-b BRIGHTEN] [-w SCALE]
                      [-p PADDING] [-o OVERLAP] [-a PAPER_SIZE] [-m MODE]
                      [-x PRESET]
                      input_dir [output_dir]

positional arguments:
  input_dir             search INPUT_DIR for map images of form name_WWxHH.png
  output_dir            write images to OUTPUT_DIR, will be created if not
                        found. If not supplied, will use input_dir.

optional arguments:
  -h, --help            show this help message and exit
  -c COLOUR, --colour COLOUR
                        saturation, 0.0-2.0, default 1.0
  -s SHARPEN, --sharpen SHARPEN
                        sharpen, 0.0-2.0, default 1.1
  -b BRIGHTEN, --brighten BRIGHTEN
                        brighten, 0.0-2.0, default 1.2
  -w SCALE, --scale SCALE
                        number of additional scaling operations after initial
                        scale + denoise pass, default 1
  -p PADDING, --padding PADDING
                        tiled mode only - padding per output page in mm,
                        default 5
  -o OVERLAP, --overlap OVERLAP
                        tiled and single modes only - overlap on bottom right
                        edges in mm, default 3
  -a PAPER_SIZE, --paper_size PAPER_SIZE
                        tiled mode only - paper size from [A4|A3|A2|A1|A0],
                        default A4
  -m MODE, --mode MODE  mode, from [tiled|single|png], default tiled. Tiled
                        mode produces a multi-page PDF with pages of the
                        requested size. Single mode produces a single PDF
                        exactly fitting the map, and PNG mode produces a lower
                        size PNG image suitable for virtual tabletops such as
                        Roll20
  -x PRESET, --preset PRESET
                        preset, overrides settings from presets within the
                        config file, available presets are [library|roll20]
```

Before this tool will work you will need to update the config which should now be in `~/.pathfinder/config.yaml`
with the appropriate paths to your `torch` and `waifu2x lua` files (on linux) or to the metal-based command
line tool on `macos` - the config should be self explanatory here (remove any leading underscores on property keys,
the default config is my setup on linux, if you're using a mac you'll want to change the `_mac` to `mac` and add
underscores to the linux paths)

You can either specify all options every time, or you can set up your own profiles. The ordering of priorities
will be:

1. Any property set in a profile
2. Any property explicitly set on the command line
3. Defaults from the config

So you can e.g. use the `roll20` profile but change the amount of lightening if you don't like the default, but
you can't change the output type as that's defined by the profile. The `library` profile is for the printer in my
local library, and the defaults for my CP1515n laserjet - yours may well be different!

When you print from the resultant PDFs, it's very important that you don't use any kind of `scale to page` function
as this will mess up the print sizes. Always print without any scaling applied, and use the padding setting in
this tool to make sure everything's within the printable area for your printer.

# Libraries  
  
## pathfinder.pydice

Library to model dice distributions, including an object
model for a distribution and a parser for standard format
strings. Also includes a higher level library to create
distributions for pathfinder damage calculations, rerolls 
and similar.

## pathfinder.pyfeats

Code to read in the feat descriptions from a public google
sheet, fix errors, then parse out into a DAG containing the
feats and dependencies, and render to graphviz dot format text.

* Requires GraphViz to actually render the graphs

## pathfinder.spells

Code to read in spell lists and generate data dumps containing
available spells for a given set of classes.