"""
Module containing classes and functions relative to Viewing.

By using this code you agree to the terms of the software license agreement.

© Copyright 2020 Wyss Center for Bio and Neuro Engineering – All rights reserved
"""

from glob import glob
import os
import pandas as pd
from skimage.io import imread
import numpy as np
import pyapr
import napari
from napari.layers import Image, Labels, Points
from pipapr.parser import tileParser
from pipapr.stitcher import tileStitcher
from pipapr.loader import tileLoader
from matplotlib.colors import LogNorm
import matplotlib.pyplot as plt

def apr_to_napari_Image(apr: pyapr.APR,
                        parts: (pyapr.ShortParticles, pyapr.FloatParticles),
                        mode: str = 'constant',
                        level_delta: int = 0,
                        **kwargs):
    """
    Construct a napari 'Image' layer from an APR. Pixel values are reconstructed on the fly via the APRSlicer class.

    Parameters
    ----------
    apr : pyapr.APR
        Input APR data structure
    parts : pyapr.FloatParticles or pyapr.ShortParticles
        Input particle intensities
    mode: str
        Interpolation mode to reconstruct pixel values. Supported values are
            constant:   piecewise constant interpolation
            smooth:     smooth interpolation (via level-adaptive separable smoothing). Note: significantly slower than constant.
            level:      interpolate the particle levels to the pixels
        (default: constant)
    level_delta: int
        Sets the resolution of the reconstruction. The size of the image domain is multiplied by a factor of 2**level_delta.
        Thus, a value of 0 corresponds to the original pixel image resolution, -1 halves the resolution and +1 doubles it.
        (default: 0)

    Returns
    -------
    out : napari.layers.Image
        An Image layer of the APR that can be viewed in napari.
    """
    if 'contrast_limits' in kwargs:
        contrast_limits = kwargs.get('contrast_limits')
        del kwargs['contrast_limits']
    else:
        cmin = apr.level_min() if mode == 'level' else parts.min()
        cmax = apr.level_max() if mode == 'level' else parts.max()
        contrast_limits = [cmin, cmax]
    par = apr.get_parameters()
    return Image(data=pyapr.data_containers.APRSlicer(apr, parts, mode=mode, level_delta=level_delta),
                 rgb=False, multiscale=False, contrast_limits=contrast_limits,
                 scale=[par.dz, par.dx, par.dy], **kwargs)


def apr_to_napari_Labels(apr: pyapr.APR,
                        parts: pyapr.ShortParticles,
                        mode: str = 'constant',
                        level_delta: int = 0,
                        **kwargs):
    """
    Construct a napari 'Layers' layer from an APR. Pixel values are reconstructed on the fly via the APRSlicer class.

    Parameters
    ----------
    apr : pyapr.APR
        Input APR data structure
    parts : pyapr.FloatParticles or pyapr.ShortParticles
        Input particle intensities
    mode: str
        Interpolation mode to reconstruct pixel values. Supported values are
            constant:   piecewise constant interpolation
            smooth:     smooth interpolation (via level-adaptive separable smoothing). Note: significantly slower than constant.
            level:      interpolate the particle levels to the pixels
        (default: constant)
    level_delta: int
        Sets the resolution of the reconstruction. The size of the image domain is multiplied by a factor of 2**level_delta.
        Thus, a value of 0 corresponds to the original pixel image resolution, -1 halves the resolution and +1 doubles it.
        (default: 0)

    Returns
    -------
    out : napari.layers.Image
        A Labels layer of the APR that can be viewed in napari.
    """
    if 'contrast_limits' in kwargs:
        del kwargs['contrast_limits']
    par = apr.get_parameters()
    return Labels(data=pyapr.data_containers.APRSlicer(apr, parts, mode=mode, level_delta=level_delta, tree_mode='max'),
                  multiscale=False, scale=[par.dz, par.dx, par.dy], **kwargs)


def display_layers(layers):
    """
    Display a list of layers using Napari.

    Parameters
    ----------
    layers: (list) list of layers to display

    Returns
    -------
    napari viewer.
    """
    with napari.gui_qt():
        viewer = napari.Viewer()
        for layer in layers:
            viewer.add_layer(layer)
    return viewer


