import os
from glob import glob

import matplotlib.pyplot as plt

import pipapr
import numpy as np
import re

# def tile_number_to_row_col(nrow, ncol):
#     rows = []
#     cols = []
#     tile_pattern = np.zeros((nrow, ncol), dtype='uint16')
#     row = 0
#     wait = True
#     direction = 1
#     for i in range(nrow*ncol):
#         if i == 0:
#             rows.append(row)
#             cols.append(0)
#         else:
#             rows.append(row)
#             if wait:
#                 cols.append(cols[-1])
#             else:
#                 cols.append(cols[-1] + direction)
#
#         tile_pattern[rows[-1], cols[-1]] = i
#
#         if (cols[-1] == ncol-1) and not wait:
#             direction = -1
#             wait = True
#             row += 1
#         elif (cols[-1] == ncol-1) and wait:
#             wait = False
#         if (cols[-1] == 0) and not wait:
#             wait = True
#             direction = 1
#             row += 1
#         elif (cols[-1] == 0) and wait:
#             wait = False
#     return tile_pattern, rows, cols
#
# files = sorted(glob('/media/hbm/HDD_data/CS_lamy/full_apr/*.apr'), key= lambda x: int(re.findall('(\d+).apr', x)[-1]))
# tile_pattern, rows, cols = tile_number_to_row_col(nrow=17, ncol=13)
#
# for file, row, col in zip(files, rows, cols):
#     os.rename(file, os.path.join(os.path.dirname(file), '{}_{}'.format(row, col)))

tiles = pipapr.parser.tileParser('/media/hbm/HDD_data/CS_lamy/full_apr')
# converter = pipapr.converter.tileConverter(tiles)
# converter.batch_convert_to_apr(Ip_th=170, rel_error=0.2, lazy_loading=True, path='/media/hbm/HDD_data/CS_lamy/full_apr')

stitcher = pipapr.stitcher.tileStitcher(tiles, overlap_h=40, overlap_v=40)
stitcher.compute_expected_registration()

# viewer = pipapr.viewer.tileViewer(tiles, stitcher.database)
# viewer.check_stitching(blending='additive')

stitcher2 = pipapr.stitcher.tileStitcher(tiles, overlap_h=40, overlap_v=40)
stitcher2.set_overlap_margin(2)
# stitcher2.compute_registration_fast(on_disk=True)
stitcher2.compute_registration_from_max_projs()
# viewer = pipapr.viewer.tileViewer(tiles, stitcher2.database)
# viewer.check_stitching(blending='additive')

pipapr.viewer.compare_stitching(100, stitcher2, stitcher, downsample=4)
