"""
Batch convert COLM acquisition to APR and arrange the data so that it can be processed by tilemanager.

By using this code you agree to the terms of the software license agreement.

© Copyright 2020 Wyss Center for Bio and Neuro Engineering – All rights reserved
"""

import numpy as np
import pyapr
from glob import glob
import os
from skimage.io import imread
from alive_progress import alive_bar
from time import time
import re
from pathlib import Path
from shutil import copyfile

def load_sequence(path):
    """
    Load a sequence of images in a folder and return it as a 3D array.
    """

    files = glob(os.path.join(path, '*tif'))
    n_files = len(files)
    u = imread(files[0])
    v = np.empty((n_files, *u.shape), dtype='uint16')
    v[0] = u
    files.pop(0)
    with alive_bar(n_files, force_tty=True) as bar:
        for i, f in enumerate(files):
            v[i+1] = imread(f)
            bar()

    return v

def sort_list(mylist):

    mylistsorted = list(range(len(mylist)))
    for i, pathname in enumerate(mylist):
        number_search = re.search('LOC0(\d+)', pathname[-10:])
        if number_search:
            n = int(number_search.group(1))
        else:
            raise TypeError('Couldn''t get the number')

        mylistsorted[n] = pathname
    return mylistsorted

# Parameters
data_path = r'/media/jules/ALICe_Ivana/LOC000_20210420_153304/VW0'
output_dir = r'/home/jules/Desktop/mouse_colm'
n_H = 10
n_V = 10
overlap = 2048 * 0.2

compress = True
par = pyapr.APRParameters()
par.rel_error = 0.2
par.gradient_smoothing = 3
par.dx = 1
par.dy = 1
par.dz = 1
par.Ip_th = 450
par.sigma_th = 95.0
par.grad_th = 15.0

folders = glob(os.path.join(data_path, 'LOC*'))
# folders = sort_list(folders)
loading = []
conversion = []
writing = []
for i, f in enumerate(folders):

    t = time()
    u = load_sequence(f)
    print('Loading took {:0.2f} s.'.format(time()-t))
    loading.append(time()-t)

    t = time()
    apr, parts = pyapr.converter.get_apr(u, params=par)
    print('Conversion took {:0.2f} s.'. format(time()-t))
    conversion.append(time()-t)

    if compress:
        parts.set_compression_type(1)
        parts.set_quantization_factor(1)
        parts.set_background(180)

    t = time()
    pyapr.io.write(os.path.join(output_dir, str(i) + '_compressed.apr'), apr, parts, write_tree=False)
    print('Writing took {:0.2f} s.'. format(time()-t))
    writing.append(time()-t)

    print(f)
    print(i)

# Rearange data in TeraStitcher style row and column folders
files_apr = glob(os.path.join(output_dir, '*apr'))
with alive_bar(len(files_apr), force_tty=True) as bar:
    for n, file_apr, f in zip(range(len(files_apr)), files_apr, folders):

        H = n % n_H
        V = n // n_V

        copyfile(file_apr, os.path.join(output_dir, 'multitile/{}_{}.apr'.format(V, H)))
        bar()

# Check on a small chunk that the data is correctly parsed and aligned
apr = []
parts = []
layers = []
from viewer.pyapr_napari import display_layers, apr_to_napari_Image
for i in [4,5,6,7]:
    apr.append(pyapr.APR())
    parts.append(pyapr.ShortParticles())
    pyapr.io.read('/home/jules/Desktop/mouse_colm/multitile/2_{}.apr'.format(i), apr[-1], parts[-1])
    position = [0, i*(2048*0.75)]
    layers.append(apr_to_napari_Image(apr[-1], parts[-1],
                                      mode='constant',
                                      translate=position,
                                      opacity=0.7,
                                      level_delta=0))

display_layers(layers)