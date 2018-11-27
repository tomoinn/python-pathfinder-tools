from mapmaker import split_image, make_pdf

make_pdf(split_image(image_file='/home/tom/Desktop/pathfinder-images/out/out/Canyon_18x11.png', squares_wide=18,
                     squares_high=12, border=5), '/home/tom/Desktop/out.pdf')
