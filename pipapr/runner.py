"""
Submodule containing classes and functions relative to the running pipeline.

By using this code you agree to the terms of the software license agreement.

© Copyright 2020 Wyss Center for Bio and Neuro Engineering – All rights reserved
"""

import re
from glob import glob
import os
import numpy as np
import pipapr
from time import sleep
import pyapr
from skimage.io import imread
from tqdm import tqdm
from pathlib import Path
import pandas as pd

class baseRunningPipeline():
    """
    Class to process tile on the fly during acquisition.
    """
    def __init__(self, path, nrow, ncol, n_channels=1, ftype='tiff3D'):
        """
        Constructor for the runningPipeline object.

        Parameters
        ----------
        path: string
            folder where the data will be acquired
        n_row: int
            number of row that will be acquired
        n_col: int
            number of col that will be acquired
        n_channels: int
            number of channels that will be acquired
        ftype: string
            type of data for each tile, can be 'tiff2D' or 'tiff3D'
        """

        # runningPipeline attributes
        self.path = path
        self.next_tile = [0, 0]
        self.frame_size = 2048
        self.tile_processed = 0
        self.nrow = nrow
        self.ncol = ncol
        self.n_tiles = nrow * ncol
        self.current_tile = None
        self.type = ftype
        self.n_channels = n_channels

        # Converter attributes
        self.converter = None
        self.lazy_loading = None
        self.compression = False
        self.bg = None
        self.quantization_factor = None
        self.folder_apr = None

        # Stitcher attributes
        self.stitcher = None
        self.overlap_h = None
        self.overlap_v = None
        self.n_vertex = None
        self.folder_max_projs = None

    def run(self):
        """
        Start the running pipeline. It is basically a loop waiting for each tile to be saved at the specified path.

        Returns
        -------
        None
        """

        while self.tile_processed < self.n_tiles:

            is_available, tile = self._is_new_tile_available()

            if is_available:

                print('New tile available: {}'.format(os.path.basename(tile.path)))

                tile.load_tile()

                # Convert tile
                if self.converter is not None:
                    self._convert_to_apr(tile)
                    self._check_conversion(tile)

                if self.stitcher is True:
                    self._pre_stitch(tile)

                self._update_next_tile()

                self.tile_processed += 1
            else:
                sleep(1)

    def set_compression(self, quantization_factor=1, bg=108):
        """
        Activate B3D compression for saving tiles.

        Parameters
        ----------
        quantization_factor: int
            quantization factor: the higher, the more compressed (refer to B3D paper for more detail).
        bg: int
            background value: any value below this threshold will be set to the background value. This helps
            save up space by having the same value for the background (refer to B3D paper for more details).

        Returns
        -------
        None
        """

        self.compression = True
        self.bg = bg
        self.quantization_factor = quantization_factor

    def deactivate_compression(self):
        """
        Deactivate B3D compression when saving particles.

        Returns
        -------
        None
        """

        self.compression = False
        self.bg = None
        self.quantization_factor = None

    def activate_conversion(self,
                             Ip_th=108,
                             rel_error=0.2,
                             gradient_smoothing=2,
                             dx=1,
                             dy=1,
                             dz=1,
                             lazy_loading=True):
        """
        Activate conversion for the running pipeline.

        Parameters
        ----------
        Ip_th: int
            Intensity threshold
        rel_error: float in [0, 1[
            relative error bound
        gradient_smoothing: (float)
            B-Spline smoothing parameter (typically between 0 (no smoothing) and 10 (LOTS of smoothing)
        dx: float
            PSF size in x, used to compute the gradient
        dy: float
            PSF size in y, used to compute the gradient
        dz: float
            PSF size in z, used to compute the gradient
        lazy_loading: bool
            if lazy_loading is true then the converter save mean tree particle which are necessary for lazy loading of
            the APR. It will require about 1/7 more storage.

        Returns
        -------
        None
        """

        # Store parameters
        self.lazy_loading = lazy_loading

        # Safely create folder to save apr data
        self.folder_apr = os.path.join(self.path, 'APR')
        Path(self.folder_apr).mkdir(parents=True, exist_ok=True)

        # Set parameters
        par = pyapr.APRParameters()
        par.Ip_th = Ip_th
        par.rel_error = rel_error
        par.dx = dx
        par.dy = dy
        par.dz = dz
        par.gradient_smoothing = gradient_smoothing
        par.auto_parameters = True

        # Create converter object
        self.converter = pyapr.converter.FloatConverter()
        self.converter.set_parameters(par)
        self.converter.verbose = True

    def activate_stitching(self,
                           overlap_h: (int, float),
                           overlap_v: (int, float),
                           ):

        self.overlap_h = overlap_h
        self.overlap_v = overlap_v
        self.stitcher = True

        # Safely create folder to save max projs
        self.folder_max_projs = os.path.join(self.path, 'max_projs')
        Path(self.folder_max_projs).mkdir(parents=True, exist_ok=True)

    # def _pre_stitch(self, tile):
    #
    #     # Max project current tile on the overlaping area.

    def _check_conversion(self, tile):
        """
        Checks that conversion is ok, if not it should keep the original data.

        Parameters
        ----------
        tile: runningTile
            tile object to try if conversion worked as expected using facy metrics.

        Returns
        -------
        None
        """

        conversion_ok = False

        # TODO: implement a way to check if conversion is ok.

        if conversion_ok:
            tile._erase_from_disk()

    def _convert_to_apr(self, tile):
        """
        Convert the given tile to APR.

        Parameters
        ----------
        tile: runningTile
            tile object to be converted to APR.

        Returns
        -------
        None
        """
        apr = pyapr.APR()
        parts = pyapr.ShortParticles()
        self.converter.get_apr(apr, tile.data)
        parts.sample_image(apr, tile.data)

        if self.compression:
            parts.set_compression_type(1)
            parts.set_quantization_factor(self.quantization_factor)
            parts.set_background(self.bg)

        if self.lazy_loading:
            tree_parts = pyapr.ShortParticles()
            pyapr.numerics.fill_tree_mean(apr, parts, tree_parts)
        else:
            tree_parts = None

        # Save converted data
        filename = '{}_{}.apr'.format(tile.row, tile.col)
        pyapr.io.write(os.path.join(self.folder_apr, 'ch{}'.format(tile.channel), filename),
                       apr, parts, tree_parts=tree_parts)

    def _is_new_tile_available(self):
        """
        Checks if a new tile is available for processing.

        Returns
        -------
        is_available: bool
            True if a new tile is available, False otherwise
        tile: runningTile
            tile object is available, None otherwise
        """

        path = glob(os.path.join(self.path, '{}_{}.tif'.format(self.next_tile[0], self.next_tile[1])))

        if path == []:
            return False, None
        if len(path) == 1:
            # Store current tile coordinate
            self.current_tile = [self.next_tile[0], self.next_tile[1]]

            path = path[0]
            tile = self._get_tile(path)

            return True, tile
        else:
            raise TypeError('Error: glob returned one than one file.')

    def _update_next_tile(self):
        """
        Update next tile coordinates given the expected pattern.

        Returns
        -------
        None
        """
        if self.current_tile[1] == self.n_col-1:
            self.next_tile = [self.current_tile[0]+1, 0]
        else:
            self.next_tile = [self.current_tile[0], self.current_tile[1]+1]

    def _get_tile(self, path):
        """
        Returns the tile at the given path.

        Parameters
        ----------
        path: string
            tile path

        Returns
        -------
        tile: runningTile
            tile object
        """

        row, col = self._get_row_col(path)
        channel = self._get_channel(path)

        return runningTile(path=path,
                            row=row,
                            col=col,
                            ftype=self.type,
                            neighbors=None,
                            neighbors_tot=None,
                            neighbors_path=None,
                            frame_size=2048,
                            folder_root=self.path,
                            channel=channel,
                            n_channels=self.n_channels)


