# Create a big stitcher file from a scan
# with a LaVision Biotec Ultramicroscope (SPIM)
#
# License BSD-3
# Volker
# .Hilsenstein @ monash
# .edu

import re
import pathlib
import numpy as np
import pandas as pd
import time
import npy2bdv
import skimage.io
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from typing import Union, List, Dict
import tifffile
import warnings


def readstack(files: List[str], convertto=None) -> np.ndarray:
    """Reads list of files as stack (using multiple Threads) with optional typeconversion
    
    Parameters
    ----------
    files : List[str]
        list of filenames
    convertto : [type], optional
        type to convert to, by default None
    
    Returns
    -------
    np.ndarray
        stack that has been read
    """

    def _imread(input):
        print(f"reading {input}")
        tmp = tifffile.imread(input, multifile=False)

        print(tmp.shape)
        if convertto is not None:
            return tmp.astype(convertto)
        else:
            return tmp

    with ThreadPoolExecutor() as p:
        images = list(p.map(_imread, files))
    return np.array(images)


def conv_strvector_to_np(strvalue: str) -> np.ndarray:
    """converts a string vector such as '(12.0, 13.0, 14.0)' into 
       a numpy array. To be used as a converter function with 
     np.read_csv
    """
    strvalue = re.sub("[\[\]\(\)]", "", strvalue)
    npar = np.fromstring(strvalue, sep=",", dtype=np.float)
    return npar


