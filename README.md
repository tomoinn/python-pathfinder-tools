# python-pathfinder-tools

A set of utilities to do things related to the 
Pathfinder tabletop role playing game. These tools are really intended 
for those already comfortable with Python, they may also have external
dependencies. Tested on linux and MacOS.

Requires Python3.7 upwards.

## chronicle

Utilities to extract and populate chronicle sheets from PFS scenario PDFs,
as our group has had to move to online games with the virus outbreak and
we still need a way to distribute chronicle sheets to players afterwards.

## pydice

Library to model dice distributions, including an object
model for a distribution and a parser for standard format
strings. Also includes a higher level library to create
distributions for pathfinder damage calculations, rerolls 
and similar.

## pyfeats

Code to read in the feat descriptions from a public google
sheet, fix errors, then parse out into a DAG containing the
feats and dependencies, and render to graphviz dot format text.

* Requires GraphViz to actually render the graphs

## mapmaker

Tools to plumb together the various command line utilities needed
to extract map images from scenario PDFs, enhance and upscale 
them, and then slice up and emit printable PDF tiles at the correct
scale for tabletop battle mats.

* Requires the pdfimages tool from poppler-utils to extract images
  from scenario PDFs (install with apt or brew)
* Requires waifu2x to do smart upscaling, although if it's not present
  the tools will still run at lower quality. On linux you'll need
  to install torch, have a CUDA compatible GPU, and build waifu2x. On
  MacOS there's a port to use the metal API, it can be downloaded from
  https://github.com/imxieyi/waifu2x-mac/releases