def display_segmentation(apr, parts, mask):
    """
    This function displays an image and its associated segmentation map. It uses napari to lazily generate the pixel
    data from APR on the fly.

    Parameters
    ----------
    apr: (APR) apr object
    parts: (ParticleData) particle object representing the image
    mask: (ParticleData) particle object representing the segmentation mask/connected component

    Returns
    -------
    None
    """
    image_nap = apr_to_napari_Image(apr, parts, name='APR')
    mask_nap = apr_to_napari_Labels(apr, mask, name='Segmentation')

    with napari.gui_qt():
        viewer = napari.Viewer()
        viewer.add_layer(image_nap)
        viewer.add_layer(mask_nap)


def display_heatmap(heatmap, atlas=None, data=None, log=False):
    """
    Display a heatmap (e.g. cell density) that can be overlaid on intensity data and atlas.
    Parameters
    ----------
    heatmap: (np.array) array containing the heatmap to be displayed
    atlas: (np.array) array containing the atlas which will be automatically scaled to the heatmap
    data: (np.array) array containing the data.
    log: (bool) plot in logscale (only used for 2D).

    Returns
    -------
    None
    """

    # If u is 2D then use matplotlib so we have a scale bar
    if heatmap.ndim == 2:
        fig, ax = plt.subplots()
        if log:
            h = ax.imshow(heatmap, norm=LogNorm(), cmap='jet')
        else:
            h = ax.imshow(heatmap, cmap='jet')
        cbar = fig.colorbar(h, ax=ax)
        cbar.set_label('Number of detected cells')
        ax.set_xticks([])
        ax.set_yticks([])
    # If u is 3D then use napari but no colorbar for now
    elif heatmap.ndim == 3:
        with napari.gui_qt():
            viewer = napari.Viewer()
            viewer.add_image(heatmap, colormap='inferno', name='Heatmap', blending='additive', opacity=0.7)
            if atlas is not None:
                viewer.add_labels(atlas, name='Atlas regions', opacity=0.7)
            if data is not None:
                viewer.add_image(data, name='Intensity data', blending='additive',
                                 scale=np.array(heatmap.shape)/np.array(data.shape), opacity=0.7)