class um_mosaic_folder:
    def __init__(self, foldername: Union[pathlib.Path, str], regexes: Dict[str, str]):
        """init ultramicroscope mosaic folder object
        
        Parameters
        ----------
        foldername : str or pathlib.Path
            Folder of Ultramicroscope images to be processed
        regexes : Dict[str:str]
            Dictionary of regular expression strings used to
            filter the files and extract metadata from the filenames

            The following keys are expected:
            'filewhitelist' files to be considered must match this regular expression, e.g. '.*.tif'
            'Z' regular expression to extract Z slice number
            'ch' regular expression to extract channel number
            'illu' regular expression to extract illumination direction
        """
        # Take the provided foldername and anlyze the contents
        self.umpath = pathlib.Path(foldername)
        self.regexes = regexes
        assert self.umpath.exists
        self.update()

    def update(self):
        self._read_tile_info()
        self._find_imfiles()

    def _find_imfiles(self):
        """ looks for all files in self.umpath 

        filters files to retain those that match "filewhitelist" from self.regexes

        Uses the other regexes  in self.regexes to populate metadata 
        """
        self.tiffiles = list(self.umpath.glob("*"))
        regex = re.compile(self.regexes["filewhitelist"])
        self.tiffiles = list(filter(regex.search, map(str, self.tiffiles)))
        self.df = pd.DataFrame(self.tiffiles, columns=["pathname"])
        self.df["filename"] = self.df["pathname"].apply(lambda f: pathlib.Path(f).name)

        def _extract_first_match_with_regex(regex, teststring):
            try:
                return regex.findall(teststring)[0]
            except:
                print(f"{regex} did not match {teststring}")
                return ""

        for regexname in self.regexes.keys():
            if regexname != "filewhitelist":
                print(f"Applying regex {regexname} to filenames.")
                regex = re.compile(self.regexes[regexname])
                _extract = partial(_extract_first_match_with_regex, regex)
                self.df[regexname] = self.df["filename"].apply(_extract)
        # for column in ["Z","ch"]:
        #    self.df[column] = pd.to_numeric(self.df[column])

        self.df = pd.merge(self.df, self.tiles, on="filename")

        # In order to identify Z-stacks we add a column with the filename of the first Z slice
        unique_z = self.df["Z"].unique()
        print(unique_z)
        # numeric_unique_z  = list(map(int, unique_z))
        unique_z = sorted(unique_z, key=int)
        print(f"first z slice is {unique_z[0]}")
        _replacer = partial(re.sub, self.regexes["Z"], unique_z[0])
        self.df["first_Z"] = self.df["filename"].apply(_replacer)

        self.df["Znumeric"] = self.df["Z"].apply(int)
        self.df = self.df.sort_values("Znumeric")
        print(self.df)
        print(f'nr of unique Z: {len(self.df["Z"].unique())}')
        print(f'nr of unique Illu: {len(self.df["illu"].unique())}')
        print(f'nr of uniqu ch: {len(self.df["ch"].unique())}')

    def _read_tile_info(self):
        tilefile = self.umpath / "tiles.txt"
        # print(str(tilefile))
        if tilefile.exists():
            print("Trying to read tiles.txt file")
            self.tiles = pd.read_csv(
                str(tilefile),
                sep=";",
                skiprows=[0],
                names=["filename", "unknown", "stagexyz"],
                converters={"stagexyz": conv_strvector_to_np},
            )
        else:
            print("Error: Tiles.txt not found. That file should have been produced"
                    "by the microscope software and contains the stage positions")
            exit(-1)

    def _generate_project_folder(self, basefolder: str, projtype: str):
        projectfolder = pathlib.Path(basefolder) / pathlib.Path(projtype)
        projectfolder.mkdir(parents=True, exist_ok=True)
        return str(projectfolder / "dataset.h5")

    def generate_big_stitcher(
        self,
        outfolder_base: str,
        projected: bool = True,
        volume: bool = True,
        xyspacing: float = 1.0,
        zspacing: float = 1.0,
        project_func=np.max,
        direction_x: int = 1,
        direction_y: int = -1,
    ):
        """Generate a big stitcher project (.xml/h5)
        
        Parameters
        ----------
        outfolder_base : str
            base folder for the output
        projected : bool, optional
            if True, create a project based on z-projected tiles, by default True
        volume : bool, optional
            if True create a project for the full volumes, by default True
        xyspacing : float, optional
            pixel spacing in x/y in um/pix, by default 1.0
        zspacing : float, optional
            pixel spacing in z in um/pix, by default 1.0
        project_func : [type], optional
            projection function for z-stacks if projected, by default np.max
        direction_x : int, optional
            can be used to flip coordinate axes should be 1 or -1, by default 1
        direction_y : int, optional
            as above, by default -1
        """

        if not (projected or volume):
            print("Neither 2D nor 3D project generation selected. Nothing to do.")
            return

        assert len(self.df) > 0, "No files found"
        print(f"Zspacing: {zspacing}")
        print(f"XYspacing: {xyspacing}")

        # get unique channels and illuminations
        # the index into these lists will be used to identify the dataset
        channels = list(
            map(str, self.df["ch"].unique())
        )  # converting to string fixes problems with nan
        illuminations = list(map(str, self.df["illu"].unique()))

        # Group by stack
        grouped_stacks = self.df.groupby("first_Z")
        ntiles: int = len(grouped_stacks)
        nchannels: int = len(channels)
        nillu: int = len(illuminations)
        print(f"Processing {ntiles} tiles.")
        affine_matrix_template = np.array(
            ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0))
        )

        if projected:
            h5_proj_name: str = self._generate_project_folder(outfolder_base, "projected")
            bdv_proj_writer = npy2bdv.BdvWriter(
                h5_proj_name,
                nchannels=nchannels,
                nilluminations=nillu,
                ntiles=ntiles,
                subsamp=((1, 1, 1), (1, 2, 2), (1, 4, 4), (1, 8, 8), (1, 16, 16)),
                blockdim=((1, 64, 64),),
                compression="gzip",
            )

        if volume:
            h5_vol_name: str = self._generate_project_folder(outfolder_base, "volume")
            bdv_vol_writer = npy2bdv.BdvWriter(
                h5_vol_name,
                nchannels=nchannels,
                nilluminations=nillu,
                ntiles=ntiles,
                subsamp=(
                    (1, 1, 1),
                    (1, 2, 2),
                    (1, 4, 4),
                    (1, 8, 8),
                    (2, 16, 16),
                    (4, 32, 32),
                ),
                blockdim=(
                    (64, 64, 64),
                    (64, 64, 64),
                    (64, 64, 64),
                    (64, 64, 64),
                    (32, 32, 32),
                    (16, 16, 16),
                ),
                compression="gzip",
            )

        for tile_nr, (grname, group) in enumerate(grouped_stacks):
            print(f"Processing {tile_nr+1} out of {ntiles}:")
            stack = readstack(group["pathname"].values, convertto=np.int16)

            print("finished reading stack")
            xyz = group["stagexyz"].values[0]
            print(f"xyz is {xyz}")
            affine = affine_matrix_template.copy()

            # Explanation for formula below:
            # Stage position in metadata appears to be in units of metres (m)
            # PhysicalSize appears to be micrometers per voxel (um/vox)
            # therefore for the stageposition in voxel coordinates we need to
            # scale from meters to um (factor 1000000) and then divide by um/vox
            # the direction vectors should be either 1 or -1 and can be used
            # to flip the direction of the coordinate axes.
            affine[1, 3] = xyz[1] / xyspacing * direction_y
            affine[0, 3] = xyz[0] / xyspacing * direction_x

            ch = str(group["ch"].values[0])
            illu = str(group["illu"].values[0])
            ch_index = channels.index(ch)
            illu_index = illuminations.index(illu)

            if volume:
                bdv_vol_writer.append_view(
                    stack,
                    time=0,
                    channel=ch_index,
                    illumination=illu_index,
                    m_affine=affine,
                    tile=tile_nr,
                    name_affine=f"tile {tile_nr} translation",
                    voxel_size_xyz=(xyspacing, xyspacing, zspacing),
                    voxel_units="um",
                    calibration=(1, 1, zspacing / xyspacing),
                )
            if projected:
                outstack = np.expand_dims(project_func(stack, axis=0), axis=0)
                bdv_proj_writer.append_view(
                    outstack,
                    time=0,
                    channel=ch_index,
                    illumination=illu_index,
                    m_affine=affine,
                    tile=tile_nr,
                    name_affine=f"proj. tile {tile_nr} translation",
                    # Projections are inherently 2D, so we just repeat the X voxel size for Z
                    voxel_size_xyz=(xyspacing, xyspacing, xyspacing),
                    voxel_units="um",
                    # calibration=(1, 1, 1),
                )

        if projected:
            bdv_proj_writer.write_xml_file(ntimes=1)
            bdv_proj_writer.close()
        if volume:
            bdv_vol_writer.write_xml_file(ntimes=1)
            bdv_vol_writer.close()
