"""
Script to try out napari

By using this code you agree to the terms of the software license agreement.

© Copyright 2020 Wyss Center for Bio and Neuro Engineering – All rights reserved
"""

from napari.layers import Image
import napari
import pyapr
from pipapr.viewer import tileViewer
from pipapr.parser import tileParser
import pandas as pd

def get_pyramid(apr, parts, n):
    p = []
    for i in range(n):
        p.append(pyapr.data_containers.APRSlicer(apr, parts, mode='constant', level_delta=-i))
    return p

# Parameters
path = '/mnt/Data/wholebrain/multitile/c1/apr'

# Load APR file
tiles = tileParser(path, frame_size=2048, overlap=512, ftype='apr')
database = pd.read_csv('/mnt/Data/wholebrain/multitile/c1/registration_results.csv')

# Display pyramidal file with Napari
viewer = tileViewer(tiles, database)
viewer.display_all_tiles_pyramid(4, contrast_limits=[0, 1000])