class tileViewer():
    """
    Class to display the registration and segmentation using Napari.
    """
    def __init__(self,
                 tiles: (tileParser),
                 database: (tileStitcher, pd.DataFrame, str),
                 segmentation: bool=False,
                 cells=None,
                 atlaser=None):
        """

        Parameters
        ----------
        tiles: (tileParser) tileParser object containing the dataset to be displayed.
        database: database containing the tile positions.
        segmentation: (bool) option to also display the segmentation (connected component) data.
        cells: (np.array) cells center to be displayed.
        atlaser: (tileAtlaser) tileAtlaser object containing the Atlas to be displayed.
        """

        self.tiles = tiles

        if isinstance(database, tileStitcher):
            self.database = database.database
        elif isinstance(database, pd.DataFrame):
            self.database = database
        elif isinstance(database, str):
            self.database = pd.read_csv(database)
        else:
            raise TypeError('Error: unknown type for database.')

        self.nrow = tiles.nrow
        self.ncol = tiles.ncol
        self.loaded_ind = []
        self.loaded_tiles = {}
        self.segmentation = segmentation
        self.loaded_segmentation = {}
        self.cells = cells
        self.atlaser = atlaser

    def get_layers_all_tiles(self, downsample=1, **kwargs):
        """
        Display all parsed tiles.

        Parameters
        ----------
        downsample: (int) downsampling parameter for APRSlicer
                            (1: full resolution, 2: 2x downsampling, 4: 4x downsampling..etc)
        kwargs: (dict) dictionary passed to Napari for custom option

        Returns
        -------
        None
        """

        # Compute layers to be displayed by Napari
        layers = []

        # Convert downsample to level delta
        level_delta = int(-np.sign(downsample)*np.log2(np.abs(downsample)))

        for t in self.tiles:
            tile = tileLoader(t)
            # Load tile if not loaded, else use cached tile
            ind = np.ravel_multi_index((tile.row, tile.col), dims=(self.nrow, self.ncol))
            if self._is_tile_loaded(tile.row, tile.col):
                apr, parts = self.loaded_tiles[ind]
                if self.segmentation:
                    mask = self.loaded_segmentation[ind]
            else:
                tile.load_tile()
                apr, parts = tile.data
                self.loaded_ind.append(ind)
                self.loaded_tiles[ind] = apr, parts
                if self.segmentation:
                    tile.load_segmentation()
                    apr, mask = tile.data_segmentation
                    self.loaded_segmentation[ind] = mask

            position = self._get_tile_position(tile.row, tile.col)
            if level_delta != 0:
                position = [x / level_delta ** 2 for x in position]
            layers.append(apr_to_napari_Image(apr, parts,
                                              mode='constant',
                                              name='Tile [{}, {}]'.format(tile.row, tile.col),
                                              translate=position,
                                              opacity=0.7,
                                              level_delta=level_delta,
                                              **kwargs))
            if self.segmentation:
                layers.append(apr_to_napari_Labels(apr, mask,
                                                   mode='constant',
                                                   name='Segmentation [{}, {}]'.format(tile.row, tile.col),
                                                   translate=position,
                                                   level_delta=level_delta,
                                                   opacity=0.7))
        if self.cells is not None:
            par = apr.get_parameters()
            layers.append(Points(self.cells, opacity=0.7, name='Cells center',
                                 scale=[par.dz/downsample, par.dx/downsample, par.dy/downsample]))

        if self.atlaser is not None:
            layers.append(Labels(self.atlaser.atlas, opacity=0.7, name='Atlas',
                                 scale=[self.atlaser.z_downsample/downsample,
                                        self.atlaser.y_downsample/downsample,
                                        self.atlaser.x_downsample/downsample]))

        return layers

    def display_all_tiles(self, downsample=1, **kwargs):
        """
        Display all parsed tiles.

        Parameters
        ----------
        downsample: (int) downsampling parameter for APRSlicer
                            (1: full resolution, 2: 2x downsampling, 4: 4x downsampling..etc)
        kwargs: (dict) dictionary passed to Napari for custom option

        Returns
        -------
        None
        """

        # Compute layers to be displayed by Napari
        layers = []

        # Convert downsample to level delta
        level_delta = int(-np.sign(downsample)*np.log2(np.abs(downsample)))

        for t in self.tiles:
            tile = tileLoader(t)
            # Load tile if not loaded, else use cached tile
            ind = np.ravel_multi_index((tile.row, tile.col), dims=(self.nrow, self.ncol))
            if self._is_tile_loaded(tile.row, tile.col):
                apr, parts = self.loaded_tiles[ind]
                if self.segmentation:
                    mask = self.loaded_segmentation[ind]
            else:
                tile.load_tile()
                apr, parts = tile.data
                self.loaded_ind.append(ind)
                self.loaded_tiles[ind] = apr, parts
                if self.segmentation:
                    tile.load_segmentation()
                    apr, mask = tile.data_segmentation
                    self.loaded_segmentation[ind] = mask

            position = self._get_tile_position(tile.row, tile.col)
            if level_delta != 0:
                position = [x / level_delta ** 2 for x in position]
            layers.append(apr_to_napari_Image(apr, parts,
                                              mode='constant',
                                              name='Tile [{}, {}]'.format(tile.row, tile.col),
                                              translate=position,
                                              opacity=0.7,
                                              level_delta=level_delta,
                                              **kwargs))
            if self.segmentation:
                layers.append(apr_to_napari_Labels(apr, mask,
                                                   mode='constant',
                                                   name='Segmentation [{}, {}]'.format(tile.row, tile.col),
                                                   translate=position,
                                                   level_delta=level_delta,
                                                   opacity=0.7))
        if self.cells is not None:
            par = apr.get_parameters()
            layers.append(Points(self.cells, opacity=0.7, name='Cells center',
                                 scale=[par.dz/downsample, par.dx/downsample, par.dy/downsample]))

        if self.atlaser is not None:
            layers.append(Labels(self.atlaser.atlas, opacity=0.7, name='Atlas',
                                 scale=[self.atlaser.z_downsample/downsample,
                                        self.atlaser.y_downsample/downsample,
                                        self.atlaser.x_downsample/downsample]))

        # Display layers
        display_layers(layers)

    def display_tiles(self, coords, downsample=1, **kwargs):
        """
        Display tiles only for coordinates specified in coords.

        Parameters
        ----------
        coords: (np.array) array containing the coords of tiles to be displayed.
        downsample: (int) downsampling parameter for APRSlicer
                            (1: full resolution, 2: 2x downsampling, 4: 4x downsampling..etc)
        kwargs: (dict) dictionary passed to Napari for custom option

        Returns
        -------
        None
        """
        # Check that coords is (n, 2) or (2, n)
        if coords.size == 2:
            coords = np.array(coords).reshape(1, 2)
        elif coords.shape[1] != 2:
            coords = coords.T
            if coords.shape[1] != 2:
                raise ValueError('Error, at least one dimension of coords should be of size 2.')

        # Convert downsample to level delta
        level_delta = int(-np.sign(downsample)*np.log2(np.abs(downsample)))

        # Compute layers to be displayed by Napari
        layers = []
        for i in range(coords.shape[0]):
            row = coords[i, 0]
            col = coords[i, 1]

            # Load tile if not loaded, else use cached tile
            ind = np.ravel_multi_index((row, col), dims=(self.nrow, self.ncol))
            if self._is_tile_loaded(row, col):
                apr, parts = self.loaded_tiles[ind]
                if self.segmentation:
                    mask = self.loaded_segmentation[ind]
            else:
                apr, parts = self._load_tile(row, col)
                self.loaded_ind.append(ind)
                self.loaded_tiles[ind] = apr, parts
                if self.segmentation:
                    apr, mask = self._load_segmentation(row, col)
                    self.loaded_segmentation[ind] = mask

            position = self._get_tile_position(row, col)
            if level_delta != 0:
                position = [x/level_delta**2 for x in position]
            layers.append(apr_to_napari_Image(apr, parts,
                                               mode='constant',
                                               name='Tile [{}, {}]'.format(row, col),
                                               translate=position,
                                               opacity=0.7,
                                               level_delta=level_delta,
                                               **kwargs))
            if self.segmentation:
                layers.append(apr_to_napari_Labels(apr, mask,
                                                  mode='constant',
                                                  name='Segmentation [{}, {}]'.format(row, col),
                                                  translate=position,
                                                  level_delta=level_delta,
                                                  opacity=0.7))
        if self.cells is not None:
            par = apr.get_parameters()
            layers.append(Points(self.cells, opacity=0.7, name='Cells center',
                                 scale=[par.dz/downsample, par.dx/downsample, par.dy/downsample]))

        if self.atlaser is not None:
            layers.append(Labels(self.atlaser.atlas, opacity=0.7, name='Atlas',
                                 scale=[self.atlaser.z_downsample/downsample,
                                        self.atlaser.y_downsample/downsample,
                                        self.atlaser.x_downsample/downsample]))

        # Display layers
        display_layers(layers)

    def _load_segmentation(self, row, col):
        """
        Load the segmentation for tile at position [row, col].
        """
        df = self.database
        path = df[(df['row'] == row) & (df['col'] == col)]['path'].values[0]
        apr = pyapr.APR()
        parts = pyapr.LongParticles()
        folder, filename = os.path.split(path)
        folder_seg = os.path.join(folder, 'segmentation')
        pyapr.io.read(os.path.join(folder_seg, filename[:-4] + '_segmentation.apr'), apr, parts)
        u = (apr, parts)
        return u

    def _is_tile_loaded(self, row, col):
        """
        Returns True is tile is loaded, False otherwise.
        """
        ind = np.ravel_multi_index((row, col), dims=(self.nrow, self.ncol))
        return ind in self.loaded_ind

    def _load_tile(self, row, col):
        """
        Load the tile at position [row, col].
        """
        df = self.database
        path = df[(df['row'] == row) & (df['col'] == col)]['path'].values[0]
        if self.tiles.type == 'tiff2D':
            files = glob(os.path.join(path, '*.tif'))
            im = imread(files[0])
            u = np.zeros((len(files), *im.shape))
            u[0] = im
            files.pop(0)
            for i, file in enumerate(files):
                u[i+1] = imread(file)
            return self._get_apr(u)
        elif self.tiles.type == 'tiff3D':
            u = imread(path)
            return self._get_apr(u)
        elif self.tiles.type == 'apr':
            apr = pyapr.APR()
            parts = pyapr.ShortParticles()
            pyapr.io.read(path, apr, parts)
            u = (apr, parts)
            return u
        else:
            raise TypeError('Error: image type {} not supported.'.format(self.type))

    def _get_tile_position(self, row, col):
        """
        Parse tile position in the database.
        """
        df = self.database
        tile_df = df[(df['row'] == row) & (df['col'] == col)]
        px = tile_df['ABS_H'].values[0]
        py = tile_df['ABS_V'].values[0]
        pz = tile_df['ABS_D'].values[0]

        return [pz, py, px]