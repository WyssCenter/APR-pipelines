"""
Script for obtaining the stitching speed against computational ratio.

By using this code you agree to the terms of the software license agreement.

© Copyright 2020 Wyss Center for Bio and Neuro Engineering – All rights reserved
"""

import pipapr
from time import time
import os
from pathlib import Path
import numpy as np
from skimage.io import imsave
import pyapr
from glob import glob

# Parameters
output_folder_apr = r'/home/apr-benchmark/Desktop/data/synthetic'

#
folders = glob(os.path.join(output_folder_apr, '*/'))

elapsed_time = []
cr = []

for folder in folders:
    # Parse data
    tiles = pipapr.parser.tileParser(folder[:-1], frame_size=512, overlap=128, ftype='apr')

    # Stitch tiles
    stitcher = pipapr.stitcher.tileStitcher(tiles)
    t = time()
    stitcher.compute_registration_fast()
    elapsed_time.append(time()-t)

    tmp= []
    for tile in tiles:
        tile.load_tile()
        tmp.append(tile.apr.computational_ratio())
    cr.append(np.mean(tmp))

    print('CR {} - Elapsed time {} s.'.format(cr[-1], elapsed_time[-1]))


import matplotlib.pyplot as plt
plt.plot(cr, elapsed_time, 'k+', label='APR')
plt.plot([np.min(cr), np.max(cr)], [52, 52], 'r:', label='TeraStitcher multicore')
plt.xlabel('Computational ratio')
plt.ylabel('Stitching time [s.]')
plt.legend()
plt.xscale('log')