class clearscopeRunningPipeline(baseRunningPipeline):

    def __init__(self, path, n_channels=1):

        # runningPipeline attributes
        self.path = os.path.join(path, '0001')
        self.acq_param = None
        self.nrow, self.ncol = self._parse_acquisition_settings()
        self.frame_size = 2048
        self.tile_processed = 0
        self.n_tiles = self.nrow * self.ncol
        self.type = 'clearscope'
        self.n_channels = n_channels
        self.buffer_tile_to_be_processed = []

        # Converter attributes
        self.converter = None
        self.lazy_loading = None
        self.compression = False
        self.bg = None
        self.quantization_factor = None
        self.folder_apr = None

        # Stitcher attributes
        self.stitcher = None
        self.overlap_h = None
        self.overlap_v = None
        self.n_vertex = None
        self.folder_max_projs = None

    def run(self):
        """
        Start the running pipeline. It is basically a loop waiting for each tile to be saved at the specified path.

        Returns
        -------
        None
        """

        while self.tile_processed < self.n_tiles:

            is_available, tile = self._is_new_tile_available()

            if is_available:

                print('New tile available: {}'.format(os.path.basename(tile.path)))

                tile.load_tile()

                # Convert tile
                if self.converter is not None:
                    self._convert_to_apr(tile)
                    self._check_conversion(tile)

                if self.stitcher is True:
                    self._pre_stitch(tile)

                self._update_next_tile()

                self.tile_processed += 1
                self.buffer_tile_to_be_processed.pop(0)
            else:
                sleep(1)

    def _parse_acquisition_settings(self):

        print('Waiting for AcquireSettings.txt file in {}'.
              format(os.path.join(self.path, '*_AcquireSettings.txt')))

        files = glob(os.path.join(self.path, '*_AcquireSettings.txt'))
        while files == []:
            sleep(1)
            files = glob(os.path.join(self.path, '0001', '*_AcquireSettings.txt'))

        path = files[0]
        print('File found: {}'.format(path))


        with open(path) as f:
            lines = f.readlines()

        self.acq_param = {}
        for l in lines:
            pattern_matched = re.match('^(\w*) = (.*)$', l)
            if pattern_matched is not None:
                if pattern_matched.group(2).isnumeric():
                    self.acq_param[pattern_matched.group(1)] = float(pattern_matched.group(2))
                elif pattern_matched.group(2) == 'True':
                    self.acq_param[pattern_matched.group(1)] = True
                elif pattern_matched.group(2) == 'False':
                    self.acq_param[pattern_matched.group(1)] = False
                else:
                    self.acq_param[pattern_matched.group(1)] = pattern_matched.group(2)

        nrow = self.acq_param['ScanGridY']
        ncol = self.acq_param['ScanGridY']
        n_planes = self.acq_param['StackDepths']
        return nrow, ncol

    def _is_new_tile_available(self):
        """
        Checks if a new tile is available for processing.

        Returns
        -------
        is_available: bool
            True if a new tile is available, False otherwise
        tile: runningTile
            tile object is available, None otherwise
        """

        paths = glob(os.path.join(self.path, '000000_*_*c/'))
        self.buffer_tile_to_be_processed.extend(paths)

        if self.buffer_tile_to_be_processed == []:
            return False, None
        elif len(paths) >= 1:
            # Store current tile coordinate
            path = paths[0]
            tile = self._get_tile(path)

            return True, tile

    def _get_row_col(self, path):
        """
        Get ClearScope tile row and col position given the tile number.

        Parameters
        ----------
        n: int
            ClearScope tile number

        Returns
        -------
        row: int
            row number
        col: int
            col number
        """

        pattern_search = re.findall('\d{6}_(\d{6})___\dc', path)

        if pattern_search != []:
            n = int(pattern_search[0])

        col = np.absolute(np.mod(n - self.ncol - 1, 2 * self.ncol) - self.ncol + 0.5) + 0.5
        row = np.ceil(n / self.ncol)

        col = int(col-1)
        row = int(row-1)

        return row, col

    def _get_channel(self, path):

        pattern_search = re.findall('\d{6}_\d{6}___(\d)c', path)

        if pattern_search != []:
            return int(pattern_search[0])


