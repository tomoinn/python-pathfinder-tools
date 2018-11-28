import logging

import mapmaker

# Enable INFO level logging to see what's happening
logging.basicConfig(level=logging.INFO)

# If you have a working installation of waifu2x / Torch / CUDA specify it here. If these are not set then no
# upscaling will be applied. If these do not exist then, again, no upscaling will be applied.
mapmaker.WAIFU2X_LUA_PATH = '/home/tom/git/waifu2x/waifu2x.lua'
mapmaker.TORCH_PATH = '/home/tom/torch/install/bin/th'

# Pull map images out of the scenario PDF. It's sometimes necessary to check whether the image is actually
# rotated in the PDF file in order to get the right number of squares for the split_image call.
# In this example, extract maps from page 18 of the 'Fugitive on the Red Planet' Starfinder scenario, they're both about
# 20 squares high so we can specify that and not worry about the width at all.
for index, image in enumerate(
        mapmaker.extract_images_from_pdf(pdf_filename='/home/tom/Desktop/mars.pdf', min_height=100, page=18)):
    # Run waifu2x twice - if waifu2x isn't configured this won't fail, but it won't do anything either
    image = mapmaker.run_waifu2x(image, scale=True, noise=1)
    image = mapmaker.run_waifu2x(image, scale=True, noise=None)
    # Split image up into a number of tiles
    split = mapmaker.split_image(im=image, squares_wide=1, squares_high=20, border=5, brighten=1.2, sharpen=1.1,
                                 saturation=None)
    # Take the tiles from the previous step and write them out to a PDF file
    mapmaker.make_pdf(split, '/home/tom/Desktop/out-{}.pdf'.format(index))
