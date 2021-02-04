# Python-pathfinder-tools v0.4.2

A set of utilities to do things related to the 
Pathfinder tabletop role playing game. These tools are really intended 
for those already comfortable with Python, they may also have external
dependencies. Tested on linux, MacOS and Win10. Note that CUDA GPU acceleration is only available for Nvidia GPUs, and
unless you build Torch from source yourself, only available on linux and Win10. This library will work on MacOS, but
the super-resolution upscaling for map images will be much slower (go make yourself a cup of tea while it thinks about
everything!)

There are some command-line tools, and some utility libraries you could use
to write your own tools if you were so minded.

To run from github directly do:

```
> git checkout https://github.com/tomoinn/python-pathfinder-tools.git
> cd python-pathfinder-tools/src/python
> python3 setup.py install
```

Alternatively install with `pip3 install python-pathfinder-tools`

Requires Python3.8 upwards, use a virtual environment by preference, although it'll probably
work without one.

# Installation under Windows

The tools here will run under Win10 and Python3.8

1. Get Python3.8 from https://www.python.org/ftp/python/3.8.7/python-3.8.7-amd64.exe, run the installer and make sure you
   enable the **add to path** option
2. If you have an Nvidia GPU, make sure you've updated your graphics card drivers to the current version
3. Open a terminal window (regular CMD or PowerShell, doesn't really matter)
4. Run this command to install the GPU accelerated libraries used when upscaling (if you don't have a compatible GPU this
   will still work, but you obviously won't gain any performance boosts) - this is all on one line, make sure you don't
   split it:

```
pip install torch===1.7.1+cu110 torchvision===0.8.2+cu110 -f https://download.pytorch.org/whl/torch_stable.html
```

5. Next install the pathfinder tools library:

```bash
pip install python-pathfinder-tools
```

6. You should now be able to run the `pfs_extract`, `pfs_grid`, and `pfs_build_maps` tools to generate upscaled
   maps from scenario PDFs, and the `pfs_sheets` tool to build chronicle sheets for your players after the game. See
   the docs below for more details on running and configuring these tools.
   
# Installation under Linux

1. Get Python3.8 from your normal software source. Ensure that `pip` as used below is using this installation - I tend to
   use a virtual environment here, but you don't have to.
2. Install Nvidia drivers if available and appropriate
3. Use `pip` to install the appropriate version of torch:

```bash
pip install torch==1.7.1+cu110 torchvision==0.8.2+cu110 -f https://download.pytorch.org/whl/torch_stable.html
```

4. Install the pathfinder tools

```bash
pip install python-pathfinder-tools
```

5. You should now be able to run the `pfs_extract`, `pfs_grid`, and `pfs_build_maps` tools to generate upscaled
   maps from scenario PDFs, and the `pfs_sheets` tool to build chronicle sheets for your players after the game. See
   the docs below for more details on running and configuring these tools.

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

* Ideally requires a CUDA compatible GPU and the associated CUDA installation,
  but can revert to CPU only for scaling if that's not available
  
### Usage

This is a three-stage process. Firstly you run `pfs_extract` to pull images that look like they might be maps,
as well as any other large images (it's nice to have these for characters and scenes especially if you're using
a virtual tabletop). Secondly you go through the output, removing any duplicates, files that aren't maps, and 
renaming anything you want to use as a map. 

You can then either manually rename map images to e.g. `canyon_25x30.png`, or run the `pfs_grid` tool to calculate
sizes interactively. The UI for this is pretty basic, but it shows each file in a directory in turn and prompts
for mouse clicks on the NW of a grid square at the top left of the image, then the SE corner of that square, and
finally another grid intersection on the bottom right of the map. It'll attempt to work out the size, and crop to
whole squares, but you might need to re-run the tool a few times to get it exactly right.

Finally you run the `pfs_build_maps` tool which scans a directory for images with the right name pattern, scales 
and de-noises, does some basic image processing operations, and packages them into your choice of output format.

Extract images with `pfs_extract`:

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

Either manually rename, or run `pfs_grid`:

```
> pfs_grid -h
usage: pfs_grid [-h] input_dir [output_dir]

positional arguments:
  input_dir   search INPUT_DIR for map images of form NAME.png
  output_dir  write images to OUTPUT_DIR, will be created if not found. 
              If not supplied, will use INPUT_DIR

optional arguments:
  -h, --help  show this help message and exit
```

Then run `pfs_build_maps` to generate scaled images or PDFs from these files:

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
  -g GRIDSIZE, --gridsize GRIDSIZE
                        target size in pixels of a grid square, defaults to 120
                        for print, and 60 for screen use i.e. roll20
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

## pathfinder.sessions

Code to handle the horrible format of Paizo's organised play session
list pages and pull out the information from them.