class runningTile():
    """
    Class to load each tile, neighboring tiles, segmentation and neighboring segmentation.

    Tile post processing is done on APR data, so if the input data is tiff it is first converted.
    """

    def __init__(self, path, row, col, ftype, neighbors, neighbors_tot, neighbors_path, frame_size, folder_root,
                 channel, n_channels):
        """
        Constructor for the runningTile class.

       Parameters
        ----------
        path: string
            path to the tile (APR and tiff3D) or the folder containing the frames (tiff2D)
        row: int
            vertical position of the tile (for multi-tile acquisition)
        col: int
            horizontal position of the tile (for multi-tile acquisition)
        ftype: str
            tile file type ('apr', 'tiff3D', 'tiff2D')
        neighbors: list
            neighbors list containing the neighbors position [row, col] of only the EAST and SOUTH
            neighbors to avoid the redundancy computation when stitching. For example, below the tile [0, 1] is
            represented by an 'o' while other tile are represented by an 'x'::

                            x --- o --- x --- x
                            |     |     |     |
                            x --- x --- x --- x
                            |     |     |     |
                            x --- x --- x --- x
                            |     |     |     |
                            x --- x --- x --- x

            in this case neighbors = [[0, 2], [1, 1]]

        neighbors_tot: list
            neighbors list containing all the neighbors position [row, col]. For example, below the
            tile [0, 1] is represented by an 'o' while other tile are represented by an 'x'::

                            x --- o --- x --- x
                            |     |     |     |
                            x --- x --- x --- x
                            |     |     |     |
                            x --- x --- x --- x
                            |     |     |     |
                            x --- x --- x --- x

            in this case neighbors_tot = [[0, 0], [0, 2], [1, 1]]
        neighbors_path: list
            path of the neighbors whose coordinates are stored in neighbors
        frame_size: int
            camera frame size (only square sensors are supported for now).
        folder_root: str
            root folder where everything should be saved.
        n_channels: int
            number of channels that will be acquired
        """
        self.path = path
        self.row = row
        self.col = col
        self.type = ftype
        self.neighbors = neighbors
        self.neighbors_tot = neighbors_tot
        self.neighbors_path = neighbors_path
        self.frame_size = frame_size
        self.folder_root = folder_root
        self.channel = channel
        self.n_channels = n_channels

        # Initialize attributes to load tile data
        self.data = None  # Pixel data
        self.apr = None  # APR tree
        self.parts = None  # Particles
        self.parts_cc = None  # Connected component
        self.lazy_data = None  # Lazy reconstructed data

        # Initialize attributes to load neighbors data
        self.data_neighbors = None
        self.apr_neighbors = None
        self.parts_neighbors = None
        self.parts_cc_neighbors = None

    def load_tile(self):
        """
        Load the current tile if not already loaded.

        Returns
        -------
        None
        """
        if self.type == 'apr':
            if self.apr is None:
                self.apr, self.parts = self._load_data(self.path)
        else:
            if self.data is None:
                self.data = self._load_data(self.path)

    def lazy_load_tile(self, level_delta=0):
        """
        Load the tile lazily at the given resolution.

        Parameters
        ----------
        level_delta: int
            parameter controlling the resolution at which the APR will be read lazily

        Returns
        -------
        None
        """

        if self.type != 'apr':
            raise TypeError('Error: lazy loading is only supported for APR data.')

        self.lazy_data = pyapr.data_containers.LazySlicer(self.path, level_delta=level_delta)

    def load_neighbors(self):
        """
        Load the current tile neighbors if not already loaded.

        Returns
        -------
        None
        """
        if self.data_neighbors is None:
            if self.type == 'apr':
                aprs = []
                partss = []
                for path_neighbor in self.neighbors_path:
                    apr, parts = self._load_data(path_neighbor)
                    aprs.append(apr)
                    partss.append(parts)
                self.apr_neighbors = aprs
                self.parts_neighbors = partss
            else:
                u = []
                for path_neighbor in self.neighbors_path:
                    u.append(self._load_data(path_neighbor))
                self.data_neighbors = u
        else:
            print('Tile neighbors already loaded.')

    def load_segmentation(self, load_tree=False):
        """
        Load the current tile connected component (cc) if not already loaded.

        Returns
        -------
        None
        """
        if self.parts_cc is None:
            cc = pyapr.LongParticles()
            aprfile = pyapr.io.APRFile()
            aprfile.set_read_write_tree(True)
            aprfile.open(self.path, 'READ')
            if load_tree:
                apr = pyapr.APR()
                aprfile.read_apr(apr, t=0, channel_name='t')
                self.apr = apr
            aprfile.read_particles(self.apr, 'segmentation cc', cc, t=0)
            aprfile.close()
            self.parts_cc = cc
        else:
            print('Tile cc already loaded.')

    def load_neighbors_segmentation(self, load_tree=False):
        """
        Load the current tile neighbors connected component (cc) if not already loaded.

        Returns
        -------
        None
        """
        if self.data_neighbors is None:
            if self.type == 'apr':
                aprs = []
                ccs = []
                for i, path_neighbor in enumerate(self.neighbors_path):
                    if not load_tree:
                        apr = self.apr_neighbors[i]
                    cc = pyapr.LongParticles()
                    aprfile = pyapr.io.APRFile()
                    aprfile.set_read_write_tree(True)
                    aprfile.open(path_neighbor, 'READ')
                    if load_tree:
                        apr = pyapr.APR()
                        aprfile.read_apr(apr, t=0, channel_name='t')
                    aprfile.read_particles(apr, 'segmentation cc', cc, t=0)
                    aprfile.close()
                    aprs.append(apr)
                    ccs.append(cc)
                self.apr_neighbors = aprs
                self.parts_neighbors = ccs

            else:
                u = []
                for path_neighbor in self.neighbors_path:
                    u.append(self._load_data(path_neighbor))
                self.data_neighbors = u
        else:
            print('Tile neighbors already loaded.')

    def _erase_from_disk(self):
        """
        Delete the pixel data

        Returns
        -------
        None
        """

        if self.type == 'tiff3D':
            os.remove(self.path)

    def _load_data(self, path):
        """
        Load data at given path.

        Parameters
        ----------
        path: string
            path to the data to be loaded.

        Returns
        -------
        u: array_like
            numpy array containing the data.
        """
        if self.type == 'colm':
            u = self._load_colm(path)
        elif self.type == 'clearscope':
            u = self._load_clearscope(path)
        elif self.type == 'tiff3D':
            u = imread(path)
        elif self.type == 'apr':
            apr = pyapr.APR()
            parts = pyapr.ShortParticles()
            pyapr.io.read(path, apr, parts)
            u = (apr, parts)
        elif self.type == 'raw':
            u = self._load_raw(path)
        else:
            raise TypeError('Error: image type {} not supported.'.format(self.type))
        return u

    def _load_raw(self, path):
        """
        Load raw data at given path.

        Parameters
        ----------
        path: string
            path to the data to be loaded.

        Returns
        -------
        u: array_like
            numpy array containing the data.
        """
        u = np.fromfile(path, dtype='uint16', count=-1)
        return u.reshape((-1, self.frame_size, self.frame_size))

    def _load_colm(self, path):
        """
        Load a sequence of images in a folder and return it as a 3D array.

        Parameters
        ----------
        path: string
            path to folder where the data should be loaded.

        Returns
        -------
        v: array_like
            numpy array containing the data.
        """
        files_sorted = sorted(glob(os.path.join(path, '*CHN0' + str(self.channel) + '_*tif')))
        n_files = len(files_sorted)
        v = np.empty((n_files, self.frame_size, self.frame_size), dtype='uint16')
        for i, f in enumerate(tqdm(files_sorted, desc='Loading sequence', leave=False)):
            v[i] = imread(f)
        return v

    def _load_clearscope(self, path):
        """
        Load a sequence of images in a folder and return it as a 3D array.

        Parameters
        ----------
        path: string
            path to folder where the data should be loaded.

        Returns
        -------
        v: array_like
            numpy array containing the data.
        """
        files_sorted = sorted(glob(os.path.join(self.path, '*')))
        n_files = len(files_sorted)
        v = np.empty((n_files, self.frame_size, self.frame_size), dtype='uint16')
        for i, f in enumerate(tqdm(files_sorted, desc='Loading sequence', leave=False)):
            v[i] = imread(f)

        return v